"""The rads probe's writer (dotnet/RadsProbe) on a synthetic Starfield.esm, its script's properties against the tool's,
the optional-reading mechanism and the stage with a fake Papyrus compiler and fake base sources (never a game; the real
Papyrus compile and the real Starfield.esm are the PC's job). The dotnet tests skip without the .NET SDK."""
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
import make_rads_probe as mrp  # noqa: E402

PSC = (ROOT / "scripts" / "planet" / "FO4SF_RadsProbeQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "RadsProbe" / "Program.cs").read_text(encoding="utf-8")
HAND_PSC = (ROOT / "scripts" / "planet" / "FO4SF_RadsHandQuest.psc").read_text(encoding="utf-8")
PLUGIN = "FO4SFRadsProbe.esm"


class HandScriptTests(unittest.TestCase):
    """The by-hand mode (FAL-273): a second quest of the same plugin that shows every change on screen."""

    def test_the_hand_scripts_properties_are_the_tools(self):
        m = re.search(r"HandPropNames = \{([^}]*)\}", TOOL_SRC)
        tool = re.findall(r'"(\w+)"', m.group(1))
        psc = re.findall(r"^(\w+) Property (\w+) Auto Const Mandatory", HAND_PSC, re.M)
        self.assertEqual([n for _, n in psc], tool)
        self.assertEqual([t for t, _ in psc], ["ActorValue", "ActorValue", "Form", "Form"])
        self.assertTrue(HAND_PSC.startswith("Scriptname FO4SF_RadsHandQuest extends Quest"))
        self.assertIn('HandScript = "FO4SF_RadsHandQuest"', TOOL_SRC)

    def test_every_change_is_an_on_screen_message_in_the_owners_words(self):
        self.assertIn("Debug.Notification(msg)", HAND_PSC)
        self.assertIn('return "Rads " + (p.GetValue(RadsAV) as int) + ", " + MaxText(p)', HAND_PSC)
        self.assertIn('"max health "', HAND_PSC)
        # the change path: a different value than the last one shown is applied to the route and said
        self.assertRegex(HAND_PSC, r"if rads != LastRads\n\s+ApplyRoute\(p\)\n\s+Say\(UsedPrefix\(\) \+ Describe\(p\)\)")
        # the failure path is in the log only (owner's words, PC 11 Nov): one plain line per use, whole numbers, the sentence is not shown
        self.assertNotIn('Say(UsedWhat + " used: the effect left rads at "', HAND_PSC)
        self.assertIn('note=effect left a wrong number', HAND_PSC)
        self.assertIn('Shown + " used. "', HAND_PSC)
        self.assertIn('(p.GetValue(HealthAV) as int)', HAND_PSC)               # no ".000000" on screen
        self.assertNotIn('"health " + p.GetValue(HealthAV)', HAND_PSC)
        self.assertIn("ModRads(p, WantRads - have)", HAND_PSC)
        self.assertIn("p.SetValue(RadsAV, WantRads)", HAND_PSC)       # only when ModValue is not declared

    def test_an_item_used_while_another_settles_is_added_not_dropped(self):
        """FAL-278: the second Rad Dose of the card (step 5) came inside the first one's 3 s and was dropped, then the settle
        reset the value and the screen said the effect did nothing."""
        poll = HAND_PSC.split("Function Poll()")[1].split("Function Settle()")[0]
        self.assertNotIn("if !Settling\n        float want", poll)
        self.assertIn("if dose < LastDose || away < LastAway", poll)
        self.assertIn("want = WantRads", poll)                                    # a use during a settle adds to the target
        self.assertIn("if !Settling\n            Settling = true", poll)          # one timer only
        settle = HAND_PSC.split("Function Settle()")[1]
        self.assertIn("StartTimer(wait, TIMER_SETTLE)", settle)                   # the latest use gets its full time
        self.assertLess(settle.index("StartTimer(wait"), settle.index("Settling = false"))

    def test_a_runaway_effect_is_clamped_and_hidden_until_the_settle(self):
        """FAL-213 PC run: an ingestible's effect was applied once per frame (rads -59,700). The hand quest must not show or
        route that, and must keep the value in range itself."""
        poll = HAND_PSC.split("Function Poll()")[1].split("Function Settle()")[0]
        self.assertIn("if rads < 0.0 || rads > RadsMaxValue", poll)
        self.assertIn("p.SetValue(RadsAV, Clamp(rads))", poll)
        self.assertLess(poll.index("if Settling\n        ; an item was just used"), poll.index("ApplyRoute(p)"))   # no route while it settles
        self.assertLess(poll.index("p.SetValue(RadsAV, Clamp(rads))"), poll.index("if Settling\n        ; an item was just used"))

    def test_no_console_is_needed_the_items_come_with_the_quest(self):
        # OnInit ran twice 0.18 s apart on the PC: the kit tops up to GiveCount, it never adds GiveCount again
        self.assertIn("p.AddItem(RadAway, GiveCount - haveAway, true)", HAND_PSC)
        self.assertIn("p.AddItem(RadDose, GiveCount - haveDose, true)", HAND_PSC)
        self.assertNotIn("p.AddItem(RadAway, GiveCount, true)", HAND_PSC)
        init = HAND_PSC.split("Event OnInit()")[1].split("EndEvent")[0]
        self.assertIn("if gave", init)                                     # a second run says nothing
        self.assertIn("int GiveCount = 3", HAND_PSC)
        self.assertNotIn("GetStageDone", HAND_PSC)               # no stage numbers

    def test_the_numbers_are_the_writers_and_the_probes(self):
        self.assertIn("float DoseMagnitude = 100.0", HAND_PSC)
        self.assertIn("float RadAwayMagnitude = -200.0", HAND_PSC)
        self.assertIn("DoseMagnitude = 100f", TOOL_SRC)
        self.assertIn("RadAwayMagnitude = -200f", TOOL_SRC)
        self.assertIn("float PenaltyPerRad = 0.1", HAND_PSC)
        self.assertIn("float RadsMaxValue = 1000.0", HAND_PSC)
        self.assertIn("RadsMax = 1000f", TOOL_SRC)

    def test_the_hand_log_lines_end_and_the_optional_lines_are_comments(self):
        self.assertIn('"FO4SFRADSHAND rt="', HAND_PSC)
        self.assertIn('" end=true"', HAND_PSC)
        self.assertEqual(mrp.enable(HAND_PSC, []), HAND_PSC)
        self.assertEqual(mrp.optional_names(HAND_PSC), ["Actor.GetValueMax", "Actor.ModValue"])
        self.assertEqual(len(re.findall(r"^;OPT Actor\.ModValue +p\.ModValue\(HealthAV, delta\)", HAND_PSC, re.M)), 1)
        self.assertEqual(len(re.findall(r"^;OPT Actor\.ModValue +p\.ModValue\(RadsAV, delta\)", HAND_PSC, re.M)), 1)

    def test_nothing_the_script_calls_is_missing_from_the_required_list(self):
        for base, name in (("Actor", "GetItemCount"), ("Debug", "Notification")):
            self.assertIn(name, mrp.REQUIRED[base])


class ScriptTests(unittest.TestCase):
    def test_the_scripts_properties_are_the_tools(self):
        m = re.search(r"PropNames = \{([^}]*)\}", TOOL_SRC)
        tool = re.findall(r'"(\w+)"', m.group(1))
        psc = re.findall(r"^(\w+) Property (\w+) Auto Const( Mandatory)?", PSC, re.M)
        self.assertEqual([n for _, n, _ in psc], tool)
        self.assertEqual([t for t, _, _ in psc], ["ActorValue", "ActorValue", "Spell", "Form", "Spell"])
        self.assertEqual([bool(m) for _, _, m in psc], [True, True, True, True, False])     # ControlSpell is optional
        self.assertIn('string ProbePlugin = "FO4SFRadsProbe.esm"', PSC)
        self.assertIn('Script = "FO4SF_RadsProbeQuest"', TOOL_SRC)
        self.assertTrue(PSC.startswith("Scriptname FO4SF_RadsProbeQuest extends Quest"))
        self.assertEqual(len(re.findall(r"^\w+(\[\])? Property ", PSC, re.M)), 5)       # the fifth, ControlSpell, is not Mandatory

    def test_the_log_name_prefix_and_events_are_the_readers(self):
        from fo4sf.rads import probe_log
        self.assertIn('string LogName = "FO4SFRadsProbe"', PSC)
        self.assertIn('"FO4SFRADS rt="', PSC)
        for e in probe_log.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e} ')            # every event the reader knows, one the script writes
        self.assertIn('" end=true"', PSC)                    # every line ends so

    def test_the_stages_the_script_runs_are_the_quests_and_the_readers(self):
        from fo4sf.rads import probe_log
        for s in (10, 20, 30, 40, 50):
            self.assertIn(f"GetStageDone({s})", PSC)
        self.assertIn("{ 10, 20, 30, 40, 50 }", TOOL_SRC)
        self.assertEqual(probe_log.STAGES, (10, 20, 30, 40, 50))
        for stage, want in probe_log.EXPECT.items():
            self.assertRegex(PSC, rf"stage == {stage}\n\s+return {want}") if stage != 10 else None

    def test_the_numbers_the_reader_assumes_are_the_scripts_and_the_writers(self):
        from fo4sf.rads import probe_log
        self.assertIn(f"float PenaltyPerRad = {probe_log.PENALTY}", PSC)
        self.assertIn(f"float ControlDelta = {probe_log.CONTROL_DELTA}", PSC)
        self.assertIn("SpellMagnitude = 100f, RadAwayMagnitude = -200f, RadAwayMirrorMagnitude = 200f", TOOL_SRC)

    def test_the_calls_under_test_are_made(self):
        self.assertEqual(PSC.count("RadsSpell.Cast(p, p)"), 3)            # once at stage 20, twice at stage 30
        self.assertIn("p.EquipItem(RadAway, false, true)", PSC)
        for w in ("added", "now", "settled"):
            self.assertIn(f'Trace("item stage=40 when={w} count=" + p.GetItemCount(RadAway))', PSC)
        self.assertIn("moved = ModRads(p, dRad)", PSC)
        self.assertIn('Trace("radaway stage=40 item_had="', PSC)
        self.assertIn("ModRads(p, want - have)", PSC)                  # the force is a difference, not SetValue(want)
        self.assertRegex(PSC, r"(?m)^;OPT Actor\.ModValue +p\.ModValue\(RadsAV, delta\)")
        self.assertIn("p.SetValue(RadsAV, 0.0)", PSC)
        self.assertIn("p.SetValue(RadsAV, WriteTest)", PSC)            # stage 10 writes a number that is not zero
        self.assertIn(f"float WriteTest = {int(__import__('fo4sf.rads.probe_log', fromlist=['x']).WRITE_TEST)}.0", PSC)
        self.assertEqual(len(re.findall(r"^;OPT Actor\.ModValue +p\.ModValue\(HealthAV, delta\)", PSC, re.M)), 1)

    def test_the_committed_script_compiles_alone_every_optional_line_is_a_comment(self):
        self.assertEqual(mrp.enable(PSC, []), PSC)
        self.assertEqual(mrp.optional_names(PSC), ["Actor.GetBaseValue", "Actor.GetValueMax", "Actor.GetActiveEffects",
                                                   "Actor.GetActiveMagicEffects", "Actor.ModValue"])

    def test_enabling_an_optional_reading_uncomments_exactly_its_lines(self):
        on = mrp.enable(PSC, ["Actor.ModValue"])
        self.assertIn("    p.ModValue(HealthAV, delta)", on)
        self.assertNotIn(";OPT Actor.ModValue", on)
        self.assertIn(";OPT Actor.GetBaseValue", on)
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        fx = mrp.enable(PSC, ["Actor.GetActiveEffects"])
        self.assertEqual(len(re.findall(r"^\s+(?:while fxa|endwhile|ActiveMagicEffect\[\] fxa)", fx, re.M)), 3)
        self.assertNotIn(";OPT Actor.GetActiveEffects", fx)
        self.assertIn(";OPT Actor.GetActiveMagicEffects", fx)


BASES = {
    "Form": "Scriptname Form\nint Function GetFormID() native\n",
    "ObjectReference": "Scriptname ObjectReference extends Form\nfloat Function GetValue(ActorValue a) native\nint Function GetItemCount(Form f) native\n"
                       "Function SetValue(ActorValue a, float f) native\nFunction ModValue(ActorValue a, float f) native\n"
                       "float Function GetBaseValue(ActorValue a) native\n"
                       "ObjectReference Function AddItem(Form f, int n, bool b) native\n",
    "Actor": "Scriptname Actor extends ObjectReference\nFunction EquipItem(Form f, bool a, bool b) native\n"
             "ActiveMagicEffect[] Function GetActiveEffects() native\n",
    "Spell": "Scriptname Spell extends Form\nFunction Cast(ObjectReference s, ObjectReference t) native\n",
    "Game": "Scriptname Game\nActor Function GetPlayer() native global\nbool Function IsPluginInstalled(string p) native global\n",
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
        r = mrp.precheck_sources(mrp.read_sources(z), PSC)
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["required"]["Actor.GetValue"])                      # declared on ObjectReference
        self.assertEqual(r["optional"], {"Actor.GetBaseValue": True, "Actor.GetValueMax": False, "Actor.GetActiveEffects": True,
                                         "Actor.GetActiveMagicEffects": False, "Actor.ModValue": True})

    def test_a_missing_required_native_is_named(self):
        z = os.path.join(self.tmp.name, "cr.zip")
        fake_sources(z)
        sources = mrp.read_sources(z)
        sources["spell"] = sources["spell"].replace("Cast", "Other")
        self.assertEqual(mrp.precheck_sources(sources, PSC)["missing"], ["Spell.Cast"])


FAKE_COMPILER = """#!{python}
import os, sys
name = sys.argv[1][:-4]
text = open(sys.argv[1], encoding="utf-8").read()
out = [a[3:] for a in sys.argv if a.startswith("-o=")][0]
if any("GetBaseValue" in l for l in text.splitlines() if not l.startswith(";")):
    print("%s.psc(1,1): error: GetBaseValue does not match the fake compiler" % name)
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
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "RadsProbe"), "-c", "Release", "--nologo"],
                              capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/RadsProbe/bin/Release/net9.0/RadsProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-rads-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.master = cls.root / "m" / "Starfield.esm"
        r = cls.run_tool("fixture", cls.root / "m")
        assert r.returncode == 0, r.stdout + r.stderr
        for mode in ("spell", "none"):          # the real file's case (a restore effect only on a spell) and the fallback
            r = cls.run_tool("fixture", cls.root / f"m_{mode}", "--restore", mode)
            assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def test_build_and_check(self):
        out = self.root / "b1"
        proc = self.run_tool("build", self.master, out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("HealthAV = Health", proc.stdout)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("AVIF FO4SF_Rads", check.stdout)
        self.assertIn("type Variable default 0 min 0 max 1000 flags DefaultToZero, DamageIsPositive", check.stdout)
        self.assertIn("archetype ValueModifier actor value (DATA word 14) 000800:FO4SFRadsProbe.esm association Null", check.stdout)
        self.assertIn("SPEL FO4SF_RadsSpell", check.stdout)
        self.assertIn("1 effect(s) at 100", check.stdout)
        self.assertIn('ALCH FO4SF_RadAway 000803:FO4SFRadsProbe.esm "RadAway"', check.stdout)
        self.assertIn("1 effect(s) at 200", check.stdout)               # the restore pattern: +200 on a damage-is-positive value
        self.assertIn('ALCH FO4SF_RadDose 000806:FO4SFRadsProbe.esm "Rad Dose"', check.stdout)
        self.assertIn("1 effect(s) at 100", check.stdout)
        self.assertIn("QUST FO4SF_RadsHandQuest flags StartGameEnabled scripts [FO4SF_RadsHandQuest (4 properties)]", check.stdout)
        self.assertIn("QUST FO4SF_RadsProbeQuest flags StartGameEnabled stages [10,20,30,40,50]", check.stdout)
        self.assertIn("(4 properties)", check.stdout)
        self.assertIn("property HealthAV = 00A02D:Starfield.esm", check.stdout)

    def test_one_effect_serves_the_spell_and_radaway(self):
        out = self.root / "b1b"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        check = self.run_tool("check", out / PLUGIN, self.master).stdout
        self.assertIn("records: MagicEffect 2, Spell 1, Ingestible 2, Quest 2, ActorValueInformation 1", check)

    def test_the_plugin_adds_records_and_overrides_none(self):
        """Raw bytes: every record carries load index 1 (our own plugin; Starfield.esm is master 0), no hazard record."""
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
        self.assertEqual(kinds, {b"TES4": 1, b"AVIF": 1, b"MGEF": 2, b"SPEL": 1, b"ALCH": 2, b"QUST": 2})
        self.assertNotIn(b"HAZD", kinds)

    def test_the_effect_spell_and_radaway_are_copies_of_vanilla_records(self):
        """The first game session crashed on Spell.Cast with records written from nothing: they now carry the
        template's own subrecords (equip type, effect ids, description) and none of its keywords or conditions."""
        out = self.root / "b2t"
        proc = self.run_tool("build", self.master, out)
        self.assertIn("templates (preferred): SPEL DamageHealthSpell", proc.stdout)
        self.assertIn("MGEF SynthValueEffect", proc.stdout)
        self.assertIn("ALCH SynthRestoreHealthAid", proc.stdout)
        data = (out / PLUGIN).read_bytes()
        subs = {}

        def walk(buf, i, end):
            while i < end:
                sig = buf[i:i + 4]
                size = struct.unpack_from("<I", buf, i + 4)[0]
                if sig == b"GRUP":
                    walk(buf, i + 24, i + size)
                    i += size
                    continue
                body, j, names = buf[i + 24:i + 24 + size], 0, []
                while j < len(body):
                    names.append(body[j:j + 4])
                    j += 6 + struct.unpack_from("<H", body, j + 4)[0]
                subs[sig] = names
                i += 24 + size
        walk(data, 0, len(data))
        for sub in (b"ETYP", b"MAGF", b"EFIF", b"MUID", b"DESC"):
            self.assertIn(sub, subs[b"SPEL"], sub)
        self.assertIn(b"DNAM", subs[b"MGEF"])
        for sub in (b"MAGF", b"EFIF", b"MUID", b"DESC"):
            self.assertIn(sub, subs[b"ALCH"], sub)
        self.assertNotIn(b"KWDA", subs[b"SPEL"] + subs[b"MGEF"] + subs[b"ALCH"])
        self.assertNotIn(b"CTDA", subs[b"SPEL"] + subs[b"MGEF"] + subs[b"ALCH"])
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("templates (preferred)", check.stdout)

    def test_the_mgef_data_word_14_is_our_actor_value_and_the_flags_do_not_negate(self):
        """Both game crashes (FAL-213): the engine reads the effect's actor value (DATA word 14, Mutagen's
        SecondActorValue) at Spell.Cast and the kit left it null. Raw bytes, no game."""
        out = self.root / "b2w"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        data = (out / PLUGIN).read_bytes()
        i = data.index(b"MGEF", data.index(b"MGEF") + 4)       # the first is the group's label, the second the record
        size = struct.unpack_from("<I", data, i + 4)[0]
        body, j, subs = data[i + 24:i + 24 + size], 0, {}
        while j < len(body):
            n = struct.unpack_from("<H", body, j + 4)[0]
            subs[body[j:j + 4]] = body[j + 6:j + 6 + n]
            j += 6 + n
        words = struct.unpack_from(f"<{len(subs[b'DATA']) // 4}I", subs[b"DATA"])
        avif = 0x01000800                                   # our plugin is load index 1, the AVIF is 0x800
        self.assertEqual(words[14], avif)                   # the actor value
        self.assertEqual(words[0], 0)                       # the association stays empty, as in every vanilla effect
        self.assertEqual(words[16], 0)                      # no resist value (the synthetic template named one)
        self.assertEqual(words[1], 0)                       # no skill
        self.assertEqual(words[17], 0)
        self.assertIn("actor value (DATA word 14) 000800:FO4SFRadsProbe.esm",
                      self.run_tool("check", out / PLUGIN, self.master).stdout)

    def test_the_preferred_template_is_the_vanilla_damage_spell_and_its_flags_are_kept(self):
        """Fourth session: DamageHealthSpell works from Cast; the copy keeps its effect's own flags (only Detrimental off)."""
        out = self.root / "b2p"
        proc = self.run_tool("build", self.master, out)
        self.assertIn("templates (preferred): SPEL DamageHealthSpell", proc.stdout)
        self.assertEqual(self.run_tool("check", out / PLUGIN, self.master).returncode, 0)

    def test_the_script_clamps_our_value_at_zero_before_the_route(self):
        self.assertRegex(PSC, r"if rads < 0\.0\n(?:.*\n)*?\s+p\.SetValue\(RadsAV, 0\.0\)\n\s+rads = 0\.0\n\s+clamped = true")
        self.assertIn('" clamped=" + clamped', PSC)

    def test_the_sign_pair_detrimental_effect_and_a_damage_is_positive_value(self):
        """Fifth session: the rads effect keeps its template's Detrimental bit and the value carries "damage is positive"
        (AVFL bit 26 = 0x04000000), so the engine's sign rule (negate when exactly one is set) leaves +100 as +100;
        RadAway's own effect is the restore pattern (not Detrimental), +200, which the rule turns into a fall of 200."""
        out = self.root / "b2y"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        check = self.run_tool("check", out / PLUGIN, self.master)
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertRegex(check.stdout, r"MGEF FO4SF_RadsEffect .* flags Detrimental, NoDuration\n")
        self.assertRegex(check.stdout, r"MGEF FO4SF_RadAwayEffect .* flags NoDuration, HideInUI\n")
        self.assertIn("flags DefaultToZero, DamageIsPositive", check.stdout)
        self.assertIn("RadAway MGEF SynthRestoreHealthEffect", check.stdout)
        data = (out / PLUGIN).read_bytes()
        j = data.index(b"AVFL") + 6
        self.assertEqual(struct.unpack_from("<I", data, j)[0], 0x04000400)      # DefaultToZero | bit 26
        # raw: both MGEFs carry our AVIF in word 14; the first has the Detrimental bit in word 26, the second does not
        pos, words = 0, []
        while True:
            k = data.find(b"DATA", pos)
            if k < 0:
                break
            n = struct.unpack_from("<H", data, k + 4)[0]
            if n == 142 or n == 136:
                words.append(struct.unpack_from(f"<{n // 4}I", data, k + 6))
            pos = k + 6
        self.assertEqual(len(words), 2, words)
        for w in words:
            self.assertEqual(w[14], 0x01000800)

    def test_with_no_restore_ingestible_the_mirror_effect_comes_from_a_spell(self):
        """The real Starfield.esm has one Health ingestible (ShipRepairKit, entry duration 10): the restore effect then comes
        from a spell's entry (Dueling_RestoreHealth_Spell on the real file), the shell stays a vanilla medicine's."""
        m = self.root / "m_spell" / "Starfield.esm"
        out = self.root / "b2s"
        proc = self.run_tool("build", m, out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("ALCH SynthAid", proc.stdout)                                   # the shell
        self.assertIn("RadAway MGEF SynthRestoreHealthEffect", proc.stdout)           # the effect, from the spell
        self.assertNotIn("shares the spell's effect", proc.stdout)
        chk = self.run_tool("check", out / PLUGIN, m)
        self.assertEqual(chk.returncode, 0, chk.stdout)
        self.assertIn("MGEF FO4SF_RadAwayEffect", chk.stdout)
        self.assertIn("1 effect(s) at 200", chk.stdout)
        self.assertIn("records: MagicEffect 2,", chk.stdout)
        self.assertIn("next 0x808", chk.stdout)
        named = self.run_tool("build", m, self.root / "b2s2", "--restore-spell", "SynthRestoreSpell")
        self.assertEqual(named.returncode, 0, named.stdout + named.stderr)
        bad = self.run_tool("build", m, self.root / "b2s3", "--restore-spell", "NoSuchSpell")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("0 SPEL named NoSuchSpell", bad.stderr)

    def test_with_no_restore_effect_anywhere_radaway_shares_the_spells_effect(self):
        """The fallback (no test before this one): one MGEF, RadAway at -200 on the shared effect, next form id 0x808 (0x806 the Rad Dose, 0x807 the hand quest)."""
        m = self.root / "m_none" / "Starfield.esm"
        out = self.root / "b2n"
        proc = self.run_tool("build", m, out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RadAway shares the spell's effect", proc.stdout)
        chk = self.run_tool("check", out / PLUGIN, m)
        self.assertEqual(chk.returncode, 0, chk.stdout)
        self.assertIn("1 effect(s) at -200", chk.stdout)
        self.assertIn("records: MagicEffect 1,", chk.stdout)
        self.assertIn("next 0x808", chk.stdout)
        self.assertNotIn("FO4SF_RadAwayEffect", chk.stdout)

    def test_a_restore_template_that_is_detrimental_is_not_picked_by_search(self):
        """The search wants a Health value modifier that is not Detrimental with duration 0: the synthetic SynthAid (whose
        effect is Detrimental and on another value) is passed over, SynthRestoreHealthAid is taken."""
        out = self.root / "b2y2"
        proc = self.run_tool("build", self.master, out)
        self.assertIn("ALCH SynthRestoreHealthAid", proc.stdout)
        self.assertNotIn("ALCH SynthAid", proc.stdout)

    def test_the_second_control_spell_is_a_fifth_property_only_when_named(self):
        out = self.root / "b2z"
        ok = self.run_tool("build", self.master, out, "--control-spell", "SynthSelfSpell")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        chk = self.run_tool("check", out / PLUGIN, self.master, "--control-spell", "SynthSelfSpell")
        self.assertEqual(chk.returncode, 0, chk.stdout)
        self.assertIn("(5 properties)", chk.stdout)
        self.assertIn("property ControlSpell = 00A101:Starfield.esm", chk.stdout)
        plain = self.run_tool("check", out / PLUGIN, self.master)            # checked as built without it
        self.assertEqual(plain.returncode, 1, plain.stdout)
        self.assertIn("exactly 4 properties", plain.stdout)
        none = self.root / "b2z0"
        self.assertEqual(self.run_tool("build", self.master, none).returncode, 0)
        self.assertIn("(4 properties)", self.run_tool("check", none / PLUGIN, self.master).stdout)
        bad = self.run_tool("build", self.master, self.root / "b2z1", "--control-spell", "NoSuchSpell")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("0 SPEL named NoSuchSpell", bad.stderr)

    def test_check_refuses_a_kit_whose_actor_value_is_not_ours(self):
        out = self.root / "b2x"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        data = bytearray((out / PLUGIN).read_bytes())
        i = data.index(b"MGEF")
        d = data.index(b"DATA", i) + 6
        struct.pack_into("<I", data, d + 14 * 4, 0)         # the crash of both sessions: word 14 empty
        (out / "bad").mkdir()
        (out / "bad" / PLUGIN).write_bytes(bytes(data))
        bad = self.run_tool("check", out / "bad" / PLUGIN, self.master)
        self.assertEqual(bad.returncode, 1, bad.stdout)
        self.assertIn("SecondActorValue, DATA word 14) is not FO4SF_Rads", bad.stdout)

    def test_the_no_template_effect_is_not_detrimental_either(self):
        self.assertRegex(TOOL_SRC, r"Flag\.Detrimental \| MagicEffect\.Flag\.NoDuration \| MagicEffect\.Flag\.NoArea")

    def test_a_named_template_is_used_and_an_unknown_one_is_refused(self):
        out = self.root / "b2u"
        ok = self.run_tool("build", self.master, out, "--template-spell", "SynthSelfSpell", "--template-aid", "SynthAid")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("templates (named)", ok.stdout)
        bad = self.run_tool("build", self.master, self.root / "b2v", "--template-spell", "NoSuchSpell")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("0 SPEL named NoSuchSpell", bad.stderr)
        self.assertFalse((self.root / "b2v" / PLUGIN).exists())

    def test_the_avif_type_can_be_named_and_is_checked(self):
        out = self.root / "b3"
        proc = self.run_tool("build", self.master, out, "--type", "DerivedAttribute")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("DerivedAttribute", proc.stdout)
        self.assertEqual(self.run_tool("check", out / PLUGIN, self.master, "--type", "DerivedAttribute").returncode, 0)
        wrong = self.run_tool("check", out / PLUGIN, self.master)            # checks for Variable
        self.assertEqual(wrong.returncode, 1, wrong.stdout)
        self.assertIn("the AVIF is not a Variable", wrong.stdout)
        bad = self.run_tool("build", self.master, self.root / "b3b", "--type", "Nonsense")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("is not an AVIF type", bad.stderr)

    def test_a_missing_health_record_is_refused_by_name(self):
        proc = self.run_tool("build", self.master, self.root / "b5", "--health", "NoSuchValue")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 AVIF named NoSuchValue", proc.stderr)
        self.assertFalse((self.root / "b5" / PLUGIN).exists())

    def test_check_refuses_another_health_target(self):
        out = self.root / "b6"
        self.assertEqual(self.run_tool("build", self.master, out).returncode, 0)
        wrong = self.run_tool("check", out / PLUGIN, self.master, "--health", "SynthOther")
        self.assertEqual(wrong.returncode, 1, wrong.stdout)
        self.assertIn("property HealthAV is not", wrong.stdout)

    def test_stage_publishes_a_plan_with_the_optional_readings_fate(self):
        z = self.root / "cr.zip"
        fake_sources(z)
        compiler = fake_compiler(self.root)
        final = self.root / "stage"
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        code = mrp.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", str(compiler),
                         "--content-resources", str(z)])
        self.assertEqual(code, 0)
        plan = json.loads((final / "plan.json").read_text())
        self.assertEqual(plan["kind"], "rads-probe")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual((plan["health"], plan["avif_type"]), ("Health", "Variable"))
        self.assertEqual(sorted(plan["outputs"]), sorted([PLUGIN, "Data/Scripts/FO4SF_RadsProbeQuest.pex", "Data/Scripts/FO4SF_RadsHandQuest.pex"]))
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mrp.sha256(str(self.master)))
        self.assertTrue(plan["templates"].startswith("preferred: SPEL DamageHealthSpell"))
        self.assertEqual(plan["optional"]["Actor.ModValue"], "kept")
        self.assertEqual(plan["optional"]["Actor.GetActiveEffects"], "kept")
        self.assertTrue(plan["optional"]["Actor.GetBaseValue"].startswith("declared but did not compile"))
        self.assertEqual(plan["optional"]["Actor.GetValueMax"], "not declared in the base scripts")
        self.assertEqual(plan["optional"]["Actor.GetActiveMagicEffects"], "not declared in the base scripts")
        self.assertEqual(plan["optional_hand"], {"Actor.GetValueMax": "not declared in the base scripts", "Actor.ModValue": "kept"})
        self.assertIn("p.ModValue(HealthAV, delta)", (final / "FO4SF_RadsHandQuest.psc").read_text())
        kept = (final / "FO4SF_RadsProbeQuest.psc").read_text()
        self.assertIn("p.ModValue(HealthAV, delta)", kept)
        self.assertNotIn(";OPT Actor.ModValue", kept)
        self.assertIn(";OPT Actor.GetValueMax", kept)                          # still a comment
        self.assertEqual(mrp.verify_stage(str(final), plan, str(self.master.parent)), [])
        self.assertTrue((final / "offline_check.txt").read_text().rstrip().endswith("all checks pass"))
        self.assertFalse((final / "work").exists())
        with self.assertRaises(SystemExit) as e:                               # an earlier stage is never overwritten
            mrp.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", str(compiler),
                      "--content-resources", str(z)])
        self.assertIn("exists", str(e.exception))
        (final / PLUGIN).write_bytes(b"changed")
        self.assertTrue(any("changed after the stage" in p for p in mrp.verify_stage(str(final), plan)))

    def test_stage_refuses_when_a_required_native_is_missing(self):
        z = self.root / "cr2.zip"
        fake_sources(z, drop=("Quest",))
        final = self.root / "stage2"
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(Path(self.dotnet).parent) + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        with self.assertRaises(SystemExit) as e:
            mrp.main(["stage", "--out", str(final), "--starfield", str(self.master), "--compiler", "/nonexistent",
                      "--content-resources", str(z)])
        self.assertIn("Quest.GetStageDone", str(e.exception))
        self.assertFalse(final.exists())                                       # nothing published


class ConsoleCommandTests(unittest.TestCase):
    def test_the_console_lines_carry_the_quest_form_id_of_the_session(self):
        import contextlib
        import io
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        f = Path(tmp.name) / "l.log"
        f.write_text("\n".join(["[x] FO4SFRADS rt=1.0 init version=1 quest=184551428 installed=true end=true",
                                "[x] FO4SFRADS rt=9.0 init version=1 quest=184551429 installed=true end=true"]), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = mrp.main(["console", "--file", str(f)])
        self.assertEqual(code, 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[:4], [f"setstage 0B000805 {s}" for s in (10, 20, 30, 40)])   # the latest init
        self.assertIn("player.getav FO4SF_Rads", lines)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mrp.main(["console", "--file", str(Path(tmp.name) / "none.log")]), 2)

    def test_the_log_is_looked_for_under_onedrive_first(self):
        paths = mrp.user_logs()
        self.assertIn("OneDrive", paths[0])
        self.assertNotIn("OneDrive", paths[1])


class LogCommandTests(unittest.TestCase):
    def test_log_exit_code_follows_the_control(self):
        import contextlib
        import io
        from test_rads_probe_log import good_log, head
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for lines, want in ((good_log(), 0), (head(), 1)):
            f = Path(tmp.name) / f"l{want}.log"
            f.write_text("\n".join(lines), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = mrp.main(["log", "--file", str(f)])
            self.assertEqual(code, want, out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mrp.main(["log", "--file", str(Path(tmp.name) / "missing.log")]), 2)


if __name__ == "__main__":
    unittest.main()
