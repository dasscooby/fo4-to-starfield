"""CC-64 gateway-list contract on invented marker/plugin data; no game assets or native acceptance.

The SHA256 pins were measured from seedpack.write on main 85d27a75104708932260feec99f8b4cc19248f7f,
before the gateway implementation. They cover the small two-world marker draft, the Commonwealth-scale
synthetic draft, and an empty draft. Both API and CLI must preserve the actual file bytes.
"""
import copy
import hashlib
import json
import pathlib
import tempfile
import unittest

from tests import test_combined_seedpack as seed_tests
from fo4sf.combined import balance, pack, seed, seedpack, sim
from fo4sf.combined.model import ROLES, STRENGTH_CAP, WorldState


MAIN_SHA256 = {
    "markers": {
        "pack": "1052f9506959e83fcb21bd575e82fb7b8eb293d05ef1d72ff13e9ea7b8e8367d",
        "report": "7104f72e3627c39515bf74f6d9ae6944f035a4760e82367d7e016f955ee6eb18",
    },
    "scale": {
        "pack": "55260f95c95663f723c0d5690e658c84bbd22a9f47409c17d8da3c9ff5743e13",
        "report": "87dabc00299dd27b6785ea055d2ed5c8ce8181b688b427d8e1e30fbd66fddd61",
    },
    "empty": {
        "pack": "d28be343981e104a12d3b348d56b885309e7500c46c2884c6dfadb07ac171cf2",
        "report": "47cb74466d1b4c548fb1dee01d0469aa75fc6c7a3de150f6a0af9b1568c9a836",
    },
}


def marker_draft(directory):
    base = pathlib.Path(directory) / "Base.esm"
    seed_tests.write_base(str(base))
    draft, _ = seed.build(seed.read([str(base)]))
    return draft


def gateway(a="TestFarmA", b="TestIsland", hours=48):
    return {"a": a, "b": b, "hours": hours}


class GatewayTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = pathlib.Path(tmp.name)
        self.draft = marker_draft(self.dir)
        self.baseline, self.report = seedpack.generate(self.draft)

    def assert_refused(self, value, rule, draft=None):
        draft = self.draft if draft is None else draft
        before = copy.deepcopy((draft, value))
        baseline, baseline_report = seedpack.generate(draft)
        result, report = seedpack.generate(draft, gateways=value)
        # Includes routes, places, factions/homes, and settlements: no partial application.
        self.assertEqual(result, baseline)
        self.assertEqual(seedpack.dumps(result), seedpack.dumps(baseline))
        used = report.pop("gateways")
        self.assertEqual(report, baseline_report)
        self.assertEqual(used["pairs"], [])
        self.assertEqual(used["world_pairs"], [])
        self.assertEqual(used["hours"], {})
        self.assertTrue(any(p.startswith(rule + ":") for p in used["problems"]), used)
        self.assertEqual((draft, value), before)

    def test_g1_unknown_dropped_or_non_id_end_refuses_entire_list(self):
        for bad in ("TestUnknown", "TestQuestSpot", "TestBadMarker", None, True, [], {}):
            with self.subTest(bad=bad):
                self.assert_refused({"gateways": [gateway(), gateway(a=bad)]}, "G1")

    def test_g2_no_marker_world_refuses_entire_list(self):
        self.assert_refused({"gateways": [gateway(), gateway(a="TestFarmAnnex")]}, "G2")
        for world in (None, "", "missing key"):
            with self.subTest(world=world):
                draft = copy.deepcopy(self.draft)
                marker = next(p for p in draft["places"] if p["id"] == "TestFarmB")["marker"]
                if world == "missing key":
                    del marker["world"]
                else:
                    marker["world"] = world
                self.assert_refused({"gateways": [gateway(), gateway(a="TestFarmB")]}, "G2", draft)

    def test_g2_same_world_despite_different_regions_and_self_pair(self):
        draft = copy.deepcopy(self.draft)
        next(p for p in draft["places"] if p["id"] == "TestFarmB")["region"] = "DifferentRootLocation"
        for b in ("TestFarmA", "TestFarmB"):
            with self.subTest(b=b):
                self.assert_refused({"gateways": [gateway(), gateway(b=b)]}, "G2", draft)

    def test_g3_only_positive_integer_hours(self):
        for hours in (0, -1, 1.0, 0.5, "48", True, False, None, [], {}):
            with self.subTest(hours=hours):
                self.assert_refused({"gateways": [gateway(), gateway(a="TestFarmB", hours=hours)]}, "G3")

    def test_g4_repeated_or_reversed_pair_refuses_entire_list(self):
        for duplicate in (gateway(), gateway(a="TestIsland", b="TestFarmA")):
            with self.subTest(duplicate=duplicate):
                self.assert_refused({"gateways": [gateway(), duplicate]}, "G4")

    def test_g5_exact_top_level_and_entry_keys(self):
        malformed = [None, [], True, "gateways", {}, {"gateways": None}, {"gateways": {}},
                     {"gateways": [], "extra": 1}]
        for entry in (None, [], "pair", {}, {"a": "TestFarmB", "b": "TestIsland"},
                      {"a": "TestFarmB", "hours": 2}, {"b": "TestIsland", "hours": 2},
                      dict(gateway(a="TestFarmB"), world="base.esm:000080")):
            malformed.append({"gateways": [gateway(), entry]})
        for value in malformed:
            with self.subTest(value=value):
                self.assert_refused(value, "G5")

    def test_all_problems_are_reported_in_plain_words(self):
        _, report = seedpack.generate(self.draft, gateways={"gateways": [
            gateway(), gateway(a="TestUnknown"), gateway(b="TestFarmB"),
            gateway(a="TestFarmB", hours=False), gateway(), {},
        ]})
        self.assertEqual({p.split(":")[0] for p in report["gateways"]["problems"]},
                         {"G1", "G2", "G3", "G4", "G5"})

    def test_valid_hub_adds_exact_sorted_edges_and_reports_world_pairs_and_hours(self):
        # All kept places share a root-location region, but Island's marker belongs to another WRLD.
        entries = [gateway(a="TestIsland", b="TestFarmB", hours=1), gateway(),
                   gateway(a="TestGhoulDen", hours=99)]
        before = copy.deepcopy((self.draft, entries))
        result, report = seedpack.generate(self.draft, gateways={"gateways": entries})
        expected = [gateway(a="TestFarmB", hours=1), gateway(), gateway(a="TestGhoulDen", hours=99)]
        expected.sort(key=lambda r: (r["a"], r["b"]))
        self.assertEqual(result["routes"], sorted(self.baseline["routes"] + expected,
                                                key=lambda r: (r["a"], r["b"])))
        self.assertEqual(result["places"], self.baseline["places"])
        self.assertEqual(result["settlements"], self.baseline["settlements"])
        self.assertEqual(report["gateways"], {
            "pairs": expected,
            "world_pairs": [{"a": "base.esm:000080", "b": "base.esm:000082", "count": 3}],
            "hours": {1: 1, 48: 1, 99: 1}, "problems": [],
        })
        self.assertEqual(report["routes"], self.report["routes"] + 3)
        self.assertEqual(report["route_hours"][48], 1)
        self.assertEqual(report["isolated"], ["TestOrphanFarm"])
        self.assertEqual(report["route_scale"], self.report["route_scale"])
        self.assertEqual(pack.validate_pack(result), [])
        self.assertEqual(report["validation_problems"], [])
        self.assertEqual((self.draft, entries), before)

    def test_hours_are_unscaled_and_one_is_allowed_even_above_the_rules_minimum(self):
        rules = copy.deepcopy(seedpack.DEFAULT_RULES)
        rules.update(median_route_hours=300, min_route_hours=20)
        result, _ = seedpack.generate(self.draft, rules, {"gateways": [gateway(hours=1)]})
        self.assertIn(gateway(hours=1), result["routes"])
        self.assertEqual(pack.validate_pack(result), [])

    def test_draft_and_list_order_and_pair_orientation_do_not_change_bytes(self):
        entries = [gateway(), gateway(a="TestGhoulDen", hours=7)]
        expected = seedpack.generate(self.draft, gateways={"gateways": entries})
        shuffled = copy.deepcopy(self.draft)
        shuffled["places"].reverse()
        shuffled["factions"].reverse()
        reversed_entries = [{"a": r["b"], "b": r["a"], "hours": r["hours"]} for r in reversed(entries)]
        actual = seedpack.generate(shuffled, gateways={"gateways": reversed_entries})
        self.assertEqual(tuple(map(seedpack.dumps, actual)), tuple(map(seedpack.dumps, expected)))

    def test_valid_two_world_pack_loads_and_runs_deterministically_with_balance_invariants(self):
        draft = copy.deepcopy(self.draft)
        # Add a synthetic story lock so that its invariant is exercised too.
        story = copy.deepcopy(next(p for p in draft["places"] if p["id"] == "TestRuin"))
        story["id"] = "Goodneighbor"
        draft["places"].append(story)
        result, _ = seedpack.generate(draft, gateways={"gateways": [gateway(hours=6)]})
        self.assertEqual(pack.validate_pack(result), [])
        for rng_seed in (1, 2, 3):
            with self.subTest(seed=rng_seed):
                ws = WorldState(seed=rng_seed)
                pack.load_pack(ws, copy.deepcopy(result))
                self.assertEqual(sim._distances(ws, "TestFarmA")["TestIsland"], 6)
                start = copy.deepcopy(ws)
                repeated = copy.deepcopy(ws)
                for _ in range(30 * 24 // sim.TICK_HOURS):
                    sim.run(ws, sim.TICK_HOURS)
                    self.assert_invariants(ws, start)
                sim.run(repeated, 30 * 24)
                self.assertEqual(ws.to_json(), repeated.to_json())
                self.assertEqual(ws.hour, 30 * 24)
                metrics = balance.metrics(ws)
                self.assertEqual((metrics["story_lock_violations"], metrics["home_violations"]), (0, 0))
                self.assertIsNone(ws.places["Goodneighbor"].holder)
                self.assertTrue(any(e["kind"] == "attack_launched" for e in ws.events))

    def assert_invariants(self, ws, start):
        for pid, place in ws.places.items():
            if place.story_lock:
                self.assertEqual(place.holder, start.places[pid].holder)
        for fid, faction in ws.factions.items():
            self.assertEqual(ws.places[faction.home].holder, fid)
            self.assertTrue(0 <= faction.strength <= STRENGTH_CAP)
        for settlement in ws.settlements.values():
            self.assertTrue(0 <= settlement.population <= settlement.beds)
            self.assertTrue(0 <= settlement.morale <= 100)
            self.assertEqual(set(settlement.roles), set(ROLES))
            self.assertEqual(sum(settlement.roles.values()), settlement.population)
            self.assertTrue(all(n >= 0 for n in settlement.stock.values()))
        for squad in ws.squads.values():
            self.assertIn(squad.at, ws.places)
            self.assertIn(squad.goal, ws.places)

    def test_api_and_cli_no_list_and_empty_list_match_main_file_bytes(self):
        drafts = {"markers": self.draft, "scale": seed_tests.commonwealth_scale_draft(),
                  "empty": {"draft": True, "places": [], "factions": []}}
        empty = self.dir / "empty-gateways.json"
        empty.write_text('{"gateways": []}', encoding="utf-8")
        for name, draft in drafts.items():
            draft_path = self.dir / f"{name}.json"
            draft_path.write_text(json.dumps(draft), encoding="utf-8")
            for supplied in (False, True):
                with self.subTest(draft=name, empty_list=supplied):
                    kwargs = {"gateways": {"gateways": []}} if supplied else {}
                    generated, report = seedpack.generate(draft, **kwargs)
                    self.assertNotIn("gateways", report)
                    api_paths = seedpack.write(str(self.dir / "api"), generated, report)
                    out = self.dir / "cli"
                    args = ["seed-pack", str(draft_path), str(out)]
                    code, _, err = seed_tests.run_cli(args + (["--gateways", str(empty)] if supplied else []))
                    self.assertEqual(code, 0, err)
                    for key, path in api_paths.items():
                        data = pathlib.Path(path).read_bytes()
                        self.assertEqual(hashlib.sha256(data).hexdigest(), MAIN_SHA256[name][key])
                        self.assertEqual((out / pathlib.Path(path).name).read_bytes(), data)

    def test_cli_gateway_file_acceptance_and_whole_list_refusal(self):
        draft_path, list_path, out = self.dir / "draft.json", self.dir / "gateways.json", self.dir / "out"
        draft_path.write_text(json.dumps(self.draft), encoding="utf-8")
        values = [({"gateways": [gateway()]}, 0),
                  ({"gateways": [gateway(), gateway(a="dropped")]}, 1), (None, 1)]
        for value, expected_code in values:
            with self.subTest(value=value):
                list_path.write_text(json.dumps(value), encoding="utf-8")
                code, _, err = seed_tests.run_cli(["seed-pack", str(draft_path), str(out),
                                                   "--gateways", str(list_path)])
                self.assertEqual(code, expected_code, err)
                generated = json.loads((out / "commonwealth.pack.json").read_text(encoding="utf-8"))
                report = json.loads((out / "seedpack_report.json").read_text(encoding="utf-8"))
                if expected_code:
                    self.assertEqual(generated, self.baseline)
                    self.assertTrue(report["gateways"]["problems"])
                    self.assertIn(report["gateways"]["problems"][0], err)
                else:
                    expected, expected_report = seedpack.generate(self.draft, gateways=value)
                    self.assertEqual(generated, expected)
                    self.assertEqual((out / "seedpack_report.json").read_text(encoding="utf-8"),
                                     seedpack.dumps(expected_report))
                    self.assertEqual(err, "")


class GatewayCppParityTests(unittest.TestCase):
    """Use the existing compiler/FOCCSIM_EXE gate and byte-parity oracle on a generated gateway pack."""
    @classmethod
    def setUpClass(cls):
        from tests import test_combined_cpp_parity as parity
        parity.CppParityTests.setUpClass()
        cls.addClassCleanup(parity.CppParityTests.tearDownClass)

    def test_generated_gateway_routes_keep_cpp_state_and_outputs_byte_identical(self):
        from tests import test_combined_cpp_parity as parity
        with tempfile.TemporaryDirectory() as tmp:
            generated, _ = seedpack.generate(marker_draft(tmp), gateways={"gateways": [gateway(hours=6)]})
        oracle = parity.CppParityTests()
        for rng_seed in (1, 2, 3):
            with self.subTest(seed=rng_seed):
                ws = WorldState(seed=rng_seed)
                pack.load_pack(ws, copy.deepcopy(generated))
                oracle.parity(f"generated two-world gateway seed {rng_seed}", ws, 30 * parity.DAY, every=1)


if __name__ == "__main__":
    unittest.main()
