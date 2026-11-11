"""The build pieces kit's writer (dotnet/BuildPieces) on a synthetic Starfield.esm and core, the script's ids against the tool's,
the stager with a fake Papyrus compiler and fake base sources (never a game; the real Papyrus compile, the real Starfield.esm
and the real core are the PC's job). The dotnet tests skip without the .NET SDK."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_build_pieces as mbp  # noqa: E402

PSC = (ROOT / "scripts" / "planet" / "FO4SF_BPQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "BuildPieces" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFBuildPieces.esm"
TYPES = {"race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug", "utility", "int", "float",
         "string", "bool", "math", "location", "activator", "message", "armor", "weapon", "shell", "recipe", "static"}


def const_ids(text):
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_are_the_tools(self):
        ids = const_ids(TOOL_SRC)
        self.assertEqual(ids["QuestId"], 0x800)
        self.assertEqual(int(re.search(r"^int ShellBase = (0x[0-9A-Fa-f]+)", PSC, re.M).group(1), 16), ids["ShellBase"])
        self.assertNotIn("RecipeBase", PSC)                                         # the recipe of a piece is the stager's RecipeIds line
        self.assertEqual((ids["ShellBase"], ids["RecipeBase"], ids["CategoryId"]), (0x802, 0x82A, 0x801))
        self.assertEqual((ids["ListBase"], ids["InnerBase"]), (0x852, 0x860))
        self.assertEqual(ids["InnerBase"] - ids["ListBase"], 14)                    # MaxLists form lists
        self.assertEqual(ids["InnerBase"] + 40, 0x888)                              # one inner recipe per variant, MaxPieces of them
        self.assertEqual(ids["RecipeBase"] - ids["ShellBase"], 40)                 # room for MaxPieces shells
        self.assertIn("MaxPieces = 40", TOOL_SRC)
        self.assertIn(f'string BpPlugin = "{PLUGIN}"', PSC)
        self.assertTrue(PSC.startswith("Scriptname FO4SF_BPQuest extends Quest"))
        self.assertIn('Script = "FO4SF_BPQuest"', TOOL_SRC)

    def test_no_property_and_the_core_is_not_a_master(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        self.assertIn("masters are not exactly [Starfield.esm]", TOOL_SRC)
        self.assertIn('string CorePlugin = "FO4TerrainCore.esm"', PSC)
        self.assertIn('string CorePlugin2 = "FO4TerrainCore_Mars.esm"', PSC)        # the _Mars core when that plugin is absent

    def test_the_log_prefix_and_events_are_the_readers(self):
        from fo4sf.workshop import build_pieces_log as bl
        self.assertIn('string LogName = "FO4SFBP"', PSC)
        self.assertIn('"FO4SFBP rt="', PSC)
        self.assertIn('" end=true"', PSC)
        for e in bl.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e}[ "]')

    def test_no_local_variable_parameter_or_script_variable_is_named_like_a_type_or_a_base_script(self):
        decl = re.findall(r"^\s*(?:[A-Za-z:]+(?:\[\])?)\s+(\w+)\s*(?:=|$)", PSC, re.M)
        params = [p for m in re.findall(r"Function\s+\w+\(([^)]*)\)", PSC) for p in re.findall(r"\s(\w+)\s*(?:,|$)", " " + m)]
        self.assertEqual([n for n in decl + params if n.lower() in TYPES], [])

    def test_the_core_id_line_is_empty_as_committed_and_the_stager_puts_the_ids_in(self):
        self.assertEqual(len(mbp.CORE_LINE.findall(PSC)), 1)
        pieces = [{"core_id": 0x0A2002, "recipe_id": 0x82A}, {"core_id": 0x0A2003, "recipe_id": 0x861}, {"core_id": 0x0A2005, "recipe_id": 0x862}]
        out = mbp.set_core_ids(PSC, pieces)
        self.assertIn("    CoreIds = new int[3]\n    CoreIds[0] = 0x0A2002\n    CoreIds[1] = 0x0A2003\n    CoreIds[2] = 0x0A2005", out)
        self.assertIn("    RecipeIds = new int[3]\n    RecipeIds[0] = 0x00082A\n    RecipeIds[1] = 0x000861\n    RecipeIds[2] = 0x000862", out)   # with variants: the inner recipes
        self.assertNotIn("\n    ;COREIDS\n", out)
        many = mbp.set_core_ids(PSC, [{"core_id": 0x0A2000 + i, "recipe_id": 0x82A + i} for i in range(40)])
        self.assertIn("CoreIds[39] = 0x0A2027", many)
        with self.assertRaises(SystemExit):
            mbp.set_core_ids(PSC, [{"core_id": 1, "recipe_id": 1}] * 41)
        with self.assertRaises(SystemExit):
            mbp.set_core_ids("int x\n", pieces)

    def test_the_script_only_reads_it_places_and_changes_nothing(self):
        code = "\n".join(l for l in PSC.splitlines() if not l.strip().startswith(";"))
        for call in ("PlaceAtMe", "AddItem", "Delete(", "MoveTo", "SetValue", "Disable(", "Enable("):
            self.assertNotIn(call, code)

    def test_the_required_list_has_the_natives_the_script_calls(self):
        code = re.sub(r"\{[^}]*\}", "", "\n".join(l for l in PSC.splitlines() if not l.strip().startswith(";")), flags=re.S)
        called = set(re.findall(r"\b(Game|Debug|Utility)\.(\w+)\(", code)) | {("ScriptObject", "StartTimer")} | {("Form", "GetFormID")}
        for base, name in called:
            self.assertIn(name, mbp.REQUIRED.get(base, []), f"{base}.{name}")
        self.assertIn("StartTimer(", code)
        self.assertIn("GetFormID()", code)


BASES = {
    "Form": "Scriptname Form\nint Function GetFormID() native\n",
    "Game": "Scriptname Game\nForm Function GetFormFromFile(int i, string p) native global\nbool Function IsPluginInstalled(string p) native global\n",
    "Debug": "Scriptname Debug\nFunction Notification(string s) native global\nbool Function OpenUserLog(string n) native global\nbool Function TraceUser(string n, string t) native global\n",
    "Utility": "Scriptname Utility\nfloat Function GetCurrentRealTime() native global\n",
    "ScriptObject": "Scriptname ScriptObject\nFunction StartTimer(float f, int i) native\n",
}


def fake_sources(zip_path, drop=()):
    with zipfile.ZipFile(zip_path, "w") as z:
        for name, text in BASES.items():
            if name not in drop:
                z.writestr(f"Scripts/Source/{name}.psc", text)
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "Flags")


FAKE_COMPILER = """#!{python}
import os, sys
name = sys.argv[1][:-4]
text = open(sys.argv[1], encoding="utf-8").read()
out = [a[3:] for a in sys.argv if a.startswith("-o=")][0]
if os.environ.get("FAKEC_FAIL"):
    print("%s.psc(1,1): error: the fake compiler was told to fail" % name)
    sys.exit(1)
os.makedirs(out, exist_ok=True)
open(os.path.join(out, name + ".pex"), "wb").write(text.encode())
print("Compilation succeeded.")
"""


def fake_compiler(root):
    script = Path(root) / "fakec.py"
    script.write_text(FAKE_COMPILER.format(python=sys.executable), encoding="utf-8")
    if os.name != "nt":
        script.chmod(0o755)
        return script
    cmd = Path(root) / "fakec.cmd"
    cmd.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    return cmd


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_every_required_native_is_found_in_the_fake_sources(self):
        z = Path(self.tmp.name) / "cr.zip"
        fake_sources(z)
        self.assertEqual(mbp.main(["precheck", "--content-resources", str(z)]), 0)

    def test_a_missing_required_native_is_named_and_fails(self):
        z = Path(self.tmp.name) / "cr.zip"
        fake_sources(z, drop=("Utility",))
        out = Path(self.tmp.name) / "p.json"
        self.assertEqual(mbp.main(["precheck", "--content-resources", str(z), "--out", str(out)]), 1)
        self.assertEqual(json.loads(out.read_text())["missing"], ["Utility.GetCurrentRealTime"])


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "BuildPieces"), "-c", "Release", "--nologo"],
                              capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/BuildPieces/bin/Release/net9.0/BuildPieces.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-bp-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.fx = cls.root / "m"
        r = cls.run_tool("fixture", cls.fx)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.sf = cls.fx / "Starfield.esm"
        cls.core = cls.fx / "FO4TerrainCore.esm"

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def build(self, name, *opts, pieces_opts=()):
        out = self.root / name
        proc = self.run_tool("build", self.sf, self.core, out, *opts)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return out

    def test_menu_reads_the_template_recipe_and_its_neighbours(self):
        r = self.run_tool("menu", self.sf)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for want in ("COBJ 2E2F2C co_Outpost_Crafting_WorkbenchIndustrialStation", "created object 000C01 Workbench_Industrial type Furniture",
                     "workbench keyword 000E01 OutpostCategoryCrafting",
                     "recipe filters [000E02 OutpostFilterCraftingStations, 000E03 OutpostFilterCraftingAll]",
                     "build limit (max build count global) 000E10 OutpostStationLimit", "component 000B12 ResOre_Aluminum x4",
                     "component 000B11 ResOre_Iron x3", "recipes under the same workbench keyword (OutpostCategoryCrafting)",
                     "outpost category / filter keywords: 9"):
            self.assertIn(want, r.stdout)

    def test_menu_refuses_a_recipe_that_is_not_there_by_name(self):
        r = self.run_tool("menu", self.sf, "--cobj", "co_Nothing")
        self.assertEqual(r.returncode, 1)
        self.assertIn("0 COBJ named co_Nothing", r.stderr)

    def test_core_lists_the_statics_and_the_default_choice_skips_collision_and_a_repeated_model(self):
        r = self.run_tool("core", self.core)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("core: 12 STAT with a model", r.stdout)
        picks = re.findall(r"^piece (\d): core (\w+) (\S+)", r.stdout, re.M)
        self.assertEqual([(n, i) for n, i, _ in picks], [("1", "0A2002"), ("2", "0A2003"), ("3", "0A2005"), ("4", "0A2006")])
        self.assertNotIn("000a01", r.stdout.split("piece 1")[1])                    # the collision block is not a piece
        pj = json.loads(self.run_tool("pieces", self.core).stdout.strip().splitlines()[-1])
        self.assertEqual([p["core_id"] for p in pj], [0x0A2002, 0x0A2003, 0x0A2005, 0x0A2006])
        self.assertTrue(all(p["name"].startswith("FO4 ") for p in pj))

    def test_pieces_by_editor_id_from_three_up_and_nothing_else(self):
        three = self.run_tool("pieces", self.core, "--pieces", "FO4Core_stat_000a07_fallout4,FO4Core_stat_000a02_fallout4,FO4Core_stat_000a06_fallout4")
        self.assertEqual(three.returncode, 0, three.stderr)
        self.assertEqual([p["core_id"] for p in json.loads(three.stdout.strip().splitlines()[-1])], [0x0A2007, 0x0A2002, 0x0A2006])
        two = self.run_tool("pieces", self.core, "--pieces", "FO4Core_stat_000a07_fallout4,FO4Core_stat_000a02_fallout4")
        self.assertEqual(two.returncode, 1)
        self.assertIn("2 piece(s) chosen: between 3 and 40 are needed", two.stderr)
        five = self.run_tool("pieces", self.core, "--pieces", ",".join(f"FO4Core_stat_000a0{i}_fallout4" for i in (2, 3, 5, 6, 7)))
        self.assertEqual(five.returncode, 0, five.stderr)                           # the four-piece limit is gone
        self.assertEqual(len(json.loads(five.stdout.strip().splitlines()[-1])), 5)
        nope = self.run_tool("pieces", self.core, "--pieces", "FO4Core_stat_000a07_fallout4,FO4Core_stat_000aFF_fallout4,FO4Core_stat_000a02_fallout4")
        self.assertEqual(nope.returncode, 1)
        self.assertIn("0 STAT with a model named FO4Core_stat_000aFF_fallout4", nope.stderr)

    def test_the_named_set_and_wildcards(self):
        r = self.run_tool("pieces", self.core, "--set", "fo4")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = [p["edid"] for p in json.loads(r.stdout.strip().splitlines()[-1])]
        self.assertEqual(got, ["FO4Core_junkwall01", "FO4Core_junkwall02", "FO4Core_piershackwall01", "FO4Core_piershackwall02", "FO4Core_woodcrate"])
        self.assertIn("junkwall03 (or FO4Core_junkwall03) in the core, skipped", r.stderr)    # names the core lacks are reported, not fatal
        star = self.run_tool("pieces", self.core, "--pieces", "FO4Core_junkwall*,FO4Core_stat_000a02_fallout4")
        self.assertEqual([p["edid"] for p in json.loads(star.stdout.strip().splitlines()[-1])], ["FO4Core_junkwall01", "FO4Core_junkwall02", "FO4Core_stat_000a02_fallout4"])
        self.assertEqual(self.run_tool("pieces", self.core, "--set", "nope").returncode, 1)

    def test_a_big_set_builds_checks_and_costs_cycle(self):
        out = self.build("b-set", "--set", "fo4", "--shell", "plain")
        check = self.run_tool("check", out / PLUGIN, self.sf, self.core, "--set", "fo4", "--shell", "plain")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("records: Activator 5, Quest 1, ConstructibleObject 5", check.stdout)
        self.assertIn('COBJ 00082E:FO4SFBuildPieces.esm "FO4 WoodCrate" makes 000806', check.stdout)       # recipe 5 = RecipeBase + 4, shell 5 = ShellBase + 4
        self.assertIn("cost 000B11 x1, sort 15", check.stdout)                             # piece 5: the cost cycle starts again

    def test_tab_files_the_recipes_under_a_vanilla_category_keyword(self):
        for tab, kid in (("structures", "000E20"), ("furniture", "000E21"), ("OutpostCategoryDefenses", "000E25")):
            rep_ = self.build(f"b-tab-rep-{tab}", "--category", "replace", "--tab", tab)
            c = self.run_tool("check", rep_ / PLUGIN, self.sf, self.core, "--category", "replace", "--tab", tab)
            self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
            self.assertIn(f"workbench {kid}, filters [{kid}]", c.stdout)                  # workbench keyword AND filter both the tab's
            self.assertIn("records: Furniture 4, Quest 1, ConstructibleObject 4", c.stdout)    # no keyword of our own
            add = self.build(f"b-tab-add-{tab}", "--category", "add", "--tab", tab)
            c = self.run_tool("check", add / PLUGIN, self.sf, self.core, "--category", "add", "--tab", tab)
            self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
            self.assertIn(f"workbench 000E01, filters [000E02, 000E03, {kid}]", c.stdout)     # template's workbench keyword, tab appended
        bad = self.run_tool("build", self.sf, self.core, str(self.root / "b-tab-bad"), "--tab", "structures")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("--tab needs --category add or replace", bad.stderr)
        nope = self.run_tool("build", self.sf, self.core, str(self.root / "b-tab-nope"), "--category", "add", "--tab", "OutpostCategoryNothing")
        self.assertEqual(nope.returncode, 1)
        self.assertIn("0 KYWD named OutpostCategoryNothing", nope.stderr)
        wrong = self.run_tool("check", rep_ / PLUGIN, self.sf, self.core, "--category", "replace", "--tab", "furniture")
        self.assertEqual(wrong.returncode, 1)

    def test_menu_reads_a_vanilla_variants_entry_whose_created_object_is_a_form_list(self):
        r = self.run_tool("menu", self.sf, "--cobj", "co_Outpost_Furniture_BedList02_Beds")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("created object 000C10 OutpostFurnitureBedList02_Beds type FormList", r.stdout)
        self.assertIn("FLST 3 item(s)", r.stdout)
        self.assertIn("2E3010 co_Outpost_Furniture_BedList02_Decor1_01 [ConstructibleObject]", r.stdout)       # a recipe among the items
        self.assertIn("recipe makes 000C03 OutpostFurnitureBed02, workbench 000E01 OutpostCategoryCrafting, filters [OutpostFilterCraftingStations]", r.stdout)
        self.assertIn("000C02 OutpostFurnitureBed01 [Furniture]", r.stdout)
        self.assertIn("000C03 OutpostFurnitureBed02 [Furniture]", r.stdout)

    def test_the_tabs_table_prints_a_sample_once(self):
        r = self.run_tool("menu", self.sf)
        crafting = r.stdout.split("000E01 OutpostCategoryCrafting: 3 / 0")[1].split("\n  0")[0]
        self.assertEqual(crafting.count("sample 2E2F2C"), 1)

    def test_workbench_and_filter_are_chosen_apart(self):
        # workbench only: the template's filters stay; filter only: the template's workbench stays; both by editor id or by form id
        for name, opts, want in (
                ("wb", ["--workbench", "000E20"], "workbench 000E20, filters [000E02, 000E03]"),
                ("fl", ["--filter", "OutpostCategoryFurniture"], "workbench 000E01, filters [000E21]"),
                ("both", ["--workbench", "000E01", "--filter", "000E22"], "workbench 000E01, filters [000E22]"),
                ("short", ["--workbench", "structures", "--filter", "000E21"], "workbench 000E20, filters [000E21]")):
            out = self.build(f"b-sep-{name}", *opts)
            c = self.run_tool("check", out / PLUGIN, self.sf, self.core, *opts)
            self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
            self.assertIn(want, c.stdout)
            self.assertIn("records: Furniture 4, Quest 1, ConstructibleObject 4", c.stdout)    # no keyword of our own
            other = self.run_tool("check", out / PLUGIN, self.sf, self.core)                    # the plain variant must not pass for it
            self.assertEqual(other.returncode, 1)
        for bad in (["--workbench", "0E6A3E"], ["--filter", "Nothing"], ["--workbench", "000E20", "--tab", "structures"], ["--filter", "000E20", "--category", "add"]):
            r = self.run_tool("build", self.sf, self.core, str(self.root / "b-sep-bad"), *bad)
            self.assertEqual(r.returncode, 1, bad)
            self.assertRegex(r.stderr, "KYWD named|their own choice")

    def test_filter_own_is_a_keyword_of_our_own_with_a_full_name_under_the_chosen_workbench(self):
        opts = ["--workbench", "000E20", "--filter", "own"]
        out = self.build("b-own", *opts)
        c = self.run_tool("check", out / PLUGIN, self.sf, self.core, *opts)
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        self.assertIn("workbench 000E20, filters [000801]", c.stdout)
        self.assertIn("records: Keyword 1, Furniture 4, Quest 1, ConstructibleObject 4", c.stdout)
        opts = ["--filter", "own"]
        out2 = self.build("b-own2", *opts)
        c2 = self.run_tool("check", out2 / PLUGIN, self.sf, self.core, *opts)
        self.assertIn("workbench 000E01, filters [000801]", c2.stdout)
        data = (out / PLUGIN).read_bytes()
        self.assertIn(b"FO4 pieces", data)                                                      # the keyword's full name

    def test_variants_are_one_recipe_whose_created_object_is_a_form_list_of_shells(self):
        opts = ["--set", "fo4", "--variants"]
        out = self.build("b-var", *opts)
        c = self.run_tool("check", out / PLUGIN, self.sf, self.core, *opts)
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        self.assertIn("records: Furniture 5, Quest 1, FormList 2, ConstructibleObject 7", c.stdout)   # 5 shells, 3 recipes (2 walls, 1 crate), 4 inner recipes
        self.assertIn('COBJ 00082A:FO4SFBuildPieces.esm "FO4 junk wall" makes 000852', c.stdout)       # recipe 1 makes form list 1
        self.assertIn('COBJ 00082B:FO4SFBuildPieces.esm "FO4 pier shack wall" makes 000853', c.stdout)
        self.assertIn('COBJ 00082C:FO4SFBuildPieces.esm "FO4 WoodCrate" makes 000806', c.stdout)       # a single piece: its shell, no list
        self.assertIn('"FO4 junk wall" model', c.stdout)                                               # the shells take the group's name
        self.assertNotIn('"FO4 JunkWall01"', c.stdout)
        built = self.run_tool("build", self.sf, self.core, self.root / "b-var2", *opts).stdout
        self.assertIn("5 pieces in 3 recipe(s)", built)
        self.assertIn('recipe 1 00082A makes form list 000852 "FO4 junk wall" of 2 recipes (one per shell, from 000860)', built)
        self.assertIn("piece 1: shell 000802 recipe 000860", built)                                  # the junk walls' own inner recipes
        self.assertIn("piece 3: shell 000804 recipe 000862", built)
        self.assertIn("piece 5: shell 000806 recipe 00082C", built)                                  # the single crate: its own entry's recipe
        self.assertIn("inner COBJ 000860:FO4SFBuildPieces.esm makes 000802, workbench 000E01, filters 2", c.stdout)
        wrong = self.run_tool("check", out / PLUGIN, self.sf, self.core, "--set", "fo4")           # without --variants the same plugin fails
        self.assertEqual(wrong.returncode, 1)

    def test_variants_inner_recipes_bare_have_no_workbench_keyword_and_no_filter(self):
        opts = ["--set", "fo4", "--variants", "--inner", "bare"]
        out = self.build("b-bare", *opts)
        c = self.run_tool("check", out / PLUGIN, self.sf, self.core, *opts)
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        self.assertIn("inner COBJ 000860:FO4SFBuildPieces.esm makes 000802, workbench none, filters 0", c.stdout)
        self.assertIn('COBJ 00082A:FO4SFBuildPieces.esm "FO4 junk wall" makes 000852, workbench 000E01', c.stdout)   # the list's own recipe keeps its filing
        same = self.run_tool("check", out / PLUGIN, self.sf, self.core, "--set", "fo4", "--variants")
        self.assertEqual(same.returncode, 1)                                                          # --inner same does not fit a bare plugin
        bad = self.run_tool("build", self.sf, self.core, str(self.root / "b-inner-bad"), "--set", "fo4", "--variants", "--inner", "x")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("--inner is same or bare", bad.stderr)

    def test_variants_inner_recipes_follow_the_list_recipes_filing_by_default(self):
        opts = ["--set", "fo4", "--variants", "--workbench", "000E01", "--filter", "000E22"]
        out = self.build("b-inner-filing", *opts)
        c = self.run_tool("check", out / PLUGIN, self.sf, self.core, *opts)
        self.assertEqual(c.returncode, 0, c.stdout + c.stderr)
        self.assertIn("inner COBJ 000860:FO4SFBuildPieces.esm makes 000802, workbench 000E01, filters 1", c.stdout)

    def test_pieces_json_names_each_pieces_recipe(self):
        r = self.run_tool("pieces", self.core, "--set", "fo4", "--variants")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got = json.loads([l for l in r.stdout.splitlines() if l.startswith("[")][-1])
        self.assertEqual([x["recipe_id"] for x in got], [0x860, 0x861, 0x862, 0x863, 0x82C])
        plain = json.loads([l for l in self.run_tool("pieces", self.core, "--set", "fo4").stdout.splitlines() if l.startswith("[")][-1])
        self.assertEqual([x["recipe_id"] for x in plain], [0x82A + i for i in range(5)])

    def test_menu_prints_the_art_fields_and_the_tabs(self):
        r = self.run_tool("menu", self.sf)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("fields of created object (Furniture):", r.stdout)
        self.assertIn("Model", r.stdout)
        self.assertIn("fields of COBJ (ConstructibleObject):", r.stdout)
        self.assertIn("tabs (OutpostCategory keywords)", r.stdout)
        self.assertRegex(r.stdout, r"000E20 OutpostCategoryStructures: 0 / 0")
        self.assertRegex(r.stdout, r"000E01 OutpostCategoryCrafting: 3 / 0")

    def test_every_variant_builds_and_checks(self):
        for shell in ("clone", "plain"):
            for cat in ("vanilla", "add", "replace"):
                opts = ["--shell", shell, "--category", cat]
                out = self.build(f"b-{shell}-{cat}", *opts)
                check = self.run_tool("check", out / PLUGIN, self.sf, self.core, *opts)
                self.assertEqual(check.returncode, 0, f"{shell} {cat}\n{check.stdout}{check.stderr}")
                self.assertIn("masters [Starfield.esm]", check.stdout)
                self.assertIn("all checks pass", check.stdout)
                kinds = "Furniture 4" if shell == "clone" else "Activator 4"
                self.assertIn(f"records: {'Keyword 1, ' if cat != 'vanilla' else ''}{kinds}, Quest 1, ConstructibleObject 4", check.stdout)

    def test_the_recipes_are_the_templates_with_a_small_cost_and_the_shells_carry_the_cores_models(self):
        out = self.build("b-detail")
        check = self.run_tool("check", out / PLUGIN, self.sf, self.core).stdout.replace("\\", "/")       # Windows prints the model path with backslashes
        self.assertIn('COBJ 00082A:FO4SFBuildPieces.esm "FO4 Crate01" makes 000802, workbench 000E01, filters [000E02, 000E03], cost 000B11 x1, sort 11', check)
        self.assertIn('COBJ 00082D:FO4SFBuildPieces.esm "FO4 Locker03" makes 000805, workbench 000E01, filters [000E02, 000E03], cost 000B11 x2, sort 14', check)
        self.assertIn('"FO4 Crate01" model Meshes/Props/Crate01.nif (core 0A2002 FO4Core_stat_000a02_fallout4)', check)
        self.assertIn('"FO4 Locker03" model Meshes/Props/Locker03.nif (core 0A2006', check)

    def test_the_own_category_is_a_renamed_copy_of_the_templates_first_filter(self):
        add = self.build("b-add", "--category", "add")
        c = self.run_tool("check", add / PLUGIN, self.sf, self.core, "--category", "add").stdout
        self.assertIn("filters [000E02, 000E03, 000801]", c)
        rep = self.build("b-rep", "--category", "replace")
        c = self.run_tool("check", rep / PLUGIN, self.sf, self.core, "--category", "replace").stdout
        self.assertIn("filters [000E03, 000801]", c)

    def test_the_plugin_adds_records_and_overrides_none_and_the_core_is_not_a_master(self):
        out = self.build("b-bytes", "--category", "add")
        data = (out / PLUGIN).read_bytes()
        self.assertEqual(data[:4], b"TES4")
        self.assertIn(b"Starfield.esm", data[:400])
        self.assertNotIn(b"FO4TerrainCore", data)                                  # nothing names the core: its model paths are strings
        ids = []
        pos = 0
        import struct
        while pos + 24 <= len(data):
            sig = data[pos:pos + 4]
            size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
            if sig == b"GRUP":
                pos += 24
                continue
            if sig != b"TES4":
                ids.append(struct.unpack("<I", data[pos + 12:pos + 16])[0])
            pos += 24 + size
        self.assertTrue(ids)
        self.assertEqual({i >> 24 for i in ids}, {1})                              # every record is ours (load index 1)
        self.assertEqual(sorted(i & 0xFFFFFF for i in ids), [0x800, 0x801, 0x802, 0x803, 0x804, 0x805, 0x82A, 0x82B, 0x82C, 0x82D])

    def test_check_refuses_another_variant_another_choice_and_a_changed_core(self):
        out = self.build("b-refuse")
        wrong_cat = self.run_tool("check", out / PLUGIN, self.sf, self.core, "--category", "add")
        self.assertEqual(wrong_cat.returncode, 1)
        self.assertIn("not exactly 10 records", wrong_cat.stdout)
        wrong_shell = self.run_tool("check", out / PLUGIN, self.sf, self.core, "--shell", "plain")
        self.assertEqual(wrong_shell.returncode, 1)
        self.assertIn("is not an Activator", wrong_shell.stdout)
        wrong_pick = self.run_tool("check", out / PLUGIN, self.sf, self.core, "--pieces",
                                   "FO4Core_stat_000a07_fallout4,FO4Core_stat_000a02_fallout4,FO4Core_stat_000a06_fallout4")
        self.assertEqual(wrong_pick.returncode, 1)
        self.assertIn("not exactly 7 records", wrong_pick.stdout)
        self.assertIn("is not the core static's", wrong_pick.stdout)

    def test_check_refuses_a_plugin_that_masters_something_else_or_overrides(self):
        out = self.root / "b-fake"
        out.mkdir()
        shutil.copy(self.core, out / PLUGIN)                                        # a plugin of another name's records
        r = self.run_tool("check", out / PLUGIN, self.sf, self.core)
        self.assertEqual(r.returncode, 1)
        self.assertIn("FAIL", r.stdout)


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the stage test")
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-bps-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        tool = ROOT / "dotnet/BuildPieces/bin/Release/net9.0/BuildPieces.dll"
        if not tool.exists():
            subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "BuildPieces"), "-c", "Release", "--nologo"], check=True, capture_output=True)
        subprocess.run([cls.dotnet, str(tool), "fixture", str(cls.root / "m")], check=True, capture_output=True)
        cls.sf = cls.root / "m" / "Starfield.esm"
        cls.core = cls.root / "m" / "FO4TerrainCore.esm"

    def setUp(self):
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old
        self.addCleanup(os.environ.__setitem__, "PATH", old)

    def stage(self, name, *extra, z=None):
        z = z or self.root / "cr.zip"
        if not z.exists():
            fake_sources(z)
        final = self.root / name
        code = mbp.main(["stage", "--out", str(final), "--starfield", str(self.sf), "--core", str(self.core),
                         "--compiler", str(fake_compiler(self.root)), "--content-resources", str(z), *extra])
        return code, final

    def test_stage_publishes_a_plan_with_the_variant_and_the_pieces(self):
        code, final = self.stage("stage1", "--category", "add")
        self.assertEqual(code, 0)
        plan = json.loads((final / "plan.json").read_text())
        self.assertEqual(plan["kind"], "build-pieces")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(sorted(plan["outputs"]), sorted([PLUGIN, "Data/Scripts/FO4SF_BPQuest.pex"]))
        self.assertEqual(plan["variant"], {"shell": "clone", "category": "add", "tab": None, "set": None, "cobj": "co_Outpost_Crafting_WorkbenchIndustrialStation",
                                       "workbench": None, "filter": None, "variants": False, "inner": None, "pictures": [], "default_filing": False})
        self.assertEqual([p["core_id"] for p in plan["pieces"]], [0x0A2002, 0x0A2003, 0x0A2005, 0x0A2006])
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mbp.wp.sha256(str(self.sf)))
        self.assertEqual(plan["inputs"]["core"]["sha256"], mbp.wp.sha256(str(self.core)))
        kept = (final / "FO4SF_BPQuest.psc").read_text()
        self.assertIn("    CoreIds[0] = 0x0A2002", kept)
        self.assertIn("    CoreIds[3] = 0x0A2006", kept)
        self.assertTrue((final / "offline_check.txt").read_text().rstrip().endswith("all checks pass"))
        self.assertIn("COBJ 2E2F2C", (final / "menu.txt").read_text())
        self.assertFalse((final / "work").exists())
        self.assertEqual(mbp.verify_stage(str(final), plan, str(self.sf.parent)), [])
        with self.assertRaises(SystemExit) as e:                                    # an earlier stage is never overwritten
            self.stage("stage1")
        self.assertIn("exists", str(e.exception))
        (final / PLUGIN).write_bytes(b"changed")
        self.assertTrue(any("changed after the stage" in p for p in mbp.verify_stage(str(final), plan)))

    def test_stage_set_fo4_is_rung_a_by_default_with_variant_recipes_and_pictures(self):
        code, final = self.stage("stage-fo4", "--set", "fo4", "--variants", "--pictures", "3")
        self.assertEqual(code, 0)
        plan = json.loads((final / "plan.json").read_text())
        v = plan["variant"]
        self.assertEqual((v["workbench"], v["filter"], v["default_filing"], v["variants"], v["inner"]), ("2CFDE6", "06D72D", True, True, "same"))
        icons = [f"Textures/Interface/WorkshopIcons/{PLUGIN}/0000080{n}cl.dds" for n in (2, 3, 4)]
        self.assertEqual(v["pictures"], icons)
        for rel in icons:
            data = (final / "Data" / rel).read_bytes()
            self.assertEqual((data[:4], len(data)), (b"DDS ", 148 + 128 * 128))
            self.assertIn("Data/" + rel, plan["outputs"])                                    # pinned like every staged file
        self.assertFalse((final / "Data" / "Textures" / "Interface" / "WorkshopIcons" / PLUGIN / "00000805cl.dds").exists())   # only the first three
        kept = (final / "FO4SF_BPQuest.psc").read_text()
        self.assertIn("    RecipeIds[0] = 0x000860", kept)                                     # junk walls: their inner recipes
        self.assertIn("    RecipeIds[4] = 0x00082C", kept)                                     # the single crate: its entry's recipe
        self.assertEqual([p["recipe_id"] for p in plan["pieces"]], [0x860, 0x861, 0x862, 0x863, 0x82C])
        self.assertIn("pictures=3", (final / "README.txt").read_text())
        self.assertTrue((final / "offline_check.txt").read_text().rstrip().endswith("all checks pass"))
        self.assertEqual(mbp.verify_stage(str(final), plan, str(self.sf.parent)), [])
        code, kept_tpl = self.stage("stage-fo4-tpl", "--set", "fo4", "--template-filing")
        self.assertEqual(code, 0)
        tv = json.loads((kept_tpl / "plan.json").read_text())["variant"]
        self.assertEqual((tv["workbench"], tv["filter"], tv["default_filing"], tv["pictures"]), (None, None, False, []))
        with self.assertRaises(SystemExit):
            self.stage("stage-fo4-bad", "--set", "fo4", "--pictures", "41")

    def test_an_own_filing_switch_beats_the_fo4_default(self):
        code, final = self.stage("stage-fo4-own", "--set", "fo4", "--workbench", "000E01", "--filter", "000E22")
        self.assertEqual(code, 0)
        v = json.loads((final / "plan.json").read_text())["variant"]
        self.assertEqual((v["workbench"], v["filter"], v["default_filing"]), ("000E01", "000E22", False))

    def test_verify_stage_notices_a_changed_core_or_starfield(self):
        code, final = self.stage("stage2", "--shell", "plain")
        self.assertEqual(code, 0)
        plan = json.loads((final / "plan.json").read_text())
        data = self.root / "gamedata"
        data.mkdir()
        shutil.copy(self.sf, data / "Starfield.esm")
        shutil.copy(self.core, data / "FO4TerrainCore.esm")
        self.assertEqual(mbp.verify_stage(str(final), plan, str(data)), [])
        (data / "FO4TerrainCore.esm").write_bytes(b"another core")
        self.assertTrue(any("FO4TerrainCore.esm changed since the stage" in p for p in mbp.verify_stage(str(final), plan, str(data))))
        (data / "Starfield.esm").write_bytes(b"another game")
        self.assertTrue(any("Starfield.esm changed since the stage" in p for p in mbp.verify_stage(str(final), plan, str(data))))

    def test_stage_refuses_when_a_required_native_is_missing(self):
        z = self.root / "cr2.zip"
        fake_sources(z, drop=("Debug",))
        final = self.root / "stage3"
        with self.assertRaises(SystemExit) as e:
            self.stage("stage3", z=z)
        self.assertIn("Debug.TraceUser", str(e.exception))
        self.assertFalse(final.exists())

    def test_stage_refuses_when_the_compile_fails_and_publishes_nothing(self):
        z = self.root / "cr3.zip"
        fake_sources(z)
        final = self.root / "stage4"
        os.environ["FAKEC_FAIL"] = "1"
        self.addCleanup(os.environ.pop, "FAKEC_FAIL", None)
        with self.assertRaises(SystemExit) as e:
            self.stage("stage4", z=z)
        self.assertIn("the Papyrus compile of FO4SF_BPQuest.psc failed", str(e.exception))
        self.assertIn("the fake compiler was told to fail", str(e.exception))
        self.assertFalse(final.exists())                                            # only the .partial attempt is left


if __name__ == "__main__":
    unittest.main()
