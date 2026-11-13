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


def _sample(t, q, e=0.0):
    return {"elapsed": e, "translation_source_units": list(t), "quaternion_wxyz": list(q), "scale": 1.0}


class ToggleIdlesTests(unittest.TestCase):
    """FAL-489 session 7: StateA_Idle = first frame of slot A's clip, StateB_Idle = its last frame, slot B starts from there."""
    def plan(self):
        p = door_rig.animated_identity_binds(door_rig.plan(console_nif(), placed=True, aliases=STATES, allowed=tuple(STATES.values())))
        return anim_object.add_toggle_idles(anim_object.fill_static_tracks(p))

    def test_the_two_idles_are_the_first_and_the_last_pose_of_slot_a(self):
        plan = self.plan()
        by = {c["name"]: c for c in plan["clips"]}
        self.assertEqual(sorted(by), anim_object.slot_names(STATES, "toggle"))
        a = by["StateA_Play"]
        for name, which, label in (("StateA_Idle", 0, "first"), ("StateB_Idle", -1, "last")):
            hold = by[name]
            self.assertEqual((hold["hold_of"], hold["hold_frame"], hold["duration"]), ("StateA_Play", label, 0.0))
            self.assertEqual([t["name"] for t in hold["tracks"]], [t["name"] for t in a["tracks"]])      # one track per rig bone, same order
            for t, h in zip(a["tracks"], hold["tracks"]):
                self.assertEqual(len(h["samples"]), 1)
                self.assertEqual(h["samples"][0]["quaternion_wxyz"], t["samples"][which]["quaternion_wxyz"])
                self.assertEqual(h["samples"][0]["translation_source_units"], t["samples"][which]["translation_source_units"])
                self.assertEqual(h["samples"][0]["elapsed"], 0.0)
        shut = [t for t in by["StateA_Idle"]["tracks"] if t["name"] == "LeafA"][0]["samples"][0]["quaternion_wxyz"]
        opened = [t for t in by["StateB_Idle"]["tracks"] if t["name"] == "LeafA"][0]["samples"][0]["quaternion_wxyz"]
        self.assertNotEqual(shut, opened)                                                              # a moving leaf is at its start in one and its end in the other

    def test_slot_b_starts_from_the_open_pose_for_every_bone_it_leaves_standing(self):
        """The fixture is a two-leaf door shape: both leaves move in both clips (so slot B's own data already starts at slot A's end), and the
        root is a static filler in both (so it is held at slot A's last pose, the bind). The synthetic test below has a bone only A moves."""
        plan = self.plan()
        by = {c["name"]: c for c in plan["clips"]}
        a_last = {t["name"]: t["samples"][-1] for t in by["StateA_Play"]["tracks"]}
        b = by["StateB_Play"]
        self.assertEqual(b["starts_from"], "StateB_Idle")
        self.assertEqual(b["held_at_idle_pose"], ["Root"])
        original = door_rig.animated_identity_binds(door_rig.plan(console_nif(), placed=True, aliases=STATES, allowed=tuple(STATES.values())))
        original_b = next(c for c in anim_object.fill_static_tracks(original)["clips"] if c["name"] == "StateB_Play")
        for t, o in zip(b["tracks"], original_b["tracks"]):
            if t["name"] not in b["held_at_idle_pose"]:
                self.assertEqual(t, o)                                                                  # what slot B moves is untouched
        idle = {t["name"]: t["samples"][0] for t in by["StateB_Idle"]["tracks"]}
        for t in b["tracks"]:
            self.assertEqual(t["samples"][0]["quaternion_wxyz"], idle[t["name"]]["quaternion_wxyz"])    # B starts at B_Idle's pose, bone by bone
            self.assertEqual(idle[t["name"]]["quaternion_wxyz"], a_last[t["name"]]["quaternion_wxyz"])

    def test_the_native_writer_takes_the_toggle_clips_and_the_table_says_what_they_are(self):
        plan = self.plan()
        prepared = native_door.prepare(plan, 0.01428)
        for name in ("StateA_Idle", "StateB_Idle"):
            self.assertEqual({len(t["keys"]) for c in prepared["clips"] if c["name"] == name for t in c["tracks"]}, {1})
        table = {r["name"]: r for r in anim_object.clip_table(plan, convert_static.UNIT_SCALE)}
        self.assertEqual((table["StateA_Idle"]["hold_frame"], table["StateB_Idle"]["hold_frame"]), ("first", "last"))
        self.assertEqual(table["StateB_Play"]["starts_from"], "StateB_Idle")
        self.assertIsNone(table["StateA_Play"]["starts_from"])

    def test_a_lone_slot_is_the_source_of_both_idles_and_a_bad_mode_is_refused(self):
        self.assertEqual(anim_object.slot_names({"Stage1": "StateA_Play"}, "toggle"), ["StateA_Idle", "StateA_Play", "StateB_Idle"])
        self.assertEqual(anim_object.slot_names({"Stage1": "StateA_Play"}), ["StateA_Idle", "StateA_Play"])          # the hold rule is unchanged
        with self.assertRaisesRegex(ValueError, "not one of"):
            anim_object.slot_names(STATES, "latch")
        p = door_rig.animated_identity_binds(door_rig.plan(console_nif(), placed=True, aliases={"Stage1": "StateA_Play"}, allowed=("StateA_Play",)))
        names = sorted(c["name"] for c in anim_object.add_toggle_idles(anim_object.fill_static_tracks(p))["clips"])
        self.assertEqual(names, ["StateA_Idle", "StateA_Play", "StateB_Idle"])

    def test_a_static_filler_for_a_bone_slot_a_moves_becomes_a_real_track_at_the_open_pose(self):
        ident, turned = (1.0, 0.0, 0.0, 0.0), (0.7, 0.7, 0.0, 0.0)
        def clip(name, lid, btn):
            return {"name": name, "duration": 1.0, "events": [], "tracks": [
                {"node": 1, "name": "Lid", "samples": lid, **({"static": True} if all(tuple(x["quaternion_wxyz"]) == ident for x in lid) else {})},
                {"node": 2, "name": "Button", "samples": btn}]}
        a = clip("StateA_Play", [_sample((0, 0, 0), ident), _sample((0, 0, 0), turned, 1.0)], [_sample((0, 0, 0), ident), _sample((0, 0, 0), ident, 1.0)])
        a["tracks"][1]["static"] = True
        b = clip("StateB_Play", [_sample((0, 0, 0), ident), _sample((0, 0, 0), ident, 0.6)], [_sample((0, 0, 0), ident), _sample((0, 0, -1), ident, 0.6)])
        self.assertTrue(b["tracks"][0].get("static"))
        out = anim_object.add_toggle_idles({"bones": [], "attachments": [], "clips": [a, b]})
        nb = next(c for c in out["clips"] if c["name"] == "StateB_Play")
        lid = nb["tracks"][0]
        self.assertNotIn("static", lid)                                                                  # it is no longer identity
        self.assertEqual([s["quaternion_wxyz"] for s in lid["samples"]], [list(turned)] * 2)
        self.assertEqual([s["elapsed"] for s in lid["samples"]], [0.0, 0.6])
        self.assertEqual(nb["tracks"][1], b["tracks"][1])                                                # what B moves is untouched
        self.assertEqual(nb["held_at_idle_pose"], ["Lid"])
        self.assertTrue(anim_object._same_pose(_sample((0, 0, 0), (0.5, 0.5, 0.5, 0.5)), _sample((0, 0, 0), (-0.5, -0.5, -0.5, -0.5))))


class SwapSiblingsTests(unittest.TestCase):
    """FAL-489 session 6: --swap-siblings exchanges the root's two children (Lid, Button) and nothing else."""
    def base(self):
        return door_rig.animated_identity_binds(door_rig.plan(console_nif(), placed=True, aliases=STATES, allowed=tuple(STATES.values())))

    def test_the_two_siblings_trade_places_and_every_index_follows(self):
        plan = self.base()
        names = [b["name"] for b in plan["bones"]]
        self.assertEqual(len(names), 3)
        swapped = anim_object.swap_siblings(plan)
        self.assertEqual([b["name"] for b in swapped["bones"]], [names[0], names[2], names[1]])
        self.assertEqual([b["parent"] for b in swapped["bones"]], [-1, 0, 0])
        for a_old, a_new in zip(plan["attachments"], swapped["attachments"]):          # an attachment keeps its bone BY NAME
            self.assertEqual(plan["bones"][a_old["bone"]]["name"], swapped["bones"][a_new["bone"]]["name"])
        by = {b["name"]: b for b in plan["bones"]}
        for b in swapped["bones"]:                                                      # binds and nodes are untouched
            self.assertEqual(b["bind"], by[b["name"]]["bind"])
            self.assertEqual(b["node"], by[b["name"]]["node"])
        self.assertEqual(anim_object.swap_siblings(swapped)["bones"], plan["bones"])    # twice is the original

    def test_tracks_follow_the_new_order_and_the_clip_table_says_the_new_index(self):
        plan = anim_object.add_holds(anim_object.fill_static_tracks(anim_object.swap_siblings(self.base())))
        order = [b["name"] for b in plan["bones"]]
        for clip in plan["clips"]:
            self.assertEqual([t["name"] for t in clip["tracks"]], order)
        table = anim_object.clip_table(plan, convert_static.UNIT_SCALE)
        play = [c for c in table if c["name"] == "StateA_Play"][0]
        moved = [t for t in play["tracks"] if not t.get("static")]
        self.assertEqual([t["bone_index"] for t in moved], [order.index(t["bone"]) for t in moved])

    def test_a_built_kit_writes_the_rig_and_the_manifest_in_the_swapped_order(self):
        (built0, anim0), _ = BuilderTests().build()
        (built1, anim1), plan1 = BuilderTests().build(swap=True)
        n0 = [r["name"] for r in anim0["rig"]]
        n1 = [r["name"] for r in anim1["rig"]]
        self.assertEqual(n1, [n0[0], n0[2], n0[1]])
        rig = lambda built: [v for k, v in built.items() if k.endswith("skeleton.rig")][0]      # noqa: E731
        self.assertNotEqual(rig(built0), rig(built1))                                           # the rig file bytes differ
        self.assertEqual([r["parent"] for r in anim1["rig"]], [-1, 0, 0])

    def test_refuses_a_rig_without_exactly_one_pair(self):
        plan = self.base()
        flat = {**plan, "bones": plan["bones"][:2]}
        with self.assertRaisesRegex(ValueError, "exactly one parent with exactly two children"):
            anim_object.swap_siblings(flat)


IDENT, TURNED, DOWN = (1.0, 0.0, 0.0, 0.0), (0.7, 0.7, 0.0, 0.0), (0.0, 0.0, -1.0)


def _chain_clip(name, dur, lid, btn, lid_static=False, btn_static=False):
    """A console-shaped clip: Root (always standing), Lid, Button; a track is flagged static only when its source says so."""
    def trk(node, nm, samples, static=False):
        return {"node": node, "name": nm, "samples": samples, **({"static": True} if static else {})}
    return {"name": name, "duration": dur, "events": [], "tracks": [
        trk(0, "Root", [_sample((0, 0, 0), IDENT), _sample((0, 0, 0), IDENT, dur)], True), trk(1, "Lid", lid, lid_static), trk(2, "Button", btn, btn_static)]}


def _lid(q0, q1, dur):
    return [_sample((0, 0, 0), q0), _sample((0, 0, 0), q1, dur)]


def _btn(z1, dur):
    return [_sample((0, 0, 0), IDENT), _sample((0, 0, z1), IDENT, dur)]


def console_chain(third_moves_lid=False):
    """Stage2 (the lid turns, 1.6 s), Stage3 (the button goes down, 0.6 s), Stage4 (0.033 s; it moves nothing, or turns the lid back)."""
    a = _chain_clip("StateA_Play", 1.6, _lid(IDENT, TURNED, 1.6), _btn(0, 1.6), btn_static=True)
    b = _chain_clip("StateB_Play", 0.6, _lid(IDENT, IDENT, 0.6), _btn(-1.0, 0.6), lid_static=True)
    c = _chain_clip("StateC_Play", 0.033, _lid(TURNED, IDENT, 0.033) if third_moves_lid else _lid(IDENT, IDENT, 0.033), _btn(0, 0.033), lid_static=not third_moves_lid, btn_static=True)
    return {"bones": [], "attachments": [], "clips": [a, b, c]}


def _pose(clip):
    """{bone: (first quaternion w, last translation z)} of a one-frame or longer clip's last sample."""
    return {t["name"]: (t["samples"][-1]["quaternion_wxyz"][0], t["samples"][-1]["translation_source_units"][2]) for t in clip["tracks"]}


class ChainIdlesTests(unittest.TestCase):
    """FAL-489, the converted console on genericstategraph01: four Idle slots hold four successive poses and the Play clips chain."""
    def test_the_chain_is_the_mapped_play_slots_in_slot_order_and_may_leave_one_out(self):
        full = anim_object.parse_states("Stage2=StateA_Play,Stage3=StateB_Play,Stage4=StateC_Play", anim_object.PLAY_SLOTS4)
        self.assertEqual(anim_object.chain_slots(full), ["StateA_Play", "StateB_Play", "StateC_Play"])
        everything = [f"State{x}_Idle" for x in "ABCD"] + [f"State{x}_Play" for x in "ABCD"]
        for states in ({"S2": "StateA_Play"}, {"S2": "StateA_Play", "S3": "StateB_Play"}, full,
                       {"S1": "StateA_Play", "S2": "StateB_Play", "S3": "StateC_Play", "S4": "StateD_Play"}):
            self.assertEqual(anim_object.slot_names(states, "chain"), sorted(everything))                 # always all eight, whatever is mapped
        for gap in ({"S": "StateB_Play"}, {"S": "StateA_Play", "T": "StateC_Play"}, {"S": "StateD_Play"}, {"T": "StateC_Play", "S": "StateA_Play"}):
            self.assertEqual(anim_object.slot_names(gap, "chain"), sorted(everything))
        self.assertEqual(anim_object.chain_slots({"T": "StateC_Play", "S": "StateA_Play"}), ["StateA_Play", "StateC_Play"])    # slot order, not map order
        with self.assertRaisesRegex(ValueError, "at least one"):
            anim_object.chain_slots({})
        with self.assertRaises(ValueError):
            anim_object.slot_names({}, "chain")
        with self.assertRaises(ValueError):                                                                # the two-slot parser still refuses C and D
            anim_object.parse_states("Stage4=StateC_Play")
        with self.assertRaises(ValueError):
            anim_object.parse_states("Stage4=StateC_Idle", anim_object.PLAY_SLOTS4)

    def test_the_four_idles_are_four_successive_poses(self):
        plan = anim_object.add_chain_idles(console_chain())
        by = {c["name"]: c for c in plan["clips"]}
        self.assertEqual(sorted(by), sorted(anim_object.slot_names({"a": "StateA_Play", "b": "StateB_Play", "c": "StateC_Play"}, "chain")))
        self.assertEqual(_pose(by["StateA_Idle"]), {"Root": (1.0, 0), "Lid": (1.0, 0), "Button": (1.0, 0)})              # rest: lid shut, button up
        self.assertEqual(_pose(by["StateB_Idle"]), {"Root": (1.0, 0), "Lid": (0.7, 0), "Button": (1.0, 0)})              # the lid turned, button still up
        self.assertEqual(_pose(by["StateC_Idle"]), {"Root": (1.0, 0), "Lid": (0.7, 0), "Button": (1.0, -1.0)})           # and the button down
        self.assertEqual(_pose(by["StateD_Idle"]), _pose(by["StateC_Idle"]))                                             # Stage4 moves nothing here
        for name, source, label in (("StateA_Idle", "StateA_Play", "first"), ("StateB_Idle", "StateA_Play", "last"),
                                    ("StateC_Idle", "StateB_Play", "last"), ("StateD_Idle", "StateC_Play", "last")):
            c = by[name]
            self.assertEqual((c["hold_of"], c["hold_frame"], c["duration"], c["events"]), (source, label, 0.0, []))
            self.assertEqual([len(t["samples"]) for t in c["tracks"]], [1, 1, 1])                                        # one frame, one track per bone
            self.assertEqual([t["name"] for t in c["tracks"]], ["Root", "Lid", "Button"])                                # in rig order

    def test_a_third_clip_that_moves_something_gives_the_fourth_idle_its_own_pose(self):
        by = {c["name"]: c for c in anim_object.add_chain_idles(console_chain(third_moves_lid=True))["clips"]}
        self.assertEqual(_pose(by["StateC_Idle"])["Lid"], (0.7, 0))
        self.assertEqual(_pose(by["StateD_Idle"])["Lid"], (1.0, 0))                                                      # the lid turned back
        self.assertEqual(_pose(by["StateD_Idle"])["Button"], (1.0, -1.0))                                                # the button stays down
        self.assertNotEqual(_pose(by["StateD_Idle"]), _pose(by["StateC_Idle"]))

    def test_each_clip_starts_from_the_pose_the_one_before_it_ended_in(self):
        by = {c["name"]: c for c in anim_object.add_chain_idles(console_chain())["clips"]}
        self.assertNotIn("starts_from", by["StateA_Play"])
        b, c = by["StateB_Play"], by["StateC_Play"]
        self.assertEqual((b["starts_from"], b["held_at_idle_pose"]), ("StateB_Idle", ["Root", "Lid"]))                   # B moves the button only
        self.assertEqual((c["starts_from"], c["held_at_idle_pose"]), ("StateC_Idle", ["Root", "Lid", "Button"]))        # C moves nothing: held at C_Idle
        lid_b = [t for t in b["tracks"] if t["name"] == "Lid"][0]
        self.assertEqual([s["quaternion_wxyz"] for s in lid_b["samples"]], [list(TURNED)] * 2)                           # held at where A left it
        self.assertNotIn("static", lid_b)                                                                                # no longer identity
        self.assertEqual([t for t in b["tracks"] if t["name"] == "Button"][0]["samples"][-1]["translation_source_units"][2], -1.0)   # B's own motion untouched
        btn_c = [t for t in c["tracks"] if t["name"] == "Button"][0]
        self.assertEqual(btn_c["samples"][0]["translation_source_units"][2], -1.0)                                       # C holds the button down (not at rest)
        root_c = [t for t in c["tracks"] if t["name"] == "Root"][0]
        self.assertTrue(root_c.get("static"))                                                                            # a bone that never moved stays identity

    def test_a_play_slot_nobody_mapped_is_a_spare_hold_of_the_last_pose(self):
        three = {c["name"]: c for c in anim_object.add_chain_idles(console_chain())["clips"]}
        d = three["StateD_Play"]
        self.assertTrue(d["spare"])
        self.assertEqual((d["hold_of"], d["hold_frame"], d["events"]), ("StateC_Play", "last", []))
        self.assertAlmostEqual(d["duration"], 1.0 / anim_object.FPS)
        self.assertEqual([len(t["samples"]) for t in d["tracks"]], [2, 2, 2])
        self.assertEqual(_pose(d), _pose(three["StateD_Idle"]))                                                          # holds the end pose, moves nothing
        for t in d["tracks"]:
            self.assertEqual(t["samples"][0]["quaternion_wxyz"], t["samples"][1]["quaternion_wxyz"])
        two = dict(console_chain())
        two["clips"] = two["clips"][:2]
        by2 = {c["name"]: c for c in anim_object.add_chain_idles(two)["clips"]}                                          # a chain of two: C and D hold the second pose, both plays spare
        self.assertTrue(by2["StateC_Play"]["spare"] and by2["StateD_Play"]["spare"])
        self.assertEqual(_pose(by2["StateC_Idle"]), _pose(by2["StateD_Idle"]))
        self.assertEqual(_pose(by2["StateD_Idle"])["Lid"], (0.7, 0))
        self.assertEqual(_pose(by2["StateD_Idle"])["Button"], (1.0, -1.0))
        self.assertNotIn("spare", three["StateC_Play"])                                                                  # a mapped clip is not spare

    def test_four_mapped_clips_make_no_spare_and_the_fourth_idle_is_the_pose_after_the_third(self):
        plan = console_chain()
        plan["clips"].append(_chain_clip("StateD_Play", 0.5, _lid(IDENT, IDENT, 0.5), _btn(0, 0.5), lid_static=True, btn_static=True))
        by = {c["name"]: c for c in anim_object.add_chain_idles(plan)["clips"]}
        self.assertEqual(len(by), 8)
        self.assertNotIn("spare", by["StateD_Play"])
        self.assertEqual(by["StateD_Play"]["starts_from"], "StateD_Idle")
        self.assertEqual(by["StateD_Idle"]["hold_of"], "StateC_Play")                                                    # the pose after the fourth clip has no idle slot

    def test_a_chain_that_leaves_slot_b_out_follows_the_graphs_own_wiring(self):
        """Stage2 on StateA_Play and Stage3 on StateC_Play: the control showed StateB_Play returns to the rest pose and StateC_Play to StateC_Idle."""
        plan = console_chain()
        a, b = plan["clips"][0], plan["clips"][1]
        c = {**b, "name": "StateC_Play"}                                                                                  # the button clip, on slot C
        by = {x["name"]: x for x in anim_object.add_chain_idles({**plan, "clips": [a, c]})["clips"]}
        self.assertEqual(sorted(by), sorted(anim_object.slot_names({"s": "StateA_Play", "t": "StateC_Play"}, "chain")))
        self.assertEqual(_pose(by["StateB_Idle"])["Lid"], (0.7, 0))                                                      # the pose after the first clip: the lid open
        self.assertEqual(_pose(by["StateC_Idle"])["Button"], (1.0, -1.0))                                                # the pose after the second: the button down
        self.assertEqual(_pose(by["StateC_Idle"])["Lid"], (0.7, 0))
        self.assertEqual(by["StateC_Play"]["starts_from"], "StateB_Idle")                                                # its POSITION in the chain (second), not its slot
        self.assertEqual(by["StateC_Play"]["held_at_idle_pose"], ["Root", "Lid"])
        self.assertTrue(by["StateB_Play"]["spare"] and by["StateD_Play"]["spare"])
        self.assertEqual(_pose(by["StateD_Idle"]), _pose(by["StateC_Idle"]))
        self.assertEqual(anim_object.add_chain_idles({"bones": [], "attachments": [], "clips": []}), {"bones": [], "attachments": [], "clips": []})

    def test_the_other_idle_modes_are_unchanged(self):
        self.assertEqual(anim_object.slot_names(STATES, "toggle"), ["StateA_Idle", "StateA_Play", "StateB_Idle", "StateB_Play"])
        self.assertEqual(anim_object.slot_names(STATES, "hold"), ["StateA_Idle", "StateA_Play", "StateB_Idle", "StateB_Play"])
        self.assertEqual(anim_object.GRAPH, "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx")
        self.assertEqual(anim_object.GRAPH_GENERIC, "AnimTextData\\Tables\\Graphs\\GenericStateGraph01.agx")

    def test_descriptors_name_their_slot_and_a_spare_play_slot_carries_no_sound(self):
        plan = anim_object.add_chain_idles(console_chain())
        plan["clips"][0]["events"] = [{"text": "SoundPlay.Flip", "elapsed": 0.0, "in_playback_range": True}]
        plan["clips"][-1]["events"] = [{"text": "SoundPlay.Flip", "elapsed": 0.0, "in_playback_range": True}]          # even if a spare clip had one
        d = anim_object.descriptors(plan, "QST_X")
        self.assertEqual(sorted(d), sorted(c["name"] for c in plan["clips"]))
        self.assertEqual(len(d), 8)
        for name, raw in d.items():
            root = ET.fromstring(raw)
            self.assertEqual((root.findtext("tag"), root.findtext("filename")), (name, name + ".af"))
        self.assertIsNotNone(ET.fromstring(d["StateA_Play"]).find("audios"))                                              # a mapped play slot keeps its sound
        self.assertIsNone(ET.fromstring(d["StateD_Play"]).find("audios"))                                                 # the spare does not
        self.assertIsNone(ET.fromstring(d["StateC_Idle"]).find("audios"))


class SlowTests(unittest.TestCase):
    """FAL-489, PC session 12 Nov 23:57 UTC: the button clip (0.6 s) could not be caught by a shot 1.2 s after the call: run a clip slower by a whole factor."""
    def test_parse_slow_maps_the_fo4_sequence_to_its_slot_and_refuses_the_rest(self):
        states = anim_object.parse_states("Stage2=StateA_Play,Stage3=StateC_Play", anim_object.PLAY_SLOTS4)
        self.assertEqual(anim_object.parse_slow("Stage3=4", states), {"StateC_Play": 4})
        self.assertEqual(anim_object.parse_slow("Stage2=2, Stage3=8", states), {"StateA_Play": 2, "StateC_Play": 8})
        self.assertEqual(anim_object.parse_slow("", states), {})
        for bad in ("Stage4=4", "Stage3=1", "Stage3=9", "Stage3=2.5", "Stage3=x", "Stage3", "=4"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                anim_object.parse_slow(bad, states)

    def test_stretch_multiplies_every_time_and_nothing_else(self):
        plan = console_chain()
        plan["clips"][1]["events"] = [{"text": "SoundPlay.Click", "elapsed": 0.3, "in_playback_range": True}]
        out = anim_object.stretch_clips(plan, {"StateB_Play": 4})
        before, after = plan["clips"][1], out["clips"][1]
        self.assertAlmostEqual(after["duration"], before["duration"] * 4)
        self.assertEqual(after["slowed"], 4)
        self.assertAlmostEqual(after["events"][0]["elapsed"], 1.2)
        self.assertEqual(after["events"][0]["text"], "SoundPlay.Click")
        for tb, ta in zip(before["tracks"], after["tracks"]):
            self.assertEqual(len(tb["samples"]), len(ta["samples"]))
            for sb, sa in zip(tb["samples"], ta["samples"]):
                self.assertAlmostEqual(sa["elapsed"], sb["elapsed"] * 4)
                self.assertEqual({k: v for k, v in sa.items() if k != "elapsed"}, {k: v for k, v in sb.items() if k != "elapsed"})     # the same pose
        self.assertIs(out["clips"][0], plan["clips"][0])                                                  # another clip is the same object
        self.assertNotIn("slowed", plan["clips"][1])                                                      # the input is not changed
        self.assertAlmostEqual(plan["clips"][1]["duration"], 0.6)

    def test_stretch_keeps_frames_on_the_grid_and_the_chain_idles_follow_the_stretched_clip(self):
        out = anim_object.stretch_clips(console_chain(), {"StateB_Play": 3})
        for s in out["clips"][1]["tracks"][2]["samples"]:
            self.assertAlmostEqual(s["elapsed"] * anim_object.FPS, round(s["elapsed"] * anim_object.FPS), places=6)
        chained = anim_object.add_chain_idles(out)
        by = {c["name"]: c for c in chained["clips"]}
        self.assertAlmostEqual(by["StateB_Play"]["duration"], 1.8)
        self.assertEqual(by["StateC_Idle"]["duration"], 0.0)
        plain = {c["name"]: c for c in anim_object.add_chain_idles(console_chain())["clips"]}
        self.assertEqual(_pose(by["StateC_Idle"]), _pose(plain["StateC_Idle"]))                            # the same held pose, slow or not

    def test_stretch_refuses_a_missing_clip_and_a_bad_factor_and_does_nothing_for_none(self):
        plan = console_chain()
        self.assertEqual(anim_object.stretch_clips(plan, {})["clips"], plan["clips"])
        self.assertEqual(anim_object.stretch_clips(plan, None)["clips"], plan["clips"])
        self.assertEqual(anim_object.stretch_clips(plan, {"StateB_Play": 1})["clips"], plan["clips"])
        with self.assertRaisesRegex(ValueError, "does not hold"):
            anim_object.stretch_clips(plan, {"StateD_Play": 2})
        for bad in (0, 2.5, -1, "2"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                anim_object.stretch_clips(plan, {"StateB_Play": bad})


class BuilderTests(unittest.TestCase):
    def build(self, **kw):
        f = console_nif()
        count = len([s for s in nif.fo4_trishapes(f) if s.positions and s.triangles])
        seen = {}

        def hook(plan):
            if kw.get("swap"):
                plan = anim_object.swap_siblings(plan)
            plan = anim_object.fill_static_tracks(plan)
            seen["plan"] = anim_object.add_toggle_idles(plan) if kw.get("idles") == "toggle" else anim_object.add_holds(plan)
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
        self.assertEqual(files[base + "animations/StateA_Idle.af"], b"Root,LeafA,LeafB|3")     # one block per rig bone, in rig order, one key each: the hold

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

    def test_every_clip_has_one_block_per_rig_bone_in_rig_order_and_the_static_ones_move_nothing(self):
        """PC dump (12 Nov): the .af files had 2 blocks for a 3-bone rig, so a block's position differed from its bone's rig index."""
        (files, anim), plan = self.build()
        rig = [r["name"] for r in anim["rig"]]
        for c in plan["clips"]:
            self.assertEqual([t["name"] for t in c["tracks"]], rig, c["name"])              # one track per bone, rig order
        statics = {(c["name"], t["name"]) for c in plan["clips"] for t in c["tracks"] if t.get("static")}
        self.assertEqual(statics, {(c["name"], "Root") for c in plan["clips"]})            # only the unanimated root is static
        prepared = native_door.prepare(plan, convert_static.UNIT_SCALE)
        for c in prepared["clips"]:
            self.assertEqual([t["bone"] for t in c["tracks"]], [0, 1, 2], c["name"])         # block i is rig bone i
            root = c["tracks"][0]
            self.assertTrue(all(k["quaternion_wxyz"] == [1.0, 0.0, 0.0, 0.0] and k["translation"] == [0.0, 0.0, 0.0] for k in root["keys"]))
            self.assertEqual(root["channels"], ["rotation"])
        self.assertEqual(files["meshes/fo4port/vault/console_anim/animations/StateA_Play.af"], b"Root,LeafA,LeafB|" + b"%d" % (2 + 31 + 31))   # keys: root 2 (first and last frame), two leaves 31 each
        table = {c["name"]: c for c in anim_object.clip_table(plan, convert_static.UNIT_SCALE)}
        self.assertEqual(table["StateA_Play"]["bones"], ["LeafA", "LeafB"])                 # 'bones' still lists the moving ones
        self.assertEqual([t["bone"] for t in table["StateA_Play"]["tracks"]], rig)
        self.assertEqual([t["static"] for t in table["StateA_Play"]["tracks"]], [True, False, False])
        self.assertEqual([m["bone"] for m in table["StateA_Play"]["motion"]], ["LeafA", "LeafB"])   # a static track moves nothing and is not listed
        self.assertEqual(anim["animated_bones"], ["LeafA", "LeafB"])
        self.assertEqual(anim["moving_bodies"], 2)                                          # the root's shape is still static geometry

    def test_a_rig_bone_without_a_source_node_is_refused_not_misaligned(self):
        plan = door_rig.animated_identity_binds(door_rig.plan(console_nif(), placed=True, aliases=STATES, allowed=tuple(STATES.values())))
        broken = {**plan, "bones": [dict(b, node=None) if i == 0 else b for i, b in enumerate(plan["bones"])]}
        with self.assertRaisesRegex(ValueError, "no source node"):
            anim_object.fill_static_tracks(broken)

    def test_door_clips_are_written_exactly_as_before(self):
        """The door path never fills static tracks: a door's .af keeps only the tracks it had (same bytes as the parent commit)."""
        f = door_nif(two_leaves())
        plan = door_rig.animated_identity_binds(door_rig.plan(f, placed=True))
        names = [t["name"] for c in plan["clips"] for t in c["tracks"]]
        self.assertFalse(any(t.get("static") for c in plan["clips"] for t in c["tracks"]))
        prepared = native_door.prepare(plan, convert_static.UNIT_SCALE)
        self.assertEqual(sorted({t["name"] for c in prepared["clips"] for t in c["tracks"]}), sorted(set(names)))

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

    def test_the_chain_mode_writes_all_eight_clips_and_names_the_graph_it_is_given(self):
        graph = "AnimTextData\\Tables\\Graphs\\GenericStateGraph01.agx"
        with tempfile.TemporaryDirectory() as tmp, patch.object(native_door, "export", fake_exporter):
            res = self.converter(tmp).convert_anim_object("Meshes\\Interiors\\Vault\\Console01.nif", STATES, foley="QST_Flip", idles="chain", graph=graph)
            self.assertTrue(res["ok"], res.get("reason"))
            anim = res["anim"]
            self.assertEqual((anim["idles"], anim["anim_graph"]), ("chain", graph))
            names = sorted(c["name"] for c in anim["clips"])
            self.assertEqual(names, sorted(anim_object.slot_names(STATES, "chain")))
            self.assertEqual(len(names), 8)
            by = {c["name"]: c for c in anim["clips"]}
            self.assertEqual((by["StateA_Idle"]["hold_frame"], by["StateB_Idle"]["hold_frame"]), ("first", "last"))
            self.assertEqual((by["StateC_Idle"]["hold_of"], by["StateD_Idle"]["hold_of"]), ("StateB_Play", "StateB_Play"))       # two mapped: the last pose repeats
            self.assertEqual(by["StateC_Play"]["frames"], 1)                                                                     # a spare play slot is one frame long
            for slot in names:
                for ext in (".af", ".afx"):
                    self.assertTrue(os.path.isfile(os.path.join(tmp, "meshes", "fo4port", "interiors", "vault", "console01_anim", "animations", slot + ext)), slot + ext)
        with tempfile.TemporaryDirectory() as tmp, patch.object(native_door, "export", fake_exporter):
            res = self.converter(tmp).convert_anim_object("Meshes\\Interiors\\Vault\\Console01.nif", STATES)               # the defaults are unchanged
            self.assertEqual((res["anim"]["idles"], res["anim"]["anim_graph"]), ("toggle", anim_object.GRAPH))

    def test_a_chain_that_skips_a_slot_still_writes_all_eight_clips_and_an_empty_map_is_refused_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(native_door, "export", fake_exporter):
            res = self.converter(tmp).convert_anim_object("Meshes\\x.nif", {"Stage1": "StateA_Play", "Stage2": "StateC_Play"}, idles="chain")
            self.assertTrue(res["ok"], res.get("reason"))
            by = {c["name"]: c for c in res["anim"]["clips"]}
            self.assertEqual(len(by), 8)
            self.assertEqual(by["StateC_Play"]["starts_from"], "StateB_Idle")                                                   # second in the chain
            self.assertEqual(by["StateB_Play"]["frames"], 1)                                                                    # the slot nobody mapped is a spare
            for ext in (".af", ".afx"):
                self.assertTrue(os.path.isfile(os.path.join(tmp, "meshes", "fo4port", "x_anim", "animations", "StateB_Play" + ext)))
        with tempfile.TemporaryDirectory() as tmp:
            res = self.converter(tmp).convert_anim_object("Meshes\\x.nif", {}, idles="chain")
            self.assertFalse(res["ok"])
            self.assertIn("at least one", res["reason"])
            self.assertEqual(os.listdir(tmp), [])

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
