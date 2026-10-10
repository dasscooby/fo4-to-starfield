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


class CompoundLayoutTests(unittest.TestCase):
    """Vanilla dynamic compounds (40 items): SIMD node counts 2->3, 3->3, 5->4, 8->4, 9->5; root always inner."""

    @staticmethod
    def nodes(n):
        boxes = [(k, ((k, 0.0, 0.0), (k + 0.5, 1.0, 1.0))) for k in range(n)]
        raw = meshcollision.build_simd_tree(boxes, leaf_root=False)
        out = []
        for i in range(len(raw) // 128):
            data = struct.unpack_from("<4I", raw, 128 * i + 96)
            out.append((raw[128 * i + 112], data))
        return out

    def test_node_counts_match_vanilla_compounds(self):
        for n, want in ((2, 3), (3, 3), (5, 4), (8, 4), (9, 5)):
            with self.subTest(n=n):
                self.assertEqual(len(self.nodes(n)), want)

    def test_root_is_inner_and_every_instance_is_in_exactly_one_leaf(self):
        for n in (1, 2, 4, 7, 16, 19):
            with self.subTest(n=n):
                nodes = self.nodes(n)
                self.assertEqual(nodes[1][0], 0)                                   # node 1 (root) is not a leaf
                keys = [d for leaf, data in nodes[1:] if leaf for d in data if d != 0xFFFFFFFF]
                self.assertEqual(sorted(keys), list(range(n)))

    def test_mesh_trees_keep_a_leaf_root(self):
        boxes = [(k, ((k, 0.0, 0.0), (k + 0.5, 1.0, 1.0))) for k in range(2)]
        self.assertEqual(len(meshcollision.build_simd_tree(boxes)), 2 * 128)       # sentinel + leaf root, as before

    def test_compound_mass_is_its_aabb_as_a_solid_box(self):
        com, vol, q, inertia = meshcollision.box_mass_distribution((-0.1878, -0.0464, -0.00107), (0.18537, 0.0736, 0.26578))
        # vanilla CB_BlackMarketAntiquities: centre (-0.00122, 0.0136, 0.13235), volume 0.01195, inertia (0.0107, 0.02631, 0.01921)
        for got, want in zip(com, (-0.00122, 0.0136, 0.13235)):
            self.assertAlmostEqual(got, want, places=4)
        self.assertAlmostEqual(vol, 0.01195, places=4)
        for got, want in zip(inertia, (0.0107, 0.02631, 0.01921)):
            self.assertAlmostEqual(got, want, places=4)
        self.assertEqual(q, (0.0, 0.0, 0.0, 1.0))


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


def two_bone_nif(shared=True, same_body=False):
    """root -> two bone nodes (70 units along x / y, the second turned 90 degrees about z), each with a collision object
    that owns one body of a physics system (one shared system, or one each)."""
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    f.string_index(b"Bone")
    ident = (1, 0, 0, 0, 1, 0, 0, 0, 1)
    f.add_block("NiNode", av_fields(0, (0, 0, 0), ident, 1.0) + struct.pack("<Iii", 2, 1, 2))
    f.add_block("NiNode", av_fields(0, (70, 0, 0), ident, 1.0) + struct.pack("<I", 0))
    f.add_block("NiNode", av_fields(0, (0, 70, 0), ROT_Z90, 1.0) + struct.pack("<I", 0))
    f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 1, 0x80, 5, 0))
    f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 2, 0x80, 5 if shared else 6, 0 if same_body else 1))
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"sys0")
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"sys1")
    f.footer = struct.pack("<II", 1, 0)
    return nif.parse(nif.serialize(f))


class RigidRagdollTests(unittest.TestCase):
    def run_rigid(self, src):
        seen = {}

        def fake(blob, template, placements, motion):
            seen.update(blob=blob, placements=placements)
            motion["dynamic"], motion["rigid_bodies"] = 15.0, len(placements)
            return b"RIGID"
        objs = [i for i in range(len(src.blocks)) if src.type_of(i) == "bhkNPCollisionObject"]
        with patch.object(meshcollision, "rigid_dynamic_body", side_effect=fake):
            out = convert_static._rigid_ragdoll(src, objs, nif.world_transforms(src), b"dyn", {})
        return out, seen

    def test_bones_sharing_one_system_are_placed_in_root_space(self):
        out, seen = self.run_rigid(two_bone_nif())
        self.assertEqual(out, b"RIGID")
        self.assertEqual(seen["blob"], b"sys0")
        self.assertEqual(sorted(seen["placements"]), [0, 1])
        rot0, t0 = seen["placements"][0]
        rot1, t1 = seen["placements"][1]
        self.assertEqual([round(x, 6) for x in t0], [1.0, 0.0, 0.0])               # 70 units = 1 m
        self.assertEqual([round(x, 6) for x in t1], [0.0, 1.0, 0.0])
        self.assertEqual([round(x, 6) for x in rot1], list(ROT_Z90))

    def test_separate_systems_or_shared_body_are_not_merged(self):
        self.assertIsNone(self.run_rigid(two_bone_nif(shared=False))[0])
        self.assertIsNone(self.run_rigid(two_bone_nif(same_body=True))[0])

    def test_part_transforms_compose_bone_then_part(self):
        captured = {}

        class P:
            def objects(self):
                return [(1, "hknpPhysicsSystemData")]

            def array(self, at):
                return (100, 2)

            def pointer(self, at):
                return 7

        def dyn(template, p, parts, filt, mass):
            captured.update(parts=parts, filt=filt, mass=mass)
            return b"BLOB"
        motion = {}
        placements = {0: ((1, 0, 0, 0, 1, 0, 0, 0, 1), (0.0, 0.0, 0.0)), 1: (ROT_Z90, (2.0, 0.0, 0.0))}
        with patch.object(meshcollision.hkpackfile, "Packfile", return_value=P()), \
                patch.object(fc, "body_mass", return_value=10.0), \
                patch.object(meshcollision, "_shape_parts",
                             return_value=[("convex", 7, meshcollision.IDENTITY3, (0.5, 0.0, 0.0))]), \
                patch.object(meshcollision, "_dynamic_body", side_effect=dyn):
            out = meshcollision.rigid_dynamic_body(b"x", b"dyn", placements, motion)
        self.assertEqual(out, b"BLOB")
        self.assertEqual(captured["mass"], 20.0)
        self.assertEqual(captured["filt"], meshcollision.RIGID_RAGDOLL_LAYER)
        self.assertEqual(motion["rigid_bodies"], 2)
        (_, _, R0, t0), (_, _, R1, t1) = captured["parts"]
        self.assertEqual(t0, (0.5, 0.0, 0.0))
        self.assertEqual(tuple(round(x, 6) for x in t1), (2.0, 0.5, 0.0))           # bone turns the part's offset
        self.assertEqual(tuple(round(x, 6) for x in R1), tuple(float(x) for x in ROT_Z90))

    def test_anchored_body_keeps_the_system_static(self):
        class P:
            def objects(self):
                return [(1, "hknpPhysicsSystemData")]

            def array(self, at):
                return (100, 2)
        motion = {}
        placements = {0: ((1, 0, 0, 0, 1, 0, 0, 0, 1), (0.0, 0.0, 0.0)), 1: ((1, 0, 0, 0, 1, 0, 0, 0, 1), (0.0, 0.0, 0.0))}
        with patch.object(meshcollision.hkpackfile, "Packfile", return_value=P()), \
                patch.object(fc, "body_mass", side_effect=[None, 10.0]):
            self.assertIsNone(meshcollision.rigid_dynamic_body(b"x", b"dyn", placements, motion))
        self.assertIn("not dynamic", motion["kept_static"][0])


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
