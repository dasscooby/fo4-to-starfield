# Codex / Claude / Grok status

Owner: dasscooby. Goal: finish the verified interior slice before actor implementation.

## Goal and acceptance

Vault 111, Vault 81, Red Rocket cave, Vault 114, Prydwen, Hotel Rexford, Boston Public Library, Parsons: walkable floors/stairs, clear doorways, correct door swing/body ownership/frame collision, acceptable materials and recoverable deployment. Require in-game evidence tied to exact revision/artifact hashes. Unreadable results are inconclusive. Preserve Fallout 4 gameplay and Starfield native physics/modern capabilities. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

Next: [actor milestone proposal](ACTOR-MILESTONE.md), #31. Planning only until interiors pass; assignments not yet acknowledged.

## Owners / locks

- Claude: collision/Havok (`sfcollision`, `fo4collision`, `hkpackfile`, `hktagfile`, `meshcollision`), `convert_static.py`, `pipeline.py`, `scripts/convert_batch.py`, `dotnet/PluginSpike`, game scripts/staging/live control. Do not overwrite active edits.
- Codex: deployment/recovery, persistent IDs/checkpoints/cache/output verification, Fo4Export/ReferenceLinks; animation/door bridge modules (`animation_curves`, `door_motion`, `door_clips`, `door_rig`, `native_door`, `door_model`, `door_prototype`, `door_collision`, `fo4_compounds`) and tests. Owns this status/archive. Shared `sfnif.py`: announce exact function before edits.
- Grok: acceptance oracle and `route_eval.judge` plausibility. No other game scripts/collision/doors/live control without a new claim.

## Current evidence / remaining work

Claude-reported journal at56e3e37: every Vault114 door now passes after camera/console runner fixes; raised-door diagnosis withdrawn. Rexford:21 PASS/4 BLOCKED/1 UNREAD door walks,13 doors traversed from at least one side;8 stair passes. Vault81:2/3 stall doors pass;19DA36 remains unresolved. Vault114 stairs:6 pass,2 stuck; reruns and remaining cells still required. These are reported results, not independent Codex validation or full slice acceptance. One-sided traversal does not pass both-side acceptance.

Collision batch reported:3,012 native,243 source-none,199 box,36 surface boxes. Codex synthetic regression confirms source-none stays renderable without physics in both fallback modes; historical failures reproduced.

Door prototype:30 rigs/60 clips read back,42 selected source bodies/62 leaves; offline only, not installed, native moving linkage/activation still unverified. Collision ownership contract:14-byte target/flags/data/BodyID; shared systems select the body's node index, never every body per attachment.

Codex:10 checkpoint tests,24 deployment tests and guard pass. Resume reconstructs dependencies/hashes; malformed/degraded results rejected. Claude dependency: batch saves only ok results; failed reconversions skip invalidation. Deploy uses post-build plugin-list snapshot (reproduced lost entry added during archive build); checks hashes/fresh archives/BOM. Uninstall preserves modified hashed artifacts with retry manifest. No live install changed by Codex.

## Coordination / housekeeping

Check owner issues #29/#30, next-step #31 and shared updates [#32](https://github.com/dasscooby/fo4-to-starfield/issues/32) each work session. Publish concise evidence and blockers there; all three agents have posted. Keep this file under4KB; replace stale status. [History](handoff-archive/2026-10-07-codex-history.md).

Review then delete own scratch exports/recordings; never commit recordings. Keep current staging at C:\Modding\staging\multi. Pending Codex-owned cleanup: staging\codex-resume-smoke and research\codex-reflect; inspect before removal. Media audit unclaimed.
