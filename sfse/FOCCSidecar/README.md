# FOCCSidecar: the P1 probe plugin for SFSE

Probe P1 of the combined-core probe kit (research note
`research/framework/combined-core-notes/engine-feasibility.md`, "PC probes"; runbook `docs/spikes/combined-core-probes.md`):
does an SFSE plugin that writes a **sidecar file per save** on `PreSaveGame` and reads it back on `PostLoadGame` work on
the owner's PC, and what happens to the sidecar when a save is deleted? The plugin is the smallest thing that answers
that. It is not the combined core's real plugin and keeps no real world state.

**Since FAL-216 it is built like FO4SFPipboyMenu (PR #704) and FOCCPing:** against libxse/commonlibsf `9d090c4`
(submodule `lib/commonlib-shared` at `9fbb74d`) through xmake, with the same version guard (runtime 1.16.244.0 only) and
the same `refuse step=` lines, so the probe session builds all three plugins the same way. The first build (21 to 28
Oct 2026) used SFSE's own `PluginAPI.h` and `cl.exe` directly; the PC built it on 28 Oct
(`D:\Modding\staging\focc_sfse_20261028c`, exit 0) and it was never run. That source is gone from this folder;
`fetch_pluginapi.ps1` stays because `sfse/FO4SFBorder` fetches its header through it, and `check_toolchain.ps1` stays as
the runbook's read-only P1-0 check.

Nothing of Bethesda's, of SFSE's or of CommonLibSF's is in this folder. libxse/commonlibsf (GPL-3.0-or-later with its
modding and linking exceptions) is cloned on the PC; `build.ps1` junctions it into the staging copy of the project. The
plugin's save and load message numbers are SFSE's, restated from its MIT-licensed `sfse/PluginAPI.h` (48535cc, lines
103-110): PreSaveGame 4, PostSaveGame 5, PreLoadGame 6, PostLoadGame 7 (libxse's enum names only 0 to 3).

## Files

| File | Role |
|---|---|
| `src/main.cpp` | the plugin: the version guard, the kill switch, the "SFSE" message listener, file I/O, the JSON-lines log |
| `src/pch.h` | the precompiled header (`RE/Starfield.h`, `SFSE/SFSE.h`), as FOCCPing's |
| `codec.h` | header-only mirror of `src/fo4sf/combined/sidecar.py`: file-name rule, canonical body, envelope reader |
| `sha256.h`, `sha256.cpp` | portable SHA-256 (FIPS 180-4) so the name rule and checksum match Python's `hashlib` |
| `xmake.lua` | the plugin target in the shape of libxse/commonlibsf-template; `codec.h` and `sha256.cpp` from this folder's top |
| `FOCCSidecar.ini` | the kill switch, `bEnabled=0` as shipped |
| `build.ps1` | PC build: FO4SFPipboyMenu's and FOCCPing's xmake build; `build.json` with every sha256 and both library commits |
| `check_toolchain.ps1` | runbook P1-0, read-only: MSVC, the Windows SDK and SFSE on the PC, as JSON |
| `fetch_pluginapi.ps1` | fetches SFSE's MIT `PluginAPI.h` at a pinned commit for `sfse/FO4SFBorder` (not used by this plugin) |

`codec.h` and `sha256.cpp` stay at the folder's top: `tests/test_sfse_sidecar_codec.py` and
`tests/test_combined_cpp_parity.py` compile them on Linux. `tests/test_sfse_sidecar_scripts.py` pins this folder's
contract as text (no compiler for the dll here).

## What the plugin does

Checked first, as FO4SFPipboyMenu and FOCCPing do, each failure one `refuse step=<step>` line in the plugin's SFSE log
(`Documents\My Games\Starfield\SFSE\Logs\FOCCSidecar.log`) and the plugin idle:

1. `step=load runtime=<v> sfse=<v> plugin_version=2 enabled=<0|1>`, then the runtime must be 1.16.244.0
   (`refuse step=version runtime=<v> expected=1.16.244.0`).
2. The kill switch (below): off logs `step=off` and nothing else happens.
3. `<dll folder>\FOCCSidecar\sidecars\` is created if missing (`refuse step=folder path=<p> error=<n>`).
4. SFSE's messaging interface takes the listener (`refuse step=listen messaging=<0|1>`); then `step=listen`.

The plugin reads no Address Library id and touches no game address or structure. libxse's plugin rule still marks
it as an Address Library user, so SFSE wants `versionlib-1-16-244-0.bin` in the plugin folder; the probe session
installs it anyway.

Then, on SFSE's messages (sender `"SFSE"`):

1. `PostLoad`: logged (`sfse_post_load`).
2. `PreSaveGame` (4): increments an in-process counter `k`, writes `sidecars\<sidecar_name(save)>` with the body
   `{"format": "focc-sidecar", "save_name": <name>, "schema": 1, "sha256": <sha256 of the world_state text>,
   "world_state": {"counter": k, "probe": "P1"}}` (a temp file in the same folder, flushed and closed, then renamed
   over the target, like `sidecar.write`), logs `pre_save`.
3. `PostSaveGame` (5), `PreLoadGame` (6): logged.
4. `PostLoadGame` (7): reads the sidecar for the loaded save name, checks format, schema, save name and checksum
   (`sidecar.decode`'s checks), logs `post_load` with `found`, `valid`, `counter` and, on a valid file, adopts its
   counter.
5. It never deletes a file but its own temp file of a failed write. SFSE sends no message on save deletion
   (`engine-feasibility.md` section 1), so orphaned sidecars are listed offline by `sidecar.orphans()`; the probe's
   checker does that from the collected folder.

Every JSON line is also written to the SFSE log as `step=event <line>`. The P1 world state is a stub, not a
`model.WorldState`: group C's checker verifies the envelope (format, schema, save name, checksum over the sorted-keys
JSON of `world_state`), as the probe plan's P1 pass rule says. `sidecar.decode` in Python would reject the stub at
`WorldState.from_json`, by design.

### Where the files land

`<Starfield>\Data\SFSE\Plugins\FOCCSidecar\focc_sidecar.log` and `...\FOCCSidecar\sidecars\*.focc`. The folder is
found with `GetModuleFileNameW` on the dll itself, so the sidecars and their log are not written under Documents
(Controlled Folder Access blocks our writes there; `scripts/bridge/make_bridge.py`). The plugin's SFSE log is libxse's,
`Documents\My Games\Starfield\SFSE\Logs\FOCCSidecar.log`, where SFSE writes its own logs and where FO4SFPipboyMenu's log
was written on the PC on 10 Nov. The job card copies all three into the testqueue folder.

### Log format

One JSON object per line, CRLF, appended (never rewritten), keys `seq` and `time` (UTC) first:

```
{"seq": 1, "time": "...", "event": "load", "plugin": "FOCCSidecar", "plugin_version": 2, "sfse_version": "0x...", "runtime_version": "1.16.244.0", "messaging": true, "registered": true, "dir": "..."}
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

The plugin writes nothing of its own unless `<Starfield>\Data\SFSE\Plugins\FOCCSidecar.ini` holds

```
[FOCCSidecar]
bEnabled=1
```

Without the file, the section or the key, or with any other value, the plugin logs `step=off` in its SFSE log and
registers nothing, writes nothing in its folder and creates no folder. The repo's `FOCCSidecar.ini` (copied by
`build.ps1`) says `bEnabled=0`; the session sets 1 in the installed copy and deletes the dll and the ini afterwards.

## Build card for the PC (FAL-216)

Game closed. The repo checked out at the PR head; the PC's x64 environment; a new staging folder each time:

```powershell
powershell -File sfse\FOCCSidecar\build.ps1 -Out D:\Modding\staging\focc_sidecar_<date> -Env D:\Modding\tools\msvc_env.ps1
```

`-Lib` defaults to `D:\Modding\tools\libxse-commonlibsf` (libxse `9d090c4`, `lib\commonlib-shared` at `9fbb74d`),
as for FOCCPing and FO4SFPipboyMenu; the script is theirs with this plugin's name and its three codec files. Expect
exit `0`, then `FOCCSidecar.dll`, `FOCCSidecar.pdb`, `FOCCSidecar.ini` (`bEnabled=0`) and `build.json` in `-Out`;
`build.json` names libxse `9d090c4c521f4f2c1aa00bb05923c380d47ae596` and `9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d`,
`plugin_version` `0.2.0` and the dll's sha256. Post the exit code, the dll's sha256 and, on exit 1 (`build.cmd exit 90`
configure or `91` build), `xmake_output.txt` whole. It refuses an `-Out` that already holds a dll; after exit 90 or 91
the same `-Out` runs again.

**Install (by hand, game closed):** `FOCCSidecar.dll` and `FOCCSidecar.ini` into `<Starfield>\Data\SFSE\Plugins\`,
`bEnabled=1` in that ini, and `versionlib-1-16-244-0.bin` there too if it is not already (the session installs it
for the other plugins). Record the sha256s. **Run** through `sfse_loader.exe`. **Uninstall:** delete the dll and the
ini (and, once collected, the `FOCCSidecar\` folder beside them). The runbook's P1 card has the save and load steps and
the judge (`python -m fo4sf.combined.probes p1 <folder>`).

## Verified offline (Linux container, 2026-10-21; the codec only since FAL-216)

- `codec.h` + `sha256.cpp` compiled with `g++ -std=c++20 -Wall -Wextra -Werror` and were run against
  `src/fo4sf/combined/sidecar.py`: `sidecar_name` and the full body text are byte-identical to Python's for
  `focc_p1_a`, `Autosave 1`, `Quicksave`, names with `/ : ? " \`, leading/trailing dots, control characters, a 200-char
  name (the 80-cut), and the checker's recomputation (`sha256(json.dumps(body["world_state"], sort_keys=True))`) equals
  the `sha256` field. SHA-256 agrees with `hashlib` on the empty string and on lengths 55, 56, 63, 64, 119, 120 and
  1000 (padding boundaries). `decode_sidecar` round-trips, and rejects a tampered body and another save's body.
- The first build's `FOCCSidecar.cpp` (removed in FAL-216) passed a clang syntax check against the real `PluginAPI.h`
  then, and the PC built it on 28 Oct. Neither says anything about the libxse build in `src/`.

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

## Not verified (the first build and run settle these)

- **The libxse build of this plugin has never been compiled** (no MSVC here). FOCCPing's and FO4SFPipboyMenu's
  builds use the same script and library; compile errors are cheap and come back whole.
- `std::filesystem::rename` over an existing sidecar on the PC (MSVC's STL replaces the target, as the C++ standard
  asks; a failure logs `"written": false` with `rename failed <code>`). The write is flushed and closed before the
  rename but not forced to disk (the old build's `FlushFileBuffers` and `MOVEFILE_WRITE_THROUGH`); a power cut between
  save and rename can lose that one sidecar, which P1 does not test.
- **Save-name semantics**: `Hooks_Serialization.cpp` dispatches `a_name` as `const char*` with `dataLen = strlen`;
  whether it is the display name, the `.sfs` stem or a path, and its encoding, are unverified. The log's `save` and
  `save_hex` fields exist so the checker can compare against the `.sfs` names and report, not guess.
- Whether `PreSaveGame` also fires for autosaves, quicksaves and exit-saves, and whether `PostLoadGame` fires on the
  first load from the main menu, are unverified; every event is logged, so the log answers it.
