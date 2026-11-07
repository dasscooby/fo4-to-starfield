# Map markers: overlay location chain (playtest row 7)

Author: Grok, 2026-10-17. Status: **implemented, offline**. TerrainOverlays restores one MapMarker + LCSR/LCID per
overlay (`grok/map-marker-restore`). Nothing deployed; nothing run in game. Labels as in the other terrain docs: **verified** = read from files, **supported** = hypothesis with
evidence, **unresolved** = open. Owner playtest row 7 (fast travel to The Frontier from the overlay map hung). Plan
section 5 of [commonwealth-build-plan.md](commonwealth-build-plan.md): "FO4 map markers -> LCTN/REFR".

## What hangs today

The overlay has a Location (`FO4Core_CommonwealthLocation`) with `LocTypeOverlay` and parent `SSol_PMars_Surface`, so
it shows as a Mars overlay. It has **none** of the map-marker / fast-travel records a vanilla unique overlay or
landing overlay carries.

Pinned `FO4TerrainCore.esm` (`terrain_core64k`, read-only):

- LCTN `01000802` `FO4Core_CommonwealthLocation`: `LCSR` and `LCID` present with 0-byte payloads, `FULL` "Commonwealth 00 (FO4
  terrain)", `KWDA` `002CA99D` (`LocTypeOverlay`), `PNAM` `0001B736` (`SSol_PMars_Surface`).
- WRLD `FO4Core_Commonwealth` `XLCN` that location (already documented in [overlay-records.md](overlay-records.md) §2).
- 654,600 `REFR`: **0** carry `XMRK`, **0** `NAME` a MapMarker STAT (`00000010` / long / short / medium-long).
- One `COCMarkerHeading` `FO4Core_RedRocketSpawnMarker` at overlay-local (−989.257, 1146.514, 107.143).

The writer **does** Duplicate vanilla `LC172WorldLocation` (`3807BE`), then
`MasterSpecialReferences.Clear()` and `MasterInitiallyDisabledReferences.Clear()`
(`dotnet/TerrainOverlays/Program.cs`). Mutagen 0.55 names those lists for `LCSR` and `LCID`. Overlay-records.md
already noted the two `LCSR` statics and `LCID` were dropped; that drop is the map-marker chain.

## Starfield has no MAPM group (**verified**, Starfield.esm 1.16.244)

176 top groups. `LCRT` and `LCTN` exist. There is no `MAPM` (or `MAPR`) group.

Map markers are **placed references**: `REFR` whose `NAME` is STAT `MapMarker` `00000010` (also
`MapMarker_LongRange` `00254244`, `MapMarker_ShortRange` `00254245`, `MapMarker_MediumLongRange` `0031FB3E`).

A typical unique-overlay marker (LC172 persistent `REFR` `003E5E12`):

| Field | Value |
|---|---|
| flags | `00000C00` (Persistent `0x400` + Initially Disabled `0x800`) |
| `NAME` | `00000010` MapMarker |
| `XMRK` | empty payload |
| `FNAM` | `1b000000` (u32 `0x1B`) |
| `FULL` | null lstring |
| `TNAM` | `1700` (u16 `0x17` = 23) |
| `UNAM` | `00000000` |
| `DATA` | (37.4, 57.2, 7.6) m in `LC172World` |
| `XLKR` | `00000000 -> 0028DC51` |

`TNAM` is the marker type. What each type id draws, and the `FNAM` bits, are **unresolved**.

## LCTN links the marker through LCSR + LCID (**verified**)

`LCSR` is a repeated 20-byte (5 × u32) stride:

```
LCRT formid, REFR formid, WRLD formid, grid (two i16, Y then X), 0xFFFFFFFF
```

The 4th dword is the marker's cell as two i16, Y then X (Mutagen `LocationCellStaticReference.Grid`). The 5th is
Mutagen `Unknown = -1` (`0xFFFFFFFF` on every vanilla MapMarkerRefType row). The constructor default is 0; the
writer sets Grid from `spawn_cell` and Unknown to -1.

`LCID` is often the map-marker `REFR`. Mutagen: `MasterSpecialReferences` = `LCSR`,
`MasterInitiallyDisabledReferences` = `LCID`.

Helpers and the LC172 / landing fixtures live in `src/fo4sf/map_markers.py` (synthetic tests,
`tests/test_map_markers.py`).

### Unique overlay template: LC172WorldLocation `003807BE`

`KWDA` `LocTypeOverlay` `002CA99D`, `PNAM` `SSol_PMars_Surface` `0001B736`. Two `LCSR` entries (40 bytes) and
`LCID` `003E5E12`:

| LCRT | REFR | WRLD |
|---|---|---|
| `Landmark_SnowGlobe_RefType` `00009A42` | `00009A32` | `LC172World` `0002DF8C` |
| `MapMarkerRefType` `0002271F` | MapMarker `003E5E12` | `LC172World` `0002DF8C` |

WRLD `LC172World` `0002DF8C` `XLCN` this location. The snow-globe `LCSR` is LC172 flavour, not a map marker.

### Landing overlay: LandingOverlay01Location `003807CF`

Three `LCSR` (60 bytes). Same 5-dword stride. The extra two bind the **ship pad**, not a second map icon:

| LCRT | REFR | WRLD |
|---|---|---|
| `MapMarkerRefType` `0002271F` | `003A866E` | `LandingOverlay01` `001187EA` |
| `ShipLandingMarkerRefType` `00009105` | pad `00093DC9` | `001187EA` |
| `ShipLandingMarkerRefType_Large` `00009102` | same pad `00093DC9` | `001187EA` |

The pad `REFR` also carries `XLKR` `LandingZoneTriggerKeyword` `00267F4D` → trigger and
`LinkShipLandingOverlayMapMarker` `003A866F` → the map-marker `REFR`. Marker `FNAM` `0x33`, `TNAM` `0x2D`, flags
`00000400` (persistent only). DefaultSpaceshipLandingOverlayLocation and PCMGenericLandingOverlayLocation use the
same three-`LCSR` shape.

Related keywords (named in Starfield.esm, not required for the first writer change): `DMP_ShipLandingMarker`
`000D40EA`, `LandingZoneTriggerKeyword` `00267F4D`.

### Unique cities

`NewAtlantis` `0001251B` is a large unique overlay (hundreds of cells, many persistent MapMarker STAT). City location
editor ids are `CityNewAtlantisLocation` `0001295A` and `CityAkilaCityLocation` `00010DFB`. A 64-cell Commonwealth
overlay is the LC172 unique-overlay family, not a 3 × 3 PCM landing overlay.

## Cause of the missing chain (**verified** records)

`TerrainOverlays` (and the exp1 / exp2 writers) Duplicate `LC172WorldLocation` then clear both special-ref lists.
That throws away LC172's `MapMarkerRefType` `LCSR` and `LCID`. The Duplicate also does not copy LC172's persistent
MapMarker `REFR` into our world (cells are rebuilt empty, then objects). The pinned plugin matches: empty `LCSR` /
`LCID`, no MapMarker `REFR`.

## Playtest row 7 (**supported hypothesis**)

Fast travel to The Frontier from the overlay map started a load that never finished (bridge log rotated, game still
running). The overlay is a Mars `LocTypeOverlay` with no map-marker / ship-landing chain.

Two things can be true together:

1. Missing MapMarker + `LCSR` is why the overlay does not behave like LC172 or a landing site on the planet map
   (**supported**; records match).
2. The hang itself may be "fast travel *out of* the overlay *into a ship*" (`ConstellationFrontierShipLocation`), a
   different engine path than "show an icon on the overlay" (**unresolved** until an in-game overlay with the restored
   marker).

Restoring LC172's one MapMarker may only add a local icon. That is still the first writer change: it makes our
location match the template we already Duplicate.

## FO4 map markers

`Fallout4.esm` is not on this machine. Byte-level FO4 `XMRK` is **unresolved**.

`scripts/terrain/make_cw_overlays.py` already names FO4 landmark refs (Commonwealth, FO4 units): Red Rocket building
`0x000211C0`, Sanctuary map marker `0x00072A48`, Vault 111 `0x0009F272`, Concord `0x00082138`. `fo4land.parse_ref`
reads `NAME` / `DATA` / `XSCL` only, so a later promotion class needs `XMRK` / `TNAM` / `FNAM` on the FO4 `REFR`.
Core `selected.json` does not list a MapMarker type (FO4 markers are not a converted STAT class).

## Plan

### GO (this PR, writer; Claude scratch overlay for in-game)

One persistent MapMarker `REFR` in the Commonwealth overlay, written **after** doors/lights so reserved object FormIDs
stay:

- Duplicate LC172's persistent MapMarker `REFR` `003E5E12` (keeps empty `XMRK`, `FNAM` `0x1B`, `TNAM` `0x17`), `NAME`
  STAT `00000010`.
- Position: the Red Rocket COC spawn, overlay-local metres; persistent in the world's `TopCell` (same list as the
  XMarker anchor). `FULL` "Red Rocket". LC172's `XLKR` is cleared.
- After the existing `MasterSpecialReferences.Clear()` (LC172's snow-globe `LCSR` and LC172's own marker form id stay
  dropped; those refs are not in our world), append one `LCSR` `MapMarkerRefType` → that `REFR` → our WRLD, and `LCID`
  that `REFR`. `formids.json` `"map_markers"` maps world editor id → REFR id.

Do **not** stamp a PCM 3 × 3 landing overlay over the unique 64-cell Commonwealth overlay. Do **not** add ship pads
or `LinkShipLandingOverlayMapMarker` in this first change.

### NOT go yet

- Full FO4 map-marker promotion class (needs `Fallout4.esm` `XMRK`).
- Ship landing pads / `ShipLandingMarkerRefType` `LCSR`.
- Replacing the unique overlay with a landing overlay.

### If the Frontier hang remains after the first overlay

Second PR: add the landing-overlay `XLKR` (`LinkShipLandingOverlayMapMarker` from a pad to the marker) **without**
swapping the world type. Still no PCM stamp. Claude runs the game.

## Commonwealth markers (Claude-cloud, 2026-10-17, stacked on #296)

Status: **offline, verified by synthetic tests only**; the writer change is not built in the cloud (no .NET there) and
nothing has run in game.

`make_core64c.py stage` now writes the overlay's `map_markers` into `overlays_params.json`
(`fo4sf.map_markers.overlay_markers`), and `TerrainOverlays` writes one MapMarker REFR, one `LCSR` MapMarkerRefType row
and one `LCID` entry per entry, in this order, after every other record:

| Tag | Map name | FO4 source | Position (local m) |
|---|---|---|---|
| RedRocket | Red Rocket Truck Stop | building `000211C0` | the COC arrival (`FO4Core_RedRocketSpawnMarker`), as #296 |
| Sanctuary | Sanctuary Hills | map marker `00072A48` | FO4 position / 70, z = BTD ground |
| Vault111 | Vault 111 | map marker `0009F272` | FO4 position / 70, z = BTD ground |
| Concord | Concord | map marker `00082138` | FO4 position / 70, z = BTD ground |

FO4 positions are the ones `make_cw_overlays.py` already uses as probe landmarks (read from Fallout4.esm). A marker less
than 200 m inside the overlay stops the stage. Without `map_markers` (core64 itself, exp builds) the writer keeps #296's
single marker at the COC. The first marker keeps #296's EditorID and `formids.json` `map_markers`; all of them are in
`formids.json` `map_marker_refs` {world: {tag: id}}.

`make_core64c.py check` judges them (`map_marker_problems`): MapMarker NAME, XMRK, persistent, position, one `LCSR` row per
marker with tail `0xFFFFFFFF`, no `LCID` (see the correction below), ids after every other record. It also stops counting the markers against the
door rules (doors after everything, the persistent cell holds anchor + door markers) and compares core64's Location
without its `LCSR` / `LCID`: before this, a door build with #296's marker would have failed `check`.

The FO4 map names, the `FNAM` bits (fast travel, discovered) and the `TNAM` icon type stay LC172's (`0x1B`, `0x17`):
whether the icons show undiscovered, and which icon they draw, is **unresolved** until the in-game check.

### Correction (Claude-cloud, 2026-10-18): the markers were written initially disabled

In game on FO4TerrainCore fdd3f0a5 (markers 0A7759 to 0A775C), **no icon showed on the map** (owner). The writer
Duplicated LC172's 003E5E12 with its flags 0xC00, which include Initially Disabled 0x800. LC172's quest enables that marker.
Ours have nothing to enable them, and the writer also listed them in `LCID` (the Location's initially disabled
references). The landing-overlay marker 003A866E is 0x400 (persistent only). The writer now writes 0x400 and no `LCID`,
and `check` fails a marker that is initially disabled or listed in `LCID`. **Supported hypothesis** until the
in-game confirmation (`prid 030A7759`, `enable`, then open the map; `03` is FO4TerrainCore's load-order slot).

## Every Commonwealth marker (Claude-cloud, 2026-10-19, offline only)

Status: **built and tested on synthetic plugins; the PC export ran (2026-10-19)**: 310 Commonwealth markers, all
named; 307 left after the fixed four's own records, all inside the overlay. Nothing has run in game.

1. On the PC, `dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-mapmarkers <out.json>` lists
   every placed object of the Commonwealth worldspace that carries map-marker data (`MapMarkersExport.cs`):
   its FormID, editor id, name, FO4 position and whether it is persistent, in FormID order. The name is the marker's
   own FULL, which Mutagen reads from the Strings files next to the localized plugin, as `export-names` does. The
   output is derived game data and stays outside the repository.
2. `make_core64c.py stage ... --fo4-map-markers <out.json>` adds every named marker that lies more than 200 m inside
   the overlay (`map_markers.load_fo4_markers`, `extra_markers`, FO4 position / 70, z = BTD ground). The fixed four
   come first, so their FormIDs stay. The others follow in FO4 FormID order, tagged `M<FO4 id>`. Markers left out
   (no name, one of the fixed four, no finite position, outside the overlay, or within 100 m of a fixed marker of the
   same name: FO4's Red Rocket Truck Stop marker 024FBE, since the core's Red Rocket sits on the COC arrival) go to `map_markers_left_out.json` with
   their reason. `check` judges every marker the same way as the four.
3. `dotnet/MapMarkers` splits the core's markers into quests of at most 20 (`FO4SF_MapMarkersQuest`,
   `FO4SF_MapMarkersQuest2`, ...: 0x800, 0x801, ...; at most 100 until 2026-10-31, "Reload"). Papyrus arrays made in
   script hold at most 128 entries; whether a plugin-filled property may hold more is **unresolved**, so no quest goes
   near that limit. A quest's `MaxMoves` is the script's 40, twice its marker count, so one session can place them all. `check` matches the
   quests, in FormID order, against the core.

Every new marker keeps LC172's `FNAM` 0x1B and `TNAM` 0x17, so they all draw one icon type; FO4's own marker types
are not mapped yet. The export carries each FO4 marker's type (`type`, `type_id`) for that later table.

Marker data in the two games (Claude-cloud, 2026-10-19). Mutagen 0.55.0-alpha.67, read by reflection on
`PlacedObjectMapMarker`:
- Fallout 4: `Flags` (Visible 1, CanTravelTo 2, ShowAllIsHidden 4, UseLocationName 8), `Name`, `Type` (an enum of
  66 FO4 icons: Cave 0, City 1, DiamondCity 2, MetroStation 6, Vault 15, ... Minutemen 57, ...), then one unknown
  byte. This is **verified** as Mutagen's layout. The byte widths on disk are **unresolved** (no `Fallout4.esm` here;
  the synthetic test writes `FNAM` 1 byte and `TNAM` 2 bytes).
- Starfield: the same `Flags`, plus `Name`, `Type` as a bare signed byte (no enum), one unknown byte, `VNAM` (u16),
  `UNAM` (a string) and `VISI` (a byte). LC172's bytes above agree: `FNAM` is u32, and `TNAM` `1700` is type 0x17
  plus the unknown 0x00 (**verified**).
- The Interiors thread reports that no Starfield marker type matches FO4's Vault, Metro or Diamond City icons. That
  is **unresolved**: Mutagen names no Starfield types, so checking it takes a census of `TNAM` values in
  `Starfield.esm` or the in-game check. Either way, a lossy FO4-to-Starfield type table is the likely shape. This takes a new core build, so it waits for the current phase's tests.

## Acceptance

Claude: scratch overlay from this writer, `coc` Red Rocket, open the planet / overlay map, confirm one icon at the
station, then retry Frontier fast travel. Offline `check` cannot see a hang.

## Markers in the merged world (2026-10-19, supported hypothesis)

With #356 the markers are enabled, yet v6 showed no icon (owner, 19 Oct). The markers are **persistent** references of
the overlay world, and a persistent reference of that world stays at its **local** position in the base world
(`0x02000803`: door probe (a), 16 Oct, docs/JOURNAL.md), while the player walks in a world made at run time that places
the core's records at local + the merge offset (`vmad_patch.MERGE_MEASURED`, (-1200, -2700)). The mission's actors hit
the same wall (#353 moves them). So the map of the world the player is in has no marker in it.

`FO4SFMapMarkers.esm` (`dotnet/MapMarkers`, `scripts/mapmarkers/make_map_markers.py stage --core <core> --out <dir>`)
is one start-game-enabled quest carrying `FO4SF_MapMarkers`: every 2 s, with the player outdoors inside the overlay's
merged extent (x -4400..2000, y -5900..500), each marker that is not at its merged spot in the player's world is
enabled and moved there (`MoveTo` onto the player with the difference as the offset, the form the door script and
the mission use), at most 40 moves per session, each logged to `fo4sf_map.0.log`. The plugin names the core's marker
REFRs by FormID, so it is rebuilt with every core build. **Verified in game** (owner, 2026-10-22, core dc751664,
plugin 46d4ca26, `fo4sf_map.0.log`): the quest started 55 s into the session, moved all four markers 15 s later
(`before=` FLT_MAX is the expected other-world reading, not a failed read; `d=` matched the player's distance), and
the four icons drew on the surface map after the owner left the area and came back. Why not at once is
**unresolved** (the map may hold its marker list until the area reloads). Still unverified: the
extent check cannot tell another world with the same coordinates apart (as the mission).

Install: `scripts/game/map_markers_install.py install --dir <staged> --starfield <game>` (game closed). It keeps its
own record, `Data\FO4SFMapMarkers.install.json`, beside exp_install's one experiment record (the core set), the way
`bridge_install.py` does, and packs the .pex into `FO4SFMapMarkers - Main.ba2` (this install reads no loose scripts).
It refuses unless the core is an active Plugins.txt line and its file in Data has the sha256 the stage pinned in
`core.json` (the plugin names that core build's records by FormID; a stage from before the pin is staged again).
`order` repeats those checks before it writes, and cycle.ps1 stops with exit 7 when it refuses. After the save loads,
cycle.ps1 runs `active` (read-only) and stops with exit 8 if the save's load order turned the plugin off. Its `order` command moves its line to the end; cycle.ps1
runs it before the bridge's, so the experiment's and FO4Port's load indexes stay as they were. Before a core swap,
`uninstall` it (its only master leaves Plugins.txt for the length of the swap, and exp_install refuses missing
masters), then install it again after; and keep it out of runner runs on a commit older than this installer.

### Overrides (Claude-cloud, 2026-10-22): the marker's own name, a lifted arrival

The owner's play test (core dc751664, plugin 46d4ca26; Install's Ctrl+Alt+K captures) found two defects once the
markers drew. (1) Every icon read "COMMONWEALTH 00 (FO4 TERRAIN)", the cell's location, not the marker's name:
the core copies LC172's marker flags `FNAM 0x1B`, which include UseLocationName (`0x8`). (2) Fast travel to
Concord put the player half in the ground: the marker sits at the terrain height `make_core64c` sampled (86.93 m),
and the arrival there has ground above it; the Red Rocket arrival, 1.9 m above its marker's landing, dropped
without harm. FO4's own marker heights are no reference (its Sanctuary marker floats 6.9 m up).

Fix, in `FO4SFMapMarkers.esm` rather than a core rebuild: `dotnet/MapMarkers build` adds an override of every core
marker REFR (the same FormKeys, so Starfield.esm joins the core as a master): flags without UseLocationName and
with Visible, enabled, the position lifted `--z-lift` metres (default 2.5, the smallest round figure above the
proven 1.9 m drop with a margin for Concord; **unresolved** until the owner's next test), name and base as the
core wrote them. The quest's `LocalZ` holds the lifted height, so the mover places the marker where the override
says; a save made before a lifted build keeps the markers at the old height (moved references outlive their
records), so the script also re-moves a marker whose height is off by more than `ZTolerance` (0.05 m), and the
build takes `--z-lift` in steps of 0.1 m only, so every change between builds reaches a saved game while a landed
move (within 0.01 m) stays. The move budget (`MaxMoves`) is saved state too, so the script starts it over when a
build changes the markers' count or height: a save whose budget the first placement spent still takes a later
lift. `check` reads the overrides back (`override <FormKey> "<name>" flags 13 at (...)`; 03 for a marker the
star map list leaves out, see Star map below) and fails one that still
uses the location name, is Initially Disabled, is at another height, or overrides anything that is not a core
marker (the override's parents arrive as copies of the worldspace and its persistent cell; the build prunes
them to the markers). Those two copies are overrides too, and this plugin loads after the core, so `check` also
fails when either differs from the core's record: a core rebuilt after the stage (a changed world flag, as the
border fix of 2026-10-22 makes) needs a new stage, or the plugin would put the old record back. For the border
settling test (Interiors, 2026-10-22) `--world nosmall|city` takes that WRLD copy from `dotnet/BorderProbe`'s
variant instead (nosmall: SmallWorld cleared; city: SmallWorld cleared and `HNAM` 5; `control`, the default, the
core's record), with the marker overrides unchanged, so the variant is the last `WRLD` override whatever the load
order; `check` wants the same `--world` and fails the copy under any other. The icon type `TNAM 0x17` is "NASA" in xEdit's SF1
definitions (corrected 2026-10-28; see Star map below); how each type draws in game is still **unresolved**.

Console check (no plugin needed): `prid 030A775A`, `getpos x`, `getpos y`: about (-1154, 1260) is the local spot,
about (-2354, -1440) the merged one. `prid 030A775A` then `moveto player` moves the Sanctuary marker onto the player by
hand, then the map shows whether a moved marker draws.

**Can a writer fix exist? (`dotnet/MergeProbe`, offline-checked, not run in game).** Two writer-side candidates
failed in game: the vanilla persistent-cell shape (fix A, cave_fixA_1015, refuted: the door still read local) and
WRLD OFST / CLSZ (fix E, cave_ofst_1015, FAIL NOLOAD only, which does not isolate an unmerged position). Neither
rules out every writer fix. `MergeProbe build <Starfield.esm> <out>` writes `FO4SFMergeProbe.esm`: one persistent XMarker
`FO4SF_MergeProbeMarker` (0x800) in an override of vanilla LC172World's persistent cell, 3 m east of the COC marker
0010238E, which reads merged in game (offset -500, -2300, -3.62). In game, with only this plugin added:
`coc LC172Ext01`, then `prid <its load index>000800`, `getpos x`, `getpos y`, and in the same session `prid 0010238E`,
`getpos x`, `getpos y` as the vanilla control (it must read merged, or the session proves nothing). One read is scoped
to that world, build, load order, save and session. A merged probe read says a plugin's persistent reference can
merge there, so the cause is likely in our WRLD / LCTN records (diff them next). A local read with a merged control
says persistent references this plugin adds did not merge in that setup; it supports keeping the runtime moves (the
door script, #353, this quest) as the design, but does not prove no record shape can merge.

### More location markers without a core rebuild (Claude-cloud, 2026-10-23, offline)

The owner asked for "more location markers" after the section A play (2026-10-23). The core route above
(`make_core64c.py stage --fo4-map-markers`) needs a new core, and v6i closes this phase, so the markers plugin now adds
them itself:

1. `make_map_markers.py stage ... --fo4-map-markers <export.json> --core-stage <folder>` picks the markers the core route
   would pick (`load_fo4_markers`, `extra_markers`), with the BTD ground and the bounds of the folder that staged the core.
   Its copy of the core must be `--core` byte for byte, so the heights and the markers belong to that build. A core that
   already carries them (tags `M<FO4 id>` among its params' markers) stops the stage. The picked markers go to
   `extra_markers.json` and the rest to `map_markers_left_out.json`, each with its reason.
2. `extra_markers` now also leaves out a marker within 100 m of an earlier kept marker with the same name. FO4's
   USS Constitution has two markers 4 m apart where the ship comes to rest (1F2637, 074BE0). Same-named places farther
   apart stay (FO4's two "Cave" markers, about 390 m apart).
3. `dotnet/MapMarkers build --extra <json>` writes each as a REFR of the plugin (0x900, 0x901, ...). Each is a copy of the
   core's first marker (LC172's template, as the core writes its own), in the WRLD copy's persistent cell at its local
   spot, lifted `--z-lift`, with its own name and the overrides' flags. Each also gets one `MapMarkerRefType` `LCSR` row
   in an override of the core's Location, as TerrainOverlays writes the core's four. The quests list them after the
   core's markers, at most 100 per quest (20 since 2026-10-31, "Reload"). `check --extra` fails a plugin with any other REFR of its own
   (with `--reload`, but for the stop's two). It also fails a
   Location override that differs from the core's in anything but those rows, the same stale-stage rule as the WRLD copy.
   Without `--extra` the plugin is byte for byte as before: built here from the v6i core, it has sha256 `af56df9c`, the
   installed one.

**Verified offline** (cloud, 2026-10-23) against the installed v6i core (sha256 `dc751664`), its stage folder's BTD and
`overlays_params.json` (`terrain_core64v6i_l125_mission_wfc11_plainshader`), and the PC's export (`cw_markers.json`,
310 markers). All of them were read from the PC without running anything there.
- The fixed four's heights in the params match that BTD (Red Rocket sits on the COC arrival, as written), so it is the
  core's own ground.
- 305 markers are kept and 5 left out: the fixed three, FO4's Red Rocket next to the core's, and one USS Constitution.
- The plugin is 73,904 bytes, sha256 `d7b17206`. It has 4 quests (100, 100, 100, 9 markers), 309 LCSR rows, and all
  checks pass.
- The Papyrus compile and the stage itself run on the PC.

**Unresolved until the owner's play:**
- whether all 309 icons draw, and whether they draw only after a revisit like the four;
- whether a fast travel arrival at the ground plus 2.5 m clears the converted buildings, since FO4's markers stand at
  the place and some sit by a wall or under a roof;
- whether 309 rows on one Location change anything about the four.

Some FO4 markers belong to quests and show only during them in FO4, such as "Waypoint Echo" and the USS Constitution's
resting place. Here they show from the start. **Known risk, larger now:** the mover cannot tell another world with the
same coordinates apart (above). In such a world it would pull up to 100 markers per quest there, and the move budget,
200 per quest per build, would run out after one trip there and back.

### How a vanilla world lands a ship (survey, 2026-10-23)

This is for the owner's "temp ship landing spot". The source is `SfInspect landing`, run on the PC read-only against
Starfield.esm 1.16.244 (queue folder `C:\Modding\scratch\landing_survey`, commit 69a3b4ce). It is **verified** as
records; nothing here has run in game.

| Part | LandingOverlay01 (`1187EA`) | DefaultSpaceshipLandingOverlay (`2A5AE3`) | PCMShipLanding01 (`233DA3`) |
|---|---|---|---|
| pad | `093DC9` ShipLandingMarker_80m_Large (`007145`), persistent `0x400`, has a script | `2C66E6`, the same | `0314F2`, the same base, `0x10400`, no script, LocationRefTypes `076E88` |
| pad links | LandingZoneTriggerKeyword to the trigger; LinkShipLandingOverlayMapMarker to the marker | the same | LandingZoneTriggerKeyword to the trigger only |
| trigger | `093DCA` landingZoneTrigger (`267F4C`), a primitive, temporary in cell (0, 0), on the pad | `267F51`, the same | `0314F5`, the same |
| map marker | `3A866E` MapMarker, persistent, Radius 100, flags 0x33, type 45, "Landing Area" | `3A8679`, the same | `0314F7` MapMarker_ShortRange, `0xC00` (initially disabled, in LCID), Radius 50, flags 0, type 45 |
| heading | `3A8670` XMarkerHeading, persistent, linked from the marker (no keyword), about 47 m from the pad | `3A867A`, the same, about 50 m from the pad | `0314F8`, the same link |
| Location LCSR | MapMarkerRefType to the marker; ShipLandingMarkerRefType and ShipLandingMarkerRefType_Large to the pad | the same | the same three, plus random-encounter rows |

New Atlantis does the same per site. Its spaceport location lists marker `023602` (NewAtlantisMapMarkerSpaceport, flags
0x13, type 4, linked to a heading `023604`) and the pad `2CFDE8` (ShipLandingMarkerVertical_80m_Large) under
ShipLandingMarkerRefType and its _Large twin. The player's pad `023605` NewAtlantisShipLandingMarker carries a script
and links to its shield animation.

So a landing spot is four references: a pad with its script, a landing-zone trigger on it, a map marker linked to a
heading, and three LCSR rows on the Location. Our Location has none of the ship rows today (the core writes only
MapMarkerRefType), which fits the owner's report that the ship and the arrival "get buggy".

Two later runs at commits e3c470e5 and 1d59b368 (`landingoverlay01_scripts.txt`, `landingoverlay01_primitive.txt`) add
**verified** detail:
- LandingOverlay01's pad carries the script `LandingPadBlastShields` with no properties. PCMShipLanding01's pad carries
  none.
- The trigger's primitive is a Box with bounds 81.6183, 81.53047, 29.697622, color A 0 R 204 G 76 B 51, and unknown
  0.3. It sits 8.03 m above the pad, with the pad's rotation.
- The pad and the marker are `IsLinkedRefTransient`; the trigger and the heading are not.

### A temporary landing spot (Claude-cloud, 2026-10-23, offline)

The owner asked for "a temp ship landing spot". The markers plugin now carries one: `make_map_markers.py stage --landing
<x> <y> --core-stage <folder>`, with the pad at getpos (x, y) in the merged frame.
- **Layout.** `fo4sf.map_markers.landing_spot` moves LandingOverlay01's four references by one offset, so the pad lands
  at the spot and the rest keeps the vanilla layout and rotations. The pad takes the BTD ground at its spot, and the
  trigger and the marker keep their vanilla height above it. The heading stands on its own ground plus the markers'
  lift (2.5 m), in case it is the fast-travel arrival (**hypothesis**).
- **Records.** `dotnet/MapMarkers --landing` writes the four as REFRs of the plugin at 0x8F0..0x8F3, persistent in the
  world copy's persistent cell:
  - the pad (ShipLandingMarker_80m_Large `007145`, without the blast-shield script, as PCMShipLanding01's), linked by
    LandingZoneTriggerKeyword to the trigger and by LinkShipLandingOverlayMapMarker to the marker;
  - the trigger (`267F4C`, the vanilla primitive), persistent here, while LandingOverlay01's is temporary, so the quests
    move it with the rest;
  - the marker, a copy of the core's first marker with flags 0x33, type 45, Radius 100 and the name "Commonwealth
    Landing Area", linked to the heading;
  - the heading (`000034`).
- **Rows and quests.** The Location override gets the three LandingOverlay01 rows, after `--extra`'s. The quests list
  the four after the markers, so the mover places them in the merged world like the markers.
- **Mover.** It now keeps each reference's own rotation (`MoveTo` without match-rotation), so the pad keeps its facing
  instead of taking the player's. That makes no difference to the markers.
- **Check.** `check --landing` requires exactly the four records the build makes (so a core rebuilt since the stage
  fails too) and the three rows.
- **The spot.** The ground around Red Rocket inside FO4's border is cluttered everywhere (a 90 m square search within
  1.5 km; the best candidate 470 m north-east has trees, shrubs and rocks within 15 m). Just past FO4's north border,
  1.09 km north of Red Rocket, the pad at local (-759, 2207), getpos (-1959, -493), has a 2.2 m rise over a 50 m square
  and no object within 270 m. The owner can move it with a snapshot at a spot they prefer.
- **Cloud build** against the installed v6i core (core sha256 `dc751664`), with the 305 extra markers: 74,695 bytes,
  sha256 `79eb6a93…`, 4 quests, 312 LCSR rows, check passes.
- **Unverified until a play test:** whether the ship lands at this pad when the player lands at the Commonwealth;
  whether the planet map offers "Commonwealth Landing Area" as a landing target; whether the trigger works when
  persistent; and whether landing on uneven ground clips the ship's gear.

## BACUP's FO4 to Starfield world writer (Claude-cloud, 2026-10-19, read only)

[BACUP](https://github.com/Bryant-21/bacup) (GPL-3) was read at commit `cfa3d0d` (2026-10-17). Nothing was run, and
no code is copied here. Its `fo4:starfield` pair has no evidence of loading in game; its own test is a synthetic
2x2-cell slice (`bacup_lib/tests/test_fo4_starfield_vertical_slice.py`). Findings below are **verified** against its
source:
- **Its own world, no overlay.** `native/conversion/src/phase/starfield_cells.rs` writes the FO4 worldspace as a new
  `WRLD`: a world persistent cell plus a re-latticed 100 m exterior grid (FO4's 4096-unit cells do not divide into
  100 m, so refs are bucketed by position and `XCLC` is rebuilt). It notes `Starfield.esm` measurements: block =
  grid div 32, sub-block = grid div 8, label `[y, x]` (its claim, not rechecked here).
- **Persistent refs keep their own position.** The persistent cell "never re-lattices; its children keep their
  (rescaled) positions verbatim" (FO4 position / 69.99125, our 70). No world is merged into another, so it never
  meets our case: an overlay whose runtime world places records at local + (-1200, -2700). It has no answer for the
  merge probe's question.
- **No map markers and no locations.** `embedded/translation_maps/fo4_to_starfield.yaml` drops `XMRK`, `FNAM`,
  `TNAM` and `XLOC` from every `REFR` ("codec differs between games") and drops `WRLD` `XLCN`, `TNAM`, `UNAM`,
  `ICON`. `LCTN` is not translated. Its marker-type code (`fullscreen_map_markers.py`) is for FO76 to FO4 and draws
  icons in a map mod, not in Starfield.
- **Scale.** 69.99125 FO4 units per metre against our 70 is a 0.0125 % difference: about 0.4 m across the core's
  6.4 km. Not worth a change on its own; **unresolved** which figure is exact.

Nothing to borrow for markers, locations or the merge question. Its standalone-world approach would sidestep the
offset entirely, but it is a different design from our overlay and is a decision for the world threads.

**Decided by the owner, 2026-10-19 (22:04Z, in the next-phase talk-through):** reuse BACUP's GPL-3 code, with credit,
for three ideas rather than writing our own: zero a door's transition cell when that cell is not built, keep each
cell's FO4 lighting template, and texture land per quadrant from `VTXT` / `ATXT`. None of them touches markers,
locations or the merge probe; they belong to the doors, lighting and terrain work.

## Border signal (2026-10-23)
`FO4SF_MapMarkers` also writes `border=off` / `border=on` lines to fo4sf_map.0.log for the SFSE plugin FO4SFBorder
(docs/terrain/border.md, "Per-world switch"). `BorderSignal = False` turns the lines off. They are written before the
marker pass; indoors the last state is kept. The lines change nothing in the game by themselves.
Since 2026-10-28 every line carries `q=<quest>` (the quest's FormID, low 12 bits: 2048 is 0x800, the only quest that
writes the signal), and each quest's first pass of a game session writes `session id=... signal=... enabled=...
markers=... first=... interior=...`, what Border's guards read. A coc session from the main menu at Red Rocket wrote no
border line in 240 s while `moved 9` lines kept coming (Review, 2026-10-28); that line says which guard returned.

## Icons, the pad and the planet map (Claude-cloud, 2026-10-28)
The owner, 2026-10-28: "Map icons don't show up when you teleport me to the red rocket and there's no map location on
the surface of Mars, too fast travel to." Setup: a new game in Starfield's own start, landed on Mars, then `coc
FO4Core_RedRocketSpawn`, with the installed mapmarkers build `landing_border2` on core v6i. Read offline from the
24 Oct Card B logs (fo4sf_map.0-3.log, Papyrus.0.log, staged from `C:\Modding\scratch\a3_1017\cardB_border\logs`):
- **verified: the landing pad never moves.** Papyrus.0.log has `FO4Core_CommonwealthLandingPadRedRocketNorth
  (080008F0): cannot be moved.` on every pass. The fourth quest retried it until its budget (40) was spent; the
  trigger, the marker and the heading moved. So no pad is in the world the player walks in, and nothing is there to
  land at.
- **verified: a load door during a pass misplaced every marker after it.** At 10:24:13 a FO4SF_LoadDoor trip into
  Vault 95 happened while a pass ran. `Place` had read the player once, so about 300 markers went to their target
  plus the trip's offset (1905.1, 3920.4, -72.4), and every budget was spent (moves=200), so that save kept them there.
- **supported hypothesis (questioned by the 2026-10-28 PC runs below): the map takes markers only when the player
  enters a world.** A marker moved into the current world shows only after a world change or a save and load.
  Skyrim modders report the same, and that
  `AddToMap` does not help ([8993053](https://forums.nexusmods.com/topic/8993053-moving-mapmarkers-across-worldspaces),
  [8512658](https://forums.nexusmods.com/topic/8512658-help-needed-with-placing-a-dynamic-mapmarker)). Our markers
  are moved a few seconds after arrival, so the first arrival has no icons. Moving them cannot fix that on its own;
  the routes left are markers the map already knows (records in the runtime world, the merge question) or a map of
  our own on the Pip-Boy (owner, 2026-10-24).
- **hypothesis: the planet map lists only discovered landing markers.** A vanilla landing site is discovered when the
  player lands there; ours never was.

What the script does now (`FO4SF_MapMarkers.psc`):
- Just before each move it reads the player again and stops the pass once they are indoors or in another world.
- A reference still in its own world after `MoveTo` (the pad), while the player stayed in theirs, is not tried
  again that session or build. Until 2026-10-28 the rule also asked for its x/y to be unchanged; on the PC that never
  held for the pad (attempts 2 and 3: 18 and 27 `cannot be moved` errors, no `refused 9` line), so the `refused` line
  now logs where the reference was before the move.
- The move budget starts over at every game session as well as at every build, so markers a session left wrong are
  put right in the next one. A session starts at every save load (the player's `OnPlayerLoadGame`, which each quest
  registers for) and whenever the real-time clock goes back; the border signal starts over the same way. The clock
  alone missed a launch whose first pass reads a later time than the save's last one (Codex on #570).
- Once per session it marks the landing marker discovered and visible on the star map: the pad (`LandingPadID`
  0x7145) is fourth from its quest's end and the marker two places after it, because dotnet/MapMarkers keeps the
  landing spot's four pieces last and in one quest.

Unverified until a play test: whether a save and load brings the icons; whether Mars's map then lists "Commonwealth
Landing Area"; and whether the ship can land with no pad (if not, the pad needs to be a record of the runtime world).

PC attempts 2 to 4 (Install, 2026-10-28, `C:\Modding\scratch\a3_1017\cardB_border\logs_570`; a new game in
Starfield's start, `coc FO4Core_RedRocketSpawn` from the main menu, mapmarkers `landing_border3` from #570):
- **verified:** every marker reached the player's world. The moved lines go from another world (`before` float max)
  to d 0.8 to 2.9 km within about 10 s of arrival, and the landing marker was marked discovered 6 s before it moved.
- **verified:** after 60 s outdoors, Mars's surface map showed the player and one hexagon to the south-east. Mars's
  planet view showed Starfield's Fracking Station, Cydonia and Mars Mech Factory, a place by the player named "Dark
  Hollow Pond" with a small cyan hexagon beside it, and no "Commonwealth Landing Area" label. Dark Hollow Pond is one
  of our markers (FO4's, in the `--fo4-map-markers` export `cw_markers.json` on the PC), so the planet view drew our
  places as one labelled icon.
- **the owner's assumption, 2026-10-28 (watching the run; they asked for research):** the hexagon is all our icons
  layered over each other, the way Starfield draws a city: one icon, and clicking it lists the places inside to fast
  travel to. If so, the icons register on the first arrival, and the world-entry limit above does not hold here.
  Open: whether clicking it lists our places and fast travel reaches them, and how Starfield decides the grouping.
- **verified:** a save load closes the user logs. fo4sf_map.0.log ends `Log closed` at the load (16:46:38); the
  bridge's next line went to a new fo4sf.0.log with its own `log opened` header, though the bridge opens its log only
  in OnInit. The map script reopens its log on the first pass after a load (`NewSession`); attempt 4 has no pass
  after the load: the console stayed open after it (after_load_console_open_1650.png), and every log ends within 2 s
  of it, though quest 4 still had budget to retry the pad every 4 s.

## Star map (Claude-cloud, 2026-10-28)
Research (`/mnt/project-files/map/starfield-map-icon-grouping.md`, web and Creation Kit sources, not tested in game):
- **supported:** the planet view stacks every marker flagged Visible on Star Map (`FNAM` bit 4, 0x10) that sits at
  about the same spot on the globe under one icon, and selecting it lists them. That is how a city shows its
  districts. All our markers had the bit (`FNAM` 0x13, the landing marker 0x33) and sit a few km apart, so they made
  one stack of about 309 entries. The surface map does not collapse them.
- **supported (xEdit's SF1 definitions):** the `FNAM` bits are 0 Visible, 1 Can Travel To, 2 "Show All" Hidden,
  3 Use Location Name, 4 Visible on Star Map, 5 Discovered, 6 Requires Scanning, 7 Allow Grav Jump, 9 Suppress
  Discovery, 10 Use Accurate Z-Height, 11 Limit Map Visibility To Compass Range, 12 Must Cruise to First.

The owner's pick, 2026-10-28 (option A, of A: a short star map list, or B: also distinct surface map icons): "Both are
gonna need to get adjusted because most locations on the surface map are not something on the fallout map in your
pipboy, for right now go with a". So:
- `dotnet/MapMarkers build|check --star-map <json>` (`{"names": [...], "strict": bool}`) keeps bit 4 on the markers
  the list names and clears it on every other override and extra; the landing marker keeps 0x33. Every marker keeps
  Visible, so the surface map still shows all of them. A name that matches no marker fails the build when `strict`
  and is only reported otherwise; `check` wants the same list.
- `make_map_markers.py stage` writes `star_map.json` and passes it to both. Its default list is Red Rocket Truck Stop,
  Sanctuary Hills, Vault 111, Concord, Lexington, The Castle, Vault 81 and Bunker Hill (lenient, since the FO4 export
  can differ by PC; Diamond City and Goodneighbor have no marker in it). `--star-map NAME ...` gives a strict list
  instead, and `--star-map-all` keeps the bit on every marker, as before.

Unverified until a play test: that Mars's planet view then lists only those places plus the landing area, and that
fast travel from the list reaches them. Also open: whether clearing the flag hides a marker from the hand scanner
too (the sources disagree: a comment on Nexus mod 15633 says so, the mod's own page says hidden markers stay on the
surface map and scanner), and whether a save made before this build keeps the old flags for
markers it already knows (a guess, not tested); the play test should use a new game, or say which save it loaded.
B (FO4 marker types mapped to Starfield `TNAM` icons on the surface map) is for later.

## Reload (Claude-cloud, 2026-10-31)
The owner's new game v10 run (31 Oct): Mars's map icons were fine, but "nothing on the map shows up", and no
Commonwealth marker could be discovered by walking past it, until a trip to Cydonia and back. Logs
(`fo4sf_map.0.log` of the PC test folder `newgame_20261031_v10`):
- **verified (log):** the player came out of the elevator at rt 179 s and every marker was moved in from rt 186 s on;
  the last of the 313 first moves came at rt 233 s, about 47 s later. Each of the four quests, side by side, moved
  one marker every 0.45 s. **Supported hypothesis:** the time goes to the calls, about 18 for a moved marker (reads,
  the move, the log line; counted from the script), which the game answers about once a frame.
- **verified (log):** 475 moves for 313 markers. A move onto a walking player lands off by their steps in between
  (z 0.4 m off, `moved 10 ... target ...`), and such a marker was moved again on a later pass.
- **verified (log, 24 Oct):** after a trip to Cydonia and back, the player's world had the same instance id
  (FF00549A) and no marker but the refused pad was moved again: the world keeps the markers while the player is away.
- **supported hypothesis:** the map, and discovery on the way past, list only the markers that are in a world when the
  player enters it; ours come after, so they show only after the player leaves and comes back.

So (offline, waits on a play test):
- **20 markers a quest** (`dotnet/MapMarkers` `PerQuest`, was 100): about 16 quests side by side for 313 markers.
- **Fewer reads:** a marker in another world is moved without reading where it stands there; `QuestLow` reads the
  quest's id once; once a full pass finds every marker of a quest in place, a pass reads one of them in turn
  (`Probe`) and goes back to full passes when one is off.
- **SetPosition after the move:** once the marker is in the player's world, `SetPosition` puts it on its spot. The
  move line now says how far off a marker in the world was (`off=dx dy dz`).
- **The reload:** `dotnet/MapMarkers --reload` (on by default in `make_map_markers.py stage`, `--no-reload` leaves it
  out) adds a small interior of the plugin's own, `FO4SF_MapMarkersHop` (0x8F4: lit as PluginSpike's door test cell,
  which worked in game on 8 Oct; its platform 0x8F6 and a persistent COC marker 0x8F5), and names the marker in the
  first quest's `HopMarker`. When every quest's markers are in place in our world (or its moves are spent), some of
  them went in after the player entered, the player has been outdoors there for `HopDelay` (10 s: the new game's
  landing check is done by then), and they are not in combat or a scene and have their movement controls, the first
  quest fades to black, reads the player again (indoors, in another world or off the map by then: it fades back in and
  stops, since going indoors and out loads the world anyway), moves them to the stop, moves them back to the same spot
  by one of its markers in their world (then `SetPosition` there once the 3D is in, as the new game's ride up does, only if they are
  back in the same world), turns them back to their facing and fades in. Once a session (`HopLimit`). It also waits
  while the player is dead or seated (`GetSitState`). A player in the stop's cell on a later pass (a move back that did
  not take, a move out that landed late, a save made there) is brought back again: the stop has no door. A first
  quest out of moves before every marker stood still reloads too, so the log says why when none comes.
- **Log lines** (q=2048): `fast travel, all <n> quests' markers in place or out of moves, some after the player came: <bool>`
  (`Game.IsFastTravelEnabled`, `IsFastTravelControlsEnabled`, and the first marker's `IsMapMarkerVisible`,
  `CanFastTravelToMarker`), `reload 1: out to ...`, `reload 1: at the stop=...`, `reload 1 back: ... same=<bool>`
  (whether the world is the one the reload began in), then the fast travel line again; or `reload 1 called off: ...`,
  or `reload waits: ...` once.

The owner's play tests of #624 (31 Oct, new game v12, PC logs `mapmarkers_20261031_reload` and `..._reload2`):
- **verified (log):** 16 quests placed the 313 markers in 20 s after the arrival (rt 125.9 to 146.1; 130.1 to 150.0 in
  the retest), was 47 s with 4 quests. 312 moves for 312 markers plus the refused pad: `SetPosition` held every marker,
  none was moved again (was 475 moves).
- **verified (log):** the first test opened the map about 11 s after the arrival and kept it (or a menu) open until the
  game closed: the bridge's 0.5 s timer line stopped at rt 137 while the game ran to about 199 s, and no map pass ran
  after 146 s, so no reload came (**inferred:** Papyrus timers do not fire while a menu is open).
- **verified (owner and log):** in the retest the owner waited outdoors: `fast travel, all 16 quests' ...` at rt 156.3
  (6.3 s after the last move; `visible=true can=true` already), `reload 1` out at 157.6, at the stop at once, back at
  163.9 with `set=true same=true`; the owner then saw the Commonwealth's icons on the map. So the hypothesis holds: the
  map lists the markers in a world when the player enters it, and one round trip through the stop lists them all.

Open: whether the reload's world stays the same instance in every case (`same=` was true once), and the stop's look
(nobody saw it lit: the screen is black).

### Dark hold (Claude-cloud, 2026-10-31, option A; owner play test: "everything worked")
With `HoldDark` (on), the first quest fades to black (staying black) at its first marker that comes in late within
`HoldWindow` (15 s) of the player entering the world, if a reload can follow (`BorderSignal`, `HopMarker`, one left in
`HopLimit`, and the player in our world as Border learned it), once per entry; the reload's way back fades in, so the
first map the player opens lists every marker. In the retest that is about 31 s of black (the first quest's first
move at rt 133.0 to the way back at 163.9). The window covers the new game's ride, which lands
at its anchor off the map and on the arrival 4.3 s later (the first quest's first move came 7.2 s after the ride), a
GAMMA start and a save loaded outdoors; a player who walks into the Commonwealth long after entering Mars keeps the
blink. The hold also ends (fading in) past `HoldMax` (60 s), when the player leaves the map or our world or goes
indoors, whenever the reload would wait (a fight, dead, seated, in a scene, no movement controls), checked at every
pass and between moves of a long pass, when the reload is skipped or called off, and at a load. Log lines: `dark hold: markers coming in <s> s after the player entered the
world`, `dark hold ends with the reload after <s> s`, `dark hold released: <why>`. The offline reading (31 Oct, before
the play test): whether the game keeps the screen black through the stop's loading screens is open (the loading menu may fade in on its own:
FO4SF_NewGameQuest.psc FadeIn's note).

Play test (owner, 2026-10-31 22:34Z, #626 installed from main d285a885 on core v6i with newgame_v12): "ok everything
worked only issue left will be solved with the pipboy". Option A stands; B and C were not built.
The issue left is for the Pip-Boy map (owner's words above; which issue was not said).

Log reading (Claude, 1 Nov; the game's rotating script logs copied to the PC's test-log folder
`mapmarkers_20261101_logsnap` before they rotated out). The play test's map log (31 Oct, 16:14 PC time) reads
`dark hold: markers coming in 0.027000 s after the player entered the world`, then
`dark hold ends with the reload after 30.750999 s` and `reload 1 back: ... same=true`: the hold ended with the reload,
as in the retest (**verified, log**). A later session that day (20:56 PC time) held 20.9 s. A `coc
FO4Core_RedRocketSpawn` session on 1 Nov (11:20 PC time, Codex's P9 probe session, FO4SFMission off) ran to the cap
instead: the last marker move came at rt 776.8 (23.5 s into the hold), then the log has no map line for 38.8 s of rt
until `dark hold released: no reload after 62.257996 s` (rt 815.6); the reload went out 3.5 s after that (rt 819.1)
and was back at rt 824.6 (`same=true`). So the cap works as written when no reload comes; why none came in that gap
is not known (the 31 Oct pass reported every marker in place 7.4 s after its last move, this one 41 s after). One
observation, not a cause: across that gap rt ran 38.8 s while the PC clock ran 3 min 3 s (11:21:20 to 11:24:23). Most
intervals in these logs agree within about a second, but rt also falls behind the PC clock by 8 to 113 s in other
places (for example 31 Oct, 16:11 to 16:14, just before that play test's hold), so this is the largest such gap, not
a new kind. No one has said whether the screen stayed black
through the stop's loading screens; the owner's "everything worked" is all there is, and the logs cannot show it.
