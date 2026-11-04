"""A failed native request must not borrow the actor's later wandering as proof."""
import re
import unittest

from fo4sf.combined import probes
from tests.test_combined_probes import col, p9_log


def request(*, result=None, after=1.0, offset=0.0, **kwargs):
    lines = p9_log(**kwargs)
    lines = [re.sub(r"rt=([0-9.]+)", lambda m: f"rt={float(m[1]) + offset:.1f}", line) for line in lines]
    start = next(i for i, line in enumerate(lines) if " p9 start " in line)
    distance = kwargs.get("start", 450.0)
    origin = offset + 1.5
    lines.insert(start + 1, f"FOCC rt={origin} p9 go actor=-16711680 call={origin} target=dest "
                 f"id=50333723 dist={distance}")
    if result is not None:
        returned = f"FOCC rt={origin + after} p9 path returned actor=-16711680 call={origin} " \
                   f"target=dest result={result} after={after} dist={distance}"
        at = next((i for i in range(start + 2, len(lines))
                   if float(re.search(r"rt=([0-9.]+)", lines[i])[1]) > origin + after), len(lines))
        lines.insert(at, returned)
    return lines


class P9PathResultTests(unittest.TestCase):
    def test_non_success_then_wandering_cannot_pass(self):
        for code in (1, 2, 3, 4, 99):
            with self.subTest(code=code):
                verdict = probes.check_p9(col(log=request(result=code)))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())
                self.assertEqual(verdict.extra["attempts"][-1]["path_result"], code)

    def test_malformed_result_is_not_a_legacy_missing_result(self):
        for value in (-1, 1.5, "bogus", "nan", "inf", ""):
            with self.subTest(value=value):
                verdict = probes.check_p9(col(log=request(result=value)))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())
                self.assertFalse(verdict.extra["attempts"][-1]["path_succeeded"])
                if value in (1.5, "bogus", "nan", "inf", ""):
                    self.assertTrue(any("invalid result=" in reason for reason in verdict.reasons), verdict.to_dict())

    def test_failed_short_control_cannot_validate_a_later_stall(self):
        base = p9_log(start=20.0, speed=0.0, seconds=60)
        stalled = request(speed=0.0, offset=200.0)
        for result in (1, 2, 3, 4, 99, "bogus"):
            with self.subTest(result=result):
                control = request(start=20.0, seconds=60, result=result, offset=100.0)
                verdict = probes.check_p9(col(log=base + control[1:] + stalled[1:]))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())

    def test_wandering_after_failure_cannot_prove_the_driver_for_a_stall(self):
        for result in (0, 1, 2, 3, 4, 99, "bogus"):
            with self.subTest(result=result):
                verdict = probes.check_p9(col(log=request(result=result, stuck_from=100)))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())
                self.assertEqual(verdict.extra["attempts"][-1]["command_approach_m"], 0.0)

    def test_movement_before_failure_still_supports_a_stall_finding(self):
        verdict = probes.check_p9(col(log=request(result=1, after=240.0, stuck_from=100)))
        self.assertEqual(verdict.verdict, probes.FAIL, verdict.to_dict())

    def test_success_cannot_borrow_an_arrival_after_its_return(self):
        for after in (1.0, 220.0):
            with self.subTest(after=after):
                verdict = probes.check_p9(col(log=request(result=0, after=after)))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())
                self.assertFalse(verdict.extra["attempts"][-1]["arrived"])
        # The sample at exactly the return time belongs to the request.
        self.assertEqual(probes.check_p9(col(log=request(result=0, after=222.0))).verdict, probes.PASS)

    def test_success_control_cannot_borrow_an_arrival_after_its_return(self):
        base = p9_log(start=20.0, speed=0.0, seconds=60)
        control = request(start=20.0, seconds=60, result=0, after=1.0, offset=100.0)
        stalled = request(speed=0.0, offset=200.0)
        verdict = probes.check_p9(col(log=base + control[1:] + stalled[1:]))
        self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())

    def test_interrupted_or_invalid_return_cannot_prove_a_navmesh_failure(self):
        for result in (0, 2, 3, 4, 99, -1, 1.5, "bogus", "nan", "inf"):
            with self.subTest(result=result):
                verdict = probes.check_p9(col(log=request(result=result, after=240.0, stuck_from=100)))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())

    def test_control_does_not_turn_an_interrupted_request_into_a_navmesh_failure(self):
        base = p9_log(start=20.0, speed=0.0, seconds=60)
        control = request(start=20.0, seconds=60, result=0, after=8.0, offset=100.0)
        for result in (1, 2, 3, 4, 99, "bogus"):
            with self.subTest(result=result):
                stalled = request(speed=0.0, offset=200.0, result=result, after=240.0)
                verdict = probes.check_p9(col(log=base + control[1:] + stalled[1:]))
                self.assertEqual(verdict.verdict, probes.FAIL if result == 1 else probes.INCONCLUSIVE,
                                 verdict.to_dict())

    def test_malformed_after_does_not_hide_the_return_code(self):
        lines = [line.replace("after=1.0", "after=bogus") for line in request(start=22.0, result=1)]
        verdict = probes.check_p9(col(log=lines))
        self.assertEqual(verdict.verdict, probes.INCONCLUSIVE)
        self.assertTrue(any("Failure" in reason for reason in verdict.reasons), verdict.to_dict())

    def test_invalid_return_time_cannot_borrow_later_movement(self):
        for stamp in ("", "rt=nan", "rt=bogus"):
            with self.subTest(stamp=stamp):
                lines = [re.sub(r"rt=\S+", stamp, line, count=1) if " path returned " in line else line
                         for line in request(result=0, after=222.0)]
                verdict = probes.check_p9(col(log=lines))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())

    def test_invalid_actor_state_refuses_a_pathing_verdict(self):
        good = {"loaded": "True", "dead": "False", "disabled": "False", "targetdisabled": "False"}
        for key, value in (("loaded", "False"), ("dead", "True"), ("disabled", "True"),
                           ("targetdisabled", "True"), ("loaded", "bogus")):
            with self.subTest(key=key, value=value):
                lines = request(result=1, after=240.0, stuck_from=100)
                at = next(i for i, line in enumerate(lines) if " p9 go " in line)
                fields = good | {key: value}
                lines.insert(at, "FOCC rt=1.5 p9 state actor=-16711680 " +
                             " ".join(f"{k}={v}" for k, v in fields.items()))
                verdict = probes.check_p9(col(log=lines))
                self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())

        lines = request(result=1, after=240.0, stuck_from=100)
        at = next(i for i, line in enumerate(lines) if " p9 go " in line)
        lines.insert(at, "FOCC rt=1.5 p9 state actor=-16711680 " +
                     " ".join(f"{k}={v}" for k, v in good.items()))
        self.assertEqual(probes.check_p9(col(log=lines)).verdict, probes.FAIL)

    def test_invalid_state_control_cannot_qualify_a_later_stall(self):
        base = p9_log(start=20.0, speed=0.0, seconds=60)
        control = request(start=20.0, seconds=60, result=0, after=8.0, offset=100.0)
        at = next(i for i, line in enumerate(control) if " p9 go " in line)
        control.insert(at, "FOCC rt=101.5 p9 state actor=-16711680 loaded=True dead=True "
                       "disabled=False targetdisabled=False")
        stalled = request(speed=0.0, offset=200.0)
        verdict = probes.check_p9(col(log=base + control[1:] + stalled[1:]))
        self.assertEqual(verdict.verdict, probes.INCONCLUSIVE, verdict.to_dict())

    def test_success_and_legacy_missing_return_keep_their_route_results(self):
        for result in (0, None):
            with self.subTest(result=result):
                verdict = probes.check_p9(col(log=request(result=result, after=222.0)))
                self.assertEqual(verdict.verdict, probes.PASS, verdict.to_dict())
        old_driver = [line.replace(" result=0", "") for line in request(result=0, after=222.0)]
        verdict = probes.check_p9(col(log=old_driver))
        self.assertEqual(verdict.verdict, probes.PASS, verdict.to_dict())
        self.assertIsNone(verdict.extra["attempts"][-1]["path_succeeded"])

    def test_short_control_reports_the_native_failure_without_a_long_route_verdict(self):
        verdict = probes.check_p9(col(log=request(start=22.0, speed=0.0, seconds=60, result=1)))
        self.assertEqual(verdict.verdict, probes.INCONCLUSIVE)
        self.assertTrue(any("Failure" in reason and "PathToReference" in reason
                            for reason in verdict.reasons), verdict.to_dict())


if __name__ == "__main__":
    unittest.main()
