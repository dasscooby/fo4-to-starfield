import struct
import unittest
from test_review_fixes import av_fields, trishape_block
from fo4sf import door_motion, nif


def fixture():
    f = nif.NifFile(bs_version=130)
    root, a, b, op = [f.string_index(s) for s in (b"Root", b"LeafA", b"LeafB", b"Open")]
    identity = (1, 0, 0, 0, 1, 0, 0, 0, 1)
    f.add_block("NiNode", av_fields(root, (70, 0, 0), identity, 1) + struct.pack("<Iii", 2, 1, 2))
    f.add_block("NiNode", av_fields(a, (0, 0, 0), identity, 1) + struct.pack("<Ii", 1, 3))
    f.add_block("NiNode", av_fields(b, (140, 0, 0), identity, 1) + struct.pack("<Ii", 1, 4))
    for _ in range(2):
        f.add_block("BSTriShape", trishape_block([(0, 0, 0), (70, 0, 0), (0, 70, 0)], [(0, 1, 2)]))
    targets = b"".join(struct.pack("<iiBiiiii", -1, -1, 0, name, -1, -1, -1, -1) for name in (a, b))
    f.add_block("NiControllerSequence", struct.pack("<iII", op, 2, 0) + targets)
    f.footer = struct.pack("<II", 1, 0)
    return f


class DoorMotionTests(unittest.TestCase):
    def test_independent_leaf_and_world_pivots_preserved(self):
        report = door_motion.inspect(fixture())
        self.assertEqual(report["single_hinge_shape_blocks"], [3])
        self.assertEqual(report["animated_shapes_outside_single_hinge"], [4])
        self.assertTrue(report["requires_additional_motion_support"])
        self.assertEqual(report["sequences"][0]["targets"][1]["pivot_source_units"], [210, 0, 0])

    def test_truncated_target_list_rejected(self):
        f = fixture()
        f.blocks[-1] = f.blocks[-1][:-1]
        with self.assertRaises(nif.NifError):
            door_motion.inspect(f)

    def test_missing_binding_reported(self):
        f = fixture()
        struct_name = f.string_index(b"Missing")
        data = bytearray(f.blocks[-1])
        struct.pack_into("<i", data, 12 + 29 + 9, struct_name)
        f.blocks[-1] = bytes(data)
        self.assertTrue(door_motion.inspect(f)["issues"])


if __name__ == "__main__":
    unittest.main()
