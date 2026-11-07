"""L2 simulation prototype: advances the world state on game time, deterministically.

Paper prototype to tune rules before any game work. Every number here is a
placeholder to argue with, not a balance decision. The RNG is seeded from
(seed, hour), so a run resumed from a saved state replays exactly; every draw
comes from that per-tick RNG and dicts are walked in sorted order.

Lessons from the first prototype that this version encodes: growth needs a role
rule and a beds cap, faction strength needs a sink (daily upkeep), capture must
hurt the settlement, factions prefer to retake what they lost, and caravans can
be raided so supply lines are breakable.
"""
from __future__ import annotations

import random

from . import reputation
from .model import GOODS, STRENGTH_CAP, Squad, WorldState  # noqa: F401  (STRENGTH_CAP re-exported for callers)
from .modes import STORY_SHIELD_HOURS

TICK_HOURS = 6
STAGE_POP = (0, 4, 8, 14, 22)        # population needed for stage 0..4
NEWS_HOURS_PER_ROUTE_HOUR = 1        # news travels at travel speed

# Faction economy (placeholders to tune): income and upkeep both scale with territory, so holding
# more costs more and a faction that over-extends bleeds strength while a failed attack is a total loss.
STRENGTH_INCOME_PER_PLACE = 2        # strength gained per held place per day
UPKEEP_PER_PLACE = 1                 # strength paid per held place per day, floor 0
RETAKE_WEIGHT = 3                    # a lost place counts this many times when picking a target
SETTLEMENT_TARGET_WEIGHT = 1         # a hostile or empty settlement counts this many times when picking a target
                                     # (multiplies RETAKE_WEIGHT); placeholder, see "Commonwealth-scale baseline"
ATTACK_CHANCE_PER_AGGRESSION = 0.25  # percent chance per tick per aggression point, times the raid-pressure
                                     # multiplier from ws.settings (modes.py, CC-41)

# Caravan raiding (placeholders): a hostile faction holding a place next to either end of the route
# gets one interception roll per caravan, scaled by its strength.
RAID_CHANCE_PER_STRENGTH = 0.01      # chance = min(cap, strength * this)
RAID_CHANCE_CAP = 0.35
RAID_STRENGTH_GAIN = 1               # loot feeds the raider a little

# Player hooks (placeholders). Reputation rules live in reputation.py (NV fame and infamy per faction, gains in
# the NV tiers); REP_TIERS stays as an alias for callers of the first prototype.
REP_TIERS = reputation.GAIN_TIERS
PLAYER_DEFENCE_BONUS = 10            # defence a player garrison adds to the next attack at that place
PLAYER_DEFENCE_HOURS = 72            # a garrison the player leaves goes home after this long
PLAYER_DEFENCE_FAME = 4
TRADE_GOODS_PER_TIER = 10            # goods handed over per reputation tier step

# Settlement production focus (placeholder; our own addition under CC-10 "both", where the player's management feeds
# the same numbers the simulation grows; set via manage.set_priority): each worker of the role that makes the
# prioritised good adds this much more of it per tick. Which role makes which good follows _settlement_tick; a
# priority of None (the default) changes nothing, so saves made before the field existed replay exactly.
PRIORITY_BONUS_PER_WORKER = 1
PRIORITY_ROLE = {"food": "farmer", "water": "farmer", "scrap": "scavenger", "ammo": "crafter",
                 "medicine": "doctor"}

# Shortage response (placeholder; the second prototype's balance run found capture stripping a farm of every farmer,
# since _remove_settler takes from the biggest role, and starvation then emptied it: docs/combined-core.md "Balance
# baseline"). On a tick short of food or water, this many settlers of the biggest other role take up farming while
# 3 * farmers < population + 2 (the same food-ahead-of-mouths rule _add_settler grows by). Capture still hurts: the
# population halves and the larder drains for a tick or two (a resupply job window), but a place with people in it
# feeds itself again instead of emptying. 0 disables.
REROLE_ON_SHORTAGE = 1

# Resettlement (placeholders): an empty settlement a faction holds draws a wanderer once a day when it is safe (no
# attack has touched it for RESETTLE_SAFE_HOURS and none is on its way) and fed (the wanderer brings RESETTLE_KIT food
# and water, so a looted larder does not keep a place dead for good). The first settler is a farmer (_add_settler),
# morale restarts at no less than RESETTLE_MORALE. Design: "settlements that grow into real places and can fall", so
# a place can empty, but rarely, and can be resettled.
RESETTLE_SAFE_HOURS = 48
RESETTLE_KIT = 6
RESETTLE_MORALE = 50
ATTACK_EVENT_KINDS = ("place_taken", "attack_failed", "place_cleared")   # events that mean fighting at a place

# Growth brake (placeholder, deterministic, no random draw). Alone, a settlement with the generated starting stats
# saturates: three farmers make 9 food a tick against 5 eaten, _add_settler keeps farmers ahead of mouths, so stock
# only grows, morale pins at 100 and one settler arrives every day until the beds are full (day 18 from population 5
# with 20 beds; docs/combined-core.md "Commonwealth-scale baseline"). With this, a settler may arrive only every
# 1 + population // ARRIVAL_SLOWDOWN_POP days (days counted from hour 0, so a resumed save judges the same): a place
# fills fast while small and slowly when nearly full, and the larder gets time to build the surplus caravans carry.
# 0 disables (the first prototype's daily arrival). Measured 2026-10-21, see the doc's Commonwealth-scale table.
ARRIVAL_SLOWDOWN_POP = 3

# Farm capacity (placeholder, the structural brake): only `beds // FARM_SLOTS_PER_BEDS` farmers find land to work, so
# a place feeds about three quarters of its beds on its own (3 food per farmer) and fills the rest only with caravans
# or the player's management (manage.add_beds also adds slots). Extra arrivals take the other roles (guards, then
# scavengers, ...). 0 disables (every farmer produces). LEAVE_ONLY_WHEN_SHORT keeps a settlement at its food edge
# instead of cascading to empty: at morale 10 a settler leaves only on a tick that was short of food or water, not
# every tick until morale recovers (1 on, 0 off). MORALE_DRIFT is the morale gained on a tick that is neither short
# nor in surplus, so a fed place at its edge climbs slowly back to the arrival threshold instead of freezing.
FARM_SLOTS_PER_BEDS = 4
LEAVE_ONLY_WHEN_SHORT = 1
MORALE_DRIFT = 1

# Event kinds that change a place's holder and carry `previous`: place_taken (here and jobs' retake, `faction` is the
# new holder) and place_cleared (jobs' clear: the holder becomes None, `faction` is the giver). Every reader of holder
# history (here, jobs, balance) walks both, so a player-cleared place counts as lost to its old holder.
HOLDER_CHANGE_KINDS = ("place_taken", "place_cleared")


def holder_changes(ws: WorldState) -> list[dict]:
    """The events that changed a holder, in log order."""
    return [e for e in ws.events if e["kind"] in HOLDER_CHANGE_KINDS]


def new_holder(e: dict) -> str | None:
    """Who held the place after holder-change event `e`."""
    return e["faction"] if e["kind"] == "place_taken" else None


RNG_SEED_LIMIT = 2 ** 64   # the per-tick seed must fit in 64 unsigned bits, as the C++ port holds it


def rng_seed(seed: int, hour: int) -> int:
    """The per-tick RNG seed, refused outside [0, 2**64): Python would take any integer (its absolute value), the
    in-game port only an unsigned 64-bit one (docs/combined-core-cpp-port.md section 3, "Seed range")."""
    n = seed * 1_000_003 + hour
    if not 0 <= n < RNG_SEED_LIMIT:
        raise ValueError(f"seed {seed} at hour {hour} gives the RNG seed {n}, outside 0 to 2**64 - 1")
    return n


def _rng(ws: WorldState) -> random.Random:
    return random.Random(rng_seed(ws.seed, ws.hour))


def _event(ws: WorldState, kind: str, place: str, **info) -> None:
    ws.events.append({"hour": ws.hour, "kind": kind, "place": place,
                      "region": ws.places[place].region, **info})


def _new_id(ws: WorldState, prefix: str) -> str:
    i = ws.next_id
    ws.next_id += 1
    return f"{prefix}{i}"


def _rep_tier(amount: int) -> int:
    """NV-style gain for `amount` goods given: one tier per TRADE_GOODS_PER_TIER (reputation.tier_for)."""
    return reputation.tier_for(amount, TRADE_GOODS_PER_TIER)


def _story_shielded(ws: WorldState) -> set[str]:
    """Places no attack may target under story mode: within STORY_SHIELD_HOURS by route of a story-locked place
    whose story is active (CC-50 "mute the sandbox's pressure on story places"). Empty when story mode is off."""
    out: set[str] = set()
    for pid in sorted(ws.places):
        if ws.settings.story_active(ws.places[pid].story_lock):
            out.update(p for p, h in _distances(ws, pid).items() if h <= STORY_SHIELD_HOURS)
    return out


# --- settlements -----------------------------------------------------------

def _settlement_tick(ws: WorldState) -> None:
    for sid in sorted(ws.settlements):
        s = ws.settlements[sid]
        r = s.roles
        farming = r["farmer"] if _farm_slots(s) is None else min(r["farmer"], _farm_slots(s))
        s.stock["food"] += 3 * farming
        s.stock["water"] += 3 * farming
        s.stock["scrap"] += 2 * r["scavenger"]
        made = min(r["crafter"], s.stock["scrap"] // 2)
        s.stock["scrap"] -= 2 * made
        s.stock["ammo"] += 3 * made
        s.stock["medicine"] += r["doctor"]
        if s.priority is not None:   # focus bonus (manage.set_priority); ammo still needs the scrap
            workers = made if s.priority == "ammo" else r[PRIORITY_ROLE[s.priority]]
            s.stock[s.priority] += PRIORITY_BONUS_PER_WORKER * workers
        need = s.population
        short = 0
        for g in ("food", "water"):
            if s.stock[g] >= need:
                s.stock[g] -= need
            else:
                short += need - s.stock[g]
                s.stock[g] = 0
        if short:
            s.morale = max(0, s.morale - 5)
            for role, n in sorted(_reroles_to_farming(s, REROLE_ON_SHORTAGE).items()):
                _event(ws, "roles_changed", sid, from_role=role, to_role="farmer", n=n)
        elif s.stock["food"] > 2 * need and s.stock["water"] > 2 * need:
            s.morale = min(100, s.morale + 2)
        else:
            s.morale = min(100, s.morale + MORALE_DRIFT)
        if s.morale <= 10 and s.population > 0 and (short or not LEAVE_ONLY_WHEN_SHORT):
            _remove_settler(s)
            _event(ws, "settler_left", sid)
            if s.population == 0:
                _event(ws, "settlement_emptied", sid, holder=ws.places[sid].holder)
        elif (s.population > 0 and s.morale >= 70 and ws.hour % 24 == 0 and not short
              and s.population < s.beds and _arrival_due(ws, s)):     # an empty place only refills by resettlement
            _add_settler(s)
            _event(ws, "settler_arrived", sid)
        elif (s.population == 0 and s.beds > 0 and ws.hour % 24 == 0
              and ws.places[sid].holder is not None and _resettle_safe(ws, sid)):
            _add_settler(s)                     # a farmer, since no farmer feeds anyone yet
            s.stock["food"] += RESETTLE_KIT
            s.stock["water"] += RESETTLE_KIT
            s.morale = max(s.morale, RESETTLE_MORALE)
            _event(ws, "settlement_resettled", sid, faction=ws.places[sid].holder)
        stage = max(i for i, p in enumerate(STAGE_POP) if s.population >= p)
        if stage != s.stage:
            _event(ws, "stage_changed", sid, old=s.stage, new=stage)
            s.stage = stage


def _farm_slots(s) -> int | None:
    """Farmers that find land to work (FARM_SLOTS_PER_BEDS), None when the rule is off."""
    return None if FARM_SLOTS_PER_BEDS <= 0 else s.beds // FARM_SLOTS_PER_BEDS


def _wants_farmer(s) -> bool:
    """The food rule: farmers stay ahead of mouths (3 * farmers < population + 2) while land remains for them."""
    slots = _farm_slots(s)
    return 3 * s.roles["farmer"] < s.population + 2 and (slots is None or s.roles["farmer"] < slots)


def _add_settler(s) -> None:
    s.population += 1
    # keep food ahead of mouths, then fill the scarcest other role
    if _wants_farmer(s):
        s.roles["farmer"] += 1
        return
    order = sorted(("guard", "scavenger", "trader", "crafter", "doctor"),
                   key=lambda r: (s.roles[r], r))
    s.roles[order[0]] += 1


def _arrival_due(ws: WorldState, s) -> bool:
    """Whether the growth brake lets a settler arrive on this day tick (ARRIVAL_SLOWDOWN_POP)."""
    if ARRIVAL_SLOWDOWN_POP <= 0:
        return True
    return (ws.hour // 24) % (1 + s.population // ARRIVAL_SLOWDOWN_POP) == 0


def _remove_settler(s) -> None:
    s.population -= 1
    biggest = max(sorted(s.roles), key=lambda r: s.roles[r])
    if s.roles[biggest]:
        s.roles[biggest] -= 1


def _reroles_to_farming(s, n: int) -> dict[str, int]:
    """Move up to `n` settlers, one at a time from the biggest non-farmer role, to farming while farmers are below
    the food rule (3 * farmers < population + 2). Returns {role: how many came from it}, empty when nobody moved.
    Same fields as manage.set_roles's roles_changed event, so news shows it with that template."""
    moved: dict[str, int] = {}
    for _ in range(max(0, n)):
        if not _wants_farmer(s):
            break
        others = [r for r in sorted(s.roles) if r != "farmer" and s.roles[r] > 0]
        if not others:
            break
        role = max(others, key=lambda r: s.roles[r])
        s.roles[role] -= 1
        s.roles["farmer"] += 1
        moved[role] = moved.get(role, 0) + 1
    return moved


def _resettle_safe(ws: WorldState, sid: str) -> bool:
    """No attack squad bound for `sid`, and no fighting there (ATTACK_EVENT_KINDS) within RESETTLE_SAFE_HOURS.
    Read from the squads and the event log, so a resumed save judges the same."""
    if any(q.kind == "attack" and q.goal == sid for q in ws.squads.values()):
        return False
    since = ws.hour - RESETTLE_SAFE_HOURS
    for e in reversed(ws.events):
        if e["hour"] < since:
            break
        if e["place"] == sid and e["kind"] in ATTACK_EVENT_KINDS:
            return False
    return True


# --- caravans and supply ---------------------------------------------------

def _dispatch_caravans(ws: WorldState) -> None:
    for sid in sorted(ws.settlements):
        s = ws.settlements[sid]
        holder = ws.places[sid].holder
        if not s.roles["trader"] or holder is None:
            continue
        if any(q.kind == "caravan" and q.at == sid for q in ws.squads.values()):
            continue
        friends = [(n, h) for n, h in ws.neighbours(sid)
                   if n in ws.settlements and ws.places[n].holder == holder]
        if not friends:
            continue
        target, hours = min(friends, key=lambda nh: (ws.settlements[nh[0]].stock["food"], nh[0]))
        surplus = s.stock["food"] - 3 * s.population
        if surplus < 6:
            continue
        cargo = {"food": surplus // 2}
        s.stock["food"] -= cargo["food"]
        q = Squad(id=_new_id(ws, "c"), faction=holder, size=2, at=sid, goal=target,
                  kind="caravan", cargo=cargo, eta=ws.hour + hours)
        ws.squads[q.id] = q


def _raider(ws: WorldState, q: Squad, rng: random.Random) -> str | None:
    """Faction that intercepts caravan `q`, or None. One roll per hostile faction holding a place
    next to either end of the route, in sorted order so the draw sequence is fixed."""
    ends = {q.at, q.goal}
    near = set()
    for end in sorted(ends):
        near.update(n for n, _ in ws.neighbours(end))
    near -= ends
    for fid in sorted(ws.factions):
        if not _hostile(ws, fid, q.faction):
            continue
        if not any(ws.places[n].holder == fid for n in sorted(near)):
            continue
        chance = min(RAID_CHANCE_CAP,
                     ws.factions[fid].strength * RAID_CHANCE_PER_STRENGTH * ws.settings.raid_multiplier())
        if rng.random() < chance:
            return fid
    return None


# --- factions ----------------------------------------------------------------

def _hostile(ws: WorldState, a: str, b: str | None) -> bool:
    return b is not None and a != b and ws.factions[a].relations.get(b, 0) < 0


def _lost_places(ws: WorldState, fid: str) -> set[str]:
    """Places `fid` once held and does not hold now (taken from it, or cleared by the player), read back from
    the event log so a resumed save knows them too (no extra model field needed)."""
    return {e["place"] for e in holder_changes(ws)
            if e.get("previous") == fid and ws.places[e["place"]].holder != fid}


def _daily_strength(ws: WorldState, fid: str, held: list[str]) -> None:
    f = ws.factions[fid]
    f.strength = min(STRENGTH_CAP, f.strength + STRENGTH_INCOME_PER_PLACE * len(held))
    f.strength = max(0, f.strength - UPKEEP_PER_PLACE * len(held))


def _faction_tick(ws: WorldState, rng: random.Random) -> None:
    pressure = ws.settings.raid_multiplier()
    shielded = _story_shielded(ws)
    for fid in sorted(ws.factions):
        f = ws.factions[fid]
        held = sorted(p for p, pl in ws.places.items() if pl.holder == fid)
        if ws.hour % 24 == 0:
            _daily_strength(ws, fid, held)
        if f.strength < 6 or rng.random() * 100 > f.aggression * ATTACK_CHANCE_PER_AGGRESSION * pressure:
            continue
        lost = _lost_places(ws, fid)
        targets = []
        for p in held:
            for n, hours in ws.neighbours(p):
                pl = ws.places[n]
                if pl.story_lock or n in shielded or any(x.home == n for x in ws.factions.values()):
                    continue
                if pl.holder is None or _hostile(ws, fid, pl.holder):
                    weight = (RETAKE_WEIGHT if n in lost else 1) * (SETTLEMENT_TARGET_WEIGHT if n in ws.settlements
                                                                     else 1)
                    targets.extend([(n, hours, p)] * weight)
        if not targets:
            continue
        target, hours, origin = rng.choice(sorted(targets))
        size = f.strength // 3
        f.strength -= size
        q = Squad(id=_new_id(ws, "s"), faction=fid, size=size, at=origin, goal=target,
                  kind="attack", eta=ws.hour + hours)
        ws.squads[q.id] = q
        _event(ws, "attack_launched", origin, faction=fid, target=target, size=size,
               retake=target in lost)


def _garrisons(ws: WorldState, place: str) -> list[str]:
    return sorted(qid for qid, q in ws.squads.items() if q.kind == "garrison" and q.at == place)


def _defence(ws: WorldState, place: str) -> int:
    d = ws.places[place].defence
    holder = ws.places[place].holder
    if holder is not None:
        d += min(ws.factions[holder].strength, 10) // 2   # garrison share
    s = ws.settlements.get(place)
    if s:
        d += 2 * s.roles["guard"] + s.stock["ammo"] // 10
    d += sum(ws.squads[g].size for g in _garrisons(ws, place))  # player_defended
    return d


def _resolve_arrivals(ws: WorldState, rng: random.Random) -> None:
    shielded = _story_shielded(ws)            # a story that became active after dispatch still shields (Codex, #431)
    # garrisons last: one due home this hour still meets an attack due this hour (Codex review of #431)
    for qid in sorted(ws.squads, key=lambda i: (ws.squads[i].kind == "garrison", i)):
        q = ws.squads.get(qid)
        if q is None or q.eta > ws.hour:      # None: a garrison consumed by an attack this tick
            continue
        del ws.squads[qid]
        if q.kind == "garrison":              # the player's helpers go home unused
            continue
        pl = ws.places[q.goal]
        if q.kind == "caravan":
            raider = _raider(ws, q, rng)
            dest = ws.settlements.get(q.goal)
            if raider is not None:
                r = ws.factions[raider]
                r.strength = min(STRENGTH_CAP, r.strength + RAID_STRENGTH_GAIN)
                _event(ws, "caravan_raided", q.goal, faction=q.faction, raider=raider,
                       origin=q.at, cargo=q.cargo)
            elif dest and pl.holder == q.faction:
                for g, n in q.cargo.items():
                    dest.stock[g] += n
                _event(ws, "caravan_arrived", q.goal, faction=q.faction, cargo=q.cargo)
            else:
                _event(ws, "caravan_lost", q.goal, faction=q.faction)
            continue
        if pl.holder == q.faction:
            f = ws.factions[q.faction]
            f.strength = min(STRENGTH_CAP, f.strength + q.size)
            continue
        # turned back, no roll and no garrison spent: the story shields the target now, or its new holder is no
        # enemy of the attacker, an attack _faction_tick would never launch (Codex review of #431)
        if (q.goal in shielded and not pl.story_lock) or (pl.holder is not None
                                                          and not _hostile(ws, q.faction, pl.holder)):
            f = ws.factions[q.faction]
            f.strength = min(STRENGTH_CAP, f.strength + q.size)
            _event(ws, "attack_called_off", q.goal, faction=q.faction, defender=pl.holder)
            continue
        defence = _defence(ws, q.goal)
        for g in _garrisons(ws, q.goal):      # a player garrison is spent on one attack
            del ws.squads[g]
        if pl.story_lock or rng.random() * (q.size + defence) >= q.size:
            _event(ws, "attack_failed", q.goal, faction=q.faction, defender=pl.holder)
            continue
        old = pl.holder
        retaken = q.goal in _lost_places(ws, q.faction)
        pl.holder = q.faction
        s = ws.settlements.get(q.goal)
        if s and s.population:
            for _ in range((s.population + 1) // 2):
                _remove_settler(s)
            s.morale = min(s.morale, 30)
            if s.population == 0:
                _event(ws, "settlement_emptied", q.goal, holder=q.faction)
        f = ws.factions[q.faction]
        f.strength = min(STRENGTH_CAP, f.strength + q.size // 2)
        _event(ws, "place_taken", q.goal, faction=q.faction, previous=old, retaken=retaken)


# --- player-facing hooks -----------------------------------------------------

def player_helped(ws: WorldState, faction: str, amount: int = 10) -> None:
    """New Vegas-style: `amount` fame with the faction, and a share of infamy with its enemies (reputation.helped)."""
    reputation.helped(ws, faction, amount)


def player_defended(ws: WorldState, place: str, bonus: int = PLAYER_DEFENCE_BONUS,
                    hours: int = PLAYER_DEFENCE_HOURS) -> str:
    """The player stands guard: a garrison squad adds `bonus` defence to the next attack on `place`
    (spent by that attack, or gone after `hours`, PLAYER_DEFENCE_HOURS by default). Fame with the holder, if any.
    Returns the garrison squad id."""
    q = Squad(id=_new_id(ws, "g"), faction="player", size=bonus, at=place, goal=place,
              kind="garrison", eta=ws.hour + hours)
    ws.squads[q.id] = q
    holder = ws.places[place].holder
    if holder is not None and holder in ws.reputation:
        player_helped(ws, holder, PLAYER_DEFENCE_FAME)
    _event(ws, "player_defended", place, holder=holder, bonus=bonus)
    return q.id


def player_traded(ws: WorldState, settlement: str, goods: dict[str, int]) -> dict[str, int]:
    """Move goods with a settlement: positive amounts go in, negative come out (clamped to stock).
    Giving earns fame with the holder in NV tiers; taking earns nothing. Returns what moved."""
    s = ws.settlements[settlement]
    bad = sorted(str(g) for g in goods if g not in GOODS)
    if bad:                                   # refuse before any stock moves (Codex review of #431)
        raise ValueError(f"unknown good {bad[0]}")
    if any(not isinstance(n, int) or isinstance(n, bool) for n in goods.values()):
        raise ValueError("trade amounts must be whole numbers")
    moved = {}
    for g in sorted(goods):
        n = max(goods[g], -s.stock[g])
        if n:
            s.stock[g] += n
            moved[g] = n
    given = sum(n for n in moved.values() if n > 0)
    holder = ws.places[settlement].holder
    if given and holder is not None and holder in ws.reputation:
        reputation.add(ws, holder, fame=_rep_tier(given))
    _event(ws, "player_traded", settlement, goods=moved)
    return moved


def news_for(ws: WorldState, place: str, since: int = 0) -> list[dict]:
    """Events that have had time to travel to `place` (spread along routes)."""
    dist = _distances(ws, place)
    out = []
    for e in ws.events:
        if e["hour"] < since or e["place"] not in dist:
            continue
        if e["hour"] + dist[e["place"]] * NEWS_HOURS_PER_ROUTE_HOUR <= ws.hour:
            out.append(e)
    return out


def _distances(ws: WorldState, start: str) -> dict[str, int]:
    best = {start: 0}
    todo = [start]
    while todo:
        todo.sort(key=lambda p: (best[p], p))
        p = todo.pop(0)
        for n, h in ws.neighbours(p):
            if n not in best or best[p] + h < best[n]:
                best[n] = best[p] + h
                todo.append(n)
    return best


def tick(ws: WorldState) -> None:
    ws.hour += TICK_HOURS
    rng = _rng(ws)
    _resolve_arrivals(ws, rng)
    _settlement_tick(ws)
    _dispatch_caravans(ws)
    _faction_tick(ws, rng)


def run(ws: WorldState, hours: int) -> None:
    end = ws.hour + hours
    while ws.hour < end:
        tick(ws)


assert set(GOODS) >= {"food", "water", "scrap", "ammo", "medicine"}
