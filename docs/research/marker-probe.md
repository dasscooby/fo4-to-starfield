# Map marker probe: the PC card (FAL-771, FAL-489)

Author: Minuteman. Status: built and tested offline; **no game run, no install, the Papyrus script never compiled** (the stager compiles it on the PC).
Labels follow docs/ai/research-log.md. Inputs: the Papyrus function list (FAL-489 comment d68a0c70), the two offline reads (8876c782, note section 36),
the owner's answer (14 Nov: fast travel unlocks when the first location is discovered).

## What it decides
1. **Shape A or B for the reveal.** Can the new-game exit place and discover markers while the player is still inside the vault cell? If yes (B), the
   ~20 s of placement hides inside the cog door, the walk and the ride, with no reload and no hold. If no (A), the placement and the 31 s reload
   happen at arrival and the only hide is a deliberate beat at the exit (owner's eye, unmeasured).
2. **What "first location discovered" does.** Does `Game.IsFastTravelEnabled()` change when Vault 111 alone is discovered (the owner's unlock), and what
   do the two proxies `IsMapMarkerVisible` / `CanFastTravelToMarker` do. There is no getter for "discovered": the proxies and the PC's eye on the map
   are the measurement.
3. **The landing marker** (needs PR #781's `--landing-undiscovered` map-marker build): does discovering it with the first location draw a label, a
   compass entry or a landing target; and is `AddToMap(false)` a way to list a marker without allowing travel.

## The kit
`python scripts/mapmarkers/make_marker_probe.py stage --out <new dir>` then `marker_probe_install.py install --dir <stage> --starfield <game dir>`
(the owner's word, game closed; Plugins.txt gets `*FO4SFMarkerProbe.esm`; uninstall removes exactly that). The plugin is one quest
(`FO4SF_MarkerProbeQuest`, stages 10 20 30 40 50 60 70, no properties, master Starfield.esm only); no existing record is overridden and nothing of
the map-marker plugin is changed. Run `make_marker_probe.py precheck` first: it lists every native the script calls against ContentResources.zip
(`AddToMap`, `SetMarkerDiscovered`, `IsFastTravelEnabled` ... all from Claude's read; none of them has been compiled by us).
Log: `My Games\Starfield\Logs\Script\User\FO4SFMarkerProbe.0.log`, read with `make_marker_probe.py log`. Every line also shows on screen as `AP ...`.

References (all `Game.GetFormFromFile`, file-local ids): **V111** FO4TerrainCore.esm 0x0A775B (the Vault 111 marker, and the new-game exit anchor: note 36),
**LAND** FO4SFMapMarkers.esm 0x0008F2, **TEST** 0x000900 and **TEST2** 0x000901 (the first two plain markers of the plugin; ids sequential from 0x900 per
dotnet/MapMarkers `ExtraId`, inferred for 0x901). The world is not assumed: every line logs `GetWorldSpace()` of the marker and of the player (note 36: the
core's Commonwealth is 0x000803, `04000803` at run time by load order; the surface `world=` has never been logged).

## Session A (stages 10 to 50; the installed map-marker plugin as it is)
Use a throwaway save. Stages are set one at a time from the console, `setstage FO4SF_MarkerProbeQuest <n>`, **after the last stage's "later done" line** (or,
for 10, 40, 50, its "stage done" line); keep the console closed between them; shots private.
- **Inside**: go to the cog door's cell by the same console line step 0 used (spot x -55, y -2.7, z 0.5 is fine). Wait for the quest's `init` line.
  - `setstage ... 10`: baseline. Record the lines: `fast ... enabled=`, and for each of V111, LAND, TEST, TEST2 `world= cell= visible= canfast=`.
  - `setstage ... 20`: TEST.MoveTo(V111) (the exit's own call, `Surface()` in FO4SF_NewGameQuest.psc), then SetPosition to its own old position + (-1200, -2700, 0).
    Lines `moved`, `set`, `later` (2 s). **Note the world id and the cell on each.**
  - `setstage ... 30`: `V111.SetMarkerDiscovered()` while inside. Lines `before`, `after`, `later` for `fast` and V111.
- **Outside**: go to the Commonwealth by the sessions' own exterior `coc` line. `setstage ... 40`. Then, with no input beyond the map keys: open the surface map;
  shots of the whole map and zoomed on Vault 111 (discovered? is "Fast Travel" offered when it is selected: **do not travel**) and on the spot TEST was moved to; open
  Mars's planet map; shot.
- **Persistence**: save as a new throwaway name, quit to the menu, load it, wait for the game, `setstage ... 50` (the quest's timer must still run; if no line comes, say so,
  that is a finding), the same map shots.
Return: the two log tables (`make_marker_probe.py log`), the shots' descriptions, nothing from the game.

## Session B (stages 60 and 70; needs PR #781 landed and a map-marker build made with `--landing-undiscovered`; its own install authorization)
Same kit, new game or a fresh throwaway save so that LAND is undiscovered: `setstage ... 10`, then `60` (LAND.SetMarkerDiscovered), shot the map and the
planet map and the compass; then `70` (`TEST2.AddToMap(false)`, a marker nothing else touched), shots. Stage 60 on today's plugin (landing marker already
discovered, flags 0x33) tests nothing; do not run it there.

## Reading the result (fixed in advance)
| Question | PASS reading | FAIL / other reading |
| --- | --- | --- |
| Indoor placement (shape B) | after stage 20, TEST's world id **equals** the player's world id at stage 40, its position is within 5 m of the target logged by `move ... target=`, and at stage 40 the map lists it | `moved`/`set` leave world `none` or the vault's world, or the position unchanged, or stage 40 differs: **shape A**, then the exit beat |
| Indoor discovery | stage 30 prints no error and stage 40/50 show V111 discovered on the map | a refusal in the log, or not discovered outside: discover at arrival |
| First-location unlock | `fast ... enabled` goes False to True across stage 30 (or the map offers Fast Travel to V111) | no change: the unlock is something else; say what the map offered |
| Persistence | stage 50 after the load shows what stage 40 showed | a difference is the finding (do not infer a cause) |
| Proxies | record whether `visible` / `canfast` change at stage 30: **a measurement, not pass/fail** | |
| Landing (session B) | record what 60 and 70 add on the map, planet map and compass | |

## Not run, said plainly
No game, no Papyrus compile (the stager's step), no real ContentResources check (precheck runs on the PC), no install. `OnMapMarkerDiscovered` is not used
(remote registration on it is unread). The 0x901 id and the quest timer's survival of a load are inferences. Offline checks are not in-game acceptance.
