"""src/fo4sf/powerarmor/probe_log.py on synthetic logs (never a game): the table, the control, and one test per verdict
branch (docs/research/power-armor-probe.md)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.powerarmor import probe_log as pl  # noqa: E402

QUEST, SUITREF, CTRLREF, PARACE, ORIG = 0x0A000803, 0x0A000804, 0x0A000805, 0x0A000802, 0x00013746


def s32(v):
    """A form id as Papyrus prints it: signed decimal."""
    return v - (1 << 32) if v >= 1 << 31 else v


def line(rt, event, **kw):
    body = " ".join(f"{k}={v}" for k, v in kw.items())
    return f"[11/10/2026 - 08:00:00PM] FO4SFPA rt={rt} {event} {body} end=true"


def state(rt, stage, when, race=ORIG, pos="0.0,2.5,0.0", cam=0, worn=3, inpa="false", furn="none", sit=0, distc=9.0, cell=0x0A000800):
    return line(rt, "state", stage=stage, when=when, race=s32(race), cell=s32(cell), pos=pos, cam=cam, worn=worn,
                inpa=inpa, furn=furn if furn in ("none", "na") else s32(furn), sitstate=sit, distc=distc)


def head(controlref=CTRLREF):
    return [line(1.0, "init", version=1, quest=s32(QUEST), installed="true"),
            line(1.1, "start", suitref=s32(SUITREF), controlref=s32(controlref) if controlref else "none",
                 pa_race=s32(PARACE), orig_race=s32(ORIG)),
            state(1.2, 0, "start")]


def sat(rt=5.0):
    return [line(rt, "sit", furn=s32(CTRLREF), sitstate=3, distc=0.4)]


def steps(inpa_after="false", race10=ORIG, race20=PARACE, race30=ORIG, cam10=0, last=True):
    out = [line(10.0, "step", stage=10, call="SwitchToPowerArmor", suitref=s32(SUITREF)),
           state(10.1, 10, "before"), state(10.2, 10, "now", inpa=inpa_after, race=race10, cam=cam10),
           state(14.2, 10, "settled", inpa=inpa_after, race=race10, cam=cam10),
           line(20.0, "step", stage=20, call="SetRace", race=s32(PARACE), orig_race=s32(ORIG)),
           state(20.1, 20, "before", race=race10), state(20.2, 20, "now", race=race20),
           state(24.2, 20, "settled", race=race20),
           line(30.0, "step", stage=30, call="SetRace", race=s32(ORIG), orig_race=s32(ORIG)),
           state(30.1, 30, "before", race=race20), state(30.2, 30, "now", race=race30)]
    if last:
        out.append(state(34.2, 30, "settled", race=race30))
    return out


class ParseTests(unittest.TestCase):
    def test_a_line_parses_with_ids_unsigned_and_position_as_a_tuple(self):
        p = pl.parse_line(state(1.5, 10, "now", race=PARACE, pos="1.5,-2.0,0.25", inpa="True", cam=-1, worn=-1))
        self.assertEqual((p["event"], p["stage"], p["when"], p["race"]), ("state", 10, "now", PARACE))
        self.assertEqual(p["pos"], (1.5, -2.0, 0.25))
        self.assertIs(p["inpa"], True)                          # case ignored
        self.assertEqual((p["cam"], p["worn"]), (-1, "na"))     # -1 worn = Actor.GetWornItem not available
        self.assertTrue(p["end"])

    def test_other_lines_are_ignored_and_a_cut_line_is_counted_not_read(self):
        lines = ["FO4SFPP rt=1 init", "noise", "FO4SFPA rt=2.0 state stage=10 when=now race=5 pos=1,2"] + head()
        rs, cut = pl.runs(lines)
        self.assertEqual(cut, 1)
        self.assertEqual([e["event"] for e in rs[0]], ["init", "start", "state"])

    def test_an_empty_init_does_not_split_a_run(self):
        rs, _ = pl.runs(head() + ["FO4SFPA rt=2 init end=true"] + sat())
        self.assertEqual(len(rs), 1)
        rs, _ = pl.runs(head() + head())                    # init and start are logged twice at load: one run
        self.assertEqual(len(rs), 1)
        rs, _ = pl.runs(head() + steps() + head())          # a new script instance after a step: a second run
        self.assertEqual(len(rs), 2)


class VerdictTests(unittest.TestCase):
    def test_no_start_line_is_inconclusive(self):
        s = pl.summarize([line(1.0, "init", version=1, quest=1)] + sat())
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE: control failed: no start line"), s["verdict"])
        self.assertFalse(s["control"][0])

    def test_never_sat_on_the_control_is_inconclusive_and_the_steps_are_not_judged(self):
        s = pl.summarize(head() + steps(inpa_after="true"))
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE: control failed"), s["verdict"])
        self.assertIn("never read sitting", s["verdict"])
        self.assertNotIn("entered", s["verdict"])
        out = "\n".join(pl.report(s))                     # the printout never judges a step either (FAL-223)
        self.assertIn("stage 10 SwitchToPowerArmor: not judged (control failed", out)
        self.assertNotIn("SwitchToPowerArmor: entered", out)

    def test_a_start_line_logged_at_load_has_no_control_ref_and_the_sit_state_still_reads(self):
        # PC run of 11 Nov: controlref=none (the cell is not loaded at load), sit lines furn=na sitstate=3 distc 0.12
        lines = head(controlref=None) + [line(5.0, "sit", furn="na", sitstate=3, distc=0.12)] + steps()
        s = pl.summarize(lines)
        self.assertTrue(s["control"][0], s["control"])
        self.assertTrue(s["verdict"].startswith("CONTROL OK"), s["verdict"])

    def test_a_control_furniture_ref_of_none_and_never_seated_is_inconclusive(self):
        s = pl.summarize(head(controlref=None) + [line(5.0, "sit", furn="na", sitstate=2, distc=1.0)] + steps())
        self.assertIn("controlref none", s["verdict"])
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE"))
        # a furniture id cannot match a none reference
        s = pl.summarize(head(controlref=None) + [line(5.0, "sit", furn=s32(CTRLREF), sitstate=0, distc=9.0)] + steps())
        self.assertFalse(s["control"][0])

    def test_furniture_and_sit_state_both_na_cannot_read_the_control(self):
        na = lambda ls: [l.replace("sitstate=0", "sitstate=na").replace("furn=none", "furn=na") for l in ls]  # noqa: E731
        lines = na(head()) + [line(5.0, "sit", furn="na", sitstate="na", distc=0.4)] + na(steps())
        s = pl.summarize(lines)
        self.assertIn("control cannot be read", s["verdict"])

    def test_sit_state_near_the_control_reads_when_the_furniture_is_na(self):
        near = head() + [line(5.0, "sit", furn="na", sitstate=3, distc=0.9)] + steps()
        self.assertTrue(pl.summarize(near)["control"][0])
        far = head() + [line(5.0, "sit", furn="na", sitstate=3, distc=6.0)] + steps()
        self.assertFalse(pl.summarize(far)["control"][0])

    def test_sitting_on_the_suit_furniture_is_not_the_control(self):
        lines = head() + [line(5.0, "sit", furn=s32(SUITREF), sitstate=3, distc=5.0)] + steps()      # the suit stands 5 m away
        self.assertFalse(pl.summarize(lines)["control"][0])

    def test_everything_works(self):
        s = pl.summarize(head() + sat() + steps(inpa_after="true", cam10=1))
        self.assertTrue(s["control"][0])
        self.assertEqual(s["steps"][10]["result"], "entered (IsInPowerArmor true)")
        self.assertEqual(s["steps"][20]["result"], "race set")
        self.assertEqual(s["steps"][30]["result"], "restored")
        self.assertTrue(s["verdict"].startswith("CONTROL OK"), s["verdict"])
        self.assertEqual(s["problems"], [])

    def test_switch_to_power_armor_changes_the_camera_only(self):
        s = pl.summarize(head() + sat() + steps(cam10=3))
        self.assertEqual(s["steps"][10]["result"], "changed: cam")

    def test_switch_to_power_armor_changes_nothing(self):
        s = pl.summarize(head() + sat() + steps())
        self.assertEqual(s["steps"][10]["result"], "no logged change")
        self.assertIn("SwitchToPowerArmor: no logged change", s["verdict"])

    def test_race_swap_that_does_not_stick(self):
        s = pl.summarize(head() + sat() + steps(race20=ORIG, race30=ORIG))
        self.assertEqual(s["steps"][20]["result"], "race unchanged")
        self.assertEqual(s["steps"][30]["result"], "restored")

    def test_race_became_something_else_and_not_restored(self):
        s = pl.summarize(head() + sat() + steps(race20=0x00000999, race30=0x00000999))
        self.assertEqual(s["steps"][20]["result"], "race became 00000999")
        self.assertEqual(s["steps"][30]["result"], "not restored")

    def test_a_step_that_never_ran_and_a_step_without_readings(self):
        lines = head() + sat() + steps()[:4]
        s = pl.summarize(lines)
        self.assertEqual(s["steps"][20]["result"], "not run")
        self.assertEqual(s["steps"][30]["result"], "not run")
        only_call = head() + sat() + [line(10.0, "step", stage=10, call="SwitchToPowerArmor", suitref=s32(SUITREF))]
        self.assertEqual(pl.summarize(only_call)["steps"][10]["result"], "no readings")

    def test_a_missing_settled_reading_is_a_note_not_a_failure(self):
        s = pl.summarize(head() + sat() + steps(last=False))
        self.assertEqual(s["steps"][30]["result"], "restored")
        self.assertTrue(any("stage 30: no settled reading" in p for p in s["problems"]), s["problems"])

    def test_cut_lines_and_several_runs_are_noted_and_the_latest_run_is_read(self):
        old = head() + sat() + steps(inpa_after="true")
        new = head() + steps()                              # the control failed in the later run
        s = pl.summarize(old + new + ["FO4SFPA rt=9 state stage=10 when=now race=5"])
        self.assertEqual((s["runs"], s["run"], s["cut"]), (2, 1, 1))
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE"))
        self.assertTrue(any("2 runs" in p for p in s["problems"]))
        self.assertTrue(any("without end=true" in p for p in s["problems"]))

    def test_unavailable_readings_are_listed(self):
        lines = head() + sat() + [l.replace("cam=0", "cam=na").replace("inpa=false", "inpa=na") for l in steps()]
        lines = [l.replace("cam=0", "cam=na").replace("inpa=false", "inpa=na") for l in head()] + lines[3:]
        s = pl.summarize(lines)
        self.assertIn("camera state", s["unavailable"])
        self.assertIn("IsInPowerArmor", s["unavailable"])
        self.assertNotIn("worn item count", s["unavailable"])

    def test_empty_log(self):
        s = pl.summarize([])
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE"))
        self.assertEqual(pl.table(s), ["no readings"])


class PcRunTests(unittest.TestCase):
    def test_the_log_of_the_pc_run_of_11_nov_reads_as_control_ok_in_one_run(self):
        """init and start twice at load with controlref none, sit lines with furn=na, no change at stage 10."""
        lines = head(controlref=None) + head(controlref=None) + [
            line(5.0, "sit", furn="na", sitstate=2, distc=1.049007), line(6.0, "sit", furn="na", sitstate=3, distc=0.12),
            line(7.0, "sit", furn="na", sitstate=4, distc=0.12), line(8.0, "sit", furn="na", sitstate=0, distc=1.032809)] + steps()
        s = pl.summarize(lines)
        self.assertEqual(s["runs"], 1)
        self.assertEqual(s["problems"], [])
        self.assertTrue(s["verdict"].startswith("CONTROL OK"), s["verdict"])
        self.assertEqual(s["steps"][10]["result"], "no logged change")
        self.assertEqual((s["steps"][20]["result"], s["steps"][30]["result"]), ("race set", "restored"))


REFUSED = ("[11/10/2026 - 08:42:09PM] error: FO4SF_PAProbeSuitRef (09000804): is not valid power armor furniture.\n"
           "stack:\n\t[Actor (00000014)].Actor.SwitchToPowerArmor() - \"<native>\" Line ?")


class PapyrusTests(unittest.TestCase):
    """The PC run of 11 Nov: the probe log said no change, the game's Papyrus log said it refused (FAL-212)."""
    def test_a_refusal_naming_our_suit_is_shown_and_overrides_no_logged_change(self):
        lines = head() + sat() + steps()
        plain = pl.summarize(lines)
        self.assertEqual(plain["steps"][10]["result"], "no logged change")
        self.assertFalse(plain["papyrus_read"])
        s = pl.summarize(lines, papyrus=["noise line", *REFUSED.splitlines()])
        self.assertEqual(s["papyrus"], ["error: FO4SF_PAProbeSuitRef (09000804): is not valid power armor furniture."])
        self.assertEqual(s["steps"][10]["result"],
                         "refused by the game: error: FO4SF_PAProbeSuitRef (09000804): is not valid power armor furniture.")
        self.assertIn("SwitchToPowerArmor: refused by the game", s["verdict"])
        out = pl.report(s)
        self.assertIn("game Papyrus log: error: FO4SF_PAProbeSuitRef (09000804): is not valid power armor furniture.", out)
        self.assertEqual(s["steps"][20]["result"], "race set")                       # the other steps are untouched

    def test_other_scripts_errors_and_repeats_are_left_out(self):
        errs = pl.papyrus_errors(["error: Quest XYZ: bad", "warning: FO4SF_PAProbeQuest: something", "x error: FO4SF_PAProbeQuest: something",
                                  "warning: FO4SF_PAProbeQuest: something", "info FO4SF_PAProbeQuest fine"])
        self.assertEqual(errs, ["warning: FO4SF_PAProbeQuest: something", "error: FO4SF_PAProbeQuest: something"])

    def test_a_papyrus_log_with_no_errors_of_ours_changes_nothing_and_says_it_was_read(self):
        s = pl.summarize(head() + sat() + steps(), papyrus=["error: Other thing"])
        self.assertEqual(s["steps"][10]["result"], "no logged change")
        self.assertTrue(s["papyrus_read"])
        self.assertFalse(any("was not read" in l for l in pl.report(s)))

    def test_without_the_papyrus_log_the_report_says_a_refusal_would_be_invisible(self):
        self.assertTrue(any("Papyrus log was not read" in l for l in pl.report(pl.summarize(head() + sat() + steps()))))

    def test_a_failed_control_still_says_not_judged_with_a_refusal(self):
        s = pl.summarize(head() + steps(), papyrus=REFUSED.splitlines())
        out = "\n".join(pl.report(s))
        self.assertIn("stage 10 SwitchToPowerArmor: not judged", out)
        self.assertTrue(s["verdict"].startswith("INCONCLUSIVE"))


class HasKeywordTests(unittest.TestCase):
    def with_haskw(self, value):
        return [l.replace("suitref=%d" % s32(SUITREF), "suitref=%d haskw=%s" % (s32(SUITREF), value), 1) if " step " in l and "stage=10" in l else l
                for l in head() + sat() + steps()]

    def test_the_keyword_check_on_the_reference_is_reported(self):
        s = pl.summarize(self.with_haskw("false"))
        self.assertIs(s["steps"][10]["haskw"], False)
        self.assertTrue(any("HasKeyword(FurnitureTypePowerArmor) before the call: false" in l for l in pl.report(s)))
        s = pl.summarize(self.with_haskw("true"))
        self.assertTrue(any("before the call: true" in l and "throwaway" in l for l in pl.report(s)))

    def test_an_unavailable_check_says_nothing(self):
        for v in ("na", None):
            s = pl.summarize(self.with_haskw(v) if v else head() + sat() + steps())
            self.assertFalse(any("HasKeyword(FurnitureTypePowerArmor)" in l for l in pl.report(s)))


class AddKeywordAndCrashTests(unittest.TestCase):
    def step10(self, kb, ka, k2):
        return [l.replace("suitref=%d" % s32(SUITREF), "suitref=%d haskw=%s addkw=%s haskw2=%s" % (s32(SUITREF), kb, ka, k2), 1)
                if " step " in l and "stage=10" in l else l for l in head() + sat() + steps()]

    def test_the_keyword_added_by_script_is_reported_before_and_after(self):
        out = pl.report(pl.summarize(self.step10("false", "done", "true")))
        self.assertIn("suit reference HasKeyword(FurnitureTypePowerArmor): false before the call, AddKeyword by script, true after", out)
        out = pl.report(pl.summarize(self.step10("false", "done", "false")))
        self.assertTrue(any("AddKeyword by script, false after" in l for l in out))

    def test_without_add_keyword_a_false_keyword_still_says_the_call_will_be_refused(self):
        out = pl.report(pl.summarize(self.step10("false", "na", "false")))
        self.assertTrue(any("false and AddKeyword is not available" in l and "will be refused" in l for l in out), out)

    def test_a_log_that_ends_after_the_before_reading_is_a_crash_result_not_a_failed_session(self):
        lines = head() + sat() + [l for l in steps()[:2]]                       # the step line and 'before', then nothing
        s = pl.summarize(lines)
        self.assertTrue(s["control"][0])
        self.assertTrue(s["steps"][10]["result"].startswith("no reading after the call: the log ends inside it"), s["steps"][10]["result"])
        self.assertTrue(s["verdict"].startswith("CONTROL OK"), s["verdict"])
        self.assertEqual(s["steps"][20]["result"], "not run")
        self.assertIn("the game may have ended during the call", "\n".join(pl.report(s)))


class TableTests(unittest.TestCase):
    def test_the_quests_form_id_is_printed_for_setstage(self):
        out = pl.report(pl.summarize(head() + sat() + steps()))
        self.assertEqual(out[0], f"quest form id {QUEST:08X}: setstage {QUEST:08X} 10 / 20 / 30")
        self.assertEqual(pl.quest_lines(pl.summarize([]))[0], "quest form id: not in the log (no init line with quest=)")

    def test_one_table_in_stage_order_then_the_verdict_last(self):
        out = pl.report(pl.summarize(head() + sat() + steps(inpa_after="true")))
        self.assertEqual(out[1].split(), ["stage", "when", "race", "cam", "worn", "inpa", "furn", "sit", "pos"])
        rows = [l.split() for l in out[2:15]]
        self.assertEqual([(r[0], r[1]) for r in rows[:4]], [("0", "start"), ("10", "before"), ("10", "now"), ("10", "settled")])
        self.assertIn(["20", "settled", "PA"], [r[:3] for r in rows])        # the race column names the copy
        self.assertIn(["30", "settled", "orig"], [r[:3] for r in rows])
        self.assertTrue(out[-1].startswith("CONTROL OK"))
        self.assertIn("stage 10 SwitchToPowerArmor: entered (IsInPowerArmor true)", out)


if __name__ == "__main__":
    unittest.main()
