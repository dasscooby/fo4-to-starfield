# Next-phase research (2026-10-19 overnight)

Research inputs for the owner's next-phase discussion, written by the Claude-cloud project threads on the night of
2026-10-18/19. **Nothing here is decided.** The owner's direction (2026-10-19 03:30Z): breadth before polish;
Fallout 4's animations, NPCs, quests, game and UI running as their own ecosystem, as far from Starfield as possible,
through a GAMMA-style launcher that ships no assets and builds everything on the player's PC from their own Fallout 4
and all six DLC. Other candidates: the leader core live on the PC, and the core-launcher plan.

Labels follow docs/ai/research-log.md (verified, supported hypothesis, unresolved). Copies of the project's working
files; the threads may revise them during the night.

| File | Area |
|---|---|
| launcher-architecture.md | launcher stages, leader core as its back end, changes to the Oct 17 core-launcher plan |
| launcher-gamma-model-and-community-tools.md | GAMMA, Wabbajack, TTW precedents; hosting and licence norms; tools to reuse |
| animations-ui-and-start.md | animation conversion, Pip-Boy and menus, a Fallout-only new game |
| npcs-ai-factions-dialogue-quests.md | NPC, package, faction, dialogue, quest and Papyrus conversion at scale |
| voice-lipsync-companions.md | voice pipeline, lip sync, companions |
| doors-activators-workshops.md | doors, locks, elevators, workshops and settlements |
| world-maps-lod-fasttravel.md | world extent, DLC worldspaces, maps, LOD, fast travel |
| trees-grass-terrain.md | land textures, grass, trees, DLC terrain |
| physics-conversion.md | movable props, constraints, ragdolls, weapons |
| lighting.md | interior and exterior lighting breadth |
| testing-automation.md | testing at full-game scale, turning the leader core on |

Grok: see #381. Codex: see #382.

## Review qualifications (Codex, review 5569026425 on #380, delta at fccb6e7)

Read these notes with Codex's three limits until their authors revise them:
- world-maps-lod-fasttravel.md: "already refuted in game" for the OFST/CLSZ fix rests on a NOLOAD result, which does not by itself isolate an unmerged position; fix A's unmerged reading and fix E's NOLOAD are separate results, and two failed candidates do not rule out every writer-side fix.
- testing-automation.md: Steam error 84 plus the crash-budget stop show a failed launch and a bounded stop, not that elevation is the cause or the fix. The elevated launch stays a proposal for the owner.
- trees-grass-terrain.md: the Part B biome and ground-cover counts come from a private PC job not re-run here; its producer has two known issues in #379 that may or may not affect it. Record wiring proves neither rendering nor the BIOM test.
