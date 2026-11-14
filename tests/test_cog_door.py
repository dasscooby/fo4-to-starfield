"""The Vault 111 cog door (VltGearDoor01): an Activator FO4 opens with its Stage2 sequence, converted as a door with its own
rig (pipeline.OWN_RIG_ALIASES): Stage2 becomes Open, Stage2 backwards becomes Close, skinned shapes are left out."""
import dataclasses
import struct
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fo4sf import convert_static, door_clips, door_motion, door_rig, native_door, nif  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_door_two_panels import IDENTITY, door_nif, donor, fake_clip_files, sequences, sliding_panels  # noqa: E402
import test_sliding_doors  # noqa: E402

ALIASES = {"Stage2": "Open"}
COG = "meshes/Interiors/Vault/VltGearDoor01.nif"


def cog_nif(parts=None, particles=()):
    """door_nif with FO4's activator clip names: Open renamed Stage2, Close renamed Stage0 (not a door clip); particles:
    extra Stage2 targets that are particle systems (NiParticleSystem blocks, not nodes), as the cog door's emitters."""
    f = door_nif(parts or sliding_panels(), extra_targets=particles)
    for i in range(len(f.blocks)):
        if f.type_of(i) == "NiNode" and f.strings[struct.unpack_from("<i", f.blocks[i])[0]].decode() in particles:
            if "NiParticleSystem" not in f.block_types:
                f.block_types.append("NiParticleSystem")
            f.block_type_index[i] = f.block_types.index("NiParticleSystem")
    for name, new in ((b"Open", b"Stage2"), (b"Close", b"Stage0")):
        i = sequences(f)[name]
        block = bytearray(f.blocks[i])
        struct.pack_into("<i", block, 0, f.string_index(new))
        f.blocks[i] = bytes(block)
    return f


def convert(f, **kw):
    count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
    return convert_static.convert_multipart_door(nif.serialize(f), "fo4port/interiors/vault/vltgeardoor01", ["x.mat"] * count,
                                                 fake_clip_files, collision_template=fake_template(),
                                                 leaf_physics_donor=donor(), rest_pose_check=True, **kw)


class CogDoorPlanTests(unittest.TestCase):
    def test_the_aliased_sequence_is_the_only_door_clip(self):
        f = cog_nif()
        self.assertEqual([s["name"] for s in door_motion.inspect(f)["sequences"]], [])
        self.assertEqual([s["name"] for s in door_motion.inspect(f, ALIASES)["sequences"]], ["Open"])

    def test_only_the_cog_door_paper_may_skip_an_unsampled_interpolator(self):
        # PC build f8c9b95: Stage2 moves the paper (FXPaper01, FXPaper002) on NiPathInterpolator, which no clip samples.
        # Review of #329 (Codex P2): that exception is for the paper only, never for a rendered opening part.
        paper = ("FXPaper01", (0, 0, 0), IDENTITY, None, [(0, (0, 0, 0)), (1, (0, 0, -50))])

        def retype(f, every, kind):
            interps = [i for i in range(len(f.blocks)) if f.type_of(i) == "NiTransformInterpolator"]
            f.block_types.append(kind)
            for i in interps[every]:
                f.block_type_index[i] = len(f.block_types) - 1
            return f
        f = retype(cog_nif(sliding_panels() + [paper]), slice(2, None, 3), "NiPathInterpolator")
        report = door_motion.inspect(f, ALIASES)
        self.assertEqual([(t["target"], t["reason"]) for t in report["ignored_targets"]],
                         [("FXPaper01", "unsampled interpolator NiPathInterpolator")])
        self.assertEqual(convert(f, aliases=ALIASES)[1]["rig"], "native")
        for kind in ("NiPathInterpolator", "NiBSplineTransformInterpolator"):          # a rendered panel: refused
            panel = retype(cog_nif(), slice(1, None, 2), kind)
            self.assertEqual(door_motion.inspect(panel, ALIASES)["ignored_targets"], [])
            with self.assertRaisesRegex(nif.NifError, "unsupported sampled door interpolator"):
                convert(panel, aliases=ALIASES)
        with self.assertRaisesRegex(nif.NifError, "unsupported sampled door interpolator"):
            door_rig.plan(retype(door_nif(sliding_panels() + [paper]), slice(2, None, 3), "NiPathInterpolator"),
                          placed=True)                                              # no alias: the paper too

    def test_particle_emitters_in_the_aliased_clip_are_left_out_and_listed(self):
        # PC build 1449688: Stage2 also drives 27 particle-system targets, refused as unbound before
        f = cog_nif(particles=("p_Dust Door", "p_Sparks Track"))
        report = door_motion.inspect(f, ALIASES)
        self.assertEqual(report["issues"], [])
        self.assertEqual(sorted((t["target"], t["reason"]) for t in report["ignored_targets"]),
                         [("p_Dust Door", "particle system"), ("p_Sparks Track", "particle system")])
        self.assertEqual(convert(f, aliases=ALIASES)[1]["rig"], "native")
        door = door_nif(sliding_panels(), extra_targets=("p_Dust Door",))           # a real door is unchanged
        door.block_types.append("NiParticleSystem")
        door.block_type_index[[i for i in range(len(door.blocks)) if door.type_of(i) == "NiNode"][-1]] = len(door.block_types) - 1
        self.assertTrue(door_motion.inspect(door)["issues"])

    def test_the_float32_length_of_stage2_is_on_the_30_fps_grid(self):
        # PC build 01ee50e: Stage2 stops at float32(43 1/3 s) = 1300.0003 frames, refused as off the grid
        def stopping_at(stop):
            f = cog_nif()
            i = sequences(f)[b"Stage2"]
            block = bytearray(f.blocks[i])
            count = struct.unpack_from("<I", block, 4)[0]
            struct.pack_into("<f", block, 12 + 29 * count + 20, stop)
            f.blocks[i] = bytes(block)
            return door_rig.plan(f, placed=True, aliases=ALIASES)
        prepared = native_door.prepare(stopping_at(43.333343505859375), 0.01)     # the value the PC read
        self.assertEqual([round(c["duration"] * 30, 3) for c in prepared["clips"]], [1300.0, 1300.0])
        self.assertTrue({k["frame"] for t in prepared["clips"][1]["tracks"] for k in t["keys"]} >= {0, 1300})
        with self.assertRaisesRegex(nif.NifError, "not on the 30 fps grid"):
            native_door.prepare(stopping_at(43.34), 0.01)

    def test_close_is_open_played_backwards(self):
        plan = door_rig.plan(cog_nif(), placed=True, aliases=ALIASES)
        opening, closing = plan["clips"]
        self.assertEqual((opening["name"], closing["name"], closing["reversed_from"]), ("Open", "Close", "Open"))
        for a, b in zip(opening["tracks"], closing["tracks"]):
            self.assertEqual(b["samples"][0]["translation_source_units"], a["samples"][-1]["translation_source_units"])
            self.assertEqual(b["samples"][-1]["translation_source_units"], a["samples"][0]["translation_source_units"])
            self.assertEqual([s["elapsed"] for s in b["samples"]], sorted(s["elapsed"] for s in b["samples"]))
        self.assertIsNone(door_rig.rest_pose_issue(plan))

    def test_a_real_door_with_its_own_close_is_unchanged(self):
        plan = door_rig.plan(door_nif(sliding_panels()), placed=True)
        self.assertNotIn("reversed_from", plan["clips"][1])
        self.assertEqual(door_clips.reversed_clip(plan["clips"][0])["events"], [])


class CogDoorConversionTests(unittest.TestCase):
    def test_the_cog_door_gets_its_own_rig_and_says_which_clip_it_used(self):
        files, door = convert(cog_nif(), aliases=ALIASES)
        self.assertEqual(door["rig"], "native")
        self.assertEqual(door["sequence_aliases"], ALIASES)
        self.assertIn("meshes/fo4port/interiors/vault/vltgeardoor01/animations/Close.af", files)
        with self.assertRaisesRegex(nif.NifError, "exactly one Open and one Close"):
            convert(cog_nif())                                   # without the alias it is no door

    def test_skinned_shapes_are_left_out_and_listed_or_refused(self):
        f = cog_nif()
        real = nif.fo4_trishapes

        def one_skinned(source):
            shapes = real(source)
            return [dataclasses.replace(s, skinned=True, name=b"CogCable") if k == len(shapes) - 1 else s
                    for k, s in enumerate(shapes)]
        with patch.object(convert_static.nifmod, "fo4_trishapes", one_skinned):
            with self.assertRaisesRegex(nif.NifError, "skinned door shapes cannot be rigged"):
                convert(f, aliases=ALIASES)
            _, door = convert(f, aliases=ALIASES, drop_skinned=True)
        self.assertEqual(door["dropped_skinned_shapes"], ["CogCable"])
        self.assertEqual(door["rig"], "native")


class FakePack:
    def objects(self): return [(0, "hknpPhysicsSystemData")]
    def array(self, off): return 100, 1
    def pointer(self, off): return 1000
    def unpack(self, fmt, off): return (0, 0, 0, 1) if fmt == "<4f" else (0, 0, 0)


SLAB = [(x, y, z) for x in (-1.0, 1.0) for y in (-.5, .5) for z in (-.05, .05)]
SLAB_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
             (1, 5, 7), (1, 7, 3)]


def with_deck_collision(f):
    """cog_nif plus a helper node c_Deck (not a rig bone) under the first moving part, carrying one FO4 collision object."""
    from test_review_fixes import av_fields
    part = bytearray(f.blocks[1])
    shape = struct.unpack_from("<i", part, len(part) - 4)[0]
    helper = len(f.blocks)
    f.blocks[1] = bytes(part[:-8]) + struct.pack("<Iii", 2, shape, helper)
    f.add_block("NiNode", av_fields(f.string_index(b"c_Deck"), (0, 0, 0), IDENTITY, 1) + struct.pack("<I", 0))
    system = f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"test")
    f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", helper, 128, system, 0))
    return f


class CogDoorFo4BodyTests(unittest.TestCase):
    def run_convert(self, tris=SLAB_TRIS):
        from fo4sf import convert_static as cs, fo4collision, hkpackfile, meshcollision
        with patch.object(hkpackfile, "Packfile", return_value=FakePack()), \
                patch.object(meshcollision, "_shape_parts", return_value=[("convex", 1000, meshcollision.IDENTITY3, (0, 0, 0))]), \
                patch.object(fo4collision, "_convex", return_value=(SLAB, tris)):
            return convert(with_deck_collision(cog_nif()), aliases=ALIASES)

    def test_a_deck_keeps_its_thin_fo4_body_instead_of_the_bounding_block(self):
        from fo4sf import sfcollision
        files, door = self.run_convert()
        self.assertEqual(door["moving_bodies"], 1)
        self.assertTrue(door["fo4_collision"]["carried"])
        model = nif.parse(files["meshes/fo4port/interiors/vault/vltgeardoor01.nif"])
        bodies = [i for i in range(len(model.blocks)) if model.type_of(i) == "bhkNPCollisionObject"]
        self.assertEqual(len(bodies), 1)                  # the other moving part has no FO4 body: no body
        raw = files["meshes/fo4port/interiors/vault/vltgeardoor01.nif"]
        node = struct.unpack_from("<i", model.blocks[bodies[0]])[0]
        name = model.strings[struct.unpack_from("<i", model.blocks[node])[0]]
        self.assertTrue(name.startswith(b"Collision_") and name.endswith(b"_0"), name)
        blob = sfcollision.physics_blob_from_nif(raw, name)
        _, half = sfcollision.read_box(blob)
        self.assertAlmostEqual(min(half), sfcollision.MIN_LEAF_HALF, places=3)   # thin, not the 0.7 m leaf-sized block

    def test_a_large_mesh_part_is_refused(self):
        from fo4sf import fo4collision, meshcollision
        many = SLAB_TRIS * 5
        with patch.object(meshcollision, "_shape_parts", return_value=[("mesh", 1000, meshcollision.IDENTITY3, (0, 0, 0))]), \
                patch.object(fo4collision, "_compressed_mesh", return_value=(SLAB, many)):
            from fo4sf import hkpackfile
            with patch.object(hkpackfile, "Packfile", return_value=FakePack()):
                with self.assertRaisesRegex(nif.NifError, "not a thin deck"):
                    convert(with_deck_collision(cog_nif()), aliases=ALIASES)

    def test_a_source_without_collision_keeps_the_one_box_per_bone_fallback(self):
        files, door = convert(cog_nif(), aliases=ALIASES)
        self.assertNotIn("fo4_collision", door)
        self.assertGreaterEqual(door["moving_bodies"], 1)


class CogDoorRoutingTests(unittest.TestCase):
    convert = test_sliding_doors.NonHingedRoutingTests.convert

    def route(self, name, dll, multipart=None):
        with patch("test_sliding_doors.door_nif", lambda parts: cog_nif(parts)):
            with tempfile.TemporaryDirectory() as staging:
                return self.convert(staging, name, sliding_panels(), dll, multipart)

    def test_the_cog_door_takes_the_own_rig_path_with_its_alias(self):
        result, single, multi, static = self.route(COG, "calumi.dll")
        self.assertTrue(result["ok"], result)
        single.assert_not_called()
        static.assert_not_called()
        self.assertEqual(multi.call_args.kwargs["aliases"], ALIASES)
        self.assertTrue(multi.call_args.kwargs["drop_skinned"])
        self.assertEqual(multi.call_args.kwargs["seam_limit_m"], convert_static.SEAM_LIMIT_M)      # the catwalk's hinged seams may ride one bone
        self.assertTrue(multi.call_args.kwargs["rest_pose_check"])
        self.assertEqual(result["door"]["rig"], "native")

    def test_a_failed_rig_or_no_library_leaves_it_solid_not_passable(self):
        def fail(*a, **k):
            raise nif.NifError("synthetic failure")
        for dll, multipart in (("calumi.dll", fail), (None, None)):
            result, _, _, static = self.route(COG, dll, multipart)
            self.assertTrue(result["ok"], result)
            self.assertNotIn("door_not_opening", result)
            self.assertNotIn("door", result)
            self.assertIsNotNone(static.call_args.kwargs["collision_template"])   # keeps its collision

    def test_another_activator_with_a_stage2_clip_is_not_a_door(self):
        result, single, multi, static = self.route("meshes/Interiors/Vault/VltElevator.nif", "calumi.dll")
        multi.assert_not_called()
        single.assert_not_called()
        static.assert_called_once()
        self.assertNotIn("door", result)


if __name__ == "__main__":
    unittest.main()
