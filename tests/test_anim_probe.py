"""The animation probe, variant A (vanilla control): its script's ids and stages against the writer's (dotnet/AnimProbe), the optional
and register-shape mechanisms, the precheck on fake base sources, the log reader on synthetic lines and the stage with a fake
Papyrus compiler (never a game; the real Papyrus compile and the real Starfield.esm are the PC's job). The dotnet tests skip
without the .NET SDK."""
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
import dotnet_fast  # noqa: E402,F401  (FAL-558: stager `dotnet run` calls use the built dll)
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_anim_probe as map_  # noqa: E402
from fo4sf import anim_probe_log as alog  # noqa: E402

PSC = (ROOT / "scripts" / "newgame" / "FO4SF_AnimProbeQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "AnimProbe" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFAnimProbe.esm"
TYPES = {"race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug", "utility", "int", "float",
         "string", "bool", "math", "location", "activator", "message", "armor", "weapon", "pad", "bench", "beacon", "ref"}


def const_ids(text):
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_stages_and_log_are_the_tools_and_the_readers(self):
        ids = const_ids(TOOL_SRC)
        self.assertEqual(ids["QuestId"], 0x800)
        self.assertEqual(ids["ActiId"], 0x1CCAC2)
        self.assertIn("int ActiId = 0x1CCAC2", PSC)                       # the vanilla control: IndIntAddonArtifactHolder01
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', PSC)
        self.assertTrue(PSC.startswith("Scriptname FO4SF_AnimProbeQuest extends Quest"))
        self.assertIn('Script = "FO4SF_AnimProbeQuest"', TOOL_SRC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 40, 60])
        self.assertIn(f"StageList = new int[{len(ran)}]", PSC)
        self.assertIn(f"DoneList = new bool[{len(ran)}]", PSC)
        self.assertIn('string LogName = "FO4SFAnim"', PSC)
        self.assertIn('"FO4SFANIM rt="', PSC)
        self.assertIn('" end=true"', PSC)
        for e in alog.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e}[ "]')

    def test_no_property_the_wait_form_is_never_called_and_the_master_is_starfield_only(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        self.assertNotRegex("\n".join(l.split(";")[0] for l in PSC.splitlines() if not l.startswith(" ")), r"PlayAnimationAndWait\(")
        self.assertIn("masters are not exactly [Starfield.esm]", TOOL_SRC)
        self.assertIn("the plugin carries a cell or an ACTI", TOOL_SRC)    # no REFR, no cell, no ACTI of ours

    def test_each_play_stage_sends_one_name_and_events_are_registered_from_the_activator(self):
        names = re.findall(r'PlayNames\[(\d)\] = "(\w+)"', PSC)
        self.assertEqual(len(names), 8)                                    # stages 21..28
        self.assertEqual(names[0], ("0", "Play01"))
        self.assertIn("PlayOne(stage, PlayNames[stage - 21])", PSC)
        self.assertEqual(PSC.count("TestRef.PlayAnimation(n)"), 1)
        self.assertIn("bool ok = TestRef.PlayAnimation(n)", PSC)
        self.assertIn("Event OnAnimationEvent(ObjectReference akSource, string asEventName)", PSC)
        events = re.findall(r'EventNames\[\d+\] = "(\w+)"', PSC)
        for want in ("Trans01", "Done", "StateA_Play", "StateB_Idle", "Play01", "TurnOn", "TransitionComplete", "AnimFinish", "EndAnim", "Stage4", "KlaxonStop"):
            self.assertIn(want, events)
        self.assertEqual(PSC.count("new string[22]"), 1)
        self.assertEqual(len(events), 22)
        self.assertIn("RegisterForAnimationEvent(r, n)", PSC)
        self.assertIn("p.PlaceAtMe(base, 1, true, false, false)", PSC)

    def test_the_committed_script_compiles_alone_every_optional_and_void_line_is_a_comment(self):
        self.assertEqual(map_.enable(PSC, []), PSC)
        self.assertEqual(map_.optional_names(PSC), ["ObjectReference.MoveTo", "ObjectReference.Delete"])
        self.assertEqual(len(map_.VOID.findall(PSC)), 2)
        self.assertIn(map_.BOOL_LINE, PSC)

    def test_no_local_variable_parameter_or_script_variable_is_named_like_a_type_or_a_base_script(self):
        decl = re.findall(r"^\s*(?:[A-Za-z:]+(?:\[\])?)\s+(\w+)\s*(?:=|$)", PSC, re.M)
        params = [p for m in re.findall(r"Function\s+\w+\(([^)]*)\)", PSC) for p in re.findall(r"\s(\w+)\s*(?:,|$)", " " + m)]
        self.assertEqual([n for n in decl + params if n.lower() in TYPES], [])

    def test_the_required_list_has_every_native_called_outside_an_optional_line(self):
        for base, names in {"Actor": ["PlaceAtMe"], "ObjectReference": ["PlayAnimation", "Activate", "Disable"],
                            "ScriptObject": ["RegisterForAnimationEvent", "StartTimer"], "Debug": ["TraceUser", "Notification"]}.items():
            for n in names:
                self.assertIn(n, map_.REQUIRED[base])


BASES = {
    "Form": "Scriptname Form\nint Function GetFormID() native\n",
    "ObjectReference": "Scriptname ObjectReference extends Form\nfloat Function GetPositionX() native\nfloat Function GetPositionY() native\n"
                       "float Function GetPositionZ() native\nfloat Function GetDistance(ObjectReference a) native\nCell Function GetParentCell() native\n"
                       "float Function GetAngleZ() native\nObjectReference Function PlaceAtMe(Form f, int n, bool a, bool b, bool c) native\n"
                       "bool Function PlayAnimation(string s) native\nbool Function Is3DLoaded() native\n"
                       "bool Function IsDisabled() native\nFunction Disable(bool f) native\nFunction Activate(ObjectReference a, bool d) native\n"
                       "Form Function GetBaseObject() native\nFunction MoveTo(ObjectReference a, float x, float y, float z, bool m) native\nFunction Delete() native\n",
    "Actor": "Scriptname Actor extends ObjectReference\n",
    "Game": "Scriptname Game\nActor Function GetPlayer() native global\nForm Function GetFormFromFile(int i, string p) native global\n"
            "bool Function IsPluginInstalled(string p) native global\n",
    "Debug": "Scriptname Debug\nbool Function OpenUserLog(string n) native global\nbool Function TraceUser(string n, string t) native global\n"
             "Function Notification(string s) native global\n",
    "Utility": "Scriptname Utility\nfloat Function GetCurrentRealTime() native global\n",
    "Math": "Scriptname Math\nfloat Function Sin(float f) native global\nfloat Function Cos(float f) native global\n",
    "ScriptObject": "Scriptname ScriptObject\nFunction StartTimer(float f, int i) native\n"
                    "bool Function RegisterForAnimationEvent(ObjectReference s, string e) native\n",
    "Quest": "Scriptname Quest extends ScriptObject\nbool Function GetStageDone(int i) native\n",
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

    def test_inherited_names_are_found_and_the_register_return_is_read(self):
        fake_sources(self.z)
        r = map_.precheck_sources(map_.read_sources(self.z), PSC)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["required"]["Actor.GetDistance"])                  # declared on ObjectReference
        self.assertEqual(r["optional"], {"ObjectReference.MoveTo": True, "ObjectReference.Delete": True})
        self.assertIs(r["register_returns_bool"], True)

    def test_a_missing_required_native_is_named(self):
        fake_sources(self.z)
        sources = map_.read_sources(self.z)
        sources["objectreference"] = sources["objectreference"].replace("PlayAnimation", "Other")
        self.assertEqual(map_.precheck_sources(sources, PSC)["missing"], ["ObjectReference.PlayAnimation"])

    def test_a_register_call_that_returns_nothing_changes_the_scripts_shape_only(self):
        bases = dict(BASES)
        bases["ScriptObject"] = bases["ScriptObject"].replace("bool Function RegisterForAnimationEvent", "Function RegisterForAnimationEvent")
        fake_sources(self.z, bases)
        sources = map_.read_sources(self.z)
        self.assertIs(map_.register_returns_bool(sources), False)
        self.assertEqual(map_.precheck_sources(sources, PSC)["missing"], [])
        shaped = map_.reg_shape(PSC, False)
        self.assertNotIn(map_.BOOL_LINE, shaped)
        self.assertIn('    RegisterForAnimationEvent(r, n)\n    return "void"\n', shaped)
        self.assertEqual(map_.reg_shape(PSC, True), PSC)
        self.assertEqual(map_.reg_shape(PSC, None), PSC)                      # an undeclared one is refused by the precheck, not here

    def test_a_declaration_with_another_return_type_is_not_bool(self):
        self.assertIs(map_.register_returns_bool({"x": "int Function RegisterForAnimationEvent(ObjectReference a, string b) native"}), False)
        self.assertIs(map_.register_returns_bool({"x": "Function Other() native"}), None)


FAKE_COMPILER = """#!{python}
import os, sys
name = sys.argv[1][:-4]
text = open(sys.argv[1], encoding="utf-8").read()
out = [a[3:] for a in sys.argv if a.startswith("-o=")][0]
if any("TestRef.Delete()" in l for l in text.splitlines() if not l.startswith(";")):
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
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "AnimProbe"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/AnimProbe/bin/Release/net9.0/AnimProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-anim-")
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
        self.assertIn("vanilla control: ACTI 1CCAC2 IndIntAddonArtifactHolder01", proc.stdout)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("QUST FO4SF_AnimProbeQuest flags StartGameEnabled stages [10,20,21,22,23,24,25,26,27,28,30,40,60] "
                      "scripts [FO4SF_AnimProbeQuest (0 properties)]", check.stdout)

    def test_the_plugin_adds_one_quest_and_overrides_none(self):
        """Raw bytes: every record carries load index 1 (our own plugin; Starfield.esm is master 0); no REFR, ACTI or CELL."""
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
        self.assertEqual([f for f in ids], [0x01000800])

    def test_a_master_without_the_control_activator_is_refused(self):
        other = self.root / "o"
        other.mkdir()
        shutil.copy(self.master, other / "Starfield.esm")
        raw = bytearray((other / "Starfield.esm").read_bytes())
        i = raw.find(b"ActivatorStateGraph01")
        self.assertGreater(i, 0)
        raw[i:i + len(b"ActivatorStateGraph01")] = b"SimpleOpenClose01xxxx"[:len(b"ActivatorStateGraph01")]      # same length: Mutagen aborts otherwise
        (other / "Starfield.esm").write_bytes(bytes(raw))
        proc = self.run_tool("build", other / "Starfield.esm", self.root / "b3")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("not activatorstategraph01", proc.stderr)

    def test_check_refuses_a_plugin_with_the_wrong_master(self):
        out = self.root / "b4"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        raw = bytearray((out / PLUGIN).read_bytes())
        i = raw.find(b"Starfield.esm")
        raw[i:i + 13] = b"Starfield.xxx"
        (out / PLUGIN).write_bytes(bytes(raw))
        self.assertNotEqual(self.run_tool("check", out / PLUGIN, self.master).returncode, 0)      # a master that is not Starfield.esm: refused or aborted

    def test_stage_with_a_fake_compiler_keeps_what_compiles_and_pins_every_file(self):
        z = self.root / "cr.zip"
        fake_sources(z)
        comp = fake_compiler(self.root)
        out = self.root / "staged"
        code = map_.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(comp), "--content-resources", str(z)])
        self.assertEqual(code, 0)
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual(plan["kind"], "anim-probe")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(plan["optional"]["ObjectReference.MoveTo"], "kept")
        self.assertTrue(plan["optional"]["ObjectReference.Delete"].startswith("declared but did not compile"))
        self.assertTrue(plan["register_returns_bool"])
        self.assertEqual(sorted(plan["outputs"]), sorted([PLUGIN, "Data/Scripts/FO4SF_AnimProbeQuest.pex"]))
        self.assertEqual(map_.verify_stage(str(out), plan), [])
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        staged_psc = (out / "FO4SF_AnimProbeQuest.psc").read_text()
        self.assertIn("        TestRef.MoveTo(p,", staged_psc)                                    # the kept optional line is live
        self.assertNotIn(";OPT ObjectReference.MoveTo", staged_psc)
        self.assertIn(";OPT ObjectReference.Delete", staged_psc)
        with self.assertRaises(SystemExit):                                      # an earlier stage is never overwritten
            map_.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(comp), "--content-resources", str(z)])

    def test_stage_with_a_void_register_keeps_the_void_lines(self):
        z = self.root / "cr2.zip"
        bases = dict(BASES)
        bases["ScriptObject"] = bases["ScriptObject"].replace("bool Function RegisterForAnimationEvent", "Function RegisterForAnimationEvent")
        fake_sources(z, bases)
        out = self.root / "staged2"
        self.assertEqual(map_.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(fake_compiler(self.root)),
                                    "--content-resources", str(z)]), 0)
        text = (out / "FO4SF_AnimProbeQuest.psc").read_text()
        self.assertNotIn(map_.BOOL_LINE, text)
        self.assertIn('    return "void"', text)
        self.assertFalse(json.loads((out / "plan.json").read_text())["register_returns_bool"])

    def test_a_changed_stage_is_refused_by_verify(self):
        z = self.root / "cr3.zip"
        fake_sources(z)
        out = self.root / "staged3"
        map_.main(["stage", "--out", str(out), "--starfield", str(self.master), "--compiler", str(fake_compiler(self.root)), "--content-resources", str(z)])
        plan = json.loads((out / "plan.json").read_text())
        with open(out / PLUGIN, "ab") as f:
            f.write(b"!")
        self.assertIn("changed after the stage", " ".join(map_.verify_stage(str(out), plan)))
        self.assertIn("is not the animation probe's", " ".join(map_.verify_stage(str(out), dict(plan, kind="workshop-probe"))))


class LogTests(unittest.TestCase):
    def lines(self, *rows):
        return [f"[11/12/2026 - 06:00:00AM] FO4SFANIM rt={i + 1}.0 {r} end=true" if not r.endswith("CUT") else
                f"[11/12/2026 - 06:00:00AM] FO4SFANIM rt={i + 1}.0 {r[:-3]}" for i, r in enumerate(rows)]

    def test_events_arrive(self):
        s = alog.summarize(self.lines(
            "init version=1 quest=5 installed=true acti=77 events=22 plays=8",
            "spawn stage=10 base=77 ref=99 moved=true persist=true",
            "register stage=10 name=Trans01 ref=99 ok=true",
            "register stage=10 name=Done ref=99 ok=false",
            "play stage=21 name=Play01 ref=99 ok=true",
            "event name=Trans01 src=99 stage=21 since=0.0",
            "event name=Done src=99 stage=21 since=2.5",
            "play stage=22 name=StateA_Play ref=99 ok=false",
            "quiet stage=22 seconds=15.0"))
        self.assertEqual(s["verdict"][0], "EVENTS ARRIVE")
        self.assertEqual([e["name"] for e in s["plays"][21]["events"]], ["Trans01", "Done"])
        self.assertTrue(s["plays"][22]["quiet"])
        text = "\n".join(alog.report(s))
        self.assertIn("register calls: 2 (false 1, true 1); not true: Done", text)
        self.assertIn("21     Play01            true    Trans01@0.0s, Done@2.5s", text)
        self.assertIn("22     StateA_Play       false   none (quiet 15 s)", text)

    def test_an_event_outside_the_play_window_does_not_make_events_arrive(self):
        """FAL-493 FINDING: a stage-0 event (registration, spawn) beside a true PlayAnimation whose own window is quiet."""
        s = alog.summarize(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true", "event name=StateA_Idle src=99 stage=0 since=0.0",
                                      "play stage=21 name=Play01 ref=99 ok=true", "quiet stage=21 seconds=15.0"))
        self.assertEqual(s["verdict"][0], "PLAY, NO EVENTS")
        self.assertIn("1 event(s) arrived outside them", s["verdict"][1])
        self.assertIn("events outside any play window (stage 0 or a stage with no play): StateA_Idle (stage 0)", "\n".join(alog.report(s)))
        # an event in a window whose call returned false is not counted either
        s = alog.summarize(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true", "play stage=21 name=Play01 ref=99 ok=false",
                                      "event name=Done src=99 stage=21 since=0.0", "listened stage=21 events=1 seconds=15.0"))
        self.assertEqual(s["verdict"][0], "NO PLAY")

    def test_a_quiet_line_beside_an_event_in_the_same_window_is_not_called_quiet(self):
        s = alog.summarize(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true", "play stage=21 name=Play01 ref=99 ok=true",
                                      "event name=Trans01 src=99 stage=21 since=0.0", "quiet stage=21 seconds=15.0"))
        self.assertEqual(s["verdict"][0], "EVENTS ARRIVE")
        self.assertFalse(s["plays"][21]["quiet"])
        self.assertIn("21     Play01            true    Trans01@0.0s", "\n".join(alog.report(s)))

    def test_each_event_carries_the_window_stage_and_a_window_counts_its_events(self):
        self.assertIn("int ListenStage = 0", PSC)
        self.assertIn('" stage=" + ListenStage', PSC)
        self.assertNotIn("CurrentStage", PSC)
        self.assertEqual(PSC.count("ListenStage = stage"), 2)                  # PlayOne and ActivateOnce open a window
        self.assertIn("WindowEvents = 0", PSC)
        self.assertIn('Trace("quiet stage=" + stage + " seconds=" + LISTEN_S)', PSC)
        self.assertIn('Trace("listened stage=" + stage + " events=" + WindowEvents', PSC)
        self.assertIn("if WindowEvents == 0", PSC)

    def test_every_finding_also_shows_on_screen_for_a_session_with_logging_off(self):
        """FAL-489, 12 Nov: variant A ran with script logging off; the screen is then the only readout."""
        self.assertIn('Debug.Notification("AP " + msg)', PSC)
        for what in ('Say("EV " + asEventName + " w" + ListenStage)', 'Say("PLAY s" + stage + " " + n + " ok=" + ok)',
                     'Say("W s" + stage + " quiet")', 'Say("W s" + stage + " heard " + WindowEvents)',
                     'Say("REG s" + stage + " " + okCount + "/" + EventNames.Length + " true")', 'Say("ACTIVATE s" + stage)'):
            self.assertIn(what, PSC)
        self.assertEqual(PSC.count("Say(\"EV "), 1)
        self.assertIn("Notification", map_.REQUIRED["Debug"])

    def test_play_true_and_no_events(self):
        s = alog.summarize(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true", "register stage=10 name=Trans01 ref=99 ok=true",
                                      "play stage=21 name=Play01 ref=99 ok=true", "quiet stage=21 seconds=15.0"))
        self.assertEqual(s["verdict"][0], "PLAY, NO EVENTS")
        self.assertIn("1 of 1 register call(s) returned true", s["verdict"][1])

    def test_no_play_and_inconclusive_and_the_void_register(self):
        s = alog.summarize(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true", "register stage=10 name=Trans01 ref=99 ok=void",
                                      "play stage=21 name=Play01 ref=99 ok=false"))
        self.assertEqual(s["verdict"][0], "NO PLAY")
        self.assertEqual(s["registers"][0]["ok"], "void")
        s = alog.summarize(self.lines("init version=1 quest=5 installed=true acti=none events=22 plays=8", "spawn stage=10 base=none ref=none"))
        self.assertEqual(s["verdict"][0], "INCONCLUSIVE")
        self.assertEqual(alog.summarize([])["verdict"][0], "INCONCLUSIVE")

    def test_a_cut_line_is_left_out_and_counted_and_other_lines_are_ignored(self):
        s = alog.summarize(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true", "play stage=21 name=Play01 ref=99 ok=trueCUT") + ["something else"])
        self.assertEqual(s["cut"], 1)
        self.assertEqual(s["verdict"][0], "NO PLAY")
        self.assertIn("1 line(s) without end=true were cut", "\n".join(alog.report(s)))

    def test_activate_by_script_is_a_row_and_events_outside_a_play_stage_are_listed(self):
        s = alog.summarize(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true", "step stage=30 call=Activate ref=99",
                                      "event name=Done src=99 stage=30 since=1.0", "event name=Reset src=99 stage=50 since=3.0"))
        self.assertIn("30     Activate(player)", "\n".join(alog.report(s)))
        self.assertIn("events outside any play window (stage 0 or a stage with no play): Reset (stage 50)", "\n".join(alog.report(s)))

    def test_log_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "log.txt")
            self.assertEqual(map_.main(["log", "--file", f]), 2)
            Path(f).write_text("\n".join(self.lines("spawn stage=10 base=77 ref=99 moved=true persist=true")), encoding="utf-8")
            self.assertEqual(map_.main(["log", "--file", f]), 0)
            Path(f).write_text("nothing here\n", encoding="utf-8")
            self.assertEqual(map_.main(["log", "--file", f]), 1)


if __name__ == "__main__":
    unittest.main()
