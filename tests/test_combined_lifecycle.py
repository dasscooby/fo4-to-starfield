"""The lifecycle fixture (3 Nov 2026, from the reference review on #32): one resupply job followed from its offer
to its one outcome through every way it can go wrong, plus the planner's materialize-once rule and the simulation's
reservation and catch-up properties. The cases are the rules the reference mods describe (SSaW's encounter tokens
and load recovery, StarSim's reservation and elapsed-time catch-up), written against what jobs.py, present.py and
sim.py do today. A case the modules did not honour was marked expectedFailure with the missing contract named; the
superseded-instance case was built from its mark on 4 Nov 2026 (Offer.read_at), so no mark is left.
Some cases restate tests of the module suites on purpose: the fixture reads as one story. Synthetic REGION packs;
placeholder names, not game facts."""
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
        ws.hour += 1                                         # still inside it an hour later (review of bfb6a142)
        short(ws)
        self.assertIsNone(resupply(ws))
        rebuilt = jobs.Offer(**{**o.to_dict(), "offered_hour": ws.hour})
        self.assertIn("superseded", jobs.valid(ws, rebuilt))   # read before the give-up, by another hour
        with self.assertRaises(ValueError):
            jobs.fail(ws, rebuilt)
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

    def superseded(self):
        """Two worlds where an instance of the resupply job was superseded by a later outcome for its id, and the
        need is back by a different amount. First: A read at hour 0, B read at hour 1 and handed in. Second: Z read
        at hour 0, A read at hour 1, Z handed in at hour 1 (A's offered hour is the newer one). Returns
        [(world, superseded instance, live instance)]."""
        ws, a = self.ws, self.offer
        ws.hour += 1
        b = resupply(ws)
        jobs.complete(ws, b)
        ws.hour += 1                                         # the need comes back an hour later, by another amount
        short(ws, stock=2)
        ws2 = quiet(world())
        short(ws2)
        z = resupply(ws2)
        ws2.hour += 1
        a2 = resupply(ws2)
        jobs.complete(ws2, z)
        ws2.hour += 1
        short(ws2, stock=2)
        return [(ws, a, resupply(ws)), (ws2, a2, resupply(ws2))]

    def test_the_same_need_comes_back_as_another_instance(self):
        """The preconditions of the superseded-instance case, outside its expectedFailure mark so that a change in
        how offers repeat fails loudly here instead of hiding under the mark (review of bfb6a142)."""
        for ws, stale, live in self.superseded():
            self.assertIsNotNone(live)
            self.assertEqual(live.id, stale.id)
            self.assertNotEqual(live.offered_hour, stale.offered_hour)
            self.assertNotEqual(live.detail["amount"], stale.detail["amount"])    # the stale amount differs
            self.assertEqual(len(done_events(ws, stale.id)), 1)

    def test_a_superseded_instance_is_refused(self):
        """SSaW's rule: a result for a token that is not the live one is ignored. An instance of a repeating job is
        refused once an outcome for its id was logged after the instance was read (Offer.read_at, by event-log
        position): the need it described was settled or given up after it, and handing it in would pay by its
        own, stale, amount. Both shapes from superseded() are refused without a trace while the live instance is
        good; a "newer offered hour wins" rule would miss the second shape (review of bfb6a142). Built on 4 Nov
        2026 from the expected failure the fixture recorded."""
        for ws, stale, live in self.superseded():
            fame = ws.reputation["settlers"].fame
            self.assertIn("superseded", jobs.valid(ws, stale))
            with self.assertRaises(ValueError):
                jobs.complete(ws, stale)
            self.assertEqual((len(done_events(ws, stale.id)), ws.reputation["settlers"].fame), (1, fame))
            self.assertIsNone(jobs.valid(ws, live))

    def test_a_need_back_within_the_hour_waits_for_the_next_hour(self):
        """A repeating id handed in is not offered again for the rest of the hour, whatever the stock does (the
        once-per-hour cap of #431, kept by the review of 084f68cc: it is the only limit on handing in, taking the
        goods back and handing in again). The next hour the need is a new instance with a later read_at."""
        ws, o = self.ws, self.offer
        jobs.complete(ws, o)
        short(ws)                                            # the farm is short again within the hour
        self.assertIsNone(resupply(ws))
        self.assertIn("already handed in", jobs.valid(ws, o))
        ws.hour += 1
        again = resupply(ws)
        self.assertEqual((again.id, again.offered_hour), (o.id, o.offered_hour + 1))
        self.assertGreater(again.read_at, o.read_at)
        self.assertIsNone(jobs.valid(ws, again))
        jobs.complete(ws, again)
        self.assertEqual(len(done_events(ws, o.id)), 2)
        with self.assertRaises(ValueError):
            jobs.complete(ws, again)

    def test_an_instance_read_after_the_save_pays_once_on_the_reloaded_world(self):
        """Review of 084f68cc (P1): the log grew after the save, then the instance was read, then the game went back
        to the save. Its own hand-in now lands below read_at, so the position rule alone would pay it again on every
        shortage; the offered-hour rule refuses it at any position."""
        ws = self.ws
        before = ws.to_json()
        lose(ws, "farm_a", "raiders")                        # unrelated events after the save
        later = resupply(ws)
        ws = WorldState.from_json(before)                    # the game reloaded the earlier save
        self.assertGreater(later.read_at, len(ws.events))
        jobs.complete(ws, later)
        short(ws)                                            # short again: the same instance must not pay twice
        self.assertIn("already handed in", jobs.valid(ws, later))
        with self.assertRaises(ValueError):
            jobs.complete(ws, later)
        self.assertEqual(len(done_events(ws, later.id)), 1)

    def test_a_give_up_logged_right_after_the_read_supersedes(self):
        """The position rule is inclusive: the first event after an instance was read can be an earlier instance's
        outcome (a give-up logs nothing else), and it supersedes the later-read instance, which only the position
        can tell (the earlier instance's offered hour is older); the window rule would refuse it too, so the reason
        says which (review of 084f68cc: an off-by-one here was caught by one test)."""
        ws, z = self.ws, self.offer                          # z read at hour 0
        ws.hour += 1
        a = resupply(ws)                                     # a read at hour 1
        self.assertEqual(len(ws.events), a.read_at)         # nothing logged since a was read
        jobs.fail(ws, z)                                     # z given up: the first event after a's read
        self.assertIn("superseded", jobs.valid(ws, a))

    def test_a_stale_instance_is_superseded_on_the_reloaded_world_too(self):
        """Delta review of bda0d0e3: a stale instance read from a longer log than the reloaded world's, and the live
        instance's hand-in an hour later landing below its read_at. The position rule cannot see it; the later
        offered hour on the outcome does (logged at that hour or after, so after the stale instance)."""
        ws = self.ws
        before = ws.to_json()
        for _ in range(4):                                   # the log grows well past the save
            lose(ws, "farm_a", "raiders")
        stale = resupply(ws)                                 # read at hour 0 from the longer log
        ws = WorldState.from_json(before)                    # back to the save
        ws.hour += 1
        short(ws, stock=2)                                   # the live need, by another amount
        live = resupply(ws)
        self.assertNotEqual(live.detail["amount"], stale.detail["amount"])
        jobs.complete(ws, live)
        done = [i for i, e in enumerate(ws.events) if e["kind"] == "job_done"]
        self.assertLess(done[-1], stale.read_at)            # the hand-in sits below the stale read
        short(ws)
        self.assertIn("superseded", jobs.valid(ws, stale))
        with self.assertRaises(ValueError):
            jobs.complete(ws, stale)
        self.assertEqual(len(done_events(ws, stale.id)), 1)

    def test_an_instance_from_a_later_hour_is_refused_on_an_earlier_world(self):
        """The mirror reload: the game went back to a save from before the instance was read, so the world has not
        reached the instance's offered hour. The giver has not made that offer here: neither door opens and nothing
        is logged, while the instance of this hour is still good."""
        ws = self.ws
        before = ws.to_json()
        ws.hour += 3
        future = resupply(ws)
        ws = WorldState.from_json(before)
        self.assertIn("later than the world", jobs.valid(ws, future))
        with self.assertRaises(ValueError):
            jobs.complete(ws, future)
        with self.assertRaises(ValueError):
            jobs.fail(ws, future)
        self.assertEqual(ws.to_json(), before)
        self.assertIsNone(jobs.valid(ws, self.offer))

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
        escorts = by_kind(jobs.offers(ws, "farm_a", limit=50), "escort")       # the one job that carries it
        self.assertEqual([e.detail["cargo"] for e in escorts], [out[0].cargo])


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
