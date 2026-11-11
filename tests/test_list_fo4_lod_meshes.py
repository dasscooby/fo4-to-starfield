"""Offline path-mapping tests for scripts/lod/list_fo4_lod_meshes.py. No game files."""
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "lod", "list_fo4_lod_meshes.py")
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import convert_static, fo4land, surface_map  # noqa: E402


def load_script():
    spec = importlib.util.spec_from_file_location("list_fo4_lod_meshes", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lod = load_script()


def rec(typ, fid, fields, compress=False):
    data = b"".join(sig + struct.pack("<H", len(d)) + d for sig, d in fields)
    flags = 0
    if compress:
        data = struct.pack("<I", len(data)) + zlib.compress(data)
        flags = fo4land.COMPRESSED
    return typ + struct.pack("<III", len(data), flags, fid) + b"\0" * 8 + data


def grup(label, gtype, items):
    body = b"".join(items)
    if isinstance(label, int):
        label = struct.pack("<I", label)
    return b"GRUP" + struct.pack("<I4si", 24 + len(body), label, gtype) + b"\0" * 8 + body


def mnam_slots(*paths):
    buf = bytearray(lod.MNAM_SLOT * lod.MNAM_LEVELS)
    for i, path in enumerate(paths[:lod.MNAM_LEVELS]):
        raw = path.encode("cp1252") + b"\0"
        buf[i * lod.MNAM_SLOT:i * lod.MNAM_SLOT + len(raw)] = raw
    return bytes(buf)


def refr(fid, base, pos):
    return rec(b"REFR", fid, [
        (b"NAME", struct.pack("<I", base)),
        (b"DATA", struct.pack("<6f", pos[0], pos[1], pos[2], 0.0, 0.0, 0.0)),
    ])


def synthetic_plugin_bytes():
    tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 0, 0))])
    stat = rec(b"STAT", 0x100, [
        (b"EDID", b"RedRExt_Workshop01\0"),
        (b"OBND", struct.pack("<6h", -50, -50, 0, 60, 60, 300)),
        (b"MODL", b"Interiors\\RedRocket\\RedRExt_Workshop01.nif\0"),
        (b"MNAM", mnam_slots("LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif", "", "", "")),
    ])
    bare = rec(b"STAT", 0x101, [
        (b"EDID", b"NoLodRock\0"),
        (b"MODL", b"Landscape\\Rocks\\Rock.nif\0"),
    ])
    stats = grup(b"STAT", 0, [stat, bare])
    pcell = rec(b"CELL", 0x200, [(b"EDID", b"\0"), (b"XCLC", struct.pack("<iiI", 0, 0, 0))])
    cell = rec(b"CELL", 0x300, [(b"DATA", b"\0\0"), (b"XCLC", struct.pack("<iiI", -17, 19, 0))])
    kids = grup(0x300, 6, [grup(0x300, 9, [
        rec(b"LAND", 0x301, [(b"VHGT", b"\0" * 1093)]),
        refr(0x211C0, 0x100, (-69232.0, 80304.0, 7360.0)),
        refr(0x211C1, 0x101, (-69200.0, 80300.0, 7360.0)),
    ])])
    world_items = [
        pcell,
        grup(0x200, 6, [grup(0x200, 8, [])]),
        grup(b"\0\0\0\0", 4, [grup(b"\0\0\0\0", 5, [cell, kids])]),
    ]
    wrld = rec(b"WRLD", 0x3C, [(b"EDID", b"Commonwealth\0")])
    return tes4 + stats + grup(b"WRLD", 0, [wrld, grup(0x3C, 1, world_items)])


class PathMappingTests(unittest.TestCase):
    def test_mnam_four_260_byte_slots(self):
        raw = mnam_slots(
            "LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif",
            "LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif",
            "",
            "",
        )
        self.assertEqual(len(raw), 1040)
        paths = lod.parse_stat_mnam(raw)
        self.assertEqual(paths[0], "LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif")
        self.assertEqual(paths[1], "LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif")
        self.assertEqual(paths[2], "")
        self.assertEqual(paths[3], "")

    def test_mnam_ignores_junk_after_first_null(self):
        raw = bytearray(1040)
        raw[0:4] = b"LOD\x00"
        raw[4:8] = b"\xff\xff\xff\xff"
        self.assertEqual(lod.parse_stat_mnam(bytes(raw))[0], "LOD")

    def test_archive_path_prefixes_meshes(self):
        self.assertEqual(
            lod.fo4_lod_archive_path("LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif"),
            "meshes/LOD/Interiors/RedRocket/RedRExtAll01_LOD.nif",
        )
        self.assertEqual(
            lod.fo4_lod_archive_path("Meshes\\LOD\\x.nif"),
            "Meshes/LOD/x.nif",
        )

    def test_converted_full_mesh_matches_pipeline_prefix(self):
        self.assertEqual(
            lod.converted_full_mesh_path("Interiors\\RedRocket\\RedRExt_Workshop01.nif"),
            "meshes/fo4core/interiors/redrocket/redrext_workshop01.nif",
        )
        self.assertEqual(
            lod.converted_full_mesh_path("Meshes\\Architecture\\Buildings\\House.nif", "fo4core"),
            "meshes/fo4core/architecture/buildings/house.nif",
        )

    def test_per_object_generated_keyed_by_converted_full_mesh(self):
        full = "meshes/fo4core/interiors/redrocket/redrext_workshop01.nif"
        self.assertEqual(
            lod.per_object_generated_lod_path(full, 0),
            "meshes/lod/generated/meshes/fo4core/interiors/redrocket/redrext_workshop01_lod_0.nif",
        )
        self.assertEqual(
            lod.per_object_generated_lod_path(full, 3),
            "meshes/lod/generated/meshes/fo4core/interiors/redrocket/redrext_workshop01_lod_3.nif",
        )
        with self.assertRaises(ValueError):
            lod.per_object_generated_lod_path(full, 4)

    def test_convert_static_out_name_writes_generated_nif_key(self):
        full = "meshes/fo4core/interiors/redrocket/redrext_workshop01.nif"
        out_name = lod.convert_static_out_name(full, 1)
        self.assertEqual(
            f"meshes/{out_name}.nif",
            lod.per_object_generated_lod_path(full, 1),
        )

    def test_placeholder_material_is_referenced_not_written(self):
        self.assertEqual(lod.PLACEHOLDER_MATERIAL, convert_static.PLACEHOLDER_MATERIAL)
        self.assertEqual(
            lod.PLACEHOLDER_MATERIAL,
            "Materials\\Common\\Metal\\MetalIronCast01.mat",
        )
        note = lod.starfield_targets("Interiors\\RedRocket\\RedRExt_Workshop01.nif")
        self.assertEqual(note["material"], convert_static.PLACEHOLDER_MATERIAL)
        self.assertIn("references PLACEHOLDER_MATERIAL", note["convert_static_as_stands"])
        self.assertIn("does not write a .mat", note["convert_static_as_stands"])
        self.assertIn("Generated .mat output is the pipeline path", note["convert_static_as_stands"])

    def test_per_block_and_lodsettings_overlay_range(self):
        self.assertEqual(
            lod.per_block_object_lod_paths(),
            [
                "meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.1.0.0.nif",
                "meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.2.0.0.nif",
                "meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.4.0.0.nif",
                "meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.8.0.0.nif",
            ],
        )
        raw = lod.overlay_lodsettings_bytes()
        self.assertEqual(len(raw), 20)
        self.assertEqual(struct.unpack_from("<iii", raw), (-32, -32, 64))
        self.assertEqual(raw[12:], b"\x00" * 8)
        self.assertEqual(lod.overlay_lodsettings_rel(), surface_map.lodsettings_rel(surface_map.WORLD_EDID))
        with self.assertRaises(ValueError):
            lod.overlay_lodsettings_bytes(size=0)

    def test_landmark_cells_include_the_three_named_cells(self):
        cells = lod.landmark_cell_map(0)
        self.assertEqual(cells[(-17, 19)], ["redrocket"])
        self.assertEqual(cells[(-20, 21)], ["sanctuary"])
        self.assertEqual(cells[(-15, 17)], ["concord"])
        self.assertEqual(len(lod.landmark_cell_map(1)), 26)


class IsolatedCliTests(unittest.TestCase):
    def test_help_under_isolated_python(self):
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT, "-h"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("list_fo4_lod_meshes.py", proc.stdout)
        self.assertIn("--plugin", proc.stdout)

    def test_missing_plugin_exits_2(self):
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT, "--plugin", os.path.join(ROOT, "no-such.esm"),
             "--fo4-data", ROOT],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("plugin not found", proc.stderr)

    def _assert_isolated_scan(self, cwd):
        with tempfile.TemporaryDirectory() as tmp:
            esm = os.path.join(tmp, "Fallout4.esm")
            with open(esm, "wb") as fh:
                fh.write(synthetic_plugin_bytes())
            proc = subprocess.run(
                [sys.executable, "-I", SCRIPT, "--plugin", esm, "--fo4-data", tmp, "--radius", "0"],
                capture_output=True,
                text=True,
                cwd=cwd,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("No module named", proc.stderr)
            report = json.loads(proc.stdout)
        self.assertEqual(report["row_count"], 1)
        row = report["rows"][0]
        self.assertEqual(row["ref"], "000211c0")
        self.assertEqual(row["base"], "00000100")
        self.assertEqual(row["base_edid"], "RedRExt_Workshop01")
        self.assertEqual(row["fo4_lod_paths"][0]["path"], "LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif")
        self.assertFalse(row["fo4_lod_paths"][0]["present"])

    def test_isolated_scan_from_repo_root(self):
        self._assert_isolated_scan(ROOT)

    def test_isolated_scan_from_unrelated_cwd(self):
        with tempfile.TemporaryDirectory() as cwd:
            self._assert_isolated_scan(cwd)


class SyntheticScanTests(unittest.TestCase):
    def test_scan_emits_row_for_stat_with_mnam(self):
        with tempfile.TemporaryDirectory() as tmp:
            esm = os.path.join(tmp, "Fallout4.esm")
            with open(esm, "wb") as fh:
                fh.write(synthetic_plugin_bytes())
            report = lod.scan(esm, tmp, radius=0)
        self.assertEqual(report["row_count"], 1)
        row = report["rows"][0]
        self.assertEqual(row["cell"], [-17, 19])
        self.assertEqual(row["ref"], "000211c0")
        self.assertEqual(row["base_edid"], "RedRExt_Workshop01")
        self.assertEqual(row["fo4_lod_paths"][0]["path"], "LOD\\Interiors\\RedRocket\\RedRExtAll01_LOD.nif")
        self.assertFalse(row["fo4_lod_paths"][0]["present"])
        self.assertEqual(
            row["starfield"]["converted_full_mesh"],
            "meshes/fo4core/interiors/redrocket/redrext_workshop01.nif",
        )
        self.assertEqual(report["lodsettings"]["path"], "lodsettings/fo4core_commonwealth.lod")
        self.assertEqual(len(report["per_block_targets"]), 4)


if __name__ == "__main__":
    unittest.main()
