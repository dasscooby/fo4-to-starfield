# A first mission: cut-down "When Freedom Calls" (2026-10-18, Claude-cloud)

Phase B4 of docs/ROADMAP.md, built from the anatomy in docs/spikes/B4-mission-anatomy.md. Status: **built and checked
offline on synthetic masters only; not yet run on the real game files or in game.** Labels as in docs/ai/research-log.md.

## What the plugin holds

`FO4SFMission.esm` (dotnet/Mission), masters Starfield.esm, FO4TerrainCore.esm, FO4ActorRaider.esm:

| record | what |
|---|---|
| QUST `FO4SF_Min00` 0x800 | the quest, start game enabled, named from Fallout 4's Min00; stages 10 / 20 / 30 / 40 / 200 (200 completes it); objectives 10 / 85 / 86 with Min00's own texts (Find the Last Minutemen, Kill the Raiders, Talk to Preston Garvey); a reference alias forced to Preston (objective markers; `--no-alias` drops it) |
| NPC_ `FO4_PrestonGarvey` 0x801 | the raider plugin's calm probe (no factions, Spacer template) under Preston's Fallout 4 name, Essential, Unique: Preston's identity on a Starfield stand-in body, as ROADMAP B2 allows while the face pipeline is open |
| ACHR 0x802 | Preston, at the point where Fallout 4 puts the player outside the Museum of Freedom's front door |
| ACHR 0x803 on | up to 8 raiders (FO4_LvlRaider) at Fallout 4's own Concord positions: the enabled placed raiders within 120 m of that door, without the dead-body loot placements (Loot_Corpse*, Starts Dead) |
| NPC_ `FO4_Codsworth` 0x810 | Codsworth (ROADMAP B2 stretch): a copy of Starfield's `OutpostRobotMiniBotA_Garden` (04297C, "Garden Mini Bot", MiniBotARace, a hovering robot) under his Fallout 4 name, Essential, Unique, without its factions and scripts; `write --codsworth-body EDID` picks another body, `--no-codsworth` leaves him out |
| ACHR 0x811 | Codsworth at Fallout 4's own Sanctuary placement, ACHR 01CA7D of NPC_ 0179FF: (-1146.709, 1293.837, 111.734) m, rot z 2.356 |
| WRLD + CELL override | the core world `FO4Core_Commonwealth` and its persistent cell, holding only the ACHRs above |

Positions are Fallout 4's divided by 70, the core's frame (make_core64c.py). Because the plugin copies the core's world
record, it is rebuilt whenever FO4TerrainCore.esm changes; plan.json records the masters' hashes.

## What the script does (scripts/mission/FO4SF_Min00Quest.psc)

A one-second check replaces Fallout 4's triggers, scenes and fragments:

1. Stage 10 at start: "Find the Last Minutemen" (marker on Preston).
2. The fight counts as started as soon as any raider fights or is dead, whoever started it (a quest that starts or
   reloads mid-fight still advances), or when the player finds Preston: activates him, or comes within 20 m of him
   (`FindRadius`, chosen), before the fight. A living raider within 60 m of the player that is not fighting is put
   into combat with the player (Fallout 4's DN092 does the same with StartCombat; our raider never engaged unprompted,
   npc_combat_c1, and engaged when forced, npc_combat_c2/c4); once the fight is on (Preston found, or stage 20), every
   living raider whose 3D is loaded and that is not fighting is, at any distance, on every check until stage 30:
   stage 20, "Kill the Raiders".
3. Every raider dead: stage 30, "Talk to Preston Garvey".
4. Activating Preston, or standing within 3 m of him: stage 40, 100 credits for Fallout 4's 100 caps, then stage 200,
   quest complete.

Every stage and a status line every 5 s go to `fo4sf_mission.0.log` (the Papyrus user log); `make_mission.py log`
summarises it (exit 0 when stage 200 was reached).

## Stand-ins and gaps (stated, not hidden)

- No dialogue, voice or scenes: "talk" is activation or proximity. Dialogue is the next step (DialogueConcordArea).
- Preston and the raiders wear Starfield Spacer looks; Preston carries the calm probe's weapon.
- The fight takes place in the street outside the museum; the museum interior, Preston's door, the power armor, the
  minigun, the deathclaw and the waves are left out (B4 spike's cut list).
- **Unresolved:** whether the engine fills the alias and shows the markers from these records; whether persistent
  actors added to the core's persistent cell by a later plugin load there; the quest flags (StartGameEnabled,
  RunOnce, DisplaysInHud) were chosen, not copied from a vanilla quest.

## In game 18 Oct: the actors were not in the world the player walks in (fixed by Relocate)

**Verified** (the PC's read of `fo4sf_mission.0.log`, v5 + the Codsworth set, save fo4sf_test_1d4591b6_s100): the
quest started (`init raiders=5`, stage 10), but every status line read `nearest_raider` and `preston` = float max
(3.4e38), also at 13:25:38 with the player standing on Preston's merged spot (-2011.1, -1697.2): local (-811.1, 1002.5)
+ the merge offset (-1200, -2700). So persistent references added to the core's persistent cell by a later plugin
exist at their LOCAL position in the base world, as probe (a) found for the core's own anchor (scripted-doors.md); the
"unresolved" item above is answered "no". Fix: the script's `Relocate` moves Preston, the raiders and Codsworth once,
when the player is within 3 km of Preston's merged spot and still cannot reach him: each actor's local position +
`MergeOffsetX/Y` (vmad_patch.MERGE_MEASURED, a test pins them equal), z kept, by `MoveTo(player, dx, dy, dz)`. Log lines
`moved <who> to ... target ...` and `relocated preston=<m>`. **Unresolved** until the next run: that MoveTo with an
offset lands an actor in the merged world's cell at that spot.

**Second run, 18 Oct 14:40 local (wfc5b, the 13:32 autosave):** `relocate not needed preston=4061.8`, then status lines
at the museum street (x -2035 to -2352, y -1397 to -1676) with Preston and the nearest raider 2,839 to 2,944 away, the
offset's length (2,955); stage stayed 10. **Supported hypothesis:** this time the actors were in the player's world but
at their local spot, so a finite distance does not mean "already moved". Relocate now decides per actor and by position,
on every check: the player outdoors within `RelocateRadius` (800) of that actor's position + the offset, and the actor
farther than `RelocateGap` (1,500). A moved actor's position + the offset is far from the player, so nobody is offset
twice. A move that misses is retried, up to 10 failed moves in all (Codex 5564899342). Tests pin
radius < gap < offset length - radius and model the rule: no-op, partial, retry, no double move.
**Open risk (accepted, not fixed):** coordinates cannot tell two exterior worlds apart. The merged world is created at
run time (FF0054C8 in the log), so no fixed form id can name it in a property. A player standing outdoors in another
world within 800 of (-2011, -1697) before the mission is done would pull the actors there.

**Third run, 18 Oct 15:15 local (wfc6, 6911ef9), verified from the PC's read of the logs:** every actor moved with
`fails=0` (after the move, d = 174 to 229 from the player), raider 3 was put into combat at 57, all 5 died, and the
status reached stage 40 twice, after which the user reloaded. Codsworth was moved a second time at 15:17:44: his position
read his local spot again (supported hypothesis: he went back to his editor location), and the per-actor rule moved him
back. Open from the user's report: the quest never showed in the Missions tab, Preston "treats me like an enemy", and
the status stayed at stage 40 after the reward. Changes: `SetActive`, a stage-10 notification, Preston
`IgnoreFriendlyHits` plus `StopCombat` if he targets the player, and 40 to 200 set from the timer with `CompleteQuest`.
The quest record has no QuestType keyword (Starfield's QTYP, a KYWD); `dotnet/Mission quests` lists the vanilla ones
to choose from (read only). **Verified** on the PC: 118 vanilla quests carry QuestTypeSideQuest (047600), e.g.
FFNeonZ09 "Balancing the Books"; the writer now sets it and check requires it. The PC's log also had no "stage" line at
all: OnStageSet never ran (unresolved why), so no objective, notification or reward happened. The stage actions now run
from `AdvanceTo` (SetStage, then `Apply`), with OnStageSet as a second caller; `Apply` runs each stage once.

## Codsworth (2026-10-18)

The owner asked for a Codsworth test. A Mr. Handy has no Starfield skeleton (ROADMAP B2), so the first one is a
Starfield robot body under his name at his own spot. **Verified** by `dotnet/Mission npcs` on the PC (read only):
Fallout4.esm NPC_ 0179FF `Codsworth` (HandyRace) has one placed ACHR, 01CA7D, in the Commonwealth's persistent cell
at the core-frame position above (about 30 m from the walk route's Sanctuary goal); Starfield.esm has no Mr. Handy
(the robot races are ModelARace, ModelSRace and MiniBotARace). The Garden Mini Bot was chosen as the closest look (a
small hovering robot, not a companion with quests like Vasco). **Unresolved:** whether the bot's AI packages and
template run without its outpost, and how he behaves (sandbox, hover, idle). No dialogue or voice yet (WP-15).
Check in game: travel to Sanctuary; a robot named Codsworth hovers near his house, does not attack, and stays.
Since the 20 Oct review, Codsworth is moved by his own check (`KeepCodsworth`, timer 2, every `CodsworthCheck` = 5 s,
with its own budget of 10 failed moves), not by the mission's 1 s check. Stage 200 cancels only the mission's timer,
so he is still placed, and placed again after a snap-back, when the player reaches Sanctuary after the mission.
**Supported hypothesis:** a quest's timers keep running after `CompleteQuest`, since the quest is completed, not
stopped. To check in game: finish the mission, then go to Sanctuary and look for a `moved codsworth` line in the log.

**His voice (18 Oct, from the Codsworth thread, PR #361):** `stage --codsworth-voice <codsworth_voice.py output>` reads
lines.tsv, gives each line a WEMFile id (00F4C001 on, below 0x01000000 like vanilla's) and copies its `<info>_<response>.wem` to
`sound\voice\fo4sfmission.esm\robotminibota\<wemfile>.wem` (he inherits RobotMiniBotA). The writer adds DIAL
FO4SF_CodsworthHellos (0x820, Misc / Hello) in the mission quest with one INFO per line (0x821 on, flags Random as
vanilla's mini bot Hellos), each said only by him (GetIsID on the subject), "sir" lines to a male player and "mum" lines to a
female one (GetIsSex on the target). **Verified** (the PC's `infos wem:...` dump): all 20
starfield.esm\robotminibota .wem names are the WEMFile of a vanilla INFO, e.g. BE_KT03's survey bot Hellos (DIAL 025C46,
Misc / Hello, INFO flags Random, WEMFile 00D8DA42 and others); they are not INFO form ids (0E6020 is a REFR). **Unresolved:** whether Wwise 2026 .wem files decode in game.

**His own model (18 Oct, from the Codsworth thread, PR #361):** `make_mission.py stage --codsworth-assets <convert_codsworth.py
output>` copies its meshes, geometries, materials and textures into the stage's Data (not its report) and pins each in
plan.json; the writer adds ARMA FO4_AA_Codsworth (0x812, a copy of Starfield.esm 081886 AA_MiniBotA_Gardening with the
mesh fo4port\actors\codsworth\codsworth.nif, written with the vanilla path's prefix) and ARMO FO4_Skin_Codsworth
(0x813, a copy of 3FFD3A Skin_MiniBotA_Gardening listing only that ARMA) as his WNAM; check requires them. fold carries
the files, verify checks them. **Supported hypothesis:** the experiment archive is one stored General BA2, and the
textures in it load from there (the port uses a DDS archive); a missing texture would show on him in game.

## Commands (on the PC)

`exp_install.py` holds one experiment at a time, so the mission goes in with the core set: `fold` copies the core's
experiment folder and adds the plugin and the script; `verify` (run by `fold`, and again before install) refuses a
plugin, script, core or raider plugin whose SHA-256 differs from the stage's plan.json. A stage or fold never
overwrites an existing folder; a failed one publishes nothing.

```powershell
& $py scripts\mission\make_mission.py stage --out D:\Modding\staging\mission_wfcN --fo4 $f4\Fallout4.esm `
      --core <core experiment dir>\FO4TerrainCore.esm --raider $sf\Data\FO4ActorRaider.esm
& $py scripts\mission\make_mission.py fold --mission D:\Modding\staging\mission_wfcN --core-dir <core experiment dir> `
      --out <core experiment dir>_mission --raider $sf\Data\FO4ActorRaider.esm
& $py scripts\mission\make_mission.py verify --exp-dir <core experiment dir>_mission --plan D:\Modding\staging\mission_wfcN\plan.json --raider $sf\Data\FO4ActorRaider.esm
# the swap, on the owner's words: the core set's usual install with --exp-dir <core experiment dir>_mission and
# FO4SFMission.esm appended to its --plugins list (--pack), then exp_install.py order
& $py scripts\mission\make_mission.py log
```

### v6c wfc9b in game (19 Oct, user report)

The mission ran and could be finished (**verified** by the user's play, no log read yet), but Preston still turned on
the player. The fix was `IgnoreFriendlyHits` plus `StopCombat` from the timer. **Supported hypothesis:** with no factions
he is only neutral to the player. Friendly-hit tolerance covers friends and allies, so a stray hit in the fight still
makes him hostile, and the timer's StopCombat loses to his combat restarting. Change: a faction of ours,
`FO4SF_MinutemenFaction` (0x81F), with one relation, Ally to `PlayerFaction` (Starfield.esm 01C21C, checked by EDID
when written). Preston is in it and only in it. check requires both. Unrelated, routed to the Red Rocket work: the game
crashes once the player nears the Red Rocket workshop.

### Logs of the v6c wfc9b play (19 Oct, read on the PC, read only)

Four sessions of `fo4sf_mission.{0..3}.log` (verified, the install thread's extract):
- **Moves.** About 30 moves, fails=0 in every session, each landing within 2.5 of its target. The first move
  from a fresh load had `before=3.4e38`: Preston read float max before the move, then 229 after it. So a "GetDistance
  finite" gate would have blocked the only move that works. Codex's world-identity point needs the anchor route.
- **Actors snap back.** In one session Preston was moved 5 times and raider 0 3 times, 40 to 80 s apart, with
  fails=0 each time. Every time, the actor read its unmerged spot again (supported hypothesis: the actor returns to
  its editor location as its cell reloads, as Codsworth did on 18 Oct). The retry hides this. The real fix is in the
  world build (persistent ACHRs in the merged frame), which is next-phase work.
- **The fight and Preston.** Stage 20 on the first StartCombat, 30 when 5/5 were dead, then 40, 200 and complete
  (00:12:41 local). `preston was targeting the player: stopcombat` was logged twice, mid-fight and at stage 40. That
  confirms he targeted the player; the faction above (wfc10) is the fix.
- **Crashes.** Two of the four sessions ended in a crash dump: 7 s after stage 30 (player at -2074, -1654) and 21 s
  after complete. Both were in the mission area. The mission did not run anything at those moments except its
  1 s status check. Passed to the Red Rocket work (the workshop radius covers this area, unresolved).

### New game run 3 (28 Oct): activating Preston did nothing (fixed: finding him starts the fight)

The owner's play report (new game run 3 on newgame_v9, snapshot 20261028-181340 PC time, quoted with typos fixed):
"the Freedom Calls activation didn't work", at Concord. **Verified** (Install's read of
`D:\Modding\testqueue\newgame_20261028_run3\concord\fo4sf_mission.0.log`, relayed 29 Oct): at 18:10:17 to 18:10:19
the moves placed Preston at (-2011.14, -1697.54, 89.09) and raiders 0 to 4 near him, all `failed=false`; every status
line read `stage=10 dead=0/5`; `preston activated at stage 10` was logged five times (18:12:45, 18:13:08 twice,
18:13:09 twice) and the stage never left 10; no raider was ever put into combat, the nearest 91 to 129 m away.

**Cause (verified from the script):** OnActivate acted only at stage 30 (talking to Preston after the fight), and the
only thing that started the fight was the player coming within `EngageRadius` (60 m) of a living raider, since our
raider never engages unprompted. Stage 10's objective puts the marker on Preston, and the plugin takes the raiders
within 120 m of the museum door, his spot. **Supported hypothesis** (the status lines read the nearest raider 91 to
129 m away all session): the raiders stand farther than 60 m from his spot, so a player who walks straight to the
marker never starts the fight. On 18 Oct the fight started from the 60 m rule (raider 3 at 57 m).

**Fix (offline, untested in game):** before the fight, activating Preston or coming within `FindRadius` (20 m) of him
finds him (`found preston activated` or `found preston near d=<m>`, logged once): stage 20 at the next check, and from
then on every living raider whose 3D is loaded and that is not fighting is put into combat with the player
(`startcombat raider <i> d=<m>`), whatever the distance. The 60 m rule stays for a player who meets a raider first.
A dead Preston is never found: activating his body or standing near it starts nothing (his death stays the quest's
failure path). **Unverified hypothesis:** raiders 91 to 129 m away may not have their 3D loaded (`Is3DLoaded()`
false) when Preston is found, so those raiders are put into combat only as they load, on a later check, not at once.
This is the owner's playtest row 44.
`make_mission.py log` reports `found`. Only `FO4SF_Min00Quest.pex` changes: `FindRadius` has a default in the script,
so the plugin's records are the same. **Supported hypothesis:** the new .pex also applies to the run 3 save, where the
quest is running at stage 10 (a script's new variables start at their defaults on a loaded save). Check in game: walk
to Preston's marker (or activate him), read `found preston`, `startcombat raider` for every loaded raider, then stages
20, 30, 40 and 200.

Not this mission: Papyrus.0.log's `Cannot call GetSingleRefArray()/Activate() on a None object` at 18:12:01 is the core's
activator 00DCC6 (DefaultActivateLinkedRefOnActivate with no linked reference), routed separately.

### After the mission (7 Nov owner report): nothing put Preston back (fixed offline: the keeper keeps him)

The owner's report (Ctrl+Alt+K capture, 7 Nov 21:48 PC time, build terrain_core64v6i_l125_keeper_newgame12): "no
preston garvy after misson finshes but nothings seems broken". The capture is on the core world (the compass reads
MARS, as for the whole overlay), with no position, no stage and no mission log, so **where** Preston was is unknown.

**Intended behaviour (this doc, not Fallout 4's):** Preston stays at his placement outside the museum after the mission.
The cut-down mission has no Sanctuary move, no "The First Step" and no dialogue; sending him to Sanctuary after
stage 200, as Fallout 4 does, would be a new placement and is the owner's decision, not this fix.

**Cause (verified from the script, with the 19 Oct logs):** Relocate, the only thing that moved Preston to his merged
spot, runs from the mission's 1 s timer, and stage 200 cancels that timer. On 19 Oct Preston read his unmerged spot
again 5 times in one session (snap-back, a supported hypothesis about why), and Relocate put him back each time. After
stage 200 nothing does, so once his cell reloads (the player leaves Concord and comes back, or loads a save) he stays at
his unmerged spot, about 2,955 units from the museum or in the base world.

**Fix (offline, untested in game):** the keeper quest (FO4SF_CodsworthKeeper, timer 2, never cancelled, restarted on
every save load) also keeps Preston: `KeepPreston`, the same `MoveOver` rule and the same spot as Relocate, outdoors
only, with its own budget of 10 failed moves (renewed at each load). It logs where he is at each load
(`keeper load preston d=... at x y z disabled= dead= fails= player=x y z interior=`) and every `KeeperStatusEvery`
(12) checks, about once a minute (`keeper status preston ...`); `make_mission.py log` reports the last such line as
`keeper` and the count of `moved preston` lines as `preston_moves`. Only `FO4SF_Min00Quest.pex` changes: the keeper
already carries the `Preston` property, so the plugin's records are the same, and a save that completed the mission
gets the new check at its next load. While the mission runs, the keeper and Relocate apply the same rule. Once he has
been moved, his position + the offset is far from the player, so neither moves him twice. A `--no-codsworth` build has
no keeper and so does not keep him.

Check in game: finish the mission (or load a save where it is complete), leave Concord, come back to the museum.
Preston stands outside its door; the log has `moved preston` (if he had snapped back) and `keeper status preston d=`
small.

### PC evidence 10 Nov: his first placement never held (fixed offline: one fixed spot, FAL-128)

**Verified** (the PC's read-only check, FAL-128 document `pc-evidence-20261110`): the 7 and 9 Nov owner tests ran with
Papyrus logging off (the launcher's `papyrus_logging=off` writes `bEnableLogging=0` to StarfieldCustom.ini since
6 Nov), so they say nothing about the keeper. The last logged sessions, four on 31 Oct (keeper build, before
`2590549e`), each have `keeper init codsworth=[Actor <FO4SF_CodsworthREF (07000811)>]`: the keeper starts and
Codsworth binds.

**Cause (verified from the script against those logs):**
- Preston was moved once per session, from 542 to 544 m away (inside `RelocateRadius`, 800), into `cell=None`. The
  raiders' first moves, 488 to 530 m away, also ended in `cell=None`; they later read their unmerged spot again
  (`before` 2,727 to 2,889) and were moved a second time from 198 to 353 m away, into a loaded cell (`Surface
  (04000DEF)`), and stayed.
- Preston never got that second move: all session he read 100 to 453 m from the player, under `RelocateGap` (1,500),
  and `MoveOver` takes "under the gap from the player" as "already moved". At 20:59:31 the player stood 9 m from his
  spot and he was 155.3 m away. He was already off his spot at stage 10 (20:58:49: the player 117 m from the spot,
  Preston 210 m away), before the fight. Why he drifted there (the move into an unloaded cell, or his AI walking: his
  distance rose from 152 to 338 m in 100 s with the player nearly still) is not in the logs.
- **Correction** of the two sections above: "nobody is offset twice" is false. `MoveOver` takes an actor's target
  from where it stands, so an actor already moved is offset again when the player stands about one offset length
  (2,955 m) south-west of it: at 16:33:47 (`.1.log`) the five raiders were moved to (-3000 to -3150, -4500 to -4600).
  `2590549e`'s keeper used the same rule for Preston, so it could send him there too, and nothing brings him back.

**Fix (offline, untested in game):** Preston has one rule, `PlacePreston`, used by the mission (`Relocate`) and the
keeper (`KeepPreston`), with a **fixed** target: `PrestonLocalX/Y/Z` (the plugin's ACHR 0x802, (-811.14, 1002.46,
89.09), script defaults, no plugin change) + the merge offset = (-2011.14, -1697.54, 89.09), where the 28 Oct moves
put him. He is at his spot when he is within `HoldRadius` (25 m) of it and within `RelocateGap` of the player;
otherwise he is moved there when the player stands outdoors within `PlaceRadius` (300 m, below the 353 m move that held)
of it, unless he is fighting in the player's world (put back once the fight is over). A failed move leaves him off his
spot; the mission's and the keeper's budgets of 10 stay. `make_mission.py stage` refuses points whose Preston
position differs from `PrestonLocalX/Y/Z` by more than 0.5 m, so the spot cannot go stale silently. The raiders keep
`MoveOver` (their double offset is open, a separate fix).

`KeepCodsworthLoad` and `KeepCodsworth` no longer return early when Codsworth is None: only his own steps need him, and
Preston's check runs and restarts either way (FO4SF_Min00 itself, with neither, still does nothing on an old timer 2).

**Visible without a log** (both owner tests were blind): the keeper's state is in script variables, `prestonState`
(`at spot`, `placed`, `move failed`, `off, player away`, `off, player inside`, `off, fighting`, `gave up`),
`prestonOff` (m from his spot at the last check) and `prestonMoves`, beside `prestonFails` and `keeperChecks`; `sqv
FO4SF_CodsworthKeeper` should list them (supported hypothesis: sqv shows a quest script's variables, as in Fallout 4).
On screen: at every save load `FO4SF keeper: Preston <m> m from his spot (last: <state>, moves <n>)`, at every move
`FO4SF: Preston put back at the museum door (<mission|keeper>, was <m> m off, failed=<bool>)`, and once when the
budget is spent. The log lines gain `off=`, `state=` and `moves=` (`keeper load/status preston ...`), `off=` and
`by=` (`moved preston ...`) and `preston_off=` (the mission's status line); `make_mission.py log` reports the last
keeper line's `off=` as `preston_off`.

Check (logging on, the 9 Nov exit save, wait 70 s at the museum door, capture, quit): PASS is Preston visible at the
door and `preston_off` at most 25 (`keeper status preston ... off=`); the load notification shows without the log.

### In game 10 Nov: placed, he walked off again (fixed offline: he is held at his spot, FAL-170)

**Verified** (the PC's checks on installed `f9cae827`, logging on, the owner's 9 Nov save; FAL-128 documents
`ingame-check-1-f9cae827` and `ingame-check-2-restrain`): `PlacePreston` works, 73.7 m off at the load and at the door
within a second (`preston_off=1.5`). Not fighting, he then walked off east-north-east at about 0.9 m/s and was put back
every 29 s, 7 times in 175 s, each time with the notification. Held from the console (`setrestrained 1`) after a
put-back, he stayed: no put-back in 100 s, the same position in every line. The player then activated him: `preston
activated at stage 30`, stages 40 and 200, `reward credits=100`, `complete stage=200`, the first logged completion on
this build line.

**Fix (offline, untested in game):** `PlacePreston` holds him with `SetRestrained(True)` (Starfield's `Actor.psc`:
`bool Function SetRestrained(bool abRestrained = true) native`; Papyrus has no getter, so each instance keeps its own
`prestonHeld` and counts `prestonHolds`):
- right after every move that lands (`failed=false`), in the same call, unless he is fighting;
- at his spot, when he is calm, not yet held by this instance and within `HeldRadius` (3 m) of it, with no move: a
  load whose hold the engine did not keep, or a save where he already stands there. From `HeldRadius` to `HoldRadius`
  (25 m) nothing changes: he is put back past 25 m, and that put-back holds him;
- never in a fight: while his combat state is not 0, both instances let him go (`SetRestrained(False)`) on every check,
  whatever their own `prestonHeld` says, before `PlacePreston` and whatever the budget, the interior or the stage
  (`ReleaseInFight`), since his death stays the quest's failure path; once calm he is held again at his spot or by his
  next put-back. The PC's second review of `79c9ba81` found the first rule, "release when this instance's flag says
  held", missed him: the flag can be False while he is held (the keeper's after a load, with the engine very likely
  keeping the restraint as the game's own quests assume; the other instance's hold; a hold 3 to 25 m off). The keeper
  keeps checking with a spent budget once it has held him, so that release still runs.

The keeper clears its `prestonHeld` at every save load (`KeepCodsworthLoad`), so its first check after the load (5 s)
holds him again, whatever the engine kept. The mission instance has no load hook (it never registers
`OnPlayerLoadGame`, and the owner's save ran its `OnQuestInit` long before), so its flag can outlive a load; the
keeper's hold and every put-back cover that. Both instances may hold him: `SetRestrained` is safe to repeat. The flag
limits the at-spot hold to once per instance and session and gives the state its `, held`; the release does not trust
it. Log: `hold preston by=<mission|keeper> off=<m> ok=<SetRestrained's return>` (False when the state did not change,
the game's `Actor.psc`: he was already held) and `release preston by=<who> reason=fighting`, once per fight and
instance; `held=` in the mission's
status line, `held=` and `holds=` in `keeper load/status preston ...`. The states (`sqv`) end in `, held` while this
instance holds him (`placed, held`, `at spot, held`). No notification for a hold or a release: only a move is on
screen. `make_mission.place_preston` models the same order (`held`, `landed`). The 3 m talk rule on a
held Preston: yes, the PC's check 2b (2.5 m completed the mission, 3.2 m did not); activation did too (check 2).

Check 3 (PC, logging on, the 9 Nov save): one put-back at the load, then `preston_off` under 2 m with no further
`moved preston`, the player within 3 m, completion, and Preston in the screenshot.
