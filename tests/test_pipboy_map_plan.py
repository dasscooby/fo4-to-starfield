"""FAL-584: the MAP page plan (docs/spikes/pipboy-map-page-plan.md). Its account of today's page is checked against the
plugin's source and ini, so the plan is rewritten when the page changes; and it keeps its rules."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "spikes" / "pipboy-map-page-plan.md"
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"


class MapPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = PLAN.read_text(encoding="utf-8")
        cls.main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
        cls.ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")

    def test_today_is_what_the_plugin_shows(self):
        page = self.ini[self.ini.index("[Page MAP/WORLD]\n"):]
        page = page[:page.index("\n\n")]
        rows = [line.split("=", 1)[1].split("|")[0] for line in page.splitlines()[1:]]
        self.assertEqual(rows, ["WORLD", "CELL", "POSITION", "HEADING", "GRID", "TIME", "DAYS PASSED"])   # FAL-595
        for row in rows:
            self.assertIn(f"| {row} |", self.plan, row)
        self.assertIn("kPositionAt = 0x80 + 0x0C;", self.main)       # location after angle in OBJ_REFR
        self.assertIn("kParentCellAt = 0xB0;", self.main)
        self.assertIn("`+0x80 + 0x0C`", self.plan)
        self.assertIn("`+0xB0`", self.plan)
        self.assertIn('return { cellText, "NONE (INTERIOR)" };', self.main)

    def test_the_plan_keeps_its_rules(self):
        for text in ("**A plan, no code.**", "**hypothesis**", "`Pause=0`", "No game files in Git",
                     "nothing extracted, nothing copied into Git", "out of scope until a separate owner decision",
                     "Nothing walks the game's own lists"):
            self.assertIn(text, self.plan, text)
        for read in ("**R1:**", "**R2:**", "**R3:**", "**R4:**", "**R5:**"):
            self.assertIn(read, self.plan, read)
        self.assertIn("map-markers.md", self.plan)
        self.assertTrue((ROOT / "docs" / "terrain" / "map-markers.md").is_file())
        self.assertTrue((ROOT / "docs" / "terrain" / "walk-redrocket-sanctuary.md").is_file())
        self.assertIn("-989.257, 1146.514, 107.143", (ROOT / "docs" / "terrain" / "map-markers.md").read_text(encoding="utf-8")
                      .replace("−", "-").replace("(", "").replace(")", ""))


if __name__ == "__main__":
    unittest.main()
