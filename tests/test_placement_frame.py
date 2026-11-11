"""Synthetic-fixture tests for the placement-frame oracle."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def rec(typ, fid, fields):
    data = b"".join(sig + struct.pack("<H", len(d)) + d for sig, d in fields)
    return typ + struct.pack("<III", len(data), 0, fid) + b"\0" * 8 + data


def grup(label, gtype, items):
    body = b"".join(items)
    if isinstance(label, int):
        label = struct.pack("<I", label)
    return b"GRUP" + struct.pack("<I4si", 24 + len(body), label, gtype) + b"\0" * 8 + body


class PlacementFrameTests(unittest.TestCase):
    def test_flags_outside_cell_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            core_path = os.path.join(d, "core.esp")
            plug_path = os.path.join(d, "mission.esp")

            tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 1.0, 0, 0))])
            wrld = rec(b"WRLD", 0x803, [(b"EDID", b"TestWorld\0"), (b"DNAM", struct.pack("<ff", 0., 0.))])
            cell = rec(b"CELL", 0x100, [(b"EDID", b"CoreCell\0"), (b"XCLC", struct.pack("<iiI", 0, 0, 0))])
            g = b"\0" * (33 * 33)
            vhgt = struct.pack("<f", 0.0) + g + b"\0\0\0"
            land = rec(b"LAND", 0x101, [(b"VHGT", vhgt)])
            temp_land = grup(0, 9, [land])
            cell_children = grup(0x100, 6, [temp_land])
            world_children = grup(0x803, 1, [cell, cell_children])
            top = grup(b"WRLD", 0, [wrld, world_children])
            with open(core_path, "wb") as f:
                f.write(tes4 + top)

            wrld2 = rec(b"WRLD", 0x803, [(b"EDID", b"TestWorld\0"), (b"DNAM", struct.pack("<ff", 0., 0.))])
            cell2 = rec(b"CELL", 0x100, [(b"EDID", b"MissionCell\0"), (b"XCLC", struct.pack("<iiI", 0, 0, 0))])
            good = rec(b"REFR", 0x200, [(b"NAME", struct.pack("<I", 0x10)),
                                        (b"DATA", struct.pack("<6f", 50., 50., 0., 0., 0., 0.))])
            bad = rec(b"REFR", 0x201, [(b"NAME", struct.pack("<I", 0x10)),
                                       (b"DATA", struct.pack("<6f", 150., 50., 0., 0., 0., 0.))])
            missing = rec(b"ACHR", 0x202, [(b"NAME", struct.pack("<I", 0x10))])
            temp_refs = grup(0, 9, [good, bad, missing])
            cell_children2 = grup(0x100, 6, [temp_refs])
            world_children2 = grup(0x803, 1, [cell2, cell_children2])
            top2 = grup(b"WRLD", 0, [wrld2, world_children2])
            with open(plug_path, "wb") as f:
                f.write(tes4 + top2)

            cmd = [sys.executable, os.path.join(ROOT, "scripts/oracles/placement_frame.py"),
                   "--plugin", plug_path, "--core", core_path,
                   "--world-edid", "TestWorld", "--json"]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, msg=proc.stderr + proc.stdout)
            data = json.loads(proc.stdout)
            self.assertGreaterEqual(data["flagged"], 3)
            self.assertEqual(data["cell_size_m"], 100.0)
            # synthetic cell is parsed as persistent, so no spatial coverage; all flagged
            for e in data["refs"]:
                self.assertTrue(e["flag"])
            missing_entry = next(e for e in data["refs"] if e["fid"] == "00000202")
            self.assertEqual(missing_entry["reason"], "missing_or_invalid_position")


if __name__ == "__main__":
    unittest.main()
