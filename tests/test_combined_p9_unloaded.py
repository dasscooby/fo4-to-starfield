"""P9u, the owner's design (1 Nov 2026): the player stays at the start, the actor is spawned about 450 m out, linked to the
marker at the player's feet while it is loaded, and the player hops back. Does it come while it is out of the loaded
area? Synthetic logs; no game."""
import re
import unittest

from tests.test_combined_p9_package import FOLLOW, PATROL, TRAVEL, drive  # noqa: E402  (puts src on the path)
from fo4sf.combined import probes  # noqa: E402

INCONCLUSIVE, PASS = probes.INCONCLUSIVE, probes.PASS


def out_of_range(lines, after_t=20.0, near_m=270.0, frozen=False):
    """The player hops back about after_t seconds into the walk: from then on the samples read unloaded until the actor
    comes within near_m of the marker (the player's feet; on 1 Nov an actor read loaded within about 270 m of the
    player). frozen: while unloaded the readings stay at the first unloaded one (an engine
    that moves an unloaded actor only when it loads again)."""
    out, held = [], None
    for ln in lines:
        if " p9 sample " in ln:
            t = float(re.search(r" t=([\d.]+)", ln)[1])
            dist = float(re.search(r"dist=([\d.]+)", ln)[1])
            if t >= after_t and dist > near_m:
                ln = ln.replace("loaded=True", "loaded=False")
                if frozen:
                    held = held or (re.search(r"pos=(\S+ \S+ \S+)", ln)[1], re.search(r"dist=([\d.]+)", ln)[1])
                    ln = re.sub(r"pos=\S+ \S+ \S+", f"pos={held[0]}", ln)
                    ln = re.sub(r"dist=[\d.]+", f"dist={held[1]}", ln)
        out.append(ln)
    return out


def walk(**kwargs):
    return drive(driver="link", package=PATROL, **kwargs)


class P9UnloadedTests(unittest.TestCase):
    def test_an_actor_that_comes_while_unloaded_passes(self):
        v = probes.check_p9u(probes_col(out_of_range(walk())))
        self.assertEqual(v.verdict, PASS, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 136.0)           # 410 m to 274 m, then loaded again
        self.assertLess(v.extra["arrived_at_s"], probes.PLACEHOLDERS["p9u_seconds"])
        self.assertEqual(v.extra["unloaded_from_m"], 410.0)                 # 40 m walked before the player went back
        self.assertEqual(v.extra["sample_gap_s"], {"median": 2.0, "max": 2.0})   # the tracker's 2 s, no lag

    def test_registered_and_judged_by_name(self):
        self.assertIn("p9u", probes.PROBES)
        self.assertIs(probes.CHECKS["p9u"], probes.check_p9u)
        self.assertEqual(probes.check("p9u", probes_col(out_of_range(walk()))).verdict, PASS)

    def test_a_walk_kept_loaded_says_nothing_about_unloaded_travel(self):
        v = probes.check_p9u(probes_col(walk()))                            # P9's Shadow walk: arrives, always loaded
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("beyond the loaded area" in r and "arrived after" in r for r in v.reasons), v.reasons)
        self.assertEqual(probes.check_p9(probes_col(walk())).verdict, PASS)  # the loaded test it comes after still holds

    def test_an_actor_that_does_not_come_is_never_a_fail(self):
        v = probes.check_p9u(probes_col(out_of_range(walk(speed=0.0))))   # it stands where it was spawned
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 0.0)
        v = probes.check_p9u(probes_col(out_of_range(walk(speed=0.3, seconds=900))))   # comes, but too slowly
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertGreaterEqual(v.extra["unloaded_progress_m"], probes.PLACEHOLDERS["p9u_unloaded_m"])
        self.assertTrue(any("did not arrive in time" in r for r in v.reasons), v.reasons)

    def test_readings_frozen_while_unloaded_are_not_unloaded_travel(self):
        # the actor turns up once it loads again, but its readings never moved while it was out of range
        v = probes.check_p9u(probes_col(out_of_range(walk(), frozen=True)))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 0.0)
        self.assertIsNotNone(v.extra["arrived_at_s"])

    def test_the_link_must_have_taken_toward_the_marker_from_far_enough(self):
        cases = {"package driver": drive(driver="package", package=TRAVEL),
                 "follow package": drive(driver="link", package=FOLLOW),
                 "no package line": drive(driver="link", package=None),
                 "to the player": drive(driver="link", package=FOLLOW, target="Player"),
                 "scripted": drive(driver="script"),
                 "too close": walk(start=300.0)}
        for name, lines in cases.items():
            with self.subTest(name):
                v = probes.check_p9u(probes_col(out_of_range(lines)))
                self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())


def probes_col(lines):
    from tests.test_combined_probes import col
    return col(log=lines)


if __name__ == "__main__":
    unittest.main()
