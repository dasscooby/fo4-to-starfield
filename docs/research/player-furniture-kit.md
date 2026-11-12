# Player-furniture control kit, variant P

Task: FAL-518 (the player side of the Vault 111 exit). Design: the Scribe's document `vault111-player-furniture` revision 6 (on FAL-502), section 4, "In-game control run". Status: **built offline; NOT_RUN. Nothing here has been compiled with Starfield's Papyrus compiler, checked against the real `Starfield.esm`, installed or played.** The PC offline check and the game session are the owner's.

## The question
Does `Activate(player)` on a **spawned** copy of a vanilla play-once furniture put the player into its pose, outside its original cell and without a scene? And what ends it: which events does Papyrus hear (`Actor.OnSit`, `Actor.OnGetUp`, `ObjectReference.OnEnterFurniture`, `ObjectReference.OnExitFurniture`, the player's animation events), and at what time after the activate? This is how the game's own `SBPowerCollectionActivatorScript` starts a player use (input layer, `DisablePlayerControls()`, `furniture.Activate(player)`), and `MQ101Script` ends on `Actor.OnGetUp` through `RegisterForRemoteEvent`.

## What is built
| Piece | Where |
|---|---|
| Plugin writer (build, check, fixture) | `dotnet/PlayerFurn` |
| Quest script | `scripts/newgame/FO4SF_PlayerFurnQuest.psc` |
| Stage (precheck, stage) | `scripts/newgame/make_player_furn.py` |
| Ride-along installer, own record `Data\FO4SFPlayerFurn.install.json` | `scripts/newgame/player_furn_install.py` |
| Tests | `tests/test_player_furn.py`, `tests/test_player_furn_install.py` |

`FO4SFPlayerFurn.esm`: master `Starfield.esm` only; ONE record, QUST `FO4SF_PlayerFurnQuest` (0x800; start game enabled; stages below; script `FO4SF_PlayerFurnQuest`; no properties). No FURN, no REFR, no cell, nothing overridden: `check` asserts all of it. `build` also reads the given `Starfield.esm` and refuses unless the four furniture below exist under those editor ids.

Not in this kit: our converted panel, Fallout 4 clips, any FO4Port master, any override of a vanilla record, `PlayerPathToFurniture` (no Starfield record of these types carries it), stamping `FurnitureForce1stPerson` onto a record, `PlayAnimation` / `PlayIdle` / `SnapIntoInteraction`, the wait form of anything. There is no log reader: the readout is the on-screen notices; the user log (when script logging is on) is read by eye.

## The session (stages from the console; the plugin's load index, two hex digits, then `000800`)
The console does not know the quest by its editor id: use `setstage <index>000800 <n>`. The script polls once a second. Test save, **no saving** (the spawned references are persistent). Tolerant god mode (`tgm`) on.

| Stage | What it does |
|---|---|
| 10 | spawn `PowerCycle` `03607F` 2.5 m in front of you, at your height, upright, turned to face you; notice `PF S10 PowerCycle 3D=... D=...` |
| 11 / 12 / 13 | the same for `COM_Quest_Andreja_Q01_SecretPanel` `0FEBB0` / `NPCIDCardReader` `00A329` / `Scenes_MQ101_HellerTechReaderPickUp` `24E491` |
| 20 | **use** the furniture spawned by 10: the 15 s guard timer first, then an input layer and `DisablePlayerControls()`, then `Activate(player)`; 15 s of timed logging |
| 21 / 22 / 23 | the same use for the furniture spawned by 11 / 12 / 13 |
| 40 | a reading of every spawned reference (log only) and **one summary box that stays on screen** (a plain notice if the box does not compile): `PF SUMMARY <furniture>: ENTER <t> SIT <t> GETUP <t> EXIT <t> IDLECHAIRSITTING <t> ANIMATIONCOMPLETE <t> IDLESTOP <t>`, each time in seconds since the activate of the LAST use, `-` when that event did not arrive. Set 40 after the use's 15 s close; close the box with its button |
| 60 | release the layer, disable and delete every spawned reference |

Order: set 10, look (is the panel in view, 3D=TRUE, D about 2.5), then 20. Each stage runs once per loaded save; to repeat one, reload the test save. Use one furniture at a time: set the next use stage only after the `SAFE` / `EXIT OK` / `STILL IN` notice of the last (15 s after its activate). Try the next name (11 then 21, ...) only when the last one gave **no pose** or no ENTER/SIT notice; do not run all four for the sake of it. Finish with 60.

## What the screen says (notices begin `PF `)
`REG n/10 true` registrations of the player's animation names that returned true (first use only). `S10 ...` spawn. `U20 ...` use began (3D, distance). `ACTIVATE s20` the Activate call was made. `ENTER t=` / `EXIT t=` `ObjectReference.OnEnterFurniture` / `OnExitFurniture`; `SIT t=` / `GETUP t=` `Actor.OnSit` / `OnGetUp` (t = seconds since the activate). `SIT STATE n t=` the sit state changed (0 not sitting, 3 sitting; the others in between are the game's). `EV <name> t=` one of the player's animation events (`IdleChairSitting`, `AnimationComplete`, `IdleStop` and the Fallout 4 names `pipboyIdleRoot`, `On`, `Play01`, `Off`, `Done`, `Trans01`, `AnimFinish`, the last ones only to see that they do **not** arrive). `HOLD OFF getup|exit|timer|stage60` the input layer was released and deleted. `SAFE sit=0` the 15 s guard closed the use cleanly. `EXIT ACTIVATE sit=n` the guard found the player still not at sit state 0 at 15 s and activated the furniture once more (the game's own way out). `EXIT OK` / `STILL IN sit=n: FURN DISABLED` its recheck 3 s later. `CLEAN` stage 60 done.
Notices queue (about three visible at once) and a lot can come at once: **record the screen** and read the times from `t=`. With script logging on, the same lines (and one per 0.5 s `sit` line) are in `Documents\My Games\Starfield\Logs\Script\User\FO4SFPFurn.0.log`, each starting `FO4SFPFURN rt=<real time>` and ending `end=true`.

## What each outcome means
| You see | It means |
|---|---|
| The player visibly in a pose **and** `ENTER` or `SIT` **and** `EXIT` or `GETUP` at the end (or `SAFE`/`EXIT OK` after an `EXIT ACTIVATE`) | **Pass** (design section 4): a spawned vanilla one-shot furniture takes the player on `Activate(player)`, and Papyrus hears the end. Note which event ended it and at what `t=`; that event is the signal to copy. Graph events are extra. |
| Pose seen, `SIT STATE` or `ENTER` but **no** end event | Partial: a single-play use ends with no end event Papyrus hears (here). The 15 s guard then released the layer; `SAFE sit=0` is only `GetSitState` = 0 at 15 s (a one-shot may never change the sit state); whether the player left the pose is what the screen shows. The signal has to be something else (timer, or a different event). |
| Pose seen, no `ENTER`/`SIT`/`EV` at all, but `HOLD OFF timer` | The pose does not report to our script: the handlers did not compile (see the stage's `optional` list in `README.txt`) or the events do not exist as guessed. Read the log if it was on. |
| **No pose**: `ACTIVATE` shown, nothing moves, no `ENTER`, `SIT STATE` stays 0 | `Activate(player)` on this spawned copy does nothing. Go to the next name in order (see Order). If all four do nothing the design's fallback is the standing terminal `_Template_Terminal_MissionBoard01` `01D0AB`, which this kit does not carry: report it. |
| `U20` says `3D=FALSE` or `D` far from 2.5 | The reference was not loaded or not moved ahead: the use is not a fair test. A stage runs once per loaded save (setting 10 or 60 a second time does nothing): reload the test save and start again. |
| `EXIT ACTIVATE` then `STILL IN ... FURN DISABLED` | The use did not end by itself and the furniture's own exit did not take the player out; the furniture was disabled. Say what the screen shows now (stuck, free) and use the last-ditch lines below if stuck. |
| Camera | Read it by eye and say: first person or third, locked or free, height. It is a result, not a pass gate (`PowerCycle` has no `FurnitureForce1stPerson`). The log cannot see it. |
| Any of the Fallout 4 names (`pipboyIdleRoot`, `On`, `Off`, `Play01`, `Done`) arriving on the player | Report it: it would mean those names reach the player on a Starfield furniture. Expected: none do. |

## Guards against stranding the player (all in the script)
1. The 15 s timer is started **before** the input layer exists and releases and deletes the layer whatever happened. 2. A player not at sit state 0 at 15 s gets `Activate` once more (and a notice); 3 s later a player still not at 0 gets the furniture disabled. 3. Stage 60 releases the layer and deletes every spawned reference. 4. The layer is also released at once on `OnGetUp` / `OnExitFurniture`. The player's scale is saved before the use and restored when it ends (two of the four, the secret panel and the ID reader, carry `FurnitureScaleActorToOne` per rev 6; PowerCycle and the Heller reader do not).
**Last ditch, only if the timer itself fails** (script stopped, no notices after 20 s): console `enableplayercontrols`, then `player.moveto <a named safe reference you know>`. No save exists to fall back on, so this is the card's line, not the plan.

## Staging (on the PC)
    python scripts\newgame\make_player_furn.py precheck
    python scripts\newgame\make_player_furn.py stage --out <new folder>
    python scripts\newgame\player_furn_install.py install --dir <that folder> --starfield <game dir>    (game closed, the owner's word)
    python scripts\newgame\player_furn_install.py uninstall --starfield <game dir>                      (after the session)

`precheck` looks every native up in `ContentResources.zip` (inheritance followed). `stage` compiles with Starfield's compiler, keeping each optional line that compiles and reporting the rest in `plan.json` and `README.txt`. Required (the stage refuses without them): `Actor.GetSitState` and the four `InputEnableLayer` calls (the guard cannot work without them), `RegisterForRemoteEvent`, `RegisterForAnimationEvent`. Optional (`;OPT`): the four event handlers, the summary box (`Debug.MessageBox`), a switch to third person at the activate (`Game.ForceThirdPerson`: the pose can then be seen; the camera is not put back, press the view key),  `MoveTo`, `SetAngle`, `GetScale`, `SetScale`, `Delete`. Without `MoveTo` the furniture stays at your feet (a bad control: the notice says `D` near 0; do not run it).

## NOT_RUN, stated plainly
- Compiled on the owner's PC at `83a18513` (before the enter-handler fix): the script compiles; `OnGetUp`, `OnSit`, `OnExitFurniture`, `MoveTo`, `SetAngle`, `GetScale`, `SetScale`, `Delete` kept; the `OnEnterFurniture` form with an `ObjectReference` actor was refused, the game's source declares `Actor`, and this head uses `Actor`. Not compiled at this head: restage and read `README.txt` `optional` before the session.
- Not checked against the real `Starfield.esm`: the four ids and editor ids are the Scribe's (reads 15 and 16, Claude's dumps); the tool's `build` is run against a synthetic fixture only.
- No game run. The turn to face the player (`SetAngle` z + 180) is the same convention as variant D, not read from a FURN marker; where the marker puts you is a result.
- Whether `RegisterForAnimationEvent` on the **player** delivers anything is unknown; each registration's return is logged.
