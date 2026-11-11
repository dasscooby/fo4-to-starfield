# Next phase: animations, the Pip-Boy and menus, and a Fallout-only new game

Written 2026-10-19 by the own-ecosystem thread for the morning talk. Sources: draft PR #371
(`docs/spikes/E-own-ecosystem.md`, branch claude/animations-npcs-quests-ui-f5dzpn), PC read-only jobs AR to AU, the repo
and public modding pages (listed at the end). Labels follow docs/ai/research-log.md. Papyrus, dialogue, quests and
holding off Starfield's quests are covered in `npcs-ai-factions-dialogue-quests.md` (same folder); this file doesn't repeat them.

## 1. Bottom line

- **Animations can be converted.** The project already writes Starfield `.af` clips: the door converter does it through
  the CALUMI.Animation library (`src/fo4sf/native_door.py`; layout notes on issue #40). The missing pieces are reading
  FO4's compressed Havok clips and retargeting them from FO4's 129-node skeleton onto Starfield's 97-bone human rig.
  The bone map is written and tested (`src/fo4sf/human_bones.py`, PR #371).
- **For breadth, NPCs should move with Starfield's own animations first.** Starfield's human rig ships 6,810 walk, run,
  idle and turn clips. FO4 bodies bound to that rig move as soon as they're bound. FO4's own clips come next, starting
  with what Starfield has no equivalent for: Codsworth's arms, creatures, and FO4-specific idles and furniture.
- **Menus are Scaleform in both games** (verified: Starfield's interface\almanacmenu.swf is a CWS v12 SWF). Building a
  Pip-Boy as our own SWF is plausible. Opening a new menu reliably needs SFSE, and community frameworks for that exist.
  Whether SFSE is allowed for players is the owner's call (PLAN.md already pins SFSE 0.2.21; #286 route D allows a
  small SFSE plugin where measured behaviour needs it).
- **Fallout-only new game:** 144 Starfield quests start with every new game (verified, `SfInspect startquests`, job
  AT). Our own start quest moving the player to Vault 111 is plain plugin work. Which of the 144 to hold off is in the
  NPC/quest file's section 8.

## 2. Animations

### What is verified
| Fact | Evidence |
|---|---|
| FO4 animations are Havok packfiles: 14,128 `.hkx` (Animations.ba2) + 371 (DLCRobot) + 49 (DLCworkshop01) | job AR |
| Starfield has no `.hkx`: 19,358 `.af` clips, 19,303 `.afx` event XML, 390 `.rig`, 347 `.agx` graphs, 12 `.xtbl` tables | job AR |
| `.afx` is XML (state, tag, filename, sound or foot events by frame) | job AS |
| Human rig `meshes\actors\human\characterassets\skeleton.rig`: 97 named bones, name table offset at 0x80 | job AU |
| FO4 human `skeleton.nif`: 129 NiNodes, about 38 `_skin` and fat helpers, numbered fingers | job AT |
| The repo writes `.af` and `.rig` through CALUMI (external DLL, Windows, read back on the PC) | `native_door.py`, research-log 2026-10-12 |

### The pipeline (supported hypothesis; each step is a bounded task)
1. **Decode FO4 clips.** FO4 `.hkx` animations are `hkaSplineCompressedAnimation` in Havok 2014 packfiles.
   `hkpackfile.py` already finds objects. The spline decoder is the new part: a clean-room decoder written from public
   descriptions, tested on a synthetic packfile. Candidate cross-checks: hkxpack (MIT, bundled in the Behavior Graph
   Studio editor) for packfile-to-XML, and the Blender HKX add-on for Skyrim's format. Unresolved: how many FO4 clips
   use the spline compression rather than the interleaved form.
2. **Retarget.** Map tracks with `human_bones.BONES`. Convert local rotations through each skeleton's bind pose
   (FO4 local delta to Starfield local), and scale root translation by the rig ratio. FO4 has three spine bones and
   Starfield has four (C_Spine, C_Spine1, C_Spine2, C_Chest): C_Spine1 gets an interpolated share (to test). Starfield's
   IK bones (R_HandIk, L_HandIk, Eye_Target) stay at rest.
3. **Write.** Sample at 30 fps and write `.af` through CALUMI, as the doors do, plus an `.afx` carrying FO4's
   annotations (foot and sound events) in Starfield's XML. Then add the clip to `anim_files.xtbl` or an override of it.
4. **Wire.** How an actor picks a clip is in the `.agx` graphs and `.xtbl` tables (anim_events, anim_groups,
   anim_actions). Unresolved: whether a plugin can add a new graph or only replace clips at existing paths. Replacing
   clips is proven by players (the Nexus thread swaps walk and run files), so the first proof replaces clips on a
   test-only race or graph copy, never Starfield's own.

### First proofs, smallest first
- A1: FO4 human body bound to the Starfield human rig with real joint weights (actor_rebind binds each vertex to one
  bone today, so bodies would crease). Acceptance: an FO4-bodied NPC walks with Starfield clips, and a screenshot shows
  no crease or stretch at the elbows and knees.
- A2: decode one FO4 clip offline and compare its first and last frames with the FO4 NIF bind pose (synthetic test plus
  one PC readback).
- A3: one FO4 idle retargeted and written as `.af`, played on a test actor through the console (`playidle` or a
  package). In-game screenshot required.
- A4: Codsworth's own arm and thruster clips onto his mini-bot rig (that thread owns him; A4 hands over a tool).

## 3. The Pip-Boy and menus

- Verified: Starfield - Interface.ba2 holds 250 `.swf`, 29 `.gfx` and 3 `.json` data providers. FO4's menus are also
  Scaleform. FO4's `pipboy_*.swf` would be the player's own copy, read on their PC like any other asset. Unresolved:
  whether an FO4 SWF runs unchanged under Starfield's Scaleform build, since its ActionScript calls into FO4's game
  code. The likely answer is that its look survives and its data calls don't.
- **Routes**, best first for "away from Starfield":
  1. **SFSE menu plugin plus our SWF.** Public examples: SFSE Menu Framework (GPL-3.0 with an MIT SDK; ImGui, not
     SWF), OSF UI (an HTML/CSS/JS overlay via WebView2), Carbon UI. Our own small SFSE plugin would register an "FO4
     Pip-Boy" menu that loads a SWF built from the player's FO4 Pip-Boy art and feeds it inventory, quest, map and stats
     data. This is the most faithful route but needs SFSE on every player's PC.
  2. **Reskin an existing Starfield menu.** Override a Starfield menu's SWF (for example the data menu) with one that
     looks like the Pip-Boy, keeping Starfield's data interface. This needs no SFSE but stays tied to Starfield's data.
  3. **Papyrus message boxes.** A test-only fallback.
- First proof (U1): load FO4's Pip-Boy SWF in a desktop Scaleform/Flash inspector and list the ActionScript classes
  and external calls it expects. This is an offline read on the PC with no game launch.

## 4. A Fallout-only new game

- Verified: 144 start-enabled Starfield quests, including MQ00 (the main quest start), SQ_PlayerShip and SQ_ENV, the
  radiant parents and about 40 generic dialogue quests (full list on the PC, D:\Modding\scratch\e1_inventory\at\).
- Route (supported hypothesis): our start quest runs on a new game, moves the player to Vault 111's cryo pod and gives
  FO4's starting gear. Overrides keep Starfield's intro and start quests from running. No public Starfield
  "alternate start" mod's method was confirmed tonight (the Nexus pages checked don't describe it), so the first proof
  is in game: start a new game with the plugin and record where the player appears and which quests are running
  (`sqv`). The owner's Starfield character creation either still runs or is replaced by FO4's mirror scene. FO4's
  character creation is its own UI item.
- DLC: Far Harbor, Contraptions, Vault-Tec and Nuka-World aren't installed yet (job AR), and their content needs them.

## 5. Questions for the talk

1. Is SFSE acceptable as a player requirement? It decides the Pip-Boy route and whether new animation graphs can be
   registered.
2. Should NPCs move with Starfield's animations for breadth now (recommended), with FO4 clips following? Or do FO4
   clips gate NPC work?
3. Should the new game skip Starfield character creation entirely?

## Sources
- [Help wanted: .af layout (issue #40)](https://github.com/fo4sf/fo4-to-starfield/issues/40), with the CALUMI notes.
- [Animation IO, Blender add-on for Starfield .rig/.af (Nexus 16184)](https://www.nexusmods.com/starfield/mods/16184); sources [sf_animation_io](https://github.com/deveris256/sf_animation_io), [CALUMI.Animation](https://github.com/Calaverah/CALUMI.Animation).
- [Nexus forum: animation in af, afx](https://forums.nexusmods.com/topic/13200546-animation-in-af-afx/) (`.afx` holds annotations; replacing locomotion clips works).
- [Behavior Graph Studio, FO4 HKX editor with hkxpack (Nexus FO4 107691)](https://www.nexusmods.com/fallout4/mods/107691); [blender-hkx](https://github.com/jgernandt/blender-hkx).
- [Champollion releases (FO4 and Starfield support)](https://github.com/Orvid/Champollion/releases); [Caprica/Champollion wrapper (Nexus SF 7333)](https://www.nexusmods.com/starfield/mods/7333).
- [SFSE Menu Framework](https://github.com/QTR-Modding/SFSE-Menu-Framework); [OSF UI (Nexus SF 17711)](https://www.nexusmods.com/starfield/mods/17711); [Carbon UI (Nexus SF 17899)](https://www.nexusmods.com/starfield/mods/17899).
