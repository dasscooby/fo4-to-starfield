import importlib.util
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from test_collision import fake_template
from fo4sf import nif, sfnif

spec = importlib.util.spec_from_file_location("collision_nodes", Path(__file__).resolve().parents[1] / "scripts/oracles/collision_nodes.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

IDENT = struct.pack("<3f9ff", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0)


def fo4_lift(sequence=True):
    """Synthetic FO4-shaped NIF: Root > [Platform > Floor, Shaft]; collision on Floor (x2) and Shaft; a sequence animating Platform."""
    f = nif.NifFile()
    f.bs_version = 130
    s = f.string_index

    def node(name, children):
        return f.add_block("NiNode", struct.pack("<iIiI", s(name), 0, -1, 0xE) + IDENT + struct.pack("<iI", -1, len(children))
                           + b"".join(struct.pack("<i", c) for c in children))
    # block order: 0 Root, 1 Platform, 2 Floor, 3 Shaft; root's children patched after creation
    node(b"Root", [1, 3])
    node(b"Platform", [2])
    node(b"Floor", [])
    node(b"Shaft", [])
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"junk")          # 4
    for target in (2, 2, 3):
        f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", target, 0x80, 4, 0))
    if sequence:
        blk = struct.pack("<iIi", s(b"Up"), 1, 0) + struct.pack("<iiB", -1, -1, 0) + struct.pack("<5i", s(b"Platform"), -1, -1, -1, -1)
        f.add_block("NiControllerSequence", blk)
    f.footer = struct.pack("<Ii", 1, 0)
    return nif.serialize(f)


class CollisionNodesTests(unittest.TestCase):
    def test_collision_under_animated_node_is_moving_and_shaft_is_static(self):
        rep = tool.read(fo4_lift())
        self.assertEqual(rep["format"], "fo4")
        self.assertEqual(rep["collision_objects"], 3)
        self.assertEqual(rep["sequences"], {"Up": ["Platform"]})
        self.assertEqual(rep["by_binding"], {"under-animated": 2, "static-node": 1})
        self.assertEqual([o["path"] for o in rep["objects"]], ["Root/Platform/Floor", "Root/Platform/Floor", "Root/Shaft"])
        self.assertEqual(rep["objects"][0]["motion"], "unread")       # junk physics blob: reported, not guessed
        self.assertIn("2 of 3", rep["reading"])

    def test_no_sequence_means_no_clip_can_carry_anything(self):
        rep = tool.read(fo4_lift(sequence=False))
        self.assertEqual(rep["by_binding"], {"static-node": 3})
        self.assertIn("no NiControllerSequence", rep["reading"])

    def test_converted_static_nif_has_flat_collision_nodes_and_no_clip(self):
        bodies = []
        for motion in (0, 1):
            d = bytearray(fake_template())
            struct.pack_into("<I", d, 240, motion)
            bodies.append(bytes(d))
        rep = tool.read(nif.serialize(sfnif.build_static_nif(b"Lift", [], collision_blob=None, child_collision_blobs=bodies)))
        self.assertEqual(rep["format"], "starfield")
        self.assertEqual(rep["collision_objects"], 2)
        self.assertEqual({o["binding"] for o in rep["objects"]}, {"static-node"})
        self.assertEqual([o["motion"] for o in rep["objects"]], ["static", "keyframed"])
        self.assertEqual([o["target"] for o in rep["objects"]], ["Collision0", "Collision1"])
        self.assertFalse(rep["has_NiControllerManager"])
        self.assertIn("no NiControllerSequence", rep["reading"])

    def test_bounds_are_per_body_not_the_whole_shared_system(self):
        """PC run 13 Nov printed one identical box on all 17 FO4 rows: bounds came from every body of the shared system."""
        from fo4sf import fo4collision as fc
        positions = {0: (0.0, 0.0, 0.0), 1: (10.0, 0.0, 5.0)}
        shapes = {0: 1000, 1: 2000}

        class Pack:
            def __init__(self, blob):
                pass

            def objects(self):
                return [(1, "hknpPhysicsSystemData"), (1000, "hknpConvexPolytopeShape"), (2000, "hknpConvexPolytopeShape")]

            def array(self, at):
                return (100, 2)

            def pointer(self, at):
                return shapes[(at - 100) // fc.BODY_SIZE]

            def unpack(self, fmt, at):
                k = (at - 100) // fc.BODY_SIZE
                return (0.0, 0.0, 0.0, 1.0) if fmt == "<4f" else positions[k]

        with patch.object(tool.hkpackfile, "Packfile", Pack), \
                patch.object(tool.fc, "_convex", lambda p, shape: ([(0.0, 0.0, 0.0), (1.0, 2.0, 3.0)], [])):
            self.assertEqual(tool._bounds(b"x", 0), [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]])
            self.assertEqual(tool._bounds(b"x", 1), [[10.0, 0.0, 5.0], [11.0, 2.0, 8.0]])
            self.assertIsNone(tool._bounds(b"x", 5))                  # index out of range: unread


if __name__ == "__main__":
    unittest.main()
