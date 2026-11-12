"""The animation console probe, variant D: its script's ids and stages against the writer's (dotnet/AnimConsoleProbe), the
stager with a fake converter, fake base sources and a fake Papyrus compiler, the texture rule and the plan verification (never a
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
import make_anim_console as mac  # noqa: E402
from fo4sf import anim_object, nif  # noqa: E402
from test_anim_object import STATES, console_nif  # noqa: E402
from test_anim_probe import BASES, fake_compiler, fake_sources  # noqa: E402

PSC = (ROOT / "scripts" / "newgame" / "FO4SF_AnimConsoleQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "AnimConsoleProbe" / "Program.cs").read_text(encoding="utf-8")
PLUGIN = "FO4SFAnimConsole.esm"
MODEL_IN_PORT = "Meshes/fo4port/interiors/vault/props/console01.nif"


def norm(text):
    """Tool output in one normal form: forward slashes (the tool prints a path as it was given, Windows or not)."""
    return text.replace("\\", "/")


class ScriptTests(unittest.TestCase):
    def test_ids_stages_log_and_layout_match_the_tool_and_the_reader(self):
        self.assertTrue(PSC.startswith("Scriptname FO4SF_AnimConsoleQuest extends Quest"))
        self.assertIn('Script = "FO4SF_AnimConsoleQuest"', TOOL_SRC)
        self.assertIn("const uint QuestId = 0x800", TOOL_SRC)
        self.assertIn('string LogName = "FO4SFAnimD"', PSC)
        self.assertIn('string ProbePlugin = "FO4SFAnimConsole.esm"', PSC)
        self.assertIn('string BasePlugin = "FO4Port.esm"', PSC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 40, 60])
        self.assertIn(f"StageList = new int[{len(ran)}]", PSC)
        self.assertIn('"FO4SFANIM rt="', PSC)                                  # the variant A reader reads this log too
        from fo4sf import anim_probe_log
        for e in anim_probe_log.EVENTS:
            self.assertRegex(PSC, rf'Trace\("{e}[ "]')

    def test_no_property_no_wait_form_one_base_line_and_a_spawn_not_a_cell(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        self.assertNotIn(" Property ", PSC)
        self.assertNotRegex("\n".join(l.split(";")[0] for l in PSC.splitlines() if not l.startswith(" ")), r"PlayAnimationAndWait\(")
        self.assertEqual(len(mac.BASE_LINE.findall(PSC)), 1)
        self.assertIn("p.PlaceAtMe(base, 1, true, false, false)", PSC)
        self.assertIn("Game.GetFormFromFile(BaseId, BasePlugin)", PSC)
        self.assertNotIn("ActiId", PSC)
        self.assertEqual(PSC.count("TestRef.PlayAnimation(n)"), 1)

    def test_the_play_names_start_with_the_four_that_moved_the_vanilla_activator(self):
        names = dict(re.findall(r'PlayNames\[(\d)\] = "(\w+)"', PSC))
        self.assertEqual([names[str(i)] for i in range(4)], ["Play01", "Play02", "TurnOff", "StateB_Play"])      # variant A, 12 Nov
        self.assertEqual(len(names), 8)
        self.assertIn("PlayOne(stage, PlayNames[stage - 21])", PSC)

    def test_every_finding_shows_on_screen_and_the_clip_time_is_logged(self):
        self.assertIn('Debug.Notification("AP " + msg)', PSC)
        self.assertIn('" after=" + after', PSC)                                      # Done's after= is the clip's length
        self.assertEqual(PSC.count("PlayRt = Utility.GetCurrentRealTime()"), 2)      # PlayOne and ActivateOnce
        for what in ('Say("EV " + asEventName + " w" + ListenStage + " t" + after)', 'Say("PLAY s" + stage + " " + n + " ok=" + ok)',
                     'Say("W s" + stage + " quiet")', 'Say("ACTIVATE s" + stage)'):
            self.assertIn(what, PSC)

    def test_the_committed_script_compiles_alone_and_the_register_shape_replaces_cleanly(self):
        self.assertEqual(mac.enable(PSC, []), PSC)
        self.assertEqual(mac.optional_names(PSC), ["ObjectReference.MoveTo", "ObjectReference.Delete"])
        self.assertIn(mac.probe_a.BOOL_LINE, PSC)
        self.assertNotIn(mac.probe_a.BOOL_LINE, mac.probe_a.reg_shape(PSC, False))

    def test_the_base_id_is_written_once_and_a_bad_one_is_refused(self):
        on = mac.set_base_id(PSC, "0x001234")
        self.assertRegex(on, r"(?m)^int BaseId = 0x001234  ;BASE")
        self.assertEqual(on.count("\n"), PSC.count("\n"))
        self.assertRegex(mac.set_base_id(PSC, "1319"), r"(?m)^int BaseId = 0x1319  ;BASE")
        for bad in ("zz", "", "12345678"):
            with self.assertRaises(SystemExit):
                mac.set_base_id(PSC, bad)
        with self.assertRaises(SystemExit):
            mac.set_base_id("no line here\n", "12")

    def test_info_output_is_parsed_and_a_missing_one_refused(self):
        self.assertEqual(mac.parse_info("ACTI x\nBASE_ID 0x001234\nMODEL Meshes/a/b.nif\n"), {"base_id": "001234", "model": "Meshes/a/b.nif"})
        self.assertEqual(mac.parse_info("BASE_ID 0xE0D9\nMODEL Meshes\\a\\b.nif\n")["model"], "Meshes/a/b.nif")   # Windows prints backslashes
        for bad in ("BASE_ID 0x1\nMODEL \n", "MODEL Meshes/a.nif\n", ""):
            with self.assertRaises(SystemExit):
                mac.parse_info(bad)

    def test_the_variant_a_precheck_list_covers_this_script(self):
        z = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, z, True)
        zp = os.path.join(z, "cr.zip")
        fake_sources(zp)
        r = mac.probe_a.precheck_sources(mac.read_sources(zp), PSC)
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["optional"], {"ObjectReference.MoveTo": True, "ObjectReference.Delete": True})


class SequencesTableTests(unittest.TestCase):
    def test_the_console_clips_are_listed_with_seconds_and_bones(self):
        rows = mac.sequences_table(nif.serialize(console_nif()))
        self.assertEqual(sorted(r["name"] for r in rows), ["Stage1", "Stage2"])
        for r in rows:
            self.assertEqual((r["seconds"], r["bones"]), (1.0, ["LeafA", "LeafB"]))
            self.assertEqual(r["text_keys"], [])


class FakeSrc:
    def __init__(self, raw):
        self.raw, self.asked = raw, []

    def mesh(self, name):
        self.asked.append(name)
        return self.raw if name.lower().endswith("console01.nif") and "interiors" in name.lower() else None

    def mesh_names(self, pattern):
        return []


class FakeConv:
    """convert_anim_object without CALUMI or the game: writes the files a conversion would into the staging."""
    def __init__(self, staging, textures=()):
        self.staging, self.textures, self.calls = staging, textures, []

    def convert_anim_object(self, name, states, foley=None):
        self.calls.append((name, dict(states), foley))
        out = "fo4port/interiors/vault/props/console01_anim"
        files = {f"meshes/{out}.nif": b"nif", f"meshes/{out}/characterassets/skeleton.rig": b"rig", "geometries/ab/cd.mesh": b"mesh",
                 "materials/fo4port/x.mat": b"mat"}
        for slot in anim_object.slot_names(states):
            files[f"meshes/{out}/animations/{slot}.af"] = b"af"
            files[f"meshes/{out}/animations/{slot}.afx"] = anim_object.descriptor(slot, audio=[(1, foley)] if foley and "Play" in slot else ())
        for t in self.textures:
            files[t] = b"dds"
        for rel, data in files.items():
            p = os.path.join(self.staging, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            Path(p).write_bytes(data)
        clips = [{"name": n, "seconds": 1.0 if "Play" in n else 0.0, "frames": 30 if "Play" in n else 0, "bones": ["LeafA"],
                  "hold_of": None if "Play" in n else n.replace("Idle", "Play"), "sound_keys": []} for n in anim_object.slot_names(states)]
        return {"ok": True, "out_name": out, "anim": {"skeleton": out.replace("/", "\\") + "\\characterassets\\skeleton.rig",
                                                      "animations": out.replace("/", "\\") + "\\animations", "clips": clips, "states": dict(states)}}


class StageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "AnimConsoleProbe"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/AnimConsoleProbe/bin/Release/net9.0/AnimConsoleProbe.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-animc-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.data = cls.root / "Data"
        r = cls.run_tool("fixture", cls.data)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.margs = ["--model", "fo4port\\interiors\\vault\\props\\console01_anim.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations"]

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def paths(self):
        return self.data / "FO4Port.esm", self.data / "Starfield.esm"

    # ------------------------------------------------------------- the plugin tool
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
        self.assertIn(norm("ANAM AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx BNAM fo4port\\r\\skeleton.rig CNAM fo4port\\r\\animations"), out)
        self.assertIn("scripts [FO4SF_AnimConsoleQuest (0 properties)]", out)
        wrong = self.run_tool("check", out_dir / PLUGIN, port, sf, "--model", "other.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations")
        self.assertEqual(wrong.returncode, 1)
        self.assertIn("the model is not Meshes/other.nif", norm(wrong.stdout))
        backslash = self.run_tool("check", out_dir / PLUGIN, port, sf, "--model", "other\\sub.nif", "--rig", "fo4port\\r\\skeleton.rig", "--anims", "fo4port\\r\\animations")
        self.assertIn("the model is not Meshes/other/sub.nif", norm(backslash.stdout))        # a backslash model compares in the same form

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

    def test_a_base_that_is_not_there_is_refused_by_name(self):
        port, sf = self.paths()
        proc = self.run_tool("build", port, sf, self.root / "b3", *self.margs, "--edid", "NoSuchActi")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 ACTI named NoSuchActi", proc.stderr)

    # ------------------------------------------------------------- the stager
    def args(self, out, **kw):
        z = self.root / (Path(out).name + "-cr.zip")
        fake_sources(z)
        base = dict(out=str(out), starfield_data=str(self.data), port_data="", fo4_data="fo4", door_anim_dll="d.dll", collision_template="c.nif",
                    texconv="t.exe", content_resources=str(z), compiler=str(fake_compiler(self.root)), states="Stage1=StateA_Play,Stage2=StateB_Play",
                    foley="", model="", edid=mac.EDID)
        base.update(kw)
        return type("A", (), base)()

    def converter(self, textures=()):
        raw = nif.serialize(console_nif())
        holder = {}

        def make(a, staging):
            holder["conv"] = FakeConv(staging, textures)
            holder["src"] = FakeSrc(raw)
            return holder["src"], holder["conv"]
        return make, holder

    def test_stage_converts_builds_compiles_and_pins_every_file(self):
        make, holder = self.converter()
        out = self.root / "staged"
        self.assertEqual(mac.stage(self.args(out, foley="QST_Flip"), converter=make), 0)
        self.assertTrue(holder["conv"].calls[0][0].lower().endswith("console01.nif"))      # the first candidate the source holds
        self.assertEqual(holder["conv"].calls[0][1:], (STATES, "QST_Flip"))
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual(plan["kind"], "anim-console")
        self.assertEqual(plan["plugins"], [PLUGIN])
        self.assertEqual(set(plan["inputs"]), {"Starfield.esm", "FO4Port.esm"})
        outputs = set(plan["outputs"])
        self.assertIn(PLUGIN, outputs)
        self.assertIn("Data/Scripts/FO4SF_AnimConsoleQuest.pex", outputs)
        self.assertIn("Data/meshes/fo4port/interiors/vault/props/console01_anim/animations/StateB_Idle.afx", outputs)
        self.assertIn("Data/geometries/ab/cd.mesh", outputs)
        self.assertEqual(plan["optional"]["ObjectReference.MoveTo"], "kept")
        self.assertEqual(mac.verify_stage(str(out), plan, str(self.data)), [])
        manifest = json.loads((out / "anim_manifest.json").read_text())
        self.assertEqual((manifest["base_id"], manifest["model"], manifest["foley"]), ("001234", "fo4port\\interiors\\vault\\props\\console01_anim.nif", "QST_Flip"))
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        self.assertIn("int BaseId = 0x001234  ;BASE", (out / "FO4SF_AnimConsoleQuest.psc").read_text())
        self.assertIn("StateA_Idle: 0.0 s (0 frames)", (out / "README.txt").read_text())
        self.assertFalse((out / "work").exists())
        with self.assertRaises(SystemExit):                                                  # an earlier stage is never overwritten
            mac.stage(self.args(out), converter=make)

    def test_the_kit_ships_no_textures_and_refuses_ones_the_port_lacks(self):
        make, _ = self.converter(textures=["textures/fo4port/c_d.dds"])
        with self.assertRaises(SystemExit) as ctx:
            mac.stage(self.args(self.root / "staged-t"), converter=make)
        self.assertIn("the port's archives do not hold", str(ctx.exception))
        self.assertIn("textures/fo4port/c_d.dds", str(ctx.exception))
        self.assertFalse((self.root / "staged-t").exists())
        # the same texture is fine when the port's archive holds it, and still not copied into the kit
        from ba2_fixture import general_archive
        port_dir = self.root / "portdata"
        port_dir.mkdir()
        shutil.copy(self.data / "FO4Port.esm", port_dir / "FO4Port.esm")
        (port_dir / "FO4Port - Textures.ba2").write_bytes(general_archive({"textures\\fo4port\\c_d.dds": b"dds"}))
        self.assertEqual(mac.stage(self.args(self.root / "staged-t2", port_data=str(port_dir)), converter=make), 0)
        self.assertFalse(any("textures" in k for k in json.loads((self.root / "staged-t2" / "plan.json").read_text())["outputs"]))

    def test_a_failed_conversion_and_a_bad_state_map_stop_before_anything_is_published(self):
        class Failing(FakeConv):
            def convert_anim_object(self, name, states, foley=None):
                return {"ok": False, "reason": "NifError: door has no moving geometry"}
        with self.assertRaises(SystemExit) as ctx:
            mac.stage(self.args(self.root / "staged-f"), converter=lambda a, st: (FakeSrc(nif.serialize(console_nif())), Failing(st)))
        self.assertIn("the console did not convert: NifError: door has no moving geometry", str(ctx.exception))
        self.assertFalse((self.root / "staged-f").exists())
        with self.assertRaises(ValueError):
            mac.stage(self.args(self.root / "staged-b", states="Stage1=StateA_Idle"), converter=self.converter()[0])

    def test_an_original_that_cannot_be_found_asks_for_the_model_option(self):
        class Nothing(FakeSrc):
            def mesh(self, name):
                return None
        with self.assertRaises(SystemExit) as ctx:
            mac.stage(self.args(self.root / "staged-n"), converter=lambda a, st: (Nothing(b""), FakeConv(st)))
        self.assertIn("name it with --model", str(ctx.exception))

    def test_a_changed_stage_or_starfield_esm_is_refused_by_verify(self):
        make, _ = self.converter()
        out = self.root / "staged-v"
        mac.stage(self.args(out), converter=make)
        plan = json.loads((out / "plan.json").read_text())
        with open(out / PLUGIN, "ab") as f:
            f.write(b"!")
        self.assertIn("changed after the stage", " ".join(mac.verify_stage(str(out), plan)))
        self.assertIn("is not the animation console probe's", " ".join(mac.verify_stage(str(out), dict(plan, kind="anim-probe"))))
        plan["inputs"]["Starfield.esm"]["sha256"] = "0" * 64
        self.assertIn("Starfield.esm changed since the stage", " ".join(mac.verify_stage(str(out), plan, str(self.data))))

    def test_log_command_reads_the_variant_a_reader(self):
        f = self.root / "d.log"
        self.assertEqual(mac.main(["log", "--file", str(f)]), 2)
        f.write_text("FO4SFANIM rt=1.0 spawn stage=10 base=77 ref=99 moved=true persist=true end=true\n"
                     "FO4SFANIM rt=2.0 play stage=21 name=Play01 ref=99 ok=true end=true\n"
                     "FO4SFANIM rt=3.0 event name=Done src=99 stage=21 since=0.5 after=0.64 end=true\n", encoding="utf-8")
        self.assertEqual(mac.main(["log", "--file", str(f)]), 0)


if __name__ == "__main__":
    unittest.main()
