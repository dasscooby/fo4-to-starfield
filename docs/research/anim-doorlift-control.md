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
- The control's graph component is the vanilla door's WHOLE component (BNAM, CNAM, DNAM, ENAM and anything else it carries) with only the ANAM changed, and `check` compares them: the same flaw the Courier held on the generic control (FAL-579), fixed here the same way.
- `dotnet/AnimDoorLiftControl` (new): `FO4SFAnimDoorLift.esm`, master `Starfield.esm` only, two records, overrides none. QUST `FO4SF_AnimDoorLiftQuest`
  (0x800, start game enabled, stages 10 20..24 30..36 40 60, no properties) and ACTI `FO4SF_AnimDoorControl` (0x801): a **new** activator (a DOOR is not an ACTI, so there is
  nothing to duplicate) with the model, BNAM and CNAM of the vanilla DOOR `AK_Ext_Bld_WallA_DoorA_01_Alt02` `000AA24A` (read from the `Starfield.esm` given) and ANAM
  `genericopenclose01.agx` (its path read from the game's archives). One component only, the graph. The vanilla door is neither overridden nor placed.
  `info` / `build` / `check` / `fixture`; `build` refuses a graph that is not `genericopenclose01`, a door that is missing, has no graph component, no model, no rig or
  folder, or does not name `simpleopenclose01`; `check` reads the plugin back (two records, own form keys, masters exactly `[Starfield.esm]`, the door's model/rig/folder).
- The lift is **only read** by the tool (`info`/`check` print its record type, editor id, model and which graph it names, with `lift_names_twostages`): never refused,
  because the session places it whatever it is. **Supported** (Claude's PC read of the real `Starfield.esm`, relayed in the FAL-489 thread, not replayed here): `ShipQuickLift1` is an ACTI, its graph is `TwoStages.agx`, its graph component has no CNAM, and its VMAD is 64 bytes, so it carries a script. **Unread:** what that script does.
- `scripts/newgame/FO4SF_AnimDoorLiftQuest.psc`: places both, registers events on each, one call per stage, 15 s of listening, log `FO4SFAnimDL` (every line says `label=door|lift`).
- `scripts/newgame/make_anim_doorlift.py` (`precheck`, `stage`, `log`) and `anim_doorlift_install.py` (own install record): variant A's way. **No clip is copied or written**: this kit holds no game asset.
- Built on the generic control (PR #756): the stager reuses `make_anim_generic.py`'s archive helpers and the installer is its fork, so this branch sits on #756's head `a70e6e69` (its DNAM/ENAM fix and event list; the held head was `0ba9282b`).

## The session
| stage | what |
|---|---|
| 10 | the DOOR only: place it 4 m ahead, register; a notice after each step (`S10 start`, `door placed`, `door moved=`, then the `REG` line, `S10 done`) |
| 20 | register every event again on the door, and on the lift when it exists |
| 21..24 | DOOR: `Open`, `Close`, then the direct `Opened`, `Closed` |
| 30 | the LIFT's own placement, after the door's stages: placed **disabled**, moved 2.5 m ahead, between the player and the door (4 m), no side offset (5 m ahead and 3 m right was not seen in the 13 Nov session; the lift's size is unread, so a large platform may overlap the player: the one reading says), enabled only if the move happened (no `MoveTo` = it stays disabled: never a moving platform on the player), with `EnableNoWait` when the game declares it (it never blocks), else `Enable`; registered; a notice after each step (`S30 start`, `lift placed`, `lift moved=`, `lift enabled nowait=`, `REG`, `S30 done`) |
| 31..36 | LIFT: `Stage1`, `Stage2`, `Stage1NoTransition`, `Stage2NoTransition`, then `Stage1Transition`, `Stage2Transition` (clip names, not events: expected false, tried once so the log says so) |
| 40 | a reading of both |
| 60 | disable and delete both |

Set the next stage only after the previous window has closed (`W sN quiet` / `W sN heard n`). **The lists are the PC's read of the real graphs (supported: Claude on #755 at `1bfe5534`, 12 Nov 21:15 UTC; not replayed here):**
`twostages` takes `Stage1`, `Stage2`, `Stage1NoTransition`, `Stage2NoTransition` and sends `TransitionComplete`; `genericopenclose01` takes `Open`, `Close` and the direct `Opened`, `Closed` (states `Closed`,
`Opening`, `Opened`, `Closing`; clip tags `Open` and `Close`). Registered on the door: `Opened`, `Closed`, `Trans01`, `Done`, `IsOn`, `IsOff`, `Open`, `Close`; on the lift: `TransitionComplete`, `Stage1`, `Stage2`, `Stage1NoTransition`, `Stage2NoTransition` (the last two are called at stages 33 and 34, so an arrival is logged; `Stage1Transition` and `Stage2Transition` at 35 and 36 are clip names, not events, and are not registered).
What a `PlayAnimation` of those names DOES in the game is what the session shows: the read says which events enter which state, not that the call fires them.

What the log cannot say: whether the door or the lift moved. That is a screenshot before and after each stage. The lift is a moving platform: stand well away from its spot.

## Unread, and what would change this kit
- Whether a bare ACTI with only the door's model and a graph component behaves like the door (the real DOOR's other components are printed by `info` as `door_components`, none copied).
- Whether `genericopenclose01` takes the door's own clips. **Supported** (Claude, PC, 12 Nov 21:37 UTC, not replayed here): the vanilla door's clip folder holds exactly `open.af(x)` and `close.af(x)`, which fits the graph's clip tags `Open` and `Close` up to case; whether the engine matches them case-blind, and whether the graph plays them, is unread.
- **The lift, supported** (Claude, PC read of the real `Starfield.esm`, relayed in the FAL-489 thread, not replayed here): `ShipQuickLift1` is an ACTI, its graph is `TwoStages.agx`, its graph component has **no CNAM** (no clip folder of its own), and its VMAD is 64 bytes: it carries a script. Still **unread**: what that script does. It may start or stop the platform itself or ignore a placed copy, so a true return with no motion, or a motion nobody called, are both open readings. `info` prints the type and graph at stage time, so the real record is checked again there; and so is what a disabled-then-enabled platform does.
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

## Session 1 result and what changed (supported: Claude's PC game session at f00bcdcb, 13 Nov 00:16 to 00:28 UTC, on the pull request; not replayed here)
The door control appeared about 4 m ahead after stage 10, and then the kit was silent for the whole session: no `REG`, `PLAY`, `EV` or `W` notice in any of 87 shots, the door never moved.
No crash, no save. **Seen:** the door's placement; the silence. **Not seen / unread:** why. Claude's reading (inference, no log): stage 10 placed the door, placed the lift disabled, moved it 40 m
ahead (outside the closed room, about 12 m deep) and called a blocking `Enable` before the first notice; if that step never returns, stage 10 never finishes and every later stage queues behind it.
That is a hypothesis, not a result. The change makes the session tell where it stops, whichever it is: (1) a notice at the start of stage 10 and after each step; (2) the door is placed and
registered before the lift is touched, and the lift has its own stage 30 after the door's stages (21..24); (3) the lift lands 5 m ahead and 3 m to the right; (4) `EnableNoWait` when the base scripts
declare it (the stager keeps the optional line only if it compiles), else the blocking `Enable` as before. If the notices still stop at one step, that step is the finding.

## Session 2 result (supported: Claude's PC game session at ccc2dfb8, 13 Nov 2026, 01:20 to 01:33 UTC, on the pull request, comment 6841159941; not replayed here)
**Door half: seen on screen, a pass for these calls.** `Open` opens (swings left) and holds, `Close` closes, `Opened` and `Closed` set the pose at once, all four `ok=TRUE`; the plays send `Trans01` and `Done`,
the direct poses only `IsOn` / `IsOff`; every stage 10 step notice came. **Lift half: not a result.** Stage 30 ran to `S30 done` (placed disabled, `moved=TRUE`, `enabled nowait=TRUE`, so `EnableNoWait` compiled in,
`REG lift 5/5`), but the lift was in no shot, and stages 31 to 36 printed nothing in 49 shots. Missing for the door too: the `W s21..24` closing lines and a stage 20 `REG` line.
**What is read from it (inference, no log; not a result):** (a) the first lift `PlayAnimation`, or the reading once enabled, may never return and hold the poll: that is Claude's reading. (b) The missing `W` and stage 20
`REG` notices are also consistent with a single short notice that had already gone by the time of the shot (taken up to 20 s after a 15 s window closed); the console kit repeats its notices and its `W` line was seen.
(c) Stage 40 (and the settled readings) only wrote to the log in this kit: their silence on screen is by construction, not a finding.
**Changed in the next head (script and card only; the clips, the plugin and the stage list are untouched):** each play stage has its own one-shot timer (`TIMER_CALL + stage`), the poll only starts it, so no call is made inside the poll;
a notice before the reading and one before the call (`C sN name reading`, `C sN name calling`), so the last notice on screen names the step that did not return; the return and closing notices are repeated like the console kit's;
the readings after a stage's call and stage 40 are shown on screen (`READ ...`), the lift's after it was enabled included; the lift is placed 2.5 m ahead, between the player and the door.
Whether the lift's call really hangs, and why, is still **unread**: the next session shows the step.
