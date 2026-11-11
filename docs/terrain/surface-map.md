# 3D surface map, this testing stage (ROADMAP §3 item 1)

Author: Grok, 2026-10-17. Status: **research + go/no-go, offline**. Nothing written into the overlay plugin;
nothing run in game. Claude takes the acceptance screenshot. Labels: **verified** = read from files,
**supported** = hypothesis with evidence, **unresolved** = open.

Owner: "lets task grok to make a 3d view for the surface view in the map view for this stage in testing".
Roadmap acceptance: a screenshot of the surface map opened at Red Rocket showing Commonwealth terrain in 3D
with the Red Rocket marker.

## Short answer

Starfield already has the 3D surface map (May 2024). We do **not** author a separate map mesh. It draws the
**current loading zone**: overlay BTD terrain (and its LOD levels), the planet's procedural ground around the
overlay, and **world object LOD** for structures. Ours would show **Mars** because the overlay is a Mars unique
overlay (`LocTypeOverlay`, parent `SSol_PMars_Surface`, PNDT `MarsPlanetData`, WRLD overlay SNAM 0 / PNAM 4).
An overlay world **can** appear there from our own plugin and locally generated BTD/mask: vanilla unique
overlays do, and core64k is already that kind of overlay in game. What is missing for a *useful* Commonwealth
3D map is the marker chain (#296 after the LCSR tail fix) and Starfield world object LOD (CK generate), not a
new renderer.

## What the surface map draws from

Three layers, different files:

| Layer | Files / records | What the 3D map uses it for |
|---|---|---|
| Overlay terrain | WRLD overlay `BNAM` → SFBK `ANAM` `Data\TERRAIN\<EDID>.btd` (LOD0–4 inside the BTD); overlay mask `textures/terrain/overlaymasks/<edid>.dds` | The authored heightfield of the loading zone. Vanilla overlays match their BTD in the mask interior (**verified** in game on LC172World, journal 11 Oct). |
| Planet surface | PNDT (biome / `MasterWorldspaces`), SFTR / SFPT procedural blocks | Everything around the overlay, and the planet the map is *of*. |
| Structures | `lodsettings/<edid>.lod` (20 bytes) + `meshes/lod/generated/…_lod_0..3.nif` | Distant buildings on the 3D map and in the world past the cell buffer. Bethesda: the 2024 map shows "terrain … trees, rocks, all the structures in the loading zone". |

WRLD `MapData` on Starfield overlays is all zero (**verified**, [architecture.md](architecture.md) §1.2). This is
not FO4's 2D local map. There is no separate "surface map mesh" record group.

World object LOD is **not** the converted FO4 `*_lod.nif` files. Those are ordinary meshes. Starfield world LOD
is the `lodsettings` + `meshes/lod/generated/` pair ([JOURNAL.md](../JOURNAL.md) 11 Oct: every vanilla overlay has
a `.lod`; core64k has none). How the four FO4 LOD kinds (per-object NIF, `.bto`, `.btr`, 16-byte `LODSettings`)
map onto that contract is [fo4-lod-meshes.md](fo4-lod-meshes.md).

## Why ours would show Mars (**verified** records)

Pinned `terrain_core64k` (read-only this session, `fo4land.Plugin`):

- LCTN `FO4Core_CommonwealthLocation` `01000802`: `PNAM` `0001B736` (`SSol_PMars_Surface`), `KWDA` `LocTypeOverlay`
  `002CA99D`, **LCSR 0 / LCID 0**.
- WRLD `FO4Core_Commonwealth` overlay component: `SNAM` 0 (Sol), `PNAM` 4 (Mars), same as LC172World /
  CydoniaCity in [architecture.md](architecture.md).
- `FO4TerrainCore_Mars.esm` overrides PNDT `MarsPlanetData` `0003F59A`: 11 `CNAM` entries (10 vanilla + ours);
  last entry latitude 0.3, longitude −1.2, WRLD `01000803`.
- Staged `Data\`: BTD `Terrain\FO4Core_Commonwealth.btd` 103,172,485 B; mask
  `textures\terrain\overlaymasks\fo4core_commonwealth.dds`; **no** `lodsettings\` directory; **0** files under
  `meshes\lod\generated\`; **315** files under `meshes\fo4core\lod\` (FO4 LOD NIFs converted as normal meshes).

The overlay is parented to the Mars surface location and registered on Mars, so the map's planet is Mars. The
6.4 km Commonwealth BTD is a unique overlay on that planet, like LC172, not its own world.

## Can an overlay appear from our plugin and local files?

**Yes, as the loading-zone 3D view** (**supported**): unique overlays are activated by PNDT `CNAM`; activation
merges overlay cells into the planet ([overlay-records.md](overlay-records.md), binding findings). The owner
already walked core64k in game (playtest row 25), so the overlay *is* the current exterior loading zone. Vanilla
cities (New Atlantis, Cydonia) show their overlay in the 3D surface map; they are the same record family we
Duplicate (LC172).

**Not as a replacement planet globe.** Unparenting from Mars / making a custom planet is Phase C / architecture
option C, not this testing stage.

What still would not look like the Commonwealth on that map today:

1. **No MapMarker / LCSR** — no Red Rocket icon, no fast travel target ([map-markers.md](map-markers.md)). #296
   restores one marker; Codex QA: the writer emits LCSR tail `0` instead of template `0xFFFFFFFF`. Fix that
   before Claude's scratch overlay.
2. **No Starfield world object LOD** — 3D map and distant view show BTD terrain without buildings. Playtest row
   24 (nothingness past loaded cells) is the in-world version of the same gap. FO4 `meshes/fo4core/lod/*.nif` do
   not fill it.
3. **Edge blend** — overlay mask 255 on the outer cell ring blends to Mars procedural ground. The 3D map will
   show Mars around the Commonwealth footprint. That is expected for a Mars overlay.

Whether the map camera actually samples overlay BTD vs only the planet SFTR is **unresolved** until Claude's
screenshot. In-world probes already read Commonwealth BTD heights, so **supported** that the loading-zone map
uses the same merge.

## Plan

### GO (this testing stage)

1. This note on #32 (done with the PR).
2. LCSR tail fix on #296, then Claude scratch overlay: `coc` Red Rocket, open the surface map, screenshot.
   Expectation: overlay-shaped terrain (Commonwealth heights) in the 3D view, Mars beyond the mask, one marker
   at the station if #296 is in the build.
   Done offline (Claude-cloud, 2026-10-17): the LCSR tail fix is on #296, and the stacked PR adds Sanctuary,
   Vault 111 and Concord beside Red Rocket ([map-markers.md](map-markers.md), "Commonwealth markers"). Both wait
   for a core64c rebuild on the PC and the screenshot.
3. Object-LOD trial on a **tiny** overlay via CK `-MockWorldSpaceLOD` (Claude window), then the same for
   `FO4Core_Commonwealth` if the tiny overlay's 3D map shows structures. Grok hands patches; Claude owns the
   writer/staging/game. That is ROADMAP §3 item 3, not a build in this PR.

### NOT go

- A custom 3D map renderer, FO4 `.bto` port, or raising `uExterior Cell Buffer`.
- Unparenting the location from `SSol_PMars_Surface` or replacing the unique overlay with a landing overlay / new
  planet.
- Shipping the 315 `meshes/fo4core/lod` NIFs as if they were `meshes/lod/generated` world LOD.
- Building on #296 before the LCSR `0xFFFFFFFF` fix.

## Acceptance

Claude: from a build that has the #296 marker (fixed LCSR) and, for structures, CK object LOD, open the surface
map at Red Rocket. Pass = Commonwealth terrain in 3D plus the Red Rocket marker. Offline `check` cannot see the
map camera.
