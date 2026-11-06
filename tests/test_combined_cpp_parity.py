"""The combined core's C++ port (sfse/FOCCSim) against the Python reference (src/fo4sf/combined): the same state, the
same ticks and the same player actions give byte-identical canonical JSON after every tick
(docs/combined-core-cpp-port.md section 2, the parity contract), and the same engine adapter output (step C2: the
record plan and game view, then every tick's writes). The repo's first compiled test: the portable core is
built with the C++ compiler on PATH (g++ or clang++; CI's ubuntu has g++) into a temporary folder, and the test is
skipped where there is none. FOCCSIM_EXE=<path> runs the same tests against a core built elsewhere instead (the PC's
MSVC build).

By default: the two-region fixture for seeds 0 to 9 over 90 days, its variants (raid pressure low and high, story mode
with an active story, scripted player actions) for seed 0, and the Commonwealth-scale draft for 30 days, each compared
once per game day and at the end. With FO4SF_PARITY_FULL=1: after every tick, every variant for seeds 0 to 9, and the
Commonwealth-scale draft for 90 days, as the plan asks."""
import copy
import dataclasses
import glob
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
from fo4sf.combined import adapter, fixtures, model, present, seedpack, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402

SOURCES = sorted(glob.glob(os.path.join(ROOT, "sfse", "FOCCSim", "*.cpp"))) + \
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


def canonical(value):
    return json.dumps(value, sort_keys=True)                      # WorldState.to_json's form


def diff_at(a, b):
    """The first index where the two texts differ (the shorter one's length when one is a prefix of the other)."""
    return next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))


def adapter_start(ws, plan):
    """The first line of foccsim --adapter: the writes from nothing, the record plan and the game view."""
    view = adapter.game_view(ws, plan)
    return canonical({"changes": adapter.changes(None, view), "plan": plan.to_dict(), "view": view}), view


def walk_for(ws, ticks):
    """Where the player stands for the presentation planner (step C3): a start, then one route step along the sorted
    neighbours each tick; every 5th tick a wide view on a small budget (so slots are dropped), and every 7th tick a
    second look from somewhere else (a fast travel) at the same tick. Routes never change, so the walk is fixed up
    front."""
    places = sorted(ws.places)
    here = sorted(ws.settlements)[0] if ws.settlements else places[0]
    out = [{"tick": 0, "place": here, "radius": present.RADIUS_HOURS, "max_actors": present.MAX_LIVE_ACTORS}]
    for t in range(1, ticks + 1):
        near = ws.neighbours(here)
        if near:
            here = near[t % len(near)][0]
        wide = t % 5 == 0
        out.append({"tick": t, "place": here, "radius": 24 if wide else present.RADIUS_HOURS,
                    "max_actors": 15 if wide else present.MAX_LIVE_ACTORS})
        if t % 7 == 0:
            out.append({"tick": t, "place": places[t % len(places)], "radius": 12, "max_actors": 40})
    return out


def present_lines(ws, walk, t, shown, out):
    """present.plan and present.diff for the walk's entries at tick t, as foccsim --present writes them; returns the
    plan shown last."""
    for w in walk:
        if w["tick"] != t:
            continue
        new = present.plan(ws, w["place"], w["radius"], w["max_actors"])
        d = present.diff(shown, new)
        out.append(canonical([t, new.to_dict(), {k: [dataclasses.asdict(x) for x in getattr(d, k)]
                                                 for k in ("spawn", "keep", "dissolve")}]))
        shown = new
    return shown


def apply(ws, a):
    """tests' copy of foccsim::apply_action: the same three player hooks, before the tick of that hour."""
    if a["do"] == "help":
        sim.player_helped(ws, a["faction"], a.get("amount", 10))
    elif a["do"] == "defend":
        sim.player_defended(ws, a["place"], a.get("bonus", 10), a.get("hours", 72))
    else:
        sim.player_traded(ws, a["settlement"], a["goods"])


PREBUILT = os.environ.get("FOCCSIM_EXE")                        # a core built elsewhere, e.g. by MSVC on the PC


@unittest.skipUnless(PREBUILT or compiler(),
                     "no C++ compiler on PATH (g++ or clang++), and FOCCSIM_EXE names no prebuilt core")
class CppParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="foccsim-")
        if PREBUILT:
            if not os.path.isfile(PREBUILT):
                shutil.rmtree(cls.tmp, ignore_errors=True)
                raise AssertionError(f"FOCCSIM_EXE={PREBUILT} is not a file")
            cls.exe = os.path.abspath(PREBUILT)
            return
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

    def native(self, ws, ticks, actions=(), *extra, walk=()):
        """Run the core on `ws`; the engine adapter's lines go to adapter.jsonl beside the state, and the presentation
        planner's lines for `walk` to present.jsonl."""
        d = tempfile.mkdtemp(dir=self.tmp)
        state, acts, walk_p = (os.path.join(d, n) for n in ("state.json", "actions.json", "walk.json"))
        with open(state, "w", encoding="utf-8") as f:
            f.write(ws.to_json())
        with open(acts, "w", encoding="utf-8") as f:
            json.dump(list(actions), f)
        with open(walk_p, "w", encoding="utf-8") as f:
            json.dump(list(walk), f)
        r = subprocess.run([self.exe, state, str(ticks), "--actions", acts, "--adapter", os.path.join(d, "adapter.jsonl"),
                            "--walk", walk_p, "--present", os.path.join(d, "present.jsonl"), *extra],
                           capture_output=True, text=True)
        return r, d, state

    def lines(self, d, name="adapter.jsonl"):
        with open(os.path.join(d, name), encoding="utf-8") as f:
            text = f.read()
        if not text:
            return []
        self.assertTrue(text.endswith("\n"))
        return text[:-1].split("\n")

    adapter_lines = lines

    def same_lines(self, name, what, want, got, label=lambda k: "start" if k == 0 else f"tick {k}"):
        for k, (w, g) in enumerate(zip(want, got)):
            if w != g:
                at = diff_at(w, g)
                self.fail(f"{name}: {what}'s {label(k)} differs at byte {at}:\n"
                          f"  Python: ...{w[max(0, at - 160):at + 160]}...\n"
                          f"  C++:    ...{g[max(0, at - 160):at + 160]}...")
        self.assertEqual(len(got), len(want), name)

    def same_adapter_lines(self, name, want, got):
        self.same_lines(name, "the engine adapter", want, got)

    def parity(self, name, ws, ticks, actions=(), every=1 if FULL else DAY):
        """Run both and compare the sha256 of the canonical JSON after every `every`-th tick (and the last); at the
        first that differs, show both texts around the first differing byte. The engine adapter (step C2) is
        compared after every tick: its record plan and game view at the start, then each tick's writes, which add up
        to the game view after every tick."""
        start = ws.to_json()
        plan = adapter.record_plan(ws)
        first, view = adapter_start(ws, plan)
        want = [first]
        walk, shown_want = walk_for(ws, ticks), []
        shown = present_lines(ws, walk, 0, None, shown_want)
        r, d, state = self.native(ws, ticks, actions, walk=walk)
        self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), ticks, name)
        for t in range(1, ticks + 1):
            for a in actions:
                if a["hour"] == ws.hour:
                    apply(ws, a)
            sim.tick(ws)
            new = adapter.game_view(ws, plan)
            want.append(canonical([t, adapter.changes(view, new)]))
            view = new
            shown = present_lines(ws, walk, t, shown, shown_want)
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
                at = diff_at(text, theirs)
                self.fail(f"{name}: tick {t} (hour {ws.hour}) differs at byte {at}:\n"
                          f"  Python: ...{text[max(0, at - 160):at + 160]}...\n"
                          f"  C++:    ...{theirs[max(0, at - 160):at + 160]}...")
            self.assertEqual((int(n), int(hour)), (t, ws.hour), name)
        self.same_adapter_lines(name, want, self.adapter_lines(d))
        self.same_lines(name, "the presentation planner", shown_want, self.lines(d, "present.jsonl"),
                        lambda k: f"walk entry {k} (tick {walk[k]['tick']}, at {walk[k]['place']})")

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

    def test_the_engine_adapter_with_other_characters_settings_and_tiers(self):
        """Editor ids from ids with other characters and one exactly at the length limit, every setting's value, the
        reputation thresholds, then 30 days of ticks; and the record plan under a second prefix."""
        ws = fixture_world(2, survival="light", raid_pressure="low", story_mode=True)   # story mode, no story active
        at_limit = "a" * (adapter.EDITOR_ID_MAX - len("FOCC_Place_"))
        model.load_pack(ws, {"places": [{"id": "farm-c", "region": "R1", "kind": "landmark"},
                                        {"id": "ruin.2 x", "region": "R1", "kind": "base", "holder": "raiders"},
                                        {"id": at_limit, "region": "R1", "kind": "landmark"}],
                             "routes": [{"a": "farm-c", "b": "market", "hours": 6},
                                        {"a": "ruin.2 x", "b": "ruins", "hours": 6}]})
        for fid, (fame, infamy) in {"settlers": (10, 9), "raiders": (49, 50), "order": (-5, 10 ** 12),
                                    "traders": (25, 24)}.items():
            ws.reputation[fid].fame, ws.reputation[fid].infamy = fame, infamy
        r, d, _state = self.native(ws, 0, (), "--prefix", "X_")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.same_adapter_lines("prefix X_", [adapter_start(ws, adapter.record_plan(ws, "X_"))[0]],
                                self.adapter_lines(d))
        self.parity("other characters", ws, 30 * DAY)
        for settings in ({"survival": "full", "story_mode": True, "active_stories": ["main_story_1"]},
                         {"story_mode": False, "active_stories": ["main_story_1"]}):   # a story outside story mode
            with self.subTest(settings=settings):
                ws = fixture_world(0, **settings)
                r, d, _state = self.native(ws, 0)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.same_adapter_lines(str(settings), [adapter_start(ws, adapter.record_plan(ws))[0]],
                                        self.adapter_lines(d))

    def test_the_engine_adapter_refuses_what_python_refuses(self):
        clash = fixture_world(1)
        clash.places["farm-a"] = model.Place(id="farm-a", region="R1", kind="landmark")      # farm_a after sanitising
        too_long = fixture_world(1)
        pid = "b" * (adapter.EDITOR_ID_MAX - len("FOCC_Place_") + 1)
        too_long.places[pid] = model.Place(id=pid, region="R1", kind="landmark")
        cases = [("collides", clash, adapter.PREFIX), ("longer than 64", too_long, adapter.PREFIX),
                 ("invalid editor id", fixture_world(1), "1X_")]
        for why, ws, prefix in cases:
            with self.subTest(why=why):
                with self.assertRaisesRegex(ValueError, why) as cm:
                    adapter.record_plan(ws, prefix)
                r, _d, _state = self.native(ws, 1, (), "--prefix", prefix)
                self.assertEqual(r.returncode, 2, r.stdout)
                self.assertIn(str(cm.exception), r.stderr)                            # Python's message, word for word

    def test_the_presentation_planner_ranks_budgets_and_caps(self):
        """The player's own garrison (ranked last at its distance), a role above the per-role cap, and budgets that
        cut at each slot boundary, all from the same place at the start; then 10 days of ticks on that world."""
        ws = fixture_world(0)
        sim.player_defended(ws, "market", 30, 72)                      # a "player" squad of 30 at the market
        ws.settlements["market"].roles["farmer"] = 9                   # above SETTLERS_PER_ROLE_MAX
        walk = [{"tick": 0, "place": "market", "radius": r, "max_actors": m}
                for r, m in ((0, 40), (6, 40), (6, 9), (6, 10), (6, 0), (12, 100), (48, 25))]
        want, shown = [], None
        shown = present_lines(ws, walk, 0, shown, want)
        r, d, _state = self.native(ws, 0, walk=walk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.same_lines("ranks and budgets", "the presentation planner", want, self.lines(d, "present.jsonl"),
                        lambda k: f"walk entry {k}")
        self.parity("defended market", ws, 10 * DAY)

    def test_the_presentation_planner_refuses_an_unknown_place(self):
        ws = fixture_world(0)
        with self.assertRaisesRegex(KeyError, "unknown place 'nowhere'"):
            present.plan(ws, "nowhere")
        r, _d, _state = self.native(ws, 1, walk=[{"tick": 1, "place": "nowhere", "radius": 6, "max_actors": 40}])
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("unknown place 'nowhere'", r.stderr)

    def test_the_presentation_planner_escapes_garrison_id_components(self):
        """#641: places and holders whose ids hold the separator (the AMBIGUOUS pairs of test_combined_present_ids)
        and a place literally named region%3Acamp, walked from region and its neighbours on budgets that keep, drop
        and respawn slots; the plans and diffs match line by line, so the escaped garrison ids match too.

        diff()'s duplicate-id refusal (ValueError in Python, std::invalid_argument and exit 2 in the core) has no
        parity case: foccsim only diffs plans that plan() built, and plan() cannot give two slots one id (garrison
        ids are escaped, a settler's role holds no ':', squad ids are the squads' keys), so the walk cannot feed
        the core a plan with duplicate ids. test_combined_present_ids covers the refusal on the Python side."""
        from test_combined_present_ids import AMBIGUOUS, world as id_world
        ws = id_world(AMBIGUOUS + [("region%3Acamp", "raiders")])
        walk = [{"tick": 0, "place": p, "radius": r, "max_actors": m}
                for p, r, m in (("region", 6, 100), ("region", 2, 3), ("region:camp", 2, 9), ("region%3Acamp", 2, 6),
                                ("region", 2, 0), ("region", 2, 100), ("region:camp", 1, 100))]
        want = []
        present_lines(ws, walk, 0, None, want)
        self.assertIn("garrison:region%3Acamp:raiders", want[0])
        self.assertIn("garrison:region:camp%3Araiders", want[0])
        self.assertIn("garrison:region%253Acamp:raiders", want[0])
        r, d, _state = self.native(ws, 0, walk=walk)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.same_lines("escaped ids", "the presentation planner", want, self.lines(d, "present.jsonl"),
                        lambda k: f"walk entry {k}")


if __name__ == "__main__":
    unittest.main()
