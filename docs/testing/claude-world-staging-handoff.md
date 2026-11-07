# Claude PC: next world-staging actions

Owner-requested refinement of [#665](https://github.com/fo4sf/fo4-to-starfield/pull/665) and
[#667](https://github.com/fo4sf/fo4-to-starfield/pull/667), 1 November 2026 Mountain time.
Read the local environment handoff and live checkpoint first. In Windows PowerShell, locate it with
`Join-Path $env:USERPROFILE 'Desktop/codehell/ENVIRONMENT-HANDOFF.md'`. Use an isolated checkout of
`codex/multi-game-world-staging`; resolve the current reviewed commit from the PR rather than assuming this document's
presence means QA passed. Game/deployment remain with Claude and the owner; this handoff grants no live release.

## Current decisions and artifacts

| Item | Recorded state | What it does not mean |
|---|---|---|
| Era choices | Owner confirmed **2287 + later speculative**, selected at a new save; no separate 2281 preset | Exact later year or show-derived regional outcomes are not chosen |
| Later preset | Main-story campaigns off; suitable side missions retained after NPC/era/prerequisite review | Every old side mission works unchanged with future NPC/faction state |
| Own-planet candidate | Four plugins, existing route-B build/check passed; private stage is frozen | Installed, native passed, or Commonwealth migrated |
| Arrival coverage | Actual candidate lists LC172 + own planet | Full four-arrival ladder |
| Cross-game pilots | Seven bounded proposals, source paths/IDs still pending | Other games converted or staged |
| Recovery-source audit | Five recorded stage roots exist; port staging must be supplied separately | Complete restoreability, unchanged source bytes or permission to clean up |

Source references and per-game limits are in the [research note](../research/framework/multi-game-world-staging-nov01.md).
Use the [pilot matrix](multi-game-world-pilots.json), not an assumed whole-game build.

## Action cards

### A. Resolve the two control bindings (read only first)

**Question:** does the census lack a control because the source has no useful marker, because the source cell is
unnamed, or because discovery requires the wrong record relationship?

The private source audit distinguishes them:

- NewAtlantis has named exterior cells and COC marker references. Those markers are in the world's persistent CELL;
  `census.coc_cells` currently requires a marker's parent cell to be the named, gridded exterior CELL. It consequently
  returns no choices. The absence of a census choice is not absence of vanilla markers.
- LC172 shows the same persistent-parent pattern. The existing tool already carries its known destination separately.
- TempJemisonWorld has a COC marker but no named cells in this readout, so it has a separate entry-binding problem.

**Inputs:** private `vanilla-control-records.json`, current source master identity, the frozen candidate's census/plan,
and `src/fo4sf/planet/census.py` / `probe.world_items`. Exact record IDs and coordinate candidates stay in the private
checkpoint's audit folder. A geometric grid match is a candidate, not a verified console landing.

**Output:** a binding table with world/cell/reference identity, how the destination is entered, and evidence for the
expected world/frame. If the implementation is changed, use an isolated authorized source branch, synthetic persistent
marker/unnamed-cell cases and a fresh candidate; never edit the frozen kit. Bind both controls or report only the
existing two-arrival experiment with the others explicitly unrun. No guessed console command fills an empty row.

### B. Run the bounded own-planet test (only under an explicit live release)

Use a fresh game-closed recovery snapshot and a NEW operational copy of the candidate; recheck it against current Data.
Coordinate with the existing P9 session and its save/profile. Use the actual plan's arrivals and the existing
[planet card](../planet/planet-probe.md#6-stage-install-run-take-out), including its dwell/readings. Retain a fresh
session identity so no old log can qualify this run.

**Output:** every planned arrival and T1-T6/MERGE/LC172COC result, player world/planet/location chain, missing readings,
biome observations, and verified restoration. Use the [receipt template](world-pilot-receipt-template.json). Generic
stage/check/log exit codes do not settle native placement. No migration if a failure has merely been hidden by a mover.

### C. Choose one source-backed geography pilot

Obtain the actual owned source path, game update/language/master/archive identities and source world/map IDs.
Only Fallout 4 was found in the inspected Steam library; do not interpret this as an ownership check or search result
for every library. Select one of the seven proposals with the owner/lead; keep its released topology as the control.
Do not combine Strip, Freeside, McCarran, population and cut-content changes in the first candidate.

**Output:** source intake receipt, source-to-target transform/units, bounded footprint, missing dependencies and proposed
changes. Source intake/isolated offline work may proceed while native host questions are investigated separately.

### D. Prepare strip-down measurements independently

Reuse the [shell matrix](fallout-shell-matrix.json) and [baseline runbook](baseline.md). Compare startup/quest/map/error
readings before and after one reviewed restriction. Preserve masters, assets and service systems until their concrete
dependencies are understood. Keep one planet, one worldspace, one region and one active loaded area as different concepts.

**Output:** what was suppressed, what still runs, new errors relative to the baseline, and retained start/AI/door/save
checks. Use a disposable save. This is not a request for bulk quest stopping, deleting archives or opening all city barriers.

### E. Protect recovery sources before any cleanup or core replacement

Read the private `recovery-source-protection.json` and refresh its receipt hashes at the actual handoff. Current records
name stage roots for the experiment/core, bridge, combined probe, map markers and quest probe. All five existed at the
read-only observation. The port receipt stores no source staging directory **by design**: provide `--port-staging` and
validate it with the supported restore preflight rather than guessing its folder from a build name.
A follow-up lookup using the restore tool's supported layouts found the matching port stage under a nested `port/`
directory. The existing `port_restore.snapshot_spec/check_stage/check_core` preflight passed for all three recorded
source artifacts (plugin, main archive and texture archive), against the current receipt and observed core identity.
Receipt/core context stayed stable during that check. The exact root and hashes are in the private checkpoint's
`port-source-preflight.json`; source-stage binding is resolved for that observation. The earlier limited scan remains
preserved as an incomplete search, not evidence that the source was lost.

Revalidate this binding against fresh records before a swap. The check hashed the staged archives; it did not rehash
the installed archives, validate every other component's source tree or perform a restore. Its observed core hash is
not an independently approved compatibility pin. Source availability does not establish whole-setup recovery or
native acceptance.

**Output:** exact source root/pin for each installed component and its riders, refreshed port/source-drift
preflight and a restore dry run. The original protection inventory did not hash whole asset trees; the follow-up
hashed only the port source cohort named above.
It is not a restore target. Preserve installed assets, saves, queues, rollback/history, worktrees, frozen index sources
and unindexed recovery. An unreferenced directory is not a deletion candidate. No cleanup release is included here.

## Report and stop conditions

Each result separates source facts, proposed changes, offline checks and native observations. Cite the exact artifact
and attempt for every PASS/FAIL; `NOT_RUN`, `INCONCLUSIVE` and a staging HOLD remain distinct. On missing inputs,
unreadable receipts, changed pins, wrong world/frame or partial recovery, retain the evidence and report the specific
gap. Do not clear it by resetting IDs, reinstalling a different stage silently or reusing a prior run's verdict.
