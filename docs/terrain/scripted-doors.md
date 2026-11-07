# Scripted load doors: exterior FO4 load doors into the converted interiors

Author: Claude, 2026-10-16 (return trip writer side: 2026-10-17). Status (checked 2026-11-06, Mountain): **partial
in-game results**. [Return trip](#return-trip-writer-side-2026-10-17) records the 2026-10-16 forward PASS ARRIVED and
return EXPECTED-REFUSED on core64k + integ_1018_doors, plus probe (e)'s persistent-anchor move and setpos hops. Later
Vault 95 exit results are recorded under "Retry on a missed trip" and "One long jump instead of two" below; this
status does not establish a successful return on every build. Labels as in the other terrain docs: **verified** =
read from files, **supported** = hypothesis with evidence, **unresolved** = open.
Records read raw with `src/fo4sf/fo4land.py` and `scripts/terrain/vmad_patch.py`; the design pass (2026-10-16,
workflow wf_f78e6bf6) read the VMAD layout off `Starfield.esm` 1.16.244 and off a plugin Mutagen 0.55.0-alpha.67
wrote; this build reproduces its bytes exactly.

## What a door pair is

A Fallout 4 load door is a persistent DOOR reference with an XTEL (the destination door, an arrival point and a
heading); both ends point at each other. Our builds place both ends as plain STAT references without XTEL (the core
places the exterior one, FO4Port.esm the interior one), and a vanilla-style XTEL door failed in game because a
persistent reference of the overlay reads its unmerged position (docs/slice/door-frames.md, JOURNAL 2026-10-13 a2).
The scripted door keeps every record temporary and moves the player with Papyrus instead:
`scripts/door_bridge/FO4SF_LoadDoor.psc` (Codex, PR #243) attaches to the door reference; on the player's
activation it resolves `Game.GetFormFromFile(DestinationId, DestinationPlugin)` and calls `MoveTo` on it. The
contract: `DestinationPlugin` (string, the plugin's file name) and `DestinationId` (int, the destination reference's
plugin-local id, 1..0xFFFFFF); since 2026-10-17 also `DestinationX` / `DestinationY` / `DestinationZ` (float: where
the player is put with `SetPosition` after the MoveTo, see "Return trip" below) and `UseDestinationPosition` (bool:
the script applies the three floats only when it is true; zero is a valid coordinate, so the bool, not the values,
is the switch). No plugin masters the other.

**Retry on a missed trip (2026-10-22; run in game 2026-10-22/23, it never fired).** The Vault 95 exit fails intermittently: the player stays
in the interior and the engine shows "BOUNDARY REACHED" (2 of 9 runs in the settling test, plus earlier control and
hnam5 failures; whether the world's border fields change the rate is open, docs/terrain/border.md). After the MoveTo the script checks whether the player has left the cell they activated it from (by cell,
not world: on an exterior trip the player's world can read as the runtime instance while the marker's reads as the
core's WRLD; a destination in that cell counts as arrived). If not, it waits `RetryWaitSeconds` (default 0.5), checks again, and repeats
the same MoveTo, at most `MoveRetries` times (default 1; 0 turns it off). Both properties have defaults, so existing
VMADs need no change. Each retry traces `FO4SF_LoadDoor retry N of M` and `phase=after_retry`, and a miss after the last one `FO4SF_LoadDoor retry gave up after N`. A door PASS in the
doors_out judge's results can therefore come from the second MoveTo; the trace tells which. The check is not a judged
arrival either: it only sees that the player left their starting cell, and the judge still reads where they ended up.
In the 10 retry runs it never fired (docs/terrain/border.md, "Rate and retry runs"): the MoveTo always lands in the
exterior, and the popup comes up afterwards and pauses the game, so the script cannot see the failure.

**Settle before the position step (2026-10-23, not yet run in game).** With `UseDestinationPosition`, the script now
waits `SettleSeconds` (default 1.0; an Auto property, so existing VMADs need no change) after the MoveTo and traces
`phase=settled` before the SetPosition. It is a diagnostic first: the popup pauses Papyrus, so where the trace stops
tells which step raised it.

**One long jump instead of two (2026-10-23; withdrawn 2026-10-28).** Bridge t6 (#512) put the destination marker
itself at `DestinationX / Y / Z` with `destination.SetPosition` before the MoveTo (traced as `phase=marker_placed`), so
that the MoveTo onto it would land at the merged spot and the SetPosition after it would move about 0. In game it did
the opposite: in 20 Vault 95 exits on the PC (28 Oct, queues `doors_v95_land2_r01..r20`, the animated doors port
07756819, border switch off and on alike) the trace read `marker_placed` (the marker in FO4Core_Commonwealth), then
`MoveTo returned` with the player still in the interior cell, then the retry's MoveTo the same: 19 FAIL STAYED, 1 not
run, 0 landings. Without that step (t4 and t5) every traced MoveTo of the same door landed outside (border.md "Rate
and retry runs"; the owner's exits of 23 and 24 Oct). So a persistent marker moved far from its cell by SetPosition
while unloaded is not a destination the player's MoveTo follows; the script no longer touches the marker, and the
player is put at the merged spot by the SetPosition after the move, as before. Only FO4SF_LoadDoor.pex changes.

Per door, this build writes:

| side | record | where | what |
| --- | --- | --- | --- |
| exterior (FO4TerrainCore.esm) | ACTI `FO4Core_door_<6 hex>_<plugin>` | appended after the lights, one per FO4 door base | the converted door mesh (collision as the STAT it replaces), FULL "Door" (FO4's door names are localized string ids; `--names` can give the FULL), PNAM cc4c3300, FNAM 0, JNAM 360 (the activators' vanilla majority) |
| exterior | the door REFR | **its original slot** (as every promoted class) | base = that ACTI; VMAD: one local script FO4SF_LoadDoor, `DestinationPlugin` = "FO4Port.esm", `DestinationId` = the interior arrival marker, `DestinationX/Y/Z` = that marker's position (interior coordinates, as its DATA), `UseDestinationPosition` = true |
| exterior | arrival marker REFR | new id after every other record (lights included), in the world's **persistent cell** (beside the anchor) | XMarker 00003B:Starfield.esm, **persistent** (0x400, since 2026-10-17), at the interior door's FO4 XTEL arrival / 70 (local coordinates) with its heading: where the interior door's MoveTo lands the player |
| interior (FO4Port.esm, `vmad_patch.py port`) | the door REFR 01007D0B-style | unchanged record + VMAD | `DestinationPlugin` = "FO4TerrainCore.esm", `DestinationId` = the exterior arrival marker, `DestinationX/Y/Z` = that marker's **merged** position: local x - 1200, y - 2700, z unchanged, `UseDestinationPosition` = true |
| interior | arrival marker REFR | the port plugin's next free id + k, in the CELL's **persistent** children group | XMarker, persistent, at the exterior door's FO4 XTEL arrival / 70 with its heading: where the exterior door's MoveTo lands the player |

Why both destinations are persistent markers and not the doors themselves: a temporary reference of an unloaded
cell is not in memory, so `GetFormFromFile` from the other side returns None and the script refuses (**verified** in
game for the exterior side on 2026-10-16: door_trip_sdm_1018, see "Return trip"). Interiors have no overlay merge, so
a persistent reference reads its written position there (docs/terrain/overlay-records.md). In the overlay a
persistent reference reads its UNMERGED (local) position: the MoveTo of the return trip lands there, in a runtime
instance of the overlay, and the door's `DestinationX/Y/Z` then moves the player to the merged spot (probe (e)).

## Path

```
python scripts/terrain/make_cluster.py doors --work <core64c work> --build <core64i> --port <integ_1017> --out doors.json
python scripts/terrain/make_cluster.py merge --out cluster_j.json commonwealth_cluster_i.json doors.json
python scripts/terrain/make_core64c.py stage --work <work> --core <terrain_core64> --out <core64j_doors> --sf-esm <Starfield.esm> --cluster cluster_j.json --navmesh <navmesh.json>
python scripts/terrain/make_core64c.py check --work <work> --core <terrain_core64> --out <core64j_doors> --sf-data <Starfield Data> --fo4 <Fallout4.esm>
python scripts/terrain/make_core64c.py compare-ids --out <core64j_doors> --against <core64i>
python scripts/terrain/vmad_patch.py port  --port <integ_1017> --core <core64j_doors> --out <integ_1017_doors>
python scripts/terrain/vmad_patch.py check --port <integ_1017> --out <integ_1017_doors>
```

1. **`make_cluster.py doors`** reads every exported Door reference with an XTEL (band exports) and keeps those whose
   destination door is a reference of a converted interior of the port staging (its `<cell>.json` exports); both
   sides must be placed (the exterior by the build's objects.json, the interior by the port's formids.json) and the
   interior door must link back. A door with a missing side goes to `door_skipped` with the reason and is never
   promoted. Each entry carries the FO4 base, editor id and model, the converted model, both arrival points (XTEL
   arrival / 70, rotation) and XTEL flags, the interior door's port id and CELL, and `destination.id` = the interior
   marker's id, which is the port plugin's HEDR next object id + k (read from the plugin; it must equal the highest
   own id + 1, else refused). `doors_port` records the plugin and that next id, so `vmad_patch.py port` can refuse a
   port that changed. `merge` accepts the two keys.
2. **`make_core64c.py stage --cluster`** promotes `doors` like the other classes (`cluster_doors`: one slot plan with
   containers, items, activators, terminals, workshops and benches; a source in two classes is refused, as are two
   doors sharing a destination or an interior door, a bad plugin name or id, an arrival outside the overlay's cells);
   the writer (dotnet/TerrainOverlays) places the door REFR in its reserved slot with the VMAD and, after the lights,
   the markers in `doors` order (persistent, in the world's persistent cell) then the ACTIs in first-use order;
   formids.json gains `"doors": {src: {base, ref,
   arrival}}`. **Every id of the build without doors stays put** (compare-ids: every section identical but `refs`,
   which loses the promoted doors to `doors`, their REFR ids unchanged).
3. **`check`** adds: the door REFRs keep their slots (`check_reference_slots`), the markers and ACTIs come after
   every other record including the lights (`check_door_identities`, `doors_after`), ACTI count = distinct door
   edids (with the activators and workshops: one line per signature), and per door the ACTI fields, the REFR's VMAD
   decoded back to the script and every property value (DestinationX / Y / Z = the entry's destination.arrival
   position, UseDestinationPosition present and true: floats without the bool are refused), the marker's base, position, rotation and persistent flag (`door_record_problems`); the markers sit in
   the persistent children of the world's persistent cell with the anchor and nothing else there
   (`door_marker_groups`, `door_marker_placement`), over the overlay's cells, and no longer count in the per-cell REFR
   totals.
4. **`vmad_patch.py port`** copies the pinned port folder into a NEW folder (every file hard-linked; the plugin and
   formids.json copied), patches the plugin record by record (the tree parser writes an untouched plugin back byte for
   byte, **verified** on FO4Port.esm) and writes doors.json + README.txt; **`check`** proves every other record
   byte-identical and in its group, each door REFR unchanged but for the inserted VMAD (which decodes to the core's
   arrival marker and its merged position: objects.json arrival + `merge_offset`, read from the core's
   overlays_params.json), the markers persistent in the persistent group at the arrival points and nothing else new,
   HEDR counts. formids.json gains `MARK:<cell edid>:<exterior door formkey>` keys.

Mutagen or a raw post-pass for the VMAD: Mutagen writes the exterior side (the design pass verified the written bytes
against vanilla; `tests/test_terrain_doors_writer.py` asserts the writer's VMAD equals `vmad_patch.load_door_vmad`
byte for byte). The interior side is a raw patch because the pinned FO4Port.esm must not be rewritten by a library
that normalizes records: the record-level byte diff is the proof that nothing else changed.

## VMAD layout (**verified**)

`int16 version 6 | uint16 object format 2 | uint16 script count`; per script `uint16 length + name | uint8 status
(0 local) | uint16 property count`; per property `uint16 length + name | uint8 type | uint8 status (1 edited) | value`
(2 string = `uint16 length + chars`, 3 int = int32, 4 float = f32, 5 bool = u8). Since 2026-10-17 a door with a
destination position has six properties: `0c00 "DestinationX" 04 01 <f32>`, then Y and Z, follow DestinationId, and
`1600 "UseDestinationPosition" 05 01 01` is the sixth (`vmad_patch.load_door_vmad(plugin, id, position)`; Mutagen's
ScriptFloatProperty and ScriptBoolProperty write the same bytes: tests/test_terrain_doors_writer.py). The decoder
(`vmad_patch.load_door_target`) reads the six-property shape and returns the position, or the two-property shape and
returns None; floats without the bool (the five-property VMAD this writer wrote before the bool) or a false bool are
refused, and the checks require the position. Papyrus binds a VMAD property by name and type, so the order is
cosmetic: PR #291's psc declares the bool before the three floats, this writer puts it sixth, the reader takes both
(`test_property_names_and_types_are_the_scripts_declarations` compares the names and types with the psc once #291 is
in the tree). The
80-byte reference of the design pass (FO4Port.esm:0x2339):
`0600 0200 0100 0e00 "FO4SF_LoadDoor" 00 0200 1100 "DestinationPlugin" 02 01 0b00 "FO4Port.esm" 0d00 "DestinationId"
03 01 39230000`; `vmad_patch.encode` reproduces it and `decode` reads Starfield.esm's own
`DefaultRefOnTriggerEnter` example (101 bytes, an inherited script with int / object / int properties) back to the
same bytes (tests/test_vmad_patch.py). On the REFR the VMAD is the first field after EDID, before NAME (vanilla order).

## The 18 doors of the core (**verified** against the data; the design pass's census)

1,286 Door references in the 11 band exports, 373 with an XTEL, 18 into 13 of the 16 converted interiors (Vault81,
DmndValentines01, GoodneighborHotelRexford have no exterior load door in the Commonwealth worldspace). 15 are placed
on both sides and become scripted doors (11 FO4 door bases); 3 are editor-marker doors on both sides and are listed
in `door_skipped` (`08EB65` the Red Rocket cave AutoloadDoor, `0998E3` and `248AAE` the Vault 111 autoload / hidden
doors: "exterior side not placed by the build (editor_marker); interior side missing in the port (marker model)").
The first pair is Super Duper Mart `0EE661` <-> `0EE5D6`: the nearest pair whose both sides are real converted door
meshes (727.8 m from the Red Rocket spawn), nothing unusual on either record (no script, lock, owner or enable parent,
XTEL flags 0 both ways).

## Full-scale build (offline, **verified**, 2026-10-16)

`terrain_core64j_doors` = `terrain_core64c_work` + `terrain_core64` + `commonwealth_cluster_i.json` merged with
`make_cluster.py doors` (15 doors over 11 FO4 bases, 3 skipped) + core64i's navmesh.json (sha256 = core64h's).
The writer: 224 ACTI (211 activators + 2 workshops + 11 doors), 654,624 REFR (core64i's 654,609 + 15 markers), the
rest as core64i; next FormID 0xA772B (core64i 0xA7711 + 15 markers + 11 ACTI); 62 s placement, 23 s plugin, 43 s
plan. `check --sf-data --fo4`: 265 of 265 PASS (152 s), among them: slots retained over the seven classes, the 15
door REFRs keep their slots, markers 0A7711..0A771F then ACTIs 0A7720..0A772A after every other record (last other
0A7710 = the last LIGH), every door's VMAD decodes to its destination, every marker at its arrival point.
`compare-ids` against core64i: every section identical (`bases`, `containers`, `items`, `activators`, `terminals`,
`workshops`, `benches`, `lights`, `navmeshes`, `navi`, `plugin`, `world`), `refs` 628,065 same, 0 changed, 15 only in
core64i (the doors, now in `doors`, their REFR ids unchanged), `doors` added (15).

The Super Duper Mart pair (FO4 0EE661 <-> 0EE5D6), raw:

- ACTI `010A7725` FO4Core_door_018c8b_fallout4: EDID, OBND (24 zero bytes, as every promoted base), ODTY 0, FULL
  "Door", MODL fo4core\interiors\industrial\doors\indmetaldoorload01.nif, PNAM `cc4c3300`, FNAM `0000`, JNAM `6801`
  (360), no VMAD.
- REFR `0102D22C` (core64i's slot), temporary in cell (-5, 6), flags 0: VMAD
  `0600 0200 0100 0e00 "FO4SF_LoadDoor" 00 0200 1100 "DestinationPlugin" 02 01 0b00 "FO4Port.esm" 0d00 "DestinationId"
  03 01 ffde0000` (= FO4Port.esm:0x00DEFF), NAME `25770a01` (the ACTI), DATA (-469.8529, 636.7089, 42.356) rot z
  2.58121: the STAT reference's own position.
- marker REFR `010A7717`, temporary in cell (-5, 6), flags 0: NAME `3b000000` (XMarker), DATA (-469.4441, 636.0741,
  42.356) rot z 2.58121 (the interior door's FO4 XTEL arrival / 70), no XSCL.

`integ_1017_doors` = `integ_1017` with 20,395 files hard-linked; FO4Port.esm 4,083,513 -> 4,086,084 bytes;
`vmad_patch.py check`: PASS, 54,395 of 54,395 other records byte-identical and in their groups, the 15 door REFRs
unchanged but for the VMAD, the 15 markers (00DEF9..00DF07) the only new records, HEDR 54,480 -> 54,495 records,
next 0xDEF9 -> 0xDF08. The Super Duper Mart side:

- door REFR `01007D0B`, temporary in CELL 01006C46 FO4Port_SuperDuperMart01, flags 0: VMAD (87 bytes)
  `... "DestinationPlugin" 02 01 1200 "FO4TerrainCore.esm" 0d00 "DestinationId" 03 01 17770a00` (= 0x0A7717, the
  exterior marker), then NAME `5b680001` (DOOR FO4Port_indmetaldoorload02) and DATA (6.4, 17.3714, -3.6571) rot z
  4.712389 as before.
- marker REFR `0100DEFF`, flags 0x400, in the cell's new persistent children group: NAME XMarker, DATA (5.449,
  17.2909, -3.6536) rot z 4.71239 (the exterior door's FO4 XTEL arrival / 70).

## Return trip (writer side, 2026-10-17)

**In game, 2026-10-16** (owner's PC, read from the queues' files):

- `C:\Modding\testqueue\door_trip_sdm_1018` (core64k + integ_1018_doors), `door_trip_judge.json`: the forward trip
  PASS ARRIVED (activating the exterior REFR 02D22B; first interior bridge line `pos=5.448989 17.290892 -3.636801`
  in cell 04006C46, 0.02 m from the interior marker 00DEFF); the return EXPECTED-REFUSED: `FO4SF_LoadDoor refused:
  destination unavailable or self`, and `Resolve FO4TerrainCore.esm 685821` (the temporary exterior marker 0A76FD) gave
  `form=none` from inside. **Verified**: a temporary overlay reference in an unloaded cell does not resolve.
- `C:\Modding\testqueue\door_probe_1017e` (probe (e), `C:\Modding\scratch\probee\judge_e.py <bridge.log>`): from inside
  RedRocket01, `MoveTo` onto the persistent anchor 0x800 (world persistent cell 02001805) landed the player at its
  UNMERGED position (-989.257, 1146.514, 105.29) in planet cell FF01181F (offsets are ignored); after setpos hops to the
  merged spot (-2189.26, -1553.49) = local + (-1200, -2700) the bridge read z 110.22 .. 110.49, then 110.49 for 21 lines:
  the top of FO4Core_redrext_workshop02 at that spot (core64k's plan, entry 3 "arrival": 110.4923). The judge says
  INCONCLUSIVE UNSETTLED only because its PASS window stops at 109.5 to exclude a hang at the 110.0 drop height; the
  reading is the canopy, not the drop height (**supported**: the player stands on the merged world's objects).

**What the writer does now** (code: dotnet/TerrainOverlays, scripts/terrain/vmad_patch.py, make_core64c.py):

- Each exterior arrival marker is **persistent** (0x400) and sits in the **world's persistent cell** (01001805, beside
  the anchor), not in its exterior cell. Same id as before (new ids after every record, the lights included, markers
  then ACTIs): formids.json does not change. Why the world's persistent cell rather than the exterior cell's
  persistent children: the anchor there is the only persistent overlay reference seen to resolve and take a MoveTo in
  game (probe (e)), and vanilla keeps every persistent worldspace reference there: Starfield.esm 16,057 of 16,057,
  Fallout4.esm 33,571 of 33,571, 0 in an exterior cell's persistent children (**verified**,
  `C:\Modding\scratch\doorreturn\survey_persistent.py <esm>`: a raw GRUP walk counting worldspace REFRs by group type
  and whether an exterior block (types 4 / 5) is above them).
- Both door VMADs carry `DestinationX` / `DestinationY` / `DestinationZ` (float, edited, after DestinationId) and,
  since the restage of 2026-10-17 below, `UseDestinationPosition` (bool, edited, true) as the sixth property. The
  exterior door: the interior marker's position (objects.json destination.arrival.pos, the marker's DATA, interior
  coordinates). The interior door: the exterior marker's **merged** position, its written position + `merge_offset`:
  overlays_params.json `planet_target_cell` of the world ([-12, -27]) x 100 m = (-1200, -2700), z unchanged; any
  other offset is refused (`vmad_patch.MERGE_MEASURED`, the only one measured: seven core64 / core64b spawn reads and
  probe (e)). The names are those of Codex's FO4SF_LoadDoor extension, PR #291, a draft (not on main on 2026-10-17):
  its `UseDestinationPosition` bool gates the `SetPosition`, so both writers set it (see "Restage with the bool").

**Build `C:\Modding\staging\terrain_core64l`** (offline, **verified**; `C:\Modding\scratch\doorreturn\*.log`, commit
b1b0e26): `make_core64c.py stage --work terrain_core64c_work_fix3 --core terrain_core64 --out terrain_core64l --sf-esm
<Starfield.esm> --cluster C:\Modding\scratch\core64k3\commonwealth_cluster_k.json --navmesh terrain_core64i\navmesh.json`
(core64k's stage command with another --out; as first staged, with five properties, before the bool: restaged
below): FO4TerrainCore.esm 193,631,182 bytes (core64k + 900 = 15 doors x 3
properties x 20 bytes), next FormID 0xA7711 as core64k. `check --sf-data`: 265 of 265 PASS (core64k: 264 of 264; the
new line: "15 door arrival markers in the persistent children of FO4Core_Commonwealth's persistent cell, the anchor's
(16 REFRs there = anchor + markers), each over the overlay's cells"). Oracle `collision_mesh_keys.py Data\meshes`:
11,768 NIFs, 0 violations. `compare-ids --against terrain_core64k`: every section identical, `doors` (15) included;
formids.json, objects.json, plan.json and FO4TerrainCore_Mars.esm byte-identical to core64k's (sha256). Raw record
diff against core64k (`core_rawdiff.py`): 683,794 records both, 683,764 identical in bytes and group; the 15 door
REFRs differ (the VMAD), the 15 markers differ (flags 0 -> 0x400) and moved from their exterior cell's temporary
children to the persistent children of 01001805; group count 3,499 both; TES4 identical.

**Port `C:\Modding\staging\integ_1018_doors2`** = `vmad_patch.py port --port integ_1018 --core terrain_core64l`:
20,395 files hard-linked, FO4Port.esm 4,083,513 -> 4,086,984 bytes (sha256 447ff623...); `vmad_patch.py check`: PASS,
49 of 49 (54,395 of 54,395 other records byte-identical and in their groups, the 15 door REFRs unchanged but for the
VMAD, each decoding to the core's arrival marker at its merged position, the 15 markers 00DEF9..00DF07, HEDR 54,480 ->
54,495 records, next 0xDEF9 -> 0xDF08). Independent raw diff (`rawdiff2.py`, no repo code; the merged positions
recomputed from the core's objects.json + overlays_params.json): 15 changed REFRs, 15 new, 54,395 identical, order
preserved, all 15 VMADs match; against integ_1018_doors (the port of core64k) only the 15 door REFRs differ, each by
the three floats appended to the same two properties, TES4 identical.

The Super Duper Mart pair, raw (`sdm_records.py`, `vmad_patch.py decode`):

- exterior door REFR `0102D22B` (temporary, cell 01000EEB, flags 0): VMAD (167 bytes) `0600 0200 0100 0e00
  "FO4SF_LoadDoor" 00 0600 ... "DestinationPlugin" 02 01 "FO4Port.esm" ... "DestinationId" 03 01 ffde0000 0c00
  "DestinationX" 04 01 1e5eae40 0c00 "DestinationY" 04 01 bf538a41 0c00 "DestinationZ" 04 01 1bd469c0 1600
  "UseDestinationPosition" 05 01 01` = FO4Port.esm 57087 (0x00DEFF) at (5.448989, 17.290892, -3.653571): the same float
  bytes as that marker's DATA, and the bool true (restaged with the bool, see below).
- exterior marker REFR `010A76FD`: flags 0x400, group path WRLD children 01000803 -> cell children 01001805 ->
  persistent children 01001805 (with the anchor 01000800); NAME 0000003B (XMarker), DATA (-469.44415, 636.0741,
  42.355988) rot z 2.58121, as in core64k (where it was flags 0 in cell 01000EEB's temporary children).
- interior door REFR `01007D0B` (integ_1018_doors2): VMAD (174 bytes) `... "DestinationPlugin" 02 01
  "FO4TerrainCore.esm" ... "DestinationId" 03 01 fd760a00 ... "DestinationX" 04 01 36aed0c4 ... "DestinationY" 04 01
  d0fe00c5 ... "DestinationZ" 04 01 886c2942 1600 "UseDestinationPosition" 05 01 01` = FO4TerrainCore.esm 685821
  (0x0A76FD) at (-1669.4441, -2063.9258, 42.355988) = the marker's local position + (-1200, -2700, 0), bool true; NAME
  and DATA as before.
- interior marker REFR `0100DEFF`: unchanged from integ_1018_doors (flags 0x400, the cell's persistent children).

### Restage with the bool (2026-10-17)

PR #291's script applies `DestinationX/Y/Z` only when `UseDestinationPosition` is true, and the five-property VMADs
above carried no bool, so the script would have taken the plain MoveTo path and ignored the coordinates. Both writers
now add `UseDestinationPosition` (type 5 bool, status 1 edited, value 1) as the sixth property, right after
`DestinationZ`: the exterior VMAD in dotnet/TerrainOverlays (Mutagen `ScriptBoolProperty`), the interior one in
`vmad_patch.py`. #291's psc declares the bool before the three floats; the names and types match, the order does not,
which Papyrus does not care about (it binds by name), and the reader takes both. `load_door_target` refuses a VMAD
with the floats and no bool, with a false bool, or with the bool and no floats; `check_port` and
`make_core64c.door_record_problems` fail on those shapes; the two-property door stays readable.

Both builds were regenerated from this code (the old folders moved aside, not deleted):

- `terrain_core64l`: the same `stage` command as above. FO4TerrainCore.esm 193,631,587 bytes (the first staging +
  405 = 15 doors x 27 bytes for `1600 "UseDestinationPosition" 05 01 01`; core64k + 1,305), sha256 391f3d3c30e4....
  `check --sf-data`: **265 of 265** PASS. Oracle `collision_mesh_keys.py`: 11,768 NIFs, 0 violations. `compare-ids
  --against terrain_core64k`: every section identical, `doors` (15) included; formids.json, objects.json, plan.json and
  FO4TerrainCore_Mars.esm are byte-identical (sha256) to core64k's and to the first core64l's. Raw record diff against
  the first core64l (`core_rawdiff.py`): 683,794 records both, 683,779 identical in bytes and group, exactly the 15 door
  REFRs differ (the VMAD), none regrouped, TES4 identical.
- `integ_1018_doors2` = `vmad_patch.py port --port integ_1018 --core terrain_core64l`: FO4Port.esm 4,087,389 bytes (+405
  against the first port), sha256 945528ce02dc...; `check` PASS, **49 of 49**.
- An independent raw read (stdlib only, `C:\Modding\scratch\usedest\raw_vmad_check.py`): all 30 door VMADs (15 per
  side) are the six-property shape, every status edited, the bool 1, the values recomputed from objects.json and
  overlays_params.json.

Logs: `C:\Modding\scratch\usedest\*.log`. Still no script in game reads these properties: the PEX must ride an
active plugin's archive and #291 is a draft.

## Open (Step 0 in game decides)

- ~~Whether a temporary exterior marker resolves from inside the interior (the return trip).~~ It does not
  (2026-10-16, door_trip_sdm_1018); answered by "Return trip" below: the marker itself became persistent (no twin, no
  fourth id), and `MoveTo` offsets are ignored across the world switch, so the coordinates are three VMAD properties
  applied with `SetPosition` after the MoveTo instead of `OffsetX/Y/Z`.
- ~~Whether `Game.GetFormFromFile` takes the plugin-local id (the FO4 convention) in Starfield.~~ It does (the forward
  trip resolved `FO4Port.esm` 57087 = 0x00DEFF and moved the player onto it).
- Whether MoveTo on the interior marker lands the player on the floor (arrival z = the door z on both sides of the
  first pair; FO4 put it there). The forward trip's first interior bridge line read z -3.6368 at 0.02 m from the
  marker (z -3.6536): on the floor for this door (door_trip_judge.json); the other 14 are unrun.
- The return trip in game: MoveTo onto a persistent exterior marker, then one SetPosition of 1.2 / 2.7 km. Probe (e)
  moved the player there in 15 setpos hops of at most 180 m per axis (single jumps of 3 cells or more raised
  "Boundary Reached" or hung in earlier runs); one large SetPosition from a script is untested (PR #291 says so too).
- PR #291 (Codex, draft) applies `DestinationX/Y/Z` only when its bool `UseDestinationPosition` is true. Both writers
  now write that bool (true, sixth property, "Restage with the bool"); the script itself is not on main yet, and its
  declaration order (the bool before the floats) differs from the written order, which binds by name.
- FO4SF_LoadDoor.pex must be packed into an active plugin's archive (loose scripts are not read on this install): the
  stage does not place it; the deploy step must.

## Protecting the pinned interior source

The proposed door-stage preservation repair preflights every selected REFR for an
existing VMAD before modifying any door. Even an empty or matching load-door VMAD
is refused: merging existing behavior needs its own reviewed policy. Marker-map
collisions also refuse before creating output. A stage/report cannot be placed
inside either pinned input directory.

The plugin, formids.json, README.txt and door reports are generated independently;
reserved names are matched case-insensitively. Old doors_check.json is not carried
into a new stage. Each generated write replaces its destination through a new
file, so a checker run on an old hard-linked report cannot truncate the source.
Failed replacement preserves the old report and removes its temporary file.
This protects individual writes; it does not make the entire directory build a
transaction or authorize installation. Unchanged assets remain hard-linked.

Offline: nine new synthetic regressions plus seven existing codec/plugin tests
pass; successful plugin/map bytes match the parent writer exactly. No private
stage was rewritten and no native door/save test was run. Independent QA remains
required before integration.
