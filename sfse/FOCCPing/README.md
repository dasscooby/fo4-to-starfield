# FOCCPing: the B0 bridge spike for SFSE

The plugin half of B0 (`docs/combined-core-cpp-port.md`, section 4; runbook `docs/spikes/combined-core-probes.md`,
section B0): can a quest script call our SFSE plugin and read its answer on Starfield 1.16.244? One Papyrus native,
`FOCC.Ping(int v)`, answers `v + 1`. The kit side (`scripts/combined_probes/FOCC.psc`, the declaration, and
`FOCC_B0.psc`, the console commands) is in the probe stage since #568. It is the owner's stack A (28 Oct 2026): the
Address Library as a dependency and a CommonLibSF, fixed where 1.16.244 breaks it. The plugin keeps no state and is
not the combined core's real plugin.

The library is **libxse/commonlibsf** (`9d090c4`, 6 Oct 2026; its submodule `lib/commonlib-shared` at `9fbb74d`).
The original Starfield-Reverse-Engineering/CommonLibSF is archived and points there; the first PC build of 28 Oct
found why it could not serve: the Address Library for 1.16.244 (v22) is format 5, and that library (`9caec20`, like
the archived main) reads format 2 only. libxse reads formats 1, 2 and 5, sets the SFSE version-data bit SFSE 0.2.21
counts as address independence (`AddressLibraryV2`), and carries the 1.15.216+ ids. It builds with xmake, not cmake.

Nothing of Bethesda's, of SFSE's or of CommonLibSF's is in this folder. libxse/commonlibsf (GPL-3.0-or-later with its
modding and linking exceptions, `COPYING` and `EXCEPTIONS` in its repository) is cloned on the PC; this plugin builds
against that checkout through a directory junction that `build.ps1` makes in the staging folder. The licence review
named in section 4 is owed before anything built on it ships; a spike dll ships nowhere.

## Files

| File | Role |
|---|---|
| `xmake.lua` | the plugin target in the shape of libxse/commonlibsf-template: `includes("lib/commonlibsf")`, the `commonlibsf.plugin` rule (it writes the SFSE version data), no install step |
| `src/main.cpp` | the plugin: the version guard, the checks before use (its own Address Library read, the `NativeFunctionBase` slots, the VM's type), the messaging listener, the native bound at `kPostDataLoad` |
| `src/pch.h` | the precompiled header (`RE/Starfield.h`, `SFSE/SFSE.h`) |
| `build.ps1` | PC build: xmake in the loaded MSVC environment into a new staging folder; `build.json` with every sha256 and both library commits |

`tests/test_sfse_ping_plugin.py` pins the contract between this folder, `FOCC.psc` and the runbook as text (no
compiler here).

## What it stands on (checked offline against libxse/commonlibsf `9d090c4`)

- **The Address Library.** `lib/commonlib-shared/src/REL/IDDB.cpp` opens `Data\SFSE\Plugins\versionlib-1-16-244-0.bin`
  (the plugin's folder, the game's file version with dashes) on the first id lookup, not at load. It reads formats 1,
  2 and 5; anything else is `REX::FAIL` ("Unsupported Address Library format"), a message box, and the game stops. The
  v22 file for 1.16.244 is format 5: header `05 00 00 00`, then the game version as four uint32 (`01 00 00 00`,
  `10 00 00 00`, `F4 00 00 00`, `00 00 00 00`), a 64-byte name, pointer size, data format and offset count, then a
  flat table of uint32 offsets indexed by id. The game version in the header must equal the exe's. SFSE itself
  (`PluginManager::checkAddressLibrary`) only checks that the file exists before loading a plugin that declares the
  library.
- **Version data.** The `commonlibsf.plugin` rule generates `SFSEPlugin_Version` from `xmake.lua`
  (`res/commonlibsf-plugin.cpp.in`): `UsesAddressLibrary(true)` sets `kAddressIndependence_AddressLibraryV2`
  (`include/SFSE/Interfaces.h`), `IsLayoutDependent(true)` the 1.14.70+ layout bit, `CompatibleVersions` the
  library's `RUNTIME_LATEST` (1.16.244 at `9d090c4`, `include/SFSE/Version.h`: the running game). SFSE 0.2.21's
  `PluginManager.cpp` treats a plugin with the V2 bit and a layout bit as version independent and skips the
  compatible-versions list, so that number does not gate the load;
  the old library's v1 bit was not counted, and a v1 plugin loads only through that list.
- **Binding the native.** libxse has no `SFSE::SetPapyrusCallback` (the old trampoline hook at
  `REL::ID(169912) + 0x514`, an id of the pre-1.15.216 space). `main.cpp` registers an SFSE messaging listener and,
  on `kPostDataLoad` (all game data loaded), binds through `RE::GameVM::GetSingleton()->GetVM()->BindNativeMethod("FOCC",
  "Ping", &Ping, std::nullopt, false)` (no tasklet flag, not latent). `ID::GameVM::Singleton` is `937585` in
  `include/RE/IDs.h` (the auto-generated 1.15.216+ ids). A global native takes `std::monostate` in the self slot
  (`RE/B/BSScriptUtil.h`). `FOCC.pex` is linked when the console first calls `FOCC_B0.Ping`, after the bind. No hook,
  no trampoline (`SFSE::Init(a_sfse, { .trampoline = false, .hook = false })`). The tasklet flag is left out on purpose:
  with it, libxse also calls `IVirtualMachine::SetCallableFromTasklets`, one of an overloaded pair (libxse slots 0x1F
  and 0x20) whose order MSVC may lay out reversed, so the call could land on the other overload. Without it neither is
  called, and the VM keeps its own default for a native (a call from a tasklet then runs on the main thread).

## What is checked before the bind (FAL-216: the ids, library pin and checks of PR #704)

The plugin calls nothing it has not checked, and any mismatch is one `refuse step=<step>` line in `FOCCPing.log`, with
the plugin idle (no bind; the game runs on, and B0-2 reads `got=0`):

1. **Runtime 1.16.244.0 only** (`refuse step=version runtime=<v> expected=1.16.244.0`).
2. **The game image** is a PE32+ executable, whose size bounds every check below (`refuse step=image`).
3. **The Address Library, read by the plugin itself** from `versionlib-1-16-244-0.bin` next to the dll: format 5, game
   version 1.16.244.0, pointer size 8 (`refuse step=address_library reason=missing|short_header|header`); every id
   below the file's count, non-zero and inside `Starfield.exe`'s image (`refuse step=id name=<n> id=<i>
   reason=beyond_count|short_file|missing|outside_image`); then libxse's own lookup of each id must give the same
   offset (`reason=library_mismatch`). So libxse's lookup, which stops the game with a message box on a missing id,
   can never meet one.
4. **The game's own `NativeFunctionBase` vtable** (id 480710): its locator says offset 0 and the type descriptor that
   libxse's RTTI id 853245 names (`refuse step=rtti vtable=NativeFunctionBase`), and its slots 0x06, 0x0F, 0x10, 0x14
   and 0x15 are the five functions libxse's `NativeFunctionBase` forwards to (`refuse step=slots ... have=<rva>
   want=<rva>`). These are the functions the VM calls through our function object, so the ids and libxse's
   `IFunction` layout are both proven against the game before anything is bound.
5. **At `kPostDataLoad`:** the GameVM singleton is a `GameVM` by RTTI (id 865426, offset 0), the VM it holds is a
   `BSScript::Internal::VirtualMachine` by RTTI (id 870795; the `IVirtualMachine` subobject, offset logged), and the
   VM's slot 0x1E (libxse's `BindNativeMethod(IFunction*)`, the one call into the VM) is inside the image
   (`refuse step=object name=GameVM|VirtualMachine ...`). Reading the object pointers is guarded: a fault is a
   refusal line, not a crash.

| Name | Id | Source | Checked by |
| --- | --- | --- | --- |
| GameVM.Singleton | 937585 | libxse | file + libxse lookup; the object's RTTI |
| GameVM RTTI | 865426 | libxse `RTTI_GameVM` | the singleton's locator |
| VirtualMachine RTTI | 870795 | libxse `RTTI_BSScript__Internal__VirtualMachine` | the VM's locator |
| BSStringPool.GetEntry, Entry.Release | 1186742, 139340 | libxse | file + libxse lookup (the function's names) |
| NativeFunctionBase vtable | 480710 | libxse `VTABLE_BSScript__NF_util__NativeFunctionBase` | RTTI: offset 0, id 853245 |
| NativeFunctionBase RTTI | 853245 | libxse | the vtable's locator |
| NativeFunctionBase GetParam, Call, GetSourceFilename, GetParamInfo, Unk_15 | 138061, 138074, 138065, 138067, 138068 | libxse | vtable slots 0x06, 0x0F, 0x10, 0x14, 0x15 |
| Stack.GetPageForFrame, StackFrame.GetVariable | 138020, 84986 | libxse | file + libxse lookup (read when Ping is called) |

**Still unverified until the launch:** that slot 0x1E is `BindNativeMethod` (one source, libxse; only its place in
the image is checked), and that a native bound after the VM's own `BindEverythingToScript` is callable. B0-2's
`got=42` settles both.

- **Log:** `Documents\My Games\Starfield\SFSE\Logs\FOCCPing.log` (`SFSE::Init` opens it, named after the plugin).
  Lines: `FOCCPing v0.3.0.0` (the library's own, from `SFSE::Init`), `FOCCPing loaded on runtime 1.16.244.0`,
  `step=image`, `step=address_library ... format=5 version=1.16.244.0`, fourteen `step=id` lines, `step=rtti
  vtable=NativeFunctionBase offset=0x0 slots=0x06,0x0F,0x10,0x14,0x15 match`, `listening for PostDataLoad; FOCC.Ping
  binds then`; at the main menu `step=object name=GameVM`, `step=object name=VirtualMachine`, `step=bind slot=0x1e`,
  `bound FOCC.Ping`; then one `ping N -> N+1` per call. "no script VM at PostDataLoad: FOCC.Ping not bound" means the
  singleton or its VM was null then (a timing finding). A log that stops after `step=bind` with the game gone is a
  fault in the bind itself (slot 0x1E is not what libxse says; a crash dump, no message box).

## Building on the owner's PC (runbook section B0, job B0-2)

Prerequisites (on the PC since 28 Oct): the portable MSVC and SDK (`D:\Modding\tools\msvc_env.ps1` puts cl.exe and
xmake on PATH and sets `VCToolsInstallDir` and `WindowsSdkDir`), xmake 3.1.2 (`D:\Modding\tools\xmake-3.1.2`), and the
library checkout `D:\Modding\tools\libxse-commonlibsf` (`git clone --recurse-submodules
https://github.com/libxse/commonlibsf`, at `9d090c4`, `lib\commonlib-shared` at `9fbb74d`).

```powershell
powershell -File sfse\FOCCPing\build.ps1 -Out D:\Modding\staging\focc_ping_<date> -Env D:\Modding\tools\msvc_env.ps1
```

`-Lib` defaults to that checkout. xmake finds MSVC through Visual Studio installs or through `xmake f --sdk=<root>`, a
folder shaped like a VS root (`<root>\VC\Tools\MSVC\<ver>` and `<root>\Windows Kits\10`, its `find_build_tools`); the
PC has no VS install and keeps the SDK under `msvc\sdk\`, so the script builds that root in the staging folder from the
two environment variables (two directory junctions, `vsroot\VC` and `vsroot\Windows Kits`), or takes one as `-Sdk`.
It copies `xmake.lua` and `src\` to `<Out>\proj`, junctions `proj\lib\commonlibsf` to the checkout, clears
`XSE_SF_GAME_PATH` and `XSE_SF_MODS_PATH` (the library's rule would copy the dll into a game folder named by them),
runs `xmake f -y -p windows -a x64 -m releasedbg --toolchain=msvc --sdk=...` and `xmake build -y FOCCPing` with
stderr merged into `xmake_output.txt`, and copies `build\windows\x64\releasedbg\FOCCPing.dll` (and `.pdb`) to `-Out`.
The first configure fetches and builds spdlog through xmake's package manager (internet, a few minutes). It refuses an
`-Out` that already holds a dll; after a failed configure or build (exit 90 or 91) the same `-Out` runs again, keeping
the first run's junctions, project copy and xmake state, so the library is not rebuilt. `build.json` records xmake's
version, the compiler banner, the two library commits against the pinned ones, and every sha256. Compile errors on a
first build against a new library are expected and cheap.

**Build card for the PC (FAL-216).** From a checkout at the PR head, in the PC's x64 environment, a new staging folder
each time: the command above. Expect exit `0`, then `FOCCPing.dll`, `FOCCPing.pdb` and `build.json` in `-Out`;
`build.json` names libxse `9d090c4c521f4f2c1aa00bb05923c380d47ae596` and `9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d`
and the dll's sha256. Post the exit code, the dll's sha256 and, on exit 1, `xmake_output.txt` whole. The dll's own
version reads `0.3.0` (the log's first line, `FOCCPing v0.3.0.0`); an older `v0.2.0.0` in the log is the pre-FAL-216
build and must not be used.

## Install and run (the owner's line; game closed for the copies)

1. The Address Library's `.bin` into `<Starfield>\Data\SFSE\Plugins\` (its own name; `versionlib-1-16-244-0.bin` is
   what the library opens). The first row of `Format-Hex <path> | Select-Object -First 1` opens with `05 00 00 00`
   (format 5; the v22 file on the PC, 5,099,968 bytes, does). The PC keeps it in `D:\Modding\staging\addresslib_v22`;
   FO4SFPipboyMenu's sessions (FAL-187) put the same file in and take it out again. The plugin reads this file itself
   before anything else (section "What is checked before the bind").
2. `FOCCPing.dll` into the same folder.
3. Launch through `sfse_loader.exe`. The kit's rule: a dll that keeps the game from the main menu is deleted at once.
4. Runbook job B0-2: `cgf "FOCC_B0.Gmst"`, `cgf "FOCC_B0.Ping" 41`, `save focc_b0_a`, load it, `cgf "FOCC_B0.Ping" 43`,
   `cgf "FOCC_B0.Gmst"`; expect `b0 pong sent=41 got=42` and `got=44`. Collect `focc.0.log`, `FOCCPing.log` (as
   `sfse\FOCCPing.log`), the loader's output and, on `got=0`, `Papyrus.0.log`; judge
   `python -m fo4sf.combined.probes b0 <folder>`.
5. Uninstall (game closed): delete `FOCCPing.dll` before any other experiment. Delete `versionlib-1-16-244-0.bin`
   too, unless it was there before the session (it does nothing on its own, but the owner's set is put back exactly).
