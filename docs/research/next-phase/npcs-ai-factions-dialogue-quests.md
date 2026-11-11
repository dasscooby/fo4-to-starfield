# Next phase: NPCs, AI packages, factions, dialogue and quests at full-game scale

Author: Claude-cloud, NPC and mission thread, 2026-10-19 (night research for the morning talk).

Scope: how Fallout 4's people and story run as their own ecosystem on Creation Engine 2. That means NPC records, AI
packages, factions and crime, combat, dialogue and voice, quests, the Story Manager and Papyrus. The output is built on
the player's PC from their own Fallout 4 and all DLC by a GAMMA-style launcher that ships no assets.

Labels as in docs/ai/research-log.md:
- **verified**: read from files, or seen in game.
- **supported hypothesis**: has evidence.
- **unresolved**: open.

Nothing here was run on the PC tonight. Everything comes from the repo, its measurements, this thread's in-game
results (Oct 18 and 19), and the web sources listed at the end.

## 1. Bottom line

1. **The record side is a translation job, not a research gamble.** Mutagen 0.55 types every record this area needs
   on both sides: QUST, DIAL, INFO, SCEN, PACK, SMQN, DLBR, FACT, VTYP, CSTY, LVLN and NPC_ (verified: the typed
   getters exist in both assemblies). Fallout 4's DLVW (dialogue view) is the one record with no Starfield
   counterpart. It is CK layout data, so dropping it costs nothing at run time (supported hypothesis). PACK is the
   closest layout match of any record type (subrecord overlap 0.87, docs/FORMAT-GAP.md). Starfield has the same
   package templates by editor id: Travel, Sandbox, ForceGreet, HoldPosition, UseWeapon, PatrolAndGuard and others
   (verified, docs/spikes/B4-mission-anatomy.md 1.6).
2. **The two hard problems are voice-with-lip-sync and scripts**, not records.
   - Voice: Starfield wants a `.wem` plus a FaceFX `.ffxanim` per line. Fallout 4 ships `.fuz`, which is xWMA audio
     plus a `.lip`. Lip files are built in the Creation Kit from WAV (section 5).
   - Scripts: Fallout 4's quest logic lives in 8,369 compiled `.pex` files with no sources shipped. Running them means
     decompiling and recompiling against a shim layer for the native functions that differ (section 7).
3. **"As far from Starfield as possible" is achievable inside the plugin layer.** That means our own factions,
   keywords, quest types, voice types, Story Manager tree and script library, with Starfield's own systems kept out of
   our world. The mission already proves the shape: its own faction (since tonight), its own quest, its own dialogue
   topic and its own voice folder. What Starfield systems leak in must be listed and fenced. The Red Rocket workshop
   crash (19 Oct) is the first concrete leak: an outpost activator in a world with no outpost context.
4. **The launcher must run the pipeline in stages with checkpoints.** The volume is large: 78k INFOs and 123k voice
   files in the base game alone. Lip-sync generation needs the Creation Kit on the PC, so the launcher has to drive
   it, or replace it if no headless route exists (unresolved).

## 2. Scale (verified unless marked)

Counts from docs/measurements (recon.py, read-only, Fallout4.esm 1.10.163 base game only, Starfield.esm 1.16.244):

| record | Fallout4.esm | Starfield.esm | note |
|---|---|---|---|
| QUST | 1,336 | 2,077 | |
| DIAL | 35,443 | 68,154 | |
| INFO | 78,089 | 126,347 | |
| SCEN | 3,568 | 7,613 | Fallout 4's conversations run mostly as scenes (B4: 243 of the 255 DIAL in DialogueConcordArea are scene topics) |
| PACK | 3,828 | 3,548 | |
| NPC_ | 3,015 | 7,131 | |
| FACT | 699 | 812 | |
| SMQN | 219 | 354 | Story Manager quest nodes: radiant quests, random encounters |
| DLBR / DLVW | 132 / 1 | 79 / none | |
| VTYP | 531 | 683 | |
| CSTY | 112 | 161 | |
| LVLN | 228 | 243 | |
| IDLE | 3,025 | 1,158 | idles point at Havok `.hkx` behaviours; that is animation work, not this area |
| voice files | 122,857 `.fuz` | 325,246 `.wem` + 278k `.ffxanim` | archives, FORMAT-GAP.md |
| scripts | 8,369 `.pex` | 5,034 `.pex` | |

- **DLC: unresolved.** The DLC plugins (Automatron, Far Harbor, Nuka-World, Vault-Tec and the workshop packs) are not
  measured yet. Far Harbor and Nuka-World add a lot of quests and voice. A small read-only PC job, recon.py over
  each DLC esm and its Voices ba2, gives the real totals. It is listed in section 10.
- **The voiced player.** Fallout 4 voices the player in both sexes (B4: about 100 lines per sex in one mission's
  dialogue quest). Starfield's player is silent and the game has no player-voice playback path (supported
  hypothesis: Bethesda's own statements, sources). Either keep the player's lines as text-only choices, or play them
  as the player's own sound from a script. Decide this before the dialogue converter is designed (section 5).

## 3. NPCs

What works (verified in game):
- A converted Fallout 4 actor record on a Starfield template: the raider, and Preston and Codsworth in the mission.
  It spawns, paths on the converted navmesh, fights, dies and is Essential when asked.
- Persistent ACHRs in the core world's persistent cell. Our converted world loads them at their local position until
  a script moves them: the merge offset (-1200, -2700), worked around by the mission's per-actor relocate.

What full scale needs:
- **Bodies and faces.** Humans: Fallout 4 face morphs and tints do not map to Starfield's face data (raider doc,
  section 4: "out of scope"). Two routes:
  - (a) Starfield human templates, chosen per NPC by sex, age and skin (cheap; looks wrong for named NPCs).
  - (b) The FO4 head as a skin ARMO, the way Codsworth's model works now (one path for named NPCs; it needs
    facegen meshes converted and an empty Starfield face).
  - Recommendation: (a) for generic NPCs, (b) for the named cast once (b) shows in game on one human.
- **Creatures** (deathclaws, mirelurks, super mutants, robots): new races, skeletons and animations. This depends on
  the animation track. Until it lands, creatures are Starfield stand-ins, the way Codsworth stands on the mini bot's
  race.
- **The persistent-cell offset** must be solved in the world build, not per script. Fix: write ACHRs with merged
  coordinates where the core places its own refs, or keep a per-cell anchor. Codex's world-identity hold on the
  mission is the same question.
- **Leveled lists** (LVLN 228) map almost one to one. The levels follow Fallout 4's curve, not Starfield's (decide
  once).

## 4. AI packages, factions, crime, combat

- **Packages.**
  - Same templates by editor id on both sides (verified). Converting a PACK means mapping its template link, its
    data and its conditions.
  - Conditions are the bulk of the work: Fallout 4's condition functions are mostly present in Starfield by name.
    The mission's GetIsID and GetIsSex compile and pass check. The full function table is unresolved: a read-only diff
    of the two CTDA function enums in Mutagen gives it offline.
  - Package targets that point at Fallout 4 refs need the same deterministic FormID map the doors use.
- **Factions (verified in game, Oct 18 and 19).**
  - An NPC with no faction is neutral to the player. Neutral actors turn hostile on any stray hit, and
    `IgnoreFriendlyHits` does not cover them. Preston did exactly this twice.
  - Fallout 4's relations have to be carried over whole. That includes ally and friend relations to PlayerFaction
    (Starfield.esm 01C21C), not only enemy ones.
  - Fallout 4's raiders are hostile through AIDT aggression; Starfield's Spacers are hostile through an Enemy
    relation to PlayerFaction (raider doc, verified). The converter must turn aggression-based hostility into
    relations, or keep the aggression values and accept Starfield's reaction-radius behaviour.
- **Our own faction graph.**
  - The 699 FACTs become ours: FO4_ prefix, with deterministic ids.
  - Starfield factions touch our actors only through PlayerFaction.
  - Crime factions: Fallout 4 towns barely use bounty crime. Starfield's crime system (UC, Freestar) must not attach to
    our world. Our cells set no crime faction, and our NPCs carry none of Starfield's.
- **Combat styles** (CSTY 112): typed both sides. Map them, or pick the nearest Starfield style per class (cheap first).

## 5. Dialogue and voice

- **Records.**
  - DIAL and INFO convert like the mission's Codsworth Hellos. In Starfield, DIALs live in their quest's DialogTopics,
    INFO conditions are rebuilt, and each response's WEMFile names its voice file (verified on the PC Oct 18).
  - Fallout 4's 4-option player wheel is a scene action, the "player dialogue" action with four topic slots.
    Starfield keeps scenes and player dialogue actions, with list-style choices (supported hypothesis; check against
    one vanilla SCEN).
  - The scene converter is the biggest single piece in this area. 3,568 SCEN carry most of the story's talk, against
    the mission's 20 Random Hellos.
- **Voice audio.** Fallout 4 `.fuz` = xWMA plus lip.
  - Path: extract the xWMA, decode it with ffmpeg (already on the PC in the render venv), encode to `.wem` with the
    Wwise console. Job AH did 20 files with Wwise 2026; whether 2026-built `.wem` decode in the 2021-built game is
    unresolved until Codsworth speaks.
  - Volume: about 123k files plus DLC. Batch time needs one measured run, for example 1,000 files, before any
    estimate.
- **Lip sync (the hard one).**
  - Starfield plays FaceFX `.ffxanim` files. The Creation Kit builds them from WAV files in
    `Data\Sound\Voice\<plugin>.esm\<VoiceType>\` via Audio > Run FaceFX Compiler (Starfield wiki, sources).
  - Without them a line plays with no mouth movement (supported hypothesis; Codsworth's mini bot body has no
    mouth, so the mission cannot test it).
  - Three routes:
    - (a) Drive the CK's compiler from the launcher (needs the CK installed, a GUI step; can it be scripted? unresolved).
    - (b) Write `.ffxanim` from Fallout 4's `.lip` (both FaceFX; the format is not public, unresolved).
    - (c) Ship text and audio first with no lips.
  - Recommendation: (c) now, then a spike on (b) with (a) as fallback.
- **Voice types.** Fallout 4's 531 VTYPs become ours, one folder each, named for our VTYP, not Starfield's. A converted
  voice folder never sits inside a Starfield voice type, so no vanilla line can play from our NPCs and the reverse.
- **The player.** Starfield has no voiced player.
  - Default: the converter keeps Fallout 4's player lines as the choice text (the paraphrase, or the full line as an
    option), and drops the player's audio.
  - A later option: play the player's FO4 line from a scene script action as a sound on the player.
  - The owner decides; it changes the converter.

## 6. Quests and the Story Manager

Lessons from the mission (verified in game, this thread, Oct 18 and 19):
- The Missions tab shows only quests with a QuestType keyword (QTYP). Ours used QuestTypeSideQuest 047600. Full scale
  needs our own quest types or a mapping: Main, Minutemen, Brotherhood, Railroad, Institute, Misc. Can a new QTYP
  keyword get its own tab heading? Unresolved.
- `OnStageSet` never fired on our quest (unresolved why). The mission runs its stage actions itself. At full scale,
  the stage fragments are the real logic, so this must be understood first. Spike: one quest with one fragment on
  stage 10 and one OnStageSet event, run in game.
- Objectives, notifications and rewards work through Papyrus. Quest markers through aliases are unresolved: the
  mission's forced-ref alias exists, but the markers were not checked.

At full scale:
- **QUST.** Stages, objectives and aliases convert. Aliases are the hard part. Fallout 4 quests share actors across
  quests through external aliases, as B4 found: Min00 takes 20 of its 26 aliases from MQ102 and DN092.
  The converter has to keep the alias graph intact. It only works if every quest converts with deterministic ids.
- **Story Manager** (SMQN 219). Radiant quests (Minutemen settlements, Brotherhood and Railroad repeatables, random
  encounters) run through Story Manager event nodes.
  - Ours should be its own branch under our own root, so Starfield's events (planet landings, ship events) never
    start our quests and ours never start Starfield's.
  - Can a plugin add a top-level SM branch? Supported hypothesis: yes, as mods do in Fallout 4. Check one Starfield
    SMBN.
- **Starfield's quests in our world.** Starfield's main quest, its radiant mission boards and its random encounters
  key off planets and locations. Our worldspace has no planet data. Most should never fire there (supported
  hypothesis), but crashes like the workshop one show unvetted systems do run. Plan: a fence list of Starfield
  systems that must not touch our world, each with an in-game check.

## 7. Papyrus

- **The source problem.** Fallout 4 ships compiled scripts only; Starfield ships its sources in
  Tools\ContentResources.zip (B4, verified). Route:
  1. Decompile each `.pex` (Champollion handles Fallout 4).
  2. Recompile with Starfield's compiler or Caprica against Starfield's sources plus our shim scripts.
  3. Pack the `.pex` into our archive.
  This all runs on the player's PC (no redistribution).
- **The API gap.** FORMAT-GAP says the language is the same and the native functions differ. Next step, offline on the
  PC: diff the native function lists of Fallout 4's and Starfield's base scripts (from the `.pex` call lists, as B4
  did), then count how many of the 8,369 scripts call a missing function.
  - Missing functions get a shim in our own script namespace (FO4SF_), written once.
  - What the mission already used works: SetStage, SetObjectiveDisplayed, StartCombat, StopCombat, MoveTo,
    GetDistance, AddItem, IgnoreFriendlyHits, SetActive, CompleteQuest, RegisterForRemoteEvent and OnActivate
    (verified compiling, and in game where the mission reached them).
  - Fallout 4-only systems (workshop, Pip-Boy, power armor, companion affinity scripts) need their own decisions.
    Starfield has affinity events (the AFFE record is typed in Mutagen), which may carry the companions (unresolved).
- **Event gaps.** OnStageSet is the first we hit. The decompile route only works if the events quest fragments rely
  on actually fire. The spike in section 6 comes first.

## 8. Fencing Starfield out (the "own ecosystem" list)

Known so far:
- Outposts and workshops. The Red Rocket crash (19 Oct): our workshop ACTI is patterned on
  OutpostPlayerHouseActivator, and entering its 250 m build area crashes. Fallout 4 settlements need their own
  workshop system (script-driven), not Starfield's outpost one, or a shim that only borrows its build menu after a
  proven safe test.
- Crime factions: none on our cells or NPCs (section 4).
- Story Manager: our own branch (section 6).
- Voice: our own voice types (section 5).
- Quest types: our own QTYP, or a vetted mapping (section 6).
- Still to check in game: ship and space prompts, scanner and planet UI, the Missions tab categories, and Starfield's
  random-encounter and mission-board quests while in our world.

## 9. Proposed order (bounded tasks, smallest proof first)

1. **N1. The engine questions** (one plugin, one PC run): OnStageSet with one fragment, quest markers through a forced
   alias, a new QTYP heading, and a top-level Story Manager branch. Each one gets PASS, FAIL or INCONCLUSIVE.
2. **N2. Voice proof.** Codsworth speaks (wfc9b and later), which proves Wwise 2026 `.wem`. Then one human line with
   no lips (route c), then the `.lip` to `.ffxanim` spike.
3. **N3. Faction and package converter.** All 699 FACTs with relations, our namespace, plus PACK by template.
   Offline, synthetic-fixture tests; the in-game check is one Concord settler sandboxing and one guard patrolling.
4. **N4. Papyrus census.** Decompile all 8,369 `.pex` on the PC, read-only, plus the native-function diff, giving a
   count of missing functions weighted by script use. That count sizes the shim work.
5. **N5. One whole Fallout 4 quest converted end to end** by the general converter, not hand-written as Min00 is.
   Candidate: a short self-contained one with a scene and voice. Pick it from the census.
6. **N6. The launcher stage list** for this area: records, voice, lips and scripts, each with a checkpoint and
   resume, for the core-launcher plan's L1 note.

## 10. Small read-only PC checks (when the builds leave room; through the coordinator)

- recon.py over the DLC esm files and Voices ba2: the totals in section 2.
- One vanilla Starfield SCEN with a player dialogue action, dumped: how list-style choices are stored.
- One vanilla SMBN or SMQN root: whether a plugin can add a top-level branch.
- The CK's FaceFX compiler: is there a command line?

## Sources

- Repo: docs/FORMAT-GAP.md and docs/measurements (record and archive counts); docs/spikes/B4-mission-anatomy.md;
  docs/actors/raider-conversion.md; docs/mission/when-freedom-calls.md; docs/terrain/stations.md;
  /mnt/project-files/plans/core-launcher/core-launcher-plan-2026-10-17.md;
  /mnt/project-files/research/leader-core-and-starfield-modding-2026-10-14.md.
- Lip sync and voice layout: [Starfield Mod: Audio File Conversion (Starfield wiki)](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion).
- Silent protagonist: [PC Gamer](https://www.pcgamer.com/uk/bethesda-confirms-your-starfield-character-will-be-a-silent-protagonist), [HotHardware](https://hothardware.com/news/starfield-has-111k-lines-no-voiced-protagonist).
- Papyrus compilers: [Caprica thread (Nexus forums)](https://forums.nexusmods.com/topic/3638775-wip-caprica-papyrus-compiler).
- Mutagen 0.55.0-alpha.67 assemblies (typed record getters), read locally.
