# Animation console probe, variant D (FAL-489)

Question: does OUR console (Vault 111 console base `FO4Port_acti_091a48_fallout4`, placed form 001319) answer `PlayAnimation`
and send `Done` when it is given its own rig and its own `.af`/`.afx` clips under the vanilla graph `activatorstategraph01`?
Variant A (12 Nov, PC; see `anim-probe.md` for exactly what its two sessions showed and did not show) moved a spawned vanilla activator with `PlayAnimation` for four names and delivered `Done` after each move; it did not measure event times. Probe kit only: nothing goes into the owner's install.

## Built, new versus reused
New: `src/fo4sf/anim_object.py` (slot map, one-frame Idle hold clips, `.afx` writer in the vanilla shape, sound frame only when a
foley name is given); `Converter.convert_anim_object` (pipeline.py); `dotnet/AnimConsoleProbe` (ACTI override + quest, `info`/`build`/`check`);
`scripts/newgame/FO4SF_AnimConsoleQuest.psc`, `make_anim_console.py`, `anim_console_install.py`.
Reused, door path: `door_motion.inspect`, `door_rig.plan`, `native_door` (rig and `.af` through CALUMI), `convert_static.convert_multipart_door`.
Generalised with defaults that leave doors unchanged (door tests pass): an `allowed` clip-name set, `expect_clips`, `plan_hook`, `anim_graph`, `motion_clip`, and `descriptors` in `native_door.export`.
Variant A's installer, log reader and stager pieces are reused.

## Map of the original clips (UNREAD: not checked against the Fallout 4 archives)
The seven FO4 console sequences, their names, lengths and which is the glass flip or the button have not been read. Run
`make_anim_console.py clips --fo4-data <FO4 Data>` first; it prints each sequence with seconds, bones and text keys.
Design: first activation `Play01` = StateA_Play (glass flip), StateA_Idle = one-frame hold; second `Play02` = StateB_Play (button), StateB_Idle = hold.
The map is given as `--states "<FO4 seq>=StateA_Play,<FO4 seq>=StateB_Play"`; every FO4 sequence not named there is left out (the stager's report lists them).
The graph has no end event for these slots, but variant A showed `Done` after each clip, and the script logs `after=` on it (the clip's length as played).

## Sounds
No foley/sound record is named yet. Without `--foley` the `.afx` files carry no `<audio>` frame (said, not guessed). With it, a sound frame is written
for each Sound text key of a Play clip (frame = seconds x 30, at least 1). Whether the engine takes a foley name there is unread.

## Run (PC, one session; Claude)
1. `make_anim_console.py precheck`, then `clips` to choose the map.
2. `make_anim_console.py stage --out <new dir> --fo4-data ... --door-anim-dll ... --collision-template ... --texconv ... --states ... [--port-data <dir with FO4Port.esm and its ba2>]`.
   Needs the port's plugin and archive. The kit ships meshes, geometries and materials only; the stage refuses if the conversion wrote a texture the port's archives lack.
3. `anim_console_install.py install --dir <stage> --starfield <game dir>`; throwaway state, no save (the spawned reference is persistent).
4. Console: `setstage <load index>000800 10`, then 21 to 28 one at a time, after each 15 s window closes (a `W` notice or the stage's quiet/listened line). Screenshots before and after each. Stages 21..24 are the four names that moved the vanilla activator (Play01, Play02, TurnOff, StateB_Play); 25..28 are controls. 30 = Activate by script.
5. `make_anim_console.py log`, then `uninstall`.

## Reading
- `REG s10 22/22 true` and `PLAY s21 Play01 ok=true` as in variant A. A false `PlayAnimation` shows `PLAY s<N> <name> ok=false` (the same `Say` line with the returned value); that was not observed in variant A.
- Pass: our console moves on 21 and 22 (the flip and the button), `EV Done` arrives in the same window with `t` near the clip's length.
- If the console does not move but the vanilla one did: the rig or `.af` path does not take a non-door model (unread, the main risk), or the plugin's graph component is wrong; the offline check shows the component written.
- Not verified here: any in-game behaviour, the real Papyrus compile on the base sources, the CALUMI clip writer on a console.

## Where the console is, and what the PC build used (from the PC's offline run, 12 Nov)
- The override is on the BASE (ACTI `00E0D9` of FO4Port.esm on that PC's build), so every reference of that base shows the new model. Stages 10 to 28 act on a SPAWNED copy: `PlaceAtMe` 2.5 m in front of the player, in whatever cell they stand in. Look in front of you after stage 10.
- Whether the placed console `001319` is a reference of this base is UNVERIFIED here (the stager prints the base id; `001319` is the placed ref named in the experiment's plan). To check the placed one too, `player.moveto 03001319` (port at index 03 on that load order) and look; if it still shows the old model, the placed ref uses a different base.
- The PC's collision template was gone: the first `historicaloilportraits` model of the game's archive was used for it. It is a stand-in for the physics donor, not the console's shape.
- FO4 clips read on the PC: `Stage2` 1.633 s (flip, `SoundPlay.OBJSwitchGearDoorPanelOpenFlip` at 0), `Stage3` 0.633 s (button, `SoundPlay.OBJSwitchGearDoorPanelOpenPush` at 0), `Stage2Loop` 1.0 s, `Stage3Loop` 0.033 s with key `Stage4`, three more of 0.033 s; bones `Button` and `Lid`. Map used: `--states "Stage2=StateA_Play,Stage3=StateB_Play"`; the other five are left out.

## Session 1 result (PC, 12 Nov 07:46 to 07:55, head b3e5a587) and the lines this head adds
`REG 22/22 true`. `Play01` ok: `Trans01` 0.069 s, `Done` 1.569, `IsOff` 1.586; `Play02` ok: `Trans02` 0.071, `Done` 0.581, `IsOn` 0.599; `TurnOff` `Done` 1.572; `StateB_Play` `Done` 0.588; `Activate` `Done` 1.573. The originals are 1.633 s and 0.633 s: `Done` is about 0.06 s short each time. **Measured:** the `Done` times of the clips, read from the `AP` notices (script logging off; stages 10, 21 to 24 and 30 read, stages 25 to 28 are in the shots but not read). **Not seen: the panel moving.** After stage 10 nothing new was visible 2.5 m ahead in any screenshot (level view from the cryo room's walkway); the spawned copy was not found in frame, so neither the lid flip nor the button push is seen, only timed. The `Done` times match the converted clips' lengths and not variant A's (variant A's event times were not measured, so there is no like-for-like comparison); that points to the converted `.af` clips being played, and it is a reading of the times, not something seen. A spawned reference, not a placed one.
Variant A's vanilla object WAS seen at the same offset (`AheadM` = 2.5, the same `MoveTo(AheadM * sin, AheadM * cos, 0)` call; 2.5 m per variant A's card), so the offset alone is not the proven cause; the model not rendering is equally possible. Unread which. This head adds two on-screen lines to tell them apart (they were not in `b3e5a587`, and session 1 did not record `moved`): `SPAWN s10 moved=<bool> ahead=<n>` and `READ s<stage> <when> 3d=<Is3DLoaded> off=<IsDisabled> dist=<GetDistance> dz=<height of the copy minus the player's>`. Read `3d=false` as the object not loaded; `3d=true` with nothing in frame as a model or placement problem. Offsets are unchanged in this head. Stages 25 to 28 were in session 1's shots and were not read.
Sounds: not named. No Starfield sound record was read here; `.afx` carries no `<audio>` frame unless `--foley` names one. The two `SoundPlay` keys are `OBJSwitchGearDoorPanelOpenFlip` (flip, at 0) and `OBJSwitchGearDoorPanelOpenPush` (button, at 0).
