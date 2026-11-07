"""The combined core's C++ port (sfse/FOCCSim) against the Python reference (src/fo4sf/combined): the same state, the
same ticks and the same player actions give byte-identical canonical JSON after every tick
(docs/combined-core-cpp-port.md section 2, the parity contract). The repo's first compiled test: the portable core is
built with the C++ compiler on PATH (g++ or clang++; CI's ubuntu has g++) into a temporary folder, and the test is
skipped where there is none (the PC builds with cl.exe through the plugin's own script later).

By default: the two-region fixture for seeds 0 to 9 over 90 days, its variants (raid pressure low and high, story mode
with an active story, scripted player actions) for seed 0, and the Commonwealth-scale draft for 30 days, each compared
once per game day and at the end. With FO4SF_PARITY_FULL=1: after every tick, every variant for seeds 0 to 9, and the
Commonwealth-scale draft for 90 days, as the plan asks."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fo4sf.combined import fixtures, model, seedpack, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402

SOURCES = [os.path.join(ROOT, "sfse", "FOCCSim", n) for n in ("foccsim.cpp", "main.cpp")] + \
          [os.path.join(ROOT, "sfse", "FOCCSidecar", "sha256.cpp")]
FULL = os.environ.get("FO4SF_PARITY_FULL") == "1"
DAY = 4                                                          # ticks per game day (sim.TICK_HOURS = 6)
ACTIONS = [{"hour": 24, "do": "help", "faction": "settlers", "amount": 15},
           {"hour": 48, "do": "defend", "place": "farm_b"},
           {"hour": 60, "do": "trade", "settlement": "market", "goods": {"food": 25, "ammo": -5}},
           {"hour": 300, "do": "defend", "place": "market", "bonus": 30, "hours": 24},
           {"hour": 500, "do": "trade", "settlement": "farm_a", "goods": {"water": 40}}]


def compiler():
    for name in (os.environ.get("CXX"), "g++", "clang++"):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


def fixture_world(seed, **settings):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    for k, v in settings.items():
        setattr(ws.settings, k, v)
    return ws


def apply(ws, a):
    """tests' copy of foccsim::apply_action: the same three player hooks, before the tick of that hour."""
    if a["do"] == "help":
        sim.player_helped(ws, a["faction"], a.get("amount", 10))
    elif a["do"] == "defend":
        sim.player_defended(ws, a["place"], a.get("bonus", 10), a.get("hours", 72))
    else:
        sim.player_traded(ws, a["settlement"], a["goods"])


@unittest.skipUnless(compiler(), "no C++ compiler on PATH (g++ or clang++); the PC builds the core with cl.exe")
class CppParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="foccsim-")
        cls.exe = os.path.join(cls.tmp, "foccsim.exe" if os.name == "nt" else "foccsim")
        # -ffp-contract=off: no fused multiply-add may change a rounding (section 3, "Floats")
        r = subprocess.run([compiler(), "-std=c++17", "-O2", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror",
                            "-o", cls.exe, *SOURCES], capture_output=True, text=True)
        if r.returncode:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise AssertionError("the portable core does not build:\n" + r.stdout + r.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def native(self, ws, ticks, actions=(), *extra):
        d = tempfile.mkdtemp(dir=self.tmp)
        state, acts = os.path.join(d, "state.json"), os.path.join(d, "actions.json")
        with open(state, "w", encoding="utf-8") as f:
            f.write(ws.to_json())
        with open(acts, "w", encoding="utf-8") as f:
            json.dump(list(actions), f)
        r = subprocess.run([self.exe, state, str(ticks), "--actions", acts, *extra], capture_output=True, text=True)
        return r, d, state

    def parity(self, name, ws, ticks, actions=(), every=1 if FULL else DAY):
        """Run both and compare the sha256 of the canonical JSON after every `every`-th tick (and the last); at the
        first that differs, show both texts around the first differing byte."""
        start = ws.to_json()
        r, d, state = self.native(ws, ticks, actions)
        self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), ticks, name)
        for t in range(1, ticks + 1):
            for a in actions:
                if a["hour"] == ws.hour:
                    apply(ws, a)
            sim.tick(ws)
            if t % every and t != ticks:
                continue
            text = ws.to_json()
            n, hour, digest = lines[t - 1].split()
            if digest != hashlib.sha256(text.encode()).hexdigest():
                out = os.path.join(d, "native.json")
                with open(state, "w", encoding="utf-8") as f:
                    f.write(start)
                subprocess.run([self.exe, state, str(t), "--actions", os.path.join(d, "actions.json"), "--out", out])
                with open(out, encoding="utf-8") as f:
                    theirs = f.read()
                at = next((k for k in range(min(len(text), len(theirs))) if text[k] != theirs[k]),
                          min(len(text), len(theirs)))
                self.fail(f"{name}: tick {t} (hour {ws.hour}) differs at byte {at}:\n"
                          f"  Python: ...{text[max(0, at - 160):at + 160]}...\n"
                          f"  C++:    ...{theirs[max(0, at - 160):at + 160]}...")
            self.assertEqual((int(n), int(hour)), (t, ws.hour), name)

    def test_the_fixture_world_for_ten_seeds_over_90_days(self):
        for seed in range(10):
            with self.subTest(seed=seed):
                self.parity(f"fixture seed {seed}", fixture_world(seed), 90 * DAY)

    def test_raid_pressure_story_mode_and_player_actions(self):
        variants = [("raid low", {"raid_pressure": "low"}, ()), ("raid high", {"raid_pressure": "high"}, ()),
                    ("story mode", {"story_mode": True, "active_stories": ["main_story_1"]}, ()),
                    ("player actions", {}, ACTIONS)]
        for seed in (range(10) if FULL else (0,)):
            for name, settings, actions in variants:
                with self.subTest(seed=seed, variant=name):
                    self.parity(f"{name} seed {seed}", fixture_world(seed, **settings), 90 * DAY, actions)

    def test_the_commonwealth_scale_draft(self):
        from test_combined_seedpack import commonwealth_scale_draft
        pack, _report = seedpack.generate(commonwealth_scale_draft())
        for seed in (range(10) if FULL else (0,)):
            with self.subTest(seed=seed):
                ws = WorldState(seed=seed)
                model.load_pack(ws, copy.deepcopy(pack))
                self.assertGreater(len(ws.places), 200)
                self.parity(f"Commonwealth-scale seed {seed}", ws, (90 if FULL else 30) * DAY)

    def test_the_state_is_read_and_written_back_byte_for_byte(self):
        ws = fixture_world(3)
        sim.run(ws, 10 * 24)
        ws.events.append({"hour": ws.hour, "kind": "note", "place": "market", "region": "R1",
                          "text": 'quote " back\\slash \t tab é ✓ 😀 \x01 \x7f', "flag": False, "none": None,
                          "list": [1, -2, {"b": 1, "a": [True]}], "empty": {}})
        out = os.path.join(self.tmp, "back.json")
        r, _d, _state = self.native(ws, 0, (), "--out", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(f.read(), ws.to_json())

    def test_the_core_refuses_what_python_refuses(self):
        good = json.loads(fixture_world(1).to_json())
        cases = {
            "seed and hour are outside": dict(good, seed=-1),
            "integers only": json.loads(json.dumps(good).replace('"defence": 2', '"defence": 2.5', 1)),
            "unknown field": dict(good, places=dict(good["places"], ruins=dict(good["places"]["ruins"], extra=1))),
            "unknown schema": dict(good, schema=9),
            "must be ASCII": dict(good, places=dict(good["places"], **{"rüins": dict(good["places"]["ruins"],
                                                                                      id="rüins")})),
            "unknown raid pressure": dict(good, settings=dict(good["settings"], raid_pressure="extreme")),
        }
        for why, state in cases.items():
            with self.subTest(why=why):
                p = os.path.join(self.tmp, "bad.json")
                with open(p, "w", encoding="utf-8") as f:
                    f.write(json.dumps(state))
                r = subprocess.run([self.exe, p, "1"], capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, r.stdout)
                self.assertIn(why, r.stderr)


if __name__ == "__main__":
    unittest.main()
