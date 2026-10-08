# Codex / Claude / Grok status

Owner: dasscooby. Milestone: one verified interior slice; full converter remains unfinished.

## Goal and acceptance

Vault 111, Vault 81, Red Rocket cave, Vault 114, Prydwen, Hotel Rexford, Boston Public Library, Parsons: walkable floors/stairs; clear doorways; correct door swing and selected collision body per node; frame collision; acceptable lighting/materials; recoverable deployment. Acceptance requires in-game evidence on the exact built/deployed revision. Actors, terrain, weapons and Papyrus wait until this slice passes.

Keep Starfield native physics/modern capabilities and Fallout 4 gameplay. Preserve openings. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

## Owners / file locks

- Claude: collision/Havok integration (`sfcollision.py`, `fo4collision.py`, `hkpackfile.py`, `hktagfile.py`, `meshcollision.py`), `convert_static.py`, `pipeline.py`, `scripts/convert_batch.py`, `dotnet/PluginSpike`, `scripts/game/*`, live-game staging/tests/control. Active edits remain Claude's.
- Codex: deploy/recovery, persistent IDs/checkpoints/cache verification, Fo4Export/ReferenceLinks; new animation/door bridge modules (`animation_curves.py`, `door_motion.py`, `door_clips.py`, `door_rig.py`, `native_door.py`, `door_model.py`, `door_prototype.py`, `door_collision.py`, `fo4_compounds.py`) and their tests. `sfnif.py` shared: announce exact function before editing. Codex owns this short status/archive maintenance.
- Grok: acceptance oracle. #29 adds `walk_route.py`, `walk.ps1`, `test_walk_route.py`, one game README row. Not taking other game scripts, collision, doors, or the live game. #30 stays Claude. Media audit not started.

## Last verified evidence / immediate blocker

Last documented game probe: Cambridge stable on floor after6s, atrium rendered (older build). New transplant staged, startup/collision NOT verified; prior launches ended ambiguously and mod was uninstalled. Claude: startup + one transplanted model first, then slice stairs/doors.

Door prototype:30 source rigs/60 clips exported/read back; custom multi-bone model assembled locally, NOT installed. Physics/activation remain unverified. Source42 body attachments mapped correctly. New compound extractor:62 leaves from42 selected bodies;40 targeted tests pass, four compound AABBs match radius-inclusive geometry within8.4e-8. Offline only.

URGENT Claude: collision object is14 bytes (`target i32, flags u16, data i32, Body ID u32`). Painted double-door nodes22/29 share system24 but select bodies0/1. Never decode/attach every system body at each node. `door_collision.plan` preserves ownership; `fo4_compounds.decode_body` extracts only the selected body's leaves. Native child conversion/BVH and moving-body linkage still required. Multi-body transplant guard rejects silent loss.

## Shared GitHub issue workflow

Owner direction: [GitHub issues](https://github.com/dasscooby/fo4-to-starfield/issues) are the shared bug-report/priority inbox. Claude, Codex and Grok: check new/updated issues and relevant comments before each work session, choosing the next task and declaring a fix complete. Coordinate ownership here, reference issue numbers in fixes, and keep full discussions in issues to save tokens. Offline checks do not establish in-game acceptance. Checks happen during work sessions; real-time monitoring is not guaranteed.

Team agreement: Grok owns acceptance/evidence checks; Claude supplies game observations. Codex's fastest verified lane is deploy/resume, identities/cache and output verification. Interior slice first, startup gate first. Keep status under4KB; replace stale status instead of appending transcripts. Grok can audit media after acceptance work, claim exact files before compression/removal, retain proof. Smaller checkout does not shrink Git history; no history rewrite.

[Historical detail](handoff-archive/2026-10-07-codex-history.md). Grok acknowledged the slice and the file lock above. Awaiting Claude.
