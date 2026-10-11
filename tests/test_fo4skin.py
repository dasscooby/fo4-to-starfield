"""FO4 skin reader and linear blend pose bake (src/fo4sf/fo4skin.py). Synthetic NIFs only; no game data."""
import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import fo4skin, nif  # noqa: E402

IDENT = (1, 0, 0, 0, 1, 0, 0, 0, 1)
ROT_Z90 = (0, -1, 0, 1, 0, 0, 0, 0, 1)            # row-major: x' = -y, y' = x
VF_VERTEX, VF_UV, VF_NORMAL, VF_TANGENT, VF_COLOR, VF_SKIN, VF_FULL = 0x1, 0x2, 0x8, 0x10, 0x20, 0x40, 0x400


def av_fields(name_idx, trans=(0, 0, 0), rot=IDENT, scale=1.0):
    return (struct.pack("<iIiI", name_idx, 0, -1, 0xE) + struct.pack("<3f", *trans) + struct.pack("<9f", *rot)
            + struct.pack("<f", scale) + struct.pack("<i", -1))


def node_block(name_idx, children, trans=(0, 0, 0), rot=IDENT):
    return av_fields(name_idx, trans, rot) + struct.pack(f"<I{len(children)}i", len(children), *children)


def shape_block(name_idx, points, skin_ref=-1, weights=None, slots=None, full=False, color=False, tris=((0, 1, 2),),
                trans=(0, 0, 0), rot=IDENT, scale=1.0):
    """FO4 BSTriShape. With weights, the vertices carry VF_SKIN data (4 x f16 weights, 4 x u8 slots) placed after the
    optional colour, the way FO4 lays it out; the descriptor's offset nibbles point at each field."""
    skinned = weights is not None
    attrs = VF_VERTEX | VF_UV | VF_NORMAL | VF_TANGENT | (VF_FULL if full else 0) | (VF_COLOR if color else 0)
    attrs |= VF_SKIN if skinned else 0
    uv = 16 if full else 8
    nrm, tan = uv + 4, uv + 8
    col = uv + 12 if color else 0
    skin = uv + 12 + (4 if color else 0)
    vsize = skin + (12 if skinned else 0)
    desc = (attrs << 44 | vsize // 4 | (uv // 4) << 8 | (nrm // 4) << 16 | (tan // 4) << 20 | (col // 4) << 24
            | ((skin // 4) << 28 if skinned else 0))
    verts = b""
    for k, p in enumerate(points):
        verts += struct.pack("<3ff", *p, 0.0) if full else struct.pack("<4e", *p, 0.0)
        verts += struct.pack("<2e", 0.0, 0.0) + bytes([128, 128, 255, 128, 255, 128, 128, 128])
        verts += bytes([255, 255, 255, 255]) if color else b""
        if skinned:
            verts += struct.pack("<4e", *weights[k]) + bytes(slots[k])
    head = av_fields(name_idx, trans, rot, scale) + struct.pack("<4f", 0, 0, 0, 1) + struct.pack("<iii", skin_ref, -1, -1)
    head += struct.pack("<Q", desc) + struct.pack("<IHI", len(tris), len(points), vsize * len(points) + 6 * len(tris))
    return head + verts + b"".join(struct.pack("<HHH", *t) for t in tris)


def instance_block(root, data, bones, extra=()):
    return (struct.pack(f"<iiI{len(bones)}i", root, data, len(bones), *bones) + struct.pack("<I", len(extra))
            + b"".join(struct.pack("<3f", *v) for v in extra))


def bone_data_block(entries):
    """entries: (sphere (cx, cy, cz, r), rotation 9-tuple, translation, scale) per bone slot."""
    out = struct.pack("<I", len(entries))
    for sphere, rot, tr, scale in entries:
        out += struct.pack("<4f", *sphere) + struct.pack("<9f", *rot) + struct.pack("<3f", *tr) + struct.pack("<f", scale)
    return out


# Two-bone chain: BoneA at z 10, BoneB 10 above it (world z 20). The bone data holds the inverse of each bone's world
# transform, so the NIF's node pose is the bind pose. v0 follows A, v1 follows B, v2 is split half and half.
POINTS = [(1.0, 0.0, 5.0), (1.0, 0.0, 25.0), (0.0, 1.0, 15.0)]
WEIGHTS = [(1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.5, 0.5, 0.0, 0.0)]
SLOTS = [(0, 0, 0, 0), (1, 0, 0, 0), (0, 1, 0, 0)]


def skinned_nif(points=POINTS, weights=WEIGHTS, slots=SLOTS, bone_entries=None, instance=None, full=False, color=False,
                bone_b_rot=IDENT, shape_trans=(0, 0, 0)):
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    for s in (b"Root", b"BoneA", b"BoneB", b"Body"):
        f.string_index(s)
    f.add_block("NiNode", node_block(0, [1, 3]))
    f.add_block("NiNode", node_block(1, [2], trans=(0, 0, 10)))
    f.add_block("NiNode", node_block(2, [], trans=(0, 0, 10), rot=bone_b_rot))
    f.add_block("BSTriShape", shape_block(3, points, 4, weights, slots, full=full, color=color, trans=shape_trans))
    f.add_block("BSSkin::Instance", instance if instance is not None else instance_block(0, 5, [1, 2]))
    if bone_entries is None:
        bone_entries = [((0, 0, -5, 6), IDENT, (0, 0, -10), 1.0), ((0, 0, 5, 6), IDENT, (0, 0, -20), 1.0)]
    f.add_block("BSSkin::BoneData", bone_data_block(bone_entries))
    f.footer = struct.pack("<II", 1, 0)
    return nif.parse(nif.serialize(f))


def close(test, got, want, places=5):
    test.assertEqual(len(got), len(want))
    for g, w in zip(got, want):
        for a, b in zip(g, w):
            test.assertAlmostEqual(a, b, places=places, msg=f"{got} != {want}")


class SkinLayoutTests(unittest.TestCase):
    def test_reads_instance_bone_data_and_vertex_weights(self):
        n = skinned_nif()
        skin = fo4skin.read_skin(n, 3)
        self.assertEqual((skin.shape, skin.instance, skin.data, skin.skeleton_root), (3, 4, 5, 0))
        self.assertEqual(skin.bones, [1, 2])
        self.assertEqual(skin.bone_names, [b"BoneA", b"BoneB"])
        self.assertEqual(skin.skin_to_bone[1], ((0.0, 0.0, -20.0), tuple(float(x) for x in IDENT), 1.0))
        self.assertEqual(skin.bounds, [(0.0, 0.0, -5.0, 6.0), (0.0, 0.0, 5.0, 6.0)])
        self.assertEqual(skin.weights, WEIGHTS)
        self.assertEqual(skin.indices, SLOTS)
        self.assertEqual(skin.extra, [])

    def test_skin_data_offset_follows_the_vertex_descriptor(self):
        """Half or full precision positions and an optional colour move the skin data (20, 24, 28, 32 bytes)."""
        for full in (False, True):
            for color in (False, True):
                skin = fo4skin.read_skin(skinned_nif(full=full, color=color), 3)
                self.assertEqual(skin.weights, WEIGHTS, (full, color))
                self.assertEqual(skin.indices, SLOTS, (full, color))

    def test_instance_trailing_vectors_are_read_and_sized(self):
        n = skinned_nif(instance=instance_block(0, 5, [1, 2], extra=[(1, 2, 3)]))
        self.assertEqual(fo4skin.read_skin(n, 3).extra, [(1.0, 2.0, 3.0)])

    def test_unskinned_shape_has_no_skin(self):
        f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
        f.string_index(b"Plain")
        f.add_block("NiNode", node_block(0, [1]))
        f.add_block("BSTriShape", shape_block(0, POINTS))
        f.footer = struct.pack("<II", 1, 0)
        self.assertIsNone(fo4skin.read_skin(nif.parse(nif.serialize(f)), 1))

    def test_inconsistent_blocks_raise(self):
        three = [((0, 0, 0, 1), IDENT, (0, 0, 0), 1.0)] * 3
        with self.assertRaises(nif.NifError):                       # bone data has 3 slots, instance 2 bones
            fo4skin.read_skin(skinned_nif(bone_entries=three), 3)
        with self.assertRaises(nif.NifError):                       # instance block longer than its counts
            fo4skin.read_skin(skinned_nif(instance=instance_block(0, 5, [1, 2]) + b"\0\0\0\0"), 3)
        with self.assertRaises(nif.NifError):                       # vertex weighted to slot 2 of 2
            fo4skin.read_skin(skinned_nif(slots=[(0, 0, 0, 0), (2, 0, 0, 0), (0, 1, 0, 0)]), 3)

    def test_zero_weight_slots_may_hold_any_index(self):
        skin = fo4skin.read_skin(skinned_nif(slots=[(0, 9, 9, 9), (1, 9, 9, 9), (0, 1, 9, 9)]), 3)
        self.assertEqual(skin.indices[0], (0, 9, 9, 9))


class PoseTests(unittest.TestCase):
    def test_node_pose_equal_to_bind_pose_reproduces_stored_positions(self):
        n = skinned_nif()
        shape = nif.fo4_trishapes(n)[0]
        skin = fo4skin.read_skin(n, shape.block)
        close(self, fo4skin.pose_vertices(shape.positions, skin, fo4skin.node_world(n, skin)), POINTS)

    def test_rotating_one_bone_moves_only_its_share(self):
        n = skinned_nif()
        skin = fo4skin.read_skin(n, 3)
        world = fo4skin.node_world(n, skin)
        world[1] = ((0.0, 0.0, 20.0), ROT_Z90, 1.0)             # BoneB turned 90 degrees about z in place
        posed = fo4skin.pose_vertices(POINTS, skin, world)
        # v0 only follows A; v1 (1, 0, 5) in B's space turns to (0, 1, 5); v2 is the mean of (0, 1, 15) and (-1, 0, 15)
        close(self, posed, [(1, 0, 5), (0, 1, 25), (-0.5, 0.5, 15)])

    def test_skin_to_bone_rotation_uses_the_niavobject_convention(self):
        """BoneB carries a 90 degree local rotation; its bone data holds the inverse of its world transform written
        with the same row-major rotation as NiAVObject. Read that way, the node pose reproduces the positions; a
        transposed read would turn BoneB's vertices 180 degrees."""
        world_b = ((0.0, 0.0, 20.0), ROT_Z90, 1.0)
        inv_b = fo4skin.invert(world_b)
        entries = [((0, 0, -5, 6), IDENT, (0, 0, -10), 1.0), ((0, 0, 5, 6), inv_b[1], inv_b[0], 1.0)]
        n = skinned_nif(bone_entries=entries, bone_b_rot=ROT_Z90)
        skin = fo4skin.read_skin(n, 3)
        self.assertEqual(skin.skin_to_bone[1][1], (0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0))
        close(self, fo4skin.pose_vertices(POINTS, skin, fo4skin.node_world(n, skin)), POINTS)

    def test_bind_world_includes_the_shape_transform(self):
        n = skinned_nif()
        skin = fo4skin.read_skin(n, 3)
        shape_world = ((5.0, 0.0, 0.0), ROT_Z90, 2.0)
        posed = fo4skin.pose_vertices(POINTS, skin, fo4skin.bind_world(skin, shape_world))
        close(self, posed, [fo4skin.apply(shape_world, p) for p in POINTS])

    def test_weights_are_normalised_unless_asked_not_to(self):
        skin = fo4skin.read_skin(skinned_nif(weights=[(1, 0, 0, 0), (1, 0, 0, 0), (0.5, 0.25, 0, 0)]), 3)
        world = [((0.0, 0.0, 10.0), IDENT, 1.0), ((3.0, 0.0, 20.0), IDENT, 1.0)]   # BoneB moved 3 in x
        self.assertAlmostEqual(fo4skin.pose_vertices(POINTS, skin, world)[2][0], 1.0)            # 3 * 0.25 / 0.75
        self.assertAlmostEqual(fo4skin.pose_vertices(POINTS, skin, world, normalize=False)[2][0], 0.75)

    def test_vertex_without_weight_follows_its_first_slot(self):
        skin = fo4skin.read_skin(skinned_nif(weights=[(1, 0, 0, 0), (0, 0, 0, 0), (0.5, 0.5, 0, 0)]), 3)
        world = [((0.0, 0.0, 10.0), IDENT, 1.0), ((3.0, 0.0, 20.0), IDENT, 1.0)]   # BoneB moved 3 in x
        self.assertAlmostEqual(fo4skin.pose_vertices(POINTS, skin, world)[1][0], 4.0)  # v1 (slots 1, ...) moves with B
        with self.assertRaises(nif.NifError):                       # ...so that first slot must exist
            fo4skin.read_skin(skinned_nif(weights=[(1, 0, 0, 0), (0, 0, 0, 0), (0.5, 0.5, 0, 0)],
                                          slots=[(0, 0, 0, 0), (5, 0, 0, 0), (0, 1, 0, 0)]), 3)

    def test_count_mismatches_raise(self):
        skin = fo4skin.read_skin(skinned_nif(), 3)
        with self.assertRaises(ValueError):
            fo4skin.pose_vertices(POINTS[:2], skin, fo4skin.bind_world(skin))
        with self.assertRaises(ValueError):
            fo4skin.pose_vertices(POINTS, skin, fo4skin.bind_world(skin)[:1])

    def test_invert_undoes_a_scaled_rotation(self):
        xf = ((1.0, -2.0, 3.0), (0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0), 2.5)
        p = (0.3, -4.0, 7.0)
        q = fo4skin.apply(fo4skin.invert(xf), fo4skin.apply(xf, p))
        for a, b in zip(q, p):
            self.assertAlmostEqual(a, b, places=9)
        self.assertTrue(math.isclose(fo4skin.invert(xf)[2], 0.4))


if __name__ == "__main__":
    unittest.main()
