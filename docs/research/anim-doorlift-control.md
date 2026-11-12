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
  (0x800, start game enabled, stages 10 20 21..24 31..34 40 60, no properties) and ACTI `FO4SF_AnimDoorControl` (0x801): a **new** activator (a DOOR is not an ACTI, so there is
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
| 21..24 | DOOR: `Open`, `Close`, `StateA_Play`, `StateB_Play` (the last two matter when both first calls returned false; run them anyway, they cost nothing) |
| 31..34 | LIFT: `Stage1`, `Stage1Transition`, `Stage2`, `Stage2Transition` |
| 40 | a reading of both |
| 60 | disable and delete both |

Set the next stage only after the previous window has closed (`W sN quiet` / `W sN heard n`). Door events registered: `Open`, `Close`, `Trans01`, `IsOn`, `IsOff`, `Done`,
`StateA_Play`, `StateB_Play`, `StateA_Idle`, `StateB_Idle`. Lift events: **the dump of `twostages` is unread**, so the list is its four call names plus `Done` and `Trans01`; to be replaced
by what Claude's `--dump-graph twostages --dump-graph genericopenclose01` shows (a one-line edit of `LiftEvents` / `DoorEvents`, then re-stage).

What the log cannot say: whether the door or the lift moved. That is a screenshot before and after each stage. The lift is a moving platform: stand well away from its spot.

## Unread, and what would change this kit
- Whether a bare ACTI with only the door's model and a graph component behaves like the door (the real DOOR's other components are printed by `info` as `door_components`, none copied).
- Whether `genericopenclose01` takes the door's own clips (`SimpleOpenClose01` names them; the generic graph's Sequence Names are unread by me).
- What `ShipQuickLift1` is (ACTI/FURN/other), whether it names `twostages`, and what a disabled-then-enabled platform does.
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
