# Next phase: doors, activators, workshops and settlements

Author: Claude (cloud research agent), 2026-10-19. Research notes only: no code, nothing deployed, nothing run in game.
Labels per docs/ai/research-log.md: **verified** (repo file:line or URL), **supported hypothesis**, **unresolved**.
Repo citations are to `main` as checked out on 2026-10-19.

## 1. Summary and recommendation

Doors and activators are engine primitives (activation, prompt, lock UI, NPC pathing, navmesh door links), and FO4 and
Starfield share them closely: same DOOR/XTEL/lock lineage, same `WorkshopKeyword` id, same bench types. Rebuilding them
"our own way" would cost a lot and buy nothing, so for doors the "own ecosystem" principle should mean *FO4's data and
FO4's behaviour rules on Starfield's native records*, not our own door engine. Settlements are the opposite: FO4's
settlement game (settlers, food/water/defense/happiness, supply lines, attacks, the build budget) is Papyrus logic
on top of a native build mode, and Starfield's outpost logic (beacon, resource extraction, crew, cargo links, planet
biomes) is a different game. **Recommendation: hybrid.** Use Starfield's native build-mode engine (placement, snapping,
menu) as the placement layer only, and run FO4's settlement rules as our own Papyrus layer (an FO4SF "WorkshopParent"),
never the outpost beacon / OutpostBeaconScript. Breadth first: (1) make every FO4 door behave as FO4 set it up (locks,
enable parents, names, unusable doors), (2) one load-door shape everywhere, (3) workbench opens a build menu of FO4
parts at Red Rocket, (4) settlement stats, later settlers and attacks. Before any of that, rule the v6 workshop ACTI in
or out of the Red Rocket RAM/crash report with one A/B run (section 6, check P1).

## 2. What Starfield gives us

### 2.1 Doors (DOOR + REFR)
- **verified** (docs/ai/research-log.md:728-740, raw survey of Starfield.esm): a vanilla load door is a persistent DOOR
  REFR (0x400) with XTEL (destination door, absolute arrival point, flags), both ends linked, 964 of 964. 506 load-door
  bases have an AnimationGraphComponent (`*_Load` graphs); 458 have none and are Hidden or Automatic (e.g.
  `LoadElevator_InvisibleDoor` 21F2A7, 322 refs; `AutoloadDoor_Cave` 24F9CE, scripted).
- **verified** (docs/spikes/WP-doors-research.md:10-19, docs/spikes/sliding-doors.md:52-69): door motion is not in the
  NIF; the DOOR record names a graph (`SimpleOpenClose01.agx` etc.), a skeleton `.rig` and an animations folder.
- **verified** (docs/terrain/scripted-doors.md:13-16, 36-40): in our overlay a persistent reference reads its unmerged
  position, which is why native XTEL exterior doors failed and the exterior side uses ACTI + `FO4SF_LoadDoor` (MoveTo).
- Door flags: FO4's CK lists Automatic, Hidden, Minimal Use, Do Not Open in Combat Search, Non Occluder, No "To" Text,
  Sliding, Is Marker (**verified** for FO4: https://falloutck.uesp.net/wiki/Door). Starfield uses Automatic and Hidden
  on vanilla records (**verified**, research-log:734); that the rest of FO4's FNAM bits mean the same in Starfield is a
  **supported hypothesis** (shared lineage; Mutagen exposes `Flags` on both) until the door survey compares them.
- Locks: Starfield has four tiers, Novice / Advanced / Expert / Master, gated by Security rank and digipicks
  (**verified**: https://www.shacknews.com/article/136876/lockpicking-starfield), the same four names as FO4. That a
  REFR lock block (XLOC: level, key, flags) exists in Starfield records and in Mutagen 0.55 Starfield `PlacedObject`
  is a **supported hypothesis**; **unresolved** until reflection on the PC (check P3). Our export already reads FO4's
  (dotnet/Fo4Export/ReferenceExport.cs:45-49); nothing writes it (docs/spikes/door-behaviour.md:20).
- Activate parents: Mutagen 0.55 Starfield has no ActivateParents on a reference (**verified**,
  docs/terrain/garage-button.md:289-290); the native substitute is vanilla `DefaultActivateLinkedRefOnActivate` with a
  `LinkCustom02` linked ref (**verified**, garage-button.md:301-305), already used by PluginSpike ActivationChains.cs
  (docs/terrain/port-promotions.md:222-231).

### 2.2 Elevators
- **verified** (docs/spikes/sliding-doors.md:184-197): three vanilla mechanisms. (1) `ElevatorMasterScript` (2 refs):
  linked-ref keywords for platform helper, buttons and doors; a `PlatformHelperFree01` ACTI driven by graph variables.
  (2) `MovingPlatformMasterScript` (22 refs): a helper moved by `TranslateToRef` between floor markers, buttons and
  door attached by AttachRef. (3) Load elevators (`LoadElevatorManagerScript`, `LoadElevatorFloorScript`, teleport
  doors such as `ElvGen_ExSm_DoorFull01_Load`), i.e. most vanilla elevators are a door + load screen.
- A community mod turned 18 vanilla elevators into real moving ones (**verified** that it exists:
  https://wccftech.com/starfield-mod-adds-real-elevators-with-no-loading-screen/amp/), so true rides are doable with
  CK-level content; its method is not published there (**unresolved**).

### 2.3 Activators
- ACTI + optional VMAD; vanilla `Default1StateActivator` / `Default2StateActivator` style scripts and graphs exist
  (**verified** for the garage pair's FO4 side; Starfield side via `DefaultActivateLinkedRefOnActivate`,
  garage-button.md:281-305). Prompt text comes from FULL plus the activate verb; Starfield-side override keywords such
  as `WorkshopUseDecorateTextKeyword` exist (**verified**, docs/terrain/stations.md:118-122).

### 2.4 Outposts and build mode
- **verified** (stations.md:116-129): build mode opens on activating a REFR whose base carries `WorkshopKeyword`
  (054BA7, same id as FO4); no script is required. The pre-placed pattern is ACTI `OutpostPlayerHouseActivator`
  00024DC7 ("Decorate", OutpostCategory* keywords pick the menu categories, PRPS `OutpostBuildAreaRadius` = 250),
  placed once in an exterior worldspace (Neon). `OutpostBeaconScript` has no OnActivate.
- `OutpostBuildAreaRadius` is an actor value (AVIF 00063FC5, stations.md:101); the beacon's default area is 150
  and a mod that raised it via that AV reports floating-item warnings, camera clipping and broken ship landing
  (**verified** as the mod author's report: https://www.nexusmods.com/starfield/mods/5576). Treat large radii as risky.
- Build mode outside the beacon flow works with Papyrus-only mods: SKK "Player Homes Anywhere" deploys a decorator
  panel in most interior cells, ~250 m range, refuses ship interiors and non-persistent (procedural) cells
  (**verified** as described: https://www.nexusmods.com/starfield/mods/7271); a console/batch mod places outposts in
  "restricted" areas (https://www.nexusmods.com/starfield/mods/2997). So the build engine is not tied to planets or
  to the beacon: **supported hypothesis** for our overlay worldspace (registered on a planet; docs/JOURNAL.md:747).
- Beacons need a planet surface and cannot sit on POIs (**verified** as a mod author's report:
  https://nexusmods.com/starfield/mods/12318); we should not use the beacon at all.
- Starfield buildables are COBJ records filtered into categories by keywords (**supported hypothesis**: the
  OutpostCategory* keywords on the activator decide which categories show; how a COBJ joins a category is
  **unresolved**, check P5).

## 3. What FO4 needs

### 3.1 Doors
Per door, FO4 decides (docs/spikes/door-behaviour.md:14-27): teleport (XTEL), open/close motion (NIF sequences), lock
(level + key), open at start, initially disabled + enable parent (quest-hidden doors), activate parents (buttons,
terminals), FNAM flags (automatic, hidden, minimal use, no "to" text), FULL name, sounds, scripts (elevators, quest
doors). Today the port writes XTEL (interiors), FO4SF_LoadDoor (exterior), open-by-default, and disabled; it does not
write locks, enable parents, door activate parents, flags, FO4 names on exterior doors (FULL "Door") or sounds.
Quest doors matter for breadth: Preston's door is a locked door the quest unlocks (`OpenPrestonDoor`: Unlock, SetOpen;
**verified**, docs/spikes/B4-mission-anatomy.md:71); the Vault 111 exit ends in an automatic load door
`AutoloadDoorNoText` FNAM 0x42 (B4-mission-anatomy.md:204-206).

### 3.2 Elevators
FO4 uses (a) load elevators: car + scripted doors + panel, then a load (Fort Hagen, Vault 95; exact records
**unresolved**, door-behaviour.md:29-30); (b) animated activator rides (Vault 111 `VltElevator`, stage clips played by
the quest; **verified**, sliding-doors.md:174-182). Today both are plain teleports.

### 3.3 Workshops and settlements
- The workbench is a CONT with `WorkshopScript` (VMAD) and `WorkshopKeyword` first in KWDA; 28 + 1 refs in the core
  (**verified**, stations.md:78-82). The v6 build turns each into an ACTI copied from 00024DC7 (stations.md:97-104).
- FO4's settlement layer (**verified** from https://falloutck.uesp.net/wiki/Workshop unless noted): build area from
  `WorkshopLinkedPrimitive` primitives, else the location's world marker + radius; `WorkshopLinkContainer`,
  `WorkshopLinkSpawn`, `WorkshopLinkCenter`, `WorkshopLinkAttackMarker` links; location keyword
  `LocTypeWorkshopSettlement`; scrap via `WorkshopRecipeFilterScrap`; ratings for population, power, water, food,
  shelter, defense, happiness; tuning such as base max NPCs 10 + Charisma, vendor income.
- Script side: a `WorkshopParent` quest running `WorkshopParentScript` (quest 0002058E in Fallout4.esm per a modder;
  **supported hypothesis**: https://forums.nexusmods.com/topic/13481102-papyrus-workshopparentscriptworkshopobjectbuilt-not-triggering-for-all-built-objects),
  `WorkshopScript` on each workbench, `WorkshopObjectScript` on buildables, `WorkshopNPCScript` on settlers
  (names **supported hypothesis**; read them in the user's FO4 scripts, check P6). Built-object events
  (`OnWorkshopObjectPlaced` etc.) are native ObjectReference events in FO4 (**verified**:
  https://falloutck.uesp.net/wiki/OnWorkshopObjectPlaced_-_ObjectReference); whether Starfield's Papyrus keeps them is
  **unresolved** (check P4).
- Build budget: per-workshop actor values 348/349 (triangles current/max) and 34A/34B (draws current/max)
  (**verified** as community reports: https://steamcommunity.com/app/377160/discussions/0/3418810706128557734,
  https://www.nexusmods.com/fallout4/mods/87081).
- The owner's Preston report (still aggressive, quest completes) touches this layer: FO4 settlers carry
  `WorkshopNPCFaction` and the workshop scripts (B4-mission-anatomy.md:162-166); whether the hostility comes from a
  missing faction relation is **unresolved** and belongs to the NPC/faction note, not here.

## 4. Options per system (cost, risk)

| System | Reuse Starfield | Own ecosystem | Hybrid (recommended where marked) |
|---|---|---|---|
| Interior doors | Native DOOR + XTEL + lock + flags (works today for XTEL). Cost: low (writer fields). Risk: low | Scripted ACTI everywhere. Cost: medium; loses lock UI, NPC door use, navmesh door links. Risk: medium | **Reuse** |
| Exterior load doors | Native XTEL: blocked by the overlay position bug (scripted-doors.md:13-16) | ACTI + FO4SF_LoadDoor (today). No lock UI, NPCs cannot follow | **Hybrid**: a non-load DOOR base (rigged, FO4 FULL, XLOC) carrying FO4SF_LoadDoor, so the engine gives lock, prompt and animation and the script teleports. Cost: low-medium. Risk: whether a scripted DOOR's OnActivate runs before / instead of the open (check P2) |
| Locks + keys | Native XLOC with FO4 level mapped 1:1 to the four tiers, FO4 key form as KEYM (keys must exist in the build). Cost: low. Risk: Mutagen field (P3) | Script lock on ACTI. Cost: medium, no minigame | **Reuse**; ACTI doors use the hybrid DOOR above |
| Enable parents | Native XESP. Cost: low. Risk: parent must be in the build, else door hidden forever (write only when present, list the rest) | n/a | **Reuse** |
| Activate parents | `DefaultActivateLinkedRefOnActivate` wire (exists) | own multi-child script | **Reuse**, add a small multi-child script later (one parent, many children) |
| Elevators (load) | Starfield load-elevator pattern (manager + floor scripts, `*_Load` door) | keep teleport | **Reuse-lite**: keep the teleport, add the FO4 panel as the activator and a fade; full manager later |
| Elevators (ride) | `MovingPlatformMasterScript` + `TranslateToRef` (records only, sliding-doors.md:199-205) | stage clips on own graph (NO-GO for B1, B4 doc:215) | **Reuse** later, Vault 111 first |
| Build mode (placement, menu) | Native build mode from a `WorkshopKeyword` ACTI (no script). Cost: low. Risk: outpost UI/limits, RAM (P1), persistence of built refs in an overlay (stations.md:192-194) | Own placement UI (SFSE + UI). Cost: very high. Risk: high | **Reuse** as placement engine only |
| Build menu content | Starfield COBJs (outpost parts) | FO4 parts as our own COBJ list built on the PC from FO4 COBJs + converted meshes | **Own content**: FO4 COBJ → our COBJ with FO4 components mapped to converted MISC junk; Starfield categories hidden |
| Settlement rules | Outpost beacon / crew / extraction. Different game, planet-bound | Port of FO4's settlement scripts as FO4SF Papyrus (own quest, own AVs or globals) | **Own ecosystem**; never attach OutpostBeaconScript |
| Settlers, attacks, supply lines | Starfield crew/outpost assignment | FO4 links (center, spawn, attack markers) + our quest | **Own ecosystem**, after NPC/AI basics work |
| Native fallback | – | SFSE plugin (CommonLibSF) for events Papyrus lacks (e.g. object placed, budget) | only where a measured gap exists (core-launcher plan route D) |

Cost scale: low = writer field + test; medium = new record class or script; high = new subsystem. Script porting
note: FO4's settlement scripts are Bethesda's; under the "ship no assets" rule we write our own FO4SF scripts that
follow FO4's rules (documented behaviour, numbers read from the user's Fallout4.esm at build time), and do not copy
FO4 .psc text into the repo. Decompiling the user's own .pex at install time is possible (Champollion) but
**unresolved** as a policy question for the owner.

## 5. Recommended next-phase plan (smallest useful first)

0. **Rule the workshop ACTI in or out of the Red Rocket RAM / crash report** (P1, one A/B run, no code). If it is the
   cause, ship builds without workshop ACTIs until step 6.
1. **Door survey on the PC** (already planned, door-behaviour.md:51-53): re-export the door cells, run
   `door_survey.py` / `door_audit.py`. Output: counts per behaviour class. Gates steps 2-4 by evidence.
2. **Door data writer, interiors** (PluginSpike): XLOC (level map + key when the KEYM is built), XESP enable parents
   when the parent is built, FNAM flags copied, FO4 FULL. Synthetic tests per field. Fixes "doors usable that should
   not be" and quest-hidden doors. Preston's door needs only the lock + the quest's Unlock.
3. **One exterior door shape**: replace the ACTI load door with a scripted DOOR (P2 decides). Gives locks and the FO4
   name outdoors; same FO4SF_LoadDoor contract, so no destination changes.
4. **Elevators v0**: FO4 elevator panel as the activator, teleport + fade; Fort Hagen and Vault 95 entrances made
   aimable (door_audit result). Rides (Vault 111) stay for later.
5. **Workbench build mode v0 at Red Rocket**: keep the WorkshopKeyword ACTI, but with a category set that shows only our
   own keyword's COBJs; 10-20 FO4 buildables (walls, floors, a bed, a light) as COBJs on converted meshes, costs in
   converted junk MISC. Acceptance: owner builds a wall, saves, reloads, wall is there.
6. **FO4SF settlement layer v0** (own quest): ratings (food, water, beds, defense, power) recomputed on build events,
   shown on the workbench prompt or a message; FO4 links (center/spawn) carried into the build. No settlers yet.
7. **Settlers, recruitment beacon, attacks, supply lines**: after the NPC/AI note's basics; SFSE only for measured gaps.

## 6. Open questions and read-only PC checks

- **P1 (crash lead, weak):** does the Red Rocket RAM spike follow the workshop ACTI? A/B: same save, same walk, (a) as
  is, (b) `prid 0200D272` then `disable` before walking in, (c) a build without workshops. Record the game's working
  set each time. **unresolved**; v5 carried the same records and the walk passed (context given), so expect "no".
- **P2:** does a non-load DOOR with a VMAD script get OnActivate and can it MoveTo the player (vanilla
  `AutoloadDoor_Cave` 24F9CE is a scripted DOOR, research-log:735)? Read its VMAD with SfInspect; then one test cell.
- **P3:** does Mutagen 0.55-alpha.67 Starfield `PlacedObject` have `Lock` / `EnableParent` / `Flags` on DOOR, and what
  do vanilla locked doors carry? Read-only: reflection dump + a SfInspect scan of DOOR REFRs with XLOC
  (level values, key, flags) in Starfield.esm.
- **P4:** which workshop events and functions does Starfield Papyrus keep? Read-only: grep `ObjectReference.psc`,
  `WorkshopParentScript.psc`, `OutpostBeaconScript.psc` in `Tools\ContentResources.zip` for `OnWorkshop`,
  `GetWorkshop`, `WorkshopObject`.
- **P5:** how does a COBJ join a build-mode category (keyword on the COBJ, on the created object, or a FLST)? Read-only:
  dump 5 vanilla outpost COBJs and their created objects with SfInspect.
- **P6:** FO4 settlement data inventory: per settlement LCTN (keyword, world marker, radius), workbench links
  (center, spawn, attack, primitives, containers), and AVs 348-34B defaults. Read-only Fo4Export over Fallout4.esm +
  DLC; also list FO4 script names on workbenches and buildables.
- **P7:** do player-built objects in our overlay worldspace persist across save/load and reload in the right place
  (overlay persistent-position bug)? First build-mode test (step 5) answers it.
- **P8 (owner):** is decompiling the user's own FO4 scripts at install time acceptable, or must every FO4SF script be
  written fresh from documented behaviour?

## Tool landscape (for the above)
- SFSE 0.2.21 matches the pinned Starfield 1.16.244, Steam only (**verified**, docs/SETUP.md:10-11); public history
  shows SFSE tracking each runtime (0.2.18 for 1.15.222, Aug 2025: https://allmods.net/?p=167831). CommonLibSF exists
  for native plugins (credited on https://www.nexusmods.com/starfield/mods/3846).
- Creation Kit for Starfield since June 2024, with full/medium/small masters and ESM-only sharing
  (**verified**: https://nexusmods.com/news/14993). The CK's `Tools\Papyrus Compiler\PapyrusCompiler.exe` with
  imports from `Tools\ContentResources.zip` is what the repo already uses (**verified**,
  scripts/bridge/make_bridge.py:12, 54-67, 229).
- SF1Edit (xEdit) supports Starfield (**verified** that it exists and needed updates per game version: same Nexus news
  post). Mutagen.Bethesda.Starfield is pinned at 0.55.0-alpha.67 (**verified**, dotnet/PluginSpike/PluginSpike.csproj:12);
  it is alpha, so every new record field we write needs a byte check against a vanilla record.
