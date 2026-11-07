# Combined core: porting the simulation to C++ (plan, 28 October 2026)

This is a plan. Nothing in it has run in game. **Status, 1 November 2026 (Claude-cloud-2): steps 1 and 2 are done
offline.**
- Step 1: the Python guards for the seed range and ASCII ids; the event log measured over one game year (section 5).
- Step 2 (C1): `sfse/FOCCSim/` is the portable core. `tests/test_combined_cpp_parity.py` shows it byte-identical to
  Python after every tick for every world below.

C2 to C5 and everything on the PC are still to do. It carries out the 28 October decision in `docs/ai/decisions.md`:
the in-game sim is a C++ port inside our SFSE plugin, and the Python model in `src/fo4sf/combined/` stays the
reference. The owner's order (28 October): the GAMMA core comes first, with probes P1 to P10, then the seed rerun
with all DLC, then a 20-place slice in game. The rerun is done ("Real pack, all DLC" in `docs/combined-core.md`).

## 1. What moves to C++ and what stays Python

Stays Python. These run offline, or at install time on the player's machine, where the converters already run:
- `seed` and `seedpack` (pack generation);
- `pack` (validation);
- `balance`, the probe judges in `probes.py`, and the `sidecar.py` reference codec.

The plugin starts from a world state that Python wrote (`WorldState.to_json`, schema 2). It never reads a pack.

Moves to C++, in this order. Each step is one PR with its own parity tests:

| Step | Python | Lines | In game it does |
|---|---|---|---|
| C1 | `model.py` (state, JSON), `modes.py`, `reputation.py`, `sim.py` (`tick`, `_distances`, player hooks) | about 990 | the 6-hour tick |
| C2 | `adapter.py` (`game_view`, `changes`) | 159 | which keyword data and globals Papyrus must write |
| C3 | `present.py` (`plan`, `diff`) | 187 | what to spawn and dissolve near the player |
| C4 | `manage.py`, `jobs.py` | 519 | the player's settlement actions and radiant jobs |
| C5 | `news.py` | 149 | terminal text (later; dynamic terminal text has its own engine question) |

## 2. The parity contract

"The same results" means byte-identical state:
- Same input: one state JSON, one number of ticks, and the same player actions at the same hours.
- Same output: byte-identical canonical JSON after every tick (`json.dumps(..., sort_keys=True)` with the default
  separators, as `WorldState.to_json` writes it).
- The harness compares a sha256 per tick, and prints both texts at the first tick that differs.

The test worlds are all synthetic, so they are in the repo:
- the fixtures (`fixtures.py`);
- the Commonwealth-scale draft (`tests/test_combined_seedpack.py`, `commonwealth_scale_draft()`, through
  `seedpack.generate`);
- variants of each: raid pressure low and high, and story mode on with an active story;
- a scripted list of player actions (defend, trade, help) at fixed hours.

Each world runs seeds 0 to 9 for 90 days.

The real pack is derived from the owner's files, so it never enters the repo. Its parity check runs on the PC
only.

The harness is a Python unittest. It compiles the portable core (no Windows, no SFSE) with `g++` on CI, which runs
on ubuntu-24.04, and compares the output against Python. That makes it the repo's first compiled test.
`sfse/FOCCSidecar/codec.h` was only checked by hand (its README, "Verified offline"); this harness should cover it
too. On the PC the same core is built with `cl.exe` by the plugin's `build.ps1`, and the parity run is repeated
there once.

## 3. What the port must copy exactly

**RNG.** The sim draws from `random.Random(seed * 1_000_003 + hour)`. That is Python's MT19937 with these parts:
- seeding: `init_by_array` over the absolute seed, split into 32-bit words, low word first;
- `random()`: two draws, `(a >> 5) * 67108864 + (b >> 6)`, divided by 2^53;
- `choice`: `_randbelow(n)`, which takes `getrandbits(k)` with k = n's bit length and rejects results until one is
  below n.

`std::mt19937` seeds differently, so the port carries its own 40-line generator. **Verified 28 Oct 2026:** that
generator matched Python 3.13 on 300 mixed `random()` and `randrange` draws for 10 seeds from 0 to 2^64 - 1. The
prototype and its checker are in the project folder, `research/combined-core/cpp-port/`. CI's Python 3.12 uses the
same algorithm, and the parity tests pin it.

**Seed range.** `seed * 1_000_003 + hour` must fit in 64 unsigned bits. The port refuses a state outside that. The
Python model should refuse it too: `WorldState` accepts any integer today. That is a small change in its own PR.

**Floats.** Three comparisons use doubles:
- the attack roll in `_faction_tick` (`rng.random() * 100 > aggression * 0.25 * pressure`);
- the raid chance in `_raider`;
- the capture roll in `_resolve_arrivals`.

Write each one in Python's left-to-right order. Build with `-ffp-contract=off` (GCC and Clang) and `/fp:precise`
without `/fp:contract` (MSVC), so no fused multiply-add changes a rounding.

**Integer division.** Python's `//` floors; C++'s `/` truncates toward zero. Every `//` in the sim has
non-negative operands today. The port still uses a floor-division helper, and asserts.

**Order.** Every Python walk is sorted. `std::map<std::string, ...>` orders bytes, which matches Python for ASCII
ids. `pack._is_id` accepts any non-empty string, so validation should also require ASCII. The places that need
explicit comparators:
- tuple sorts: targets `(place, hours, origin)`, squads by `(is garrison, id)`, neighbours `(place, hours)`;
- `max` and `min` ties: Python keeps the first in sorted order.

**Events.** Each event is an open dict: `hour`, `kind`, `place`, `region`, plus per-kind fields that can hold
null, a bool or a cargo dict. The port stores a small typed variant and writes it as canonical JSON.

The sim reads its own log. `_lost_places` scans every holder change, and `_resettle_safe` scans back 48 hours.
Trimming the log would therefore change results. The port keeps the whole log first. Trimming it later needs two
indexes, proved equal by the parity tests:
- the places each faction has lost;
- the last hour of fighting at each place.

The log's growth sets the sidecar's size. Measure it in Python on the real pack over one game year before the
port.

**JSON.** The plugin reads only world-state JSON that our Python wrote, and writes canonical JSON. A small reader
of our own for that one shape will do, like `codec.h`'s envelope reader. No third-party library.

## 4. The blocker: Papyrus cannot call our plugin through SFSE's public API

**Verified 28 Oct 2026.** SFSE's `PluginAPI.h` at the commit `fetch_pluginapi.ps1` pins (`48535cc`) offers four
interfaces: messaging, trampoline, menu and task. It has no Papyrus native registration and no access to game
data. SFSE has had custom Papyrus natives since 0.1.1
(`docs/research/framework/combined-core-notes/engine-feasibility.md`), but not through that header.

The in-game sim needs to:
- read game time and the player's location;
- have Papyrus call it for the player's actions;
- hand back the `changes()` list for Papyrus to apply.

That needs a Papyrus bridge. The usual route is CommonLibSF, which offers Papyrus native registration and game
types. The tool verdict (`docs/ai/decisions.md`, 28 October, "which outside tools we use") put CommonLibSF under "later,
for a named job", and this is that job. Its costs:
- **Licence:** GPL with exceptions, reviewed before anything built on it ships.
- **Addresses:** it relies on community reverse-engineered addresses for runtime 1.16.244, which a game update can
  break.
- **A second player dependency:** it usually needs the Address Library plugin, which players would install like
  SFSE. The owner's "SFSE required" decision covers SFSE only, so this one is the owner's call before anything
  ships.

**Step B0, a spike before any in-game port:**
- One native, `FOCC_Ping(int) -> int`, registered through CommonLibSF on 1.16.244 and called from a test quest
  script.
- Pass: the value comes back, and the native still works after a save and a load.
- Setup: CommonLibSF's build tools on the PC. The owner approved them on 28 October 2026 and Install put them under
  `D:\Modding\tools`, nothing elevated: MSVC 14.44, Windows SDK 10.0.26100, cmake 4.4.5, ninja 1.13.2, vcpkg
  (baseline `15b12b99`); CommonLibSF `9caec20` configured with the preset `build-release-msvc-ninja`, spdlog from
  vcpkg's builtin registry (upstream's spdlog registry is gone), an overlay triplet pointing vcpkg at the portable
  toolchain. No plugin has been built yet.

**Checked 28 October 2026, offline, against CommonLibSF `9caec20` (the commit on the PC) and that setup:**
- **spdlog.** Upstream's `vcpkg.json` pins no spdlog version: it names `spdlog` from a git registry
  (ThirdEyeSqueegee/vcpkg-ports, baseline `6e8f58e0`) that no longer resolves, and its builtin baseline `89dc8be6`
  would give spdlog 1.15.3 with fmt 11.0.2. CommonLibSF touches spdlog in four places: `include/SFSE/Logger.h`
  (`spdlog::format_string_t`, `spdlog::log`, `spdlog::source_loc`), `src/SFSE/Logger.cpp` (`basic_file_sink_mt`,
  `msvc_sink_mt`, `spdlog::logger`, `set_default_logger`, `set_pattern`, `flush_on`), `include/SFSE/Impl/PCH.h`
  (`<spdlog/spdlog.h>`, `spdlog::log`) and `find_package(spdlog CONFIG REQUIRED)`. All of it is in 1.17.0, and the
  format-string type follows whichever variant the package was built as (fmt here, 12.2.0), so Install's spdlog
  1.17.0 fits. Building the library is the check; nothing else to pin.
- **Address Library.** `SFSE::Init` loads the address database before anything else (`src/SFSE/API.cpp`,
  `REL::IDDatabase::get()`), from `Data\SFSE\Plugins\versionlib-<runtime>.bin` (`src/REL/ID.cpp`); a missing file
  is `report_and_fail` ("failed to open address library file"). So every CommonLibSF plugin, B0's included, needs the
  Address Library for SFSE Plugins installed. v22 covers 1.16.244
  (`docs/research/framework/engine-mechanics-notes/wave2-rechecks.md`, section 3); its download is a Nexus login,
  so the owner's, and it is the second player dependency named above.
- **Runtime.** `9caec20` dates from 15 September 2025. `include/SFSE/Version.h` ends at `RUNTIME_SF_1_14_74` and
  nothing in the library names 1.15 or 1.16. The Papyrus registration B0 needs (`SFSE::SetPapyrusCallback`) is a
  trampoline call hook at `REL::ID(169912) + 0x514` inside `GameVM::GameVM`, so B0 stands on that id resolving on
  1.16.244 and on that offset still being the `BindEverythingToScript` call. Neither is verified; 1.15.216 and
  1.16.236 each broke the address-based plugins once already, and the research note has CommonLibSF moving on to
  libxse (`tools-and-scripting.md`, "Precedents and lessons" and row 5.2; libxse itself is unchecked). A missing
  id stops the game with a message box; a wrong offset is a crash. One launch tells, and the kit's rule holds: a
  dll that keeps the game from the main menu is deleted at once.
- **A bridge with no game addresses.** Two mechanisms are already verified on this PC without an address or a
  game structure: Papyrus to plugin through a traced log line the plugin tails, and plugin to game memory through a
  setting found by its name (`sfse/FO4SFBorder`, 24 October). A bridge on those survives game updates but is
  narrow (one value per setting per poll); whether Papyrus can read a setting back (`Utility.GetINI*`) is
  unverified and is the one check it needs (Starfield's `Utility.psc` stub on the PC).

**The owner's call, put on 28 October:**
- A. The Address Library as a dependency, and B0 as written: one build, one launch; it may fail on 1.16.244 for
  the reasons above.
- B. A bridge with no game addresses. B0 becomes: a quest script traces `ping 41`, the plugin writes 42 into a
  named setting, the script reads it back and traces it; after a save and a load the same. No new dependency.
- C. Check libxse first (does it track 1.16.244, and on what addresses), then choose between A and B.

**The owner's answer, 28 October, 16:45 UTC:** A first, with the brief to make sure it does not break and to fix it
if it does; B is fine as the backup; C when needed, since a mod as a requirement is no problem unless it restricts
the modding of the finished work. So B0 runs on stack A: the Address Library v22 installed, CommonLibSF `9caec20`
built on the PC, and one plugin, `sfse/FOCCPing`, binding `FOCC.Ping`; if the 1.16.244 hook fails, the fix goes
into the library (the id, the offset) before B comes in. The kit side is in the probes runbook as section B0:
B0-1 (`FOCC_B0.Gmst`, Papyrus reads the probe plugin's game setting `iFOCC_Pong`; no SFSE plugin, so it runs with any
probe session and also proves B's return leg) and B0-2 (`FOCC_B0.Ping`, the native, before and after a save and a
load); `python -m fo4sf.combined.probes b0` judges both.

**Checked 28 October 2026, evening, after the first PC build:** `FOCCPing.dll` compiled against `9caec20` on the first
try, and the Address Library check before its install found the break: the v22 `versionlib-1-16-244-0.bin` is format
5 (header `05 00 00 00`, then 1, 16, 244, 0), and `9caec20` (like the archived upstream main) reads format 2 only, so
the dll would have stopped the game at `SFSE::Init` with "Unsupported address library format: 5". It was not installed.
Option C's question answered itself: the original repository is archived and points to **libxse/commonlibsf**
(`9d090c4`, 6 October 2026), whose shared layer reads formats 1, 2 and 5 (`lib/commonlib-shared/src/REL/IDDB.cpp`,
`load_v5`: a flat table of offsets indexed by id), sets the version-data bit SFSE 0.2.21 counts as address independence
(`kAddressIndependence_AddressLibraryV2`; `9caec20` set the v1 bit, which `PluginManager.cpp` no longer counts), and
carries the 1.15.216+ ids (`include/RE/IDs.h`, `ID::GameVM::Singleton` 937585). It builds with xmake 3.0+, not cmake.
libxse has no `SFSE::SetPapyrusCallback`; `sfse/FOCCPing` now binds the native on SFSE's `kPostDataLoad` message
through `RE::GameVM::GetSingleton()->GetVM()->BindNativeMethod`, with no hook of its own. So stack A stands, with the
library changed under it: B0 runs on libxse/commonlibsf, and "fix it where 1.16.244 breaks it" cost no patch of ours.
Still unverified until the first launch: that the GameVM singleton is set by `kPostDataLoad`, and that a native bound
after the VM's own `BindEverythingToScript` is callable from `FOCC.pex`.

**If B0 fails, or the licence does not fit:**
- The 20-place slice runs in Papyrus, if P5 shows a Papyrus tick over 20 places is fast enough. P5 on the owner's
  PC (28 Oct) measured 2.42 ms per place for its tick of one global per place, so about 50 ms for 20 places of
  that shape. A real tick does more per place, so measure the slice's own tick before relying on it.
- The full Commonwealth (about 230 places) stays offline until a bridge exists.
- A Papyrus port cannot match the Python rolls, because Papyrus floats are 32-bit. The three rolls would become
  integer rolls in the reference model first, with a new balance baseline.

## 5. Steps

Each step is one PR, with green CI and an independent review.

1. **Offline (Python):** the seed-range and ASCII-id checks; the event-log growth over one game year on a
   synthetic Commonwealth-scale world. **Done.**
   - `sim.rng_seed` refuses a per-tick seed outside `[0, 2**64)`, and so does `WorldState.from_json`.
   - `pack._is_id` and `model._check_state` refuse non-ASCII ids.
   - Event-log growth: the synthetic Commonwealth-scale draft (234 places, 38 settlements, 7 factions) was measured
     over 365 game days for seeds 0, 1 and 2.

   | Day | Events | Event JSON | Whole state |
   |---|---|---|---|
   | 30 | 1,818 to 1,899 | 0.27 to 0.29 MB | 0.35 to 0.36 MB |
   | 90 | 3,190 to 3,305 | 0.46 to 0.48 MB | 0.54 to 0.56 MB |
   | 180 | 5,241 to 5,359 | 0.74 to 0.77 MB | 0.82 to 0.84 MB |
   | 365 | 9,124 to 9,235 | 1.27 to 1.29 MB | 1.35 to 1.36 MB |

   The state starts at 0.075 MB. So the sidecar holds about 1.3 MB after a game year, almost all of it the event log.
   That is the number the trimming indexes in section 3 would cut, and that the sidecar's save-time cost should be
   measured against (P1). Real-pack numbers come from the PC.
2. **Offline, C1:** a portable core in `sfse/FOCCSim/`, with no Windows or SFSE code. It holds the generator, the
   state with its JSON reader and writer, and the tick. Plus the parity harness and its unittest. **Done** (README
   there).
   - Byte-identical to Python after every tick (`FO4SF_PARITY_FULL=1`):
     - the fixture world for seeds 0 to 9 over 90 days, with raid pressure low and high, story mode, and scripted
       help, defend and trade;
     - the Commonwealth-scale draft for seeds 0 to 9 over 90 days.
   - The CI default runs a lighter set, about 19 s.
   - The generator was also checked on its own against Python for seeds 0, 1, 2^32 - 1, 2^32 and 2^64 - 1.
   - Not built with cl.exe yet.
3. **Offline, C2 to C4:** each step with its parity tests.
4. **PC:** probes P2 to P10, then P1 (restaged from main and queued on 28 Oct).
5. **PC:** bridge spike B0 on stack A (the owner's call, 28 October): B0-1 with the kit alone, then the Address
   Library (on the PC since 24 October), the CommonLibSF build, `sfse/FOCCPing` (the plugin, in the repo) and B0-2
   (runbook section B0). The build tools are in.
6. **PC:** the 20-place slice.
   - Python slices the real pack to the 20 places nearest the Commonwealth slice.
   - The plugin keeps the state in the save's sidecar (P1) and ticks every 6 game hours.
   - Papyrus applies `changes()` to keyword data (P2) or globals.
   - One encounter comes from `present.plan`.
   - Pass: save, leave and return, and the world has moved on.
7. **Later:** the whole Commonwealth in game, after the slice's tick cost is measured. Tracy comes in here, as the
   tool verdict says.

## 6. What the owner decides, and when

- Nothing for steps 1 to 4.
- Before step 5: the bridge stack. Decided 28 October: A, B as the backup, C when needed (section 4).
- Before shipping anything built on it: the Address Library as a player dependency, and the CommonLibSF licence
  check.
