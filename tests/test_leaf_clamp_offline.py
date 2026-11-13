"""Offline reproduction of the 0.02 leaf-clamp that crashed Red Rocket (issue #458 task 1).

Converts a tiny synthetic door leaf whose natural half-extent is below 0.05 and asserts:
- no written float in the output NIF equals the bit pattern 0x3ca3d70a (float 0.02)
- the leaf box half-extent is floored at MIN_LEAF_HALF (0.05)

This fails on the parent of the #455 fix (where the floor was 0.02) and passes on main.
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
from fo4sf import convert_static, nif, sfcollision  # noqa: E402
from test_door_two_panels import door_nif, collision_targets  # noqa: E402
from test_collision import fake_template  # noqa: E402

IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1)
CRASH_FLOAT = struct.pack("<I", 0x3CA3D70A)  # 0.02f


class LeafClampOfflineTests(unittest.TestCase):
    def test_thin_leaf_floor_and_no_crash_float(self):
        # 2 FO4 units deep ≈ 0.0286 m → half-extent ≈ 0.014 m, below 0.05
        f = door_nif([("Leaf", (0, 0, 0), IDENTITY,
                       [(0, (0, 0, 0, 1)), (1, (0, 0, -0.7071, 0.7071))], None)])
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        files, _off, _b = convert_static.convert_door(
            nif.serialize(f),
            "fo4port/doors/thinleaf",
            ["Materials\\x.mat"] * count,
            collision_template=fake_template(),
        )
        nif_bytes = files["meshes/fo4port/doors/thinleaf.nif"]

        self.assertNotIn(CRASH_FLOAT, nif_bytes, "found the Red Rocket crash float 0.02")

        parsed = nif.parse(nif_bytes)
        blobs = list(collision_targets(parsed).values())
        self.assertTrue(blobs, "no collision blob written")
        _c, half = sfcollision.read_box(blobs[0])
        self.assertGreaterEqual(min(half), sfcollision.MIN_LEAF_HALF - 1e-6)
        self.assertEqual(sfcollision.MIN_LEAF_HALF, 0.05)


if __name__ == "__main__":
    unittest.main()
