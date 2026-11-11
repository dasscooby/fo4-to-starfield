"""Reproducing tests of the offline bug hunt (issue #200, 2026-10-16): one test per confirmed finding, each marked
expectedFailure until its issue is fixed, so the suite stays green and the fix flips the decorator off. Every test is
synthetic (no game data): the collision ones build a Havok 2014 packfile and a Starfield tagfile template with
havok_fixtures.py, the navmesh ones use test_navmesh's builders, the texture ones write bytes in a temp folder.
Each test's docstring starts with its issue number (#203 to #220); the finding's file:line is at main 1b3ba39."""
import importlib.util
import json
import os
import struct
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fo4sf import fo4collision as fc  # noqa: E402
from fo4sf import convert_static, door_motion, fo4land, meshcollision, pipeline, sfbodies, textures  # noqa: E402
from fo4sf import navmesh as nm  # noqa: E402
from fo4sf import nif  # noqa: E402
import bridge_log  # noqa: E402
import testqueue as tq  # noqa: E402
import test_testqueue as tt  # noqa: E402
import havok_fixtures as hf  # noqa: E402
import parse_getpos as pg  # noqa: E402
import test_walk_eval as twe  # noqa: E402
import walk_eval as we  # noqa: E402
import test_fo4land as tf  # noqa: E402
import test_navmesh as tn  # noqa: E402
import test_door_two_panels as tdp  # noqa: E402
from test_review_fixes import av_fields, trishape_block  # noqa: E402


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace("/", "_"), os.path.join(ROOT, "scripts", name))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TextureTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_decode_bc5_accepts_sizes_that_are_not_multiples_of_four(self):
        """#203: textures.py:71 decode_bc4 / decode_bc5 reshape (h//4, w//4, 4, 4): a 1x1, 2x2, 6x6 or 8x6 texture (one
        partial block, which _bc_level_bytes counts with (w + 3) // 4) raises ValueError instead of returning planes."""
        block = bytes([200, 100] + [0] * 6) * 2                      # one BC5 block: an R half and a G half
        for w, h in ((2, 2), (1, 1), (6, 6), (4, 2), (8, 6)):
            n = ((w + 3) // 4) * ((h + 3) // 4)
            planes = textures.decode_bc5(block * n, w, h)
            for p in (planes if isinstance(planes, tuple) else (planes,)):
                self.assertEqual(tuple(p.shape[:2]), (h, w), (w, h))

    @staticmethod
    def rgba_dds(w, h):
        return struct.pack("<4s7I", b"DDS ", 124, 0x100F, h, w, w * 4, 0, 1) + bytes(44) + \
            struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0) + struct.pack("<5I", 0x1000, 0, 0, 0, 0) + \
            struct.pack("<5I", 28, 3, 0, 1, 0) + bytes([200, 200, 200, 255]) * (w * h)

    @unittest.expectedFailure
    def test_a_decal_without_a_normal_map_gets_a_flat_normal(self):
        """#204: pipeline.py:286 hands np.zeros(int8) to textures.write_rg8_snorm, which maps unorm 0..255 (128 = zero);
        every texel of the written R8G8_SNORM normal is (-127, -127), a normal tilted hard to -x/-y, not the flat
        (0, 0) that _make_neutral_material writes with np.full(..., 128)."""
        with tempfile.TemporaryDirectory() as tmp:
            conv = pipeline.Converter.__new__(pipeline.Converter)
            conv.staging, conv.texconv, conv.prefix = tmp, "texconv", "fo4port"
            conv.texture_caps, conv.texture_log, conv._decal_template, conv.content_resources = {}, {}, {"t": 1}, "cr.zip"
            conv.src = SimpleNamespace(texture=lambda name: self.rgba_dds(4, 4) if name == "fx/grime_d.dds" else None)

            def fake_texconv(exe, src, out_dir, fmt, extra=()):
                pass                                                  # the uncompressed intermediate stays as written
            with mock.patch.object(textures, "texconv", side_effect=fake_texconv), \
                    mock.patch.object(pipeline.cm, "build_from_template", return_value={}), \
                    mock.patch.object(pipeline.cm, "dump_mat", return_value="{}"):
                conv._convert_texture_set("fxdecals/grime", "fx/grime_d.dds", "", "", decal=True)
            with open(os.path.join(tmp, "textures", "fo4port", "fxdecals", "grime_normal.dds"), "rb") as f:
                normal = f.read()
            h = textures.read_dds_header(normal)
            self.assertEqual(h["dxgi"], textures.DXGI_R8G8_SNORM)
            texels = np.frombuffer(normal[h["data_offset"]:], dtype=np.int8).reshape(-1, 2)
            self.assertEqual(set(map(tuple, texels.tolist())), {(0, 0)})


class ScriptTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_convert_batch_applies_max_tris(self):
        """#205: scripts/convert_batch.py:151 parses --max-tris ("skip meshes with more triangles than this") and never
        reads it again: with --max-tris 0 every mesh is still converted and listed as a success."""
        batch = load_script("convert_batch.py")
        with tempfile.TemporaryDirectory() as tmp:
            staging = os.path.join(tmp, "staging")
            collision = os.path.join(tmp, "c.nif")
            with open(collision, "wb") as f:
                f.write(b"x")
            src = SimpleNamespace(mesh_names=lambda pattern: ["meshes/big.nif"])
            seen, calls = {}, []

            def converter(*args, **kw):
                seen.update(kw)
                return SimpleNamespace(stats={}, material_errors={}, convert_nif=lambda n: (
                    calls.append(n) or {"ok": True, "out_name": "fo4port/big", "shapes": 1, "fallback_materials": 0}))
            argv = ["convert_batch.py", "--fo4-data", "u", "--staging", staging, "--content-resources", "u", "--texconv", "u",
                    "--collision-template", collision, "--max-tris", "0"]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                    mock.patch.object(batch.pipeline, "Converter", side_effect=converter), \
                    mock.patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"t"), \
                    mock.patch("builtins.print"):
                batch.main()
        self.assertTrue("max_tris" in seen or calls == [], f"--max-tris 0 reached nothing: converter kwargs {sorted(seen)}, converted {calls}")

    @unittest.expectedFailure
    def test_convert_asset_without_a_folder_writes_single_separators(self):
        """#206: scripts/convert_asset.py:50: with --name chair (no folder) tex_rel is 'textures//chair' (strip('/') trims the
        ends only); the DDS files land at textures/chair_<kind>.dds but build_mat gets 'Data\\textures\\\\chair_color.dds',
        a path that is not the written file's. mat_rel on line 79 handles the same case with .replace('//', '/')."""
        ca = load_script("convert_asset.py")
        with tempfile.TemporaryDirectory() as tmp:
            fo4 = os.path.join(tmp, "fo4")
            os.makedirs(os.path.join(fo4, "materials"))
            os.makedirs(os.path.join(fo4, "textures"))
            with open(os.path.join(fo4, "materials", "m.bgsm"), "wb") as f:
                f.write(b"bgsm")
            for n in ("d.dds", "n.dds", "s.dds"):
                with open(os.path.join(fo4, "textures", n), "wb") as f:
                    f.write(b"DDS " + bytes(124))
            nifp = os.path.join(tmp, "in.nif")
            with open(nifp, "wb") as f:
                f.write(b"nif")
            staging = os.path.join(tmp, "staging")

            def fake_texconv(exe, src, out_dir, fmt, extra=()):
                with open(os.path.join(out_dir, os.path.basename(src)), "wb") as f:
                    f.write(b"converted")
            plane = np.zeros((4, 4), np.uint8)
            seen = {}

            def build_mat(template, name, color, normal, rough, metalness=0.0):
                seen.update(color=color, normal=normal, rough=rough)
                return {}
            argv = ["convert_asset.py", "--fo4-nif", nifp, "--fo4-root", fo4, "--staging", staging, "--name", "chair",
                    "--content-resources", "cr.zip", "--texconv", "tc.exe"]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(ca.nif, "parse", return_value=SimpleNamespace(strings=[b"materials\\m.bgsm"])), \
                    mock.patch.object(ca.cm, "parse_bgsm", return_value=SimpleNamespace(diffuse="d.dds", normal="n.dds", smooth_spec="s.dds")), \
                    mock.patch.object(ca.textures, "texconv", side_effect=fake_texconv), \
                    mock.patch.object(ca.textures, "load_fo4_bc5", return_value=(plane, plane)), \
                    mock.patch.object(ca.cm, "read_template", return_value={}), mock.patch.object(ca.cm, "build_mat", side_effect=build_mat), \
                    mock.patch.object(ca.cm, "dump_mat", return_value="{}"), \
                    mock.patch.object(ca.convert_static, "convert_static", return_value={"meshes/chair.nif": b"x"}), \
                    mock.patch("builtins.print"):
                ca.main()
            written = sorted(os.path.relpath(os.path.join(d, f), staging) for d, _, fs in os.walk(staging) for f in fs)
        for key in ("color", "normal", "rough"):
            self.assertNotIn("//", seen[key], seen)
            self.assertNotIn("\\\\", seen[key], seen)
        self.assertTrue(any(w.endswith("chair_color.dds") for w in written), written)


class TerrainTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_read_world_lists_the_persistent_references(self):
        """#207: fo4land.py:202 Plugin.read_world initialises result["persistent"] = [] and nothing appends to it: the
        persistent cell goes to "persistent_cell" and its REFR/ACHR to cell["persistent_refs"], so the documented
        top-level list is empty for every world."""
        steps = tf.plane_steps(0, 0)
        cells = {(0, 0): (fo4land.encode_vhgt(3.0, steps), [])}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.esm")
            with open(path, "wb") as f:
                f.write(tf.build_plugin(cells, persistent_refs=[tf.refr(0x901, 0x100, (-100.0, -100.0, 5.0))]))
            with fo4land.Plugin(path) as p:
                w = p.read_world("TestWorld")
        self.assertEqual(len(w["persistent"]), 1, w.get("persistent_cell"))


class NavmeshTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_inventory_reduced_triangle_loss_is_never_negative(self):
        """#208: scripts/actors/navmesh_inventory.py:109: a cell is "reduced" when EITHER the triangle count OR the area fell;
        reduced_triangles_approx sums fo4 - sf over those cells, so a cell flagged for an 80 % area loss while the
        triangle count rose 50 % contributes -50 and the headline loss goes negative or cancels real losses."""
        inv = load_script(os.path.join("actors", "navmesh_inventory.py"))
        r = inv.inventory({"c": {"triangles": 100, "area": 50.0}}, {"c": {"triangles": 150, "area": 10.0}})
        self.assertEqual([x["cell"] for x in r["reduced_coverage"]], ["c"])
        self.assertGreaterEqual(r["reduced_triangles_approx"], 0, r["reduced_triangles_approx"])

    @unittest.expectedFailure
    def test_clipped_triangles_counts_only_triangles_that_were_cut(self):
        """#209: navmesh.py:563: cut = (cx0, cy0) != (cx1, cy1) from a bounding box widened by eps, so a triangle whose edge
        lies exactly on a 100 m cell line spans two cell indices and is counted as clipped although it stays whole."""
        pieces, rep = nm.convert([(0x1, nm.parse(tn.fo4_bytes(0x3C, (0, 0), *tn.square(0, 100, 700, 800))))])
        self.assertEqual([(p.cell, len(p.tris)) for p in pieces], [((0, 0), 2)])    # whole, one piece
        self.assertEqual(rep["clipped_triangles"], 0)

    @staticmethod
    def portal(xa, xb):
        """Two navmeshes joined by an FO4 type-0 portal: A's edge at x = xa, B's at x = xb (units; 7000 = 100 m)."""
        F = nm.F_FOUND
        av, _ = tn.square(xa - 700, 700, xa, 1400)
        bv, _ = tn.square(xb, 700, xb + 700, 1400)
        at = [((0, 1, 2), (-1, 0, 1), 3.4e38, F | nm.EDGE_LINK_BITS[1]), ((0, 2, 3), (0, -1, -1), 3.4e38, F)]
        bt = [((0, 1, 2), (-1, -1, 1), 3.4e38, F), ((0, 2, 3), (0, -1, 0), 3.4e38, F | nm.EDGE_LINK_BITS[2])]
        a = (0xA, nm.parse(tn.fo4_bytes(0x3C, (0, 0), av, at, links=[(0, 0xB, 1, 2)])))
        b = (0xB, nm.parse(tn.fo4_bytes(0x3C, (0, 0), bv, bt, links=[(0, 0xA, 0, 1)])))
        pieces, rep = nm.convert([a, b])
        fids, navs, infos = tn.sf_set(pieces)
        return (rep["links"]["fo4_portal"], rep["dropped"]["fo4_portal_subedge_missing"],
                nm.validate(navs, infos)["errors"], nm.triangle_path(navs, (fids[0], 0), (fids[1], 0)) is not None)

    @unittest.expectedFailure
    def test_a_portal_on_or_straddling_a_cell_line_is_linked(self):
        """#210: navmesh.py:677: convert() joins an FO4 portal inside ONE Starfield cell only; a portal whose two edges sit on
        the 100 m line (or straddle it by less than FO4's own 0.343 m gap) has its sub-edges in two cells, is never
        linked and is counted as 'fo4_portal_subedge_missing' (4,599 such drops in the committed core64n report), while
        validate() reports 0 errors. Related: #173."""
        self.assertEqual(self.portal(1400, 1400), (1, 0, [], True))        # 20 m: linked
        self.assertEqual(self.portal(7007, 7007), (1, 0, [], True))        # 100.1 m: linked
        self.assertEqual(self.portal(7000, 7000)[::3], (1, True), "a portal exactly on x = 100 m is dropped")
        self.assertEqual(self.portal(6986, 7014)[::3], (1, True), "a portal straddling x = 100 m is dropped")


class CollisionTests(unittest.TestCase):
    @staticmethod
    def two_body_system(w):
        """Body 0 a static anchor, body 1 a dynamic 5 kg convex (motion 0 -> props 0, inverse mass 0.2)."""
        v, f = hf.cube((0, 0, 0), (1, 1, 1))
        a = hf.fo4_convex(w, v, f)
        b = hf.fo4_convex(w, [(x + 2, y, z) for x, y, z in v], f)
        return [(a, (0, 0, 0), (0, 0, 0, 1), 1, fc.STATIC_MOTION), (b, (0, 0, 0), (0, 0, 0, 1), 4, 0)], [(0, 0.2)]

    @staticmethod
    def two_object_nif(blob):
        """root -> two NiNodes, each with a bhkNPCollisionObject owning body 0 / body 1 of the one bhkPhysicsSystem."""
        f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
        f.string_index(b"Bone")
        ident = (1, 0, 0, 0, 1, 0, 0, 0, 1)
        f.add_block("NiNode", av_fields(0, (0, 0, 0), ident, 1.0) + struct.pack("<Iii", 2, 1, 2))
        f.add_block("NiNode", av_fields(0, (0, 0, 0), ident, 1.0) + struct.pack("<I", 0))
        f.add_block("NiNode", av_fields(0, (70, 0, 0), ident, 1.0) + struct.pack("<I", 0))
        f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 1, 0x80, 5, 0))
        f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 2, 0x80, 5, 1))
        f.add_block("bhkPhysicsSystem", struct.pack("<I", len(blob)) + blob)
        f.footer = struct.pack("<II", 1, 0)
        return nif.parse(nif.serialize(f))

    @unittest.expectedFailure
    def test_a_declined_multi_body_system_keeps_its_dynamic_body_static(self):
        """#211: meshcollision.py:958: after rigid_dynamic_body declines a multi-body system (motion["rigid_reported"] = True),
        convert_bodies' `if why and not motion.get("rigid_reported")` falls into the else branch for every body with a
        FO4 mass: with no dynamic template (the native path, convert_static.py:180 passes None whenever the merge was
        attempted) _Tmpl(None) raises TypeError, fo4_native_collision records fo4_collision_error and the whole model
        loses its native collision; with a template, one body of the system is written motionType 2 (dynamic)."""
        blob = hf.pack_blob(self.two_body_system)
        src = self.two_object_nif(blob)
        report, motion = {}, {}
        res = convert_static.fo4_native_collision(src, hf.universal_template(), report,
                                                  dynamic_template=hf.universal_template(dynamic=True), motion=motion)
        self.assertNotIn("fo4_collision_error", report, report)
        self.assertEqual(len(res or []), 2, report)
        motion = {"rigid_reported": True}
        meshcollision.convert_bodies(blob, hf.universal_template(), node_rot=None, skipped=[],
                                     dynamic_template=hf.universal_template(dynamic=True), motion=motion)
        self.assertNotIn("dynamic", motion, motion)                      # "any other dynamic body stays static"

    @staticmethod
    def mesh_with_odd_primitives(prims):
        def build(w):   # one section, four packed vertices (11/11/10-bit, scale 0.01)
            packed = [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)]
            secs = [dict(off=(0, 0, 0), scale=(0.01,) * 3, first_packed=0, shared_start=0, n_shared_idx=0,
                         prim_start=0, n_prim=len(prims), n_packed=4)]
            m = hf.fo4_mesh(w, secs, prims, packed, keys=(2, 8, 1))
            return [(m, (0, 0, 0), (0, 0, 0, 1), 1, fc.STATIC_MOTION)], []
        return hf.pack_blob(build)

    @unittest.expectedFailure
    def test_decode_sf_mesh_skips_unused_slots_and_degenerate_points_like_the_fo4_reader(self):
        """#212: meshcollision.py:359: decode_sf_mesh iterates every primitive without the filter fo4collision._compressed_mesh
        (line 72) and sfbodies._cms_triangles (line 128) apply; transplant copies FO4's primitive array verbatim, so an
        unused 0xDEAD slot makes it index sharedVertices out of range (IndexError) and a degenerate point (i, i, i, i)
        becomes an extra zero-area triangle, so its count disagrees with the FO4 decode of the same blob."""
        blob = self.mesh_with_odd_primitives([(0, 1, 2, 3), (0xDE, 0xAD, 0xDE, 0xAD), (1, 1, 1, 1)])
        sf = meshcollision.transplant(blob, hf.universal_template())
        self.assertEqual(len(fc.decode(blob)[1]), 2)
        self.assertEqual(len(sfbodies.blob_bodies(sf)[0]["triangles"]), 2)
        self.assertEqual(len(meshcollision.decode_sf_mesh(sf)), 2)      # IndexError today
        blob2 = self.mesh_with_odd_primitives([(0, 1, 2, 3), (1, 1, 1, 1)])
        sf2 = meshcollision.transplant(blob2, hf.universal_template())
        self.assertEqual(len(meshcollision.decode_sf_mesh(sf2)), len(fc.decode(blob2)[1]))   # 3 != 2 today


class JudgeTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_bridge_log_clock_age_is_positive_for_a_stamp_from_yesterday(self):
        """#213: scripts/game/bridge_log.py:200 clock_age wraps a stamp past midnight only when it is more than 12 h
        ahead of now, so a stamp 12 to 24 h old gets a negative age and latest(max_age=3) reports the stale line ok."""
        now = time.mktime((2026, 10, 15, 2, 0, 0, 0, 0, -1))                  # 02:00:00 local
        self.assertEqual(bridge_log.clock_age("13:00:00", now), 13 * 3600)    # -39600 today
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(time, "time", lambda: now):
            log = os.path.join(tmp, "fo4sf.0.log")
            with open(log, "w", encoding="utf-8") as f:
                f.write("[13:00:00] FO4SF rt=1 pos=-10.07 43.95 -10.95 n=7\n")
            os.utime(log, (now - 13 * 3600, now - 13 * 3600))
            r = bridge_log.latest(log, max_age=3)
        self.assertIs(r["ok"], False, r)

    @unittest.expectedFailure
    def test_walk_judge_never_passes_a_leg_with_a_recorded_popup(self):
        """#214: scripts/game/walk_eval.py:440 turns a recorded popup into a FAIL only when its text matches
        BOUNDARY|REACHED; qstep.ps1 (line 1732) records popups for FAST TRAVEL and PLANET MAP too, and such a leg
        passes."""
        t, _ = twe.test_of()
        obs = twe.good_obs()
        obs["legs"][2]["popup"] = "PLANET MAP"                                  # what qstep.ps1 records from the centre OCR
        obs["legs"][2]["shot"] = "walk_002.png"                                 # the event's screenshot is kept
        self.assertNotEqual(we.judge(t, obs, twe.shot_ok)[0], "PASS")

    @unittest.expectedFailure
    def test_parse_getpos_with_a_nonce_never_joins_an_older_value(self):
        """#215: scripts/game/parse_getpos.py:57 cuts the text at the nonce's echo and then runs the bare-number
        fallback over everything after it; in the column OCR layout an older read's value sits after this read's
        echo, so with one own value lost the last three numbers are the previous Z plus this X and Z."""
        n = "fo4sfr1a2b3c4d"
        col = ("GetPos: Z > >\n" + n + "\nScript command \"" + n + "\" not found.\nplayer.getpos x\nGetPos: X > >\n"
               "player.getpos y\nGetPos: Y > >\nplayer.getpos z\nGetPos: Z > >\n99.74\n-2195.27\n99.41")   # Y value lost
        self.assertEqual(pg.parse(col, nonce=n), "fail")                       # '99.74 -2195.27 99.41' today


class DoorTests(unittest.TestCase):
    @staticmethod
    def two_leaf_door():
        """Root -> Door (animated, constant keys) -> LeafA, LeafB (each with geometry and its own opposite keys)."""
        ident = (1, 0, 0, 0, 1, 0, 0, 0, 1)
        f = nif.NifFile(bs_version=130)
        root, door, a, b = [f.string_index(s) for s in (b"Root", b"Door", b"LeafA", b"LeafB")]
        f.add_block("NiNode", av_fields(root, (0, 0, 0), ident, 1) + struct.pack("<Ii", 1, 1))
        f.add_block("NiNode", av_fields(door, (0, 0, 0), ident, 1) + struct.pack("<Iii", 2, 2, 3))
        f.add_block("NiNode", av_fields(a, (0, -70, 0), ident, 1) + struct.pack("<Ii", 1, 4))
        f.add_block("NiNode", av_fields(b, (0, 70, 0), ident, 1) + struct.pack("<Ii", 1, 5))
        for _ in range(2):
            f.add_block("BSTriShape", trishape_block([(0, 0, 0), (0, 70, 0), (0, 70, 140)], [(0, 1, 2)]))

        def seq(name, keys):
            interps = []
            for n, (pos, rk) in keys:
                d = f.add_block("NiTransformData", tdp.transform_data(rk, None))
                interps.append(f.add_block("NiTransformInterpolator", struct.pack("<8fi", *pos, 1, 0, 0, 0, 1, d)))
            targets = b"".join(struct.pack("<iiBiiiii", i, -1, 0, n, -1, -1, -1, -1) for i, (n, _) in zip(interps, keys))
            f.add_block("NiControllerSequence", struct.pack("<iII", f.string_index(name), len(interps), 0) + targets
                        + struct.pack("<fiIfffiiH", 1, -1, 2, 1, 0, 1, -1, root, 0))
        q = tdp.quat_z
        seq(b"Open", [(door, ((0, 0, 0), [(0, q(0)), (1, q(0))])), (a, ((0, -70, 0), [(0, q(0)), (1, q(-90))])),
                      (b, ((0, 70, 0), [(0, q(0)), (1, q(90))]))])
        seq(b"Close", [(door, ((0, 0, 0), [(0, q(0)), (1, q(0))])), (a, ((0, -70, 0), [(0, q(-90)), (1, q(0))])),
                       (b, ((0, 70, 0), [(0, q(90)), (1, q(0))]))])
        f.footer = struct.pack("<II", 1, 0)
        return f

    @unittest.expectedFailure
    def test_leaves_with_their_own_keys_under_an_animated_parent_need_more_than_one_hinge(self):
        """#216: door_motion.py:108-113 derives the "outside the single hinge" set from subtree membership only, so two
        leaves with their own opposite keys under an animated parent read as covered by one hinge; frozen_door_parts is
        empty, the own-rig path is never taken and convert_door welds both leaves to one pivot."""
        f = self.two_leaf_door()
        r = door_motion.inspect(f)
        self.assertTrue(r["requires_additional_motion_support"], r)
        self.assertEqual(sorted(r["animated_shapes_outside_single_hinge"]), [4, 5])
        self.assertNotEqual(convert_static.frozen_door_parts(f), [])


class RunnerTests(unittest.TestCase):
    """testqueue.py's planners, judge and run loop (scripts/game); the runner tests of test_testqueue.py supply the
    fake controls and the queue builder. Every run here is offline: no game, no PowerShell."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        self.staging = os.path.join(self.d, "staging")
        os.makedirs(self.staging)
        with open(os.path.join(self.staging, "FO4Port.esm"), "wb") as f:
            f.write(b"TES4")

    def plan(self, kind, entries, name, *extra):
        exp = os.path.join(self.d, "exp_" + name)
        os.makedirs(exp)
        with open(os.path.join(exp, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(entries, f)                                    # json.dump writes NaN by default, as numpy-fed generators do
        out = os.path.join(self.d, "q_" + name)
        with mock.patch("builtins.print"):
            tq.main([kind, "--staging", self.staging, "--exp-dir", exp, "--out", out, *extra])
        with open(os.path.join(out, "queue.json"), encoding="utf-8") as f:
            return out, json.load(f)

    @unittest.expectedFailure
    def test_plan_movable_pins_the_bridge_it_was_given(self):
        """#218: testqueue.py:1109 plan_movable calls queue_extras with SimpleNamespace(plugins=""), so apply_bridge
        never sees --bridge: no bridge pin in queue.json, no bridge_reads on the test, no "bridge" need, and a
        missing --bridge folder is not refused (the other planners refuse it)."""
        br = os.path.join(self.d, "bridge")
        os.makedirs(os.path.join(br, "Data", "Scripts"))
        with open(os.path.join(br, "FO4SFBridge.esm"), "wb") as f:
            f.write(b"plugin")
        with open(os.path.join(br, "Data", "Scripts", "FO4SF_Bridge.pex"), "wb") as f:
            f.write(b"pex")
        plan = [{"label": "C_burntbook", "travel": "coc QASmoke", "base": "0200CE2A", "mass_kg": 25.0, "spot": [-3.0, 4.0, 0.0]}]
        _, q = self.plan("plan-movable", plan, "movable", "--bridge", br)
        self.assertIn("bridge", q, sorted(q))
        self.assertTrue(q["tests"][0].get("bridge_reads"), q["tests"][0])
        self.assertIn("bridge", q.get("needs", []))
        with self.assertRaises(SystemExit):
            self.plan("plan-movable", plan, "movable2", "--bridge", os.path.join(self.d, "nowhere"))

    @unittest.expectedFailure
    def test_terrain_points_are_validated_and_the_judge_never_passes_without_them(self):
        """#219: testqueue.py:489 plan_terrain copies "points" from plan.json unvalidated; the terrain judge then
        PASSes a test with no points on a screenshot alone, PASSes a NaN expect with a read 400 m below, and raises
        TypeError on a string expect (the npc / door / walk / movable planners refuse such values at planning)."""
        d = os.path.join(self.d, "obs")
        os.makedirs(d)
        shot = tt.touch(d, "spawn.png")
        _, q = self.plan("plan-terrain", [{"coc": "FO4CW_X", "points": [], "beyond": {"x": 0.0, "y": 0.0}}], "nopoints")
        self.assertNotEqual(tq.judge(q["tests"][0], {"shot": shot}, d)[0], "PASS")
        _, q = self.plan("plan-terrain", [{"coc": "FO4CW_X", "points": [{"label": "v0", "x": 0.0, "y": 0.0, "expect": float("nan")}]}], "nan")
        self.assertNotEqual(tq.judge(q["tests"][0], {"shot": shot, "points": [{"read": "0.0 0.0 -400.0"}]}, d)[0], "PASS")
        _, q = self.plan("plan-terrain", [{"coc": "FO4CW_X", "points": [{"label": "v0", "x": 0.0, "y": 0.0, "expect": "15"}]}], "str")
        verdict = tq.judge(q["tests"][0], {"shot": shot, "points": [{"read": "0.0 0.0 15.0"}]}, d)   # TypeError today
        self.assertIn(verdict[0], ("PASS", "FAIL", "INCONCLUSIVE"))

    @unittest.expectedFailure
    def test_an_open_breaker_never_rewrites_a_test_that_ran(self):
        """#220: testqueue.py:2994 the open-breaker branch appends a BREAKER row "not run", attempt 0, and sets
        done[id].attempts = 0 for a test that already ran once (its retry was pending), so its real INCONCLUSIVE
        attempt vanishes from state.done and the report keeps only "BREAKER 6, not run"."""
        tt.make_queue(self.d, n=tq.BREAKER)                            # six fall tests, --max-attempts 2
        r = tq.Runner(self.d, tt.args(max_attempts=2), ctl=tt.FakeControls(), step=lambda t, o: 0)   # never an obs.json
        r.session, r.cell, r._ps = True, "C", (lambda *a, **k: (0, ""))
        r.log = lambda msg: None
        r.run()
        with open(os.path.join(self.d, "state.json"), encoding="utf-8") as f:
            st = json.load(f)
        with open(os.path.join(self.d, "results.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(x) for x in f if x.strip()]
        self.assertEqual(st["attempts"]["0000_fall"], 1)
        self.assertEqual(st["done"]["0000_fall"]["attempts"], st["attempts"]["0000_fall"])
        last = [x for x in rows if x["id"] == "0000_fall"][-1]
        self.assertNotEqual((last["attempt"], last["class"]), (0, "BREAKER"), last)


if __name__ == "__main__":
    unittest.main()
