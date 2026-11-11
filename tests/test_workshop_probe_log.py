"""src/fo4sf/workshop/probe_log.py on synthetic log lines (written as scripts/planet/FO4SF_WSProbeQuest.psc writes them)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.workshop import probe_log  # noqa: E402


def ln(rt, rest, end=True):
    return f"[11/11/2026 - 08:00:00AM] FO4SFWS rt={rt} {rest}" + (" end=true" if end else "")


GOOD = [
    ln(1, "init version=1 quest=1 installed=true core=FO4TerrainCore.esm benchbase=33554 workshopkw=none padbase=150983 beaconid=0"),
    ln(5, "spawn stage=10 what=bench base=33554 ref=-16777000 moved=true"),
    ln(5, "read stage=10 when=now what=bench ref=-16777000 base=33554 loaded=true haskw=na disabled=false ws=na cell=1 pos=1,2,3 dist=2.5"),
    ln(9, "read stage=10 when=settled what=bench ref=-16777000 base=33554 loaded=true haskw=na disabled=false ws=na cell=1 pos=1,2,3 dist=2.5"),
    ln(20, "read stage=24 when=before what=bench ref=-16777000 base=33554 loaded=true haskw=na disabled=false ws=false cell=1 pos=1,2,3 dist=2.5"),
    ln(20, "step stage=24 call=4 name=StartWorkshop what=bench ref=-16777000"),
    ln(20, "read stage=24 when=after what=bench ref=-16777000 base=33554 loaded=true haskw=na disabled=false ws=true cell=1 pos=1,2,3 dist=2.5"),
    ln(25, "read stage=24 when=settled what=bench ref=-16777000 base=33554 loaded=true haskw=na disabled=false ws=true cell=1 pos=1,2,3 dist=2.5"),
    ln(30, "spawn stage=30 what=pad base=150983 ref=-16776999 moved=true"),
    ln(40, "read stage=31 when=before what=pad ref=-16776999 base=150983 loaded=false haskw=na disabled=false ws=na cell=1 pos=1,2,3 dist=2.5"),
    ln(40, "step stage=31 call=1 name=DisableEnable what=pad ref=-16776999"),
    ln(40, "read stage=31 when=after what=pad ref=-16776999 base=150983 loaded=false haskw=na disabled=false ws=na cell=1 pos=1,2,3 dist=2.5"),
    ln(50, "step stage=33 call=3 name=na what=pad ref=-16776999"),
    ln(60, "cell now=77"),
    ln(60, "read stage=0 when=arrival what=bench ref=-16777000 base=33554 loaded=false haskw=na disabled=false ws=true cell=1 pos=1,2,3 dist=900"),
]


class ReaderTests(unittest.TestCase):
    def test_parse_ignores_other_lines_and_the_time_stamp(self):
        self.assertIsNone(probe_log.parse_line("something else"))
        self.assertIsNone(probe_log.parse_line("FO4SFWSHAND rt=1 init end=true"))          # the hand mode's log is not this reader's
        d = probe_log.parse_line(GOOD[1])
        self.assertEqual((d["event"], d["stage"], d["what"], d["ref"], d["moved"], d["end"]), ("spawn", 10, "bench", -16777000, True, True))

    def test_case_is_ignored(self):
        d = probe_log.parse_line("fo4sfws RT=1 READ stage=10 when=now what=bench loaded=True ws=NA haskw=NONE end=TRUE")
        self.assertEqual((d["event"], d["loaded"], d["ws"], d["haskw"], d["end"]), ("read", True, "na", None, True))

    def test_a_word_in_another_case_still_counts_as_the_bench_and_pad(self):
        """PC 11 Nov: the game printed what=Bench and the verdict said no bench was placed."""
        lines = [l.replace("what=bench", "what=Bench").replace("what=pad", "what=Pad") for l in GOOD]
        s = probe_log.summarize(lines)
        self.assertTrue(s["control"][0])
        self.assertEqual(set(k for k in s["spawned"]), {"bench", "pad"})

    def test_a_cut_line_is_left_out_and_counted(self):
        s = probe_log.summarize(GOOD + [ln(70, "spawn stage=40 what=beacon base=1 ref=2", end=False)])
        self.assertEqual(s["cut"], 1)
        self.assertNotIn("beacon", s["spawned"])

    def test_the_call_that_changed_a_reading_is_named(self):
        s = probe_log.summarize(GOOD)
        st = s["stages"][(24, "bench")]
        self.assertEqual(st["call"], "StartWorkshop")
        self.assertEqual(st["changed"], ["ws"])
        self.assertEqual(s["stages"][(31, "pad")]["changed"], [])
        self.assertEqual(s["stages"][(33, "pad")]["call"], "na")

    def test_the_report_says_the_prompt_is_the_screenshot_and_a_native_the_game_lacks(self):
        text = "\n".join(probe_log.report(probe_log.summarize(GOOD)))
        self.assertIn("changed: ws false->true", text)
        self.assertIn("no logged change", text)
        self.assertIn("not in this game", text)
        self.assertIn("arrival bench: loaded=false", text)
        self.assertIn("ok: bench placed (bench); control pad placed", text)
        self.assertIn("screenshot", text)

    def test_a_log_with_only_stage_13_and_a_pad_is_not_inconclusive_and_stage50_prints(self):
        """PC 11 Nov (workshop4): stage 13 + 30 log said INCONCLUSIVE and the stage50 block printed nothing."""
        lines = [l.replace("what=bench", "what=Bench_Still").replace("when=arrival", "when=Stage50") for l in GOOD]
        s = probe_log.summarize(lines)
        self.assertTrue(s["control"][0])
        self.assertIn("bench_still", s["control"][1])
        self.assertTrue(s["returns"])
        self.assertIn("Stage50".lower() + " bench_still", "\n".join(probe_log.report(s)))

    def test_a_pad_alone_is_inconclusive_and_a_missing_pad_is_only_said(self):
        s = probe_log.summarize([l for l in GOOD if "what=bench" not in l])
        self.assertFalse(s["control"][0])
        s = probe_log.summarize([l for l in GOOD if "what=pad" not in l])
        self.assertTrue(s["control"][0])
        self.assertIn("no pad placed", s["control"][1])

    def test_without_a_spawn_it_is_inconclusive(self):
        s = probe_log.summarize([l for l in GOOD if "spawn" not in l])
        self.assertFalse(s["control"][0])
        self.assertIn("INCONCLUSIVE", "\n".join(probe_log.report(s)))
        self.assertFalse(probe_log.summarize([])["control"][0])

    def test_a_spawn_that_gave_no_reference_is_not_a_placement(self):
        lines = [l.replace("ref=-16777000 moved", "ref=none moved") for l in GOOD]
        self.assertFalse(probe_log.summarize(lines)["control"][0])


if __name__ == "__main__":
    unittest.main()
