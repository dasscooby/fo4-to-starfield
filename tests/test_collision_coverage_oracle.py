import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("collision_coverage", Path(__file__).resolve().parents[1]
                                           / "scripts" / "oracles" / "collision_coverage.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class CollisionCoverageOracleTests(unittest.TestCase):
    def test_missing_report_is_not_a_pass(self):
        result = oracle.audit({"items": [{"source": "unknown", "collision_report": {}}]})
        self.assertEqual(result["unassessed"], ["unknown"])
        self.assertEqual(result["reported_without_drops"], 0)

    def test_any_dropped_coverage_is_incomplete(self):
        result = oracle.audit({"items": [{"source": key, "collision_report": {"boxes": 2, key: 1}}
                                        for key in oracle.COUNTS]})
        self.assertEqual(len(result["incomplete"]), 3)
        self.assertEqual(result["reported_without_drops"], 0)

    def test_coarse_resolution_is_exposed_even_without_drops(self):
        result = oracle.audit({"items": [{"source": "floor", "collision_report": {"boxes": 2, "surface_cell": 1.0}}]})
        self.assertEqual(len(result["coarsened"]), 1)
        self.assertEqual(result["reported_without_drops"], 1)

    def test_malformed_counts_cannot_pass(self):
        for value in [-1, "1", True, 1.5]:
            result = oracle.audit({"items": [{"source": "bad", "collision_report": {"floor_dropped": value}}]})
            self.assertTrue(result["errors"])
            self.assertEqual(result["reported_without_drops"], 0)

    def test_malformed_manifest_entries_are_reported(self):
        for manifest in [[], {"items": []}, {"items": [None]},
                         {"items": [{"collision_report": {"boxes": -1}}]}]:
            self.assertTrue(oracle.audit(manifest)["errors"])
