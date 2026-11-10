"""FO4SFPipboyMenu's world surface (FAL-250): src/world.cpp as text (no compiler here: the PC build is the compile
check), its four calls in main.cpp after every check of #704, the ini shipping it off, the README job card naming every
refusal it can log, and make_pipboy_probe.py twin, which writes our movie byte for byte at a vanilla movie's path."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
SCRIPT = ROOT / "scripts" / "ui" / "make_pipboy_probe.py"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "ui"))
import make_pipboy_probe as mpp  # noqa: E402
import make_probe_swf  # noqa: E402


def function(text, signature, indent="\t"):
    """The body of the function whose definition starts with `signature` (to its closing brace at `indent`)."""
    start = text.index(signature)
    return text[start:text.index(f"\n{indent}}}\n", start)]


class WorldSourceTests(unittest.TestCase):
    world = (PLUGIN / "src" / "world.cpp").read_text(encoding="utf-8")
    header = (PLUGIN / "src" / "world.h").read_text(encoding="utf-8")
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")

    def test_no_id_no_hook_no_write_into_the_engine(self):
        for absent in ("REL::", "SafeWrite", "trampoline", "write_branch", "VirtualProtect", "SetFlags", "flagsUpdated"):
            self.assertNotIn(absent, self.world, absent)
        # the only engine calls are the overlay key's own, and the candidate's one BSFixedString
        self.assertEqual(re.findall(r"queue->AddMessage\(([^,]+),", self.world), ["WorldName()"])
        self.assertEqual(self.world.count("new RE::BSFixedString("), 1)

    def test_main_calls_world_only_after_its_checks(self):
        self.assertEqual(len(re.findall(r"\bWorld::\w+\(", self.main)), 3)
        load = self.main[self.main.index("SFSE_PLUGIN_LOAD("):]
        self.assertLess(load.index("if (!CheckEverything(dir)) {"),
                        load.index("World::Configure(ini, g_stage, g_key, g_base, g_imageSize);"))
        self.assertLess(load.index('Refuse("version"'), load.index("World::Configure("))
        register = function(self.main, "void Register()")
        self.assertLess(register.index('REX::INFO("step=register result=ok'), register.index("World::Start(g_task);"))
        self.assertIn("World::OnMovieCreated(a_menu);", function(self.main, "void OnMovieCreated(RE::IMenu* a_menu)"))
        self.assertIn('#include "world.h"', self.main)
        for name in ("void Configure(", "void Start(", "void OnMovieCreated(const RE::IMenu* a_menu)"):
            self.assertIn(name, self.header)

    def test_off_means_nothing_runs(self):
        configure = function(self.world, "\tvoid Configure(")
        self.assertIn('if (ReadNumber(a_ini, L"World", 0) == 0) {\n\t\t\treturn;', configure)
        self.assertLess(configure.index("if (!Read(a_ini, a_stage, a_menuKey)) {"), configure.index("g_on = true;"))
        for signature in ("\tvoid Start(", "\tvoid OnMovieCreated("):
            self.assertIn("if (!g_on", function(self.world, signature).split("\n")[2], signature)
        self.assertIn("\nWorld=0\n", self.ini)
        self.assertIn("\nStage=0\n", self.ini)

    def test_every_address_is_checked_before_it_is_read(self):
        cls = function(self.world, "std::string ClassOf(")
        self.assertLess(cls.index("if (!InImage(vtable - 8, 8)) {"),
                        cls.index("*reinterpret_cast<const std::uintptr_t*>(vtable - 8)"))
        self.assertLess(cls.index("!InImage(locator, 0x14)"), cls.index("locator + 0x0C"))
        self.assertIn("i < kNameMax && InImage(type + 0x10 + i, 1)", cls)

    def test_the_candidate_is_sent_only_when_registered(self):
        toggle = function(self.world, "void Toggle(")
        order = [toggle.index(s) for s in ("if (g_menu.empty()) {", "if (!ui || !queue) {",
                                           "if (!ui->IsMenuRegistered(WorldName())) {", "ui->IsMenuOpen(WorldName())",
                                           "queue->AddMessage(")]
        self.assertEqual(order, sorted(order))
        read = function(self.world, "bool Read(")
        self.assertIn('if (lower == "fo4sf_pipboymenu") {', read)
        self.assertIn("g_key == a_menuKey", read)

    def test_the_census_is_bounded_and_once_per_name_and_flags(self):
        movie = function(self.world, "\tvoid OnMovieCreated(")
        self.assertIn('g_seen.insert(std::format("{}|{}", name, a_menu->flags)).second', movie)
        self.assertIn("if (g_seen.size() == kMaxMovies) {", movie)
        self.assertIn("g_worldLoads.fetch_add(1) < kMaxWorldLoads", movie)
        self.assertIn("if (n == kMaxRegistered) {", function(self.world, "void CensusRegistered("))

    def test_the_ini_keys_and_defaults(self):
        for key, default in (("WorldKey", "0x77"), ("WorldMenu", ""), ("WorldMovie", "")):
            self.assertIn(f"\n{key}={default}\n", self.ini)
            self.assertIn(f'L"{key}"', self.world)
        self.assertIn('ReadNumber(a_ini, L"WorldKey", 0x77)', self.world)

    def test_the_readme_names_every_line_and_lead(self):
        world = self.readme[self.readme.index("## World surface (FAL-250)"):self.readme.index("\n## Job card\n")]
        reasons = set(re.findall(r"reason=([a-z_]+)", self.world))
        self.assertEqual(reasons, {"needs_movie_stage", "key", "world_menu", "world_menu_is_ours", "world_movie",
                                   "no_world_menu", "no_ui_or_queue", "not_registered", "create_failed"})
        for reason in reasons - {"create_failed"}:
            self.assertIn(f"reason={reason}", world, reason)
        for step in set(re.findall(r'"(?:refuse )?step=([a-z_]+)', self.world)):
            self.assertIn(f"step={step}", world, step)
        leads = re.search(r"kLeads\{([^;]+)\};", self.world).group(1)
        for lead in re.findall(r'"([a-z0-9]+)"sv', leads):
            self.assertIn(f"`{lead}`", world, lead)
        for part in ("Overlay control", "World candidate", "Negative", "Inconclusive", "useful FAIL",
                     "testmenus_dynamictexturedgeo", "make_pipboy_probe.py twin", "Starfield - Interface.ba2"):
            self.assertIn(part, world, part)


class TwinTests(unittest.TestCase):
    def test_the_twin_is_the_movie_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, movie = mpp.stage(tmp)
            twin = mpp.twin(tmp, "Interface/testmenus_dynamictexturedgeo.swf")
            self.assertEqual(os.path.relpath(twin, tmp).replace(os.sep, "/"),
                             "Data/Interface/testmenus_dynamictexturedgeo.swf")
            self.assertEqual(Path(twin).read_bytes(), Path(movie).read_bytes())
            self.assertEqual(Path(twin).read_bytes(), make_probe_swf.movie_bytes())

    def test_a_twin_copies_whatever_movie_was_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, movie = mpp.stage(tmp, label=False)
            twin = mpp.twin(tmp, "Interface/Terminals/terminalmenu.gfx")
            self.assertEqual(Path(twin).read_bytes(), Path(movie).read_bytes())

    def test_names_that_are_not_a_vanilla_movie_path_are_refused(self):
        for rel in ("FO4SF_PipboyMenu.swf", "Textures/x.swf", "Interface/../x.swf", "Interface//x.swf",
                    "Interface/x.dds", "Interface/x y.swf", "Interface/é.swf", "interface/fo4sf_pipboymenu.SWF",
                    mpp.MOVIE, "Interface"):
            self.assertIsNotNone(mpp.twin_problem(rel), rel)
        with tempfile.TemporaryDirectory() as tmp:
            mpp.stage(tmp)
            with self.assertRaises(mpp.TwinError):
                mpp.twin(tmp, mpp.MOVIE)
            self.assertEqual(sorted(os.listdir(os.path.join(tmp, "Data", "Interface"))), ["FO4SF_PipboyMenu.swf"])

    def test_the_stage_comes_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(OSError):
                mpp.twin(tmp, "Interface/x.swf")

    def test_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = [sys.executable, str(SCRIPT)]
            self.assertEqual(subprocess.run(run + ["stage", tmp], capture_output=True).returncode, 0)
            ok = subprocess.run(run + ["twin", tmp, "Interface/terminalmenu.swf"], capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertIn("WorldMovie=Interface/terminalmenu.swf", ok.stdout)
            bad = subprocess.run(run + ["twin", tmp, "Interface/../x.swf"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertIn("make_pipboy_probe:", bad.stderr)


if __name__ == "__main__":
    unittest.main()
