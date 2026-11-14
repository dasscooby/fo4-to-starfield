"""A skinned door shape whose triangles run across hinged bones may ride the bone with the smaller error (FAL-489, the Vault 111 cog door's
catwalk: 288 triangles of WalkWay01:7 across hinges, at most 2.25 cm from FO4's skinning). Synthetic shapes only."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import convert_static, fo4skin, nif  # noqa: E402
from test_fo4skin import skinned_nif  # noqa: E402

C = 2 ** -0.5
BONES = [{"node": 1}, {"node": 2}]                       # BoneA, BoneB of test_fo4skin.skinned_nif: world z 10 and 20, skin_to_bone -10 / -20
FLAT = [(1.0, 0.0, 0.0, 0.0)] * 3


def shape_of(points, slots):
    """One triangle (0, 1, 2); vertex v follows skin slot slots[v] fully: slot 0 = BoneA (node 1), slot 1 = BoneB (node 2)."""
    src = skinned_nif(points=points, weights=FLAT, slots=[(s, 0, 0, 0) for s in slots])
    shape = next(s for s in nif.fo4_trishapes(src) if s.skinned)
    return src, shape


def poses(b_turns):
    """BoneA still; BoneB, at its bind (0, 0, 20), turns 90 degrees about z in the clip's second sample (b_turns) or stays."""
    q = (C, 0, 0, C) if b_turns else (1, 0, 0, 0)
    return {"Open": {1: [((0.0, 0.0, 10.0), (1, 0, 0, 0), 1.0)] * 2,
                     2: [((0.0, 0.0, 20.0), (1, 0, 0, 0), 1.0), ((0.0, 0.0, 20.0), q, 1.0)]}}


class SeamRuleTests(unittest.TestCase):
    def test_without_poses_a_triangle_across_two_bones_is_refused_as_before(self):
        src, shape = shape_of([(1.0, 0.0, 5.0), (0.0, 0.0, 25.0), (0.0, 1.0, 15.0)], [0, 1, 0])
        self.assertIsNone(convert_static.rigid_skinned_parts(src, shape, BONES))

    def test_the_set_rides_the_side_with_the_smaller_error(self):
        # vertex 1 (BoneB's) sits on BoneB's turning axis, so BoneB turning moves it nowhere: the set riding BoneA costs 0
        # (BoneA is still); riding BoneB would drag vertices 0 and 2, BoneA's, round the axis
        src, shape = shape_of([(1.0, 0.0, 5.0), (0.0, 0.0, 25.0), (0.0, 1.0, 15.0)], [0, 1, 0])
        (index, piece), = convert_static.rigid_skinned_parts(src, shape, BONES, poses(True))
        self.assertEqual(index, 0)                                           # BoneA, the first bone of the rig
        self.assertEqual(len(piece.triangles), 1)
        self.assertEqual(piece.positions, [(1.0, 0.0, -5.0), (0.0, 0.0, 15.0), (0.0, 1.0, 5.0)])     # skin_to_bone(A) = z - 10, all three

    def test_the_other_geometry_picks_the_other_bone(self):
        # vertex 0 (BoneA's) now sits on BoneB's axis: riding BoneB leaves it where skinning puts it (0), riding BoneA would drag BoneB's
        # vertices 1 and 2 round that axis (1.41 units each)
        src, shape = shape_of([(0.0, 0.0, 5.0), (1.0, 0.0, 25.0), (0.0, 1.0, 15.0)], [0, 1, 1])
        (index, piece), = convert_static.rigid_skinned_parts(src, shape, BONES, poses(True))
        self.assertEqual(index, 1)                                           # BoneB
        self.assertEqual(piece.positions, [(0.0, 0.0, -15.0), (1.0, 0.0, 5.0), (0.0, 1.0, -5.0)])    # skin_to_bone(B) = z - 20

    def test_equal_errors_go_to_the_lowest_slot(self):
        src, shape = shape_of([(1.0, 0.0, 5.0), (1.0, 0.0, 25.0), (0.0, 1.0, 15.0)], [0, 1, 1])      # 1.41 units either way
        (index, _), = convert_static.rigid_skinned_parts(src, shape, BONES, poses(True))
        self.assertEqual(index, 0)

    def test_a_still_pair_costs_nothing(self):
        src, shape = shape_of([(1.0, 0.0, 5.0), (0.0, 0.0, 25.0), (0.0, 1.0, 15.0)], [0, 1, 0])
        (index, _), = convert_static.rigid_skinned_parts(src, shape, BONES, poses(False))
        self.assertEqual(index, 0)

    def test_a_best_error_over_the_limit_refuses_the_shape(self):
        src, shape = shape_of([(1.0, 0.0, 5.0), (1.0, 0.0, 25.0), (0.0, 1.0, 15.0)], [0, 1, 1])      # best side still 1.41 units = 2 cm
        self.assertIsNotNone(convert_static.rigid_skinned_parts(src, shape, BONES, poses(True), seam_limit_m=0.05))
        self.assertIsNone(convert_static.rigid_skinned_parts(src, shape, BONES, poses(True), seam_limit_m=0.001))

    def test_a_bone_that_is_not_in_the_poses_refuses_the_shape(self):
        src, shape = shape_of([(1.0, 0.0, 5.0), (0.0, 0.0, 25.0), (0.0, 1.0, 15.0)], [0, 1, 0])
        one = {"Open": {1: poses(True)["Open"][1]}}
        self.assertIsNone(convert_static.rigid_skinned_parts(src, shape, BONES, one))

    def test_triangles_on_one_bone_still_make_a_piece_each_beside_a_spanning_set(self):
        # two triangles: (0, 1, 2) across A/B, (3, 4, 5) wholly on B: the spanning set rides A (as above); B keeps its own piece
        src = skinned_nif(points=[(1.0, 0.0, 5.0), (0.0, 0.0, 25.0), (0.0, 1.0, 15.0)], weights=FLAT, slots=[(0, 0, 0, 0), (1, 0, 0, 0), (0, 0, 0, 0)])
        shape = next(s for s in nif.fo4_trishapes(src) if s.skinned)
        from dataclasses import replace
        shape = replace(shape, positions=shape.positions + [(2.0, 0.0, 22.0), (2.0, 1.0, 22.0), (2.0, 0.0, 23.0)],
                        uvs=(shape.uvs * 2) if shape.uvs else shape.uvs, normals=(shape.normals * 2) if shape.normals else shape.normals,
                        tangents=(shape.tangents * 2) if shape.tangents else shape.tangents, colors=(shape.colors * 2) if shape.colors else shape.colors,
                        triangles=[(0, 1, 2), (3, 4, 5)])
        skin = fo4skin.read_skin(src, shape.block)
        skin = type(skin)(**{**skin.__dict__, "weights": [(1.0, 0, 0, 0)] * 6, "indices": [(0, 0, 0, 0), (1, 0, 0, 0), (0, 0, 0, 0)] + [(1, 0, 0, 0)] * 3})
        from unittest.mock import patch
        with patch.object(fo4skin, "read_skin", return_value=skin):
            parts = convert_static.rigid_skinned_parts(src, shape, BONES, poses(True))
        self.assertEqual(sorted(i for i, _ in parts), [0, 1])
        self.assertEqual({i: len(p.triangles) for i, p in parts}, {0: 1, 1: 1})


if __name__ == "__main__":
    unittest.main()
