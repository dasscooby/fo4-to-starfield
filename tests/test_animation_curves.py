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

class CurveEvaluationTests(unittest.TestCase):
    def group(self, mode, values):
        return {'interpolation': mode, 'keys': values}

    def test_linear_clamp_and_empty_bind(self):
        group = self.group(1, [{'time': 2, 'value': [0, 2, 4]}, {'time': 6, 'value': [8, 6, 0]}])
        self.assertEqual(animation_curves.evaluate_group(group, 3, [0]*3), [2, 3, 3])
        self.assertEqual(animation_curves.evaluate_group(group, -1, [0]*3), [0, 2, 4])
        self.assertEqual(animation_curves.evaluate_group(group, 10, [0]*3), [8, 6, 0])
        self.assertEqual(animation_curves.evaluate_group(self.group(None, []), 1, [5]), [5])

    def test_quadratic_tangent_direction_and_interval_units(self):
        group = self.group(2, [
            {'time': 2, 'value': [0], 'forward': [99], 'backward': [2]},
            {'time': 6, 'value': [1], 'forward': [0], 'backward': [99]}])
        self.assertAlmostEqual(animation_curves.evaluate_group(group, 3, [0])[0], .4375)
        self.assertAlmostEqual(animation_curves.evaluate_group(group, 4, [0])[0], .75)
        group['keys'][0]['backward'] = [0]
        self.assertAlmostEqual(animation_curves.evaluate_group(group, 3, [0])[0], .15625)

    def test_vector_quadratic_and_invalid_curves(self):
        group = self.group(2, [
            {'time': 0, 'value': [0, 1, 2], 'forward': [0]*3, 'backward': [0]*3},
            {'time': 1, 'value': [4, 5, 6], 'forward': [0]*3, 'backward': [0]*3}])
        self.assertEqual(animation_curves.evaluate_group(group, .5, [0]*3), [2, 3, 4])
        for invalid in [self.group(3, group['keys']), self.group(1, [
            {'time': 0, 'value': [1]}, {'time': 0, 'value': [2]}]), self.group(1, [
            {'time': 0, 'value': [float('nan')]}])]:
            with self.assertRaises(nif.NifError):
                animation_curves.evaluate_group(invalid, .5, [0])
