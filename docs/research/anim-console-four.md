# The converted console on four states (FAL-489)

Question: with the converted Fallout 4 console on `genericstategraph01` and **eight different clips**, does each of the graph's states show its own pose, and which call
leaves the panel in which pose? The generic control (PR #756, PC game session 12 Nov 22:35 to 22:47 UTC) passed its bar with C and D as copies of A and B, so those
states could not be told apart by eye. This kit is the next step the Scribe's `vault111-console-stages` rev 4 names ("the converted four-clip panel"), as Claude
asked it on FAL-489 (12 Nov 22:49 UTC). Probe kit only: nothing goes into the owner's install; Claude stages it on the real files and runs it for one session on the PC
after the Courier's CLEAR. **Nothing here has been run in the game.**

## Session 1 result and what changed in this head (supported: Claude's PC session at 617909a0, 12 Nov 23:45 to 23:57 UTC, on the pull request; not replayed here)
Seen there (pixel counts on the front copy): `StateA_Idle` rest, `StateB_Idle` lid open, `StateC_Idle` lid open with the button down (94 px from B, 46 in the button's box),
`StateD_Idle` equal to C as built; all returns TRUE/TRUE. `Play01` ends in B's pose (events 1.57 to 1.62 s). `Play02` ends in REST already at 1.2 s (the card's expectation; the button
going down was not caught). `Play03` ends in rest, events at 2.10 s, nothing visible. `Play04` ends in C's pose and holds it, events at 0.07 s. `StateD_Play` ends in rest.
Claude's reading: a play followed by the direct idle call holds a pose. Three asks, and the answers:

1. **The map and the order for the scene (lid opens and stays open; button goes down and stays down).** Default map now `Stage2=StateA_Play,Stage3=StateC_Play,Stage4=StateD_Play`
   (the old one is still `--states "Stage2=StateA_Play,Stage3=StateB_Play,Stage4=StateC_Play"`). The poses the idles hold are the same four (rest, lid open, lid open + button down, the pose
   after Stage4); `StateB_Play` becomes the one-frame spare, because the graph returns from `StateB_Play` to rest (supported, `Play02`). **New stage 30, the scene** (both copies, one 20 s window,
   closing notice `W s30 scene`): `StateA_Idle` (to rest), 1 s later `Play01` (lid opens; supported: rests in B's pose), 2.5 s later the **button clip by its slot name** `StateC_Play`
   (the second clip of the chain: the stager writes the slot into the script, so any map works), then `ButtonS + 0.7` s later that slot's Idle `StateC_Idle` (supported: holds the C pose,
   lid open and button down). The idle's start pose is the clip's last frame, so the hand-over has no jump (the chain builder starts each clip from the pose before it; tested on synthetic clips).
   It is built so; **whether a direct `StateC_Play` plays our clip is inferred from the control** (`StateC_Play` returned true and played its clip there), not seen with this map.
2. **A slower button.** `--slow Stage3=4` (the default): every sample time, the duration and the event times of that clip times a whole factor 2 to 8, nothing else (same poses, same keys, on
   the 30 fps grid). The button is then 2.533 s instead of 0.633 s, so a shot 1.2 s after the call lands inside the motion. `--slow ""` = as authored. The README and the manifest name the factor;
   the script's `ButtonS` is the clip table's stretched seconds. I did not build "call twice with a pause": the factor does the same job and needs no second call.
3. **What `Play03` plays for 2.1 s: not known.** In the eight clips of 617909a0 no slot is that long (1.633, 0.633, 0.033, 0.033, and the idles) and no sum of them is 2.1 s, so a plain slot
   is not the answer. The graph dump (supported: the control's card) says `Play03` and `Play04` BOTH enter the C side, with `StateC_Play` and `StateC_Idle`; what the C side does with them
   (a blend, a nested machine) is **unread**. This head makes the next session answer it by itself: stages 23 and 24 are unchanged, and now `StateC_Play` is the **2.5 s button clip** and
   `StateD_Play` the Stage4 frame. If `Play04`'s events move from 0.07 s to about 2.5 s, `Play04` plays slot C; if `Play03`'s 2.1 s stays 2.1 s, it is not a slot clip of ours at all (a graph-internal time).
   Stage 21 `Play01` and stage 22 `Play02` stay for the same comparison (1.57 s and 0.58 s before).

## Not run
The real conversion, the real archives and compile of this head, the game. Tests (synthetic fixtures): 45 anim_object (4 new: slow), 33 console-four (3 new: scene, slow, default map), 12 install;
the #747 console suites (28, 12) and papyrus-strings (7) pass; guard ok.

## Labels
**Verified** = read or run in this tree (synthetic fixtures). **Supported** = a PC report or session as Claude posted it, not replayed here. **Inference** = my reading
of supported facts. **Unread** = nobody has read it.

## What is built
- `src/fo4sf/anim_object.py`: a third idle mode, `chain` (`add_chain_idles`), and the four-slot names (`PLAY_SLOTS4`, `GRAPH_GENERIC`); `pipeline.Converter.convert_anim_object`
  takes `idles="chain"` and `graph=<ANAM>`. The two existing modes (`toggle`, the default, and `hold`) and the activator graph are unchanged (the #747 tests pass untouched).
- `dotnet/AnimConsoleFour` (new, a fork of #747's `AnimConsoleProbe`): `FO4SFAnimConsoleFour.esm`, masters `Starfield.esm` + `FO4Port.esm`: an **override of the port's
  console base** (as #747: the record as it is, the converted model, one animation graph component: ANAM `genericstategraph01.agx` as the game stores it, BNAM the rig,
  CNAM the clip folder) and QUST `FO4SF_AnimConsoleFourQuest` (stages 10 11 20 21..29 40 60, no properties). `--graph` is required and the tool refuses a path that is not
  `genericstategraph01`; `check` reads the plugin back.
- `scripts/newgame/FO4SF_AnimConsoleFourQuest.psc`: #747's spawn (in front of the player, chest height, facing the player) and side copy, then the call list below.
- `scripts/newgame/make_anim_console_four.py` (`precheck`, `clips`, `stage`, `inspect`, `dump`, `log`) and `anim_console_four_install.py` (own install record).
  `stage` reads the real graph path from the game's archives (`Starfield - Animations.ba2`) and refuses, naming the archive to pass, when it is not there.
- Tests: `tests/test_anim_object.py` (chain), `tests/test_anim_console_four.py`, `tests/test_anim_console_four_install.py`: synthetic fixtures, a real chain conversion of a
  synthetic console with the native writer replaced by a fake.

## The eight clips and the pose each Idle slot holds
(This section and the next two describe the first session's map, button on `StateB_Play`. With the default of the second head the button clip is on `StateC_Play`, `StateD_Play` carries Stage4 and `StateB_Play` is the spare; the four poses the Idle slots hold are the same.)

The console's sequences (**supported**, #747 `clips`): `Stage1` and `Stage1Loop` 0.033 s, `Stage2` 1.633 s (the lid), `Stage2Loop` 1.0 s, `Stage3` 0.633 s (the button),
`Stage3Loop` 0.033 s (text key `Stage4`), `Stage4` 0.033 s. Bones `Lid` and `Button`. Map of the first session (the Scribe's rev 4): `Stage2=StateA_Play`, `Stage3=StateB_Play`, `Stage4=StateC_Play`; the default since the second head is in the section above.
Each clip starts from the pose the one before it ended in (a bone a clip leaves standing is held at that pose, as `--idles toggle` does for slot B).

| clip | what it is | |
|---|---|---|
| `StateA_Idle` | the first frame of `Stage2` | **rest: lid shut, button up** |
| `StateA_Play` | `Stage2`, the lid opens (1.633 s) | |
| `StateB_Idle` | the last frame of `Stage2` | **lid open, button up** |
| `StateB_Play` | `Stage3`, the button goes down (0.633 s), lid held open | |
| `StateC_Idle` | the last frame of `Stage3` | **lid open, button down** |
| `StateC_Play` | `Stage4` (0.033 s) | |
| `StateD_Idle` | the pose after `Stage4` | **as C unless `Stage4` moves a bone** (its tracks are unread: `make_anim_console_four.py clips` prints them; the staged README says what each Idle holds) |
| `StateD_Play` | spare: a one-frame hold of the last pose | nothing should move |

## Calls, and what the graph is expected to do after them
One call per stage, 15 s of listening each, on **both copies** (stage 11's side copy too). Stages: `10` spawn, `11` side copy, `20` register again, `21..24` `Play01`, `Play02`,
`Play03`, `Play04`, `25..28` `StateA_Idle`, `StateB_Idle`, `StateC_Idle`, `StateD_Idle`, `29` `StateD_Play` (the spare; added last so it cannot disturb the requested eight),
`30` the scene (below), `40` a reading, `60` delete. Registered: `Trans01`, `Trans02`, `Trans03`, `Done`, `IsOn`, `IsOff`, `Play01`..`Play05`, the eight state names, `TurnOn`, `TurnOff`, `Opened`, `Stage4`,
`TransitionComplete`.

**Notices** (the control's session missed two return lines): the `PLAY s<stage> <name> ok=<front>/<side>` line is shown right after the call, before any other notice of the
stage, and shown again three times, two seconds apart; the line that closes the window says which call it was, what it returned and how many events came in
(`W s<stage> <name> ok=.. heard n`). The "before" reading is logged only. Script logging is off on the PC's install, so the notices and the screenshots are the record.

What to expect, **supported** = the control as Claude reported it, **inference** = applied to this kit:

- `Play01` -> `StateA_Play` (the lid opens) -> rests in `StateB_Idle` (lid open). Supported: on the control `Play01` opened the holder and it stayed open.
- `Play02` -> `StateB_Play` (the button goes down) -> **the control's graph then returned to the rest pose** (supported: `Play02` closed the holder and it stayed closed). Inference:
  here the button goes down and then the panel snaps back to rest (lid shut, button up), because that is where `StateB_Play` ends in the graph's wiring (`Trans01` into `StateA_Idle`).
  **Expected, and the first thing to look at.**
- `Play03`, `StateC_Play` -> the `Stage4` clip -> then a rest. Supported on the control: the opening clip, then a closed rest. **Which idle that rest is, the control cannot say**: its `StateC_Idle` was a
  copy of `StateA_Idle`, so a rest in either looked the same. Here they differ (rest versus button down), so this stage answers it. The link table reads `Trans01` entering `StateC_Idle` (inference: C_Play ends there).
- `Play04`: unread beyond the control's "plays the opening clip, then rests closed"; it enters a nested B-to-A machine and a C blend tree. Not a console stage.
- `StateA_Idle` .. `StateD_Idle`, called directly: the state's own pose, held (supported on the control: `StateC_Idle` held closed and `StateD_Idle` held open for two minutes, through
  stages 30 and 40). **This is the test of the four poses.**
- `StateD_Play`: the spare (nothing moves), then a rest. Supported on the control: it played the closing clip and rested closed, in an idle the control could not name (A's and C's idles were alike).

## If `Play02` does rest at the rest pose
Then a held four-state console is not "four plays in a row" on this graph. What the control shows for certain: `A_Play -> B_Idle` and `B_Play -> A_Idle` (a toggle). Where `C_Play` and `D_Play` end is **not** shown (see
above); the link table reads `Trans01` entering `StateC_Idle`. If `Play03` does rest in `StateC_Idle`, the map that follows the graph puts the button clip on slot C:

    --states "Stage2=StateA_Play,Stage3=StateC_Play"

(`Play01` then `Play03`: the lid opens and holds in `StateB_Idle`; the button goes down and holds in `StateC_Idle`). The stager and the converter take it as it is: unmapped Play slots become spare
one-frame holds, and a clip's "starts from" names its position in the chain (tested here on synthetic fixtures). A game script can also follow any play with a direct idle call. Neither is the default,
which is the mapping asked for.

## Unread, and what would change this kit
- What `Stage4` moves (if anything): the staged README and `clips` say; if it moves nothing, `StateD_Idle` looks like `StateC_Idle` and the "fourth pose" is not a fourth look.
- Whether a one-frame `StateD_Play` (two samples, 1/30 s) plays like any other clip; the control's D clip was a copy of a 1.0 s-class clip.
- Whether `Stage4`'s 0.033 s as a play slot, and the one-frame idles, behave as the control's idles did (the control's idles were the vanilla one-frame holds; ours are made the same way as #747's).
- Whether the real console's lid and button show the poses at the right place (#747 session 8: a thin dark line and a pale plane on the panel's top; the glass draws almost nothing).
- Which call the real console quest would use for the door's `"stage4"` wait: not decided here.
- The real `genericstategraph01` path in the archives is read at stage time (**supported** by the control stage: Claude's stage of #756 on the real files exited 0).

## Stage and run (PC)
```
python scripts\newgame\make_anim_console_four.py clips --fo4-data <Fallout 4 Data> --starfield-data <Starfield Data>        (read only: the sequences, seconds, tracks)
python scripts\newgame\make_anim_console_four.py stage --out <dir> --starfield-data <Starfield Data> --fo4-data <Fallout 4 Data> --door-anim-dll <CALUMI.Animation dll>
        --collision-template <nif> --texconv <texconv.exe> --content-resources <ContentResources.zip> [--states "Stage2=StateA_Play,Stage3=StateB_Play,Stage4=StateC_Play"]
python scripts\newgame\make_anim_console_four.py inspect --stage <dir>                                                     (read only)
python scripts\newgame\anim_console_four_install.py install --dir <dir> --starfield <game dir>                              (the owner's word, game closed)
python scripts\newgame\make_anim_console_four.py log
python scripts\newgame\anim_console_four_install.py uninstall --starfield <game dir>
```
Do not install it next to #747's console kit: both override the same console base, and the load order would decide which model shows. THROWAWAY STATE ONLY, NO SAVE: the spawned references are persistent.

## What was and was not run
Run here (synthetic fixtures only): the tool's `fixture`/`info`/`build`/`check` and its refusals, a real chain conversion of a synthetic console with the native writer replaced by a fake,
the stage with a fake Papyrus compiler, a synthetic archive and fake base sources, the installer on a temp game folder, `inspect` on the staged kit. **Not run:** the real conversion (no
Fallout 4 data, no CALUMI library here), the real `Starfield.esm` and archives, the real Papyrus compile, the game.

## Not here
The glass opacity flag (the Scribe's third step: not asked for this round), the door and the lift controls (PR #757), the cog door, the pick-up object, `StartAltIdle`.
