# Fallout 4 navmesh on the native Red Rocket terrain (experiment 2d) and the N1 NPC tests

Author: Claude, 2026-10-11. Branch `claude/terrain-navmesh`, stacked on PR #66 (`claude/terrain-exterior-statics`, which
contains #64, #60, #57, #56) and PR #68 (`claude/runner-npc-nav`, which contains #59). Research base: PR #61
(`docs/actors/npc-navigation.md` there). Starfield 1.16.244, Mutagen 0.55.0-alpha.67.
Status (checked 2026-11-07, Mountain): **converted, written and checked offline; N1a / N1c ran in game without a
command; P9 / P9u later walked one linked citizen in game on this converter's whole-core output**.
- N1, on this page's exp2d plugin: see [npc-navigation.md, section 5.3](npc-navigation.md#53-how-far-actors-moved-without-a-command-verified-obsjson-of-npc_nav_n0-npc_nav_n1a-npc_nav_n1c)
  (section 5 dated 2026-10-12). No command was shown to walk an actor there; those runs do not establish commanded
  navigation.
- P9 / P9u, 2 Nov 2026 (receipts on #644, judges #663 and #669; [combined-core.md](../combined-core.md) CC-63, lines
  391-409). Navmesh: the installed `FO4TerrainCore.esm`, worldspace `FO4Core_Commonwealth`, 12,104 NAVM and 3,749,066
  triangles ([#644 offline check](https://github.com/fo4sf/fo4-to-starfield/issues/644#issuecomment-6567945885)), the
  counts of this converter's core64n run ([navmesh-core64n-convert.md](navmesh-core64n-convert.md); JOURNAL.md,
  2026-10-16). Driver: `FOCC_P9Drive.Link`, a linked ref plus `EvaluatePackage` that Starfield's
  `DefaultMaster_PatrolPackage` then walks, not `PathToReference` (combined-core.md:392-393;
  [combined-core-probes.md](../spikes/combined-core-probes.md):575-585). The `PathToReference` and console rungs
  stayed INCONCLUSIVE (combined-core-probes.md:172, 180-181).
  - P9 PASS twice, loaded: the go found the actor 439 m from a target picked offline 447 m north-west of the start;
    7 cells; arrived in 440 s and 443 s; kit #663 `a2c67b26`
    ([#644](https://github.com/fo4sf/fo4-to-starfield/issues/644#issuecomment-6572484090)).
  - P9u PASS once, the actor spawned 643 m south-south-west of the Red Rocket start, 149 m walked unloaded, branch
    `claude/p9-unloaded` ([#644](https://github.com/fo4sf/fo4-to-starfield/issues/644#issuecomment-6573465163)). From
    710 m and 899 m it was INCONCLUSIVE: the actor moved in one jump, or was parked outside the world
    ([#644 ladder](https://github.com/fo4sf/fo4-to-starfield/issues/644#issuecomment-6580035484);
    combined-core.md:407-409; the P9u judge, combined-core-probes.md:639-641).
  - Not stated in the receipts: the core plugin's build or hash, and the ids of the cells walked.
- Not shown in game: any walk on this page's exp2d plugin (`FO4TerrainExp2.esm`, `FO4CW_Commonwealth`); core64c's
  `FO4TerrainCore.esm`, which had 0 NAVM (JOURNAL.md, 2026-10-16 night, R06); any other route, worldspace or
  interior; more than one actor; a `PathToReference` or console-command walk.

Labels: **verified** = checked here on files, number given; **supported** = supported hypothesis; **unresolved**;
**refuted**. Offline checks are not in-game acceptance.

## Summary
- The 105 Fallout 4 navmeshes of FO4 cells x -20..-15, y 16..21 (the cells of exp2c's 8,069 objects) are cut at
  Starfield's 100 m cell lines into **156 NAVM records** (68,132 triangles) in the matching `FO4CW_Commonwealth`
  exterior cells, at FO4 position / 70, with **4,104 edge-link pairs** (2,145 across the new cell lines, 1,959 from
  FO4's own portals), plus a **NAVI override holding one NVMI per new navmesh**. They live in the same plugin as exp2c
  (`FO4TerrainExp2.esm`), after every exp2c record: exp2c's 10,301 records are unchanged byte for byte.
- Offline: every NVNM parses with the vanilla layout and is byte-identical to the Python reference writer; all 8,208
  link ends are symmetric, none dangles; cell-line links join identical points; 41,207 of 43,901 vertices lie within
  0.5 m of the decoded BTD or the converted collision (median 2 cm), and 2,674 of the other 2,694 are just as far from
  Fallout 4's own terrain and collision (FO4's navmesh is a simplified surface over rocks, cliffs, logs).
- Staged: `C:\Modding\staging\terrain_exp2d` (exp2c + navmesh), N1 plans `npc_nav_n1a` (terrain only), `npc_nav_n1b`
  (terrain + `gnm`), `npc_nav_n1c` (converted navmesh), and `terrain_exp2b2_npc` (the world check N1a/N1b require).

## 1. Format facts the conversion rests on

### 1.1 NVNM (navmesh geometry)
Layout as in PR #61 section 2.1 (both games parse exactly). Re-checked or added here:

| Fact | Evidence | Status |
|---|---|---|
| Triangle = 3 i16 vertices, 3 i16 edges, f32 height, **u8 extra, u16 flags, u16 cover flags** | with the flags read at byte +17, an edge whose bit (1, 2, 4) is set holds an edge-link index and every other edge a triangle index or -1: 0 inconsistent edges in 63,875 FO4 triangles (Red Rocket area) and 256,726 Starfield triangles (CydoniaCity); with the flags at +16: 5,970 and 1 inconsistent | **verified** |
| An edge link is (u32 type, navmesh, i16 triangle, u8 edge of **that** triangle) and comes in symmetric pairs | edge field = the target triangle's matching edge in 7,598 of 7,606 FO4 links (rest degenerate) and 7,196 of 7,196 CydoniaCity links; each link answered by a link back: 7,606 / 7,606 and 7,196 / 7,196 | **verified** |
| Linked edges overlap but need not coincide | FO4 portal edge endpoints differ by up to 632 units (partial overlaps); as segment gap at most 0.343 m in the converted area; CydoniaCity endpoint differences up to 0.36 m | **verified** |
| Parent = worldspace + **grid y, then grid x** (i16) | matches the containing cell's XCLC in 105 / 105 FO4 and 2,708 / 2,708 Starfield exterior navmeshes | **verified** |
| Triangle height = clearance above the triangle; FLT_MAX = no ceiling | FO4: FLT_MAX in 91,833 of 110,008, otherwise 170 units (2.43 m) and more; Starfield: FLT_MAX in 194,499 of 256,726, otherwise 1.8 m and more | **supported** (meaning); converted as finite / 70, FLT_MAX kept |
| Search grid: divisor = 1 up to 16 triangles, else min(12, n // 50 + 2); min = vertex bounding box; max x, y = bounding box, max z = highest vertex z + triangle height (float32); d x d triangle lists, y-major, a triangle in every cell its shape touches | divisor rule 1,004 / 1,004 (akilacity) and 2,708 / 2,708 (CydoniaCity); `navmesh.build_grid` reproduces divisor, min, max and cell size of all 1,004 akilacity navmeshes, the lists identically in 873 and as a superset in all 1,004 (0.3 % extra entries from its 1 mm tolerance) | **verified** (geometry); superset is safe for point lookups (**supported**) |
| Starfield vertex i32: 1 on an open-boundary vertex, 0 inside | akilacity: 136,176 of 136,976 open-boundary vertices are 1, 34,057 of 34,057 interior ones 0 | **supported** |
| Triangle extra byte | FO4 0 / 16 / 4 / 1 / 2 / 3; Starfield 0 everywhere in CydoniaCity, 0 / 32 / 2 in akilacity | **unresolved**: written 0 |
| Cover (FO4 8 B, Starfield 12 B per entry) and triangle cover flags (FO4 1..6, Starfield adds bits 14-15) | layouts parse; meaning not decoded | **unresolved**: dropped, flags cleared |
| Door triangle u32 = 0xE48A5FF3 in both games | every door triangle of the FO4 area and of CydoniaCity | **verified** (value) |
| Trailing 4 bytes `0c 00 08 00` | every NVNM of SFBGS003 (852) and SFBGS006 (3); 55,994 of 56,570 in Starfield.esm (PR #61) | **verified** |

Correction to PR #61 (section 2.1, "Triangle flags (u16 after the height) share the common values 0 / 16384 / 4 / 16388 /
2"): the u16 right after the height is the extra byte plus the low byte of the flags; the flags u16 starts one byte
later (table above). In that order FO4 sets 0x0800 on every triangle and 0x0040 on 30,294 of 63,875.

### 1.2 NAVI / NVMI (navmesh info map)
Layout, **verified** on all 56,631 NVMI entries of Starfield.esm (every one parses to its exact end, the CRC field is
0xA5E9A03C in all): u32 navmesh, u32 flags, f32 x, y, z, f32, merged-to (u32 count + FormIDs), preferred merges
(count + FormIDs), linked doors (count + (u32, door REFR)), **traversals (count + 60 B each)**, u8 outline flag and, if
set, the outline (6 f32 bounding box, count + 3 i16 triangles, count + 3 f32 vertices), u32 0xA5E9A03C, u32 worldspace,
(i16 grid y, i16 grid x | u32 cell), **u8 border bits, 4 zero bytes**. Mutagen splits it into NavigationMesh, `Data`
(20 B: flags .. f32), MergedTo, PreferredMerges, LinkedDoors and `Unknown` (the rest, raw: the worldspace FormID in it
is file-local).

| Field | Evidence (Starfield.esm unless named) | Status |
|---|---|---|
| merged-to = the navmeshes the edge links reach, in link order | equal sets in 56,502 of 56,563 entries (61 subsets); link order 35 of 40 (SFBGS003) | **verified** |
| location = mean of the navmesh's vertices | within 1 mm in 56,490 of 56,563 | **verified** |
| the f32 after the location | 0 in 56,152 of 56,563 | written 0; meaning **unresolved** |
| linked door = (door-triangle u32, door REFR) | 43 / 43 (SFBGS003) | **verified** |
| border bits: S 1, E 2, N 4, W 8 = which edges of its 100 m cell the navmesh reaches | e.g. 2,324 entries touching only W have 8, 2,312 only S 1, 1,263 all four 15 | **verified** |
| flag 0x20 = outline present | 54,549 with outline, 2,082 without; outline vertices are navmesh vertices (53,838), bounding box = the navmesh's (54,539 of 54,542), area >= the navmesh's (median x 1.09): a simplified outline, holes filled | layout **verified**; algorithm **unresolved** |
| entries without outline are mostly the large navmeshes | median 3,520 triangles (outline: 14); 1,088 exterior ones with edge links and traversals, 73 without traversals | **verified** |

**Does a plugin need NVMI entries, and how?** Every official plugin with navmesh carries a NAVI that overrides
Starfield.esm's `00000FF1` with only its own entries: SFBGS003 920 NVMI (981 NAVM), SFBGS00D 4,126 (4,058),
BlueprintShips 507 (439), SFBGS006 71 (3) against Starfield.esm's 56,631 (**verified**). The base game keeps
working with them loaded, so the engine merges NVMI entries per navmesh across plugins (**supported**). The
pathfinder searches the NAVI graph for paths between navmeshes and has a separate case for "Start and Goal are on the
same Navmesh" (exe strings, PR #61 section 1.3; **supported**).

**Decision (minimal correct thing):** one NAVI override `000FF1:Starfield.esm` in `FO4TerrainExp2.esm` with one NVMI per
new navmesh: flags 0, no outline, no traversals (the vanilla form of 2,021 large navmeshes), merged-to from our links,
linked doors from our door triangles, location = float32 vertex mean, border bits, NVER 17, empty NVPP (as SFBGS006).
Alternatives: no NAVI (a path across navmeshes probably fails: N1c's cross pair would show it); a full NAVI copy (53.9 MB,
replacing every vanilla entry the plugin does not change); outlines (the algorithm is not known; a wrong outline could
misplace a point). The A/B pair of N1c lies on one navmesh, so it tests the NAVM alone; the cross pair tests links + NAVI.

## 2. The conversion (`src/fo4sf/navmesh.py`, `convert`)

| Step | Rule | Red Rocket area |
|---|---|---|
| source | NAVM of Commonwealth cells x -20..-15, y 16..21 (Fallout4.esm, raw walk) | 105 navmeshes, 63,875 triangles, 44,916 vertices |
| position | game units / 70 at the absolute FO4 position (as the terrain and exp2c's objects) | |
| cell cut | each navmesh clipped at the 100 m lines into **one Starfield NAVM per (FO4 navmesh, Starfield cell)**; convex pieces fanned from the apex with the largest smallest triangle; slivers under 1e-6 m2 dropped | 156 NAVM in 16 cells, 68,132 triangles; 2,142 triangles cut; 1 sliver |
| exact cut points | every point has a canonical key (original vertex / cut of original edge a-b at a line / cell corner inside a triangle), computed from the canonical edge direction: the same point on both sides of a line and in both triangles of an edge is bit-identical | cell-line links: largest endpoint difference 0.0 m |
| adjacency | inside a piece: two triangles sharing two point keys; non-manifold edges left open | 0 non-manifold |
| new links | an open edge in two pieces of one navmesh (the cut edge on a cell line) -> link pair | 2,145 |
| FO4 portals | a type-0 link between two converted navmeshes -> a link between their pieces in every cell where both sub-edges exist and overlap >= 1 cm | 1,959 (2 dropped: no overlap after the cut); gap <= 0.343 m = FO4's own largest portal gap here |
| dropped links | to navmeshes outside the area (the converted area's rim) | 749 |
| ledge links | FO4 types 1 / 2 (jump up / down; Starfield uses only type 0, jumps are traversal data) | 396 dropped (**unresolved**: traversal mapping) |
| flags | FO4's flags kept except edge-link bits (recomputed), door (recomputed), water (no water is converted) | water: 0 triangles had it |
| height | finite / 70, FLT_MAX kept | |
| cover | entries and triangle cover flags dropped | 11,947 entries, 5,830 triangles |
| doors | kept when the door REFR is a converted rigged DOOR of exp2c (on the largest piece of the triangle), else dropped and the flag cleared | 1 kept (`0007895C`), 8 dropped (load doors and doors exp2c placed as statics or skipped) |
| waypoints | moved to the piece triangle under them | 6 of 6 kept |
| vertex extra | 1 on open-edge vertices | |
| grid | `build_grid` (1.1) | |

Why one NAVM per (FO4 navmesh, cell) and not one per cell: FO4's own portals stay links (their partial overlaps need no
re-meshing), and FO4 cell (-17, 19) lies wholly in Starfield cell (-10, 11) (PR #61 2.2), so Red Rocket's main navmesh
`001A0D0A` (2,354 triangles) converts whole into one record (`010030A1`): a walk on it needs neither links nor NAVI.

## 3. The writer (`dotnet/TerrainExp2`, navmesh mode)
`exp2_params.json` key `"navmesh": "navmesh.json"` (written by `navmesh.export`): NAVM records are allocated after every
object, in the cell's navmesh group; the NAVI override goes into the same plugin. Mutagen 0.55.0-alpha.67 needs four
adjustments, each found by writing, reading back raw and comparing (all **verified** by the byte check below):
1. **Grid lists**: a vanilla record read with Mutagen gives ONE `GridArrays` entry holding every list with its u32 count
   (as two i16) and the 4 trailing bytes, `Unknown3` 0, and writes back byte-identical (round trip of SFBGS006's three
   NAVMs: same sizes, only the remapped FormID byte differs). A new record with one entry per list loses the counts and
   always gets `Unknown3` appended. So the writer passes the lists with counts as one array (`navmesh.grid_raw`) and
   `Unknown3` = `0x0008000C`.
2. **Parent coordinates**: `WorldspaceNavmeshParent.Coordinates.X` is written first, but the file holds grid y first:
   X = grid y, Y = grid x.
3. **MNAM**: a new `NavigationMesh` has `PreCutMapEntries` null and writes no MNAM; vanilla NAVMs carry an empty MNAM
   (SFBGS003: 852 of 852 non-empty records). Set to an empty list.
4. **Form version** 581 on NAVM and NAVI (Starfield.esm's newest NAVM and its NAVI, SFBGS006, BlueprintShips: 581;
   SFBGS003: 582). The rest of the plugin keeps Mutagen's 576, which exp2c's objects load with.

## 4. Offline verification (`make_exp2d.py check`, `offline_check_navmesh.json`): PASS, 37 checks
- exp2c unchanged: the Mars plugin, the BTD (both copies) and the overlay mask byte-identical; **all 10,301 exp2c records
  unchanged**; added: 156 NAVM + 1 NAVI only; masters [Starfield.esm]; NAVM FormIDs `0100303D`..`010030D8` after every
  exp2c record (`0100303C`); NAVI `00000FF1`, NVER 17, empty NVPP.
- **Every NVNM parses with the vanilla layout and is byte-identical to `navmesh.write_sf`** of the same pieces with the
  FormIDs the plugin got; every one ends with `0c 00 08 00`; subrecords NVNM + MNAM (0 B), and every NAVM in its
  cell's temporary group ahead of the references, as vanilla (CydoniaCity: 2,708 of 2,708 there).
- Structure (`navmesh.validate`): 0 problems. 8,208 link ends, all symmetric, each used by exactly one triangle edge;
  182,686 internal edge references, every one pointing back and sharing the two vertices; every vertex inside its
  navmesh's 100 m cell; every triangle in the grid; the divisor rule; door triangles flagged; 156 NVMI: merged-to = link
  targets in link order, location = vertex mean, border bits, parent, linked doors.
- Cell-line links join identical points (0.0 m); portal links at most 0.3427 m apart = FO4's own largest portal gap.
- **On the surface**: vertex vs the decoded BTD (bilinear) and every converted collision surface at its x, y: within
  0.05 m 30,930, 0.1 m 35,597, 0.25 m 39,313, **0.5 m 41,207 of 43,901**, 1 m 42,683; median 0.021 m, p95 0.62 m;
  61,543 of 68,132 triangles with all three vertices within 0.5 m. Of the 2,694 off: 16 lie on FO4's own LAND (the
  BTD's 0.78 m grid at sharp terrain edges, exp2c's cliff note), and against FO4's own LAND plus the collision of the
  source NIFs within 8 m (`--fo4-data`: 939 models, 230 without decodable collision) **2,674 are off FO4's own
  surfaces too**: rocks, cliffs, terrain shelves, logs, maple trees, roots (nearest object). They are FO4's navmesh,
  not the conversion (**supported**: FO4's navmesh is generated as a simplified walkable surface; the 230 models without
  decodable FO4 collision leave some cases open).
- NPC points (section 6): open level terrain, nothing above them within 1.5 m, on a converted triangle (-0.001 m and
  +0.024 m above the terrain), A -> B connected inside one navmesh, A2 -> B2 through edge links; plan entries 2 to 5 =
  exp2c's four entries.
- The plans load with this branch's runner (`plan-terrain` / `plan-npc --fresh` into scratch queue folders): 1 + 5
  terrain tests, 3 x 4 npc_nav tests, every one `fresh`, preconditions resolved.
- Synthetic tests: `tests/test_navmesh.py` (20: both layouts, grid, NVMI, cell-line / corner / shared-edge /
  vertex-on-line cuts, portals, ledges, rim links, doors, waypoints, deleted triangles, the validator's failure modes,
  export vs reference writer, N1 entries through the runner's validator), `tests/test_npc_nav.py`
  (`test_fresh_tests_relaunch_the_game`).

## 5. Staged (outside the repo)

| Folder | Content |
|---|---|
| `C:\Modding\staging\terrain_exp2d` | `FO4TerrainExp2.esm` 3,401,036 B (exp2c + 156 NAVM + NAVI), `FO4TerrainExp2_Mars.esm` (= exp2c's), `Data\` (= exp2c's: BTD, mask, 7,733 converted model files), `navmesh.json`, `navmesh_report.json`, `formids.json` (+ NAVM ids), `objects.json`, `skipped.json`, `plan.json` (5 entries), `expected.json`, `exp2_params.json`, `offline_check_navmesh.json`, `README.txt` (install, manual steps) |
| `C:\Modding\staging\terrain_exp2b2_npc` | byte-identical copy of `terrain_exp2b2`'s plugins, params and Data tree; `plan.json` = one terrain entry at the N1 points (the world check N1a / N1b require) |
| `C:\Modding\staging\npc_nav_n1a`, `_n1b`, `_n1c` | `plan.json` (4 tests each), `README.txt` |

exp2d's `plan.json`: entry 1 = the world check of the NPC points (drops at A, B, A2, B2 and `zref_ground`, heights
relative to it), entries 2 to 5 = exp2c's four entries unchanged (terrain gate, object tops, shop floor, informational).

## 6. N1: the same actor, methods and points on the same terrain, three navigation states

NPC points (worldspace frame, metres; terrain heights from the BTD):

| Point | x | y | z | on (exp2d) |
|---|---|---|---|---|
| A | -985.0 | 1139.0 | 105.0293 | `010030A1` (FO4 `001A0D0A`, Red Rocket's main navmesh) |
| B | -972.0 | 1153.0 | 105.0293 | `010030A1`; A -> B 19.1 m, a straight clear line, 12 triangles |
| A2 | -988.0 | 1162.0 | 105.0293 | `010030A1` |
| B2 | -1003.0 | 1153.0 | 105.3718 | `01003094` (FO4 `001A97FE` in cell (-11, 11)); A2 -> B2 17.5 m through `010030A3` (FO4 portal 001A0D0A-001A97FE) and the x = -1000 m cell-line link |

Chosen automatically (`pick_points`) within 45 m of the arrival in cell (-10, 11): level open terrain with no collision
above it within 1.5 m (so the player and the actor land on the terrain in exp2b2 and exp2d alike), the same converted
navmesh under a 2 m disc, the straight line clear. A and B are in Red Rocket's cell, so `gnm` ("Generates nav-mesh on
the current cell") covers both. The staged N1 of PR #68 used exp2b's `flat_1` / `flat_2`; in exp2d a truck and a car
stand within 1 m of them, so they cannot serve all three variants.

| Queue | World installed | Tests (actor `002B211C` EncCitizen01Template, reads 0 / 5 / 15 / 30 / 60 s, dropped from 30 m, all `fresh`) | Precondition | Expected |
|---|---|---|---|---|
| `npc_nav_n1a` | `terrain_exp2b2_npc` (exp2b2: terrain only) | A->B with `ptr_player`, `cf_pathto_player`, `follow_player`; A2->B2 `ptr_player` | `terrain_exp2b2_npc` 0000 PASS | FAIL NONAV (**supported**, PR #61 1.4) |
| `npc_nav_n1b` | same | the same four, each with `pre: ["gnm"]`, 20 s wait | same | **unresolved** (A->B PASS if `gnm` builds navmesh in a plugin worldspace cell; A2->B2 crosses into the next cell) |
| `npc_nav_n1c` | `terrain_exp2d` (exp2c + converted navmesh) | the same four | `terrain_exp2d` 0000 PASS | A->B PASS (**supported**: offline checks); A2->B2 PASS **unresolved** (links + NVMI) |

The spawn frame: `anchor` 02000800 (reads its unmerged position, so the runner takes the arrival), `spawn_local`
(-989.0286, 1147.2, z) with z = 105.1434 (exp2b2: the terrain under the COC marker) or 105.2609 (exp2d: the pump island,
as exp2c). FAIL verdicts count only where N0's control with the same method and N0_base passed (`--control-queue
npc_nav_n0`; `report` re-applies the gate).

| Outcome | Reading |
|---|---|
| world check FAIL / INCONCLUSIVE, N1 INCONCLUSIVE PRECONDITION | a world problem at the points (terrain or the drop), nothing about navigation |
| N1a FAIL NONAV, N1c PASS (same method passed in N0) | the converted navmesh is what lets the actor walk: conversion works |
| N1a PASS | Starfield paths without NAVM in a plugin worldspace (runtime generation, R0): N1c says nothing more |
| N1b PASS, N1a FAIL | `gnm` generates navmesh in a plugin worldspace cell: a quick route for test cells |
| N1c A->B PASS, A2->B2 FAIL / STALLED | NAVM works, the cross-navmesh part (links or NVMI) does not |
| N1c FAIL NONAV on A->B with N0 passing | the NAVM records are not used (layout, parent, form version, NAVI) |
| FELL | world (collision), not navigation |

## 7. Queue commands (with the checkout that runs the chain, once it holds this branch's `testqueue.py`)
Order: N0 first (already queued), then the world checks, then N1.

    python scripts\game\testqueue.py plan-terrain --staging C:\Modding\staging\<pinned build> --exp-dir C:\Modding\staging\terrain_exp2b2_npc --out C:\Modding\testqueue\terrain_exp2b2_npc --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh
    python scripts\game\testqueue.py plan-terrain --staging C:\Modding\staging\<pinned build> --exp-dir C:\Modding\staging\terrain_exp2d --out C:\Modding\testqueue\terrain_exp2d --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh
    python scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\<pinned build> --exp-dir C:\Modding\staging\npc_nav_n1a --out C:\Modding\testqueue\npc_nav_n1a --install-exp C:\Modding\staging\terrain_exp2b2_npc --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --control-queue C:\Modding\testqueue\npc_nav_n0 --fresh
    python scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\<pinned build> --exp-dir C:\Modding\staging\npc_nav_n1b --out C:\Modding\testqueue\npc_nav_n1b --install-exp C:\Modding\staging\terrain_exp2b2_npc --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --control-queue C:\Modding\testqueue\npc_nav_n0 --fresh
    python scripts\game\testqueue.py plan-npc --staging C:\Modding\staging\<pinned build> --exp-dir C:\Modding\staging\npc_nav_n1c --out C:\Modding\testqueue\npc_nav_n1c --install-exp C:\Modding\staging\terrain_exp2d --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --control-queue C:\Modding\testqueue\npc_nav_n0 --fresh

then chain lines in this order: `terrain_exp2b2_npc`, `npc_nav_n1a`, `npc_nav_n1b`, `terrain_exp2d`, `npc_nav_n1c`.

2026-10-12: N0 could not tell a commanded walk from wandering (docs/actors/npc-navigation.md section 5), so N1's FAILs
gated by `npc_nav_n0` say nothing. The re-plans `npc_nav_n1c_b` (first), `npc_nav_n1a_b`, `npc_nav_n1b_b` keep these
worlds and points, judge with N0b's rule for their own pairs (the walk from t0: within 3 m after P, or P closer;
P = 13 m on the 19.1 m pair, 11 m on the 17.5 m cross pair), drop `cf` / `follow`, add a baseline of the citizen in
that world, and use `--control-queue C:\Modding\testqueue\npc_nav_n0b`. Plan them only once `npc_control.py ready`
exits 0 (N0b's PathToRef control and baselines passed; N0b expects that control to fail, then they are not run); the
staged READMEs (`C:\Modding\staging\npc_nav_n1*_b`) have the exact commands.
`plan-npc --fresh` and a plan's `"fresh"` need this branch's `testqueue.py` (commit "plan-npc keeps a test's fresh");
the runner on `claude/integration-1011` drops `fresh` for npc_nav tests and has no `plan-npc --fresh`. PR #68's
staged `npc_nav_n1` requires `terrain_exp2b3` 0000 PASS, which read INCONCLUSIVE MOVED: as staged it would never run;
`npc_nav_n1a` replaces it.

## 8. Unknowns
1. Everything in game; first whether the engine uses plugin NAVM records in an overlay worldspace merged into Mars at a
   whole-cell offset (the navmesh is placed at the overlay's local coordinates like its references; whether the merge
   moves navmeshes with them is **unresolved**, exp2c's object entries will show it for references).
2. NVMI without outline for small navmeshes (vanilla gives most small ones an outline); the outline algorithm.
3. Triangle extra byte, vertex i32 for linked vertices, the NVMI f32, cover semantics, traversals (FO4 ledges).
4. The intermediate `setpos` positions of the cross pair and of exp2d's entry 1 graze objects (console open, final
   positions clear; whether setpos resolves an overlap is **unresolved**, as in exp2c).
5. Whether `gnm` is allowed outside the editor and how long it takes (N1b waits 20 s after it).

## 9. Reproduce

    python scripts/terrain/make_exp2d.py stage --exp2c C:\Modding\staging\terrain_exp2c --out C:\Modding\staging\terrain_exp2d ^
        --fo4 <Fallout4.esm> --sf-esm <Starfield.esm>
    python scripts/terrain/make_exp2d.py check --exp2c C:\Modding\staging\terrain_exp2c --out C:\Modding\staging\terrain_exp2d ^
        --fo4 <Fallout4.esm> --fo4-data <FO4 Data>
    python scripts/terrain/make_exp2d.py npc --exp2b2 C:\Modding\staging\terrain_exp2b2 --exp2d C:\Modding\staging\terrain_exp2d ^
        --staging-root C:\Modding\staging --queue-root C:\Modding\testqueue
    python -m unittest tests.test_navmesh tests.test_npc_nav

Times: stage 42 s (plus the first 2.3 GB copy), check 27 s with `--fo4` and `--fo4-data`, npc 5 s.
