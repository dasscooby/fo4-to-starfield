# FO4SFBorder: the border off in our world only

SFSE plugin for `docs/terrain/border.md`, "Per-world switch". It turns Starfield's border regions
(`bBorderRegionsEnabled:General`, the setting run _f switched with `SetINI`) off while `FO4SF_MapMarkers` says the
player is in our world, and back to their found value elsewhere. No Address Library, no game structures: the setting
is found by its name.

Nothing of Bethesda's or of SFSE's is in this folder. `PluginAPI.h` is SFSE's MIT-licensed header, fetched by
`../FOCCSidecar/fetch_pluginapi.ps1` (pinned commit 48535cc, sha256 checked) and kept out of git (`.gitignore`).

## Files

| File | Role |
|---|---|
| `FO4SFBorder.cpp` | the plugin: version data, load, the worker that scans, tails the signal log and queues writes |
| `scan.h` | header-only rules: find the name string, the 8-aligned pointers to it in writable memory, the newest token |
| `FO4SFBorder.ini` | kill switch and settings; ships with `Mode=0` |
| `build.sh` | mingw-w64 static cross-build (`build.sh OUT_DIR`), prints sha256s |

`tests/sfse_border_scan_test.cpp` (run by `tests/test_sfse_border.py` where g++ exists) checks `scan.h` on synthetic
memory; `tests/test_sfse_border.py` also pins the contract with the script's log lines.

## Modes (`[FO4SFBorder]` in the ini next to the dll)

- `Mode=0` (the kill switch): loads and stays idle and silent: no log line, no file, no worker.
- `Mode=1` probe: after game data loads, finds the candidates every 2 s and logs the 32 bytes before each pointer
  whenever they change (`changed` lines). Never writes game memory. Typing `SetINI "bBorderRegionsEnabled:General" 0`
  then `1` in the console shows the value's offset.
- `Mode=2` switch: on each new `border=off` / `border=on` in the signal log, queues a one-byte write at
  `ValueOffset` (default -16, verified by the probe on 1.16.244) through SFSE's Task interface. Refuses (`refuse` line) unless exactly one
  candidate is found and the byte reads 0 or 1.

`SignalLog` overrides the log path (default `Documents\My Games\Starfield\Logs\Script\User\fo4sf_map.0.log`). Lines
written before the plugin loaded are skipped; a new log file (new session) is read from its start.

Log (FAL-246, out of the game's `Data` folder): `<Dir>\logs\fo4sf_border.log`, one JSON object per line, where `<Dir>` is
the profile's run-time folder named by `FO4SF-Runtime.ini` next to the dll (`sfse/FOCCSidecar/README.md`, "Where the
files land": the same file and rules for every dll of ours). With `Mode=1` or `2` and no usable `Dir` (no file, a
malformed one, or a `Dir` whose parent folder does not exist) the plugin stays idle: no worker, no game memory
written, no file. It says why once through `OutputDebugString` (`FO4SFBorder: refuse step=runtime_dir ...`, visible
in a debugger or DebugView); it has no other log of its own. `Mode=0` needs no `FO4SF-Runtime.ini`.

## Install (PC card, the owner's line)

Copy `FO4SFBorder.dll` and `FO4SFBorder.ini` to `Starfield\Data\SFSE\Plugins\`, with `FO4SF-Runtime.ini` there too
(the launcher writes it; by hand, as the sidecar README shows). Papyrus logging must be on for the
signal (`bEnableLogging` and `bEnableTrace` under `[Papyrus]`, as the bridge already needs). Remove both files to undo.
