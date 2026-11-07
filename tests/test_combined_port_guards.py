"""The two guards the C++ port needs from the Python model (docs/combined-core-cpp-port.md section 5, step 1): the
per-tick RNG seed fits in 64 unsigned bits, and every id is ASCII (byte order is then Python's sort order). Synthetic
packs only."""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.combined import fixtures, model, pack, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402


def world(seed=1):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    return ws


class PortGuardTests(unittest.TestCase):
    def test_the_rng_seed_must_fit_in_64_unsigned_bits(self):
        self.assertEqual(sim.rng_seed(0, 0), 0)
        top = (2 ** 64 - 1) // 1_000_003
        self.assertEqual(sim.rng_seed(top, 0), top * 1_000_003)
        for seed, hour in ((-1, 0), (top + 1, 0), (0, 2 ** 64)):
            with self.subTest(seed=seed, hour=hour), self.assertRaisesRegex(ValueError, "outside 0 to 2"):
                sim.rng_seed(seed, hour)
        ws = world(seed=-3)
        with self.assertRaisesRegex(ValueError, "outside"):
            sim.tick(ws)                                         # refused before any draw

    def test_a_saved_state_outside_the_range_does_not_load(self):
        ws = world()
        good = json.loads(ws.to_json())
        self.assertEqual(WorldState.from_json(json.dumps(good)).seed, 1)
        for seed in (-1, 2 ** 64):
            with self.subTest(seed=seed), self.assertRaisesRegex(ValueError, "outside the RNG's range"):
                WorldState.from_json(json.dumps(dict(good, seed=seed)))

    def test_ids_must_be_ascii(self):
        p = copy.deepcopy(fixtures.REGION_1)
        p["places"][0]["id"] = "farm_ä"
        p["settlements"][0]["place"] = "farm_ä"
        self.assertTrue(pack.validate_pack(p))
        with self.assertRaises(ValueError):
            model.load_pack(WorldState(seed=1), p)
        good = json.loads(world().to_json())
        good["places"]["farm_ä"] = dict(good["places"]["ruins"], id="farm_ä")
        with self.assertRaisesRegex(ValueError, "must be ASCII"):
            WorldState.from_json(json.dumps(good))


if __name__ == "__main__":
    unittest.main()
