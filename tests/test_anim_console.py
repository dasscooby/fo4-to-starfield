"""The animation console probe, variant D: its script's ids and stages against the writer's (dotnet/AnimConsoleProbe), the
stager with a fake converter, fake base sources and a fake Papyrus compiler, the texture rule and the plan verification (never a
game; the conversion, the CALUMI library and the real compile are the PC's job). The dotnet tests skip without the .NET SDK."""
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
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_anim_console as mac  # noqa: E402
from fo4sf import anim_object, convert_static, nif  # noqa: E402
from test_anim_object import STATES, console_nif  # noqa: E402
from test_anim_probe import BASES, fake_compiler, fake_sources  # noqa: E402

BASES_D = {**BASES, "ObjectReference": BASES["ObjectReference"] + "Function SetAngle(float x, float y, float z) native\n"}
PSC = (ROOT / "scripts" / "newgame" / "FO4SF_AnimConsoleQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "AnimConsoleProbe" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFAnimConsole.esm"
MODEL_IN_PORT = "Meshes/fo4port/interiors/vault/props/console01.nif"


def norm(text):
    """Tool output in one normal form: forward slashes (the tool prints a path as it was given, Windows or not)."""
    return text.replace("\\", "/")


class ScriptTests(unittest.TestCase):
    def test_ids_stages_log_and_layout_match_the_tool_and_the_reader(self):
        self.assertTrue(PSC.startswith("Scriptname FO4SF_AnimConsoleQuest extends Quest"))
        self.assertIn('Script = "FO4SF_AnimConsoleQuest"', TOOL_SRC)
        self.assertIn("const uint QuestId = 0x800", TOOL_SRC)
        self.assertIn('string LogName = "FO4SFAnimD"', PSC)
        self.assertIn('string ProbePlugin = "FO4SFAnimConsole.esm"', PSC)
        self.assertIn('string BasePlugin = "FO4Port.esm"', PSC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 11, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 31, 32, 40, 60])
        self.assertIn(f"StageList = new int[{len(ran)}]", PSC)
        self.assertIn('"FO4SFANIM rt="', PSC)                                  # the variant A reader reads this log too
        from fo4sf import anim_probe_log
        for e in anim_probe_log.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e}[ "]')

    def test_no_property_no_wait_form_one_base_line_and_a_spawn_not_a_cell(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        self.assertNotRegex("\n".join(l.split(";")[0] for l in PSC.splitlines() if not l.startswith(" ")), r"PlayAnimationAndWait\(")
        self.assertEqual(len(mac.BASE_LINE.findall(PSC)), 1)
        self.assertIn("p.PlaceAtMe(base, 1, true, false, false)", PSC)
        self.assertIn("Game.GetFormFromFile(BaseId, BasePlugin)", PSC)
        self.assertNotIn("ActiId", PSC)
        self.assertEqual(PSC.count("TestRef.PlayAnimation(n)"), 2)       # PlayOne and PlayQuiet (the side copy is TestRef2)

    def test_the_play_names_start_with_the_four_that_moved_the_vanilla_activator(self):
        names = dict(re.findall(r'PlayNames\[(\d)\] = "(\w+)"', PSC))
        self.assertEqual([names[str(i)] for i in range(4)], ["Play01", "Play02", "TurnOff", "StateB_Play"])      # variant A, 12 Nov
        self.assertEqual(len(names), 8)
        self.assertIn("PlayOne(stage, PlayNames[stage - 21])", PSC)

    def test_every_finding_shows_on_screen_and_the_clip_time_is_logged(self):
        self.assertIn('Debug.Notification("AP " + msg)', PSC)
        self.assertIn('" after=" + after', PSC)                                      # Done's after= is the clip's length
        self.assertEqual(PSC.count("PlayRt = Utility.GetCurrentRealTime()"), 3)      # PlayOne, PlayQuiet and ActivateOnce
        self.assertIn('Say("READ s" + stage + " " + when + " 3d=" + r.Is3DLoaded()', PSC)      # 3D loaded / distance / height difference on screen
        self.assertIn('" az=" + r.GetAngleZ() + " pa=" + p.GetAngleZ())', PSC)           # the copy's and the player's heading
        self.assertIn('Say("SPAWN s" + stage + " moved=" + moved + " turned=" + turned', PSC)
        for what in ('Say("EV " + asEventName + " w" + ListenStage + " t" + after)', 'Say("PLAY s" + stage + " " + n + " ok=" + ok)',
                     'Say("W s" + stage + " quiet")', 'Say("ACTIVATE s" + stage)'):
            self.assertIn(what, PSC)

    def test_the_committed_script_compiles_alone_and_the_register_shape_replaces_cleanly(self):
        self.assertEqual(mac.enable(PSC, []), PSC)
        self.assertEqual(mac.optional_names(PSC), ["ObjectReference.MoveTo", "ObjectReference.SetAngle", "ObjectReference.Delete"])
        self.assertIn(mac.probe_a.BOOL_LINE, PSC)
        self.assertNotIn(mac.probe_a.BOOL_LINE, mac.probe_a.reg_shape(PSC, False))

    def test_the_quiet_stages_play_both_copies_and_say_nothing_until_the_window_closes(self):
        quiet = PSC.split("Function PlayQuiet")[1].split("EndFunction")[0]
        self.assertIn("Quiet = true", quiet)
        self.assertEqual(quiet.count(".PlayAnimation(n)"), 2)                      # the first copy and the side copy
        self.assertNotIn("Say(", quiet)                                             # no notification inside the window
        say = PSC.split("Function Say")[1].split("EndFunction")[0]
        self.assertRegex(say, r"if Quiet\s+return\s+endif")                          # Say is silent while Quiet
        close = PSC.split("Event OnTimer")[1].split("EndEvent")[0]
        self.assertLess(close.index("Quiet = false"), close.index('Say("PLAYQ s"'))   # the window closes quiet, then speaks once
        self.assertIn('" firstDone=" + FirstDoneAfter', close)
        self.assertIn("PlayQuiet(stage, \"Play01\")", PSC)
        self.assertIn("PlayQuiet(stage, \"Play02\")", PSC)
        self.assertNotIn("Quiet = true", PSC.split("Function PlayOne")[1].split("EndFunction")[0])   # the ordinary stages keep their notices

    def test_the_side_copy_is_a_second_reference_turned_a_quarter_circle_and_cleaned_up(self):
        side = PSC.split("Function SpawnSide")[1].split("EndFunction")[0]
        self.assertIn("TestRef2 = p.PlaceAtMe(base, 1, true, false, false)", side)
        self.assertIn("SideM * Math.Cos(a)", side)
        self.assertIn("AheadM * Math.Cos(a) - SideM * Math.Sin(a)", side)          # to the player's right: (cos a, -sin a)
        self.assertIn("TestRef2.SetAngle(0.0, 0.0, p.GetAngleZ() + 270.0)", side)    # 180 (facing the player) plus a quarter circle
        self.assertIn("RegisterRef(stage, TestRef2)", side)
        self.assertNotIn("elif", side)
        self.assertIn("stage == 11", PSC)
        self.assertIn("SpawnSide(stage)", PSC.split("Function Step")[1].split("EndFunction")[0])
        cleanup = PSC.split("Function Cleanup")[1].split("EndFunction")[0]
        self.assertIn("TestRef2.Disable(false)", cleanup)
        self.assertIn(";OPT ObjectReference.Delete         TestRef2.Delete()", cleanup)
        on = mac.enable(PSC, ["ObjectReference.MoveTo", "ObjectReference.SetAngle", "ObjectReference.Delete"])
        self.assertIsNone(re.search(r"^;OPT ", on, re.M))                           # every optional line of the new function switches on with its name

    def test_a_placed_reference_is_taken_not_spawned_and_is_never_disabled_or_deleted(self):
        """FAL-489 lift session 2: the clips play on the PLACED lift (REFR 001618). Stage 10 must not PlaceAtMe or move it; stage 11 makes no copy;
        stage 60 must leave it alone (Disable / Delete of the real lift would be destructive)."""
        self.assertEqual(len(re.findall(r"(?m)^int PlacedId = 0 +;PLACED", PSC)), 1)
        spawn = PSC.split("Function Spawn(int stage)")[1].split("EndFunction")[0]
        self.assertLess(spawn.index("if PlacedId != 0"), spawn.index("TestRef = p.PlaceAtMe"))                    # the placed branch returns before any spawn
        self.assertIn("UsePlaced(stage, base)", spawn)
        used = PSC.split("Function UsePlaced")[1].split("EndFunction")[0].split("}", 1)[1]                # the code, not its doc comment
        for forbidden in ("PlaceAtMe", "MoveTo", "SetAngle", "Disable", "Delete"):
            self.assertNotIn(forbidden, used)
        self.assertIn("Game.GetFormFromFile(PlacedId, BasePlugin)", used)
        self.assertIn("f as ObjectReference", used)
        self.assertIn("RegisterAll(stage)", used)
        side = PSC.split("Function SpawnSide")[1].split("EndFunction")[0]
        self.assertLess(side.index("if UsingPlaced"), side.index("PlaceAtMe"))
        cleanup = PSC.split("Function Cleanup")[1].split("EndFunction")[0]
        first = cleanup.split("if TestRef2")[0]
        self.assertIn("if TestRef && !UsingPlaced", first)                                           # the first reference is disabled / deleted only when it was spawned
        self.assertIn("UsingPlaced = false", cleanup)

    def test_the_placed_id_is_written_once_and_a_bad_one_is_refused(self):
        on = mac.set_placed(PSC, "0x001618")
        self.assertRegex(on, r"(?m)^int PlacedId = 0x001618  ;PLACED")
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        self.assertRegex(mac.set_placed(PSC, "1618"), r"(?m)^int PlacedId = 0x1618  ;PLACED")
        for bad in ("zz", "", "12345678", "0", "0x000000"):
            with self.assertRaises(SystemExit):
                mac.set_placed(PSC, bad)
        with self.assertRaises(SystemExit):
            mac.set_placed("no line here\n", "12")

    def test_the_base_id_is_written_once_and_a_bad_one_is_refused(self):
        on = mac.set_base_id(PSC, "0x001234")
        self.assertRegex(on, r"(?m)^int BaseId = 0x001234  ;BASE")
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        self.assertRegex(mac.set_base_id(PSC, "1319"), r"(?m)^int BaseId = 0x1319  ;BASE")
        for bad in ("zz", "", "12345678"):
            with self.assertRaises(SystemExit):
                mac.set_base_id(PSC, bad)
        with self.assertRaises(SystemExit):
            mac.set_base_id("no line here\n", "12")

    def test_info_output_is_parsed_and_a_missing_one_refused(self):
        self.assertEqual(mac.parse_info("ACTI x\nBASE_ID 0x001234\nMODEL Meshes/a/b.nif\n"), {"base_id": "001234", "model": "Meshes/a/b.nif"})
        self.assertEqual(mac.parse_info("BASE_ID 0xE0D9\nMODEL Meshes\\a\\b.nif\n")["model"], "Meshes/a/b.nif")   # Windows prints backslashes
        for bad in ("BASE_ID 0x1\nMODEL \n", "MODEL Meshes/a.nif\n", ""):
            with self.assertRaises(SystemExit):
                mac.parse_info(bad)

    def test_the_copy_is_placed_upright_at_chest_height_facing_the_player(self):
        self.assertIn("float AheadM = 1.5", PSC)
        self.assertIn("float UpM = 1.2", PSC)
        self.assertIn("TestRef.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), UpM, false)", PSC)
        self.assertIn("TestRef.SetAngle(0.0, 0.0, p.GetAngleZ() + 180.0)", PSC)          # turned half a circle from the player's heading
        on = mac.enable(PSC, ["ObjectReference.MoveTo", "ObjectReference.SetAngle"])
        self.assertIn("turned = true", on.split("Spawn")[1].split("EndFunction")[0].replace(";OPT ObjectReference.SetAngle ", ""))
        off = mac.enable(PSC, ["ObjectReference.MoveTo"])
        self.assertIn(";OPT ObjectReference.SetAngle         TestRef.SetAngle", off)        # a SetAngle that does not compile stays off

    def test_the_variant_a_precheck_list_covers_this_script(self):
        z = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, z, True)
        zp = os.path.join(z, "cr.zip")
        fake_sources(zp, BASES_D)
        r = mac.probe_a.precheck_sources(mac.read_sources(zp), PSC)
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["optional"], {"ObjectReference.MoveTo": True, "ObjectReference.SetAngle": True, "ObjectReference.Delete": True})


class SequencesTableTests(unittest.TestCase):
    def test_the_console_clips_are_listed_with_seconds_and_bones(self):
        rows = mac.sequences_table(nif.serialize(console_nif()))
        self.assertEqual(sorted(r["name"] for r in rows), ["Stage1", "Stage2"])
        for r in rows:
            self.assertEqual((r["seconds"], r["bones"]), (1.0, ["LeafA", "LeafB"]))
            self.assertEqual(r["text_keys"], [])


class ClipsCommandTests(unittest.TestCase):
    def test_clips_prints_the_motion_of_every_track_not_only_which_bones_have_one(self):
        import contextlib
        import io
        raw = nif.serialize(console_nif())
        motion = mac.sequence_motion(raw, ["Stage1", "Stage2"])
        self.assertEqual(sorted(motion), ["Stage1", "Stage2"])
        self.assertEqual(sorted(m["bone"] for m in motion["Stage1"]), ["LeafA", "LeafB"])
        self.assertEqual(mac.sequence_motion(b"not a nif", ["Stage1"]), {})
        a = type("A", (), dict(fo4_data="fo4", port_data="", starfield_data="sf", model="", edid=mac.EDID))()
        fake = type("S", (), {"mesh": staticmethod(lambda n: raw), "mesh_names": staticmethod(lambda p: [])})()
        from fo4sf import pipeline
        buf = io.StringIO()
        with unittest.mock.patch.object(mac, "run", lambda *x, **k: type("R", (), {"stdout": "BASE_ID 0x1\nMODEL Meshes/a/console01.nif\n"})()), \
                unittest.mock.patch.object(pipeline, "Fo4Archives", lambda d: fake), contextlib.redirect_stdout(buf):
            self.assertEqual(mac.clips(a), 0)
        out = buf.getvalue()
        self.assertIn("Stage1: 1.0 s, tracks LeafA, LeafB", out)
        self.assertRegex(out, r"LeafA: travel \[[-\d., ]+\] m, turns [-\d.]+ deg")


class FakeSrc:
    def __init__(self, raw):
        self.raw, self.asked = raw, []

    def mesh(self, name):
        self.asked.append(name)
        return self.raw if name.lower().endswith("console01.nif") and "interiors" in name.lower() else None

    def mesh_names(self, pattern):
        return []


class FakeConv:
    """convert_anim_object without CALUMI or the game: writes the files a conversion would into the staging."""
    def __init__(self, staging, textures=()):
        self.staging, self.textures, self.calls = staging, textures, []

    def convert_anim_object(self, name, states, foley=None, swap_siblings=False, idles="toggle"):
        self.calls.append((name, dict(states), foley))
        self.swapped, self.idles = swap_siblings, idles
        out = "fo4port/interiors/vault/props/console01_anim"
        files = {f"meshes/{out}.nif": b"nif", f"meshes/{out}/characterassets/skeleton.rig": b"rig", "geometries/ab/cd.mesh": b"mesh",
                 "materials/fo4port/x.mat": b"mat"}
        for slot in anim_object.slot_names(states, idles):
            files[f"meshes/{out}/animations/{slot}.af"] = b"af"
            files[f"meshes/{out}/animations/{slot}.afx"] = anim_object.descriptor(slot, audio=[(1, foley)] if foley and "Play" in slot else ())
        for t in self.textures:
            files[t] = b"dds"
        for rel, data in files.items():
            p = os.path.join(self.staging, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            Path(p).write_bytes(data)
        from test_anim_object import BuilderTests
        (built, anim), plan = BuilderTests().build(idles=idles)           # a real conversion of the fixture: rig, tracks, shapes, poses
        Path(os.path.join(self.staging, *f"meshes/{out}.nif".split("/"))).write_bytes(built["meshes/fo4port/vault/console_anim.nif"])
        clips = anim_object.clip_table(plan, convert_static.UNIT_SCALE)
        return {"ok": True, "out_name": out, "anim": {**anim, "skeleton": out.replace("/", "\\") + "\\characterassets\\skeleton.rig",
                                                      "animations": out.replace("/", "\\") + "\\animations", "clips": clips, "states": dict(states), "idles": idles}}


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "AnimConsoleProbe"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/AnimConsoleProbe/bin/Release/net9.0/AnimConsoleProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-animc-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.data = cls.root / "Data"
        r = cls.run_tool("fixture", cls.data)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.margs = ["--model", "fo4port\\interiors\\vault\\props\\console01_anim.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations"]
        # FAL-558: one default stage (~9 s: the stager's tool calls) shared by the tests that only read it; a test that changes the
        # stage works on its own copy (fresh_stage), one that changes inputs stages again.
        make, cls.shared_holder = cls.converter()
        cls.shared = cls.root / "staged"
        assert mac.stage(cls.args(cls.shared, foley="QST_Flip"), converter=make) == 0

    def fresh_stage(self, name):
        out = self.root / name
        shutil.copytree(self.shared, out)
        return out

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def paths(self):
        return self.data / "FO4Port.esm", self.data / "Starfield.esm"

    # ------------------------------------------------------------- the plugin tool
    def test_info_build_and_check(self):
        port, sf = self.paths()
        info = self.run_tool("info", port, sf)
        self.assertEqual(info.returncode, 0, info.stderr)
        self.assertEqual(mac.parse_info(info.stdout), {"base_id": "001234", "model": MODEL_IN_PORT})
        out_dir = self.root / "b1"
        proc = self.run_tool("build", port, sf, out_dir, *self.margs)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        check = self.run_tool("check", out_dir / PLUGIN, port, sf, *self.margs)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        out = norm(check.stdout)
        self.assertIn("masters [Starfield.esm, FO4Port.esm]", out)
        self.assertIn("override: ACTI 001234:FO4Port.esm FO4Port_acti_091a48_fallout4 name 'Vault Door Controls'", out)
        self.assertIn(norm("ANAM AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx BNAM fo4port\\r\\skeleton.rig CNAM fo4port\\r\\animations"), out)
        self.assertIn("scripts [FO4SF_AnimConsoleQuest (0 properties)]", out)
        wrong = self.run_tool("check", out_dir / PLUGIN, port, sf, "--model", "other.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations")
        self.assertEqual(wrong.returncode, 1)
        self.assertIn("the model is not Meshes/other.nif", norm(wrong.stdout))
        backslash = self.run_tool("check", out_dir / PLUGIN, port, sf, "--model", "other\\sub.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations")
        self.assertIn("the model is not Meshes/other/sub.nif", norm(backslash.stdout))        # a backslash model compares in the same form

    def test_the_plugin_is_one_override_and_one_quest_raw(self):
        """Raw bytes: ACTI carries the FO4Port load index (1), the quest ours (2); the master list is Starfield.esm, FO4Port.esm."""
        port, sf = self.paths()
        out = self.root / "b2"
        self.assertEqual(self.run_tool("build", port, sf, out, *self.margs).returncode, 0)
        data = (out / PLUGIN).read_bytes()
        kinds = {}

        def walk(buf, i, end):
            while i < end:
                sig = buf[i:i + 4]
                size = struct.unpack_from("<I", buf, i + 4)[0]
                if sig == b"GRUP":
                    walk(buf, i + 24, i + size)
                    i += size
                    continue
                kinds.setdefault(sig, []).append(struct.unpack_from("<I", buf, i + 12)[0])
                i += 24 + size
        walk(data, 0, len(data))
        self.assertEqual({k: v for k, v in kinds.items() if k != b"TES4"}, {b"ACTI": [0x01001234], b"QUST": [0x02000800]})
        self.assertLess(data.index(b"Starfield.esm"), data.index(b"FO4Port.esm"))

    def test_a_base_that_is_not_there_is_refused_by_name(self):
        port, sf = self.paths()
        proc = self.run_tool("build", port, sf, self.root / "b3", *self.margs, "--edid", "NoSuchActi")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 ACTI named NoSuchActi", proc.stderr)

    # ------------------------------------------------------------- the stager
    @classmethod
    def args(cls, out, **kw):
        z = cls.root / (Path(out).name + "-cr.zip")
        fake_sources(z, BASES_D)
        base = dict(out=str(out), starfield_data=str(cls.data), port_data="", fo4_data="fo4", door_anim_dll="d.dll", collision_template="c.nif",
                    texconv="t.exe", content_resources=str(z), compiler=str(fake_compiler(cls.root)), states="Stage1=StateA_Play,Stage2=StateB_Play",
                    foley="", model="", edid=mac.EDID)
        base.update(kw)
        return type("A", (), base)()

    @classmethod
    def converter(cls, textures=()):
        raw = nif.serialize(console_nif())
        holder = {}

        def make(a, staging):
            holder["conv"] = FakeConv(staging, textures)
            holder["src"] = FakeSrc(raw)
            return holder["src"], holder["conv"]
        return make, holder

    def test_stage_converts_builds_compiles_and_pins_every_file(self):
        holder = self.shared_holder
        out = self.shared                                                                  # staged once in setUpClass with foley QST_Flip
        self.assertTrue(holder["conv"].calls[0][0].lower().endswith("console01.nif"))      # the first candidate the source holds
        self.assertEqual(holder["conv"].calls[0][1:], (STATES, "QST_Flip"))
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual(plan["kind"], "anim-console")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(set(plan["inputs"]), {"Starfield.esm", "FO4Port.esm"})
        outputs = set(plan["outputs"])
        self.assertIn(PLUGIN, outputs)
        self.assertIn("Data/Scripts/FO4SF_AnimConsoleQuest.pex", outputs)
        self.assertIn("Data/meshes/fo4port/interiors/vault/props/console01_anim/animations/StateB_Idle.afx", outputs)
        self.assertIn("Data/geometries/ab/cd.mesh", outputs)
        self.assertEqual(plan["optional"]["ObjectReference.MoveTo"], "kept")
        self.assertEqual(mac.verify_stage(str(out), plan, str(self.data)), [])
        manifest = json.loads((out / "anim_manifest.json").read_text())
        self.assertEqual((manifest["base_id"], manifest["model"], manifest["foley"]), ("001234", "fo4port\\interiors\\vault\\props\\console01_anim.nif", "QST_Flip"))
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        self.assertIn("int BaseId = 0x001234  ;BASE", (out / "FO4SF_AnimConsoleQuest.psc").read_text())
        self.assertIn("StateA_Idle: 0.0 s (0 frames)", (out / "README.txt").read_text())
        self.assertFalse((out / "work").exists())
        make, _ = self.converter()
        with self.assertRaises(SystemExit):                                                  # an earlier stage is never overwritten
            mac.stage(self.args(out), converter=make)

    def test_the_kit_ships_no_textures_and_refuses_ones_the_port_lacks(self):
        make, _ = self.converter(textures=["textures/fo4port/c_d.dds"])
        with self.assertRaises(SystemExit) as ctx:
            mac.stage(self.args(self.root / "staged-t"), converter=make)
        self.assertIn("the port's archives do not hold", str(ctx.exception))
        self.assertIn("textures/fo4port/c_d.dds", str(ctx.exception))
        self.assertFalse((self.root / "staged-t").exists())
        # the same texture is fine when the port's archive holds it, and still not copied into the kit
        from ba2_fixture import general_archive
        port_dir = self.root / "portdata"
        port_dir.mkdir()
        shutil.copy(self.data / "FO4Port.esm", port_dir / "FO4Port.esm")
        (port_dir / "FO4Port - Textures.ba2").write_bytes(general_archive({"textures\\fo4port\\c_d.dds": b"dds"}))
        self.assertEqual(mac.stage(self.args(self.root / "staged-t2", port_data=str(port_dir)), converter=make), 0)
        self.assertFalse(any("textures" in k for k in json.loads((self.root / "staged-t2" / "plan.json").read_text())["outputs"]))

    def test_the_spawn_distances_are_written_into_the_script_and_a_bad_one_is_refused(self):
        self.assertEqual(mac.set_spawn(PSC), PSC)                                           # nothing asked: the script is untouched
        on = mac.set_spawn(PSC, ahead=45, up=1.7)
        self.assertRegex(on, r"(?m)^float AheadM = 45.0 +;")
        self.assertRegex(on, r"(?m)^float UpM = 1.7 +;")
        self.assertIn("float SideM = 0.9", on)                                              # a distance not named keeps the script's own
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        self.assertRegex(mac.set_spawn(PSC, up=-9.5), r"(?m)^float UpM = -9.5 +;")
        self.assertRegex(mac.set_spawn(mac.set_spawn(PSC, ahead=60), ahead=60), r"(?m)^float AheadM = 60.0 +;")   # the same value twice is not an error
        for bad in (float("nan"), float("inf"), 201, -201):
            with self.assertRaises(SystemExit):
                mac.set_spawn(PSC, ahead=bad)
        with self.assertRaises(SystemExit):
            mac.set_spawn("no line here\n", up=1)

    def test_the_stage_writes_the_spawn_distances_into_the_compiled_script_and_the_manifest(self):
        make, holder = self.converter()
        out = self.root / "staged-spawn"
        self.assertEqual(mac.stage(self.args(out, ahead_m=45.0, up_m=1.7), converter=make), 0)
        text = (out / "FO4SF_AnimConsoleQuest.psc").read_text()
        self.assertRegex(text, r"(?m)^float AheadM = 45.0 +;")
        self.assertRegex(text, r"(?m)^float UpM = 1.7 +;")
        self.assertEqual(json.loads((out / "anim_manifest.json").read_text())["spawn_m"], {"ahead": 45.0, "up": 1.7})
        make, holder = self.converter()
        self.assertEqual(mac.stage(self.args(self.root / "staged-nospawn"), converter=make), 0)
        self.assertEqual(json.loads((self.root / "staged-nospawn" / "anim_manifest.json").read_text())["spawn_m"], {})   # the default stage names none
        self.assertRegex((self.root / "staged-nospawn" / "FO4SF_AnimConsoleQuest.psc").read_text(), r"(?m)^float AheadM = 1.5 +;")

    def test_the_stage_writes_the_placed_id_and_refuses_it_together_with_spawn_distances(self):
        make, holder = self.converter()
        out = self.root / "staged-placed"
        self.assertEqual(mac.stage(self.args(out, placed_ref="001618"), converter=make), 0)
        self.assertRegex((out / "FO4SF_AnimConsoleQuest.psc").read_text(), r"(?m)^int PlacedId = 0x001618  ;PLACED")
        self.assertEqual(json.loads((out / "anim_manifest.json").read_text())["placed_ref"], "001618")
        make, holder = self.converter()
        self.assertEqual(mac.stage(self.args(self.root / "staged-noplaced"), converter=make), 0)
        self.assertRegex((self.root / "staged-noplaced" / "FO4SF_AnimConsoleQuest.psc").read_text(), r"(?m)^int PlacedId = 0 +;PLACED")
        self.assertEqual(json.loads((self.root / "staged-noplaced" / "anim_manifest.json").read_text())["placed_ref"], "")
        make, holder = self.converter()
        with self.assertRaises(SystemExit):
            mac.stage(self.args(self.root / "staged-both", placed_ref="001618", up_m=1.7), converter=make)
        self.assertFalse((self.root / "staged-both").exists())                                       # nothing published

    def test_swap_siblings_is_off_by_default_and_reaches_the_converter_when_asked(self):
        self.assertFalse(self.shared_holder["conv"].swapped)                                # the default stage is the one staged in setUpClass
        make, holder = self.converter()
        self.assertEqual(mac.stage(self.args(self.root / "staged-sw1", swap_siblings=True), converter=make), 0)
        self.assertTrue(holder["conv"].swapped)
        self.assertEqual(holder["conv"].idles, "toggle")                          # the idle rule is the toggle unless --idles hold is given
        make, holder = self.converter()
        self.assertEqual(mac.stage(self.args(self.root / "staged-sw2", idles="hold"), converter=make), 0)
        self.assertEqual(holder["conv"].idles, "hold")

    def test_a_failed_conversion_and_a_bad_state_map_stop_before_anything_is_published(self):
        class Failing(FakeConv):
            def convert_anim_object(self, name, states, foley=None):
                return {"ok": False, "reason": "NifError: door has no moving geometry"}
        with self.assertRaises(SystemExit) as ctx:
            mac.stage(self.args(self.root / "staged-f"), converter=lambda a, st: (FakeSrc(nif.serialize(console_nif())), Failing(st)))
        self.assertIn("the console did not convert: NifError: door has no moving geometry", str(ctx.exception))
        self.assertFalse((self.root / "staged-f").exists())
        with self.assertRaises(ValueError):
            mac.stage(self.args(self.root / "staged-b", states="Stage1=StateA_Idle"), converter=self.converter()[0])

    def test_an_original_that_cannot_be_found_asks_for_the_model_option(self):
        class Nothing(FakeSrc):
            def mesh(self, name):
                return None
        with self.assertRaises(SystemExit) as ctx:
            mac.stage(self.args(self.root / "staged-n"), converter=lambda a, st: (Nothing(b""), FakeConv(st)))
        self.assertIn("name it with --model", str(ctx.exception))

    def test_inspect_reads_the_staged_rig_tracks_nodes_and_predicted_poses(self):
        import contextlib
        import io
        out = self.fresh_stage("staged-i")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = mac.main(["inspect", "--stage", str(out)])
        text = buf.getvalue()
        self.assertIn("rig bones (index: name", text)
        self.assertIn("matches the rig order: yes", text)
        self.assertIn("StateA_Play: moves Root[3]@LeafA, Root[4]@LeafB", text)
        self.assertIn("StateB_Play: moves nothing", text)
        self.assertEqual(code, 0)

    def test_inspect_catches_a_track_filed_under_the_wrong_rig_index_and_a_swapped_model_order(self):
        import contextlib
        import io
        from test_anim_object import BuilderTests
        (files, anim), plan = BuilderTests().build()
        anim = {**anim, "clips": anim_object.clip_table(plan, convert_static.UNIT_SCALE)}
        names = [r["name"] for r in anim["rig"]]
        model = nif.serialize(console_nif())
        order, _all = mac.model_bone_order(model, names)
        self.assertIsInstance(order, list)
        stage_dir = self.root / "staged-sw"
        (stage_dir / "Data" / "meshes" / "fo4port" / "vault").mkdir(parents=True)
        (stage_dir / "Data" / "meshes" / "fo4port" / "vault" / "console_anim.nif").write_bytes(files["meshes/fo4port/vault/console_anim.nif"])
        good = {"original": "x", "model": "fo4port\\vault\\console_anim.nif", "states": STATES, "anim": anim}
        (stage_dir / "anim_manifest.json").write_text(json.dumps(good))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mac.main(["inspect", "--stage", str(stage_dir)]), 0)
        text = buf.getvalue()
        self.assertIn("matches the rig order: yes", text)
        self.assertIn("StateA_Play (1.0 s): ", text)
        self.assertRegex(text, r"LeafA -> 1 \(\d+ keys\)")
        self.assertIn("StateA_Play: moves Root[3]@LeafA, Root[4]@LeafB", text)    # a clip that moves nothing says so, one that moves says what
        self.assertIn("StateB_Play: moves nothing", text)
        bad = json.loads(json.dumps(good))
        for c in bad["anim"]["clips"]:
            for t in c["tracks"]:
                t["bone_index"] = 2 if t["bone"] == "LeafA" else 1             # a swap of the two bone indices
        (stage_dir / "anim_manifest.json").write_text(json.dumps(bad))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mac.main(["inspect", "--stage", str(stage_dir)]), 1)
        self.assertIn("track LeafA filed under rig index 2 = LeafB", buf.getvalue())
        bad2 = json.loads(json.dumps(good))
        bad2["anim"]["rig"][1]["name"], bad2["anim"]["rig"][2]["name"] = "LeafB", "LeafA"
        (stage_dir / "anim_manifest.json").write_text(json.dumps(bad2))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mac.main(["inspect", "--stage", str(stage_dir)]), 1)
        self.assertIn("model node order differs from rig order", buf.getvalue())

    def test_dump_checks_position_only_when_there_is_a_block_per_rig_bone(self):
        """FAL-528 HOLD: CALUMI's read-back position is the order blocks were added, not the rig index the writer passed. A clip with fewer
        blocks than bones (a door: only animated bones) is a NOTE, not a failure; with one block per bone the contract is block i = bone i."""
        import contextlib
        import io
        import math as m
        out = self.fresh_stage("staged-d")
        folder = out / "Data" / "meshes" / "fo4port" / "interiors" / "vault" / "props" / "console01_anim"
        (folder / "characterassets").mkdir(parents=True, exist_ok=True)
        (folder / "animations").mkdir(parents=True, exist_ok=True)
        (folder / "characterassets" / "skeleton.rig").write_bytes(b"r" * 10)
        for n in ("StateA_Play", "StateB_Play"):
            (folder / "animations" / (n + ".af")).write_bytes(b"a" * 20)
        half = m.radians(157) / 2
        lid_turn = (m.sin(half), 0.0, 0.0, m.cos(half))                      # 157 degrees about x, as (x, y, z, w)
        ident = (0.0, 0.0, 0.0, 1.0)
        bones = [("Root", -1), ("Lid", 0), ("Button", 0)]

        class Fake:
            def __init__(self, layout):
                self.layout = layout

            def read(self, rig, af):
                a = os.path.basename(str(af)).startswith("StateA")
                lid_rot = [(0, ident), (30, lid_turn)] if a else [(0, ident), (30, ident)]
                blk = lambda pos, bone, rot, t=0: {"position": pos, "bone": bone, "rot": rot, "trans_count": t}   # noqa: E731
                root = blk(0, "Root", [(0, ident), (30, ident)])
                lid = blk(0 if self.layout == "two" else 1, "Lid", lid_rot)
                btn = blk(1 if self.layout == "two" else 2, "Button", [(0, ident), (30, ident)], 0 if a else 2)
                if self.layout == "two":                                       # the old layout: no root block (2 blocks, 3 bones)
                    return {"bones": bones, "blocks": [lid, btn]}
                if self.layout == "three":
                    return {"bones": bones, "blocks": [root, lid, btn]}
                if self.layout == "swapped":                                   # a block per bone, but in the wrong order
                    return {"bones": bones, "blocks": [root, {**btn, "position": 1}, {**lid, "position": 2}]}
                if self.layout == "dup":
                    return {"bones": bones, "blocks": [root, lid, {**lid, "position": 2}]}
                if self.layout == "alien":
                    return {"bones": bones, "blocks": [root, lid, blk(2, "Handle", [(0, ident)])]}
                raise AssertionError(self.layout)

        def run(layout):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = mac.dump_stage(type("A", (), dict(stage=str(out), dll="x.dll"))(), Fake(layout))
            return code, buf.getvalue()
        code, text = run("three")
        self.assertEqual(code, 0)
        self.assertIn("1: Lid (parent 0)", text)
        self.assertIn("block 1: bone 'Lid', 2 rotation keys", text)
        self.assertIn("last 157.0 deg about (1.0, 0.0, 0.0)", text)
        self.assertIn("first 0.0 deg about None", text)
        self.assertNotIn("NOTE", text)
        code, text = run("two")                                                  # a door-like layout: not a failure, said as a note
        self.assertEqual(code, 0)
        self.assertIn("NOTE: 2 blocks for 3 rig bones", text)
        self.assertIn("NOTE: position 0 but the rig has 'Root'", text)
        code, text = run("swapped")                                              # one block per bone but wrong order: the writer's contract broken
        self.assertEqual(code, 1)
        self.assertIn("one block per rig bone, but the block at position 1 is 'Button' and the rig has 'Lid' there", text)
        code, text = run("dup")
        self.assertEqual(code, 1)
        self.assertIn("two blocks for 'Lid'", text)
        code, text = run("alien")
        self.assertEqual(code, 1)
        self.assertIn("block names 'Handle', which the rig lacks", text)

    def test_inspect_says_re_stage_for_a_manifest_whose_rig_is_a_string(self):
        import contextlib
        import io
        stage_dir = self.root / "staged-old"
        stage_dir.mkdir()
        (stage_dir / "anim_manifest.json").write_text(json.dumps({"original": "x", "model": "a.nif", "states": {}, "anim": {"rig": "native", "clips": []}}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mac.main(["inspect", "--stage", str(stage_dir)]), 2)
        self.assertIn("re-stage", buf.getvalue())

    def test_quaternion_angle_axis_and_a_stage_without_files(self):
        import math as m
        self.assertEqual(mac.quat_angle_axis((0.0, 0.0, 0.0, 1.0)), (0.0, None))
        angle, axis = mac.quat_angle_axis((0.0, m.sin(m.radians(45)), 0.0, m.cos(m.radians(45))))
        self.assertEqual((angle, axis), (90.0, (0.0, 1.0, 0.0)))
        self.assertEqual(mac.quat_angle_axis((0.0, 0.0, 0.0, -1.0)), (0.0, None))      # the shorter way round: q and -q agree
        import tempfile as t
        with t.TemporaryDirectory() as d:
            (Path(d) / "anim_manifest.json").write_text(json.dumps({"model": "a\\\\b.nif"}))
            self.assertEqual(mac.dump_stage(type("A", (), dict(stage=d, dll="x"))(), object()), 2)

    def test_a_changed_stage_or_starfield_esm_is_refused_by_verify(self):
        out = self.fresh_stage("staged-v")
        plan = json.loads((out / "plan.json").read_text())
        with open(out / PLUGIN, "ab") as f:
            f.write(b"!")
        self.assertIn("changed after the stage", " ".join(mac.verify_stage(str(out), plan)))
        self.assertIn("is not the animation console probe's", " ".join(mac.verify_stage(str(out), dict(plan, kind="anim-probe"))))
        plan["inputs"]["Starfield.esm"]["sha256"] = "0" * 64
        self.assertIn("Starfield.esm changed since the stage", " ".join(mac.verify_stage(str(out), plan, str(self.data))))

    def test_log_command_reads_the_variant_a_reader(self):
        f = self.root / "d.log"
        self.assertEqual(mac.main(["log", "--file", str(f)]), 2)
        f.write_text("FO4SFANIM rt=1.0 spawn stage=10 base=77 ref=99 moved=true persist=true end=true\n"
                     "FO4SFANIM rt=2.0 play stage=21 name=Play01 ref=99 ok=true end=true\n"
                     "FO4SFANIM rt=3.0 event name=Done src=99 stage=21 since=0.5 after=0.64 end=true\n", encoding="utf-8")
        self.assertEqual(mac.main(["log", "--file", str(f)]), 0)


if __name__ == "__main__":
    unittest.main()
