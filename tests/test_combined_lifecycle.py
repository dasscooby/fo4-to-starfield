"""The lifecycle fixture (3 Nov 2026, from the reference review on #32): one resupply job followed from its offer
to its one outcome through every way it can go wrong, plus the planner's materialize-once rule and the simulation's
reservation and catch-up properties. The cases are the rules the reference mods describe (SSaW's encounter tokens
and load recovery, StarSim's reservation and elapsed-time catch-up), written against what jobs.py, present.py and
sim.py do today. A case the modules do not yet honour is marked expectedFailure with the missing contract named:
implementing it later turns the mark into an unexpected success, which fails the run until the mark is removed.
Synthetic REGION packs; placeholder names, not game facts."""
import unittest

from tests.test_combined_jobs import by_kind, lose, quiet, world  # noqa: E402  (puts src on the path)
from fo4sf.combined import jobs, present, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402


def short(ws, sid="farm_b", good="food", stock=1):
    ws.settlements[sid].stock[good] = stock


def resupply(ws, place="market"):
    found = by_kind(jobs.offers(ws, place), "resupply")
    return found[0] if found else None


def done_events(ws, offer_id):
    return [e for e in ws.events if e["kind"] == "job_done" and e.get("offer") == offer_id]


class ResupplyLifecycleTests(unittest.TestCase):
    """One resupply job at farm_b, offered by the settlers at the market."""

    def setUp(self):
        self.ws = quiet(world())
        short(self.ws)
        self.offer = resupply(self.ws)
        self.assertIsNotNone(self.offer)
        self.fame0 = self.ws.reputation["settlers"].fame
        self.stock0 = self.ws.settlements["farm_b"].stock["food"]

    def test_the_job_has_one_outcome_from_offer_to_hand_in(self):
        ws, o = self.ws, self.offer
        changed = jobs.complete(ws, o)
        self.assertEqual(changed["moved"], {"food": o.detail["amount"]})
        self.assertEqual(len(done_events(ws, o.id)), 1)
        self.assertGreater(ws.reputation["settlers"].fame, self.fame0)
        self.assertIsNone(resupply(ws))                      # the need is settled: not offered again this hour

    def test_stale_ownership_is_refused_while_it_lasts(self):
        ws, o = self.ws, self.offer
        lose(ws, "farm_b", "raiders")                        # the holder changed under the open job
        self.assertIn("no longer the giver's", jobs.valid(ws, o))
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)
        self.assertEqual(done_events(ws, o.id), [])
        self.assertEqual(ws.reputation["settlers"].fame, self.fame0)
        self.assertEqual(ws.settlements["farm_b"].stock["food"], self.stock0)
        ws.places["farm_b"].holder = "settlers"              # the giver has it back: the same need is work again
        self.assertIsNone(jobs.valid(ws, o))
        self.assertEqual(resupply(ws).id, o.id)

    def test_cancel_is_one_outcome_and_closes_both_doors(self):
        ws, o = self.ws, self.offer
        self.assertEqual(jobs.fail(ws, o), jobs.FAIL_INFAMY["resupply"])
        with self.assertRaises(ValueError):
            jobs.fail(ws, o)
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)
        self.assertEqual(done_events(ws, o.id), [])
        self.assertIsNone(resupply(ws))                      # given up: not offered again inside its window
        ws.hour = o.expires_hour
        short(ws)
        later = resupply(ws)                                 # the window over, the need is new work
        self.assertEqual((later.id, later.offered_hour), (o.id, o.expires_hour))

    def test_a_late_hand_in_is_refused_without_a_trace(self):
        ws, o = self.ws, self.offer
        ws.hour = o.expires_hour
        self.assertIn("expired", jobs.valid(ws, o))
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)
        self.assertEqual(done_events(ws, o.id), [])
        self.assertEqual(ws.reputation["settlers"].fame, self.fame0)
        self.assertEqual(ws.settlements["farm_b"].stock["food"], self.stock0)

    def test_a_replayed_outcome_pays_nothing(self):
        ws, o = self.ws, self.offer
        jobs.complete(ws, o)
        fame1 = ws.reputation["settlers"].fame
        for _ in range(3):                                   # the hand-in replayed: a settled token pays nothing
            with self.assertRaises(ValueError):
                jobs.complete(ws, o)
        short(ws)                                            # even once the farm is short again
        with self.assertRaises(ValueError):
            jobs.complete(ws, o)
        self.assertEqual((ws.reputation["settlers"].fame, len(done_events(ws, o.id))), (fame1, 1))

    @unittest.expectedFailure
    def test_a_stale_instance_is_refused_once_a_newer_one_settled_the_need(self):
        """Contract gap, SSaW's rule: a result for a token that is not the live one is ignored. Offer A at hour 0
        is not handed in; the same need is offered again at hour 1 as B (the same id, a newer offered hour) and B
        is handed in; the farm runs short again. Handing in the old A should be refused: its instance was
        superseded, and it would pay by its stale amount. jobs.valid accepts it today, because its checks are the
        world's need and the outcome log, and A's instance has no outcome of its own."""
        ws, a = self.ws, self.offer
        ws.hour += 1
        b = resupply(ws)
        self.assertEqual((b.id, b.offered_hour), (a.id, a.offered_hour + 1))
        jobs.complete(ws, b)
        short(ws)
        self.assertIsNotNone(jobs.valid(ws, a))

    def test_a_hand_in_is_acknowledged_by_the_save(self):
        """Restart before acknowledgement: the save is the acknowledgement. A save made after the hand-in refuses
        it again; a save made before it is a world where the job is still open, where the hand-in happens exactly
        once and ends in the same world."""
        ws, o = self.ws, self.offer
        before = ws.to_json()
        jobs.complete(ws, o)
        after = WorldState.from_json(ws.to_json())
        self.assertIn("already handed in", jobs.valid(after, o))
        with self.assertRaises(ValueError):
            jobs.complete(after, o)
        self.assertEqual(after.to_json(), ws.to_json())
        earlier = WorldState.from_json(before)               # the game reloaded a save from before the hand-in
        self.assertIsNone(jobs.valid(earlier, o))
        jobs.complete(earlier, o)
        self.assertEqual(len(done_events(earlier, o.id)), 1)
        with self.assertRaises(ValueError):
            jobs.complete(earlier, o)
        self.assertEqual(earlier.to_json(), ws.to_json())


class CatchUpTests(unittest.TestCase):
    def test_the_same_hours_in_any_batching_give_the_same_world_and_offers(self):
        """StarSim advances unloaded activity by elapsed time and SSaW's turns run on game time; a throttled or
        paused simulation catches up later. Our ticks give one world whether 48 hours pass as one call, two or
        eight (the RNG is seeded per hour), so a catch-up changes nothing but when it ran."""
        worlds = []
        for steps in ((48,), (24, 24), (6,) * 8):
            ws = world(3)
            for h in steps:
                sim.run(ws, h)
            worlds.append((ws.to_json(), [o.to_dict() for o in jobs.offers(ws, "market", limit=50)]))
        self.assertEqual(worlds[0], worlds[1])
        self.assertEqual(worlds[0], worlds[2])


class ReservationTests(unittest.TestCase):
    def test_a_caravan_takes_its_cargo_out_of_stock_at_dispatch(self):
        """StarSim reserves stock per job until pickup or loss. Here the cargo leaves the source's stock when the
        caravan leaves, so no second job can carry the same food, and one caravan per source is out at a time."""
        ws = quiet(world())
        s = ws.settlements["farm_a"]
        s.roles["trader"] = max(1, s.roles.get("trader", 0))
        s.stock["food"] = 3 * s.population + 40
        before = s.stock["food"]
        sim._dispatch_caravans(ws)
        out = [q for q in ws.squads.values() if q.kind == "caravan" and q.at == "farm_a"]
        self.assertEqual(len(out), 1)
        self.assertEqual(s.stock["food"], before - out[0].cargo["food"])
        sim._dispatch_caravans(ws)
        self.assertEqual(len([q for q in ws.squads.values() if q.kind == "caravan" and q.at == "farm_a"]), 1)


class MaterializeOnceTests(unittest.TestCase):
    def test_a_plan_names_each_group_once_and_replanning_spawns_nothing(self):
        """StarSim pools and re-activates objects by identity. A slot's id is the L2 entity's own id, so the same
        world planned twice is one set of slots and the difference is empty: a duplicate activation is one slot."""
        ws = world(2)
        sim.run(ws, 10 * 24)
        for place in sorted(ws.places)[:4]:
            p = present.plan(ws, place)
            ids = [s.id for s in p.slots + p.dropped]
            self.assertEqual(len(ids), len(set(ids)), place)
            d = present.diff(p, present.plan(ws, place))
            self.assertEqual((d.spawn, d.dissolve), ([], []), place)
            self.assertEqual(len(d.keep), len(p.slots), place)

    def test_every_slot_has_a_live_owner_in_the_simulation(self):
        """A dissolve must find what it came from: every slot names a place the world has, a faction it has, and
        for a squad or caravan a squad it still has."""
        ws = world(5)
        sim.run(ws, 10 * 24)
        seen = 0
        for place in sorted(ws.places)[:4]:
            for s in present.plan(ws, place).slots:
                seen += 1
                self.assertIn(s.place, ws.places)
                if s.faction not in (None, "player"):
                    self.assertIn(s.faction, ws.factions)
                if s.kind in ("squad", "caravan"):
                    self.assertIn(s.id.split(":", 1)[1], ws.squads)
        self.assertGreater(seen, 0)


if __name__ == "__main__":
    unittest.main()
