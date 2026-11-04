"""dotnet/CombinedProbe on synthetic masters (the synthetic Starfield.esm of dotnet/TerrainIdentityFixture with the
map-marker template, and the core dotnet/TerrainOverlays writes on it, as tests/test_map_markers_plugin.py builds
them), never a game: every record of the probe plugin, its check, the refusals; plus the Papyrus scripts' text
contracts (they cannot be compiled here) and scripts/combined_probes/make_combined_probe.py with the tools mocked."""
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
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402
from test_map_markers_plugin import MapMarkersPluginTests, build  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "combined_probes"))
import make_combined_probe as mcp  # noqa: E402

SCRIPTS = ROOT / "scripts/combined_probes"
PROGRAM = (ROOT / "dotnet/CombinedProbe/Program.cs").read_text(encoding="utf-8")
QUEST = (SCRIPTS / "FOCC_ProbeQuest.psc").read_text(encoding="utf-8")
PROBE = (SCRIPTS / "FOCC_Probe.psc").read_text(encoding="utf-8")
P10 = (SCRIPTS / "FOCC_P10Quest.psc").read_text(encoding="utf-8")
ARRAY = (SCRIPTS / "FOCC_P5_Array129.psc").read_text(encoding="utf-8")
DRIVE = (SCRIPTS / "FOCC_P9Drive.psc").read_text(encoding="utf-8")
NATIVE = (SCRIPTS / "FOCC.psc").read_text(encoding="utf-8")
B0 = (SCRIPTS / "FOCC_B0.psc").read_text(encoding="utf-8")

# the plugin-local ids the plan fixes (dotnet/CombinedProbe/Program.cs header); the scripts quote some as decimals
IDS = {"QuestId": 0x804, "HolderId": 0x805, "P2LocId": 0x806, "P3NoParentId": 0x807, "P3ChainedId": 0x808, "RouteId": 0x809,
       "P4MarkerId": 0x80B, "P8Parent0Id": 0x80C, "P8Child0Id": 0x80F, "P9DestId": 0x81B, "P6ListId": 0x81C, "P7ListId": 0x81D,
       "RepId": 0x81E, "P10EventId": 0x81F, "P10QuestId": 0x820, "P10BranchId": 0x821, "P10NodeId": 0x822, "P5FirstId": 0x823,
       "PongId": 0x855, "NextId": 0x856}
# the properties the builder fills, by Papyrus type, as the quest script declares them
PROPERTIES = {"Holder": "Keyword", "Route": "Keyword", "P2Loc": "Location", "P3LocNoParent": "Location", "P3LocChained": "Location",
              "P4Marker": "ObjectReference", "P4Base": "Form", "P5Globals": "GlobalVariable[]", "P6List": "Form", "P6BaseA": "Form",
              "P6BaseB": "Form", "P7Rep": "GlobalVariable", "P7List": "Form", "P8Parents": "ObjectReference[]",
              "P8Children": "ObjectReference[]", "P9Dest": "ObjectReference", "P10Event": "Keyword", "P10Quest": "Quest"}
# every Papyrus base type a script of the kit names (declarations, casts, static calls)
PAPYRUS_TYPES = ("Actor", "Cell", "Debug", "Form", "Game", "GlobalVariable", "Keyword", "Location", "ObjectReference", "Package", "Quest",
                 "Utility", "WorldSpace", "ScriptObject")


OWN = 0x02 << 24          # the plugin's own records in the written file: masters Starfield.esm (00), the core (01)


def records(path):
    """tests/test_terrain_reference_identity.records keyed by the FULL form id (master index included): the core's
    world and cell overrides keep the core's ids, which can share their low 24 bits with the plugin's own records."""
    data = path.read_bytes()
    out = {}

    def walk(start, end, owner=None):
        pos = start
        while pos < end:
            sig, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
            if sig == b"GRUP":
                label, kind = struct.unpack_from("<II", data, pos + 8)
                walk(pos + 24, pos + size, label if kind in (6, 8, 9) else owner)
                pos += size
            else:
                flags, form = struct.unpack_from("<II", data, pos + 8)
                payload = data[pos + 24:pos + 24 + size]
                if flags & 0x40000:
                    payload = zlib.decompress(payload[4:])
                if form:
                    out[form] = (sig, payload, owner, flags)
                pos += 24 + size
    walk(0, len(data))
    return out


class CombinedProbePluginTests(unittest.TestCase):
    """The actual tool on the synthetic core (skipped without the .NET SDK)."""
    run_writer = MapMarkersPluginTests.run_writer

    @classmethod
    def setUpClass(cls):
        MapMarkersPluginTests.setUpClass.__func__(cls)                     # fixture, writer, synthetic core
        cls.tool = build(cls.dotnet, "CombinedProbe")
        # the synthetic Starfield.esm holds a STAT (3807C6 SyntheticStatic) and no NPC_: the NPC bases are links the
        # masters read here do not hold (warned, written as given), as 002B211C is not in the synthetic master
        cls.opts = ["--sf", cls.master, "--core", cls.core, "--world", "SyntheticWorld", "--location", "SyntheticLocation",
                    "--stat", "Starfield.esm:3807C6", "--lvln-b", "Starfield.esm:2B211D"]

    def tool_run(self, *argv):
        return subprocess.run([self.dotnet, str(self.tool), *map(str, argv)], capture_output=True, text=True)

    def built(self, name, *extra):
        out = self.root / name
        proc = self.tool_run("build", "--out", out, *self.opts, *extra)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("wrote ", proc.stdout)
        return out / "FO4SFCombinedProbe.esm", proc

    def test_every_record_is_written_and_read_back(self):
        plugin, proc = self.built("default")
        self.assertRegex(proc.stdout, r"WARN  --npc 2B211C:Starfield\.esm is not in the Starfield\.esm read here")   # FormKey prints id:plugin
        check = self.tool_run("check", plugin, *self.opts)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("all checks pass", check.stdout)
        self.assertIn("fn=651 EqualTo 1 param=", check.stdout)              # the P6 conditions read back
        self.assertIn("fn=74 LessThan 8 param=", check.stdout)              # the P7 conditions read back
        self.assertIn("event SCPT", check.stdout)                           # the P10 quest's Script Event
        self.assertIn("1 GMST", check.stdout)                               # B0's game setting read back
        recs = records(plugin)
        sigs = {}
        for sig, *_ in recs.values():
            sigs[sig] = sigs.get(sig, 0) + 1
        self.assertEqual(sigs[b"QUST"], 2)
        self.assertEqual(sigs[b"KYWD"], 3)
        self.assertEqual(sigs[b"LCTN"], 3)
        self.assertEqual(sigs[b"GLOB"], 51)
        self.assertEqual(sigs[b"GMST"], 1)
        self.assertEqual(sigs[b"REFR"], 2 + 3 * 5)
        self.assertEqual(sigs[b"LVLN"], 2)
        self.assertEqual(sigs[b"SMBN"], 1)
        self.assertEqual(sigs[b"SMQN"], 1)
        self.assertEqual(sigs[b"WRLD"], 1)                                   # the core world, overridden
        self.assertEqual(sigs[b"CELL"], 1)                                   # its persistent cell, overridden
        for name, id_ in IDS.items():
            if name == "NextId":
                continue
            self.assertIn(OWN | id_, recs, f"{name} 0x{id_:X} not written")
        self.assertEqual(recs[OWN | 0x804][0], b"QUST")
        vmad = tlw.field(recs[OWN | 0x804][1], b"VMAD")
        self.assertEqual(struct.unpack_from("<hH", vmad), (6, 2))
        self.assertIn(b"FOCC_ProbeQuest", vmad)
        for prop in PROPERTIES:
            self.assertIn(struct.pack("<H", len(prop)) + prop.encode(), vmad, prop)
        self.assertNotIn(b"Variant", vmad)                                   # the default build leaves the script's default
        self.assertIn(b"FOCC_P10Quest", tlw.field(recs[OWN | 0x820][1], b"VMAD"))
        # the P8 children carry the STAT and an enable parent (XESP: parent form id + flags)
        for k in range(3):
            for j in range(4):
                sig, payload, _, flags = recs[OWN | (0x80F + 4 * k + j)]
                self.assertEqual(sig, b"REFR")
                self.assertEqual(flags & 0xC00, 0x400)
                self.assertEqual(struct.unpack("<I", tlw.field(payload, b"NAME"))[0], 0x3807C6)
                self.assertEqual(struct.unpack("<I", tlw.field(payload, b"XESP")[:4])[0] & 0xFFFFFF, 0x80C + k)
        self.assertEqual(recs[OWN | 0x80D][3] & 0xC00, 0xC00)                # stage 1 parent initially disabled
        self.assertEqual(recs[OWN | 0x80C][3] & 0xC00, 0x400)                # stage 0 parent enabled
        for i in range(50):
            self.assertEqual(recs[OWN | (0x823 + i)][0], b"GLOB")
        sig, payload, *_ = recs[OWN | 0x855]                                 # B0: iFOCC_Pong, an int game setting of 7
        self.assertEqual(sig, b"GMST")
        self.assertEqual(tlw.field(payload, b"EDID"), b"iFOCC_Pong\0")
        self.assertEqual(tlw.field(payload, b"DATA"), struct.pack("<i", 7))

    def test_check_refuses_other_bases_and_a_mismatched_skip(self):
        plugin, _ = self.built("bases")
        other = [a if a != "Starfield.esm:3807C6" else "Starfield.esm:3807D0" for a in self.opts]   # not in the master: warned
        check = self.tool_run("check", plugin, *other)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  REFR FOCC_P8_Child_0_0: base", check.stdout)
        check = self.tool_run("check", plugin, *self.opts, "--skip", "lvln,sm")
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  --skip lvln but the plugin holds LVLN records", check.stdout)
        self.assertIn("FAIL  --skip sm but the plugin holds SM nodes", check.stdout)

    def test_skip_leaves_the_unverified_records_out(self):
        plugin, proc = self.built("skip", "--skip", "lvln,sm")
        self.assertIn("lvln skipped", proc.stdout)
        recs = records(plugin)
        self.assertEqual([s for s, *_ in recs.values() if s in (b"LVLN", b"SMBN", b"SMQN")], [])
        self.assertNotIn(b"P6List", tlw.field(recs[OWN | 0x804][1], b"VMAD"))
        check = self.tool_run("check", plugin, *self.opts, "--skip", "lvln,sm")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        check = self.tool_run("check", plugin, *self.opts)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  LVLN 0x81C FOCC_P6_HolderList missing", check.stdout)

    def test_build_refusals(self):
        no_stat = [a for a in self.opts if a not in ("--stat", "Starfield.esm:3807C6")]
        proc = self.tool_run("build", "--out", self.root / "nostat", *no_stat)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("--stat <plugin:hexid> is required", proc.stderr)
        no_b = [a for a in self.opts if a not in ("--lvln-b", "Starfield.esm:2B211D")]
        proc = self.tool_run("build", "--out", self.root / "nob", *no_b)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("--lvln-b <plugin:hexid> is required", proc.stderr)
        # a STAT where an NPC_ is wanted is refused by type, not warned
        wrong = [a if a != "Starfield.esm:2B211D" else "Starfield.esm:3807C6" for a in self.opts]
        proc = self.tool_run("build", "--out", self.root / "wrong", *wrong)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("refused: --lvln-b ", proc.stderr)
        self.assertIn(", not Npc", proc.stderr)
        # the cell variant needs the port plugin's two interiors; the core has none
        proc = self.tool_run("build", "--out", self.root / "cells", *self.opts, "--p3-cells", "--port", self.core)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("has no cell FO4Port_RedRocket01", proc.stderr)
        # another core location name: not in the core
        proc = self.tool_run("build", "--out", self.root / "loc", *[a if a != "SyntheticLocation" else "Other" for a in self.opts])
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertIn("has no location Other", proc.stderr)
        self.assertFalse((self.root / "loc" / "FO4SFCombinedProbe.esm").exists())


    # --- P10's Story Manager branch on a master with a Script Event node (TerrainIdentityFixture "story-manager") ---

    SM_KEYWORD, SM_BRANCH_A, SM_BRANCH_B = 0x3807E0, 0x3807E2, 0x3807E4      # the fixture's ids

    def sm_opts(self, mode):
        """self.opts with --sf on a master that adds a Script Event SMEN and its nodes ("story-manager": keyword
        filters; "story-manager-open": none)."""
        master = self.root / f"sm-{mode}/Starfield.esm"
        if not master.exists():
            fixture = build(self.dotnet, "TerrainIdentityFixture")
            subprocess.run([self.dotnet, str(fixture), str(master), "map-marker", mode], capture_output=True, check=True)
        opts = list(self.opts)
        opts[opts.index("--sf") + 1] = master
        return master, opts

    def test_the_p10_branch_copies_the_vanilla_keyword_filter(self):
        # Owner's PC, 28 Oct 2026: an unconditioned branch let FOCC_P10_Quest start at game start (Codex review of #557).
        master, opts = self.sm_opts("story-manager")
        out = self.root / "sm"
        proc = self.tool_run("build", "--out", out, *opts)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        # two of the three filters under the node are GetIsID/Keyword1; the root branch's decoy is not under it
        self.assertIn(f"after {self.SM_BRANCH_B:06X}:Starfield.esm, condition GetEventData GetIsID/Keyword1 EqualTo 1 "
                      "(shape of 2 of 3 vanilla keyword filters, e.g. SyntheticScriptEventBranchA", proc.stdout)
        plugin = out / "FO4SFCombinedProbe.esm"
        check = self.tool_run("check", plugin, *opts)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("SMBN condition GetEventData GetIsID/Keyword1 record", check.stdout)
        self.assertIn("vanilla keyword filter GetIsID/Keyword1 EqualTo 1, 2 of 3", check.stdout)
        # binary round trip: our CTDA is branch A's, with FOCC_P10_Event in place of the fixture's keyword
        ours = tlw.field(records(plugin)[OWN | 0x821][1], b"CTDA")
        theirs = tlw.field(records(master)[self.SM_BRANCH_A][1], b"CTDA")
        self.assertIn(struct.pack("<I", self.SM_KEYWORD), theirs)
        self.assertEqual(ours, theirs.replace(struct.pack("<I", self.SM_KEYWORD), struct.pack("<I", OWN | 0x81F)))
        # the check reads the condition back: the default master's root-node plugin has none, which this master refuses
        plain, _ = self.built("sm-plain")
        check = self.tool_run("check", plain, *opts)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  FOCC_P10_Branch has no single GetEventData condition naming FOCC_P10_Event", check.stdout)

    def test_a_script_event_node_without_keyword_filters_is_refused(self):
        _, opts = self.sm_opts("story-manager-open")
        proc = self.tool_run("build", "--out", self.root / "sm-open", *opts)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("refused: no node under SyntheticScriptEventNode", proc.stderr)
        self.assertIn("--skip sm", proc.stderr)
        self.assertFalse((self.root / "sm-open" / "FO4SFCombinedProbe.esm").exists())
        proc = self.tool_run("build", "--out", self.root / "sm-open-skip", *opts, "--skip", "sm")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class ScriptContractTests(unittest.TestCase):
    def test_entry_points_resolve_the_quest_and_log_the_same_prefix(self):
        for name in mcp.ENTRY_POINTS:
            self.assertRegex(PROBE, rf"\nFunction {name}\([^)]*\) global\n", name)
        self.assertIn('Game.GetFormFromFile(2052, "FO4SFCombinedProbe.esm") as Quest', PROBE)      # 0x804 as a decimal
        self.assertEqual(IDS["QuestId"], 2052)
        self.assertEqual(PROBE.count('Q("'), len(mcp.ENTRY_POINTS))                  # every entry point resolves the quest
        self.assertEqual(PROBE.count("if q != None") + PROBE.count("if q == None"), len(mcp.ENTRY_POINTS))
        for text in (QUEST, PROBE, P10):
            for m in re.finditer(r'Debug\.TraceUser\("focc", (.+)\)', text):
                self.assertTrue(m.group(1).startswith('"FOCC rt=" + Utility.GetCurrentRealTime() + " '), m.group(0))
        self.assertIn('Debug.OpenUserLog(LogName)', QUEST)
        self.assertIn('string LogName = "focc"', QUEST)
        self.assertIn('Debug.OpenUserLog("focc")', P10)

    def test_quest_script_declares_what_the_builder_fills(self):
        for name, kind in PROPERTIES.items():
            self.assertRegex(QUEST, rf"\n{re.escape(kind)} Property {name} Auto Const Mandatory\n", name)
        self.assertIn('string Property Variant = "default" Auto Const', QUEST)
        # the builder fills exactly these names (its Obj / ObjList calls), plus Variant on the p3cells build
        filled = set(re.findall(r'Obj(?:List)?\("([A-Za-z0-9]+)", ', PROGRAM)) - {""}
        self.assertEqual(filled, set(PROPERTIES))
        self.assertIn('new ScriptStringProperty { Name = "Variant"', PROGRAM)

    def test_ids_in_scripts_match_the_builder(self):
        for name, id_ in IDS.items():
            self.assertRegex(PROGRAM, rf"\b{name} = 0x{id_:X}\b", name)
        self.assertEqual(IDS["P5FirstId"] + 50, IDS["PongId"])
        self.assertEqual(IDS["PongId"] + 1, IDS["NextId"])
        self.assertIn('EditorID = "iFOCC_Pong", Data = 7', PROGRAM)
        self.assertIn('local=2054', QUEST)                                   # 0x806 FOCC_P2_Loc
        self.assertIn('local=2055', QUEST)                                   # 0x807
        self.assertIn('local=2056', QUEST)                                   # 0x808
        self.assertIn('local=2080', QUEST)                                   # 0x820 FOCC_P10_Quest
        self.assertIn('local=2080', P10)
        self.assertEqual((0x806, 0x807, 0x808, 0x820), (2054, 2055, 2056, 2080))

    def test_every_probe_logs_its_event_lines(self):
        for line in ('"p2 set loc="', '"p2 link a="', '"p2 read loc="', '"p2 linkread a="', '"p3 set a="', '"p3 read a="',
                     '"where cell="', '"p4 start cycles="', '"p4 cycle n="', '"p4 done cycles="', '"p5 start ticks="',
                     '"p5 tick n="', '"p6 reset loc="', '"p8 move stage="', '"p8 stage="', '"p8 child stage="', '" id=" + P8Children[4 * k + j].GetFormID()', '"p9 dest id="',
                     '"p9 sample t="', '"p9 done t="', '"p10 state id="'):
            self.assertIn(line, QUEST, line)
        self.assertIn('" p10 sent event="', PROBE)
        # Codex review of #560: an unnamed cell is bound to FO4Port.esm by the game itself, not by the stage's record
        self.assertIn('Game.GetFormFromFile(local, "FO4Port.esm") == (c as Form)', QUEST)
        self.assertIn('" port=" + port', QUEST)
        self.assertIn("int local = c.GetFormID() % 16777216", QUEST)
        self.assertNotRegex(PROBE, r"bool \w+ = k\.SendStoryEvent")     # PC compile 2d53642: its return is not a bool
        self.assertIn('" p10 quest started id="', P10)
        self.assertIn('Event OnQuestInit()', P10)
        # P6 / P7 trials share one line shape, with the base named a / b / other / none
        self.assertIn('" trial=" + k + " base=" + Id(b) + " baselocal=" + BaseName(b)', QUEST)
        self.assertRegex(QUEST, r'Trace\("p6", head, P6List, trials\)|SpawnTrials\("p6", head, P6List, trials\)')
        self.assertIn('SpawnTrials("p7", head, P7List, trials)', QUEST)
        self.assertIn(" mode=placeatme", QUEST)

    def test_console_script_opens_the_log_before_reporting_a_missing_quest(self):
        q = PROBE[PROBE.index("Function Q(string probe) global"):PROBE.index("EndFunction")]
        self.assertLess(q.index('Debug.OpenUserLog("focc")'), q.index("Game.GetFormFromFile(2052"))
        self.assertIn('refused quest=none', q)

    def test_only_imported_base_types_and_no_unverified_calls(self):
        for text in (QUEST, PROBE, P10, ARRAY, DRIVE, NATIVE, B0):
            words = set(re.findall(r"\b([A-Z][A-Za-z]+)\b", text))
            used = words & set(PAPYRUS_TYPES)
            self.assertTrue(used <= set(mcp.IMPORTS), used - set(mcp.IMPORTS))
            for banned in ("Math.", "LeveledActor", "ActorBase", "Faction", "Debug.Trace(", "Debug.Notification"):
                self.assertNotIn(banned, text, banned)
            if text is not DRIVE:                    # unverified in Starfield: only the driver, compiled on its own, calls it
                self.assertNotIn("PathToReference(", text)
        self.assertEqual(set(mcp.IMPORTS) - set(PAPYRUS_TYPES), set())     # nothing imported that no script uses
        # the kit's own scripts are not base scripts
        self.assertFalse({"FOCC_ProbeQuest", "FOCC_Probe", "FOCC_P10Quest", "FOCC_P5_Array129", "FOCC_P9Drive", "FOCC", "FOCC_B0"}
                         & set(mcp.IMPORTS))
        # per-frame work runs from timers; the P4 and P5 loops never block a cgf call
        for f in ("P4Place()", "P4Dissolve()", "P5One()", "P9Sample()"):
            self.assertIn(f, QUEST[QUEST.index("Event OnTimer"):])
        self.assertIn("r.Disable(False)\n            r.Delete()", QUEST)       # the dissolve rule (L3): disable, then delete
        self.assertIn("Scriptname FOCC_P5_Array129 Hidden", ARRAY)
        self.assertIn("new float[129]", ARRAY)
        self.assertIn("SendStoryEvent(None, Game.GetPlayer(), None, 0, 0)", PROBE)

    def test_p9_driver_calls_path_to_reference_between_two_lines_and_logs_its_result(self):
        body = DRIVE[DRIVE.index("Function Go(int actorId, int toPlayer) global"):]
        self.assertIn("Scriptname FOCC_P9Drive Hidden", DRIVE)
        self.assertIn('FOCC_ProbeQuest q = FOCC_Probe.Q("p9")', body)          # the quest, or a logged refusal
        self.assertEqual(DRIVE.count("PathToReference("), 2)                  # the one call, and the declaration quoted
        # Starfield's three arguments (the PC's compile at c0c3c96c refused the two-argument call) and its int return
        # (Actor.psc line 490 on the PC, 28 Oct 2026: PathingResult_Success 0 .. Timeout 4), logged as result=
        self.assertIn("\n    int r = a.PathToReference(target, 1.0, 1.0)\n", body)
        self.assertIn('" result=" + r + " after="', body)
        for code in ("PathingResult_Success 0", "Failure 1", "Stopped 2", "Cleared 3", "Timeout 4"):
            self.assertIn(code, DRIVE)
        go, call, back = body.index('"p9 go actor="'), body.index("a.PathToReference("), body.index('"p9 path returned actor="')
        self.assertLess(go, call)
        self.assertLess(call, back)
        self.assertIn('q.Trace("p9 go refused actor="', body)
        self.assertIn('" after=" + (Utility.GetCurrentRealTime() - t0)', body)
        self.assertEqual(body.count('" call=" + t0'), 2)                    # the return names its own call
        self.assertNotIn("Debug.TraceUser", DRIVE)                             # every line through the quest's Trace

    def test_b0_scripts_declare_the_native_and_log_both_routes(self):
        # the native stub the SFSE plugin binds (sfse/FOCCPing): one global native, no body, declared like Game.psc's
        self.assertIn("Scriptname FOCC Hidden Native", NATIVE)
        self.assertIn("\nint Function Ping(int v) global native\n", NATIVE)
        self.assertNotIn("EndFunction", NATIVE)
        # the entry points: both resolve the quest (a logged refusal otherwise) and trace through it
        self.assertIn("Scriptname FOCC_B0 Hidden", B0)
        self.assertEqual(B0.count('FOCC_ProbeQuest q = FOCC_Probe.Q("b0")'), 2)
        self.assertEqual(B0.count("if q == None"), 2)
        self.assertNotIn("Debug.TraceUser", B0)
        # B0-1: the probe plugin's game setting read by name (Game.GetGameSettingInt, Starfield's Game.psc lines 217-221)
        self.assertIn('q.Trace("b0 gmst name=iFOCC_Pong value=" + Game.GetGameSettingInt("iFOCC_Pong"))', B0)
        # B0-2: the ping line a log-tailing plugin reads, the native call, the pong with its answer
        body = B0[B0.index("Function Ping(int v) global"):]
        self.assertIn('q.Trace("b0 ping sent=" + v)', body)
        self.assertIn("int got = FOCC.Ping(v)", body)
        self.assertIn('q.Trace("b0 pong sent=" + v + " got=" + got)', body)
        self.assertLess(body.index('"b0 ping sent="'), body.index("FOCC.Ping(v)"))
        self.assertLess(body.index("FOCC.Ping(v)"), body.index('"b0 pong sent="'))
        # the stage compiles them apart, the stub first; the console header lists them
        self.assertEqual(mcp.B0, ("FOCC", "FOCC_B0"))
        self.assertIn('cgf "FOCC_B0.Gmst"', PROBE)
        self.assertIn('cgf "FOCC_B0.Ping" 41', PROBE)

    def test_sources_are_the_seven_scripts(self):
        self.assertEqual(mcp.sources(), ["FOCC.psc", "FOCC_B0.psc", "FOCC_P10Quest.psc", "FOCC_P5_Array129.psc", "FOCC_P9Drive.psc",
                                         "FOCC_Probe.psc", "FOCC_ProbeQuest.psc"])
        self.assertEqual(set(mcp.PACKED) | {mcp.COMPILE_ONLY, mcp.DRIVE} | set(mcp.B0), {s[:-4] for s in mcp.sources()})


class StageTests(unittest.TestCase):
    def fake_tools(self, calls, array_ok, drive_ok=True, b0_ok=True):
        def fake_run(cmd, cwd=None):
            calls.append((cmd, cwd))
            if cmd[0].endswith("PapyrusCompiler.exe"):
                self.assertEqual(cwd, str(SCRIPTS))
                self.assertFalse(os.sep in cmd[1])
                open(os.path.join(cmd[-1][3:], cmd[1][:-4] + ".pex"), "wb").close()
                return "Starting 1 compile threads for 1 files...\nCompilation succeeded.\n"
            return f"{cmd[-1]} ok\n"

        def fake_capture(cmd, cwd=None):
            calls.append((cmd, cwd))
            if cmd[1] == "FOCC_P9Drive.psc":
                if drive_ok:
                    with open(os.path.join(cmd[-1][3:], "FOCC_P9Drive.pex"), "wb") as f:
                        f.write(b"drive")
                    return 0, "Compilation succeeded.\n"
                return 1, "FOCC_P9Drive.psc(30,6): PathToReference is not a function or does not exist\nNo output generated\n"
            if cmd[1] in ("FOCC.psc", "FOCC_B0.psc"):
                if b0_ok or cmd[1] == "FOCC.psc":                      # the stub always compiles; the entry points may not
                    with open(os.path.join(cmd[-1][3:], cmd[1][:-4] + ".pex"), "wb") as f:
                        f.write(cmd[1].encode())
                    return 0, "Compilation succeeded.\n"
                return 1, "FOCC_B0.psc(18,41): GetGameSettingInt is not a function or does not exist\nNo output generated\n"
            if array_ok:
                open(os.path.join(cmd[-1][3:], "FOCC_P5_Array129.pex"), "wb").close()
                return 0, "Compilation succeeded.\n"
            return 1, "FOCC_P5_Array129.psc(8,15): arrays cannot have more than 128 elements\nNo output generated\n"
        return fake_run, fake_capture

    def stage(self, d, array_ok=True, *extra, drive_ok=False, b0_ok=True):
        calls = []
        fake_run, fake_capture = self.fake_tools(calls, array_ok, drive_ok, b0_ok)
        out = os.path.join(d, "stage")
        core = os.path.join(d, "FO4TerrainCore.esm")
        with open(core, "wb") as f:
            f.write(b"core")
        with mock.patch.object(mcp.make_bridge, "run", fake_run), mock.patch.object(mcp, "run_capture", fake_capture), \
                mock.patch.object(mcp, "extract_sources", lambda z, w, imports=mcp.IMPORTS: w):
            # the build is mocked: the plugin file stands in for dotnet's output
            def build_then(cmd, cwd=None):
                if "build" in cmd:
                    with open(os.path.join(out, "FO4SFCombinedProbe.esm"), "wb") as f:
                        f.write(b"plugin")
                return fake_run(cmd, cwd)
            with mock.patch.object(mcp.make_bridge, "run", build_then):
                mcp.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe", "--stat", "Starfield.esm:1234",
                          "--lvln-b", "Starfield.esm:5678", "--starfield", os.path.join(d, "game"), *extra])
        return out, calls

    def test_stage_builds_compiles_checks_and_records(self):
        with tempfile.TemporaryDirectory() as d:
            out, calls = self.stage(d, False)
            for f in ("README.txt", "plan.json", "offline_check.txt", "compile_p5_array129.txt", "FO4SFCombinedProbe.esm",
                      "Data/Scripts/FOCC_ProbeQuest.pex", "Data/Scripts/FOCC_Probe.pex", "Data/Scripts/FOCC_P10Quest.pex",
                      "FOCC_ProbeQuest.psc", "FOCC_Probe.psc", "FOCC_P10Quest.psc", "FOCC_P5_Array129.psc"):
                self.assertTrue(os.path.exists(os.path.join(out, f)), f)
            self.assertFalse(os.path.exists(os.path.join(out, "Data", "Scripts", "FOCC_P5_Array129.pex")))   # never packed
            plan = json.load(open(os.path.join(out, "plan.json"), encoding="utf-8"))
            self.assertEqual(plan["kind"], "combined-probe")
            self.assertEqual(plan["variant"], "default")
            self.assertEqual(plan["skip"], [])
            self.assertIs(plan["lvln_conditions_written"], True)
            self.assertIs(plan["sm_nodes_written"], True)
            self.assertEqual(plan["build_id"], plan["plugin_sha256"][:8])
            self.assertEqual(plan["outputs"]["FO4SFCombinedProbe.esm"], plan["plugin_sha256"])
            self.assertEqual(sorted(plan["outputs"]), ["Data/Scripts/FOCC.pex", "Data/Scripts/FOCC_B0.pex", "Data/Scripts/FOCC_P10Quest.pex",
                                                       "Data/Scripts/FOCC_Probe.pex", "Data/Scripts/FOCC_ProbeQuest.pex",
                                                       "FO4SFCombinedProbe.esm"])
            self.assertEqual(sorted(plan["inputs"]["sources"]), mcp.sources())
            self.assertEqual(plan["inputs"]["core"]["sha256"], mcp.sha256(os.path.join(d, "FO4TerrainCore.esm")))
            self.assertEqual(plan["array129"], {"script": "FOCC_P5_Array129", "compiled": False, "exit_code": 1,
                                                "output": "compile_p5_array129.txt"})
            self.assertTrue(plan["sendstoryevent_compiles"])
            self.assertEqual(plan["entry_points"], list(mcp.ENTRY_POINTS))
            self.assertEqual(plan["ids"]["quest"], 0x804)
            self.assertEqual(plan["bases"], {"npc": "Starfield.esm:2B211C", "lvln_a": "Starfield.esm:2B211C",
                                             "lvln_b": "Starfield.esm:5678", "stat": "Starfield.esm:1234"})
            report = open(os.path.join(out, "compile_p5_array129.txt"), encoding="utf-8").read()
            self.assertIn("exit code 1", report)
            self.assertIn("more than 128 elements", report)
            self.assertIn("refused:", report)
            # the order of the tool calls: build, three compiles, the array compile, the driver, B0's two, check
            kinds = [("build" if "build" in c[0] else "check" if "check" in c[0] else c[0][1]) for c in calls]
            self.assertEqual(kinds, ["build", "FOCC_ProbeQuest.psc", "FOCC_Probe.psc", "FOCC_P10Quest.psc", "FOCC_P5_Array129.psc",
                                     "FOCC_P9Drive.psc", "FOCC.psc", "FOCC_B0.psc", "check"])
            # B0's two compiled: both packed and pinned, the plan names the entry-point script
            self.assertEqual(plan["b0"], {"scripts": ["FOCC", "FOCC_B0"], "compiled": True, "exit_code": 0, "output": "compile_b0.txt"})
            self.assertEqual(plan["scripts"]["b0"], "FOCC_B0")
            for name in ("FOCC", "FOCC_B0"):
                pex = os.path.join(out, "Data", "Scripts", name + ".pex")
                self.assertEqual(plan["outputs"][f"Data/Scripts/{name}.pex"], mcp.sha256(pex))
            b0_report = open(os.path.join(out, "compile_b0.txt"), encoding="utf-8").read()
            self.assertIn("--- FOCC.psc\nexit code 0", b0_report)
            self.assertIn("--- FOCC_B0.psc\nexit code 0", b0_report)
            self.assertIn("compiled: FOCC.Ping is declared", b0_report)
            readme = open(os.path.join(out, "README.txt"), encoding="utf-8").read()
            self.assertIn("Data\\Scripts\\FOCC.pex, Data\\Scripts\\FOCC_B0.pex", readme)
            self.assertIn('cgf "FOCC_B0.Gmst" needs no SFSE plugin', readme)
            # the driver refused: only it is missing, and the stage says so
            self.assertEqual(plan["p9_drive"], {"script": "FOCC_P9Drive", "compiled": False, "exit_code": 1,
                                                "output": "compile_p9_drive.txt"})
            self.assertIsNone(plan["scripts"]["p9_drive"])
            self.assertFalse(os.path.exists(os.path.join(out, "Data", "Scripts", "FOCC_P9Drive.pex")))
            self.assertIn("refused: this stage has no P9 scripted driver",
                          open(os.path.join(out, "compile_p9_drive.txt"), encoding="utf-8").read())
            self.assertIn("no scripted P9", open(os.path.join(out, "README.txt"), encoding="utf-8").read())
            build_cmd, check_cmd = calls[0][0], calls[-1][0]
            self.assertIn("--out", build_cmd)
            for opt in ("--sf", "--core", "--stat", "--lvln-b", "--npc", "--lvln-a", "--plugin", "--world", "--location"):
                self.assertIn(opt, build_cmd)
                self.assertIn(opt, check_cmd)
            self.assertEqual(build_cmd[build_cmd.index("--sf") + 1], os.path.join(d, "game", "Data", "Starfield.esm"))
            self.assertEqual(check_cmd[check_cmd.index("check") + 1], os.path.join(out, "FO4SFCombinedProbe.esm"))
            self.assertNotIn("--p3-cells", build_cmd)
            self.assertIn("FOCC rt=", open(os.path.join(out, "README.txt"), encoding="utf-8").read())
            with self.assertRaises(SystemExit):                              # never into a used folder
                self.stage(d)

    def test_a_compiled_driver_is_packed_and_pinned(self):
        with tempfile.TemporaryDirectory() as d:
            out, _calls = self.stage(d, True, drive_ok=True)
            plan = json.load(open(os.path.join(out, "plan.json"), encoding="utf-8"))
            self.assertTrue(plan["p9_drive"]["compiled"])
            self.assertEqual(plan["scripts"]["p9_drive"], "FOCC_P9Drive")
            pex = os.path.join(out, "Data", "Scripts", "FOCC_P9Drive.pex")
            self.assertEqual(plan["outputs"]["Data/Scripts/FOCC_P9Drive.pex"], mcp.sha256(pex))   # probe_install packs it
            self.assertIn("compiled: Actor.PathToReference", open(os.path.join(out, "compile_p9_drive.txt"), encoding="utf-8").read())
            self.assertIn("Data\\Scripts\\FOCC_P9Drive.pex", open(os.path.join(out, "README.txt"), encoding="utf-8").read())

    def test_a_refused_b0_leaves_both_scripts_out(self):
        with tempfile.TemporaryDirectory() as d:
            out, _calls = self.stage(d, True, b0_ok=False)
            plan = json.load(open(os.path.join(out, "plan.json"), encoding="utf-8"))
            self.assertEqual(plan["b0"], {"scripts": ["FOCC", "FOCC_B0"], "compiled": False, "exit_code": 1, "output": "compile_b0.txt"})
            self.assertIsNone(plan["scripts"]["b0"])
            for name in ("FOCC", "FOCC_B0"):                      # the stub compiled, but nothing of B0 is packed without its caller
                self.assertFalse(os.path.exists(os.path.join(out, "Data", "Scripts", name + ".pex")), name)
                self.assertNotIn(f"Data/Scripts/{name}.pex", plan["outputs"])
            report = open(os.path.join(out, "compile_b0.txt"), encoding="utf-8").read()
            self.assertIn("--- FOCC.psc\nexit code 0", report)
            self.assertIn("--- FOCC_B0.psc\nexit code 1\nFOCC_B0.psc(18,41): GetGameSettingInt", report)
            self.assertIn("refused: this stage has no B0 scripts", report)
            self.assertIn("refused, not packed: no B0", open(os.path.join(out, "README.txt"), encoding="utf-8").read())

    def test_variant_and_skip_reach_the_tool_and_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            port = os.path.join(d, "FO4Port.esm")
            with open(port, "wb") as f:
                f.write(b"port")
            out, calls = self.stage(d, True, "--p3-cells", "--port", port, "--skip", "sm")
            plan = json.load(open(os.path.join(out, "plan.json"), encoding="utf-8"))
            self.assertEqual(plan["variant"], "p3cells")
            self.assertEqual(plan["skip"], ["sm"])
            self.assertIs(plan["sm_nodes_written"], False)                 # what probes.check_p10 reads as blocked
            self.assertIs(plan["lvln_conditions_written"], True)
            self.assertEqual(plan["inputs"]["port"]["sha256"], mcp.sha256(port))
            self.assertTrue(plan["array129"]["compiled"])
            build_cmd = calls[0][0]
            self.assertEqual(build_cmd[build_cmd.index("--port") + 1], port)
            self.assertIn("--p3-cells", build_cmd)
            self.assertEqual(build_cmd[build_cmd.index("--skip") + 1], "sm")
            self.assertIn("compiled: no compile-time cap", open(os.path.join(out, "compile_p5_array129.txt"), encoding="utf-8").read())

    def test_refusals(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):                              # no --lvln-b and no --skip lvln
                mcp.main(["stage", "--core", "c.esm", "--out", os.path.join(d, "x"), "--stat", "Starfield.esm:1"])
            with self.assertRaises(SystemExit):                              # --p3-cells without --port
                mcp.main(["stage", "--core", "c.esm", "--out", os.path.join(d, "y"), "--stat", "Starfield.esm:1", "--skip", "lvln", "--p3-cells"])
            self.assertFalse(os.path.exists(os.path.join(d, "y", "plan.json")))

    def test_tool_defaults_follow_the_chosen_game_folder(self):
        # Codex P2 on #431: --starfield elsewhere still looked for the compiler under make_bridge's default install.
        seen = {}
        with mock.patch.object(mcp, "stage", lambda a: seen.update(compiler=a.compiler, zip=a.content_resources)):
            mcp.main(["stage", "--core", "c.esm", "--out", "x", "--stat", "Starfield.esm:1", "--skip", "lvln",
                      "--starfield", "E:\\Games\\Starfield"])
        self.assertEqual(seen["compiler"], os.path.join("E:\\Games\\Starfield", "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
        self.assertEqual(seen["zip"], os.path.join("E:\\Games\\Starfield", "Tools", "ContentResources.zip"))

    def test_compile_commands_name_the_flags_and_both_include_folders(self):
        cmd = mcp.compile_cmd("PapyrusCompiler.exe", "FOCC_Probe", "SRC", "OUT")
        self.assertEqual(cmd, ["PapyrusCompiler.exe", "FOCC_Probe.psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={mcp.HERE};SRC", "-o=OUT"])
        self.assertEqual(set(mcp.IMPORTS) - set(mcp.make_bridge.IMPORTS), {"Keyword", "Package"})


if __name__ == "__main__":
    unittest.main()
