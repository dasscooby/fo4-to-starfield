# A Fallout 4 new game: the Vault 111 start (phase 1)

Written 2026-10-19 by Claude-cloud (the new-game thread). Phase 1 of the approved roadmap: a new game that opens in
Vault 111 with no Starfield intro, which everything else plugs into. **In game three times (28 Oct 2026, sections 10 to 12):
runs 1 and 2 failed (the pirate-fight developer start, then a load that never finished); run 3 (newgame_v9) reached
stage 200, with two placement defects of ours fixed offline in newgame_v10.** **Since newgame_v11 (29 Oct, the owner's
pick F: our own start) the plugin replaces Starfield's start instead of stopping it: a New Game starts our quest, not
MQ101 (sections 1, 2 and 13). v11 crashed at every boot (section 13a); run 4 (newgame_v12, 31 Oct) passed to stage 200
with our own start (section 13b).** Labels follow docs/ai/research-log.md (verified, supported
hypothesis, unresolved).

Files: `dotnet/NewGame/Program.cs` (the plugin writer and its checks), `dotnet/NewGame/Records.cs` (the read-only PC
record reader, section 6a), `scripts/newgame/FO4SF_NewGameQuest.psc` (the
quest script), `scripts/newgame/FO4SF_NewGameLooks.psc` (optional character creation),
`scripts/newgame/FO4SF_NewGameSpecial.psc` (optional SPECIAL at the vault terminal),
`scripts/newgame/FO4SF_NewGameVersion.psc` (optional save version check), `scripts/newgame/make_newgame.py` (precheck,
stage, verify, fold, log reader), `tests/test_newgame.py`.

## 1. What the player gets (the defaults)

1. **Start:** our quest is Starfield's startup quest. The plugin overrides the DefaultObject `StartupQuest_DO`
   (Starfield.esm 00562D, which names `MQ101`, the opening, in vanilla) to name our quest, so a New Game starts ours
   instead of Starfield's opening (our own start, the owner's pick F, 29 Oct; section 2, F). The quest runs once and is
   not start-game enabled, so no save should ever start it (step 2). It starts while the game is still on its first
   loading screen and does there what MQ101's stage 0 would have done: it moves the player (step 4). Nothing else of
   Starfield's moves the player now, and a first load that nobody ends never finishes (run 2, section 11), so the start
   runs from `OnQuestStarted` (the event Roleplayers' Alternate Start, which replaces the same record, moves its player
   from) or from `OnQuestInit`, whichever comes first, once. When the player's 3D has loaded the screen fades in
   (`Game.FadeOutGame(False, True, 0.0, 0.1, False)`, the call Roleplayers' Alternate Start makes once its start cell
   has loaded) and saving and the HUD are turned on: from the start if its wait for the 3D ends with the 3D in, else
   from the timer once it sees it, never before. Which of the two events fires during the load on 1.16.244 is what run 4
   shows (section 13).
2. **Guard:** it acts only on a new game: fewer than one game day has passed and the player is at level 1. Only the
   engine's New Game (and New Game+) starts the startup quest (**supported hypothesis**: the precedent relies on it,
   MQ101 has an NG+ entry, and what reads `StartupQuest_DO` is not in the records report, NG-N4), so a save the player
   made should never start ours, nor an existing save that gains the plugin: the owner's test saves are safe. A session
   started with `coc` from the main menu does not start the startup quest either (**supported hypothesis**: Install's
   map test of 28 Oct found MQ101, the startup quest then, not running). The opening-stage test of newgame_v9 and v10
   (MQ101 running and below stage 105, the 21 Oct review) is gone: MQ101 no longer runs before ours. A New Game+ keeps
   the player's level, so it stands down (stage 1); when either reading of the start says the game is still loading (the
   player's 3D not in, or no parent cell yet: `loading=true` on the `start route` line), the quest first asks MQ101 to
   start (`Opening.StartNoWait()`, which waits for nothing; logged `handing back ...`, then `handed back: ...`), whose
   stage 0 entry 0 is the NG+ start; whether MQ101 started by a script during the first load starts up then and moves
   the player is **unverified** (section 13). The guard now reads days and level during the first load; the readings of
   section 10 were taken a second later, so an NG+ whose level still read 1 then would get our start instead
   (**unverified**; not a hang). A console start on a played save (a game day or more, or above level 1) stands down and
   moves nothing; one in a session under a day at level 1 (a `coc` session from the main menu: Install's map test read
   `days=0.333532 level=1`, section 11) passes the guard and runs the whole start, as a New Game does. The day limit was
   0.25 in the first build, which stood every new game down: Starfield's clock starts at 8:00 and `GameDaysPassed`
   carries the hour, so a new game reads about 0.3335 a second in (**verified** in game 28 Oct, two runs; section 10).
   The guard logs every reading it judges (the `guard` line).
3. **Our start replaces Starfield's opening, and its start quests are held off:** on a start that goes on, nothing
   starts MQ101 any more (only a stand-down during the first load asks it to start, step 2). The quest still stops
   `MQ00` (the main-quest start, start-game enabled), `MQ101` (the opening), `MQ101PostQuest` and
   `MQ_TutorialQuest_Misc04` if they run, and logs each stop: once in the start right after the move, and once more when
   the vault has loaded, for a quest that started meanwhile and for the two that MQ101's stage 9000 starts if something
   had started MQ101 and the first pass stopped it (section 2). The plugin overrides no other Starfield record:
   `MQ101Debug` keeps its value (section 2, B). Right after the hold-off's first pass the quest writes 2 into that
   global itself (`SetValueInt`), logged as `mq101debug written=2.000000 was=0.000000`. 2 is the value the main quests'
   developer skip-start stages write; a normally finished intro leaves 0. It opens the sustenance condition (`MQ101Debug
   != 0`), whose normal route (MQ101 stage 310) is never reached. A hand back never follows the write or the hold-off:
   both come after the move, and both stand-downs return before them.
   Without MQ101's stage 0 nothing empties the inventory or puts on Starfield's miner spacesuit (newgame_v9 and v10
   left the player in it at the pod): what the player wears and carries now is **unresolved** until run 4 (section 13; run 4 is section 13b;
   the inventory reset, section 4c, stays off until then).
4. **The cryo pod:** during the first load the player is moved into the converted Vault 111 (`FO4Port_Vault111Cryo`)
   and stands up one metre in front of their own pod, facing out of it (a port whose COC marker is temporary is refused
   by default since newgame_v11; under `--allow-temporary-anchor` the script first loads the cell by centering on it:
   section 3a; the port of run 3 has the marker persistent). Once the player's 3D has
   loaded, the timer confirms they stand in the vault's cell (`enter vault confirmed after the load ...` when the move's
   own check could not tell yet) and moves them again only if they do not. Since newgame_v10 the player is put 0.3 m
   above the pod's z (`PodLift`) and drops onto the floor: at the pod's own z they sank under it in run 3 and the game
   stood them on the COC marker 8 m away (section 12). The first tick the player is loaded there logs `pod settle
   ok=<bool> ...`. The notification reads "Vault 111" and the objective is "Leave Vault
   111" under FO4's quest name for this part (MQ102's name, read from Fallout4.esm by the points step; "Out of
   Time" is only the fallback when it has none).
5. **Looks:** a message box in the vault asks "Create character" or "Quick start" (NG-6, NG-C9). Create opens
   Starfield's character creation in place of FO4's bathroom mirror and waits for it to close; quick start keeps the
   preset and skips it. A message box needs no voice: the player stays silent (optional script; see section 4).
6. **SPECIAL:** standing at the vault terminal after the looks asks "Set SPECIAL" or "Later". Set opens the
   allocation: FO4's numbers, 1 in each stat, 21 points to spend, 10 at most in one; one button per stat, Reset,
   Confirm, Leave. Confirm writes seven actor values of our own (NG-5, NG-C4; section 4a). The player can skip it and
   ride up; the log then says so (optional script).
7. **The cog door:** standing at its console opens the cog door (no Pip-Boy needed, unlike FO4).
8. **The exit:** standing on the elevator platform asks "Ride the elevator up to the surface?". Yes moves the player to
   the core's Vault 111 map marker and, on a later tick once they are outside and loaded, puts them at FO4's surface
   arrival of the ride, at the right world position (core-local + the measured merge offset), reading the position
   back (`surface setposition ok=<bool>`, three tries). Run 3 set it in the move's own tick and the game ignored it
   (section 12). If the player lands more than 3 m below the arrival, they are put on the Vault 111 map marker's spot.
9. The quest completes. The player is **silent** (Starfield's player has no voice; nothing to do), and has **no
   Pip-Boy** (section 5). The stages the quest passes through are a published contract (section 9).
10. **Save version:** the save records the build's version number when the new game starts. Every later load compares
    it with the installed build's and shows a notification when they differ (NG-15, NG-L2; section 4b). Nothing else
    changes (optional script).
11. **Starting inventory (off by default):** the player keeps whatever Starfield gives them. A `--clear-inventory` build
    empties the inventory (whether quest items stay is **unverified**, section 4c) once the player is confirmed in the
    vault and logs the count; with `--vault-suit <EditorID>` it then adds and equips that armor of the port (NG-K8;
    section 4c). Off until the first in-game run of our own start shows what a game whose MQ101 never ran leaves in the
    inventory.

Every step goes to `My Games\Starfield\Logs\Script\User\fo4sf_newgame.0.log`; `make_newgame.py log` summarises it.

## 2. How Starfield's intro is bypassed

| Option | How | For | Against |
|---|---|---|---|
| **F. Our own start (default since newgame_v11, the owner's pick 29 Oct)** | The plugin overrides the DefaultObject `StartupQuest_DO` (Starfield.esm 00562D; **verified**, records report PC 21 Oct: it names MQ101 003448; that the engine starts the quest it names on a New Game is what the precedent below relies on) to name our quest, which is run once and not start-game enabled. The writer refuses a Starfield.esm whose `StartupQuest_DO` is missing, sits at another id than 00562D or names another quest than MQ101, and `check` holds the plugin to exactly one DFOB, that override, and to our quest as its only QUST. The quest moves the player into the vault itself during the first load and fades the screen in once the player's 3D has loaded (section 1, steps 1 and 4); A's hold-off and B's write stay, after the move. A start that is not a new game, or cannot move the player, stands down and, when either reading says the game is still loading (the player's 3D not in, or no cell yet), first asks MQ101 to start (`HandBack`, `StartNoWait`) | MQ101 never runs, so nothing of the intro (character generation on, its input layer, the miner suit, the stop's stage 9000) has to be undone; no save should ever start our quest (**supported hypothesis**, section 1 step 2). Shipped precedent: Roleplayers' Alternate Start and No Ship Fast Start override the same record (research, 28 Oct). The deployment gate's start check passes exactly one plugin of ours overriding it (`fo4sf.core.preflight` `check_start`) | One Starfield record overridden (removing our plugin undoes it). Anything of Starfield's that waits on MQ101 having run is **unresolved**. That `OnQuestStarted` fires during the first load for our quest, that a MoveTo then ends that load in the vault and that the screen then comes in on 1.16.244 are **supported hypotheses** (the precedent; MQ101's intro makes no fade call of its own) until run 4 (section 13); if neither start event comes, the load hangs as run 2 did, and newgame_v10 is the way back. That MQ101 started by a script during the first load moves the player (the hand back, the stand-downs' only way out of that load) is **unverified**: no run has stood down during it, and run 4 should not either |
| A. Stop the opening quests at start (the default until newgame_v10; kept in F, after the move) | Our start-game quest stops MQ00, MQ101, MQ101PostQuest and MQ_TutorialQuest_Misc04 from Papyrus (`Quest.Stop`), then moves the player. **verified** (ContentResources.zip, PC 19 Oct): MQ00's only fragment, stage 10, sets MQ101Debug to 10, waits 0.1 s and starts MQ101; MQ101Script's OnQuestInit jumps to stage 400 only when MQ101Debug reads 1. **verified** (records report, PC 21 Oct): MQ00 is "Important Script Functions and Aliases", StartGameEnabled with 18 aliases, and its stage 10 is not a start-up stage, so vanilla never runs it; holding MQ00 off is no longer load-bearing and stays in the list only as the approved default. **verified** (19 Oct read): MQ101's stage 9000 runs on stop; it always starts MQ101PostQuest and, when the player never entered the Unity, MQ_TutorialQuest_Misc04, and restores neither saving nor the HUD. So the script walks the hold-off list a second time one tick after the first pass (NG-19, NG-N1) and restores saving and the HUD itself | Edits no Starfield quest record; reversible by removing our plugin; the list is a build option (`--hold`) | **verified** (run 3, 28 Oct, section 12): one tick is enough; pass 2 held MQ101PostQuest and MQ_TutorialQuest_Misc04, and MQ101 had not restarted. With no override the intro's stage 0 has run (character generation on, the move to its start marker, the chargen HUD mode) before our quest starts, so the hold-off stops a running intro; in run 3 saving and the HUD came back (a save at 18:11:36) and the owner walked on to Concord. Anything of the intro run 3 did not show (its controls layer, menus) stays **unverified**; runs 1 and 2 never reached the hold-off |
| **B. The debug global (written after the hold-off by default: `--debug-after-hold <n>`, 0 for no write; `--mq101debug <n>` overrides the record, experiments only)** | No record override. Right after hold-off pass 1 (which stopped a running MQ101 before F; under F MQ101 never runs), the quest writes 2 into Starfield's GLOB `MQ101Debug` (0A7D31) with `SetValueInt`. **verified** (records report, PC 21 Oct, lines 352 to 396; the fragment sources, PC 19 Oct; the owner's two runs, 28 Oct): MQ101's stage 0 has 12 log entries, ten of them conditioned on the global. Entry 0 is the NG+ start (`PlayerUnityTimesEntered >= 1`, whatever the global holds). Entry 2 (`== 0`) is the normal intro: its fragment (`Fragment_Stage_0000_Item_02`) disables controls in MQ101's input layer, turns character generation on, moves the player to `CharGenStartMarker`, sets the chargen HUD mode and waits for the player's 3D; after the wait it empties the inventory, equips the miner spacesuit, helmet, backpack and clothes, and takes Lin's and Heller's weapons. Nothing after its 3D wait sets a stage or starts a scene, so stopping MQ101 then leaves nothing that restarts it. Entries 1 and 10 (`== 1`, `== 10`) and 3 to 9 (6, 3, 4, 5, 7, 8, 9) are developer starts, each moving the player itself; entry 11 has no condition and only ghosts Lin, Heller and Barrett. Entry 10's fragment (`Fragment_Stage_0000_Item_10`) moves the player to the Scene08 marker, equips the miner gear and the Cutter, enables Barrett's ship, sets stages 210 and 250 ("make pirate ship land") and the local time to 10: the pirate fight with no cutscene and no mine, where the owner landed in run 1 (log: `opening_stage=250`). A value no entry matches moves nobody: the second build's override of 2 left the new game on its loading screen (run 2, section 11). MQ00's stage 10 writes 10 and starts MQ101, but nothing runs that stage on a New Game (the records report: it is no start-up stage; StartupQuest_DO 00562D starts MQ101), so the 19 Oct belief that vanilla writes 10 was wrong. 2 is the value the main quests' developer skip-start fragments write (MQ102 to MQ305, FFLodge01 and City_NA_Viewport02, each of which then jumps MQ101 to its end: 1800 and 1810, or 2000); a normally finished intro leaves 0 (MQ101's own fragments never write the global). Writing it opens PEO_SustenanceAllowed's `MQ101Debug != 0`, whose normal route (`GetStageDone(MQ101, 310)`) a held-off intro never reaches (NG-2, NG-M1; its four conditions are in the 21 Oct report). SKK Fast Start's 8 is entry 8 (New Atlantis), a start that moves the player itself; RoleplayersAlternateStart writes its unmatched 11 only after its own quest has placed the player (the research thread's read, 28 Oct), the same order as ours | No record touched; the write comes after the hold-off's first pass (before F that pass had stopped MQ101; under F it also follows the move, and no hand back follows it), so MQ101's stage 0 never reads it; sustenance stays possible | **verified** (run 3, section 12): `mq101debug written=2.000000 was=0.000000`. That nothing reads the global in the moment between the stop and the write is **unverified** |
| C. Override MQ00 / MQ101 without StartGameEnabled | Plugin overrides of Starfield's quest records | The opening never starts | Edits Starfield records; anything that expects MQ101 (NG+, Constellation, achievements) may break; hardest to undo in a save |
| D. Our own start menu (as SKK) | A message box after character creation picking Vault 111 or Starfield's own start | Players keep the choice | More UI; only worth it once the Fallout start works |

The ladder for the next in-game proof: the default (F, with A's hold-off and B's write of 2 after the move) first. If
our own start fails (section 13's failure readings), the way back is newgame_v10 (restage main d9958261, the last
build that stops Starfield's opening instead), where the old ladder applies: `--debug-after-hold
0` if the write itself does harm (the global then stays at the intro's 0, and PEO_SustenanceAllowed's `!= 0` stays
closed). `--mq101debug 8` (SKK's New Atlantis start, a value an entry matches) was **not** a rung with v10's guard:
entry 8 sets MQ101's stages 500 and 1310 itself, so the guard would read the opening past 105 and stand down, as it did
in run 1. Never an override no entry matches (2, 11): it hangs the first load (section 11). `--mq101debug 10` is the
first build's pirate-fight start, kept only to reproduce run 1; C only on the owner's word.
Which of Starfield's other 142
start-game quests to hold off (the ship, the radiant parents, city and companion quests, generic dialogue) is the
`npcs-ai-factions-dialogue-quests.md` section 8 list; the first proof records what runs (`sqv`) before more are added,
because stopping SQ_PlayerShip or SQ_ENV could break the HUD or travel.

## 3. Where the player goes, and why the plugin has no masters but Starfield.esm

- **verified:** FO4Port.esm places FO4 interiors at FO4 position / 70 (metres) in cells named `FO4Port_<cell>` and puts
  each cell's COC marker on Starfield's `COCMarkerHeading` 000032 (`dotnet/PluginSpike`, WP10); `coc
  FO4Port_Vault111Cryo` works in game (journal 2026-10-08, the bridge runs).
- **verified:** persistent references of the core's world stay at their core-local position; MoveTo onto such a
  reference puts the player in the core world at that local spot, and SetPosition to local + (-1200, -2700) then puts
  them where FO4 has it (door probe (e), the Super Duper Mart round trip PASS 17 Oct, `FO4SF_LoadDoor`
  UseDestinationPosition). The new game uses the same two steps for the elevator exit.
- So the script resolves its places at run time with `Game.GetFormFromFile(id, plugin)` (the `FO4SF_LoadDoor`
  contract): the vault anchor is a reference of `FO4Port_Vault111Cryo`, persistent when the cell has one (its COC marker
  when that is persistent, else the port's persistent reference nearest to it) and otherwise the cell's temporary COC
  marker, which the script must load the cell for first (section 3a: a temporary reference in an unloaded cell resolves
  to none, 16 Oct probe), and every resolved reference must be the named plugin's own record; the exit anchor is the core's persistent
  `FO4Core_CommonwealthMapMarkerVault111`; the cog door is the port's reference keyed
  `REFR:FO4Port_Vault111Cryo:0330C3:Fallout4.esm` (Mutagen prints six digits; the id is matched as a number) in its stable `formids.json`. The writer reads the port, its
  `formids.json` and the core to find those ids and refuses when any is missing or ambiguous; `check` re-reads them.
  Because port and core ids are stable across rebuilds, a rebuilt port or core does not need a rebuilt plugin, but the
  stage pins their SHA-256 and `verify` refuses an install against other bytes until the stage is re-run (a quick,
  offline re-check).
- Alternative: master FO4Port.esm and the core and place our own markers (a WRLD and CELL override, as the mission
  does). That costs a rebuild after every port or core build and ties the start to one build pair.

## 3a. The vault anchor: persistent, or the temporary COC marker

- **The evidence (PC, 21 Oct, real data):** the installed port's `FO4Port_Vault111Cryo` has **0 persistent references of
  1,166**; its COC marker is `001338:FO4Port.esm`, temporary, and every terminal is temporary. So the writer as it stood
  refused the build ("has no persistent reference of FO4Port.esm to anchor the start on"). **verified** (16 Oct probe):
  a temporary reference in an unloaded cell resolves to None via `Game.GetFormFromFile`, and `player.moveto` a
  non-persistent reference fails. A later port build (another thread) will make each cell's COC marker persistent with
  the same form id; until then the start needs a way in that does not depend on a persistent reference.
- **Two modes, one property.** The writer's `Resolve` prefers a persistent anchor (the COC marker when it is persistent,
  else the port's persistent reference nearest to it) and writes `AnchorTemporary = false`: the **persistent mode**, the
  one the start returns to by itself once the port marks its COC markers persistent (the id stays, so the same plugin
  needs no rebuild beyond the re-stage that pins the new port's bytes). When the cell has no persistent reference the
  writer anchors on the temporary COC marker itself and writes `AnchorTemporary = true` and `VaultCell =
  "FO4Port_Vault111Cryo"` (the cell's EditorID): the **temporary mode**. `write` and `check` print the mode after the
  anchor's id (`vault anchor FO4Port.esm:001338 temporary`), `offline_check.txt` keeps the line, `make_newgame.py` reads
  it into plan.json as `anchor` and `check` holds a build to its mode (a temporary-anchor build fails the check against
  a port with a persistent reference, and the other way round). **Since newgame_v11 the refusal is the default:** with
  our own start the centering comes during the first load, and a centering counts as a move, so one that moves nobody
  hands nothing back and that load would never end (the 29 Oct review on #588). `--allow-temporary-anchor` builds the
  temporary mode on request; `--require-persistent-anchor` is kept for old command lines and changes nothing.
- **The script in the temporary mode:** `EnterVault` resolves the anchor as before. When it comes back None and
  `AnchorTemporary` is set, `CenterOnVault` calls `Debug.CenterOnCell(VaultCell)` once, logs `centered on
  FO4Port_Vault111Cryo attempt=1 tick=1: ...` and returns false, so the existing 1 s retry resolves the now-loaded
  marker and does the same `MoveTo` with the pod's offset: the player, already standing in the cell on the COC marker
  after the centering, still ends at their pod, and the `enter vault ok=` line is the same proof as in the persistent
  mode. The wait is bounded once the player's 3D is in: after `CenterTicks` (30) tries without the anchor resolving the
  script centers once more, at most, and past that logs a failure line every 10 tries (`vault anchor FO4Port.esm:<id>
  does not resolve after <n> ticks and <m> centerings on FO4Port_Vault111Cryo: the temporary-anchor start failed`)
  instead of recentering in a loop. The tries after the first are the timer's, and the timer waits for the player's 3D
  before it tries: a centering during the first load that moves nobody leaves the 3D out, so none of this follows, and
  the timer's `waiting for the 3d tick=<n> vault_moves=0 centered=1 ...` line every 10 ticks is the only trace (section
  13). The guard runs before the first `EnterVault` (once, in the start), so a centering never re-judges it; a centering
  counts as a move under way, so the start goes on to the hold-off and the write as after a MoveTo and never hands back
  (the reason the mode is built only on request). Whether a centering during the first load ends that load in the vault,
  as a MoveTo does, is **unverified** (the installed port's anchor is persistent: run 3). The persistent mode never
  centers.
- **What is unverified:** FO4 declares `Function CenterOnCell(string asCellname) native global` in Debug.psc.
  Starfield's Debug.psc declares the same `CenterOnCell` and also `CenterOnCellAndWait` (**verified**:
  ContentResources.zip, read 29 Oct; it is in the quest script's NATIVES, so the precheck reads it on every build);
  whether the call works in retail Starfield, loads the cell and leaves the player in it is **unverified** until the PC
  run (the `centered on` line followed by `enter vault ok=True` is the proof; the failure line is the counter-proof, or
  the timer's `waiting for the 3d` lines when the centering came during the first load). The selftest covers the
  resolver and the plugin: the no-persistent-reference fixture (every reference of the cell temporary, as on the PC on
  21 Oct) is refused by default and writes a temporary-anchor build under `--allow-temporary-anchor`, and mutations of
  `AnchorTemporary` and `VaultCell` are rejected.
- `make_newgame.py log` prints `centered` (the first centering line's text; None in the persistent mode).
- Run 3 (28 Oct, section 12): the installed port's COC marker `001338` is persistent now (`anchor_temporary=false`), so
  the persistent mode ran, with no centering.

## 4. The cryo pod and character creation

- FO4 (**verified**, B4 spike): MQ102 opens the pod after the cut scene; the player has no Pip-Boy until the overseer's
  office; the cog door console needs it (stage 5 and a fail sound without it, stage 7 seats the player and plays the
  plug-in animation).
- Ours: no cut scene and no pod animation (the pod is a converted static). The player stands one metre out of the pod
  along its facing. Which of the pod's axes faces out is a **supported hypothesis** (+Y turned by its z rotation); the
  points step prints every candidate pod (on the PC: MQPlayerCryopodREF 0004A011, the player's, and MQPlayerSpousePodREF
  0004A012, which the rule skips), and `--pod-ref` names one if that ever changes. If the move
  misses the cell, the quest retries each second; the log shows the landing. The pod's z is under the hall's floor
  (run 3, section 12: the player sank there), so since newgame_v10 the start is `PodLift` (0.3 m) higher and the
  `pod settle` line says where the player stands once loaded. Facing out: run 3's bridge read heading 0 after the
  move, the direction of the step (the start is 1 m along +y from the pod's origin).
- The opening choice: once the player is in the vault, `FO4SF_NewGameLooks` shows MESG `FO4SF_NewGameStart`
  (FO4SFNewGame.esm 0x802), "Create character" or "Quick start". The owner decided (2026-10-19, NG-C9) that phase 1
  has a preset quick start for replays: button 1 skips the creator and keeps the look the player already has (the
  game's default new player; a shipped Fallout-style face preset is a later item, NG-M9). Button 0 opens the creator.
- Character creation: `Game.ShowRaceMenu(None, RaceMenuMode)`. **verified** (PC read, 19 Oct): Starfield's Game.psc
  declares `ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0, ...)`, the modes FO4's (0 chargen, 1
  remake, 2 haircut, 3 surgery, 4 face paint). The owner wants a looks-only creator (NG-C3); which mode that is, and
  what each shows with MQ101 stopped, is **unresolved** until the in-game C1 test (one mode per run). So the mode is a
  writer option, `--race-menu-mode <n>` (default 0, the full creator), written into the looks script's `RaceMenuMode`
  property; `check` and the selftest hold a build to its mode.
- Waiting for the creator: Starfield's Utility.psc has **no** `IsInMenuMode` (verified, PC precheck 19 Oct).
  **verified** (PC read, 19 Oct): ScriptObject has `RegisterForMenuOpenCloseEvent(string)` and the creator's menu is
  "ChargenMenu" (9 vanilla registrations). The looks script registers for it before the menu opens and sets stage 20 in
  `OnMenuOpenCloseEvent` when "ChargenMenu" closes. The event handler is written with FO4's signature
  `(string asMenuName, bool abOpening)`, **unverified** until the Papyrus compile on the PC; the precheck looks the
  registration and the event up in ScriptObject.psc, and a miss means `--no-looks`. The quest's `LooksWait` (120 s from
  stage 10, so it also covers a player who leaves the choice open) stays as the fallback. The log says which ended the
  wait: `looks done: creator closed`, `looks done: quick start` or `looks done: LooksWait fallback after <LooksWait> s`
  (Papyrus prints the float as `120.000000`); `make_newgame.py log` prints the first ending as `looks_done`. A later
  ending is not logged: once stage 20 is set, the looks script's `Done` does nothing.
- The looks script stays separate so a failed compile drops only it (`--no-looks`, and the quest then does not wait
  and shows no choice). FO4's own looks menu and the bathroom mirror are a later UI item (Scaleform;
  animations-ui-and-start.md section 3). SPECIAL is set at a vault terminal (NG-C4), not here (section 4a).

## 4a. SPECIAL at the vault terminal

- The owner decided (2026-10-19, NG-C4 / NG-K7, page NG-5): SPECIAL is set at a vault terminal for testing; the
  elevator version comes with the remade start. FO4 sets it pre-war with the Vault-Tec Rep, which our start skips.
- The stats: seven AVIF records of our own, `FO4SF_Special_Strength` to `FO4SF_Special_Luck` (FO4SFNewGame.esm 0x810 to
  0x816), each a SpecialAttribute with default 1, range 1 to 10, and the record's flags that name the same numbers
  (DefaultToOne, MinimumOne, MaximumTen: Mutagen's names for the AVFL bits). Starfield has no SPECIAL values, and
  nothing in this repo reads a Starfield AVIF back in full, so the record shape is minimal (name, abbreviation, type,
  default, min, max, those three flags) and **unverified** until the PC run opens the plugin in xEdit next to a shipped
  AVIF. Later phases read the player's values from these records (`Actor.GetValue`).
- The terminal: the points step lists every placed TERM of FO4's Vault111Cryo, nearest the player's pod first (the cryo
  hall's terminals stand by the pods), or the one `--terminal-ref <hex>` names. The writer takes the first of them the
  port carries (its `formids.json` key `REFR:FO4Port_Vault111Cryo:<FO4 id>:Fallout4.esm`), a persistent one preferred,
  and refuses a key that names a reference outside the cell or another plugin's record, as it does the anchor and the
  cog door. When the port carries none, the id is 0 and the prompt watches FO4's spot of the nearest terminal (the
  position is FO4's / 70 either way). A points.json without a terminal refuses a SPECIAL build: `--no-special`, or
  `--terminal-ref`. Which terminal the real cell gives, and whether the installed port carries it, is **unresolved**
  until the PC build (the points step prints every candidate; `offline_check.txt` prints the pick).
- The prompt: `FO4SF_NewGameSpecial` waits for stage 20 (the looks done), then shows MESG `FO4SF_NewGameTerminal`
  (0x803) once per visit when the player stands within 2.5 m of the terminal: "Set SPECIAL" or "Later". Set runs MESG
  `FO4SF_NewGameSpecial` (0x804) in a loop: its text has one `%.0f` token per stat and one for the points left, filled
  from `Message.Show`'s float arguments; the ten buttons are the seven stats, Reset, Confirm and Leave. A stat button
  adds a point (nothing past 10 in one stat, nothing with no points left); Confirm only applies with every point spent
  (a notification says how many are left); Leave keeps the defaults. The loop is bounded: after 300 presses without
  Confirm or Leave (`MaxPresses`, `SPECIAL_MAX_PRESSES`; a pass takes about 22) it ends as Leave and logs it, so a
  message box that returns at once cannot spin. Confirm writes each value with
  `Actor.SetValue(Special[i], value)` and reads two back into the log. `make_newgame.py special_press` is the same
  rule, tested in Python; the three constants live in `SPECIAL_BASE`, `SPECIAL_POINTS`, `SPECIAL_MAX` and are held
  equal to the writer's and the script's by `tests/test_newgame.py`.
- **Unverified** until the PC run: `Actor.SetValue` / `GetValue` with a plugin's own AVIF (FO4's Actor.psc declares
  them; Starfield's Actor.psc does not, but the script compiled for newgame_v7 on 23 Oct, so a script higher in Actor's
  `extends` chain does: the precheck follows that chain since run 2, section 11, and only a miss along the whole chain
  means `--no-special`), the `%.0f` token substitution in a Starfield
  message box, and a ten-button message box (FO4's MESG limit).
- The quest never waits on SPECIAL: the player can ride the elevator with it unset. The script logs
  `special skipped: left the vault with SPECIAL unset` at stage 40, `special set S=.. P=.. ...` on Confirm, `special
  later` and `special left: ...` for the other buttons; `make_newgame.py log` prints the first ending as `special`.
- The script is separate for the same reason as the looks script: a failed compile drops only it (`--no-special`, and
  the plugin then carries no AVIF and neither MESG).

## 4b. The save version check

- The owner decided (2026-10-19, NG-F5 / NG-L2, page NG-15): a save version from v1, checked on every load with a
  visible warning. This is the first half; the launcher's block on unsafe swaps is a later item.
- The version: GLOB `FO4SF_NewGameVersion` (FO4SFNewGame.esm 0x805) holds the build's version number, `--build-version
  <n>` (default 1, `DefaultBuildVersion` in the writer and `DEFAULT_BUILD_VERSION` in Python, held equal by the tests).
  Bump it when a save made under the old build must not go on under the new one. The GLOB is flagged **Constant**: the
  Creation Kit documents a constant global as not saved, so a loaded save reads the installed plugin's number, not its
  own. Whether Starfield's save keeps that rule is **unverified** until the PC run.
- The alias: the quest's alias 0, "Player", is forced to the player (`PlayerRef` 00000014, the engine's fixed id; the
  door probe reads the player as ref 20). It carries `FO4SF_NewGameVersion`, bound through the quest's VMAD alias
  fragment (the quest's form and the alias id, the shape Mutagen reads back; whether the game binds the script the same
  way is **unverified** until the PC run).
- The script: when the alias fills (`OnInit`, a new game) it writes the GLOB's value into its `SavedVersion` property
  once; the save keeps it (-1 until then). On `OnPlayerLoadGame` (**verified**, PC read 19 Oct: declared on Actor and
  ReferenceAlias) it reads the GLOB again, logs `version load saved=<n> installed=<n>`, and on a mismatch logs `version
  mismatch` and shows "Fallout 4 new game: this save is from build <n>, the installed build is <n>". It sets no stage,
  moves nothing and writes no value: the save is left as it is. `make_newgame.py log` prints `version_saved`,
  `version_load` (the last load's line; a load logs no `init`, so it joins the run before it) and `version_mismatch`.
- Limits: a save that stood the quest down (stage 1, an existing save that gained the plugin) has no check, because the
  quest stops and the alias clears; nothing of ours is in that save to version. Whether the alias stays filled after the
  quest completes at stage 200, and so still receives the load event, is **unverified** until the PC run: the `version
  load` line on a reload after a completed start is the proof. If it does not, the check moves to a quest of its own.
- The script is separate for the same reason as the other two: a failed compile drops only it (`--no-version`, and the
  plugin then carries no GLOB of its own and no alias). The precheck looks `OnPlayerLoadGame` up in ReferenceAlias.psc
  and `OnInit` in ScriptObject.psc; a miss means `--no-version`.

## 4c. The starting inventory reset

- The question (NG-K8, with NG-N3): FO4's MQ101 runs `PlayerREF.RemoveAllItems()` at stages 0 and 900 (**verified**
  from the SKK FastStart article and a forum post, research note 06-fo4-vault111-chain; the fragment itself was not
  read); Starfield's MQ101 stage 0 entry 2 (the intro) runs `RemoveAllItems()` after its 3D wait and equips the miner
  spacesuit, helmet, backpack and clothes (**verified**, PC read of QF_MQ101_00003448.psc, 19 Oct; NG-N3 answered).
  In newgame_v9 and v10 that fragment ran before our quest, so a default build left the player in the miner suit at the
  pod (**unverified** in game: run 3's screenshots are first person and a default build logs no inventory line, section
  12). Since newgame_v11 MQ101 never runs, so neither does that fragment: what a New Game leaves the player with then is
  **unresolved** until run 4 (section 13; run 4 is section 13b). `--clear-inventory --vault-suit <the port's Vault 111 suit EditorID>` stays
  the answer for a start that does not depend on it: the reset runs once the player is confirmed in the vault. The reset stays a writer option, **off by default** until the owner picks it:
  `--clear-inventory`, and the quest script's `ClearInventory` property (false) and `VaultSuitId` (0) record the choice in
  the plugin; `check` holds a build to it, and the selftest's cross-option runs reject a build read under the other
  setting.
- When on: once the player is confirmed in the vault (the timer's first tick after the 3D has loaded) and before stage
  10, `ResetInventory` calls `player.RemoveAllItems(None, false, false)`, reads `GetItemCount(None)` before and after
  and logs `inventory cleared removed=<n> left=<n>`. Both natives are written with FO4's signatures; Starfield's
  `ObjectReference.psc` is what the precheck reads, and a miss fails the core script (there is no `--no-...` for it: the
  property is off, but the script must compile). Starfield's third parameter of `RemoveAllItems` is
  `abRespectTargetCapacity` (`ObjectReference.psc`, ContentResources.zip, read 29 Oct), so whether quest items stay is
  **unverified**: `left=` says how many items stayed, not which. Whether Starfield's `GetItemCount(None)` counts every
  item, as FO4's does, is **unverified**: both numbers are logged so the proof can say.
- The suit: `--vault-suit <EditorID>` (only with `--clear-inventory`; refused alone) names an ARMO of FO4Port.esm. The
  writer resolves it offline exactly as it does the anchors and the terminal: exactly one ARMO of that EditorID (any
  case) in the port, the port's own record, else refused (none, two, or another plugin's record). The script resolves it
  with `Game.GetFormFromFile(VaultSuitId, VaultPlugin) as Armor`, `AddItem(suit, 1, true)` and
  `EquipItem(suit, false, true)` (silent), and logs `vault suit equipped <armor> worn=<IsEquipped>`, or that the id did
  not resolve. Whether the installed port carries a wearable vault suit ARMO at all, and under which EditorID, is
  **unresolved**: the owner names it when it exists; the selftest uses a synthetic `FO4Port_VaultSuit111`.
- `make_newgame.py log` prints `inventory_cleared` and `vault_suit` (None when the build kept the inventory, or named no
  suit); plan.json records `clear_inventory` and `vault_suit`.

## 5. What Vault 111 needs from the port today

| Piece | State | Source |
|---|---|---|
| The cryo hall, corridors, stairs | converted and walkable (`coc FO4Port_Vault111Cryo`), sliding doors work | ROADMAP, owner rows 1 and 6 |
| Gear-room gates passable, gear-pit water sheet | fixes on main (static gate leaves, water planes left out); need an interior rebuild | ROADMAP Phase A table |
| Cog door VltGearDoor01 | converted as a door with its own rig (Stage2 as Open, `pipeline.OWN_RIG_ALIASES`, tests/test_cog_door.py); in game it was still a solid static on integ_1018. Whether the installed port carries the rigged door and whether `SetOpen` opens it: **unresolved** | ROADMAP, door_motion.py |
| Cog door console | FO4 activator with MQ03ControlPanelScript; ours is only a spot the quest watches | B4 |
| The SPECIAL terminal | FO4 TERM references of the cryo cell; the converted one is a prop, the SPECIAL script watches its spot (section 4a). Which one the port carries: **unresolved** | this plugin |
| Exit elevator | not connected: both autoload doors (interior 01F180, surface 0998E3) are marker doors the converter never places (`door_skipped`); the elevator is an animated activator. The new-game quest's prompt replaces the ride | scripted-doors.md, research log 2026-10-14 |
| Going back down | not handled: the surface elevator and the descend trigger are not converted; the doors phase owns it | B4 |
| Pip-Boy, the overseer's office skeleton, the cryo cut scene, the spouse, Kellogg | none: later phases (UI with SFSE; NPCs and scenes) | animations-ui-and-start.md |
| The surface arrival | core-local, from the XTEL of 01F180; whether the surface elevator platform is solid there is **unresolved**, hence the fall check and the map-marker fallback | this plugin |

## 6. Build recipe (PC, offline, no game)

1. `python scripts\newgame\make_newgame.py precheck --out D:\Modding\scratch\newgame\precheck.json` reads
   ContentResources.zip only and lists every native and event the four scripts use and every MQ101Debug line. Exit 1
   means a core native is missing: stop and report. A missing `Game.ShowRaceMenu`, `RegisterForMenuOpenCloseEvent` or
   `OnMenuOpenCloseEvent` means stage with `--no-looks`; a missing `Actor.SetValue` or `Actor.GetValue` means
   `--no-special` (a function counts as present when any script in the base's `extends` chain declares it, as the
   compiler resolves it); a missing `OnPlayerLoadGame` or `OnInit` means `--no-version`. The inventory reset's natives
   (`RemoveAllItems`, `GetItemCount`, `AddItem`, `EquipItem`, `IsEquipped`) belong to the quest script, so a miss there
   is a core miss (section 4c). So do our own start's (section 13): `Game.FadeOutGame`, `ObjectReference.WaitFor3DLoad`,
   `Quest.StartNoWait` and `Quest.IsStarting` (the hand back) and the start events `OnQuestStarted` and `OnQuestInit`,
   which the looks and SPECIAL scripts start on too.
2. `python scripts\newgame\make_newgame.py stage --out D:\Modding\staging\newgame_v1 --fo4 <Fallout4.esm> --port
   <installed FO4Port.esm> --port-ids <that port build's formids.json> --core <installed FO4TerrainCore.esm>` runs
   points, write, check and the Papyrus compile, then writes plan.json and README.txt. Inputs are read only; the output is
   one new folder on D:.
   Options: `--hold <list>` (default `MQ00,MQ101,MQ101PostQuest,MQ_TutorialQuest_Misc04`), `--debug-after-hold <n>`
   (default 2, the value the quest writes after the hold-off; 0 writes nothing), `--mq101debug <n>` (a GLOB override,
   none by default, experiments only: a value no MQ101 entry matches hangs the first load, section 11;
   `--no-mq101debug` is kept for old command lines: alone it changes nothing, but it still cancels a `--mq101debug`
   given with it), `--no-looks`, `--race-menu-mode <n>` (default 0, section 4),
   `--no-special` (section 4a), `--no-version`, `--build-version <n>` (default 1, section 4b), `--pod-ref <hex>`,
   `--terminal-ref <hex>`, `--clear-inventory` and `--vault-suit <EditorID>` (off by default, section 4c), and
   `--allow-temporary-anchor` (build on a vault cell without a persistent reference, the temporary-anchor mode, section
   3a; refused by default since newgame_v11, and `--require-persistent-anchor` is kept for old command lines). plan.json
   records them, the anchor's id and mode (`anchor`), and the stage contract.
3. The offline checks are `offline_check.txt` (every record, property and resolved id) and the selftest (`dotnet run -c
   Release --project dotnet\NewGame -- selftest <scratch>`, synthetic masters and mutations). The selftest builds the
   default, `--no-looks`, `--mq101debug 0`, `--mq101debug 8`, `--debug-after-hold 0`, `--mq101debug 10`, no-cog-door,
   two-quest-hold, `--race-menu-mode 1`, `--no-special`, temporary-terminal-only, `--no-version`, `--build-version 2`,
   `--clear-inventory` and `--clear-inventory --vault-suit` variants, and each build must fail `check` under the others'
   options; `--vault-suit` without `--clear-inventory`, without an EditorID, or naming an ARMO the port lacks, has
   twice, or that another plugin owns is refused. A port whose vault cell has no persistent reference (every reference
   temporary, the shape of the port installed on 21 Oct) is refused by default; under `--allow-temporary-anchor` it
   builds a temporary-anchor plugin whose `write` and `check` lines say `temporary` and that fails `check` against the
   port with persistent references (and that build fails against it). It also checks the four MESG records (two buttons
   each, ten on the allocation), the seven AVIF, the looks script's `StartMessage` and `RaceMenuMode` properties, the
   SPECIAL script's list, messages and terminal, and the version GLOB (its value and Constant flag), the player alias
   (forced to 00000014, the only alias) and the alias script's binding and `BuildVersion` property; the terminal pick
   prefers a persistent reference and refuses a foreign or missing one. Our own start: the plugin's one DFOB must be
   Starfield's `StartupQuest_DO` naming QUST 0x800, the quest run once and not start-game enabled, and our quest the
   plugin's only QUST (mutations: the override removed, naming MQ101 or MQ00, renamed, a second DFOB, a new DFOB of ours
   named `StartupQuest_DO` instead of the override, the quest start-game enabled again, an MQ101 override added), and
   `write` refuses a Starfield.esm without `StartupQuest_DO`, with one naming another quest than MQ101, or with one at
   another id than 00562D (`check` refuses the default build against the second).
4. Install is a later owner line: `fold` into a copy of the installed core set, `verify`, then `exp_install.py`, game
   closed, after the current v6e test. Testing needs a NEW game, so it never touches the owner's saves.

## 6a. The record reader (PC, read only, no game): one run for newgame.md sections K and N

`dotnet/NewGame/Records.cs` adds the `records` verb: it opens Starfield.esm, Fallout4.esm and the installed FO4Port.esm
read-only (Mutagen 0.55.0-alpha.67) and writes one plain-text report. Nothing else is written; a plugin or record that
is missing is said so in its section and the run still exits 0. The exact PC command (Fallout 4's Data folder is the
argument; Starfield's defaults to `D:\SteamLibrary\steamapps\common\Starfield\Data`, `--sf-data` for another):

```
dotnet run -c Release --project dotnet\NewGame -- records "<Fallout 4>\Data" --out D:\Modding\scratch\newgame\records.txt
```

Options: `--sf-data <dir>` (Starfield's Data folder), `--port <path>` (another FO4Port.esm than `<sf-data>\FO4Port.esm`),
`--nearest <n>` (how many persistent references the anchor section lists, default 30). The report's sections, and the
newgame.md question each answers:

| Section | Answers | What it lists |
|---|---|---|
| `NG-K1` | NG-K1 | MQ102 (Fallout4.esm 0001CC2A): every stage with its flags, each log entry's flags, text and conditions, the script fragments per stage, and `completes: stage <n>` for the log entries flagged CompleteQuest (or that none is, and completion is scripted) |
| `NG-K2` | NG-K2 | MQ101 (Fallout4.esm): stages 710 to 1000 in the same detail (the cryo scene, 770, 900) |
| `NG-K4` | NG-K4 | every reference in the port's Vault 111 cells (`FO4Port_Vault111*`) whose base record's EditorID mentions PipBoy: cell, reference, base, position (metres), persistence. None means the converted vault has no Pip-Boy prop under that name |
| `NG-K9` | NG-K9 | the conditions that reference MQ102 on records named Codsworth, Dogmeat or Min00 (quests: their own conditions, stage log entries, aliases, objective targets; dialogue responses, scenes and packages named so or owned by a quest named so) and on MQ102's own aliases named for them. It also reads NG-K3 (stage 6 sits in the K1 table) |
| `NG-N4` | NG-N4 (and NG-M1, NG-A1) | Starfield's MQ101 stage 0: each log entry's conditions and the stage's fragments (which of the 12 starts runs under which MQ101Debug value); MQ00's conditions, stages and aliases; the record 002EEA4D (SustenanceAllowed: type, conditions, links); every record whose EditorID mentions StartupQuest |
| `anchor` | the anchor and terminal picks (section 3, 4a) | the persistent references of `FO4Port_Vault111Cryo` nearest the player's pod (FO4's pod / 70; the COC marker when Fallout4.esm is absent) with base and distance, and every terminal in the cell with its persistence |

Conditions print as `[flags] Function(parameters) on <RunOn> <reference> <op> <value>`, every linked record as
`EditorID (Type id:plugin)`. Fallout 4 stores a condition's two parameters as unions (a record id and a number share the
bytes), so the first prints as the record when Fallout4.esm has one of that id, else the number, and the second as the
number with any record of that id after a bar; Starfield's parameters are typed per function. The selftest
(`records-selftest <scratch>`, also run by `selftest`) builds synthetic plugins covering every section, checks the
report line by line, and checks that a missing Fallout4.esm or port is reported, not fatal, and that only `--out` is
written. The real plugins have not been read yet: every fact the report will state is **unresolved** until that PC run,
and its findings go into newgame.md section N as the 19 Oct script read did.

## 7. First in-game proof (later, on the owner's word)

New game with the plugin installed. Record the log, `sqv MQ101`, `sqv MQ00` and screenshots at the pod, at the cog door
and on the surface. PASS means the log reaches stage 200 with "enter vault ok=True" and "landed", there is no Starfield
intro on screen, and the surface screenshot shows the Vault 111 elevator area. Then walk on from there: the
continuous-traversal gate starts at the vault exit. Since newgame_v11 the start's own lines are section 13's table.

## 8. Questions for the talk

1. Option A (stop the opening quests) as the default, B as the fallback? Or skip straight to B?
2. Character creation: decided (2026-10-19): looks only, in the vault, with a quick start (NG-C3, NG-C9). Open:
   which `ShowRaceMenu` mode is looks-only (NG-C1, the first in-game test).
3. Should players be able to pick Starfield's own start instead (option D)?
4. Hold off more of Starfield's 144 start quests now, or only after the first `sqv` record?

## 9. The stage contract (NG-14)

The owner decided (2026-10-19) that the start publishes fixed stages, as FO4's MQ102 does, so later phases and other
mods can listen to them. These are the stages of `FO4SF_NewGame` (FO4SFNewGame.esm 0x800). The numbers and their
meanings live in one place each: `scripts/newgame/make_newgame.py` `STAGE_CONTRACT` (the log summary and plan.json
read it), the header of `FO4SF_NewGameQuest.psc`, and this table; `tests/test_newgame.py` holds all three equal, and
the writer's `Stages` array must list every stage but 0. Stage 0 is the quest's start, not a stage record. A stage,
once reached, is never set back. Stage 20 is set by the looks script (the creator closed, or the quick start), or by
the quest after `LooksWait` seconds; a `--no-looks` build does not wait.

| Stage | Meaning |
|---|---|
| 0 | started: as Starfield's startup quest, the guard, the move into the vault and the hold-off |
| 1 | stood down: not a new game, or no move into the vault (Starfield's opening is asked to start if the game still loads) |
| 10 | in the vault: the player stands at their pod |
| 20 | looks done: character creation closed, or LooksWait passed |
| 30 | cog door opened: from its console |
| 40 | on the surface: the elevator ride is over |
| 200 | complete: landed, or put on the fallback spot |

`make_newgame.py log` prints the stages a run reached with these names (`stages_named`) and what each hold-off pass
stopped (`held_off_by_pass`). Objective 10, "Leave Vault 111", shows from stage 10 and completes at 40.

## 10. In game, run 1 (28 Oct 2026): FAIL, Starfield's pirate-fight developer start

**Build:** FO4SFNewGame.esm sha256 3fb78b14 (newgame_v7, staged 23 Oct at 118d5d8 against port 9AF962D2 and core
DC751664), installed on the owner's word 28 Oct with Plugins.txt QuestProbe, Core, Mars, Raider, Mission, NewGame,
Port, MapMarkers, Bridge (all nine active, Install's copy). Starfield 1.16.244, SFSE 0.2.21.

**The owner's report (17:29 and 17:35 UTC, typos fixed, meaning kept):** "I ended up at the beginning stage of the game
where you fight the pirates. That mission activated with no cutscene or anything; I didn't need to go through the mine
part." Then, after flying on: "I landed at Mars and don't see anything."

**The logs (Install's copy, `D:\Modding\testqueue\newgame_20261028\`):** four new games between 10:35 and 11:24 PC
time. Two ended within six seconds of the version line (`.3`, `.1`). The two that reached the guard stood down:

- `fo4sf_newgame.2.log` (10:44): `init holdoff=4 vault=fo4port.esm:4920 anchor_temporary=true core=fo4terraincore.esm:685915`,
  then `not a new game: days=0.333530 level=1 opening_stage=0 fresh=true: standing down`, `stage 1`.
- `fo4sf_newgame.0.log` (11:24): the same init, then `not a new game: days=0.333537 level=1 opening_stage=250
  fresh=false: standing down`, `stage 1`.

Papyrus.0.log has no error of ours. Starfield prints booleans as `true` / `false` and plugin names lowercased; the log
reader takes both spellings since this run.

**Cause 1, verified (records, fragments, log): the override's value.** The installed plugin overrides GLOB `MQ101Debug`
to 10 (read from the esm's GLOB group: `FLTV 10.0`). MQ101's stage 0 entry 10 needs `MQ101Debug == 10` (records report,
21 Oct) and its fragment sets stages 210 and 250, the pirate landing (the 19 Oct fragment copy, section 2, row B). That
is the start the owner described, and `opening_stage=250` is what our guard read. Our quest did run, saw the opening
past stage 105 and stood down as designed, so Vault 111 never came. The 19 Oct reading that vanilla writes 10 (MQ00's
stage 10) was wrong: that stage runs only when something sets it.

**Cause 2, verified (log): the day limit.** The 10:44 run stood down with the opening still at stage 0: `days=0.333530`
failed the 0.25 limit alone. Starfield's clock starts at GameHour 8 (the record's value) and `GameDaysPassed` carries
the hour, so every new game reads about 0.3335 a second in. The limit is now one game day; a player's save is kept out
by the opening-stage test, not by this number.

**Fix (#569, offline):** the override is 2, the inert start (row B); the day limit is 1.0; the guard logs every
reading it judges and the global as the game read it (`guard days=... opening_stage=... mq101debug=... expected=...`);
`make_newgame.py log` reports it as `guard`. Nothing else in the start changed. The hold-off, the saving and HUD
restore, `Debug.CenterOnCell`, the move into the vault, the cog door and the elevator are still **unverified in game**:
run 1 never reached them.

**Correction (run 2, section 11):** 2 is not an inert start. No stage-0 entry matches it, so nothing moves the player
and the new game never leaves its loading screen. Since newgame_v9 the plugin overrides nothing and the quest writes 2
after the hold-off.

**Mars:** the owner flew the vanilla game to Mars and landed at a vanilla site. Our world is an overlay worldspace on
Mars that a vanilla landing does not enter; it is reached by `coc FO4Core_RedRocketSpawn` or, once this start works,
by the Vault 111 elevator. Whether the "Commonwealth Landing Area" marker (#524) is offered as a landing choice from
orbit is the Map thread's question (its markers are known to register only after a visit, 24 Oct).

**Next on the PC (done 28 Oct):** newgame_v8 was restaged from main, reinstalled and run: section 11.

## 11. In game, run 2 (28 Oct 2026): FAIL, the new game never left its loading screen

**Build:** FO4SFNewGame.esm 5167F6AA (newgame_v8, staged from main e9c12e2b after #569): GLOB `MQ101Debug` overridden
to 2.0, the vault anchor FO4Port.esm:001338 (persistent), staged `--no-special` on the precheck's word. Install's copy of
Plugins.txt: QuestProbe, Port, Core, Mars, Raider, Mission, NewGame, MapMarkers, Bridge, all active. FOCCSidecar.dll
present with `bEnabled=0`. Starfield 1.16.244, SFSE 0.2.21.

**The owner's report (19:39 UTC, typos fixed, meaning kept):** "So I clicked new game a few minutes ago and it has just
been stuck on the loading screen. It's not crashed. I can't click any buttons or anything but there's a little loading
circle on the right." Then: "I can run console commands."

**The logs (Install's copy, `D:\Modding\testqueue\newgame_20261028_run2\`):** `fo4sf_newgame.0.log` has two lines, both
at 13:35:28 PC time (rt 64.0): the log opening and `version saved=1.000000 (new game)`. There is no `init holdoff` and
no `guard` line. The map and bridge scripts logged their init in their own logs and nothing after, at the same second.
Papyrus.0.log (13:34:36 to 13:35:28) holds only the engine's bind errors and property warnings of a new game's first
phase and vanilla `SFFL_SE_EC08` alias errors: none of the fragment loads and OnQuestInit lines that follow the first
load in run 1. Install's snapshot:
the game's main thread busy on one core, memory flat at 8.1 GB, the console working.

**Cause, verified (fragment sources, records, both runs' logs): the override's value.** MQ101's stage 0 runs the entry
whose `MQ101Debug` condition matches, and each start's fragment is what moves the player into the game: the intro's
entry 2 moves the player to `CharGenStartMarker` and waits for the 3D, entry 10 to the pirate landing. No entry
matches 2 (entry 11, the conditionless one, only ghosts three NPCs), so nobody moved the player and Starfield's first
load never finished. The quest did start: its version alias filled, and that is the `version saved` line. Its
OnQuestInit only fires after that load (run 1: 1 s and 7 s after `version saved`), so the script that acts never ran.
Run 3 reads the same way: a `version saved` line with no `init holdoff` line means the first load did not finish.
Section 10's "inert start" was wrong: 2 is a value the main quests' developer skip-start stages write, not a start.

**Ruled out:** FOCCSidecar.dll returns from `SFSEPlugin_Load` before registering anything when `bEnabled=0` (its
source); the plugin order loads every plugin after its masters; the vault anchor is read only by our quest's script,
which never ran.

**Fix (newgame_v9, offline):** the plugin overrides no record. Starfield's intro places the player as it does without
mods; our quest starts after that load, and the guard and the hold-off run as before. Right after hold-off pass 1 has
stopped MQ101, the quest writes `DebugAfterHold` (2) into the global with `SetValueInt`, the call the developer
skip-start fragments make. The guard line now ends `mq101debug=<read> write_after_hold=<n>`, and the write logs `mq101debug
written=<n> was=<n>`; `make_newgame.py log` reports both (`guard`, `mq101debug_written`). `--debug-after-hold 0`
writes nothing; `--mq101debug <n>` still builds an override for experiments. The guard now also needs MQ101
running, so a `coc` session from the main menu stands down (section 1, step 2).

**Install's map-test session (28 Oct, v8 installed, `coc FO4Core_RedRocketSpawn` from the main menu):** the quest ran
end to end on that character. The guard read `days=0.333532 level=1 opening_stage=0 fresh=true`; hold-off pass 1 held
MQ00 and found MQ101, MQ101PostQuest and MQ_TutorialQuest_Misc04 not running; saving and the HUD were restored; `enter
vault ok=true` in `FO4Port_Vault111Cryo`, stage 10, pass 2 stopped none, and the start prompt showed. So the move into
the vault and the prompt work once a load completes; stage 10 onward past the prompt was not exercised. It also showed
that a `coc` session passed the old guard, which v9 closes.

**SPECIAL:** v8 was staged `--no-special` because the precheck found neither `SetValue` nor `GetValue` in Starfield's
Actor.psc. The compiler resolves inherited functions, and v7 compiled the same script on 23 Oct, so the declarations
sit higher in the `extends` chain. The precheck now walks that chain, so v9 stages with SPECIAL again.

**Unverified in game:** the intro's stage 0 turns character generation on and sets the chargen HUD mode before our
quest starts; the hold-off's restore of saving and the HUD (section 1, step 3) is what undoes that. Its input layer is
deleted by MQ101's stage 9000 when we stop it. After its 3D wait the fragment empties the inventory and equips the miner
suit, which nothing undoes in a default build. The fragment and our first tick both follow the 3D load; entry 2 has no
stage set or scene after its wait, so the stop cannot be undone by it, and hold-off pass 2's lines for MQ101 would show
a restart. Run 3 is the first New Game that reaches the hold-off (section 12: the restore and pass 2 held).

**Next on the PC (done 28 Oct):** newgame_v9 was restaged from main with SPECIAL, reinstalled and run: section 12.
Expected then: the `guard` line shows `opening_running=true` and ends `mq101debug=0.000000 write_after_hold=2`, then
`mq101debug written=2.000000 was=0.000000`; the player stands at the pod in the miner spacesuit (the default build has
no inventory reset; `--clear-inventory --vault-suit` is the answer).

## 12. In game, run 3 (28 Oct 2026): PASS to stage 200, with two placement defects of ours

**Build:** FO4SFNewGame.esm newgame_v9 (staged from main 4790ebf2 after #573, with SPECIAL; the install record's
folder `terrain_core64v6i_l125_keeper_newgame9`), the vault anchor FO4Port.esm:001338 persistent. Plugins.txt:
QuestProbe, Port, Core, Mars, Raider, Mission, NewGame, MapMarkers, Bridge, all active. Starfield 1.16.244, SFSE 0.2.21.
A New Game from the main menu at 18:07 PC time (00:07 UTC 29 Oct).

**The owner's report:** three hotkey snapshots (`C:\Modding\snapshots\20261028-180758`, `-181101`, `-181340`) with
their own descriptions (typos fixed, meaning kept): "You fall under at first" (in the vault, 18:07:58); "No Codsworth"
(Sanctuary, 18:11:01); "Here's showing broken textures, and the freedom calls activation didn't work" (Concord,
18:13:40; FO4's Concord quest, and our mission plugin's, is When Freedom Calls). The first screenshot shows our "Vault 111" notification and "Mission updated" with the FO4 quest name "Out
of Time", which the quest posts after `enter vault ok=true` and stage 10.

**The logs (Install's copy, `D:\Modding\testqueue\newgame_20261028_run3\`):** fo4sf_newgame.0.log, the bridge's
fo4sf.0.log (one line each 0.5 s), Papyrus.0.log, Plugins.txt and `make_newgame.py log`'s summary (exit 0).

**Against section 11's expected lines: PASS.**

| Step | Run 3 | Verdict |
|---|---|---|
| Guard | `guard days=0.333526 level=1 opening_stage=5 opening_running=true fresh=true mq101debug=0.000000 write_after_hold=2` | PASS: a New Game has MQ101 running (at 5) |
| Hold-off | pass 1 held MQ00 and MQ101; pass 2, one tick later, held MQ101PostQuest and MQ_TutorialQuest_Misc04 (what MQ101's stop started); MQ101 not running in pass 2 | PASS: no restart |
| Write | `mq101debug written=2.000000 was=0.000000` | PASS |
| Saving, HUD | `saving and HUD restored after the hold-off`; the HUD shows in every screenshot; Papyrus logs a save at 18:11:36 | PASS |
| Vault | `enter vault ok=true pos=9.204920 -3.086447 -1.044888 target=9.142858 -3.114286 -1.028571`, stage 10 | at the pod, then sank (defect 1) |
| Looks | `start choice button=1`, `quick start: preset kept, creator skipped`, stage 20 | PASS (quick start) |
| Cog door | `cog door open_state before=3 after=2`, stage 30 | PASS |
| SPECIAL | `special skipped: left the vault with SPECIAL unset` | not used by the owner |
| Ride | `elevator prompt button=0`, `surface moveto`, `surface setposition`, stage 40 | the arrival did not take (defect 2) |
| End | `fell z=119.384842: fallback pos=-2475.313965 -1394.724243 127.223747`, stage 200 | PASS through the fallback |

The owner then walked to Sanctuary and Concord. Not verified: the miner suit at the pod (first-person screenshots; a
default build logs no inventory line). The first screenshot also shows "Constellation space helmet removed" and
"Constellation removed"; no log says what removed them (our build has no inventory reset). The phase 1 exit's quest
list (no Starfield start quest in it) was not looked at.

**Defect 1, ours: the player sank under the floor at the pod, and the game stood them on the COC marker.** The bridge:
at rt 43.05 the player is in the intro's cell (66892, pos -21.8 49.4 58.0); our MoveTo at rt 43.59 leaves them at z
-1.045, at the pod's z (-1.029); the next bridge line, after the vault's load, at rt 45.34, reads pos 9.203 -2.641
-1.738, 0.69 m lower; at rt 45.98 the player stands at 1.531505 -7.385632 (z -0.815, then -0.851672 from rt 46.65),
the cell's COC marker FO4Port.esm:001338 at (1.532, -7.386, -0.738) m (newgame.md section O, the anchor bullet). Nothing in our log moves the
player then (pass 2 starts at rt 46.04), and no Papyrus entry around it moves the player, so the game itself put them
on the marker. **Cause (inferred from those numbers):** the pod's z is not the floor's. On the marker the player stood
at -0.852, so the hall's floor there is about 0.18 m above the pod's z, and a player started under a floor drops
through it. Whether the floor at the pod is level with the marker's is **unverified**; Install's map test (section 11)
logged the same `enter vault` position and was not watched after it. **Fix (newgame_v10):** the start is `PodLift`
(0.3 m) above the pod's z, the marker's own height. The first tick the player is loaded after the move logs `pod
settle ok=<bool> pos=<x y z> dx=<n> dy=<n> drop=<n>` (ok: within 1 m of the pod's x and y and at most 0.5 m under the
start), and `make_newgame.py log` prints it as `pod_settle`. It moves nothing: the game's own reset to the marker stays
the fallback.

**Defect 2, ours: the ride's arrival was set in the move's own tick and ignored.** `surface moveto pos=-1275.313965
1305.275757 119.384842` (MarsPlanetWorld, runtime FF00C482) is the exit anchor's (FO4TerrainCore.esm 0A775B, the
Vault 111 map marker) local x and y (-1275.314, 1305.276), 6.8 m under the anchor's z in the build (126.224,
`FallbackZ`: the End row's fallback line above reads it plus 1 m, 127.224). The `surface setposition` line
right after reads the same position against the target -2467.781 -1406.925 128.110, so that SetPosition did nothing.
The bridge has the player on that spot from rt 178.70 to 179.42, after the ride's load. At rt 181.43 the landing check
read z 119.38, more than 3 m under the arrival, logged `fell` and put the player on the map marker's merged spot with
its own SetPosition, which took at once. So "fell" here means "not on the arrival", and the player came up 5.7 s
after the move, next to the marker instead of on the elevator's arrival. **Fix (newgame_v10):** the ride is two ticks,
in the load door's order (MoveTo, a wait, SetPosition: FO4SF_LoadDoor's `SettleSeconds`). `Surface` only moves;
`FinishSurface` sets the merged arrival on a later tick, once the player is outside and loaded, reads the position
back (`surface setposition ok=<bool> set=<n> ...`), and goes on to stage 40 when it took, or after three tries
(the landing check's fallback then decides). A move that has not left the vault after 10 s is made once more, then
the elevator asks again.

**Not ours (sent on to their threads, 29 Oct):** Codsworth missing at Sanctuary (the snapshot's bridge position
-2342.7 -1408.3 112.0; the known Section A item, Codsworth about 3 km away; no run 3 log places him); at Concord, black
patches on the church and the buildings (textures), and the owner's When Freedom Calls activation, which has no log
yet: the staged Papyrus.0.log, like the 18:13:40 snapshot's tail, ends at 18:12:23, before the owner reached Concord, so
a later copy is needed. The activator FO4TerrainCore.esm:00DCC6 (0400DCC6 in this load order) that runs
`DefaultActivateLinkedRefOnActivate` with no linked ref was activated at 18:12:01 at Red Rocket (bridge pos -2204.9
-1561.9 105.2), not at Concord (core data). FO4SF_MapMarkers logs `FO4Core_CommonwealthLandingPadRedRocketNorth
(090008F0): cannot be moved` every few seconds from 18:10:15, when the player came out, to the log's end (map
markers). Vanilla noise at the start (SFBGS003 bounty quest errors, MQ101 alias shutdowns from the hold-off's stop)
moves nobody.

**Next on the PC:** after this PR merges, restage newgame_v10 from main against the installed port and core, reinstall
on the owner's line, a New Game from the main menu. Expected: `enter vault ok=true ... target=9.142858 -3.114286
-0.728571`, then `pod settle ok=true` with a drop of about 0.1 m, and no fall; at the ride, `surface setposition
ok=true set=1` and `landed z=...`, stage 200. A `pod settle ok=false` with the player on the COC marker means the
floor at the pod is higher than the marker's (or has no collision there), the next thing to read in the port.

## 13. Our own start (newgame_v11, 29 Oct 2026): what run 4 must show

**Why (the owner, 29 Oct, typos fixed):** "too many things are breaking because we are forcing ourselves into the
Starfield system". Of the strip-down plan's choices the owner picked F, our own start. newgame_v9 and v10 let MQ101's
stage 0 run and then undid it (the hold-off, the restore of saving and the HUD, the miner suit left on); v11 replaces
the start itself, as Roleplayers' Alternate Start does.

**What changed (offline; the writer's selftest and tests/test_newgame.py hold it):** the plugin overrides
`StartupQuest_DO` (00562D) to name `FO4SF_NewGame` (0x800), and the quest is no longer start-game enabled. The script
starts from `OnQuestStarted` or `OnQuestInit` (`Begin`, once), during the first load: the guard, the move into the
vault, the hold-off's first pass and the `MQ101Debug` write, then the timer, and once the player's 3D has loaded the
fade in (`FadeIn`, from the start's own wait or from the timer, whichever sees the 3D first). The timer confirms the
vault cell, runs pass 2 and sets stage 10; everything after stage 10 is newgame_v10's (the pod settle check, the looks,
SPECIAL, the cog door, the two-tick ride). A start that is not a new game, or that cannot move the player (the anchor
does not resolve), stands down (stage 1) and, when either reading of the start says the game is still loading (the
player's 3D not in, or no parent cell yet: `loading=true`), first asks MQ101 to start (`HandBack`, with `StartNoWait`,
before it sets that stage, so nothing of ours waits on MQ101's start-up), so that its stage 0 moves the player and the
first load does not wait on a move nobody makes (**unverified**, below). The first review of 29 Oct (on #588) found
three ways the first load could still go wrong: the fade could fire under the loading screen when the start's wait ended
without the 3D (fixed: each caller checks the 3D first), a stand-down judged the load by one reading (fixed: either),
and a temporary anchor's centering counts as a move, so a centering that moves nobody hands nothing back (not fixed but
gated: that mode is built only on request, `--allow-temporary-anchor`, section 3a). The second start event's line now
always follows the start's route line. The second review found the hand back's effect stated as fact and a stalled hand
back invisible in the log: it is labelled, the request waits for nothing, the reader keeps both of its lines
(`handing_back`, `handed_back`), and the timer's wait for the 3D writes a line every 10 ticks (`waiting_3d`). The
deployment gate's start check passes the override (`our own start overrides StartupQuest_DO:
FO4SFNewGame.esm:StartupQuest_DO`). The looks and SPECIAL scripts start their timers on the same two events.

**Expected lines on a New Game, in this order** (`make_newgame.py log` keys in the last column):

| Step | Line | Reader |
|---|---|---|
| Version | `version saved=1.000000 (new game)` | `version_saved` |
| Start | `init holdoff=4 ...`, then `start route=OnQuestStarted player_loaded=false cell=None loading=true` (or `OnQuestInit`) | `start`, `start_events` |
| Guard | `guard days=0.33... level=1 opening_stage=0 opening_running=false mq101debug=0.000000 write_after_hold=2` | `guard` |
| Move | `enter vault ok=<bool> pos=... target=9.142858 -3.114286 -0.728571 cell=...` (false is possible while the cell loads) | `entered_vault` |
| Hold-off 1 | `held off ...` or `not running ... pass=1`, then `hold-off pass 1 stopped=<n> of 4` | `held_off_by_pass` |
| Write | `mq101debug written=2.000000 was=0.000000` | `mq101debug_written` |
| Second event | `start event OnQuestInit came after the start: nothing to do`, if it fires: anywhere after the `start route` line (right after it when it came during the start's first calls) | `start_events` |
| 3D | `3d wait over loaded=true`; `fade in by=start loaded=true cell=[Cell <FO4Port_Vault111Cryo ...>]; saving and HUD on` (after `loaded=false`, or when the timer sees the 3D first: `by=timer`); a timer still waiting for the 3D writes `waiting for the 3d tick=<n> ...` every 10 ticks | `start_wait`, `fade`, `waiting_3d` |
| Vault | `enter vault confirmed after the load ...` if the move's own check said false; pass 2; `stage 10` | `entered_vault`, `stages` |
| Pod | `pod settle ok=true ... drop=<about 0.1>` | `pod_settle` |

From there on as section 12's next run: the looks prompt, the cog door, `surface setposition ok=true set=1`, `landed`,
stage 200. On screen: no Starfield intro at all (no mine, no Lin), and the loading screen ends in the vault.

**What run 4 answers (each open until then):**
- Which start events fire, and in what order. **Supported hypothesis:** `OnQuestStarted` during the load, the
  precedent's event; run 2 showed a start-game-enabled quest's `OnQuestInit` waiting for the end of the load.
- Whether `GetParentCell` names the vault right after a MoveTo during the load. **Unverified**; the timer's
  confirmation covers both answers.
- Whether the player's 3D reads as not loaded, or the player has no parent cell, when the start runs during the load
  (**supported hypothesis**: MQ101's intro waits for the 3D after its move). A hand back needs either; the `start`
  line logs both and the verdict (`player_loaded=`, `cell=`, `loading=`).
- Whether the guard's readings during the load are those of a second later (section 10 read them then): an NG+ whose
  level still read 1 would get our start, not MQ101's NG+ start (not a hang). MQ101's own NG+ test,
  `PlayerUnityTimesEntered >= 1`, is the candidate for a stronger guard once a records read shows what it is.
- Nothing about the hand back: on a New Game our start goes on, so MQ101 is never asked. Whether MQ101 started by a
  script during the first load starts up then and moves the player is **unverified** until a run stands down during that
  load (a New Game+, or a build whose anchor does not resolve, on purpose).
- Whether the fade call ends the loading screen, or the move does and the loading menu fades the game in itself.
  **Supported hypothesis:** the latter, from MQ101's own fragments: they wait 0.1 s after the move before they fade
  (`Utility.Wait`, which does not run in menu mode), because a fade requested while the loading menu is up "would be
  bashed when the loading menu goes away and tells the fade menu to fade in", and the intro's entry (Item_02) makes no
  fade call at all (QF_MQ101_00003448, ContentResources.zip, read 29 Oct). The precedent's comment says its fade
  "finishes main menu loading". Either way the screen should come in once the player's 3D is in.
- What the player wears and carries with no MQ101 stage 0. **Unresolved.**
- Whether MQ00 starts before or after our start (the pass that stops it will say).
- Whether a centering during the first load works in the temporary-anchor mode. Not exercised: the installed port's
  anchor is persistent, and the mode is built only on request since the 29 Oct review.
- Whether anything else of Starfield's waits on MQ101 having run (a quest list with `sqv` after the run).
- A `coc` session from the main menu should no longer start our quest at all: its log has no `init` line.

**Failure readings:**
- Only a `version saved` line and no `init` line, with the loading screen up: neither start event came during the
  load (run 2's shape). The way back is newgame_v10 (restage main d9958261). The next step would be a stage 0 fragment
  on our quest, as MQ101 moves its own player, or a route from the player alias (its `OnInit` ran during run 2's load).
- `no move into the vault ...`, then `handing back ...` and `handed back: requested=true ...`, then Starfield's intro on
  screen: the anchor did not resolve and Starfield's own intro took over (the hand back works during the load). The game
  is playable; ours did not start.
- `not a new game ... loading=true`, then `handed back`: the guard judged the New Game a New Game+; its `guard`
  line has the readings.
- `handed back: requested=true ...` comes right after the request, which waits for nothing, so it reads MQ101 while its
  start-up may still be under way (most likely `starting=true running=false`) and is no verdict. If the loading screen
  then stays up, MQ101 started by a script during the first load did not start up or did not move the player;
  Papyrus.0.log cannot say which (MQ101's own `Debug.Trace` lines are not in run 3's, though its stage 0 ran then: our
  log read `opening_stage=5`). The way back is newgame_v10; the next build would move the player to MQ101's own start
  marker (`CharGenStartMarker`, where its intro entry moves the player) before the request, so that load ends whatever
  MQ101 does. `requested=false`: MQ101 could not be started at all, with the same way back.
- `handing back ...` with no `handed back` line (`handing_back` set, `handed_back` None): the request itself never
  returned, which `StartNoWait` should not do (Quest.psc: it returns at once). `handed back` with no `stage 1` line
  after it: our own `SetStage(1)` waited, after the request had gone out.
- `not a new game ... loading=false` or `no move into the vault ...` with no `handing back` line, on a New Game whose
  loading screen stays up: neither reading saw the load (`start route ... loading=false`), so nothing was handed back.
  The hand back then needs another signal of the first load.
- `enter vault ok=false`, pass 1 and the write, then no `3d wait over` line and no `enter vault confirmed`, with the
  loading screen up: most likely the MoveTo during the load did not take (the start counts MoveTo calls, not moves that
  took), so the load waits as in run 2 (the timer's `waiting for the 3d ... vault_moves=1` lines, if it runs then, show
  the same). The way back is newgame_v10.
- `3d wait over loaded=false` and no `fade in` line, the screen black: the timer never saw the player's 3D. While it
  waits it writes `waiting for the 3d tick=<n> vault_moves=<n> centered=<n> cell=<cell>` every 10 ticks (`waiting_3d`,
  the last one): those lines say it ran and what the start had done; none at all means the timer did not run then
  (whether a script timer runs under the loading menu is **unverified**: ScriptObject.psc does not say).

## 13a. The v11 boot crash (29 to 31 Oct 2026): a doc comment over 4 KB

**What happened (Install's reads of the PC, through the coordinator, 31 Oct):** with newgame_v11 installed
(FO4SFNewGame.esm 418C491C), every launch died 22 to 36 s in with an access violation at Starfield.exe+0x28281B5
(1.16.244.0) reading 0xFFFFFFFFFFFFFFFF: one on 29 Oct, five on 31 Oct (12:42 to 12:48 PC time). fo4sf_newgame.0.log
and every other user log stayed untouched, and Papyrus.0.log to .3.log hold only vanilla bind errors, the last about 2 s
before the exit. FO4SFBorder's log has its `load` line but no `post_data_load` line for each of the four SFSE launches
of 31 Oct, while a launch that boots gets that line 25 to 26 s after `load` (29 Oct 05:03 UTC, 26.5 s; newgame_v10 on
31 Oct 18:58 UTC, 25.4 s): the game died while it loaded its data files, before the main menu (**verified**). Two of
the crashes came after the local model was unloaded, one with 13.4 GiB free, so memory is not the cause (**supported**:
one relayed sample; the stronger sign is the read itself, a pointer made of text, not a failed allocation).
newgame_v10 booted and played to stage 200 that afternoon.

**The cause:** the exception dump's rax was 0x20726f66206c6c65, the eight bytes `ell for `. FO4SF_NewGameQuest.psc's
doc comment (the `{...}` after its `Scriptname` line) was 4,196 bytes in v11 (v10's: 2,745), and its bytes 4,096 to
4,103 are exactly `ell for `, from "the script must load the cell for (Debug.CenterOnCell)" (**verified**: the dump and
the source). The compiler keeps doc comments in the .pex, and the game loads the scripts its records name while it
loads the data files (the bind errors in Papyrus.0.log come from then); both are standard Papyrus behaviour, not seen
here (the repo has no .pex reader). So Starfield's script loader copies a doc comment into a 4 KB buffer, and the bytes
past it overwrite a pointer the loader then uses (**supported hypothesis**, from that one dump). No other doc comment
or string of ours is longer than 2,353 bytes.

Byte counts in this section are of the files with LF line ends, and the dump matches them: with CRLF line ends
`ell for ` would start at byte 4,135. The test counts each line end as two bytes all the same (its own figures, such
as 2,376 for that 2,353-byte comment, are larger), as a margin, not because the evidence needs it.

**The fix (newgame_v12):** that doc comment is now 1,409 bytes and keeps the stage contract (section 9); the notes it
carried are `;` comments, which the compiler leaves out of the .pex. `tests/test_papyrus_strings.py` holds every doc
comment and string literal of the repo's .psc files at or under 3,072 bytes, each line end counted as two bytes (a
Windows checkout); the bytes past 4,096 are where the crash came from. Nothing else changed: the plugin's records and
the script's code are v11's, so section 13 is still what run 4 must show, on newgame_v12. Before run 4, Install checks
two things the repo cannot: the staged FO4SFNewGame.esm's CRC is v11's 418C491C (the writer is unchanged; a mismatch is
reported, not assumed away), and no string in the staged .pex is anywhere near 4 KB.

**What would show it wrong:** newgame_v12 dying the same way (no `post_data_load`, the same address). The next suspect
is then the startup override record, the only other change from v10 that the game reads while it loads its data
files; a build without it (v11's start never runs, MQ101 starts as in vanilla) tells. Not suspected now: the override
is in no part of the dump, and Roleplayers' Alternate Start and No Ship Fast Start ship the same override on 1.16.244
(section 2, option F). No Ship Fast Start's placeholder ship, sustenance and Cruise Mode steps run once a game is going,
and run 3 played to stage 200 with no ship, so they cannot explain a crash before the main menu. A limit on a
script's doc comments in total is not ruled out either: the quest script's 44 doc comments come to 19,123 bytes in v12
(v10, which booted: 14,109; v11: 21,910), though the exact offset 4,096 points at one comment.

## 13b. In game, run 4 (31 Oct 2026, newgame_v12): PASS to stage 200, our own start

**Setup:** newgame_v12 restaged from main 63c59599 (#623, merged 20:31:51 UTC) and installed by Install on the owner's
line ("Reinstall the new game", given 20:13 UTC, before the merge; the installed FO4SFNewGame.esm's file time is
20:39:46 UTC, after it, read on the PC 1 Nov); one boot to the main menu, then the owner's New Game (the boot's `load` at 20:51:13.803
UTC). The owner: "v12 worked fine". Logs and `log_summary.txt`: `D:\Modding\testqueue\newgame_20261031_run4`
(Install's read, through the coordinator).

**The boot crash is gone (verified):** FO4SFBorder logged `post_data_load` at 20:51:38.279 UTC, 24.5 s after `load`,
as a good launch does (section 13a), so the data load finished with the short doc comment. The esm CRC check of
section 13a was not in the relay.

**What `make_newgame.py log` read (main) on fo4sf_newgame.0.log:**
- stages 10, 20, 30, 40, 200, `landed` true; stage 200 at rt 89.8 s;
- `start`: `OnQuestInit player_loaded=false cell=None loading=true`; start events `OnQuestInit`, then `OnQuestStarted`;
  `start_wait` loaded=true;
- `fade`: `by=Start loaded=true cell=FO4Port_Vault111Cryo; saving and HUD on`;
- `guard`: days=0.333 level=1 opening_stage=0 opening_running=false mq101debug=0 write_after_hold=2;
- `held_off`: MQ00 at pass 2; `mq101debug_written` 2.0 was 0.0;
- `looks` Quick start; `special` skipped: left the vault with SPECIAL unset (the owner did not set it); `version_saved`
  1.0;
- `pod_settle` ok=true drop=-0.864;
- `surface setposition` ok=true set=1, pos -2467.78 -1406.92 127.45.

**What run 4 answered (section 13's list):**
- The start events: as Starfield's startup quest, ours got `OnQuestInit` during the first load, before
  `OnQuestStarted` (**verified**, this run). The supported hypothesis of section 13 (`OnQuestStarted` first, from run
  2's start-game-enabled quest) was wrong for a startup quest; `Begin` runs once from whichever comes first, so
  nothing changes.
- During the load the player's 3D was not in and the player had no parent cell (`player_loaded=false cell=None
  loading=true`): **verified**. A stand-down then would have handed back to MQ101.
- The start's own wait saw the 3D, and by then `GetParentCell` named the vault (`fade ... cell=FO4Port_Vault111Cryo`):
  **verified**. The `enter vault` check right after the MoveTo read `ok=true ... cell=FO4Port_Vault111Cryo` at rt
  33.220, 3.6 s after the start (rt 29.585) and as the load ended (`3d wait over loaded=true` at rt 33.243; run 4's
  log, read on the PC 1 Nov): **verified**. Whether the cell was named earlier, inside the load, is not known.
- The guard read during the load what section 10 read a second into a new game (0.333 days, level 1, MQ101 at stage 0
  and not running): **verified**, one run.
- MQ00 starts after our start: pass 1 found it not running and pass 2 stopped it (**verified**, one run).
- The hand back was not exercised (a New Game; nothing stood down). Whether the fade call or the end of the load
  brought the screen in is not told apart by the log; the owner reported none.
- Still **unresolved**: what the player wears with no MQ101 stage 0, a quest list (`sqv`) after the run, and a `coc`
  session from the main menu with no `init` line.

**One reading to watch, not a defect:** `pod settle drop=-0.864` puts the player 0.86 m above the start point (PodZ
plus PodLift, -0.729), at about z 0.14 to 0.15 (the logged `pos` reads 0.1497), where section 12 expected about 0.1 m
under it. The check only bounds a fall (at most 0.5 m under), so it reads ok. Why the player stood higher is
**unresolved**: on the pod's base or step, or lifted out of something solid by the game, are guesses. The owner
reported nothing wrong. If the player is ever seen
standing on the pod or floating, this is the line to read. It is not a one-off: the other three v12 new games in the
game's own logs on 31 Oct (15:14, 16:11 and 20:53 PC time, copied 1 Nov to the PC's `mapmarkers_20261101_logsnap`)
read `drop=` -0.993, -0.393 and -0.334, so the player stood above the start point in all four.

**Also played (not a numbered run):** newgame_v10 on 31 Oct, 12:58 PC time (18:58 UTC): 489 s, a normal exit,
stage 200 on the Mars surface, SPECIAL skipped; `post_data_load` 25.4 s after `load`; logs
`D:\Modding\testqueue\newgame_20261031_v10`. The owner's map report from that play went to the map markers work.

## Sources

- [SKK Fast Start New Game (Nexus Starfield 5971)](https://www.nexusmods.com/starfield/mods/5971): MQ101Debug = 8, the
  `NewAtlantisSpaceport03` check, MQ101 stage checks.
- RoleplayersAlternateStart (GitHub ZeCroque, `Data/Scripts/Source/RAS`, read by the research thread 28 Oct): its
  startup quest places the player first and writes its unmatched MQ101Debug value afterwards.
- [ECS Asteria (Nexus Starfield 16206)](https://www.nexusmods.com/starfield/mods/16206): a new game teleports the player
  from a start script and guards against mid-game installs.
- docs/spikes/B4-mission-anatomy.md section 3 (the Vault 111 exit chain, verified ids), docs/terrain/scripted-doors.md,
  docs/ROADMAP.md, scripts/door_bridge/FO4SF_LoadDoor.psc, the mission (#353) as the pattern.
