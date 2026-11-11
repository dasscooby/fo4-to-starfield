# Next phase: whole world, DLC worldspaces, maps, LOD and fast travel

Research thread (Claude-cloud), 2026-10-19 overnight. Repo main 303f73f (local), origin/main 4492d13. Labels follow
docs/ai/research-log.md: **verified** (file, command or output named), **supported** (evidence points one way, not
shown in game), **unresolved**. Nothing here was run in game, and no game data is in the cloud. Ground textures,
water and foliage are covered in the sibling note trees-grass-terrain.md. This note covers the world's extent, the
maps, LOD and travel.

## Summary (5 lines)

1. The 64x64-cell core already holds every Fallout4.esm exterior object. "Beyond the core" means the DLC content plus FO4's unplayable outer LAND ring, not more playable Commonwealth.
2. Each DLC exterior worldspace (Far Harbor, Nuka-World) should be its own overlay in its own landing, joined by scripted doors and fast travel. Four of the six DLC are still not installed on the PC (PR #371 E1).
3. Map markers, fast travel and inter-world doors share one root problem: our persistent references stay at their local (unmerged) position, while vanilla LC172's persistent anchor moves with its merge. Two writer-side fixes (the persistent-cell shape, WRLD OFST/CLSZ) were already refuted in game, so the runtime mover in #376 is the path; one add-on test in vanilla LC172World would settle whether a writer fix can exist.
4. Starfield world object LOD (`lodsettings/*.lod` + `meshes/lod/generated`) is absent. xLODGen does not list Starfield. We would need either the Creation Kit on the player's PC or our own generator, and a tiny-overlay spike decides which.
5. Breadth order: (1) persistent-ref diff, (2) DLC census, (3) bulk FO4 map markers, (4) LOD spike, (5) a second overlay for Far Harbor. The Pip-Boy map comes after Starfield's surface map works.

## Facts this builds on (all from repo docs)

| Fact | Label | Evidence |
|---|---|---|
| Core = one overlay `FO4Core_Commonwealth`, 64x64 Starfield cells (6.4 km), FO4 units / 70, on Mars | verified | docs/terrain/core64c.md |
| Core holds all 648,358 converting Fallout4.esm exterior refs; FO4 refs reach FO4 cells x -53..33, y -49..41 | verified | core64c.md; commonwealth-build-plan.md section 0 |
| FO4 LAND grid -96..95 (192 FO4 cells = 11,234.7 m = 114 Starfield cells), heights -118.86..641.03 m | verified | commonwealth-scale.md 1.3 |
| Pip-Boy map bounds (WRLD MNAM) NW (-33,25) SE (28,-36) = 37 Starfield cells | verified | commonwealth-scale.md 1.3 |
| Landing default 100 cells, playable buffer 5; largest planet-registered overlay is 14 cells; biggest vanilla BTD (editor/test) is 100x100 | verified values, meaning supported | commonwealth-scale.md 1.1-1.2 |
| Merge offset of the core (-1200, -2700) m, the only offset ever measured | verified (one overlay) | scripts/terrain/vmad_patch.py:70 `MERGE_MEASURED` |
| Persistent refs of our world resolve at local coords in base WRLD 0x02000803; temp refs resolve merged; MoveTo onto a persistent ref drops the player at unmerged coords (falls) | verified | JOURNAL 16 Oct night, door probes (a)-(e) |
| Vanilla LC172World anchor 0010238E moved with its merge (-500, -2300); ours did not in 4 of 4 reads | verified | commonwealth-scale.md section 2 |
| A teleport of 2 cells or less per axis lands (144/145). At 3 cells or more, 11 of 28 relocated ("Boundary Reached") or hung | supported | core64c.md teleport rule |
| Walking Red Rocket -> Diamond City: no Boundary Reached | verified (owner) | playtest row 25 |
| Starfield map markers are REFRs of STAT MapMarker 00000010, linked via LCTN `LCSR` (5 x u32 rows) | verified | map-markers.md |
| Markers enabled since #356 (flags 0x400, no LCID), still no icon in v6 | verified (owner, 19 Oct) | map-markers.md "Markers in the merged world" |
| 0 `lodsettings`, 0 `meshes/lod/generated` in our Data; vanilla has 864 .lod (861 of 20 bytes) + 19,535 lod NIFs + `distantlod/lodruntimedb.bgsdb` | verified | object-lod.md; surface-map.md |
| PC has DLCRobot + DLCworkshop01 only; DLCCoast, DLCworkshop02, DLCworkshop03, DLCNukaWorld not installed | verified | PR #371 docs/spikes/E-own-ecosystem.md, E1 |

## 1. The Commonwealth beyond the core

**Where we are.** The playable Commonwealth fits: FO4 refs span about 87x91 FO4 cells (5.1x5.3 km), inside the
6.4 km BTD (verified, core64c.md). Outside the BTD the engine draws Mars procedural ground past the mask ring
(supported, surface-map.md "Edge blend"). Two things are missing. First, the 25 Starfield cells per side of FO4 LAND
between 64 and 114 (FO4's own unplayable, LOD-only hills and sea; 55 % of LAND cells average below 0 m). Second, the
DLC placements and overrides inside the Commonwealth (core64c.md: "DLC placements ... not included").

**Next phase needs.** (a) DLC layers in the Commonwealth: each DLC esm read as a further master with its own
deterministic FormID range (E-own-ecosystem.md item 6). Automatron, Wasteland Workshop, Contraptions and Vault-Tec
place objects and edit Commonwealth cells. Nuka-World's Transit Center sits in the Commonwealth (supported; exact
counts are unresolved until the census). (b) A far-view answer for the outer ring.

| Option | What | For | Against |
|---|---|---|---|
| A. Grow the BTD to 80-90 cells | Generator already takes `--tile`; the 90-cell window reaches 641 m peaks | Exact terrain to the horizon, terrain LOD inside the BTD for free | 200-270 MB BTD; no precedent above 64; landing max is about 90 (100 - 2x5) |
| B. Keep 64, outer ring as static LOD meshes | Option (d) of commonwealth-scale.md | Leaves a known-good core alone | New mesh + LOD pipeline; still needs object LOD to exist |
| C. Crop, accept Mars beyond | Today | Free | Mars on the horizon, at odds with "its own ecosystem" |

**Recommendation:** A as a terrain-only trial, but only after the DLC layers (breadth first). Keep C until then.
**Risks:** a larger BTD may stream worse. The 1-cell merge ring sits further out, which helps. The core's merge
offset moves if the overlay's size or origin changes, so every hard-coded (-1200, -2700) would need a re-measure.
Prefer keeping the core's origin fixed (`--pad origin`).
**Cheapest test:** offline, from the cached LAND `.npz`: count the cells between 64 and 90 that are above sea level
and visible from the playable area (a horizon check). If few are, A is not worth it. PC (small): a terrain-only
90-cell build, then one coc plus 200 m hops along one ray. Read heights and the merge offset.

## 2. DLC worldspaces (the port assumes all six DLC)

**Where we are.** Nothing is converted. Only synthetic tests name `DLCCoast.esm` ids (tests/test_make_core64c.py:498).
Fallout4.esm-only depot (core64c.md).

| DLC | New exterior worldspace | Label |
|---|---|---|
| Far Harbor (DLCCoast) | yes: the island, Bethesda's "largest landmass for an add-on" (https://www.tweaktown.com/news/51247/fallout-4s-far-harbor-dlc-bigger-shivering-isles/index.html) | size in cells unresolved |
| Nuka-World (DLCNukaWorld) | yes: the park region. Larger download than Far Harbor (3.66 vs 2.7 GB, https://www.gamestar.de/artikel/fallout-4-nuka-world-dlc-wohl-groesser-als-far-harbor,3301230.html), which says nothing about land area | size unresolved |
| Automatron (DLCRobot) | supported: no new exterior worldspace; interiors (the Mechanist's Lair) plus Commonwealth edits | census |
| Vault-Tec Workshop (DLCworkshop03) | supported: Vault 88 as interior cells plus a Commonwealth entrance | census |
| Wasteland Workshop (DLCworkshop01), Contraptions (DLCworkshop02) | supported: workshop objects, little or no new world | census (DLCworkshop01: 38 / 23 / 15 ... in E1) |

**Next phase needs.** One overlay per DLC exterior world. Each is a separate WRLD + SFBK + BTD + Location,
registered as its own PNDT `CNAM` entry at a lat/long far enough from the core that the two landings do not overlap.
Cydonia's 8 overlays span 51x79 cells at H_ll scale 1, so a separation of more than 1 landing (>100 cells) is safe
(supported, commonwealth-scale.md section 2). Interiors go into FO4Port-style interior plugins, joined by the door path.

| Option | For | Against |
|---|---|---|
| A. Same host planet (Mars), one landing per DLC world | All existing machinery (one more PNDT entry); no new planet | Mars sky and surroundings; a merge offset to measure per world |
| B. Each DLC world on its own planet record | Matches "own ecosystem"; own sky and biome | Custom planet is Phase C research (commonwealth-scale.md option c); 4 unknown rules |
| C. Put the DLC world inside the Commonwealth BTD | One landing | Far Harbor is an island off Maine: geography would be fake |

**Recommendation:** A now, B as a later Phase C swap. The WRLD/Location layout keeps that swap possible.
**Risks:** the merge offset of a second overlay is unmeasured (H_ll is a hypothesis). Travel between landings
uses the persistent-ref path, which today drops the player at unmerged coordinates (section 5). Far Harbor's fog
and weather are separate work.
**Cheapest test:** first, the owner installs the four missing DLC. Then a read-only PC job extending E1, using the
existing raw walker (`fo4land` / Fo4Export). Per DLC esm and per WRLD, record: edid, parent world, LAND grid
min/max, MNAM map bounds, cell count, REFR/ACHR count, MapMarker count, and how many records override
Fallout4.esm cells. Per esm: interior CELL count. That takes minutes and one table, with no game launched.

## 3. Maps: Starfield surface map, its 3D view, and the Pip-Boy

**Where we are.** The surface map is Starfield's May 2024 loading-zone camera (https://progameguides.com/starfield/starfield-may-update-finally-lets-players-fast-travel-within-cities/:
the map was revamped and POIs must be rediscovered, greyed out until then). It draws overlay BTD terrain, the
planet's ground and world object LOD (supported, surface-map.md). The 3D acceptance screenshot is not taken yet.
Markers: 4 written (Red Rocket, Sanctuary, Vault 111, Concord; map-markers.md), enabled since #356, no icon in v6.
PR #376 (open) adds `FO4SFMapMarkers.esm`, a quest that moves each marker to its merged spot every 2 s.

**The key lead (supported), with a correction (Claude-cloud, 19 Oct 07:40Z).** Vanilla LC172's persistent COC marker
0010238E reads at its merged position (offset -500, -2300; terrain_A2_lc172 and merge_ctrl_lc172). Ours read unmerged
4 of 4 times (commonwealth-scale.md section 2). Two writer-side causes are **already refuted in game**:
fix A, which gave our persistent cell vanilla's record shape (flag 0x400, XCLC sentinel, LTMP, XCLW, XILS; queue
cave_fixA_1015, JOURNAL 2026-10-15), and fix E, which added WRLD OFST / CLSZ (queue cave_ofst_1015, FAIL NOLOAD,
testing/manual-test-commands-2026-10-17.md). Cell storage and the XTEL frame already match vanilla
(door-frames.md section 3). So the project moved to runtime moves (the door script's MoveTo + SetPosition, the
mission's Relocate in #353, the marker quest in #376), and #376 stays the path for now. Still **unresolved**:
cell ownership (XLCN), the WRLD's overlay component or parent fields, and whether the merge only covers persistent
refs of worlds that a vanilla master registers. **The cheapest discriminating test (PC, small, later):** an add-on
plugin that places one persistent XMarker in vanilla LC172World's persistent cell, read with `getpos` after
`coc LC172Ext01` (the control run's arrival). If it reads merged, the cause is in our WRLD/LCTN records, so diff
those next. If it reads local while vanilla 0010238E reads merged in the same session, persistent refs that plugin
adds did not merge in that world, build, load order and save; that supports keeping the runtime moves as the design,
without proving no record shape can merge. (Built and offline-checked 07:47Z as #376's FO4SFMergeProbe.esm, staged
on the PC, not installed.)

**Next phase needs.** (a) Every FO4 map marker, Fallout4.esm plus DLC, as a MapMarker REFR at the merged position,
with an `LCSR` row each. The FO4 `XMRK`/`FNAM`/`TNAM` layout is unresolved in the cloud (map-markers.md "FO4 map
markers"). (b) A discovered-on-approach behaviour like FO4's. In Starfield the marker `FNAM` bits are unresolved;
FO4/Skyrim Papyrus has `AddToMap(bool abAllowFastTravel)` (https://falloutck.uesp.net/wiki/AddToMap_-_ObjectReference);
that it exists in Starfield is supported, not verified. (c) Later, the Pip-Boy map (E7). FO4's map is a texture plus
WRLD MNAM bounds, built locally from the player's FO4 (the texture's path and format are unresolved here).

| Option | For | Against |
|---|---|---|
| A. Starfield surface map + markers only | Native fast travel and discovery; already close | Shows Mars around the core; Starfield UI |
| B. Pip-Boy world map (Scaleform, from FO4's own map assets) | "Own ecosystem"; FO4 look | New UI work (E7); fast travel must be scripted |
| C. A now, B later on the same marker records | Breadth first; B reuses A's markers | Two UIs for a while |

**Recommendation:** C. The marker records are shared and only the presenter changes.
**Cheapest tests:**
- Read-only console, owner or runner, no build: in vanilla LC172, `prid 003E5E12` then `getpos x` / `getpos y`.
  Compare with its DATA (37.4, 57.2) and the offset (-500, -2300). Then the same for ours (`prid 030A775A`: about
  (-1154, 1260) local or (-2354, -1440) merged, per map-markers.md). This tells whether vanilla persistent markers
  are merged and whether the map draws from the merged spot.
- Offline / PC read-only: a raw record diff of LC172World's persistent cell (anchor, marker, flags, owning CELL, its
  XCLC grid) against `FO4Core_Commonwealth`'s. That fits a short Fo4Land / SfInspect run.
- The owner's ask: "show all markers" is `tmm 1` in FO4/Skyrim. That it works in Starfield is a supported hypothesis
  only, and it cannot help while the markers sit at their unmerged spot.

## 4. LOD

**Where we are.** Terrain LOD: inside the BTD (LOD0-4), verified layout (commonwealth-scale.md 1.3), but only within
the 6.4 km. Object LOD: none, so past the loaded cells there is "nothingness" (playtest row 24). Vanilla format:
`lodsettings/<world>.lod` (20 bytes; the first two i32 read as cell min, then a size or flag: supported), lod NIFs
`meshes/lod/generated/..._lod_0..3.nif`, and one `distantlod/lodruntimedb.bgsdb` (object-lod.md). Converted FO4
`*_lod.nif` (315 files) are ordinary meshes, not world LOD. FO4's `.bto` object LOD is a FORMAT-GAP.

**Tools (public).** xLODGen's support thread lists FNV, FO3, FO4, FO4VR, TES5, SSE, TES5VR and Enderal, and not
Starfield (https://stepmodifications.org/forum/topic/13451-xlodgen-terrain-lod-beta-132-for-fnv-fo3-fo4-fo4vr-tes5-sse-tes5vr-enderal-enderalse/page/141);
its help page names TES5/SSE modes only (https://dyndolod.info/Help/xLODGen). Support for Starfield is
**supported** (absent). Step's Starfield guide lists an xLODGen line `-lodgen -SF1` (https://stepmodifications.org/wiki/Starfield:1.0),
but its LOD step text could not be read, so it is **unresolved**. The CK as generator (`-MockWorldSpaceLOD` in
surface-map.md) is **unresolved**: no public doc was found.

| Option | For | Against |
|---|---|---|
| A. Creation Kit LOD generation on the player's PC (launcher step) | Engine-native output | CK must be installed by the user; headless use unknown; 648k refs may take hours; CK might refuse an overlay this large |
| B. Our own generator: `.lod` + lod NIFs (+ runtime db) from converted meshes | Deterministic, runs in the launcher, no CK | Needs the .lod / lod-NIF naming / bgsdb format decoded; mesh simplification work |
| C. Convert FO4's own precomputed object LOD (.bto) from the player's FO4 | Content already exists, FO4 look | .bto layout unresolved; still needs Starfield's lodsettings/naming to load it |

**Recommendation:** spike A on a tiny overlay (the plan in surface-map.md / object-lod.md) only as a format oracle.
Decode what it writes, then build B (fed by C's meshes if .bto decodes) as the launcher path. The launcher must not
depend on the CK. Do not raise `uExterior Cell Buffer`.
**Risks:** `lodruntimedb.bgsdb` may be a global database that must be merged, not added (unresolved). LOD for DLC
worlds multiplies the work.
**Cheapest tests (offline / read-only PC):** list LODMeshes.ba2 names for `lc172world` and `newatlantis`, and
correlate the 864 `.lod` headers with each world's SFBK size and NAM0/NAM9 bounds. This confirms or refutes
"cell min / size". Then a header walk of `lodruntimedb.bgsdb` (size, record count, whether world edids appear).

## 5. Fast travel and travel between worlds

**Where we are.** Phase A's exit criterion is arriving at Red Rocket by fast travel to its marker (ROADMAP section
0); not met. Playtest row 7: fast travel to the Frontier hung (supported cause: no marker chain, a ship-travel path).
Arrivals that work today: `coc` to COC markers, door MoveTo onto loaded temporary refs (door trip PASS, 16 Oct), and
hops of 200 m or less. MoveTo onto a persistent ref lands unmerged; offsets passed across a world switch are ignored
(JOURNAL 16 Oct, probes c-d).

**Starfield's model:** star map plus ship between planets and landings, and on-planet fast travel to discovered POIs
of the current landing (May 2024 update, link above). A community mod adds interior fast-travel targets by "placing
a MapMarker in the exterior worldspace with a linked reference to an XMarker in the interior cell"
(https://www.nexusmods.com/starfield/mods/12719, verified as described; behaviour supported). **FO4's model:**
Pip-Boy fast travel to any discovered marker in the worldspace; DLC worlds reached through scripted travel (boat,
train/door).

**Recommendation.** Inside a world, use native marker fast travel once markers sit at merged positions (section 3
fix), with a mod-style linked XMarker as the arrival point. Between worlds (Commonwealth to Far Harbor or
Nuka-World), use scripted load doors and travel activators to the DLC world's COC-style arrival, the way FO4 does
it. This needs no ship. Keep Starfield's ship travel out of the port's path ("own ecosystem").
**Risks:** a fast-travel load into a 6.4 km overlay with 648k refs may be slow; fast-travel time and survival
hooks; the Frontier hang may be a separate ship-path bug.
**Cheapest tests:** after the section 3 diff, one read-only console check: open the map at Red Rocket, fast travel
to Sanctuary, and read the position (must be about the merged spot). For worlds: a terrain-only second overlay with
one COC marker, then `coc` into it and MoveTo across from the core's door script. That measures the second merge
offset and the cross-landing arrival.

## Prioritized next steps

1. **Persistent-ref diff (vanilla LC172 vs ours)**: read-only console `getpos` plus a raw record diff. Decides whether
   a writer fix replaces #376 and also fixes doors and actors. Owner: Claude (game), Codex QA.
2. **Owner installs DLCCoast, DLCworkshop02, DLCworkshop03, DLCNukaWorld**, then a read-only DLC census (section 2 table).
3. **Bulk FO4 map markers**: decode FO4 `XMRK`/`FNAM`/`TNAM` on the PC from Fallout4.esm (read-only), then one marker class over Fallout4.esm plus DLC (synthetic tests first).
4. **Object LOD format oracle**: .lod/bgsdb read-only decode, then the CK tiny-overlay spike, then a go/no-go on our own generator for the launcher.
5. **DLC layers onto the core**: DLC objects in Commonwealth cells as further masters (deterministic FormIDs).
6. **Far Harbor overlay, terrain only**, at a second lat/long; measure its merge offset; a door and travel trip.
7. **Outer ring horizon check** (offline), then a core90 trial only if it pays off.
8. **Pip-Boy map v0 design** (E7) on the shared marker records.

## Open questions for the owner

1. Can you install the four missing DLC (Far Harbor, Nuka-World, Contraptions, Vault-Tec Workshop) on the PC? The
   DLC census and everything after it waits on them.
2. Map first: is Starfield's surface map acceptable for now, with the Pip-Boy map later, or should the Pip-Boy come
   first?
3. DLC worlds: stay on Mars as separate landings (fast), or should each get its own planet (Phase C, slower)?
4. Launcher: is it acceptable that a build step needs the free Creation Kit installed (LOD), or must the launcher
   stay CK-free (our own LOD generator)?
5. Far view vs breadth: does the horizon (LOD, outer ring) wait until all worlds load, as "breadth before polish"
   suggests?
