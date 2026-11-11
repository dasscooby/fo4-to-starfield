"""Synthetic path/constant fixtures for docs/terrain/surface-map.md. No game files."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import surface_map as sm  # noqa: E402


class LodsettingsPath(unittest.TestCase):
    def test_world_edid_lowercases_like_lc172world(self):
        self.assertEqual(sm.lodsettings_rel("LC172World"), "lodsettings/lc172world.lod")
        self.assertEqual(
            sm.lodsettings_rel(sm.WORLD_EDID), "lodsettings/fo4core_commonwealth.lod"
        )

    def test_blank_or_pathed_edid_is_refused(self):
        for bad in ("", "  x", "x/y", "a\\b"):
            with self.assertRaises(ValueError):
                sm.lodsettings_rel(bad)


class WorldObjectLodVsConvertedFo4(unittest.TestCase):
    def test_generated_lod_indices_0_to_3_count(self):
        for i in range(4):
            path = f"meshes/lod/generated/newatlantis_something_lod_{i}.nif"
            self.assertTrue(sm.is_starfield_world_lod_mesh(path))
            self.assertFalse(sm.is_converted_fo4_lod_mesh(path))

    def test_fo4core_lod_nif_is_not_world_object_lod(self):
        path = "meshes/fo4core/lod/neighborhoods/backbay/backbay02_bld01lod.nif"
        self.assertTrue(sm.is_converted_fo4_lod_mesh(path))
        self.assertFalse(sm.is_starfield_world_lod_mesh(path))
        self.assertFalse(sm.is_starfield_world_lod_mesh("meshes/lod/generated/x_lod_4.nif"))

    def test_backslash_and_case_do_not_reclassify(self):
        self.assertTrue(
            sm.is_starfield_world_lod_mesh(r"Meshes\LOD\generated\City_lod_0.NIF")
        )
        self.assertTrue(
            sm.is_converted_fo4_lod_mesh(r"Meshes\FO4Core\LOD\unique\cit\x_lod_0.nif")
        )


class Fo4LodSourceKinds(unittest.TestCase):
    def test_per_object_nif_is_not_starfield_generated(self):
        path = r"Meshes\LOD\Neighborhoods\Financial\Financial15_Bld01LOD.nif"
        self.assertTrue(sm.is_fo4_per_object_lod_nif(path))
        self.assertFalse(sm.is_starfield_world_lod_mesh(path))
        self.assertFalse(sm.is_converted_fo4_lod_mesh(path))
        self.assertFalse(sm.is_fo4_world_object_lod_tile(path))

    def test_converted_fo4core_lod_is_not_a_fo4_source_nif(self):
        path = "meshes/fo4core/lod/neighborhoods/backbay/backbay02_bld01lod.nif"
        self.assertTrue(sm.is_converted_fo4_lod_mesh(path))
        self.assertFalse(sm.is_fo4_per_object_lod_nif(path))
        self.assertFalse(sm.is_starfield_world_lod_mesh(path))

    def test_starfield_generated_is_not_a_fo4_source_nif(self):
        path = "meshes/lod/generated/newatlantis_something_lod_0.nif"
        self.assertTrue(sm.is_starfield_world_lod_mesh(path))
        self.assertFalse(sm.is_fo4_per_object_lod_nif(path))

    def test_bto_and_btr_and_fo4_lodsettings(self):
        bto = r"Meshes\Terrain\Commonwealth\Objects\Commonwealth.16.-16.-32.BTO"
        btr = r"Meshes\Terrain\Commonwealth\Commonwealth.16.-16.16.BTR"
        lod = r"LODSettings\Commonwealth.LOD"
        self.assertTrue(sm.is_fo4_world_object_lod_tile(bto))
        self.assertTrue(sm.is_fo4_terrain_lod_tile(btr))
        self.assertTrue(sm.is_fo4_lodsettings(lod))
        self.assertFalse(sm.is_fo4_per_object_lod_nif(bto))
        self.assertFalse(sm.is_starfield_world_lod_mesh(bto))
        self.assertFalse(sm.is_fo4_lodsettings("lodsettings/fo4core_commonwealth.lod"))
        self.assertFalse(sm.is_fo4_lodsettings("lodsettings/lc172world.lod"))


class OverlayIsMars(unittest.TestCase):
    def test_core64k_parent_and_overlay_ids_match_lc172(self):
        self.assertEqual(sm.MARS_SURFACE, 0x0001B736)
        self.assertEqual(sm.MARS_PNDT, 0x0003F59A)
        self.assertEqual((sm.OVERLAY_SNAM_SOL, sm.OVERLAY_PNAM_MARS), (0, 4))
