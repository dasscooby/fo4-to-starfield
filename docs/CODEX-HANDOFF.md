# Codex / Claude / Grok status

## Current handoff, 6 November 2026

The project is a Commonwealth-first Fallout experience and total-conversion framework on Starfield, with the
GAMMA-style living world as the broader goal. Start with the current [roadmap](ROADMAP.md), changed
[#32 claims](https://github.com/fo4sf/fo4-to-starfield/issues/32) and the assigned PR's head, replies and reviews.
The older snapshot below is historical evidence, not a current task queue or permission grant. Main is `66783a99`
(6 Nov); the merge queue it closed is listed in the roadmap's 6 November update.

| Work | Current handoff |
|---|---|
| P9 and P9u | Claude PC owns implementation and native tests. The 2 Nov runs are in [#644](https://github.com/fo4sf/fo4-to-starfield/issues/644). The judges [#663](https://github.com/fo4sf/fo4-to-starfield/pull/663) and [#669](https://github.com/fo4sf/fo4-to-starfield/pull/669) are merged with their findings corrected. Open: the #663 near-sample excuse, #661's Success between samples and #673's hour cap |
| Far travel | [#674](https://github.com/fo4sf/fo4-to-starfield/pull/674) is merged as offline design with no production caller. Next: the P11 probe card (materialize inside 400 m, dissolve beyond 500 m); native P11 belongs to Claude PC |
| Mission | [#648](https://github.com/fo4sf/fo4-to-starfield/pull/648) is merged offline. Its in-game check (`found preston`, `startcombat`, stages 20/30/40/200) needs a Claude PC release |
| Launcher | #647, #657 and [#668](https://github.com/fo4sf/fo4-to-starfield/pull/668) are merged; the older drafts #634, #636 and #660 remain open. Do not infer code absence from a PR state or close one automatically |
| Combined core | C1 to C5 and the MSVC build script #656 are merged. MSVC parity passed on C5 source `0ba91c20` (#656); the later #641/#673 rule commits have Linux CI parity only, so an MSVC rerun at main is the next Windows gate. Then port steps 4 to 7. [Persistence audit](https://github.com/fo4sf/fo4-to-starfield/pull/654#issuecomment-6572101888): 48 offline checks, not live creature identity or death processing |
| World preparation | [#665](https://github.com/fo4sf/fo4-to-starfield/pull/665) is merged; [#667](https://github.com/fo4sf/fo4-to-starfield/pull/667) is a draft that needs retargeting to main before independent review. No game/deployment action follows from them |
| Earlier shared scope | The #280 function and stage-command ownership approvals were resolved and implemented through #378/#410. Do not revive the old permission blocker; check actual integration and recovery evidence before new work |

Claude retains lead integration, live game/controller, deployment, pipeline, terrain/collision/actors and
runner/staging. An absent process is not a control release. Codex owns deployment/recovery, persistent identities,
cache/output verification, ReferenceLinks and the door bridge; shared changes need exact coordination. Agents on
the owner's Windows PC must also read its local environment handoff and live checkpoint.

When addressing another agent, name its actual environment, branch/head, working directory, tools or shell,
authorized action, checks and expected result. Use separate worktrees and preserve concurrent edits. No self-merge,
force-push, rebase, game/deployment action or restart of paused work is granted by this handoff. Keep STOP, Guardian,
owner-idle, recovery and frozen evidence intact. Keep assets, saves, settings and private operational evidence out
of Git. Formal reviews under the shared account use COMMENT and a role prefix.

## Historical snapshot, 16 to 17 October 2026

The text below retains its original status and cadence. Later results and owner instructions supersede it; in
particular, its old pending scopes and automation state must not be applied as current instructions.

Codex checkpoint, October16 Mountain /17 UTC. Goal: playable FO4 with preserved identities/state and native Starfield physics. Persistent doors first. Read current [#32 claims](https://github.com/fo4sf/fo4-to-starfield/issues/32) first.

## Owners / locks

- Claude: integration, live game/controller, terrain/collision/actors, pipeline, runner and staging. No other launch, close, install or input without explicit release. No Codex watchdog restart.
- Codex: deployment/recovery, identities/cache/output QA, Fo4Export/ReferenceLinks, door bridge and independent evidence. Agree shared producer/caller scope before edits; use an isolated owned tree.
- Grok: materials/textures, FLOR research, then fast travel/map markers per #32; coordinate acceptance/diagnostics. Claude runs native tests.
- Claude-cloud: offline leader-core/model work; PC Claude retains live control. Do not wake paused work.

## Latest reviewed door evidence

- Probes(c)/(d): persistent anchor resolves but MoveTo lands unshifted and falls, including with requested offset. Temporary targets do not resolve in those attempts. Later boundary jumps and self-calibrated heights prove neither map limits nor correct arrival. [Pinned evidence](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229374094).
- Probe(e) completed: helper teleports reached12 cells matched to core64k; endpoint02000DAF/grid(-10,11), XY error0.057m, height+5.227m (FAIL HEIGHTS). Screenshots do not establish correct Red Rocket scenery. No door/round-trip acceptance. Runner8f55bfd/coree34dafe2/portd2b2af17; exact installed BA2 receipt missing. [Preserved result](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229854224).
- SDM forward5cfb682e: console activation followed by12 stable readings in04006C46 at(5.449,17.291,-3.637), heading270, and visible interior. Later terrain-beyond teleport uses exterior coordinates inside that room and causes a fall. Separate harness defect from arrival. [Evidence](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6229965617).
- SDM return completed: exterior target685821 resolves none; activation is refused, then13 stable readings remain in04006C46/world none. Generic height PASS is not a round-trip pass; the separate EXPECTED-REFUSED result agrees. Controller closed its owned game/uninstalled normally. Both attempts are privately preserved; walking/return/save-reload remain gates. Claude owns persistent exterior markers and candidate PR291 integration after peer QA. [Independent result](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6230125731).
- SDM judge8d9e43c3 accepted five bad synthetic arrival/selection/activation controls. Fix and independently review before acceptance; retain original verdicts. See #32 comment6229054238.

## Source work / next gates

- Codex PR277 main merge preserves pinned door-stage sources: selected existing VMAD is refused before output, generated files are independent/atomic, nested output rejected. Retains main persistent-return coordinate reporting. Offline preservation/return checks required; no staging/install/native acceptance.
- Codex activation-parent export: shared Fo4Export/Fo4Land serializer retains ordered parent FormKeys, raw flags and delays, including deferred actors. Claude reviewed the export. Requested follow-up now makes untranslated blocks counted/listed warnings by default, with partial fidelity and optional `--strict-activation-parents` gating; other link errors still block. Eight synthetic CLI controls cover publication/report/strict/override and missing-parent behavior. Grok delta QA passed at e79da3e; main-merge changes only documentation conflicts, source continuity checked. No native activation behavior or live changes. See PR305 and CELL-EXPORT.md.
- Codex PR176 full-source promoted-name identity merges main697bc07; CONT/MISC identity repair retained and current main callers reconciled. 91 Python cases covered (89 initial passes, two stale alias expectations corrected/retested) and eight actual writer tests pass; independent merge-delta QA pending; no stage or allocation migration. Previously aliased mixed-plugin builds still require separately pinned regeneration, not silent save compatibility claims.

- Codex light-patch bounds PR315: Claude independently reviewed the source and found no blocking implementation defect. Added the requested second-input-only malformed-LIGH test: both negative cases fail if B validation is removed; 31 focused light/FO4-light checks pass. Earlier selected baseline run had five failed assertions across three methods. Source-only, final test-delta review pending; no brightness-policy/stage/game changes.

- Draft PR2919ffce95: Claude reviewed13062b6 with no blocking script defect. Logging delta sends requested XYZ to normal trace without the bridge quest;16 focused checks/CK compile/assembly/guard/CI pass, delta QA pending. Writer must emit UseDestinationPosition=True plus three floats and update its strict VMAD reader. MoveTo is void; far-placement/boundary, native activation/return/save gates remain. Undeployed. Each private PEX hash pins an artifact, not byte-reproducible compilation.
- #280 / PR281f6d15bf: fixes Claude's Windows sharing/stale-state P2s;30 focused tests/guard/CI pass. Independent delta QA pending. Production callers remain unintegrated; require shared reservations/hash, retained IDs, base-growth/HEDR checks and paired recovery. Full-store rollback still needs an external latest-state pin.
- PR293 is merged at37f2820 after Claude delta QA5556622216. Follow-up on codex/rollback-completion-receipt addresses its retry P2: successful history-outage rollback checkpoints the exact original receipt bytes and completed outcome; retry archives/retires metadata without touching later file/config edits. Incomplete rollback retains guarded cleanup. The active check now refuses pending recovery even if a plugin is reactivated.81 targeted tests/guard pass; independent QA/CI pending, source-only. No existing live receipt is upgraded or reconstructed.
- PR276529a36f and PR2770c5d397 remain awaiting QA/integration. PR2793fab4b8 combines persistent IDs with reviewed writer3446a99 and merged arrival script9ffce95;30 distinct targeted checks, exact synthetic bootstrap parity and CI39010241871 pass. Combined peer QA, a fresh full-size migration and native return/save remain gates. PR278 regressions are merged.
- Grok review gates: PR288a77edfa lacks actual donor metalness override; Claude also reproduced unwanted opacity from two-sided-only materials and a broken dry-converter keyword call. PR289d7b8188 ignores palette-enable/missing palette. PR29689cc91d writes LCSR tail0 instead of templateFFFFFFFF (three actual-writer cases). Fixes pending; PR284/285 reviews remain scoped.
- PR290454856e offline QA: seven focused tests and native-template writer controls pass; promotion keeps reference IDs and writes default/custom PFIG correctly. Contrary to its docs, the Ingredient setter works. Invalid harvest target refused before output. Native harvest/visual/reset remains untested; see the pinned PR review.
- Future streaming/launcher plan: [#286](https://github.com/fo4sf/fo4-to-starfield/issues/286). Existing6.4km coverage/short walks do not prove whole-map travel. Keep persistent doors first; launcher alone cannot remove engine limits.

## Preservation / cadence

Failed/passing capsules are reopened/source-verified on a second local volume, not offsite. Claude owns cleanup/free-space receipts; Codex deleted nothing. Preserve STOP, Guardian, owner-idle, recovery and saves; no assets/private settings in Git. See testing/progress-storage.md.

Low usage: quiet four-hour Codex follow-up active; scoped monitors paused. Read changed evidence, avoid unchanged retests, guard before commits. History: #32, PRs and Git.
