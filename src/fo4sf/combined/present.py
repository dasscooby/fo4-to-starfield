"""L3 presentation planner: what the simulation says is near the player, as abstract spawn slots.

The design makes L3 the only layer that spawns things: it materializes what L2 says is near the player
and dissolves it back into data when the player leaves, with no permanent spawned references
(combined-core design, docs/research/framework/combined-core.md, layer rules). The radius idea is
A-Life's: full detail within a short range, coarse simulation beyond it (combined-core-notes/
gamma-anatomy.md, 2.4, verified for X-Ray). Here the range is route hours on the L1 graph, not
metres, because L1 has no coordinates.

This module is pure data: plan() reads a WorldState and returns a Plan of slots; diff() compares two
plans so a replan only spawns and dissolves the difference. Nothing here mutates the world, and
nothing here is engine code: an adapter later turns slots into alias fills and PlaceAtMe calls. Every
number is a placeholder to tune; the actor budget stands in for the engine's (combined-core-notes/
engine-feasibility.md names "actor-count budgets" as a risk without a measured figure).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import NamedTuple

from .model import ROLES, WorldState
from .sim import _distances

RADIUS_HOURS = 6                  # placeholder: one route hop counts as "near"
MAX_LIVE_ACTORS = 40              # placeholder: total actors a plan may ask for at once

# Garrison size (placeholders): a holder's visible guard at a place. The strength share mirrors the
# simulation's defence formula (sim._defence) so what the player sees matches what fights off-screen.
GARRISON_BASE = 1
GARRISON_PER_DEFENCE = 1          # actors per point of Place.defence
GARRISON_STRENGTH_SHARE_CAP = 10  # min(strength, cap) // 2, as in sim._defence
GARRISON_MAX = 8

SETTLERS_PER_ROLE_MAX = 6         # placeholder: settlers shown per role at one settlement
SQUAD_ACTORS_MAX = 8              # placeholder: actors a travelling squad shows, whatever its size
CARAVAN_ACTORS = 2                # placeholder: a caravan is this many actors plus its cargo

# Budget priority after distance: lower rank materializes first. Attackers before garrisons before
# settlers (the task rule); patrols, caravans and the player's own helpers come after, as placeholders.
CLASS_RANK = {"attack": 0, "garrison": 1, "settler": 2, "patrol": 3, "caravan": 4, "player": 5}


@dataclass(frozen=True)
class Slot:
    """One group of actors to materialize. `count` is actors to spawn; the abstract L2 numbers behind
    it (faction strength, settlement population) are untouched, so a dissolve loses nothing."""
    id: str                        # stable: derived from place, faction, role or squad id in the save
    kind: str                      # garrison | settler | squad | caravan
    place: str                     # where the actors appear
    faction: str | None
    count: int
    role: str | None = None        # settler role, or the squad's kind (attack, patrol, garrison)
    distance: int = 0              # route hours from the player

    def rank(self) -> tuple:
        cls = self.role if self.kind == "squad" else self.kind
        if self.faction == "player":
            cls = "player"
        return (self.distance, CLASS_RANK.get(cls, max(CLASS_RANK.values()) + 1), self.id)


@dataclass
class Plan:
    centre: str
    hour: int
    radius_hours: int
    places: list[str]              # in radius, nearest first
    slots: list[Slot]              # within budget, in priority order
    dropped: list[Slot]            # over budget, in priority order; never silently cut

    def actors(self) -> int:
        return sum(s.count for s in self.slots)

    def to_dict(self) -> dict:
        return asdict(self)


# --- slot builders -------------------------------------------------------------

def garrison_size(ws: WorldState, place: str) -> int:
    """Actors the holder keeps visible at `place`; 0 when nobody holds it. Settlement guards are
    settler slots, not garrison, so they are not counted twice."""
    pl = ws.places[place]
    if pl.holder is None:
        return 0
    n = GARRISON_BASE + GARRISON_PER_DEFENCE * pl.defence
    n += min(ws.factions[pl.holder].strength, GARRISON_STRENGTH_SHARE_CAP) // 2
    return min(GARRISON_MAX, n)


def _squad_place(ws: WorldState, q) -> str:
    """The end of its route a travelling squad is nearer to, from its departure (eta minus route hours). Route hours
    are the shortest path, as manage.send_supplies times a multi-hop caravan (Codex review of #431)."""
    if q.goal is None or q.goal == q.at:
        return q.at
    hours = _distances(ws, q.at).get(q.goal)
    if not hours:
        return q.at
    elapsed = ws.hour - (q.eta - hours)
    return q.goal if 2 * elapsed >= hours else q.at


def _id_component(value: str) -> str:
    """Escape the slot separator and its escape marker; ordinary existing identities stay unchanged."""
    return value.replace("%", "%25").replace(":", "%3A")


def _place_slots(ws: WorldState, place: str, dist: int) -> list[Slot]:
    out = []
    pl = ws.places[place]
    n = garrison_size(ws, place)
    if n:
        # Two arbitrary ids need boundaries: ("region:camp", "raiders") must differ from
        # ("region", "camp:raiders"). Keep the actual place/faction data unchanged.
        sid = f"garrison:{_id_component(place)}:{_id_component(pl.holder)}"
        out.append(Slot(sid, "garrison", place, pl.holder, n, distance=dist))
    s = ws.settlements.get(place)
    if s:
        for role in ROLES:
            k = min(SETTLERS_PER_ROLE_MAX, s.roles.get(role, 0))
            if k:
                out.append(Slot(f"settler:{place}:{role}", "settler", place, pl.holder, k, role, dist))
    return out


def _squad_slots(ws: WorldState, dist: dict[str, int], radius: int) -> list[Slot]:
    out = []
    for qid in sorted(ws.squads):
        q = ws.squads[qid]
        ends = [p for p in (q.at, q.goal) if p is not None and dist.get(p, radius + 1) <= radius]
        if not ends:
            continue
        where = _squad_place(ws, q)
        d = dist.get(where)
        if d is None or d > radius:        # still at its far end: not here yet, never shown ahead of its ETA (Codex, #431)
            continue
        if q.kind == "caravan":
            out.append(Slot(f"caravan:{qid}", "caravan", where, q.faction, CARAVAN_ACTORS, "caravan", d))
        else:
            out.append(Slot(f"squad:{qid}", "squad", where, q.faction, min(SQUAD_ACTORS_MAX, q.size),
                            q.kind, d))
    return out


# --- planning ------------------------------------------------------------------

def plan(ws: WorldState, player_place: str, radius_hours: int = RADIUS_HOURS,
         max_actors: int = MAX_LIVE_ACTORS) -> Plan:
    """Slots to materialize around `player_place`: garrisons and settlers of every place within
    `radius_hours` by route, plus squads and caravans with an end inside it. Slots are ordered nearest
    first, then by class, then id; whole slots are kept while they fit `max_actors`, the rest are
    listed in `dropped`. Reads ws only."""
    if player_place not in ws.places:
        raise KeyError(f"unknown place {player_place!r}")
    dist = _distances(ws, player_place)
    near = sorted((d, p) for p, d in dist.items() if d <= radius_hours)
    slots: list[Slot] = []
    for d, p in near:
        slots.extend(_place_slots(ws, p, d))
    slots.extend(_squad_slots(ws, dist, radius_hours))
    slots.sort(key=Slot.rank)
    kept, dropped, used = [], [], 0
    for s in slots:
        if used + s.count <= max_actors:
            kept.append(s)
            used += s.count
        else:
            dropped.append(s)
    return Plan(player_place, ws.hour, radius_hours, [p for _, p in near], kept, dropped)


class Diff(NamedTuple):
    spawn: list[Slot]       # in new only, or changed (new version)
    keep: list[Slot]        # identical in both
    dissolve: list[Slot]    # in old only, or changed (old version)


def diff(old: Plan | None, new: Plan) -> Diff:
    """What moving from `old` to `new` spawns, keeps and dissolves. A slot is matched by id; one whose
    place, faction or count changed is dissolved and spawned again. Lists are sorted by id.
    Duplicate ids in either input are refused rather than silently dropping a group."""
    before = {s.id: s for s in old.slots} if old else {}
    after = {s.id: s for s in new.slots}
    if old is not None and len(before) != len(old.slots):
        raise ValueError("old presence plan has duplicate slot ids")
    if len(after) != len(new.slots):
        raise ValueError("new presence plan has duplicate slot ids")
    spawn, keep, dissolve = [], [], []
    for sid in sorted(set(before) | set(after)):
        a, b = before.get(sid), after.get(sid)
        if a is None:
            spawn.append(b)
        elif b is None:
            dissolve.append(a)
        elif (a.place, a.faction, a.count) == (b.place, b.faction, b.count):
            keep.append(b)
        else:
            dissolve.append(a)
            spawn.append(b)
    return Diff(spawn, keep, dissolve)
