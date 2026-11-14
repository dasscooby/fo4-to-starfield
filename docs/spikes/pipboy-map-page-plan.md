# Pip-Boy MAP page: from text rows to the player's map (plan, FAL-584)

Claude (sole survivor), 12 Nov 2026. **A plan, no code.** Nothing here has run in the game. Labels as in the
terrain docs: **verified** = read from the source or a PC log, **hypothesis** = to be proven by the read named
beside it. The pause default (`Pause=0`) does not change.

## What the MAP page shows today (verified, source at `cdde9fbc`; step 1 added two rows, FAL-595)

`[Page MAP/WORLD]` in `sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini` has seven text rows:

| Row | Value | Read |
|---|---|---|
| WORLD | the worldspace's name (`NameText`), or `NONE (INTERIOR)` (FAL-595: read at `+0x110`, found on the PC) | the player's `parentCell` (`+0xB0`), its worldspace |
| CELL | the cell's name (`NameText`) | the same cell |
| POSITION | `x y z`, whole game units | `ReadPosition`: the player's `OBJ_REFR::location` at `+0x80 + 0x0C` (Peek) |
| HEADING | compass degrees, `0` to `359`; `HeadingAt=88` verified on the PC (12 Nov) and shipped | the angle float `HeadingAt=` names (Peek) |
| GRID | `x y`, POSITION over a cell's width, rounded down; `NONE (INTERIOR)` as WORLD; `GridUnits=100` verified on the PC and shipped | `ReadPosition` |
| TIME | the game hour | `GameHour` |
| DAYS PASSED | the day count | `GameDaysPassed` |

There is no picture and no marker, and HEADING and GRID stay `?` until the PC reads below set their two `[Kit]`
lines. The page is text in the kit's dot-matrix font.

## What a player needs first

In Fallout 4 the MAP tab opens on the world map: the player's arrow at their place, pointing where they face, and
the discovered locations as named icons. Quest targets, the local map and fast travel come after that. So the order
is:

1. **Where am I:** the player's place on a map, and which way they face.
2. **What have I found:** the discovered markers near them, with their names.
3. Later: quest targets (after the objective text, candidate 2 of this task), the local map, fast travel. Fast
   travel is a call into the game, so it is out of scope until a separate owner decision.

## The gap that matters most (verified, `docs/terrain/map-markers.md`)

Our world has **almost no map markers yet**. The pinned `FO4TerrainCore.esm` has 0 references with `XMRK`. The
marker-restore work adds one `MapMarker` reference for the overlay. Fallout 4's own location markers (the
Commonwealth's named places) are not converted yet. So the page cannot show "discovered markers" until the
converter writes them. **The marker conversion is a dependency of item 2, not a page task.** Item 1 needs nothing
converted.

## The steps, smallest first, each ending in something a player can see

### Step 1: heading and grid as rows (code: small, Peek only; written on FAL-595, PC reads open)

Two rows on MAP/WORLD, each `?` with one `step=page_unknown` line saying why until the PC has proven its place
(`sfse/FO4SFPipboyMenu/README.md`, `heading` and `grid`). F11 at stage (e) logs the player's bytes from `+0x80` to
`+0xC0` with the six floats there (`step=kit_map_bytes`) and the player's cell with its own grid (libxse
`TESObjectCELL::cellData` at `+0x58`, `EXTERIOR_DATA` `cellX`, `cellY`: `step=kit_map_cell`);
`scripts/ui/pipboy_map_bytes.py` reads two dumps and prints `HeadingAt=` (and `--grid`: `GridUnits=`). The rows:
- **HEADING:** compass degrees, from the player's `OBJ_REFR::angle`. In libxse `angle` comes before `location` in
  `OBJ_REFR`, so it is the three floats at `+0x80`, in radians. **Hypothesis:** z is the heading.
- **GRID:** the cell grid `x / 4096, y / 4096`, rounded down. **Hypothesis:** our overlay keeps 4096 units per
  cell, as Fallout 4 does.

**PC reads that prove it:**
- **R1:** F11 at stage (e), standing still, then turn on the spot about 90° right and press F11 again. The
  `kit_map_bytes` line (the 64 bytes at the player's `+0x80`, added with this step) shows which float moved, by
  about π/2; the helper prints `HeadingAt=`.
- **R1b (GRID):** F11 in one cell, walk until POSITION's x or y has crossed a multiple of 100 by 30 to 60, F11 again;
  the helper (`--grid`) prints `GridUnits=100` when the cell's own grid follows POSITION over 100 in both.
- **Found on the PC (12 Nov, `e2e551c8`):** R1 gave `HeadingAt=88` (`player.setangle z 0` then `90`: `+088` from
  `0.0000` to `1.5708`, radians rising to the right). Positions are Starfield's units: `cell_x` was x over 100 on five
  presses (Fallout 4's 4096 and the border notes' warning). `world=0x0` on every outdoor `kit_map_cell` line, so
  libxse's `cellWorldspace` at `+0x118` is not where this runtime keeps it; F11 now looks for it (`step=kit_map_world`,
  the helper's `--world`). At `4d1e7641` (PC, 12 Nov) it found Mars at `+0x110` on every outdoor press and nothing
  indoors, `cell_y` followed y over 100 (`modpos y 60`: -16 to -15), and HEADING read `270` on the page.
- **R2:** `coc FO4Core_RedRocketSpawn` and read POSITION. Compare it with the Red Rocket spawn marker's local
  position in `map-markers.md` (`-989.257, 1146.514, 107.143`) to fix the units and the offset between the overlay
  and Fallout 4's Commonwealth grid. Do the same once at Sanctuary.

Visible result: HEADING turns as the player turns, and GRID changes when they cross a cell border.

### Step 2: a text map in the kit (code: medium, no new movie)

**Parked for later uses (a warfare mode, settlement management views), not the Pip-Boy's map page** (owner, 13 Nov,
FAL-614). The Pip-Boy's map page is the Fallout 4 rebuild (`pipboy-fo4-rebuild-plan.md`, section c). The groundwork is
kept, not removed: `claude/fal614-pipboy-text-map` at `3133640d` (the cell list from the converter's
`overlays_params.json`, held, not on GitHub).

A map drawn in characters in the kit's list area, the same 16 rows the kit already draws:
- the player's character in the centre (`^ > v <` by HEADING);
- the converted cells around them as `.`, and cells we have no terrain for as blank;
- the cell list comes offline from the converter's own output (which cells we wrote), shipped as a small data file
  in the kit, nothing from the game's files.

**PC read:** none new. Walk Red Rocket to Sanctuary (the route in `walk-redrocket-sanctuary.md`) and the
character should move across the map. This is the first thing a player would call a map.

### Step 3: markers on the text map (code: after the marker conversion)

Each converted marker as the first letter of its name on the text map, with the name in the value rows when it is
selected. Our markers are references in our own plugins, so they are found the same way as the quest list
(FAL-584): by their form ids in our file, through the engine's lookup, each accepted as a `TESObjectREFR` by
RTTI. Nothing walks the game's own lists.

"Discovered" is runtime state. **Hypothesis:** it is a flag in the reference's map-marker extra data, as in
Fallout 4 and Skyrim.

**PC reads that prove it (once at least one marker of ours exists):**
- **R3:** F11 dumps the marker reference's extra-data blocks (the quest dump's method: follow its pointers that
  lead back to it).
- **R4:** walk to the marker until the game says it is discovered, then F11 again. The byte that changed is the
  discovered flag. If the console takes `tmm 1` (show all markers), use that instead of the walk, on a save that is
  not kept.

Visible result: the overlay's marker shows, and appears or changes when the player discovers it.

### Step 4: the real Fallout 4 map look (after the look plan; now `pipboy-fo4-rebuild-plan.md`)

The look survey (#759, PC run 12 Nov) found `Pipboy_MapPage.swf` in the player's own `Fallout4 - Interface.ba2`.
The world map's texture name is not known yet.

**PC read.** **R5:** the look survey's names-only listing over the Fallout 4 texture archives, for names containing
`map` under `Interface`. Names and counts only; nothing extracted, nothing copied into Git.

Whether the page can use the player's own files at runtime follows the look plan's rules
(`pipboy-real-device-look-plan.md`). No asset of the game is ever shipped.

## What this plan does not do

- No call into the game beyond the lookup the kit already uses. No fast travel, no `coc` from the plugin.
- No game files in Git. The cell list in step 2 comes from our converter's output.
- No change to the pause default or to the stages.

## Next gate

The owner picks the next step; step 1 is the smallest. Each step gets its own branch, tests, a CARRY line, the
Scribe's review, and the PC reads named above.
