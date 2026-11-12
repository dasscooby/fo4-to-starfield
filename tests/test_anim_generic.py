"""The generic-graph control (FAL-489, the Scribe's vault111-console-stages rev 2): its script's ids and calls against the writer's
(dotnet/AnimGenericControl), the clip copies (A, B as the vanilla bytes, C = A and D = B with the .afx renamed), the graph path lookup,
the plugin the tool writes and the stage with a fake Papyrus compiler and synthetic archives (never a game; the real compile, the real
Starfield.esm and the real archives are the PC's job). The dotnet tests skip without the .NET SDK."""
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
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_anim_generic as mag  # noqa: E402
import make_anim_probe as map_  # noqa: E402
import vault111_anim_graphs as graphs  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402
from test_anim_probe import BASES, fake_compiler, fake_sources  # noqa: E402

PSC = (ROOT / "scripts" / "newgame" / "FO4SF_AnimGenericQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "AnimGenericControl" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFAnimGeneric.esm"
VANILLA_FOLDER = "Props\\ArtifactHolder\\Animations"                      # what the tool's fixture ACTI names as its CNAM
GRAPH_ENTRY = "Meshes\\AnimTextData\\Tables\\Graphs\\GenericStateGraph01.agx"
ANAM = "AnimTextData\\Tables\\Graphs\\GenericStateGraph01.agx"


def const_ids(text):
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


def afx(tag, extra="<audios><audio><frame>1</frame><foley>QST_X</foley></audio></audios>"):
    return f"<root><is_state>1</is_state><tag>{tag}</tag><filename>{tag}.af</filename>{extra}</root>".encode()


def vanilla_files(folder=VANILLA_FOLDER, lower=True, skip=()):
    """{archive entry: bytes}: the vanilla holder's four .af and four .afx (the game stores them lower case)."""
    files = {}
    for name in mag.SOURCES:
        for ext, data in ((".af", b"AF-" + name.encode()), (".afx", afx(name))):
            entry = mag.meshes_name(folder, name.lower() if lower else name, ext)
            if entry not in skip:
                files[entry] = data
    return files


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_stages_and_log_are_the_tools_and_the_readers(self):
        ids = const_ids(TOOL_SRC)
        self.assertEqual((ids["QuestId"], ids["ControlId"], ids["VanillaId"]), (0x800, 0x801, 0x1CCAC2))
        self.assertIn("int ControlId = 0x801", PSC)                       # the control ACTI of our plugin, not the vanilla form
        self.assertNotIn("0x1CCAC2", PSC.split(";")[0])
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', PSC)
        self.assertIn("Game.GetFormFromFile(ControlId, ProbePlugin)", PSC)
        self.assertTrue(PSC.startswith("Scriptname FO4SF_AnimGenericQuest extends Quest"))
        self.assertIn('Script = "FO4SF_AnimGenericQuest"', TOOL_SRC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 40, 60])
        self.assertIn('string LogName = "FO4SFAnimG"', PSC)
        self.assertTrue(mag.LOG.endswith("FO4SFAnimG.0.log"))
        self.assertIn('"FO4SFANIM rt="', PSC)
        self.assertIn('" end=true"', PSC)
        for e in map_.anim_probe_log.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e}[ "]')

    def test_the_doc_comment_stays_under_the_repos_papyrus_limit(self):
        i = PSC.index("{")
        j = PSC.index("}", i)
        self.assertLess(len(PSC[i + 1:j].encode()), 3072)                   # tests/test_papyrus_strings.py (the 31 Oct load crash)

    def test_no_property_the_wait_form_is_never_called_and_the_master_is_starfield_only(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        self.assertNotRegex("\n".join(ln.split(";")[0] for ln in PSC.splitlines() if not ln.startswith(" ")), r"PlayAnimationAndWait\(")
        self.assertIn("masters are not exactly [Starfield.esm]", TOOL_SRC)
        self.assertIn("records of another plugin (overrides)", TOOL_SRC)    # nothing of the vanilla game is overridden

    def test_each_play_stage_sends_one_name_in_the_order_the_pc_read_from_the_graphs_links(self):
        """Claude, #755, 12 Nov 20:40 UTC: Play01..Play05, then the direct StateC_Play, StateD_Play, StateC_Idle, StateD_Idle; one stage per call."""
        names = re.findall(r'PlayNames\[(\d)\] = "(\w+)"', PSC)
        self.assertEqual([n for _, n in names], ["Play01", "Play02", "Play03", "Play04", "Play05", "StateC_Play", "StateD_Play", "StateC_Idle", "StateD_Idle"])
        self.assertIn("PlayOne(stage, PlayNames[stage - 21])", PSC)
        self.assertIn("elseif stage >= 21 && stage <= 29", PSC)                  # nine names, stages 21..29
        self.assertIn("PlayNames = new string[9]", PSC)
        self.assertEqual(PSC.count("TestRef.PlayAnimation(n)"), 1)
        self.assertIn("bool ok = TestRef.PlayAnimation(n)", PSC)

    def test_the_registered_events_are_the_scribes_list_and_trans03(self):
        events = re.findall(r'EventNames\[\d+\] = "(\w+)"', PSC)
        scribe = ["Trans01", "Done", "Trans02", "IsOn", "IsOff", "AnimFinish", "IdleStop", "StateA_Idle", "StateA_Play", "StateB_Idle", "StateB_Play",
                  "StateC_Idle", "StateC_Play", "StateD_Idle", "StateD_Play", "Play01", "Play02", "Play03", "Play04"]
        for e in scribe + ["Trans03", "Play05", "TurnOn", "TurnOff", "Opened"]:    # the events that enter states in the real links (Claude, 12 Nov 20:40)
            self.assertIn(e, events)
        self.assertEqual(len(events), len(set(events)))
        self.assertIn(f"new string[{len(events)}]", PSC)
        self.assertIn("RegisterForAnimationEvent(r, n)", PSC)
        self.assertIn("p.PlaceAtMe(base, 1, true, false, false)", PSC)
        self.assertIn("Event OnAnimationEvent(ObjectReference akSource, string asEventName)", PSC)

    def test_the_committed_script_compiles_alone_every_optional_and_void_line_is_a_comment(self):
        self.assertEqual(map_.enable(PSC, []), PSC)
        self.assertEqual(map_.optional_names(PSC), ["ObjectReference.MoveTo", "ObjectReference.Delete"])
        self.assertEqual(len(map_.VOID.findall(PSC)), 2)
        self.assertIn(map_.BOOL_LINE, PSC)                                  # the register shape make_anim_probe.reg_shape swaps

    def test_every_finding_also_shows_on_screen_for_a_session_with_logging_off(self):
        self.assertIn('Debug.Notification("AP " + msg)', PSC)
        for what in ('Say("EV " + asEventName + " w" + ListenStage)', 'Say("PLAY s" + stage + " " + n + " ok=" + ok)', 'Say("W s" + stage + " quiet")',
                     'Say("REG s" + stage + " " + okCount + "/" + EventNames.Length + " true")'):
            self.assertIn(what, PSC)


class ClipTests(unittest.TestCase):
    def test_the_eight_clips_are_a_b_and_two_copies(self):
        self.assertEqual([c for c, _ in mag.CLIPS], ["StateA_Idle", "StateA_Play", "StateB_Idle", "StateB_Play",
                                                      "StateC_Idle", "StateC_Play", "StateD_Idle", "StateD_Play"])
        self.assertEqual(dict(mag.CLIPS)["StateC_Play"], "StateA_Play")
        self.assertEqual(dict(mag.CLIPS)["StateD_Idle"], "StateB_Idle")

    def test_a_copy_gets_its_own_tag_and_file_name_and_keeps_the_rest(self):
        out = mag.rename_afx(afx("StateA_Play"), "StateC_Play")
        root = ET.fromstring(out)
        self.assertEqual((root.findtext("tag"), root.findtext("filename"), root.findtext("is_state")), ("StateC_Play", "StateC_Play.af", "1"))
        self.assertEqual(root.find("audios/audio/foley").text, "QST_X")      # sounds stay
        self.assertEqual(root.find("audios/audio/frame").text, "1")

    def test_an_afx_that_is_not_the_vanilla_shape_is_refused_not_guessed(self):
        with self.assertRaisesRegex(ValueError, "not XML"):
            mag.rename_afx(b"\0\1binary", "StateC_Play")
        with self.assertRaisesRegex(ValueError, "no <tag> or no <filename>"):
            mag.rename_afx(b"<root><other>x</other></root>", "StateC_Play")

    def test_a_vanilla_afx_that_is_not_xml_is_refused_where_a_copy_needs_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            vanilla = {n: (b"AF-" + n.encode(), afx(n)) for n in mag.SOURCES}
            vanilla["StateB_Play"] = (b"AF", b"\0\1binary")           # only D copies it: A, B and C are written, D is refused
            with self.assertRaisesRegex(ValueError, "not XML"):
                mag.write_clips(tmp, vanilla)

    def test_write_clips_copies_a_and_b_unchanged_and_renames_c_and_d_only_in_the_afx(self):
        with tempfile.TemporaryDirectory() as tmp:
            vanilla = {n: (b"AF-" + n.encode(), afx(n)) for n in mag.SOURCES}
            report = mag.write_clips(tmp, vanilla)
            folder = Path(tmp, *mag.CLIP_DIR.split("/"))
            self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(f"{n}{e}" for n, _ in mag.CLIPS for e in (".af", ".afx")))
            for src in mag.SOURCES:                                          # A and B: the vanilla bytes
                self.assertEqual((folder / f"{src}.af").read_bytes(), vanilla[src][0])
                self.assertEqual((folder / f"{src}.afx").read_bytes(), vanilla[src][1])
            self.assertEqual((folder / "StateC_Play.af").read_bytes(), vanilla["StateA_Play"][0])          # C = A, the .af untouched
            self.assertEqual((folder / "StateD_Idle.af").read_bytes(), vanilla["StateB_Idle"][0])          # D = B
            self.assertEqual(report["StateC_Play"], {"copy_of": "StateA_Play", "afx_tag": "StateC_Play", "afx_filename": "StateC_Play.af"})
            self.assertEqual(report["StateA_Play"]["afx_tag"], "StateA_Play")

    def test_the_vanilla_clips_are_found_case_blind_and_a_missing_one_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "Starfield - Meshes01.ba2")
            Path(p).write_bytes(general_archive(vanilla_files()))
            got, hashes, problems = mag.read_vanilla(graphs.open_archives([p]), VANILLA_FOLDER)
            self.assertEqual((sorted(got), problems), (sorted(mag.SOURCES), []))
            self.assertEqual(len(hashes), 8)
            skip = mag.meshes_name(VANILLA_FOLDER, "stateb_play", ".afx")
            Path(p).write_bytes(general_archive(vanilla_files(skip=(skip,))))
            got, hashes, problems = mag.read_vanilla(graphs.open_archives([p]), VANILLA_FOLDER)
            self.assertEqual(sorted(got), ["StateA_Idle", "StateA_Play", "StateB_Idle"])
            self.assertEqual(len(problems), 1)
            self.assertIn("stateb_play.afx: not in the archives read", problems[0].lower().replace("meshes\\props\\artifactholder\\animations\\", ""))

    def test_the_graph_path_is_the_archives_without_the_meshes_prefix_and_absent_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "Starfield - Animations.ba2")
            Path(p).write_bytes(general_archive({GRAPH_ENTRY: b"<root/>"}))
            self.assertEqual(mag.graph_anam(graphs.open_archives([p])), (ANAM, GRAPH_ENTRY))
            Path(p).write_bytes(general_archive({"Meshes\\AnimTextData\\Tables\\Graphs\\Stages.agx": b"<root/>"}))
            self.assertEqual(mag.graph_anam(graphs.open_archives([p])), (None, None))

    def test_parse_info_reads_key_value_lines(self):
        self.assertEqual(mag.parse_info("edid=X\nmodel=Meshes/a.nif\ncnam=Props\\A\\Animations\nnoise\n"),
                         {"edid": "X", "model": "Meshes/a.nif", "cnam": "Props\\A\\Animations"})


class ToolBase(unittest.TestCase):
    """The built tool and a synthetic Starfield.esm; no tests of its own."""
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "AnimGenericControl"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/AnimGenericControl/bin/Release/net9.0/AnimGenericControl.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-animgen-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.master = cls.root / "m" / "Starfield.esm"
        r = cls.run_tool("fixture", cls.root / "m")
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)


class ToolTests(ToolBase):
    def test_info_names_the_vanilla_holder(self):
        info = mag.parse_info(self.run_tool("info", self.master).stdout)
        self.assertEqual(info["edid"], "IndIntAddonArtifactHolder01")
        self.assertEqual(info["cnam"], VANILLA_FOLDER)
        self.assertTrue(info["anam"].lower().endswith("activatorstategraph01.agx"))

    def test_build_and_check(self):
        out = self.root / "b1"
        proc = self.run_tool("build", self.master, out, ANAM, mag.CNAM)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("copied from ACTI 1CCAC2 IndIntAddonArtifactHolder01", proc.stdout)
        check = self.run_tool("check", out / PLUGIN, self.master, ANAM, mag.CNAM)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("scripts [FO4SF_AnimGenericQuest (0 properties)]", check.stdout)
        self.assertIn(f"ACTI FO4SF_AnimGenericControl model Meshes/Props/ArtifactHolder/ArtifactHolder01.nif components 1 graph ANAM {ANAM} "
                      f"BNAM Props\\ArtifactHolder\\CharacterAssets\\skeleton.rig CNAM {mag.CNAM}", check.stdout)       # the vanilla model and rig, our graph and folder

    def test_the_plugin_adds_one_quest_and_one_acti_and_overrides_none(self):
        """Raw bytes: every record carries load index 1 (our own plugin; Starfield.esm is master 0); no REFR, no CELL."""
        out = self.root / "b2"
        self.assertEqual(self.run_tool("build", self.master, out, ANAM, mag.CNAM).returncode, 0)
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
        self.assertEqual({k: v for k, v in kinds.items() if k != b"TES4"}, {b"QUST": 1, b"ACTI": 1})
        self.assertEqual(sorted(ids), [0x01000800, 0x01000801])

    def test_the_vanilla_graph_and_the_vanilla_clip_folder_are_refused(self):
        proc = self.run_tool("build", self.master, self.root / "b3", "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx", mag.CNAM)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("is not genericstategraph01", proc.stderr)
        proc = self.run_tool("build", self.master, self.root / "b4", ANAM, VANILLA_FOLDER)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("must be our own, not the vanilla holder's", proc.stderr)
        self.assertFalse((self.root / "b3").exists() or (self.root / "b4").exists())

    def test_check_names_a_wrong_folder(self):
        out = self.root / "b5"
        self.assertEqual(self.run_tool("build", self.master, out, ANAM, mag.CNAM).returncode, 0)
        proc = self.run_tool("check", out / PLUGIN, self.master, ANAM, "Other\\Folder")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("clip folder is FO4SFAnimGeneric\\Animations, not Other\\Folder", proc.stdout)

    def test_a_master_without_the_vanilla_holder_graph_is_refused(self):
        other = self.root / "o"
        other.mkdir()
        shutil.copy(self.master, other / "Starfield.esm")
        raw = bytearray((other / "Starfield.esm").read_bytes())
        i = raw.find(b"ActivatorStateGraph01")
        self.assertGreater(i, 0)
        raw[i:i + len(b"ActivatorStateGraph01")] = b"SimpleOpenClose01xxxx"[:len(b"ActivatorStateGraph01")]      # same length: Mutagen aborts otherwise
        (other / "Starfield.esm").write_bytes(bytes(raw))
        proc = self.run_tool("build", other / "Starfield.esm", self.root / "b6", ANAM, mag.CNAM)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("not activatorstategraph01", proc.stderr)


class StageTests(ToolBase):
    """The whole stage on a synthetic Starfield.esm, synthetic archives next to it and the fake compiler."""
    def data_dir(self, name, files=None, graph=True):
        d = self.root / name
        d.mkdir()
        shutil.copy(self.master, d / "Starfield.esm")
        (d / "Starfield - Meshes01.ba2").write_bytes(general_archive(files if files is not None else vanilla_files()))
        (d / "Starfield - Animations.ba2").write_bytes(general_archive({GRAPH_ENTRY: b"<root/>"} if graph else {"Meshes\\Other.agx": b"<root/>"}))
        return d

    def args(self, out, d, **kw):
        z = self.root / (Path(out).name + "-cr.zip")
        fake_sources(z)
        base = ["stage", "--out", str(out), "--starfield", str(d / "Starfield.esm"), "--compiler", str(fake_compiler(self.root)), "--content-resources", str(z)]
        return base + kw.get("extra", [])

    def test_stage_builds_copies_the_clips_compiles_and_pins_every_file(self):
        d = self.data_dir("d1")
        out = self.root / "staged"
        self.assertEqual(mag.main(self.args(out, d)), 0)
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual((plan["kind"], plan["plugins"], plan["cnam"]), ("anim-generic", [PLUGIN], mag.CNAM))
        self.assertEqual(plan["graph"], {"anam": ANAM, "archive_entry": GRAPH_ENTRY})
        self.assertEqual(plan["optional"]["ObjectReference.MoveTo"], "kept")
        self.assertTrue(plan["optional"]["ObjectReference.Delete"].startswith("declared but did not compile"))
        want = {PLUGIN, "Data/Scripts/FO4SF_AnimGenericQuest.pex"} | {f"{mag.CLIP_DIR}/{n}{e}" for n, _ in mag.CLIPS for e in (".af", ".afx")}
        self.assertEqual(set(plan["outputs"]), want)
        self.assertEqual(len(plan["vanilla_clips"]), 8)                                                 # every copied vanilla file is hashed
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mag.sha256(str(d / "Starfield.esm")))
        self.assertEqual(plan["archives"], ["Starfield - Animations.ba2", "Starfield - Meshes01.ba2"])
        self.assertEqual(mag.verify_stage(str(out), plan, str(d)), [])
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        folder = out / Path(*mag.CLIP_DIR.split("/"))
        self.assertEqual((folder / "StateA_Play.af").read_bytes(), b"AF-StateA_Play")                   # the vanilla bytes
        self.assertEqual((folder / "StateC_Play.af").read_bytes(), b"AF-StateA_Play")                   # C = A
        self.assertEqual(ET.fromstring((folder / "StateD_Idle.afx").read_bytes()).findtext("tag"), "StateD_Idle")
        readme = (out / "README.txt").read_text()
        self.assertIn(ANAM, readme)
        self.assertIn("never committed", readme)
        staged_psc = (out / "FO4SF_AnimGenericQuest.psc").read_text()
        self.assertIn("        TestRef.MoveTo(p,", staged_psc)
        with self.assertRaises(SystemExit):                                                              # an earlier stage is never overwritten
            mag.main(self.args(out, d))

    def test_a_missing_vanilla_clip_stops_the_stage_and_publishes_nothing(self):
        skip = mag.meshes_name(VANILLA_FOLDER, "statea_play", ".af")
        d = self.data_dir("d2", vanilla_files(skip=(skip,)))
        out = self.root / "staged-miss"
        with self.assertRaises(SystemExit) as ctx:
            mag.main(self.args(out, d))
        self.assertIn("statea_play.af: not in the archives read", str(ctx.exception).lower().replace("meshes\\props\\artifactholder\\animations\\", ""))
        self.assertIn("nothing invented", str(ctx.exception))
        self.assertFalse(out.exists())
        self.assertEqual([p.name for p in self.root.glob("staged-miss.partial*")], [])

    def test_a_missing_graph_stops_the_stage_with_the_archive_to_pass(self):
        d = self.data_dir("d3", graph=False)
        out = self.root / "staged-nograph"
        with self.assertRaises(SystemExit) as ctx:
            mag.main(self.args(out, d))
        self.assertIn("genericstategraph01.agx is not in the archives read", str(ctx.exception))
        self.assertIn("Starfield - Animations.ba2", str(ctx.exception))
        self.assertFalse(out.exists())

    def test_an_afx_that_is_not_xml_stops_the_stage(self):
        files = vanilla_files()
        files[mag.meshes_name(VANILLA_FOLDER, "statea_idle", ".afx")] = b"\0\1binary"
        d = self.data_dir("d4", files)
        with self.assertRaises(SystemExit) as ctx:
            mag.main(self.args(self.root / "staged-badafx", d))
        self.assertIn("is not the shape the copies need", str(ctx.exception))

    def test_a_changed_stage_is_refused_by_verify(self):
        d = self.data_dir("d5")
        out = self.root / "staged-v"
        mag.main(self.args(out, d))
        plan = json.loads((out / "plan.json").read_text())
        with open(out / Path(*mag.CLIP_DIR.split("/")) / "StateC_Play.af", "ab") as f:
            f.write(b"!")
        self.assertIn("changed after the stage", " ".join(mag.verify_stage(str(out), plan)))
        self.assertIn("is not the generic-graph control's", " ".join(mag.verify_stage(str(out), dict(plan, kind="anim-probe"))))
        short = dict(plan, outputs={k: v for k, v in plan["outputs"].items() if "StateD_Play.afx" not in k})
        self.assertIn("StateD_Play.afx not pinned", " ".join(mag.verify_stage(str(out), short)))

    def test_no_archive_matching_the_pattern_is_said(self):
        d = self.data_dir("d6")
        with self.assertRaises(SystemExit) as ctx:
            mag.main(self.args(self.root / "staged-noarc", d, extra=["--game-archive", "Nothing*.ba2"]))
        self.assertIn("no archive matched", str(ctx.exception))

    def test_log_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "log.txt")
            self.assertEqual(mag.main(["log", "--file", f]), 2)
            Path(f).write_text("[11/12/2026 - 06:00:00AM] FO4SFANIM rt=1.0 spawn stage=10 base=77 ref=99 moved=true persist=true end=true\n", encoding="utf-8")
            self.assertEqual(mag.main(["log", "--file", f]), 0)
            Path(f).write_text("nothing here\n", encoding="utf-8")
            self.assertEqual(mag.main(["log", "--file", f]), 1)

    def test_the_precheck_runs_on_the_generic_script(self):
        z = self.root / "cr-pre.zip"
        fake_sources(z)
        out = self.root / "pre.json"
        self.assertEqual(mag.main(["precheck", "--content-resources", str(z), "--out", str(out)]), 0)
        r = json.loads(out.read_text())
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["optional"], {"ObjectReference.MoveTo": True, "ObjectReference.Delete": True})


if __name__ == "__main__":
    unittest.main()
