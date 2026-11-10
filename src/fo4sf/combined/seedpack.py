"""Turn a seed draft (seed.py) into a pack that runs: holders, factions, homes, routes and settlement stats by rules.

generate(draft, rules, gateways) returns (pack, report). The pack passes pack.validate_pack, loads into a WorldState
and runs under sim.run with the balance invariants kept (homes and story locks never change hands, which the simulation
enforces by construction). Route hours are data-relative (each world's median route distance is a placeholder number
of hours), so no claim about a game's units is needed. Deterministic: the same draft and rules give byte-identical JSON (sorted walks, no
randomness, no clock).

Every number and name in DEFAULT_RULES is a PLACEHOLDER to argue with, except where a comment names the first real
run (owner's PC, 2026-10-21, Fallout4.esm + DLCRobot.esm + DLCworkshop01.esm) as support. Keyword and faction
editor ids are read from the draft; nothing here states what a game's records contain beyond the keyword names that
run listed (LocTypeWorkshop, LocTypeWorkshopSettlement, LocTypeSettlement, LocEncRaiders, LocEncSuperMutants,
LocEncGhouls, and from its seed-pack report LocEncGunners plus the then-unmapped LocEncBoS, Bugs, CoA, Deathclaw,
Mirelurks, Molerats, Robots, Synths, Wildlife) and the ref type WorkshopRefType. The pack's factions are its own small set (settlers plus each enemy
the rules map), not the draft's hundreds of FACT records; FACT relation data is carried only where an edid matches a
rules pattern, otherwise the placeholder relations apply.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
from collections import Counter

from . import seed as _seed
from .model import STRENGTH_CAP
from .pack import validate_pack

# LocEnc<X> keywords: the <X> part names what is encountered at the place; the first run listed Raiders (39),
# SuperMutants (24) and Ghouls (27), and its seed-pack report then listed the unmapped <X> values BoS 2, Bugs 4,
# CoA 2, Deathclaw 1, Mirelurks 6, Molerats 1, Robots 8, Synths 5, Wildlife 5. An unmapped one is reported, not
# guessed. The pack faction ids on the right are our own names.
ENC_KEYWORD = re.compile(r"^LocEnc(\w+)$")
_NO_GATEWAYS = object()

DEFAULT_RULES = {
    # Pack faction that holds every settlement candidate at the start (our name; placeholder).
    "settlers": "settlers",
    # LocEnc<X> -> pack faction id. Raiders, SuperMutants and Ghouls are supported by the first run's keyword counts;
    # Gunners by the seed-pack report of the same run (12 places). The creature keywords (Bugs, Deathclaw, Mirelurks,
    # Molerats, Wildlife: 17 places in that report) share one PLACEHOLDER "creatures" faction and Robots (8) a
    # PLACEHOLDER "robots" faction; both are "wild" (below). Deliberately unmapped: BoS and CoA (player factions, CC-20:
    # their holder is the owner's design decision) and Synths (whether they are a sandbox enemy or belong to a story
    # faction is the same kind of decision). An absent keyword costs nothing; an unmapped one is counted in the report.
    "enc_factions": {"Raiders": "raiders", "SuperMutants": "supermutants", "Ghouls": "ghouls", "Gunners": "gunners",
                     "Bugs": "creatures", "Deathclaw": "creatures", "Mirelurks": "creatures", "Molerats": "creatures",
                     "Wildlife": "creatures", "Robots": "robots"},
    # When a place carries keywords for several mapped factions, the one earliest in this list holds it (PLACEHOLDER
    # order: the organised enemies before the wild ones); a faction not listed sorts after the list by id.
    "enc_priority": ["raiders", "gunners", "supermutants", "ghouls", "robots", "creatures"],
    # Wild factions (PLACEHOLDER): hostile to every other faction at `wild_relation`, both ways, FACT data or not. The
    # model has no "runs no caravans" flag: caravans are dispatched by the holder of a settlement with a trader
    # (sim._dispatch_caravans), so a settlement a wild faction takes would trade with another it holds. Reported,
    # not papered over.
    "wild": ["creatures", "robots"],
    "wild_relation": -80,
    # PLACEHOLDER regex guesses on FACT editor ids -> pack faction id, for carrying the drafted XNAM relations
    # (seed.REACTION_RELATION). UNVERIFIED: the first run's report counts locations' keywords, not faction names.
    # Where no FACT matches, the placeholder relations below apply.
    "fact_patterns": {"raiders": r"raider", "supermutants": r"supermutant", "ghouls": r"ghoul|feral",
                      "gunners": r"gunner"},
    # PLACEHOLDER relations: each mapped enemy is an enemy of the settlers, enemies are neutral to one another
    # unless FACT data says otherwise.
    "enemy_of_settlers": -80,
    # Story locks (CC-21: a story place is locked to its story holder until the story passes it). PLACEHOLDER story id
    # -> regex searched on place ids; a place that matches gets story_lock = that id, kind landmark, no holder and no
    # settlement stats, so no pack faction claims it and it never changes hands (sim). Unheld because the story
    # holder is the owner's call (CC-20); the pack's factions are only those that hold sandbox ground. The ids are
    # the first run's PrydwenLocation (which the settlement regex had made a settlers settlement) and Goodneighbor,
    # plus three names the lead listed; Vault81 and TheCastle were left out: nothing in the run's report needs them
    # locked, and a lock also removes a place from growth and jobs (and shields its neighbours under story mode).
    # The report lists which ids matched, so an over-wide pattern is visible.
    "story_lock": {"story_prydwen": r"^Prydwen", "story_vault111": r"^Vault111", "story_institute": r"^Institute",
                   "story_diamondcity": r"^DiamondCity", "story_goodneighbor": r"^Goodneighbor"},
    # PLACEHOLDER strength: base + per place held, capped by the model (sim needs 6 or more to attack at all).
    "strength_base": 8,
    "strength_per_place": 2,
    # PLACEHOLDER aggression (0..100 chance weight, model.Faction): settlers defend, enemies push, wild ones roam less.
    "aggression": {"settlers": 20, "creatures": 50, "robots": 40, "default": 70},
    # PLACEHOLDER defence per kind (model.Place.defence; the fixtures use 1..4 for settlements and camps).
    "defence": {"settlement": 2, "base": 4, "landmark": 0},
    # Routes: each place with a marker joins its k nearest in the same world. PLACEHOLDER k. Hours are data-relative,
    # with no claim about what a marker unit measures: in each world the median route distance maps to
    # `median_route_hours`, the rest scale linearly, rounded half up, never below `min_route_hours`. (The first run's
    # absolute placeholder speed put 441 of 446 routes at 1 hour; the report's `route_scale` gives each world's
    # distance quantiles and the derived units per hour to tune against.)
    "k_nearest": 3,
    "median_route_hours": 3,
    "min_route_hours": 1,
    # Settlement stats: the same starting numbers the fixtures' farm_a uses (fixtures.REGION_1), PLACEHOLDERS.
    "settlement": {"population": 5, "roles": {"farmer": 3, "guard": 1, "trader": 1, "crafter": 0, "scavenger": 0,
                                               "doctor": 0},
                   "stock": {"food": 20, "water": 20, "scrap": 0, "ammo": 10, "medicine": 0},
                   "morale": 50, "stage": 0, "beds": 20},
}


def _enc_faction(place: dict, rules: dict, unmapped: Counter) -> str | None:
    """The pack faction a place's LocEnc<X> keywords map to (the first by rules["enc_priority"], then by id), or
    None. Every unmapped LocEnc keyword on the place is counted, mapped or not."""
    priority = rules.get("enc_priority", [])
    found = []
    for kw in sorted(place.get("keywords", [])):
        m = ENC_KEYWORD.match(kw)
        if not m:
            continue
        fid = rules["enc_factions"].get(m.group(1))
        if fid is not None:
            found.append(fid)
        else:
            unmapped[kw] += 1
    if not found:
        return None
    return min(found, key=lambda f: (priority.index(f) if f in priority else len(priority), f))


def _story_lock(place_id: str, rules: dict) -> str | None:
    """The story id whose rules["story_lock"] regex matches the place id (first in sorted story-id order), or None."""
    for story in sorted(rules.get("story_lock", {})):
        if re.search(rules["story_lock"][story], place_id):
            return story
    return None


def _keep(place: dict) -> str | None:
    """Why a draft place is dropped, or None to keep it: settlement candidates and places with a marker position
    stay; the rest (quest and virtual locations, unplaced parents) go."""
    if place.get("kind") == "settlement" or place.get("marker"):
        return None
    return "no marker position" if not place.get("has_marker") else "marker position not found"


def _distance(a: dict, b: dict) -> float:
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def _hours(dist: float, scale: float, rules: dict) -> int:
    """Travel hours for a marker distance: distance * scale (hours per unit), rounded half up, never below the
    minimum."""
    return max(rules["min_route_hours"], int(dist * scale + 0.5))


def _quantiles(values: list[float]) -> dict[str, float]:
    """min, p25, median, p75, max of a sorted list (nearest-rank, so no interpolation surprises); {} when empty."""
    if not values:
        return {}
    n = len(values)
    at = lambda q: values[min(n - 1, int(q * n))]  # noqa: E731
    return {"min": values[0], "p25": at(0.25), "median": _median(values), "p75": at(0.75), "max": values[-1]}


def _median(values: list[float]) -> float:
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def _routes(places: list[dict], rules: dict) -> tuple[list[dict], list[str], Counter, dict]:
    """k-nearest routes per world among marker places, undirected and deduplicated; a place without a marker joins
    its parent when the parent is kept. Hours scale per world so that world's median route distance is
    rules["median_route_hours"]. Returns (routes, isolated place ids, drop reasons for unlinked places, per-world
    route scale report)."""
    by_id = {p["id"]: p for p in places}
    edges: dict[frozenset, int] = {}
    worlds: dict[str | None, list[dict]] = {}
    for p in places:
        if p.get("marker"):
            worlds.setdefault(p["marker"].get("world"), []).append(p)
    k = rules["k_nearest"]
    scale_report = {}
    for world in sorted(worlds, key=lambda w: (w is None, w or "")):
        group = sorted(worlds[world], key=lambda p: p["id"])
        dists: dict[frozenset, float] = {}
        for p in group:
            others = sorted(((_distance(p["marker"], q["marker"]), q["id"]) for q in group if q is not p))
            for dist, qid in others[:k]:
                dists.setdefault(frozenset((p["id"], qid)), dist)
        ordered = sorted(dists.values())
        median = _median(ordered) if ordered else 0.0
        scale = rules["median_route_hours"] / median if median > 0 else 0.0
        for edge in sorted(dists, key=lambda e: tuple(sorted(e))):
            edges[edge] = _hours(dists[edge], scale, rules)
        scale_report[world] = {
            "places": len(group), "routes": len(dists), "distance": _quantiles(ordered),
            "units_per_hour": (1 / scale) if scale else None,
            "route_hours": dict(sorted(Counter(edges[e] for e in dists).items())),
        }
    unlinked = Counter()
    for p in places:
        if p.get("marker"):
            continue
        parent = p.get("parent")
        if parent in by_id and parent != p["id"]:
            edges.setdefault(frozenset((p["id"], parent)), rules["min_route_hours"])  # PLACEHOLDER: the minimum
        else:
            unlinked["no marker and parent not kept"] += 1
    routes = sorted(({"a": min(e), "b": max(e), "hours": h} for e, h in edges.items()),
                    key=lambda r: (r["a"], r["b"]))
    linked = {r["a"] for r in routes} | {r["b"] for r in routes}
    isolated = sorted(p["id"] for p in places if p["id"] not in linked)
    return routes, isolated, unlinked, {str(w): v for w, v in scale_report.items()}


def _neighbours(routes: list[dict]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for r in routes:
        out.setdefault(r["a"], set()).add(r["b"])
        out.setdefault(r["b"], set()).add(r["a"])
    return out


def _gateway_routes(gateways: object, places: list[dict]) -> tuple[list[dict], dict | None]:
    """Validate the entire explicit list before using any edge (G1–G5, combined-core-gateways.md).

    Ends name kept draft ids; their worlds are marker.world, never the root-location region.
    No list or a valid empty list leaves even the report unchanged. A refused list reports no used pairs.
    """
    if gateways is _NO_GATEWAYS:
        return [], None
    report = {"pairs": [], "world_pairs": [], "hours": {}, "problems": []}
    problems = report["problems"]
    if not isinstance(gateways, dict) or set(gateways) != {"gateways"} or not isinstance(gateways["gateways"], list):
        problems.append('G5: expected an object with only a "gateways" list')
        return [], report
    if not gateways["gateways"]:
        return [], None
    by_id = {p["id"]: p for p in places}
    seen, routes, world_pairs = set(), [], Counter()
    for index, entry in enumerate(gateways["gateways"]):
        where = f"gateway {index + 1}"
        if not isinstance(entry, dict) or set(entry) != {"a", "b", "hours"}:
            problems.append(f"G5: {where} must have exactly a, b and hours")
            continue
        a, b, hours = entry["a"], entry["b"], entry["hours"]
        if not isinstance(hours, int) or isinstance(hours, bool) or hours <= 0:
            problems.append(f"G3: {where} hours must be a positive integer (not a boolean)")
        if any(not isinstance(pid, str) or pid not in by_id for pid in (a, b)):
            problems.append(f"G1: {where} ends must name kept places; got {a!r}, {b!r}")
            continue
        pair = (min(a, b), max(a, b))
        if pair in seen:
            problems.append(f"G4: {where} repeats the unordered pair {pair!r}")
        seen.add(pair)
        worlds = [(by_id[pid].get("marker") or {}).get("world") for pid in pair]
        if any(not isinstance(w, str) or not w for w in worlds) or worlds[0] == worlds[1]:
            problems.append(f"G2: {where} ends must have different marker worlds")
            continue
        routes.append({"a": pair[0], "b": pair[1], "hours": hours})
        world_pairs[tuple(sorted(worlds))] += 1
    if problems:
        return [], report
    routes.sort(key=lambda r: (r["a"], r["b"]))
    report["pairs"] = routes
    report["world_pairs"] = [{"a": a, "b": b, "count": n} for (a, b), n in sorted(world_pairs.items())]
    report["hours"] = dict(sorted(Counter(r["hours"] for r in routes).items()))
    return routes, report


def _home(fid: str, held: list[str], holder: dict[str, str | None], nbrs: dict[str, set[str]]) -> str:
    """The held place with the most neighbours held by the same faction; ties go to the smaller id."""
    return min(held, key=lambda pid: (-sum(holder.get(n) == fid for n in nbrs.get(pid, ())), pid))


def _fact_relations(draft: dict, rules: dict) -> tuple[dict[str, dict[str, int]], dict[str, list[str]]]:
    """Relations between pack factions carried from the drafted FACT records whose editor ids match
    rules["fact_patterns"]: for each pair, the first matching FACT (sorted by id) that has a relation to any FACT
    matching the other side, mapped through seed.REACTION_RELATION. Also returns which FACT ids matched."""
    rx = {fid: re.compile(pat, re.I) for fid, pat in sorted(rules["fact_patterns"].items())}
    matched: dict[str, list[str]] = {fid: [] for fid in rx}
    facts = {f["id"]: f for f in draft.get("factions", [])}
    for name in sorted(facts):
        for fid, r in rx.items():
            if r.search(name):
                matched[fid].append(name)
    rel: dict[str, dict[str, int]] = {}
    for a, names_a in sorted(matched.items()):
        for b, names_b in sorted(matched.items()):
            if a == b:
                continue
            for name in names_a:
                hits = [facts[name]["relations"][o] for o in sorted(facts[name]["relations"]) if o in names_b]
                if hits:
                    rel.setdefault(a, {})[b] = _seed.REACTION_RELATION.get(hits[0]["reaction"], 0)
                    break
    return rel, {k: v for k, v in matched.items() if v}


def generate(draft: dict, rules: dict | None = None, gateways: object = _NO_GATEWAYS) -> tuple[dict, dict]:
    """(pack, report) from a seed draft by DEFAULT_RULES (or `rules`, same keys).

    Optional gateways is {"gateways": [{"a": kept_id, "b": kept_id, "hours": positive_int}]}.
    Any G1–G5 problem refuses the whole list, recording plain-word problems in report["gateways"].
    """
    rules = copy.deepcopy(DEFAULT_RULES if rules is None else rules)
    settlers = rules["settlers"]
    drops, unmapped, holder, kinds, locks = Counter(), Counter(), {}, {}, {}
    kept = []
    for p in sorted(draft.get("places", []), key=lambda p: p["id"]):
        why = _keep(p)
        if why:
            drops[why] += 1
            continue
        kept.append(p)
        story = _story_lock(p["id"], rules)
        if story:
            locks[p["id"]] = story
            holder[p["id"]], kinds[p["id"]] = None, "landmark"
            _enc_faction(p, rules, unmapped)   # still counts its unmapped keywords
        elif p["kind"] == "settlement":
            holder[p["id"]], kinds[p["id"]] = settlers, "settlement"
        else:
            enemy = _enc_faction(p, rules, unmapped)
            holder[p["id"]] = enemy
            kinds[p["id"]] = "base" if enemy else ("landmark" if p["kind"] not in ("base", "landmark") else p["kind"])
    routes, _, unlinked, route_scale = _routes(kept, rules)
    gateway_routes, gateway_report = _gateway_routes(gateways, kept)
    routes = sorted(routes + gateway_routes, key=lambda r: (r["a"], r["b"]))
    nbrs = _neighbours(routes)
    isolated = sorted(p["id"] for p in kept if p["id"] not in nbrs)

    places = []
    for p in kept:
        place = {"id": p["id"], "region": p["region"], "kind": kinds[p["id"]], "holder": holder[p["id"]],
                 "defence": rules["defence"][kinds[p["id"]]]}
        if p["id"] in locks:
            place["story_lock"] = locks[p["id"]]
        places.append(place)
    settlements = [dict(place=p["id"], **copy.deepcopy(rules["settlement"])) for p in kept
                   if kinds[p["id"]] == "settlement"]

    held: dict[str, list[str]] = {}
    for pid in sorted(holder):
        if holder[pid]:
            held.setdefault(holder[pid], []).append(pid)
    fact_rel, fact_matched = _fact_relations(draft, rules)
    factions, factions_dropped = [], []
    wanted = sorted({settlers, *rules["enc_factions"].values()})
    wild = set(rules.get("wild", []))
    for fid in wanted:
        if fid not in held:
            factions_dropped.append(fid)          # holds nothing, so it can have no home
            continue
        rel = {}
        for other in wanted:
            if other == fid or other not in held:
                continue
            if wild & {fid, other}:
                rel[other] = rules["wild_relation"]
            elif other in fact_rel.get(fid, {}):
                rel[other] = fact_rel[fid][other]
            elif settlers in (fid, other):
                rel[other] = rules["enemy_of_settlers"]
        factions.append({
            "id": fid,
            "strength": min(STRENGTH_CAP, rules["strength_base"] + rules["strength_per_place"] * len(held[fid])),
            "home": _home(fid, held[fid], holder, nbrs),
            "aggression": rules["aggression"].get(fid, rules["aggression"]["default"]),
            "relations": rel,
        })
    pack = {"places": places, "settlements": settlements, "factions": factions, "routes": routes}
    problems = validate_pack(pack)
    report = {
        "source_plugins": draft.get("source_plugins", []),
        "draft_places": len(draft.get("places", [])), "kept": len(kept), "dropped": dict(sorted(drops.items())),
        "kinds": dict(sorted(Counter(kinds.values()).items())),
        "holders": {fid: len(v) for fid, v in sorted(held.items())},
        "unheld": sum(1 for v in holder.values() if v is None),
        "unmapped_enc_keywords": dict(sorted(unmapped.items())),
        "factions": [f["id"] for f in factions], "factions_dropped_no_place": factions_dropped,
        "fact_relations_carried": {a: dict(sorted(b.items())) for a, b in sorted(fact_rel.items())
                                   if a in {f["id"] for f in factions}},
        "fact_ids_matched": fact_matched,
        "homes": {f["id"]: f["home"] for f in factions},
        "story_locked": dict(sorted(locks.items())),
        "routes": len(routes), "route_hours": dict(sorted(Counter(r["hours"] for r in routes).items())),
        "route_scale": route_scale,
        "isolated": isolated, "unlinked": dict(sorted(unlinked.items())),
        "worlds": {str(w): n for w, n in sorted(Counter(p["marker"].get("world") for p in kept if p.get("marker")).items(),
                                                key=lambda kv: (kv[0] is None, kv[0] or ""))},   # str like route_scale
        "validation_problems": problems,
        "rules": rules,
    }
    if gateway_report is not None:
        report["gateways"] = gateway_report
    return pack, report


def write(out_dir: str, pack: dict, report: dict) -> dict:
    """Write commonwealth.pack.json and seedpack_report.json into out_dir; return the two paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {"pack": os.path.join(out_dir, "commonwealth.pack.json"),
             "report": os.path.join(out_dir, "seedpack_report.json")}
    with open(paths["pack"], "w", encoding="utf-8") as f:
        f.write(dumps(pack))
    with open(paths["report"], "w", encoding="utf-8") as f:
        f.write(dumps(report))
    return paths


def dumps(obj) -> str:
    """The canonical JSON text: sorted keys, one-space indent, trailing newline (byte-identical for equal input)."""
    return json.dumps(obj, indent=1, sort_keys=True) + "\n"


def summary(report: dict) -> str:
    """One line for the command line."""
    return (f"seed-pack: {report['kept']} of {report['draft_places']} places kept, "
            f"{len(report['factions'])} factions, {report['routes']} routes, {len(report['isolated'])} isolated, "
            f"{len(report['validation_problems'])} validation problems")
