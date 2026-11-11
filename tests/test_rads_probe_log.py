"""src/fo4sf/rads/probe_log.py on synthetic logs (never a game): the table, the control, and one test per verdict branch
(docs/research/rads-probe.md)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.rads import probe_log as pl  # noqa: E402

HEALTH_AV, RADS_AV = 0x0000002D, 0x0A000800


def line(rt, event, **kw):
    body = " ".join(f"{k}={v}" for k, v in kw.items())
    return f"[11/10/2026 - 08:00:00PM] FO4SFRADS rt={rt} {event} {body} end=true"


def state(rt, stage, when, rads, health=200.0, base="na", mx="na", applied=0.0, fx="none"):
    return line(rt, "state", stage=stage, when=when, rads=rads, health=health, base=base, max=mx, applied=applied, fx=fx)


def head(called="true", before=200.0, after=210.0, restored=200.0):
    return [line(1.0, "init", version=1, quest=167772163),
            line(1.1, "start", rads_av=167772160, health_av=45, spell=167772162, radaway=167772163, penalty=0.1),
            state(1.2, 0, "start", 0.0)]


def control(called="true", before=200.0, after=210.0, restored=200.0):
    return [line(2.0, "control", av=45, delta=10.0, called=called, before=before, after=after, restored=restored, undone="true")]


def step(t, stage, rads_gain, rads_now, mx_by, rads_before, forced, fx0="none", fx_after="none", call="Cast", route_ok="true"):
    """One stage's lines; maximum health follows mx_by (what the route should have set)."""
    mx = 200.0 + mx_by
    want = {20: 100.0, 30: 300.0, 40: 100.0}[stage]
    return [line(t, "step", stage=stage, call=call, expect=int(want)),
            state(t + 0.1, stage, "before", rads_before, mx=mx),
            state(t + 0.2, stage, "now", rads_before, mx=mx),
            state(t + 3.2, stage, "settled", rads_now, mx=mx, fx=fx_after),
            line(t + 3.3, "fix", stage=stage, forced=forced, want=want, had=rads_now, now=want),
            line(t + 3.4, "route", rads=want, want=-int(want * 0.1), delta=-int(want * 0.1), applied=-int(want * 0.1), ok=route_ok),
            state(t + 3.5, stage, "routed", want, mx=200.0 - int(want * 0.1), applied=-int(want * 0.1), fx=fx_after),
            state(t + 6.5, stage, "final", want, mx=200.0 - int(want * 0.1), applied=-int(want * 0.1), fx=fx_after)]


def good_log(mx_key="max"):
    out = head() + control()
    out += [line(3.0, "step", stage=10, call="SetValue", expect=0),
            line(3.05, "set", stage=10, wrote=50.0, read=50.0), line(3.06, "set", stage=10, wrote=0.0, read=0.0),
            state(3.1, 10, "before", 0.0, mx=200.0), state(3.2, 10, "now", 0.0, mx=200.0),
            state(6.2, 10, "settled", 0.0, mx=200.0), line(6.3, "fix", stage=10, forced="false", want=0.0, had=0.0, now=0.0),
            line(6.4, "route", rads=0.0, want=0.0, delta=0.0, applied=0.0, ok="true"),
            state(6.5, 10, "routed", 0.0, mx=200.0), state(9.5, 10, "final", 0.0, mx=200.0)]
    out += step(10.0, 20, 100, 100.0, -10, 0.0, "false")
    out += step(20.0, 30, 200, 300.0, -30, 100.0, "false")
    out += step(30.0, 40, -200, 100.0, -10, 300.0, "false", call="EquipItem")
    if mx_key != "max":
        out = [x.replace(" max=", f" {mx_key}=").replace(f" {mx_key}=na", " max=na") if " state " in x else x for x in out]
    return out


class ParseTests(unittest.TestCase):
    def test_a_line_parses_ids_unsigned_and_effects_as_a_list(self):
        p = pl.parse_line(state(1.5, 20, "settled", 100.0, fx="-2147483000,42"))
        self.assertEqual((p["event"], p["stage"], p["when"], p["rads"]), ("state", 20, "settled", 100.0))
        self.assertEqual(p["fx"], [0x80000288, 42])
        self.assertEqual(pl.parse_line(state(1, 20, "now", 1, fx="none"))["fx"], "none")
        self.assertEqual(pl.parse_line(state(1, 20, "now", 1, fx="na"))["fx"], "na")
        self.assertEqual(pl.parse_line(line(1, "start", rads_av=-1))["rads_av"], 0xFFFFFFFF)

    def test_other_lines_and_case(self):
        self.assertIsNone(pl.parse_line("nothing here"))
        self.assertIsNone(pl.parse_line("FO4SFRADS rt=1 bogus a=1 end=true"))
        p = pl.parse_line("fo4sfrads rt=1 fix forced=True end=TRUE")
        self.assertIs(p["forced"], True)
        self.assertIs(p["end"], True)

    def test_a_cut_line_is_dropped_and_counted(self):
        rs, cut = pl.runs([line(1, "init", version=1), "FO4SFRADS rt=2 state stage=10 when=now rads=0"])
        self.assertEqual((len(rs), len(rs[0]), cut), (1, 1, 1))

    def test_an_empty_init_does_not_split_and_a_second_init_starts_a_run(self):
        rs, _ = pl.runs([line(1, "init", version=1), line(2, "init"), line(3, "start"), line(4, "init", version=1)])
        self.assertEqual([len(r) for r in rs], [3, 1])


class ControlTests(unittest.TestCase):
    def verdict(self, lines):
        return pl.summarize(lines)

    def test_no_lines_is_inconclusive(self):
        s = self.verdict([])
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE: no log"))

    def test_no_start_line_is_inconclusive(self):
        s = self.verdict(control())
        self.assertIn("the script never ran", s["verdict"])
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE"))

    def test_no_control_line_is_inconclusive_and_names_the_control(self):
        s = self.verdict(head())
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE: control failed"))
        self.assertIn("vanilla Health value was not set and read", s["verdict"])

    def test_the_call_not_made_is_inconclusive(self):
        s = self.verdict(head() + control(called="false", after=200.0))
        self.assertIn("was not made", s["verdict"])

    def test_health_that_did_not_move_is_inconclusive(self):
        s = self.verdict(head() + control(after=200.0))
        self.assertIn("did not move by 10", s["verdict"])
        self.assertEqual(s["effect"], {})                       # nothing is judged

    def test_health_that_did_not_come_back_is_inconclusive(self):
        s = self.verdict(head() + control(restored=210.0))
        self.assertIn("did not come back", s["verdict"])

    def test_a_control_with_unreadable_numbers_is_inconclusive(self):
        s = self.verdict(head() + control(before="na"))
        self.assertIn("not numbers", s["verdict"])

    def test_a_failed_control_judges_nothing_even_with_a_perfect_run(self):
        lines = head() + control(after=200.0) + good_log()[len(head()) + 1:]
        s = self.verdict(lines)
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE"))
        self.assertEqual(s["route"], {})


class NegativeValueTests(unittest.TestCase):
    def test_a_value_below_zero_is_a_note_and_a_clamp_is_a_note(self):
        lines = [x.replace("rads=100.0 health=200.0 base=na max=190.0 applied=-10 fx=none", "rads=-59700.0 health=200.0 base=na max=190.0 applied=-10 fx=none") for x in good_log()]
        s = pl.summarize(lines)
        self.assertTrue(any("below zero" in p for p in s["problems"]))
        lines = [x.replace("ok=true", "ok=true clamped=true") if " route " in x else x for x in good_log()]
        self.assertTrue(any("clamped our value at 0" in p for p in pl.summarize(lines)["problems"]))
        self.assertEqual(pl.summarize(good_log())["problems"], [])


class VanillaControlTests(unittest.TestCase):
    def vc(self, **kw):
        return good_log() + [line(60.0, "vcontrol", **kw)]

    def test_not_set_when_there_is_no_vcontrol_line(self):
        self.assertEqual(pl.summarize(good_log())["vanilla_control"], "not run (stage 50 not set)")

    def test_built_without_the_spell(self):
        s = pl.summarize(self.vc(spell="none", before=200.0, after=200.0, cast="false"))
        self.assertEqual(s["vanilla_control"], "not run (the kit was built without --control-spell)")

    def test_a_vanilla_cast_that_moves_health_tells_the_fault_is_ours(self):
        s = pl.summarize(self.vc(spell=-1234, before=200.0, after=230.0, cast="true"))
        self.assertIn("Health moved 200 to 230 (+30) with the vanilla spell FFFFFB2E: Cast works", s["vanilla_control"])
        self.assertIn("our effect's fault", s["vanilla_control"])

    def test_a_vanilla_cast_that_does_not_move_health_points_at_cast(self):
        s = pl.summarize(self.vc(spell=5, before=200.0, after=200.0, cast="true"))
        self.assertIn("Health did not move", s["vanilla_control"])
        self.assertIn("Cast from a quest script may apply no value modifier", s["vanilla_control"])
        self.assertIn("stage 50 vanilla control: Health did not move", "\n".join(pl.report(s)))

    def test_unreadable_numbers(self):
        s = pl.summarize(self.vc(spell=5, before="na", after=200.0, cast="true"))
        self.assertTrue(s["vanilla_control"].startswith("no reading"))

    def test_a_failed_first_control_judges_nothing_here_either(self):
        lines = head() + control(after=200.0) + [line(60.0, "vcontrol", spell=5, before=200.0, after=230.0, cast="true")]
        self.assertEqual(pl.summarize(lines)["vanilla_control"], "not run")


class SetValueTests(unittest.TestCase):
    def test_a_number_that_is_read_back_is_yes(self):
        s = pl.summarize(good_log())
        self.assertEqual(s["setvalue"], "yes (wrote 50, read 50; set back to 0 reads 0)")
        self.assertIn("Own value takes a number: yes", s["verdict"])
        self.assertIn("stage 10 own value takes a number: yes", "\n".join(pl.report(s)))

    def test_a_number_that_reads_back_as_zero_is_no(self):
        lines = [x.replace("wrote=50.0 read=50.0", "wrote=50.0 read=0.0") for x in good_log()]
        self.assertEqual(pl.summarize(lines)["setvalue"], "NO (wrote 50, read 0)")

    def test_no_set_line_is_not_run(self):
        lines = [x for x in good_log() if " set " not in x]
        self.assertEqual(pl.summarize(lines)["setvalue"], "not run (no set line)")

    def test_only_a_zero_write_is_not_a_test(self):
        lines = [x for x in good_log() if "wrote=50.0" not in x]
        self.assertEqual(pl.summarize(lines)["setvalue"], "not run (no non-zero write)")

    def test_a_failed_control_still_judges_nothing(self):
        lines = head() + control(after=200.0) + [line(3.05, "set", stage=10, wrote=50.0, read=50.0)]
        self.assertEqual(pl.summarize(lines)["setvalue"], "not run")


class VerdictTests(unittest.TestCase):
    def test_everything_works(self):
        s = pl.summarize(good_log())
        self.assertTrue(s["control"][0])
        self.assertTrue(s["verdict"].startswith("CONTROL OK"))
        self.assertEqual(s["effect"][20], "gave 100 without help (0 to 100)")
        self.assertEqual(s["effect"][30], "gave 300 without help (100 to 300)")
        self.assertEqual(s["radaway"], "gave 100 without help (300 to 100)")
        self.assertEqual(s["route"][20], "max 200 to 190 (-10, expected -10 at 100 rads)")
        self.assertEqual(s["route"][30], "max 200 to 170 (-30, expected -30 at 300 rads)")
        self.assertEqual(s["route"][40], "max 200 to 190 (-10, expected -10 at 100 rads)")
        self.assertEqual(s["maxsource"], "max")
        self.assertEqual(s["problems"], [])

    def test_an_effect_that_does_nothing_is_the_scripts_force(self):
        lines = head() + control() + [line(3.0, "step", stage=20, call="Cast", expect=100),
                                      state(3.1, 20, "before", 0.0, mx=200.0), state(6.2, 20, "settled", 0.0, mx=200.0),
                                      line(6.3, "fix", stage=20, forced="true", want=100.0, had=0.0, now=100.0)]
        s = pl.summarize(lines)
        self.assertEqual(s["effect"][20], "did not move the value (still 0, expected 100); the script forced it")

    def test_an_effect_with_the_wrong_magnitude(self):
        lines = head() + control() + [line(3.0, "step", stage=20, call="Cast", expect=100),
                                      state(3.1, 20, "before", 0.0), state(6.2, 20, "settled", 50.0),
                                      line(6.3, "fix", stage=20, forced="true", want=100.0, had=50.0, now=100.0)]
        self.assertEqual(pl.summarize(lines)["effect"][20], "moved it to 50, not 100; the script forced it")

    def test_a_route_that_does_not_move_maximum_health(self):
        lines = good_log()
        lines = [x.replace(" max=190.0", " max=200.0").replace(" max=170.0", " max=200.0") if " state " in x else x for x in lines]
        s = pl.summarize(lines)
        self.assertEqual(s["route"][20], "max unchanged at 200 (expected -10 at 100 rads)")
        self.assertEqual(s["route"][30], "max unchanged at 200 (expected -30 at 300 rads)")

    def test_a_route_that_moves_it_by_another_amount(self):
        lines = [x.replace(" max=170.0", " max=150.0") if " state " in x else x for x in good_log()]
        self.assertEqual(pl.summarize(lines)["route"][30], "max 200 to 150 (-50, expected -30 at 300 rads)")

    def test_radaway_that_does_not_lower_the_value(self):
        lines = good_log()
        i = next(i for i, x in enumerate(lines) if "fix stage=40" in x.lower() or " fix " in x and "stage=40" in x)
        lines[i] = line(33.3, "fix", stage=40, forced="true", want=100.0, had=300.0, now=100.0)
        # the stage 40 "before" reading holds 300 rads
        self.assertEqual(pl.summarize(lines)["radaway"], "did not move the value (still 300, expected 100); the script forced it")

    def test_a_stage_that_never_ran(self):
        lines = head() + control()
        s = pl.summarize(lines)
        self.assertEqual(s["effect"], {20: "not run", 30: "not run"})
        self.assertEqual(s["radaway"], "not run")
        self.assertEqual(s["route"][20], "no readings")

    def test_without_a_maximum_the_route_is_judged_on_current_health_and_base_is_only_named(self):
        """Sixth session: GetValueMax is not declared; base stays 200 while the route lowers current Health."""
        lines = [x.replace(" max=", " zz=") if " state " in x else x for x in good_log()]
        lines = [x.replace(" base=na", " base=200.0") if " state " in x else x for x in lines]
        lines = [x.replace("health=200.0", "health=205.0") if " state stage=10" in x else x for x in lines]
        # health follows the route: 205 at stage 10, then -10, -30, -10 from there (what the script's route does)
        out = []
        for x in lines:
            if " state stage=20" in x or " state stage=40" in x:
                x = x.replace("health=200.0", "health=195.0")
            elif " state stage=30" in x:
                x = x.replace("health=200.0", "health=175.0")
            out.append(x)
        s = pl.summarize(out)
        self.assertEqual(s["maxsource"], "health")
        self.assertIn("health 205 to 195 (-10, expected -10 at 100 rads)", s["route"][20])
        self.assertIn("health 205 to 175 (-30, expected -30 at 300 rads)", s["route"][30])
        self.assertTrue(any("not the maximum" in p and "base read 200 throughout" in p for p in s["problems"]))
        self.assertFalse(any("base unchanged" in v for v in s["route"].values()))

    def test_the_item_count_separates_consumed_from_not(self):
        base = good_log()
        def with_items(added, settled):
            out = []
            for x in base:
                out.append(x)
                if " step stage=40" in x:
                    out.append(x.split("step")[0] + f"item stage=40 when=added count={added} end=true")
            out.append(base[0].split("init")[0] + f"item stage=40 when=settled count={settled} end=true")
            return out
        self.assertIn("item count 1 to 0: consumed", pl.summarize(with_items(1, 0))["radaway"])
        self.assertIn("item count 1 to 1: NOT consumed", pl.summarize(with_items(1, 1))["radaway"])
        self.assertNotIn("item count", pl.summarize(base)["radaway"])

    def test_extra_effect_ids_are_named(self):
        lines = [x.replace("rads=100.0 health=200.0 base=na max=190.0 applied=-10 fx=none", "rads=100.0 health=200.0 base=na max=190.0 applied=-10 fx=-1234") for x in good_log()]
        s = pl.summarize(lines)
        self.assertEqual(s["extra_effects"], {20: [(-1234) & 0xFFFFFFFF], 40: [(-1234) & 0xFFFFFFFF]})
        self.assertTrue(any("not there at stage 10" in l and "FFFFFB2E" in l for l in pl.report(s)))

    def test_effects_that_cannot_be_listed_are_a_note(self):
        lines = [x.replace("fx=none", "fx=na") for x in good_log()]
        s = pl.summarize(lines)
        self.assertTrue(any("no list of active effects" in p for p in s["problems"]))

    def test_a_route_call_that_was_not_made_is_a_note(self):
        lines = [x.replace("ok=true", "ok=false") if " route " in x else x for x in good_log()]
        self.assertTrue(any("ModValue was not called" in p for p in pl.summarize(lines)["problems"]))

    def test_two_runs_show_the_latest_and_say_so(self):
        s = pl.summarize(good_log() + good_log())
        self.assertEqual(s["runs"], 2)
        self.assertTrue(any("2 runs in the log" in p for p in s["problems"]))

    def test_the_report_ends_with_the_verdict_and_has_one_table(self):
        s = pl.summarize(good_log())
        rep = pl.report(s)
        self.assertEqual(rep[-1], s["verdict"])
        self.assertTrue(rep[0].startswith("stage  when"))
        self.assertEqual(len([x for x in rep if x.startswith("stage ") and "when" in x]), 1)
        self.assertEqual(len(pl.table(s)), 1 + len(s["states"]))


if __name__ == "__main__":
    unittest.main()
