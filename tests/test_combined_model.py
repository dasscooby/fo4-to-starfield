"""Combined core L1 model and L5 packs: synthetic fixtures only, no game data."""
import copy
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import model, pack, sim  # noqa: E402
from fo4sf.combined.fixtures import REGION_1, REGION_2  # noqa: E402
from fo4sf.combined.model import SCHEMA_VERSION, WorldState  # noqa: E402


def r1():
    return copy.deepcopy(REGION_1)


def r2():
    return copy.deepcopy(REGION_2)


def world(*packs):
    ws = WorldState(seed=7)
    for p in packs:
        pack.load_pack(ws, p)
    return ws


class ModelTests(unittest.TestCase):
    def test_neighbours_are_sorted_and_undirected(self):
        ws = world(r1())
        self.assertEqual(ws.neighbours("market"),
                         [("farm_a", 6), ("farm_b", 6), ("gate_1", 12), ("story_vault", 6)])
        self.assertEqual(ws.neighbours("nowhere"), [])

    def test_json_round_trip_carries_schema(self):
        ws = world(r1(), r2())
        ws.hour = 42
        ws.events.append({"hour": 6, "kind": "raid", "place": "farm_a", "region": "R1"})
        text = ws.to_json()
        self.assertEqual(json.loads(text)["schema"], SCHEMA_VERSION)
        back = WorldState.from_json(text)
        self.assertEqual(back, ws)
        self.assertEqual(back.to_json(), text)

    def test_from_json_rejects_unknown_or_missing_schema(self):
        d = json.loads(world(r1()).to_json())
        d["schema"] = SCHEMA_VERSION + 1
        with self.assertRaises(ValueError):
            WorldState.from_json(json.dumps(d))
        del d["schema"]
        with self.assertRaises(ValueError):
            WorldState.from_json(json.dumps(d))
        for other in ("[]", "3", "null", json.dumps({"schema": SCHEMA_VERSION}),
                      json.dumps({**d, "schema": SCHEMA_VERSION, "places": []}),
                      json.dumps({**d, "schema": SCHEMA_VERSION, "events": [None]}),
                      json.dumps({**d, "schema": SCHEMA_VERSION, "events": [{"hour": 0}]}),
                      json.dumps({**d, "schema": SCHEMA_VERSION,
                                  "events": [{"hour": "bad", "kind": "x", "place": "p"}]}),
                      json.dumps({**d, "schema": SCHEMA_VERSION, "hour": "bad"}),
                      json.dumps({**d, "schema": SCHEMA_VERSION, "next_id": True})):   # Codex review of #431: misshapen
            with self.assertRaises(ValueError):
                WorldState.from_json(other)

    def test_from_json_rejects_misshapen_records_and_routes(self):
        # Codex review of #431: a resumed route or record of the wrong shape fails at load, not in a tick
        d = json.loads(world(r1()).to_json())
        place = sorted(d["places"])[0]
        bad = []
        for hours in ("bad", 0, -2, 1.5):
            bad.append({**d, "routes": [{**d["routes"][0], "hours": hours}]})
        bad.append({**d, "routes": [{**d["routes"][0], "a": "nowhere"}]})
        bad.append({**d, "places": {**d["places"], place: {**d["places"][place], "defence": "high"}}})
        faction = sorted(d["factions"])[0]
        bad.append({**d, "factions": {**d["factions"], faction: {**d["factions"][faction], "relations": {"x": "y"}}}})
        bad.append({**d, "places": {**d["places"], place: {**d["places"][place], "holder": "ghost"}}})   # Codex, #431
        bad.append({**d, "factions": {**d["factions"], faction: {**d["factions"][faction], "home": "nowhere"}}})
        bad.append({**d, "reputation": {**d["reputation"], "ghost": {"fame": 0, "infamy": 0}}})
        bad.append({**d, "reputation": {k: v for k, v in d["reputation"].items() if k != faction}})   # Grok, #431
        settlement = sorted(d["settlements"])[0]
        bad.append({**d, "settlements": {**d["settlements"], settlement: {**d["settlements"][settlement],
                                                                          "place": "nowhere"}}})
        for other in bad:
            with self.assertRaises(ValueError):
                WorldState.from_json(json.dumps(other))

    def test_model_load_pack_delegates(self):
        ws = WorldState(seed=1)
        model.load_pack(ws, r1())
        self.assertEqual(sorted(ws.factions), ["order", "raiders", "settlers"])
        self.assertEqual(sorted(ws.reputation), ["order", "raiders", "settlers"])
        with self.assertRaises(ValueError):
            model.load_pack(ws, r1())


class PackLoadTests(unittest.TestCase):
    def test_fixtures_are_valid_alone_and_together(self):
        self.assertEqual(pack.validate_pack(r1()), [])
        ws = world(r1())
        self.assertEqual(pack.validate_pack(r2(), ws), [])
        pack.load_pack(ws, r2())
        self.assertIn("river_town", ws.places)
        self.assertEqual(ws.neighbours("gate_1"), [("gate_2", 48), ("market", 12)])
        self.assertEqual(ws.factions["slavers"].relations["settlers"], -50)

    def test_region_2_alone_needs_region_1(self):
        # its route to gate_1 and relation to settlers point at the first pack
        problems = pack.validate_pack(r2())
        self.assertTrue(any("gate_1" in p for p in problems))
        self.assertTrue(any("settlers" in p for p in problems))
        with self.assertRaises(ValueError):
            world(r2())

    def test_invalid_pack_leaves_world_untouched(self):
        ws = world(r1())
        before = ws.to_json()
        bad = r2()
        bad["routes"].append({"a": "river_town", "b": "ghost", "hours": 3})
        with self.assertRaisesRegex(ValueError, "ghost"):
            pack.load_pack(ws, bad)
        self.assertEqual(ws.to_json(), before)

    def test_packs_only_add(self):
        ws = world(r1())
        again = {"places": [dict(r1()["places"][0])]}
        self.assertTrue(any("already defined" in p for p in pack.validate_pack(again, ws)))
        again = {"factions": [dict(r1()["factions"][0])]}
        self.assertTrue(any("already defined" in p for p in pack.validate_pack(again, ws)))
        again = {"settlements": [dict(r1()["settlements"][0])]}
        self.assertTrue(any("already defined" in p for p in pack.validate_pack(again, ws)))

    def test_story_lock_is_a_story_id_or_null(self):
        # Codex review of #431: the sim tests story_lock by truthiness, so "" would drop a lock and [] or 0 mislead
        for bad in ("", 0, [], {"id": "x"}, True):
            p = r1()
            p["places"][0]["story_lock"] = bad
            self.assertTrue(any("story_lock" in q for q in pack.validate_pack(p)), bad)
        for ok in (None, "main_story_1"):
            p = r1()
            p["places"][0]["story_lock"] = ok
            self.assertFalse(any("story_lock" in q for q in pack.validate_pack(p)), ok)

    def test_partial_role_and_stock_tables_are_filled(self):
        p = r1()
        p["settlements"][0]["roles"] = {"farmer": 5}
        p["settlements"][0]["stock"] = {"food": 1}
        ws = world(p)
        s = ws.settlements["farm_a"]
        self.assertEqual(s.roles, {"farmer": 5, "guard": 0, "trader": 0, "crafter": 0, "scavenger": 0, "doctor": 0})
        self.assertEqual(s.stock["medicine"], 0)

    def test_load_pack_file(self):
        ws = WorldState(seed=7)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "r1.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(r1(), f)
            pack.load_pack_file(ws, path)
        self.assertEqual(len(ws.places), 8)
        self.assertEqual(ws, world(r1()))


class PackValidationTests(unittest.TestCase):
    def problems(self, mutate, base=None, ws=None):
        p = base or r1()
        mutate(p)
        return pack.validate_pack(p, ws)

    def assertProblem(self, mutate, text, **kw):
        problems = self.problems(mutate, **kw)
        self.assertTrue(any(text in q for q in problems), f"{text!r} not in {problems}")

    def test_ids_must_be_non_empty_strings(self):
        # Codex P2 on #431: a null id loaded under the key None and broke the save round-trip.
        for bad in (None, "", 7):
            self.assertProblem(lambda p: p["places"][0].update(id=bad), "must be a non-empty ASCII string")
            self.assertProblem(lambda p: p["factions"][0].update(id=bad), "must be a non-empty ASCII string")

    def test_references_must_be_strings(self):
        # Codex P2 on #431: a list holder raised TypeError instead of a validation problem.
        self.assertProblem(lambda p: p["places"][0].update(holder=[]), "must be a faction id")
        self.assertProblem(lambda p: p["factions"][0].update(home={}), "must be a place id")
        self.assertProblem(lambda p: p["settlements"][0].update(place=[1]), "must be a place id")
        self.assertProblem(lambda p: p["routes"][0].update(a=[]), "both ends must be place ids")

    def test_not_an_object(self):
        self.assertEqual(pack.validate_pack([]), ["pack must be an object"])

    def test_sections_and_required_keys(self):
        self.assertProblem(lambda p: p.update(extra=[]), "unknown section")
        self.assertProblem(lambda p: p["places"][0].pop("kind"), "missing kind")
        self.assertProblem(lambda p: p["factions"][0].pop("home"), "missing home")
        self.assertProblem(lambda p: p["routes"][0].pop("hours"), "missing hours")
        self.assertProblem(lambda p: p["settlements"][0].pop("place"), "missing place")
        self.assertProblem(lambda p: p["places"][0].update(colour="red"), "unknown keys colour")
        self.assertProblem(lambda p: p.update(routes={}), "must be a list")
        self.assertProblem(lambda p: p["routes"].append(3), "must be an object")

    def test_unique_ids(self):
        self.assertProblem(lambda p: p["places"].append(dict(p["places"][0])), "place farm_a: already defined")
        self.assertProblem(lambda p: p["factions"].append(dict(p["factions"][0])), "faction settlers: already defined")
        self.assertProblem(lambda p: p["settlements"].append(dict(p["settlements"][0])),
                           "settlement farm_a: already defined")

    def test_place_kinds_and_defence(self):
        self.assertProblem(lambda p: p["places"][0].update(kind="castle"), "kind 'castle'")
        self.assertProblem(lambda p: p["places"][0].update(defence=-1), "defence")

    def test_holder_must_be_known_faction(self):
        self.assertProblem(lambda p: p["places"][5].update(holder="ghosts"), "holder 'ghosts'")

    def test_faction_home_exists_and_is_held(self):
        self.assertProblem(lambda p: p["factions"][0].update(home="nowhere"), "home 'nowhere'")
        self.assertProblem(lambda p: p["factions"][1].update(home="farm_a"),
                           "faction raiders: home farm_a is held by 'settlers'")
        # home held by the faction but defined in an earlier pack is fine
        ws = world(r1())
        p = {"places": [{"id": "x", "region": "R3", "kind": "base", "holder": "settlers"}]}
        self.assertEqual(pack.validate_pack(p, ws), [])

    def test_faction_numbers(self):
        self.assertProblem(lambda p: p["factions"][0].update(strength=-2), "strength")
        self.assertProblem(lambda p: p["factions"][0].update(strength=model.STRENGTH_CAP + 1), "strength")
        self.assertProblem(lambda p: p["factions"][0].update(aggression=101), "aggression")
        p = r1()
        p["factions"][0]["strength"] = model.STRENGTH_CAP           # the cap itself is in range
        self.assertEqual(pack.validate_pack(p), [])

    def test_strength_is_capped_before_the_first_tick(self):
        # validated at the cap, no faction can attack with more than the sim's own bound (sim.STRENGTH_CAP is the
        # same object, so the two cannot drift apart)
        self.assertIs(sim.STRENGTH_CAP, model.STRENGTH_CAP)
        ws = world(r1())
        self.assertTrue(all(f.strength <= model.STRENGTH_CAP for f in ws.factions.values()))

    def test_relations(self):
        self.assertProblem(lambda p: p["factions"][0]["relations"].update(ghosts=5), "unknown faction 'ghosts'")
        self.assertProblem(lambda p: p["factions"][0]["relations"].update(raiders=-101), "-100..100")
        self.assertProblem(lambda p: p["factions"][0]["relations"].update(raiders=True), "-100..100")
        self.assertProblem(lambda p: p["factions"][0].update(relations=[]), "relations must be an object")

    def test_settlement_place(self):
        self.assertProblem(lambda p: p["settlements"][0].update(place="ruins"), "not of kind settlement")
        self.assertProblem(lambda p: p["settlements"][0].update(place="void"), "place is not known")

    def test_settlement_roles_and_goods(self):
        self.assertProblem(lambda p: p["settlements"][0]["roles"].update(mayor=1), "unknown roles key 'mayor'")
        self.assertProblem(lambda p: p["settlements"][0]["stock"].update(gold=1), "unknown stock key 'gold'")
        self.assertProblem(lambda p: p["settlements"][0]["roles"].update(farmer=-1), "roles[farmer]")
        self.assertProblem(lambda p: p["settlements"][0]["stock"].update(food=-1), "stock[food]")
        self.assertProblem(lambda p: p["settlements"][0].update(roles="many"), "roles must be an object")

    def test_settlement_population_roles_and_beds(self):
        self.assertProblem(lambda p: p["settlements"][0].update(population=4), "roles sum to 5, population is 4")
        self.assertProblem(lambda p: p["settlements"][0].update(beds=4), "population 5 exceeds beds 4")
        self.assertProblem(lambda p: p["settlements"][0].update(population=-1, roles={}), "population")
        self.assertProblem(lambda p: p["settlements"][0].update(morale=101), "morale")
        self.assertProblem(lambda p: p["settlements"][0].update(stage=5), "stage")

    def test_settlement_priority_is_a_good_or_null(self):
        self.assertProblem(lambda p: p["settlements"][0].update(priority="gold"), "priority must be one of")
        self.assertProblem(lambda p: p["settlements"][0].update(priority=7), "priority must be one of")
        self.assertEqual(self.problems(lambda p: p["settlements"][0].update(priority="food")), [])
        self.assertEqual(self.problems(lambda p: p["settlements"][0].update(priority=None)), [])
        p = r1()
        p["settlements"][0]["priority"] = "scrap"
        ws = world(p)
        sim.run(ws, 24)                                  # a validated priority runs; "gold" would be a KeyError
        self.assertEqual(ws.settlements["farm_a"].priority, "scrap")

    def test_routes(self):
        self.assertProblem(lambda p: p["routes"][0].update(hours=0), "hours must be a positive integer")
        self.assertProblem(lambda p: p["routes"][0].update(hours=2.5), "hours must be a positive integer")
        self.assertProblem(lambda p: p["routes"][0].update(b="void"), "'void' is not a known place")
        self.assertProblem(lambda p: p["routes"][0].update(b="farm_a"), "joins a place to itself")
        self.assertProblem(lambda p: p["routes"].append({"a": "market", "b": "farm_a", "hours": 9}), "duplicate edge")
        # a duplicate of an edge an earlier pack loaded is also a duplicate
        ws = world(r1())
        self.assertProblem(lambda p: None, "duplicate edge",
                           base={"routes": [{"a": "market", "b": "farm_a", "hours": 1}]}, ws=ws)

    def test_cross_pack_references_need_the_first_pack_loaded(self):
        ws = world(r1())
        p = {
            "places": [{"id": "outpost", "region": "R2", "kind": "base", "holder": "order"}],
            "factions": [{"id": "cult", "strength": 3, "home": "outpost", "relations": {"settlers": 10}}],
            "routes": [{"a": "outpost", "b": "gate_1", "hours": 4}],
        }
        # cult's home is held by order, so this fails for one reason only
        problems = pack.validate_pack(copy.deepcopy(p), ws)
        self.assertEqual(len(problems), 1)
        self.assertIn("held by 'order'", problems[0])
        p["places"][0]["holder"] = "cult"
        self.assertEqual(pack.validate_pack(copy.deepcopy(p), ws), [])
        self.assertEqual(len(pack.validate_pack(copy.deepcopy(p))), 2)   # relation, route


class FixtureHygieneTests(unittest.TestCase):
    def test_tests_did_not_mutate_the_module_fixtures(self):
        self.assertEqual(pack.validate_pack(copy.deepcopy(REGION_1)), [])
        self.assertEqual(REGION_1["settlements"][0]["population"], 5)
        self.assertEqual(len(REGION_1["routes"]), 9)


if __name__ == "__main__":
    unittest.main()
