import struct
import unittest
from test_door_motion import fixture
from fo4sf import animation_curves, nif


class AnimationCurveTests(unittest.TestCase):
    def test_quadratic_translation_tangents_and_scale(self):
        data = struct.pack("<III10fII2f", 0, 1, 2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 1, 1, 0, 2)
        result = animation_curves.decode(data)
        key = result["translation_source_units"]["keys"][0]
        self.assertEqual(key["value"], [1, 2, 3])
        self.assertEqual(key["forward"], [4, 5, 6])
        self.assertEqual(key["backward"], [7, 8, 9])
        self.assertEqual(result["scale"]["keys"][0]["value"], [2])

    def test_quaternion_tbc_and_empty_channels(self):
        result = animation_curves.decode(struct.pack("<II8fII", 1, 3, 0, 1, 0, 0, 0, .1, .2, .3, 0, 0))
        self.assertEqual(result["rotation"]["keys"][0]["value"], [1, 0, 0, 0])
        self.assertEqual(len(result["rotation"]["keys"][0]["tension_bias_continuity"]), 3)

    def test_xyz_channels_and_bad_data(self):
        data = struct.pack("<IIII2fIIII", 1, 4, 1, 1, 0, .5, 0, 0, 0, 0)
        self.assertEqual(animation_curves.decode(data)["rotation"]["axes"][0]["keys"][0]["value"], [.5])
        for invalid in (data[:-1], data + b"extra", struct.pack("<II", 1, 99)):
            with self.assertRaises(nif.NifError):
                animation_curves.decode(invalid)
