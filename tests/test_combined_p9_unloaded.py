"""P9u, the owner's design (1 Nov 2026): the player stays at the start, the actor is spawned far out (450 m in these
logs), linked to the marker at the player's feet while it is loaded, and the player hops back. Does it come while it is
out of the loaded area? Synthetic logs; no game. Each gate has a case that would PASS without it (review of 861714e0)."""
import re
import unittest

from tests.test_combined_p9_package import FOLLOW, PATROL, TRAVEL, drive  # noqa: E402  (puts src on the path)
from tests.test_combined_probes import col  # noqa: E402
from fo4sf.combined import probes  # noqa: E402

INCONCLUSIVE, PASS = probes.INCONCLUSIVE, probes.PASS
P = probes.PLACEHOLDERS


def out_of_range(lines, after_t=20.0, near_m=270.0, frozen=False):
    """The player hops back about after_t seconds into the walk: from then on the samples read unloaded until the actor
    comes within near_m of the marker (the player's feet; on 1 Nov an actor read loaded within about 270 m of the
    player). frozen: while unloaded the readings stay at the first unloaded one (an engine that moves an unloaded actor
    only when it loads again)."""
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


def track(points, start=450.0):
    """A link rung whose samples are the given (t, x, loaded) points, the marker at x=start."""
    head = [ln for ln in walk() if " p9 sample " not in ln and " p9 done " not in ln]
    rows = [f"FOCC rt={t + 1.5:.1f} p9 sample t={t:.6f} actor=-16711680 pos={x:.6f} 0.000000 0.000000 "
            f"cell={50333000 + int(x // 100)} loaded={loaded} dist={start - x:.6f}" for t, x, loaded in points]
    t, x, _ = points[-1]
    return head + rows + [f"FOCC rt={t + 2.0:.1f} p9 done t={t:.6f} dist={start - x:.6f}"]


def judge(lines):
    return probes.check_p9u(col(log=lines))


class P9UnloadedTests(unittest.TestCase):
    def test_an_actor_that_comes_while_unloaded_passes(self):
        v = judge(out_of_range(walk()))
        self.assertEqual(v.verdict, PASS, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 136.0)           # 410 m to 274 m, then loaded again
        self.assertLess(v.extra["arrived_at_s"], P["p9u_seconds"])
        self.assertEqual(v.extra["window_s"], P["p9u_seconds"])           # 450 m: the 900 s floor
        self.assertEqual(v.extra["unloaded_from_m"], 410.0)                 # 40 m walked before the player went back
        self.assertEqual(v.extra["sample_gap_s"], {"median": 2.0, "p90": 2.0, "max": 2.0})   # the tracker's 2 s
        self.assertEqual(v.extra["max_step_m_per_s"], 2.0)

    def test_registered_and_judged_by_name(self):
        self.assertIn("p9u", probes.PROBES)
        self.assertIs(probes.CHECKS["p9u"], probes.check_p9u)
        self.assertEqual(probes.check("p9u", col(log=out_of_range(walk()))).verdict, PASS)

    def test_a_walk_kept_loaded_says_nothing_about_unloaded_travel(self):
        v = judge(walk())                                                   # P9's Shadow walk: arrives, always loaded
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("beyond the loaded area" in r and "arrived after" in r for r in v.reasons), v.reasons)
        self.assertEqual(probes.check_p9(col(log=walk())).verdict, PASS)  # the loaded test it comes after still holds

    def test_an_actor_that_does_not_come_is_never_a_fail(self):
        v = judge(out_of_range(walk(speed=0.0)))                            # it stands where it was spawned
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 0.0)
        v = judge(out_of_range(walk(speed=0.3, seconds=900)))              # comes, but too slowly
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertGreaterEqual(v.extra["unloaded_progress_m"], P["p9u_unloaded_m"])
        self.assertTrue(any("did not arrive in time" in r for r in v.reasons), v.reasons)

    def test_an_arrival_after_the_window_does_not_count(self):
        # 0.45 m/s: it comes, 978 s after the go, past p9u_seconds (900)
        v = judge(out_of_range(walk(speed=0.45, seconds=1100)))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertLess(v.extra["closest_m"], P["p9_arrive_m"])
        self.assertIsNone(v.extra["arrived_at_s"])
        self.assertTrue(any("did not arrive in time" in r for r in v.reasons), v.reasons)

    def test_the_window_grows_with_the_start_distance(self):
        # 2 Nov 2026: a 900 m start; 0.8 m/s arrives after about 1100 s, inside 2 s per metre (1800 s), not inside 900 s
        v = judge(out_of_range(walk(start=900.0, speed=0.8, seconds=1800)))
        self.assertEqual(v.verdict, PASS, v.to_dict())
        self.assertEqual(v.extra["window_s"], 1800.0)
        self.assertGreater(v.extra["arrived_at_s"], P["p9u_seconds"])
        v = judge(out_of_range(walk(start=900.0, speed=0.45, seconds=2200)))  # about 2000 s: past 1800
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("did not arrive in time" in r and "within 1800 s" in r for r in v.reasons), v.reasons)
        # the floor (review of c51e7074): from 420 m, 2 s per metre is 840 s; an arrival at about 870 s still counts
        v = judge(out_of_range(walk(start=420.0, speed=0.47, seconds=1000)))
        self.assertEqual(v.verdict, PASS, v.to_dict())
        self.assertEqual(v.extra["window_s"], P["p9u_seconds"])
        self.assertGreater(v.extra["arrived_at_s"], 2 * 420.0)

    def test_a_start_under_400_m_does_not_count(self):
        # 300 m out, unloaded from 260 m to 150 m (110 m): every other gate holds
        v = judge(out_of_range(walk(start=300.0), near_m=150.0))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("400 m or more" in r for r in v.reasons), v.reasons)

    def test_jumps_are_not_unloaded_travel(self):
        # review of 861714e0: summed changes of dist counted an engine jump as travel
        cases = {
            # it stands unloaded 280 s, jumps 170 m in one gap, then walks in
            "jump while unloaded": [(t, 0.0, "True" if t < 20 else "False") for t in range(0, 282, 2)]
            + [(282 + 2 * k, 170.0 + 4 * k, "False" if 280 - 4 * k > 270 else "True") for k in range(68)],
            # frozen, then read at the marker before its 3D loads
            "frozen then at the marker": [(t, 0.0, "False") for t in range(0, 302, 2)] + [(302, 446.0, "False")],
            # it walks unloaded, then turns up next to the player when it loads again
            "teleport on reload": [(t, 2.0 * t, "False") for t in range(0, 152, 2)] + [(152, 444.0, "True")],
        }
        for name, points in cases.items():
            with self.subTest(name):
                v = judge(track(points))
                self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
                self.assertTrue(any("moved in jumps" in r for r in v.reasons), v.reasons)
                self.assertGreater(v.extra["max_step_m_per_s"], P["p9_jump_m_per_s"])

    def test_readings_frozen_while_unloaded_are_not_unloaded_travel(self):
        # the actor turns up once it loads again, but its readings never moved while it was out of range
        v = judge(out_of_range(walk(), frozen=True))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 0.0)
        self.assertIsNotNone(v.extra["arrived_at_s"])

    def test_only_this_actor_its_track_and_its_readings_count(self):
        passing = out_of_range(walk())
        other = [ln.replace("actor=-16711680", "actor=-16711681") if " p9 sample " in ln else ln for ln in passing]
        stand = out_of_range(walk(speed=0.0))
        mixed = stand + [ln for ln in other if " p9 sample " in ln]          # another actor walks in after the done
        early_done = [ln for ln in passing if " p9 done " not in ln]
        cut = [i for i, ln in enumerate(early_done) if " p9 sample " in ln][5]
        early_done.insert(cut, "FOCC rt=12.0 p9 done t=10.000000 dist=430.000000")   # the track ended 10 s in
        no_flag = [re.sub(r" loaded=\w+", "", ln) if " p9 sample " in ln else ln for ln in passing]
        backwards = [re.sub(r"rt=([\d.]+) p9 sample", lambda m: f"rt={float(m[1]) - 1000:.1f} p9 sample", ln)
                     for ln in passing]
        rows = [i for i, ln in enumerate(passing) if " p9 sample " in ln]
        stalled_clock = list(passing)                                       # one sample repeats its predecessor's rt
        prev_rt = re.search(r"rt=([\d.]+)", passing[rows[40]])[1]
        stalled_clock[rows[41]] = re.sub(r"rt=[\d.]+", f"rt={prev_rt}", passing[rows[41]])
        late_back = list(passing)                                           # the clock steps back partway
        late_back[rows[60]] = re.sub(r"rt=[\d.]+", "rt=50.0", passing[rows[60]])
        for name, lines in {"another actor": other, "another actor after the done": mixed,
                            "samples after the done": early_done, "no loaded flag": no_flag,
                            "clock before the go": backwards, "clock stands still": stalled_clock,
                            "clock steps back partway": late_back}.items():
            with self.subTest(name):
                v = judge(lines)
                self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())

    def test_the_link_must_have_taken_toward_the_marker(self):
        cases = {"package driver": drive(driver="package", package=TRAVEL),
                 "follow package": drive(driver="link", package=FOLLOW),
                 "no package line": drive(driver="link", package=None),
                 "to the player": drive(driver="link", package=FOLLOW, target="Player"),
                 "scripted": drive(driver="script")}
        for name, lines in cases.items():
            with self.subTest(name):
                v = judge(out_of_range(lines))
                self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())

    def test_the_first_sample_must_follow_from_the_go(self):
        # review of eada2c28: only the steps between samples were checked, so a track whose first sample read 200 m
        # nearer than the go found the actor, 4 s later (50 m/s), passed on the rest
        v = judge(track([(4, 200.0, "False"), (24, 300.0, "False"), (44, 446.0, "True")]))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertTrue(any("is a jump, not a walk" in r for r in v.reasons), v.reasons)
        # the slack is the P9 judge's: 2 m plus 15 m/s for the time since the go (62 m after 4 s)
        v = judge(track([(4, 60.0, "False"), (24, 100.0, "False"), (44, 200.0, "False"), (64, 300.0, "False"),
                         (84, 446.0, "True")]))
        self.assertEqual(v.verdict, PASS, v.to_dict())

    def test_incomplete_readings_refuse_the_judgement(self):
        # review of eada2c28: the teleport-on-reload track read INCONCLUSIVE whole, PASS once the jumping sample lost
        # its pos= (the fallback measured |change of dist|, a floor), its dist= or its rt= (the row was dropped)
        lines = track([(t, 2.0 * t, "False") for t in range(0, 152, 2)] + [(152, 444.0, "True")])
        jumping = [i for i, ln in enumerate(lines) if " p9 sample " in ln][-1]
        self.assertTrue(any("moved in jumps" in r for r in judge(lines).reasons))
        cuts = {"no pos": (r" pos=\S+ \S+ \S+", ""), "no dist": (r" dist=[\d.]+", ""), "no rt": (r"rt=[\d.]+ ", ""),
                "torn pos": (r" pos=(\S+) \S+ \S+", r" pos=\1"), "unreadable rt": (r"rt=[\d.]+", "rt=late"),
                "unreadable dist": (r"dist=[\d.]+", "dist=nan"), "no actor": (r" actor=\S+", ""),
                "torn before the actor": (r" actor=.*$", ""),      # review of 3d116e23: the actor filter dropped it
                "torn after the kind": (r" t=.*$", "")}           # review of 61b18cad: a fieldless sample was a gap
        for name, (pattern, repl) in cuts.items():
            with self.subTest(name):
                hidden = list(lines)
                hidden[jumping] = re.sub(pattern, repl, hidden[jumping])
                v = judge(hidden)
                self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
                self.assertTrue(any("incomplete readings" in r for r in v.reasons), v.reasons)
        # another actor's torn line is not this track's: the jump still shows, and nothing is refused for it
        other = lines[jumping].replace("rt=", "rt=late ", 1).replace("actor=-16711680", "actor=-16711681")
        v = judge(lines[:jumping] + [other] + lines[jumping:])
        self.assertTrue(any("moved in jumps" in r for r in v.reasons), v.reasons)

    def test_the_arriving_pair_counts_and_the_window_edge_is_inside(self):
        # review of 3d116e23: the pair that arrives counts when both samples read unloaded (rows[:hit_k + 1]), and a
        # sample at the window's last second is inside it (<= window), with and without an arrival
        v = judge(track([(0, 0.0, "True"), (30, 346.0, "False"), (90, 446.0, "False")]))
        self.assertEqual(v.verdict, PASS, v.to_dict())
        self.assertEqual((v.extra["unloaded_progress_m"], v.extra["arrived_at_s"]), (100.0, 90.0))
        v = judge(track([(0, 0.0, "True"), (300, 100.0, "False"), (600, 200.0, "False"), (900, 446.0, "True")]))
        self.assertEqual(v.verdict, PASS, v.to_dict())
        self.assertEqual(v.extra["arrived_at_s"], 900.0)
        v = judge(track([(0, 0.0, "True"), (800, 100.0, "False"), (900, 200.0, "False")]))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 100.0)

    def test_unloaded_progress_counts_only_up_to_the_arrival(self):
        # review of eada2c28: an actor that arrived loaded at 100 s, then wandered out and back unloaded after 1000 s,
        # read PASS on progress made after its arrival and outside the 900 s window
        points = [(4, 0.0, "True"), (100, 446.0, "True"), (1000, 100.0, "False"), (1100, 200.0, "False"),
                  (1200, 300.0, "False"), (1400, 446.0, "True")]
        v = judge(track(points))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertEqual(v.extra["arrived_at_s"], 100.0)
        self.assertEqual(v.extra["unloaded_progress_m"], 0.0)
        # no arrival: progress counts inside the window only (100 m unloaded at 950-1050 s is past 900 s)
        late = [(4, 0.0, "True"), (400, 40.0, "True"), (950, 100.0, "False"), (1050, 200.0, "False"),
                (1150, 200.0, "False")]
        v = judge(track(late))
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertEqual(v.extra["unloaded_progress_m"], 0.0)

    def test_the_marker_must_be_the_probes_own(self):
        # review of eada2c28: to_dest matched the go's id against the `p9 dest` line's, whatever that line named
        lines = [ln.replace("50333723", "50333724") for ln in out_of_range(walk())]
        v = judge(lines)
        self.assertEqual(v.verdict, INCONCLUSIVE, v.to_dict())
        self.assertFalse(v.extra["attempts"][-1]["dest_ok"])
        self.assertTrue(any("probe's own marker" in r for r in v.reasons), v.reasons)


if __name__ == "__main__":
    unittest.main()
