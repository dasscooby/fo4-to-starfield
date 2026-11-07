# Cross-game world staging: city continuity, source versions and campaign eras

Owner direction, 1 November 2026; preparation tracked in [#666](https://github.com/fo4sf/fo4-to-starfield/issues/666).
Extends the [Fallout-shell packet](../../testing/fallout-shell-preparation.md), not Claude's current runtime/world
implementation. Source observations below are research, not native acceptance. The [pilot matrix](../../testing/multi-game-world-pilots.json)
is non-executable; the [source register](multi-game-world-sources-nov01.json) distinguishes developer accounts, mod
authors, source code and project decisions. No third-party converter was run or adopted.
For execution order, required inputs and receipts, use the [Claude PC action cards](../../testing/claude-world-staging-handoff.md).

## Owner decisions carried forward

- Commonwealth first, on the shared Fallout planet. Prepare Fallout 3 and New Vegas geography next; research classic
  Fallout 1/2 reconstruction now. Fallout 76 is the last **complete integration**, with its other locations revisited
  separately. This is not an instruction to delay all reusable 76 format research.
- For New Vegas, prefer a continuous, developer-intent-informed city where evidence and testing support it. Cut-content
  decisions remain per game and per item; neither every deleted item nor every fan restoration becomes canon.
- GAMMA saves will select an era at creation. Overlapping locations need alternative, mutually exclusive region
  versions. The future, show-informed interpretation is a project prediction, with no main-story campaigns; retain
  suitable side missions and opportunities after dependency/era checks. TV-derived implementation waits for the owner's
  later season review. Do not generate speculative lore into the read-once lore store.
- **Owner confirmed the two era choices: 2287 plus a speculative later era.** There is no separate 2281 preset.
  The later year remains unspecified until the owner's later show/world-state review. The 2287 preset keeps
  story availability configurable by mode/region; the later preset has no main-story campaigns.
  Bethesda's [official timeline](https://bethesda.net/en-US/news/fallout25-presents-the-fallout-timeline) places Fallout 3
  in 2277, New Vegas in 2281 and Fallout 4 in 2287. Preserve those source dates separately from our campaign date.
  Concurrent quests across these games are a gameplay arrangement, not proof that their original stories share a year
  or cannot interact. Geography, faction outcomes and references still need review. Do not silently rewrite dialogue
  or main stories to disguise a timeline mismatch; put proposed exceptions in the owner's review list.

## Fallout 3: reconstruct the route graph before opening downtown

The owner identifies metro-only access to parts of DC. Treat that as an audit target: extract each exterior district,
metro/interior, load door and destination from the owned game records, then check which routes exist on the surface.
Do not infer the exact reachable graph from a map image or assume that a separate worldspace is intrinsically
unopenable. No exhaustive district/metro graph was extracted in this research.

There was a design tradeoff as well as a technical problem. In the direct
[Game Informer oral history](https://gameinformer.com/FalloutOralHistory-PartII), Pagliarulo describes reducing an
initially much larger connected underground network because traversal became excessive. That supports keeping useful
metro travel and encounters; it does not prove every rubble barrier was solely a memory workaround.

**First pilot:** one verified pair of downtown districts and the metro route connecting them. Keep the released route
as a control. Build a proposed surface connection only after locating its true coordinates, height, collision and
story/encounter conditions. Record whether the opening changes a quest's first encounter, hostility, companion path,
or intended restricted access. Test both story-preserving and GAMMA policies; optional surface access must not erase
the underground location or create a route through missing geometry. The particular districts remain unselected until
the source census supplies their IDs and links.

Do not mistake a title such as "True Open World DC" for proof of contiguous city geometry: the
[author's documented scope](https://www.nexusmods.com/fallout3/mods/26959) primarily changes access to main-quest content.
Compare the actual edited records and version, not the name of a mod.

## New Vegas: Strip, Freeside and McCarran are separate questions

Sawyer's [direct interview](https://feed4gamers.com/game-news/297795/josh-sawyer-reflects-on-design-evolution-from-icewind-dale-to-pentiment.htm)
describes an **18-month**, not 12-month, development window and difficulties learning the tools and memory/streaming
behaviour. The [making-of interviews with Sawyer and Scott Everts](https://www.pcgamesn.com/fallout-new-vegas/making-of)
describe console-driven simplification, scaled/adjusted geography and Freeside/suburb partitioning. That is useful
evidence of constraints, not a complete design document authorizing every proposed restoration.

The mod authors offer concrete engineering precedents:

- [Simple Open Strip](https://www.nexusmods.com/newvegas/mods/73127) makes the Strip contiguous, rebuilds navmesh and uses
  occlusion. Its author explains that the released game repositions a small NPC pool between gated zones; opening the
  gates needs different population handling. Its changelog also fixes zone-variable and promoter triggers. These are
  acceptance cases for our core, not cosmetic cleanup.
- [Simple Open Freeside](https://www.nexusmods.com/newvegas/mods/73128) separately joins Freeside, with rebuilt navigation,
  scene/door-link fixes and compatibility work. The author warns against changing it mid-save and distinguishes this
  layout work from restoring most cut content.
- [FLVJOD](https://www.nexusmods.com/newvegas/mods/56373) explicitly pursues an earlier-development interpretation of the
  Strip. It is a fan layout proposal; changes involving a McCarran-style gate do not establish that the developers
  intended Camp McCarran itself to share a continuously walkable city space. That historical point remains unresolved.

**Three pilots, not one giant merge:** join the Strip's internal sections; join Freeside's sections; then separately
evaluate the McCarran approach/monorail/restricted access. Preserve casino interiors and security semantics. Test
cross-zone NPC identity/density, a promoter/scene trigger from both street edges, companion pathing, faction entry
conditions, monorail state and save/reload. Keep world continuity, cut content, population and faction control as
separate build choices, frozen for a save. McCarran is not automatically included in the first open-Strip pilot.

## Fallout 76: real conversion precedents, versioned geography, offline gameplay

The old [UnleashOne Appalachia author account](https://www.reddit.com/r/FalloutMods/comments/bm4kvi/) describes hand
recreation with Fallout 4 assets, including handmade terrain at the time. It is not evidence that a complete 76 map
was imported. More recent source projects are different:

| Reference | What is evidenced in its own material | What this does not establish |
|---|---|---|
| [fo76utils](https://github.com/fo76utils/fo76utils/tree/c52da18cbe0b7529673bb1c373a89ee5efa37260), particularly [btddump](https://github.com/fo76utils/fo76utils/blob/c52da18cbe0b7529673bb1c373a89ee5efa37260/doc/btddump.md) | Tools extract BTD heights, texture/ground-cover information and render/read world data | A playable CE2 world, correct actors/quests or current-patch coverage |
| [BACUP pinned README](https://github.com/Bryant-21/bacup/blob/0abb21361ae623e32a655bda5a28ea061efa609c/README.md) and [pair registry](https://github.com/Bryant-21/bacup/blob/0abb21361ae623e32a655bda5a28ea061efa609c/bacup/py_bacup_lib/python/bacup_lib/source_pairs.py) | A concrete `fo76:fo4` source pair and hooks; broader asset/terrain/record conversion is claimed by its author | Full correctness, all 76 content, or our ability to chain conversions without losses; no execution/benchmark here |
| [FO76→FO4 Conversion Toolkit](https://www.nexusmods.com/fallout4/mods/108858) | Author documents selected mesh/material/texture routes and explicit alpha limitations | Terrain/plugin/quest conversion or native equivalence; no binary downloaded or run |

BACUP's README lists three wired pairs, but its pinned registry also contains `fo4:starfield` and `starfield:fo4`, with
mandatory world-only exclusions (no quests/NPCs/actors). The README alone would understate the code. Treat those paths
as audit candidates, not an accepted replacement for this project's tested pipeline. In particular, a schema, a hook
or a green conversion report is not native actor, collision or script acceptance. Record licenses/dependencies and
review before reuse; this research copies no implementation into FO4SF.

**First 76 pilot:** a bounded terrain rectangle and one material/static-object sample, with original source-coordinate
and water-height checks. Then one exterior/interior pair and one representative creature. Use original source data as
the comparison baseline; an intermediate FO4 output may have already discarded fields. Pin `SeventySix.esm`, the data
archives and the exact update. Measure actual source bounds and terrain density instead of budgeting from a marketing
map-size multiplier. [Bethesda's 2025 directors' letter](https://bethesda.net/en-US/news/fallout-76-letter-from-the-directors-2025)
describes a further region expansion, reinforcing the need to bind a version rather than "all Appalachia" forever.

Keep expanded Appalachia, interiors and expedition destinations as separately inventoried regions. Map server-dependent
events, instancing, ownership, resets and quest services to explicit local rules; reuse our FO4-like baseline where
appropriate. No online-account/session emulation or live service dependency is part of the proposed playable core.
Full integration remains last, and a map import does not make these systems done.

## Fallout 1 and 2: authored 3D worlds informed by the original maps

The community-engine projects require original data and expose map structures containing tile data, entering tiles,
elevations and rotations ([FO1 map header](https://github.com/alexbatalov/fallout1-ce/blob/0609bcfd0ec40ff0571d0f57fab2821eb461dc8b/src/game/map.h),
[FO2 map header](https://github.com/alexbatalov/fallout2-ce/blob/e97087b9582f37075db347a89898887320753f8b/src/map.h)).
These are useful read-only format references. They do not supply missing 3D buildings, terrain, interiors, rigs or CE2
navigation. Keep the implementation in Starfield; inspect the original data rather than porting a different engine.

Prepare one small source map per game with its map-script, entrances, exits and elevations. Reconstruct a greybox of
one outdoor area, one room and one elevation transition; obtain owner review of scale/layout before detailed art.
Preserve important sightlines, exits and encounter roles without pretending the isometric framing specifies every
hidden wall or roof. Keep the old overland map's travel/encounter graph separate from local geometry. This fits the
owner's corridor/vehicle travel direction and does not reopen a requirement to hand-build continuously walkable America.

Where both games depict a place, keep stable location identity with alternative era-specific geometry/population,
not two overlapping active towns. A later setting needs an authored state choice; it is not generated canon.

## Staging contract shared by all games

1. **Source intake:** owner-provided install paths, edition/update/language, masters/DLC/archive hashes, reader/tool
   commit and source-world IDs. The checked D-drive Steam library contains Fallout 4 only; no FO3/NV/76/1/2 source
   bundle was built here. This is not a statement about ownership or other libraries.
2. **Released topology first:** source-keyed cells/worlds, doors, quest/scene/navmesh dependencies and missing records.
   Add a proposed contiguous layout as a separate revision. Do not silently fill absent geometry or recycle source IDs.
3. **Identity:** `(game_id, source_plugin, source_id)` distinguishes identical numeric IDs across games; region identity
   survives era variants. Retain allocation history/gaps, output pins and old source stages.
4. **Era manifest:** separate source-game year, source-build version and campaign year. Select one variant per overlapping
   region, with a new-save-bound policy. Main-story permissions, side-quest eligibility, faction/population state and
   travel connections follow that selection. No mid-save geometry/era swap or unsupported main-quest reactivation.
5. **Tests:** height/water/coordinate/scale checks; meshes/materials/collision; actual actor navigation and doors;
   quests/security/population triggers; save/reload and paired recovery. An offline graph does not prove native routes.
6. **Deployment:** after independent QA, Claude PC uses a fresh authorized snapshot and a new operational stage. Keep
   private assets out of Git; never test by removing Starfield masters or overwriting the installed Fallout worlds.

The next implementation decision is which **small, source-backed pilot** to stage. Offline intake and isolated
conversion preparation can proceed as soon as its source path and IDs are known; integrating it on the new host needs
the own-planet reference evidence. Choose the pilot with Claude from the matrix. TV content and speculative regional
futures remain design work for later owner review.
