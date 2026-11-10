"""The combined core's C++ port (sfse/FOCCSim) against the Python reference (src/fo4sf/combined): the same state, the
same ticks and the same player actions give byte-identical canonical JSON after every tick
(docs/combined-core-cpp-port.md section 2, the parity contract), and the same engine adapter output (step C2: the
record plan and game view, then every tick's writes), presentation plans (C3: for a player walking the world) and
results of the player's actions (C4: settlement management and radiant jobs, refusals included; C5: the news and
its terminal page, with a fuzz test of the textwrap port). The repo's first compiled test: the portable core is
built with CXX or a C++ compiler on PATH (c++, g++ or clang++) into a temporary folder. Without a compiler,
the test fails in CI and skips locally. FOCCSIM_EXE=<path> runs the same tests against a core built elsewhere instead
(the PC's MSVC build).

By default: the two-region fixture for seeds 0 to 9 over 90 days, its variants (raid pressure low and high, story mode
with an active story, scripted player actions) for seed 0, and the Commonwealth-scale draft for 30 days, each compared
once per game day and at the end. With FO4SF_PARITY_FULL=1: after every tick, every variant for seeds 0 to 9, and the
Commonwealth-scale draft for 90 days, as the plan asks. Seeds 2**32 and 2**32 + 7 also run with settlement priorities
and regional reputation for 8 days (90 in FULL), always compared after every tick."""
import copy
import dataclasses
import glob
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fo4sf.combined import adapter, fixtures, jobs, manage, model, news, present, seedpack, sim  # noqa: E402
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
    for name in (os.environ.get("CXX"), "c++", "g++", "clang++"):
        if name and (path := shutil.which(name)):
            return path
    return None


def fixture_world(seed, **settings):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    for k, v in settings.items():
        setattr(ws.settings, k, v)
    return ws


def layered_world(seed):
    """Non-default Settlement.priority and WorldState.regional_reputation, with jobs in both regions."""
    ws = fixture_world(seed)
    manage.set_priority(ws, "market", "food")
    manage.set_priority(ws, "river_town", "water")
    ws.regional_reputation = {
        "R1": {"settlers": model.Reputation(fame=9, infamy=24), "raiders": model.Reputation(infamy=49)},
        "R2": {"settlers": model.Reputation(fame=24, infamy=9), "traders": model.Reputation(infamy=25)},
    }
    ws.settlements["market"].stock["food"] = 1       # a guaranteed resupply job, so its reward reaches both layers
    ws.squads["s900"] = model.Squad(id="s900", faction="slavers", size=3, at="slaver_pit", goal="river_town",
                                    kind="attack", eta=12)   # a defence job to give up: nonzero regional infamy
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


def run(ws, a, last):
    """One scripted action, as foccsim's run_action does it: the player hooks (help, defend, trade), manage's
    settlement actions (assign, beds, priority, send, status, threats), the radiant jobs (offers; complete or fail
    one of the last offers by position, nothing past the end, or an offer given in full), the news at a place (items
    and terminal page), and textwrap and str.upper on their own (wrap, shorten, upper). Returns the line foccsim --results writes: the result,
    or the ValueError's message."""
    do = a["do"]
    try:
        if do == "help":
            r = sim.player_helped(ws, a["faction"], a.get("amount", 10))
        elif do == "defend":
            r = sim.player_defended(ws, a["place"], a.get("bonus", 10), a.get("hours", 72))
        elif do == "trade":
            r = sim.player_traded(ws, a["settlement"], a["goods"])
        elif do == "assign":
            r = manage.assign_role(ws, a["settlement"], a["from"], a["to"], a.get("n", 1))
        elif do == "beds":
            r = manage.add_beds(ws, a["settlement"], a.get("n", 1))
        elif do == "priority":
            r = manage.set_priority(ws, a["settlement"], a.get("good"))
        elif do == "send":
            r = manage.send_supplies(ws, a["from"], a["to"], a["goods"])
        elif do == "status":
            r = manage.status(ws, a["settlement"])
        elif do == "threats":
            r = manage.threats(ws, a["settlement"], a.get("hours", manage.THREAT_HOURS))
        elif do == "offers":
            last[:] = jobs.offers(ws, a["place"], a.get("limit", jobs.OFFER_LIMIT), a.get("names"))
            r = [o.to_dict() for o in last]
        elif do in ("complete", "fail"):
            pick = a.get("pick", 0)
            offer = jobs.Offer(**a["offer"]) if "offer" in a else last[pick] if 0 <= pick < len(last) else None
            r = None if offer is None else (jobs.complete if do == "complete" else jobs.fail)(ws, offer)
        elif do == "news":
            args = (ws, a["place"], a.get("since", 0), a.get("limit", news.HEADLINE_LIMIT))
            r = {"items": news.items(*args, names=a.get("names")),
                 "page": news.terminal_page(*args, width=a.get("width", news.TERMINAL_WIDTH), names=a.get("names"))}
        elif do == "wrap":
            r = textwrap.wrap(a["text"], a.get("width", 70), subsequent_indent=a["indent"])
        elif do == "shorten":
            r = textwrap.shorten(a["text"], a.get("width", 70), placeholder=a["placeholder"])
        elif do == "upper":
            r = a["text"][:1].upper() + a["text"][1:]
        else:
            raise AssertionError(f"unknown action {do}")
    except ValueError as e:
        return canonical([ws.hour, do, {"error": str(e)}])
    return canonical([ws.hour, do, {"ok": r}])


def script_for(ws, days):
    """Player actions for step C4 on any world, from its sorted settlements and held places: a status, a look at
    the offers somewhere each day, the first offer done and the second given up a tick later, a stale hand-in now and
    then, and every 6th day one done at once; settlers moved, beds built, a focus set and cleared, supplies sent (often
    refused: another holder, no route, too little stock); and on day 2 every refusal manage has. Sorted by hour, so
    actions at one hour run in the order written here."""
    setts = sorted(ws.settlements)
    held = sorted(p for p, pl in ws.places.items() if pl.holder is not None)
    goods = [None, "food", "water", "scrap", "ammo", "medicine"]
    names = {p: f"{p.replace('_', '-')}-o-ville éa" for p in held[::3]}     # hyphens and a non-ASCII letter to wrap
    out = []
    for day in range(days):
        h, s, t = day * 24, setts[day % len(setts)], setts[(day * 3 + 1) % len(setts)]
        out += [{"hour": h, "do": "status", "settlement": s},
                {"hour": h, "do": "offers", "place": held[(day * 5) % len(held)], "limit": 4 + day % 3},
                {"hour": h + 6, "do": "complete", "pick": 0},
                {"hour": h + 6, "do": "fail", "pick": 1}]
        if day % 3 == 0:
            out.append({"hour": h + 12, "do": "assign", "settlement": s, "from": "farmer", "to": "guard"})
        elif day % 3 == 1:
            out.append({"hour": h + 12, "do": "beds", "settlement": s, "n": 2})
        else:
            out.append({"hour": h + 12, "do": "priority", "settlement": s, "good": goods[day % len(goods)]})
        if day % 4 == 0:
            out.append({"hour": h + 12, "do": "send", "from": s, "to": t, "goods": {"food": 3, "water": 2}})
        if day % 5 == 0:
            out.append({"hour": h + 18, "do": "threats", "settlement": s, "hours": 24})
        out.append({"hour": h + 18, "do": "news", "place": held[(day * 7 + 3) % len(held)],
                    "since": max(0, h - 24 * (day % 4)), "limit": 3 + day % 12,
                    "width": (60, 40, 23, 12, 7)[day % 5], **({"names": names} if day % 3 == 0 else {})})
        if day % 7 == 3:
            out.append({"hour": h + 18, "do": "complete", "pick": 0})        # the same offer again: refused
        if day % 6 == 5:
            out.append({"hour": h, "do": "complete", "pick": 0})             # at once, before a caravan leaves
    s, t, place = setts[0], setts[1 % len(setts)], sorted(set(ws.places) - set(ws.settlements))[0]
    out += [{"hour": 48, "do": "assign", "settlement": s, "from": "farmer", "to": "pilot"},
            {"hour": 48, "do": "assign", "settlement": s, "from": "guard", "to": "guard"},
            {"hour": 48, "do": "assign", "settlement": s, "from": "farmer", "to": "guard", "n": 0},
            {"hour": 48, "do": "assign", "settlement": s, "from": "doctor", "to": "guard", "n": 50},
            {"hour": 48, "do": "beds", "settlement": s, "n": 100},
            {"hour": 48, "do": "beds", "settlement": place},
            {"hour": 48, "do": "priority", "settlement": s, "good": "gold"},
            {"hour": 48, "do": "send", "from": s, "to": s, "goods": {"food": 1}},
            {"hour": 48, "do": "send", "from": s, "to": t, "goods": {}},
            {"hour": 48, "do": "send", "from": s, "to": t, "goods": {"gold": 1}},
            {"hour": 48, "do": "send", "from": s, "to": t, "goods": {"food": 0}},
            {"hour": 48, "do": "send", "from": s, "to": t, "goods": {"food": 10 ** 6}},
            {"hour": 48, "do": "status", "settlement": place},
            {"hour": 48, "do": "trade", "settlement": s, "goods": {"gold": 1}}]
    return sorted(out, key=lambda a: a["hour"])                                # stable: same-hour order kept


class CppParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prebuilt = os.environ.get("FOCCSIM_EXE")                  # a core built elsewhere, e.g. by MSVC on the PC
        cxx = None if prebuilt else compiler()
        if not prebuilt and not cxx:
            if os.environ.get("CI"):
                raise RuntimeError("C++ parity tests need a C++17 compiler or FOCCSIM_EXE in CI")
            raise unittest.SkipTest("no C++ compiler on PATH (CXX, c++, g++ or clang++), "
                                    "and FOCCSIM_EXE names no prebuilt core")
        cls.tmp = tempfile.mkdtemp(prefix="foccsim-")
        if prebuilt:
            if not os.path.isfile(prebuilt):
                shutil.rmtree(cls.tmp, ignore_errors=True)
                raise AssertionError(f"FOCCSIM_EXE={prebuilt} is not a file")
            cls.exe = os.path.abspath(prebuilt)
            return
        cls.exe = os.path.join(cls.tmp, "foccsim.exe" if os.name == "nt" else "foccsim")
        # -ffp-contract=off: no fused multiply-add may change a rounding (section 3, "Floats")
        r = subprocess.run([cxx, "-std=c++17", "-O2", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror",
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
                            "--walk", walk_p, "--present", os.path.join(d, "present.jsonl"),
                            "--results", os.path.join(d, "results.jsonl"), *extra],
                           capture_output=True, text=True, timeout=300)   # a hang fails instead of stalling CI
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
        results, last = [], []
        r, d, state = self.native(ws, ticks, actions, walk=walk)
        self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), ticks, name)
        for t in range(1, ticks + 1):
            for a in actions:
                if a["hour"] == ws.hour:
                    results.append(run(ws, a, last))
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
        self.same_lines(name, "the player actions", results, self.lines(d, "results.jsonl"),
                        lambda k: f"action {k} ({json.loads(results[k])[1]} at hour {json.loads(results[k])[0]})")

    def test_the_fixture_world_for_ten_seeds_over_90_days(self):
        for seed in range(10):
            with self.subTest(seed=seed):
                self.parity(f"fixture seed {seed}", fixture_world(seed), 90 * DAY)

    def test_large_seeds_with_priority_settlements_and_regional_reputation(self):
        for seed in (2 ** 32, 2 ** 32 + 7):
            with self.subTest(seed=seed):
                ws = layered_world(seed)
                days = 90 if FULL else 8
                sim.rng_seed(seed, days * 24)       # the entire run fits the unsigned 64-bit per-tick seed bound
                # Before the general script, complete a resupply and give one up in the other region. These
                # exercise fame/infamy propagation, priority status and news even in the short default run.
                actions = [{"hour": 0, "do": "status", "settlement": "market"},
                           {"hour": 0, "do": "offers", "place": "market"},
                           {"hour": 0, "do": "complete", "pick": 0},
                           {"hour": 0, "do": "offers", "place": "river_town"},
                           {"hour": 0, "do": "fail", "pick": 0},
                           {"hour": 0, "do": "news", "place": "market"},
                           {"hour": 0, "do": "news", "place": "river_town"}] + script_for(ws, days)
                self.parity(f"large seed {seed}, priorities and regional reputation", ws, days * DAY,
                            actions, every=1)       # multi-word init_by_array: never thin these state comparisons

    def test_raid_pressure_story_mode_and_player_actions(self):
        variants = [("raid low", {"raid_pressure": "low"}, ()), ("raid high", {"raid_pressure": "high"}, ()),
                    ("story mode", {"story_mode": True, "active_stories": ["main_story_1"]}, ()),
                    ("player actions", {}, ACTIONS), ("settlements and jobs", {}, None)]
        for seed in (range(10) if FULL else (0, 3)):                    # seed 3 also completes a defence
            for name, settings, actions in variants:
                if seed == 3 and actions is not None and not FULL:
                    continue
                with self.subTest(seed=seed, variant=name):
                    ws = fixture_world(seed, **settings)
                    self.parity(f"{name} seed {seed}", ws, 90 * DAY, script_for(ws, 90) if actions is None else actions)

    def test_the_commonwealth_scale_draft(self):
        from test_combined_seedpack import commonwealth_scale_draft
        pack, _report = seedpack.generate(commonwealth_scale_draft())
        for seed in (range(10) if FULL else (0,)):
            with self.subTest(seed=seed):
                ws = WorldState(seed=seed)
                model.load_pack(ws, copy.deepcopy(pack))
                self.assertGreater(len(ws.places), 200)
                days = 90 if FULL else 30
                self.parity(f"Commonwealth-scale seed {seed}", copy.deepcopy(ws), days * DAY)
                if seed == 0:
                    self.parity("Commonwealth-scale with settlements and jobs", ws, days * DAY, script_for(ws, days))

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

    def jobs_world(self):
        """The fixture world at hour 0 with one offer of every kind at the market (the settlers'): raiders bound for
        farm_a (defend), a caravan leaving for farm_a (escort; the order's caravan there is not offered), farm_b lost
        to the raiders (retake), the market short of food (resupply), and the raiders at gate_1 next door (clear)."""
        ws = fixture_world(0)
        ws.squads["s900"] = model.Squad(id="s900", faction="raiders", size=7, at="raider_camp", goal="farm_a",
                                        kind="attack", eta=12)
        ws.squads["c901"] = model.Squad(id="c901", faction="settlers", size=2, at="market", goal="farm_a",
                                        kind="caravan", cargo={"food": 15, "ammo": 0}, eta=6)
        ws.squads["c902"] = model.Squad(id="c902", faction="order", size=2, at="market", goal="order_fort",
                                        kind="caravan", cargo={"ammo": 5}, eta=12)      # not the settlers' to offer
        ws.places["farm_b"].holder = "raiders"
        sim._event(ws, "place_taken", "farm_b", faction="raiders", previous="settlers", retaken=False)
        ws.settlements["market"].stock["food"] = 1
        ws.places["gate_1"].holder = "raiders"
        offers = {o.kind: o for o in jobs.offers(ws, "market", limit=10)}
        self.assertEqual(sorted(offers), sorted(jobs.KINDS))
        return ws, offers

    def same_actions(self, name, ws, actions):
        """Run `actions` at the state's hour in Python and in the core, then one tick: the results and the state
        after the tick must match."""
        want, last = [], []
        hour = ws.hour
        out = os.path.join(tempfile.mkdtemp(dir=self.tmp), "after.json")
        r, d, _state = self.native(ws, 1, [dict(a, hour=hour) for a in actions], "--out", out)
        self.assertEqual(r.returncode, 0, f"{name}: {r.stderr}")
        for a in actions:
            want.append(run(ws, dict(a, hour=hour), last))
        sim.tick(ws)
        self.same_lines(name, "the player actions", want, self.lines(d, "results.jsonl"), lambda k: f"action {k}")
        with open(out, encoding="utf-8") as f:
            self.same_lines(name, "the state", [ws.to_json()], [f.read()], lambda k: "after the actions and a tick")
        return [json.loads(w)[2] for w in want]

    def test_the_jobs_refuse_a_moot_offer_with_pythons_reason(self):
        """Every reason jobs.valid gives, from an offer made before the world changed; then each kind done, and each
        given up."""
        base, offers = self.jobs_world()

        def moved(ws, place, event_kind, **info):
            sim._event(ws, event_kind, place, **info)

        cases = {
            "defend": [("the attack is over", lambda ws: ws.squads.pop("s900")),
                       ("the giver no longer holds the place", lambda ws: setattr(ws.places["farm_a"], "holder", "order")),
                       ("a garrison already stands there", lambda ws: sim.player_defended(ws, "farm_a"))],
            "escort": [("the caravan has already arrived or was lost", lambda ws: ws.squads.pop("c901")),
                       ("the destination is no longer held by the giver",
                        lambda ws: setattr(ws.places["farm_a"], "holder", "order"))],
            "retake": [("the giver holds the place again", lambda ws: setattr(ws.places["farm_b"], "holder", "settlers")),
                       ("the place was lost again since", lambda ws: moved(ws, "farm_b", "place_taken", faction="raiders",
                                                                           previous="settlers")),
                       ("the place cannot change hands", lambda ws: setattr(ws.places["farm_b"], "story_lock", "s1")),
                       ("held by a friend of the giver", lambda ws: setattr(ws.places["farm_b"], "holder", "order"))],
            "resupply": [("no longer the giver's", lambda ws: setattr(ws.places["market"], "holder", "order")),
                         ("no longer short", lambda ws: ws.settlements["market"].stock.update(food=100))],
            "clear": [("no longer a hostile neighbour", lambda ws: setattr(ws.places["gate_1"], "holder", None)),
                      ("someone else holds the place now", lambda ws: moved(ws, "gate_1", "place_taken",
                                                                            faction="raiders", previous=None))],
        }
        for kind, changes in cases.items():
            offer = offers[kind].to_dict()
            for why, change in changes:
                with self.subTest(kind=kind, why=why):
                    ws = copy.deepcopy(base)
                    change(ws)
                    got = self.same_actions(f"{kind}: {why}", ws, [{"do": "complete", "offer": offer}])
                    self.assertIn(why, got[0]["error"])
            with self.subTest(kind=kind, why="done, then done again and given up"):
                got = self.same_actions(f"{kind} done", copy.deepcopy(base),
                                        [{"do": "complete", "offer": offer}, {"do": "complete", "offer": offer},
                                         {"do": "fail", "offer": offer}])
                self.assertIn("ok", got[0])
                self.assertIn("already handed in or given up", got[1]["error"])
                self.assertIn("already handed in or given up", got[2]["error"])
            with self.subTest(kind=kind, why="given up"):
                self.same_actions(f"{kind} given up", copy.deepcopy(base), [{"do": "fail", "offer": offer},
                                                                          {"do": "complete", "offer": offer}])
        offer = offers["clear"].to_dict()
        for why, bad in (("offer expired at hour", dict(offer, expires_hour=0)),
                         ("giver or target no longer exists", dict(offer, giver="nobody")),
                         ("unknown offer kind 'dance'", dict(offer, kind="dance"))):
            with self.subTest(why=why):
                got = self.same_actions(why, copy.deepcopy(base), [{"do": "complete", "offer": bad}])
                self.assertIn(why, got[0]["error"])

    def test_the_jobs_refuse_superseded_later_and_given_up_instances(self):
        """#673's rules on the market's resupply job, read at hour 0 (a0, with its read_at), each refused by both doors
        with Python's reason: a0 after another instance read at hour 1 was handed in (superseded by the later
        offered hour); an instance read at hour 1 after a0 was given up right after the read (superseded by log
        position alone); an instance from an hour the world has not reached (from later); and an instance read after
        a0's give-up inside its window, by another hour (the window reason). The offers' read_at is compared too."""
        base, offers = self.jobs_world()
        a0 = offers["resupply"].to_dict()
        self.assertEqual(a0["read_at"], len(base.events))
        cannot = "cannot {} " + a0["id"] + ": "
        superseded = "this offer was superseded: an outcome for the job was logged after it was read"

        def at_hour_1(ws):
            ws.hour = 1
            return [o.kind for o in jobs.offers(ws, "market", limit=10)].index("resupply")

        with self.subTest(why="superseded by a later instance's hand-in"):
            ws = copy.deepcopy(base)
            pick = at_hour_1(ws)
            got = self.same_actions("superseded by hour", ws, [
                {"do": "offers", "place": "market", "limit": 10}, {"do": "complete", "pick": pick},
                {"do": "complete", "offer": a0}, {"do": "fail", "offer": a0}])
            self.assertIn("ok", got[1])
            self.assertEqual(got[2]["error"], cannot.format("complete") + superseded)
            self.assertEqual(got[3]["error"], cannot.format("fail") + superseded)
        with self.subTest(why="superseded by a give-up logged right after the read"):
            ws = copy.deepcopy(base)
            pick = at_hour_1(ws)
            got = self.same_actions("superseded by position", ws, [
                {"do": "offers", "place": "market", "limit": 10}, {"do": "fail", "offer": a0},
                {"do": "complete", "pick": pick}, {"do": "fail", "pick": pick}])
            self.assertIn("ok", got[1])
            self.assertEqual(got[2]["error"], cannot.format("complete") + superseded)
            self.assertEqual(got[3]["error"], cannot.format("fail") + superseded)
        with self.subTest(why="from a later hour"):
            later = dict(a0, offered_hour=base.hour + 5)
            got = self.same_actions("from later", copy.deepcopy(base), [{"do": "complete", "offer": later},
                                                                        {"do": "fail", "offer": later}])
            why = f"this offer was read at hour {base.hour + 5}, later than the world's hour {base.hour}"
            self.assertEqual(got[0]["error"], cannot.format("complete") + why)
            self.assertEqual(got[1]["error"], cannot.format("fail") + why)
        with self.subTest(why="given up and inside its window"):
            ws = copy.deepcopy(base)
            jobs.fail(ws, jobs.Offer(**a0))
            ws.hour = 1
            again = dict(a0, offered_hour=1, read_at=len(ws.events))
            got = self.same_actions("window", ws, [{"do": "offers", "place": "market", "limit": 10},
                                                   {"do": "complete", "offer": again}, {"do": "fail", "offer": again}])
            self.assertNotIn("resupply", [o["kind"] for o in got[0]["ok"]])
            why = "this job was given up and its window has not ended"
            self.assertEqual(got[1]["error"], cannot.format("complete") + why)
            self.assertEqual(got[2]["error"], cannot.format("fail") + why)

    def test_one_time_jobs_stay_retired_across_new_offer_instances(self):
        """Pin the C++ one_time predicate by behavior: an older outcome retires only these three kinds forever.
        A fresh repeating offer read after that outcome (and after a failed window) remains usable."""
        base, offers = self.jobs_world()
        for kind, offer in offers.items():
            for outcome in ("job_done", "job_failed"):
                with self.subTest(kind=kind, outcome=outcome):
                    ws = copy.deepcopy(base)
                    sim._event(ws, outcome, "market", offer=offer.id, job=kind, faction=offer.giver,
                               offered=0, until=1)
                    ws.hour = 1
                    fresh = dataclasses.replace(offer, offered_hour=1, read_at=len(ws.events)).to_dict()
                    got = self.same_actions(f"{kind} after {outcome}", ws,
                                            [{"do": "complete", "offer": fresh}, {"do": "fail", "offer": fresh}])
                    if kind in ("defend", "escort", "retake"):
                        self.assertIn("already handed in or given up", got[0]["error"])
                    else:
                        self.assertIn("ok", got[0])
                    self.assertIn("already handed in or given up", got[1]["error"])

    def test_manage_at_its_limits_and_a_long_defence(self):
        """Each manage action exactly at its limit and one past it; and a defence whose attack is due after the usual
        72 hours, so the garrison stays until then."""
        ws = fixture_world(0)
        food = ws.settlements["farm_a"].stock["food"]
        farmers = ws.settlements["farm_a"].roles["farmer"]
        got = self.same_actions("limits", ws, [
            {"do": "beds", "settlement": "farm_a", "n": manage.BEDS_MAX - ws.settlements["farm_a"].beds},
            {"do": "beds", "settlement": "farm_a", "n": 1},
            {"do": "send", "from": "farm_a", "to": "market", "goods": {"food": food + 1}},
            {"do": "send", "from": "farm_a", "to": "market", "goods": {"food": food, "water": 1}},
            {"do": "assign", "settlement": "farm_a", "from": "farmer", "to": "doctor", "n": farmers + 1},
            {"do": "assign", "settlement": "farm_a", "from": "farmer", "to": "doctor", "n": farmers},
            {"do": "threats", "settlement": "farm_a", "hours": 12},
            {"do": "threats", "settlement": "farm_a", "hours": 11},
            {"do": "priority", "settlement": "farm_a", "good": "medicine"},
            {"do": "priority", "settlement": "farm_a"},
            {"do": "status", "settlement": "farm_a"}])
        self.assertEqual([("ok" in g) for g in got], [True, False, False, True, False, True, True, True, True, True,
                                                      True])
        ws = fixture_world(0)
        ws.squads["s900"] = model.Squad(id="s900", faction="raiders", size=7, at="raider_camp", goal="farm_a",
                                        kind="attack", eta=100)
        got = self.same_actions("long defence", ws, [{"do": "offers", "place": "market"},
                                                     {"do": "complete", "pick": 0}])
        self.assertEqual(ws.squads[got[1]["ok"]["garrison"]].eta, 100)

    def test_the_jobs_texts_with_display_names_and_limits(self):
        """The offers' own wording at the market, every kind, plain and with a pack's display names; limits of 0 and -2
        (a Python slice); offers where nobody holds the place; and an unknown place."""
        ws, _offers = self.jobs_world()
        names = {"market": "the Market", "farm_a": "Abernathy-ish Farm", "raiders": "the raiders", "settlers": "",
                 "Day 1, 12:00": "noon"}                            # display_name also sees the due stamp
        got = self.same_actions("offers", ws, [{"do": "offers", "place": "market", "limit": 10},
                                               {"do": "offers", "place": "market", "limit": 10, "names": names},
                                               {"do": "offers", "place": "market", "limit": 10, "names": {}},
                                               {"do": "offers", "place": "ruins"},
                                               {"do": "offers", "place": "market", "limit": 0},
                                               {"do": "offers", "place": "market", "limit": -2}])
        self.assertIn("noon", " ".join(o["text"] for o in got[1]["ok"]))
        self.assertEqual(len(got[5]["ok"]), len(got[0]["ok"]) - 2)            # found[:limit], Python's slice
        with self.assertRaisesRegex(KeyError, "unknown place 'nowhere'"):
            jobs.offers(ws, "nowhere")
        r, _d, _state = self.native(ws, 1, [{"hour": ws.hour, "do": "offers", "place": "nowhere"}])
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("unknown place 'nowhere'", r.stderr)

    def test_textwrap_and_the_capital_letter_against_python(self):
        """news.wrap and news.shorten against Python's textwrap on 3,000 random texts: words, hyphenated words,
        em-dashes, punctuation, every whitespace textwrap knows (tabs too), a no-break space, letters outside ASCII,
        widths from -1 to 40, indents and placeholders; and news.upper_first against str.upper for every first character
        it covers."""
        rnd = random.Random(20261101)
        pieces = ["a", "b", "word", "Zz", "9", "12", "-", "--", "---", " ", "  ", "\t", "\n", "\r", "\x0b", ".", ",",
                  "!", "?", '"', "'", "&", "_", "é", "ß", "Ж", "Ω", "✓", "\xa0", "x-y", "ab-cd", "a-b-c", "re-do",
                  "--x", "é-é", "a--b", "1-2", "end.", "long" * 5]
        actions = []
        for k in range(3000):
            text = "".join(rnd.choice(pieces) for _ in range(rnd.randint(0, 25)))
            width = rnd.choice([-1, 0, 1, 2, 3, 4, 5, 7, 9, 12, 20, 40])
            if k % 3 == 0:
                actions.append({"do": "shorten", "text": text, "width": width,
                                "placeholder": rnd.choice(["...", " [...]", "", "  ...", "…"])})
            else:
                actions.append({"do": "wrap", "text": text, "width": width, "indent": rnd.choice(["", "  ", "    ", "\t"])})
        firsts = [c for c in range(0x20, 0x180) if c != 0x7F] + list(range(0x386, 0x3D0)) + list(range(0x400, 0x460))
        actions += [{"do": "upper", "text": chr(c) + "bc"} for c in firsts if c not in (0x390, 0x3B0)]
        got = self.same_actions("textwrap", fixture_world(0), actions)
        self.assertGreater(sum("error" in g for g in got), 100)                  # widths below 1, big placeholders
        self.assertGreater(sum(len(g.get("ok") or []) > 2 for g in got[:3000] if isinstance(g.get("ok"), list)), 500)

    def test_the_news_writes_every_template(self):
        """A headline for every event kind news.py knows, and the variants it picks between; an unknown kind is
        skipped; exact repeats collapse; since and limit; a page with nothing on it; and widths down to the one that
        cannot hold the title's placeholder."""
        ws = fixture_world(0)
        ws.hour = 100
        def ev(kind, place="market", hour=90, **info):
            ws.events.append({"hour": hour, "kind": kind, "place": place, "region": ws.places[place].region, **info})
        ev("place_taken", faction="raiders", previous="settlers", retaken=False)
        ev("place_taken", faction="raiders", previous="settlers", retaken=True)
        ev("place_taken", faction="raiders", previous=None)
        ev("attack_launched", "raider_camp", faction="raiders", target="farm_a", size=5)
        ev("attack_failed", faction="raiders", defender="settlers")
        ev("attack_called_off", faction="raiders", defender=None)
        ev("caravan_raided", faction="settlers", raider="raiders", origin="farm_a", cargo={"food": 3, "ammo": 0})
        ev("caravan_arrived", faction="settlers", cargo={"water": 2, "food": 1})
        ev("caravan_arrived", faction="settlers", cargo={})
        ev("caravan_lost", faction="settlers")
        ev("stage_changed", old=1, new=2)
        ev("stage_changed", old=2, new=1)
        ev("stage_changed", "farm_b", old=2, new=2)                                # no change counts as grown
        ev("settler_left")
        ev("settler_arrived")
        ev("settlement_emptied", holder="raiders")
        ev("settlement_resettled", faction="settlers")
        ev("player_defended", holder="settlers", bonus=10)
        ev("player_traded", goods={"food": 5, "ammo": -2})
        ev("player_traded", goods={"ammo": -2})
        ev("place_cleared", faction="settlers", previous="raiders", player=True)
        ev("job_done", faction="settlers", job="clear")
        ev("job_failed", faction="settlers", job="escort")
        ev("roles_changed", from_role="farmer", to_role="guard", n=1)
        ev("beds_added", n=2, beds=22)
        ev("priority_set", old=None, new="medicine")
        ev("priority_set", old="medicine", new=None)
        ev("supplies_sent", target="farm_a", cargo={"food": 3}, squad="c1", eta=96)
        ev("weather_changed")                                                       # no template: skipped
        ev("settler_left", hour=95)                                                 # an exact repeat, newer
        ev("settler_left", "farm_a", hour=99)                                       # not here yet (6 route hours)
        ev("settler_left", "gate_2", hour=5)                                        # a far place, long since arrived
        actions = [{"do": "news", "place": "market", "limit": 50},
                   {"do": "news", "place": "market", "limit": 50, "names": {"market": "the market", "raiders": "Ödland"}},
                   {"do": "news", "place": "market", "since": 95, "limit": 5, "width": 25},
                   {"do": "news", "place": "market", "limit": 0},
                   {"do": "news", "place": "market", "limit": -1},
                   {"do": "news", "place": "ruins", "since": 1000, "width": 9},
                   {"do": "news", "place": "nowhere", "width": 14},
                   {"do": "news", "place": "market", "width": 3},
                   {"do": "news", "place": "market", "width": 2},
                   {"do": "news", "place": "market", "width": 0}]
        got = self.same_actions("news", ws, actions)
        texts = [i["text"] for i in got[0]["ok"]["items"]]
        self.assertEqual(len(texts), len(set(texts)))
        # 32 events: one unknown kind, one exact repeat (settler_left), and two not here yet (farm_a's at hour 99,
        # and the attack from the raider camp, 12 route hours away, at hour 90)
        self.assertEqual(len(texts), 28)
        self.assertIn("Farm b has grown.", texts)
        self.assertTrue(got[1]["ok"]["items"][0]["text"][0].isupper())
        self.assertIn("error", got[-1])                                             # textwrap: invalid width 0
        self.assertIn("error", got[-2])                                             # the placeholder cannot fit



if __name__ == "__main__":
    unittest.main()
