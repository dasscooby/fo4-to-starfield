"""FO4 loose items -> movable Starfield bodies: FO4 motion decoding, mass distribution, NIF routing (synthetic data).

Reference values come from vanilla Starfield MiscItem bodies (docs/ai/research-log.md 2026-10-10): a box grown by its
convex radius, inertia per kg x 1.5. Numbers only, no game data."""
import math
import struct
import unittest
from unittest.mock import patch

from test_review_fixes import av_fields, trishape_block, ROT_Z90
from fo4sf import convert_static, fo4collision as fc, meshcollision, nif

CUBE = [(x, y, z) for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)]
CUBE_FACES = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]


def box(half, centre=(0.0, 0.0, 0.0), rot=None):
    pts = [tuple(c + (h if v else -h) for c, h, v in zip(centre, half, p)) for p in CUBE]
    if rot:
        pts = [tuple(sum(rot[3 * i + k] * (p[k] - centre[k]) for k in range(3)) + centre[i] for i in range(3)) for p in pts]
    return pts


class MassDistributionTests(unittest.TestCase):
    def test_unit_cube(self):
        com, vol, q, inertia = meshcollision.mass_distribution(CUBE, CUBE_FACES)
        self.assertAlmostEqual(vol, 1.0, places=9)
        for a in range(3):
            self.assertAlmostEqual(com[a], 0.5, places=9)
            self.assertAlmostEqual(inertia[a], 1.0 / 6.0 * meshcollision.INERTIA_FACTOR, places=9)
        self.assertEqual(q, (0.0, 0.0, 0.0, 1.0))

    def test_vanilla_credit_stick_values(self):
        # vanilla Starfield credit stick: box half extents + convex radius -> stored volume and inertia per kg
        com, vol, q, inertia = meshcollision.mass_distribution(box((0.088618, 0.029793, 0.003881), (-0.001416, 0.000557, 0.011319)),
                                                               CUBE_FACES, radius=0.005301)
        self.assertAlmostEqual(vol, 0.000242, delta=0.000001)
        for got, want in zip(inertia, (0.000658, 0.004452, 0.005026)):
            self.assertAlmostEqual(got, want, delta=0.000002)
        for got, want in zip(com, (-0.001416, 0.000557, 0.011319)):
            self.assertAlmostEqual(got, want, places=6)

    def test_rotated_box_keeps_principal_moments_and_reports_axes(self):
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        rz = (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)
        plain = meshcollision.mass_distribution(box((0.3, 0.1, 0.05)), CUBE_FACES)
        turned = meshcollision.mass_distribution(box((0.3, 0.1, 0.05), rot=rz), CUBE_FACES)
        self.assertAlmostEqual(turned[1], plain[1], places=9)
        for got, want in zip(sorted(turned[3]), sorted(plain[3])):
            self.assertAlmostEqual(got, want, places=9)
        self.assertGreater(abs(turned[2][2]), 0.1)        # a z rotation shows in the quaternion
        self.assertAlmostEqual(sum(x * x for x in turned[2]), 1.0, places=9)

    def test_flat_shape_rejected(self):
        flat = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        with self.assertRaises(Exception):
            meshcollision.mass_distribution(flat + flat, [[0, 1, 2, 3], [7, 6, 5, 4]])


class FakePack:
    """Just enough of hkpackfile.Packfile for fo4collision.body_mass."""

    def __init__(self, arrays, data):
        self.arrays, self.data = arrays, data

    def array(self, at):
        return self.arrays.get(at, (None, 0))

    def unpack(self, fmt, at):
        return struct.unpack_from(fmt, self.data, at)


def fake_system(motion_index, props_id, inv_mass):
    data = bytearray(1024)
    struct.pack_into("<I", data, 100 + fc.BODY_MOTION, motion_index)          # one body at 100
    struct.pack_into("<H2xf", data, 400, props_id, inv_mass)                  # one motion cinfo at 400
    return FakePack({fc.SYS_BODIES: (100, 1), fc.SYS_MOTION_CINFOS: (400, 1)}, data)


class Fo4MotionTests(unittest.TestCase):
    def test_dynamic_body_mass_is_inverse_of_inverse_mass(self):
        self.assertAlmostEqual(fc.body_mass(fake_system(0, 0, 0.2), 0, 0), 5.0, places=5)   # inverse mass is float32

    def test_static_keyframed_and_broken_bodies_are_not_dynamic(self):
        self.assertIsNone(fc.body_mass(fake_system(fc.STATIC_MOTION, 0, 0.2), 0, 0))     # static
        self.assertIsNone(fc.body_mass(fake_system(0, 0xFFFF, 0.0), 0, 0))              # keyframed (railings, pods)
        self.assertIsNone(fc.body_mass(fake_system(0, 0, 0.0), 0, 0))                   # no mass
        self.assertIsNone(fc.body_mass(fake_system(5, 0, 0.2), 0, 0))                   # motion index out of range
        self.assertIsNone(fc.body_mass(fake_system(0, 0, 0.2), 0, 1))                   # no such body


def fo4_nif_with_collision():
    """root NiNode with a triangle and a root collision object (the physics payload is a placeholder)."""
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    f.string_index(b"Shape")
    f.add_block("NiNode", av_fields(0, (0, 0, 0), (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0) + struct.pack("<Ii", 1, 1))
    f.add_block("BSTriShape", trishape_block([(0, 0, 0), (70, 0, 0), (0, 70, 0)], [(0, 1, 2)]))
    f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 0, 0x80, 3, 0))
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"fake")
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


class RoutingTests(unittest.TestCase):
    def convert(self, dynamic):
        def fake_native(src, tmpl, report, dynamic_template=None, motion=None):
            self.seen_template = dynamic_template
            if dynamic:
                motion["dynamic"] = 5.0
            return [b"BODY"]
        report = {}
        with patch.object(convert_static, "fo4_native_collision", side_effect=fake_native):
            files = convert_static.convert_static(fo4_nif_with_collision(), "fo4port/synthetic_can",
                                                  collision_template=b"t", sf_mesh_template=b"t",
                                                  dynamic_template=b"dyn" if dynamic else None, report=report)
        g = nif.parse(files["meshes/fo4port/synthetic_can.nif"])
        return g, [g.type_of(i) for i in range(len(g.blocks))]

    def test_movable_item_body_on_root_with_dynamic_bsx(self):
        g, types = self.convert(dynamic=True)
        self.assertEqual(self.seen_template, b"dyn")
        self.assertEqual(types[:4], ["NiNode", "BSXFlags", "bhkNPCollisionObject", "bhkPhysicsSystem"])
        self.assertEqual(struct.unpack_from("<iI", g.blocks[1], 0)[1], 0x42)
        self.assertEqual(struct.unpack("<iHiI", g.blocks[2])[0], 0)                 # target = root: the whole model moves
        self.assertEqual(g.blocks[3][4:], b"BODY")
        self.assertEqual(types.count("NiNode"), 1)                                 # no Collision child node

    def test_fixed_item_keeps_child_collision_node(self):
        g, types = self.convert(dynamic=False)
        self.assertEqual(struct.unpack_from("<iI", g.blocks[1], 0)[1], 2)
        self.assertEqual(types.count("NiNode"), 2)


if __name__ == "__main__":
    unittest.main()
