"""dotnet/CoreStorage and scripts/core_storage on a synthetic core (CoreStorage fixture: a Starfield.esm stand-in and a
FO4TerrainCore.esm whose world holds the spawn cell FO4Core_RedRocketSpawn and a second cell), never a game: one
persistent and one temporary XMarker in the spawn cell's own groups, the exact masters, the cell the core's own."""
from pathlib import Path
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "core_storage"))
from test_map_markers_plugin import build  # noqa: E402
import make_core_storage  # noqa: E402

PERSISTENT_CHILDREN, TEMPORARY_CHILDREN = 8, 9      # GRUP types of a cell's persistent / temporary children


def walk(path):
    """{local form id: (signature, record flags, enclosing GRUP type, enclosing cell form id, master index)} of a plugin."""
    data = path.read_bytes()
    out = {}

    def rec(start, end, kind=None, cell=None):
        pos = start
        while pos < end:
            sig, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
            if sig == b"GRUP":
                label, gkind = struct.unpack_from("<II", data, pos + 8)
                rec(pos + 24, pos + size, gkind, label if gkind in (6, 8, 9) else cell)
                pos += size
            else:
                flags, form = struct.unpack_from("<II", data, pos + 8)
                if form:
                    out[form & 0xFFFFFF] = (sig, flags, kind, cell, form >> 24)
                pos += 24 + size
    rec(0, len(data))
    return out


def masters(path):
    data = path.read_bytes()
    size = struct.unpack_from("<I", data, 4)[0]
    body, pos, out = data[24:24 + size], 0, []
    while pos < len(body):
        sig, n = body[pos:pos + 4], struct.unpack_from("<H", body, pos + 4)[0]
        if sig == b"MAST":
            out.append(body[pos + 6:pos + 6 + n].rstrip(b"\0").decode())
        pos += 6 + n
    return out


class CoreStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        cls.tool = build(cls.dotnet, "CoreStorage")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-corestorage-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.fx = cls.root / "fixture"
        cls.run_tool("fixture", cls.fx).check_returncode()
        cls.sf, cls.core = cls.fx / "Starfield.esm", cls.fx / "FO4TerrainCore.esm"

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def built(self, name="plugin"):
        out = self.root / name
        proc = self.run_tool("build", "--sf", self.sf, "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return out / "FO4SFCoreStorage.esm"

    def check(self, plugin):
        return self.run_tool("check", plugin, "--sf", self.sf, "--core", self.core)

    def test_each_reference_is_in_its_own_group_of_the_core_spawn_cell(self):
        plugin = self.built()
        proc = self.check(plugin)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(masters(plugin), ["Starfield.esm", "FO4TerrainCore.esm"])
        recs = walk(plugin)
        spawn_cell = 0x901                                    # the core's FO4Core_RedRocketSpawn
        sig, flags, kind, cell, _ = recs[0x800]
        self.assertEqual((sig, flags & 0xC00, kind, cell & 0xFFFFFF), (b"REFR", 0x400, PERSISTENT_CHILDREN, spawn_cell))
        sig, flags, kind, cell, _ = recs[0x801]
        self.assertEqual((sig, flags & 0xC00, kind, cell & 0xFFFFFF), (b"REFR", 0, TEMPORARY_CHILDREN, spawn_cell))
        self.assertEqual(recs[0x802][0], b"QUST")
        self.assertEqual(sorted(v[0] for v in recs.values()), [b"CELL", b"QUST", b"REFR", b"REFR", b"WRLD"])
        self.assertEqual({k for k, v in recs.items() if v[4] == 1}, {0x803, 0x901})       # core's world and cell only
        self.assertIn("(-985.257, 1146.514, 107.143)", proc.stdout)                        # marker + 4 m
        self.assertIn("(-981.257, 1146.514, 107.143)", proc.stdout)                        # marker + 8 m

    def test_the_world_override_keeps_its_cell_and_nothing_else(self):
        proc = self.check(self.built("plugin-cells"))
        self.assertNotIn("SyntheticOtherCell", proc.stdout)
        self.assertIn("records: Worldspace 1, Cell 1, PlacedObject 2, Quest 1", proc.stdout)

    def test_every_variant_writes_its_part_and_keeps_the_same_masters(self):
        """FAL-273 (#707): one game run per variant; the variants differ in the cell's references and the cell, nothing else."""
        want = {"full": {b"WRLD", b"CELL", b"REFR", b"QUST"}, "persist-only": {b"WRLD", b"CELL", b"REFR", b"QUST"},
                "temp-only": {b"WRLD", b"CELL", b"REFR", b"QUST"}, "cell-only": {b"WRLD", b"CELL", b"QUST"}, "world-only": {b"WRLD", b"QUST"}}
        for v, sigs in want.items():
            out = self.root / f"variant-{v}"
            proc = self.run_tool("build", "--sf", self.sf, "--core", self.core, "--out", out, "--variant", v)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            plugin = out / "FO4SFCoreStorage.esm"
            self.assertEqual(masters(plugin), ["Starfield.esm", "FO4TerrainCore.esm"], v)
            self.assertEqual({x[0] for x in walk(plugin).values()}, sigs, v)
            self.assertEqual(self.run_tool("check", plugin, "--sf", self.sf, "--core", self.core, "--variant", v).returncode, 0, v)
        recs = walk(self.root / "variant-persist-only" / "FO4SFCoreStorage.esm")
        self.assertEqual(recs[0x800][2], PERSISTENT_CHILDREN)
        self.assertNotIn(0x801, recs)
        recs = walk(self.root / "variant-temp-only" / "FO4SFCoreStorage.esm")
        self.assertEqual(recs[0x801][2], TEMPORARY_CHILDREN)
        self.assertNotIn(0x800, recs)

    def test_check_follows_the_variant_and_refuses_another_one(self):
        plugin = self.root / "variant-cell-only" / "FO4SFCoreStorage.esm"
        if not plugin.exists():
            self.test_every_variant_writes_its_part_and_keeps_the_same_masters()
        wrong = self.run_tool("check", plugin, "--sf", self.sf, "--core", self.core)             # checked as the full plugin
        self.assertEqual(wrong.returncode, 1, wrong.stdout)
        self.assertIn("does not hold exactly FO4SF_CS_P", wrong.stdout)
        bad = self.run_tool("build", "--sf", self.sf, "--core", self.core, "--out", self.root / "variant-bad", "--variant", "nonsense")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("is not one of full, persist-only, temp-only, cell-only, world-only", bad.stderr)

    def test_the_stage_names_the_variant(self):
        self.assertIn("--variant", (ROOT / "scripts" / "core_storage" / "make_core_storage.py").read_text(encoding="utf-8"))
        self.assertEqual(make_core_storage.VARIANTS, ("full", "persist-only", "temp-only", "cell-only", "world-only"))

    def test_the_twin_dump_shows_the_override_beside_the_core_cell(self):
        import twin_dump
        plugin = self.built("plugin-twin")
        lines, summary = twin_dump.report(str(plugin), str(self.core))
        text = "\n".join(lines)
        self.assertIn("override records of the core in the plugin: [('WRLD', '000803'), ('CELL', '000901')]", text)
        self.assertIn("children, core:     cell temporary children: REFR x1", text)
        self.assertIn("children, override: cell persistent children: REFR x1; cell temporary children: REFR x1", text)
        self.assertEqual(summary, ["WRLD 000803: no difference in header or subrecords", "CELL 000901: no difference in header or subrecords"])

    def test_check_refuses_a_plugin_built_against_another_core(self):
        # a plugin built against another core: the same tool refuses it (the cell id is the core's own)
        plugin = self.built("plugin-other")
        other = self.root / "other-core"
        shutil.copytree(self.fx, other)
        data = (other / "FO4TerrainCore.esm").read_bytes()
        marker = struct.pack("<fff", -989.257, 1146.514, 107.143)
        self.assertEqual(data.count(marker), 1)
        (other / "FO4TerrainCore.esm").write_bytes(data.replace(marker, struct.pack("<fff", -900.0, 1146.514, 107.143)))
        proc = self.run_tool("check", plugin, "--sf", other / "Starfield.esm", "--core", other / "FO4TerrainCore.esm")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAIL  FO4SF_CS_P is at", proc.stdout)

    def test_build_refuses_a_core_without_the_spawn_cell(self):
        plain = self.root / "plain"
        shutil.copytree(self.fx, plain)
        data = (plain / "FO4TerrainCore.esm").read_bytes()
        (plain / "FO4TerrainCore.esm").write_bytes(data.replace(b"FO4Core_RedRocketSpawn\0", b"FO4Core_NotTheSpawn\0\0\0\0"))
        proc = self.run_tool("build", "--sf", plain / "Starfield.esm", "--core", plain / "FO4TerrainCore.esm", "--out", self.root / "none")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("0 CELL FO4Core_RedRocketSpawn", proc.stderr)
        self.assertFalse((self.root / "none" / "FO4SFCoreStorage.esm").exists())


def cs_lines(p, t):
    """A FO4SFCS log, one arrival read at 60 s: p / t are "with", "behind", "none" (not loaded) or "no" (not installed)."""
    def ref(tag, v, lid):
        head = f"[11/10/2026 - 06:00:00PM] FO4SFCS rt=70.0 ref n=1 at=60 tag={tag} local={lid} plugin=FO4SFCoreStorage.esm"
        if v == "no":
            return head + " installed=False"
        if v == "none":
            return head + " found=False"
        w = "-16777000" if v == "with" else "-2113925120"
        same = "true" if v == "with" else "false"
        return head + f" found=True id=-2080373760 world={w} cell=none x=-985.0 y=1146.0 z=107.0 loaded=true disabled=false dist=4.0 sameworld={same}"
    return ["[11/10/2026 - 06:00:00PM] FO4SFCS rt=1.0 init quest=-2080373758 installed=true",
            "[11/10/2026 - 06:00:00PM] FO4SFCS rt=2.0 arrive n=1 world=-16777000 cell=none x=0 y=0 z=0",
            ref("CS_P", p, 2048), ref("CS_T", t, 2049)]


class ReaderTests(unittest.TestCase):
    def result(self, p, t):
        from fo4sf.planet import probe_log
        return probe_log.core_storage_result(cs_lines(p, t))[0]["result"]

    def test_verdicts(self):
        sys.path.insert(0, str(ROOT / "src"))
        self.assertEqual(self.result("none", "none"), "cell not loaded")     # the control first: CS_P is not judged
        self.assertEqual(self.result("with", "none"), "cell not loaded")
        self.assertEqual(self.result("with", "with"), "PASS")
        self.assertEqual(self.result("behind", "with"), "FAIL")
        self.assertEqual(self.result("none", "with"), "FAIL")
        self.assertEqual(self.result("with", "no"), "not installed")
        self.assertEqual(self.result("with", "behind"), "PASS")


class SessionTests(unittest.TestCase):
    INIT = "[11/10/2026 - 06:00:00PM] FO4SFCS rt=1.0 init quest=-2080373758 installed=true"

    def test_a_later_session_never_borrows_an_earlier_one(self):
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf.planet import probe_log
        good, cut = cs_lines("with", "with"), cs_lines("none", "with")
        cut = [x for x in cut if "tag=CS_P" not in x]              # a later session that never read CS_P
        both = good + cut
        self.assertEqual(probe_log.core_storage_result(good)[0]["result"], "PASS")
        self.assertEqual(probe_log.core_storage_result(cut)[0]["result"], "unknown")
        self.assertEqual(probe_log.core_storage_result(both)[0]["result"], "unknown")      # the last run only
        self.assertEqual(probe_log.core_storage_result(both, run=0)[0]["result"], "PASS")
        self.assertEqual(probe_log.core_storage_result([]), [])

    def test_an_empty_init_after_arrivals_starts_a_new_run(self):
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf.planet import probe_log
        empty = "[10/29/2026 - 03:00:00AM] FO4SFPP rt=9.0 init version=2 quest=1 world=none loc=none planet=none surface=none planetloc=none merge=true"
        arrive = "[10/29/2026 - 03:00:00AM] FO4SFPP rt=2.0 arrive n=1 world=1 cell=none x=0 y=0 z=0 probeworld=false"
        self.assertEqual(len(probe_log.runs([empty, arrive, empty])), 2)           # a later session
        self.assertEqual(len(probe_log.runs([empty, empty, arrive])), 1)           # OnInit twice before the first arrival

    def test_a_headerless_prefix_stays_its_own_run(self):
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf.planet import probe_log
        old_tail = [x for x in cs_lines("with", "with") if " ref n=" in x]          # ref lines only: no init, no arrive
        new = [x for x in cs_lines("none", "with") if "tag=CS_P" not in x]
        self.assertEqual(probe_log.core_storage_result(new)[0]["result"], "unknown")
        both = old_tail + new
        self.assertEqual(len(probe_log.runs(both)), 2)
        self.assertEqual(probe_log.core_storage_result(both)[0]["result"], "unknown")   # no borrowed CS_P

    def test_install_refuses_another_or_missing_core(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d)
            core = data / "FO4TerrainCore.esm"
            plan = {"inputs": {"core": {"sha256": ""}}}
            self.assertEqual(make_core_storage.core_pin_problems({}, str(data)), ["plan.json does not pin the core it was built against"])
            plan["inputs"]["core"]["sha256"] = "0" * 64
            self.assertIn("is not installed", make_core_storage.core_pin_problems({"inputs": {"core": {"sha256": "0" * 64}}}, str(data))[0])
            core.write_bytes(b"core B")
            pinned_a = {"inputs": {"core": {"sha256": "0" * 64}}}
            self.assertIn("not the core this stage was built against", make_core_storage.core_pin_problems(pinned_a, str(data))[0])
            pinned_b = {"inputs": {"core": {"sha256": make_core_storage.sha256(str(core))}}}
            self.assertEqual(make_core_storage.core_pin_problems(pinned_b, str(data)), [])


class InstallPreflightTests(unittest.TestCase):
    def test_a_stage_pinned_to_core_a_never_reaches_the_installer_on_core_b(self):
        import core_storage_install
        from types import SimpleNamespace
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            stage, game = d / "stage", d / "game"
            (stage / "Data" / "Scripts").mkdir(parents=True)
            (game / "Data").mkdir(parents=True)
            (stage / make_core_storage.PLUGIN).write_bytes(b"plugin")
            (stage / "Data" / "Scripts" / "x.pex").write_bytes(b"pex")
            (game / "Data" / "FO4TerrainCore.esm").write_bytes(b"core B")
            plan = {"kind": "core-storage-probe", "plugin": make_core_storage.PLUGIN, "plugins": [make_core_storage.PLUGIN],
                    "inputs": {"core": {"sha256": make_core_storage.sha256(str(stage / make_core_storage.PLUGIN))}},   # core A
                    "outputs": {make_core_storage.PLUGIN: make_core_storage.sha256(str(stage / make_core_storage.PLUGIN)),
                                "Data/Scripts/x.pex": make_core_storage.sha256(str(stage / "Data" / "Scripts" / "x.pex"))}}
            (stage / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            args = SimpleNamespace(dir=str(stage), starfield=str(game))
            with mock.patch.object(core_storage_install, "installer") as inst:
                with self.assertRaises(SystemExit) as cm:
                    core_storage_install.install(args)
                self.assertIn("not the core this stage was built against", str(cm.exception))
                inst.assert_not_called()
                plan["inputs"]["core"]["sha256"] = make_core_storage.sha256(str(game / "Data" / "FO4TerrainCore.esm"))
                (stage / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
                core_storage_install.install(args)
                inst.assert_called_once()


class ScriptTests(unittest.TestCase):
    def test_script_ids_and_names_match_the_plugin(self):
        psc = (ROOT / "scripts" / "core_storage" / "FO4SF_CoreStorageQuest.psc").read_text(encoding="utf-8")
        self.assertTrue(psc.startswith(f"Scriptname {make_core_storage.SCRIPT} extends Quest"))
        self.assertEqual(int(re.search(r"^int PersistentId = (0x[0-9A-Fa-f]+)", psc, re.M).group(1), 16), make_core_storage.IDS["cs_p"])
        self.assertEqual(int(re.search(r"^int TemporaryId = (0x[0-9A-Fa-f]+)", psc, re.M).group(1), 16), make_core_storage.IDS["cs_t"])
        self.assertIn(f'string Plugin = "{make_core_storage.PLUGIN}"', psc)
        self.assertIn("FO4SFCS rt=", psc)
        for secs in ("2.0", "10.0", "30.0"):
            self.assertIn(f"return {secs}", psc)
        self.assertNotIn("Property", psc.replace("NO properties", ""))      # a property would make CS_T persistent
        self.assertEqual(make_core_storage.PREFIX, "FO4SFCS rt=")
        src = (ROOT / "dotnet" / "CoreStorage" / "Program.cs").read_text(encoding="utf-8")
        self.assertIn(f'Script = "{make_core_storage.SCRIPT}"', src)
        self.assertIn('QuestEdid = "FO4SF_CoreStorageProbe"', src)           # run-2 section 3
        self.assertIn(f'CellEdid = "{make_core_storage.SPAWN_CELL}"', src)

    def test_verify_stage_pins_every_output(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "Data" / "Scripts").mkdir(parents=True)
            (d / make_core_storage.PLUGIN).write_bytes(b"plugin")
            (d / "Data" / "Scripts" / "x.pex").write_bytes(b"pex")
            plan = {"kind": "core-storage-probe", "plugin": make_core_storage.PLUGIN,
                    "outputs": {make_core_storage.PLUGIN: make_core_storage.sha256(d / make_core_storage.PLUGIN),
                                "Data/Scripts/x.pex": make_core_storage.sha256(d / "Data" / "Scripts" / "x.pex")}}
            (d / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            self.assertEqual(make_core_storage.verify_stage(str(d))[1], [])
            (d / "Data" / "Scripts" / "x.pex").write_bytes(b"changed")
            self.assertEqual(make_core_storage.verify_stage(str(d))[1], ["Data/Scripts/x.pex does not match plan.json"])


if __name__ == "__main__":
    unittest.main()
