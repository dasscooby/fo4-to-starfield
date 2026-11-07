"""L5 content packs: JSON that only ever adds places, settlements, factions and routes to a WorldState.

A pack is a dict with the lists "places", "settlements", "factions" and "routes" (each optional) whose entries
are the keyword arguments of the matching model dataclass. validate_pack lists every problem it finds in plain
words; load_pack refuses a pack with any problem, so a half-loaded world never happens. A second pack may refer
to things an earlier pack loaded (a route to its gateway, a relation to its faction): that is how a second
region plugs in without the first knowing about it.
"""
from __future__ import annotations

import dataclasses
import json

from .model import (GOODS, PLACE_KINDS, ROLES, STRENGTH_CAP, Faction, Place, Reputation, Route, Settlement,
                    WorldState)

SECTIONS = ("places", "settlements", "factions", "routes")
_REQUIRED = {
    "places": ("id", "region", "kind"),
    "settlements": ("place",),
    "factions": ("id", "strength", "home"),
    "routes": ("a", "b", "hours"),
}
_FIELDS = {
    "places": {f.name for f in dataclasses.fields(Place)},
    "settlements": {f.name for f in dataclasses.fields(Settlement)},
    "factions": {f.name for f in dataclasses.fields(Faction)},
    "routes": {f.name for f in dataclasses.fields(Route)},
}


def _is_id(v) -> bool:
    """A reference to a place or faction: JSON can carry any value, but only a non-empty string can be a key. ASCII
    only: the in-game port walks ids in byte order, which matches Python's sort only for ASCII
    (docs/combined-core-cpp-port.md section 3, "Order")."""
    return isinstance(v, str) and v != "" and v.isascii()


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _entries(pack: dict, section: str, problems: list[str]) -> list[dict]:
    """The section's dict entries that have every required key; others are reported and skipped."""
    items = pack.get(section, [])
    if not isinstance(items, list):
        problems.append(f"{section}: must be a list")
        return []
    out = []
    for n, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"{section}[{n}]: must be an object")
            continue
        missing = [k for k in _REQUIRED[section] if k not in item]
        unknown = sorted(set(item) - _FIELDS[section])
        if missing:
            problems.append(f"{section}[{n}]: missing {', '.join(missing)}")
        if unknown:
            problems.append(f"{section}[{n}]: unknown keys {', '.join(unknown)}")
        if not missing and not unknown:
            out.append(item)
    return out


def validate_pack(pack: dict, ws: WorldState | None = None) -> list[str]:
    """Return human-readable problems with the pack (empty when it may be loaded into ws)."""
    problems: list[str] = []
    if not isinstance(pack, dict):
        return ["pack must be an object"]
    for key in pack:
        if key not in SECTIONS:
            problems.append(f"unknown section {key!r}")
    places = _entries(pack, "places", problems)
    settlements = _entries(pack, "settlements", problems)
    factions = _entries(pack, "factions", problems)
    routes = _entries(pack, "routes", problems)

    known_places = dict(ws.places) if ws else {}
    known_factions = set(ws.factions) if ws else set()
    new_places: dict[str, dict] = {}
    for p in places:
        pid = p["id"]
        if not _is_id(pid):
            problems.append(f"place id {pid!r}: must be a non-empty ASCII string")
            continue
        if pid in known_places or pid in new_places:
            problems.append(f"place {pid}: already defined (packs only add)")
            continue
        if not _is_id(p["region"]):
            problems.append(f"place {pid}: region {p['region']!r} must be a non-empty ASCII string")
        if p["kind"] not in PLACE_KINDS:
            problems.append(f"place {pid}: kind {p['kind']!r} not in {', '.join(PLACE_KINDS)}")
        if not _is_int(p.get("defence", 0)) or p.get("defence", 0) < 0:
            problems.append(f"place {pid}: defence must be a non-negative integer")
        lock = p.get("story_lock")
        if lock is not None and not _is_id(lock):    # Place.story_lock is str | None; the sim tests it by truthiness
            problems.append(f"place {pid}: story_lock {lock!r} must be a story id (a non-empty ASCII string) or null")
        new_places[pid] = p
    new_factions = {}
    for f in factions:
        fid = f["id"]
        if not _is_id(fid):
            problems.append(f"faction id {fid!r}: must be a non-empty ASCII string")
            continue
        if fid in known_factions or fid in new_factions:
            problems.append(f"faction {fid}: already defined (packs only add)")
            continue
        new_factions[fid] = f
    all_factions = known_factions | set(new_factions)
    all_places = set(known_places) | set(new_places)

    def holder_of(pid: str):
        if pid in new_places:
            return new_places[pid].get("holder")
        return known_places[pid].holder if pid in known_places else None

    for pid, p in new_places.items():
        holder = p.get("holder")
        if holder is not None and not _is_id(holder):
            problems.append(f"place {pid}: holder {holder!r} must be a faction id (an ASCII string) or null")
        elif holder is not None and holder not in all_factions:
            problems.append(f"place {pid}: holder {holder!r} is not a known faction")

    for fid, f in new_factions.items():
        if not _is_int(f["strength"]) or not 0 <= f["strength"] <= STRENGTH_CAP:
            problems.append(f"faction {fid}: strength must be an integer in 0..{STRENGTH_CAP}")
        agg = f.get("aggression", 50)
        if not _is_int(agg) or not 0 <= agg <= 100:
            problems.append(f"faction {fid}: aggression must be in 0..100")
        home = f["home"]
        if not _is_id(home):
            problems.append(f"faction {fid}: home {home!r} must be a place id (an ASCII string)")
        elif home not in all_places:
            problems.append(f"faction {fid}: home {home!r} is not a known place")
        elif holder_of(home) != fid:
            problems.append(f"faction {fid}: home {home} is held by {holder_of(home)!r}, not {fid}")
        rel = f.get("relations", {})
        if not isinstance(rel, dict):
            problems.append(f"faction {fid}: relations must be an object")
            continue
        for other, v in rel.items():
            if other not in all_factions:
                problems.append(f"faction {fid}: relation to unknown faction {other!r}")
            if not _is_int(v) or not -100 <= v <= 100:
                problems.append(f"faction {fid}: relation to {other} must be in -100..100")

    seen_settlements = set(ws.settlements) if ws else set()
    for s in settlements:
        pid = s["place"]
        if not _is_id(pid):
            problems.append(f"settlement place {pid!r}: must be a place id (an ASCII string)")
            continue
        if pid in seen_settlements:
            problems.append(f"settlement {pid}: already defined (packs only add)")
            continue
        seen_settlements.add(pid)
        if pid not in all_places:
            problems.append(f"settlement {pid}: place is not known")
        elif (new_places[pid]["kind"] if pid in new_places else known_places[pid].kind) != "settlement":
            problems.append(f"settlement {pid}: place is not of kind settlement")
        _check_counts(f"settlement {pid}", "roles", s.get("roles", {}), ROLES, problems)
        _check_counts(f"settlement {pid}", "stock", s.get("stock", {}), GOODS, problems)
        pop = s.get("population", 0)
        beds = s.get("beds", 20)
        if not _is_int(pop) or pop < 0:
            problems.append(f"settlement {pid}: population must be a non-negative integer")
        elif isinstance(s.get("roles", {}), dict) and all(_is_int(v) for v in s.get("roles", {}).values()):
            if sum(s.get("roles", {}).values()) != pop:
                problems.append(f"settlement {pid}: roles sum to {sum(s.get('roles', {}).values())}, population is {pop}")
            if _is_int(beds) and pop > beds:
                problems.append(f"settlement {pid}: population {pop} exceeds beds {beds}")
        for key, lo, hi in (("morale", 0, 100), ("stage", 0, 4)):
            v = s.get(key, lo)
            if not _is_int(v) or not lo <= v <= hi:
                problems.append(f"settlement {pid}: {key} must be in {lo}..{hi}")
        if not _is_int(beds) or beds < 0:
            problems.append(f"settlement {pid}: beds must be a non-negative integer")
        pr = s.get("priority")
        if pr is not None and pr not in GOODS:
            problems.append(f"settlement {pid}: priority must be one of {', '.join(GOODS)} or null")

    edges = {frozenset((r.a, r.b)) for r in ws.routes} if ws else set()
    for r in routes:
        a, b = r["a"], r["b"]
        if not (_is_id(a) and _is_id(b)):
            problems.append(f"route {a!r}-{b!r}: both ends must be place ids (ASCII strings)")
            continue
        for end in (a, b):
            if end not in all_places:
                problems.append(f"route {a}-{b}: {end!r} is not a known place")
        if a == b:
            problems.append(f"route {a}-{b}: joins a place to itself")
        if not _is_int(r["hours"]) or r["hours"] <= 0:
            problems.append(f"route {a}-{b}: hours must be a positive integer")
        edge = frozenset((a, b))
        if edge in edges:
            problems.append(f"route {a}-{b}: duplicate edge")
        edges.add(edge)
    return problems


def _check_counts(who: str, what: str, counts, keys: tuple[str, ...], problems: list[str]) -> None:
    if not isinstance(counts, dict):
        problems.append(f"{who}: {what} must be an object")
        return
    for k, v in counts.items():
        if k not in keys:
            problems.append(f"{who}: unknown {what} key {k!r}")
        elif not _is_int(v) or v < 0:
            problems.append(f"{who}: {what}[{k}] must be a non-negative integer")


def load_pack(ws: WorldState, pack: dict) -> None:
    """Validate the pack against ws, then add its data. Raises ValueError listing every problem."""
    problems = validate_pack(pack, ws)
    if problems:
        raise ValueError("invalid pack:\n  " + "\n  ".join(problems))
    for p in pack.get("places", []):
        ws.places[p["id"]] = Place(**p)
    for s in pack.get("settlements", []):
        s = dict(s)
        # partial role/stock tables are filled with zeros so the sim can index every key
        s["roles"] = {r: s.get("roles", {}).get(r, 0) for r in ROLES}
        s["stock"] = {g: s.get("stock", {}).get(g, 0) for g in GOODS}
        ws.settlements[s["place"]] = Settlement(**s)
    for f in pack.get("factions", []):
        ws.factions[f["id"]] = Faction(**f)
        ws.reputation.setdefault(f["id"], Reputation())
    for r in pack.get("routes", []):
        ws.routes.append(Route(**r))


def load_pack_file(ws: WorldState, path: str) -> None:
    """Load a JSON pack from disk (UTF-8)."""
    with open(path, encoding="utf-8") as f:
        pack = json.load(f)
    load_pack(ws, pack)
