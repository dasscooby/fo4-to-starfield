"""FAL-489 variant D: an animated FO4 object that is no door (the Vault 111 console) on an activator graph: clip slots, one-frame
hold clips, .afx descriptors, and the door path's builder generalised without changing what a door gets (synthetic fixtures only;
no game data, no CALUMI library)."""
import os
import pathlib
import struct
import sys
import tempfile
import unittest
import unittest.mock
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fo4sf import anim_object, convert_static, door_motion, door_rig, fo4skin, native_door, nif, pipeline  # noqa: E402
from test_collision import fake_template  # noqa: E402
from test_door_two_panels import donor, door_nif, fake_clip_files, node_names, sliding_panels, two_leaves  # noqa: E402

STATES = {"Stage1": "StateA_Play", "Stage2": "StateB_Play"}


def console_nif():
    """The door fixture's two parts (a glass lid and a button, here two leaves) with the sequences named like the console's:
    Stage1 (the old Open) and Stage2 (the old Close)."""
    f = door_nif(two_leaves())
    f.strings[f.strings.index(b"Open")] = b"Stage1"
    f.strings[f.strings.index(b"Close")] = b"Stage2"
    return f


def fake_exporter(plan, dll, output, unit_scale, descriptors=None):
    """native_door.export without CALUMI: the rig and, per clip, the .af (track names) and the .afx the caller asked for."""
    prepared = native_door.prepare(plan, unit_scale)
    out = pathlib.Path(output)
    (out / "door.rig").write_bytes(b"rig:" + ",".join(b["name"] for b in prepared["bones"]).encode())
    allowed = set(descriptors) if descriptors is not None else {"Open", "Close"}
    for clip in prepared["clips"]:
        if clip["name"] not in allowed:
            raise ValueError("unsupported door clip name")
        (out / (clip["name"] + ".af")).write_bytes(",".join(t["name"] for t in clip["tracks"]).encode() + b"|%d" % len(
            [k for t in clip["tracks"] for k in t["keys"]]))
        (out / (clip["name"] + ".afx")).write_bytes(descriptors[clip["name"]] if descriptors is not None
                                                    else native_door.clip_descriptor(clip["name"]))
    return prepared


class StatesTests(unittest.TestCase):
    def test_the_state_map_is_read_and_bad_ones_are_refused(self):
        self.assertEqual(anim_object.parse_states("Stage1=StateA_Play, Stage2=StateB_Play"), STATES)
        self.assertEqual(anim_object.slot_names(STATES), ["StateA_Idle", "StateA_Play", "StateB_Idle", "StateB_Play"])
        for bad in ("", "Stage1", "Stage1=StateA_Idle", "Stage1=StateA_Play,Stage1=StateB_Play", "Stage1=StateA_Play,Stage2=StateA_Play", "Stage1=Open"):
            with self.assertRaises(ValueError, msg=bad):
                anim_object.parse_states(bad)


class DoorPathUnchangedTests(unittest.TestCase):
    def test_a_door_still_reports_open_and_close_and_an_unknown_slot_is_not_a_door_clip(self):
        f = door_nif(two_leaves())
        names = [s["name"] for s in door_motion.inspect(f)["sequences"]]
        self.assertEqual(sorted(names), ["Close", "Open"])
        plan = door_rig.plan(f, placed=True)
        self.assertEqual(sorted(c["name"] for c in plan["clips"]), ["Close", "Open"])
        g = console_nif()
        self.assertEqual(door_motion.inspect(g)["sequences"], [])                      # Stage1 / Stage2 are no door clips
        self.assertEqual(door_motion.inspect(g, {"Stage1": "Open"})["sequences"][0]["name"], "Open")

    def test_native_door_export_refuses_other_clip_names_without_descriptors(self):
        plan = door_rig.animated_identity_binds(door_rig.plan(console_nif(), placed=True, aliases=STATES, allowed=tuple(STATES.values())))
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(ValueError, "unsupported door clip name"):
            fake_exporter(plan, "x.dll", tmp, 0.01428)


class SlotsAndHoldsTests(unittest.TestCase):
    def plan(self):
        p = door_rig.animated_identity_binds(door_rig.plan(console_nif(), placed=True, aliases=STATES, allowed=tuple(STATES.values())))
        return anim_object.add_holds(p)

    def test_the_sequences_become_the_slots_and_no_close_is_made_up(self):
        plan = door_rig.plan(console_nif(), placed=True, aliases={"Stage1": "StateA_Play"}, allowed=("StateA_Play",))
        self.assertEqual([c["name"] for c in plan["clips"]], ["StateA_Play"])           # a door's lone Open would get a reversed Close
        plan = self.plan()
        self.assertEqual(sorted(c["name"] for c in plan["clips"]), anim_object.slot_names(STATES))

    def test_a_hold_is_the_last_pose_in_one_frame(self):
        plan = self.plan()
        play = next(c for c in plan["clips"] if c["name"] == "StateA_Play")
        hold = next(c for c in plan["clips"] if c["name"] == "StateA_Idle")
        self.assertEqual(hold["duration"], 0.0)
        self.assertEqual(hold["hold_of"], "StateA_Play")
        self.assertEqual(len(hold["tracks"]), len(play["tracks"]))
        for t, h in zip(play["tracks"], hold["tracks"]):
            self.assertEqual(len(h["samples"]), 1)
            self.assertEqual(h["samples"][0]["quaternion_wxyz"], t["samples"][-1]["quaternion_wxyz"])
            self.assertEqual(h["samples"][0]["elapsed"], 0.0)
        prepared = native_door.prepare(plan, 0.01428)                                   # the native writer takes a duration-0 clip
        self.assertEqual([len(t["keys"]) for c in prepared["clips"] if c["name"] == "StateA_Idle" for t in c["tracks"]], [1, 1])

    def test_descriptors_have_the_vanilla_shape_and_sounds_only_when_a_foley_is_named(self):
        root = ET.fromstring(anim_object.descriptor("StateA_Play", audio=[(1, "QST_Console_Flip")]))
        self.assertEqual([(c.tag, c.text) for c in root if c.tag != "audios"],
                         [("is_state", "1"), ("tag", "StateA_Play"), ("filename", "StateA_Play.af")])
        a = root.find("audios/audio")
        self.assertEqual((a.find("frame").text, a.find("foley").text), ("1", "QST_Console_Flip"))
        self.assertIsNone(ET.fromstring(anim_object.descriptor("StateA_Idle")).find("audios"))
        clip = {"events": [{"text": "SoundPlay.Flip", "elapsed": 0.0, "in_playback_range": True},
                           {"text": "Stage4", "elapsed": 0.033, "in_playback_range": True},
                           {"text": "Sound: Late", "elapsed": 0.5, "in_playback_range": True},
                           {"text": "SoundOut", "elapsed": 9.0, "in_playback_range": False}]}
        self.assertEqual(anim_object.audio_frames(clip, "QST_X"), [(1, "QST_X"), (15, "QST_X")])      # frame >= 1; text keys and out-of-range ignored
        self.assertEqual(anim_object.audio_frames(clip, None), [])
        d = anim_object.descriptors(self.plan(), "QST_X")
        self.assertEqual(sorted(d), anim_object.slot_names(STATES))
        self.assertIsNone(ET.fromstring(d["StateA_Idle"]).find("audios"))


class BuilderTests(unittest.TestCase):
    def build(self, **kw):
        f = console_nif()
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        seen = {}

        def hook(plan):
            seen["plan"] = anim_object.add_holds(plan)
            return seen["plan"]

        def clip_files(plan, scale):
            with tempfile.TemporaryDirectory() as tmp:
                prepared = fake_exporter(plan, "x.dll", tmp, scale, anim_object.descriptors(plan, kw.get("foley")))
                out = {native_door.RIG_FILE: (pathlib.Path(tmp) / "door.rig").read_bytes()}
                for c in prepared["clips"]:
                    for suffix in (".af", ".afx"):
                        out[f"{native_door.CLIP_DIR}/{c['name']}{suffix}"] = (pathlib.Path(tmp) / (c["name"] + suffix)).read_bytes()
            return out
        mats = kw.get("mats") or ["Materials\\x.mat"] * count
        result = convert_static.convert_multipart_door(
            nif.serialize(f), "fo4port/vault/console_anim", mats, clip_files, collision_template=fake_template(),
            leaf_physics_donor=donor(), aliases=STATES, drop_skinned=True, allowed=tuple(STATES.values()),
            expect_clips=anim_object.slot_names(STATES), plan_hook=hook, anim_graph=anim_object.GRAPH, motion_clip="StateA_Play")
        return result, seen["plan"]

    def test_the_object_gets_a_rig_four_clips_and_the_activator_graph(self):
        (files, anim), _ = self.build()
        base = "meshes/fo4port/vault/console_anim/"
        for slot in anim_object.slot_names(STATES):
            self.assertIn(base + f"animations/{slot}.af", files)
            self.assertIn(base + f"animations/{slot}.afx", files)
        self.assertIn(base + "characterassets/skeleton.rig", files)
        self.assertEqual(anim["anim_graph"], anim_object.GRAPH)
        self.assertEqual(anim["skeleton"], "fo4port\\vault\\console_anim\\characterassets\\skeleton.rig")
        self.assertEqual(anim["animations"], "fo4port\\vault\\console_anim\\animations")
        self.assertEqual(anim["animated_bones"], ["LeafA", "LeafB"])
        self.assertEqual(anim["moving_bodies"], 2)
        self.assertEqual(anim["sequence_aliases"], STATES)
        self.assertEqual([r["bone"] for r in anim["open_motion"]], ["LeafA", "LeafB"])    # reported for StateA_Play
        self.assertIn("meshes/fo4port/vault/console_anim.nif", files)
        self.assertEqual(set(node_names(nif.parse(files["meshes/fo4port/vault/console_anim.nif"]))) >= {"LeafA", "LeafB"}, True)
        self.assertEqual(files[base + "animations/StateA_Idle.af"], b"LeafA,LeafB|2")     # one key per track: the hold

    def test_the_manifest_says_what_became_of_every_shape_and_which_track_moves(self):
        (_, anim), plan = self.build()
        rows = anim["shapes"]
        self.assertEqual(len(rows), len([s for s in nif.fo4_trishapes(console_nif()) if s.positions and s.triangles]))
        self.assertEqual({r["fate"] for r in rows}, {"kept"})
        self.assertTrue(all(r["bones"] and r["material"] == "Materials\\x.mat" for r in rows))
        table = {c["name"]: c for c in anim_object.clip_table(plan, convert_static.UNIT_SCALE)}
        play, hold = table["StateA_Play"], table["StateA_Idle"]
        self.assertEqual(sorted(m["bone"] for m in play["motion"]), play["bones"])
        self.assertTrue(any(m["travel_m"] != [0.0, 0.0, 0.0] or m["rotation_deg"] for m in play["motion"]))   # the leaves move
        self.assertTrue(all(m["travel_m"] == [0.0, 0.0, 0.0] and m["rotation_deg"] == 0.0 for m in hold["motion"]))   # a hold stands still

    def test_travel_is_in_metres_and_matches_open_motion(self):
        (_, anim), plan = self.build()
        table = {c["name"]: c for c in anim_object.clip_table(plan, convert_static.UNIT_SCALE)}
        raw = {c["name"]: c for c in anim_object.clip_table(plan, 1.0)}
        for name in ("StateA_Play", "StateB_Play"):
            for m, r in zip(table[name]["motion"], raw[name]["motion"]):
                self.assertEqual(m["rotation_deg"], r["rotation_deg"])                               # a turn does not depend on the scale
                for x, y in zip(m["travel_m"], r["travel_m"]):
                    self.assertAlmostEqual(x, y / 70.0, places=3)                                    # metres are source units over 70
        self.assertEqual(table["StateA_Play"]["motion"], anim["open_motion"])                       # the manifest's open_motion uses the same scale
        with self.assertRaises(TypeError):
            anim_object.clip_table(plan)                                                             # no silent 1.0

    def test_two_shapes_with_one_name_get_their_own_fate(self):
        """Every shape of the sliding-door fixture is named Root. One is blended across two rig bones and dropped (drop_skinned);
        the name must not drag the kept panel and the frame into the 'dropped' label (FAL-512)."""
        from test_sliding_by_motion import SkinnedPanelTests
        f = door_nif(sliding_panels())
        names = node_names(f)
        _, shapes, read_skin = SkinnedPanelTests().skinned(f, names["PanelA"], second=names["PanelB"])
        with unittest.mock.patch.object(nif, "fo4_trishapes", side_effect=shapes), \
                unittest.mock.patch.object(fo4skin, "read_skin", side_effect=read_skin):
            count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
            _, door = convert_static.convert_multipart_door(
                nif.serialize(f), "fo4port/ped", ["x.mat"] * count, fake_clip_files, collision_template=fake_template(),
                leaf_physics_donor=donor(), drop_skinned=True, plan_hook=lambda plan: plan)
        rows = door["shapes"]
        self.assertEqual({r["shape"] for r in rows}, {"Root"})                                       # one name for all
        dropped = [r for r in rows if r["fate"].startswith("dropped")]
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["bones"], [])
        self.assertEqual(door["dropped_skinned_shapes"], ["Root"])
        kept = [r for r in rows if r["fate"] == "kept"]
        self.assertEqual(len(kept), len(rows) - 1)
        self.assertTrue(all(r["bones"] for r in kept))                                               # the others keep their bones

    def test_the_rig_tracks_and_model_nodes_agree_on_every_bone_index(self):
        """Rig bone order, the track index a clip files its block under, and the model's node order all come from plan['bones']:
        a swap between them (the lid's turn landing on the button) must be impossible on a fixture, and is what `inspect` checks
        on the real stage."""
        (files, anim), plan = self.build()
        anim = {**anim, "clips": anim_object.clip_table(plan, convert_static.UNIT_SCALE)}
        rig = anim["rig"]
        self.assertEqual([r["name"] for r in rig], [b["name"] for b in plan["bones"]])
        model = nif.parse(files["meshes/fo4port/vault/console_anim.nif"])
        order = [model.strings[struct.unpack_from("<i", model.blocks[i])[0]].decode() for i in range(len(model.blocks)) if model.type_of(i) == "NiNode"]
        self.assertEqual([n for n in order if n in {r["name"] for r in rig}], [r["name"] for r in rig])
        for c in anim["clips"]:
            for t in c["tracks"]:
                self.assertEqual(rig[t["bone_index"]]["name"], t["bone"])
        att = {x["key"]: x for x in anim["attachments"]}
        self.assertEqual({x["bone"] for x in att.values()}, {"Root", "LeafA", "LeafB"})
        for x in att.values():
            self.assertEqual(rig[x["bone_index"]]["name"], x["bone"])

    def test_predicted_end_boxes_move_only_the_shapes_on_animated_bones(self):
        (_, anim), _ = self.build()
        rest, ends = anim["pose_boxes_m"]["rest"], anim["pose_boxes_m"]["end_of_clip"]
        att = {x["key"]: x["bone"] for x in anim["attachments"]}
        play = ends["StateA_Play"]
        for k, box in play.items():
            if att[k] == "Root":
                self.assertEqual(box, rest[k])                       # a static shape never moves
            else:
                self.assertNotEqual(box, rest[k])                    # the leaves swing in the fixture's first clip
        self.assertEqual(ends["StateA_Idle"], ends["StateA_Play"])   # the hold stays where the clip ended

    def test_a_shape_without_a_material_is_reported_as_left_out(self):
        f = console_nif()
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        mats = ["Materials\\x.mat"] * count
        mats[0] = None                                           # the glass, say: an effect shader with no material
        (_, anim), _ = self.build(mats=mats)
        self.assertTrue(anim["shapes"][0]["fate"].startswith("left out"))
        self.assertEqual(anim["shapes"][0]["bones"], [])
        self.assertEqual({r["fate"] for r in anim["shapes"][1:]}, {"kept"})

    def test_a_door_manifest_has_no_shapes_entry(self):
        f = door_nif(two_leaves())
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])

        def clip_files(plan, scale):
            with tempfile.TemporaryDirectory() as tmp:
                prepared = fake_exporter(plan, "x.dll", tmp, scale)
                out = {native_door.RIG_FILE: (pathlib.Path(tmp) / "door.rig").read_bytes()}
                for c in prepared["clips"]:
                    out[f"{native_door.CLIP_DIR}/{c['name']}.af"] = b"af"
            return out
        _, door = convert_static.convert_multipart_door(nif.serialize(f), "fo4port/d", ["a.mat"] * count, clip_files,
                                                        collision_template=fake_template(), leaf_physics_donor=donor())
        self.assertNotIn("shapes", door)                           # the door manifest is what it was

    def test_the_afx_files_name_their_own_slot_and_hold_the_sound_only_on_a_play_slot(self):
        (files, _), _ = self.build(foley=None)
        base = "meshes/fo4port/vault/console_anim/animations/"
        for slot in anim_object.slot_names(STATES):
            root = ET.fromstring(files[base + slot + ".afx"])
            self.assertEqual((root.find("tag").text, root.find("filename").text, root.find("is_state").text), (slot, slot + ".af", "1"))
            self.assertIsNone(root.find("audios"))

    def test_the_exact_clip_set_is_enforced(self):
        f = console_nif()
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        with self.assertRaisesRegex(nif.NifError, "needs exactly the clips"):
            convert_static.convert_multipart_door(nif.serialize(f), "fo4port/d", ["a.mat"] * count, lambda p, s: {}, collision_template=fake_template(),
                                                  leaf_physics_donor=donor(), aliases=STATES, allowed=tuple(STATES.values()),
                                                  expect_clips=["StateA_Play"])


class ConverterTests(unittest.TestCase):
    def converter(self, staging):
        conv = pipeline.Converter.__new__(pipeline.Converter)
        f = console_nif()
        raw = nif.serialize(f)
        conv.src = type("S", (), {"mesh": staticmethod(lambda name: raw)})()
        conv.staging, conv.prefix, conv.door_anim_dll = staging, "fo4port", "CALUMI.dll"
        conv.door_physics_donor, conv.collision_template = donor(), fake_template()
        conv.stats = {"assets": 0, "failed": 0}
        conv._shape_material = lambda src, s: "Materials\\x.mat"
        return conv

    def test_convert_anim_object_writes_the_model_the_rig_and_the_clips_into_the_staging(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(native_door, "export", fake_exporter):
            res = self.converter(tmp).convert_anim_object("Meshes\\Interiors\\Vault\\Console01.nif", STATES, foley="QST_Flip")
            self.assertTrue(res["ok"], res.get("reason"))
            self.assertEqual(res["out_name"], "fo4port/interiors/vault/console01_anim")
            anim = res["anim"]
            self.assertEqual(anim["states"], STATES)
            self.assertEqual(anim["foley"], "QST_Flip")
            self.assertEqual([c["name"] for c in anim["clips"]], ["StateA_Play", "StateB_Play", "StateA_Idle", "StateB_Idle"])
            self.assertEqual([c["frames"] for c in anim["clips"]][2:], [0, 0])
            for rel in ("meshes/fo4port/interiors/vault/console01_anim.nif",
                        "meshes/fo4port/interiors/vault/console01_anim/characterassets/skeleton.rig",
                        "meshes/fo4port/interiors/vault/console01_anim/animations/StateB_Idle.afx"):
                self.assertTrue(os.path.isfile(os.path.join(tmp, *rel.split("/"))), rel)

    def test_without_the_library_or_the_donor_it_says_so_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            conv = self.converter(tmp)
            conv.door_anim_dll = None
            res = conv.convert_anim_object("Meshes\\x.nif", STATES)
            self.assertFalse(res["ok"])
            self.assertIn("needs door_anim_dll", res["reason"])
            self.assertEqual(os.listdir(tmp), [])


if __name__ == "__main__":
    unittest.main()
