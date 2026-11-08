# Combined core: gateway pairs between converted worlds (CC-64 data contract, 8 November 2026)

This is a design and data contract. Nothing in it is implemented or has run in game: no code, no runtime travel, no
game transition, no plugin records. It is the first source-side step of CC-64 (docs/combined-core.md) and rests on
the owner's decisions of 7 November 2026, listed below. Runtime travel and the in-game transition are later,
separate steps.

## Owner decisions this rests on (7 November 2026)

- **D1 = A.** The player moves between areas by scripted transitions at fixed exits first (fade, time advance,
  arrival at a marker). A map pick from known places may come later as a layer on the same transition. A vertibird or
  ship (CC-61) stays a future option, not current work.
- **D2 = A.** A trip costs the route hours of the inter-world edge, the same for the player and for squads.
- **D3 = B.** What happens on the way is a roll against the simulation at departure, for an encounter at arrival or at
  a fixed waypoint, inside the encounter-conservation rules. No new ambush interiors.
- **D4 = A.** Inter-world edges are explicit, deterministic gateway pairs listed per world, each with its own hours.
  No nearest-marker guessing across worlds: marker units of different worlds are not comparable (seedpack.py).
- **D5 = A.** Off-screen travel between worlds shows only through its effects at the endpoints (arrivals, news, map
  icons). There is no continuous position during an inter-world leg and no in-transit overlay.
- **D6 (research first).** Before any place is chosen as exterior or interior, survey how Starfield builds its big
  city spaces (Cydonia, Neon). Each place's choice stays open; this contract does not depend on it.

## What the source has today (main 13bb2b18)

- `model.PLACE_KINDS` has `gateway`, and a pack route may join places of different regions: the synthetic
  `fixtures.REGION_2` joins `gate_1` (R1) to `gate_2` (R2) with a 48-hour route. Nothing in `sim.py`, `present.py`,
  `jobs.py`, `manage.py` or `travel.py` branches on the `gateway` kind; to the simulation a gateway route is an
  ordinary route.
- `pack.validate_pack` checks a route's ends, hours and duplicates, but not region or kind, so it cannot tell an
  inter-world edge from any other.
- `seedpack._routes` links each marker place to its `k_nearest` neighbours **inside one marker world** and scales
  hours per world. It never makes an edge between worlds and never produces a `gateway` place.
  `DEFAULT_RULES["defence"]` has no `gateway` key.
- A seed draft's `region` is the name of the place's root location (`seed.py`), not its worldspace. The world is
  `marker.world`, the WRLD key of the place's map marker. L1 has neither coordinates nor a world field.
- `travel.py` positions a travelling squad on the straight line between two anchors of one atlas, in one converted
  world's metres.

## The contract

### Input: a gateway list

A gateway list is JSON, supplied next to a seed draft and kept with it on the player's machine, like the draft. It is
written by the owner or a data file, never derived from distances:

```json
{"gateways": [{"a": "<pack place id>", "b": "<pack place id>", "hours": 48}]}
```

- `a`, `b`: ids of places that `seedpack.generate` keeps (the seed draft's ids, as they appear in the pack).
- `hours`: a positive integer, used as given. It is not scaled by `median_route_hours` and has no default.
- No other keys. Optional fields wait for a decision that needs them.

Entries that must be refused, each reported in plain words:

| Rule | Refused when |
|---|---|
| G1 | an end is not a kept place (dropped, or unknown to the draft) |
| G2 | an end has no marker world, or both ends are in the same marker world (that is an ordinary route) |
| G3 | `hours` is not a positive integer (booleans count as not an integer, as in `pack._is_int`) |
| G4 | the unordered pair appears twice in the list |
| G5 | the entry has a missing or unknown key, or the top level is not `{"gateways": [...]}` |

On any problem the whole list is refused and the pack gets no gateway edge, so a half-joined world never happens
(the same rule as `load_pack`). One place may be an end of several pairs; a hub world (D4 option C) is therefore
expressible but not required.

### Output: what the seed pack gains

- One route `{"a": min(a, b), "b": max(a, b), "hours": hours}` per pair, sorted together with the in-world routes
  (by `a`, then `b`), so the same draft, rules and list give byte-identical JSON.
- Ends keep the kind, holder and defence `generate` already gave them. A settlement or a base can be a gateway end;
  the exit itself is engine data (D1), not a place kind. The `gateway` kind stays available for packs that add a
  dedicated exit place, as the fixtures do; the seed pack does not create such places.
- With no list, or an empty one, the pack and the report are byte-identical to today's.
- With a list, the report gains a `gateways` block: the pairs used, their count per world pair, the hours used, and
  the problems found (empty when the list was accepted). `isolated` is computed after the gateway edges are added, so
  a place reachable only through a gateway is no longer isolated.

### Invariants the later steps must keep

- **No position on an inter-world leg (D5).** A squad whose next hop is a gateway edge has no simulated position.
  The far-travel layer must answer "not in this world" for it rather than interpolate between anchors of two atlases.
  Today an atlas is one world's metres, so a mixed leg has to be refused explicitly, not left to chance.
- **One cost for everyone (D2).** The player's trip and a squad's trip over the same pair cost the same `hours`,
  through the same shortest-route reading (`sim._distances`, `travel.route_hours`).
- **The departure roll reads existing state (D3).** It uses squads and routes as they are, adds no new state shape
  without a schema bump, and follows the encounter-conservation rules.
- **Packs only add.** A later pack can add a pair to a place an earlier pack loaded, through an ordinary route
  entry, as `REGION_2` does today. No pack edits another's routes.

## Acceptance for the code step that implements this (not this change)

1. No list: `seedpack.generate` and `seed-pack` give byte-identical pack and report files to main.
2. A valid two-world list adds exactly its edges, passes `validate_pack`, loads, and runs under `sim.run` with the
   balance invariants, deterministically.
3. Each of G1 to G5 has a refusing test; a refused list changes neither the pack's routes nor its places.
4. The C++ parity suite stays byte-identical. Gateway routes are ordinary routes to the ported sim, so no C++ change
   is expected; parity is checked, not assumed.
5. `travel.py` refuses, or returns no position for, a leg over a gateway edge, with a test (or that invariant is
   split into its own step).

## Not decided here, and not claimed

- Which places are gateways, and their hours: owner or data choices, per world.
- Exterior or interior for any place (D6, survey first).
- The engine side of an exit: door, trigger or menu, fade, time advance, arrival marker (NG-9). That is the runtime
  transition step, with its own in-game acceptance on the PC under a fresh owner release.
- Whether P9's navmesh walk carries over to other worldspaces, interiors or builds: P9 measured one actor in one
  converted exterior (CC-63). Nothing here relies on it.
