# Cog door probe: the DOOR install route and the SetOpen fallback (FAL-756, FAL-489 Plan B step 1)

Author: Minuteman. Status: built and tested offline; **no game run, no install**. Verified/unresolved labels follow docs/ai/research-log.md.

## Why this exists
Plan B step 0 (PC, 14 Nov 2026, nothing installed): `prid` printed `DOOR '' (0300126D)`; no activation prompt and E did nothing from the
ramp end (about 6 m from the cog); the cog and the view stayed identical over 13 shots; walking west fell into the gap (getpos -59.26, -3.06,
-2.38). Step 1 (the converted door, #778) could not run: `make_anim_console.py stage` overrides an ACTI only, the cog door base is a DOOR
(FO4Port.esm local 00DEF9, FO4Port_VltGearDoor01), and `anim_console_install.py` replaces no archived file and reads no loose files.

## Decision: route (a), a DOOR override on a new model path (supported, not run in game)
- **(a)** `make_cog_door.py stage` converts the Fallout 4 door again with the converter's own `_anim` suffix
  (`fo4port/interiors/vault/doors/vltgeardoor/vltgeardoor01_anim.nif`, its rig and clip folder beside it; the rig and clip paths are derived from the
  model's output name in `convert_static.convert_multipart_door`, read in the source) and writes `FO4SFCogDoor.esm`: a DOOR override of the base the
  placed reference stands on (model, rig and clips replaced; ANAM door graph, name, flags, sounds kept) plus the SetOpen quest. The session
  installer packs it; no archived file is replaced, nothing relies on archive order. The door's origin offset is 0 (`convert_static`), so the
  placed reference needs no shift. Because the override is on the base, every reference of that base shows it; this base has the one cog door.
- **(b)** "a later plugin's archive wins for the same path": **unresolved**. Nothing in the repo shows it (only "loose files are not read on
  this install", docs/planet/planet-probe.md). It would need its own session to prove, and a shadowed file is also a worse thing to leave
  in an install. Not needed with (a).
- The stager refuses a reference whose base is not a DOOR of FO4Port.esm, a conversion that fell back to a static (`door_error`,
  `door_not_opening`), a converted path equal to the port's own, and any texture the port's archives lack.

## The kit
`python scripts/newgame/make_cog_door.py stage --out <new dir> ... [--control]` then `cog_door_install.py install --dir <stage> --starfield <game dir>`
(the owner's word, game closed). Two kits from one stager:
- **control** (`--control`): the quest alone, no DOOR override. The installed port's own door answers the stages: step 0 repeated with a trigger.
- **full**: the DOOR override plus the quest: step 1.
Quest stages (set one at a time, `setstage <quest form id> <n>`: the plugin's load index plus 000800, e.g. `setstage 0E000800 20` when it loaded as 0E; the name form `setstage FO4SF_CogDoorQuest <n>` is refused by the console, "Item ... not found for parameter Quest", observed in the PC session of 14 Nov; after the previous watch closed; each of 20/30/40 logs the open state every 2 s
for 60 s; console closed through the watch): 10 read, 20 `SetOpen(true)`, 30 `SetOpen(false)`, 40 `Activate(player)`, 50 read. Log:
`My Games\Starfield\Logs\Script\User\FO4SFCogDoor.0.log`, read with `make_cog_door.py log`. Every line also shows on screen ("AP ...").

## Console `prid 0300126D` then `activate player`
Yes, the PC may run it with nothing installed: it needs no install, writes no save, and tells whether the DOOR answers activation at all.
Run it after the passive control shots, shoot at 12, 20, 30, 36, 44 s with the console closed, and record whether the cog turns. Note the quest's
stage 40 repeats it by script, so once a control kit is installed the console version adds nothing.

## Corrected Plan B card (replaces step 4 and the install line of note section 33)
1. Control (nothing installed, done 14 Nov 04:36-04:49): activation from the ramp does nothing, no prompt. Stop line reached; no verdict.
2. Optional now, free: console `prid 0300126D`, `activate player`, close the console, timed shots; record.
3. Control kit installed (`--control`): stages 10, 20 (watch 60 s with shots at 12, 20, 30, 36, 44 s), then 30, then 40. Record the log table.
   - open state stays put and the cog never turns after 20: the installed port's rig does not play on SetOpen (its own question).
   - the state changes and the cog turns: the installed door works by script; activation is the missing piece (prompt/no-prompt, name `''`).
4. Full kit installed instead (uninstall the control kit first; one kit at a time): the same stages 10 and 20. Judge by note section 33a
   (PASS / PARTIAL / FAIL) only here.
Never both kits at once: the same plugin name and quest id.

## Not done / limits
Papyrus compile against the real ContentResources.zip (the stager does it on the PC; the offline tests use a fake compiler and fake sources);
whether `SetOpen` on a DOOR with a CALUMI rig plays the Open clip; whether the new-path model loads; any game behaviour. The reference's local id
00126D and base 00DEF9 are from the repo's reading (note section 33); the stager's `info` prints the real ones before anything is converted.
