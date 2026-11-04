# Combined-core probes P1 to P10: the PC runbook (spike, 2026-10-21)

For: the owner's PC (Windows PowerShell 5.1, Python 3.13 on PATH as `python`, `dotnet` 9 SDK, Starfield with the
Papyrus compiler under `<Starfield>\Tools`). Branch: `claude/project-thread-6yh1ex` (draft PR #431). Commit: `<commit>`
(the lead fills it in when the probe kit lands; every card repeats it). Nothing here runs by itself: each probe is one
job card the owner pastes into PowerShell, with the game closed where the card says so.

What the probes are and what they settle is in `docs/combined-core.md` ("Waiting on the PC") and the engine note
`research/framework/combined-core-notes/engine-feasibility.md` ("PC probes", P1 to P10). The judge is
`src/fo4sf/combined/probes.py`: `python -m fo4sf.combined.probes pN <collection folder>` prints one JSON verdict
(PASS / FAIL / INCONCLUSIVE with the quoted log lines) and exits 0 / 1 / 2. PASS comes only from the attempt's own
evidence; a missing file, a missing line or a `none` in the log is INCONCLUSIVE, never a PASS; thresholds (save growth,
tick time, arrival distance) are placeholders the verdict labels as such. A teleport or a single end state never
passes a probe about continuous behaviour (P9's samples must show a walk; P2's read must come from a second launch).

Status: **kit staged, nothing run.** Every Starfield fact below that is not cited is labelled unverified. The builder
(`scripts/combined_probes/make_combined_probe.py`, group A), the installer (`scripts/combined_probes/probe_install.py`)
and the SFSE plugin (`sfse/FOCCSidecar/`, group B) are written to the same plan as this runbook; where a card names a
file those groups produce, the file's exact name is the plan's and the first PC run confirms it.

## Rules on every card

1. **Game closed** for every install, uninstall and dll copy. Starfield rewrites `Plugins.txt` and the user log on
   launch (scripts/game/bridge_log.py docstring), so installs during a run are lost or half-applied.
2. **One probe plugin variant installed at a time.** The default stage and the `--p3-cells` variant both override the
   core's persistent cell / FO4Port cells; FO4SFMission.esm overrides the same core cell (plan open question 7): never
   together. `probe_install.py uninstall` before another variant, before any core swap, and before any other
   experiment changes.
3. **Never during a runner run.** If `scripts\game\testqueue.py run` or `cycle.ps1` is going (a lease is held, see
   docs/ai/leader-core.md), wait; the probe plugin is appended last in `Plugins.txt` so the planned load indices of the
   queue's experiments do not shift (the bridge_install.py pattern), but a launch mid-run still breaks the queue.
4. **D: keeps 40 GB free.** Check `(Get-PSDrive D).Free / 1GB` before an install (the archive build makes a copy of
   the stage's Data tree; crash dumps go to D: too, docs/ai/test-queue.md `--min-free-gb`). Below 40, stop and say so.
5. **Nothing from the PC is committed**: logs carry user paths, saves and plugins are game data; `scripts/guard.py`
   refuses them. Collected folders stay under `D:\Modding\testqueue\focc_P<n>_<date>`; what comes back to the thread
   is the pasted output plus the files listed under "Send back".
6. **Hashes before and after.** `Get-FileHash -Algorithm SHA256` of every staged input on the card; `plan.json` in
   the stage holds the builder's own; the two must agree (a mismatch means the stage changed after it was built).
7. **A failed launch is itself a result.** If the game does not reach the main menu with the plugin or dll installed,
   uninstall (game closed), launch once clean to confirm, and paste the crash dump name from D:. Do not retry blind.

Variables used in every block (set once per PowerShell window):

```powershell
$sf   = 'D:\SteamLibrary\steamapps\common\Starfield'     # the folder with Starfield.exe; adjust
$date = Get-Date -Format yyyyMMdd
$stage = "D:\Modding\staging\focc_probe_$date"
$logs = "$env:USERPROFILE\OneDrive\Documents\My Games\Starfield\Logs\Script\User"   # or ...\Documents\My Games\... without OneDrive
$saves = "$env:USERPROFILE\OneDrive\Documents\My Games\Starfield\Saves"             # same choice as $logs
Test-Path "$sf\Starfield.exe"; Test-Path $logs; Test-Path $saves
```

Expect three `True`. The owner's logs sit under OneDrive\Documents on the 2026-10-17 PC (bridge_log.default_log tries
both); pick whichever exists. Reading those folders is fine; our scripts never write under Documents (Controlled Folder
Access, make_bridge.py notes).

### Form ids in the console

Papyrus prints form ids as **signed decimal ints**: a runtime id `FF012345` is logged as `-16702651`. `cgf` takes
ints, `prid` / `PathToRef` take hex. Convert with `python -m fo4sf.combined.probes hex2dec FF012345` and `dec2hex
-16702651`. A wrong conversion shows up as `none` in the log, which the judge reads as INCONCLUSIVE, never PASS.

## Stage and install (shared by P2 to P10)

**Job focc-stage. Branch `claude/project-thread-6yh1ex`, commit `<commit>`. Game: any.**

```powershell
cd <your fo4-to-starfield checkout>
git fetch origin claude/project-thread-6yh1ex; git checkout claude/project-thread-6yh1ex; git log -1 --oneline
$core = (Get-Content "$sf\Data\FO4SFExp.install.json" | ConvertFrom-Json).exp_dir   # the installed core's staging dir
python scripts\combined_probes\make_combined_probe.py stage --core "$core\FO4TerrainCore.esm" --starfield $sf --out $stage `
  --npc Starfield.esm:2B211C --lvln-a Starfield.esm:2B211C --lvln-b <plugin:id> --stat Starfield.esm:<id>
$LASTEXITCODE
Get-ChildItem $stage -Recurse -File | Get-FileHash -Algorithm SHA256 | Select Hash,Path
Get-Content "$stage\offline_check.txt"
Get-Content "$stage\compile_p5_array129.txt"
```

Expect: `wrote ...\FO4SFCombinedProbe.esm (<bytes> bytes): ...` and `all checks pass` from the dotnet check; one
`Compilation succeeded` per script (FOCC_ProbeQuest, FOCC_Probe, FOCC_P10Quest); the number `0`. `compile_p5_array129.txt`
is **expected to fail or succeed, either is the P5 finding** (do not fix it). `--lvln-b` (a second, visually distinct
vanilla NPC_) and `--stat` (a visible vanilla STAT such as a crate) are not verified in the repo: pick both in xSFEdit
on the PC and write them on this card (plan open question 5). The citizen `002B211C` is the one verified to spawn and
walk (docs/owner/in-game-test-sheet.md). Inputs: the installed core's `FO4TerrainCore.esm` (its sha256 lands in
`plan.json`; the plugin is rebuilt for every core build, plan item 6). Writes: `$stage` only. Paste: the two check
blocks, the hash list, both compile files.

If `FOCC_ProbeQuest.psc` or `FOCC_Probe.psc` fails to compile, paste the compiler's error: a missing
`Location.SetKeywordData` / `AddLinkedLocation` / `GetCurrentLocation` / `Keyword.SendStoryEvent` is a negative answer
to P2 / P3 / P10 at compile time (plan open question 3), not a bug to work around.

**Job focc-install. Game: CLOSED.** Rules 1 to 4 apply.

```powershell
(Get-PSDrive D).Free / 1GB
python scripts\combined_probes\probe_install.py status --starfield $sf
python scripts\combined_probes\probe_install.py install --dir $stage --starfield $sf
$LASTEXITCODE
Get-Content "$env:LOCALAPPDATA\Starfield\Plugins.txt"
Get-FileHash -Algorithm SHA256 "$sf\Data\FO4SFCombinedProbe.esm","$sf\Data\FO4SFCombinedProbe - Main.ba2"
```

Expect: a number above 40; `not installed`; the install lines; `0`; `*FO4SFCombinedProbe.esm` as the **last** line of
Plugins.txt; two hashes (the plugin's equals the stage's). Writes: `Data\FO4SFCombinedProbe.esm`,
`Data\FO4SFCombinedProbe - Main.ba2`, `Data\FO4SFCombinedProbe.install.json`, one line in Plugins.txt. On the first
launch answer the "load order changed" dialog with **Current**, load the throwaway save, and run `probe_install.py
status --starfield $sf` after quitting: it must say the plugin is still active (plan open question 11, the first
install answers whether a plugin with WRLD + CELL overrides plus KYWD/LCTN/LVLN/GLOB records loads cleanly).

**Job focc-uninstall. Game: CLOSED.** After the last probe of a session, before any core swap, before the P3 variant.

```powershell
python scripts\combined_probes\probe_install.py uninstall --starfield $sf
$LASTEXITCODE
Get-Content "$env:LOCALAPPDATA\Starfield\Plugins.txt"
```

Expect: the removed files listed, `0`, no `FO4SFCombinedProbe` line. Receipts stay under
`%LOCALAPPDATA%\FO4SF\experiment-receipts` (docs/testing/experiment-receipts.md).

**Collecting a log.** After every quit:

```powershell
$out = "D:\Modding\testqueue\focc_P<n>_$date"; New-Item -ItemType Directory -Force $out | Out-Null
Copy-Item "$logs\focc.0.log" "$out\focc_session1.log"      # or focc_session2.log after the second launch; focc.0.log for one-launch probes
Get-FileHash -Algorithm SHA256 "$out\*"
```

The game rewrites `focc.0.log` on every launch, so copy it **before** the next launch. On a new game the first line
of the log is `FOCC init variant=default` (or `variant=p3cells`). Loading a save made after the quest started does
not run OnInit again (owner's PC, 28 Oct 2026), so session2 may have no init line. The judge then proves the relaunch
by the clock: session2 repeats no line of session1, and its first `rt` (seconds since the game started) is below
session1's highest.

## Compile answers so far (PC stage at 1b23a26, D:\Modding\staging\focc_probe_20261021d, Oct 21)

- P5 array cap: Starfield's compiler refuses `new float[129]` with "Array size of 129 is invalid. Must be between 0
  and 128 (inclusive)" (FOCC_P5_Array129.psc(8,15)). Papyrus arrays stay capped at 128 entries.
- P10 compile half: `Keyword.SendStoryEvent(None, akRef1, None, 0, 0)` compiles as a statement; assigning its result
  to a bool does not (FOCC_Probe.psc(164,9) at 2d53642, type mismatch), so its return is not a bool.
- P2 compile half: FOCC_ProbeQuest.psc, which calls the Location keyword-data and linked-location functions, compiles.
- The in-game halves wait for the probe install (a session with FO4SFMission.esm off, on the owner's word).

## Order

P2, P3, P5, P10, P6, P7, P8, P4, P9, then P1 (P1 needs a toolchain decision and an SFSE launch; it goes last so a
mistaken dll cannot cost the other sessions), then B0 (section B0: its first half, `FOCC_B0.Gmst`, needs no SFSE plugin
and can ride along with any probe session; its second needs the plugin dll and comes after P1 for the same reason).
P2 and P3 can share two launches; P5, P10, P6, P7 can share one launch after P2's commands; P8, P4 and P9 each get
their own saves.

Every judged line names the probe records it used (`holder=`, `route=`, `list=`, `rep=`, P4's `base=`, P5's
`first=`/`last=`, P8's `parent=`/`id=`, P9's dest `id=`, P10's `event=`/`id=`). A missing or foreign id (a stale or
foreign property binding) makes the verdict INCONCLUSIVE, never PASS. P4's `base=` must equal plan.json's `npc`.

## Results on the owner's PC (28 Oct 2026, stage and judges at main de91d6d0)

Run by the Install thread from the main menu (`coc FO4Core_RedRocketSpawn`, `tgm`), with FO4SFMission.esm off. Logs
and verdicts are in `D:\Modding\testqueue\focc_<P>_20261027\` on the PC.

| Probe | Verdict | What the log shows |
|---|---|---|
| P2 | PASS (judged again at dc0bc3b4) | set 37, readback 37, link `linked=True`; after a relaunch and a load, read 37 and `linked=True`. Session2 had no init line (OnInit does not run again on loading a save made after the quest started), so the first judge said INCONCLUSIVE; since #556 a restarted `rt` (74 vs 127) proves the relaunch |
| P3 (keyword half) | PASS (judged again at dc0bc3b4) | va=5 ra=5, vb=6 rb=6; read back ra=5 rb=6 after the relaunch. Same judge gap as P2. The cell half needs the `--p3-cells` restage |
| P4 | PASS | 20 cycles, each placed 3 and deleted 3 (PlaceAtMe); the save shrank by 1,776 bytes |
| P5 | PASS, recorded | 10 ticks over 50 globals, median 121.0 ms (min 119.0, max 123.0), 2.42 ms per place; `array_cap` 128. The first run quit before 10 ticks; a rerun with a 150 s hold passed |
| P6 | PASS | `datum=1` spawned base A three times, `datum=2` base B three times, both resets read back 0 |
| P7 | PASS (minimal; the vendor half is deferred) | tier 3 (global 3) gave A three times, tier 9 (global 9) gave B three times |
| P8 | judge said FAIL; INCONCLUSIVE since #557 | every child matched its parent, but all three readouts (within 1.4 s) showed stage 0's layout: the three P8Stage calls overlapped in one console session. Save growth +1,104 bytes. Rerun with the console closed between calls |
| P10 | INCONCLUSIVE | FOCC_P10_Quest started at game start (rt 59.1), 44 s before the send (rt 103.5); `running=True` after. See the P10 card |
| P8 (rerun) | PASS | the console closed for about 4 s after each P8Stage call; every child followed its parent in each stage's layout; save growth 0 bytes (`focc_P8r_20261027`) |
| P9 | judge said FAIL; INCONCLUSIVE since the ladder judge | `player.placeatme 002B211C`, `PathToRef` to FOCC_P9_Dest 450 m out: for 600 s the actor stayed within about 3 m of its start, in one cell. No rung showed the command moving it, so this cannot tell `PathToRef` from the navmesh; rerun as the ladder on the P9 card |

Second session (28 Oct, after #557's restage; `focc_probe_20261028b`, plugin e2e549f2; Install's report):

| Probe | Verdict | What the log shows |
|---|---|---|
| P10 | PASS | the check printed the branch's new condition (GetEventData GetIsID Keyword1, record 00081F, equal to 1, the shape of 80 of the 82 vanilla keyword filters); `SendStoryEvent` ran, FOCC_P10_Quest's OnQuestInit came after it, `running=True` |
| P3 (cell half) | INCONCLUSIVE; run again after the restage | both `where` lines are in the log (Red Rocket cell 117449528, loc 167774215 = local 0x807; Super Duper Mart cell 117468230, loc 167774216 = local 0x808), but `cellname=` came back empty on both, and the judge named cells only by cellname. It now names them by the stage's form ids in offline_check.txt, bound to FO4Port.esm by the script's `port=True` (P3b card); the 28 Oct log has no `port=`, so P3b runs again with the restaged kit |
| P9 (ladder) | INCONCLUSIVE | rung b (`PathToRef player`, start 16.7 m): the actor ended about 22 m away, so the ladder stopped there as the card says. Next: the scripted driver (P9 card) |
| P9 (scripted ladder, kit d after #566; evidence `focc_P9_20261028_1043`) | INCONCLUSIVE | rung a (baseline, 60 s): 16.7 m to 21.7 m. Rung b (`FOCC_P9Drive.Go <actor> 1`, 24.43 m): `PathToReference(player, 1.0, 1.0)` returned after 2.89 s with the actor 24 to 28 m away (26.70 m at the end), so the ladder stopped. The driver did not log the return then; Starfield's Actor.psc (line 490) declares it `int`, latent, with PathingResult_Success 0, Failure 1, Stopped 2, Cleared 3, Timeout 4, and the driver now logs it as `result=` (1 = unsuccessful request; 2 or 4 = stopped or timed out; none alone identifies the cause). Next: rung b again with the code, before any new driver (a Travel package on a quest alias, or Cassiopeia's PathToPoint) |

**The load order trap.** Loading a save made while FO4SFMission.esm was active silently switched Starfield to that
save's load order: Mission came back on and the probe plugin went off, with no dialog. The cgf calls then failed with
"Cannot open store for class FOCC_Probe". Start each probe from the main menu, or from a save made with the probe
plugin on. The leader-core preflight must check the active plugins after a save loads, not only at launch.

## P2: keyword data persists across save and load

Settles: **CC-02** (the floor of option C': location keyword data as the holder datum) and linked-location route data
(engine-feasibility.md "Building blocks", persistence **unresolved** until this runs).

**Job focc-P2. Commit `<commit>`. Game: running after focc-install.** Inputs: the installed stage (hashes above).

Launch (Steam or `cycle.ps1`), load the throwaway save, open the console:

```
cgf "FOCC_Probe.Hello"
cgf "FOCC_Probe.P2Set" 37.0
cgf "FOCC_Probe.P2Link"
save focc_p2
```

Quit to desktop. Collect as `focc_session1.log` into `D:\Modding\testqueue\focc_P2_$date`. Relaunch, load `focc_p2`:

```
cgf "FOCC_Probe.P2Read"
cgf "FOCC_Probe.P2LinkRead"
```

Quit; collect as `focc_session2.log`. Judge:

```powershell
$env:PYTHONPATH = "src"; python -m fo4sf.combined.probes p2 "D:\Modding\testqueue\focc_P2_$date"; $LASTEXITCODE
```

Expect in session1: `FOCC rt=... p2 set loc=<id> local=2054 value=37.000000 readback=37.000000 holder=<id>` and `p2 link a=<id>
b=<id> linked=True route=<id>`; in session2 (a fresh `FOCC init`, or an `rt` that started again below session1's)
`p2 read local=2054 value=37.000000` and `p2 linkread linked=True`. PASS = those four, across two launches. FAIL = the
read is 0 or another value after a confirmed set, or linkread False. INCONCLUSIVE = a file missing, no relaunch proven
in session2, `refused` (a property did not resolve), or no readback. Send back: both logs, the verdict JSON, the console's reply to `Hello` if it printed anything.

## P3: our location with and without a parent; the cell's current location

Settles: whether an LCTN of ours without a planet parent behaves like one chained to the core's overlay location,
and whether a converted interior given our LCTN reports it as the player's current location (interiors D1, the
"location per interior" prerequisite; engine-feasibility.md "In short"). Explored state is **unresolved** (no verified
Papyrus read; FO4's IsCleared is missing, PC job 15) and the verdict says so instead of judging it.

**Job focc-P3a (keyword half). Game: running, default stage, same two launches as P2.** After `P2Set`/`P2Link` and
before `save focc_p2`:

```
cgf "FOCC_Probe.P3Set" 5.0 6.0
```

and in the second launch after `P2Read`:

```
cgf "FOCC_Probe.P3Read"
```

Copy the same two logs into `D:\Modding\testqueue\focc_P3_$date` as `focc_session1.log` / `focc_session2.log`; judge
`probes p3`. Expect `p3 set a=<id> va=5.000000 ra=5.000000 b=<id> vb=6.000000 rb=6.000000` and, after relaunch,
`p3 read a=<id> ra=5.000000 b=<id> rb=6.000000 holder=<id>` (both ids must be the probe locations, locals 2055 and 2056). FAIL when one of the two reads 0 (the verdict says which: that alone decides whether
unparented locations are usable).

**Job focc-P3b (cell half). Game: CLOSED for the swap.** Run focc-uninstall, then stage the variant into a new folder
and install it alone:

```powershell
python scripts\combined_probes\make_combined_probe.py stage --core "$core\FO4TerrainCore.esm" --starfield $sf --out "${stage}_p3cells" --p3-cells --port "$sf\Data\FO4Port.esm" <same --npc/--lvln/--stat as before>
$LASTEXITCODE
python scripts\combined_probes\probe_install.py install --dir "${stage}_p3cells" --starfield $sf
```

Launch, load the throwaway save:

```
coc FO4Port_RedRocket01
cgf "FOCC_Probe.Where"
coc FO4Port_SuperDuperMart01
cgf "FOCC_Probe.Where"
```

Quit; collect as `focc.0.log` into `D:\Modding\testqueue\focc_P3cells_$date`, and copy `offline_check.txt` from
`${stage}_p3cells` beside it; judge `probes p3`. Expect `FOCC init variant=p3cells`, then `where cell=<id> loc=<id>
local=2055 cellname=<editor id or empty> port=True` for Red Rocket and the Super Duper Mart line with `local=2056`. On
the PC (28 Oct) `cellname=` came back empty on both lines, so the judge names each cell by the form id the stage recorded
for it in offline_check.txt (`CELL FO4Port_RedRocket01 <id>:FO4Port.esm`), and only when the line also says `port=True`:
the script asks `Game.GetFormFromFile(<the cell's local id>, "FO4Port.esm")` for the cell the player stands in and logs
whether the game hands back that same cell, so the id is FO4Port.esm's in this run and not another plugin's in that load
slot (the stage's file proves the source FormKeys, not the run's load order; Codex review of #560). Without the file, or
on a log from before the script logged `port=` (the 28 Oct log), the cell half is INCONCLUSIVE and P3b runs again with
the restaged kit. FAIL = `loc=none` or another location. **Then run focc-uninstall and reinstall the default stage**
before anything else (rule 2: the variant overrides two FO4Port interiors while installed). A crash on load with the
variant is itself the answer for an unparented LCTN (plan P3 risks): paste the dump name.

Send back: the logs, both verdicts, and whether the two `coc` cells looked normal.

## P5: Papyrus tick baseline and the array cap

Settles: the script-latency baseline for the L2 fallback (recorded under docs/ai/optimization.md's before/after rule,
not judged beyond a placeholder cap) and the 128-entry array cap at compile time.

**Job focc-P5. Game: running, default stage (after P2's commands is fine).**

```
cgf "FOCC_Probe.P5Tick" 10
```

Wait for ten `p5 tick` lines (`Get-Content -Wait "$logs\focc.0.log"` in a second window shows them), quit. Collect
`focc.0.log` and the stage's `compile_p5_array129.txt` into `D:\Modding\testqueue\focc_P5_$date`; judge `probes p5`.
Expect `p5 start ticks=10 places=50 first=<id> last=<id>` then `p5 tick n=<1..10> places=50 ms=<float> sum=<float>`; the verdict reports min / median
/ max ms and ms per place as the baseline and `array_cap` 128 (compile refused `new float[129]`), `null` (it compiled)
or `unknown` (file missing). FAIL only on fewer than 10 ticks after a start or a tick above the placeholder 1000 ms.
Send back: the log, the compile file, the verdict; the lead copies the baseline into docs/ai/optimization.md.

## P10: SendStoryEvent compiles; our Story Manager branch starts our quest

Settles: event plumbing for radiant quests (engine-feasibility.md P10; `Keyword.SendStoryEvent` compile is the
unresolved item in starfield-systems-to-reuse.md). Mutagen's SMBN/SMQN writing is unverified (plan open question 2):
if the stage's `plan.json` says `"sm_nodes_written": false`, the probe answers the compile question only.

**Job focc-P10. Game: running, default stage.**

```
cgf "FOCC_Probe.P10State"
cgf "FOCC_Probe.P10Send"
```

The first line proves the quest is not running before the send. Wait 10 s, then:

```
cgf "FOCC_Probe.P10State"
```

Quit. Collect `focc.0.log`, and from the stage `offline_check.txt`, `plan.json` and `FOCC_Probe.psc` (stage root,
not Data\Scripts; copy, the judge reads the call from the source) into `D:\Modding\testqueue\focc_P10_$date`; judge `probes p10`.
Expect `p10 sent event=<id>` (the call's return is not logged: Starfield's SendStoryEvent does not return a bool, PC compile at 2d53642), within 10 s (rt) `p10 quest started id=<id> local=2080` (FOCC_P10Quest.OnQuestInit) and
`p10 state running=True`. FAIL = `result=False`, or True with no start and `running=False`. INCONCLUSIVE when
the quest was already running before the send (a `p10 quest started` line or `running=True` before it). The verdict's
`sendstoryevent_compiles` is the compile answer on its own. Send back: the four files and the verdict.

**28 Oct 2026, owner's PC (stage at de91d6d0):** INCONCLUSIVE. FOCC_P10_Quest's OnQuestInit logged at rt 59.1, at
game start, 44 s before the send at rt 103.5 (and at rt 58.6 in P2's session 1). `running=True` after the send, so
the send did not start it. Likely cause, not yet proven: FOCC_P10_Branch has no condition, so the first script event
any script sends that no earlier sibling takes starts our quest. The fix is a `GetEventData` condition on the
branch that names FOCC_P10_Event, copied from Starfield.esm's own Script Event nodes; restage and rerun.

## P6: leveled-list entries conditioned on location keyword data

Settles: data-only territory spawns (engine-feasibility.md section 3): `GetKeywordDataForCurrentLocation` (condition
index 651, **verified** in xEdit SF1) on an LVLN entry. Depends on the builder writing per-entry conditions (unverified
Mutagen API; `plan.json` `"lvln_conditions_written": false` makes the verdict INCONCLUSIVE/blocked, never faked).

**Job focc-P6. Game: running, default stage, outdoors at Red Rocket (`coc FO4Core_RedRocketSpawn`), `tgm`.**

```
cgf "FOCC_Probe.P6" 1.0 3
cgf "FOCC_Probe.P6" 2.0 3
```

Quit; collect `focc.0.log` and the stage's `plan.json` (it names `lvln_a` / `lvln_b`) into
`D:\Modding\testqueue\focc_P6_$date`; judge `probes p6`. Expect six lines `p6 datum=<1|2>.000000 loc=<id>
readback=<same> list=<id> holder=<id> trial=<1..3> base=<id> baselocal=a|b|other|none` (a and b are the plan's entries A and B), then `p6 reset`. PASS = datum 1
spawns entry A three times and datum 2 entry B three times. FAIL = the other entry or `base=none`. INCONCLUSIVE =
`loc=none` (you were not in a location), a `list=` or `holder=` that is not the probe's own record (locals 0x81C,
0x805), fewer trials, or a `baselocal` the judge cannot map. Note: the datum is set on the core's overlay location; the script resets it to 0 (`p6 reset`).

## P7: a condition reads our reputation global

Settles: the minimal form of reputation effects (`GetGlobalValue`, index 74, **verified**) on an LVLN entry at the
tier `adapter.reputation_tier` produces. The real question, a vendor refusing service, is **P7b, deferred**: it needs an
NPC_ with a VEND faction entry and PLVD, a merchant container and dialogue INFO conditioned on the global
(economy-vendors-barter.md), which no converter of ours produces; the verdict reports it as deferred, never judged.

**Job focc-P7. Game: running, default stage, outdoors, `tgm`.**

```
cgf "FOCC_Probe.P7" 3.0 3
cgf "FOCC_Probe.P7" 9.0 3
```

Quit; collect `focc.0.log` and `plan.json` into `D:\Modding\testqueue\focc_P7_$date`; judge `probes p7`. Expect
`p7 tier=3.000000 glob=3.000000 list=<id> rep=<id> trial=<k> ... baselocal=a` three times and `tier=9.000000 ... baselocal=b` three times.
INCONCLUSIVE when `glob=` differs from the tier set, or `list=` / `rep=` is not the probe's own record (locals 0x81D,
0x81E).

## P8: enable-parent stage swap and its save cost

Settles: build stages without player building (engine-feasibility.md section 5): three XMarker parents each parenting
four statics, swapped by Enable/Disable, with save size before and after.

**Job focc-P8. Game: running, default stage, at Red Rocket, `tgm`.**

```
save focc_p8_before
cgf "FOCC_Probe.P8Move"
cgf "FOCC_Probe.P8Stage" 1
cgf "FOCC_Probe.P8Stage" 2
cgf "FOCC_Probe.P8Stage" 0
save focc_p8_after
```

Close the console for about 3 s after each `P8Stage` line. P8Stage reads the children after `Utility.Wait(1.0)`,
which does not count down while the console is open: three calls in one console session all toggle before any
readout, and every readout sees the last stage (owner's PC, 28 Oct 2026). The judge reports that as INCONCLUSIVE.

(A screenshot after each stage is optional: `scripts\game\shot.ps1`.) Quit, then:

```powershell
$out = "D:\Modding\testqueue\focc_P8_$date"; New-Item -ItemType Directory -Force $out | Out-Null
Copy-Item "$logs\focc.0.log" "$out\focc.0.log"
Get-Item "$saves\focc_p8_before.sfs","$saves\focc_p8_after.sfs" | Select Name,Length | ConvertTo-Json > "$out\saves.json"
```

Judge `probes p8`. Expect three `p8 move stage=<k> parent=<id>` lines (stages 0, 1, 2; parents locals 0x80C..0x80E), then for each `p8 stage=<s>` twelve `p8 child stage=<k> j=<j> id=<id> disabled=<bool>
parent_disabled=<bool>` with `disabled=False` exactly for `k == s`. FAIL = a child disagreeing with its parent (enable
parents not honoured after MoveTo, itself the finding, plan P8 risks) or growth above the placeholder bound
(max(2 MB, 5 %)). Send back: the log, `saves.json`, the verdict, screenshots if taken.

## P4: materialize and dissolve, 20 cycles, save size

Settles: spawn reliability and save bloat for the L3 presence layer (design rule L3, no permanent spawned refs). v1
uses PlaceAtMe/Delete (`mode=placeatme`); the alias variant appears as `mode=alias` only if the builder gets the alias
API, and the judge accepts either.

**Job focc-P4. Game: running, default stage, `coc FO4Core_RedRocketSpawn`, `tgm`.**

```
save focc_p4_before
cgf "FOCC_Probe.P4Run" 20 8.0
```

Wait for `p4 done` (about 3 minutes; `Get-Content -Wait "$logs\focc.0.log"`), then `save focc_p4_after`, quit. Collect
`focc.0.log` and `saves.json` for `focc_p4_before.sfs` / `focc_p4_after.sfs` (the P8 block with the names changed) into
`D:\Modding\testqueue\focc_P4_$date`; judge `probes p4`. Expect `p4 cycle n=<1..20> placed=3 loaded=<k> deleted=3
mode=placeatme` for every n and `p4 done cycles=20 placed=60 deleted=60`. FAIL = a cycle with placed<3 or deleted<3,
or growth above the bound. INCONCLUSIVE = no done line, a save missing, or actors never loaded in more than two
cycles (a spawn problem, not a bloat answer). The growth number itself is the finding.

## P9: one actor walks 450 m across exterior cells

Settles: long-route pathing on the converted navmesh (the exterior gate passed only over 19 m in the test sheet).
The probe needs a driver that walks a calm citizen at all, and the console has none so far. The test sheet's 19 m
gate read 7.2 m in 30 s, inside the 14 m a calm citizen drifts on its own (N1c); N0 refuted the earlier `PathToRef`
PASSes as wander (docs/actors/npc-navigation.md section 5); and on the PC's ladder (28 Oct, second session) the
console's `PathToRef player` left the actor about 22 m from the player after starting 16.7 m away. So the driver is
now `FOCC_P9Drive.Go`: `Actor.PathToReference` called from Papyrus, which `cf` never reached (N0_cf). It is compiled
on its own (`compile_p9_drive.txt`): if Starfield's Actor.psc does not declare it, only P9 waits, and the stage says so.
The PC's first compile (main c0c3c96c, 28 Oct) refused FO4's two-argument call: Starfield's Actor.psc wants a third,
`afNormalizedRotationSpeed`, with no default, so the script passes `PathToReference(target, 1.0, 1.0)`.
If the scripted control does not bring the actor either, the next driver is a package on a quest alias (a Travel
package, the way the game moves its own actors); its PACK record needs Mutagen's Starfield API checked first.
The card is a ladder in one launch: a baseline with no command, a short scripted control, then longer routes. The
judge needs continuous samples: a jump faster than a walk between two samples is read as a teleport and is never a
PASS.

**Job focc-P9. Game: running, default stage, at Red Rocket, `tgm`, `SetLocalTime 12`.** First read the stage's
`compile_p9_drive.txt`: if it says `refused`, do not run P9; send that file (the compiler's line is the finding).

```
player.placeatme 002B211C 1
PickLastRef                                  (note the FFxxxxxx it prints; hex2dec FFxxxxxx gives the negative decimal cgf wants)
```

Walk about 20 m away from the actor and stand still there until rung b ends: you are the destination. Close the
console after every rung's last line (the game is paused while it is open, so nothing walks).

**Rung a, the baseline (60 s, no command).**

```
cgf "FOCC_Probe.P9Dest" 0.0 0.0              (FOCC_P9_Dest at your feet)
cgf "FOCC_Probe.P9Track" <actor id as signed decimal> 60
```

**Rung b, the scripted control (60 s).** After `p9 done`:

```
cgf "FOCC_Probe.P9Track" <actor id as signed decimal> 60
cgf "FOCC_P9Drive.Go" <actor id as signed decimal> 1
```

The log then has `p9 go actor=<id> call=<t> target=player ...` and, when the call returns, `p9 path returned ...
result=<code> after=<s> dist=<m>`. The code is Starfield's `PathingResult` (Actor.psc lines 476 to 480: 0 Success,
1 Failure, 2 Stopped, 3 Cleared, 4 Timeout; the judge names it). If the actor did not come within 10 m of you, stop
here and send the log: `result=1` reports an unsuccessful request, while `2` or `4` reports a stopped or timed-out
walk. None of these codes alone identifies a NAVM or AI fault. Compare a vanilla-area control and the actor/target
state before attributing a cause; a Travel package on a quest alias (or Cassiopeia's PathToPoint) is a separate
driver to test. Otherwise go on.

**Rungs c, d and e (20 m for 120 s, 120 m for 180 s, 450 m for 600 s).** Start each only after the previous rung's
`p9 done` and its `p9 path returned` (or 30 s after `p9 done` if no return came: note that). For each, with the dx
used (direction: along the road per docs/terrain/walk-redrocket-sanctuary.md; write the dx dy used on the card):

```
cgf "FOCC_Probe.P9Dest" <dx> 0.0             (20.0, then 120.0, then 450.0)
cgf "FOCC_Probe.P9Track" <actor id as signed decimal> <120, then 180, then 600>
cgf "FOCC_P9Drive.Go" <actor id as signed decimal> 0
```

Follow with `tcl` if the actor gets far (AI processing distance may drop the path; the tracker's `loaded=` shows it).
Quit after the last `p9 done` and its `p9 path returned` (or 30 s). Collect `focc.0.log` into
`D:\Modding\testqueue\focc_P9_$date`; judge `probes p9`. Expect `p9 sample t=<s> actor=<id> pos=x y z cell=<id>
loaded=<bool> dist=<m>` every 2 s.

The verdict is the latest rung's: dist from >= 400 to < 10 within 600 s through >= 4 distinct cell ids, timed by each
line's `rt=` from the start's (real seconds; late timers do not stretch the deadline). When the script sent the actor, the walk and its clock start at its `p9 go`
(samples before it show an actor not yet commanded). FAIL = stuck (dist within 2 m for 120 s while loaded) or never
leaving the first cell, and only when the log shows the command moving this actor: it came at least 20 m closer on
that route, or the first rung within 30 m (the baseline, with no `p9 go`) stayed away and a later rung that the script
sent (its `p9 go` inside its track, after the start and before its `p9 done`) was found by that go 15 to 30 m out and
came under 10 m after it through continuous samples (the walk's own checks: readings complete, time increasing, no
step faster than 15 m/s; a jump to the destination is a setup fault, not the command). The distance that counts is the go line's `dist=`, not the start line's: what the actor did
between P9Track and the go was not the command's doing, and an actor already under 10 m when commanded arrived on its
own. The judged rung's go must name the tracked destination (`Go <id> 0`: `target=dest` with FOCC_P9_Dest's id), since
P9Track measures the distance to FOCC_P9_Dest: a long rung sent to the player (`1` left in from the control) or to
another reference commanded a different walk than the samples describe and is INCONCLUSIVE, whatever the samples show.
The control's go may name the player (standing at the destination for that rung) or the destination itself. A console command leaves no line in the log, so a rung without a go never stands as the control and a rung without
a go is judged by its own approach only: an actor that arrived without a logged command may have wandered (N1c drifted
14 m; Codex review of #560). Otherwise those cases are INCONCLUSIVE: a still actor cannot tell a command that did nothing
from a navmesh with no path. Every rung is summarised in the verdict's `extra.attempts` (start, go and closest
distance, how far the actor moved, cells, whether it arrived, its driver, target and whether that was the tracked destination, the line of its go, and after how
many seconds its PathToReference returned, paired by `call=`). Send back: the log, the verdict, the dx dy used and the
actor id.

**Unsuccessful native requests (1 November 2026).** The judge retains each matched return code and reports it even
when a short control cannot judge the 400 m route. A request returning Failure, Stopped, Cleared, Timeout or an unknown
code cannot earn PASS from later wandering, and cannot qualify as the successful short control. Every explicit
return, including Success, ends the request's evidence window: arrival, approach, cell crossings and any stall must
be sampled by that return's real time. A missing or malformed return timestamp supplies no such window. A Success
code alone is not arrival evidence; the samples must show arrival before or at the return. Stopped, Cleared, Timeout,
unknown and malformed codes, or a Success code conflicting with a stall, remain INCONCLUSIVE rather than a navmesh
FAIL. Failure (1) still needs a sustained in-request stall and proof the driver moves the actor; it is a failed route
test, not an isolated root cause. Legacy logs without a result code retain their existing rules, including missing
returns; they cannot prove that a modern latent request completed.
The driver now logs actor/target cells and actor load/death/disable/current-package state before the call. These
are diagnostic reads, with no AI, package or navmesh changes. If a state line is present, an unloaded, dead or disabled
actor, a disabled target or an unreadable state makes the rung INCONCLUSIVE and excludes it as a control. The owner's same-profile Commonwealth and QASmoke
requests both returned Failure; their cause remains unresolved, and the longer route stays held pending a working
control. QASmoke under the same installed profile is not an unmodded-profile control.

## P1: SFSE sidecar on save and load (last)

Settles: **CC-02** option C' / B: whether an SFSE plugin can keep a file per save keyed to the save name through
`kMessage_PreSaveGame` / `kMessage_PostLoadGame` (**verified** messages, PluginAPI.h lines 103-110;
Hooks_Serialization.cpp), and what happens to orphans when a save is deleted (no delete message, so the plugin never
deletes; `sidecar.orphans` lists). No SFSE build has ever happened in this project or on the PC (docs/terrain/source-
patch.md: no cl, cmake, Visual Studio), so the first step is a toolchain check and an **owner decision** to install
Visual Studio Build Tools 2022 with the C++ workload (several GB). The SFSE loader, dll and plugin folder names are
what the Nexus archive ships and are unverified here; the first card confirms them.

**Job focc-P1-0 (toolchain, read-only). Game: CLOSED.**

```powershell
powershell -File sfse\FOCCSidecar\check_toolchain.ps1 -Starfield $sf -Env D:\Modding\tools\msvc_env.ps1
$LASTEXITCODE
```

Expect a JSON of findings (cl.exe, Windows SDK, `sfse_loader.exe` beside Starfield.exe, the SFSE dll version) and `0`.
`1` = stop; nothing else in P1 proceeds until the owner decides on the Build Tools install.
(28 Oct 2026: the owner approved, and Install put a portable MSVC 14.44 with the Windows SDK 10.0.26100 under
`D:\Modding\tools`, loaded by dot-sourcing `msvc_env.ps1`; no Visual Studio, so nothing for vswhere to find. Both scripts
take that environment with `-Env`, and the JSON's `toolchain` reads `environment`; both refuse a loaded environment
whose `cl.exe` banner does not say x64, so an x86 developer prompt cannot produce a dll the 64-bit game cannot load.)

**Job focc-P1-1 (header and build). Game: any.**

```powershell
powershell -File sfse\FOCCSidecar\fetch_pluginapi.ps1 -Commit <pinned sfse commit> -Sha256 <hash from the README>
powershell -File sfse\FOCCSidecar\build.ps1 -Out "D:\Modding\staging\focc_sfse_$date" -Env D:\Modding\tools\msvc_env.ps1
$LASTEXITCODE
Get-Content "D:\Modding\staging\focc_sfse_$date\build.json"
Get-FileHash -Algorithm SHA256 "D:\Modding\staging\focc_sfse_$date\FOCCSidecar.dll"
```

Expect `0`, `build.json` with the sha256 of every source and the dll, a matching hash. `PluginAPI.h` is MIT and stays
out of git (.gitignore); compile errors on the first build are expected and cheap (struct names from the F4SE lineage
may differ): paste them whole.

**Job focc-P1-2 (install by hand). Game: CLOSED.** No installer of ours covers SFSE plugins; the copy is recorded here.

```powershell
New-Item -ItemType Directory -Force "$sf\Data\SFSE\Plugins" | Out-Null
Copy-Item "D:\Modding\staging\focc_sfse_$date\FOCCSidecar.dll" "$sf\Data\SFSE\Plugins\FOCCSidecar.dll"
Copy-Item "D:\Modding\staging\focc_sfse_$date\FOCCSidecar.ini" "$sf\Data\SFSE\Plugins\FOCCSidecar.ini"
(Get-Content "$sf\Data\SFSE\Plugins\FOCCSidecar.ini") -replace 'bEnabled=0','bEnabled=1' | Set-Content -Encoding ASCII "$sf\Data\SFSE\Plugins\FOCCSidecar.ini"
Get-Content "$sf\Data\SFSE\Plugins\FOCCSidecar.ini"
Get-FileHash -Algorithm SHA256 "$sf\Data\SFSE\Plugins\FOCCSidecar.dll"
```

Expect the ini to read `bEnabled=1` (the build writes 0, the kill switch; without 1 the dll loads idle and writes no
`FOCCSidecar\` folder, so P1-3 would be INCONCLUSIVE). Uninstall = delete `FOCCSidecar.dll` and `FOCCSidecar.ini` (and the `FOCCSidecar\` folder beside it once collected). If the game does not reach
the main menu, delete it at once (rule 7).

**Job focc-P1-3 (run). Game: launched through `sfse_loader.exe`, not Steam** (cycle.ps1 is not the path here).
Load the throwaway save, then in the console:

```
save focc_p1_a
```

load the Autosave again (menu), `save focc_p1_b`, load `focc_p1_a` (menu), quit to desktop. Relaunch through the
loader, in the save menu delete `focc_p1_b`, quit.

```powershell
$out = "D:\Modding\testqueue\focc_P1_$date"; New-Item -ItemType Directory -Force "$out\sfse" | Out-Null
Copy-Item "$sf\Data\SFSE\Plugins\FOCCSidecar\focc_sidecar.log" "$out\sfse\"
Copy-Item "$sf\Data\SFSE\Plugins\FOCCSidecar\sidecars" "$out\sfse\sidecars" -Recurse
Get-ChildItem $saves -Filter *.sfs | Select Name,Length | ConvertTo-Json > "$out\saves.json"
$env:PYTHONPATH = "src"; python -m fo4sf.combined.probes p1 $out; $LASTEXITCODE
```

Expect in the log one JSON object per line: `{"event":"pre_save","save":"focc_p1_a","counter":1}`, `post_save`,
`{"event":"post_load","save":"focc_p1_a","found":true,"valid":true,"counter":1}`. PASS = every `pre_save` has its
`post_save` and a sidecar named by the Python rule (`sidecar.sidecar_name`: safe name, `-`, 8 hex of sha256 of the save
name, `.focc`) whose envelope decodes with the right checksum and counter; every `post_load` of a saved name says
found and valid with the last counter; after the delete the orphan list is exactly `focc_p1_b`'s sidecar. FAIL = a
missing file, a `found:false` for a saved name, or a name mismatch between the C++ and Python rule (the judge recomputes
the name). INCONCLUSIVE = no `post_load` at all (the plugin did not load: paste the loader's console output), or the
save name SFSE passes does not equal any `.sfs` stem (display name vs file stem is unverified; the verdict prints both
lists and leaves the orphan question open rather than guessing). Send back: `focc_sidecar.log`, the `.focc` files,
`saves.json`, the verdict, the loader output, and which file names the archive used.

## B0: the plugin bridge, Papyrus to the SFSE plugin and back (after P1)

Settles: whether a value crosses from a quest script into our SFSE plugin and back on 1.16.244, the link the C++ port
stands on (docs/combined-core-cpp-port.md, section 4). The owner's call of 28 Oct 2026: stack A first (the Address
Library as a dependency and CommonLibSF as it is, fixed where 1.16.244 breaks it), B as the backup (a bridge with no
game addresses: a traced line in, a game setting written by its name out), C (Cassiopeia) when needed. Kit: `FOCC.psc`
(the native stub the plugin binds) and `FOCC_B0.psc` (the console entry points), compiled on their own
(`compile_b0.txt`; a refusal leaves only B0 out of the stage), and GMST `iFOCC_Pong` = 7 (0x855) in the probe
plugin. Judge: `python -m fo4sf.combined.probes b0 <folder>`: PASS = the setting read back as 7 and one route
answered; INCONCLUSIVE = the first half alone, a setting answer that is not fresh, or an unbound native beside an
unchanged setting (nothing happened; the plugin's own log says whether the dll loaded); FAIL = Papyrus read something
other than 7 first, or the native answered wrong and the setting changed to a wrong value too. A ping's pong and
setting reads are taken from the window up to the next ping, and any read of N + 1 in it is the answer. Two rules for the
commands, both from the Codex review of #568: every launch rewrites `focc.0.log`, so each launch starts with
`cgf "FOCC_B0.Gmst"` before any ping (the judge wants the launch's first read to be the stage's 7, and a first read
after a ping is INCONCLUSIVE, not FAIL); and a setting answer counts only when it differs from the value the setting
held before the ping, so no ping value repeats within a launch and no ping expects the value already there (a ping of
6 expects 7; a second `Ping 41` after a 42 reads the stale 42; neither settles anything). Two jobs.

**Job focc-B0-1 (Papyrus reads our game setting; no SFSE plugin). Game: running, the default stage from this main
installed, any save.** The stage's `compile_b0.txt` must say `compiled`. Then:

```
cgf "FOCC_B0.Gmst"
```

Expect `FOCC rt=<s> b0 gmst name=iFOCC_Pong value=7`. Collect `focc.0.log` into `D:\Modding\testqueue\focc_B0_<date>\`
and judge `b0`: INCONCLUSIVE with the reason "B0-1: Papyrus read the plugin's game setting" is this half's pass (the
bridge is not yet tried). `value=0` is this half's FAIL: a setting new to the game does not reach
`Game.GetGameSettingInt` from a plugin, so stack B's return leg (plugin to script) is dead and only A remains; send the
log. This job rides along with any probe session on the kit.

**Job focc-B0-2 (the native route, stack A). Game: CLOSED for the installs, then launched through the loader.**
Prerequisites, in this order, each a game-folder or build step for the owner's line:
1. The Address Library for SFSE Plugins (Nexus 3256; v22 covers 1.16.244; on the PC since 24 Oct, extracted on 28 Oct
   to `D:\Modding\staging\addresslib_v22`: `versionlib-1-16-244-0.bin`, 5,099,968 bytes). The `.bin` goes to
   `<Starfield>\Data\SFSE\Plugins\`, together with the dll. The library opens `versionlib-<exe version with
   dashes>.bin` in the plugin's folder (libxse `lib/commonlib-shared/src/REL/IDDB.cpp`) on the first id lookup; a
   missing file or another game version in its header stops the game with a message box. Before the launch, the first
   row of `Format-Hex <the .bin> | Select-Object -First 1` (Windows PowerShell 5.1 has no `-Count`) must open with
   `05 00 00 00`: the file is address library format 5 (Install's header check, 28 Oct), the generation SFSE's
   `PluginAPI.h` calls "Address Library for 1.15.216+"; libxse reads formats 1, 2 and 5, and the old CommonLibSF
   `9caec20` read 2 only, which is why the first dll of 28 Oct was never installed. Another first word is a
   library-generation finding ("Unsupported Address Library format" box), not a bind finding.
2. libxse/commonlibsf at `9d090c4` with its submodule `lib\commonlib-shared` at `9fbb74d`, cloned on the PC on 28 Oct
   (`D:\Modding\tools\libxse-commonlibsf`), and xmake 3.1.2 (`D:\Modding\tools\xmake-3.1.2`, on PATH through
   `msvc_env.ps1`). The original CommonLibSF is archived and points to libxse; the PC's `CommonLibSF-install` prefix of
   the morning is no longer used.
3. `FOCCPing.dll` built from `sfse/FOCCPing` (its README) with `build.ps1 -Out D:\Modding\staging\focc_ping_<date>
   -Env D:\Modding\tools\msvc_env.ps1` (`-Lib` defaults to the checkout; the script makes xmake's MSVC root from
   `VCToolsInstallDir` and `WindowsSdkDir`; `build.json` records every sha256 and both library commits), and copied by
   hand to `<Starfield>\Data\SFSE\Plugins\`.
Then launch through `sfse_loader.exe`. The kit's rule holds: a dll that keeps the game from the main menu is deleted
at once. Three readings of a stop: an id whose slot in the Address Library is empty stops the game with a message
box ("Failed to find offset for Address Library ID"); an id that resolves to a wrong offset faults at the bind
(`GameVM::GetSingleton`, `GetVM` or the virtual call) with no message box, a crash dump and `FOCCPing.log` ending at
"listening for PostDataLoad" (the plugin hooks nothing, so nothing of ours runs before that message); and a log that
reads "no script VM at PostDataLoad" with the game running means the GameVM singleton was not set when the native was
to be bound, a timing finding for the plugin, not the library. At the main menu,
load a save and, the `Gmst` first (this launch's `focc.0.log` is new, and the judge reads its first `b0 gmst` as B0-1):

```
cgf "FOCC_B0.Gmst"
cgf "FOCC_B0.Ping" 41
save focc_b0_a
```

Load `focc_b0_a` from the menu, then `cgf "FOCC_B0.Ping" 43` and `cgf "FOCC_B0.Gmst"`. Expect `b0 gmst name=iFOCC_Pong
value=7` first, then `b0 pong sent=41 got=42`
and `b0 pong sent=43 got=44`: the native bound, and still bound after a save and a load (section 4's pass). `got=0` is
an unbound native (no plugin registered `FOCC.Ping`; `Papyrus.0.log` names it); with the closing read still 7 the
verdict is INCONCLUSIVE, since nothing writes the setting on stack A, and `FOCCPing.log` (present = the dll loaded;
absent = the loader never ran it) is the next thing to look at. Collect `focc.0.log`, the plugin's own
log `Documents\My Games\Starfield\SFSE\Logs\FOCCPing.log` (CommonLibSF's logger path; as `sfse\FOCCPing.log` in the
folder), the loader's console output and, on `got=0`, `Papyrus.0.log`; judge `b0`. Uninstall the dll (game closed)
before any other experiment.

**Job focc-B0-2b (the setting route, stack B), only if B0-2 fails on 1.16.244 and the library fix does not come.**
The plugin variant tails the `focc` log for `b0 ping sent=N` and writes N + 1 into `iFOCC_Pong` by its name (the
`sfse/FO4SFBorder` mechanism of 24 Oct). Same commands as B0-2 (the `Gmst` first in each launch), with
`cgf "FOCC_B0.Gmst"` a few seconds after each ping: the judge takes every `b0 gmst` between the ping and the next ping
and any read of N + 1 among them is the answer (`value=42`, then `44`; a read that came too early still shows the old
value and does no harm, read again), and only when that answer differs from the value the setting held before the ping (7 before
the 41, 42 before the 43). A repeated ping value, or one whose answer is the value already there, reads the stale
value and is INCONCLUSIVE, never a PASS; on a rerun in the same launch pick a new value (45, 47, ...).

## What each answer settles (for the design)

| Probe | Question | Decided by |
|---|---|---|
| P1 | CC-02: can the bulk state live in a sidecar beside each save (option C' / B)? Orphans? | pass/fail of P1-3; a FAIL on name or load sends CC-02 to option A for the bulk too |
| P2 | CC-02: does location keyword data survive save/load (the floor of C')? Do linked locations persist? | FAIL = holder data goes to GLOBs or quest variables per place |
| P3 | Can our interiors carry a location of ours (interiors D1), parented or not? | FAIL on the unparented one = every LCTN of ours chains to the overlay location |
| P4 | L3: are PlaceAtMe/Delete cycles reliable and save-cheap? | the growth number; FAIL = alias quests or fewer refs |
| P5 | L2 fallback: ms per place per tick; array cap | numbers recorded in docs/ai/optimization.md; cap 128 shapes the Papyrus data layout |
| P6 | Territory spawns from data alone (conditioned LVLN)? | FAIL = script-driven spawns (L3 planner output) instead |
| P7 | Do conditions read our reputation GLOB? (vendor refusal deferred) | FAIL = reputation effects need scripts |
| P8 | Settlement build stages by enable parent, and their save cost | FAIL = stage swaps by script-placed refs |
| P9 | Long-route pathing on the converted navmesh | FAIL = caravans move abstractly and materialize near the player only |
| P10 | SendStoryEvent + our SM branch for radiant quests | FAIL = quests started from script directly |
| B0 | Can Papyrus call our SFSE plugin and read its answer on 1.16.244 (the C++ port's bridge)? | PASS on stack A = CommonLibSF natives; PASS on B only = the setting bridge; FAIL of B0-1 = no return leg for B |

## What to send back, always

1. The pasted output of every block, with the `$LASTEXITCODE` numbers.
2. The collected folder's text files (logs, `saves.json`, `plan.json`, compile files, verdict JSON): no saves, no
   plugins, no dll; the lead strips user paths before anything is quoted in the repo.
3. The ids chosen on the PC (`--lvln-b`, `--stat`, the P9 direction and actor id).
4. `Data\FO4SFCombinedProbe.install.json` after install and the `status` output after the first load.

Left out: nothing is run here; every expectation above is the plan's contract, and the first PC run is what makes any
of it a fact.
