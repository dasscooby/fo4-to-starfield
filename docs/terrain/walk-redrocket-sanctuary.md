# Walking Red Rocket <-> Sanctuary on core64c (runner kind `walk`)

Author: Claude, 2026-10-13. Branch `claude/walk-redrocket-sanctuary`, stacked on `claude/integration-1013` (PRs #59,
#68, #73, #75, #76, #77, #78, #79, #66 and Codex's #80, #81, #83, #86, #89, #100 merged there, plus main 3b0bfb7).
Status (checked 2026-11-06, Mountain): **walk gate PASS recorded on core64c and core64d**
(254 m Red Rocket <-> Sanctuary, |dz| <= 0.14 m); see
[commonwealth-build-plan.md, section 0](commonwealth-build-plan.md#0-what-already-exists-so-the-scale-up-is-not-more-cells)
(2026-10-15). Route and runner checks below retain their original offline evidence.
Labels: **verified** = checked here (file, command or test named); **supported** = supported hypothesis;
**unresolved**; **refuted**. Offline checks and sandbox runs are not in-game acceptance.

The owner's acceptance (docs/CODEX-HANDOFF.md) starts with: "Walk Red Rocket-Sanctuary and its bridge/cell borders both
ways; prove terrain remains loaded. [...] Initial COC/ray hops are setup/loading evidence, not walking or door
acceptance." Every terrain test so far dropped the player onto points (teleports); this kind makes the player walk.

## What one test does
1. `coc FO4Core_RedRocketSpawn`, the arrival read until two reads 3 s apart agree (Read-Settled). The overlay's merge
   offset is O = arrival - `spawn_local` (core64c's runs read (-1200.0029, -2700.0043, ~0)). Time of day 12 is set as
   for terrain tests (daylight screenshots; the walk's verdict does not depend on it).
2. The reverse test only: ONE teleport to the route's start (the cul-de-sac), 1 m above its ground, then the landing
   read until it settles. This is setup, not walking evidence; it moves 92.49 m in x and 146.24 m in y, inside the
   teleport rule of docs/terrain/core64c.md (at most 200 m per axis, **supported**).
3. The walk, leg after leg, until the controller says done or stop. One leg:
   - one console session: `ClearConsole`, `player.getpos x`, `player.getpos y`, `player.getpos z`, the console OCR'd
     with `parse_npc.py` (only what follows this session's start is read, and a position needs all three values from
     it; a failed read, and the second read of an implausible move, is a fresh session of the same kind: never
     `readpos.ps1`, whose `parse_getpos.py` takes the last X, Y, Z anywhere on screen and could join this session's
     x / y with an older z. Each leg records which path read it: `via`, `read_how`, `reread_via`);
   - the controller (`scripts/game/walk_eval.py steer`) decides on that read: which waypoint is next, the heading,
     how long to hold W; `player.setangle z <heading>` is typed in the same session and the console closed;
   - W is held for that time with `input.ps1`'s new **guarded hold** `holdg:w,<ms>`: the foreground is checked every
     50 ms and the key is released at once when the game loses it (the step then stops with exit 2, as every guard);
   - the owner's stop controls are honoured inside the walk (the runner is blocked in the step while it runs): the
     STOP files `testqueue.py` honours (the queue's `STOP`, the chain folder's `STOP_ALL`, `testqueue.STOP`; passed in
     the spec as `stop`) are tested before every action and during the hold (`holdg`, `FO4SF_STOP_FILES`), the
     Resource Guardian once per leg (`walk_eval.py steer`). A stop ends the step like a guard stop: exit 2, nothing
     more typed, `obs.json` with the legs so far and `stopped`; the runner counts no attempt;
   - one screenshot: the HUD (`hud_visible.py`; when it is gone the step waits up to 20 s for it and records the gap)
     and the screen centre's text (`ocr.ps1` on the region 320, 150, 640 x 330): "BOUNDARY REACHED" ends the walk and
     nothing is pressed to close it. The box leaves the HUD on screen, so a HUD check alone would miss it
     (**verified** on Codex's capture `02-nearby-baseline_0001.../a1/beyond.png`: oxygen ring and health bar bright,
     Windows OCR of that region read "BOUNDARY REACHED" in 0.5 s);
   - every leg records the console lines it typed. During the walk only `ClearConsole`, `player.getpos` and
     `player.setangle` are typed: **never a setpos** (the judge checks every leg's list).
   A screenshot is kept every `shot_every` (3) legs and at every event (popup, HUD gap, detour).
4. The end screenshot. The runner records the experiment install record with the result (`results.jsonl` `install`:
   the staged folder, the plugins and the sha256 of every installed file, the packed archive included, and of every
   staged input) and checks it against the experiment the queue pinned when it was planned (`queue.json`
   `experiment_identity`: `plan-walk --install-exp` / `--plugins`, the sha256 of the plugins and the Data tree). A
   changed staged folder stops the runner before a launch; a missing, incomplete or different install record turns a
   PASS or FAIL into INCONCLUSIVE INSTALL (the raw verdict kept in the detail) and stops the run.

The controller (`walk_eval.py`, plain Python, one call per leg): a waypoint counts as reached within its radius (2.5 m;
1.2 m at corners and their lead points; 3 m at the goal), or once the player is past it along the route (only within
twice its radius for a waypoint the plan keeps). A leg aims at the next waypoint, or straight past waypoints the plan
does not keep while they stay within 1 m of the line (at most `max_leg_m` 15 m); the hold is the distance over the
measured speed (start 4.6 m/s, the run measured in 2026-10-08's route runs; then the mean of the last estimate and the
last leg, 1.5..8 m/s), 0.4..8 s. After a leg without movement (< 0.6 m) it steps aside (+50, then -50 degrees, 1 s).
It stops: goal; stuck (3 legs without movement, or 6 legs without 1 m of progress along the route); off the route
(10 m); far below the route (15 m: falling through the world); a jump (a move faster than 9 m/s over the hold plus
2 s, read twice: two agreeing reads stop the walk, a second read that is plausible is taken and the first counted as
an OCR misread); the leg budget (`max_legs`); the step's time budget.

## The route (offline, `scripts/terrain/walk_route.py`, verified)
```
python scripts/terrain/walk_route.py plan --fo4 <Fallout4.esm> --core C:\Modding\staging\terrain_core64c --out C:\Modding\staging\walk_core64c
```
22 s; byte-identical output when run again (route.json, plan.json, walk_ground.json and README.txt compared).
1. **Fallout 4's own navmesh.** The NAVM records of Fallout4.esm, worldspace Commonwealth, FO4 cells x -21..-15,
   y 17..24 (the area +- 60 m and one cell): 152 records, 99,419 triangles, joined over shared edges and edge links
   (`src/fo4sf/navmesh.py` parse; deleted triangles left out). A* over triangle centroids from the Red Rocket arrival
   over the middle of the NorthBridge deck (a via point: navmesh also covers the river bed under it) to the cul-de-sac
   (`SancRoadLoop01`, `0788BD:Fallout4.esm`: the loop pieces turn about it); the funnel through those 223 corridor
   triangles (9 navmeshes) is Fallout 4's own shortest path: **248.73 m**.
2. **Why not walk that path as is.** Checked against core64c's converted collision (a standing capsule of 0.35 m
   radius from 0.4 m above the ground to 1.8 m), the funnel path is blocked at 33 of 499 samples (route.json
   `fo4_path_capsule`): guardrails (`GRailStrShort01`, `GRailEnd01Haz`, `GRailCurveRampL01`), a station wagon
   (`StationWagon01_PreWar`), a trash can, a picket fence post, a swing set, a tree stump and the elm at the
   cul-de-sac (`TreeElmFree01`). Fallout 4's baked navmesh runs under these objects; why (for example navmesh cut
   out around them at run time) is **unresolved**, not checked. The converted collision decides here.
3. **A walkability raster** of a 25 m band around that corridor, 0.5 m cells in core64c's local frame (FO4 position
   / 70): a cell is walkable when Fallout 4's navmesh covers it (where navmesh layers overlap, the one nearest the
   corridor's own layer: the ground under the Red Rocket canopy and not its roof, the bridge deck and not the river
   bed), the ground under it (the BTD terrain, or a converted object's upward surface: road, deck, kerb) lies within
   1 m of the navmesh, and no converted collision stands in the capsule above it (every collision triangle sampled
   every 0.2 m). 350 x 391 cells: 52,118 on navmesh, 4,632 blocked, 47,343 walkable.
4. **The walked path:** A* over the raster (8 neighbours, at most 0.4 m rise between cells, a cost for passing closer
   than 2 m to anything not walkable) start -> the deck -> the goal, pulled straight wherever a 0.75 m clearance
   holds, corners that see each other merged. **254.33 m**, 14 corners. Exact checks every 0.5 m (510 samples): the
   capsule (`exterior.capsule_hits`) meets no converted collision anywhere, every sample on the navmesh; the steepest
   0.5 m step is a 0.335 m rise from `SancRoadBlock02` onto `SancRoadCrv01` at s 158.4 (33.9 degrees), every other
   step is lower. The raster's clearance along the walked path is at least 1.0 m (1.5 m along the A* cells).
5. **Waypoints:** at most 12 m apart, 8 m on the bridge, 4 m before and after every turn of 30 degrees or more, 2 m
   before and after every cell border; points closer than 1 m merged. 43 waypoints (gaps 1.2..10.5 m), 21 of them
   kept (the start, the goal, corners, borders, everything on the bridge: the runner reads the player there). An
   ideal walker run through the controller needs 27 to 32 legs (true speed 3.5 to 6 m/s, heading noise +-8 degrees).

| | |
|---|---|
| Length | 254.33 m (Fallout 4's navmesh shortest 248.73 m) |
| Local cell borders (100 m cells; O is whole cells, so the game's borders are the same lines) | x = -1000 at s 12.5 m, x = -1100 at s 128.4 m (on the bridge), y = 1200 at s 137.4 m (on the bridge), x = -1100 at s 232.3 m; cells (-10, 11) -> (-11, 11) -> (-12, 11) -> (-12, 12) -> (-11, 12); in the game's frame (-22, -16) -> (-23, -16) -> (-24, -16) -> (-24, -15) -> (-23, -15) |
| Fallout 4 cells (58.5 m) crossed | 10: (-17, 19) ... (-19, 22), informational |
| Bridge | `FO4Core_northbridge` (`01F970:Fallout4.esm`): 44.47 m of the path on its deck (s 102.43..146.90), 8 waypoints on it; the deck rises from 107.82 to 109.85 and falls to 107.86 (an arch; the river bed under it 102.8..104.5) |
| Ground under the waypoints | terrain, and the converted objects `roadaskirt*` (the road to the bridge), `northbridge`, `sancroadend01`, `sancroadcrv01`, `sancroadloop01`, `grassmoundhalves08`, `swisland9x1str01` (the Red Rocket pump island the arrival stands on) |
| Reverse setup teleport | 92.49 m in x, 146.24 m in y from the arrival; nothing in the capsule at the landing |
| Pinned | core64c `FO4TerrainCore.esm` sha256 924e182b... (route.json), walk_ground.json sha256 20b7c4a3f9d1c735... (plan.json, checked when planning and again when judging) |

Forward waypoints (the reverse test uses them backwards; s along the route, local frame, z the expected ground):

| wp | s (m) | x | y | z expected | stands on | kind | read kept |
|---|---|---|---|---|---|---|---|
| 00 | 0.0 | -989.26 | 1146.51 | 105.26 | swisland9x1str01 | start | yes |
| 01 | 10.5 | -998.38 | 1151.71 | 105.33 | terrain | border | yes |
| 02 | 14.5 | -1001.86 | 1153.69 | 105.37 | terrain | border | yes |
| 03 | 24.7 | -1010.75 | 1158.75 | 106.73 | terrain | bend 7 deg |  |
| 04 | 33.2 | -1017.55 | 1163.85 | 107.38 | terrain | lead |  |
| 05 | 37.2 | -1020.75 | 1166.25 | 107.56 | roadaskirtend01 | corner 39 deg | yes |
| 06 | 41.2 | -1024.75 | 1166.08 | 107.60 | roadaskirtend02 | lead |  |
| 07 | 51.1 | -1034.62 | 1165.67 | 107.54 | roadaskirtcurvel02 | fill |  |
| 08 | 61.0 | -1044.50 | 1165.25 | 107.71 | roadaskirtcurvel02 | fill |  |
| 09 | 70.9 | -1054.38 | 1164.83 | 107.52 | roadaskirtend02 | fill |  |
| 10 | 80.8 | -1064.25 | 1164.42 | 107.78 | roadaskirtcurvel01 | lead |  |
| 11 | 84.8 | -1068.25 | 1164.25 | 107.87 | roadaskirtcurvel01 | corner 35 deg | yes |
| 12 | 88.8 | -1071.61 | 1166.41 | 107.83 | roadaskirtcurvel01 | lead |  |
| 13 | 95.1 | -1076.93 | 1169.83 | 107.78 | roadaskirtcurvel01 | fill |  |
| 14 | 101.4 | -1082.25 | 1173.25 | 107.68 | roadaskirtend02 | bend 16 deg |  |
| 15 | 103.4 | -1083.59 | 1174.75 | 107.82 | northbridge | bridge | yes |
| 16 | 111.1 | -1088.69 | 1180.46 | 109.04 | northbridge | fill | yes |
| 17 | 118.7 | -1093.79 | 1186.17 | 109.64 | northbridge | fill | yes |
| 18 | 126.4 | -1098.89 | 1191.89 | 109.85 | northbridge | border | yes |
| 19 | 130.4 | -1101.55 | 1194.87 | 109.71 | northbridge | border | yes |
| 20 | 135.4 | -1104.88 | 1198.60 | 109.34 | northbridge | border | yes |
| 21 | 139.4 | -1107.55 | 1201.58 | 108.93 | northbridge | border | yes |
| 22 | 145.9 | -1111.88 | 1206.43 | 107.86 | northbridge | bridge | yes |
| 23 | 150.2 | -1114.72 | 1209.61 | 107.38 | sancroadend01 | fill |  |
| 24 | 154.4 | -1117.56 | 1212.79 | 107.58 | terrain | lead |  |
| 25 | 158.4 | -1120.25 | 1215.75 | 107.89 | sancroadcrv01 | corner 72 deg | yes |
| 26 | 162.4 | -1118.46 | 1219.33 | 108.03 | sancroadcrv01 | lead |  |
| 27 | 166.2 | -1116.75 | 1222.75 | 107.92 | sancroadcrv01 | corner 63 deg | yes |
| 28 | 167.5 | -1115.75 | 1223.25 | 107.65 | terrain | bend 27 deg |  |
| 29 | 170.2 | -1114.87 | 1225.90 | 107.48 | terrain | lead |  |
| 30 | 177.9 | -1112.44 | 1233.18 | 107.56 | terrain | fill |  |
| 31 | 185.6 | -1110.01 | 1240.46 | 107.86 | terrain | lead |  |
| 32 | 189.6 | -1108.75 | 1244.25 | 108.75 | terrain | corner 59 deg | yes |
| 33 | 193.6 | -1111.35 | 1247.29 | 109.01 | terrain | lead |  |
| 34 | 198.8 | -1114.75 | 1251.25 | 109.62 | terrain | corner 61 deg | yes |
| 35 | 202.8 | -1113.37 | 1255.00 | 110.01 | terrain | lead |  |
| 36 | 211.9 | -1110.25 | 1263.50 | 110.76 | terrain | fill |  |
| 37 | 220.9 | -1107.13 | 1272.00 | 110.74 | terrain | lead |  |
| 38 | 224.9 | -1105.75 | 1275.75 | 111.04 | terrain | corner 34 deg | yes |
| 39 | 230.3 | -1101.36 | 1278.86 | 111.58 | terrain | border | yes |
| 40 | 234.3 | -1098.09 | 1281.17 | 111.79 | terrain | border | yes |
| 41 | 244.3 | -1089.92 | 1286.96 | 111.37 | sancroadloop01 | fill |  |
| 42 | 254.3 | -1081.75 | 1292.75 | 111.34 | grassmoundhalves08 | goal | yes |

The path north of the bridge crosses Sanctuary's lawns between the houses, as Fallout 4's own funnel does, rather
than following the streets; the goal is 3.26 m from the loop's centre (the centre itself has no navmesh, and the
elm stands there).

## Evidence rules (the judge, `walk_eval.judge`)
Positions are judged in core64c's local frame (read - O). The judge's ground is `walk_ground.json` in the staging
folder (sha256 pinned in the test): the BTD window around the route (bilinear, as `make_core64c.Terrain`; core64's
probes read FO4 height / 70 within 0.01 m in game, **verified** 2026-10-11) and the upward collision surfaces of every
converted object within 12 m of the path (0.5 m grid, 14,255 nodes, 515 objects).

**PASS** only when all of these hold:
- the leg records themselves hold up, checked before any geometry: legs 0, 1, 2, ... in order with every one but the
  last an "aim", each `used` the leg's own `read` or `reread` (a confirmed jump with the re-read that confirmed it),
  every aim leg with its typed lines, hold and HUD check recorded and its screenshot where the step keeps one (every
  `shot_every` legs and at an event);
- the merge offset comes from the settled arrival alone (`spawn_read` with `spawn_settled`, its last two reads
  agreeing within 0.3 m; the step's own `offset` has to agree, it decides nothing) and the first leg was read within
  `start_tol` (3 m) of the arrival (the setup landing for the reverse test): the walk starts where the player stood;
- the last read is within `goal_radius` (3 m) of the goal;
- every leg was read (`used`), every move between two reads is plausible for walking (at most 9 m/s over the hold
  plus 2 s per leg, + 1 m);
- every read stands within `z_tol` (0.6 m) of the terrain or of a converted object's surface near it (0.75 m);
- every planned cell border was crossed between two consecutive reads: the reads stand in the local frame (read - O,
  so the measured offset need not be cell-aligned) and the planned crossings are matched in route order, one observed
  crossing for one planned;
- at least `bridge.min_reads` (2) reads stood on the bridge deck's surface, with reads before and after the bridge;
- every console line typed during the walk was `ClearConsole`, `player.getpos` or `player.setangle`;
- no popup was seen, the HUD never went away, the arrival screenshot and every kept leg screenshot exist.

**FAIL** (the first failing leg decides, a popup first): `BOUNDARY` (the "BOUNDARY REACHED" box on screen), `FELL`
(a read more than `fell_m` 3 m below the terrain: no ground there; or more than 3 m below the route's surface, e.g.
off the bridge deck onto the river bed), `HEIGHTS` (below every known ground by more than 0.6 m but less than 3 m),
`JUMP` (an implausible move that a second read confirmed: a relocation), `OFFROUTE` (more than 10 m from the route),
`STUCK` (the controller's stuck: no movement after two side steps, or no progress along the route in 6 legs).

**INCONCLUSIVE** (retried once, never a PASS): `POPUP` (any other recorded popup, e.g. FAST TRAVEL or PLANET MAP), `UNREAD` (a leg not read), `READ` (an implausible move not confirmed),
`OFFGROUND` (above every known surface by more than 0.6 m: standing on something not converted, or mid-step),
`HUDGAP`, `NOHUD`, `NOTREACHED` (leg or time budget used up short of the goal), `RUNCOND` (planned with
`--speedmult`: the player's speedmult was not read as 100 before the travel, so the speed model and the JUMP / STUCK
limits did not hold; testqueue.py judge, docs/ai/test-queue.md), `CROSSING` (a planned border not crossed
between two consecutive reads, in route order), `BRIDGE`, `NOSHOT`, `TYPED` (anything else typed during the walk, e.g. a recovery teleport), `START`
(the reverse test's setup landing not read or more than 3 m off; the first leg read more than `start_tol` from the
arrival / the landing), `ANCHOR` (no merge offset: the arrival not read, not settled, or the recorded offset not the
settled arrival's), `GROUND` (walk_ground.json missing or changed), `LEGS` (legs missing, out of order, or a stop before the last one), `EVIDENCE` (a `used` that is
neither the leg's read nor its re-read, a confirmed jump without its re-read, an aim leg without its typed lines, hold,
HUD check or kept screenshot).

Not shown by a PASS: interiors and load doors, stairs, door collision, NPCs, anything beyond the route's 12 m corridor,
streaming farther than 300 m from the arrival, daylight materials.

## How to read a result
`C:\Modding\testqueue\walk_core64c\report.md` (verdicts), `results.jsonl` (one line per attempt: verdict, class,
detail with reads, walked metres, |dz|, the objects stood on, cells seen; `install`: the installed plugins' and
archive's sha256), `tests\<id>\a<n>\`: `obs.json` (`spawn_read` / `offset`, `setup`, `legs`: per leg `read`, `used`,
`reread`, `via` / `read_how` / `reread_via` (which read path and parse_npc reading gave each value), `local` (the local
frame), `wp`, `heading`, `hold_ms`, `hud`, `popup`, `cmds`, `shot`; `walk_stopped`),
`walk_NNN.png` (kept leg screenshots), `arrival.png`, `setup.png`, `end.png`, `walk_state.json` (the controller's
state). The route itself: `C:\Modding\staging\walk_core64c\route.json` (both directions, every waypoint's expected
ground and source, the report) and `README.txt`.

## Staged, queued, and how to run it
Staged: `C:\Modding\staging\walk_core64c` (README.txt, plan.json, route.json, walk_ground.json; 1.3 MB). The runner
installs core64c itself (`C:\Modding\staging\terrain_core64c`, `verify-data` 2026-10-13: 51,823 files unchanged since
its check); nothing of core64c is copied.

Planned (`C:\Modding\testqueue\walk_core64c`, this branch's runner, build integ_1011 2470f876, fresh launch per test):
```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
& $py scripts\game\testqueue.py plan-walk --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\walk_core64c `
      --install-exp C:\Modding\staging\terrain_core64c --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm `
      --out C:\Modding\testqueue\walk_core64c --fresh
```
queue.json (planned at commit b5822a3): build 2470f876, `needs` = light, walk; `pre_launch` = this checkout's
`exp_install.py install --exp-dir C:\Modding\staging\terrain_core64c --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm
--pack --needs light,walk`; tests `0000_walk_walk_redrocket_to_sanctuary` (step limit 4,597 s) and
`0001_walk_walk_sanctuary_to_redrocket` (setup teleport; 5,030 s), both fresh, 43 waypoints, at most 57 legs, local
noon, walk_ground.json 20b7c4a3f9d1c735....

To run, from a checkout of this branch (the walk kind is not in the integration worktree's runner, which refuses the
queue: runner feature `walk`), with the game closed and no other runner active:
```powershell
& $py scripts\terrain\make_core64c.py verify-data --out C:\Modding\staging\terrain_core64c
& $py scripts\game\exp_install.py status --starfield D:\SteamLibrary\steamapps\common\Starfield
#   another experiment installed (on 2026-10-13: slice_redrocket_door_b)? uninstall it first (its record names it):
& $py scripts\game\exp_install.py uninstall --starfield D:\SteamLibrary\steamapps\common\Starfield
& $py scripts\game\testqueue.py run --queue C:\Modding\testqueue\walk_core64c --max-attempts 2 --wait-for-idle --refocus
& $py scripts\game\testqueue.py report --queue C:\Modding\testqueue\walk_core64c
```
Expected time: the first launch packs core64c's 3.63 GiB stored archive in %TEMP% and installs it (several minutes;
later launches find it installed), each fresh launch with the dedicated save and god mode about 4 min, the arrival
and light about 2 min, the walk 27 to 32 legs of about 33 s (console session, typing at 0.24 s a character, OCR, the
hold, the screenshot checks): 15 to 18 min. About 25 min a test, **about 1 hour** for both; a retry of an
INCONCLUSIVE adds up to 25 min. The step's own limit is 4,597 s / 5,030 s (57 legs worst case); the step stops
walking 150 s before its budget (limit - 60 s), so a cut-off keeps every leg already read.

## Tests
- `tests/test_terrain_walk_route.py`: edge links joining two navmeshes, A*, the funnel bending only at an inner corner,
  short portals, layer choice (canopy / bridge), the blocking raster (a wall blocks within the capsule only, a kerb
  does not), the raster A* round a wall and never up a cliff, line of sight with clearance, waypoints at corners and
  on the bridge, merged corners, cell crossings.
- `tests/test_walk_eval.py`: plan-walk (validation, queue needs and pre_launch, the experiment pinned by its staged
  inputs), the stop controls inside the walk, a changed experiment stopping before the launch, a walk result without
  the pinned install record (INCONCLUSIVE INSTALL), the controller (waypoint by waypoint, past a waypoint, lookahead past waypoints not kept, side steps then
  stuck, a misread read again, a confirmed and an unconfirmed jump, off the route, falling, unread, leg budget, the
  hold cap) and the judge (PASS through testqueue, every FAIL and INCONCLUSIVE class above).
- `tests/test_qstep_sandbox.py` `QstepWalkSandboxTests` (opt-in `FO4SF_QSTEP_SANDBOX=1`): the real step against a
  simulated ground (a slope, a raised deck, cell borders, a merged offset; the fake game walks along the heading, with
  heading noise): a PASS typing only getpos / setangle; a reverse walk after one setup teleport; a hole in the ground
  (FELL); a boundary box (FAIL BOUNDARY, the popup read from the centre OCR, nothing pressed); a wall (detours, then
  STUCK); an OCR misread (read again, PASS); a straight run past a waypoint not kept; refused specs type nothing.
- An ideal walker through the staged plan judged against the real walk_ground.json: PASS both ways (27 to 32 legs).

## Unresolved / to watch in the first run
- The player's speed and whether the save starts walking or running (the controller measures it; **supported**: 4.6
  m/s run, 2026-10-08) and whether `setangle z` turns the first-person view as it did in the route runs.
- Whether walking over a cell border or onto the bridge shows a loading screen or a popup on the merged overlay
  (exactly what this test is for).
- The capsule size and step height are assumptions (0.35 m, 0.4 m step); a kerb or a deck edge the converted
  collision makes higher than Fallout 4's would show as STUCK. The tallest step on the route is the 0.335 m one at
  s 158.4 (north end of the bridge, `SancRoadBlock02` -> `SancRoadCrv01`): if Starfield's player does not step it,
  the forward walk stops there (STUCK after two side steps) and the reverse walk steps down it.
- Mars's own procedural objects on the overlay (if any) would read as OFFGROUND, not as a FAIL.
