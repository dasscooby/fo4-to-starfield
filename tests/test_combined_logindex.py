"""Synthetic parity checks for the combined-core event log indexes."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fo4sf.combined import fixtures, jobs, model, seedpack, sim  # noqa: E402
from fo4sf.combined.logindex import LogIndex  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402
from test_combined_seedpack import commonwealth_scale_draft  # noqa: E402


FULL = os.environ.get("FO4SF_PARITY_FULL") == "1"
VARIANTS = ("normal", "raid_low", "raid_high", "story", "actions")
# Kept byte-for-byte equivalent in fields and order to the C5 parity fixture at
# 0ba91c20. Its scheduler applies entries only when ws.hour equals the hour,
# immediately before that tick; hour 500 falls between six-hour ticks.
ACTIONS = [
    {"hour": 24, "do": "help", "faction": "settlers", "amount": 15},
    {"hour": 48, "do": "defend", "place": "farm_b"},
    {"hour": 60, "do": "trade", "settlement": "market", "goods": {"food": 25, "ammo": -5}},
    {"hour": 300, "do": "defend", "place": "market", "bonus": 30, "hours": 24},
    {"hour": 500, "do": "trade", "settlement": "farm_a", "goods": {"water": 40}},
]


def two_region_world(seed, variant="normal"):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    if variant == "raid_low":
        ws.settings.raid_pressure = "low"
    elif variant == "raid_high":
        ws.settings.raid_pressure = "high"
    elif variant == "story":
        ws.settings.story_mode = True
        ws.settings.active_stories = ["main_story_1"]
    ws.settings.validate()
    return ws


def commonwealth_world(seed):
    generated, _report = seedpack.generate(commonwealth_scale_draft(seed=seed))
    ws = WorldState(seed=seed)
    model.load_pack(ws, generated)
    return ws


def reference_fought_since(ws, place, since):
    """Reference copy of the log half of sim._resettle_safe, excluding squads."""
    for event in reversed(ws.events):
        if event["hour"] < since:
            break
        if event.get("place") == place and event.get("kind") in sim.ATTACK_EVENT_KINDS:
            return True
    return False


def apply_player_action(ws, action):
    if action["do"] == "help":
        sim.player_helped(ws, action["faction"], action.get("amount", 10))
    elif action["do"] == "defend":
        sim.player_defended(ws, action["place"], action.get("bonus", 10), action.get("hours", 72))
    elif action["do"] == "trade":
        sim.player_traded(ws, action["settlement"], action["goods"])
    else:
        raise AssertionError(f"unknown scheduled player action: {action['do']}")


def assert_index_matches_readers(test, ws, index):
    hours = [event["hour"] for event in ws.events]
    test.assertEqual(hours, sorted(hours), "event hours must stay non-decreasing")
    test.assertEqual(index, LogIndex.build(ws.events))
    for fid in ws.factions:
        test.assertEqual(index.lost_places(ws, fid), sim._lost_places(ws, fid), (ws.seed, fid, ws.hour))
    since = ws.hour - sim.RESETTLE_SAFE_HOURS
    for sid in ws.settlements:
        test.assertEqual(index.fought_since(sid, since), reference_fought_since(ws, sid, since),
                         (ws.seed, sid, since, ws.hour))


def assert_index_after_each_tick(test, ws, days, actions=()):
    index = LogIndex.build(ws.events)
    action_index = 0
    for _ in range(days * 24 // sim.TICK_HOURS):
        # Match C5's exact-hour scheduler: actions run in table order immediately
        # before a tick; a missed (non-aligned) hour is never rounded or replayed.
        while action_index < len(actions) and actions[action_index]["hour"] <= ws.hour:
            action = actions[action_index]
            action_index += 1
            if action["hour"] != ws.hour:
                continue
            old_count = len(ws.events)
            apply_player_action(ws, action)
            for event in ws.events[old_count:]:
                index.add(event)
            assert_index_matches_readers(test, ws, index)
        old_count = len(ws.events)
        sim.tick(ws)
        for event in ws.events[old_count:]:
            index.add(event)
        assert_index_matches_readers(test, ws, index)


class LogIndexTests(unittest.TestCase):
    def test_event_categories_and_equal_cutoff_are_exact(self):
        events = [
            {"hour": 1, "kind": "place_taken", "place": "p", "previous": "a", "faction": "b"},
            {"hour": 4, "kind": "attack_failed", "place": "p"},
            {"hour": 4, "kind": "player_defended", "place": "p"},
            {"hour": 8, "kind": "place_cleared", "place": "q", "previous": "b"},
            {"hour": 8, "kind": "trade", "place": "q", "previous": "a"},
            {"hour": 9, "kind": "place_taken", "place": "p", "previous": "b", "faction": "a"},
        ]
        index = LogIndex.build(events)
        self.assertEqual(index.ever_lost, {"a": {"p"}, "b": {"q", "p"}})
        self.assertEqual(index.last_fight, {"p": 9, "q": 8})
        self.assertTrue(index.fought_since("p", 9))
        self.assertFalse(index.fought_since("p", 10))
        self.assertFalse(index.fought_since("missing", 0))

    def test_lost_places_filters_current_holders_and_returns_a_copy(self):
        ws = WorldState(seed=0)
        ws.places = {
            "held_again": model.Place("held_again", "R", "settlement", holder="a"),
            "lost": model.Place("lost", "R", "settlement", holder="b"),
        }
        index = LogIndex.build([
            {"hour": 1, "kind": "place_taken", "place": "held_again", "previous": "a"},
            {"hour": 2, "kind": "place_cleared", "place": "lost", "previous": "a"},
        ])
        lost = index.lost_places(ws, "a")
        self.assertEqual(lost, {"lost"})
        lost.clear()
        self.assertEqual(index.lost_places(ws, "a"), {"lost"})

    def test_clear_and_retake_jobs_emit_indexed_holder_events(self):
        ws = two_region_world(1)
        ws.places["ruins"].holder = "raiders"
        clear = next(o for o in jobs.offers(ws, "market") if o.kind == "clear" and o.target == "ruins")
        before = len(ws.events)
        jobs.complete(ws, clear)
        index = LogIndex.build(ws.events)
        cleared = next(e for e in ws.events[before:] if e["kind"] == "place_cleared")
        self.assertEqual(cleared["kind"], "place_cleared")
        self.assertIn("ruins", index.lost_places(ws, "raiders"))

        retake = next(o for o in jobs.offers(ws, "raider_camp") if o.kind == "retake" and o.target == "ruins")
        before = len(ws.events)
        jobs.complete(ws, retake)
        retaken = next(e for e in ws.events[before:] if e["kind"] == "place_taken")
        for event in ws.events[before:]:
            index.add(event)
        self.assertEqual(retaken["kind"], "place_taken")
        self.assertNotIn("ruins", index.lost_places(ws, "raiders"))
        self.assertEqual(index, LogIndex.build(ws.events))

    def test_json_round_trip_is_canonical_and_does_not_alias(self):
        index = LogIndex.build([
            {"hour": 7, "kind": "place_cleared", "place": "z", "previous": "f"},
            {"hour": 9, "kind": "place_taken", "place": "a", "previous": "f"},
        ])
        encoded = json.dumps(index.to_json(), sort_keys=True)
        payload = index.to_json()
        clone = LogIndex.from_json(payload)
        self.assertEqual(clone, index)
        self.assertEqual(json.dumps(clone.to_json(), sort_keys=True), encoded)
        payload["ever_lost"]["f"].append("external")
        self.assertNotIn("external", clone.ever_lost["f"])
        clone.ever_lost["f"].clear()
        self.assertEqual(index.ever_lost["f"], {"a", "z"})

    def test_short_tick_sweep(self):
        ws = two_region_world(0)
        assert_index_after_each_tick(self, ws, 3)

    def test_exact_player_action_schedule_and_incremental_events(self):
        ws = two_region_world(0, "actions")
        assert_index_after_each_tick(self, ws, 22, ACTIONS)
        player_events = [(event["hour"], event["kind"]) for event in ws.events
                         if event["kind"] in ("player_defended", "player_traded")]
        self.assertEqual(player_events, [(48, "player_defended"), (60, "player_traded"),
                                         (300, "player_defended")])
        self.assertEqual(ws.hour, 528)  # advance past 504: the hour-500 trade is never rounded up

    @unittest.skipUnless(FULL, "set FO4SF_PARITY_FULL=1 for the 10-seed, 90-day sweep")
    def test_full_two_region_variants_and_commonwealth_sweep(self):
        for seed in range(10):
            for variant in VARIANTS:
                with self.subTest(seed=seed, variant=variant):
                    assert_index_after_each_tick(self, two_region_world(seed, variant), 90,
                                                 ACTIONS if variant == "actions" else ())
            with self.subTest(seed=seed, variant="commonwealth-scale"):
                assert_index_after_each_tick(self, commonwealth_world(seed), 90)

    @unittest.skipUnless(FULL, "size measurement is included in the extended run")
    def test_commonwealth_365_day_serialized_size(self):
        # Measured with json.dumps(..., sort_keys=True): 1,278,487 log bytes vs
        # 8,422 index bytes for synthetic Commonwealth seed 0 after 365 days.
        ws = commonwealth_world(0)
        assert_index_after_each_tick(self, ws, 365)
        log_bytes = len(json.dumps(ws.events, sort_keys=True))
        index_bytes = len(json.dumps(LogIndex.build(ws.events).to_json(), sort_keys=True))
        print(f"Commonwealth synthetic seed=0 day=365: log_json={log_bytes} index_json={index_bytes}")


if __name__ == "__main__":
    unittest.main()
