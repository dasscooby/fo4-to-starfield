# Workshop probe: what makes a placed workbench a workshop the game accepts?

Task: FAL-359 (stage plan tracks 7 and 8, settlements and C.A.M.P.s). Status: **built offline, not run in game**
(no Starfield.esm, no ContentResources.zip, no Papyrus compiler, no game on the build box).

## What the PC found on 11 Nov (test save, installed core; written by Claude, not re-run here)

* A workshop **placed in the core's cell** works: Red Rocket garage bench (reference 0D271, base `FO4Core_wkshp_0c1aeb_fallout4`
  local id 0A2ECD, model `workbenchgarage01.nif`, `WorkshopKeyword` 00054BA7 plus seven outpost keywords). Crosshair on it:
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
there. If the core's base or the workshop keyword 054BA7 is not at that local id, the log says `none`; the ids are the
11 Nov PC run's, and 054BA7 is Fallout 4's id, **not verified in the core**.

### The console quest (stages set with `setstage FO4SF_WSProbeQuest <n>`; polled once a second)

| Stage | What it does |
|---|---|
| 10 | `PlaceAtMe` of the core's workshop base, persistent, 2.5 m ahead (`MoveTo` is optional): the BENCH |
| 20 | logs the sub-stage list; calls nothing |
| 21 / 22 | on the bench: `Disable` + `Enable`; `Activate(player)` by script |
| 23 / 24 | on the bench, optional natives: `SetActorOwner(player base)`; `StartWorkshop(true)` |
| 30 | `PlaceAtMe` of vanilla `OutpostPlayerHouseActivator` 0x024DC7: the PAD, the control for "our base is the problem" |
| 31 to 34 | the same four calls on the pad |
| 40 | `PlaceAtMe` of the vanilla outpost beacon base given to the stager with `--beacon <hex id>`; 0 = says so in the log |
| 50 | reading of every spawned reference now |
| 60 | `Disable` + `Delete` every spawned reference |

Every placing stage and every call stage writes the reference's reading before, the call, the reading after and the reading
4 s later: loaded 3D, workshop keyword, disabled, `IsWorkshop` (optional), cell, position, distance. So the log says which
call changed anything. **Whether E gives WORKSHOP / BUILD [E] is not readable by Papyrus: it is the screenshot after each
stage.** Item 2 (leave the cell and come back): whenever the player's cell changes the poll writes a reading of every spawned
reference at once, +2 s and +10 s (`when=arrival...`); the trip itself is the PC's, the log only records what the bench reads on return.

### Names that may not exist

Every workshop or outpost native is a `;OPT` line (`ObjectReference.IsWorkshop`, `SetActorOwner`, `StartWorkshop`, plus
`MoveTo`, `Delete`): `precheck` looks each up in the base sources, `stage` compiles each declared one on its own, keeps the
ones that compile, and `plan.json` records the fate (`optional`, `optional_hand`); a name the game lacks logs `na`. **These
four workshop names are guesses from Fallout 4**; the real list is what Starfield declares. Read it first, offline, with
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

1. Load the test save, stand in open ground away from every fixed workshop. `setstage FO4SF_WSProbeQuest 10`.
2. Crosshair on the bench, press E, screenshot the prompt. The log has `spawn` and `read` lines.
3. `setstage FO4SF_WSProbeQuest 21`, then E and screenshot; repeat for 22, 23, 24. Each stage is one call.
4. `setstage FO4SF_WSProbeQuest 30` (the invisible pad), E, screenshot; then 31, 32, 33, 34 as above.
5. If a beacon id was staged: `setstage FO4SF_WSProbeQuest 40`, E, screenshot.
6. Leave the cell (`coc` to another place, or walk away) and come back. Screenshot the prompt on the bench; the log has the `arrival` lines.
7. `setstage FO4SF_WSProbeQuest 50` for a last reading, then `60` to clean up. `python scripts\planet\make_workshop_probe.py log`.

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
components and counts, and `player.additem <id> <2 x the largest count>` lines. **No resource id is verified**: the lines are
the tool's reading of the real file at stage time; offline it ran on a synthetic Starfield.esm only (Aluminum 4 and Iron 3
-> `additem 00000B02 8`, `00000B01 6`). Paste the lines from `additem.txt` into the console before step 2 of a build, then press
E on the workshop and build; whichever station reads "Missing resources" is a COBJ the match did not catch: widen `--match`.

## Not run, honestly

The Papyrus compile (the PC's compiler); the stage against the real Starfield.esm; ContentResources.zip (not on the build
box: the `scan` output, the fate of every optional native and the beacon id are all still unread); the whole game session.
The workshop keyword's local id in the core, the beacon base, and every guessed native are open until the PC reads them.

## Piece B (the power armor entry by script)

Follows once this is in review: `SetRace` to the kit race on a furniture of ours, our frame and pieces, a value of ours for
"in power armor", the exit that undoes it; first and third person, hand mode, card of eight steps.
