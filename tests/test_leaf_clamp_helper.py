"""Test the leaf half-extent floor helper and that thin leaves never write the 0.02 crash float."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import sfcollision  # noqa: E402


def fake_template():
    b = bytearray(sfcollision.BLOB_SIZE)
    b[0:8] = b"\x00\x00\x18\x18TAG0"
    b[100:112] = b"hknpBoxShape"
    struct.pack_into("<3f", b, 528, 1.0, 0.0, 0.0)
    struct.pack_into("<3f", b, 544, 0.0, 1.0, 0.0)
    struct.pack_into("<3f", b, 560, 0.0, 0.0, 1.0)
    return bytes(b)


CRASH_FLOAT = 0.02
CRASH_BITS = 0x3CA3D70A


class LeafClampTests(unittest.TestCase):
    def test_clamp_leaf_half_floors_thin_axis(self):
        thin = (0.01, 0.4, 0.7)
        floored = sfcollision.clamp_leaf_half(thin)
        self.assertEqual(floored, (sfcollision.MIN_LEAF_HALF, 0.4, 0.7))
        self.assertGreater(floored[0], CRASH_FLOAT)

    def test_thin_leaf_blob_never_writes_crash_float(self):
        tmpl = fake_template()
        floored = sfcollision.clamp_leaf_half((0.014, 0.5, 0.8))
        blob = sfcollision.box_blob(tmpl, (0.0, 0.0, 0.0), floored)
        _, written = sfcollision.read_box(blob)
        self.assertAlmostEqual(written[0], sfcollision.MIN_LEAF_HALF, places=6)
        for off in range(0, len(blob) - 3, 4):
            bits, = struct.unpack_from("<I", blob, off)
            self.assertNotEqual(bits, CRASH_BITS, f"crash float written at offset {off}")

    def test_clamp_preserves_thick_axes(self):
        thick = (0.1, 0.2, 0.3)
        self.assertEqual(sfcollision.clamp_leaf_half(thick), thick)


if __name__ == "__main__":
    unittest.main()
