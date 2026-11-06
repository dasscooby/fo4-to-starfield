# Next-phase framework: the questions we have to answer, and the possibilities for each

Started 2026-10-19 by Claude-cloud (framework thread) on the owner's ask: "build a framework of questions and things
for what we are going to do; look at modding communities, the tools, and other things." A living document, extended in
waves. **Wave 1 done 2026-10-19 ~18:05Z; wave 2 (gap filling) folded in ~18:30Z**: 11 research agents (raw findings with every source in
[findings/](findings/)), folded into 7 cross-cutting files with about 280 numbered questions, plus the five phase files
the phase threads write. Nothing here is decided until the owner says so; every "recommend" is a default to argue with.

## How to use it

- Each question has a stable ID (`WP-14`, `REL-26` ...), why it matters, the options with sources, how to answer it
  (owner decision, offline research, PC probe, community or Bethesda/Nexus contact), what it blocks, and a status.
- Evidence labels follow docs/ai/research-log.md: **verified** (read in a linked source or file), **supported
  hypothesis**, **unresolved**. Wave 1 ran out of web-search budget and hit Nexus rate limits part way, so every file has
  a "Gaps for wave 2" list; nothing was guessed to fill them.
- To answer a question: write the answer and its evidence under the question (status `answered: ...` or `decided by
  owner, <date>`), and record architectural decisions in docs/ai/decisions.md.

## Settled already (do not re-ask)

Silent player by default. Starfield's animations first, FO4 clips later. SFSE and the free Starfield Creation Kit MAY
be required. The Commonwealth, Far Harbor and Nuka-World share one Earth-like planet with real days, nights and weather.
Phase order: new game (Vault 111 start, no Starfield intro), door animations, all interiors, launcher; then world
breadth, people and story, Fallout systems (order open). GitHub release first, then Nexus (GPL-3 notice for Mutagen).
Breadth before polish. A launcher that ships no assets; the player owns both games.

## Files

### Phase files (written by their own threads; indexed here, not edited here)

| phase | file | raw notes |
|---|---|---|
| 1. New game (Vault 111 start) | [newgame.md](newgame.md): revision 4, 112 questions (Questions page count) NG-A1 to NG-N (K: FO4's MQ101/MQ102 chain; L: saves; M: Bethesda guideline; N: char-gen state), owner decisions, cheapest-first list | [newgame-notes/](newgame-notes/) |
| 2. Door enter and exit animations | [door-animations.md](door-animations.md): 40 questions A to J, blockers starred | |
| 3. All interiors | [interiors.md](interiors.md): 98 questions: 80 by step (A offline to F release), D1 to D9 on doors and markers, X1 to X9 from these findings | |
| 4. Launcher | [launcher.md](launcher.md): 88 questions: 13 owner decisions D1 to D13 plus 75 in seven areas | [launcher-sources/](launcher-sources/) |
| Forward focus: GAMMA-style combined core (owner, 2026-10-19 23:19Z) | [combined-core.md](combined-core.md), owned by the GAMMA-style combined core thread | [combined-core-notes/](combined-core-notes/) |
| Fallout systems and engine mechanics | [engine-mechanics.md](engine-mechanics.md): ten top decisions | [engine-mechanics-notes/](engine-mechanics-notes/) (about 400 questions) |

### Cross-cutting files (this thread)

| area | file | IDs | what it covers |
|---|---|---|---|
| World and planet | [world-and-planet.md](world-and-planet.md) | WP | host planet, overlays and landings, real geography, day, weather, hazards, coasts, map and fast travel, the ship, budgets |
| People and story | [people-and-story.md](people-and-story.md) | PS | dialogue UI for a silent player, voice and lip sync (technical), faces, bodies and clothing, companions, factions, radiant quests |
| Release, community and legal | [release-community-legal.md](release-community-legal.md) | REL | licences, Bethesda and Nexus terms, voice-audio policy, naming, money, contacting Bethesda and Nexus, community home, support, contributors, dates |
| Tooling and testing | [tooling-and-testing.md](tooling-and-testing.md) | TT | CK-only steps, SFSE, xEdit, Mutagen, Spriggit, plugin limits, crash loggers, Debug functions, performance protocol, testers |
| Asset pipeline | [asset-pipeline.md](asset-pipeline.md) | AP | meshes, collision, animation, textures, sound, voice files, facegen, clothing, LOD, build time and disk, tool licences |
| Versions and maintenance | [versions-and-maintenance.md](versions-and-maintenance.md) | VM | FO4 and Starfield versions and stores, patch days, SFSE lag, engine ceilings, hardware, long-term cost |
| Multi-game future | [multi-game-future.md](multi-game-future.md) | MG | FO3 and New Vegas on the same core, one rule set, ObScript, creatures, world placement, what to reserve now |
| Background-game audio (owner, 2026-11-01) | [background-game-audio.md](background-game-audio.md) | BGA | design on paper under [REL-61](release-community-legal.md) (do not build now) and A1 (subtitles only), building on [findings/original-engine-audio.md](findings/original-engine-audio.md): the original game in the background plays radio and music (voice only if A1 is reopened) on Starfield's cue; protocol draft, risks, stages S0 to S4 |
| **Dependencies across all files** | [dependencies.md](dependencies.md) | | critical path per phase, about 90 duplicate topics with an owner file, 16 conflicting recommendations, 29 experiments ranked by questions closed, 47 owner decisions by phase |

Raw findings (one per research agent, all sources): [precedents](findings/precedents.md),
[legal-policy](findings/legal-policy.md), [starfield-toolchain](findings/starfield-toolchain.md),
[asset-conversion](findings/asset-conversion.md), [world-planet](findings/world-planet.md),
[people-story](findings/people-story.md), [fallout-systems-precedents](findings/fallout-systems-precedents.md) (for the
engine-mechanics thread), [distribution-community](findings/distribution-community.md),
[versions-performance](findings/versions-performance.md), [testing-qa](findings/testing-qa.md),
[multi-game-scope](findings/multi-game-scope.md).

## What wave 1 changed in the picture (biggest findings)

1. **Voice audio is the sharpest legal risk.** Capital Wasteland (FO3 in FO4) built a tool to convert the player's own
   FO3 audio and cancelled it in 2018 after Bethesda staff and a lawyer flagged it: voice acting is licensed, not owned
   (**verified**, findings/precedents.md). Our `scripts/actors/codsworth_voice.py` has the same shape. REL-26, REL-27.
2. **We rest on tolerance, not permission.** Read literally, Bethesda's terms forbid tools "created for" its games
   without written permission; ~~the Starfield CK EULA names an approval route for cross-game mods~~ [Correction
   2026-10-19: that clause covers paid Creations only; the Fallout 4 ToS and Steam EULA's tool-output clause are the
   stronger obstacles; launcher-sources/eula.md]. A player-side
   cross-game converter (FNV to FO4, GPL-3) has been on Nexus since 2023 (**verified**). REL-30, REL-31.
3. **Most players own a different Fallout 4 than we pin, and our archive reader can't open it yet.** Steam is on
   1.11.240 (Aug 2026), we pin 1.10.163. The April 2024 next-gen update added BA2 header versions 7 and 8, which xEdit
   and OpenMW read with the v1 layout (**verified**, wave 2); `src/fo4sf/ba2.py` accepts 1 to 3 only. Small fix:
   accept {1, 7, 8}; that fix is on launcher PR #394 (not merged). GOG ships only 1.10.163 (gogdb.org). VM-01 to VM-03.
4. **Starfield's own Earth is a serious host.** It already has a 24 h day, the real Sun and Moon, and handmade overlays
   at real city coordinates; PNDT `EOVR` may add our overlays without overriding the planet's list (**supported
   hypothesis**). Three landings, not one worldspace. WP-01, WP-08, WP-14.
5. **Lip sync at master scale is proven by the community** (the CK's FaceFX compiler over all of Starfield.esm), but no
   one has shown it unattended or timed it; unvoiced lines flash past unreadably without silent placeholders. PS-08, PS-07.
6. **The dialogue menu is a loose SWF**, so a Fallout-style choice list is a UI file job, likely without SFSE. PS-01.
7. **No public total conversion automates in-game testing like we do**; the ecosystem is ahead on crash signatures
   (sf-crash-logger, GPL-3), Spriggit record diffs, and Starfield's own `Debug` test functions (which work in retail is
   open). TT-23, TT-15, TT-25.
8. **Engine ceilings we will meet at full scale:** 256 active BA2s, 253 full-master slots, archives over 4 GiB may not
   load, no precombines. VM-23 to VM-28.
9. **No Starfield mod has a furniture-style power armor or a real VATS**; Starcade OS shows a Pip-Boy shape (an item
   opens an HTML menu through OSF UI). Passed to the engine-mechanics thread.
10. **Mod managers handle Starfield natively now** (MO2 2.5.2, Vortex); SFSE refuses the Game Pass build. REL and launcher.

## What wave 2 added (gap filling)

- **Licence line (verified):** the GPL FAQ treats programs that talk over pipes or command-line arguments as separate
  programs; a launcher that loads Mutagen in-process becomes GPL-3. SFSE is not permissively licensed (only
  `PluginAPI.h` is MIT) and does not support Game Pass. REL-01, VM-21.
- **Nexus (verified):** auto-update does not count as "crucial" for an internet-using executable; network features need a
  staff review with source; an AI-content tag is now required. Bethesda's own mod rules ban getting around add-on
  purchases, so the converter should check DLC ownership before converting each DLC. REL.
- **CK steps:** ~~LOD has a command line (`CreationKit.exe -MockWorldSpaceLOD:<plugin> <worldspaces>`, **verified**)~~
  [Settled 2026-10-19 by PC job 20: `-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [...]` exists in the Starfield
  CK (**verified**). Also there: `-ExportFaceGenData`, `-RunValidationSuite`, `-ExportESM`; no precombine switch. Verified CK switches include `-GenerateMeshLOD*`, `-CompileFaceFXAnims` and
  `-GenerateSEQ`; lips go through `-CompileFaceFXAnims` plus `Tools\LipGenerator\LipGenerator.exe`; no CK compiles
  scripts (PapyrusCompiler.exe does, headless)];
  Starfield cells carry no precombine or previs fields, ~~(**supported hypothesis**: no bake step)~~ [Correction: the
  Starfield CK has GUI actions "Generate Precombined Visibility" for a cell or all loaded cells, so a bake may exist;
  **unresolved**, interiors.md T9]. Named NPC faces are
  pre-baked per form ID by two CK bakes. TT, AP, PS.
- **Limits (verified):** medium masters hold 65,536 new records, with 256 slots. BA2 offsets are 64-bit; whether Starfield
  loads an archive over 4 GiB is still open. VM-23 to VM-28.
- **Saves:** the game itself clears active plugins in Plugins.txt when a save loads or the Creations menu opens (users'
  reports, matching newgame.md L). VM-14.
- **Still unresolved after wave 2:** any DMCA or takedown of a cross-game converter (none found); how Shattered Space's
  landmass was built (a read of its esm settles it); whether Starfield needs an SEQ file for start-game dialogue quests
  (the Starfield CK has `-GenerateSEQ`, and our writer could make one); Wwise terms for batch conversion on players' PCs.

## Cross-cutting points from the phase threads (wave 1)

- **New game:** `StartupQuest_DO` may be a cleaner override than stopping MQ00 and MQ101 (newgame.md NG-A1).
- **Licences:** our built .NET tools are GPL-3 through Mutagen; CALUMI is LGPL (door-animations.md J38, J39). Creations
  is likely closed to us (J40; also REL-13).
- **Mutagen pin:** alpha.75 shipped today, we pin alpha.67 (TT). The "Fallout4 2.8.1-prerelease002" package named in
  next-phase/launcher-gamma-model-and-community-tools.md is an unlisted 2021 package, not a newer release (correction,
  from the Interiors thread).
- **Record tools disagree:** Mutagen and xEdit read the LIGH flag bits from bit 4 up differently (Interiors thread).
- **CK risk:** the Starfield CK may crash on terminals written outside it (Interiors thread; affects TT CK-only steps).
- **Locations:** the port writes no XLCN on interior cells, so our interiors have no location, leveling or cleared state
  today (Interiors thread; touches PS radiant quests and WP map).
- **Interior count (reconciled, interiors.md "Count reconciliation"):** 230 in the repo's interior-backlog.json counts
  interiors behind the Commonwealth worldspace's own load doors (203 plus 27 second-hop); 271 in the census adds 41
  entered from the walled Diamond City and Goodneighbor worldspaces. The plan builds 251 of the 255 still to do (4 have
  no door model), plus 2 from Automatron.
- **Medium-master test:** interiors.md declines the synthetic-plugin probe for itself (FO4Port stays a full master); it
  stays open for VM-25 and the planet master (WP-04).
- **Engine mechanics wave 2:** an own engine menu is partly possible via CommonLibSF; Mutagen types Starfield FACT fully
  but has no RELA group; Address Library supports 1.16.244; the Carbon UI licence needs its author's word; new precedent
  BACUP, a GPL-3 Creation Engine record and asset converter. A read-only PC job (CK command-line switches for lip
  generation, script compiling, animation data) is queued; its answer settles PS-08, AP-40 and TT CK-only steps.
- **Unattended lip sync: the offline chain is proven (PC jobs 24 and 27 to 33, verified; engine-mechanics dialogue.md):**
  WAV plus text goes through LipGenerator.exe and `Tools\FaceFX\ffxc.exe` to a game-format `.ffxanim`, headless, with
  our compiled male actor matching the shipped one. Left for an in-game slot: WEM-id naming and placement, one line on a
  face, and an actor for robots (none ships). PS-08, AP-41, TT-08.
- **New game save trap (newgame.md N, verified by job 23):** stopping MQ101 leaves saving off and the HUD hidden
  (stage 0 sets char-gen mode, the stop fragment restores neither); fixed offline on the NewGame branch, nothing installed.
- **Lip-sync inputs (PC job 21, verified):** Starfield ships 278,582 per-line `.ffxanim` files and no `.facefx` files;
  LipGenerator.exe needs `actor.facefx` and `actoranalysis.facefx` per face rig, which are not in the shipped data.
  Where they come from is the open lip-sync question (PS-08, AP-40, TT-08).
- **Bethesda's own guideline (newgame.md M, verbatim):** help.bethesda.net 51731 bans uploading mods with assets from
  other Bethesda games; building on the player's PC is neither covered nor approved; Creations is ruled out. REL.
- **Sustenance risk (newgame.md NG-M1):** sustenance is gated on MQ101Debug, and our start stops MQ00, possibly before
  it sets that; checkable offline.
- **Saves (newgame.md L):** the Creations load-order prompt with Save preselected silently switches our plugins off on
  old saves (verified on the owner's PC). Touches VM-14 and REL-51.
- **Map markers (PR #399, map-markers.md on its branch):** FO4 markers carry a 66-icon Type enum; Starfield's Type is a
  bare byte with no enum in Mutagen. Whether Starfield has icons for Vault, Metro and Diamond City is unresolved (a TNAM
  census of Starfield.esm settles it). Touches WP map questions.
- **Door animations (second pass):** INSTANT DOORS' ini lines only remove fades and do not shorten the load-door wait
  (door-animations.md, correction). New: a Starfield 1.16 Papyrus API table for doors, and a risk: Starfield's `Lock()`
  also locks linked lockables by default.
- **BACUP compared (2026-10-19, AP-60):** the Map, Interiors and Bugs threads read its code against ours. It writes
  FO4's world as a new WRLD with no markers or locations, has no meshes, collision or doors, and nothing shows its
  output loaded in game. Worth borrowing as ideas only: zero an unbuilt door's transition cell, keep each cell's FO4
  lighting template, per-quadrant land-texture layering from VTXT/ATXT. Owner's call: reuse its GPL-3 code for those
  or write our own.
- **Script natives (job 34, verified):** of 229 FO4 script functions Starfield lacks, 36 are engine natives and 193
  are wrappers we port. Dismemberment is the biggest native use and needs SFSE to keep: new owner decision VM-40.
- **Voice reuse** is flagged as the owner's decision by engine-mechanics.md too (same decision as REL-26).

## Where the files disagree (to settle first)

The full list (16 conflicts, quoted from both sides) is in [dependencies.md](dependencies.md). The two that matter most:

- **SFSE for release 1.** tooling-and-testing recommends requiring CK and SFSE for release 1 (TT-39); people-and-story
  (PS-35), versions-and-maintenance (VM-17) and asset-pipeline (AP-45) recommend a data-only core with SFSE as optional
  add-ons. The owner already allowed SFSE; the open point is whether the *base* needs it. One decision closes all four.
- **Fallout 4 versions in release 1.** launcher.md D1 starts with 1.10.163 only; VM-01 and AP-52 accept 1.11.240 too.
  Both wait on the record diff between the two versions.
- **Interior plugin type.** VM-25 leans toward medium masters; interiors.md X2 keeps full masters.
- **Inside the phase files** (sent to their owners 2026-10-19): Int C5 versus Door E22 on `PlacedObject.Lock`; Door
  J40 versus its own lesson 9; NG-C2's "on leaving the Lodge"; Mechanics notes Tools 6.1, 6.2, 3.5 and UI 1.2.
  dependencies.md conflict 17.

## Owner decisions that unlock the most (one line each; full options in the files)

**Answered 2026-10-19:** the owner submitted the Questions page at 21:37Z. Answers, notes and the 25
talk-through-first items are recorded in [dependencies.md](dependencies.md#owner-decisions-by-phase) (last column, with what they change on the
critical path) and in each question's Status line. The table below is the pre-answer summary.

The authoritative list of all owner decisions (47, by phase) is in [dependencies.md](dependencies.md#owner-decisions-by-phase);
this table is the short version.

| # | decision | recommended default (to argue with) | IDs |
|---|---|---|---|
| 1 | Voice audio: convert the player's files, subtitles only, re-voice? And codsworth_voice.py? | subtitles only for NPCs until Bethesda answers in writing; keep the script as a private test, out of release packaging | REL-26, REL-27, MG-03, PS-32 |
| 2 | Contact Bethesda and Nexus before the Nexus release? | yes, written, specific questions, citing FNV to FO4 | REL-30, REL-31 |
| 3 | Data-only core with SFSE optional, or SFSE required? | data-only base, SFSE features as add-ons | VM-17, TT-04, PS-35, TT-39 |
| 4 | Which Fallout 4 versions the launcher accepts | 1.10.163 and current Steam 1.11.240 via data detection; CC files ignored | VM-01, VM-07, AP-52 |
| 5 | Starfield patch day | refuse on mismatch, "known good" table, previous build until we post support | VM-12, TT-01 |
| 6 | Host planet and layout | Earth via `EOVR` if the probe works, else a cloned planet; real coordinates | WP-01, WP-14 |
| 7 | The ship | fenced out for v1; scripted travel through one chokepoint | WP-27 |
| 8 | Player choice text | prompt plus full line | PS-01 |
| 9 | First public release | a walkable-world release before people and story | WP-38, REL-52 |
| 10 | Dates and money | no dates ("what works now"); no donations or crowdfunding | REL-47, REL-37 |
| 11 | Licence split | MIT repo, GPL-3 notice on Mutagen-linked binaries | REL-01 |
| 12 | Naming | a neutral name, no Vault Boy or Pip-Boy art | REL-25 |

## Cheapest experiments that close the most (a list; nothing runs now)

Offline first:
1. **Licence reading pass** (GPL FAQ, Wwise, SFSE, Bethesda EULA, Microsoft Services Agreement): narrows 11 REL questions.
2. **Planet census** of Starfield.esm, Shattered Space and SFBGS00x (PNDT, BIOM, overlay components): WP-05/09/10/24.
3. **Spriggit and Mutagen round trip** on our current ESMs: TT-15/16/17.
4. **Offline record scan of Fallout4.esm** for player-spoken lines, dialogue structure and karma-like data: PS-04/05/13/24/30.
5. **Asset census and convert-everything failure count**: AP-01/05/32.
6. **FO3/NV masters through Mutagen and xEdit** (is ObScript source text present?): MG multi-game spike.

Read-only PC probes (through the coordinator, when the PC is free):
7. **FO4 BA2 header bytes** of a current install: VM-02/03, AP-52.
8. **Timed FaceFX compile of 1,000 FO4 WAVs** with a resume test: PS-08 to PS-11, AP-41 to AP-43.
9. **One Debug-probe launch**: which `Debug` test functions work in retail: TT-25/26.
10. **One terrain-only island overlay through `EOVR`** with gravity, an ocean biome and a map marker: WP-08/17/23/26/28.
11. **Crash logger A/B** on the known Havok assert: TT-23.

## Next

Wave 3 (the dependency map) is done. Next: fold in the phase threads' next revisions and PC job 19 (LipGenerator usage),
settle `-MockWorldSpaceLOD` (sources conflict), and keep the critical path in dependencies.md current as questions close.
