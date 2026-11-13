"""scripts/door_skin_report.py reads the clip alias the converter gives a model (FAL-489: the Vault 111 cog door plays Stage2 as Open; the report
planned without the alias, so it could not say, for that model, why its catwalk shapes are left out). Synthetic NIFs only."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import door_skin_report as dsr  # noqa: E402
from fo4sf import door_rig, nif, pipeline  # noqa: E402
from test_door_two_panels import door_nif, two_leaves  # noqa: E402


def cog_like():
    """The door fixture with its Open sequence named Stage2 and no Close: the cog door's shape."""
    f = door_nif(two_leaves())
    f.strings[f.strings.index(b"Open")] = b"Stage2"
    f.strings[f.strings.index(b"Close")] = b"Stage9"
    return nif.parse(nif.serialize(f))


class AliasTests(unittest.TestCase):
    def test_the_converters_own_table_is_read_by_file_name_whatever_the_slashes_and_case(self):
        want = pipeline.OWN_RIG_ALIASES["vltgeardoor01.nif"]
        self.assertEqual(dsr.aliases_for("Meshes\\Interiors\\Vault\\Doors\\VltGearDoor\\VltGearDoor01.nif"), want)
        self.assertEqual(dsr.aliases_for("meshes/interiors/vault/doors/vltgeardoor/vltgeardoor01.nif"), want)
        self.assertIsNone(dsr.aliases_for("Meshes\\Interiors\\RedRocket\\Doors\\RedRPedDoor.nif"))      # a plain door needs none

    def test_a_hand_alias_wins_and_a_bad_one_is_refused(self):
        self.assertEqual(dsr.aliases_for("x.nif", "Stage2=Open"), {"Stage2": "Open"})
        self.assertEqual(dsr.aliases_for("x.nif", "A=Open, B=Close"), {"A": "Open", "B": "Close"})
        for bad in ("Stage2", "Stage2=Shut", "=Open", "Stage2=Open,Other"):
            with self.assertRaises(SystemExit):
                dsr.aliases_for("x.nif", bad)

    def test_the_alias_is_what_gives_a_renamed_sequence_its_clip_in_the_plan_the_report_reads(self):
        # the report's plan must be the one the converter makes: Stage2 is the Open clip only through the alias
        src = cog_like()
        self.assertNotIn("Open", [c["name"] for c in door_rig.plan(src, placed=True)["clips"]])
        self.assertIn("Open", [c["name"] for c in door_rig.plan(src, placed=True, aliases={"Stage2": "Open"})["clips"]])
        out = dsr.report(src, {"Stage2": "Open"})
        self.assertIn("rig_bones", out)
        self.assertEqual(out["shapes"], [])                        # the fixture has no skinned shape: nothing to list

    def test_a_plain_door_is_reported_as_before(self):
        out = dsr.report(nif.parse(nif.serialize(door_nif(two_leaves()))))
        self.assertIn("rig_bones", out)


class SpanTests(unittest.TestCase):
    def test_triangles_across_bones_are_counted_by_bone_set_and_single_bone_ones_are_not(self):
        node_of = {0: 7, 1: 7, 2: 7, 3: 9, 4: 9}
        tris = [(0, 1, 2), (0, 1, 3), (1, 2, 4), (3, 4, 3), (0, 3, 4)]
        self.assertEqual(dsr.spanning(tris, node_of), {(7, 9): 3})
        self.assertEqual(dsr.spanning([(0, 1, 2)], node_of), {})

    # hand-built plans: bones are {node, parent, bind}; a clip track is {node, samples: [{translation_source_units, quaternion_wxyz, scale}]}
    @staticmethod
    def _plan(tracks):
        ident = {"translation_source_units": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0], "scale": 1.0}
        bones = [{"node": 1, "parent": -1, "bind": ident}, {"node": 2, "parent": 0, "bind": ident}, {"node": 3, "parent": 0, "bind": ident},
                 {"node": 4, "parent": 1, "bind": ident}]          # node 4 is the child of node 2; node 3 is node 2's sibling
        return {"bones": bones, "clips": [{"name": "Open", "tracks": [
            {"node": n, "samples": [{"scale": 1.0, **s} for s in seq]} for n, seq in tracks.items()]}]}

    @staticmethod
    def _s(t=(0, 0, 0), q=(1, 0, 0, 0)):
        return {"translation_source_units": list(t), "quaternion_wxyz": list(q)}

    def test_two_panels_sliding_apart_read_as_moving_apart_not_as_still(self):
        # the Courier's counterexample: each panel travels 1 m, in opposite directions: 2 m apart, not "together"
        plan = self._plan({2: [self._s(), self._s((0, -70, 0))], 3: [self._s(), self._s((0, 70, 0))]})
        got = dsr.relative_motion(dsr.bone_poses(plan), 2, 3)
        self.assertAlmostEqual(got["translation_m"], 2.0, places=4)
        self.assertAlmostEqual(got["rotation_deg"], 0.0, places=3)

    def test_panels_sliding_together_read_as_still_to_each_other(self):
        plan = self._plan({2: [self._s(), self._s((70, 0, 0))], 3: [self._s(), self._s((70, 0, 0))]})
        got = dsr.relative_motion(dsr.bone_poses(plan), 2, 3)
        self.assertAlmostEqual(got["translation_m"], 0.0, places=4)
        self.assertAlmostEqual(got["rotation_deg"], 0.0, places=3)

    def test_a_child_that_rides_a_turning_parent_is_still_to_it_though_the_parent_turns(self):
        # node 2 turns 90 degrees about z; its child (node 4) has no track: it rides, so the pair is rigid; against the sibling (node 3) it turns 90
        c = 2 ** -0.5
        plan = self._plan({2: [self._s(), self._s(q=(c, 0, 0, c))]})
        poses = dsr.bone_poses(plan)
        rigid = dsr.relative_motion(poses, 2, 4)
        self.assertAlmostEqual(rigid["translation_m"], 0.0, places=4)
        self.assertAlmostEqual(rigid["rotation_deg"], 0.0, places=3)
        self.assertAlmostEqual(dsr.relative_motion(poses, 3, 4)["rotation_deg"], 90.0, places=2)

    def test_a_still_track_under_a_moving_parent_reads_still_to_it_but_moved_to_the_world(self):
        # the case the old per-bone travel got wrong: the child's own translation never changes while its parent slides 1 m
        plan = self._plan({2: [self._s(), self._s((70, 0, 0))], 4: [self._s((0, 35, 0)), self._s((0, 35, 0))]})
        poses = dsr.bone_poses(plan)
        self.assertAlmostEqual(dsr.relative_motion(poses, 2, 4)["translation_m"], 0.0, places=4)
        self.assertAlmostEqual(dsr.relative_motion(poses, 3, 4)["translation_m"], 1.0, places=4)

    def test_a_parents_scale_stays_in_the_metres(self):
        # the Courier's FAL-710 case: the root (node 1) has scale 2; a child (node 2) keyed 1 m along x moves 2 m in model space
        plan = self._plan({2: [self._s(), self._s((70, 0, 0))]})
        for bone in plan["bones"]:
            if bone["node"] == 1:
                bone["bind"] = {**bone["bind"], "scale": 2.0}
        poses = dsr.bone_poses(plan)
        self.assertAlmostEqual(dsr.relative_motion(poses, 3, 2)["translation_m"], 2.0, places=4)   # against a sibling that does not move
        # a pair that both ride the scaled root and do not move: still 0, the scale alone moves nothing
        still = self._plan({2: [self._s(), self._s()]})
        for bone in still["bones"]:
            if bone["node"] == 1:
                bone["bind"] = {**bone["bind"], "scale": 2.0}
        self.assertAlmostEqual(dsr.relative_motion(dsr.bone_poses(still), 3, 2)["translation_m"], 0.0, places=4)

    def test_a_bone_outside_the_plan_has_no_reading(self):
        plan = self._plan({2: [self._s(), self._s((70, 0, 0))]})
        self.assertIsNone(dsr.relative_motion(dsr.bone_poses(plan), 2, 99))

    def test_the_distance_is_the_farthest_sample_not_the_end_pose(self):
        plan = self._plan({2: [self._s(), self._s((140, 0, 0)), self._s()], 3: [self._s(), self._s(), self._s()]})
        self.assertAlmostEqual(dsr.relative_motion(dsr.bone_poses(plan), 3, 2)["translation_m"], 2.0, places=4)


if __name__ == "__main__":
    unittest.main()
