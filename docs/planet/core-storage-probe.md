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

## Run 3: the game crashed (FAL-273 item 3)

**Verified** (Claude's report on FAL-208, 10 Nov 19:54 UTC, head 1184cb0e): `coc FO4Core_RedRocketSpawn` with the kit
installed; `arrive` logged; 32 s after the arrival the game ended with 0xC0000005, a read of 0x1f0 at `Starfield.exe+0x41efd6`
on a worker thread (caller `+0x41f1d1`). The control (same save, same command, only the owner's own set, no
`FO4SFCoreStorage.esm`) ran 150 s without a crash. One run each: **supported, not proven**, that the add-on's override is
what the engine reads as a null when the core's content arrives. No reading after the reload exists, so the storage
question is still open.

**What the plugin does that the core cell does not** (offline, on the synthetic core; the real core was not available here):

* a WRLD override of the core's world (every field copied, `SubCells` and the persistent cell left out) whose only child is
* the override of the core's spawn cell, copied by field with **no children**, then given
* its own **Persistent** child group holding CS_P (flag 0x400) and its own **Temporary** group holding CS_T.

In the core the cell's children are the core's (its terrain and its references); in the override they are two XMarkers. The
engine merges child groups by form id. Which of the three differences is the null is **unresolved**; the ranked guesses
(none verified): (1) the persistent reference in an exterior cell's *own* Persistent group (vanilla keeps persistent
references of a world in its persistent cell); (2) the override cell's fields as Mutagen copied them (a field the core's
twin has and the copy lacks); (3) the world override's copied fields.

### Two tools, so the next run decides

1. **The override beside its twin**, no game, raw bytes of two files:

       python scripts\core_storage\twin_dump.py <FO4SFCoreStorage.esm> <FO4TerrainCore.esm> --out twin.txt

   Prints, for the WRLD and the CELL: the group chain, header flags and version, every subrecord side by side with a verdict
   (`same`, `differs at byte N`, `ONLY IN THE CORE (the override lost it)`, `only in the override`) and the cell's child
   groups of the core and of the plugin. The report holds game bytes and stays on the PC; verdicts and offsets go to Git.
2. **The variant ladder** (`make_core_storage.py stage --variant <v>`, same plugin name, same masters, same quest and script):

   | Variant | Writes | A crash says |
   |---|---|---|
   | `cell-only` | world and cell overrides, no reference | the override of the world or the cell itself |
   | `world-only` | the world override alone | the world override |
   | `temp-only` | cell + CS_T | CS_T, or the cell with a Temporary group |
   | `persist-only` | cell + CS_P | the Persistent group of an exterior cell |
   | `full` | everything (run 3) | crashed |

   Order: `cell-only` first. No crash: the references are the cause, run `persist-only` (and `temp-only`). Crash: run
   `world-only`. Three runs at most name the part. Each run is the card of the probe: stage, install, `coc
   FO4Core_RedRocketSpawn` within the first two minutes, stay 100 s or more, read the log. A crash or its absence at about 32 s
   after the arrival is the result; the reader's verdict does not matter for the ladder.

Not run here: the real core and the game (twin report, ladder). The variants were built and checked against the synthetic
core; the `full` variant is byte-identical to the plugin of run 3's build on that core.
