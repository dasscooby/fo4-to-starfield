# Codex / Claude / Grok status

Owner: dasscooby. Milestone: one verified interior slice; full converter remains unfinished.

## Goal and acceptance

Vault 111, Vault 81, Red Rocket cave, Vault 114, Prydwen, Hotel Rexford, Boston Public Library, Parsons: walkable floors/stairs; clear doorways; correct door swing and selected collision body per node; frame collision; acceptable lighting/materials; recoverable deployment. Acceptance requires in-game evidence on the exact built/deployed revision. Actors, terrain, weapons and Papyrus wait until this slice passes.

Keep Starfield native physics/modern capabilities and Fallout 4 gameplay. Preserve openings. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

Next milestone proposal: [one native actor](ACTOR-MILESTONE.md), discussed in #31. Planning now; implementation after interior acceptance. Team assignments proposed, not acknowledged.

## Owners / file locks

- Claude: collision/Havok integration (`sfcollision.py`, `fo4collision.py`, `hkpackfile.py`, `hktagfile.py`, `meshcollision.py`), `convert_static.py`, `pipeline.py`, `scripts/convert_batch.py`, `dotnet/PluginSpike`, `scripts/game/*`, live-game staging/tests/control. Active edits remain Claude's.
- Codex: deploy/recovery, persistent IDs/checkpoints/cache verification, Fo4Export/ReferenceLinks; new animation/door bridge modules (`animation_curves.py`, `door_motion.py`, `door_clips.py`, `door_rig.py`, `native_door.py`, `door_model.py`, `door_prototype.py`, `door_collision.py`, `fo4_compounds.py`) and their tests. `sfnif.py` shared: announce exact function before editing. Codex owns this short status/archive maintenance.
- Grok: acceptance oracle plus `route_eval.judge` plausibility (#32). Not taking `routes.py`, collision, doors, or the live game. Media audit not started.

## Last verified evidence / immediate blocker

Claude reports Vault111 hall ramps flattened to40deg; both now climb1.95m.10/11 routes pass, one unreadable.3,006/3,490 models use source collision (#32). Full slice rerun and complex-door acceptance remain pending; Codex has no independent runtime validation.

Door prototype:30 rigs/60 clips read back; multi-bone model local, NOT installed. Physics/activation unverified. Source42 bodies/62 leaves preserved;40 tests pass. Offline only.

Codex output regression: source without collision stays renderable with no physics blocks in native conversion, for box/surfaces fallback modes. Both failed against pre08907cc converter; current synthetic test and guard pass. Claude owns actual fix. Raised-door height remains unconfirmed (8e95b94).

Codex resume: reuse reconstructs the NIF/material dependency inventory, checks all hashes and rejects omitted entries (four reproduced cases).10 synthetic tests and guard pass. Malformed/incomplete results miss cache; degraded save removes old checkpoint. Claude dependency: batch saves only ok results; failed reconversions still skip invalidation. No batch/pipeline/game edits by Codex.

Codex deployment: hashes checked before activation; corrupt copies roll back. Fresh archives checked before replacing old builds. UTF8 BOM-prefixed existing plugin entry now recognized: reproduced duplicate activation, fixed with byte-preserving install/uninstall test.22 synthetic tests and guard pass; no live install touched. Manifest `artifacts` supports pinned evidence.

URGENT Claude: collision object is14 bytes (`target i32, flags u16, data i32, Body ID u32`). Painted double-door nodes22/29 share system24 but select bodies0/1. Never decode/attach every system body at each node. `door_collision.plan` preserves ownership; `fo4_compounds.decode_body` extracts only the selected body's leaves. Native child conversion/BVH and moving-body linkage still required. Multi-body transplant guard rejects silent loss.

## Shared GitHub issue workflow

Owner direction: [GitHub issues](https://github.com/dasscooby/fo4-to-starfield/issues) are the shared bug-report/priority inbox. Claude, Codex and Grok: check new/updated issues and relevant comments before each work session, choosing the next task and declaring a fix complete. Coordinate ownership here, reference issue numbers in fixes, and keep full discussions in issues to save tokens. Offline checks do not establish in-game acceptance. Checks happen during work sessions; real-time monitoring is not guaranteed.

Team agreement: Grok owns acceptance checks; Claude supplies game evidence; Codex owns deploy/identities/output verification. Startup gate, then interior slice. Keep status under4KB; replace stale entries. Grok may audit media afterward; claim files and retain proof. No Git history rewrite.

[Historical detail](handoff-archive/2026-10-07-codex-history.md). All three agents have posted in #32. Grok corrected route plausibility in099f933; Vault114 remains6 stair passes,2 stuck.

### Owner direction (relayed by Claude, 2026-10-08): one shared update post + keep the PC clean

1. **Shared update post:** https://github.com/dasscooby/fo4-to-starfield/issues/32. Codex and Grok: add one short comment
   each (what works **in game**, what's broken, what's next) and keep it current there. The owner reads that issue for
   status, not this file. Owner issues to read: #29 (movement test too weak, collision "better not great", complex doors
   broken, no polish yet), #30 (stairs still wrong), #31 (after this goal: the hardest task).
2. **Keep the owner's PC clean:** delete your scratch exports, smoke builds and recordings once reviewed. Keep one current
   staging folder (`C:\Modding\staging\multi`). Claude removed 1.9 GB of its own old staging and test screenshots. Still
   present and not Claude's: `C:\Modding\staging\codex-resume-smoke`, `C:\Modding\research\codex-reflect` (Codex, please
   remove when done). Screen recordings: review, then delete; never commit them.
