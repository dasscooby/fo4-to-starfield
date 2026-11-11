"""A door whose Open slides its parts is routed to its own rig by that motion, not only by a name NOT_HINGED_RE knows
(Red Rocket's RedRPedDoor.nif slides in FO4; the hinged template swung it about the leaf's centre, owner 2026-10-18)."""
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import convert_static, door_rig, fo4skin, nif  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_door_two_panels import door_nif, donor, fake_clip_files, node_names, sliding_panels, two_leaves  # noqa: E402
import test_sliding_doors  # noqa: E402

PED = "meshes/Interiors/RedRocket/Doors/SyntheticPedDoor.nif"          # no vault / gate / slid in the name


class SlidesTests(unittest.TestCase):
    def test_a_sliding_panel_slides_and_a_hinged_leaf_does_not(self):
        self.assertTrue(door_rig.slides(door_nif(sliding_panels()[:1])))
        self.assertTrue(door_rig.slides(door_nif(sliding_panels())))
        self.assertFalse(door_rig.slides(door_nif(two_leaves()[:1])))
        self.assertFalse(door_rig.slides(door_nif(two_leaves())))

    def test_unreadable_motion_is_not_called_sliding(self):
        bad = door_nif(sliding_panels()[:1])
        bad.block_types.append("NiPathInterpolator")
        for i in range(len(bad.blocks)):
            if bad.type_of(i) == "NiTransformInterpolator":
                bad.block_type_index[i] = len(bad.block_types) - 1
        self.assertFalse(door_rig.slides(bad))


class SlidingRoutingTests(unittest.TestCase):
    convert = test_sliding_doors.NonHingedRoutingTests.convert

    def test_a_sliding_door_with_a_plain_name_gets_its_own_rig(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, static = self.convert(staging, PED, sliding_panels()[:1], "calumi.dll")
        self.assertTrue(result["ok"], result)
        single.assert_not_called()
        static.assert_not_called()
        self.assertTrue(multi.call_args.kwargs["rest_pose_check"])
        self.assertEqual(result["door"]["rig"], "native")

    def test_without_the_library_it_stays_passable_instead_of_swinging(self):
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, _ = self.convert(staging, PED, sliding_panels()[:1], None)
        single.assert_not_called()
        multi.assert_not_called()
        self.assertEqual(result["door_not_opening"], "open animation not ported: passable")

    def test_a_door_named_in_no_rig_models_stays_passable_with_the_library(self):
        """--no-rig-pattern (v6 Red Rocket crash bisect, 2026-10-19): the door is converted as without the library."""
        with tempfile.TemporaryDirectory() as staging:
            result, single, multi, _ = self.convert(staging, PED, sliding_panels()[:1], "calumi.dll",
                                                    no_rig_models={PED.replace("/", "\\").lower()})
        single.assert_not_called()
        multi.assert_not_called()
        self.assertEqual(result["door_not_opening"], "open animation not ported: passable")

    def test_a_hinged_door_with_the_same_name_keeps_the_template(self):
        with tempfile.TemporaryDirectory() as staging:
            _, single, multi, _ = self.convert(staging, PED, two_leaves()[:1], "calumi.dll")
        single.assert_called_once()
        multi.assert_not_called()


class SkinnedPanelTests(unittest.TestCase):
    """RedRPedDoor.nif's two shapes are skinned to its animated bones (PC check 2026-10-18); a shape whose vertices all
    follow one rig bone rides that bone instead of failing the door."""

    def skinned(self, f, bone, weights=(1.0, 0.0, 0.0, 0.0), offset=(5.0, 0.0, 0.0), second=None):
        """Mark the first panel shape skinned to node `bone`, skin_to_bone a pure translation by offset; second: a
        second bone that vertex 3 alone follows."""
        panel = min(s.block for s in nif.fo4_trishapes(f) if s.positions)
        real = nif.fo4_trishapes
        count = len(next(s for s in real(f) if s.block == panel).positions)

        def shapes(src):
            return [replace(s, skinned=True) if s.block == panel else s for s in real(src)]

        def read_skin(src, block):
            if block != panel:
                return None
            bones = [bone] + ([second] if second is not None else [])
            xf = (offset, (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0)
            slots = [(0, 0, 0, 0)] * count
            if second is not None:
                slots = [(1, 0, 0, 0) if v == 3 else (0, 0, 0, 0) for v in range(count)]
            return fo4skin.Fo4Skin(block, -1, -1, 0, bones, [b"bone"] * len(bones), [xf] * len(bones),
                                   [(0, 0, 0, 1)] * len(bones), [weights] * count, slots)
        return panel, shapes, read_skin

    def convert(self, f, shapes, read_skin, **kw):
        with patch.object(nif, "fo4_trishapes", side_effect=shapes), patch.object(fo4skin, "read_skin", side_effect=read_skin):
            count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
            return convert_static.convert_multipart_door(nif.serialize(f), "fo4port/ped", ["x.mat"] * count, fake_clip_files,
                                                         collision_template=fake_template(), leaf_physics_donor=donor(), **kw)

    def test_a_panel_skinned_to_one_bone_rides_that_bone(self):
        f = door_nif(sliding_panels())
        panel_b = node_names(f)["PanelB"]
        panel, shapes, read_skin = self.skinned(f, panel_b)
        with patch.object(fo4skin, "read_skin", side_effect=read_skin):
            plan = door_rig.plan(f, placed=True)
            shape = next(s for s in shapes(f) if s.block == panel)
            (index, rigid), = convert_static.rigid_skinned_parts(f, shape, plan["bones"])
        self.assertEqual(plan["bones"][index]["node"], panel_b)
        self.assertFalse(rigid.skinned)
        self.assertEqual(rigid.positions[1], (shape.positions[1][0] + 5, shape.positions[1][1], shape.positions[1][2]))
        _, door = self.convert(f, shapes, read_skin)
        self.assertEqual(door["rig"], "native")
        self.assertEqual(len(door["rebound_skinned_shapes"]), 1)
        self.assertNotIn("dropped_skinned_shapes", door)
        self.assertEqual(door["moving_bodies"], 1)                       # both panels' geometry now on PanelB

    def test_a_shape_on_two_bones_is_cut_into_one_piece_per_bone(self):
        """RedRPedDoor's Door:7: 363 vertices on b_Door, 118 on b_Handle, none blended. Here the leaf's two triangles
        share vertices 0 and 2, so a vertex on its own bone puts a triangle across two bones: refused; a separate
        triangle per bone is cut."""
        f = door_nif(sliding_panels())
        names = node_names(f)
        _, shapes, read_skin = self.skinned(f, names["PanelA"], second=names["PanelB"])
        with self.assertRaisesRegex(nif.NifError, "cannot be rigged"):
            self.convert(f, shapes, read_skin)
        panel = min(s.block for s in nif.fo4_trishapes(f) if s.positions)
        split = lambda src: [replace(s, triangles=[(0, 1, 2), (3, 4, 5)],          # noqa: E731
                                     positions=s.positions[:3] + [(0, 0, 0), (0, 5, 0), (0, 5, 9)],
                                     uvs=(s.uvs[:3] * 2) if s.uvs else s.uvs, normals=(s.normals[:3] * 2) if s.normals else
                                     s.normals, tangents=(s.tangents[:3] * 2) if s.tangents else s.tangents,
                                     colors=(s.colors[:3] * 2) if s.colors else s.colors) if s.block == panel else s
                             for s in shapes(src)]

        def skin(src, block):
            k = read_skin(src, block)
            if k is None:
                return None
            return replace(k, weights=[(1.0, 0, 0, 0)] * 6, indices=[(0, 0, 0, 0)] * 3 + [(1, 0, 0, 0)] * 3)
        _, door = self.convert(f, split, skin)
        self.assertEqual(door["rig"], "native")
        self.assertEqual(door["rebound_skinned_pieces"], 2)
        self.assertEqual(door["moving_bodies"], 2)                       # a piece on each panel

    def test_a_few_triangles_across_two_bones_are_cut_not_dropped_when_allowed(self):
        """VltGearDoor01's WalkWay01:7 (PC dump 2026-11-11): no blended vertex, but 288 of 2238 triangles (hanger rods)
        join two bones, so the whole shape was dropped and the walkway never drew. With an allowance each such triangle
        goes whole to one bone; past the allowance the shape is still refused."""
        f = door_nif(sliding_panels())
        names = node_names(f)
        _, shapes, read_skin = self.skinned(f, names["PanelA"], second=names["PanelB"])
        panel = min(s.block for s in nif.fo4_trishapes(f) if s.positions)
        with patch.object(fo4skin, "read_skin", side_effect=read_skin):
            plan = door_rig.plan(f, placed=True)
            shape = next(s for s in shapes(f) if s.block == panel)
            crossing = sum(1 for t in shape.triangles if 3 in t)
            share = crossing / len(shape.triangles)
            self.assertGreater(crossing, 0)
            self.assertIsNone(convert_static.rigid_skinned_parts(f, shape, plan["bones"]))
            self.assertIsNone(convert_static.rigid_skinned_parts(f, shape, plan["bones"], share / 2))
            parts = convert_static.rigid_skinned_parts(f, shape, plan["bones"], share)
        self.assertEqual(sum(len(p.triangles) for _, p in parts), len(shape.triangles))   # every triangle kept
        self.assertTrue(all(not p.skinned for _, p in parts))
        _, door = self.convert(f, shapes, read_skin, cross_bone_share=share)
        self.assertNotIn("dropped_skinned_shapes", door)
        self.assertEqual(door["rig"], "native")

    def test_weights_split_over_slots_of_one_bone_still_count_as_rigid(self):
        f = door_nif(sliding_panels())
        panel_a = node_names(f)["PanelA"]
        _, shapes, read_skin = self.skinned(f, panel_a, (0.5, 0.5, 0.0, 0.0), second=panel_a)

        def skin(src, block):
            k = read_skin(src, block)
            return k and replace(k, indices=[(0, 1, 0, 0)] * len(k.weights))
        self.assertEqual(self.convert(f, shapes, skin)[1]["rig"], "native")

    def test_slots_of_one_bone_with_different_binds_refuse(self):
        """Codex on #354: .5/.5 over two slots of one bone, inverse translations 0 and 70: the weighted result sits 35
        units from either bind, so no single bind can carry the piece."""
        f = door_nif(sliding_panels())
        panel_a = node_names(f)["PanelA"]
        _, shapes, read_skin = self.skinned(f, panel_a, (0.5, 0.5, 0.0, 0.0), second=panel_a)

        def skin(src, block):
            k = read_skin(src, block)
            return k and replace(k, indices=[(0, 1, 0, 0)] * len(k.weights),
                                 skin_to_bone=[((0.0, 0.0, 0.0), (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0),
                                               ((70.0, 0.0, 0.0), (1, 0, 0, 0, 1, 0, 0, 0, 1), 1.0)])
        with self.assertRaisesRegex(nif.NifError, "cannot be rigged"):
            self.convert(f, shapes, skin)

    def test_blended_or_off_rig_skins_still_refuse_the_door(self):
        f = door_nif(sliding_panels())
        names = node_names(f)
        for bone, weights in ((names["PanelA"], (0.6, 0.4, 0.0, 0.0)), (names["PanelA"], (0.995, 0.005, 0.0, 0.0)),
                              (0, (1.0, 0.0, 0.0, 0.0)), (len(f.blocks) - 1, (1.0, 0.0, 0.0, 0.0))):
            _, shapes, read_skin = self.skinned(f, bone, weights, second=names["PanelB"] if weights[1] else None)
            if weights[1]:                                               # vertex weights across PanelA and PanelB
                inner = read_skin
                read_skin = (lambda inner: lambda src, block: (lambda k: k and replace(
                    k, indices=[(0, 1, 0, 0)] * len(k.weights)))(inner(src, block)))(inner)
            if bone == 0:                                                # the root is a rig bone: rebinding is fine
                self.assertEqual(self.convert(f, shapes, read_skin)[1]["rig"], "native")
                continue
            with self.assertRaisesRegex(nif.NifError, "skinned door shapes cannot be rigged"):
                self.convert(f, shapes, read_skin)
            self.assertIn("dropped_skinned_shapes", self.convert(f, shapes, read_skin, drop_skinned=True)[1])


if __name__ == "__main__":
    unittest.main()
