"""Combined-core far-travel layer (travel.py, CC-63) on a small synthetic world: placeholder names, not game facts."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import present, sim, travel  # noqa: E402
from fo4sf.combined.model import Place, Route, Squad, WorldState  # noqa: E402

HOUR = 100
ATLAS = {"A": (0.0, 0.0), "B": (600.0, 0.0)}


def world(hour=HOUR):
    ws = WorldState(seed=1, hour=hour)
    for pid in ("A", "B", "C"):
        ws.places[pid] = Place(id=pid, region="r1", kind="landmark")
    ws.routes.append(Route("A", "B", 6))
    return ws


def squad(at="A", goal="B", eta=HOUR + 6):
    return Squad(id="q1", faction="f1", size=3, at=at, goal=goal, eta=eta)


class ProgressTests(unittest.TestCase):
    def test_progress_over_the_route(self):
        q = squad()
        self.assertEqual(travel.progress(world(HOUR), q), 0.0)
        self.assertEqual(travel.progress(world(HOUR + 3), q), 0.5)
        self.assertEqual(travel.progress(world(HOUR + 6), q), 1.0)
        self.assertEqual(travel.progress(world(HOUR + 9), q), 1.0)

    def test_before_departure_is_zero(self):
        self.assertEqual(travel.progress(world(HOUR - 2), squad()), 0.0)

    def test_no_goal_sits_at_anchor(self):
        ws = world(HOUR + 3)
        for q in (squad(goal=None), squad(goal="A")):
            self.assertEqual(travel.progress(ws, q), 0.0)
            self.assertEqual(travel.simulated_position(ws, q, ATLAS), (0.0, 0.0))

    def test_unreachable_goal_is_zero(self):
        ws = world(HOUR + 3)
        q = squad(goal="C")
        self.assertIsNone(travel.route_hours(ws, "A", "C"))
        self.assertEqual(travel.progress(ws, q), 0.0)

    def test_multi_hop_uses_shortest_path_hours(self):
        ws = world(HOUR)
        ws.routes.append(Route("B", "C", 4))
        ws.routes.append(Route("A", "C", 20))
        hours = sim._distances(ws, "A")["C"]
        self.assertEqual(hours, 10)
        self.assertEqual(travel.route_hours(ws, "A", "C"), hours)
        q = squad(goal="C", eta=HOUR + 10)
        ws.hour = HOUR + 5
        self.assertEqual(travel.progress(ws, q), 0.5)
        self.assertEqual(present._squad_place(ws, q), "C")      # same elapsed formula, nearer end at half


class PositionTests(unittest.TestCase):
    def test_lerp_at_half(self):
        self.assertEqual(travel.simulated_position(world(HOUR + 3), squad(), ATLAS), (300.0, 0.0))

    def test_missing_anchor_names_the_place(self):
        ws = world(HOUR + 3)
        with self.assertRaises(ValueError) as cm:
            travel.simulated_position(ws, squad(), {"A": (0.0, 0.0)})
        self.assertIn("B", str(cm.exception))

    def test_missing_anchors_sorted(self):
        ws = world()
        self.assertEqual(travel.missing_anchors(ws, ATLAS), ["C"])
        self.assertEqual(travel.missing_anchors(ws, {}), ["A", "B", "C"])

    def test_distance(self):
        self.assertEqual(travel.distance_m((0.0, 0.0), (300.0, 400.0)), 500.0)


class BandTests(unittest.TestCase):
    def test_hysteresis_sequence(self):
        dists = [700, 450, 400, 450, 500, 501, 450, 400]
        self.assertEqual(travel.materialization(dists),
                         [False, False, True, True, True, False, False, True])

    def test_measured_scenario(self):
        ws = world(HOUR + 3)
        pos = travel.simulated_position(ws, squad(), ATLAS)     # (300, 0)
        live = False
        for player_x, want in ((943.0, False), (700.0, True), (780.0, True), (820.0, False)):
            d = travel.distance_m((player_x, 0.0), pos)
            live = travel.should_be_live(d, live)
            self.assertEqual(live, want, d)


class HandBackTests(unittest.TestCase):
    def test_progress_from_position(self):
        a, b = ATLAS["A"], ATLAS["B"]
        self.assertEqual(travel.progress_from_position(a, b, (300.0, 100.0)), 0.5)
        self.assertEqual(travel.progress_from_position(a, b, (-50.0, 0.0)), 0.0)
        self.assertEqual(travel.progress_from_position(a, b, (900.0, 0.0)), 1.0)
        self.assertEqual(travel.progress_from_position(a, a, (10.0, 0.0)), 0.0)

    def test_eta_from_progress(self):
        self.assertEqual(travel.eta_from_progress(hour=100, hours=6, f=0.5), 103)
        self.assertEqual(travel.eta_from_progress(hour=100, hours=6, f=1.0), 100)
        self.assertEqual(travel.eta_from_progress(hour=100, hours=6, f=0.0), 106)

    def test_eta_keeps_whole_hours_whole(self):
        # review of d8aea375: (1 - 6/7) * 7 is a hair above 1.0 in floats, and ceil made it two hours
        for hours in range(1, 13):
            for k in range(hours + 1):
                self.assertEqual(travel.eta_from_progress(100, hours, k / hours), 100 + hours - k, (hours, k))
        self.assertEqual(travel.eta_from_progress(100, 7, 0.3), 105)        # 4.9 hours to go rounds up to 5

    def test_eta_clamps_progress(self):
        self.assertEqual(travel.eta_from_progress(100, 6, -0.5), 106)
        self.assertEqual(travel.eta_from_progress(100, 6, 1.5), 100)

    def test_missing_at_anchor_raises_even_without_a_goal(self):
        with self.assertRaises(ValueError) as cm:
            travel.simulated_position(world(), squad(goal=None), {"B": (600.0, 0.0)})
        self.assertIn("A", str(cm.exception))


WORLDS = {"A": "w1", "B": "w1", "C": "w1", "X": "w2", "Y": "w2"}


def two_worlds(hour=HOUR):
    """w1: A-B-C, w2: X-Y, joined by the gateway edge B-X (48 hours). The atlas is w1's."""
    ws = world(hour)
    for pid in ("X", "Y"):
        ws.places[pid] = Place(id=pid, region="r2", kind="landmark")
    ws.routes += [Route("B", "C", 4), Route("X", "Y", 4), Route("B", "X", 48)]
    return ws


class InterWorldTests(unittest.TestCase):
    def test_gateway_edges(self):
        ws = two_worlds()
        self.assertEqual(travel.gateway_edges(ws, WORLDS), [("B", "X", 48)])
        self.assertEqual(travel.gateway_edges(ws, {}), [])
        self.assertEqual(travel.gateway_edges(ws, {"B": "w1"}), [])          # an end without a world: ordinary

    def test_leg_to_another_world_has_no_position(self):
        ws = two_worlds(HOUR + 27)
        for goal, eta in (("X", HOUR + 54), ("Y", HOUR + 58)):
            q = squad(goal=goal, eta=eta)
            self.assertTrue(travel.inter_world_leg(ws, q, WORLDS))
            self.assertIsNone(travel.position_in_world(ws, q, ATLAS, WORLDS, "w1"))
            self.assertIsNone(travel.position_in_world(ws, q, {"X": (0.0, 0.0)}, WORLDS, "w2"))
            with self.assertRaises(ValueError):                              # the old, accidental answer
                travel.simulated_position(ws, q, ATLAS)

    def test_leg_from_another_world_has_no_position(self):
        q = Squad(id="q2", faction="f1", size=3, at="Y", goal="A", eta=HOUR + 58)
        self.assertIsNone(travel.position_in_world(two_worlds(HOUR + 1), q, ATLAS, WORLDS, "w1"))

    def test_same_world_leg_through_a_gateway_has_no_position(self):
        ws = two_worlds(HOUR + 3)
        ws.places["D"] = Place(id="D", region="r1", kind="landmark")
        ws.routes = [Route("A", "B", 6), Route("B", "X", 1), Route("X", "Y", 4), Route("D", "Y", 2)]   # 13 hours
        worlds = {**WORLDS, "D": "w1"}
        atlas = {**ATLAS, "D": (900.0, 0.0)}
        q = squad(goal="D", eta=HOUR + 13)
        self.assertTrue(travel.inter_world_leg(ws, q, worlds))
        self.assertIsNone(travel.position_in_world(ws, q, atlas, worlds, "w1"))
        ws.routes.append(Route("C", "D", 3))                                  # A-B-C-D: 13 too, a tie
        self.assertIsNone(travel.position_in_world(ws, q, atlas, worlds, "w1"))
        ws.routes.append(Route("A", "D", 12))                                 # in-world and shorter
        q.eta = HOUR + 12
        self.assertFalse(travel.inter_world_leg(ws, q, worlds))
        self.assertEqual(travel.position_in_world(ws, q, atlas, worlds, "w1"), (225.0, 0.0))

    def test_squad_in_another_world_has_no_position(self):
        ws = two_worlds(HOUR + 2)
        for q in (Squad(id="q2", faction="f1", size=3, at="X", goal="Y", eta=HOUR + 4),
                  Squad(id="q3", faction="f1", size=3, at="X")):
            self.assertFalse(travel.inter_world_leg(ws, q, WORLDS))
            self.assertIsNone(travel.position_in_world(ws, q, ATLAS, WORLDS, "w1"))
        self.assertEqual(travel.position_in_world(ws, Squad(id="q2", faction="f1", size=3, at="X", goal="Y",
                                                            eta=HOUR + 4), {"X": (0.0, 0.0), "Y": (0.0, 80.0)},
                                                  WORLDS, "w2"), (0.0, 40.0))

    def test_in_world_leg_matches_simulated_position(self):
        ws = two_worlds(HOUR + 3)
        q = squad()
        self.assertFalse(travel.inter_world_leg(ws, q, WORLDS))
        self.assertEqual(travel.position_in_world(ws, q, ATLAS, WORLDS, "w1"), (300.0, 0.0))
        self.assertEqual(travel.position_in_world(ws, q, ATLAS, {}, "w1"), (300.0, 0.0))   # no worlds: as today

    def test_missing_in_world_anchor_still_raises(self):
        ws = two_worlds(HOUR + 3)
        for worlds in (WORLDS, {}):
            with self.assertRaises(ValueError) as cm:
                travel.position_in_world(ws, squad(), {"A": (0.0, 0.0)}, worlds, "w1")
            self.assertIn("B", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            travel.position_in_world(ws, squad(goal=None), {}, WORLDS, "w1")
        self.assertIn("A", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
