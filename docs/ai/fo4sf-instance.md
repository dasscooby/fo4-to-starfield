# The FO4SF game folder: always FO4SF, beside the player's own Starfield

Owner, 2026-11-01: "stay FO4SF all the time make a separate area then actual starfield so people can keep their own
mod packs for that". So the launcher keeps FO4SF in a game folder of its own. The player's Steam Starfield, with
whatever mods they run there, is never switched or changed by it. This answers the 29 Oct launcher question:
always FO4SF, in its own place, instead of switching one install back and forth with restore.

Status: all four steps are built, behind the setting `instance` (empty by default: nothing changes until it is set).
The PC checks in section 4 decide whether they hold in the real game. Code: `src/fo4sf/launcher/instance.py` and
`crashwatch.play(folder=...)`. Tests: `tests/test_launcher_instance.py`, `tests/test_launcher_instance_play.py` and
`tests/test_launcher_instance_windows_safety.py` (real NTFS junctions; skipped off Windows).

How to use it (game closed):

```
python scripts\launcher.py instance plan   --starfield "D:\SteamLibrary\steamapps\common\Starfield" --at D:\FO4SF\Starfield
python scripts\launcher.py instance create --starfield "D:\SteamLibrary\steamapps\common\Starfield" --at D:\FO4SF\Starfield
python scripts\launcher.py settings --set instance=D:\FO4SF\Starfield
python scripts\launcher.py instance run -- python scripts\deploy_starfield.py install --batch <stage> --starfield D:\FO4SF\Starfield
python scripts\launcher.py instance run -- python scripts\game\exp_install.py install --exp-dir <core stage> --pack --starfield D:\FO4SF\Starfield
python scripts\launcher.py play --dry-run
python scripts\launcher.py play
```

`instance run` runs one of our tools on the folder with its own Plugins.txt. The command must name the folder exactly
once as `--starfield <folder>` (a prefix argparse takes, such as `--starf`, counts; a relative path is read from the
repo folder the tool runs in), because a tool's default `--starfield` is the player's install. After a crash or a power
cut, `instance recover` (or the next `play`, with or without the setting) puts the player's Plugins.txt back from the
journal.

## 1. What a game folder needs, and where Starfield keeps it

| What | Where Starfield looks | Shared with the player's game? | How the FO4SF folder gets its own |
|---|---|---|---|
| Game files, Data, SFSE | the folder `Starfield.exe` runs from | no, once there is a second folder | step 1: Data's game files and Tools hard-linked (same drive: no extra disk); the rest copied |
| Plugins.txt | `%LOCALAPPDATA%\Starfield\Plugins.txt` (verified, sfstack.md) | **yes** | step 2 below |
| Saves | `Documents\My Games\Starfield\Saves` | **yes** | step 3: `SLocalSavePath` in the folder's own `Starfield.ini` (H3) |
| StarfieldCustom.ini, StarfieldPrefs.ini | `Documents\My Games\Starfield` | **yes** | stay shared (graphics, controls); our writes move to the folder's own `Starfield.ini` (H3) |
| Starfield.ccc, My Games `Data` copies | My Games first, then the game folder (verified, sfstack.md) | **yes** | nothing to do: a copy in My Games\Data loads only beside a same-named plugin in the game folder's Data (verified), and the `loaders` check already refuses a ccc that lists a mod |
| The licence | Steam must be running, even for a copied folder | n/a | a community guide that runs a copied Starfield folder through MO2 says so (Steam community guide 3696909539; supported) |

Step 1's rules, in `instance.py`:
- Data's game files and `Tools` (the Creation Kit's tools, about 2 GB) are hard-linked: a second name for the same
  file, no extra disk. Another drive is refused, because a copy costs the whole game. A write into a linked file in
  place (not a new file put there) shows in both folders; the game and our installers put new files.
- Everything else is copied: the files beside `Starfield.exe` (the exe, its DLLs, SFSE's loader and DLL), the other
  small folders, and every INI at any level. An SFSE update overwrites its files in place, and the FO4SF folder may
  stay on an older game version (H4), so those must be the folder's own. On the owner's PC that is about 0.6 GB
  besides crash dumps. A copy goes to `<name>.fo4sf-part` first and takes its name only when complete.
- Data keeps only the game's own plugins and the files named after them. The player's mods, our installs, loose
  folders and SFSE plugins are left out and listed. Known gap: a player's archive named after a game plugin
  (`Starfield - MyRetexture.ba2`) is taken for the game's and comes along.
- Beside the exe, the player's add-ons are left out and listed too: injector DLLs (`dxgi.dll`, `d3d11.dll`,
  `d3d12.dll`, `dinput8.dll`, `version.dll`, `winmm.dll`, `winhttp.dll` and the like, `*.asi`), ReShade and ENB
  files and folders, and crash dumps (`*.dmp`). Copy one in by hand to use it in FO4SF too.
- Nothing is ever written in the Steam install, and nothing is overwritten.
- No write goes through a link (#655, Codex's Windows review):
  - A symlink or NTFS junction anywhere inside the folder is refused before the first file, and again at every
    folder a file goes into.
  - The protected places (a Steam library, Program Files, a synced folder: OneDrive in any of its names, Dropbox,
    Google Drive, iCloud Drive) are checked on the path as given and on the path it resolves to, so an alias does not
    get past them. A drive or share that is not there is refused.
- A stopped run carries on from its record (`FO4SF-instance.json`). Every file already there is checked before the
  record changes: a link must be the game's file; a copy must be a plain file with no second name, either recorded
  (it may have changed since: the folder's INI is its own) or byte for byte the game's (a run that stopped between the
  copy and its record). A refused rerun leaves a finished folder finished, so `play` still works.

The folder may not go inside a `steamapps` folder, Program Files or a synced folder: the Starfield Launchpad Wabbajack
instance gives the same advice (nexusmods.com/starfield/mods/18644).

## 2. Plugins.txt: the one file both games read from the same place

Every installer of ours (`exp_install.py`, `deploy_starfield.py`, `bridge_install.py`, `map_markers_install.py`, the
probes, `plugin_toggle.py`) finds Plugins.txt through the `LOCALAPPDATA` environment variable (verified in the
code: `exp_install.plugins_txt`, `deploy_starfield.plugins_txt_path`). So for the FO4SF folder they run with
`LOCALAPPDATA=<folder>\FO4SF-local`. They then keep the folder's own list in `<folder>\FO4SF-local\Starfield\Plugins.txt`
and never touch the player's. `restore` snapshots work the same way: their Plugins.txt path only has to end in
`Starfield\Plugins.txt`.

The game itself probably asks Windows for the folder (the known-folder call), not the variable (**H2**, unverified):
- If H2 holds: `play` puts the folder's list in place just before the start and puts the player's back after the
  exit. `crashwatch.play` already follows the game to its exit. A journal beside it lets the next launcher run put
  the player's list back after a crash or a power cut. While FO4SF's list is in place, the launcher says so.
- If the game reads the variable, the swap is not needed; until H2 is checked, `play` always swaps and starts the
  game with the launcher's own `LOCALAPPDATA`, which is right either way.

Not `sTestFile`, although an `sTestFile1..10` in the folder's own `Starfield.ini` makes the game ignore Plugins.txt
(verified, Ortham 2024). Since 1.16.236 the game writes the `sTestFile` plugins into Plugins.txt anyway, and it drops
listed plugins it cannot find in its Data (both verified, sfstack.md). The player's list would be rewritten every
FO4SF start. It also caps at 10 plugins; FO4SF loads about 9 today, plus texture companions.

## 3. The steps (all built)

1. **Make the folder:** `launcher.py instance plan|create --starfield <Steam folder> --at <new folder>`.
2. **Install into it:** `launcher.py instance run -- <installer> --starfield <folder>` runs our tools with
   `LOCALAPPDATA=<folder>\FO4SF-local`. With the setting `instance`, `play` runs the bridge toggle and the load
   order on that list too. The test runner's `cycle.ps1` stays as it is until the owner moves it.
3. **Its own saves and INI writes:** before each start, `play` puts `SLocalSavePath=Saves\FO4SF\` in the folder's
   copied `Starfield.ini`, and the Papyrus keys go there too, not into the shared `StarfieldCustom.ini` (H3). It never
   writes through a link or a file with a second name, and writes a new file put in place. Because the shared
   `StarfieldCustom.ini` wins over it, `play` refuses when that file (in the setting `my_games`, when set) sets
   `SLocalSavePath`, or sets `bEnableLogging=0` under `bridge=on`. `play` refuses `route=steam`, because `steam://` starts the Steam
   folder, not this one; sfse and exe start the folder's own executables.
4. **Play with the folder's list:** just before the start, `play` journals the player's Plugins.txt bytes in
   `%LOCALAPPDATA%\FO4SF\FO4SF-swap.json`, beside the launcher's settings and never in the FO4SF folder (with a second
   copy, `player-Plugins.txt.bak-<time>`, there too), and puts the folder's list in its place. When the game ends (before any wait on a crash dump), the
   game's rewrite of that list becomes the folder's list, and the player's comes back byte for byte. That also happens
   when the start fails.
   - The journal is found from the player's Plugins.txt, not from the setting: every `play` (with the setting or not)
     and `instance recover` put a left swap back first, so clearing or changing `instance`, or removing the folder,
     cannot strand the player's list. A dry run only says a swap is left.
   - While a game is still running (one that came up after the watch gave up), the player's list stays journaled until
     the next `play` or `instance recover` finds Starfield closed.
   - A recovery never adopts what it finds in the player's place as FO4SF's list; it keeps it aside as
     `Plugins.txt.after-<time>` beside the journal (also after a game whose folder is gone).
     - Never overwritten: a name already taken by other bytes gets `-2`, `-3` and so on.
     - A retry after an interrupted recovery reuses its own kept copy (same bytes) and finishes (#655).
   - The swap works whichever way H2 turns out, because the game is started with the launcher's own `LOCALAPPDATA`.
   - The window's Play starts the folder too.

Default off: until the setting `instance` is set, play, the window and every tool work on the Steam folder as before.

## 4. To check on the PC before steps 2 to 4

- **H1, the copied folder starts the game.** `launcher.py instance create --starfield <Steam folder> --at
  D:\FO4SF\Starfield`, then `D:\FO4SF\Starfield\sfse_loader.exe` with Steam running. Expected: the main menu (the
  community guides do this with full copies). Also check the plan's "left out of Data" list on the real install: any
  folder of the game's own that must stay is kept with `--keep-data-dir` (H5: vanilla Data has no folder the game
  needs; on this PC the game reads no loose files).
- **H2, where the game reads Plugins.txt.** Start the folder's `Starfield.exe` from a shell with
  `LOCALAPPDATA` set to an empty test folder. If the game makes `Starfield\Plugins.txt` there, it follows the
  variable and no swap is needed.
- **H3, the game folder's Starfield.ini counts.** Put `SLocalSavePath=Saves\FO4SF\` under `[General]` in the
  folder's `Starfield.ini`, save once, and look for `My Games\Starfield\Saves\FO4SF`. It must not be set in
  `StarfieldCustom.ini`, which would win. MO2 relies on this key for its per-profile saves (supported, MO2 issue
  #309).
- **H4, a Steam update.** After the next game update, check whether the folder's files still share their data with
  Steam's (`launcher.py measure` counts hard links once). Expected: Steam writes new files, the links break, and the
  FO4SF folder stays on its version (what "Stock Game" setups rely on), costing disk for each changed file. The test
  is on the files the update changed (newer than the update in Steam's folder): files it left alone always still
  share, and `measure` gives folder totals only, so its count alone cannot tell. If a changed file still shares its
  data, Steam wrote into it in place: the FO4SF folder's Data and Tools then changed with Steam's while its copied exe
  and DLLs stayed on the old version, so it needs `instance create` into a new folder (the new exe and DLLs, with the
  SFSE for that version) before it plays again (review of 66c353dd).

## 5. What it costs

- Disk: none for the linked files (Data, Tools); the copied rest is well under 1 GB of game files (step 1). After a
  Steam update, the changed linked files (H4).
- Steam's "verify files" or an update never touch the FO4SF folder's copied files. The linked ones (Data, Tools) stay
  as they were if Steam writes new files, which H4 checks; a hard link removed on Steam's side keeps the file alive in
  the folder.
- The player's own Starfield keeps its mods, Plugins.txt order and saves, apart from the shared INIs in section 1
  and a write in place into a linked Data or Tools file (step 1).
