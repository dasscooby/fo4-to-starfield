# FOCCSidecar: the P1 probe plugin for SFSE

Probe P1 of the combined-core probe kit (research note
`research/framework/combined-core-notes/engine-feasibility.md`, "PC probes"; runbook `docs/spikes/combined-core-probes.md`):
does an SFSE plugin that writes a **sidecar file per save** on `PreSaveGame` and reads it back on `PostLoadGame` work on
the owner's PC, and what happens to the sidecar when a save is deleted? The plugin is the smallest thing that answers
that. It is not the combined core's real plugin and keeps no real world state.

Nothing of Bethesda's or of SFSE's is in this folder. SFSE itself is installed by the owner from its Nexus page and
never bundled (legal-policy.md finding 11). The only SFSE file this build touches is `sfse/PluginAPI.h`, which the
SFSE repository's `LICENSE` places under MIT ("This applies to sfse/PluginAPI.h ... The remainder of the files are
currently not under a permissive license", read 2026-10-21 at commit `48535cc`); `fetch_pluginapi.ps1` downloads that
header and that licence file at a pinned commit, verifies their sha256s and keeps both out of git (`.gitignore`).

## Files

| File | Role |
|---|---|
| `FOCCSidecar.cpp` | the plugin: version data, `SFSEPlugin_Load`, the "SFSE" message listener, Windows file I/O, JSON-lines log |
| `codec.h` | header-only mirror of `src/fo4sf/combined/sidecar.py`: file-name rule, canonical body, envelope reader |
| `sha256.h`, `sha256.cpp` | portable SHA-256 (FIPS 180-4) so the name rule and checksum match Python's `hashlib` |
| `check_toolchain.ps1` | PC step 0: is MSVC + Windows SDK + SFSE there? JSON report; exit 1 stops the runbook |
| `fetch_pluginapi.ps1` | PC step 1: fetch `PluginAPI.h` + its licence at the pinned commit, verify hashes |
| `build.ps1` | PC step 2: `cl.exe` build into a new staging folder, `build.json` with every sha256 |

The plan's layout named a BCrypt-based SHA-256. It is a portable implementation instead, so the same `sha256.cpp`
and `codec.h` compile on Linux in the repo's container and could be checked against `sidecar.py` before anything
reached the PC (see "Verified offline"); BCrypt could not have been compiled or tested here.

## What the plugin does

Only when the kill switch is on (below):

1. `SFSEPlugin_Load`: queries `kInterface_Messaging`, registers a listener for sender `"SFSE"`, creates
   `<dll folder>\FOCCSidecar\` and `...\sidecars\`, logs one `load` line with SFSE's and the runtime's version words.
2. `kMessage_PreSaveGame`: increments an in-process counter `k`, writes `sidecars\<sidecar_name(save)>` with the body
   `{"format": "focc-sidecar", "save_name": <name>, "schema": 1, "sha256": <sha256 of the world_state text>,
   "world_state": {"counter": k, "probe": "P1"}}` (a temp file in the same folder, flushed, then `MoveFileExW` with
   replace, like `sidecar.write`), logs `pre_save`.
3. `kMessage_PostSaveGame`, `kMessage_PreLoadGame`: logged.
4. `kMessage_PostLoadGame`: reads the sidecar for the loaded save name, checks format, schema, save name and checksum
   (`sidecar.decode`'s checks), logs `post_load` with `found`, `valid`, `counter` and, on a valid file, adopts its
   counter.
5. It never deletes a file. SFSE sends no message on save deletion (`engine-feasibility.md` section 1), so orphaned
   sidecars are listed offline by `sidecar.orphans()`; the probe's checker does that from the collected folder.

The P1 world state is a stub, not a `model.WorldState`: group C's checker verifies the envelope (format, schema,
save name, checksum over the sorted-keys JSON of `world_state`), as the probe plan's P1 pass rule says.
`sidecar.decode` in Python would reject the stub at `WorldState.from_json`, by design.

### Where the files land

`<Starfield>\Data\SFSE\Plugins\FOCCSidecar\focc_sidecar.log` and `...\FOCCSidecar\sidecars\*.focc`. The folder is
found with `GetModuleFileNameW` on the dll itself, so nothing is written under Documents (Controlled Folder Access
blocks our writes there; `scripts/bridge/make_bridge.py`). The job card copies both into the testqueue folder.

### Log format

One JSON object per line, CRLF, appended (never rewritten), keys `seq` and `time` (UTC) first:

```
{"seq": 1, "time": "...", "event": "load", "plugin": "FOCCSidecar", "plugin_version": 1, "sfse_version": "0x...", "runtime_version": "0x...", "interface_version": 1, "messaging": true, "registered": true, "dir": "..."}
{"seq": 2, "time": "...", "event": "sfse_post_load"}
{"seq": 3, "time": "...", "event": "pre_load", "save": "<name>", "save_hex": "<hex of the raw bytes>"}
{"seq": 4, "time": "...", "event": "post_load", "save": "<name>", "save_hex": "...", "file": "<name>-<hash8>.focc", "found": false, "valid": false, "counter": -1, "error": "not found"}
{"seq": 5, "time": "...", "event": "pre_save", "save": "<name>", "save_hex": "...", "counter": 1, "file": "<name>-<hash8>.focc", "written": true}
{"seq": 6, "time": "...", "event": "post_save", "save": "<name>", "save_hex": "..."}
```

`save` is the raw save-name bytes SFSE passed (control characters, quotes and backslashes JSON-escaped; bytes >= 0x80
passed through); `save_hex` is their hex, so the checker can settle the encoding question without guessing. Events
with an empty name log `"error": "empty save name"`.

### Name and checksum rule (mirror of `sidecar.py`)

`sidecar_name(n)` = every byte outside `[A-Za-z0-9_.-]` replaced by `_`, cut to 80, leading and trailing `.` stripped,
`save` if empty, then `-` + first 8 hex of `sha256(n)` + `.focc`. The body is Python's `json.dumps(..., sort_keys=True)`
with its default `", "` and `": "` separators, so `sha256(json.dumps(body["world_state"], sort_keys=True))` recomputed
by the checker equals the `sha256` field. Caveat: Python replaces per *character*, the plugin per *byte*, so a save
name with non-ASCII characters gets one `_` per UTF-8 byte here and one per character there, and the hash over the
name only agrees when SFSE hands UTF-8 bytes. For ASCII names (the runbook uses `focc_p1_a`, `focc_p1_b`) the two
rules are identical and were checked to be.

### Kill switch

The plugin does nothing unless `<Starfield>\Data\SFSE\Plugins\FOCCSidecar.ini` holds

```
[FOCCSidecar]
bEnabled=1
```

Without the file, the section or the key, or with any other value, `SFSEPlugin_Load` returns `true` and registers
nothing, writes nothing, creates no folder. SFSE's own log (`<My Games>\Starfield\SFSE\Logs\sfse.log`, per its readme)
then still shows the dll being loaded. `build.ps1` writes the ini with `bEnabled=0`; the owner flips it to 1 when
installing for the probe and back to 0 (or deletes the dll) afterwards. Uninstall is deleting
`Data\SFSE\Plugins\FOCCSidecar.dll` (and, optionally, the ini and the `FOCCSidecar\` folder with the log and sidecars
after they were collected). Nothing of ours installs or removes SFSE plugins; the runbook's job card records the copy.

## Building on the owner's PC

Game closed. The repo checked out on the PC; `$sf` = the Starfield folder (the one with `Starfield.exe`).

0. **Toolchain check (stops cleanly if absent).** `powershell -File sfse\FOCCSidecar\check_toolchain.ps1 -Starfield $sf -Out toolchain.json`
   prints a JSON object and exits 1 when `cl.exe` (via `vswhere`, component `Microsoft.VisualStudio.Component.VC.Tools.x86.x64`),
   `vcvars64.bat`, a Windows 10/11 SDK with `um\windows.h`, `sfse_loader.exe` or any `sfse_*.dll` is missing. With the
   portable MSVC (D:\Modding\tools since 28 Oct 2026: no Visual Studio, nothing registered) dot-source its `msvc_env.ps1`
   first or pass `-Env D:\Modding\tools\msvc_env.ps1`: the check then takes the `cl.exe` on PATH and the SDK from
   `INCLUDE`, needs no vswhere or vcvars64, and `toolchain` in the JSON reads `environment` (only when `cl.exe`'s banner
   says x64: an x86 developer prompt is refused, since its dll could not load into the 64-bit game). On exit 1
   nothing else runs; the owner decides whether to install **Visual Studio Build Tools 2022 with the "Desktop
   development with C++" workload** (several GB; not a decision this kit makes) and SFSE 0.2.21 for Starfield
   1.16.244 (SFSE's `sfse_whatsnew.txt` and readme: "SFSE will support the latest version of Starfield available on
   Steam, currently 1.16.244"; Steam only, no Gamepass/MS Store). The docs record that no MSVC, vswhere or Visual Studio
   was on the PC on 2026-10-07/11 (`docs/terrain/source-patch.md` line 30), so exit 1 is the expected first result.
1. **Header.** `powershell -File sfse\FOCCSidecar\fetch_pluginapi.ps1` places `PluginAPI.h`, `PluginAPI.LICENSE.txt` and `PluginAPI.pin.json` (the commit, which build.json records)
   beside the sources (pinned commit `48535cc4306ab345252bf740c20a1c6194929b0e`, header sha256
   `10b834f1490b12fcab965d9c7a49f87bac3a102ed0f25a71611d499bd506c442`, licence sha256
   `4a4b6926786f261e0c19178af304190c645b1b820b7722a6973c9b2a64b8a860`). A mismatch places nothing. Both files are
   gitignored; `scripts/guard.py` must stay green.
2. **Build.** `powershell -File sfse\FOCCSidecar\build.ps1 -Out D:\Modding\staging\focc_sfse_<date>` runs
   `cl.exe /nologo /std:c++20 /EHsc /O2 /W4 /DUNICODE /D_UNICODE /LD FOCCSidecar.cpp sha256.cpp` inside `vcvars64`, or
   straight in the loaded environment (same `-Env` as step 0; `build.json` records `toolchain` and the env script),
   writes `FOCCSidecar.dll`, `FOCCSidecar.ini` (`bEnabled=0`), `cl_output.txt` and `build.json` (sha256 of the four
   sources, of `PluginAPI.h` and of the dll). It refuses an `-Out` that already holds a dll. Compile errors on the first
   build are expected and cheap: this source has never met MSVC (below).
3. **Install (by hand, game closed).** Copy `FOCCSidecar.dll` and `FOCCSidecar.ini` to `$sf\Data\SFSE\Plugins\`
   (SFSE's plugin folder: `PluginManager.cpp` builds it as `<runtime dir>\Data\SFSE\Plugins\`, read upstream), set
   `bEnabled=1`, record both sha256s on the job card.
4. **Run** through `sfse_loader.exe`, not Steam and not `cycle.ps1` (which launches through Steam). If the game does
   not reach the main menu, delete the dll first and report; a bad plugin can crash the game at start.
5. **Collect** `Data\SFSE\Plugins\FOCCSidecar\focc_sidecar.log`, `...\sidecars\*.focc` and the saves list
   (`Get-ChildItem "<My Games>\Starfield\Saves" -Filter *.sfs | Select Name,Length | ConvertTo-Json`) as the runbook's
   P1 card says; judge with `python -m fo4sf.combined.probes p1 --collect <folder>` (group C).

## Verified offline (Linux container, 2026-10-21)

- `codec.h` + `sha256.cpp` compiled with `g++ -std=c++20 -Wall -Wextra -Werror` and were run against
  `src/fo4sf/combined/sidecar.py`: `sidecar_name` and the full body text are byte-identical to Python's for
  `focc_p1_a`, `Autosave 1`, `Quicksave`, names with `/ : ? " \`, leading/trailing dots, control characters, a 200-char
  name (the 80-cut), and the checker's recomputation (`sha256(json.dumps(body["world_state"], sort_keys=True))`) equals
  the `sha256` field. SHA-256 agrees with `hashlib` on the empty string and on lengths 55, 56, 63, 64, 119, 120 and
  1000 (padding boundaries). `decode_sidecar` round-trips, and rejects a tampered body and another save's body.
- `FOCCSidecar.cpp` passed `clang++ -std=c++20 -fsyntax-only -fms-extensions -fdeclspec` against the **real**
  `PluginAPI.h` (fetched into the scratchpad, not the repo) and a hand-written stub `windows.h` declaring only the Win32
  functions the file uses. That proves the SFSE names and types (`SFSEPluginVersionData` fields and bits,
  `SFSEInterface::QueryInterface`/`GetPluginHandle`, `SFSEMessagingInterface::RegisterListener`, `Message`,
  `kMessage_*`) are used as declared; it proves nothing about the Win32 calls (stub signatures are mine).

## Automated portable-codec coverage

From the repository root, `python -m unittest tests.test_sfse_sidecar_codec -v` compiles `codec.h` and `sha256.cpp`
into a temporary console program with a C++20 compiler (GCC/Clang, or MSVC from a loaded compiler environment).
CI requires a compiler; a local environment without one reports a skip. No DLL or game API is built or loaded.

The tests compare ASCII names and canonical envelopes with Python, check SHA-256 block boundaries and valid signed
counter limits, and exercise malformed envelopes, duplicate fields, wrong probe state, and non-integer/out-of-range
counters with matching checksums. The reader accepts only the canonical P1 stub body its own writer produces;
an invalid body returns `valid=false` rather than truncating a number or throwing a numeric-conversion exception.
UTF-8 names retain their own writer/readback behavior; the documented non-ASCII filename parity caveat still applies.
These are portable codec checks, not evidence of SFSE callbacks, Win32 file recovery or in-game save/load behavior.

## Not verified (first build and first run settle these)

- **The whole dll has never been compiled by MSVC** (no Windows SDK here). Likely trouble spots: `/W4` warnings
  (not errors), the aggregate initializer of `SFSEPlugin_Version` (follows the example in `PluginAPI.h` lines 182-198),
  `out.data()` as a writable buffer (C++17 and later, fine with `/std:c++20`).
- Win32 calls used, from memory of the documented signatures: `GetModuleFileNameW`, `CreateDirectoryW`, `CreateFileW`
  (`FILE_APPEND_DATA` for the log), `WriteFile`, `FlushFileBuffers`, `MoveFileExW(MOVEFILE_REPLACE_EXISTING |
  MOVEFILE_WRITE_THROUGH)`, `GetFileSizeEx`, `ReadFile`, `DeleteFileW` (only on this write's own temp file),
  `GetPrivateProfileIntW`, `GetSystemTime`, `WideCharToMultiByte`, `DisableThreadLibraryCalls`.
- **Save-name semantics**: `Hooks_Serialization.cpp` dispatches `a_name` as `const char*` with `dataLen = strlen`;
  whether it is the display name, the `.sfs` stem or a path, and its encoding, are unverified. The log's `save` and
  `save_hex` fields exist so the checker can compare against the `.sfs` names and report, not guess.
- Whether `PreSaveGame` also fires for autosaves, quicksaves and exit-saves, and whether `PostLoadGame` fires on the
  first load from the main menu, are unverified; every event is logged, so the log answers it.
- Version-independence claim: `kAddressIndependence_Signatures | kStructureIndependence_NoStructs` makes SFSE skip the
  version list (`PluginManager::checkPluginCompatibility`, read upstream 2026-10-21); the plugin uses no addresses or
  structures, so the claim is honest, but this is the first plugin of ours SFSE has ever loaded.
- SFSE's loader and dll file names on the owner's install (`sfse_loader.exe`, `sfse_1_16_244.dll` by the readme's
  "starting with sfse_" convention): `check_toolchain.ps1` reports what it finds instead of assuming.
- `1.16.244` packs to `0x01100F40` (`MAKE_EXE_VERSION(1, 16, 244)` in `sfse_common/sfse_version.h`, read upstream;
  that file is not MIT, so only the number and formula are restated here).
