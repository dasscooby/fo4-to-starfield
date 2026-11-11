"""The workshop probe's writer (dotnet/WorkshopProbe) on a synthetic Starfield.esm, its scripts' ids against the tool's, the
optional-native mechanism, the scan of the base scripts and the stage with a fake Papyrus compiler and fake base sources
(never a game; the real Papyrus compile and the real Starfield.esm are the PC's job). The dotnet tests skip without the
.NET SDK."""
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_workshop_probe as mws  # noqa: E402

PSC = (ROOT / "scripts" / "planet" / "FO4SF_WSProbeQuest.psc").read_text(encoding="utf-8")
HAND_PSC = (ROOT / "scripts" / "planet" / "FO4SF_WSHandQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "WorkshopProbe" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFWorkshopProbe.esm"
TYPES = {"race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug", "utility", "int", "float",
         "string", "bool", "math", "location", "activator", "message", "armor", "weapon", "pad", "bench", "beacon"}


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
        self.assertEqual(ids["HandQuestId"], 0x801)
        self.assertEqual(ids["KitId"], 0x802)
        m = re.search(r"^int KitId = (0x[0-9A-Fa-f]+)", HAND_PSC, re.M)
        self.assertEqual(int(m.group(1), 16), ids["KitId"])
        for text in (PSC, HAND_PSC):
            self.assertIn(f'string ProbePlugin = "{PLUGIN}"', text)
            self.assertIn('int BenchBaseId = 0x0A2ECD', text)                  # the core's base, as the 11 Nov PC run read it
            self.assertIn('int WorkshopKwId = 0x054BA7', text)
        self.assertIn('int PadBaseId = 0x024DC7', PSC)                           # the vanilla OutpostPlayerHouseActivator
        self.assertTrue(PSC.startswith("Scriptname FO4SF_WSProbeQuest extends Quest"))
        self.assertTrue(HAND_PSC.startswith("Scriptname FO4SF_WSHandQuest extends Quest"))
        self.assertIn('Script = "FO4SF_WSProbeQuest"', TOOL_SRC)
        self.assertIn('HandScript = "FO4SF_WSHandQuest"', TOOL_SRC)

    def test_no_property_and_the_core_is_not_a_master(self):
        for text in (PSC, HAND_PSC):
            self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", text, re.M | re.I))
            self.assertNotIn(" Property ", text)
        self.assertIn("masters are not exactly [Starfield.esm]", TOOL_SRC)
        self.assertIn("FO4TerrainCore.esm", PSC)

    def test_every_stage_the_script_runs_is_a_stage_of_the_quest(self):
        ran = {int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)} | {int(s) for s in re.findall(r"GetStageDone\((\d+)\)", PSC)}
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(sorted(ran), [int(x) for x in m.group(1).split(",")])
        self.assertEqual(sorted(ran), [10, 12, 13, 20, 21, 22, 23, 24, 30, 31, 32, 33, 34, 40, 50, 60])
        self.assertEqual(PSC.count("StageList = new int[15]"), 1)
        self.assertEqual(len(re.findall(r"StageList\[\d+\] = \d+", PSC)), 15)

    def test_the_log_prefix_and_events_are_the_readers(self):
        from fo4sf.workshop import probe_log
        self.assertIn('string LogName = "FO4SFWorkshop"', PSC)
        self.assertIn('"FO4SFWS rt="', PSC)
        self.assertIn('" end=true"', PSC)
        for e in probe_log.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e}[ "]')
        self.assertIn('"FO4SFWSHAND rt="', HAND_PSC)
        self.assertIn('string LogName = "FO4SFWSHand"', HAND_PSC)

    def test_the_calls_under_test_are_made_one_per_sub_stage(self):
        self.assertIn("p.PlaceAtMe(base, 1, persist, false, false)", PSC)           # persistent by default (stage 10)
        self.assertIn("bool persist = true, bool move = true", PSC)
        self.assertIn("r.Disable(false)", PSC)
        self.assertIn("r.Enable(false)", PSC)
        self.assertIn("r.Activate(p, false)", PSC)
        self.assertIn("Game.GetFormFromFile(PadBaseId", PSC)
        self.assertIn("DoCall(stage - 20", PSC)
        self.assertIn("DoCall(stage - 30", PSC)
        self.assertNotIn("Property", PSC)

    def test_the_committed_scripts_compile_alone_every_optional_line_is_a_comment(self):
        for text in (PSC, HAND_PSC):
            self.assertEqual(mws.enable(text, []), text)
        self.assertEqual(mws.optional_names(PSC), ["ObjectReference.GetWorkshop", "ObjectReference.MoveTo", "ObjectReference.SetActorOwner",
                                                   "ObjectReference.StartWorkshop", "ObjectReference.Delete"])
        self.assertEqual(mws.optional_names(HAND_PSC), ["ObjectReference.MoveTo"])

    def test_no_local_variable_parameter_or_script_variable_is_named_like_a_type_or_a_base_script(self):
        """FAL-273 finding: Papyrus names are case-blind and 'race' as a variable is refused by the compiler."""
        for text in (HAND_PSC, PSC):
            decl = re.findall(r"^\s*(?:[A-Za-z:]+(?:\[\])?)\s+(\w+)\s*(?:=|$)", text, re.M)
            params = [p for m in re.findall(r"Function\s+\w+\(([^)]*)\)", text) for p in re.findall(r"\s(\w+)\s*(?:,|$)", " " + m)]
            self.assertEqual([n for n in decl + params if n.lower() in TYPES], [])

    def test_stage_40_says_so_when_no_beacon_is_given_and_the_stager_puts_the_id_in(self):
        self.assertRegex(PSC, r"(?m)^int BeaconId = 0 +;BEACON")
        self.assertIn("beacon=not given", PSC)
        self.assertEqual(mws.set_beacon(PSC, ""), PSC)
        on = mws.set_beacon(PSC, "0x1A2B3C")
        self.assertRegex(on, r"(?m)^int BeaconId = 0x1a2b3c  ;BEACON")
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        with self.assertRaises(SystemExit):
            mws.set_beacon(PSC, "zz")

    def test_names_the_real_starfield_declares_and_the_keyword_comes_from_starfield_esm(self):
        """PC offline pass on #732: Actor.GetActorBase does not exist (GetLeveledActorBase does), WorkshopKeyword 054BA7 is a
        Starfield.esm record (the core only points at it)."""
        for text in (PSC, HAND_PSC):
            self.assertNotIn("GetActorBase", text)
            self.assertNotIn("WorkshopKwId, CoreName()", text)
            self.assertIn('GetFormFromFile(WorkshopKwId, "Starfield.esm")', text)
        self.assertIn("p.GetLeveledActorBase()", PSC)
        self.assertNotIn("GetActorBase", "".join(mws.REQUIRED["Actor"]))

    def test_disable_is_not_followed_by_an_immediate_enable(self):
        """PC 11 Nov: Disable + Enable in one call left the reference disabled; the Enable comes from a timer 2 s later."""
        call = PSC.split("Function DoCall")[1].split("Function Cleanup")[0]
        self.assertNotIn("r.Enable(false)", call)
        self.assertIn("StartTimer(ENABLE_S, TIMER_ENABLE)", call)
        self.assertIn("Reenable(BenchRef", PSC)
        self.assertIn("Reenable(PadRef", PSC)

    def test_stages_12_and_13_vary_persistence_and_the_move(self):
        self.assertIn('TempRef = Spawn(FindBase(), "bench_temp", stage, false, true)', PSC)
        self.assertIn('StillRef = Spawn(FindBase(), "bench_still", stage, true, false)', PSC)
        self.assertIn("p.PlaceAtMe(base, 1, persist, false, false)", PSC)
        self.assertIn(";OPT ObjectReference.MoveTo     if r && move", PSC)

    def test_the_hand_mode_places_the_bench_where_the_kit_vanishes(self):
        self.assertIn("p.GetItemCount(kit) < 1", HAND_PSC)
        self.assertIn("p.AddItem(kit, 1, true)", HAND_PSC)
        self.assertIn("p.PlaceAtMe(base, 1, true, false, false)", HAND_PSC)
        self.assertIn("Debug.Notification(msg)", HAND_PSC)
        self.assertNotIn("GetStageDone", HAND_PSC)

    def test_the_required_list_has_the_natives_the_scripts_call_outside_an_optional_line(self):
        for base, names in {"Actor": ["PlaceAtMe", "GetItemCount", "AddItem"], "ObjectReference": ["Activate", "Disable", "Enable", "Is3DLoaded"],
                            "Form": ["HasKeyword"], "Debug": ["Notification"]}.items():
            for n in names:
                self.assertIn(n, mws.REQUIRED[base])


BASES = {
    "Form": "Scriptname Form\nint Function GetFormID() native\nbool Function HasKeyword(Keyword k) native\n",
    "ObjectReference": "Scriptname ObjectReference extends Form\nfloat Function GetPositionX() native\nfloat Function GetPositionY() native\n"
                       "float Function GetPositionZ() native\nfloat Function GetDistance(ObjectReference a) native\nCell Function GetParentCell() native\n"
                       "float Function GetAngleZ() native\nObjectReference Function PlaceAtMe(Form f, int n, bool a, bool b, bool c) native\n"
                       "int Function GetItemCount(Form f) native\nFunction AddItem(Form f, int n, bool s) native\nbool Function Is3DLoaded() native\n"
                       "bool Function IsDisabled() native\nFunction Disable(bool f) native\nFunction Enable(bool f) native\n"
                       "Function Activate(ObjectReference a, bool d) native\nForm Function GetBaseObject() native\n"
                       "Function MoveTo(ObjectReference a, float x, float y, float z, bool m) native\nFunction StartWorkshop(bool b) native\n"
                       "Function Delete() native\nFunction SetOutpostFlag() native\n",
    "Actor": "Scriptname Actor extends ObjectReference\nActorBase Function GetLeveledActorBase() native\n",
    "Game": "Scriptname Game\nActor Function GetPlayer() native global\nForm Function GetFormFromFile(int i, string p) native global\n"
            "bool Function IsPluginInstalled(string p) native global\n",
    "Debug": "Scriptname Debug\nFunction Notification(string s) native global\nbool Function OpenUserLog(string n) native global\nbool Function TraceUser(string n, string t) native global\n",
    "Utility": "Scriptname Utility\nfloat Function GetCurrentRealTime() native global\n",
    "Math": "Scriptname Math\nfloat Function Sin(float f) native global\nfloat Function Cos(float f) native global\n",
    "ScriptObject": "Scriptname ScriptObject\nFunction StartTimer(float f, int i) native\n",
    "Quest": "Scriptname Quest extends ScriptObject\nbool Function GetStageDone(int i) native\n",
    "OutpostBeaconScript": "Scriptname OutpostBeaconScript extends ObjectReference\n; a comment with Outpost( in it\nEvent OnActivate(ObjectReference a)\n    CreateOutpost(a)\n    Utility.Wait(1.0)\nEndEvent\n",
}


def fake_sources(zip_path, drop=()):
    with zipfile.ZipFile(zip_path, "w") as z:
        for name, text in BASES.items():
            if name not in drop:
                z.writestr(f"Scripts/Source/{name}.psc", text)
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "Flags")


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_inherited_names_are_found_and_undeclared_optional_ones_are_reported(self):
        z = os.path.join(self.tmp.name, "cr.zip")
        fake_sources(z)
        r = mws.precheck_sources(mws.read_sources(z), PSC, HAND_PSC)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["required"]["Actor.GetDistance"])                  # declared on ObjectReference
        self.assertEqual(r["optional"], {"ObjectReference.GetWorkshop": False, "ObjectReference.MoveTo": True,
                                         "ObjectReference.SetActorOwner": False, "ObjectReference.StartWorkshop": True,
                                         "ObjectReference.Delete": True})

    def test_a_missing_required_native_is_named(self):
        z = os.path.join(self.tmp.name, "cr.zip")
        fake_sources(z)
        sources = mws.read_sources(z)
        sources["objectreference"] = sources["objectreference"].replace("Activate", "Other")
        self.assertEqual(mws.precheck_sources(sources, PSC)["missing"], ["ObjectReference.Activate"])

    def test_scan_lists_the_workshop_natives_and_the_beacon_scripts_calls(self):
        z = os.path.join(self.tmp.name, "cr.zip")
        fake_sources(z)
        lines = mws.scan_sources(mws.read_sources(z))
        self.assertIn("objectreference: Function StartWorkshop(bool b) native", lines)
        self.assertIn("objectreference: Function SetOutpostFlag() native", lines)
        self.assertIn("== script outpostbeaconscript", lines)
        self.assertIn("CreateOutpost(a)", [l.strip() for l in lines])
        self.assertNotIn("; a comment with Outpost( in it", [l.strip() for l in lines])
        self.assertFalse(any("GetPositionX" in l for l in lines))


FAKE_COMPILER = """#!{python}
import os, sys
name = sys.argv[1][:-4]
text = open(sys.argv[1], encoding="utf-8").read()
out = [a[3:] for a in sys.argv if a.startswith("-o=")][0]
if any("r.Delete()" in l for l in text.splitlines() if not l.startswith(";")):
    print("%s.psc(1,1): error: Delete does not match the fake compiler" % name)
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


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "WorkshopProbe"), "-c", "Release", "--nologo"],
                              capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/WorkshopProbe/bin/Release/net9.0/WorkshopProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-ws-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.master = cls.root / "m" / "Starfield.esm"
        r = cls.run_tool("fixture", cls.root / "m")
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def test_build_and_check(self):
        out = self.root / "b1"
        proc = self.run_tool("build", self.master, out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("copy of Misc_Junk_Fork", proc.stdout)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("QUST FO4SF_WSProbeQuest flags StartGameEnabled stages [10,12,13,20,21,22,23,24,30,31,32,33,34,40,50,60]", check.stdout)
        self.assertIn("QUST FO4SF_WSHandQuest flags StartGameEnabled stages [10] scripts [FO4SF_WSHandQuest (0 properties)]", check.stdout)
        self.assertIn("records: MiscItem 1, Quest 2", check.stdout)

    def test_the_plugin_adds_records_and_overrides_none(self):
        """Raw bytes: every record carries load index 1 (our own plugin; Starfield.esm is master 0)."""
        out = self.root / "b2"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        data = (out / PLUGIN).read_bytes()
        self.assertEqual(data[:4], b"TES4")
        kinds, ids = {}, []

        def walk(buf, i, end):
            while i < end:
                sig = buf[i:i + 4]
                size = struct.unpack_from("<I", buf, i + 4)[0]
                if sig == b"GRUP":
                    walk(buf, i + 24, i + size)
                    i += size
                    continue
                form = struct.unpack_from("<I", buf, i + 12)[0]
                kinds[sig] = kinds.get(sig, 0) + 1
                if sig != b"TES4":
                    ids.append(form)
                i += 24 + size
        walk(data, 0, len(data))
        self.assertTrue(ids and all(f >> 24 == 1 for f in ids), [hex(f) for f in ids if f >> 24 != 1])
        self.assertEqual({k: v for k, v in kinds.items() if k != b"TES4"}, {b"MISC": 1, b"QUST": 2})
        self.assertEqual(sorted(f & 0xFFFFFF for f in ids), [0x800, 0x801, 0x802])

    def test_an_item_that_is_not_there_is_refused_by_name(self):
        proc = self.run_tool("build", self.master, self.root / "b5", "--item", "NoSuchMisc")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 MISC named NoSuchMisc", proc.stderr)

    def test_the_kit_copies_the_item_asked_for_and_check_refuses_another(self):
        out = self.root / "b6"
        proc = self.run_tool("build", self.master, out, "--item", "Misc_Other")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("copy of Misc_Other", proc.stdout)
        self.assertEqual(self.run_tool("check", out / PLUGIN, self.master, "--item", "Misc_Other").returncode, 0)
        wrong = self.run_tool("check", out / PLUGIN, self.master, "--item", "Misc_Junk_Fork")
        self.assertEqual(wrong.returncode, 1, wrong.stdout)

    def test_resources_lists_the_stations_components_and_additem_lines(self):
        proc = self.run_tool("resources", self.master)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("COBJ 000D01 co_Workbench_Industrial: makes 000C01 Workbench_Industrial", proc.stdout)
        self.assertIn("000B02 Ore_Aluminum x4 -> item", proc.stdout)
        self.assertIn("000B11 ResOre_Iron x3 -> MISC 000B01 Ore_Iron (of 2 that link it)", proc.stdout)   # IRES -> the MISC named like it
        self.assertNotIn("00000B11", proc.stdout)                              # never an additem for the resource record itself
        self.assertIn("player.additem 00000B01 6", proc.stdout)               # twice the count asked for
        self.assertIn("player.additem 00000B02 8", proc.stdout)
        none = self.run_tool("resources", self.master, "--match", "NoSuchStation")
        self.assertEqual(none.returncode, 1)

    def test_survey_lists_records_whose_name_says_outpost_or_beacon(self):
        proc = self.run_tool("survey", self.master)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Furniture\t000C02\tOutpostBeaconFurniture", proc.stdout)

    def test_stage_publishes_a_plan_with_the_optional_natives_fate(self):
        z = self.root / "cr.zip"
        fake_sources(z)
        compiler = fake_compiler(self.root)
        final = self.root / "stage"
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        code = mws.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", str(compiler),
                         "--content-resources", str(z), "--beacon", "0x00ABCDEF"])
        self.assertEqual(code, 0)
        plan = json.loads((final / "plan.json").read_text())
        self.assertEqual(plan["kind"], "workshop-probe")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(sorted(plan["outputs"]), sorted([PLUGIN, "Data/Scripts/FO4SF_WSProbeQuest.pex", "Data/Scripts/FO4SF_WSHandQuest.pex"]))
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mws.sha256(str(self.master)))
        self.assertEqual(plan["optional"]["ObjectReference.StartWorkshop"], "kept")
        self.assertEqual(plan["optional"]["ObjectReference.GetWorkshop"], "not declared in the base scripts")
        self.assertEqual(plan["optional"]["ObjectReference.SetActorOwner"], "not declared in the base scripts")
        self.assertTrue(plan["optional"]["ObjectReference.Delete"].startswith("declared but did not compile"))
        self.assertEqual(plan["optional_hand"]["ObjectReference.MoveTo"], "kept")
        self.assertEqual(plan["beacon"], "0x00ABCDEF")
        kept = (final / "FO4SF_WSProbeQuest.psc").read_text()
        self.assertIn("r.StartWorkshop(true)", kept)
        self.assertNotIn(";OPT ObjectReference.StartWorkshop", kept)
        self.assertIn(";OPT ObjectReference.GetWorkshop", kept)                  # still a comment
        self.assertRegex(kept, r"(?m)^int BeaconId = 0x00abcdef  ;BEACON")
        self.assertEqual(mws.verify_stage(str(final), plan, str(self.master.parent)), [])
        self.assertTrue((final / "offline_check.txt").read_text().rstrip().endswith("all checks pass"))
        self.assertIn("player.additem 00000B01 6", (final / "additem.txt").read_text())
        self.assertIn("== script outpostbeaconscript", (final / "scan.txt").read_text())
        self.assertFalse((final / "work").exists())
        with self.assertRaises(SystemExit) as e:                               # an earlier stage is never overwritten
            mws.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", str(compiler), "--content-resources", str(z)])
        self.assertIn("exists", str(e.exception))
        (final / PLUGIN).write_bytes(b"changed")
        self.assertTrue(any("changed after the stage" in p for p in mws.verify_stage(str(final), plan)))

    def test_stage_refuses_when_a_required_native_is_missing(self):
        z = self.root / "cr2.zip"
        fake_sources(z, drop=("Quest",))
        final = self.root / "stage2"
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        with self.assertRaises(SystemExit) as e:
            mws.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", "/nonexistent", "--content-resources", str(z)])
        self.assertIn("Quest.GetStageDone", str(e.exception))
        self.assertFalse(final.exists())


if __name__ == "__main__":
    unittest.main()
