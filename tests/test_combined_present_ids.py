"""Presence identity and spawn-diff accounting on valid synthetic, namespaced packs."""
import copy
import os
import sys
import unittest
from dataclasses import replace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.combined import model, pack, present  # noqa: E402


def world(pairs):
    places, factions = [], {}
    for place, faction in pairs:
        places.append({"id": place, "region": "synthetic", "kind": "base", "holder": faction})
        factions.setdefault(faction, {"id": faction, "home": place, "strength": 4})
    data = {"places": places, "factions": list(factions.values()),
            "routes": [{"a": pairs[0][0], "b": place, "hours": 1} for place, _ in pairs[1:]]}
    problems = pack.validate_pack(data)
    assert problems == [], problems
    ws = model.WorldState(seed=1)
    pack.load_pack(ws, data)
    return ws


AMBIGUOUS = [("region:camp", "raiders"), ("region", "camp:raiders")]


class PresenceIdentityTests(unittest.TestCase):
    def test_valid_namespaced_entities_have_distinct_group_ids(self):
        ws = world(AMBIGUOUS)
        plan = present.plan(ws, "region", max_actors=100)
        self.assertEqual(len(plan.slots), 2)
        self.assertEqual(len({slot.id for slot in plan.slots}), 2)

    def test_initial_diff_preserves_every_planned_group_and_actor(self):
        plan = present.plan(world(AMBIGUOUS), "region", max_actors=100)
        delta = present.diff(None, plan)
        self.assertEqual(len(delta.spawn), len(plan.slots))
        self.assertEqual(sum(slot.count for slot in delta.spawn), plan.actors())
        self.assertEqual((delta.keep, delta.dissolve), ([], []))

    def test_colons_and_literal_escape_text_cannot_alias(self):
        tokens = ("a", "a:b", "b:c", "c", "a%3Ab", "b%3Ac", "%", "a%253Ab", "cafe:beta%")
        seen = {}
        for place in tokens:
            for faction in tokens:
                slot = present.plan(world([(place, faction)]), place).slots[0]
                self.assertNotIn(slot.id, seen, f"{(place, faction)!r} aliases {seen.get(slot.id)!r}")
                seen[slot.id] = (place, faction)
        self.assertEqual(len(seen), len(tokens) ** 2)

    def test_ordinary_legacy_ids_are_unchanged(self):
        plan = present.plan(world([("farm_a", "settlers"), ("camp", "raiders")]), "farm_a")
        self.assertEqual({slot.id for slot in plan.slots},
                         {"garrison:farm_a:settlers", "garrison:camp:raiders"})

    def test_ids_and_accounting_survive_world_save_reload(self):
        ws = world(AMBIGUOUS + [("region%3Acamp", "raiders")])
        before = present.plan(ws, "region", max_actors=100)
        restored = model.WorldState.from_json(ws.to_json())
        after = present.plan(restored, "region", max_actors=100)
        self.assertEqual(before.to_dict(), after.to_dict())
        delta = present.diff(before, after)
        self.assertEqual((delta.spawn, delta.dissolve), ([], []))
        self.assertEqual(len(delta.keep), len(after.slots))
        self.assertEqual(sum(slot.count for slot in delta.keep), after.actors())

    def test_budgeted_replans_account_for_every_surviving_slot(self):
        ws = world(AMBIGUOUS + [("region%3Acamp", "raiders")])
        saved = ws.to_json()
        old = None
        for centre, budget in (("region", 3), ("region:camp", 9), ("region%3Acamp", 6),
                               ("region", 0), ("region", 100)):
            with self.subTest(centre=centre, budget=budget):
                new = present.plan(ws, centre, radius_hours=2, max_actors=budget)
                delta = present.diff(old, new)
                active = {slot.id: slot for slot in old.slots} if old is not None else {}
                for slot in delta.dissolve:
                    del active[slot.id]
                active.update((slot.id, slot) for slot in delta.keep + delta.spawn)
                self.assertEqual(set(active), {slot.id for slot in new.slots})
                self.assertEqual(len(active), len(new.slots))
                self.assertEqual(sum(slot.count for slot in active.values()), new.actors())
                self.assertLessEqual(new.actors(), budget)
                old = new
        self.assertEqual(ws.to_json(), saved)

    def test_distance_only_replan_keeps_both_groups(self):
        ws = world(AMBIGUOUS)
        old = present.plan(ws, "region", radius_hours=1, max_actors=100)
        new = present.plan(ws, "region:camp", radius_hours=1, max_actors=100)
        delta = present.diff(old, new)
        self.assertEqual((delta.spawn, delta.dissolve), ([], []))
        self.assertEqual(len(delta.keep), 2)

    def test_diff_refuses_duplicate_ids_in_either_input_without_mutation(self):
        clean = present.plan(world([("camp", "raiders")]), "camp")
        bad = replace(clean, slots=[clean.slots[0], clean.slots[0]])
        before = copy.deepcopy((clean.to_dict(), bad.to_dict()))
        for old, new in ((None, bad), (clean, bad), (bad, clean)):
            with self.subTest(old_bad=old is bad, new_bad=new is bad):
                with self.assertRaisesRegex(ValueError, "duplicate.*slot"):
                    present.diff(old, new)
        self.assertEqual((clean.to_dict(), bad.to_dict()), before)


if __name__ == "__main__":
    unittest.main()
