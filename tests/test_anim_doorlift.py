"""The door and lift controls (FAL-489, the Scribe's vault111-gear-door rev 4 section 2c; Claude's request of 12 Nov 21:06 UTC): the script's
ids, stages, calls and events against the writer's (dotnet/AnimDoorLiftControl), the plugin the tool writes and the stage with a fake Papyrus
compiler and synthetic archives (never a game; the real compile, the real Starfield.esm and the real archives are the PC's job). The dotnet tests
skip without the .NET SDK."""
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
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_anim_doorlift as mad  # noqa: E402
import make_anim_probe as map_  # noqa: E402
import vault111_anim_graphs as graphs  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402
from test_anim_probe import fake_compiler, fake_sources  # noqa: E402

PSC = (ROOT / "scripts" / "newgame" / "FO4SF_AnimDoorLiftQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "AnimDoorLiftControl" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFAnimDoorLift.esm"
GRAPH_ENTRY = "Meshes\\AnimTextData\\Tables\\Graphs\\GenericOpenClose01.agx"
ANAM = "AnimTextData\\Tables\\Graphs\\GenericOpenClose01.agx"


def const_ids(text):
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


def strings(prefix, text):
    return [v for _, v in sorted(re.findall(rf'{prefix}\[(\d+)\] = "(\w+)"', text), key=lambda t: int(t[0]))]


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_stages_and_log_are_the_tools(self):
        ids = const_ids(TOOL_SRC)
        self.assertEqual((ids["QuestId"], ids["ControlId"], ids["DoorId"], ids["LiftId"]), (0x800, 0x801, 0xAA24A, 0x10C35))
        self.assertIn("int DoorControlId = 0x801", PSC)
        self.assertIn("int LiftId = 0x10C35", PSC)
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', PSC)
        self.assertIn('string GamePlugin = "Starfield.esm"', PSC)                  # the lift is the vanilla form, not a copy
        self.assertTrue(PSC.startswith("Scriptname FO4SF_AnimDoorLiftQuest extends Quest"))
        self.assertIn('Script = "FO4SF_AnimDoorLiftQuest"', TOOL_SRC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 20, 21, 22, 23, 24, 31, 32, 33, 34, 40, 60])
        self.assertIn(f"new int[{len(ran)}]", PSC)
        self.assertIn('string LogName = "FO4SFAnimDL"', PSC)
        self.assertTrue(mad.LOG.endswith("FO4SFAnimDL.0.log"))
        self.assertIn('" end=true"', PSC)

    def test_the_doc_comment_stays_under_the_repos_papyrus_limit(self):
        i = PSC.index("{")
        j = PSC.index("}", i)
        self.assertLess(len(PSC[i + 1:j].encode()), 3072)                          # tests/test_papyrus_strings.py (the 31 Oct load crash)

    def test_no_property_the_wait_form_is_never_called_and_the_master_is_starfield_only(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        code = "\n".join(ln.split(";")[0] for ln in PSC.splitlines() if not ln.startswith(" ") or ln.strip())
        self.assertNotIn("PlayAnimationAndWait", code)
        self.assertIn("masters are not exactly [Starfield.esm]", TOOL_SRC)
        self.assertIn("records of another plugin (overrides)", TOOL_SRC)

    def test_the_calls_are_claudes_door_then_lift_one_per_stage(self):
        """Claude, FAL-489, 12 Nov 21:06 UTC: door Open, Close, then (both false) StateA_Play, StateB_Play; lift Stage1, Stage1Transition,
        Stage2, Stage2Transition; one call per stage."""
        self.assertEqual(strings("DoorCalls", PSC), ["Open", "Close", "StateA_Play", "StateB_Play"])
        self.assertEqual(strings("LiftCalls", PSC), ["Stage1", "Stage1Transition", "Stage2", "Stage2Transition"])
        self.assertIn("PlayOne(stage, \"door\", DoorRef, DoorCalls[stage - 21])", PSC)
        self.assertIn("PlayOne(stage, \"lift\", LiftRef, LiftCalls[stage - 31])", PSC)
        self.assertIn("elseif stage >= 21 && stage <= 24", PSC)
        self.assertIn("elseif stage >= 31 && stage <= 34", PSC)
        self.assertEqual(PSC.count("r.PlayAnimation(n)"), 1)
        self.assertIn("bool ok = r.PlayAnimation(n)", PSC)

    def test_the_registered_events_are_claudes_door_list_and_the_lifts_calls(self):
        door = strings("DoorEvents", PSC)
        for e in ("Open", "Close", "Trans01", "IsOn", "IsOff", "Done"):               # Claude's list
            self.assertIn(e, door)
        lift = strings("LiftEvents", PSC)
        for e in ("Stage1", "Stage1Transition", "Stage2", "Stage2Transition"):        # the dump of twostages is UNREAD: its calls stand in
            self.assertIn(e, lift)
        self.assertIn(f"new string[{len(door)}]", PSC)
        self.assertIn(f"new string[{len(lift)}]", PSC)
        self.assertIn("RegisterForAnimationEvent(r, n)", PSC)
        self.assertIn("UNREAD here", PSC)                                              # the script says so itself

    def test_the_lift_is_placed_disabled_and_enabled_only_after_a_move_away_from_the_player(self):
        self.assertIn("LiftRef = p.PlaceAtMe(liftBase, 1, true, true, false)", PSC)    # abInitiallyDisabled = true
        self.assertIn("LiftRef.Enable(false)", PSC)
        self.assertIn("if LiftRef && liftMoved", PSC)                                  # not moved, not enabled: never a platform on the player
        self.assertIn("float LiftM = 40.0", PSC)
        self.assertIn("p.PlaceAtMe(doorBase, 1, true, false, false)", PSC)
        # the move is an optional native: with no MoveTo the optional lines stay comments and the lift stays disabled
        self.assertEqual(map_.enable(PSC, []), PSC)
        on = map_.enable(PSC, ["ObjectReference.MoveTo"])
        self.assertIn("        LiftRef.MoveTo(p, LiftM", on.replace("            ", "        "))
        self.assertEqual(map_.optional_names(PSC), ["ObjectReference.MoveTo", "ObjectReference.Delete"])

    def test_every_play_and_event_line_names_which_reference(self):
        self.assertIn('" label=" + Label(akSource)', PSC)
        self.assertIn("label=door base=", PSC)
        self.assertIn("label=lift base=", PSC)
        self.assertIn('"play stage=" + stage + " label=" + what', PSC)

    def test_the_log_reader_takes_the_scripts_lines(self):
        """A session as the script would write it: both refs spawned, a door call true with events, a lift call false."""
        lines = [
            "FO4SFANIM rt=1.0 init version=1 end=true",
            "FO4SFANIM rt=2.0 spawn stage=10 label=door base=1 ref=11 moved=true persist=true end=true",
            "FO4SFANIM rt=2.0 spawn stage=10 label=lift base=2 ref=12 moved=true enabled=true persist=true end=true",
            "FO4SFANIM rt=3.0 register stage=10 label=door name=Open ref=11 ok=true end=true",
            "FO4SFANIM rt=4.0 play stage=21 label=door name=Open ref=11 ok=true end=true",
            "FO4SFANIM rt=5.0 event name=Done label=door src=11 stage=21 since=1.0 end=true",
            "FO4SFANIM rt=6.0 play stage=31 label=lift name=Stage1 ref=12 ok=false end=true",
        ]
        s = map_.anim_probe_log.summarize(lines)
        self.assertEqual(s["spawned"], 11)
        self.assertEqual(s["verdict"][0], "EVENTS ARRIVE")

    def test_the_committed_script_compiles_alone_every_optional_and_void_line_is_a_comment(self):
        self.assertEqual(len(map_.VOID.findall(PSC)), 2)
        self.assertIn(map_.BOOL_LINE, PSC)


class ToolBase(unittest.TestCase):
    """The built tool and a synthetic Starfield.esm; no tests of its own."""
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "AnimDoorLiftControl"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/AnimDoorLiftControl/bin/Release/net9.0/AnimDoorLiftControl.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-animdl-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.master = cls.root / "m" / "Starfield.esm"
        r = cls.run_tool("fixture", cls.root / "m")
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)


class ToolTests(ToolBase):
    def test_info_names_the_door_and_the_lift(self):
        info = mad.parse_info(self.run_tool("info", self.master).stdout)
        self.assertEqual(info["door_edid"], "AK_Ext_Bld_WallA_DoorA_01_Alt02")
        self.assertTrue(info["door_anam"].lower().endswith("simpleopenclose01.agx"))
        self.assertEqual(info["door_cnam"], "Architecture\\Doors\\Animations")
        self.assertEqual((info["lift_type"], info["lift_edid"]), ("ACTI", "ShipQuickLift1"))
        self.assertEqual(info["lift_names_twostages"], "True")

    def test_build_and_check(self):
        out = self.root / "b1"
        proc = self.run_tool("build", self.master, out, ANAM)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        check = self.run_tool("check", out / PLUGIN, self.master, ANAM)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("scripts [FO4SF_AnimDoorLiftQuest (0 properties)]", check.stdout)
        flat = check.stdout.replace("\\\\", "\\")
        self.assertIn(f"ACTI FO4SF_AnimDoorControl model Meshes/Architecture/Doors/WallA_DoorA_01.nif components 1 graph ANAM {ANAM} "
                      f"BNAM Architecture\\Doors\\CharacterAssets\\skeleton.rig CNAM Architecture\\Doors\\Animations", flat)    # the door's model, rig and folder; our graph
        self.assertIn("all checks pass", check.stdout)

    def test_the_plugin_adds_one_quest_and_one_acti_and_no_door_or_override(self):
        out = self.root / "b2"
        self.assertEqual(self.run_tool("build", self.master, out, ANAM).returncode, 0)
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
                kinds[sig] = kinds.get(sig, 0) + 1
                if sig != b"TES4":
                    ids.append(struct.unpack_from("<I", buf, i + 12)[0])
                i += 24 + size
        walk(data, 0, len(data))
        self.assertEqual({k: v for k, v in kinds.items() if k != b"TES4"}, {b"QUST": 1, b"ACTI": 1})       # the vanilla DOOR is not copied or overridden
        self.assertEqual(sorted(ids), [0x01000800, 0x01000801])

    def test_the_vanilla_door_graph_is_refused_as_the_control_graph(self):
        proc = self.run_tool("build", self.master, self.root / "b3", "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("is not genericopenclose01", proc.stderr)
        self.assertFalse((self.root / "b3").exists())

    def test_a_door_whose_graph_is_not_simpleopenclose01_is_refused(self):
        other = self.root / "o"
        other.mkdir()
        raw = bytearray(self.master.read_bytes())
        i = raw.find(b"SimpleOpenClose01")
        self.assertGreater(i, 0)
        raw[i:i + len(b"SimpleOpenClose01")] = b"SimpleOpenCloseXX"
        (other / "Starfield.esm").write_bytes(bytes(raw))
        proc = self.run_tool("build", other / "Starfield.esm", self.root / "b5", ANAM)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("not simpleopenclose01", proc.stderr)


class StageTests(ToolBase):
    """The whole stage on a synthetic Starfield.esm, a synthetic archive next to it and the fake compiler."""
    def data_dir(self, name, graph=True):
        d = self.root / name
        d.mkdir()
        shutil.copy(self.master, d / "Starfield.esm")
        files = {GRAPH_ENTRY: b"<root/>"} if graph else {"Meshes\\Other.agx": b"<root/>"}
        (d / "Starfield - Animations.ba2").write_bytes(general_archive(files))
        (d / "Starfield - Meshes01.ba2").write_bytes(general_archive({"Meshes\\x.nif": b"n"}))
        return d

    def args(self, out, d, extra=()):
        z = self.root / (Path(out).name + "-cr.zip")
        fake_sources(z)
        return ["stage", "--out", str(out), "--starfield", str(d / "Starfield.esm"), "--compiler", str(fake_compiler(self.root)),
                "--content-resources", str(z), *extra]

    def test_stage_builds_compiles_and_pins_every_file(self):
        d = self.data_dir("d1")
        out = self.root / "staged"
        self.assertEqual(mad.main(self.args(out, d)), 0)
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual((plan["kind"], plan["plugins"]), ("anim-doorlift", [PLUGIN]))
        self.assertEqual(plan["graph"], {"anam": ANAM, "archive_entry": GRAPH_ENTRY})
        self.assertEqual(plan["vanilla"]["lift_edid"], "ShipQuickLift1")
        self.assertEqual(set(plan["outputs"]), {PLUGIN, "Data/Scripts/FO4SF_AnimDoorLiftQuest.pex"})        # no clip, no game asset
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mad.sha256(str(d / "Starfield.esm")))
        self.assertEqual(mad.verify_stage(str(out), plan, str(d)), [])
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        readme = (out / "README.txt").read_text()
        self.assertIn(ANAM, readme)
        self.assertIn("MOVING PLATFORM", readme)
        self.assertIn("ShipQuickLift1", readme)
        with self.assertRaises(SystemExit):                                                              # an earlier stage is never overwritten
            mad.main(self.args(out, d))

    def test_a_missing_graph_stops_the_stage_with_the_archive_to_pass(self):
        d = self.data_dir("d2", graph=False)
        out = self.root / "staged-nograph"
        with self.assertRaises(SystemExit) as ctx:
            mad.main(self.args(out, d))
        self.assertIn("genericopenclose01.agx is not in the archives read", str(ctx.exception))
        self.assertIn("Starfield - Animations.ba2", str(ctx.exception))
        self.assertFalse(out.exists())

    def test_a_changed_stage_is_refused_by_verify(self):
        d = self.data_dir("d3")
        out = self.root / "staged-v"
        mad.main(self.args(out, d))
        plan = json.loads((out / "plan.json").read_text())
        with open(out / PLUGIN, "ab") as f:
            f.write(b"!")
        self.assertIn("changed after the stage", " ".join(mad.verify_stage(str(out), plan)))
        self.assertIn("is not the door and lift control's", " ".join(mad.verify_stage(str(out), dict(plan, kind="anim-generic"))))

    def test_no_archive_matching_the_pattern_is_said(self):
        d = self.data_dir("d4")
        with self.assertRaises(SystemExit) as ctx:
            mad.main(self.args(self.root / "staged-noarc", d, ["--game-archive", "Nothing*.ba2"]))
        self.assertIn("no archive matched", str(ctx.exception))

    def test_log_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "log.txt")
            self.assertEqual(mad.main(["log", "--file", f]), 2)
            Path(f).write_text("[11/12/2026 - 06:00:00AM] FO4SFANIM rt=1.0 spawn stage=10 label=door base=77 ref=99 moved=true persist=true end=true\n", encoding="utf-8")
            self.assertEqual(mad.main(["log", "--file", f]), 0)
            Path(f).write_text("nothing here\n", encoding="utf-8")
            self.assertEqual(mad.main(["log", "--file", f]), 1)

    def test_the_precheck_runs_on_the_door_lift_script(self):
        z = self.root / "cr-pre.zip"
        fake_sources(z)
        out = self.root / "pre.json"
        self.assertEqual(mad.main(["precheck", "--content-resources", str(z), "--out", str(out)]), 0)
        r = json.loads(out.read_text())
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["optional"], {"ObjectReference.MoveTo": True, "ObjectReference.Delete": True})


if __name__ == "__main__":
    unittest.main()
