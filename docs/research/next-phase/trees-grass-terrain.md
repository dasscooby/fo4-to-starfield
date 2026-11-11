# Next phase: trees, grass and terrain for every Fallout 4 worldspace (DLC included)

Foliage thread (Claude-cloud), 2026-10-19 overnight. Repo main 4492d13. Labels follow docs/ai/research-log.md:
**verified** (file, command or output named), **supported** (evidence points one way, not shown in game),
**unresolved**. Nothing here was run in game. A read-only PC survey is queued (section 7) and will fill in the
per-worldspace numbers (Part A arrived 07:30Z and is in section 2).

## Short answer

1. **Terrain heights are solved for one world; everything else about the ground is not.** The Commonwealth core is
   one 64 x 64-cell native BTD overlay with FO4 heights within centimetres (verified offline and in game: exp2b3,
   core64). Every sample is painted with one Starfield texture (`LDirtFootprints01`, 001235C2; make_cw_overlays.py
   `ltex_source`), there is no grass at all, and trees are converted statics that vanish at the loaded-cell edge.
2. **Breadth order I recommend:** (a) FO4 land textures on the BTD across the whole core, (b) a small grass go/no-go
   overlay, (c) Far Harbor and Nuka-World as their own overlay worldspaces with heights and objects, (d) tree LOD and
   wind, (e) the small worlds (prewar Sanctuary, Diamond City, Goodneighbor). (a) is offline work with a large visible payoff; (b)
   decides whether grass is cheap or expensive; (c) is the "all DLC" rule and is blocked today by one converter gap.
3. **DLC blocker (verified):** the converter opens only archives named `Fallout4 - *.ba2`
   (src/fo4sf/pipeline.py:115, scripts/convert_batch.py:30), and `dotnet/Fo4Land export-exterior` loads one plugin
   (`Fallout4Mod.CreateFromBinaryOverlay(args[0])`, ExteriorExport.cs:40). So no DLC mesh, texture or worldspace can be
   converted until both read the DLC archives and a load order (DLC records place Fallout4.esm bases).
4. **Everything below fits the launcher model**: every record (LTEX, GRAS, GCVR, BIOM, WRLD), every BTD and every
   texture is generated on the user's PC from their own Fallout4.esm, DLC esms and BA2s. No asset ships.

## 1. What today's build has (verified unless marked)

| Piece | State | Evidence |
|---|---|---|
| Heights | native BTD, 64 x 64 cells (6.4 km), FO4 heights / 70, 1.2 cm steps | docs/terrain/commonwealth-scale.md 6a; exp2b3 read FO4 heights within 0.08 m |
| Land textures | ONE Starfield LTEX on every quadrant (TempJemisonWorld's table) | make_cw_overlays.py `ltex_source` (line 397) |
| Grass | none | no GRAS / GCVR / BIOM written by TerrainOverlays (grep) |
| Trees | FO4 tree NIFs as STAT, collision kept; leaf cards now two-sided cutout (#288, v5, in-game look pending) | experiment2c.md: 1,382 tree refs convert; v5 manifest: vine.mat parent TwoSided1Layer |
| Distant view | BTD terrain only; no object LOD, so trees and buildings pop at the loaded-cell edge | docs/terrain/object-lod.md (Grok) |
| Far ring | the full FO4 LAND grid is 114 Starfield cells; one landing holds about 90 | commonwealth-scale.md 1.3, 1.4 |
| Water | not handled (55 % of LAND cells average below 0 m) | commonwealth-scale.md 1.3 |

## 2. The worldspaces to cover

Verified by the PC survey (fo4_world_survey.py at c356cc1, 2026-10-19 07:30Z, clean depots; refs = placed
REFR, by the base's model folder; "unknown" = bases outside STAT/SCOL/MSTT/FLOR/TREE such as furniture, doors, items,
lights; "other" = statics outside the landscape folders):

| Plugin | Worldspace | Cells / LAND | Heights (m) | Refs | Trees | Plants | Rocks | Grass statics | Status |
|---|---|---|---|---|---|---|---|---|---|
| Fallout4.esm | Commonwealth | 36,864 / 36,864, x and y -96..95 | -118.86..641.03 | 701,757 | 57,508 | 72,410 | 46,763 | 4,895 | core built (64 cells) |
| Fallout4.esm | SanctuaryHillsWorld (prewar intro) | 1,728 / 118, x -28..7, y -13..34 | 0..149.83 | 4,276 | 1,967 | 481 | 132 | 271 | not built |
| Fallout4.esm | DiamondCity (child of Commonwealth) | 164 / 38 | -30.06..-29.26 | 4,401 | 1 | 158 | 1 | 162 | not built |
| Fallout4.esm | Goodneighbor (child of Commonwealth) | 108 / 0 | uses the parent's land | 6,691 | 2 | 5 | 0 | 21 | not built |
| Fallout4.esm | DiamondCityFX (child) | 101 / 0 | | 1 | | | | | effects only |
| DLCRobot.esm | edits Commonwealth (no new world) | 111 / 2 | 8.69..13.83 | 671 | 4 | 4 | 4 | | rides on the core |
| DLCworkshop01.esm | no worldspace | | | | | | | | |
| DLCCoast.esm (Far Harbor) | the island | not on the PC yet | | | | | | | community count 937 navigable cells, about 32 % of the Commonwealth (unverified) |
| DLCNukaWorld.esm | the park and its wasteland | not on the PC yet | | | | | | | community count 516 cells, about 17 % (unverified) |
| DLCworkshop02, DLCworkshop03 | not on the PC yet | | | | | | | | expected: no worldspace (supported) |

LTEX 105 (52 of them carry a grass list), GRAS 82 (Fallout4.esm). Far Harbor, Nuka-World and the two other workshop
DLC esms are missing from the PC (the user is installing them), so the survey reruns when they land.

Two things this changes:
- **DiamondCity and Goodneighbor are child worldspaces of the Commonwealth** (parent 00003C): they reuse its land and
  are walled areas the player enters by a load door. In Starfield each becomes its own small overlay worldspace or an
  interior-like cell set; DiamondCity is 14 x 12 FO4 cells (about 8 x 7 Starfield cells).
- **Trees are big: 57,508 placed in the Commonwealth** (8 % of its references), plus 72,410 plants. They already
  convert as statics, so the tree work is LOD (distance) and wind, not placement.

FO4 counts: docs/terrain/architecture.md section 2 and docs/measurements/fo4_esm.json (WRLD 5, LAND 37,020).
Community size source: [The SIZE! A comparative study on vanilla FO4 and DLCs](https://steamcommunity.com/app/377160/discussions/0/350543319567332507/).

What that means here (supported): 937 FO4 cells is about 31 x 31 FO4 cells of land = about 18 x 18 Starfield cells of
area, and Nuka-World about 14 x 14; both islands of content fit one overlay each, well inside the 64 cells the core
already proved. exp3 showed a landing loads only the overlay it arrives in (commonwealth-scale.md 6a), so each FO4
worldspace becomes its **own** overlay worldspace with its own landing, and the FO4 transitions (the boat to Far
Harbor, the monorail to Nuka-World, the Vault 111 intro) become load doors or fast travel, which is how FO4 joins them
too. The host can be the same planet at different lat/long (the Mars registration already works for the core).

## 3. Land textures (next build's biggest visible change)

FO4 side (xEdit FO4 definitions, `wbDefinitionsFO4.pas` dev-4.1.6, supported; counts verified in fo4_esm.json):
LTEX (105) = texture set TXST (382) + material type + havok + a **grass list** (GNAM). LAND paints a base texture
per quadrant (BTXT) and alpha layers (ATXT + VTXT per-vertex opacity on the 33 x 33 grid).

Starfield side (xEdit SF definitions `wbDefinitionsSF1.pas`, supported; BTD layout verified, architecture.md 1.4):
LTEX (416) = a **material file** (BNAM `.mat`) + material type + havok + dirtiness, no texture set and no grass list.
The BTD holds an LTEX table, 8 bytes of LTEX table indices per cell quadrant, and per sample 5 layers of 3-bit
alphas. Our writer (src/fo4sf/btd.py) already writes all of that; today it copies a one-texture template.

Plan:
1. Convert each FO4 TXST used by LAND into a Starfield terrain `.mat` (diffuse, normal, roughness from FO4's
   specular as the object converter does), and write one LTEX per FO4 LTEX in the core plugin.
2. Resample FO4's BTXT/ATXT/VTXT onto the 128-per-cell BTD grid (the heights already use the same resampler,
   terrain_grid.py) and keep the 5 strongest layers per quadrant (FO4 can stack more; dropping the weakest is a
   supported choice, its look unresolved). Alphas quantise to 3 bits.
3. No core reconvert of objects is needed: this is the BTD plus a small set of LTEX records and textures, a rebuild of
   minutes (the 64-cell BTD built in 9.3 s), plus the terrain textures (about 100, a texconv pass).
Unresolved: whether Starfield's terrain shader reads an overlay's painted layers as-is or blends them with the
biome's procedural layers (WRLD BNAM biome; section 4); the first in-game look answers it.

## 4. Grass

FO4: grass comes only from LTEX grass lists (82 GRAS; one GRAS = a model plus density and slope rules), drawn where
that texture is painted. Placed "grass clump" and "grass mound" statics are separate (experiment2c.md: 408 clumps,
316 mounds in the exp2c area) and already convert as objects.

Starfield (xEdit SF definitions, supported): GRAS (189) keeps the same idea (model plus DNAM density, slope, wind,
coverage). Grass is grouped in **GCVR "Ground Cover"** records: a list of GRAS with density overrides, a list of
**Landscape Textures** and a "Painted Material Threshold". A biome (BIOM, 431) maps each terrain mask to a pair
(LTEX, GCVR), and **WRLD BNAM names the worldspace's biome**; WRLD DATA still has a "No Grass" flag. The community
biome guide says the same in CK terms: a biome's Terrain Data sets "Land Texture" and "Ground Cover ... grass, ferns,
moss" ([Nexus article 643](https://www.nexusmods.com/starfield/articles/643)). The GCVR's own LTEX list and painted
threshold suggest ground cover also follows **painted** textures on an overlay (supported hypothesis, the key
unknown).

Plan, gated:
1. Go/no-go (one small overlay, minutes to build): convert 2 FO4 GRAS models (the object path, with #288's two-sided
   cutout material), write GRAS, one GCVR listing them and one of our LTEX, a BIOM whose terrain data uses them, and
   set our WRLD BNAM to it; paint that LTEX on half the overlay. Look: grass on the painted half only, nothing on the
   other.
2. If it works: one GCVR per FO4 LTEX grass list across every worldspace; grass then costs almost nothing in refs.
3. If it does not: grass only as placed statics (FO4 clumps already are), which is a lot of references; or vanilla
   Starfield ground cover as a stand-in, which breaks "as far from Starfield as possible". I would report it, not
   pick it.
PC Part B (verified; Job 7, sf_ground_cover.py 0685e85, output C:\Modding\scratch\nextphase\job7.txt and
sf_ground_cover.json). Each WRLD carries two BNAMs: the first is the overlay component's Surface Block, the second
the Biome. Cities: akilacity 27CFA2 -> 203EA1 `SavannaLifeAkila`, NewAtlantis 01251B -> 1CBD6A
`ForestDeciduousLifeJemison`, CydoniaCity 2CFC4A -> 2A3777 `DesertRockyNoLifeMars`. Each biome has 12 terrain entries:
7 main (masks 0 to 6) and 5 alternate (masks 1 to 5); my earlier "5 and 5" from SfInspect was wrong. Each entry is one
(LTEX, GCVR) pair, ground cover optional; e.g. Akila mask 2 is `LGrassDeadWet02` with `GC_GrassFieldDried04` (4 GRAS:
SaltGrass02, GrassFieldDried04A, SaltGrass03, GrassFieldDried02CClump), New Atlantis mask 3 is `LDirtForestRoots02`
with a fern and mayapple cover.

Two findings change the plan:
- **Our Commonwealth already names a biome: Cydonia's Mars one.** FO4TerrainCore WRLD 000803 has BNAMs
  [FO4TerrainCore 000801, Starfield 2A3777], and its 12 terrain lines are Cydonia's (Mars sand and rock textures with
  GC_RocksLayered02 to 05, all rock "grass"). So any Starfield ground cover we see in the Commonwealth today is Mars
  rock scatter, and our own biome must replace 2A3777 there (verified record; what it draws in game is unchecked).
- **All 10 GCVRs read have an empty LTEX list** (ltex 0), with painted thresholds 0.30 to 0.52. So in vanilla the link
  from texture to grass is the biome's mask entry, not the GCVR's LTEX list. The "grass follows painted overlay
  textures" idea above is now weaker (still unresolved: how a mask is chosen per spot, and whether the threshold
  applies to the mask's weight).

Go/no-go, revised: write our own BIOM with one main entry per used mask, each pairing a converted FO4 LTEX with a GCVR of
converted FO4 GRAS, and point our WRLD's second BNAM at it in place of 2A3777. Look: FO4 grass instead of Mars rocks,
and where it appears. Totals in Starfield.esm: WRLD 434, BIOM 431, GCVR 96, GRAS 189, LTEX 416. GRAS DNAM is 40 bytes
(e.g. SaltGrass02 `00008e42 cdcc4c3f 6666e63e ...`); its field layout is not decoded yet.

## 5. Trees

- FO4 has 1 TREE record (fo4_esm.json); its trees are STAT NIFs under `landscape\trees`, so the existing static
  path converts them (verified, experiment2c.md). Starfield has no TREE records either (sf_esm.json: none).
- **Leaves**: the #288 material fix covers alpha-cutout leaf cards (two-sided parent, Summary Opacity). Its in-game
  check is the Red Rocket vines on v5; the same look on a maple or a dead tree confirms trees.
- **Wind**: FO4 sways trees through a tree-animation shader flag and vertex colours; Starfield's equivalent in its
  layered materials is unresolved. Static trees are acceptable for breadth; this is polish.
- **Distance**: no object LOD means trees disappear past the loaded cells. FO4 ships its own object and tree LOD per
  worldspace (supported: `meshes\terrain\<world>\objects`, `.bto`, and tree LOD atlases); Starfield's is
  `meshes/lod/generated/*_lod_0..3.nif` plus `lodsettings/<world>.lod` (object-lod.md, verified listing). Converting
  FO4's own LOD meshes would keep FO4's look at distance and avoid a CK step; the `.lod` settings format (20 bytes,
  cell min / size, supported) is the one unknown to test. This also covers buildings, not only trees.

## 6. Size, disk and build time (for the launcher plan)

- Core archive today 3.585 GiB of a 3.8 GiB budget (v5 check). Land textures add about 100 textures; grass adds a
  few dozen small models. Each DLC worldspace is its own plugin and archive (each under 4 GiB), so the budget is per
  world, not shared.
- Build times measured: full core object convert 2,582 s at idle priority (v5), stage plus check minutes, 64-cell BTD
  9.3 s. A Far Harbor convert should scale with its unique models (supported; the survey gives the counts).
- D: is nearly full on the PC; every new world wants its own work folder (several GiB). The launcher should check
  free space before a build and clean old work folders it owns.

## 7. PC survey (queued, read-only)

`scripts/terrain/fo4_world_survey.py` (branch claude/project-thread-su5jeg, draft PR #379, sha256 10f25a00...)
lists every worldspace in Fallout4.esm and each DLC esm: cells, LAND, height range, the LTEX it paints (with grass
lists), GRAS models, and placed refs by family (trees, grass, plants, rocks, cliffs). Part B dumps vanilla
Starfield's biome and ground-cover wiring for three overlay cities. Results land in this file when they arrive.

## 8. Recommended bounded queue

1. Converter and exporter read DLC archives and a load order (unblocks every DLC world; offline, unit-testable).
2. FO4 land textures on the core BTD (offline build plus one in-game look at Red Rocket and Sanctuary).
3. Grass go/no-go overlay (one look).
4. Far Harbor overlay: export, convert, stage with the core64c pipeline, one in-game arrival plus a short walk.
5. Nuka-World overlay, same steps.
6. Object LOD spike from FO4's own LOD meshes.
7. SanctuaryHillsWorld, DiamondCity and Goodneighbor (small; the last two are child worlds of the Commonwealth).
Unresolved, by gate: painted layers versus biome blending (2), ground cover on overlays (3), overlay size and arrival
for DLC worlds (4), `.lod` format (6).

Sources: repo docs named above; xEdit definitions `Core/wbDefinitionsSF1.pas` and `Core/wbDefinitionsFO4.pas`
(TES5Edit dev-4.1.6, read only); [Nexus Starfield article 643](https://www.nexusmods.com/starfield/articles/643);
[Steam size comparison](https://steamcommunity.com/app/377160/discussions/0/350543319567332507/);
[Wikipedia: Fallout 4 downloadable content](https://en.wikipedia.org/wiki/Fallout_4_downloadable_content).
