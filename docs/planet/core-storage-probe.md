# Core storage probe (FAL-208)

Why: planet probe run 2 (FAL-207 `run-2`, FAL-188 `pc-probe-run2`) read T7 (persistent marker in the spawn cell's own
persistent group) as not loaded, but T5 (the cell-content control) was not loaded either: the probe spawn cell never
loaded, so T7 says nothing about the Commonwealth core. This probe repeats the storage question on a core exterior cell
that is known to load.

Reader (`src/fo4sf/planet/probe_log.py`): T7 not loaded while T5 is also not loaded at that arrival prints
`cell not loaded` (not FAIL); T7 not loaded while T5 is with player or left behind stays FAIL. When OnInit logs twice,
the reader takes the complete init line (every form present), not the empty one (run 2's false "init" PROBLEM).

Plugin `FO4SFCoreStorage.esm` (`dotnet/CoreStorage`, masters `Starfield.esm` + the installed `FO4TerrainCore.esm`):
an override of the core world holding only the override of CELL `FO4Core_RedRocketSpawn` (the world's SubCells are not
cleared), with

| Local id | Record | Where | Position |
|---|---|---|---|
| `0x800` | REFR `FO4SF_CS_P`, XMarker `00003B`, flag `0x400` | the spawn cell's Persistent group | COC marker + (4, 0, 0) |
| `0x801` | REFR `FO4SF_CS_T`, XMarker `00003B` | the spawn cell's Temporary group | COC marker + (8, 0, 0) |
| `0x802` | QUST `FO4SF_CoreStorageProbe`, start game enabled, no stages, script `FO4SF_CoreStorageQuest`, no properties | | |

The script finds both references with `Game.GetFormFromFile` (a property would make CS_T persistent) and logs
`FO4SFCS rt=...` lines 2, 10, 30 and 60 s after each arrival to `FO4SFCoreStorage.0.log`.

Offline: `python scripts/core_storage/make_core_storage.py stage --core <installed FO4TerrainCore.esm> --out <new folder>`
builds, compiles the script, runs `CoreStorage check` (CS_P in the cell's Persistent, CS_T in its Temporary, the cell's
FormKey the core's own, masters exact) and writes plan.json. Install: `scripts/core_storage/core_storage_install.py`.
No plugin bytes enter Git. `tests/test_core_storage.py` runs the tool on a synthetic core.

PC session (Claude): `coc FO4Core_RedRocketSpawn` with roofs on screen.
* CS_T not found: `cell not loaded` (not a failure).
* PASS: CS_T found and CS_P with the player (runtime world, core merge offset about -1200, -2700).
* FAIL: CS_T found and CS_P left behind or not loaded.

Reader: `probe_log.core_storage_result(lines)` reads the FO4SFCS log (control first: CS_T not loaded = cell not loaded).

Out of scope: probe-overlay retarget, core rebuild. Status: offline only; not tested in game.
