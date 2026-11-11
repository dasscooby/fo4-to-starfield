"""The power armor probe's writer (dotnet/PowerArmorProbe) on a synthetic Starfield.esm, its script's ids against the
tool's, the optional-reading mechanism and the stage with a fake Papyrus compiler and fake base sources (never a game;
the real Papyrus compile and the real Starfield.esm are the PC's job). The dotnet tests skip without the .NET SDK."""
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
import make_power_armor_probe as mpa  # noqa: E402

PSC = (ROOT / "scripts" / "planet" / "FO4SF_PAProbeQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "PowerArmorProbe" / "Program.cs").read_text(encoding="utf-8")
HAND_PSC = (ROOT / "scripts" / "planet" / "FO4SF_PAHandQuest.psc").read_text(encoding="utf-8")
ENTRY_PSC = (ROOT / "scripts" / "planet" / "FO4SF_PAEntryQuest.psc").read_text(encoding="utf-8")
PLUGIN = "FO4SFPowerArmorProbe.esm"


def const_ids(text):
    """{name: id} of the `const uint A = 0x.., B = 0x..` lines of the tool."""
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


class HandScriptTests(unittest.TestCase):
    """The by-hand mode (FAL-273): a second quest of the same plugin that shows the engine's answers on screen."""

    def test_the_hand_scripts_ids_are_the_tools(self):
        ids = const_ids(TOOL_SRC)
        for name in ("CellId", "SuitRefId", "ControlRefId", "ArrivalRefId"):
            m = re.search(rf"^int {name} = (0x[0-9A-Fa-f]+)", HAND_PSC, re.M)
            self.assertIsNotNone(m, name)
            self.assertEqual(int(m.group(1), 16), ids[name], name)
        self.assertEqual(ids["HandQuestId"], 0x807)
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', HAND_PSC)
        self.assertIn('HandScript = "FO4SF_PAHandQuest"', TOOL_SRC)
        self.assertTrue(HAND_PSC.startswith("Scriptname FO4SF_PAHandQuest extends Quest"))

    def test_the_hand_script_has_no_properties_and_no_stages(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", HAND_PSC, re.M | re.I))
        self.assertNotIn(" Property ", HAND_PSC)
        self.assertNotIn("GetStageDone", HAND_PSC)

    def test_the_question_is_asked_and_the_answers_are_on_screen(self):
        self.assertEqual(HAND_PSC.count("p.SwitchToPowerArmor(suit)"), 2)       # near the suit, or 60 s in the room
        self.assertNotIn("p.SetRace(", HAND_PSC)                               # the race swap stays with the console probe
        self.assertIn("Debug.Notification(msg)", HAND_PSC)
        for reading in ("InPowerArmor(p)", "FurnId(p)", "SitState(p)", "Camera()", "WornCount(p)"):
            self.assertIn(reading, HAND_PSC.split("Function Wording")[1])
        self.assertIn("not in this game's scripts", HAND_PSC)                  # an unavailable reading is said in words
        self.assertIn("1 s after the call", HAND_PSC)
        self.assertIn("4 s after the call", HAND_PSC)

    def test_without_a_move_call_the_screen_gives_the_one_console_line(self):
        self.assertIn("coc FO4SF_PAProbeCell", HAND_PSC.split("Function Poll")[1])
        self.assertEqual(mpa.optional_names(HAND_PSC), ["Actor.GetFurnitureReference", "Actor.GetSitState", "Actor.IsInPowerArmor",
                                                        "Game.GetCameraState", "Actor.GetWornItem", "ObjectReference.MoveTo"])
        self.assertEqual(mpa.enable(HAND_PSC, []), HAND_PSC)

    def test_no_local_variable_or_parameter_is_named_like_a_type(self):
        """The PC's compile (FAL-273): 'variable race cannot have the same name as a known type or script'. Papyrus names are
        case-blind, so a local called race, cell, form, actor... is refused. The fixture compile cannot see this."""
        types = {"race", "cell", "form", "actor", "quest", "furniture", "keyword", "spell", "game", "debug", "utility", "int", "float", "string", "bool"}
        for text in (HAND_PSC, PSC, ENTRY_PSC):
            decl = re.findall(r"^\s*(?:[A-Za-z:]+(?:\[\])?)\s+(\w+)\s*(?:=|$)", text, re.M)
            params = [p for m in re.findall(r"Function\s+\w+\(([^)]*)\)", text) for p in re.findall(r"\s(\w+)\s*(?:,|$)", " " + m)]
            self.assertEqual([n for n in decl + params if n.lower() in types], [])

    def test_a_compile_failure_prints_the_compilers_own_lines(self):
        import subprocess
        from unittest import mock
        out = "FO4SF_PAHandQuest.psc(149,11): variable race cannot have the same name as a known type or script\nFO4SF_PAHandQuest.psc(158,190): race is not a variable\n"
        with mock.patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1, stdout=out, stderr="")):
            ok, err = mpa.compile_text("x", "text", ".", self.__class__.__name__ and tempfile.gettempdir(), "FO4SF_PAHandQuest")
        self.assertFalse(ok)
        self.assertIn("(149,11): variable race cannot have the same name", err)
        self.assertIn("(158,190): race is not a variable", err)

    def test_the_owner_is_told_whether_anything_changed_and_when_he_sits(self):
        """FAL-273 after the #708 PC run: the call did nothing on a keyword-only furniture and GetFurnitureReference is not in
        Starfield's scripts (furn=NA), so the screen says the verdict itself and reads the sit state."""
        self.assertEqual(HAND_PSC.count("BeforeKey = StateKey(p)"), 2)             # taken before either call
        self.assertIn("if StateKey(p) == BeforeKey", HAND_PSC)
        self.assertIn("nothing changed. SwitchToPowerArmor does nothing on a chair with only the power armor keyword", HAND_PSC)
        self.assertLess(HAND_PSC.index('Say(Wording("4 s after the call"))'), HAND_PSC.index("        Verdict()"))
        self.assertIn('if sitText == "3"', HAND_PSC)                                # seated on the control without the furniture call
        self.assertNotIn("string race ", HAND_PSC)

    def test_the_arrival_the_script_moves_to_is_persistent_and_the_60_s_call_waits_for_standing(self):
        """FAL-316 findings: MoveTo needs a reference that resolves while the room is not loaded; the timed call must not use the
        one trial while the player sits on the control chair."""
        self.assertIn("ObjectReference coc = Ref(ArrivalRefId)", HAND_PSC)
        self.assertNotIn("Ref(CocRefId)", HAND_PSC)                                # the temporary COC marker is not the target
        self.assertIn('elseif InRoom >= RoomLimit && (sitText == "0" || sitText == "na")', HAND_PSC)
        self.assertEqual(const_ids(TOOL_SRC)["ArrivalRefId"], 0x808)

    def test_the_hand_log_lines_end(self):
        self.assertIn('"FO4SFPAHAND rt="', HAND_PSC)
        self.assertIn('" end=true"', HAND_PSC)
        self.assertIn('string LogName = "FO4SFPAHand"', HAND_PSC)

    def test_the_required_list_has_the_notification(self):
        self.assertIn("Notification", mpa.REQUIRED["Debug"])


class EntryScriptTests(unittest.TestCase):
    """The power armor entry by script (FAL-361, piece B of FAL-359): quest FO4SF_PAEntryQuest, its kit records."""

    def test_the_entry_scripts_ids_are_the_tools(self):
        ids = const_ids(TOOL_SRC)
        for psc_name, tool_name in (("CellId", "CellId"), ("KitRaceId", "RaceId"), ("ControlRefId", "ControlRefId"),
                                    ("ArrivalRefId", "ArrivalRefId"), ("EntryRefId", "EntryRefId"), ("InPaId", "InPaId"),
                                    ("FrameId", "FrameId"), ("PieceHelmId", "PieceHelmId"), ("PieceTorsoId", "PieceTorsoId")):
            m = re.search(rf"^int {psc_name} = (0x[0-9A-Fa-f]+)", ENTRY_PSC, re.M)
            self.assertIsNotNone(m, psc_name)
            self.assertEqual(int(m.group(1), 16), ids[tool_name], psc_name)
        self.assertEqual(ids["EntryQuestId"], 0x809)
        own = {k: v for k, v in ids.items() if 0x800 <= v < 0x1000}                    # ours; the others are Starfield.esm's
        self.assertEqual(len(set(own.values())), len(own), "two records share an id")
        self.assertLess(max(v for k, v in own.items() if k != "FirstTileId"), ids["FirstTileId"])
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', ENTRY_PSC)
        self.assertIn('EntryScript = "FO4SF_PAEntryQuest"', TOOL_SRC)
        self.assertTrue(ENTRY_PSC.startswith("Scriptname FO4SF_PAEntryQuest extends Quest"))

    def test_no_properties_no_stage_reads(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", ENTRY_PSC, re.M | re.I))
        self.assertNotIn(" Property ", ENTRY_PSC)
        self.assertNotIn("GetStageDone", ENTRY_PSC)

    def test_the_entry_does_every_move_and_the_exit_undoes_each(self):
        put_on = ENTRY_PSC.split("Function PutOn()")[1].split("EndFunction")[0]
        take_off = ENTRY_PSC.split("Function TakeOff()")[1].split("EndFunction")[0]
        self.assertNotIn("SetRace", ENTRY_PSC.split("Function PutOn()")[1].split("Function EntryVerdict")[0])   # PC run of #733: the swap removed the body
        self.assertEqual(put_on.count("p.AddItem("), 3)
        self.assertEqual(put_on.count("p.EquipItem("), 3)
        self.assertIn("SetPaValue(p, 1.0)", put_on)
        self.assertEqual(take_off.count("p.UnequipItem("), 3)
        self.assertEqual(take_off.count("p.RemoveItem("), 3)
        self.assertIn("SetPaValue(p, 0.0)", take_off)
        self.assertNotIn("p.SetRace(", ENTRY_PSC)                                # the entry never touches the race
        self.assertIn("p.GetRace() != StartRace", ENTRY_PSC)                     # but says on screen when something else did
        self.assertIn("StartRace = p.GetRace()", ENTRY_PSC.split("Event OnInit()")[1])
        for item in ("FrameId", "PieceHelmId", "PieceTorsoId"):                  # every item added is equipped, unequipped and removed
            for call in ("AddItem", "EquipItem"):
                self.assertIn(f"p.{call}(Thing({item})", put_on)
            for call in ("UnequipItem", "RemoveItem"):
                self.assertIn(f"p.{call}(Thing({item})", take_off)

    def test_the_value_and_the_item_equip_reads_are_guesses_behind_opt(self):
        self.assertEqual(mpa.optional_names(ENTRY_PSC), ["Actor.GetSitState", "Actor.GetValue", "Actor.SetValue", "Actor.IsEquipped",
                                                         "ScriptObject.RegisterForRemoteEvent", "Actor.OnItemUnequipped", "ObjectReference.MoveTo"])
        self.assertEqual(mpa.enable(ENTRY_PSC, []), ENTRY_PSC)
        for name in ("EquipItem", "UnequipItem"):
            self.assertIn(name, mpa.REQUIRED["Actor"])
        for name in ("AddItem", "RemoveItem", "GetItemCount"):
            self.assertIn(name, mpa.REQUIRED["ObjectReference"])

    def test_the_screen_says_each_step_and_the_log_ends_each_line(self):
        self.assertIn("Debug.Notification(msg)", ENTRY_PSC)
        self.assertIn('string LogName = "FO4SFPAEntry"', ENTRY_PSC)
        self.assertIn('"FO4SFPAENTRY rt="', ENTRY_PSC)
        self.assertIn('" end=true"', ENTRY_PSC)
        for words in ("Suit 1 s after the entry", "Suit 4 s after the entry", "1 s after the exit", "4 s after the exit",
                      "the suit is ON", "the suit is OFF", "did NOT undo everything", "only partly on",
                      "not in this game's scripts", "coc FO4SF_PAProbeCell"):
            self.assertIn(words, ENTRY_PSC)

    def test_what_was_worn_is_recorded_at_entry_and_put_back_at_the_exit(self):
        """PC run of #733: the entry takes the place of what is worn in the suit's slots and nothing put it back."""
        put_on = ENTRY_PSC.split("Function PutOn()")[1].split("EndFunction")[0]
        take_off = ENTRY_PSC.split("Function TakeOff()")[1].split("EndFunction")[0]
        self.assertLess(put_on.index("WatchWorn(p)"), put_on.index("p.EquipItem("))                # listening BEFORE the suit goes on
        self.assertLess(put_on.index("Recording = true"), put_on.index("p.EquipItem("))
        self.assertLess(take_off.index("p.RemoveItem(Thing(PieceTorsoId)"), take_off.index("RestoreWorn(p)"))
        self.assertIn("p.EquipItem(SavedWorn[i], false, true)", ENTRY_PSC.split("Function RestoreWorn")[1])
        self.assertIn("SavedWorn = new Form[64]", ENTRY_PSC.split("Event OnInit()")[1])
        self.assertIn('Trace("saved worn="', ENTRY_PSC)
        self.assertIn('Trace("restored worn="', ENTRY_PSC)
        self.assertIn("will not be put back", ENTRY_PSC)                                  # said when the game gives no unequipped event
        self.assertIn("pieces of gear put back", ENTRY_PSC)
        self.assertNotIn(";OPT Actor.GetWornItem", ENTRY_PSC)                                        # not in Starfield's scripts (PC run of #733 at 8fe7c27e)
        on = mpa.enable(ENTRY_PSC, ["ScriptObject.RegisterForRemoteEvent", "Actor.OnItemUnequipped"])
        self.assertIn('RegisterForRemoteEvent(p, "OnItemUnequipped")', on)
        self.assertIn("Event Actor.OnItemUnequipped(Actor akSender, Form akBaseObject, ObjectReference akReference)", on)
        handler = on.split("Event Actor.OnItemUnequipped")[1].split("EndEvent")[0]
        self.assertIn("!IsOurs(akBaseObject)", handler)                                  # our own pieces coming off are not "worn gear"
        self.assertIn("Recording", handler)
        self.assertIn("Recording = false", on.split("aiTimerID == TIMER_READ1")[1].split("elseif")[0])   # recording stops 1 s after the entry

    def test_a_game_without_a_sit_state_still_enters_once(self):
        self.assertIn('elseif sitText == "na" && !FallbackEntryUsed', ENTRY_PSC)
        self.assertIn("FallbackEntryUsed = true", ENTRY_PSC)
        self.assertIn("if InSuitSeconds >= SuitLimit", ENTRY_PSC.replace("elseif ", "if "))   # the timed exit needs no sit state

    def test_the_tool_is_one_kit_with_one_start_game_enabled_hand_or_entry(self):
        self.assertIn("WithHand ? Quest.Flag.StartGameEnabled : default", TOOL_SRC)
        self.assertIn('"--with-hand"', TOOL_SRC)
        self.assertIn("EntryPos = new(3, 0, 0)", TOOL_SRC)


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_are_the_tools(self):
        ids = const_ids(TOOL_SRC)
        for psc_name, tool_name in (("CellId", "CellId"), ("SuitId", "SuitId"), ("RaceId", "RaceId"),
                                    ("SuitRefId", "SuitRefId"), ("ControlRefId", "ControlRefId")):
            m = re.search(rf"^int {psc_name} = (0x[0-9A-Fa-f]+)", PSC, re.M)
            self.assertIsNotNone(m, psc_name)
            self.assertEqual(int(m.group(1), 16), ids[tool_name], psc_name)
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', PSC)
        self.assertIn('Script = "FO4SF_PAProbeQuest"', TOOL_SRC)
        self.assertTrue(PSC.startswith("Scriptname FO4SF_PAProbeQuest extends Quest"))

    def test_the_script_has_no_properties(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)

    def test_the_log_name_prefix_and_events_are_the_readers(self):
        from fo4sf.powerarmor import probe_log
        self.assertIn('string LogName = "FO4SFPAProbe"', PSC)
        self.assertIn('"FO4SFPA rt="', PSC)
        for e in probe_log.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e} ')            # every event the reader knows, one the script writes
        self.assertIn('" end=true"', PSC)                    # every line ends so

    def test_the_stages_the_script_runs_are_the_quests(self):
        for s in (10, 20, 30):
            self.assertIn(f"GetStageDone({s})", PSC)
        self.assertIn("{ 10, 20, 30 }", TOOL_SRC)

    def test_the_calls_under_test_are_made(self):
        self.assertIn("p.SwitchToPowerArmor(suit)", PSC)
        self.assertEqual(PSC.count("p.SetRace("), 2)

    def test_the_committed_script_compiles_alone_every_optional_line_is_a_comment(self):
        self.assertEqual(mpa.enable(PSC, []), PSC)
        names = mpa.optional_names(PSC)
        self.assertEqual(names, ["Actor.GetWornItem", "Actor.GetFurnitureReference", "Actor.GetSitState",
                                 "Actor.IsInPowerArmor", "Game.GetCameraState"])

    def test_enabling_an_optional_reading_uncomments_exactly_its_lines(self):
        on = mpa.enable(PSC, ["Actor.IsInPowerArmor"])
        self.assertIn('    s = "" + p.IsInPowerArmor()', on)
        self.assertNotIn(";OPT Actor.IsInPowerArmor", on)
        self.assertIn(";OPT Actor.GetSitState", on)
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        worn = mpa.enable(PSC, ["Actor.GetWornItem"])
        self.assertEqual(len(re.findall(r"^\s+(?:n = 0|int slot = 0|while slot < 64|endwhile)", worn, re.M)), 4)
        self.assertNotIn(";OPT Actor.GetWornItem", worn)


BASES = {
    "Form": "Scriptname Form\nint Function GetFormID() native\n",
    "ObjectReference": "Scriptname ObjectReference extends Form\nfloat Function GetPositionX() native\nfloat Function GetPositionY() native\nFunction MoveTo(ObjectReference a) native\n"
                       "float Function GetPositionZ() native\nfloat Function GetDistance(ObjectReference a) native\nCell Function GetParentCell() native\n"
                       "Function AddItem(Form f, int n, bool s) native\nFunction RemoveItem(Form f, int n, bool s) native\nint Function GetItemCount(Form f) native\n",
    "Actor": "Scriptname Actor extends ObjectReference\nFunction SwitchToPowerArmor(ObjectReference a) native\nFunction SetRace(Race r) native\n"
             "Function EquipItem(Form f, bool a, bool b) native\nFunction UnequipItem(Form f, bool a, bool b) native\nbool Function IsEquipped(Form f) native\n"
             "Race Function GetRace() native\nObjectReference Function GetFurnitureReference() native\nint Function GetSitState() native\n"
             "Actor:WornItem Function GetWornItem(int i) native\nEvent OnItemUnequipped(Form f, ObjectReference r) native\n",
    "Game": "Scriptname Game\nActor Function GetPlayer() native global\nForm Function GetFormFromFile(int i, string p) native global\n"
            "bool Function IsPluginInstalled(string p) native global\n",
    "Debug": "Scriptname Debug\nFunction Notification(string s) native global\nbool Function OpenUserLog(string n) native global\nbool Function TraceUser(string n, string t) native global\n",
    "Utility": "Scriptname Utility\nfloat Function GetCurrentRealTime() native global\n",
    "ScriptObject": "Scriptname ScriptObject\nFunction StartTimer(float f, int i) native\nFunction RegisterForRemoteEvent(ScriptObject o, string e) native\n",
    "Quest": "Scriptname Quest extends ScriptObject\nbool Function GetStageDone(int i) native\n",
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
        r = mpa.precheck_sources(mpa.read_sources(z), PSC, HAND_PSC, ENTRY_PSC)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["required"]["Actor.GetDistance"])                  # declared on ObjectReference
        self.assertEqual(r["optional"], {"Actor.GetWornItem": True, "Actor.GetFurnitureReference": True,
                                         "Actor.GetSitState": True, "Actor.IsInPowerArmor": False, "Game.GetCameraState": False,
                                         "ObjectReference.MoveTo": True, "Actor.GetValue": False, "Actor.SetValue": False,
                                         "Actor.IsEquipped": True, "ScriptObject.RegisterForRemoteEvent": True, "Actor.OnItemUnequipped": True})

    def test_a_missing_required_native_is_named(self):
        z = os.path.join(self.tmp.name, "cr.zip")
        fake_sources(z)
        sources = mpa.read_sources(z)
        sources["actor"] = sources["actor"].replace("SwitchToPowerArmor", "Other")
        self.assertEqual(mpa.precheck_sources(sources, PSC)["missing"], ["Actor.SwitchToPowerArmor"])


FAKE_COMPILER = """#!{python}
import os, sys
name = sys.argv[1][:-4]
text = open(sys.argv[1], encoding="utf-8").read()
out = [a[3:] for a in sys.argv if a.startswith("-o=")][0]
if any("GetSitState" in l for l in text.splitlines() if not l.startswith(";")):
    print("%s.psc(1,1): error: GetSitState does not match the fake compiler" % name)
    sys.exit(1)
os.makedirs(out, exist_ok=True)
open(os.path.join(out, name + ".pex"), "wb").write(text.encode())
print("Compilation succeeded.")
"""


def fake_compiler(root):
    """A runnable stand-in for PapyrusCompiler.exe: a script under sys.executable, behind a .cmd on Windows (a shebang
    file is not an executable there) and executable as it is elsewhere."""
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
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "PowerArmorProbe"), "-c", "Release", "--nologo"],
                              capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/PowerArmorProbe/bin/Release/net9.0/PowerArmorProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-pa-")
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
        self.assertIn("copy of NPCChairTech03_Free_270", proc.stdout)
        self.assertIn("FurnitureTypePowerArmor", proc.stdout)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("QUST FO4SF_PAProbeQuest flags StartGameEnabled stages [10,20,30]", check.stdout)
        self.assertIn("QUST FO4SF_PAHandQuest flags 0 scripts []", check.stdout)   # off, and no script, unless --with-hand
        self.assertIn("QUST FO4SF_PAEntryQuest flags StartGameEnabled scripts [FO4SF_PAEntryQuest (0 properties)]", check.stdout)
        self.assertIn("(0 properties)", check.stdout)

    def test_the_plugin_adds_records_and_overrides_none(self):
        """Raw bytes: every record carries load index 1 (our own plugin; Starfield.esm is master 0)."""
        out = self.root / "b2"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        data = (out / PLUGIN).read_bytes()
        self.assertEqual(data[:4], b"TES4")
        kinds, pos = {}, 0
        ids = []

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
        for sig, n in ((b"CELL", 1), (b"FURN", 2), (b"RACE", 1), (b"QUST", 3), (b"ARMO", 3), (b"AVIF", 1)):
            self.assertEqual(kinds.get(sig), n, sig)
        self.assertEqual(kinds.get(b"REFR"), 18)           # coc marker, arrival XMarker, suit, control, entry chair, 9 floor tiles, 4 lights

    def test_the_arrival_is_a_persistent_xmarker_in_the_cells_persistent_group_and_check_refuses_otherwise(self):
        out = self.root / "b2p"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        data = bytearray((out / PLUGIN).read_bytes())
        i = data.index(b"FO4SF_PAProbeArrival")
        rec = data.rfind(b"REFR", 0, i)
        flags = struct.unpack_from("<I", data, rec + 8)[0]
        self.assertEqual(flags & 0x400, 0x400)                                    # persistent
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("FO4SF_PAProbeArrival persistent, base 00003B:Starfield.esm", check.stdout)
        struct.pack_into("<I", data, rec + 8, flags & ~0x400)                     # the same record without the flag
        (out / "bad").mkdir()
        (out / "bad" / PLUGIN).write_bytes(bytes(data))
        bad = self.run_tool("check", out / "bad" / PLUGIN, self.master)
        self.assertEqual(bad.returncode, 1, bad.stdout)

    def test_the_suit_differs_from_its_control_by_exactly_one_keyword(self):
        out = self.root / "b3"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertRegex(check.stdout, r"FURN FO4SF_PAProbeSuit keywords \[000900:Starfield.esm, 0F4A21:Starfield.esm\] \(control .*: 1 keywords\)")

    def test_the_entry_kit_records(self):
        """FAL-361: the entry furniture is the control with NO keyword, one AVIF of ours, three ARMO that carry the default vanilla art (PC run of #733: no armature, no equip)."""
        out = self.root / "e1"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertRegex(check.stdout, r"FURN FO4SF_PAEntryFurn keywords \[000900:Starfield.esm\] \(the control's, no FurnitureTypePowerArmor\)")
        self.assertRegex(check.stdout, r"AVIF FO4SF_PAInPowerArmor 00080C:FO4SFPowerArmorProbe.esm type Variable default 0 min 0 max 1")
        for edid, slot, art in (("FO4SF_PAFrame", "BODY", "Spacesuit_Mark1_Body"), ("FO4SF_PAPieceHelm", "Hat", "Spacesuit_Mark1_Helmet"),
                                ("FO4SF_PAPieceTorso", "Backpack", "Spacesuit_Mark1_Backpack")):    # the copied art's OWN slot; two pieces, two slots
            self.assertRegex(check.stdout, rf"ARMO {edid} \S+ slot {slot} armatures 1 \(art: {art}\)")
        self.assertIn("REFR 00080B:FO4SFPowerArmorProbe.esm FO4SF_PAEntryFurnRef base 00080A:FO4SFPowerArmorProbe.esm at (3, 0, 0)", check.stdout)

    def test_the_three_armor_name_humanrace_not_the_copy_and_the_hand_script_is_off_the_record_without_with_hand(self):
        """FAL-361 PC run of #733: 'armor cannot be equipped by the passed in actor's race'; the hand quest's OnInit ran unflagged."""
        out = self.root / "e0"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        data = (out / PLUGIN).read_bytes()
        self.assertEqual(data.count(b"FO4SF_PAHandQuest"), 1)                         # the quest's EDID only: no VMAD script name
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout)
        out2 = self.root / "e0b"
        self.assertEqual(self.run_tool("build", self.master, out2, "--with-hand").returncode, 0)
        self.assertGreater((out2 / PLUGIN).read_bytes().count(b"FO4SF_PAHandQuest"), 1)
        self.assertIn("armor.Race.SetTo(humanRace.FormKey)", TOOL_SRC)            # no race swap: the pieces are for HumanRace

    def test_art_options_copy_a_vanilla_armo_and_check_needs_the_same_options(self):
        out = self.root / "e2"
        art = ["--frame-art", "SynthArmorArt", "--piece-art", "SynthArmorArt", "--with-hand"]
        self.assertEqual(self.run_tool("build", self.master, out, *art).returncode, 0)
        ok = self.run_tool("check", out / PLUGIN, self.master, *art)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertIn("armatures 2 (art: SynthArmorArt)", ok.stdout)
        self.assertIn("QUST FO4SF_PAHandQuest flags StartGameEnabled scripts [FO4SF_PAHandQuest (0 properties)]", ok.stdout)
        bad = self.run_tool("check", out / PLUGIN, self.master)                       # without the options the plugin is not what is asked
        self.assertEqual(bad.returncode, 1, bad.stdout)
        self.assertIn("armatures differ from Spacesuit_Mark1_Body", bad.stdout)
        self.assertIn("only --with-hand does that", bad.stdout)
        self.assertIn("only --with-hand attaches it", bad.stdout)
        miss = self.run_tool("build", self.master, self.root / "e3", "--frame-art", "NoSuchArmor")
        self.assertEqual(miss.returncode, 1)
        self.assertIn("0 ARMO named NoSuchArmor", miss.stderr)

    def test_art_is_not_optional_by_default_and_none_is_the_explicit_opt_out(self):
        """PC run of #733: an ARMO with no armature cannot be equipped, so a stage always carries art unless `none` is said."""
        self.assertIn('FrameArt = "Spacesuit_Mark1_Body", PieceArt = "Spacesuit_Mark1_Helmet"', TOOL_SRC)
        self.assertEqual((mpa.DEFAULT_FRAME_ART, mpa.DEFAULT_PIECE_ART), ("Spacesuit_Mark1_Body", "Spacesuit_Mark1_Helmet"))
        out = self.root / "e4"
        none = ["--frame-art", "none", "--piece-art", "none"]
        self.assertEqual(self.run_tool("build", self.master, out, *none).returncode, 0)
        ok = self.run_tool("check", out / PLUGIN, self.master, *none)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        self.assertIn("armatures 0 (art: none)", ok.stdout)
        self.assertEqual(self.run_tool("check", out / PLUGIN, self.master).returncode, 1)     # the default check refuses an armature-less kit
        gone = self.run_tool("build", self.master, self.root / "e5", "--piece-art", "Spacesuit_Mark1_Nothing")
        self.assertEqual(gone.returncode, 1)
        self.assertIn("0 ARMO named Spacesuit_Mark1_Nothing", gone.stderr)

    def test_a_control_that_is_already_power_armor_is_refused(self):
        proc = self.run_tool("build", self.master, self.root / "b4", "--control", "SynthAlreadyPowerArmor")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no control", proc.stderr)
        self.assertFalse((self.root / "b4" / PLUGIN).exists())

    def test_a_missing_record_is_refused_by_name(self):
        proc = self.run_tool("build", self.master, self.root / "b5", "--control", "NoSuchFurniture")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 FURN named NoSuchFurniture", proc.stderr)

    def test_check_refuses_another_control(self):
        out = self.root / "b6"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        wrong = self.run_tool("check", out / PLUGIN, self.master, "--control", "SynthAlreadyPowerArmor")
        self.assertEqual(wrong.returncode, 1, wrong.stdout)

    def test_stage_publishes_a_plan_with_the_optional_readings_fate(self):
        z = self.root / "cr.zip"
        fake_sources(z)
        compiler = fake_compiler(self.root)
        final = self.root / "stage"
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        code = mpa.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", str(compiler),
                         "--content-resources", str(z)])
        self.assertEqual(code, 0)
        plan = json.loads((final / "plan.json").read_text())
        self.assertEqual(plan["kind"], "power-armor-probe")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(sorted(plan["outputs"]), sorted([PLUGIN, "Data/Scripts/FO4SF_PAProbeQuest.pex", "Data/Scripts/FO4SF_PAHandQuest.pex",
                                                    "Data/Scripts/FO4SF_PAEntryQuest.pex"]))
        self.assertEqual(plan["optional_entry"]["Actor.IsEquipped"], "kept")
        self.assertEqual(plan["optional_entry"]["Actor.OnItemUnequipped"], "kept")
        self.assertEqual(plan["optional_entry"]["ScriptObject.RegisterForRemoteEvent"], "kept")
        self.assertEqual(plan["pack_art"], "Spacesuit_Mark1_Backpack")
        self.assertEqual(plan["optional_entry"]["Actor.GetValue"], "not declared in the base scripts")
        self.assertEqual(plan["optional_entry"]["Actor.GetSitState"][:8], "declared")
        self.assertFalse(plan["hand_quest_on"])
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mpa.sha256(str(self.master)))
        self.assertEqual(plan["optional"]["Actor.GetWornItem"], "kept")
        self.assertEqual(plan["optional"]["Actor.GetFurnitureReference"], "kept")
        self.assertTrue(plan["optional"]["Actor.GetSitState"].startswith("declared but did not compile"))
        self.assertEqual(plan["optional"]["Actor.IsInPowerArmor"], "not declared in the base scripts")
        self.assertEqual(plan["optional"]["Game.GetCameraState"], "not declared in the base scripts")
        self.assertEqual(plan["optional_hand"]["ObjectReference.MoveTo"], "kept")
        self.assertIn("p.MoveTo(coc)", (final / "FO4SF_PAHandQuest.psc").read_text())
        kept = (final / "FO4SF_PAProbeQuest.psc").read_text()
        self.assertIn("p.GetFurnitureReference()", kept)
        self.assertNotIn(";OPT Actor.GetFurnitureReference", kept)
        self.assertIn(";OPT Actor.IsInPowerArmor", kept)                       # still a comment
        self.assertEqual(mpa.verify_stage(str(final), plan, str(self.master.parent)), [])
        self.assertTrue((final / "offline_check.txt").read_text().rstrip().endswith("all checks pass"))
        self.assertFalse((final / "work").exists())
        with self.assertRaises(SystemExit) as e:                               # an earlier stage is never overwritten
            mpa.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", str(compiler),
                      "--content-resources", str(z)])
        self.assertIn("exists", str(e.exception))
        (final / PLUGIN).write_bytes(b"changed")
        self.assertTrue(any("changed after the stage" in p for p in mpa.verify_stage(str(final), plan)))

    def test_stage_refuses_when_a_required_native_is_missing(self):
        z = self.root / "cr2.zip"
        fake_sources(z, drop=("Quest",))
        final = self.root / "stage2"
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        with self.assertRaises(SystemExit) as e:
            mpa.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", "/nonexistent",
                      "--content-resources", str(z)])
        self.assertIn("Quest.GetStageDone", str(e.exception))
        self.assertFalse(final.exists())                                       # nothing published


if __name__ == "__main__":
    unittest.main()
