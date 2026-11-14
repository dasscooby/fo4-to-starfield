"""The map marker probe (FAL-771): its quest script's ids and stages against the writer's (dotnet/MarkerProbe), the plugin tool on a
synthetic Starfield.esm, the stager with a fake Papyrus compiler, the plan verification and the log reader (never a game; the real
compile and every in-game fact are the PC's job). The dotnet tests skip without the .NET SDK."""
import contextlib
import io
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_marker_probe as mmp  # noqa: E402
from test_anim_probe import BASES, fake_compiler, fake_sources  # noqa: E402

BASES_MARK = {**BASES,
              "ObjectReference": BASES["ObjectReference"] + "Function SetPosition(float x, float y, float z) native\nWorldSpace Function GetWorldSpace() native\n"
                                 "Function SetMarkerDiscovered() native\nFunction AddToMap(bool b = false) native\n"
                                 "bool Function IsMapMarkerVisible() native\nbool Function CanFastTravelToMarker() native\n",
              "Game": BASES["Game"] + "bool Function IsFastTravelEnabled() native global\nbool Function IsFastTravelControlsEnabled() native global\n"}
PSC = (ROOT / "scripts" / "mapmarkers" / "FO4SF_MarkerProbeQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "MarkerProbe" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFMarkerProbe.esm"


def code_lines(text):
    """The script without its ; comments and its {doc strings}, so a name in prose is not a use."""
    return "\n".join(re.sub(r"\s*;.*$", "", ln) for ln in text.splitlines())


class ScriptTests(unittest.TestCase):
    def test_ids_stages_and_layout_match_the_tool(self):
        self.assertTrue(PSC.startswith("Scriptname FO4SF_MarkerProbeQuest extends Quest"))
        self.assertIn('Script = "FO4SF_MarkerProbeQuest"', TOOL_SRC)
        self.assertIn("const uint QuestId = 0x800", TOOL_SRC)
        self.assertIn('string ProbePlugin = "FO4SFMarkerProbe.esm"', PSC)
        self.assertEqual(mmp.PLUGIN, PLUGIN)
        self.assertIn(f'"{PLUGIN}"', TOOL_SRC.replace("ModKey.FromFileName(", ""))
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 20, 30, 40, 50, 60, 70])
        self.assertIn(f"StageList = new int[{len(ran)}]", PSC)
        self.assertIn(f"DoneList = new bool[{len(ran)}]", PSC)
        for stage in ran:                                                                   # every stage is handled by Step
            self.assertRegex(code_lines(PSC), rf"stage == {stage}\b")

    def test_the_ids_are_the_ones_the_pc_read(self):
        """FAL-489 note 36: ExitAnchorId 0x0A775B (= the Vault 111 marker), the landing marker 0x0008F2, the plugin's first own markers 0x900."""
        self.assertRegex(PSC, r"(?m)^int V111Id = 0x0A775B$")
        self.assertRegex(PSC, r"(?m)^int LandId = 0x0008F2$")
        self.assertRegex(PSC, r"(?m)^int TestId = 0x000900$")
        self.assertRegex(PSC, r"(?m)^int Test2Id = 0x000901$")
        self.assertIn('string CorePlugin = "FO4TerrainCore.esm"', PSC)
        self.assertIn('string MarkPlugin = "FO4SFMapMarkers.esm"', PSC)
        self.assertIn("float MergeX = -1200.0", PSC)
        self.assertIn("float MergeY = -2700.0", PSC)

    def test_no_property_and_no_held_reference(self):
        code = code_lines(PSC)
        self.assertIsNone(re.search(r"\bAuto(Readonly)?\b|\bProperty\b", code, re.I))
        self.assertNotIn(" Property ", code)
        self.assertEqual(PSC.count("Game.GetFormFromFile("), 4)
        self.assertIsNone(re.search(r"(?m)^ObjectReference \w+ *(=|$)", code))             # no script-level reference variable: it would make a temporary reference persistent

    def test_names_do_not_collide_case_blind(self):
        """Papyrus names are case-blind: no variable or parameter named like a type, a base script or a function of ours."""
        code = code_lines(PSC)
        funcs = {f.lower() for f in re.findall(r"(?m)^(?:\w+(?:\[\])? )?Function (\w+)", code)}
        names = re.findall(r"(?m)^\s*(?:int|float|bool|string|ObjectReference|Actor)(?:\[\])? (\w+)\b(?! *\()", code)
        names += re.findall(r"Function \w+\(([^)]*)\)", code)
        flat = []
        for n in names:
            flat += [x.split()[-1] for x in n.split(",") if x.strip()] if " " in n else [n]
        bad = {"race", "cell", "pad", "bench", "beacon", "actor", "form", "quest", "game", "debug", "utility"}
        self.assertEqual(sorted({n for n in flat if n.lower() in bad | funcs}), [])

    def test_each_stage_does_the_one_thing_the_card_says(self):
        step = PSC.split("Function Step(int stage)")[1].split("EndFunction")[0]
        self.assertIn('ReadAll("read", stage)', step.split("stage == 20")[0])               # 10, 40 and 50 change nothing
        self.assertIn("stage == 10 || stage == 40 || stage == 50", step)
        self.assertEqual(code_lines(PSC).count(".SetMarkerDiscovered()"), 2)
        self.assertIn("v.SetMarkerDiscovered()", step.split("stage == 30")[1].split("stage == 60")[0])
        self.assertIn("l.SetMarkerDiscovered()", step.split("stage == 60")[1].split("stage == 70")[0])
        self.assertIn("RefNamed(\"LAND\")", step.split("stage == 60")[1].split("stage == 70")[0])
        self.assertIn("t.AddToMap(false)", step.split("stage == 70")[1])
        self.assertIn('RefNamed("TEST2")', step.split("stage == 70")[1])                    # not the moved marker: nothing undoes Discovered
        self.assertEqual(code_lines(PSC).count(".AddToMap("), 1)
        move = PSC.split("Function MoveTest(int stage)")[1].split("EndFunction")[0]
        self.assertIn("t.MoveTo(a, 0.0, 0.0, 0.0, True, False)", move)                      # the exit's own call: Surface() in FO4SF_NewGameQuest.psc
        self.assertIn('RefNamed("V111")', move)
        self.assertIn("t.SetPosition(px + MergeX, py + MergeY, pz)", move)
        self.assertLess(move.index("t.MoveTo("), move.index("t.SetPosition("))
        self.assertEqual(code_lines(PSC).count(".MoveTo("), 1)
        self.assertEqual(code_lines(PSC).count(".SetPosition("), 1)

    def test_every_marker_is_read_for_world_and_both_proxies_and_fast_travel_each_time(self):
        reading = PSC.split("Function Reading")[1].split("EndFunction")[0]
        for need in ("IsMapMarkerVisible()", "CanFastTravelToMarker()", "GetWorldSpace()", "GetParentCell()", "visible=", "canfast="):
            self.assertIn(need, reading)
        fast = PSC.split("Function Fast")[1].split("EndFunction")[0]
        for need in ("Game.IsFastTravelEnabled()", "Game.IsFastTravelControlsEnabled()", "p.GetWorldSpace()", "enabled="):
            self.assertIn(need, fast)
        self.assertIn("Debug.Notification", PSC)                                          # every finding is also on screen
        later = PSC.split("Function Later()")[1].split("EndFunction")[0]
        for stage in (20, 30, 60, 70):                                                    # every stage that changes something is re-read after LaterS
            self.assertIn(f"stage == {stage}", later)
        self.assertEqual(PSC.count("StartTimer(LaterS, TIMER_LATER)"), 2)

    def test_every_native_the_script_calls_is_in_the_required_list(self):
        code = code_lines(PSC)
        used = set(re.findall(r"\b(?:r|a|t|v|l|p|Game|Debug|Utility)\.(\w+)\(", code)) | {"GetStageDone", "StartTimer", "GetFormID"}
        used -= {"Length"}
        listed = {n for names in mmp.REQUIRED.values() for n in names}
        self.assertEqual(sorted(used - listed), [])
        self.assertEqual(sorted(listed - used - {"GetPositionX", "GetPositionY", "GetPositionZ"}), [])


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.z = os.path.join(self.tmp.name, "cr.zip")

    def test_the_marker_natives_are_found_and_a_missing_one_is_named(self):
        fake_sources(self.z, BASES_MARK)
        sources = mmp.read_sources(self.z)
        self.assertEqual(mmp.precheck_sources(sources)["missing"], [])
        sources["objectreference"] = sources["objectreference"].replace("SetMarkerDiscovered", "Other")
        self.assertEqual(mmp.precheck_sources(sources)["missing"], ["ObjectReference.SetMarkerDiscovered"])
        fake_sources(self.z, BASES)                                                       # the shared fake has no marker natives
        missing = mmp.precheck_sources(mmp.read_sources(self.z))["missing"]
        self.assertIn("ObjectReference.AddToMap", missing)
        self.assertIn("Game.IsFastTravelEnabled", missing)


class LogTests(unittest.TestCase):
    LINES = [
        "FO4SFMARK rt=1.0 init version=1 quest=1 installed=True core=True markers=True end=true",
        "FO4SFMARK rt=2.0 fast stage=10 when=read enabled=False controls=True pworld=none pcell=5 pos=1,2,3 end=true",
        "FO4SFMARK rt=2.1 read stage=10 when=read name=V111 ref=7 world=4 cell=none pos=-1,2,3 visible=False canfast=False end=true",
        "FO4SFMARK rt=3.0 move stage=20 call=MoveTo anchor=7 end=true",
        "FO4SFMARK rt=3.1 read stage=20 when=moved name=TEST ref=8 world=none cell=5 pos=9,9,9 visible=False canfast=False end=true",
        "FO4SFMARK rt=5.0 later done stage=20 end=true",
        "noise line",
    ]

    def test_summarize_groups_rows_per_stage_in_order(self):
        s = mmp.summarize(self.LINES)
        self.assertEqual(s["init"]["markers"], "True")
        self.assertEqual(sorted(s["stages"]), [10, 20])
        self.assertEqual([r["event"] for r in s["stages"][10]], ["fast", "read"])
        moved = s["stages"][20][1]
        self.assertEqual((moved["when"], moved["name"], moved["world"], moved["canfast"]), ("moved", "TEST", "none", "False"))

    def test_the_log_command_prints_the_proxies_and_exits_1_without_findings(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        p = os.path.join(tmp, "l.log")
        Path(p).write_text("\n".join(self.LINES) + "\n", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mmp.main(["log", "--file", p]), 0)
        out = buf.getvalue()
        self.assertIn("fast travel enabled=False controls=True", out)
        self.assertIn("V111  world=4 cell=none visible=False canfast=False", out)
        self.assertIn("stage 20:", out)
        Path(p).write_text("nothing here\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mmp.main(["log", "--file", p]), 1)
            self.assertEqual(mmp.main(["log", "--file", os.path.join(tmp, "absent.log")]), 2)


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "MarkerProbe"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/MarkerProbe/bin/Release/net9.0/MarkerProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-markp-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.data = cls.root / "Data"
        r = cls.run_tool("fixture", cls.data)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.staged = cls.root / "staged"
        assert mmp.stage(cls.args(cls.staged)) == 0

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    @classmethod
    def args(cls, out):
        z = cls.root / (Path(out).name + "-cr.zip")
        fake_sources(z, BASES_MARK)
        return type("A", (), dict(out=str(out), starfield_data=str(cls.data), content_resources=str(z), compiler=str(fake_compiler(cls.root))))()

    @staticmethod
    def walk_kinds(data):
        """{record type: [form ids]} of a plugin's raw bytes (GRUPs walked; TES4 skipped)."""
        found = {}

        def walk(buf, i, end):
            while i < end:
                kind = buf[i:i + 4]
                size = struct.unpack_from("<I", buf, i + 4)[0]
                if kind == b"GRUP":
                    walk(buf, i + 24, i + size)
                    i += size
                    continue
                form = struct.unpack_from("<I", buf, i + 12)[0]
                if kind != b"TES4":
                    found.setdefault(kind, []).append(form)
                i += 24 + size
        walk(data, 0, len(data))
        return found

    def test_build_check_and_a_wrong_plugin_fails(self):
        r = self.run_tool("check", self.staged / PLUGIN)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("all checks pass", r.stdout)
        self.assertIn("FO4SF_MarkerProbeQuest (0 properties)", r.stdout)
        bad = self.root / "bad"
        bad.mkdir()
        raw = (self.staged / PLUGIN).read_bytes()
        self.assertIn(b"FO4SF_MarkerProbeQuest", raw)
        (bad / PLUGIN).write_bytes(raw.replace(b"FO4SF_MarkerProbeQuest", b"FO4SF_MarkerProbeQuesX"))   # same length: Mutagen aborts on a size change
        r = self.run_tool("check", bad / PLUGIN)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL", r.stdout)

    def test_the_plugin_is_the_one_quest_and_masters_only_starfield(self):
        raw = (self.staged / PLUGIN).read_bytes()
        self.assertEqual(self.walk_kinds(raw), {b"QUST": [0x01000800]})
        self.assertEqual(raw.count(b"MAST"), 1)
        self.assertIn(b"Starfield.esm", raw)
        self.assertNotIn(b"FO4TerrainCore", raw)                                           # found by GetFormFromFile, never a master
        self.assertNotIn(b"FO4SFMapMarkers", raw)

    def test_the_stage_pins_every_file_and_compiled_the_script(self):
        plan = json.loads((self.staged / "plan.json").read_text())
        self.assertEqual((plan["kind"], plan["plugins"]), ("marker-probe", [PLUGIN]))
        self.assertEqual(set(plan["inputs"]), {"Starfield.esm"})
        self.assertEqual(sorted(plan["outputs"]), ["Data/Scripts/FO4SF_MarkerProbeQuest.pex", PLUGIN])
        self.assertEqual(mmp.verify_stage(str(self.staged), plan, str(self.data)), [])
        self.assertIn("all checks pass", (self.staged / "offline_check.txt").read_text())
        self.assertEqual((self.staged / "FO4SF_MarkerProbeQuest.psc").read_text(), PSC)
        self.assertIn("setstage FO4SF_MarkerProbeQuest", (self.staged / "README.txt").read_text())
        self.assertFalse((self.staged / "work").exists())
        with self.assertRaises(SystemExit):                                                # an earlier stage is never overwritten
            mmp.stage(self.args(self.staged))

    def test_a_missing_native_stops_the_stage_and_publishes_nothing(self):
        out = self.root / "staged-lacking"
        a = self.args(out)
        fake_sources(a.content_resources, BASES)
        with self.assertRaises(SystemExit) as cm:
            mmp.stage(a)
        self.assertIn("do not stage", str(cm.exception))
        self.assertFalse(out.exists())

    def test_a_changed_stage_or_starfield_esm_is_refused_by_verify(self):
        plan = json.loads((self.staged / "plan.json").read_text())
        out = self.root / "staged-edit"
        shutil.copytree(self.staged, out)
        (out / "Data" / "Scripts" / "FO4SF_MarkerProbeQuest.pex").write_bytes(b"changed")
        self.assertTrue(any("changed after the stage" in p for p in mmp.verify_stage(str(out), plan)))
        data = self.root / "Data2"
        shutil.copytree(self.data, data)
        (data / "Starfield.esm").write_bytes(b"other")
        self.assertIn("Starfield.esm changed since the stage: re-stage", mmp.verify_stage(str(self.staged), plan, str(data)))
        self.assertEqual(mmp.verify_stage(str(self.staged), {**plan, "kind": "cog-door"}), [
            "plan.json is not the marker probe's (kind 'cog-door', plugins ['FO4SFMarkerProbe.esm'])"])


if __name__ == "__main__":
    unittest.main()
