"""FAL-614: the Fallout 4 Pip-Boy rebuild plan (docs/spikes/pipboy-fo4-rebuild-plan.md). It keeps its rules, it says
what our movie is as the source does, and its read D1 (names and header fields only) runs on our own kit movie."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "spikes" / "pipboy-fo4-rebuild-plan.md"
sys.path.insert(0, str(ROOT / "scripts" / "ui"))
import make_pipboy_kit as kit  # noqa: E402


class RebuildPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = PLAN.read_text(encoding="utf-8")
        cls.main = (ROOT / "sfse" / "FO4SFPipboyMenu" / "src" / "main.cpp").read_text(encoding="utf-8")
        cls.map_plan = (ROOT / "docs" / "spikes" / "pipboy-map-page-plan.md").read_text(encoding="utf-8")

    def test_rules(self):
        for text in ("**A plan, no code.**", "**hypothesis**", "`Pause=0`", "never go into Git",
                     "No travel from the map", "**parked**", "a separate, later page", "Fallout 4 is the first look",
                     "Nothing in the plugin or the menu may assume one", "names and header fields only",
                     "No shape, image, sound or code is written anywhere"):
            self.assertIn(text, self.plan, text)
        for read in ("**D1 (movies).**", "**D2 (data names", "**D3 (the world map).**"):
            self.assertIn(read, self.plan, read)
        for movie in ("PipboyMenu.swf", "Pipboy_StatsPage.swf", "Pipboy_InvPage.swf", "Pipboy_DataPage.swf",
                      "Pipboy_MapPage.swf", "Pipboy_RadioPage.swf", "PipboyMessageBox.swf", "pipboybootsequence.swf",
                      "fonts_en.swf"):
            self.assertIn(f"`{movie}`", self.plan, movie)

    def test_the_function_union(self):
        for text in ("## The function union: a first inventory by game", "**None of it is verified.**",
                     "**A function the look's game lacks gets a generic page in that look's style:**",
                     "A **stated gap**", "**The first build stays Fallout 4.**",
                     "| `map.travel` | fast travel from the map |", "**not designed (owner's later decision)**"):
            self.assertIn(text, self.plan, text)
        union = self.plan[self.plan.index("## The function union"):self.plan.index("**The function contract")]
        rows = [line for line in union.splitlines() if re.match(r"\| `[a-z_.]+` \|", line)]
        self.assertGreaterEqual(len(rows), 20)
        for row in rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            self.assertEqual(len(cells), 7, row)
            self.assertTrue(all(cells[i] for i in range(2, 6)), row)   # each game marked: known, unread or -

    def test_what_we_load_is_the_source(self):
        self.assertIn('"MovieRoot@AS3@GFx@Scaleform@@"sv', self.main)
        self.assertIn("kLoadMovieRva = 0x2551AB0;", self.main)
        self.assertIn('return a_root.Invoke("getChildByName", &a_out, &name, 1)', self.main)
        self.assertEqual(kit.swf.VERSION, 12)
        for name in kit.VALUE_PROVIDERS:
            self.assertIn(name, self.plan, name)

    def test_the_map_plan_parks_step_2(self):
        self.assertIn("**Parked for later uses (a warfare mode, settlement management views), not the Pip-Boy's map "
                      "page**", self.map_plan)
        self.assertIn("pipboy-fo4-rebuild-plan.md", self.map_plan)

    def test_d1_reads_names_and_headers_of_our_movie(self):
        code = re.search(r"```python\n(.*?)```", self.plan, re.S).group(1)
        space = {"__name__": "plan_d1"}
        exec(compile(code, "pipboy-fo4-rebuild-plan.md D1", "exec"), space)
        lines = space["describe"]("Interface\\FO4SF_PipboyMenu.swf", kit.kit_movie_bytes(kit.read_kit()))
        self.assertRegex(lines[0], r"^file=Interface\\FO4SF_PipboyMenu\.swf signature=CWS version=12 length=\d+ "
                                   r"stage=1920x1080 rate=30 frames=1$")
        self.assertIn("  FileAttributes flags=0x08 as3=1", lines)
        self.assertTrue(any(line.startswith("  DefineFont3 name=") for line in lines), lines)
        self.assertFalse(any("DoABC" in line for line in lines))                # our movie has no ActionScript
        self.assertTrue(lines[-1].startswith("  tags=") and "69x1" in lines[-1], lines[-1])
        self.assertEqual(space["describe"]("x.dds", b"DDS |" + bytes(16)), ["file=x.dds signature=b'DDS' not_swf=1"])


if __name__ == "__main__":
    unittest.main()
