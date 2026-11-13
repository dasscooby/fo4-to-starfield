"""FAL-614: the Fallout 4 Pip-Boy rebuild plan (docs/spikes/pipboy-fo4-rebuild-plan.md). It keeps its rules, it says
what our movie is as the source does, and its read D1 (names and header fields only) runs on our own kit movie."""
import re
import struct
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


    def test_d2_reads_only_identifier_names(self):
        code = re.findall(r"```python\n(.*?)```", self.plan, re.S)[1]
        space = {"__name__": "plan_d2"}
        exec(compile(code, "pipboy-fo4-rebuild-plan.md D2", "exec"), space)
        pool = [b"PlayerInfo", b"a sentence, not a name", b"CurrHP", b"x" * 70]
        abc = struct.pack("<HH", 16, 46) + b"\x00\x00\x00" + bytes([len(pool) + 1])
        abc += b"".join(bytes([len(s)]) + s for s in pool)
        tag = struct.pack("<I", 1) + b"boot\0" + abc
        body = b"\x00" + struct.pack("<HH", 30 << 8, 1)
        body += struct.pack("<HI", (82 << 6) | 0x3F, len(tag)) + tag + struct.pack("<H", 0)
        movie = b"FWS" + bytes([15]) + struct.pack("<I", 8 + len(body)) + body
        self.assertEqual(space["names"](movie), ["  abc=46.16 strings=4 names=2", "  name=CurrHP", "  name=PlayerInfo"])
        self.assertEqual(space["names"](kit.kit_movie_bytes(kit.read_kit())), [])        # ours has no ActionScript

    def test_movie_setting(self):
        self.assertIn("**Proof 1, the card (owner PC; the plugin's `Movie=` setting, FAL-614).**", self.plan)
        self.assertIn("`Stage=2`, `Movie=FO4SF_Fo4Boot`", self.plan)
        self.assertIn("if (!g_movie.empty() && g_loadingMovie.load()) {", self.main)
        self.assertIn("if (!name || g_stage != 2) {", self.main)
        load = self.main[self.main.index("bool MenuLoadMovie("):]
        load = load[:load.index("\n\t}\n")]
        order = [load.index(s) for s in ("g_movieNameAsks.store(0);", "g_loadingMovie.store(true);",
                                         "g_engineLoadMovie(a_self, false, a_arg2);", "g_loadingMovie.store(false);")]
        self.assertEqual(order, sorted(order))
        ini = (ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        self.assertRegex(ini, r"\nMovie=\r?\n")                                   # shipped empty: our movie
        readme = (ROOT / "sfse" / "FO4SFPipboyMenu" / "README.md").read_text(encoding="utf-8")
        for text in ("### (b) with `Movie=`: another movie in our menu (FAL-614)", "refuse step=ini movie=",
                     "name_asks=<n>"):
            self.assertIn(text, readme, text)

    def test_code_obj_setting(self):
        # FAL-614 proof 1b: the stand-in BGSCodeObj, set right after a Movie= load, logging only
        for text in ("**Proof 1, the result (owner PC, 13 Nov, 02:46 to 02:50 UTC, at `2db64a83`): PASS, verified.**",
                     "**Route A is alive:**", "**Proof 1b, the card: the stand-in engine object",
                     "`Stage=2`, `Movie=FO4SF_Fo4Boot`, `CodeObj=1`", "set=3 of=3 read_back=1 names=PlaySound,HideMenu",
                     "**Proof 2, the outline (route A): the STAT page.**", "3. Done: proof 1b (13 Nov, third run)",
                     "**Proof 1c, the card: a real `HideMenu`"):
            self.assertIn(text, self.plan, text)
        load = self.main[self.main.index("bool MenuLoadMovie("):]
        load = load[:load.index("\n\t}\n")]
        self.assertLess(load.index("g_loadingMovie.store(false);"),
                        load.index("if (loaded && g_codeObj && MovieOf(a_self)) {"))
        self.assertIn('CodeObjInstall(a_self, "load");', load)
        # proof 1b found no root right after LoadMovie: tried again after the engine's kShow and at each kUpdate
        message = self.main[self.main.index("RE::UI_MESSAGE_RESULT MenuProcessMessage("):]
        message = message[:message.index("\n\t}\n")]
        self.assertLess(message.index("g_engineProcessMessage(a_self, a_message)"),
                        message.index('CodeObjInstall(a_self, type == RE::UI_MESSAGE_TYPE::kShow ? "show" : "update");'))
        self.assertIn("if (g_stage == 2 && CodeObjPending() && ++ticks % 17 == 0) {", self.main)
        self.assertIn("if (attempt > kMaxCodeObjTries) {", self.main)
        self.assertIn("step=code_obj when={} try={} root_of={} get_variable={} root={}", self.main)
        # proof 1b's second run: root_of=0 on every try, because stage b had not read stage c's ids (RootOf's RTTI)
        self.assertIn("bool ChannelIdsNeeded() { return g_stage >= 3 || (g_stage == 2 && g_codeObj); }", self.main)
        self.assertLess(self.main.index("g_codeObj = ReadNumber(ini, L\"CodeObj\", 0) != 0;"),
                        self.main.index("if (!CheckEverything(dir)) {"))
        destroy = self.main[self.main.index("void* MenuDestroy("):]
        self.assertIn("g_codeObjMovie = nullptr;", destroy[:destroy.index("g_engineDtor(")])
        self.assertIn('if (g_codeObj && g_movie.empty()) {', self.main)
        self.assertIn('ParseCodeObjNames(ReadText(ini, L"CodeObjNames"))', self.main)
        self.assertIn('std::string("PlaySound,HideMenu")', self.main)
        install = self.main[self.main.index("bool CodeObjInstall("):]
        install = install[:install.index("\n\t}\n")]
        self.assertIn('top.SetMember("BGSCodeObj", holder)', install)
        handler = self.main[self.main.index("class CodeObjFunction final"):]
        handler = handler[:handler.index("\n\t};\n")]
        for absent in ("AddMessage", "PlaySound(", "Invoke("):   # it logs; only HideMenu may act, and only by Close
            self.assertNotIn(absent, handler, absent)
        # proof 1c: with CodeObjHide=1 the movie's HideMenu closes our menu on the main thread, as the CLOSE button does
        self.assertIn('if (g_codeObjHide && _name == "HideMenu" && g_task) {', handler)
        self.assertIn('g_task->AddTask([n]() { Close(n, "hide_menu"); });', handler)
        self.assertEqual(handler.count("g_task"), 2)
        self.assertIn('if (g_codeObjHide && !g_codeObj) {', self.main)
        self.assertRegex((ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8"),
                         r"\nCodeObjHide=0\r?\n")
        self.assertIn("if (n > kMaxCodeCalls) {", handler)
        ini = (ROOT / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        self.assertRegex(ini, r"\nCodeObj=0\r?\n")
        self.assertRegex(ini, r"\nCodeObjNames=\r?\n")
        readme = (ROOT / "sfse" / "FO4SFPipboyMenu" / "README.md").read_text(encoding="utf-8")
        for text in ("refuse step=ini code_obj=1", "step=code_call n= name= args= arg0=", "`CodeObj` (0)"):
            self.assertIn(text, readme, text)

    def test_sound_read(self):
        # FAL-614: proof 1c recorded; the boot sequence's sounds start with read D4, names and header fields only
        for text in ("**Proof 1c, the result (owner PC, 13 Nov, 04:38 to 04:42 UTC, at `9550c00a`): PASS twice",
                     "**The boot sequence's sounds, step 1: read D4 (owner PC; names and header fields only).**",
                     "`UIPipBoyBootSequenceA`, `B` and `C`", "No samples.", "D4 reads in memory and writes nothing.",
                     "**S2, the plugin plays the player's converted file itself**",
                     "no audio enters Git", "4. The owner PC runs read D4"):
            self.assertIn(text, self.plan, text)

    def test_reads_recorded(self):
        for text in ("**Read on the PC (D1, 13 Nov,", "**Read on the PC (D3, 13 Nov): verified.**",
                     "`Interface\\Pip-Boy\\WorldMap_d.dds`, 2048 x 2048", "**D2 (data names; needed"):
            self.assertIn(text, self.plan, text)


if __name__ == "__main__":
    unittest.main()
