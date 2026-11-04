"""P9's package driver (FOCC_P9Drive.Travel): Starfield.esm's DefaultTraveltoLinkedRef on the probe quest's alias. Its
go says driver=package, it has no return line, and its `p9 package` line names the package the actor ran two seconds
later. Synthetic logs; no game."""
import re
import unittest

from tests.test_combined_probes import BASE, col, p9_log  # noqa: E402  (puts src on the path)
from fo4sf.combined import probes  # noqa: E402

ACTOR = -16711680
TRAVEL = 2174939                    # 0x00212FDB as the log's signed decimal


PATROL, FOLLOW = 0x301C3, 0x301C5   # Starfield.esm DefaultMaster_PatrolPackage / DefaultMaster_FollowPackage


def drive(*, driver="package", package=TRAVEL, offset=0.0, stray_return=False, pkg_actor=ACTOR, pkg_call=None,
          target="dest", **kwargs):
    """A p9_log rung with a go at rt 1.5 (+offset) by the given driver, and for a package its `p9 package` line
    (package=None: no such line; pkg_actor / pkg_call: a line that belongs to another actor or call)."""
    lines = p9_log(**kwargs)
    lines = [re.sub(r"rt=([0-9.]+)", lambda m: f"rt={float(m[1]) + offset:.1f}", line) for line in lines]
    start = next(i for i, line in enumerate(lines) if " p9 start " in line)
    origin, dist = offset + 1.5, kwargs.get("start", 450.0)
    extra = f" driver={driver}" if driver in ("package", "link") else ""
    tid = 20 if target.casefold() == "player" else 50333723
    add = [f"FOCC rt={origin} p9 go actor={ACTOR} call={origin} target={target} id={tid} dist={dist}{extra}"]
    if driver in ("package", "link") and package is not None:
        call = origin if pkg_call is None else pkg_call
        add.append(f"FOCC rt={origin + 2.0} p9 package actor={pkg_actor} call={call} linked=50333723 "
                   f"package={package} dist={dist}")
    if stray_return:                # a return line never belongs to a package go, even with its call=
        add.append(f"FOCC rt={origin + 1.0} p9 path returned actor={ACTOR} call={origin} target=dest result=1 "
                   f"after=1.0 dist={dist}")
    return lines[:start + 1] + add + lines[start + 1:]


class P9PackageDriverTests(unittest.TestCase):
    def test_a_package_walk_that_arrives_passes_and_names_its_driver(self):
        v = probes.check_p9(col(log=drive()))
        self.assertEqual(v.verdict, probes.PASS, v.to_dict())
        last = v.extra["attempts"][-1]
        self.assertEqual(last["driver"], "package")
        self.assertEqual(last["package_after_go"], "00212FDB")
        self.assertIsNone(last["path_result"])
        self.assertIn("DefaultTraveltoLinkedRef", v.extra["driver"])

    def test_a_package_that_did_not_take_is_inconclusive(self):
        v = probes.check_p9(col(log=drive(package=0x2B2000)))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("did not take" in r for r in v.reasons), v.reasons)

    def test_a_package_go_never_takes_a_return_line(self):
        v = probes.check_p9(col(log=drive(stray_return=True)))
        self.assertEqual(v.verdict, probes.PASS, v.to_dict())
        self.assertIsNone(v.extra["attempts"][-1]["path_return_line"])

    def test_a_stall_needs_a_package_control_not_a_scripted_one(self):
        stalled = drive(speed=0.0, offset=200.0)
        package_ctl = drive(start=20.0, seconds=60, offset=100.0)
        v = probes.check_p9(col(log=BASE + package_ctl[1:] + stalled[1:]))
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())
        self.assertTrue(any("package commanded rung" in r for r in v.reasons), v.reasons)
        script_ctl = drive(driver="script", start=20.0, seconds=60, offset=100.0)
        v = probes.check_p9(col(log=BASE + script_ctl[1:] + stalled[1:]))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())   # a PathToReference control proves nothing here

    def test_no_proof_the_package_took_is_never_a_verdict(self):
        # #663 review P1: a missing, `none`, unreadable or someone else's `p9 package` line is not proof
        cases = {"no line": dict(package=None), "none": dict(package="none"), "garbage": dict(package="abc"),
                 "another actor": dict(pkg_actor=-16711681), "another call": dict(pkg_call=99.0)}
        for name, kw in cases.items():
            with self.subTest(name):
                v = probes.check_p9(col(log=drive(**kw)))                       # an arriving walk
                self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
                stalled = drive(speed=0.0, offset=200.0, **kw)
                good_ctl = drive(start=20.0, seconds=60, offset=100.0)
                v = probes.check_p9(col(log=BASE + good_ctl[1:] + stalled[1:]))
                self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())   # never blamed on the navmesh
        v = probes.check_p9(col(log=drive(package="none")))
        self.assertTrue(any("ran no package" in r for r in v.reasons), v.reasons)
        v = probes.check_p9(col(log=drive(package=None)))
        self.assertTrue(any("no `p9 package` line" in r for r in v.reasons), v.reasons)

    def test_a_control_whose_package_did_not_take_proves_nothing(self):
        # #663 review P2: the control's own `p9 package` line must name DefaultTraveltoLinkedRef too
        stalled = drive(speed=0.0, offset=200.0)
        for kw in (dict(package=0x2B2000), dict(package=None), dict(package="none")):
            with self.subTest(kw=kw):
                ctl = drive(start=20.0, seconds=60, offset=100.0, **kw)
                v = probes.check_p9(col(log=BASE + ctl[1:] + stalled[1:]))
                self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())

    # --- the linked-ref driver (FOCC_P9Drive.Link, job focc-P9l) ------------------------------------------------------
    def test_a_link_walk_under_the_patrol_package_passes(self):
        v = probes.check_p9(col(log=drive(driver="link", package=PATROL)))
        self.assertEqual(v.verdict, probes.PASS, v.to_dict())
        self.assertEqual(v.extra["attempts"][-1]["driver"], "link")
        self.assertIn("FOCC_P9Drive.Link", v.extra["driver"])

    def test_a_link_walk_needs_the_package_for_its_target(self):
        for pkg in (TRAVEL, FOLLOW, None, "none"):                         # to the marker it must be Patrol
            with self.subTest(pkg=pkg):
                v = probes.check_p9(col(log=drive(driver="link", package=pkg)))
                self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
        v = probes.check_p9(col(log=drive(driver="link", package=FOLLOW)))
        self.assertTrue(any("DefaultMaster_FollowPackage" in r and "DefaultMaster_PatrolPackage" in r
                            for r in v.reasons), v.reasons)

    def test_a_link_control_to_the_player_follows_and_qualifies_a_link_stall(self):
        # the go line's target comes as "Player" on the PC (Papyrus keeps the first casing it met): casefolded
        stalled = drive(driver="link", package=PATROL, speed=0.0, offset=200.0)
        ctl = drive(driver="link", package=FOLLOW, target="Player", start=20.0, seconds=60, offset=100.0)
        v = probes.check_p9(col(log=BASE + ctl[1:] + stalled[1:]))
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())
        self.assertTrue(any("linked ref" in r or "link commanded rung" in r for r in v.reasons), v.reasons)
        for bad in (dict(driver="link", package=PATROL, target="Player"),     # Patrol is not the player's package
                    dict(driver="package", package=TRAVEL)):                  # another driver's control
            with self.subTest(bad=bad):
                ctl = drive(start=20.0, seconds=60, offset=100.0, **bad)
                v = probes.check_p9(col(log=BASE + ctl[1:] + stalled[1:]))
                self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())

    def test_a_scripted_control_to_the_player_counts_whatever_its_casing(self):
        stalled = drive(driver="script", speed=0.0, offset=200.0)
        ctl = drive(driver="script", target="Player", start=20.0, seconds=60, offset=100.0)
        v = probes.check_p9(col(log=BASE + ctl[1:] + stalled[1:]))
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())

    def test_a_marker_above_the_ground_is_never_a_fail(self):
        # 1 Nov link rerun: the actor walked 420 m to the marker's x, y and stood there, 27.8 m under the marker that
        # P9Dest left at the player's height; the 3D dist stuck near 28 m and the judge said FAIL (stuck)
        dz = 28.0

        def floating(lines):
            out = []
            for ln in lines:
                if " p9 dest " in ln:
                    ln = ln.replace("pos=450.000000 0.000000 0.000000", f"pos=450.000000 0.000000 {dz:.6f}")
                m = re.search(r"pos=([-\d.]+) ", ln) if " p9 sample " in ln else None
                if m:
                    ln = re.sub(r"dist=[\d.]+", f"dist={((450.0 - float(m[1])) ** 2 + dz ** 2) ** 0.5:.6f}", ln)
                out.append(ln)
            return out
        walk = drive(driver="link", package=PATROL)
        samples = [ln for ln in walk if " p9 sample " in ln]
        last_rt = float(re.search(r"rt=([\d.]+)", samples[-1])[1])
        last_t = float(re.search(r" t=([\d.]+)", samples[-1])[1])
        stand = [samples[-1].replace(f"rt={last_rt:.1f}", f"rt={last_rt + s:.1f}")
                 .replace(f"t={last_t:.6f}", f"t={last_t + s:.6f}")
                 for s in range(2, 160, 2)]                                  # then it stands there 158 s, loaded
        at = walk.index(samples[-1]) + 1
        v = probes.check_p9(col(log=floating(walk[:at] + stand + walk[at:])))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("across the ground" in r and "above it" in r for r in v.reasons), v.reasons)
        self.assertLess(v.extra["closest_xy_m"], 10.0)
        v = probes.check_p9(col(log=walk))                                   # the same walk to a marker on the ground
        self.assertEqual(v.verdict, probes.PASS, v.to_dict())
        # the guard's edges: a ground arrival only within the arrival distance, and only within the rung's seconds
        miss = [re.sub(r"pos=([-\d.]+) 0\.000000", lambda m: f"pos={m[1]} 15.000000", ln) if " p9 sample " in ln else ln
                for ln in floating(walk[:at] + stand + walk[at:])]                # 15 m off to the side all the way
        v = probes.check_p9(col(log=miss))
        self.assertFalse(any("across the ground" in r for r in v.reasons), v.reasons)
        late = drive(driver="link", package=PATROL, slow=3.0)                 # arrives about 666 s in: too late
        v = probes.check_p9(col(log=floating(late)))
        self.assertFalse(any("across the ground" in r for r in v.reasons), v.reasons)

    def test_still_periods_are_reported_with_the_package_and_the_player(self):
        # 1 Nov 2026 (#644): loaded actors stood 95-200 s mid-route and walked on; the judge lists such spans
        self.assertEqual(probes.check_p9(col(log=drive(driver="link", package=PATROL))).extra["still_periods"], [])
        lines = [re.sub(r" dist=", f" package={PATROL} player_m=80.000000 dist=", ln) if " p9 sample " in ln else ln
                 for ln in drive(driver="link", package=PATROL, stuck_from=100)]
        v = probes.check_p9(col(log=lines))
        still = v.extra["still_periods"]
        self.assertEqual(len(still), 1, still)
        self.assertEqual(still[0]["from_s"], 98.0)                  # the go at rt 1.5; the last step lands at t=98
        self.assertGreaterEqual(still[0]["for_s"], 500.0)
        self.assertEqual(still[0]["packages"], [str(PATROL)])
        self.assertEqual(still[0]["player_m"], [80.0, 80.0])
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())       # stuck 500 s while loaded, the player far: P9's rule

    def test_a_stop_with_the_player_near_is_never_stuck(self):
        # owner, 1 Nov 2026 (#644): within about 30 m the NPC's own behaviour may take over; such a stop is listed but
        # is no navmesh FAIL. The same stop with the player 80 m off stays FAIL (the test above)
        def with_player(lines, near_from=None):
            out = []
            for ln in lines:
                if " p9 sample " in ln:
                    t = float(re.search(r" t=([\d.]+)", ln)[1])
                    m = 20.0 if near_from is None or t >= near_from else 80.0
                    ln = re.sub(r" dist=", f" package={PATROL} player_m={m:.6f} dist=", ln)
                out.append(ln)
            return out
        stuck = drive(driver="link", package=PATROL, stuck_from=100)
        v = probes.check_p9(col(log=with_player(stuck)))                      # near the whole time
        self.assertNotEqual(v.verdict, probes.FAIL, v.to_dict())
        self.assertFalse(any("stuck" in r for r in v.reasons), v.reasons)
        self.assertEqual(v.extra["still_periods"][0]["player_m"], [20.0, 20.0])
        v = probes.check_p9(col(log=with_player(stuck, near_from=400)))       # far for 300 s of the stop, then near
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())                 # 300 s far is stuck all the same
        v = probes.check_p9(col(log=drive(driver="link", package=PATROL, stuck_from=100)))
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())                 # no player_m= (logs before 1 Nov): as before

    def test_the_old_scripted_go_reads_as_before(self):
        v = probes.check_p9(col(log=drive(driver="script")))
        self.assertEqual(v.extra["attempts"][-1]["driver"], "script")
        self.assertIsNone(v.extra["attempts"][-1]["package_after_go"])

    def test_same_cell_timeout_respects_player_proximity(self):
        stuck = drive(driver="link", package=PATROL, stuck_from=20)
        for distance, far_from, expected in (
            (20.0, None, probes.INCONCLUSIVE),
            (35.0, None, probes.FAIL),
            (None, None, probes.FAIL),
            (20.0, 480, probes.FAIL),
            (20.0, 482, probes.INCONCLUSIVE),
        ):
            with self.subTest(distance=distance, far_from=far_from):
                log = []
                for line in stuck:
                    if distance is not None and " p9 sample " in line:
                        elapsed = float(re.search(r" t=([\d.]+)", line)[1])
                        player_m = 80.0 if far_from is not None and elapsed >= far_from else distance
                        line = line.replace(" dist=", f" player_m={player_m} dist=")
                    log.append(line)
                verdict = probes.check_p9(col(log=log))
                self.assertEqual(verdict.extra["distinct_cells"], 1)
                self.assertEqual(verdict.verdict, expected, verdict.reasons)
                # the excuse is named and counted whenever it applies (review of 10b58dd1)
                self.assertEqual(any("where its own behaviour may hold it" in r for r in verdict.reasons),
                                 expected == probes.INCONCLUSIVE, verdict.reasons)

    def test_one_near_sample_excuses_the_first_cell_timeout_and_says_so(self):
        # review of 10b58dd1: the actor paces in one cell for 600 s with the player 80 m off on every sample but one;
        # the timeout is excused all the same (an owner knob), and the reason counts the near samples
        def with_player(near_at, seconds=600, stuck_from=20):
            out = []
            for line in drive(driver="link", package=PATROL, stuck_from=stuck_from, seconds=seconds):
                if " p9 sample " in line:
                    elapsed = float(re.search(r" t=([\d.]+)", line)[1])
                    if elapsed >= stuck_from:  # pacing: dist wobbles 3 m every other sample, never still for 120 s
                        line = re.sub(r"dist=([\d.]+)",
                                      lambda m: f"dist={float(m[1]) + 3.0 * (int(elapsed) % 4 == 0):.6f}", line)
                    line = line.replace(" dist=", f" player_m={20.0 if elapsed == near_at else 80.0} dist=")
                out.append(line)
            return out
        self.assertEqual(probes.check_p9(col(log=with_player(None))).verdict, probes.FAIL)    # far throughout
        v = probes.check_p9(col(log=with_player(300.0)))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
        self.assertTrue(any(re.search(r"in 1 of 301 samples \(4 s\)", r) for r in v.reasons), v.reasons)
        # proximity after the 600 s the timeout names excuses nothing, and is not counted (review of 5f0dd2b0)
        self.assertEqual(probes.check_p9(col(log=with_player(650.0, seconds=700))).verdict, probes.FAIL)
        v = probes.check_p9(col(log=with_player(300.0, seconds=700)))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
        self.assertTrue(any(re.search(r"in 1 of 301 samples \(4 s\)", r) for r in v.reasons), v.reasons)
        # the excuse belongs to the first-cell timeout alone: a track that crossed cells, then paced, never prints it
        v = probes.check_p9(col(log=with_player(300.0, stuck_from=100)))
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())
        self.assertGreater(v.extra["distinct_cells"], 1)
        self.assertFalse(any("where its own behaviour may hold it" in r for r in v.reasons), v.reasons)

    def test_an_unloaded_sample_ends_the_stall_window(self):
        # review of 10b58dd1: an unloaded sample is no evidence of a loaded stall, so the window starts again at the
        # next loaded sample, one sample later than before (the unloaded sample itself used to start it)
        stuck = drive(driver="link", package=PATROL, stuck_from=100)      # several cells, then still to 600 s

        def unloaded_at(*whens):           # unloaded samples every 100 s keep each window under 120 s until the last
            return [ln.replace("loaded=True", "loaded=False")
                    if " p9 sample " in ln and float(re.search(r" t=([\d.]+)", ln)[1]) in whens else ln for ln in stuck]
        self.assertEqual(probes.check_p9(col(log=stuck)).verdict, probes.FAIL)
        v = probes.check_p9(col(log=unloaded_at(200.0, 300.0, 400.0, 478.0)))                 # 480 to 600: 120 s
        self.assertEqual(v.verdict, probes.FAIL, v.to_dict())
        v = probes.check_p9(col(log=unloaded_at(200.0, 300.0, 400.0, 480.0)))                 # 482 to 600: 118 s
        self.assertEqual(v.verdict, probes.INCONCLUSIVE, v.to_dict())


if __name__ == "__main__":
    unittest.main()
