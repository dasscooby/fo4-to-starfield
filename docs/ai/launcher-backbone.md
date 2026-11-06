# Launcher backbone: build manifest, resumable build, recorded restore, same-ids check

Written 2026-10-19 by Claude-cloud. Offline machinery for the GAMMA-style launcher (roadmap middle path: the
build-and-restore backbone and the same-ids check run alongside phases 1 to 3, the launcher itself comes fourth).
Nothing here has run on the PC yet: every result below is a **synthetic-fixture** result, not an in-game or PC one.

Code: `src/fo4sf/launcher/` (manifest, driver, restore, same_ids), CLI `scripts/launcher.py`, example recipe
`scripts/launcher_recipes/core_restage_same_ids.example.json`. Tests: `tests/test_launcher_*.py`.

## What each piece does

| Piece | Command | Reuses | Status |
|---|---|---|---|
| Build manifest | `launcher.py manifest --out m.json --fo4-data <Data> ... --starfield <game> --output <build>` | the checkpoint identity policy (docs/RESUMING-BUILDS.md) | synthetic tests |
| Manifest diff | `launcher.py manifest-diff a.json b.json` (paths ignored, identities and pins compared) | | synthetic tests |
| Build driver | `launcher.py build <recipe.json> --set k=v [--dry-run] [--min-free-gb 40 --disk D:\ ] [--idle]` | wraps make_core64c.py, make_mission.py, convert_batch.py, vmad_patch.py, light_patch.py, the dotnet writers as steps; their own checkpoints stay in charge inside a step | synthetic tests |
| Snapshot | `launcher.py snapshot --starfield <game> --out snap.json` (read only) | every install record (`restore.COMPONENTS`) | synthetic tests |
| Restore | `launcher.py restore --snapshot snap.json` (plan; `--apply` acts) | deploy_starfield.py, exp_install.py, bridge_install.py do every file change | synthetic tests, incl. a real exp_install round trip |
| Build status | `launcher.py status <recipe.json> [--set k=v] [--json out.json]` (read only) | the driver's state.json | synthetic tests |
| Self-update | `launcher.py update [--check]`; setting `update=off/check/pull` (default off) runs it before `play` and `gui` | git: fetch, then fast-forward only (src/fo4sf/launcher/selfupdate.py) | synthetic tests on throwaway git repos |
| FO4SF game folder | `launcher.py instance plan\|create\|run\|recover`; setting `instance` (default empty) makes `play` start it | hard links (same drive), the game folder's INIs copied, only the game's own files in Data; its own Plugins.txt (swapped in only while it runs, journaled), saves and INI; design: docs/ai/fo4sf-instance.md | synthetic tests |
| Same-ids check | `launcher.py same-ids <build A> <build B>` | make_core64c.py's `formids_diff` (compare-ids) when both have formids.json | synthetic tests |

### Build manifest
Inputs: Fallout4.esm and the six DLC masters, found across several Data folders (Steam depots keep DLC apart),
always hashed; missing DLC listed by name (`dlc_missing`); every .ba2 by size and time (`--hash-archives` for
content). Pins: repo commit and dirty flag, Python, numpy, Pillow, dotnet SDK, the Mutagen version of every dotnet
project; Starfield.exe and sfse_loader.exe hashed, Starfield.esm by size and time, Creation Kit and Archive2 presence.
Outputs: every file under each output folder, plugins and json always hashed.

### Build driver
A recipe is a list of steps (argv, inputs, outputs, dependencies, timeout, retries, code paths). State lives in
`<state_dir>/state.json`, written atomically at every transition, with one log per run of a step. A step is reused
only if it last finished with exit 0, its outputs exist and its fingerprint (argv, cwd, input identities, code
content) is unchanged, and no step it depends on ran in this run. Statuses `done`, `reused`, `failed`, `timeout`,
`blocked`, `not_run` are kept apart; `reused` is never counted as new work and only an all-done-or-reused run is
complete (exit 0). A step left `running` by a crash is rerun. One driver per state folder (lock file; `--break-lock`
on purpose only). `--min-free-gb` blocks a step before it starts (the D: 40 GB rule); `--idle` runs steps at Windows
Idle priority. A step may declare `need_gb` (the space it writes); it is blocked unless free space covers the floor
plus that need (the example's stage step says 1 GB, from the measured 0.3 to 1 GiB a staged core costs).
The floor applies to every step about to run, including one rerun only because a step it depends on ran. A step runs in its own process group; on timeout the whole tree is ended (`killpg`, `taskkill /T /F` on Windows), so a `dotnet` a make script started cannot keep writing into the outputs (review pass, 2026-10-20).
A complete run writes the build manifest.

A step with no `code` list is fingerprinted by the import closure of its Python scripts inside the repo (static
imports, resolved against the script's folder and `src/`), not all of `src/fo4sf` as before: an edit to a module
the step never imports no longer reruns it, and a changed helper two imports down still does (framework question
B7). Steps that load code another way (dotnet projects, data files) list it under `code`, as the example recipe
does. A listed code folder skips `bin`, `obj` and other build output (a `dotnet run` step writes `obj/` inside its own project and would otherwise change its own fingerprint), and a listed path that does not exist is a recipe error rather than an empty hash. No speed claim: no PC run measured the difference.

`launcher.py status <recipe>` is the read-only view of the same state (no lock taken, nothing written): each step's
last result, runs, seconds, the log of a step that did not finish well, whether a driver holds the folder, and what a
run now would do. A step recorded `running` while no driver holds the lock shows as `interrupted`. This is what the
launcher's progress screen and the install thread read instead of opening state.json by hand.

### Recorded restore
`snapshot` keeps Plugins.txt byte for byte, every top-level plugin and archive in Data (plugins hashed; Starfield's
own archives by size and time) and every install record verbatim: the port, the experiment, the planet, quest and
combined probes, the map markers and the bridge (the probes and the markers since 2026-10-31; before, the markers'
Plugins.txt line read as an owner's edit and every restore with them installed was refused). `restore` plans in the
swap scripts' uninstall order (bridge off, markers off, the probes off, experiment off, port off); installation
puts the target experiment/core back first, then restores the port and its riders. When both are reinstalled,
`exp_install.py order` waits until the port is back, because an experiment plugin can master FO4Port.esm.
A source folder that is gone is a conflict (the `--port-staging` folder too). Before any uninstall, staged input
inventories and marker/quest-probe pins are checked against the target receipts; legacy experiment records without
`source_inputs` are noted as unverified. Bridge-kit receipts without inventories refuse reinstallation because their
staged inputs cannot be checked against the snapshot. Stages must remain unchanged until apply finishes. The markers
and the combined probe ride on the experiment and the quest probe on the port
(`restore.RIDES_ON`: their installers pin that build), so when the base changes they come off first and go back on
after it, even with their own record unchanged; a snapshot that keeps a rider while restore would uninstall its base
is refused before anything runs (its installer would refuse to put it back once the base is gone). So is any change
while `plugin_toggle.py` holds a plugin off (the launcher's bridge=off, a crash split; the snapshot keeps the hold as
`held`): the installers refuse under a hold, and only `plugin_toggle.py on` may tick a held line again. The hold
record that `on` leaves empty is not counted as a difference. It restores Plugins.txt bytes only when every differing line names a plugin an
installer owns. It never deletes a file itself, leaves unowned new files alone (reported), refuses while
Starfield.exe runs, refuses on any conflict before changing anything (an owner's Plugins.txt edit, a vanished
unowned file, a port record with no staging folder unless `--port-staging`), and checks the result against the
snapshot afterwards. An equal install record is not taken as proof: every file a record owns (loose files in
subfolders included) is hashed at snapshot time and must match the hash the record keeps, before and after, or the
restore refuses. That holds for the target too: a snapshot taken while an owned file was changed or missing is refused as a target, and an owned file whose record keeps no hash must come back with the bytes the snapshot saw (Codex review, 2026-10-20). Unhashed archives are compared by size and time. A complete install that keeps
`plugins_restore_pending` set (it owns the later uninstall's Plugins.txt restoration) is healthy and left alone; only
`complete: false` or `cleanup_pending` counts as an interrupted install to recover (Codex review, 2026-10-19). The install thread's swap scripts on the PC are not replaced or touched; this is the same
practice in code, so the launcher can later call it.

Recorded port restore treats `--port-staging` as a source of **prebuilt** plugin/archive files, including complete
texture-companion pairs. An ordinary stage, an interior batch root, or its `port` folder is accepted only when every
recorded size and SHA256 matches before any uninstall; failed/incomplete stage metadata refuses too. Restore passes
the snapshot's artifact and core pins to the deployer over stdin, which checks them again and copies those outputs
without Archive2 or repacking. The core is restored first so the installed core pin can be checked before publishing
the port. Old port receipts without complete artifact identities cannot be replayed automatically. This does not
lock a stage against edits during apply or make multiple installers atomic; keep source folders immutable and retain
the snapshot and installer recovery records after any failure.

### Same-ids check
Level 1 plugin bytes; level 2 a raw record walk (no Mutagen, no load order): FormID set, type and editor id per
FormID, editor ids that moved to another FormID, record-header metadata, record bodies, TES4 header; level 3 the
converter's formids.json through compare-ids. Verdicts IDENTICAL, SAME_IDS (ids equal, explained diff listed),
IDS_DIFFER, INCOMPLETE; exit 0 only for the first two. A changed master list or TES4 header flags (master, light,
medium) is IDS_DIFFER, since both change how the game maps the plugin's FormIDs.

### detect (the launcher's first stage)
`launcher.py detect --fo4-data <Data> ... --starfield <game> --out-dir <drive> --need-gb N` answers "can this PC
build?", read only: Fallout4.esm and each DLC master matched by hash against `scripts/launcher_recipes/known_sources.json`
(unknown versions refused unless `--allow-unknown`), missing DLC named and refused unless `--allow-missing-dlc`,
Starfield.exe, Data, Archive2 and SFSE required (SFSE since the owner's NG-1 answer, 2026-10-19; `--allow-missing-sfse`
reports instead), Creation Kit reported (refused only with `--require-ck`), any `sTestFileN` in Starfield's INIs refused (the game then ignores Plugins.txt), loose files in
the My Games Data folder reported when `--my-games` is given (passed as Windows resolves it, never guessed), and free
space minus the floor (default 40 GB) against the need. Entries come from a real install's build manifest (`sources-add`). On the owner's PC today detect refuses on DLC
(only Automatron and Wasteland Workshop are installed), which is the intended answer.

Runtime gate (owner's answers LA-15, LA-16, NG-1 and RE-12, 2026-10-19). `scripts/launcher_recipes/known_runtimes.json`
lists Starfield.exe builds by sha256, each with the SFSE files measured with it: the loader, and every `sfse_*.dll`
next to it, by hash, with names read from the folder and never assumed. Detect refuses a Starfield.exe that is not
listed ("keep Steam set to update Starfield only when launched until support is published"); `--allow-unknown-runtime`
reports instead. For a listed runtime, an SFSE loader or DLL other than the listed one is refused, and so is a path
under `XboxGames` or `WindowsApps` (Steam only for version 1). An entry is added by
`launcher.py runtimes-add --manifest <manifest of a real install> [--label <text>]`, which refuses a manifest without a
hashed Starfield.exe or without SFSE. Since 2026-10-22 the table lists one runtime: Steam Starfield.exe 1.16.244.0
with SFSE 0.2.21, measured on the owner's PC (below); every other Starfield.exe is refused. Play's default route
(`sfse`) checks the same table before it changes anything or starts the game. The build manifest now records the `sfse_*.dll` hashes too, and Starfield.exe's own file and
product version from its version resource (`game.exe_version`); without `--label`, runtimes-add names the entry
"Steam, Starfield.exe <file version>". An `sfse_*.dll` the listed build lacks is refused as well.

Work folders (A6): detect refuses an `--out-dir` that is a drive root or sits under Program Files, Windows,
ProgramData, OneDrive or the Users folder, as Wabbajack and GAMMA do (Controlled Folder Access guards Documents and
Desktop and has blocked `make_bridge.py` once). The owner's `D:\Modding` and `C:\Modding` folders pass.

### find
`launcher.py find [--steam <Steam folder>]` finds Steam's Fallout 4 and Starfield the way MO2 does: SteamPath from
`HKCU\Software\Valve\Steam`, the libraries from `config\libraryfolders.vdf` (and the old `steamapps` copy), and each
game from `steamapps\appmanifest_<appid>.acf` ("installdir" under `steamapps\common`; 377160 Fallout 4, 1716740
Starfield). Depot downloads under `steamapps\content\app_377160\depot_*` are listed in depot-number order, the
fixed merge order of the owner's LA-4 answer, and it prints the detect line to run. Read only. When Steam has no
Fallout 4, GOG's is used (LA-5: Steam, then GOG), found the way LOOT does (`HKLM\Software\GOG.com\Games\1998527297`
"path", else the uninstall key's "InstallLocation") or given with `--gog`. The VDF reader and the paths are tested on
synthetic files only; neither registry lookup has run on a real Windows install.

### bundle
`launcher.py bundle --out <support.zip> [--state-dir ...] [--manifest ...] [--detect-report ...] [--starfield ...]
[--my-games ...]` writes one local zip for a GitHub issue (framework A11; the owner's RE-18 answer, GitHub only):
driver state and each step's newest log, the build manifest and detect report, every install record,
Plugins.txt, and the game's INIs from the game folder and My Games. Text only, no game data. The home folder becomes
`%USERPROFILE%` and the user name `<user>`, in either slash style and JSON's doubled backslashes; a name under three
letters is left alone so ordinary words survive. A file over 2 MiB keeps its tail and says so. BUNDLE.txt lists
what is inside and what was looked for and not found. Nothing is sent, and an existing zip is never overwritten.

### check-plugins
`launcher.py check-plugins <build folder> [--starfield-data <Starfield\Data>]` reads each built plugin's TES4 header
only and refuses `BlueprintShips-Starfield.esm` as a master (blueprint plugins load last and cannot be depended on,
framework T7), a plugin that lists itself, and a master that is neither in the build nor in the given Data folder (no
list of the game's own masters is assumed; without the folder only Starfield.esm counts). Read only; exit 1 on a
problem.

### measure
`launcher.py measure <folder>` gives a folder's real disk cost with hard links counted once and the part shared with
other folders split out, so "deleting this frees N GB" is a number, not a guess (staged builds hard-link Data from the
work folders). This is the measuring half of the unresolved full-build disk budget.

### settings and play (crash watcher that follows the game)
Owner, 2026-10-21: the crash watcher should start and close with the game, and the launcher is where its toggle and
other memory-costly settings live. `launcher.py settings` shows each setting with its cost and `--set key=value`
changes it (one JSON per player, default `%LOCALAPPDATA%\FO4SF\launcher_settings.json`; only changed values are
written, and an unknown key is refused). The defaults leave the watcher off and bridge and Papyrus logging
`unchanged`; two defaults act: `load_order=fix` (below) can rewrite Plugins.txt before a start, and `route=sfse`
starts through SFSE. `launcher.py play --starfield <game dir>` applies `bridge` (through plugin_toggle.py) and
`papyrus_logging` (the three `[Papyrus]` keys in StarfieldCustom.ini, with a `.bak-<time>` copy) with the game closed,
starts the game (`route`: Steam, as the runner does, Starfield.exe, as the owner does, or sfse_loader.exe, which loads SFSE), waits until a
Starfield.exe has stayed up `crash_watch.settle_s` (a first process that ends within that time is skipped), then
attaches ProcDump to that process id with the old watcher's triggers (`-e 1 -f 80000003`), `-mm` by default
(`crash_watch.dump=full` for `-ma`), `-t` by default (`crash_watch.dump_on_exit`, the owner's choice on 2026-10-21, so a kill or a silent exit leaves a
mini dump; a normal quit writes none, ProcDump reports "Dump count not reached"; `launcher.py settings` lists it as "Crash dump on every exit (off = log only)", and
`--set crash_watch.dump_on_exit=off` gives log only). It holds its own handle on the game and writes the exit
code and its name, and the dumps of that run, to `crashwatch.log`, so a silent exit leaves at least its code.
ProcDump ends on its own with the game and is never killed. The flow is tested with a stand-in
(`tests/test_launcher_crashwatch.py`). On the owner's PC (2026-10-21, automated walk test) `watch` found the game by
process id, armed ProcDump with `-e 1 -f 80000003 -t` together, caught a 0xC0000005 ACCESS_VIOLATION and wrote two
145 MB mini dumps. Not yet run on Windows: `play`'s own game start (Steam or exe) and its bridge and Papyrus changes.

Before the start, `play` also puts our plugins in one target order (`load_order`, default `fix`; `check` refuses a
different order, `off` leaves Plugins.txt alone) through `scripts/game/load_order.py`. Since 2026-10-28 the target is
the order the test runner's own tools leave (file order kept, every plugin after its masters, FO4SFMapMarkers after
everything else and FO4SFBridge last), so play changes nothing on a file they just wrote; an unticked line stays
unticked. The order the game itself wrote on the owner's PC on 2026-10-22 is in the target too, so a rewrite by the
game should change nothing; the start and exit comparison in crashwatch.log shows whether it does. Since
2026-10-22 the default `route` is `sfse` (SFSE is required, NG-1), and Starfield.exe 1.16.244.0 with SFSE 0.2.21 is
the listed runtime.

`launcher.py watch` is the same watcher for a game it did not start, such as the test runner's own Steam launch: it
waits for Starfield.exe (or `--pid N`), attaches after `settle_s` with the same ProcDump line, and logs the end;
`--repeat` follows each next game of a queue until none appears within `--timeout` (600 s). It changes no setting,
and it refuses while `crash_watch.enabled` is off, so the owner's toggle still decides.

### Determinism variants (framework B5)
`tests/test_determinism_variants.py` runs a static mesh conversion and the driver's step fingerprint in fresh
interpreters under string-hash seeds 0, 1, 4242 and 7, a German locale and `NPY_DISABLE_CPU_FEATURES="AVX2 AVX512F"`,
and requires the same bytes from each. `convert_static` does not import numpy today, so the numpy variant guards only
against a future import. A second machine (L4's real half) is still untested.

### Mod manifests (draft v0, plan task L2)
`src/fo4sf/launcher/mods.py`: a mod declares id, version, the core version range it needs, an optional exact Starfield
pin, its plugins, `requires` and `load_after`. `resolve` puts the core's plugins first, then mods in dependency order
with ties broken by id (the same order on every PC), and refuses with every reason at once: a missing requirement, a
cycle, a core or Starfield version mismatch, a duplicate id, a plugin claimed twice or claimed from the core. Not
wired to any install yet; the format is for the talk (it targets a core master that does not exist yet).

## First PC run (read-only and staged only; needs the install thread)

1. **Done 2026-10-19 14:40Z (verified, read only):** `same-ids` on the two staged core plugins
   `D:\Modding\staging\terrain_core64v6c\FO4TerrainCore.esm` (sha256 7030ceed...) and
   `...\terrain_core64v6e\FO4TerrainCore.esm` (0ab3cb29...), copied into the cloud session and deleted after.
   683,870 records each, the same FormID set, no editor id moved, no metadata or TES4 difference; 4 records differ:
   `010027A0 FO4Core_redrpeddoor` is DOOR in v6c and STAT in v6e (the side-door rig turned off, same FormID), and
   the bodies of REFRs `0100C94C`, `0100D9B8`, `0100D9B9` (Red Rocket door references). Verdict IDS_DIFFER, because a
   record that changes type under the same FormID is not the same id to a save; for these two builds that is the
   intended v6e change, not non-determinism (the inputs differ). 19 s for 194 MB in the cloud.
   The hard-linked Mars plugin and formids.json could not be copied (the folder tool refuses hard links), so level 3
   (compare-ids) ran only on the PC earlier ("identical", per the install thread).
2. **Done 2026-10-19 15:05 to 15:09Z on the PC (verified; install thread, Idle priority, nothing installed):** the
   example recipe at 0a8928e (launcher.py b783d89a, recipe 628ea6d1 checked) re-staged v6e from its own inputs into
   `D:\Modding\staging\det_v6e_b`. `core-restage-same-ids: COMPLETE {'done': 4}`, 235 s; check "268 of 268 checks
   ok, CHECK PASS"; compare-ids against terrain_core64v6e identical in every section (refs 624,369, bases 11,768,
   navmeshes 12,104, items 12,616, lights 6,249, doors 15, and the rest); same-ids **IDENTICAL** for
   FO4TerrainCore.esm and FO4TerrainCore_Mars.esm, every formids.json section identical. The stage ran with the
   scripts at 0a8928e rather than v6e's 5a93beb and still came out byte-identical. So on one PC, the same inputs give
   byte-identical core plugins. The first attempt stopped at check (265 of 266, "Starfield.esm needed for the vanilla
   record check"): the example's check step lacked --sf-data and --fo4; fixed in the example since. det_v6e_b (mostly
   hard links) and the worktree stay on D: because the PC refuses our deletes; about 62 GB free.
3. Later, on a second machine (or a clean second checkout path on the same PC), the same recipe: the cross-machine
   half of plan task L4.

## PC numbers, 2026-10-19 16:3xZ (verified, read only, ffe8f4e)

- **Known version table seeded** from the PC's manifest: Fallout4.esm 330,745,373 bytes sha256 ae7be31a...,
  DLCRobot.esm 8,012,051 e71e04ac..., DLCworkshop01.esm 633,592 82914c20... (Steam depots 377163, 435871, 435880). The
  "1.10.163" label is what the research notes say about this depot, not read from the file (unresolved).
- **detect on the PC:** NOT READY, refused only on the four missing DLC (Far Harbor, Contraptions, Vault-Tec,
  Nuka-World); Archive2 yes, Creation Kit yes, SFSE no; D: 42.0 GB free with 40 kept free, so 2.0 GB usable.
- **Real disk cost of staged core builds** (measure, hard links counted once):

| Folder | Files | Listed | Shared with other folders | Deleting frees |
|---|---|---|---|---|
| terrain_core64v6e | 52,550 | 4.45 GiB | 4.15 GiB | 0.30 GiB |
| det_v6e_b (the determinism re-stage) | 52,560 | 4.45 GiB | 3.50 GiB | 0.95 GiB |
| terrain_core64c_work_v6c2 (work folder) | 64,707 | 4.49 GiB | 4.09 GiB | 0.40 GiB |
| terrain_core64v6e_l125_mission_wfc10 | 52,604 | 4.47 GiB | 0.00 GiB | 4.47 GiB |

  A staged core shares nearly all its Data with the work folder, so a new staged build costs about 0.3 to 1 GiB, but
  the `_l125_mission` fold makes a full 4.5 GiB copy. Linking the fold's Data the way stage does would save about
  4 GiB per fold build (a make_mission.py change for its owner, not done here). For the owner's delete list: the
  fold folders free the most; det_v6e_b frees under 1 GiB.

### Starfield runtime on the owner's PC (2026-10-21 01:1xZ, read only, manifests at 434e8ef and ccc31a1)
Steam, Starfield.exe file and product version 1.16.244.0, 102,476,200 bytes, sha256
`7e9adb1414a8e1b325e5e1f097b9b17b78deb7eebeda37a333351a43a60f9d28`. No SFSE (no loader, no `sfse_*.dll`); Creation
Kit present. On 2026-10-22 SFSE 0.2.21 was installed from Nexus mod 106 (archive sha256
`6f196112b0f283c154e8899df4cadf71e40507ddce9e3954b50f6abb766c91ec`; both binaries signed CN=Ian Patterson):
`sfse_loader.exe` 68,600 bytes, sha256 `16916c2ec47e31774e3d550609a1844fcb368b03060c03511891564b7f5f7526`, and
`sfse_1_16_244.dll` 116,216 bytes, sha256 `28c5bda41d9959c885efcb6e889de69e92767c80a1a66842d711d215f722f82b`. That
pair, with this Starfield.exe, is the runtime listed in `known_runtimes.json` (built through `runtimes.add_runtime`
from these measurements; a detect run on the PC confirms the match).

## Alternatives for the owner's talk

1. **Driver: recipe over existing scripts (taken)** vs one Python build graph that imports the converters directly.
   The graph gives finer caching but rewrites the entry points the install thread uses every night; the recipe can
   be replaced step by step later. A third option, Make or another build tool, adds a dependency players must install.
2. **Restore: our installers plus a snapshot (taken)** vs a Mod Organizer 2 profile / virtual file system vs a
   Stock-Game copy of Starfield. MO2 keeps Data clean but is untested with Starfield at this size (unresolved); a
   Stock-Game copy costs well over 100 GB on a drive that keeps 40 GB free. The snapshot route can export to MO2 later.
3. **Same-ids: raw record walk in Python (taken)** vs a C# check with Mutagen vs Spriggit text dumps. Mutagen would
   parse every field but needs a load order and puts the check under GPL-3 binaries; the raw walk needs only the
   header layout both games share and runs in CI. Spriggit would give readable diffs; worth a look when a real diff
   needs explaining (licence not checked).
4. **Archive identity: size and time (taken)** vs full hashes. Hashing all FO4 and DLC archives is tens of GB of
   reads per build; `--hash-archives` exists for a release check.
5. **Where restore lives:** a launcher verb on the player's PC (taken) vs keeping the hand-run swap scripts. The
   scripts stay as they are until the owner decides; the launcher calls the same installers.

## Not done and unresolved
- No PC run yet; no cross-machine run (L4's real half).
- INIs are watched (`--watch`), reported if changed, never written: no installer changes an INI today.
- Release licensing (GPL-3 for shipped Mutagen binaries) is unaffected by this code (no C#), and stays a release task.
