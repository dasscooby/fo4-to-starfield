# Launcher architecture and the core-launcher plan under the own-ecosystem direction

Written 2026-10-19 06:30Z by the next-phase report thread (Claude-cloud). Research input for the group talk, not a decision.
Sources: /mnt/project-files/plans/core-launcher/core-launcher-plan-2026-10-17.md (the plan), PR #371
docs/spikes/E-own-ecosystem.md (spike E), main 4492d13 `src/fo4sf/core/` (controller, state, preflight, tasks, worker, adapters).
Labels: verified = read in the repo or a file named here; supported hypothesis; unresolved.

## 1. What changes with the direction

The plan (Oct 17) scoped launcher v0 as install, verify, launch and restore of *the current test build*. The direction
(user, Oct 19 03:30Z) makes the launcher the thing that *builds the whole game on the player's PC* from their Fallout 4 and
all six DLC, then starts it as a Fallout game with as little Starfield in play as possible. So the launcher moves from a
deployment helper to the centre of the product. Everything below follows from that.

## 2. Proposed architecture (stages, each resumable and recorded)

| Stage | Does | Reuses (verified on main unless noted) | New |
|---|---|---|---|
| detect | find FO4, check its version and all 6 DLC (Automatron, Wasteland Workshop, Far Harbor, Contraptions, Vault-Tec, Nuka-World); find Starfield and its version; measure free disk | game-version pin (#193), preflight's game reading (`core/preflight.py`) | FO4/DLC detection and a disk estimate before anything is written |
| build | run the converters (records, meshes, terrain, collision, navmesh, textures, audio, later NPCs, quests, scripts, UI) into a launcher-owned work folder | `pipeline.py`, `convert_batch.py`, checkpoints (`checkpoints.py`), the dotnet record writers | one build graph with a cache keyed by input hash + converter version, so a converter fix rebuilds only what it touches (topic rule "rebuild only the affected") |
| verify (offline) | masters, FormID stability, hashes against the build manifest | preflight's master and load-order checks | determinism check (plan L4) becomes a gate, not a side task |
| install | put the built set in front of Starfield without touching the player's normal setup | `deploy_starfield.py`, `exp_install.py` (one experiment at a time today) | a profile layer (see section 3) |
| launch | start Starfield (optionally via SFSE) in "Fallout mode": new game in Vault 111, Starfield start quests held off | runner/launch scripts on the PC | the start mode is spike E task E6 |
| verify (after load) | plugins active after load, load order, game version | `core/preflight.py` (#182) | none; already the leader core's gate |
| restore | return Plugins.txt, INIs and Data to the recorded state | ledger (`core/state.py`, #136) | byte-identical restore test (plan L3) |

The leader core is the launcher's back end: its ledger is the record of what is built and installed, its preflight is the
after-load check, its task/worker model runs the build stages. So "leader core live on the PC" and "the launcher" are one
track, not two competing candidates (supported hypothesis; it holds if the launcher is written on `core/`).

## 3. How GAMMA does it, and what we can copy (from general knowledge; the community thread's file should confirm)

- GAMMA ships an installer plus a list of mods and patches; content is downloaded and assembled on the player's PC, and
  everything runs through a portable Mod Organizer 2 instance whose virtual file system keeps the base game folder clean.
- For us: no downloads of game content at all; the "mod list" is our converter steps run against the player's own FO4.
- A virtual file system profile (MO2's) is the cleanest way to keep the player's Starfield untouched. Whether MO2 handles
  Starfield well enough for a set this size is unresolved; the fallback is our own recorded install plus restore (exists).

## 4. Changes to the core-launcher plan

| Plan item | Was | Becomes |
|---|---|---|
| L1 design note | install, profile, verify, launch, restore of the current build | adds detect and build; the build graph and its cache are the core of the note |
| L2 mod manifest | needed early for mod authors | later: first the game must build; the manifest targets our core master once it exists |
| L3 command | install, verify, launch, restore, status | adds `detect` and `build` (and `launch --mode fallout` once E6 works) |
| L4 determinism | side check | moves first: if two PCs get different FormIDs, nothing built on the core (saves, mods, bug reports) is portable |
| L5 owner trial | install today's build, launch, restore | same, then a second trial: full build from FO4 + DLC on the PC |
| Dates (Oct 20 to 25) | | stale; they assumed the play-test phase ended Oct 20. Re-date after the talk |
| Phase C "mode" question | open | partly answered: the Fallout-only start becomes the main build, not a mode of something else |

## 5. Hard limits that do not change

- Creation Engine 2 is closed, so Starfield.esm stays loaded (our plugins master it). "Away from Starfield" means
  overrides and a start option, never deleting or patching the game (plan section 2, spike E section 1).
- No assets shipped: code, scripts and docs only. Mods on the core reference converted records by FormID.
- No executable changes; SFSE only where measured behaviour needs it.
- A launcher does not lift engine limits (streaming, cell grid, loading screens).

## 6. Unresolved, and what would answer it

- Full-game build size and time on the PC: unknown. D: is nearly full now. Answer: measure one full core conversion's
  output size (v5's terrain_core64c_work_v5 folder) and scale by cell count; a read-only PC job.
- Determinism across two machines: never tested (plan L4). Answer: the synthetic half can run in the cloud now.
- Whether a profile/VFS layer works with Starfield at this size: unresolved.
- Papyrus route (decompile, shim, recompile with the player's Creation Kit): pass rate unknown (spike E task E2).
  The Creation Kit becomes a hard requirement for players if this route holds; that is a launcher prerequisite to detect.

## 7. Questions for the talk

1. Is the launcher the next phase's spine, with the leader core as its back end (one track)?
2. Does the determinism check move to the front?
3. Is the Creation Kit an acceptable player requirement (for script recompiling)?
4. MO2-style profile, or our own install and restore?
