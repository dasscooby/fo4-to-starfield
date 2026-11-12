"""The player-furniture control kit, variant P (FAL-518): its script's ids, stages and guards against the writer's (dotnet/PlayerFurn), the
optional and register-shape mechanisms, the precheck on fake base sources and the stage with a fake Papyrus compiler (never a game; the
real Papyrus compile and the real Starfield.esm are the PC's job). The dotnet tests skip without the .NET SDK."""
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
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_player_furn as mpf  # noqa: E402

PSC = (ROOT / "scripts" / "newgame" / "FO4SF_PlayerFurnQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "PlayerFurn" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFPlayerFurn.esm"
# the code: everything after the header doc block (the doc names what the kit must not do)
CODE = PSC[PSC.index("; ----------------------------------------------------------------"):]
TYPES = {"race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug", "utility", "int", "float",
         "string", "bool", "math", "location", "activator", "message", "armor", "weapon", "pad", "bench", "beacon", "ref",
         "inputenablelayer", "layer"}
FURN = [(0x03607F, "PowerCycle"), (0x0FEBB0, "COM_Quest_Andreja_Q01_SecretPanel"), (0x00A329, "NPCIDCardReader"),
        (0x24E491, "Scenes_MQ101_HellerTechReaderPickUp")]


def body(name):
    """The text of one Function of the script (up to its EndFunction)."""
    m = re.search(rf"^Function {name}\(.*?^EndFunction", PSC, re.M | re.S)
    assert m, name
    return m.group(0)


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_stages_and_log_are_the_tools(self):
        self.assertTrue(PSC.startswith("Scriptname FO4SF_PlayerFurnQuest extends Quest"))
        self.assertIn('Script = "FO4SF_PlayerFurnQuest"', TOOL_SRC)
        self.assertIn('string ProbePlugin = "FO4SFPlayerFurn.esm"', PSC)
        self.assertIn("const uint QuestId = 0x800", TOOL_SRC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 11, 12, 13, 20, 21, 22, 23, 40, 60])
        self.assertIn(f"StageList = new int[{len(ran)}]", PSC)
        self.assertIn(f"DoneList = new bool[{len(ran)}]", PSC)
        self.assertIn('string LogName = "FO4SFPFurn"', PSC)
        self.assertIn('"FO4SFPFURN rt="', PSC)
        self.assertIn('" end=true"', PSC)

    def test_the_four_vanilla_furniture_are_the_designs_and_the_scripts_match_the_tool(self):
        """vault111-player-furniture rev 6: PowerCycle first, then the secret panel, the ID reader, the Heller reader."""
        ids = [(int(i, 16), n) for i, n in re.findall(r"\(0x([0-9A-Fa-f]{6}), \"(\w+)\"\)", TOOL_SRC)]
        self.assertEqual(ids, FURN)
        script_ids = [int(x, 16) for x in re.findall(r"FurnIds\[\d\] = 0x([0-9A-Fa-f]{6})", PSC)]
        self.assertEqual(script_ids, [i for i, _ in FURN])
        names = re.findall(r'FurnNames\[\d\] = "(\w+)"', PSC)
        self.assertEqual(names, ["PowerCycle", "SecretPanel", "IDCardReader", "HellerTechReader"])
        self.assertIn('Game.GetFormFromFile(FurnIds[idx], "Starfield.esm")', PSC)
        self.assertIn("p.PlaceAtMe(base, 1, true, false, false)", PSC)
        self.assertIn("Spawn(stage, stage - 10)", PSC)
        self.assertIn("UseFurniture(stage, stage - 20)", PSC)

    def test_no_property_no_animation_call_and_none_of_the_things_the_design_forbids(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        for banned in ("PlayAnimation", "PlayIdle", "SnapIntoInteraction", "PlayerPathToFurniture", "FurnitureForce1stPerson", "FO4Port",
                       "AndWait", "SetValue", "AddKeyword", "SaveGame", "RequestSave"):
            self.assertNotIn(banned, CODE, banned)
        self.assertIn("masters are not exactly [Starfield.esm]", TOOL_SRC)
        self.assertIn("the plugin carries a cell or a FURN", TOOL_SRC)    # no REFR, no cell, no FURN of ours

    def test_the_guard_timer_starts_before_the_layer_and_the_layer_before_activate(self):
        use = body("UseFurniture")
        guard = use.index("StartTimer(GUARD_S, TIMER_SAFETY + idx)")
        create = use.index("InputEnableLayer.Create()")
        disable = use.index("Hold.DisablePlayerControls()")
        activate = use.index("r.Activate(p, false)")
        self.assertLess(guard, create)
        self.assertLess(create, disable)
        self.assertLess(disable, activate)
        self.assertEqual(CODE.count("DisablePlayerControls()"), 1)             # one place that locks the player
        self.assertIn("float GUARD_S = 15.0", PSC)
        self.assertEqual(CODE.count(".Activate("), 2)                          # the use and the one exit activate, nothing else

    def test_the_layer_is_released_by_the_timer_the_end_events_and_stage_60(self):
        rel = body("ReleaseHold")
        self.assertIn("Hold.EnablePlayerControls()", rel)
        self.assertIn("Hold.Delete()", rel)                                   # the layer is deleted, not only enabled
        self.assertIn("Hold = None", rel)
        self.assertIn("if Hold != None", rel)                                 # safe to repeat
        self.assertIn('ReleaseHold("timer")', body("Guard"))
        self.assertIn('ReleaseHold("stage60")', body("Cleanup"))
        self.assertIn("ReleaseHold(why)", body("EndUse"))
        self.assertIn('EndUse("getup")', PSC)                                 # Actor.OnGetUp
        self.assertIn('EndUse("exit")', PSC)                                  # ObjectReference.OnExitFurniture
        # the timer releases BEFORE it tries to leave the furniture
        g = body("Guard")
        self.assertLess(g.index('ReleaseHold("timer")'), g.index("FurnRef.Activate(p, false)"))

    def test_the_exit_activate_only_when_the_sit_state_is_not_zero_and_the_recheck_disables(self):
        g = body("Guard")
        self.assertIn("int s = p.GetSitState()", g)
        self.assertIn("if s != 0 && FurnRef != None", g)
        self.assertIn('Say("EXIT ACTIVATE sit=" + s)', g)
        self.assertIn("StartTimer(RECHECK_S, TIMER_RECHECK + idx)", g)
        r = body("Recheck")
        self.assertIn("if s != 0 && FurnRef != None", r)
        self.assertIn("FurnRef.Disable(false)", r)
        self.assertNotIn(".Activate(", r)                                     # the second try is one Activate, not a loop
        self.assertEqual(len(re.findall(r"TIMER_(SAFETY|SIT|RECHECK) = (\d+)", PSC)), 3)
        for hi, lo in (("TIMER_RECHECK", "TIMER_SIT"), ("TIMER_SIT", "TIMER_SAFETY")):       # the dispatcher tests the largest first
            self.assertLess(PSC.index("aiTimerID >= " + hi), PSC.index("aiTimerID >= " + lo))
        self.assertIn("SIT_TICKS = 30", PSC)                                   # 30 x 0.5 s
        self.assertIn("float SIT_S = 0.5", PSC)

    def test_stage_60_disables_and_deletes_every_spawned_reference(self):
        c = body("Cleanup")
        self.assertIn("while i < Spawned.Length", c)
        self.assertIn("Spawned[i].Disable(false)", c)
        self.assertIn(";OPT ObjectReference.Delete             Spawned[i].Delete()", c)
        self.assertIn("Spawned[i] = None", c)

    def test_every_event_and_the_player_animation_names_are_logged_with_a_time(self):
        for e in ("OnGetUp", "OnSit", "OnEnterFurniture", "OnExitFurniture"):
            self.assertRegex(PSC, rf'Trace\("event name={e} ')
        self.assertEqual(len(re.findall(r'" t=" \+ SinceUse\(\)', PSC)) >= 8, True)
        names = re.findall(r'AnimNames\[\d+\] = "(\w+)"', PSC)
        self.assertEqual(names[:3], ["IdleChairSitting", "AnimationComplete", "IdleStop"])
        self.assertEqual(len(names), 10)
        self.assertIn("AnimNames = new string[10]", PSC)
        self.assertIn('RegisterForRemoteEvent(p, "OnGetUp")', PSC)
        self.assertIn('RegisterForRemoteEvent(r, "OnExitFurniture")', PSC)
        self.assertIn('Trace("register name=" + AnimNames[i] + " ref=player ok=" + res)', PSC)     # each registration's bool
        self.assertIn('Trace("sit use=" + idx + " n=" + SitTicks + " state=" + s', PSC)           # GetSitState every 0.5 s

    def test_the_spawn_is_ahead_at_the_players_height_upright_and_never_at_the_feet(self):
        s = body("Spawn")
        self.assertIn("r.MoveTo(p, AheadM * Math.Sin(a), AheadM * Math.Cos(a), 0.0, false)", s)
        self.assertIn("r.SetAngle(0.0, 0.0, p.GetAngleZ() + 180.0)", s)       # pitch and roll 0: upright
        self.assertIn("float AheadM = 2.5", PSC)
        self.assertIn('" 3D=" + r.Is3DLoaded() + " D=" + p.GetDistance(r)', s)  # the notice: 3D loaded, distance

    def test_every_finding_also_shows_on_screen_for_a_session_with_logging_off(self):
        self.assertIn('Debug.Notification("PF " + msg)', PSC)
        self.assertIn("Notification", mpf.REQUIRED["Debug"])
        for what in ('Say("GETUP t="', 'Say("SIT t="', 'Say("ENTER t="', 'Say("EXIT t="', 'Say("EV "', 'Say("SIT STATE "', 'Say("ACTIVATE s" + stage)',
                     'Say("EXIT ACTIVATE', 'Say("SAFE sit="', 'Say("STILL IN', 'Say("HOLD OFF "', 'Say("CLEAN")', 'Say("REG "'):
            self.assertIn(what, PSC)

    def test_the_committed_script_compiles_alone_every_optional_and_void_line_is_a_comment(self):
        self.assertEqual(mpf.enable(PSC, []), PSC)
        self.assertEqual(mpf.optional_names(PSC), ["Actor.OnGetUp", "Actor.OnSit", "ObjectReference.OnEnterFurniture",
                                                   "ObjectReference.OnExitFurniture", "ObjectReference.MoveTo", "ObjectReference.SetAngle",
                                                   "ObjectReference.GetScale", "ObjectReference.SetScale", "ObjectReference.Delete"])
        self.assertEqual(len(mpf.VOID.findall(PSC)), 2)
        self.assertIn(mpf.BOOL_LINE, PSC)

    def test_no_local_variable_parameter_or_script_variable_is_named_like_a_type_or_a_base_script(self):
        decl = re.findall(r"^\s*(?:[A-Za-z:]+(?:\[\])?)\s+(\w+)\s*(?:=|$)", PSC, re.M)
        params = [p for m in re.findall(r"(?:Function|Event)\s+[\w.]+\(([^)]*)\)", PSC) for p in re.findall(r"\s(\w+)\s*(?:,|$)", " " + m)]
        self.assertEqual([n for n in decl + params if n.lower() in TYPES], [])

    def test_the_required_list_has_every_native_called_outside_an_optional_line(self):
        for base, names in {"Actor": ["PlaceAtMe", "GetSitState"], "ObjectReference": ["Activate", "Disable"],
                            "ScriptObject": ["RegisterForAnimationEvent", "RegisterForRemoteEvent", "StartTimer"],
                            "Debug": ["TraceUser", "Notification"],
                            "InputEnableLayer": ["Create", "DisablePlayerControls", "EnablePlayerControls", "Delete"]}.items():
            for n in names:
                self.assertIn(n, mpf.REQUIRED[base])


BASES = {
    "Form": "Scriptname Form\nint Function GetFormID() native\n",
    "ObjectReference": "Scriptname ObjectReference extends Form\nfloat Function GetPositionX() native\nfloat Function GetPositionY() native\n"
                       "float Function GetPositionZ() native\nfloat Function GetDistance(ObjectReference a) native\nfloat Function GetAngleZ() native\n"
                       "ObjectReference Function PlaceAtMe(Form f, int n, bool a, bool b, bool c) native\nbool Function Is3DLoaded() native\n"
                       "bool Function IsDisabled() native\nFunction Disable(bool f) native\nFunction Activate(ObjectReference a, bool d) native\n"
                       "Form Function GetBaseObject() native\nFunction MoveTo(ObjectReference a, float x, float y, float z, bool m) native\n"
                       "Function SetAngle(float x, float y, float z) native\nFunction Delete() native\nfloat Function GetScale() native\n"
                       "Function SetScale(float f) native\nEvent OnEnterFurniture(ObjectReference a)\nEndEvent\nEvent OnExitFurniture(ObjectReference a)\nEndEvent\n",
    "Actor": "Scriptname Actor extends ObjectReference\nint Function GetSitState() native\nEvent OnGetUp(ObjectReference f)\nEndEvent\n"
             "Event OnSit(ObjectReference f)\nEndEvent\n",
    "Game": "Scriptname Game\nActor Function GetPlayer() native global\nForm Function GetFormFromFile(int i, string p) native global\n"
            "bool Function IsPluginInstalled(string p) native global\n",
    "Debug": "Scriptname Debug\nbool Function OpenUserLog(string n) native global\nbool Function TraceUser(string n, string t) native global\n"
             "Function Notification(string s) native global\n",
    "Utility": "Scriptname Utility\nfloat Function GetCurrentRealTime() native global\n",
    "Math": "Scriptname Math\nfloat Function Sin(float f) native global\nfloat Function Cos(float f) native global\n",
    "ScriptObject": "Scriptname ScriptObject\nFunction StartTimer(float f, int i) native\n"
                    "bool Function RegisterForAnimationEvent(ObjectReference s, string e) native\n"
                    "Function RegisterForRemoteEvent(ScriptObject s, string e) native\n",
    "Quest": "Scriptname Quest extends ScriptObject\nbool Function GetStageDone(int i) native\n",
    "InputEnableLayer": "Scriptname InputEnableLayer extends ScriptObject\nInputEnableLayer Function Create() native global\n"
                        "Function DisablePlayerControls() native\nFunction EnablePlayerControls() native\nFunction Delete() native\n",
}


def fake_sources(zip_path, bases=None):
    with zipfile.ZipFile(zip_path, "w") as z:
        for name, text in (bases or BASES).items():
            z.writestr(f"Scripts/Source/{name}.psc", text)
        z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "Flags")


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.z = os.path.join(self.tmp.name, "cr.zip")

    def test_inherited_names_and_the_event_handlers_are_found_and_the_register_return_is_read(self):
        fake_sources(self.z)
        r = mpf.precheck_sources(mpf.read_sources(self.z), PSC)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["required"]["Actor.GetDistance"])                  # declared on ObjectReference
        self.assertEqual(r["optional"], {n: True for n in mpf.optional_names(PSC)})
        self.assertIs(r["register_returns_bool"], True)

    def test_a_missing_required_native_is_named_the_sit_state_guard_needs_its_call(self):
        fake_sources(self.z)
        sources = mpf.read_sources(self.z)
        sources["actor"] = sources["actor"].replace("GetSitState", "Other")
        self.assertEqual(mpf.precheck_sources(sources, PSC)["missing"], ["Actor.GetSitState"])
        sources = mpf.read_sources(self.z)
        sources["inputenablelayer"] = sources["inputenablelayer"].replace("Create", "Make")
        self.assertEqual(mpf.precheck_sources(sources, PSC)["missing"], ["InputEnableLayer.Create"])

    def test_a_missing_event_is_an_optional_line_not_a_stop(self):
        sources = {k.lower(): v for k, v in BASES.items()}
        sources["actor"] = sources["actor"].replace("OnGetUp", "OnOther")
        r = mpf.precheck_sources(sources, PSC)
        self.assertEqual(r["missing"], [])
        self.assertFalse(r["optional"]["Actor.OnGetUp"])
        self.assertTrue(r["optional"]["Actor.OnSit"])

    def test_a_register_call_that_returns_nothing_changes_the_scripts_shape_only(self):
        bases = dict(BASES)
        bases["ScriptObject"] = bases["ScriptObject"].replace("bool Function RegisterForAnimationEvent", "Function RegisterForAnimationEvent")
        fake_sources(self.z, bases)
        sources = mpf.read_sources(self.z)
        self.assertIs(mpf.register_returns_bool(sources), False)
        self.assertEqual(mpf.precheck_sources(sources, PSC)["missing"], [])
        shaped = mpf.reg_shape(PSC, False)
        self.assertNotIn(mpf.BOOL_LINE, shaped)
        self.assertIn('    RegisterForAnimationEvent(r, n)\n    return "void"\n', shaped)
        self.assertEqual(mpf.reg_shape(PSC, True), PSC)


FAKE_COMPILER = """#!{python}
import os, sys
name = sys.argv[1][:-4]
text = open(sys.argv[1], encoding="utf-8").read()
out = [a[3:] for a in sys.argv if a.startswith("-o=")][0]
if any("Spawned[i].Delete()" in l for l in text.splitlines() if not l.startswith(";")):
    print("%s.psc(1,1): error: Delete does not match the fake compiler" % name)
    sys.exit(1)
if any("Event Actor.OnSit" in l for l in text.splitlines() if not l.startswith(";")):
    print("%s.psc(2,1): error: the OnSit handler does not match the fake compiler" % name)
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
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "PlayerFurn"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/PlayerFurn/bin/Release/net9.0/PlayerFurn.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-pfurn-")
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
        for i, n in FURN:
            self.assertIn(f"vanilla furniture: FURN {i:06X} {n}", proc.stdout)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("QUST FO4SF_PlayerFurnQuest flags StartGameEnabled stages [10,11,12,13,20,21,22,23,40,60] "
                      "scripts [FO4SF_PlayerFurnQuest (0 properties)]", check.stdout)

    def test_the_plugin_adds_one_quest_and_overrides_none(self):
        """Raw bytes: every record carries load index 1 (our own plugin; Starfield.esm is master 0); no REFR, FURN or CELL."""
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
        self.assertEqual({k: v for k, v in kinds.items() if k != b"TES4"}, {b"QUST": 1})
        self.assertEqual(ids, [0x01000800])

    def test_a_master_without_one_of_the_furniture_or_with_another_editor_id_is_refused(self):
        other = self.root / "o"
        other.mkdir()
        shutil.copy(self.master, other / "Starfield.esm")
        raw = bytearray((other / "Starfield.esm").read_bytes())
        i = raw.find(b"NPCIDCardReader")
        self.assertGreater(i, 0)
        raw[i:i + 15] = b"NPCIDCardReadeX"                                    # same length: Mutagen aborts otherwise
        (other / "Starfield.esm").write_bytes(bytes(raw))
        proc = self.run_tool("build", other / "Starfield.esm", self.root / "b3")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("is NPCIDCardReadeX, not NPCIDCardReader", proc.stderr)

    def test_check_refuses_a_plugin_with_the_wrong_master(self):
        out = self.root / "b4"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        raw = bytearray((out / PLUGIN).read_bytes())
        i = raw.find(b"Starfield.esm")
        raw[i:i + 13] = b"Starfield.xxx"
        (out / PLUGIN).write_bytes(bytes(raw))
        self.assertNotEqual(self.run_tool("check", out / PLUGIN, self.master).returncode, 0)

    def test_stage_with_a_fake_compiler_keeps_what_compiles_and_pins_every_file(self):
        z = self.root / "cr.zip"
        fake_sources(z)
        comp = fake_compiler(self.root)
        out = self.root / "staged"
        code = mpf.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(comp), "--content-resources", str(z)])
        self.assertEqual(code, 0)
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual(plan["kind"], "player-furn-probe")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(plan["optional"]["ObjectReference.MoveTo"], "kept")
        self.assertEqual(plan["optional"]["ObjectReference.OnExitFurniture"], "kept")
        self.assertTrue(plan["optional"]["ObjectReference.Delete"].startswith("declared but did not compile"))
        self.assertTrue(plan["optional"]["Actor.OnSit"].startswith("declared but did not compile"))
        self.assertTrue(plan["register_returns_bool"])
        self.assertEqual(sorted(plan["outputs"]), sorted([PLUGIN, "Data/Scripts/FO4SF_PlayerFurnQuest.pex"]))
        self.assertEqual(mpf.verify_stage(str(out), plan), [])
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        staged = (out / "FO4SF_PlayerFurnQuest.psc").read_text()
        self.assertIn("        r.MoveTo(p,", staged)                                       # the kept optional line is live
        self.assertIn("Event ObjectReference.OnExitFurniture(", staged.replace(";OPT ObjectReference.OnExitFurniture ", ""))
        self.assertNotIn(";OPT ObjectReference.MoveTo", staged)
        self.assertIn(";OPT ObjectReference.Delete", staged)
        self.assertIn(";OPT Actor.OnSit", staged)
        self.assertIn("player_furn_install.py", (out / "README.txt").read_text())
        with self.assertRaises(SystemExit):                                              # an earlier stage is never overwritten
            mpf.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(comp), "--content-resources", str(z)])

    def test_stage_with_a_void_register_keeps_the_void_lines(self):
        z = self.root / "cr2.zip"
        bases = dict(BASES)
        bases["ScriptObject"] = bases["ScriptObject"].replace("bool Function RegisterForAnimationEvent", "Function RegisterForAnimationEvent")
        fake_sources(z, bases)
        out = self.root / "staged2"
        self.assertEqual(mpf.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(fake_compiler(self.root)),
                                   "--content-resources", str(z)]), 0)
        text = (out / "FO4SF_PlayerFurnQuest.psc").read_text()
        self.assertNotIn(mpf.BOOL_LINE, text)
        self.assertIn('    return "void"', text)
        self.assertFalse(json.loads((out / "plan.json").read_text())["register_returns_bool"])

    def test_a_missing_required_native_stops_the_stage(self):
        z = self.root / "cr4.zip"
        bases = dict(BASES)
        bases["Actor"] = bases["Actor"].replace("GetSitState", "Other")
        fake_sources(z, bases)
        with self.assertRaises(SystemExit) as e:
            mpf.main(["stage", "--out", str(self.root / "staged4"), "--starfield", str(self.master), "--compiler", str(fake_compiler(self.root)),
                      "--content-resources", str(z)])
        self.assertIn("Actor.GetSitState", str(e.exception))
        self.assertFalse((self.root / "staged4").exists())

    def test_a_changed_stage_is_refused_by_verify(self):
        z = self.root / "cr3.zip"
        fake_sources(z)
        out = self.root / "staged3"
        mpf.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(fake_compiler(self.root)), "--content-resources", str(z)])
        plan = json.loads((out / "plan.json").read_text())
        with open(out / PLUGIN, "ab") as f:
            f.write(b"!")
        self.assertIn("changed after the stage", " ".join(mpf.verify_stage(str(out), plan)))
        self.assertIn("is not the player-furniture kit's", " ".join(mpf.verify_stage(str(out), dict(plan, kind="anim-probe"))))


class CardTests(unittest.TestCase):
    CARD = (ROOT / "docs" / "research" / "player-furniture-kit.md").read_text(encoding="utf-8")

    def test_the_card_says_not_run_and_names_every_stage_and_outcome(self):
        self.assertIn("NOT_RUN", self.CARD)
        self.assertIn("not compiled", self.CARD.lower())
        for s in (10, 11, 12, 13, 20, 21, 22, 23, 40, 60):
            self.assertRegex(self.CARD, rf"(\| | / ){s}( / | \|)")
        for what in ("but **no** end event", "**no pose**", "camera", "enableplayercontrols", "no saving"):
            self.assertIn(what, self.CARD.lower())
        for i, n in FURN:
            self.assertIn(f"`{i:06X}`", self.CARD)
            self.assertIn(n, self.CARD)


if __name__ == "__main__":
    unittest.main()
