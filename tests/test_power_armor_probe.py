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
        self.assertEqual(ids["HandQuestId"], 0x809)
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
        for text in (HAND_PSC, PSC):
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
        self.assertEqual(const_ids(TOOL_SRC)["ArrivalRefId"], 0x80A)

    def test_the_hand_log_lines_end(self):
        self.assertIn('"FO4SFPAHAND rt="', HAND_PSC)
        self.assertIn('" end=true"', HAND_PSC)
        self.assertIn('string LogName = "FO4SFPAHand"', HAND_PSC)

    def test_the_required_list_has_the_notification(self):
        self.assertIn("Notification", mpa.REQUIRED["Debug"])


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
                                 "Actor.IsInPowerArmor", "ObjectReference.HasKeyword", "ObjectReference.AddKeyword", "Game.GetCameraState"])
        self.assertIn('" haskw=" + kb + " addkw=" + ka + " haskw2=" + k2 + " haskwc=" + KwChair(suit)', PSC)
        self.assertIn("if kb == \"false\"", PSC)                                 # AddKeyword only when the game does not see it

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
    "ObjectReference": "Scriptname ObjectReference extends Form\nbool Function HasKeyword(Keyword k) native\nFunction AddKeyword(Keyword k) native\nfloat Function GetPositionX() native\nfloat Function GetPositionY() native\nFunction MoveTo(ObjectReference a) native\n"
                       "float Function GetPositionZ() native\nfloat Function GetDistance(ObjectReference a) native\nCell Function GetParentCell() native\n",
    "Actor": "Scriptname Actor extends ObjectReference\nFunction SwitchToPowerArmor(ObjectReference a) native\nFunction SetRace(Race r) native\n"
             "Race Function GetRace() native\nObjectReference Function GetFurnitureReference() native\nint Function GetSitState() native\n"
             "Actor:WornItem Function GetWornItem(int i) native\n",
    "Game": "Scriptname Game\nActor Function GetPlayer() native global\nForm Function GetFormFromFile(int i, string p) native global\n"
            "bool Function IsPluginInstalled(string p) native global\n",
    "Debug": "Scriptname Debug\nFunction Notification(string s) native global\nbool Function OpenUserLog(string n) native global\nbool Function TraceUser(string n, string t) native global\n",
    "Utility": "Scriptname Utility\nfloat Function GetCurrentRealTime() native global\n",
    "ScriptObject": "Scriptname ScriptObject\nFunction StartTimer(float f, int i) native\n",
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
        r = mpa.precheck_sources(mpa.read_sources(z), PSC, HAND_PSC)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["required"]["Actor.GetDistance"])                  # declared on ObjectReference
        self.assertEqual(r["optional"], {"Actor.GetWornItem": True, "Actor.GetFurnitureReference": True,
                                         "Actor.GetSitState": True, "Actor.IsInPowerArmor": False, "ObjectReference.HasKeyword": True, "ObjectReference.AddKeyword": True,
                                         "Game.GetCameraState": False, "ObjectReference.MoveTo": True})

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
        self.assertIn("QUST FO4SF_PAHandQuest flags StartGameEnabled scripts [FO4SF_PAHandQuest (0 properties)]", check.stdout)
        self.assertIn("(0 properties)", check.stdout)
        self.assertIn("FURN keyword form component [000900:Starfield.esm, 0F4A21:Starfield.esm]", check.stdout)   # FAL-212, 11 Nov

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
        for sig, n in ((b"CELL", 1), (b"FURN", 1), (b"RACE", 1), (b"QUST", 2)):
            self.assertEqual(kinds.get(sig), n, sig)
        self.assertEqual(kinds.get(b"REFR"), 17)           # coc marker, arrival XMarker, suit, control, 9 floor tiles, 4 lights

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

    def test_variants_override_only_their_default_objects(self):
        for variant, n, kw in (("race", 1, 0), ("race,furniture,keyword", 3, 1)):
            out = self.root / ("v_" + variant.replace(",", "_"))
            proc = self.run_tool("build", self.master, out, "--variant", variant)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            check = self.run_tool("check", out / PLUGIN, self.master, "--variant", variant)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertIn(f"DefaultObject {n}", check.stdout)
            self.assertEqual(("Keyword 1" in check.stdout), bool(kw))
            # the plugin without the variant's flag is a mismatch: the check knows which overrides it must hold
            self.assertEqual(self.run_tool("check", out / PLUGIN, self.master).returncode, 1)
        self.assertIn("PowerArmorRace_DO 05C254:Starfield.esm Object 000802:FO4SFPowerArmorProbe.esm", check.stdout)
        self.assertIn("15503F:Starfield.esm]", check.stdout)                       # isPowerArmorFrame on the suit
        self.assertIn("000807:FO4SFPowerArmorProbe.esm", check.stdout)             # our armor keyword
        self.assertEqual(self.run_tool("build", self.master, self.root / "v_bad", "--variant", "bogus").returncode, 1)

    def test_the_armor_variant_copies_a_named_plain_armor_and_gives_it_the_frame_keyword(self):
        out = self.root / "v_armor"
        v = "race,furniture,keyword,armor"
        bad = self.run_tool("build", self.master, self.root / "v_armor_bad", "--variant", v)       # no --armor: refused, lists candidates
        self.assertEqual(bad.returncode, 1)
        self.assertIn("name it with --armor <editor id>", bad.stderr)
        self.assertIn("SynthPlainArmor", bad.stderr)
        self.assertFalse((self.root / "v_armor_bad" / PLUGIN).exists())
        proc = self.run_tool("build", self.master, out, "--variant", v, "--armor", "SynthPlainArmor")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("ARMO FO4SF_PAFrameArmor = copy of SynthPlainArmor", proc.stdout)
        check = self.run_tool("check", out / PLUGIN, self.master, "--variant", v, "--armor", "SynthPlainArmor")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("ARMO FO4SF_PAFrameArmor 000808:FO4SFPowerArmorProbe.esm (copy of SynthPlainArmor 0A0001:Starfield.esm)", check.stdout)
        self.assertIn("keywords [000900:Starfield.esm, 15503F:Starfield.esm] component [000900:Starfield.esm, 15503F:Starfield.esm] armor rating 7", check.stdout)
        self.assertIn("PowerArmorDefaultFrameArmor_DO 15503E:Starfield.esm Object 000808:FO4SFPowerArmorProbe.esm", check.stdout)
        self.assertIn("Armor 1", check.stdout)
        self.assertIn("DefaultObject 4", check.stdout)
        self.assertEqual(self.run_tool("check", out / PLUGIN, self.master, "--variant", "race,furniture,keyword").returncode, 1)
        self.assertEqual(self.run_tool("build", self.master, self.root / "v_armor_none", "--variant", v, "--armor", "NoSuchArmor").returncode, 1)

    def test_kw_first_puts_the_power_armor_keyword_first_in_the_list_and_the_check_knows(self):
        out = self.root / "kwfirst"
        proc = self.run_tool("build", self.master, out, "--kw-first")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        check = self.run_tool("check", out / PLUGIN, self.master, "--kw-first")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("FURN FO4SF_PAProbeSuit keywords [0F4A21:Starfield.esm, 000900:Starfield.esm]", check.stdout)
        self.assertIn("component [0F4A21:Starfield.esm, 000900:Starfield.esm]".replace("component ", "keyword form component "), check.stdout)
        self.assertEqual(self.run_tool("check", out / PLUGIN, self.master).returncode, 1)          # the default order is a mismatch
        self.assertEqual(self.run_tool("check", self.root / "b1" / PLUGIN, self.master, "--kw-first").returncode, 1)

    def test_variant_overrides_keep_the_form_ids_of_the_vanilla_records(self):
        out = self.root / "v_raw"
        self.assertEqual(self.run_tool("build", self.master, out, "--variant", "race").returncode, 0)
        data = (out / PLUGIN).read_bytes()
        self.assertIn(struct.pack("<I", 0x0005C254), data)                          # master index 0: Starfield.esm's own id

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
        self.assertEqual(sorted(plan["outputs"]), sorted([PLUGIN, "Data/Scripts/FO4SF_PAProbeQuest.pex", "Data/Scripts/FO4SF_PAHandQuest.pex"]))
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mpa.sha256(str(self.master)))
        self.assertEqual(plan["variant"], [])
        self.assertFalse(plan["kw_first"])
        self.assertEqual(plan["optional"]["Actor.GetWornItem"], "kept")
        self.assertEqual(plan["optional"]["Actor.GetFurnitureReference"], "kept")
        self.assertEqual(plan["optional"]["ObjectReference.HasKeyword"], "kept")
        self.assertEqual(plan["optional"]["ObjectReference.AddKeyword"], "kept")
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

    def test_stage_records_the_variant_and_refuses_a_bad_one(self):
        z = self.root / "cr3.zip"
        fake_sources(z)
        compiler = fake_compiler(self.root)
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        args = ["--starfield", str(self.master), "--compiler", str(compiler), "--content-resources", str(z)]
        final = self.root / "stage_race"
        self.assertEqual(mpa.main(["stage", "--out", str(final), "--variant", "race"] + args), 0)
        plan = json.loads((final / "plan.json").read_text())
        self.assertEqual(plan["variant"], ["race"])
        self.assertIn("DFOB PowerArmorRace_DO", (final / "offline_check.txt").read_text())
        self.assertIn("Variant (default objects overridden): race", (final / "README.txt").read_text())
        self.assertEqual(mpa.verify_stage(str(final), plan, str(self.master.parent)), [])
        with self.assertRaises(SystemExit) as e:                                  # armor without --armor: refused before the tool
            mpa.main(["stage", "--out", str(self.root / "stage_noarmor"), "--variant", "armor"] + args)
        self.assertIn("name it with --armor", str(e.exception))
        full = self.root / "stage_armor"
        self.assertEqual(mpa.main(["stage", "--out", str(full), "--variant", "race,furniture,keyword,armor", "--armor", "SynthPlainArmor"] + args), 0)
        plan = json.loads((full / "plan.json").read_text())
        self.assertEqual((plan["variant"], plan["armor"]), (["race", "furniture", "keyword", "armor"], "SynthPlainArmor"))
        self.assertIn("ARMO FO4SF_PAFrameArmor", (full / "offline_check.txt").read_text())
        self.assertIn("frame armor: a copy of SynthPlainArmor", (full / "README.txt").read_text())
        self.assertEqual(mpa.verify_stage(str(full), plan, str(self.master.parent)), [])
        for bad in ("bogus", "race,race"):
            with self.assertRaises(SystemExit) as e:
                mpa.main(["stage", "--out", str(self.root / "stage_bad"), "--variant", bad] + args)
            self.assertIn("--variant is a comma list", str(e.exception))

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
