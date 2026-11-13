"""The converted console on genericstategraph01, four states in a row (FAL-489; the Scribe's vault111-console-stages rev 4; Claude's request of
12 Nov 22:49 UTC after the generic control passed in the game): its script's ids, stages and call list against the writer's
(dotnet/AnimConsoleFour), the stager with a REAL chain conversion of a synthetic console (native writer replaced by a fake), a synthetic archive
that holds the graph, fake base sources and a fake Papyrus compiler (never a game; the real conversion, the CALUMI library, the real graph path
and the real compile are the PC's job). The dotnet tests skip without the .NET SDK."""
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
import make_anim_console_four as maf  # noqa: E402
import make_anim_probe as probe_a  # noqa: E402
from fo4sf import anim_object, native_door, nif, pipeline  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402
from test_anim_console import BASES_D, FakeSrc, MODEL_IN_PORT, norm  # noqa: E402
from test_anim_object import STATES, console_nif, donor, fake_exporter, fake_template  # noqa: E402
from test_anim_probe import fake_compiler, fake_sources  # noqa: E402

PSC = (ROOT / "scripts" / "newgame" / "FO4SF_AnimConsoleFourQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "AnimConsoleFour" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFAnimConsoleFour.esm"
ANAM = "AnimTextData\\Tables\\Graphs\\GenericStateGraph01.agx"
GRAPH_ENTRY = "Meshes\\" + ANAM


def strings(prefix, text=PSC):
    return [v for _, v in sorted(re.findall(rf'{prefix}\[(\d+)\] = "(\w+)"', text), key=lambda t: int(t[0]))]


class ScriptTests(unittest.TestCase):
    def test_ids_stages_log_and_layout_match_the_tool_and_the_reader(self):
        self.assertTrue(PSC.startswith("Scriptname FO4SF_AnimConsoleFourQuest extends Quest"))
        self.assertIn('Script = "FO4SF_AnimConsoleFourQuest"', TOOL_SRC)
        self.assertIn("const uint QuestId = 0x800", TOOL_SRC)
        self.assertIn('string LogName = "FO4SFAnimF"', PSC)
        self.assertTrue(maf.LOG.endswith("FO4SFAnimF.0.log"))
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', PSC)
        self.assertIn('string BasePlugin = "FO4Port.esm"', PSC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 11, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 40, 60])
        self.assertIn(f"StageList = new int[{len(ran)}]", PSC)
        self.assertIn(f"DoneList = new bool[{len(ran)}]", PSC)
        self.assertIn('"FO4SFANIM rt="', PSC)                                  # the variant A reader reads this log too
        from fo4sf import anim_probe_log
        for e in anim_probe_log.EVENTS:
            if e in ("step",):                                                  # the Activate stage is not in this kit
                continue
            self.assertRegex(PSC, rf'Trace\("{e}[ "]')

    def test_the_doc_comment_stays_under_the_repos_papyrus_limit(self):
        i = PSC.index("{")
        j = PSC.index("}", i)
        self.assertLess(len(PSC[i + 1:j].encode()), 3072)                      # tests/test_papyrus_strings.py (the 31 Oct load crash)

    def test_no_property_no_wait_form_one_base_line_and_a_spawn_not_a_cell(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        code = "\n".join(l.split(";")[0] for l in PSC.splitlines() if not l.startswith(" ") or l.strip())
        self.assertNotIn("PlayAnimationAndWait", code)
        self.assertEqual(len(mac.BASE_LINE.findall(PSC)), 1)
        self.assertIn("p.PlaceAtMe(base, 1, true, false, false)", PSC)
        self.assertIn("Game.GetFormFromFile(BaseId, BasePlugin)", PSC)
        self.assertEqual(PSC.count("TestRef.PlayAnimation(n)"), 1)             # CallOn (the side copy is TestRef2)
        self.assertEqual(PSC.count("TestRef2.PlayAnimation(n)"), 1)

    def test_the_calls_are_the_requested_order_numbered_then_direct_then_the_spare(self):
        """Claude, FAL-489, 12 Nov 22:49 UTC: Play01, Play02, Play03, Play04, then StateA_Idle, StateB_Idle, StateC_Idle, StateD_Idle; the spare play
        slot StateD_Play is added last (stage 29), so it cannot disturb the requested eight."""
        names = strings("PlayNames")
        self.assertEqual(names[:8], ["Play01", "Play02", "Play03", "Play04", "StateA_Idle", "StateB_Idle", "StateC_Idle", "StateD_Idle"])
        self.assertEqual(names[8:], ["StateD_Play"])
        self.assertIn(f"PlayNames = new string[{len(names)}]", PSC)
        self.assertIn("elseif stage >= 21 && stage <= 29", PSC)
        self.assertIn("PlayOne(stage, PlayNames[stage - 21])", PSC)
        self.assertEqual(len(names), 29 - 21 + 1)                              # one name per play stage, nothing left over

    def test_the_scene_stage_is_a_timer_chain_that_calls_a_lid_play_the_button_and_its_idle(self):
        """Claude, FAL-489, 12 Nov 23:58 UTC: Play01, then the button clip, then the idle call that holds it. Stage 30, one window, three timed calls."""
        self.assertIn("elseif stage == 30\n        SceneStart(stage)", PSC)
        self.assertIn("int TIMER_SCENE = 300", PSC)
        self.assertLess(PSC.index("aiTimerID == TIMER_SCENE"), PSC.index("aiTimerID >= TIMER_QUIET"))   # else the quiet branch would take id 300
        self.assertLess(PSC.index("aiTimerID == TIMER_RESAY"), PSC.index("aiTimerID >= TIMER_QUIET"))
        scene = PSC[PSC.index("Function SceneNext()"):PSC.index("Function Cleanup()")]
        self.assertEqual(re.findall(r'CallOn\(SceneStage, ([^)]*)\)', scene), ['"Play01"', "ButtonPlay", "ButtonIdle"])             # the order
        self.assertIn('CallOn(stage, "StateA_Idle")', PSC)                                                  # it starts from rest
        self.assertEqual(PSC.count("TestRef.PlayAnimation(n)"), 1)                                           # one place makes the call (CallOn)
        self.assertIn("StartTimer(ButtonS + 0.7, TIMER_SCENE)", scene)                                      # the idle follows the clip's own length
        for line in ('string ButtonPlay = "StateC_Play"   ;BUTTONPLAY', 'string ButtonIdle = "StateC_Idle"   ;BUTTONIDLE', "float ButtonS = 0.633               ;BUTTONS"):
            self.assertEqual(PSC.count(line), 1)
        self.assertIn('ListenName = "scene"', PSC)

    def test_the_registered_events_cover_the_controls_read_and_the_four_states(self):
        events = strings("EventNames")
        for e in ("Trans01", "Trans03", "Done", "IsOn", "IsOff", "Play01", "Play02", "Play03", "Play04", "Play05", "TurnOn", "TurnOff", "Opened",
                  "StateA_Idle", "StateA_Play", "StateB_Idle", "StateB_Play", "StateC_Idle", "StateC_Play", "StateD_Idle", "StateD_Play"):
            self.assertIn(e, events)
        self.assertEqual(len(events), len(set(events)))
        self.assertIn(f"EventNames = new string[{len(events)}]", PSC)
        self.assertIn("Reg(r, EventNames[i])", PSC)

    def test_the_return_notice_is_shown_at_once_again_every_two_seconds_and_in_the_window_close(self):
        """The control's session missed two return lines (the notices queued behind others). The PLAY line is shown right after the call, before any
        other notice of the stage, shown again three times two seconds apart, and the window-close notice names the call and its return."""
        self.assertIn("float RESAY_S = 2.0", PSC)
        self.assertIn("int RESAY_TIMES = 3", PSC)
        self.assertIn('LastPlayLine = "PLAY s" + stage + " " + n + " ok=" + ListenOk', PSC)
        self.assertIn("Say(LastPlayLine)", PSC)
        self.assertIn('Say(LastPlayLine + " (again)")', PSC)
        self.assertIn("StartTimer(RESAY_S, TIMER_RESAY)", PSC)
        self.assertIn('Say("W s" + stage + " " + ListenName + " ok=" + ListenOk + " quiet")', PSC)
        self.assertIn('Say("W s" + stage + " " + ListenName + " ok=" + ListenOk + " heard " + WindowEvents)', PSC)
        body = PSC[PSC.index("Function PlayOne("):PSC.index("Function Cleanup()")]
        self.assertLess(body.index("bool ok = TestRef.PlayAnimation(n)"), body.index("Say(LastPlayLine)"))
        self.assertNotIn("Say(", body.split("Say(LastPlayLine)")[0])             # nothing is shown before the return line
        self.assertNotIn("Quiet", PSC.replace("TIMER_QUIET", ""))                # the silent stages of variant D are not in this kit
        # the before-reading is logged only, so it cannot queue a notice ahead of the return
        self.assertIn('if when != "before"', PSC)
        timer = PSC[PSC.index("Event OnTimer"):PSC.index("Function Poll()")]
        self.assertLess(timer.index("aiTimerID == TIMER_RESAY"), timer.index("aiTimerID >= TIMER_QUIET"))   # 200 is also >= 100: the resay branch must come first

    def test_every_play_stage_calls_both_copies_and_the_events_of_the_side_copy_are_logged_not_shown(self):
        self.assertIn('ListenOk = ListenOk + "/" + ok2', PSC)
        self.assertIn("if akSource != TestRef2", PSC)
        self.assertIn("SpawnSide(stage)", PSC)
        self.assertIn("Reading(\"stage40\", stage, TestRef2)", PSC)
        self.assertIn("TestRef2.Disable(false)", PSC)

    def test_the_committed_script_compiles_alone_and_the_register_shape_replaces_cleanly(self):
        self.assertEqual(probe_a.enable(PSC, []), PSC)
        self.assertEqual(probe_a.optional_names(PSC), ["ObjectReference.MoveTo", "ObjectReference.SetAngle", "ObjectReference.Delete"])
        self.assertEqual(len(probe_a.VOID.findall(PSC)), 2)
        self.assertIn(probe_a.BOOL_LINE, PSC)

    def test_the_base_id_is_written_once_and_a_bad_one_is_refused(self):
        self.assertIn("int BaseId = 0x001234  ;BASE", mac.set_base_id(PSC, "001234"))
        with self.assertRaises(SystemExit):
            mac.set_base_id(PSC, "xyz")


class GraphAnamTests(unittest.TestCase):
    def test_the_graph_path_is_the_archives_without_the_meshes_prefix_and_absent_is_none(self):
        import vault111_anim_graphs as graphs
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "Starfield - Animations.ba2")
            Path(p).write_bytes(general_archive({GRAPH_ENTRY: b"<root/>"}))
            self.assertEqual(maf.graph_anam(graphs.open_archives([p])), (ANAM, GRAPH_ENTRY))
            Path(p).write_bytes(general_archive({"Meshes\\AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx": b"<root/>"}))
            self.assertEqual(maf.graph_anam(graphs.open_archives([p])), (None, None))

    def test_pose_lines_say_what_each_idle_holds(self):
        clips = [{"name": "StateA_Idle", "hold_of": "StateA_Play", "hold_frame": "first"}, {"name": "StateB_Idle", "hold_of": "StateA_Play", "hold_frame": "last"},
                 {"name": "StateC_Idle", "hold_of": "StateB_Play", "hold_frame": "last"}]
        self.assertEqual(maf.pose_lines(clips), ["StateA_Idle: holds the first frame of StateA_Play", "StateB_Idle: holds the last frame of StateA_Play",
                                                 "StateC_Idle: holds the last frame of StateB_Play", "StateD_Idle: not in the clip table"])


class ToolBase(unittest.TestCase):
    """The built tool, a synthetic Starfield.esm and FO4Port.esm; no tests of its own."""
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "AnimConsoleFour"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/AnimConsoleFour/bin/Release/net9.0/AnimConsoleFour.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-animf-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.data = cls.root / "Data"
        r = cls.run_tool("fixture", cls.data)
        assert r.returncode == 0, r.stdout + r.stderr
        (cls.data / "Starfield - Animations.ba2").write_bytes(general_archive({GRAPH_ENTRY: b"<root/>"}))
        cls.margs = ["--model", "fo4port\\interiors\\vault\\props\\console01_anim.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations", "--graph", ANAM]

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def paths(self):
        return self.data / "FO4Port.esm", self.data / "Starfield.esm"


class ToolTests(ToolBase):
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
        self.assertIn(norm("ANAM " + ANAM + " BNAM fo4port\\r\\skeleton.rig CNAM fo4port\\r\\animations"), out)
        self.assertIn("scripts [FO4SF_AnimConsoleFourQuest (0 properties)]", out)
        self.assertIn("stages [10,11,20,21,22,23,24,25,26,27,28,29,30,40,60]", out)
        wrong = self.run_tool("check", out_dir / PLUGIN, port, sf, "--model", "other.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations", "--graph", ANAM)
        self.assertEqual(wrong.returncode, 1)
        self.assertIn("the model is not Meshes/other.nif", norm(wrong.stdout))

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

    def test_a_graph_that_is_not_the_four_state_one_is_refused_by_build_and_by_check(self):
        port, sf = self.paths()
        other = [*self.margs[:-1], "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx"]
        proc = self.run_tool("build", port, sf, self.root / "b3", *other)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("is not genericstategraph01", proc.stderr)
        self.assertFalse((self.root / "b3").exists())
        built = self.root / "b4"
        self.assertEqual(self.run_tool("build", port, sf, built, *self.margs).returncode, 0)
        proc = self.run_tool("check", built / PLUGIN, port, sf, *other)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("is not genericstategraph01", proc.stderr)
        no_graph = self.run_tool("build", port, sf, self.root / "b5", *self.margs[:-2])                    # --graph is required
        self.assertEqual(no_graph.returncode, 2)

    def test_a_check_against_another_graph_path_of_the_right_word_fails_on_the_component(self):
        port, sf = self.paths()
        built = self.root / "b6"
        self.assertEqual(self.run_tool("build", port, sf, built, *self.margs).returncode, 0)
        proc = self.run_tool("check", built / PLUGIN, port, sf, *self.margs[:-1], "Elsewhere\\genericstategraph01.agx")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("the animation graph component is not (genericstategraph01, rig, clip folder) exactly once", norm(proc.stdout))

    def test_a_base_that_is_not_there_is_refused_by_name(self):
        port, sf = self.paths()
        proc = self.run_tool("build", port, sf, self.root / "b7", *self.margs, "--edid", "NoSuchActi")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 ACTI named NoSuchActi", proc.stderr)


class RealChainConv:
    """The real pipeline.Converter.convert_anim_object on the synthetic console (the native writer replaced by a fake): what the stager calls."""
    def __init__(self, staging, textures=()):
        self.staging, self.textures, self.calls = staging, textures, []
        conv = pipeline.Converter.__new__(pipeline.Converter)
        raw = nif.serialize(console_nif())
        conv.src = type("S", (), {"mesh": staticmethod(lambda name: raw)})()
        conv.staging, conv.prefix, conv.door_anim_dll = staging, "fo4port", "CALUMI.dll"
        conv.door_physics_donor, conv.collision_template = donor(), fake_template()
        conv.stats = {"assets": 0, "failed": 0}
        conv._shape_material = lambda src, s: "Materials\\x.mat"
        self.conv = conv

    def convert_anim_object(self, name, states, foley=None, **kw):
        self.calls.append((name, dict(states), foley, kw))
        with unittest.mock.patch.object(native_door, "export", fake_exporter):
            res = self.conv.convert_anim_object("Meshes\\Interiors\\Vault\\Console01.nif", states, foley, **kw)
        for t in self.textures:
            p = os.path.join(self.staging, *t.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            Path(p).write_bytes(b"dds")
        return res


class StageTests(ToolBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shared_holder = {}
        cls.shared = cls.root / "staged"
        assert maf.stage(cls.args(cls.shared, foley="QST_Flip"), converter=cls.converter(cls.shared_holder)) == 0

    @classmethod
    def args(cls, out, **kw):
        z = cls.root / (Path(out).name + "-cr.zip")
        fake_sources(z, BASES_D)
        base = dict(out=str(out), starfield_data=str(cls.data), port_data="", game_archive=[], fo4_data="fo4", door_anim_dll="d.dll", collision_template="c.nif",
                    texconv="t.exe", content_resources=str(z), compiler=str(fake_compiler(cls.root)), states="Stage1=StateA_Play,Stage2=StateB_Play", slow="",
                    foley="", model="", edid=mac.EDID)
        base.update(kw)
        return type("A", (), base)()

    @classmethod
    def converter(cls, holder=None, textures=()):
        raw = nif.serialize(console_nif())

        def make(a, staging):
            conv = RealChainConv(staging, textures)
            if holder is not None:
                holder["conv"] = conv
            return FakeSrc(raw), conv
        return make

    def test_stage_converts_in_chain_mode_with_the_real_graph_path_and_pins_every_file(self):
        out = self.shared                                                                  # staged once in setUpClass with foley QST_Flip
        conv = self.shared_holder["conv"]
        self.assertTrue(conv.calls[0][0].lower().endswith("console01.nif"))
        name, states, foley, kw = conv.calls[0]
        self.assertEqual((states, foley), (STATES, "QST_Flip"))
        self.assertEqual(kw, {"idles": "chain", "graph": ANAM, "slow": {}})                            # chain idles and the path read from the archive, not a constant
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual((plan["kind"], plan["plugins"]), ("anim-console-four", [PLUGIN]))
        self.assertEqual(plan["graph"], {"anam": ANAM, "archive_entry": GRAPH_ENTRY})
        self.assertEqual(plan["archives"], ["Starfield - Animations.ba2"])
        self.assertEqual(set(plan["inputs"]), {"Starfield.esm", "FO4Port.esm"})
        outputs = set(plan["outputs"])
        self.assertIn(PLUGIN, outputs)
        self.assertIn("Data/Scripts/FO4SF_AnimConsoleFourQuest.pex", outputs)
        base = "Data/meshes/fo4port/interiors/vault/console01_anim/animations/"
        for slot in anim_object.slot_names(STATES, "chain"):                               # all eight clips are pinned, .af and .afx
            self.assertIn(f"{base}{slot}.af", outputs)
            self.assertIn(f"{base}{slot}.afx", outputs)
        self.assertEqual(plan["optional"]["ObjectReference.MoveTo"], "kept")
        self.assertEqual(maf.verify_stage(str(out), plan, str(self.data)), [])
        manifest = json.loads((out / "anim_manifest.json").read_text())
        self.assertEqual((manifest["base_id"], manifest["foley"], manifest["graph"]["anam"]), ("001234", "QST_Flip", ANAM))
        self.assertEqual(manifest["anim"]["anim_graph"], ANAM)
        self.assertEqual(manifest["anim"]["idles"], "chain")
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        self.assertIn("int BaseId = 0x001234  ;BASE", (out / "FO4SF_AnimConsoleFourQuest.psc").read_text())
        self.assertFalse((out / "work").exists())
        with self.assertRaises(SystemExit):                                                  # an earlier stage is never overwritten
            maf.stage(self.args(out), converter=self.converter())

    def test_the_readme_and_the_manifest_say_what_every_idle_holds(self):
        readme = (self.shared / "README.txt").read_text()
        for line in ("StateA_Idle: holds the first frame of StateA_Play", "StateB_Idle: holds the last frame of StateA_Play",
                     "StateC_Idle: holds the last frame of StateB_Play", "StateD_Idle: holds the last frame of StateB_Play"):      # two mapped: the last pose repeats
            self.assertIn(line, readme)
        self.assertIn(ANAM, readme)
        self.assertIn("StateC_Play: 0.0333 s (1 frames)", readme)                                                                  # the spare play slot
        self.assertIn("starts from StateB_Idle", readme)
        self.assertIn("stages 10 11 20 21..30 40 60", readme)
        self.assertIn("anim_console_four_install.py install", readme)
        self.assertIn("THROWAWAY STATE ONLY, NO SAVE", readme)
        quest_stages = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        self.assertEqual(quest_stages, [10, 11, 20] + list(range(21, 31)) + [40, 60])                                               # the README's "21..29" is the quest's

    def test_the_scene_is_written_into_the_script_from_the_clip_table_and_the_slow_factor_is_applied(self):
        """Stage 30 calls Play01, then the SECOND clip of the chain by its slot, then that slot's Idle; the stager writes the slot and the clip's seconds
        (the stretched ones) into the three ;BUTTON... lines. Slowing a clip by 4 makes it four times as long and changes nothing else."""
        plain, slow = self.root / "staged-plain", self.root / "staged-slow"
        amap = "Stage1=StateA_Play,Stage2=StateC_Play"
        self.assertEqual(maf.stage(self.args(plain, states=amap), converter=self.converter()), 0)
        self.assertEqual(maf.stage(self.args(slow, states=amap, slow="Stage2=4"), converter=self.converter()), 0)
        secs = {}
        for tag, out in (("plain", plain), ("slow", slow)):
            text = (out / (maf.SCRIPT + ".psc")).read_text()
            self.assertIn('string ButtonPlay = "StateC_Play"   ;BUTTONPLAY', text)
            self.assertIn('string ButtonIdle = "StateC_Idle"   ;BUTTONIDLE', text)
            secs[tag] = float(re.search(r"float ButtonS = ([0-9.]+)   ;BUTTONS", text).group(1))
            manifest = json.loads((out / "anim_manifest.json").read_text())
            row = {c["name"]: c for c in manifest["anim"]["clips"]}
            self.assertEqual(secs[tag], row["StateC_Play"]["seconds"])                                 # the script holds the clip table's seconds
        self.assertAlmostEqual(secs["slow"], secs["plain"] * 4, places=3)
        self.assertEqual(json.loads((slow / "plan.json").read_text())["states"], {"Stage1": "StateA_Play", "Stage2": "StateC_Play"})
        self.assertEqual(json.loads((slow / "anim_manifest.json").read_text())["slow"], {"StateC_Play": 4})
        self.assertIn("Slowed: {'StateC_Play': 4}", (slow / "README.txt").read_text())
        rows = {c["name"]: c for c in json.loads((slow / "anim_manifest.json").read_text())["anim"]["clips"]}
        base = {c["name"]: c for c in json.loads((plain / "anim_manifest.json").read_text())["anim"]["clips"]}
        self.assertEqual(rows["StateC_Play"]["slowed"], 4)
        self.assertEqual(rows["StateA_Play"]["seconds"], base["StateA_Play"]["seconds"])                  # another clip is not touched
        self.assertEqual(rows["StateC_Idle"]["motion"], base["StateC_Idle"]["motion"])                    # the held poses are the same poses

    def test_a_slow_entry_that_names_nothing_or_a_bad_factor_is_refused_before_anything_is_done(self):
        for bad in ("Stage9=4", "Stage2=1", "Stage2=2.5", "Stage2", "Stage2=9"):
            with self.subTest(bad=bad):
                with self.assertRaises(SystemExit) as ctx:
                    maf.stage(self.args(self.root / "staged-badslow", slow=bad), converter=self.converter())
                self.assertIn("--slow", str(ctx.exception))
        self.assertFalse((self.root / "staged-badslow").exists())

    def test_the_default_map_is_the_scene_map_and_the_scene_button_is_its_second_clip(self):
        self.assertEqual(maf.STATES_DEFAULT, "Stage2=StateA_Play,Stage3=StateC_Play,Stage4=StateD_Play")
        self.assertEqual(maf.scene_slot(anim_object.parse_states(maf.STATES_DEFAULT, anim_object.PLAY_SLOTS4)), "StateC_Play")
        self.assertEqual(maf.scene_slot(anim_object.parse_states("Stage2=StateA_Play,Stage3=StateB_Play", anim_object.PLAY_SLOTS4)), "StateB_Play")
        self.assertEqual(maf.scene_slot({"Stage2": "StateD_Play"}), "StateD_Play")                       # one clip: itself
        self.assertEqual(anim_object.parse_slow(maf.SLOW_DEFAULT, anim_object.parse_states(maf.STATES_DEFAULT, anim_object.PLAY_SLOTS4)), {"StateC_Play": 4})

    def test_the_alternative_map_that_leaves_slot_b_out_stages_and_says_so(self):
        """The graph returns from StateB_Play to the rest pose (control, 12 Nov): the button clip on StateC_Play rests in StateC_Idle instead."""
        out = self.root / "staged-alt"
        self.assertEqual(maf.stage(self.args(out, states="Stage1=StateA_Play,Stage2=StateC_Play"), converter=self.converter()), 0)
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual(plan["states"], {"Stage1": "StateA_Play", "Stage2": "StateC_Play"})
        readme = (out / "README.txt").read_text()
        self.assertIn("StateB_Idle: holds the last frame of StateA_Play", readme)
        self.assertIn("StateC_Idle: holds the last frame of StateC_Play", readme)
        self.assertIn("StateB_Play: 0.0333 s (1 frames)", readme)                       # the slot nobody mapped is a spare
        self.assertEqual(maf.verify_stage(str(out), plan, str(self.data)), [])
        self.assertEqual(len([k for k in plan["outputs"] if "/animations/" in k]), 16)

    def test_the_kit_holds_eight_clips_and_no_game_asset(self):
        files = json.loads((self.shared / "plan.json").read_text())["outputs"]
        clips = [k for k in files if "/animations/" in k]
        self.assertEqual(len(clips), 16)                                                                                            # 8 .af + 8 .afx
        self.assertFalse([k for k in files if k.lower().endswith((".dds", ".ba2"))])                                                # no texture, no archive

    def test_a_missing_graph_stops_the_stage_with_the_archive_to_pass(self):
        d = self.root / "d2"
        d.mkdir()
        shutil.copy(self.data / "Starfield.esm", d / "Starfield.esm")
        shutil.copy(self.data / "FO4Port.esm", d / "FO4Port.esm")
        (d / "Starfield - Animations.ba2").write_bytes(general_archive({"Meshes\\AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx": b"<root/>"}))
        with self.assertRaises(SystemExit) as ctx:
            maf.stage(self.args(self.root / "staged-nograph", starfield_data=str(d)), converter=self.converter())
        self.assertIn("genericstategraph01.agx is not in the archives read", str(ctx.exception))
        self.assertIn("Starfield - Animations.ba2", str(ctx.exception))
        self.assertFalse((self.root / "staged-nograph").exists())

    def test_no_archive_matching_the_pattern_is_said(self):
        with self.assertRaises(SystemExit) as ctx:
            maf.stage(self.args(self.root / "staged-noarc", game_archive=["Nothing*.ba2"]), converter=self.converter())
        self.assertIn("no archive matched", str(ctx.exception))

    def test_a_state_map_with_an_idle_slot_a_repeat_or_nothing_is_refused_before_anything_is_done(self):
        for bad in ("Stage1=StateA_Idle", "Stage1=StateA_Play,Stage1=StateB_Play", "Stage1=Open", ""):
            with self.assertRaises(SystemExit) as ctx:
                maf.stage(self.args(self.root / "staged-bad", states=bad), converter=self.converter())
            self.assertIn("--states:", str(ctx.exception), bad)
        self.assertFalse((self.root / "staged-bad").exists())

    def test_a_failed_conversion_stops_before_anything_is_published(self):
        class Failing:
            def __init__(self, st):
                pass

            def convert_anim_object(self, *a, **k):
                return {"ok": False, "reason": "NifError: door has no moving geometry"}
        with self.assertRaises(SystemExit) as ctx:
            maf.stage(self.args(self.root / "staged-f"), converter=lambda a, st: (FakeSrc(nif.serialize(console_nif())), Failing(st)))
        self.assertIn("the console did not convert: NifError: door has no moving geometry", str(ctx.exception))
        self.assertFalse((self.root / "staged-f").exists())

    def test_the_kit_ships_no_textures_and_refuses_ones_the_port_lacks(self):
        with self.assertRaises(SystemExit) as ctx:
            maf.stage(self.args(self.root / "staged-t"), converter=self.converter(textures=["textures/fo4port/c_d.dds"]))
        self.assertIn("the port's archives do not hold", str(ctx.exception))
        self.assertFalse((self.root / "staged-t").exists())

    def test_a_changed_stage_or_starfield_esm_is_refused_by_verify(self):
        out = self.root / "staged-v"
        shutil.copytree(self.shared, out)
        plan = json.loads((out / "plan.json").read_text())
        (out / PLUGIN).write_bytes((out / PLUGIN).read_bytes() + b"!")
        self.assertIn("changed after the stage", " ".join(maf.verify_stage(str(out), plan)))
        self.assertIn("is not the four-state console kit's", " ".join(maf.verify_stage(str(out), dict(plan, kind="anim-console"))))
        shutil.copy(self.data / "Starfield.esm", self.root / "other.esm")
        d = self.root / "d3"
        d.mkdir()
        (d / "Starfield.esm").write_bytes(b"another game version")
        shutil.copytree(self.shared, self.root / "staged-v2")
        self.assertIn("Starfield.esm changed since the stage", " ".join(maf.verify_stage(str(self.root / "staged-v2"), plan, str(d))))

    def test_inspect_reads_the_staged_rig_tracks_and_predicted_poses_of_all_eight_clips(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mac.inspect_stage(type("A", (), {"stage": str(self.shared)})())
        out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        for slot in anim_object.slot_names(STATES, "chain"):
            self.assertIn(f"{slot} (", out)
        self.assertIn("inspect: ok", out)

    def test_log_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "log.txt")
            self.assertEqual(maf.main(["log", "--file", f]), 2)
            Path(f).write_text("[11/12/2026 - 06:00:00AM] FO4SFANIM rt=1.0 spawn stage=10 base=77 ref=99 moved=true turned=true persist=true end=true\n", encoding="utf-8")
            self.assertEqual(maf.main(["log", "--file", f]), 0)
            Path(f).write_text("nothing here\n", encoding="utf-8")
            self.assertEqual(maf.main(["log", "--file", f]), 1)

    def test_the_precheck_runs_on_this_script(self):
        z = self.root / "cr-pre.zip"
        fake_sources(z, BASES_D)
        out = self.root / "pre.json"
        self.assertEqual(maf.main(["precheck", "--content-resources", str(z), "--out", str(out)]), 0)
        r = json.loads(out.read_text())
        self.assertEqual(r["missing"], [])
        self.assertTrue(all(r["optional"].values()), r["optional"])


if __name__ == "__main__":
    unittest.main()
