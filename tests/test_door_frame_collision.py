"""Stationary door bodies must stay separate from the animated leaf (synthetic NIFs)."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from fo4sf import nif, sfnif


class DoorFrameCollisionTests(unittest.TestCase):
    def test_stationary_and_leaf_bodies_survive_round_trip(self):
        leaf_blob, left_blob, right_blob = b"leafbody", b"leftbody", b"rightbod"
        f = nif.parse(nif.serialize(sfnif.build_door_nif(
            b"Door", [], [], leaf_collision=leaf_blob,
            frame_collision_blobs=[left_blob, right_blob])))
        nodes = {f.strings[struct.unpack_from("<i", b)[0]]: i
                 for i, b in enumerate(f.blocks) if f.type_of(i) == "NiNode"}
        moving = nif.descendants(f, nodes[sfnif.DOOR_TEMPLATE["anim_root"]])
        fixed = nif.descendants(f, nodes[b"Frame"])
        bodies = {}
        for i, block in enumerate(f.blocks):
            if f.type_of(i) != "bhkNPCollisionObject":
                continue
            target, _, data = struct.unpack_from("<iHi", block)
            size = struct.unpack_from("<I", f.blocks[data])[0]
            bodies[f.blocks[data][4:4 + size]] = target
        self.assertEqual(set(bodies), {leaf_blob, left_blob, right_blob})
        self.assertIn(bodies[leaf_blob], moving)
        for blob in (left_blob, right_blob):
            self.assertIn(bodies[blob], fixed)
            self.assertNotIn(bodies[blob], moving)
            for actual, expected in zip(nif.world_transforms(f)(bodies[blob])[0], sfnif.DOOR_TEMPLATE["hinge_pos"]):
                self.assertAlmostEqual(actual, expected, places=6)

    def test_frame_only_collision_enables_havok(self):
        f = sfnif.build_door_nif(b"Door", [], [], frame_collision_blobs=[b"framebod"])
        flags = [struct.unpack_from("<iI", b)[1] for i, b in enumerate(f.blocks) if f.type_of(i) == "BSXFlags"]
        self.assertEqual(flags, [0x0A])
        self.assertEqual(sum(f.type_of(i) == "bhkNPCollisionObject" for i in range(len(f.blocks))), 1)

    def test_omitted_frame_collision_preserves_existing_output(self):
        self.assertEqual(nif.serialize(sfnif.build_door_nif(b"Door", [], [])),
                         nif.serialize(sfnif.build_door_nif(b"Door", [], [], frame_collision_blobs=[])))


if __name__ == "__main__":
    unittest.main()
