import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "route_eval", Path(__file__).resolve().parents[1] / "scripts" / "game" / "route_eval.py")
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)


def stair(end, start="0 0 0.3"):
    route = {"kind": "stairs", "expect": {"low": [0, 0, 0], "high": [2, 0, 2], "min_rise": 1.6}}
    return evaluator.judge(route, {"start_read": start, "end_read": end})[0]


def door(end, start="0 0 0"):
    route = {"kind": "door", "expect": {"plane_point": [0, 0, 0], "plane_normal": [2, 0, 0], "min_past": 0.8}}
    return evaluator.judge(route, {"start_read": start, "end_read": end})[0]


class RouteEvalTests(unittest.TestCase):
    def test_real_climbs_and_crossings_still_pass(self):
        self.assertEqual(stair("2.1 0.2 1.9"), "PASS")
        self.assertEqual(stair("2 0 0.4"), "STUCK")
        self.assertEqual(stair("1 0 -1"), "FALL")
        self.assertEqual(door("3 0.2 0"), "PASS")          # 1.5 m past a non-unit normal
        self.assertEqual(door("-0.4 0 0"), "BLOCKED")

    def test_impossible_reads_are_not_passes(self):
        self.assertEqual(stair("2 0 33"), "UNREAD")        # the 31 m Vault 114 climb
        self.assertEqual(stair("2 10 1.9"), "UNREAD")      # height matches, but it is off this stair
        self.assertEqual(stair("-6 0 0.1"), "STUCK")       # walked the other way along the same line
        self.assertEqual(stair("2 0 1.9", start="0 0 0.3"), "PASS")
        self.assertEqual(door("8 0.2 0"), "PASS")          # a few metres down the corridor is still a crossing
        self.assertEqual(evaluator.judge(
            {"kind": "stairs", "expect": {"low": [0, 0, 0], "high": [2, 0, 2], "min_rise": 1.6}},
            {"start_read": "0 0 0", "end_read": "20 0 1"})[0], "UNREAD")
        self.assertEqual(door("30 0 0"), "UNREAD")
        self.assertEqual(door("2 8 0"), "UNREAD")
        self.assertEqual(evaluator.judge(
            {"kind": "door", "expect": {"plane_point": [0, 0, 0], "plane_normal": [0, 0, 0], "min_past": 0.8}},
            {"end_read": "1 0 0"})[0], "UNREAD")
        self.assertEqual(evaluator.judge(
            {"kind": "stairs", "expect": {"low": [0, 0, 0], "high": [2, 0, 2], "min_rise": 1.6}},
            {"end_read": "nope"})[0], "UNREAD")
