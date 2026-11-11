# Overlay records: making our terrain worldspaces look like vanilla unique overlays

Author: Claude, 2026-10-11. Branch `claude/terrain-overlay-records`, stacked on PR #60 (terrain experiment 2, which
contains PR #56 and #57). Starfield 1.16.244. Written before any run; exp1d and exp2b then ran in game on
2026-10-11 (unattended runner), see [In-game result](#in-game-result-2026-10-11). Nothing here ran in the Creation Kit.
Labels: **verified** (checked offline on files, or measured in game where it says so), **supported** (supported
hypothesis: evidence, not proven in game), **unresolved**, **refuted** (contradicted by a measurement).

## Why
A worldspace's own BTD is applied only when the worldspace is an activated overlay on a planet (a planet's PNDT
`CNAM` entry registers it). Activation merges its cells into the planet worldspace at a whole-cell offset plus a Z
offset (research notes 2026-10-11, `C:\Modding\research\terrain\binding\findings.md`). Both are now **verified** in
game: unregistered World01 and World02 showed identical procedural planet ground (`C:\Modding\testqueue\terrain_exp1`,
`terrain_exp1b`), and the vanilla LC172World overlay was measured at (-499.98, -2300.00, -3.62) m from its
persistent COC marker `0010238E` (`terrain_A2_lc172`); World01 on Mars merged at +3000 / -3500 m, exp2b at
-1200 / -2700 m. The first
experiment plugins (exp1 / exp1b / exp1c, exp2) differ from vanilla unique overlays in four checkable places. This
branch fixes all four, adds a Mars registration plugin for experiment 2 and gives both experiments a persistent
anchor ref, so the runner can measure the merge offset directly.

| # | Difference | Vanilla | Ours before | Now |
|---|---|---|---|---|
| 1 | SFBK `FNAM` size | `DNAM.x * DNAM.y` u16 | 16 B (8 values) | one u16 per BTD cell |
| 2 | WRLD `XLCN` | always set | none | own LCTN like `LC172WorldLocation` |
| 3 | overlay mask | `textures/terrain/overlaymasks/<edid>.dds` | none | ring mask, BC4 |
| 4 | SFBK `INAM`/`HNAM` | 0 Relative (most), 1 Absolute (10 blocks) | 0 / 0 (template) | option; exp2b uses Absolute, HNAM 0 |

## 1. SFBK FNAM: one raw height per BTD cell (size verified; content rule supported, strong)
- Size: all 1,730 vanilla SFBK with an `FNAM` store `DNAM.x * DNAM.y * 2` bytes (3 x 3 = 18 B, 5 x 5 = 50 B,
  14 x 14 = 392 B; raw walk of Starfield.esm). Ours stored 16 B. The research notes add the 56 SFBK of SFBGS00D.esm.
- Content: compared with per-cell statistics of the raw u16 BTD heights. Survey: every vanilla SFBK with 1..30 cells
  whose BTD is in `Starfield - Terrain01..04 / TerrainPatch.ba2`, 1,711 records; grids always match `DNAM`.

| Statistic per cell (raw u16) | records with every cell exact | cells within 1 raw unit |
|---|---|---|
| **south-west corner sample** (row 0, column 0 of the cell; row 0 = south) | **1,464 of 1,711 (85.6 %)** | **94.6 % of all cells** |
| same, rows flipped (north first) | 0 | 9.7 % |
| min, max, mean, median, midrange, centre sample (either row order) | 0 | 0.2 to 4.6 % |

  Order: cells row-major from the south row, west to east (the same order as the BTD's LOD0 blocks).
- Examples: `lc172world` 9 of 9 cells exact; `akilacity` 89 % of cells (max difference 25 raw = 0.57 m);
  `NewAtlantis` 91 %; `lc001world` only 4 of 25 (differences up to 1,759 raw = 40 m, FNAM above the cell's own
  maximum in places). The 247 records that are not exact are consistent with an FNAM written before a later terrain
  edit (**unresolved**; not needed for our files, which are written together).
- The 85.6 % is dominated by procedural blocks. For the blocks that matter here the rule is weaker (QA review on
  PR #64): overlay blocks behind a WRLD 255 of 430 exact, registered overlays only 29 of 72 (most of the rest differ
  in a few cells, median difference 0 m; lc133world 0 of 25, lc001world 4 of 25). Hence "supported (strong)", not
  verified, for the SW-corner content; the size rule has no exception.
- The earlier observation "`FNAM[0]` = the BTD's SW corner" (experiment 2) is the first value of this rule.
- `src/fo4sf/overlay.py` `fnam_values()` writes it; exp1d stores 25 values (50 B), exp2b 841 values (1,682 B). The raw
  walk of the written plugins shows the full length (Mutagen writes the longer array unchanged; **verified**).

## 2. Location (verified records, effect unresolved)
- All 430 vanilla WRLDs with a `BGSWorldSpaceOverlay_Component` have `XLCN` (raw walk). The keyword varies: 11 of the
  72 overlays registered on a planet point at a location with `LocTypeOverlay` (`2CA99D`), e.g. `LC172World` ->
  `LC172WorldLocation` (`3807BE`); the others (NewAtlantis, akilacity, lc001world, ...) have city / settlement
  keywords. So "always LocTypeOverlay" is not quite right; a location is always there.
- Ours copies `LC172WorldLocation`: `FULL`, `KWDA` = `LocTypeOverlay`, `DATA` (template), `PNAM` = `0001B736`
  `SSol_PMars_Surface` (Mars surface location), `RNAM` 0, `ANAM` 1.0, `XNAM` -1 / `YNAM` -3 (Mutagen: StarID /
  PlanetID, template values, meaning **unresolved**), without its two `LCSR` static references and `LCID`.
  Those stripped `LCSR`/`LCID` are the map-marker chain; TerrainOverlays now restores one MapMarker `REFR` at the COC
  and fills `LCSR`/`LCID` after doors/lights (Grok 2026-10-17: [map-markers.md](map-markers.md)).
  EditorIDs `FO4TX_World01Location`, `FO4CW_CommonwealthLocation`; the WRLD's `XLCN` points at it.

## 3. Overlay mask (verified file format; it governs height blending, verified on vanilla LC172World)
- Vanilla: `textures/terrain/overlaymasks/<edid lower case>.dds` in `Starfield - DensityMaps.ba2` (a General
  archive). Size = SFBK `DNAM` cells x 100 px (lc172world 300, lc001world 500, akilacity 900, newatlantis 1400),
  legacy header, FourCC `BC4U`, one mip. Values are 0 inside the authored footprint and 255 outside, with soft edges;
  the inside is a free shape, not a cell ring (lc172world: about columns 83..210 of 300).
- Ours: 0 inside, 255 on the outer ring of BTD cells (our BTDs hold real terrain everywhere), PNG -> texconv
  `-f BC4_UNORM -m 1` -> legacy `BC4U`, one mip; decodes back exactly (`overlay.bc4_decode`). Staged under
  `Data\textures\terrain\overlaymasks\`, so `exp_install.py --pack` puts it into `<plugin> - Main.ba2` with the BTD.
- What reads it: ~~procedural generation only (rocks, scatter; research notes)~~, **refuted** in game
  (`C:\Modding\testqueue\terrain_A2_lc172`). Probing vanilla LC172World relative to its overlay offset, the ground
  matched its BTD within 0.02 m in the cell its mask marks authored (mask 0, probe `lc172_7`), was 0.30-0.36 m off
  just outside it (`lc172_5` about 3 px inside the soft edge, `lc172_2`), and 4-6 m off in the mask-255 border cells
  (5 of 6 probes there). So the mask, or the outer cell ring, also controls how the overlay's heights blend with the
  planet; procedural clutter may follow it too. In LC172World the mask edge and the outer ring coincide, so this run
  cannot tell the two apart (**unresolved**).
- Design consequence: the outer ring of a Commonwealth overlay will not keep FO4 heights, so the BTD must extend at
  least one cell beyond the authored area. Our ring mask already marks the outer cell ring 255; every exp1d and exp2b
  plan point lies in an inner cell (exp2b: cells x -13..-8, y 8..13).
- Image row order is **unresolved** (our ring is symmetric).

## 4. Alignment (verified records, meaning supported)
- `INAM` 0 = Relative: 1,743 of 1,753 vanilla SFBK, including the LC landing overlays (`LC172World`, `lc001world`: `HNAM` 0).
- `INAM` 1 = Absolute: 10 blocks, all unique overlays: NewAtlantis (`HNAM` -239, raw `0xFF11`), SettleRedMile 0,
  LC133 -75, LC136 -68, LC092 -105, SettleParadiso -90, LC135 -135, NeonCity -51, LC070World01 -162,
  SettleNewHomestead -183. `HNAM` is a signed 16-bit value; it matches none of the BTD's min, median, mean, centre or
  SW corner for these ten (**unresolved**).
- Hypothesis (**supported**, from the CK's Relative/Absolute names): Relative places the overlay relative to the planet
  ground at the site (a placement-dependent Z offset), Absolute uses the BTD heights (+ `HNAM`) as world z. For exact
  Commonwealth heights exp2b uses Absolute with `HNAM` 0; exp1d stays Relative (as `LC172World`, its template).
  In game: Relative gives a Z offset (LC172World, `HNAM` 0: -3.62 m, **verified**); what Absolute does is still
  **unresolved**, because exp2b came out flat at the BTD's raw-0 height (see the in-game result).
  `make_exp2.py --alignment relative|absolute --hnam N`, `overlay_records.py exp1d --alignment ... --hnam ...`.

## 5. Mars registration and anchor
- PNDT `CNAM` entries are 20 bytes: f64, f64, u32 WRLD (raw). Mutagen's `MasterWorldspace.Longitude` is the first
  f64 and `Latitude` the second (**verified** by writing 1.2 / 0.2 and reading the raw entry). Vanilla Mars has 10
  entries; the registration plugins append one (index 10, entry count 11, **verified**).
  - `FO4TerrainExp1_Mars.esm` (exp1d): World01 at Latitude 1.2, Longitude 0.2 (as exp1b/exp1c).
  - `FO4TerrainExp2_Mars.esm` (exp2b): `FO4CW_Commonwealth` at Latitude -1.2, Longitude 0.3, far from the vanilla
    Mars sites (Latitude -0.09..-0.38) and from exp1. Both override `MarsPlanetData`: never install both.
  - Correction (2026-10-11, [commonwealth-scale.md](commonwealth-scale.md) section 2): the names above are Mutagen's,
    which are swapped. The first f64 is the **latitude** (Earth overlays sit at their real cities), so World01 is at
    latitude 0.2, longitude 1.2 rad and exp2b at latitude 0.3, longitude -1.2 rad.
- Anchor: a persistent `XMarker` (`00003B`, flag `0x400`) in the worldspace's persistent cell, FormID `0x800` (the
  builders allocate it first): exp1d `FO4TX_W01Anchor` at local (50, 50, 10) (ground under the COC marker), exp2b
  `FO4CW_Anchor` at local (-989.0286, 1147.2, 105.1434) (ground under the Red Rocket COC marker). plan.json names it
  `"02000800"`: `02` is the **assumed** load-order byte for Plugins.txt [`FO4TerrainExpN.esm`,
  `FO4TerrainExpN_Mars.esm`, `FO4Port.esm`] and depends on which official masters load first. If `prid` fails, the
  runner falls back to `spawn_local` (COC marker x, y and the ground under it).
- In game (2026-10-11): `prid` worked (byte 02 held), but **our anchors read back their unmerged local position**
  (exp1d `50.00 50.00 10.00`, exp2b `-989.03 1147.20 105.14`; **verified**, `C:\Modding\testqueue\terrain_exp1d`,
  `terrain_exp2b`), unlike vanilla LC172World's persistent COC marker, which reads its merged position. The anchor
  therefore cannot give the merge offset; the runner (branch `claude/test-queue`) now detects this
  (`anchor_unmerged`) and falls back to the arrival point. Why vanilla's marker differs is **unresolved**.

## Staged (outside the repo; installed by the runner for the 2026-10-11 runs)

| Folder | Contents |
|---|---|
| `C:\Modding\staging\terrain_exp1d` | `FO4TerrainExp1.esm` (World01 only, 2,553 B), `FO4TerrainExp1_Mars.esm` (6,516 B), `Data\Terrain\FO4TX_World01.btd` (the exp1 World01 BTD, 298,371 B), `Data\textures\terrain\overlaymasks\fo4tx_world01.dds` (500 px, 125,128 B), `exp1_params.json`, `plan.json`, `README.txt`, `offline_check.json` |
| `C:\Modding\staging\terrain_exp2b` | `FO4TerrainExp2.esm` (38,782 B), `FO4TerrainExp2_Mars.esm` (6,512 B), `Data\Terrain\FO4CW_Commonwealth.btd` (the exp2 BTD, byte for byte), `Data\textures\terrain\overlaymasks\fo4cw_commonwealth.dds` (2,900 px, 4,205,128 B), `exp2_params.json`, `expected.json`, `plan.json`, `README.txt`, `preview.png`, `offline_check.json` |

plan.json (runner format, points and `expect` in the worldspace's own frame, the runner adds the measured offset):

| | coc | anchor | spawn_local | drop_z | settle_ms | points |
|---|---|---|---|---|---|---|
| exp1d | `FO4TX_W01Spawn` | `02000800` local (50, 50, 10) | (50, 50, 10) | 80 | 8000 | ground, padA, padB, pitC, padA_edge_in/out (10 / 35 / 22.5 / 5 / 35 / 10) |
| exp2b | `FO4CW_RedRocketSpawn` | `02000800` local (-989.0286, 1147.2, 105.1434) | same | 150 | 8000 | the 14 experiment 2 points (Red Rocket, flat, slopes, seams, resampled) |

Install: `scripts/game/exp_install.py install --exp-dir <folder> --plugins FO4TerrainExpN.esm,FO4TerrainExpN_Mars.esm
--pack` (branch `claude/test-queue`): every folder under the staged `Data\` goes into `FO4TerrainExpN - Main.ba2`.
Loose files are not an alternative: they are disabled on this install (`Starfield.ini` `sResourceDataDirsFinal=STRINGS\`,
**verified**). The 2026-10-11 runs packed with Archive2's default zlib compression, so the BTD was stored compressed
(`fo4tx_world01.btd`: 43,257 of 298,371 B), while 0 of the 2,112 vanilla BTD entries are compressed;
`exp_install.py` now packs with `-compression=None`.

## Offline verification (verified)
`overlay_records.py check` / `make_exp2.py check` (raw record walk, independent of Mutagen) passed every item for
both folders. Note: `check` is not read-only, it rewrites `offline_check.json` in the staged folder (same content
on a rerun, new mtime); avoid running it on a folder the runner is using.
- BTD decoded at every plan point under bilinear and both triangle splits: exp1d worst 10.3 mm (pit C; step
  22.9 mm), exp2b worst 3.2 mm (step 3.9 mm). `spawn_local` z and the anchor z equal the decoded ground.
- WRLD `XLCN` -> LCTN in the plugin with `KWDA` `002CA99D` and `PNAM` `0001B736`.
- SFBK `ANAM`, `DNAM` n x n, `FNAM` = n x n x 2 bytes and equal to the SW-corner rule for every cell (25/25,
  841/841), `INAM`/`HNAM` 0/0 (exp1d), 1/0 (exp2b).
- Anchor REFR: base `0000003B`, flag `0x400`, FormID `01000800` in the file (= `02000800` at load-order byte 02),
  position = plan `anchor.local`.
- Mars plugin: overrides PNDT `0003F59A` `MarsPlanetData`, masters [Starfield.esm, experiment plugin], 11 entries,
  exactly one for the experiment WRLD.
- Mask: BC4, n x 100 px, one mip, decodes to the ring with 0 differing pixels.

## In-game result (2026-10-11)
Unattended runner, evidence in `C:\Modding\testqueue\<queue>\tests\...\obs.json`:

| Queue | Read | Status |
|---|---|---|
| `terrain_exp1d` | arrival at (3050, -3450, **-500.00**): the BTD's raw-0 height (`ENAM` minimum of -500 / 1000), merge offset +3000 / -3500 m. The anchor read its unmerged local (50, 50, 10), so the runner used offset 0 and the six probes landed outside the overlay, on Mars ground | flat, verified |
| `terrain_exp2b`, `terrain_exp2b2` | merge offset -1200.0014 / -2700 m (from the arrival; the anchor read its unmerged local position); **-116.00 m at all 14 probes**, the BTD minimum (raw 0) | flat, verified |

- Neither run shows our BTD heights, so neither says whether the four record fixes matter. Flat at exactly raw 0
  means the BTD's blocks were not decoded.
- Cause (**supported hypothesis**, rerun pending): the BTD was zlib-compressed inside our BA2, and every vanilla BTD
  is stored. The LOD block tables suggest the terrain streamer reads blocks by offset straight from the archive.
  Reruns with stored BTDs are queued (exp2b3, then exp1f).
- Earlier, with the old records and the same compressed archive, World01 registered on Mars (`terrain_B_w01`,
  `terrain_exp1c_mars`) was also flat (-13.94 m at every probe), so the flat result is not caused by the fixes.

## How to read the in-game result (plan, written before the runs)
- exp1d vs exp1c (same BTD, same registration): heights now match (pad A 35, ...) after the runner's offset -> one of
  the three fixes was missing; still planet ground -> the fixes do not matter, look at activation (H2 / H8 in the
  research notes). Caveat (QA): a BTD the engine cannot read (for example a compressed archive entry) gives the same
  picture, so first rule that out with a stored BTD.
- exp2b: Z offset (anchor read - local) near 0 -> Absolute + HNAM 0 gives exact Commonwealth heights; a constant
  non-zero Z offset -> Absolute is still placed relative to something (try `--hnam`); XY offset is a whole number of
  cells -> the merge offset, as on Mars before.
- prid fails -> the load-order byte is not 02; the spawn fallback still gives an offset, but its z comes from where
  the player stands (falls from the COC marker 2 m above ground in exp2b).

## Unknowns
1. Whether any of the four differences matters to the engine (the runs so far were flat at raw 0, see the in-game
   result); first whether a stored (uncompressed) BTD in the BA2 is read at all.
2. The meaning of `HNAM` in Absolute blocks, what Absolute alignment does in game, `XNAM`/`YNAM` on the location, and
   the stale FNAM in 247 vanilla blocks.
3. Mask row order; whether the mask itself or the outer cell ring drives the height blend (section 3).
4. ~~The real load-order byte of the experiment plugin at run time~~: 02 held in the 2026-10-11 runs (`prid` found
   the anchor). Why our persistent anchors read their unmerged position while vanilla's COC marker does not.

## Reproduce

    python scripts/terrain/overlay_records.py exp1d --sf-data <Starfield\Data> --out C:\Modding\staging\terrain_exp1d
    dotnet run --project dotnet/TerrainExp1 -c Release -- <Starfield.esm> C:\Modding\staging\terrain_exp1d
    python scripts/terrain/overlay_records.py check --sf-data <Starfield\Data> --out C:\Modding\staging\terrain_exp1d

    python scripts/terrain/make_exp2.py restage --from C:\Modding\staging\terrain_exp2 --sf-data <Starfield\Data> --out C:\Modding\staging\terrain_exp2b
    dotnet run --project dotnet/TerrainExp2 -c Release -- <Starfield.esm> C:\Modding\staging\terrain_exp2b
    python scripts/terrain/make_exp2.py check --sf-data <Starfield\Data> --out C:\Modding\staging\terrain_exp2b
    python -m unittest tests.test_overlay

`restage` reuses an already staged experiment 2 (its BTD, points and spawn), so no Fallout4.esm is needed;
`make_exp2.py build --fo4 <Fallout4.esm>` now writes the same exp2b form from scratch. `TerrainExp1` without
`exp1_params.json` in the output folder still builds the original three-world experiment 1; `TerrainExp2` still
accepts the old `connections` params. The FNAM / mask / location surveys were scratch scripts (not in the repo).
