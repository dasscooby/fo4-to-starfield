# Workshop probe: what makes a placed workbench a workshop the game accepts?

Task: FAL-359 (stage plan tracks 7 and 8, settlements and C.A.M.P.s). Status: **built offline, not run in game**
(no Starfield.esm, no ContentResources.zip, no Papyrus compiler, no game on the build box).

## What the PC found on 11 Nov (test save, installed core; written by Claude, not re-run here)

* A workshop **placed in the core's cell** works: Red Rocket garage bench (reference 0D271, base `FO4Core_wkshp_0c1aeb_fallout4`
  local id 0A2ECD, model `workbenchgarage01.nif`, `WorkshopKeyword` 00054BA7 (a Starfield.esm KYWD; the core only points at it) plus seven outpost keywords). Crosshair on it:
  "WORKSHOP / BUILD [E]"; E opens Starfield's build mode (CRAFTING tab with six stations, build limit bar). A second E:
  "Cannot build item: Missing resources" (Industrial Workbench: Aluminum 0/4, Iron 0/3).
* The same base **spawned** (`player.placeatme <core index>0A2ECD 1`, open ground, far from every workshop) stands there, fully
  drawn, `GetIsID` 1, and gives **no prompt**; E does nothing. The vanilla `OutpostPlayerHouseActivator` 00024DC7 spawns too
  (no model, no prompt). No crash. The core has 29 placed workshop references and 2 workshop bases.

## What is built

| Piece | Where |
|---|---|
| Plugin writer (build, check, fixture, survey, resources) | `dotnet/WorkshopProbe` |
| Console quest script, hand quest script | `scripts/planet/FO4SF_WSProbeQuest.psc`, `FO4SF_WSHandQuest.psc` |
| Stage (precheck, scan, resources, stage, log) | `scripts/planet/make_workshop_probe.py` |
| Ride-along installer, own record `Data\FO4SFWorkshopProbe.install.json` | `scripts/planet/workshop_probe_install.py` |
| Log reader | `src/fo4sf/workshop/probe_log.py` |
| Tests | `tests/test_workshop_probe.py`, `_log.py`, `_install.py` |

`FO4SFWorkshopProbe.esm` adds three records and overrides none (a core cell is never overridden, the core-storage runs showed
what that does): QUST `FO4SF_WSProbeQuest` (start game enabled, stages below, no properties), QUST `FO4SF_WSHandQuest`
(one stage, no properties), MISC `FO4SF_WSKit` (a copy of one vanilla MISC, renamed, no script). **Deviation from the task
text:** the master list is `Starfield.esm` only; the installed core is **not** a master. Nothing in the plugin points at a
core record: the scripts find the core's workshop base with `Game.GetFormFromFile(0x0A2ECD, "FO4TerrainCore.esm")` (the
`_Mars` core is tried when that plugin is absent), so the kit loads wherever it sits and never wants a master that is not
there. If the core's base is not at that local id the log says `none`; the id is the 11 Nov PC run's. The workshop keyword is read from Starfield.esm.

### The console quest (stages set with `setstage <index>000800 <n>`; polled once a second)

The console does not know the quest by its editor id (PC, 11 Nov: "Item 'FO4SF_WSProbeQuest' not found"): use the form id, the plugin's load index (the two digits `FO4SFWorkshopProbe.esm` has in the load order, e.g. `0A`) followed by `000800`. The hand quest is `...000801`.

| Stage | What it does |
|---|---|
| 10 | `PlaceAtMe` of the core's workshop base, persistent, 2.5 m ahead (`MoveTo` is optional): the BENCH |
| 20 | logs the sub-stage list; calls nothing |
| 21 / 22 | on the bench: `Disable`, then `Enable` from a timer 2 s later (an Enable in the same call left it disabled, PC 11 Nov); `Activate(player)` by script |
| 23 / 24 | on the bench, optional natives: `SetActorOwner(player base)`; `StartWorkshop(true)` |
| 30 | `PlaceAtMe` of vanilla `OutpostPlayerHouseActivator` 0x024DC7: the PAD, the control for "our base is the problem" |
| 31 to 34 | the same four calls on the pad |
| 40 | `PlaceAtMe` of the vanilla outpost beacon base given to the stager with `--beacon <hex id>`; 0 = says so in the log |
| 12 | `PlaceAtMe` of the bench **not persistent** (moved ahead as in 10): the BENCH_TEMP |
| 13 | `PlaceAtMe` of the bench persistent, **not moved**: the BENCH_STILL. 12 and 13 separate what the PC's stage 10 (persistent + moved: a workshop) changed against the console (temporary, not moved: no prompt) |
| 50 | reading of every spawned reference now |
| 60 | `Disable` + `Delete` every spawned reference |

Every placing stage and every call stage writes the reference's reading before, the call, the reading after and the reading
4 s later: loaded 3D, workshop keyword, disabled, `GetWorkshop` (optional), cell, position, distance. So the log says which
call changed anything. **Whether E gives WORKSHOP / BUILD [E] is not readable by Papyrus: it is the screenshot after each
stage.** Item 2 (leave the cell and come back): whenever the player's cell changes the poll writes a reading of every spawned
reference at once, +2 s and +10 s (`when=arrival...`); the trip itself is the PC's, the log only records what the bench reads on return.

### Names that may not exist

Every workshop or outpost native is a `;OPT` line (`ObjectReference.GetWorkshop` (read in every `read` line as `ws=`), `SetActorOwner`, `StartWorkshop`, plus
`MoveTo`, `Delete`): `precheck` looks each up in the base sources, `stage` compiles each declared one on its own, keeps the
ones that compile, and `plan.json` records the fate (`optional`, `optional_hand`); a name the game lacks logs `na`. The PC's offline pass (11 Nov, real ContentResources.zip) found `IsWorkshop` absent and `Actor.GetActorBase` absent (now `GetLeveledActorBase`); `StartWorkshop`, `SetActorOwner`, `MoveTo`, `Delete` compile. Starfield also declares `SetWorkshopState(int)`, `ShowWorkshopBuilderMenu()`, event `OnWorkshopMode(bool)`: not yet sub-stages here (the PC types them by hand first). The real list is what Starfield declares. Read it first, offline, with
`make_workshop_probe.py scan` (every function of ObjectReference, Game, Location, Form, Actor, Quest and ScriptObject whose
name says workshop, outpost or beacon, and every call line of each base script whose own name says so, i.e. what vanilla's
beacon script calls); `stage` also writes it to `scan.txt`. If the scan shows the natives the guesses missed, the next commit
changes the sub-stage names, not the shape. `WorkshopProbe survey <Starfield.esm>` lists the vanilla records whose editor id
or script says outpost, beacon or workshop (type, local id, editor id, scripts): the beacon base for `--beacon` comes from it.

## Install and read (the owner's word, game closed)

    python scripts\planet\make_workshop_probe.py scan
    python scripts\planet\make_workshop_probe.py precheck
    python scripts\planet\make_workshop_probe.py stage --out <dir> [--beacon <hex>] [--item <MISC editor id>]
    python scripts\planet\workshop_probe_install.py install --dir <dir> --starfield <game dir>
    ... session ...
    python scripts\planet\make_workshop_probe.py log
    python scripts\planet\workshop_probe_install.py uninstall --starfield <game dir>

The log is `My Games\Starfield\Logs\Script\User\FO4SFWorkshop.0.log` (lines `FO4SFWS rt=... <event> key=value ... end=true`);
the by-hand log is `FO4SFWSHand.0.log` (`FO4SFWSHAND ...`, read by eye). The kit pairs with the installed core: THROWAWAY
STATE ONLY, NO SAVE (spawned persistent references stay in a save).

## Session card (PC, console; one answer per stage)

1. Load the test save, stand in open ground away from every fixed workshop. `setstage <index>000800 10`.
2. Crosshair on the bench, press E, screenshot the prompt. **If E opens the build mode it stays open: press Esc after every E that opens it**, or every later prompt is photographed inside build mode. The log has `spawn` and `read` lines.
3. `setstage <index>000800 21`, then E and screenshot (Esc); repeat for 22, 23, 24. After 21 the bench is back 2 s later: wait 5 s before E. Each stage is one call. Stages 12 and 13 (before 20) place the two bench variants; E on each.
4. `setstage <index>000800 30` (the invisible pad), E, screenshot; then 31, 32, 33, 34 as above.
5. If a beacon id was staged: `setstage <index>000800 40`, E, screenshot (Esc).
6. Leave the cell (`coc` to another place, or walk away) and come back. Screenshot the prompt on the bench; the log has the `arrival` lines.
7. `setstage <index>000800 50` for a last reading, then `60` to clean up. For the pad (30), press Esc first if a beacon's build mode is open. `python scripts\planet\make_workshop_probe.py log`.

## By hand (the owner; card of eight steps)

`FO4SF_WSHandQuest` needs no console. It gives a kit item 20 s after the game starts; dropping it places the bench where the
script sees it gone, and says on screen what it read.

1. Install the kit (card above, game closed), start Starfield, load a throwaway save in open ground, away from any workshop.
2. Wait 20 s: the screen says you have a "FO4SF workshop kit".
3. Open the inventory and drop the kit.
4. Within a second the bench stands 2.5 m in front of you and you have a new kit (the dropped one lies on the floor, leave it).
5. The screen says whether the bench is loaded and carries the workshop keyword.
6. Look at the bench: does the prompt say WORKSHOP / BUILD [E]? Press E once.
7. Write down what you saw (prompt, what E did); drop the kit again to place a second bench and compare.
8. Quit without saving. `python scripts\planet\workshop_probe_install.py uninstall --starfield <game dir>`.

If a bench ever opens the build mode, the owner's card for building follows (below).

## Red Rocket card: the resources of the six CRAFTING stations

`make_workshop_probe.py resources --starfield <Starfield.esm> [--out additem.txt]` (and `stage`, into `additem.txt`) reads
Starfield.esm: every COBJ whose created object's editor id matches `Workbench|Lab|Station` (change it with `--match`), its
components and counts, and `player.additem <id> <2 x the largest count>` lines. The COBJ components are resource records (IRES), not items: the tool maps each to the MISC whose body links it (the one named like the IRES without `Res` when several do) and prints `player.additem` for the MISC only. PC-proven: `0000556E` Iron, `0000557D` Aluminum (IRES 0057C7, 0057D6) gave build-mode counts and a built station. The mapping is tested on a synthetic file only; the PC's offline pass on the real file is the check. The lines are
the tool's reading of the real file at stage time; offline it ran on a synthetic Starfield.esm only (Aluminum 4 and Iron 3
-> `additem 00000B02 8`, `00000B01 6`). Paste the lines from `additem.txt` into the console before step 2 of a build, then press
E on the workshop and build; whichever station reads "Missing resources" is a COBJ the match did not catch: widen `--match`.

## Not run, honestly

The Papyrus compile (the PC's compiler); the stage against the real Starfield.esm; ContentResources.zip (not on the build
box: the `scan` output, the fate of every optional native and the beacon id are all still unread); the whole game session.
The beacon base is `OutpostBeaconActivator` 002C60E9 (PC survey): stage with `--beacon 2C60E9`.

## Result of the PC run at 8a3e39b2 (Claude, 11 Nov, third session; not re-run here)

* A bench placed by the script (`PlaceAtMe`, persistent, then `MoveTo` 2.5 m ahead) **is a workshop**: prompt WORKSHOP / BUILD [E], build mode, a station built on open ground far from any placed workshop. It survives leaving the cell and coming back. No extra call was needed (stages 22 to 24 and 32 to 34 changed nothing).
* The same base from the console `placeatme` gave no prompt: the difference is the script's persistent placement (stages 12 and 13 at 40039ed2 split it from `MoveTo`).
* The vanilla beacon `OutpostBeaconActivator` 002C60E9 placed by the script is a full outpost beacon (OUTPOST BEACON / BUILD [E] / RENAME, REMOVE OUTPOST [R]; build mode with the game's first-time box). From the console it gave no prompt.
* `GetWorkshop()` reads None on all of them, also on the working bench: it is not a test of "is a workshop".
* Not answered: the pad (the beacon's build mode was still open: Esc first), a save and reload, no-persist placement, RENAME / REMOVE OUTPOST, map marker, power and cargo, the hand drop.

## Owner card: settlement or C.A.M.P. by hand (written from the PC result; the drop step is untested)

The kit item places a **bench** (a workshop: build a station and settle around it). A beacon variant is not in the hand quest yet.

1. Install the kit (card above, game closed), start Starfield, load a throwaway save in open ground. Do not save.
2. Wait 20 s: the screen says you have a "FO4SF workshop kit".
3. Open the inventory and drop the kit.
4. The bench stands 2.5 m in front of you within a second.
5. Look at it: the prompt must read WORKSHOP / BUILD [E]. Press E: build mode opens.
6. Press Esc to leave build mode whenever you want to photograph a prompt.
7. To build: `player.additem 0000556E 40` and `player.additem 0000557D 40` (Iron, Aluminum; the other station resources are in `additem.txt` and are the tool's reading only), then E on the bench, pick a station, place it.
8. Quit without saving, then uninstall the kit.

## Piece B (the power armor entry by script)

Follows once this is in review: `SetRace` to the kit race on a furniture of ours, our frame and pieces, a value of ours for
"in power armor", the exit that undoes it; first and third person, hand mode, card of eight steps.
