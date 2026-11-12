# Door and lift controls (FAL-489)

Question: do the two vanilla graphs that nothing of ours has driven yet take calls from Papyrus, which events come back, and does the object move?
- **Door on `genericopenclose01`** (0 vanilla users, so there is no vanilla activator to place): does a new activator with the vanilla door's model, rig and
  clips, but this graph, play `Open` / `Close`?
- **Lift on `twostages`**: does the vanilla `ShipQuickLift1` (`00010C35`), placed unchanged, take `Stage1` / `Stage1Transition` / `Stage2` / `Stage2Transition`?
That is the Scribe's `vault111-gear-door` rev 4 section 2c (Claude's request on FAL-489, 12 Nov 21:06 UTC). Probe kit only: nothing goes into the owner's install;
Claude runs it for one session on the PC after the Courier's CLEAR. **Nothing here has been run in the game.**

## Labels
**Verified** = read in this tree. **Supported** = a PC report as Claude posted it, not replayed here. **Unread** = nobody has read it.

## What is built
- `dotnet/AnimDoorLiftControl` (new): `FO4SFAnimDoorLift.esm`, master `Starfield.esm` only, two records, overrides none. QUST `FO4SF_AnimDoorLiftQuest`
  (0x800, start game enabled, stages 10 20 21..24 31..36 40 60, no properties) and ACTI `FO4SF_AnimDoorControl` (0x801): a **new** activator (a DOOR is not an ACTI, so there is
  nothing to duplicate) with the model, BNAM and CNAM of the vanilla DOOR `AK_Ext_Bld_WallA_DoorA_01_Alt02` `000AA24A` (read from the `Starfield.esm` given) and ANAM
  `genericopenclose01.agx` (its path read from the game's archives). One component only, the graph. The vanilla door is neither overridden nor placed.
  `info` / `build` / `check` / `fixture`; `build` refuses a graph that is not `genericopenclose01`, a door that is missing, has no graph component, no model, no rig or
  folder, or does not name `simpleopenclose01`; `check` reads the plugin back (two records, own form keys, masters exactly `[Starfield.esm]`, the door's model/rig/folder).
- The lift is **only read** by the tool (`info`/`check` print its record type, editor id, model and which graph it names, with `lift_names_twostages`): never refused,
  because the session places it whatever it is. What the real record is, is **unread** here.
- `scripts/newgame/FO4SF_AnimDoorLiftQuest.psc`: places both, registers events on each, one call per stage, 15 s of listening, log `FO4SFAnimDL` (every line says `label=door|lift`).
- `scripts/newgame/make_anim_doorlift.py` (`precheck`, `stage`, `log`) and `anim_doorlift_install.py` (own install record): variant A's way. **No clip is copied or written**: this kit holds no game asset.
- Built on the generic control (PR #756): the stager reuses `make_anim_generic.py`'s archive helpers and the installer is its fork, so this branch sits on #756's head `0ba9282b`.

## The session
| stage | what |
|---|---|
| 10 | place the door 4 m ahead; place the lift **disabled**, move it 40 m ahead, enable it only if the move happened (no `MoveTo` = it stays disabled: never a moving platform on the player); register |
| 20 | register every event again on both |
| 21..24 | DOOR: `Open`, `Close`, then the direct `Opened`, `Closed` |
| 31..36 | LIFT: `Stage1`, `Stage2`, `Stage1NoTransition`, `Stage2NoTransition`, then `Stage1Transition`, `Stage2Transition` (clip names, not events: expected false, tried once so the log says so) |
| 40 | a reading of both |
| 60 | disable and delete both |

Set the next stage only after the previous window has closed (`W sN quiet` / `W sN heard n`). **The lists are the PC's read of the real graphs (supported: Claude on #755 at `1bfe5534`, 12 Nov 21:15 UTC; not replayed here):**
`twostages` takes `Stage1`, `Stage2`, `Stage1NoTransition`, `Stage2NoTransition` and sends `TransitionComplete`; `genericopenclose01` takes `Open`, `Close` and the direct `Opened`, `Closed` (states `Closed`,
`Opening`, `Opened`, `Closing`; clip tags `Open` and `Close`). Registered on the door: `Opened`, `Closed`, `Trans01`, `Done`, `IsOn`, `IsOff`, `Open`, `Close`; on the lift: `TransitionComplete`, `Stage1`, `Stage2`.
What a `PlayAnimation` of those names DOES in the game is what the session shows: the read says which events enter which state, not that the call fires them.

What the log cannot say: whether the door or the lift moved. That is a screenshot before and after each stage. The lift is a moving platform: stand well away from its spot.

## Unread, and what would change this kit
- Whether a bare ACTI with only the door's model and a graph component behaves like the door (the real DOOR's other components are printed by `info` as `door_components`, none copied).
- Whether `genericopenclose01` takes the door's own clips (the read names clip tags `Open` and `Close`; the vanilla door's clips live on `SimpleOpenClose01`: whether the file names match is unread).
- What `ShipQuickLift1` is (ACTI/FURN/other), whether it names `twostages` (`info` prints it at stage time), and what a disabled-then-enabled platform does.
- Whether `Stage1Transition` / `Stage2Transition` return false as the read predicts (stages 35 and 36 log it).
- That `ObjectReference.Enable` exists as called (the compile on the PC decides; it is not an optional line).

## Stage and run (PC)
```
python scripts\newgame\make_anim_doorlift.py stage --out <dir> --starfield <Starfield.esm> --compiler <PapyrusCompiler.exe> --content-resources <ContentResources.zip>
python scripts\newgame\anim_doorlift_install.py install --dir <dir> --starfield <game dir>     (the owner's word, game closed)
python scripts\newgame\make_anim_doorlift.py log
python scripts\newgame\anim_doorlift_install.py uninstall --starfield <game dir>
```
THROWAWAY STATE ONLY, NO SAVE: the spawned references are persistent.

## What was and was not run
Run here (synthetic fixtures only): the tool's `fixture`/`info`/`build`/`check`, the stage with a fake Papyrus compiler and a synthetic archive, the installer on a temp game folder, the log reader on
a made-up session. **Not run:** the real `Starfield.esm`, the real archives, the real Papyrus compiler, the game.
