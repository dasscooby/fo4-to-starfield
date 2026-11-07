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
(samples before it show an actor not yet commanded). A failure requires a loaded stall (dist within 2 m for 120 s)
or a timeout in the first cell. A sample with the player closer than 35 m breaks the stall window and makes
the first-cell timeout inconclusive on its own, however brief the proximity (one near sample is enough; the
reason counts the near samples and seconds inside those 600 s; a near sample after them excuses nothing: a knob for
the owner, reviews of 10b58dd1 and 5f0dd2b0). An unloaded sample breaks
the stall window too, and the window starts again at the next loaded, far sample. Either failure also requires proof that the command moves this
actor: it came at least 20 m closer on
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

**The package driver (job focc-P9p, Claude, 1 Nov 2026).** The next driver the card named: a package on a quest alias,
the way the game moves its own actors. Building a PACK record is not needed. Starfield.esm already has
`DefaultTraveltoLinkedRef` (`212FDB`): on the Travel template (`2CB0`, 1,023 of the master's 3,548 packages use it),
its location is "near linked ref" with no keyword, and it has no conditions (read from Starfield.esm 1.16.244 on the
PC; xEdit's TES5/FO4 meaning of PLDT type 6, **supported**). The probe quest gets alias 0, `P9Walker`: empty, optional,
allow reserved, with that package as its only one. `FOCC_P9Drive.Travel <id> <toPlayer>` logs `p9 go ... driver=package`
first, then sets the actor's linked ref to the target, forces the actor into the alias and calls `EvaluatePackage`.
Two seconds later it logs `p9 package ... package=<id>`: `2174939` (`212FDB`) when the alias package took.
`FOCC_P9Drive.TravelEnd <id>` clears the alias and the link. All five script calls are declared in Starfield's own
sources (ContentResources.zip on the PC). Whether an alias package outranks the citizen's own packages in game is
**unverified**: that is what this rung tests.

The ladder is the same as the card's, with Travel in place of Go:

```
rung a   cgf "FOCC_Probe.P9Dest" 0.0 0.0 ; cgf "FOCC_Probe.P9Track" <id> 60                        (no command)
rung b   cgf "FOCC_Probe.P9Track" <id> 60 ; cgf "FOCC_P9Drive.Travel" <id> 1                         (to the player)
rung c+  cgf "FOCC_Probe.P9Dest" <dx> 0.0 ; cgf "FOCC_Probe.P9Track" <id> <T> ; cgf "FOCC_P9Drive.Travel" <id> 0
end      cgf "FOCC_P9Drive.TravelEnd" <id>
```

How the judge reads it:
- A package rung has no return line. A `p9 path returned` line is never paired with its go, even when it carries the
  same call=.
- Unless that go's own `p9 package` line (same actor and call=) names `212FDB`, the rung is INCONCLUSIVE whatever
  the samples show. The reason says which case it is: no such line, `package=none` (the actor ran no package), an
  unreadable id, or another package (the alias did not take).
- Only a package rung whose own `p9 package` line names `212FDB` can stand as a package rung's control. A scripted
  PathToReference control proves nothing about a package, and the reverse holds too.
- Everything else is as for Go: the walk's clock and distance start at the go, samples must be continuous, and the
  verdict is the latest rung's.

`tests/test_combined_p9_package.py` covers these rules on synthetic logs.

Run it in a session whose probe quest was started with this plugin installed: a `coc` from the main menu (as the PC's
P9 session scripts do), or a save made after the install. In a save from before, the quest is already running
without alias 0. Then `Travel` logs `p9 go refused ... walker=False`, a clean refusal rather than a verdict
(**unverified** how the engine treats an alias added to a running quest; #663 review).

**In game, 1 Nov 2026 (kit `70159f58`, test folder `focc_P9p_20261101_1334`, #644):** INCONCLUSIVE. Two seconds after
each `Travel` go, `GetCurrentPackage` named Starfield's default master packages, never `212FDB`:
`DefaultMaster_FollowPackage` (`301C5`) to the player, `DefaultMaster_PatrolPackage` (`301C3`) to the marker
(`DefaultMaster_FallbackPackage`, `4FB2B`, before the first go). Yet the actor walked every rung: 18 m in 5 s, 21 m in
18 s, 100 m in 75 s, and 330 m in 294 s, unloaded in 79 of 130 samples. Supported hypothesis: the linked ref alone
starts those default packages, and the alias package never ran.

**The linked-ref driver (job focc-P9l).** That reading, tested on its own. `FOCC_P9Drive.Link <id> <toPlayer>` logs
`p9 go ... driver=link`, then sets the actor's linked ref to the target and calls `EvaluatePackage`, with no alias.
Two seconds later it logs `p9 package`. `LinkEnd <id>` clears the link. The ladder:

```
rung a   cgf "FOCC_Probe.P9Dest" 0.0 0.0 ; cgf "FOCC_Probe.P9Track" <id> 60                     (no command)
rung b   cgf "FOCC_Probe.P9Track" <id> 60 ; cgf "FOCC_P9Drive.Link" <id> 1                         (to the player)
rung c   cgf "FOCC_Probe.P9Dest" 20.0 0.0 ; cgf "FOCC_Probe.P9Track" <id> 120 ; cgf "FOCC_P9Drive.Link" <id> 0
rung L   cgf "FOCC_Probe.P9Dest" 440.0 0.0 ; cgf "FOCC_Probe.P9Track" <id> 600 ;
         cgf "FOCC_P9Drive.Link" <id> 0 ; cgf "FOCC_P9Drive.Shadow" <id> 600 25.0            (about 440 m east)
end      cgf "FOCC_P9Drive.LinkEnd" <id>
```

`Shadow` waits 3 s, then sets the player 25 m short of the actor along -X, 5 m up, every 5 s, so the actor stays
loaded. The first run's hops, typed in the console batch, closed the console, and the batch's closing key reopened it,
pausing the game (1 Nov, #644): the wait lets the batch close it first. A session should still check that the game's
scripts run after each batch (the bridge heartbeat moves) and close the console only if they do not. The 330 m
walk was unloaded in most samples, which the judge's continuity check refuses. Shadow moves only the player.

The judge treats `driver=link` like the package driver:
- the rung's `p9 package` line must name `DefaultMaster_PatrolPackage` for a go to the marker, or
  `DefaultMaster_FollowPackage` for a go to the player;
- the control must be a link rung whose own line names its target's package;
- go targets are compared without case, since Papyrus logged `target=Player` on the PC.

Rung c is the control the judge can use. Rung b to the player arrives in seconds, and P9Track stops under 10 m, so it
leaves one sample: too few for continuity (1 Nov run; #663 review). Rung c's 20 m walk to the marker left seven.
`Shadow` keeps hopping the player until its seconds run out, even after the track ends at arrival; let it finish.
The long rung starts about 420 m out (the marker 440 m east of the player, the actor about 20 m east after rung c;
P9 needs 400 m or more). Correction (#663 review): the 1 Nov 435 m link rung did not run out of time. Its actor stood
1.7 m from the marker across the ground from about 500 s on, 26.8 m under it, because `P9Dest` left the marker at the
player's height where the land falls, and P9Track measures in 3D. `P9Dest` now calls `MoveToNearestNavmeshLocation`
after placing the marker and logs `snapped_dz=`. That is **unverified for a far marker**: every long rung's go logged
`targetcell=None`, so the marker's cell was not loaded when it was placed, and the snap may have no navmesh to find
(#663 review). Before the track, read `snapped_dz=` on the `p9 dest` line: 0 on a sloped route means the marker still
floats. A sure fallback is to stand the player at the target (hops of 300 m or less), run `P9Dest 0.0 0.0` there,
where the cell is loaded and the marker lands on the ground, then hop back. Meanwhile the judge never calls a floating
marker a FAIL: when the actor came within the arrival distance across the ground and the 3D distance did not, the
verdict is INCONCLUSIVE and names the height (1 Nov rerun: 420 m, 5 cells, 9.6 m across the ground 442 s in, the marker
31 m up). The actor that walked rungs b
and c is the one
judged.

### P9u: the actor comes to the player from beyond the loaded area (owner's design, 1 Nov 2026)

Run it after the loaded walk (P9 with `Shadow`) passes on the same kit. Each new driver follows the same order: loaded
first, then unloaded (owner, 1 Nov 2026).

The player stays at the start. `P9Dest 0.0 0.0` puts the marker on the ground at the player's feet, where the cell is
loaded and the snap works. The player then hops 660 m east, 220 m at a time with `tgm` (up to z 250 and a fall:
z 140 was checked to 440 m out on 1 Nov, the ground farther out was not), spawns the actor there and reads its id. `P9Track <id> 900` and `FOCC_P9Drive.Link <id> 0` run while the actor is still loaded, so its
`p9 package` line can name `DefaultMaster_PatrolPackage`; without that line the session skips the wait. Then the
player hops back and waits, with no `Shadow`. The kit is P9's; only the judge and the session change.

Judge `probes p9u`, which never says FAIL:
- PASS: a link driver whose package took, a go to the tracked marker (the probe's own FOCC_P9_Dest) 400 m or more
  out, whole samples (rt, actor, dist and pos on every one: a sample with one missing or unreadable refuses the
  judgement, since the skipped row may be the jump; a line torn ahead of its kind is a gap, which the rate gate
  takes as a gap) that run forward in time, the first within 2 m plus 15 m/s of the go's distance
  for the time since the go, with no step faster than 15 m/s (`p9_jump_m_per_s`, as P9), 100 m or more of progress
  toward the marker between samples that both read unloaded (`p9u_unloaded_m`) up to the arrival, and a sample
  under 10 m within 900 s of the go (`p9u_seconds`), or 2 s per metre of the go's distance when that is longer
  (`p9u_s_per_m`: 1800 s from 900 m). Progress after the arrival, or outside the window, is the actor's later
  behaviour, not this travel (review of eada2c28: four gaps found by synthetic tracks, each now a test).
- INCONCLUSIVE otherwise, with the reason. The reason may be jumps (an engine that moves an unloaded actor abstractly,
  or only when it loads again, which is what positions that froze while unloaded end in), too little travel while
  unloaded, or no arrival in time. None of these is about the converted navmesh, which P9 judges with the actor
  loaded.

Why 100 m and 660 m: on 1 Nov the package rung's actor read unloaded from about 270 m from the player, and its
positions kept moving smoothly while unloaded. The actor also walks while the player hops back (about 53 s a hop on
1 Nov), and stays loaded until the player is two hops away: about 55-80 m. A 440 m start would leave about 100 m
unloaded, right at the bar (review of 861714e0); 660 m leaves about 300 m, and 900 s still covers the walk at the
1 Nov pace of about 1.1 m/s.

Cost: the session also logs the game's CPU and memory by phase (a read-only sampler beside the session). The judge
reports the tracker's sample gaps (`sample_gap_s`: median, p90, max): the tracker asks for a sample every 2 s, so
longer gaps are Papyrus running late. The console pauses during the hops back stretch a few gaps; read the median and
p90. Quote both with the result and compare them with the loaded run. What an off-screen world costs is the
next question as the tests grow (owner, 1 Nov 2026).

### P11: far travel, materialize and hand back with continuity (card, 6 Nov 2026; nothing written or run)

Settles: **CC-63**'s far-travel layer (`src/fo4sf/combined/travel.py`, #674). L2 owns a travelling squad's position
outside the loaded area; L3 creates the real actor at that position inside 400 m (`MATERIALIZE_M`), hands it to the
P9 link walk, removes it only beyond 500 m (`DISSOLVE_M`) and takes its progress back. P11 asks whether that loop
keeps one squad as one actor on one line, with no jump and no second copy, and with progress that follows the
handed-back eta plus the elapsed hours (within the one-hour rounding of `eta_from_progress`), in the game.

Status: a card only. No kit script, session or judge exists for it yet, and none is in this PR. The native run
needs a fresh owner release and runs on the PC (Claude PC). P9 and P9u passes do not stand in for it. P11 is not
a gate for port steps 4 or 6 (FAL-9); it gates using `travel.py` in game. Straight line only: the hand-back projects
onto the line between the two anchors, an approximation CC-63 records (a multi-hop route and the navmesh path are
not that line). Travel between worldspaces is CC-64, not P11.

Kit, P9's with two additions (both to write): a marker the session can place at given world x/y and snap to the
ground (P9Dest already does this relative to the player), and a dissolve command that deletes the tracked actor and
logs its last x/y (P4's `Disable` and `Delete` are the primitive; P4 logs only cycle counts, so the position line
is new). The driver stays `FOCC_P9Drive.Link`; no alias package, no `PathToReference`.
L2 is played offline by the session: a two-place atlas (A and B, on the measured P9 route east of Red Rocket, so the
navmesh is known to walk), one travelling squad, and `travel.simulated_position` for the game hour the session reads.

Legs, in one launch, at Red Rocket, `tgm`:
1. **Out of band.** The player stands more than 500 m from the squad's simulated position. Nothing is spawned.
2. **Materialize.** The player hops toward the simulated position. At the first hop that leaves the player within
   400 m of it, the session places the marker there and spawns the actor (`p11 spawn` with the simulated x/y, the
   actor's x/y/z and the player distance), then `P9Track` and `Link` toward B's marker.
3. **Hand-over.** The loaded walk, judged as P9's samples: forward in time, whole, no step faster than 15 m/s, and
   the go's `p9 package` line naming `DefaultMaster_PatrolPackage`, as the P9 link judge requires.
4. **Dissolve.** The player hops away. At the first sample with the player more than 500 m from the actor, the
   session dissolves it (`p11 dissolve` with its last x/y). Offline: `progress_from_position(A, B, last)` gives f,
   and `eta_from_progress` the new eta.
5. **Re-materialize.** After a wait of at least one game hour the player hops back inside 400 m. The session recomputes
   the simulated position from the new eta and spawns again (step 2's line).

Judge `probes p11` (to write), proposed bars for review:
- PASS: every spawn within 400 m of the player (player to simulated position, the only distance before a spawn)
  and at the snapped marker; the dissolve beyond 500 m (player to the live actor) and only there; P9's sample rules
  through the walk, with the Patrol package line; never two live actors for the squad (the first id reads deleted
  before the second spawn); after the wait of at least one game hour, the second spawn's progress at least the
  dissolve's f, not above `min(1, f + elapsed / route_hours)`, and at most one route hour behind it (the ceil in
  `eta_from_progress`). The judge reports the marker's x/y against the simulated x/y.
- FAIL: two live actors for one squad at any sample; progress going backwards at the re-materialize; a spawn
  outside 400 m or a dissolve inside 500 m.
- INCONCLUSIVE: a spawn that never loads; a large snap of the marker from the simulated x/y
  (`MoveToNearestNavmeshLocation` can move a point off the walked road, and P9 already treats an unverified snap as
  INCONCLUSIVE); a missing or other package line; a torn or missing sample; a missing dissolve line; or the walk
  stopped by the near-player stops P9 already allows (within 35 m).

Out of P11 (each its own card): a save and a load while the squad is dissolved (P1, and the save-identity card W8);
the materialized actor's death or despawn reaching L2 once (the encounter-conservation card W7); more than one squad,
which is the open load-scaling probe; routes with more than one hop.

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
| P9u | Does a linked actor travel to the player from beyond the loaded area? | never FAIL; INCONCLUSIVE with frozen positions = actors move only once loaded again, so off-screen travel is abstract |
| P11 | Does the far-travel loop keep one squad as one actor on one line (materialize inside 400 m, dissolve beyond 500 m, re-materialize with continuity)? | FAIL = `travel.py` stays offline; a second copy or lost progress needs its fix before any in-game use |
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
