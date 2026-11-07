"""Far-travel layer: where a travelling squad is in metres, and when its real actor is live (CC-63).

The measured L2/L3 split (docs/combined-core.md, CC-63, P9 and P9u): L2 owns a travelling actor's position
while it is outside the loaded area; L3 materializes the real actor only inside it, at the simulated position,
and hands over with the linked-ref walk. L2 keeps route progress in hours (a squad's `at`, `goal` and `eta`);
it has no coordinates, because L1 has none. An atlas gives each place a position in metres in the converted
world: an engine binding recorded when a world is converted, not part of the pack.

This module answers where a travelling squad is in metres, whether its real actor should be live, and how a
dissolving actor's progress would be handed back to L2. Nothing here changes WorldState or the tick; it sits
outside the C++ parity path and becomes a later port step.
"""
from __future__ import annotations

import math

from .model import Squad, WorldState
from .sim import _distances

MATERIALIZE_M = 400.0   # CC-63: conservative; the loaded edge on the measured route was about 470 m
DISSOLVE_M = 500.0      # CC-63: hysteresis; under the ~643 m the engine still walked unloaded, never the abstract band

Atlas = dict[str, tuple[float, float]]   # place id -> (x, y) metres in the converted world


def missing_anchors(ws: WorldState, atlas: Atlas) -> list[str]:
    """Place ids of the world that the atlas has no position for, sorted."""
    return sorted(p for p in ws.places if p not in atlas)


def route_hours(ws: WorldState, a: str, b: str) -> int | None:
    """Shortest route hours from `a` to `b` (sim._distances); None when unreachable or a == b."""
    if a == b:
        return None
    return _distances(ws, a).get(b)


def progress(ws: WorldState, q: Squad) -> float:
    """Fraction of its route a travelling squad has covered, in [0.0, 1.0]. Mirrors present._squad_place's
    elapsed formula: departure is eta minus the shortest route hours. 0.0 without a goal or a route."""
    if q.goal is None or q.goal == q.at:
        return 0.0
    hours = route_hours(ws, q.at, q.goal)
    if not hours:
        return 0.0
    elapsed = ws.hour - (q.eta - hours)
    return min(1.0, max(0.0, elapsed / hours))


def _anchor(atlas: Atlas, place: str) -> tuple[float, float]:
    if place not in atlas:
        raise ValueError(f"atlas has no anchor for place {place!r}")
    return atlas[place]


def simulated_position(ws: WorldState, q: Squad, atlas: Atlas) -> tuple[float, float]:
    """The squad's position in metres: linear from its `at` anchor to its `goal` anchor by progress. A squad
    without a goal sits at its anchor; a missing anchor raises ValueError naming the place."""
    a = _anchor(atlas, q.at)
    if q.goal is None or q.goal == q.at:
        return a
    b = _anchor(atlas, q.goal)
    f = progress(ws, q)
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def distance_m(p: tuple[float, float], q: tuple[float, float]) -> float:
    return math.hypot(q[0] - p[0], q[1] - p[1])


def should_be_live(dist_m: float, live: bool) -> bool:
    """A dormant actor goes live within MATERIALIZE_M of the player; a live one stays live within DISSOLVE_M."""
    return dist_m <= (DISSOLVE_M if live else MATERIALIZE_M)


def materialization(dists: list[float]) -> list[bool]:
    """should_be_live applied over a sequence of player-to-simulated-position distances, starting not live."""
    live = False
    out = []
    for d in dists:
        live = should_be_live(d, live)
        out.append(live)
    return out


def progress_from_position(a: tuple[float, float], b: tuple[float, float], pos: tuple[float, float]) -> float:
    """Hand-back: when a live actor dissolves, L2 would take the real actor's position as its progress. The
    fraction along a->b of pos's projection onto the straight line between the two anchors, clamped to
    [0.0, 1.0]; a == b gives 0.0. An approximation: a multi-hop route and the navmesh path are not that line."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return 0.0
    t = ((pos[0] - a[0]) * dx + (pos[1] - a[1]) * dy) / length2
    return min(1.0, max(0.0, t))


def eta_from_progress(hour: int, hours: int, f: float) -> int:
    """The eta L2 would hold for progress `f` (clamped to [0.0, 1.0]) on a route of `hours`: hour plus the whole
    hours still to go, at least hour. A remainder that is a whole number of hours stays whole: a tolerance absorbs
    the float error of (1 - f) * hours (review of d8aea375: 6/7 of a 7-hour route came back one hour late).
    Proposed for the future integration; this module never writes a squad."""
    f = min(1.0, max(0.0, f))
    return hour + max(0, math.ceil((1.0 - f) * hours - 1e-9))
