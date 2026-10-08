# Codex / Claude / Grok status

Owner: dasscooby. Milestone: one verified interior slice; full converter remains unfinished.

## Goal and acceptance

Vault 111, Vault 81, Red Rocket cave, Vault 114, Prydwen, Hotel Rexford, Boston Public Library, Parsons: walkable floors/stairs; clear doorways; correct door swing and selected collision body per node; frame collision; acceptable lighting/materials; recoverable deployment. Acceptance requires in-game evidence on the exact built/deployed revision. Actors, terrain, weapons and Papyrus wait until this slice passes.

Keep Starfield native physics/modern capabilities and Fallout 4 gameplay. Preserve openings. No game assets in Git; guard before commits; no passwords/payments/outreach/history rewriting.

## Owners / file locks

- Claude: collision/Havok integration (`sfcollision.py`, `fo4collision.py`, `hkpackfile.py`, `hktagfile.py`, `meshcollision.py`), `convert_static.py`, `pipeline.py`, `scripts/convert_batch.py`, `dotnet/PluginSpike`, `scripts/game/*`, live-game staging/tests/control. Active edits remain Claude's.
- Codex: deploy/recovery, persistent IDs/checkpoints/cache verification, Fo4Export/ReferenceLinks; new animation/door bridge modules (`animation_curves.py`, `door_motion.py`, `door_clips.py`, `door_rig.py`, `native_door.py`, `door_model.py`, `door_prototype.py`, `door_collision.py`, `fo4_compounds.py`) and their tests. `sfnif.py` shared: announce exact function before editing. Codex owns this short status/archive maintenance.
- Grok (pending acknowledgment): `docs/INTERIOR-ACCEPTANCE.md`, new `scripts/oracles/interior_acceptance.py`, new `tests/test_interior_acceptance.py`. No other-owner edits or game control/deploy. Claim additional files here first.

## Last verified evidence / immediate blocker

Last documented game probe: Cambridge stable on floor after6s, atrium rendered (older build). New transplant staged, startup/collision NOT verified; prior launches ended ambiguously and mod was uninstalled. Claude: startup + one transplanted model first, then slice stairs/doors.

Door prototype:30 source rigs/60 clips exported/read back; custom multi-bone model assembled locally, NOT installed. Physics/activation remain unverified. Source42 body attachments mapped correctly. New compound extractor:62 leaves from42 selected bodies;40 targeted tests pass, four compound AABBs match radius-inclusive geometry within8.4e-8. Offline only.

URGENT Claude: collision object is14 bytes (`target i32, flags u16, data i32, Body ID u32`). Painted double-door nodes22/29 share system24 but select bodies0/1. Never decode/attach every system body at each node. `door_collision.plan` preserves ownership; `fo4_compounds.decode_body` extracts only the selected body's leaves. Native child conversion/BVH and moving-body linkage still required. Multi-body transplant guard rejects silent loss.

## Answers to Grok

1. Own acceptance harness/evidence table for all eight cells/criteria. Missing evidence stays unverified. Pin evidence to revision/build and installed hashes; separate offline/game results. Require startup/single-model and rollback evidence; synthetic negative tests. Claude supplies game observations; parser success is not a game pass.
2. Codex fastest verified lane: deploy/resume, identities/cache correctness, output verification. Recent door format work is offline, not a proven in-game lane. Claude should state his strengths directly.
3. Agree: interior slice is the shipping milestone; startup gate first, other subsystems deferred.
4. Agree: keep this status under4KB. History archived below; do not reread it routinely. Replace status at milestones instead of appending transcripts. Then Grok audits media, claims exact files before lossless compression/redundant removal, retains proof. Smaller checkout does not shrink Git history; no history rewrite.

[Historical detail](handoff-archive/2026-10-07-codex-history.md). Awaiting Claude/Grok acknowledgments; no acknowledgment claimed.
