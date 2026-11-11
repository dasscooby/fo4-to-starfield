> **Record of a withdrawn guide (October 2026):** nothing is offered for download or play. The project's goal is in the [README](../README.md); its status is in [ROADMAP.md](ROADMAP.md).

# Play and test the port: a guide for newcomers

> **Withdrawn for now (owner, 19 Oct 2026).** The project is not offered for download or play, for legal reasons and so
> nobody's hopes are raised early. This page is kept as a record of the procedure; please do not follow it until the
> owner says the project is open again.

You found the Fallout 4 to Starfield project and want to try it. This page takes you from download to walking around
the converted Commonwealth in Starfield, and to sending a useful report when something is wrong.

Read this first: **the port is an unfinished research build.** The Commonwealth exterior, 16 interiors and some doors
run natively in Starfield, but there is no quest, no story start and no one-click installer. What works and what
doesn't is in the [README](../README.md#latest-progress--2026-10-17), the [roadmap](ROADMAP.md) and the live list of
playtest findings, [docs/owner/playtest-issues.md](owner/playtest-issues.md).

**Nothing converted is downloadable.** The repository holds code and documentation only. The converters read *your own*
copies of both games and write the converted files on your PC. No game files, converted plugins or archives are
published, and none may be uploaded to issues or pull requests (see [Safety](../README.md#safety-and-project-rules)).

## 1. What you need

| Need | Version | Why |
|---|---|---|
| Windows PC | 10 or 11 | The install and test scripts are PowerShell and Windows Python. |
| Fallout 4 (Steam) | **1.10.163**, with all DLC | Only its data is read. The port assumes every DLC of both games. |
| Starfield (Steam) | **1.16.244** | The Microsoft Store / Game Pass build is not supported. |
| Starfield Creation Kit | Steam app 2722710 | Its `Archive2` packs the converted files into `.ba2` archives. |
| Python | 3.12 or newer, with numpy and Pillow | The converters and installers. |
| .NET SDK | 9.x | The plugin writers in `dotnet/`. |
| `texconv` | the copy shipped in xEdit's `Edit Scripts` | Texture compression. |

The full list, with download links for the optional tools, is [docs/SETUP.md](SETUP.md). Test in a **separate
Starfield save**, never your main one.

## 2. Download

Either download the ZIP (on GitHub: **Code → Download ZIP**, then unzip it somewhere outside your game folders) or clone it:

```powershell
git clone https://github.com/fo4sf/fo4-to-starfield.git
cd fo4-to-starfield
python -m venv ..\fo4sf-venv
..\fo4sf-venv\Scripts\python.exe -m pip install -r requirements-ci.txt
```

Check that the download is complete and working (offline; it touches neither game):

```powershell
..\fo4sf-venv\Scripts\python.exe -m unittest discover -s tests
..\fo4sf-venv\Scripts\python.exe scripts\guard.py
```

**Keep it up to date by itself (a clone only, not the ZIP):** run
`..\fo4sf-venv\Scripts\python.exe scripts\launcher.py settings --set update=pull` once. From then on, `launcher.py
play` and the launcher window fetch GitHub's `main` first, fast-forward your copy, and start again on the new code;
`launcher.py update` does it by hand. It never touches a copy you changed (an edited file, a commit of your own, another
branch), never runs while Starfield runs, and a network problem only prints one line. It updates the tools, not your
built or installed game files. `update=check` only tells you when there is something new; `off` (the default) fetches
nothing.

Then copy `config.example.toml` to `config.toml` and fill in your paths. `work_dir` and `staging_dir` must be outside the
repository. If your Fallout 4 `Data` folder has mods in it, point `fo4.data_dirs` at a clean copy of the vanilla files
(base game plus DLC) instead.

## 3. Build your converted files

There is no single build command yet; a launcher that does this is on the [roadmap](ROADMAP.md). Today each part has
its own documented pipeline, and each writes a **staging folder** (a folder holding a plugin and its files) outside the
repository:

| Part | What it gives you | How to build it |
|---|---|---|
| Interiors (`FO4Port.esm`) | Vault 111, Red Rocket, Super Duper Mart, the library and 12 more cells | `scripts/convert_batch.py` per cell; steps in [docs/terrain/interior-backlog.md](terrain/interior-backlog.md) |
| Commonwealth exterior (`FO4TerrainCore.esm`, `FO4TerrainCore_Mars.esm`) | The 64 x 64 cell exterior with its objects and navmesh | The rebuild steps at the end of [docs/terrain/core64c.md](terrain/core64c.md) |
| Observation bridge (`FO4SFBridge.esm`) | Lets the report tool and the test runner read your position and cell | `scripts/bridge/make_bridge.py stage` (the plugin plus its compiled Papyrus script); steps in section 4 |

Expect this part to take time and to need the tools in section 1. If you only want to report what you see, you can skip
building and help by reviewing screenshots and evidence in [issue #32](https://github.com/fo4sf/fo4-to-starfield/issues/32).

## 4. Install and turn it on

Every installer is reversible: it refuses to overwrite existing files, writes a record of what it added into Starfield's
`Data` folder, and its `uninstall` removes exactly that. Close Starfield first. In PowerShell, from the repository folder:

```powershell
$py = '..\fo4sf-venv\Scripts\python.exe'
$sf = '<your Starfield folder, e.g. D:\SteamLibrary\steamapps\common\Starfield>'
```

Interiors (packs the archives with Archive2, copies them and `FO4Port.esm`, and switches the plugin on in `Plugins.txt`):

```powershell
& $py scripts\deploy_starfield.py install --staging "<interior staging folder>" --starfield $sf
```

The exterior, or any other experiment folder (only the plugins named after `--plugins` are switched on):

```powershell
& $py scripts\game\exp_install.py install --exp-dir "<exterior staging folder>" --starfield $sf --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --pack
```

The observation bridge (optional; the report kit and the test runner use it to read your position and cell). Build
its staging folder first. This writes the plugin and compiles its Papyrus script with the Creation Kit's compiler and
base scripts (both come with the Creation Kit, in Starfield's `Tools` folder):

```powershell
& $py scripts\bridge\make_bridge.py stage --out "<bridge staging folder>" --compiler "<Starfield>\Tools\Papyrus Compiler\PapyrusCompiler.exe" --content-resources "<Starfield>\Tools\ContentResources.zip"
& $py scripts\game\bridge_install.py install --dir "<bridge staging folder>" --starfield $sf
```

The bridge writes to Starfield's script log, which is off by default. With the game closed, turn it on:

```powershell
& $py scripts\bridge\make_bridge.py ini --game-dir $sf
```

It adds `bEnableLogging=1`, `bEnableTrace=1` and `bLoadDebugInformation=1` under `[Papyrus]` in `StarfieldCustom.ini` and
keeps a `.bak` copy. If Windows' Controlled Folder Access blocks the write, it says so and names the fallback, the game
folder's own `Starfield.ini`. Then check it works: launch the game, load a save, wait 5 seconds and run

```powershell
& $py scripts\game\bridge_log.py latest
```

It prints one line of JSON. `"ok": true` with a `"pos"` value means the bridge is reporting. `"ok": false` means it
is not; its `"why"` says the reason: no bridge lines yet (the plugin or logging is off) or a newest line too old
(the game is paused, in a menu, or not running).

See what is installed:

```powershell
& $py scripts\game\exp_install.py status --starfield $sf
& $py scripts\game\bridge_install.py status --starfield $sf
```

When Starfield starts and shows a **"load order changed"** dialog, choose **Current**. Saving that dialog can switch the
port's plugins off. After you have loaded a save, close the game and check that they stayed on (0 means all active,
8 means some were switched off):

```powershell
& $py scripts\game\exp_install.py active --starfield $sf
```

Take everything off again:

```powershell
& $py scripts\game\exp_install.py uninstall --starfield $sf
& $py scripts\game\bridge_install.py uninstall --starfield $sf
& $py scripts\deploy_starfield.py uninstall --starfield $sf
```

## 5. Play

Start Starfield from Steam (or `Start-Process "steam://rungameid/1716740"` in PowerShell) and load your test save. The
converted places are reached from the console: press the key left of **1** to open it, type one line, press Enter,
and press the same key to close it.

| Where | Console line |
|---|---|
| Red Rocket, outside (the exterior's arrival point) | `coc FO4Core_RedRocketSpawn` |
| Vault 111 | `coc FO4Port_Vault111Cryo` |
| Super Duper Mart | `coc FO4Port_SuperDuperMart01` |
| Red Rocket cave | `coc FO4Port_RedRocket01` |
| Boston Public Library | `coc FO4Port_BostonPublicLibrary02` |
| Vault 81 | `coc FO4Port_Vault81` |
| Parsons State | `coc FO4Port_ParsonsState01` |

The full list of 16 interiors and more lines to try (containers, crafting benches, spawning a vanilla NPC that walks
on the converted navmesh) is [docs/owner/in-game-test-sheet.md](owner/in-game-test-sheet.md).

From Red Rocket you can walk north-west down the road, over the bridge and up into Sanctuary Hills, about 250 m; that walk
has passed in both directions. Useful while exploring:

| Line | What it does |
|---|---|
| `SetLocalTime 12` / `SetLocalTime 21` | Noon / dusk. |
| `player.getpos x` (then `y`, `z`) | Your position, in metres. Include it in reports. |
| `tgm` | God mode (no damage). |
| `tcl` | Fly through walls; `tcl` again to land. Use it when a roof or wall traps you. |

Good to know:

- A single teleport of more than about 200 m can throw "Boundary Reached". Go in hops.
- If loading a save drops you back to the main menu, a plugin the build needs is missing or switched off. Run the
  `status` and `active` checks in section 4.
- Some exterior doors do nothing yet; use `coc` for interiors. Nights may look too bright or too dark; lighting is being
  calibrated.

## 6. Report what you find

The report kit takes a screenshot and saves where you were, so a report can be traced to an exact spot. It types
nothing into the game and sends nothing anywhere.

1. Start the hotkey from PowerShell in the repository folder, so it knows which Python to use for your position, and
   keep its window open (minimised) while you play:

   ```powershell
   $env:FO4SF_PYTHON = (Resolve-Path ..\fo4sf-venv\Scripts\python.exe).Path
   .\tools\report-kit\Start-ReportHotkey.cmd
   ```

   Double-clicking `tools\report-kit\Start-ReportHotkey.cmd` also works, but without `FO4SF_PYTHON` it saves
   screenshots and descriptions only, with no position or cell.
2. In game, press **Ctrl+Alt+L** for a screenshot (one beep), or **Ctrl+Alt+K** for a screenshot plus a box that asks
   what is wrong. Type one sentence and press **Save**.
3. Each press makes a folder in `Documents\FO4SF Reports\<date-time>\` with `screen.png`, `description.txt` and
   `state.json` (your position and cell, when the bridge is installed and reporting, and `FO4SF_PYTHON` is set).
4. Open a **Player report** on GitHub: **Issues → New issue → Player report**. Attach `screen.png` and paste your
   description and the useful lines of `state.json`. **Read `state.json` first**: it can contain folder paths with
   your Windows user name; delete those lines.

If the box doesn't appear over the game, switch Starfield to borderless or windowed, or press Alt+Tab once. More detail:
[docs/community/reporting-tool.md](community/reporting-tool.md).

A good report says, in one line per thing you checked:

```
step | cell | ref | action | observed | PASS/FAIL/INCONCLUSIVE | screenshot | save
```

For example: `door fwd | FO4Core_RedRocketSpawn -> FO4Port_SuperDuperMart01 | 0302D22B | E on door | loaded inside at
marker | PASS | door_fwd_1.png | fo4sf_manual_door_inside`.

Say whether you saw it in game or only read it from a file. If you used `tcl`, `tgm`, `coc` or `player.setpos` during a
walk, say so: a teleport means the walk was not continuous, so it can't count as a walking result.

Reports are reviewed by the project owner before anyone acts on them; until then they keep the `needs-triage` label.

### If the game crashes: catch a crash dump

Starfield often crashes straight to the desktop with no message. A crash dump (a copy of the game's memory at the
moment it crashed) shows what failed: the project found its Havok collision crash from one
([journal, 16 October](JOURNAL.md)). Use Microsoft's free
[ProcDump](https://learn.microsoft.com/sysinternals/downloads/procdump), started in a Command Prompt before you launch
the game.

**General crashes.** This writes one full dump (`-ma`) when the game hits an unhandled exception (`-e`), waiting for
`Starfield.exe` to start (`-w`):

```
procdump64.exe -accepteula -ma -e -n 1 -w Starfield.exe "<dump folder>"
```

**The engine's own assertion stop (advanced).** The collision crash ended the game with exception `0x80000003` (a
breakpoint) and no Windows error report, so the command above can miss it. The owner's PC used this variant, which
dumps on the first-chance exception (`-e 1`) whose content matches `80000003` (`-f`):

```
procdump64.exe -accepteula -e 1 -f "80000003" -ma -n 1 -w Starfield.exe "<dump folder>"
```

It caught the 16 October dump on the owner's PC without `-b`. ProcDump's documentation says debug breakpoints are
ignored unless `-b` is given, so if this variant misses a breakpoint crash on your PC, add `-b` (unverified on this
project). The filter means it only catches that one exception, not crashes in general.

- **Wait for the dump to finish.** A full dump is large (the owner's was about 17 GB). With `-n 1`, ProcDump writes one
  dump and then exits. The dump is complete only when ProcDump has printed that the dump completed (with the size it
  wrote) and no write error, and then exited. An exit without that line (after Ctrl+C, an attach or access error, or
  a full disk) means there is no usable dump. Don't close the window before then; a half-written dump is useless.
- **Stop watching** with **Ctrl+C** in ProcDump's window. That is ProcDump's graceful stop: it resumes the game if a
  capture is running. Don't kill ProcDump with Task Manager or `taskkill`, which can cut a dump off halfway.
- **With the launcher** the watcher follows one game instead of running all day: turn it on with
  `python scripts/launcher.py settings --set crash_watch.enabled=on --set crash_watch.folder="<dump folder>" --set
  crash_watch.procdump="<path to procdump64.exe>"`, then start the game with
  `python scripts/launcher.py play --starfield "<game folder>"` (or plain `play` once the game folder is saved with
  `launcher.py paths --accept` or the window's Locations tab). It attaches once the game has stayed up 20 seconds,
  writes small dumps by default (`--set crash_watch.dump=full` for full ones), and logs every exit code to
  `crashwatch.log` in the dump folder, so a crash without a dump still leaves its code.
  The launcher writes Plugins.txt only before the game starts: when bridge is on or off, and by default to put our
  plugins after their masters while keeping any already-valid order, including kits after markers or the bridge
  (load_order=fix; it keeps a Plugins.txt.bak copy and writes nothing when the order
  is already right; `--set load_order=check` refuses instead, `off` leaves the file alone). The order is in
  `scripts/game/load_order.py`. On the owner's first launcher run (2026-10-22) Plugins.txt was rewritten about 25 s after the game
  started, with FO4Port moved after FO4SFMission and every line still ticked. Nothing in the launcher runs then (it
  only waits on the game and ProcDump), so the game itself reordered it (inferred, not traced). A moved plugin gets
  another load-order index, so its form ids change between sessions (Codsworth 06000811 became 05000811). play
  compares the order at the start and after the game exits and reports any change on screen and in `crashwatch.log`.
  For a game started some other way (the test runner), `python scripts/launcher.py watch --repeat` attaches the same
  watcher to each game it sees.
- **Never upload a dump** to GitHub or anywhere else: it holds the game's memory and can hold personal data. In the report,
  give the time of the crash, the cell and what you were doing, and say that you have a dump. A maintainer will ask for
  what they need from it.
- **Delete it** when it is no longer needed: `del "<dump folder>\<name>.dmp"`.

## 7. Automated tests (optional, advanced)

The repository also has an unattended test runner that launches the game, drives it from the console and judges each
test PASS, FAIL or INCONCLUSIVE with screenshots and logs. It takes over your keyboard and screen while it runs, so
only start it on a PC you are not using. How it works and how to plan a queue: [scripts/game/README.md](../scripts/game/README.md)
and [docs/ai/test-queue.md](ai/test-queue.md).

## 8. Getting help and contributing

- Live progress and exact build pins: [issue #32](https://github.com/fo4sf/fo4-to-starfield/issues/32).
- Code changes: [CONTRIBUTING.md](../CONTRIBUTING.md). Every change needs synthetic tests and must pass
  `python scripts/guard.py`.
- Reviewing with an AI assistant: point it at [docs/ai/for-ai-reviewers.md](ai/for-ai-reviewers.md).
