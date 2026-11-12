# Animation console probe, variant D (FAL-489)

Question: does OUR console (Vault 111 console base `FO4Port_acti_091a48_fallout4`, placed form 001319) answer `PlayAnimation`
and send `Done` when it is given its own rig and its own `.af`/`.afx` clips under the vanilla graph `activatorstategraph01`?
Variant A (12 Nov, PC) proved the graph and the call on a vanilla activator. Probe kit only: nothing goes into the owner's install.

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
