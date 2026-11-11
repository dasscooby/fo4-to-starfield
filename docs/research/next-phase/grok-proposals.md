# Grok proposals for next phases (from #381 / research notes in this directory)

**Status:** proposal only. Not a decision. Written 2026-10-19 after reading the 11 notes + index.

## Claims that look wrong or weakly evidenced

Most notes correctly label **verified / supported hypothesis / unresolved**. Weak spots:

- launcher-architecture.md / launcher-gamma-model-and-community-tools.md: licence claims for third-party tools are "not checked". Full-game scale headless drive of the pipeline is untested.
- npcs-ai-factions-dialogue-quests.md: DLC record/voice counts unresolved; player-voice path is hypothesis.
- animations / voice notes: rely on supported hypotheses about formats; no measured conversion of an idle or dialogue line yet.
- testing-automation.md: crash-budget / dump-drive correctly flagged; full-game night run disk risk is real.
- Census numbers for Commonwealth are solid; DLC worldspaces, grass/tree families, full activator chains mostly unresolved. Object-LOD trial still in progress.

No outright contradictions observed. Main gaps: missing DLC measurements and untested full-scale assumptions.

## Proposed path across the next phase

**Phase 1 (measure + spine)** — goal: reliable offline census of records/meshes/materials/collision across base + DLC, plus a deterministic FormID allocator that survives reordered exports.  
Depends on: existing converters and leader-core ledger. Evidence: CI synthetic two-process harness + journal numbers.

**Phase 2 (launcher / leader-core live)** — goal: GAMMA-style launcher that runs the build graph on the player's PC, installs via profile or recorded restore, and can launch "Fallout mode".  
Depends on: Phase 1 census so disk/time estimates are real. Evidence: offline preflight + one restored Plugins.txt round-trip.

**Phase 3 (NPC / quest / dialogue at scale)** — goal: one full quest (e.g. expanded Codsworth slice) runs with its own faction, dialogue, and a minimal Papyrus shim.  
Depends on: Phase 2. Evidence: in-game route that completes the quest without console intervention.

**Phase 4 (animation / voice / UI isolation)** — goal: FO4-style Pip-Boy and a Fallout-only new-game start that does not expose Starfield UI.  
Depends on: Phase 3. Evidence: screenshot + journal of a new-game flow that never shows the Starfield menu.

Order is deliberate: measure first, then the spine, then content that depends on the spine. Leader core is the natural back-end for the launcher's build graph.

## Tasks I would take

- T1.1 census (BA2 summary sizes, largest-file CLI, object LOD probes) — fits existing Grok diagnostic work.
- Follow-on to #332 / object-LOD: diagnostic that walks a converted plugin and reports every FormID that still resolves to a Starfield base record.
- Offline material/texture census feeding the existing failure-summary in convert_batch.py.

I will not touch game input, deploys, or shared infrastructure.

## Biggest risks + cheapest test

1. Cross-machine FormID non-determinism. Cheapest: synthetic two-process allocator harness in CI.
2. Papyrus decompile + shim pass rate. Cheapest: decompile 10 most-referenced FO4 quest scripts and count clean compiles against a minimal shim.
3. Full-build disk/time on a player PC. Cheapest: measure current core64 staging size/wall-clock and multiply by census ratio.
4. Engine streaming / boundary limits. Cheapest: re-run existing core64 border probes after next content fill.

All stay offline or use existing test queues.

Ready to start T1.1 (census) on a follow-up draft PR if the owner agrees the order.
