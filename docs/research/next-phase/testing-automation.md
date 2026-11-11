# Next phase: testing and automation at full-game scale, and the leader core live

Bridge thread (Claude-cloud), 2026-10-19. This is research from the cloud: offline reading of `main` at 4492d13 plus what the PC
reported on Oct 18 and 19. No game run backs it.

Labels used below:
- **verified**: checked in code or in PC results, with the source named.
- **supported**: inferred from evidence.
- **proposal**: an idea, not yet built or tested.

## 1. Where testing stands (verified)

- **One runner drives every game test.** That is `scripts/game/testqueue.py`.
  - Its planners: `plan` (cell kinds), `plan-terrain`, `plan-npc`, `plan-door`, `plan-movable` and `plan-walk`.
  - On top of those sit generators that read the installed build and write the plans: `door_rounds.py` (#358) and
    `presence.py` (#358).
  - Every result is PASS, FAIL or INCONCLUSIVE. A PASS needs proof from the test's own attempt: GetIsID on the
    selection, an ack, and reads from the bridge log after the ack. Missing proof is never a PASS.
- **What has passed in game:** the SDM door both ways, the library door, Vault 95 and Fort Hagen 2 exits, most indoor
  pickups, 19 of 20 stair flights, and the Red Rocket to Sanctuary walk (results-2026-10-17.md).
- **Hand-planned queues break on every rebuild.** v5's 47 new FLOR bases shifted every appended core id, and the old
  SDM queue then pointed at other records. Plans generated from the installed plugins avoid this: door_rounds checks
  each door against the installed esm before planning it.
- **Crashes are not circuit-broken.** `NO_BREAKER = ("CRASH", "NOCELL", "NIGHT")` (testqueue.py:131). Only
  `--max-relaunch` (default 3, and the first launch counts) caps a repeatable crash. Each crash currently writes an
  18 GB full dump to D:, which had about 53 GB free on Oct 19. Three crashes would nearly fill the disk.
- **The launch is flaky.** A steam:// launch exited after about 2 s twice on Oct 18, once from the runner and once for
  the user. The runner now retries up to 3 times, going through all its checks each time (#358). The cause is
  unresolved. Supported hypothesis: Steam isn't elevated, and the user runs the game as admin (error 84 otherwise).
  **Verified 2026-10-19 07:46Z:** the night run's steam:// launch failed with Steam's dialog "Starfield failed to start
  (error code 84)" (D:\Modding\testqueue_v6c_out\doors_out\cycle.png). #377's `--crash-budget 1` stopped the run after
  that one dead start, as designed, so nothing was tested. Unattended runs need the elevated launch in 2.4.
- **The leader core exists but is switched off.** `src/fo4sf/core/` has the ledger model, the controller lease,
  preflight, the importer and the report. The runner uses the lease and preflight only with `--lease-dir` /
  `FO4SF_LEASE_DIR` (testqueue.py:59, 2443). Today's runs write `results.jsonl` per queue, not one ledger.

## 2. What full-game scale needs

Breadth before polish means the test count grows from tens to thousands: every converted cell, door, actor, map
marker and quest. Four things have to change.

### 2.1 Generate every plan from the build (proposal, partly built)

One planner, `inventory`, reads the build's own outputs and writes one queue per tier (2.2):
- the installed esm files;
- formids.json, objects.json and plan.json.

It re-plans automatically after each build and records the build's hashes, so a queue can never outlive the ids it
names. The door and presence generators are the pattern to follow:
- everything is checked against the installed plugins;
- every skipped item gets a reason;
- load indices come from `order`.

Classes to cover, each with its proof:

| Class | Test | Proof |
|---|---|---|
| Interior cell | coc, settle, read the position | loaded, in the cell, the player didn't fall |
| Exterior cell, per 3x3 block | hop on a grid, read the position | loaded, on the ground (zref), no NOCELL |
| Load door | round trip (door_rounds) | within 3 m of the marker on both sides |
| Actor or marker | presence | resolves at the planned index, not disabled, near its record position |
| Movable | placeatme, walk over it | the existing movable_control proof |
| Quest | stage reached after a scripted trigger | the quest's own log line plus a stage read (needs 2.5) |

### 2.2 Run in tiers, cheapest first (proposal)

0. **Offline**, every build, no game:
   - record validators;
   - Grok's oracles: collision vs mesh (#359) and placement frame (#360);
   - compare-ids against the last build;
   - the door and presence stage refusals.
   A tier-0 failure blocks that item's in-game tests.
1. **Smoke**: one coc or hop per cell, with no interaction.
   - Batch many cells per launch: the session stays up and one queue covers them.
   - Today a deploy plus launch plus load costs about 3 min (docs/ai/optimization.md).
   - Supported estimate, not yet measured: a session with 20 to 40 cocs fits about 100 to 300 cells in a night. The
     first night run should measure this and record it in optimization.md.
2. **Interaction**: doors, pickups, furniture, movables. These run only in cells that passed smoke.
3. **Scenario**: quest flows, NPC packages, map and UI. These run only once their pieces pass tier 2.

Promotion between tiers is automatic and failures go no further. This keeps a broken cell from costing a whole
night.

### 2.3 Contain crashes (proposal; the Red Rocket crash on Oct 19 is the reason)

- **A crash budget per run.**
  - Stop the whole chain at the first crash; that was done by hand for ROUNDS4.
  - Make it a runner option: `--crash-budget N`, default 1 for night runs.
  - Check a disk floor before every launch, for example D: free at least one dump plus 25 GB, and stop if it fails.
- **Small dumps.** crashwatch writes `-ma` (full) dumps today. `-mm` is queued and waits on the user's edit of
  crashwatch.cmd. A full dump can be taken once, on demand, for a crash the bugs thread wants to study.
- **Find a crash automatically.** When a coc or approach crashes, the runner should:
  - mark the spot;
  - queue a bisection: launch nearby, approach in steps, and record the last position read before the crash;
  - hand the bugs thread the REFRs within a radius of that last position, from objects.json.
  Splitting the plugin set further (core-only, without the mission, without the bridge) needs a plugin toggle that
  survives `bridge_install.py order`. Today order re-activates an unticked bridge (verified, bridge_install.py
  order()), so the toggle has to be built into exp_install and the bridge installer.
- **Crash as a result class.** A cell that crashed twice is FAIL CRASH, final, and goes on the bugs list. Today it is
  INCONCLUSIVE CRASH and is never decided.

### 2.4 Make launches reliable (proposal; the user decides)

If the 2 s exit is the admin problem, the runner needs an elevated launch with no prompt. The clean way: a one-time
scheduled task, made by the user, that runs Starfield.exe with highest privileges. cycle.ps1 would start that task and
fall back to steam://. This was proposed on Oct 18 and is waiting on the user. Until then, every night run risks
spending all three launch tries.

### 2.5 Console commands for scenarios (the user decides)

The runner may type only whitelisted commands:
- GetINI and SetINI;
- SetLocalTime;
- FO4SF_Probe;
- prid and enable, which belong to the user.

Tier 3 needs more:
- a stage read (GetStage, through the bridge's Resolve-style reply rather than typed text);
- possibly SetStage, to start a quest at a known point.

Bisection would want `disable` on a picked ref. Each of these is a whitelist decision for the user. A safer path that
needs no new console commands: put the reads into FO4SF_Probe, the bridge's own script (for example
`FO4SF_Probe.Stage <quest>`), so they arrive as log lines like today's resolves.

### 2.6 Keep humans on what machines can't judge

Machines can't judge lighting, texture quality or "feel" (the user's warm orange over-lighting, the grab feel). The
runner can still help:
- take a screenshot at every smoke spot;
- build a per-build contact sheet (a page) for the user to flag issues in one sitting.

The flags go into the ledger as `capability_result` with the source `IN_GAME` and the user as `by`.

## 3. Turning the leader core on, in order (proposal)

1. **Preflight in report-only mode** for a few runs: log what it would refuse without refusing. This is a read-only
   PC job, so it fits while D: is short.
2. **The lease, enforced.** The runner, watchdog and Codex's runbook all take `controller.json`, and the user's own
   play counts as a held lease. Today that is inferred from owner-idle.
3. **The ledger as the one record.**
   - Import the existing queues: the importer exists, and every import carries its campaign.
   - New runs write there live (leader-core.md section 10).
   - Each night's morning report is generated from the fold, so it can't drift from the results.
4. **Capability state per build.** Diff the fold between two build ids to get a regression list: what passed on v5
   and fails on v6. That is the single most useful morning artifact once breadth grows.

Each step is one cloud-session task card. The PC work in steps 1 to 3 is a switch on an existing flag, not new code.

## 4. Testing inside the launcher (proposal)

The launcher builds everything on the user's PC from their own Fallout 4 and all DLC, shipping no assets. Testing
should ship with it, in three parts:
- **`verify` after a build** runs tier 0 plus a short tier 1 (about 10 cells), so a player knows their build is sound
  before playing.
- **Build identity.** Every build is pinned by hashes, and compare-ids runs against the reference id map shipped as
  data (ids, not assets). Whether two machines with the same game version produce the same FormIDs is unresolved
  (core-launcher plan, section 2). This is the check that answers it.
- **Community reports** (#350's form) attach the ledger fold for their build, so a report says which build and which
  results, not just "it crashed".

## 5. Decisions only the user can make

1. Whether to make the elevated launch task (2.4).
2. Whether to switch crash dumps to small by default, with full dumps on request (2.3).
3. The crash budget and disk floor for night runs (suggested: 1 crash, at least 25 GB kept).
4. Which new console reads or commands to allow, or whether to route them through FO4SF_Probe instead (2.5;
   recommended: FO4SF_Probe).
5. When to switch the leader core on (section 3; recommended: preflight report-only first).

## 6. Bounded first tasks (cloud, one session each)

| Task | Output |
|---|---|
| T-crash | started: #377 (draft) adds `--crash-budget` and `--min-free-gb` / `--dump-drive`, off by default; still to do: CRASH x2 as a final FAIL |
| T-inventory | the inventory planner for tiers 1 and 2 from a core build plus port staging; synthetic-fixture tests |
| T-toggle | a plugin toggle that exp_install and bridge_install respect, with restore; tests |
| T-probe-stage | an FO4SF_Probe stage-read design (Papyrus is compiled on the PC) |
| T-preflight-report | a report-only mode for preflight in the runner |
| T-regress | a per-build capability diff from the ledger fold; tests |
