"""L1 world-state model for the combined core (paper prototype, not game code).

Game-neutral: nothing here knows Starfield or Fallout record layouts. A content pack
(L5) supplies places, factions and routes as data; the simulation (sim.py) advances
the state; an engine adapter (later) maps it to globals, aliases or an SFSE co-save.

All names in the synthetic scenario are placeholders, not game facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
import types
import typing

from .modes import Settings

GOODS = ("food", "water", "scrap", "ammo", "medicine")
ROLES = ("farmer", "guard", "trader", "crafter", "scavenger", "doctor")
PLACE_KINDS = ("settlement", "base", "landmark", "gateway")

# Bump when a saved state's shape changes; from_json refuses anything it cannot upgrade so a stale or
# foreign save fails loudly instead of loading half-right. Version 2 added settings and regional_reputation;
# a version-1 save loads with their defaults.
SCHEMA_VERSION = 2
LOADABLE_SCHEMAS = (1, 2)

# Upper bound on Faction.strength. Lives here so packs are validated against the same number the
# simulation clamps to; otherwise an oversized faction would run unclamped until its first daily step.
STRENGTH_CAP = 60


@dataclass
class Place:
    id: str
    region: str
    kind: str                     # settlement | base | landmark | gateway
    holder: str | None = None     # faction id holding it, None if empty
    story_lock: str | None = None  # story id that pins the holder (CC-21)
    defence: int = 0


@dataclass
class Settlement:
    place: str
    population: int = 0
    roles: dict[str, int] = field(default_factory=lambda: {r: 0 for r in ROLES})
    stock: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GOODS})
    morale: int = 50              # 0..100
    stage: int = 0                # growth stage, 0..4
    beds: int = 20                # population cap until the player or a stage adds more
    priority: str | None = None   # good the settlement focuses on (manage.set_priority); sim adds a bonus.
                                  # Defaults, so a schema-2 save without it still loads.


@dataclass
class Faction:
    id: str
    strength: int                 # abstract manpower
    home: str                     # place id that never changes hands
    aggression: int = 50          # 0..100, chance weight to attack
    relations: dict[str, int] = field(default_factory=dict)  # other faction -> -100..100


@dataclass
class Squad:
    id: str
    faction: str
    size: int
    at: str                       # place id
    goal: str | None = None       # target place id
    kind: str = "patrol"          # patrol | attack | caravan
    cargo: dict[str, int] = field(default_factory=dict)
    eta: int = 0                  # game hour of arrival at goal


@dataclass
class Route:
    a: str
    b: str
    hours: int                    # travel time in game hours


@dataclass
class Reputation:
    fame: int = 0
    infamy: int = 0


@dataclass
class WorldState:
    seed: int
    hour: int = 0
    places: dict[str, Place] = field(default_factory=dict)
    settlements: dict[str, Settlement] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)
    squads: dict[str, Squad] = field(default_factory=dict)
    routes: list[Route] = field(default_factory=list)
    reputation: dict[str, Reputation] = field(default_factory=dict)  # faction -> player rep
    events: list[dict] = field(default_factory=list)
    next_id: int = 1
    # schema 2: region -> faction -> rep, overriding `reputation` there (CC-22; empty in a one-world game)
    regional_reputation: dict[str, dict[str, Reputation]] = field(default_factory=dict)
    settings: Settings = field(default_factory=Settings)   # schema 2: play settings (modes.py)

    def neighbours(self, place: str) -> list[tuple[str, int]]:
        out = []
        for r in self.routes:
            if r.a == place:
                out.append((r.b, r.hours))
            elif r.b == place:
                out.append((r.a, r.hours))
        return sorted(out)

    def to_json(self) -> str:
        d = asdict(self)
        d["schema"] = SCHEMA_VERSION
        return json.dumps(d, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "WorldState":
        d = json.loads(text)
        if not isinstance(d, dict):               # a list or number is not a world state (Codex review of #431)
            raise ValueError(f"a world state is a JSON object, not {type(d).__name__}")
        if d.get("schema") not in LOADABLE_SCHEMAS:
            raise ValueError(f"unknown world-state schema {d.get('schema')!r}, want one of {LOADABLE_SCHEMAS}")
        try:
            return cls._from_dict(d)
        except (KeyError, TypeError, AttributeError) as e:   # a missing or misshapen field (Codex review of #431)
            raise ValueError(f"world state is malformed: {type(e).__name__}: {e}") from e

    @classmethod
    def _from_dict(cls, d: dict) -> "WorldState":
        for k in ("seed", "hour", "next_id"):           # (Codex review of #431)
            if not isinstance(d.get(k), int) or isinstance(d.get(k), bool):
                raise ValueError(f"world state {k} must be an integer, not {d.get(k)!r}")
        if d["seed"] < 0 or d["hour"] < 0 or d["seed"] * 1_000_003 + d["hour"] >= 2 ** 64:
            raise ValueError(f"world state seed {d['seed']} and hour {d['hour']} are outside the RNG's range "
                             "(seed * 1000003 + hour must fit in 64 unsigned bits; sim.rng_seed)")
        ws = cls(seed=d["seed"], hour=d["hour"], next_id=d["next_id"])
        ws.places = {k: Place(**v) for k, v in d["places"].items()}
        ws.settlements = {k: Settlement(**v) for k, v in d["settlements"].items()}
        ws.factions = {k: Faction(**v) for k, v in d["factions"].items()}
        ws.squads = {k: Squad(**v) for k, v in d["squads"].items()}
        ws.routes = [Route(**r) for r in d["routes"]]
        ws.reputation = {k: Reputation(**v) for k, v in d["reputation"].items()}
        ws.events = d["events"]
        if not isinstance(ws.events, list) or not all(_event_ok(e) for e in ws.events):   # (Codex review of #431)
            raise ValueError("world state events must be objects with an integer hour and string kind and place")
        ws.regional_reputation = {region: {k: Reputation(**v) for k, v in layer.items()}
                                  for region, layer in d.get("regional_reputation", {}).items()}
        ws.settings = Settings.from_dict(d.get("settings"))
        _check_state(ws)
        return ws


def _type_ok(value, hint) -> bool:
    """`value` matches a field hint of the simple shapes the model uses: int (not bool), str, None, a union of
    those, dict[str, int] and dict[str, int | None]."""
    if hint is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if hint is str:
        return isinstance(value, str)
    if hint is type(None):
        return value is None
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin in (typing.Union, types.UnionType):
        return any(_type_ok(value, a) for a in args)
    if origin is dict:
        return isinstance(value, dict) and all(_type_ok(k, args[0]) and _type_ok(v, args[1]) for k, v in value.items())
    return True                                   # shapes checked elsewhere (events, settings)


def _check_record(what: str, rec) -> None:
    for name, hint in typing.get_type_hints(type(rec)).items():
        if not _type_ok(getattr(rec, name), hint):
            raise ValueError(f"world state {what}.{name} is {getattr(rec, name)!r}, not a {hint}")


def _check_state(ws: "WorldState") -> None:
    """Field types of every restored record, references that name restored places and factions, and routes that
    join known places in a positive whole number of hours, so a misshapen save fails here with a ValueError instead of a TypeError deep in a tick (Codex review
    of #431)."""
    for table in ("places", "settlements", "factions", "squads", "reputation"):
        for k, rec in getattr(ws, table).items():
            if not k.isascii():                   # the in-game port orders ids by byte (pack._is_id)
                raise ValueError(f"world state {table} id {k!r} must be ASCII")
            _check_record(f"{table}[{k!r}]", rec)
    for region, layer in ws.regional_reputation.items():
        for k, rec in layer.items():
            _check_record(f"regional_reputation[{region!r}][{k!r}]", rec)
    known = lambda ref, table: ref is None or ref in getattr(ws, table)
    for k, pl in ws.places.items():
        if pl.id != k or not known(pl.holder, "factions"):
            raise ValueError(f"world state places[{k!r}] must carry its own id and a known holder, not {pl.holder!r}")
    for k, st in ws.settlements.items():
        if st.place != k or k not in ws.places:
            raise ValueError(f"world state settlements[{k!r}] must belong to a known place of the same id")
    for k, f in ws.factions.items():
        if f.id != k or f.home not in ws.places:
            raise ValueError(f"world state factions[{k!r}] must carry its own id and a known home")
    for k, q in ws.squads.items():
        owner_ok = q.faction in ws.factions or q.faction == "player"   # sim.player_defended's garrison
        if q.id != k or not owner_ok or q.at not in ws.places or not known(q.goal, "places"):
            raise ValueError(f"world state squads[{k!r}] must name a known faction, place and goal")
    layers = [ws.reputation, *ws.regional_reputation.values()]
    if any(k not in ws.factions for layer in layers for k in layer):
        raise ValueError("world state reputation must name known factions")
    if any(k not in ws.reputation for k in ws.factions):    # adapter.game_view reads one per faction (Grok, #431)
        raise ValueError("world state reputation needs a row for every faction")
    for n, r in enumerate(ws.routes):
        _check_record(f"routes[{n}]", r)
        if r.a not in ws.places or r.b not in ws.places or r.hours <= 0:
            raise ValueError(f"world state routes[{n}] must join two known places in a positive number of hours")


def _event_ok(e) -> bool:
    return (isinstance(e, dict) and isinstance(e.get("hour"), int) and not isinstance(e.get("hour"), bool)
            and isinstance(e.get("kind"), str) and isinstance(e.get("place"), str))


def load_pack(ws: WorldState, pack: dict) -> None:
    """Add a validated content pack (L5). Thin alias of pack.load_pack, kept for callers."""
    from . import pack as _pack  # local import: pack.py imports this module

    _pack.load_pack(ws, pack)
