"""The cog door probe (FAL-756): its quest script's ids and stages against the writer's (dotnet/CogDoorProbe), the plugin tool on a
synthetic FO4Port.esm, the stager with a fake converter and a fake Papyrus compiler, the plan verification and the log reader (never a
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_cog_door as mcd  # noqa: E402
from test_anim_probe import BASES, fake_compiler, fake_sources  # noqa: E402

BASES_DOOR = {**BASES, "ObjectReference": BASES["ObjectReference"] + "int Function GetOpenState() native\nFunction SetOpen(bool b) native\n"}
PSC = (ROOT / "scripts" / "newgame" / "FO4SF_CogDoorQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "CogDoorProbe" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFCogDoor.esm"
OUT = "fo4port/interiors/vault/doors/vltgeardoor/vltgeardoor01_anim"
MODEL = "fo4port\\interiors\\vault\\doors\\vltgeardoor\\vltgeardoor01_anim.nif"
RIG = "fo4port\\interiors\\vault\\doors\\vltgeardoor\\vltgeardoor01_anim\\characterassets\\skeleton.rig"
ANIMS = "fo4port\\interiors\\vault\\doors\\vltgeardoor\\vltgeardoor01_anim\\animations"
MARGS = ["--model", MODEL, "--rig", RIG, "--anims", ANIMS]


def norm(text):
    return text.replace("\\", "/")


class ScriptTests(unittest.TestCase):
    def test_ids_stages_and_layout_match_the_tool(self):
        self.assertTrue(PSC.startswith("Scriptname FO4SF_CogDoorQuest extends Quest"))
        self.assertIn('Script = "FO4SF_CogDoorQuest"', TOOL_SRC)
        self.assertIn("const uint QuestId = 0x800", TOOL_SRC)
        self.assertIn('string ProbePlugin = "FO4SFCogDoor.esm"', PSC)
        self.assertIn('string RefPlugin = "FO4Port.esm"', PSC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 20, 30, 40, 50])
        self.assertIn(f"StageList = new int[{len(ran)}]", PSC)
        self.assertIn(f"DoneList = new bool[{len(ran)}]", PSC)
        self.assertEqual(mcd.DEFAULT_REF, "00126D")
        self.assertIn('DefaultRef = "00126D"', TOOL_SRC)

    def test_no_property_one_ref_line_and_the_reference_is_found_not_held(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        self.assertEqual(len(mcd.REF_LINE.findall(PSC)), 1)
        self.assertIn("Game.GetFormFromFile(RefId, RefPlugin) as ObjectReference", PSC)
        self.assertIsNone(re.search(r"(?m)^ObjectReference \w+ *(=|$)", PSC))             # no script-level reference variable: it would make a temporary reference persistent

    def test_each_stage_does_the_one_thing_the_card_says_and_the_open_state_is_read_around_it(self):
        step = PSC.split("Function Step(int stage)")[1].split("EndFunction")[0]
        self.assertIn("d.SetOpen(true)", step.split("stage == 20")[1].split("elseif")[0])
        self.assertIn("d.SetOpen(false)", step.split("stage == 30")[1].split("elseif")[0])
        self.assertIn("d.Activate(p, false)", step.split("stage == 40")[1])
        self.assertEqual(PSC.count(".SetOpen("), 2)
        self.assertEqual(PSC.count(".Activate("), 1)
        self.assertIn('Reading("read", stage, d)', step)                                  # stages 10 and 50 change nothing
        self.assertEqual(step.count('Reading("after", stage, d)'), 3)
        reading = PSC.split("Function Reading")[1].split("EndFunction")[0]
        self.assertIn("openstate=", reading)
        self.assertIn("Debug.Notification", PSC)                                          # every finding is also on screen
        watch = PSC.split("Function Watch()")[1].split("EndFunction")[0]
        self.assertIn('" after=" + after', watch)
        self.assertIn("watch done", watch)

    def test_every_native_the_script_calls_is_in_the_required_list(self):
        used = set(re.findall(r"\b(?:d|p|Game|Debug|Utility)\.(\w+)\(", PSC)) | {"GetStageDone", "StartTimer", "GetFormID"}
        listed = {n for names in mcd.REQUIRED.values() for n in names}
        self.assertEqual(sorted(used - listed), [])


class StageCommandTextTests(unittest.TestCase):
    """The PC's 14 Nov session: `setstage FO4SF_CogDoorQuest <n>` is refused ("Item ... not found for parameter Quest", nothing set); the form id works."""

    def test_the_readme_and_the_doc_give_the_form_id_form_and_name_the_refused_one(self):
        for rel in ("scripts/newgame/make_cog_door.py", "docs/research/cog-door-probe.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("setstage <quest form id> <n>", text, rel)
            self.assertIn("000800", text, rel)
            self.assertIn("not found for parameter Quest", text, rel)
            # the name form may appear only as the refused one: "refused" follows it within 120 characters
            for m in re.finditer(re.escape("setstage FO4SF_CogDoorQuest <n>"), text):
                self.assertIn("refused", text[m.end():m.end() + 120], f"{rel}: the name form is given as an instruction")


class RefIdTests(unittest.TestCase):
    def test_the_ref_id_is_written_once_and_a_bad_one_is_refused(self):
        on = mcd.set_ref_id(PSC, "0x00126D")
        self.assertRegex(on, r"(?m)^int RefId = 0x00126d  ;REF")
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        self.assertRegex(mcd.set_ref_id(PSC, "126D"), r"(?m)^int RefId = 0x126d  ;REF")
        for bad in ("zz", "", "12345678", "0", "0x000000"):
            with self.assertRaises(SystemExit):
                mcd.set_ref_id(PSC, bad)
        with self.assertRaises(SystemExit):
            mcd.set_ref_id("no line here\n", "12")


class PrecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.z = os.path.join(self.tmp.name, "cr.zip")

    def test_the_door_natives_are_found_and_a_missing_one_is_named(self):
        fake_sources(self.z, BASES_DOOR)
        sources = mcd.read_sources(self.z)
        self.assertEqual(mcd.precheck_sources(sources)["missing"], [])
        sources["objectreference"] = sources["objectreference"].replace("SetOpen", "Other")
        self.assertEqual(mcd.precheck_sources(sources)["missing"], ["ObjectReference.SetOpen"])
        fake_sources(self.z, BASES)                                                         # the shared fake has no door natives
        self.assertEqual(mcd.precheck_sources(mcd.read_sources(self.z))["missing"], ["ObjectReference.GetOpenState", "ObjectReference.SetOpen"])


class LogTests(unittest.TestCase):
    def test_summarize_reads_the_open_state_per_stage_and_says_whether_it_changed(self):
        lines = [
            "FO4SFDOOR rt=1.0 init version=1 quest=1 refid=4717 end=true",
            "FO4SFDOOR rt=2.0 read stage=10 when=read ref=5 openstate=2 dist=6.0 end=true",
            "FO4SFDOOR rt=3.0 setopen stage=20 value=true end=true",
            "FO4SFDOOR rt=3.1 read stage=20 when=after ref=5 openstate=2 end=true",
            "FO4SFDOOR rt=5.1 watch stage=20 after=2.0 openstate=2 end=true",
            "FO4SFDOOR rt=7.1 watch stage=20 after=4.0 openstate=3 changed=true from=2 end=true",
            "FO4SFDOOR rt=9.0 read stage=50 when=read ref=5 openstate=2 end=true",
            "noise line",
        ]
        s = mcd.summarize(lines)
        self.assertEqual(s["init"]["refid"], "4717")
        self.assertTrue(s["stages"][20]["changed"])
        self.assertEqual(s["stages"][20]["states"], [(None, 2), (2.0, 2), (4.0, 3)])
        self.assertFalse(s["stages"][10]["changed"])
        self.assertFalse(s["stages"][50]["changed"])
        self.assertEqual(sorted(s["stages"]), [10, 20, 50])

    def test_the_log_command_prints_a_row_per_stage_and_exits_1_without_findings(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        p = os.path.join(tmp, "l.log")
        Path(p).write_text("FO4SFDOOR rt=2.0 read stage=10 when=read openstate=2 end=true\n", encoding="utf-8")
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(mcd.main(["log", "--file", p]), 0)
        self.assertIn("stage 10: open state 2; did not change", buf.getvalue())
        Path(p).write_text("nothing here\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mcd.main(["log", "--file", p]), 1)


class FakeSrc:
    def __init__(self):
        self.asked = []

    def mesh(self, name):
        self.asked.append(name)
        return b"nif" if name.lower().endswith("vltgeardoor01.nif") else None

    def mesh_names(self, pattern):
        return []


class FakeConv:
    """convert_nif without CALUMI or the game: writes the files a door conversion would into the staging, on the new path."""
    def __init__(self, staging, textures=(), door_error=None, same_path=False):
        self.staging, self.textures, self.calls, self.door_error, self.same_path = staging, textures, [], door_error, same_path

    def convert_nif(self, name, pose=None, out_suffix=""):
        self.calls.append((name, out_suffix))
        out = "fo4port/interiors/vault/doors/vltgeardoor/vltgeardoor01" + ("" if self.same_path else out_suffix)
        if self.door_error:
            return {"ok": True, "out_name": out, "door_error": self.door_error}
        files = {f"meshes/{out}.nif": b"nif", f"meshes/{out}/characterassets/skeleton.rig": b"rig", f"meshes/{out}/animations/Open.af": b"af",
                 f"meshes/{out}/animations/Close.af": b"af", "geometries/ab/cd.mesh": b"mesh", "materials/fo4port/x.mat": b"mat"}
        for t in self.textures:
            files[t] = b"dds"
        for rel, data in files.items():
            p = os.path.join(self.staging, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            Path(p).write_bytes(data)
        return {"ok": True, "out_name": out, "door": {"rig": "native", "anim_graph": "g", "skeleton": out.replace("/", "\\") + "\\characterassets\\skeleton.rig",
                                                       "animations": out.replace("/", "\\") + "\\animations", "origin_offset": [0.0, 0.0, 0.0],
                                                       "bounds": [[0, 0, 0], [1, 1, 1]], "shapes": [{"shape": "x"}]}}


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "CogDoorProbe"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/CogDoorProbe/bin/Release/net9.0/CogDoorProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-cogd-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.data = cls.root / "Data"
        r = cls.run_tool("fixture", cls.data)
        assert r.returncode == 0, r.stdout + r.stderr
        make, cls.full_holder = cls.converter()
        cls.full = cls.root / "staged-full"
        assert mcd.stage(cls.args(cls.full, model="Meshes\\Interiors\\Vault\\Doors\\VltGearDoor\\VltGearDoor01.nif"), converter=make) == 0
        cls.control = cls.root / "staged-control"
        assert mcd.stage(cls.args(cls.control, control=True)) == 0

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def paths(self):
        return self.data / "FO4Port.esm", self.data / "Starfield.esm"

    # ------------------------------------------------------------- the plugin tool
    def test_info_names_the_door_the_reference_stands_on(self):
        port, sf = self.paths()
        info = self.run_tool("info", port, sf)
        self.assertEqual(info.returncode, 0, info.stderr)
        self.assertIn("REF 00126D base 00DEF9:FO4Port.esm", info.stdout)
        self.assertEqual(mcd.mac.parse_info(info.stdout), {"base_id": "00DEF9", "model": "Meshes/fo4port/interiors/vault/doors/vltgeardoor/vltgeardoor01.nif"})
        self.assertIn("GRAPH_ANAM AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx", info.stdout)

    def test_a_reference_that_is_not_there_is_refused_by_id(self):
        port, sf = self.paths()
        proc = self.run_tool("info", port, sf, "--ref", "0099")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 placed references with local id 000099", proc.stderr)
        bad = self.run_tool("info", port, sf, "--ref", "zz")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("is not a local form id", bad.stderr)

    def test_build_and_check_the_full_kit_and_a_wrong_path_fails(self):
        port, sf = self.paths()
        out = self.root / "b1"
        proc = self.run_tool("build", port, sf, out, *MARGS)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        check = self.run_tool("check", out / PLUGIN, port, sf, *MARGS)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        text = norm(check.stdout)
        self.assertIn("masters [Starfield.esm, FO4Port.esm]", text)
        self.assertIn("override: DOOR 00DEF9:FO4Port.esm FO4Port_door_vltgeardoor01 name 'Door'", text)
        self.assertIn(norm("ANAM AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx BNAM " + RIG + " CNAM " + ANIMS), text)       # the base's own door graph, the new rig and clips
        self.assertIn("scripts [FO4SF_CogDoorQuest (0 properties)]", text)
        wrong = self.run_tool("check", out / PLUGIN, port, sf, "--model", "other.nif", "--rig", RIG, "--anims", ANIMS)
        self.assertEqual(wrong.returncode, 1)
        self.assertIn("the model is not Meshes/other.nif", norm(wrong.stdout))

    def test_the_override_keeps_the_base_graph_fields_it_does_not_change_and_check_sees_a_drop(self):
        # FAL-760 HOLD 1: the override copies the graph component and sets only BNAM and CNAM; DNAM and ENAM stay the base's, and Check compares them
        port, sf = self.paths()
        out = self.root / "b3"
        self.assertEqual(self.run_tool("build", port, sf, out, *MARGS).returncode, 0)
        ok = self.run_tool("check", out / PLUGIN, port, sf, *MARGS)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("DNAM KEEP-DNAM ENAM KEEP-ENAM", norm(ok.stdout))
        other = self.root / "DataOther"                                   # the same port with other DNAM / ENAM: the override now differs from its base
        self.assertEqual(self.run_tool("fixture", other, "OTHER-DNAM", "OTHER-ENAM").returncode, 0)
        bad = self.run_tool("check", out / PLUGIN, other / "FO4Port.esm", other / "Starfield.esm", *MARGS)
        self.assertEqual(bad.returncode, 1, bad.stdout)
        self.assertIn("the animation graph component is not", norm(bad.stdout))

    def test_a_model_path_equal_to_the_ports_own_is_refused_by_check(self):
        port, sf = self.paths()
        own = ["--model", "fo4port\\interiors\\vault\\doors\\vltgeardoor\\vltgeardoor01.nif", "--rig", RIG, "--anims", ANIMS]
        out = self.root / "b2"
        self.assertEqual(self.run_tool("build", port, sf, out, *own).returncode, 0)
        check = self.run_tool("check", out / PLUGIN, port, sf, *own)
        self.assertEqual(check.returncode, 1)
        self.assertIn("the override would shadow an archived file", check.stdout)
        # FAL-760 HOLD 2: Windows archive lookup ignores case, so the same path in other case shadows the archived file too
        loud = [own[0], own[1].upper(), *own[2:]]
        out2 = self.root / "b2case"
        self.assertEqual(self.run_tool("build", port, sf, out2, *loud).returncode, 0)
        loud_check = self.run_tool("check", out2 / PLUGIN, port, sf, *loud)
        self.assertEqual(loud_check.returncode, 1, loud_check.stdout)
        self.assertIn("the override would shadow an archived file", loud_check.stdout)

    def test_the_control_is_the_quest_alone_and_the_full_check_refuses_it(self):
        port, sf = self.paths()
        out = self.root / "b3"
        self.assertEqual(self.run_tool("build", port, sf, out, "--control").returncode, 0)
        self.assertEqual(self.run_tool("check", out / PLUGIN, port, sf, "--control").returncode, 0)
        full = self.run_tool("check", out / PLUGIN, port, sf, *MARGS)
        self.assertEqual(full.returncode, 1)
        self.assertIn("not exactly two records", full.stdout)
        both = self.run_tool("build", port, sf, self.root / "b4", "--control", *MARGS)
        self.assertEqual(both.returncode, 1)
        self.assertIn("--control writes no DOOR override", both.stderr)
        half = self.run_tool("build", port, sf, self.root / "b5", "--model", MODEL)
        self.assertEqual(half.returncode, 1)
        self.assertIn("needs --model, --rig and --anims", half.stderr)

    @staticmethod
    def walk_kinds(data):
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
        return {k: v for k, v in kinds.items() if k != b"TES4"}

    def test_the_plugin_records_raw(self):
        """Raw bytes: the DOOR carries the FO4Port load index (1) and its own local id (an override), the quest ours (2)."""
        self.assertEqual(self.walk_kinds((self.full / PLUGIN).read_bytes()), {b"DOOR": [0x0100DEF9], b"QUST": [0x02000800]})
        self.assertEqual(self.walk_kinds((self.control / PLUGIN).read_bytes()), {b"QUST": [0x02000800]})

    # ------------------------------------------------------------- the stager
    @classmethod
    def args(cls, out, **kw):
        z = cls.root / (Path(out).name + "-cr.zip")
        fake_sources(z, BASES_DOOR)
        base = dict(out=str(out), starfield_data=str(cls.data), port_data="", fo4_data="fo4", door_anim_dll="d.dll", collision_template="c.nif",
                    texconv="t.exe", content_resources=str(z), compiler=str(fake_compiler(cls.root)), ref="00126D", model="", control=False)
        base.update(kw)
        return type("A", (), base)()

    @classmethod
    def converter(cls, textures=(), **conv):
        holder = {}

        def make(a, staging):
            holder["conv"] = FakeConv(staging, textures, **conv)
            holder["src"] = FakeSrc()
            return holder["src"], holder["conv"]
        return make, holder

    def test_the_full_stage_converts_on_the_new_path_and_pins_every_file(self):
        out = self.full
        self.assertEqual(self.full_holder["conv"].calls, [("Meshes\\Interiors\\Vault\\Doors\\VltGearDoor\\VltGearDoor01.nif", "_anim")])
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual((plan["kind"], plan["plugins"], plan["control"], plan["ref"]), ("cog-door", [PLUGIN], False, "00126D"))
        self.assertEqual(set(plan["inputs"]), {"Starfield.esm", "FO4Port.esm"})
        outputs = set(plan["outputs"])
        self.assertIn(PLUGIN, outputs)
        self.assertIn("Data/Scripts/FO4SF_CogDoorQuest.pex", outputs)
        self.assertIn("Data/meshes/" + OUT + ".nif", outputs)
        self.assertIn("Data/meshes/" + OUT + "/characterassets/skeleton.rig", outputs)
        self.assertIn("Data/meshes/" + OUT + "/animations/Open.af", outputs)
        self.assertFalse([o for o in outputs if o.endswith("/vltgeardoor01.nif") or "/vltgeardoor01/" in o])      # nothing on the port's own path
        self.assertEqual(mcd.verify_stage(str(out), plan, str(self.data)), [])
        manifest = json.loads((out / "cog_manifest.json").read_text())
        self.assertEqual((manifest["base_id"], manifest["model"], manifest["ref"]), ("00DEF9", MODEL, "00126D"))
        self.assertNotIn("shapes", manifest["door"])
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        self.assertIn("int RefId = 0x00126d  ;REF", (out / "FO4SF_CogDoorQuest.psc").read_text())
        self.assertIn("new path", (out / "README.txt").read_text())
        self.assertFalse((out / "work").exists())
        make, _ = self.converter()
        with self.assertRaises(SystemExit):                                                  # an earlier stage is never overwritten
            mcd.stage(self.args(out), converter=make)

    def test_the_control_stage_converts_nothing_and_ships_no_mesh(self):
        plan = json.loads((self.control / "plan.json").read_text())
        self.assertTrue(plan["control"])
        self.assertEqual(sorted(plan["outputs"]), ["Data/Scripts/FO4SF_CogDoorQuest.pex", PLUGIN])
        self.assertEqual(mcd.verify_stage(str(self.control), plan, str(self.data)), [])
        self.assertIn("CONTROL kit", (self.control / "README.txt").read_text())
        manifest = json.loads((self.control / "cog_manifest.json").read_text())
        self.assertNotIn("model", manifest)

    def test_the_kit_ships_no_textures_and_refuses_ones_the_port_lacks(self):
        make, _ = self.converter(textures=["textures/fo4port/c_d.dds"])
        out = self.root / "staged-tex"
        with self.assertRaises(SystemExit) as cm:
            mcd.stage(self.args(out, model="Meshes\\x\\VltGearDoor01.nif"), converter=make)
        self.assertIn("the port's archives do not hold", str(cm.exception))
        self.assertFalse(out.exists())                                                       # nothing published

    def test_a_door_that_fell_back_to_a_static_or_kept_the_ports_path_is_refused(self):
        for label, kw, text in (("fallback", {"door_error": "own rig: boom"}, "did not come out with its own rig"),
                                ("samepath", {"same_path": True}, "would shadow an archived file")):
            make, _ = self.converter(**kw)
            out = self.root / ("staged-" + label)
            with self.assertRaises(SystemExit) as cm:
                mcd.stage(self.args(out, model="Meshes\\x\\VltGearDoor01.nif"), converter=make)
            self.assertIn(text, str(cm.exception))
            self.assertFalse(out.exists())

    def test_a_reference_that_is_not_a_door_stops_the_stage_before_any_conversion(self):
        make, holder = self.converter()
        out = self.root / "staged-badref"
        with self.assertRaises(SystemExit):
            mcd.stage(self.args(out, ref="0099"), converter=make)
        self.assertNotIn("conv", holder)
        self.assertFalse(out.exists())

    def test_a_changed_stage_or_starfield_esm_is_refused_by_verify(self):
        plan = json.loads((self.control / "plan.json").read_text())
        out = self.root / "staged-edit"
        shutil.copytree(self.control, out)
        (out / "Data" / "Scripts" / "FO4SF_CogDoorQuest.pex").write_bytes(b"changed")
        self.assertTrue(any("changed after the stage" in p for p in mcd.verify_stage(str(out), plan)))
        data = self.root / "Data2"
        shutil.copytree(self.data, data)
        (data / "Starfield.esm").write_bytes(b"other")
        self.assertIn("Starfield.esm changed since the stage: re-stage", mcd.verify_stage(str(self.control), plan, str(data)))
        self.assertEqual(mcd.verify_stage(str(self.control), {**plan, "kind": "anim-console"}), [
            "plan.json is not the cog door probe's (kind 'anim-console', plugins ['FO4SFCogDoor.esm'])"])


if __name__ == "__main__":
    unittest.main()
