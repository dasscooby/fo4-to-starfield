"""Map-marker LCSR through the actual terrain writer (dotnet/TerrainOverlays) on the synthetic master of
test_terrain_reference_identity (dotnet/TerrainIdentityFixture map-marker extra arg), never a game: Grid from
spawn_cell and Unknown -1 serialize as the vanilla 0xFFFFFFFF tail (docs/terrain/map-markers.md)."""
import copy
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402
import vmad_patch as vp  # noqa: E402

subrecords, field = tlw.subrecords, tlw.field
MAPMARKER_REF_TYPE = 0x0002271F
LCSR_TAIL = 0xFFFFFFFF


class TerrainMapMarkerWriterTests(unittest.TestCase):
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    promote = tri.TerrainReferenceIdentityTests.promote

    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET 9 SDK/runtime needed for actual writer test")
        sdks = subprocess.run([cls.dotnet, "--list-sdks"], capture_output=True, text=True, check=True)
        if not any(line.startswith("9.") for line in sdks.stdout.splitlines()):
            raise unittest.SkipTest(".NET 9 SDK/runtime needed for actual writer test")
        build = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet/TerrainIdentityFixture"),
                                "-c", "Release", "--nologo"], capture_output=True, text=True)
        if build.returncode:
            raise AssertionError(build.stdout + build.stderr)
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-mapmarker-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.master = cls.root / "master/Starfield.esm"
        fixture = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        subprocess.run([cls.dotnet, str(fixture), str(cls.master), "map-marker"], capture_output=True, check=True)
        cls.writer = Path(os.environ.get("FO4SF_TERRAIN_WRITER",
                                         ROOT / "dotnet/TerrainOverlays/bin/Release/net9.0/TerrainOverlays.dll"))
        cls.params = {
            "plugin": "Synthetic.esm", "hmin": 0, "hmax": 1, "alignment": "absolute", "hnam": 0,
            "objects": "objects.json", "overlays": [{"world": "SyntheticWorld", "block": "SyntheticBlock",
            "location": "SyntheticLocation", "tag": "Synthetic", "n": 2, "cell_min": 0, "cell_max": 1,
            "btd_path": "Terrain/Synthetic.btd", "fnam": [0] * 4, "bounds_min_m": 0, "bounds_max_m": 200,
            "spawn": [1, 1, 2], "spawn_cell": [1, 0], "coc": "SyntheticSpawn",
            "anchor": {"form_id": 0x800, "edid": "SyntheticAnchor", "local": [1, 1, 2]}}]}
        cls.objects = {"world": "SyntheticWorld", "bases": [{"edid": "SyntheticBase", "model": "synthetic.nif"}],
                       "refs": [{"src": f"{i + 1:06X}:Synthetic.esm", "base": 0, "cell": cell,
                                 "pos": pos, "rot": [0, 0, i / 10], "scale": 1 + i / 10, "disabled": False}
                                for i, (cell, pos) in enumerate(zip(([0, 0], [0, 1], [1, 1]),
                                                                   ([1, 2, 3], [4, 101, 6], [101, 102, 9])))]}

    def test_lcsr_tail_is_ffffffff_and_grid_follows_spawn_cell(self):
        proc, stage = self.run_writer(self.objects, "map-marker-lcsr")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        ids = json.loads((stage / "formids.json").read_text())
        self.assertIn("map_markers", ids)
        marker = int(ids["map_markers"]["SyntheticWorld"], 16)
        recs = tri.records(stage / "Synthetic.esm")
        lctn = next(r for r in recs.values() if r[0] == b"LCTN")
        lcsr = field(lctn[1], b"LCSR")
        self.assertIsNotNone(lcsr)
        self.assertEqual(len(lcsr), 20)
        lcrt, refr, wrld, grid, tail = struct.unpack_from("<5I", lcsr)
        self.assertEqual(lcrt, MAPMARKER_REF_TYPE)
        self.assertEqual(refr & 0xFFFFFF, marker)
        self.assertEqual(grid, struct.unpack("<I", struct.pack("<hh", 0, 1))[0])  # Y then X of spawn_cell [1, 0]
        self.assertEqual(tail, LCSR_TAIL)
        self.assertEqual(recs[marker][0], b"REFR")
        self.assertEqual(recs[marker][3] & 0xC00, 0x400)                     # persistent, enabled (not LC172's 0xC00)
        self.assertIsNone(field(lctn[1], b"LCID"))

    def test_multiple_markers_preserve_existing_records_and_serialize_each_link(self):
        self.params = copy.deepcopy(type(self).params)
        before, baseline = self.run_writer(self.objects, "multi-before")
        self.assertEqual(before.returncode, 0, before.stdout + before.stderr)
        entries = [
            {"tag": tag, "name": tag + " synthetic", "pos": pos, "cell": cell}
            for tag, pos, cell in (
                ("RedRocket", [1, 1, 2], [1, 0]),
                ("Sanctuary", [20, 120, 3], [0, 1]),
                ("Vault111", [120, 130, 4], [1, 1]),
                ("Concord", [140, 20, 5], [1, 0]),
            )
        ]
        self.params["overlays"][0]["map_markers"] = entries
        after, candidate = self.run_writer(self.objects, "multi-after")
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)
        old = json.loads((baseline / "formids.json").read_text())
        new = json.loads((candidate / "formids.json").read_text())
        self.assertEqual(old["map_markers"], new["map_markers"])
        for key in old.keys() - {"map_marker_refs"}:
            self.assertEqual(old[key], new[key], key)
        ids = new["map_marker_refs"]["SyntheticWorld"]
        self.assertEqual(set(ids), {e["tag"] for e in entries})
        self.assertEqual(len(set(ids.values())), len(entries))
        old_records = tri.records(baseline / "Synthetic.esm")
        new_records = tri.records(candidate / "Synthetic.esm")
        for value in old["refs"].values():
            self.assertEqual(old_records[int(value, 16)], new_records[int(value, 16)])

        plugin = vp.Plugin.read(candidate / "Synthetic.esm")
        own = len(plugin.masters()) << 24
        world = next(r for r, _ in plugin.walk() if r.sig == b"WRLD")
        location = next(r for r, _ in plugin.walk() if r.sig == b"LCTN")
        location_fields = dict(location.fields())
        rows = list(struct.iter_unpack("<IIIhhI", location_fields[b"LCSR"]))
        expected_rows = []
        anchor = next((r, path) for r, path in plugin.walk() if r.fid == own | 0x800)
        source = vp.Plugin.read(self.master)
        source_fields = dict(next(r for r, _ in source.walk() if r.fid == 0x3E5E12).fields())
        for index, entry in enumerate(entries):
            fid = own | int(ids[entry["tag"]], 16)
            record, path = next((r, p) for r, p in plugin.walk() if r.fid == fid)
            fields = dict(record.fields())
            self.assertEqual(path, anchor[1])
            self.assertTrue(any(kind == 8 for kind, _ in path))
            self.assertEqual(record.flags & 0xC00, 0xC00)
            self.assertEqual(struct.unpack("<I", fields[b"NAME"])[0], 0x10)
            self.assertEqual(fields[b"XMRK"], b"")
            self.assertEqual(fields[b"FULL"].rstrip(b"\0").decode(), entry["name"])
            suffix = "" if index == 0 else entry["tag"]
            self.assertEqual(fields[b"EDID"].rstrip(b"\0").decode(), "SyntheticWorldMapMarker" + suffix)
            self.assertEqual(struct.unpack("<6f", fields[b"DATA"])[:3], tuple(entry["pos"]))
            for sig in (b"FNAM", b"TNAM"):
                self.assertEqual(fields[sig], source_fields[sig])
            expected_rows.append((MAPMARKER_REF_TYPE, fid, world.fid,
                                  entry["cell"][1], entry["cell"][0], LCSR_TAIL))
        self.assertEqual(rows, expected_rows)
        self.assertEqual(list(struct.iter_unpack("<I", location_fields[b"LCID"])),
                         [(row[1],) for row in expected_rows])
        self.assertEqual(plugin.hedr()[2], max(new_records) + 1)

    def test_params_map_markers_write_one_chain_each(self):
        # the four-marker loop (make_core64c stage "map_markers"), judged by make_core64c check's map_marker_problems
        import copy
        import importlib.util
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        spec = importlib.util.spec_from_file_location("make_core64c", ROOT / "scripts" / "terrain" / "make_core64c.py")
        mk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mk)
        params = copy.deepcopy(self.params)
        ov = params["overlays"][0]
        ov["map_markers"] = [{"tag": "RedRocket", "name": "Red Rocket Truck Stop", "pos": ov["spawn"], "cell": [0, 0]},
                             {"tag": "Sanctuary", "name": "Sanctuary Hills", "pos": [150.0, 50.0, 1.0], "cell": [1, 0]},
                             {"tag": "Concord", "name": "Concord", "pos": [50.0, 150.0, 1.5], "cell": [0, 1]}]
        saved, self.params = self.params, params
        try:
            proc, stage = self.run_writer(self.objects, "map-marker-params")
        finally:
            self.params = saved
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        ids = json.loads((stage / "formids.json").read_text())
        self.assertEqual(sorted(ids["map_marker_refs"]["SyntheticWorld"]), ["Concord", "RedRocket", "Sanctuary"])
        self.assertEqual(ids["map_markers"]["SyntheticWorld"], ids["map_marker_refs"]["SyntheticWorld"]["RedRocket"])
        new = mk.overlay_records.walk_plugin(stage / "Synthetic.esm")
        self.assertEqual(mk.map_marker_problems(new["records"], len(new["masters"]), ov, ids), [])

    def test_missing_template_skips_map_marker_restore(self):
        identity = tri.TerrainReferenceIdentityTests()
        identity.dotnet = self.dotnet
        identity.writer = self.writer
        identity.params = self.params
        identity.objects = self.objects
        identity.root = self.root
        identity.master = self.root / "master-plain/Starfield.esm"
        fixture = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        identity.master.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.dotnet, str(fixture), str(identity.master)], capture_output=True, check=True)
        proc, stage = identity.run_writer(self.objects, "map-marker-skip")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        ids = json.loads((stage / "formids.json").read_text())
        self.assertNotIn("map_markers", ids)
        self.assertIn("003E5E12 missing", proc.stdout + proc.stderr)
