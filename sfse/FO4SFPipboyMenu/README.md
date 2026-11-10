# FO4SFPipboyMenu: Pip-Boy step 1 probe (FAL-187)

One question: **can a plugin of ours register a menu of its own and show a movie of its own** on Starfield
1.16.244.0? The plugin registers one named menu, `FO4SF_PipboyMenu`, opens it on one key, closes it on the same key,
and logs every step. Two stages, picked by `Stage` in `FO4SFPipboyMenu.ini`:

- **(a)** `Stage=1`: the menu with no movie.
- **(b)** `Stage=2`: the same menu showing `Interface/FO4SF_PipboyMenu.swf`, a filled green rectangle with a
  dot-matrix label, from `FO4SFPipboyProbe - Main.ba2`.

`Stage=0` (as shipped) logs one line and does nothing else.

| File | What |
| --- | --- |
| `src/main.cpp` | the plugin: version guard, checks before use, the menu object, the key thread |
| `src/pch.h` | precompiled header (libxse's game headers and SFSE layer) |
| `FO4SFPipboyMenu.ini` | `Stage`, `Key` (default `0x79`, F10), `Flags` (0), `KeepAlive` (1) |
| `xmake.lua`, `build.ps1` | the PC build: FOCCPing's build path (`docs/spikes/combined-core-probes.md`, B0-2) |
| `scripts/ui/make_probe_swf.py` | writes the stage (b) movie (pure Python; test `tests/test_make_probe_swf.py`) |
| `scripts/ui/make_pipboy_probe.py` | stages the empty `FO4SFPipboyProbe.esm` and the movie; `check` checks the plugin |
| `scripts/ui/pipboy_probe_install.py` | stage (b) install with its own record (test `tests/test_pipboy_probe_install.py`) |

## Design: the engine's GameMenuBase object, not libxse's menu classes

The plugin is built on libxse/commonlibsf `9d090c4` for SFSE, the Address Library, the logger, `UI::RegisterMenu`,
`UI::IsMenuOpen`, `UIMessageQueue::AddMessage` and `BSFixedString`. It does **not** use libxse's `IMenu` or
`GameMenuBase` classes: every `IMenu` virtual there is `REL::ID{ 0 }`, and a lookup of id 0 stops the game. Instead
the menu object is the engine's own `GameMenuBase`:

1. memory of ours and the engine's IMenu constructor (1.16.244 has no separate `GameMenuBase` constructor: the game's
   menu factories run the IMenu constructor and then set up `GameMenuBase` inline);
2. `+0x128` and `+0x130` cleared, as a public precedent's `GameMenuBase` constructor does (`+0x130` is the
   pause-request state);
3. a copy of the engine's `GameMenuBase` primary vtable, with only our slots replaced, and the engine's RTTI complete
   object locator for it in the slot before the copy;
4. the engine's own `GameMenuBase` vtables at `+0x10` and `+0x50`.

Why `GameMenuBase`: right after our creator returns, the engine reference-casts the new menu to `GameMenuBase`. With a
plain IMenu (`b3f352b7`) that cast threw `std::bad_cast`, nothing caught it, and the game stopped (the PC's crash
watcher dump, 10 Nov; what first looked like a freeze was that unhandled error being recorded). With the locator in
place our object's RTTI says `GameMenuBase`, so the cast succeeds.

| Slot | Ours |
| --- | --- |
| 0x00 | destructor wrapper: the engine's destructor without its delete, then our `free` |
| 0x03, 0x04 | `GetName` (`FO4SF_PipboyMenu`), `GetRootPath` (`""`: our movie has no code to bind) |
| 0x05 | `GetViewScaleMode`: ShowAll |
| 0x06 | `LoadMovie`: (a) returns true with no movie; (b) the engine's, logged, with the event dispatcher off |
| 0x08 | `ProcessMessage`: the engine's, logged; at (a) our own answer to show |
| 0x0A | (a) only: `IsMovieLoaded` true |
| 0x10, 0x11 | (a) only: IMenu's `OnAddedToMenuStack` and `OnRemovedFromMenuStack`; `GameMenuBase`'s assume a movie, as a public precedent's movie-less menu notes. (b) keeps `GameMenuBase`'s |

`LoadMovie` and `ProcessMessage` call IMenu's functions (the ids `step=slots` checks), as the public precedents do.

## Game version and where every id comes from

**Accepted runtime: 1.16.244.0 only.** Any other runtime logs `refuse step=version` and the plugin stays idle, as
FO4SFBorder does. The Address Library file `versionlib-1-16-244-0.bin` (format 5) is read by the plugin itself from
its own folder before anything else. Every id must be below the file's count, non-zero, and inside Starfield.exe's
image, and libxse's own lookup must return the same offset.

| Name | Id | Source | Checked by |
| --- | --- | --- | --- |
| UI.Singleton | 937580 | libxse | file + libxse lookup |
| UI.RegisterMenu | 130463 | libxse | file + libxse lookup |
| UI.IsMenuOpen | 130475 | libxse | file + libxse lookup |
| UIMessageQueue.Singleton | 937897 | libxse | file + libxse lookup |
| UIMessageQueue.AddMessage | 130659 | libxse | file + libxse lookup |
| BSStringPool.GetEntry | 1186742 | libxse | file + libxse lookup |
| BSStringPool.Entry.Release | 139340 | libxse | file + libxse lookup |
| IMenu vtable, primary | 475515 | libxse `VTABLE_IMenu[2]` | RTTI: locator offset 0, type `.?AVIMenu@@` |
| IMenu vtable, BSInputEventUser | 475517 | libxse `VTABLE_IMenu[1]` | RTTI: offset 0x10 (10 slots) |
| IMenu vtable, BSTEventSink | 475519 | libxse `VTABLE_IMenu[0]` | RTTI: offset 0x50 (2 slots) |
| IMenu RTTI type descriptor | 844868 | libxse `RTTI_IMenu` | the three locators point at it |
| IMenu constructor | 130615 | a public precedent | its first 0x200 bytes load the primary vtable |
| IMenu scalar deleting destructor | 130616 | a public precedent | primary vtable slot 0x00 |
| IMenu::LoadMovie | 130618 | a public precedent | slot 0x06, and equal to SFSE 0.2.21's own hook address `0x2551AB0` |
| IMenu::ProcessMessage | 130624 | a public precedent | slot 0x08 |
| IMenu::IsMovieLoaded | 130619 | a public precedent | slot 0x0A |
| GameMenuBase vtables | 434723, 434725, 434721 | libxse `VTABLE_GameMenuBase[0..2]` | ordered by their locators' offsets (0, 0x10, 0x50), then RTTI: type `.?AVGameMenuBase@@` |
| GameMenuBase RTTI type descriptor | 852954 | libxse `RTTI_GameMenuBase` | the three locators point at it |
| GameMenuBase::OnAddedToMenuStack | 93620 | a public precedent | `GameMenuBase` primary slot 0x10 |
| GameMenuBase::OnRemovedFromMenuStack | 93621 | a public precedent | `GameMenuBase` primary slot 0x11 |

libxse's `VTABLE_IMenu` array is `{ 475519, 475517, 475515 }`, not in subobject order. Read on the PC from the
1.16.244.0 executable (FAL-187, 10 Nov): 475519 at rva `0x4d7e938` has locator offset 0x50, 475517 at rva `0x4d7e950`
has 0x10. The first stage (a) run, with the two swapped, stopped at `refuse step=rtti vtable=BSInputEventUser ...
offset=0x50 expected_offset=0x10` before any registration.

Any mismatch logs one `refuse step=<step>` line and the plugin stays idle: no registration, no call into the game.

## Build (PC)

From a checkout at the PR head, in the PC's x64 environment:

```
powershell -File sfse\FO4SFPipboyMenu\build.ps1 -Out <new staging folder> -Lib <libxse-commonlibsf at 9d090c4> -Env <msvc_env.ps1>
```

Exit 0 leaves `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `build.json` (every sha256, both library commits) in
`-Out`. Nothing is installed. Exit 1 after `build.cmd exit 90` (configure) or `91` (build): see `xmake_output.txt`.

Stage the plugin and movie, and check the plugin:

```
python scripts/ui/make_pipboy_probe.py stage <exp folder>
python scripts/ui/make_pipboy_probe.py check <exp folder>\FO4SFPipboyProbe.esm
```

## Install and uninstall (probe session only, game closed)

Install:

1. Copy `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `versionlib-1-16-244-0.bin` into
   `<Starfield>\Data\SFSE\Plugins\`. Set `Stage=1` or `Stage=2` in that copy of the ini.
2. Stage (b) only: `python scripts/ui/pipboy_probe_install.py install --dir <exp folder> --starfield <game>`.
   This checks the stage, activates `FO4SFPipboyProbe.esm` and packs its `Data` tree into
   `FO4SFPipboyProbe - Main.ba2`, under its own record `Data\FO4SFPipboyProbe.install.json`; the installed
   experiment's `FO4SFExp.install.json` is not read or changed. A `plugin_toggle.py` hold makes it refuse, so run it
   between `plugin_toggle.py on` and `off`. `status`, `order` and `active` take `--starfield <game>` alone.

Uninstall:

1. Stage (b) only: `python scripts/ui/pipboy_probe_install.py uninstall --starfield <game>`. This removes exactly
   what its record lists and the Plugins.txt line it added.
2. Delete `FO4SFPipboyMenu.dll` and `FO4SFPipboyMenu.ini` from `Data\SFSE\Plugins\`. Delete
   `versionlib-1-16-244-0.bin` too, unless it was there before the session.
3. Compare with the receipts taken before the install.

**Log:** `Documents\My Games\Starfield\SFSE\Logs\FO4SFPipboyMenu.log`. `SFSE::Init` opens it, named after the plugin.

## Job card

Load a save, wait until in control, then press the key ten times, about two seconds apart: five opens and five closes.
Take a screenshot while the menu is open after the fifth press, and one after the tenth.

### PASS at (a), `Stage=1`

1. The log shows, in this order: `step=load runtime=1.16.244.0 stage=1`, then `step=image`, twenty-two `step=id`
   lines, three IMenu `step=rtti` lines, `step=slots`, `step=ctor`, `step=gmb_order`, three `GameMenuBase` `step=rtti`
   lines, `step=gmb_slots`, `step=ready stage=a class=GameMenuBase ... locator=<rva>`, `step=listen`,
   `step=post_data_load`, `step=register result=ok`, and `step=key_thread`.
2. Toggles: `step=toggle n=1..10`, alternating `sent=show` and `sent=hide`. Each toggle is followed by
   `step=state n=<same> ... match=yes`.
3. At least one `step=create ... class=GameMenuBase vtables=engine rtti=engine`, and `step=message ... type=show` and `type=hide` lines.
4. No crash: the game is still running after the tenth press, and the second screenshot is the game in play.
5. Nothing of ours is visible at (a), because there is no movie. The open state is the log's `open=1`.

### PASS at (b), `Stage=2`

1. Everything in (a), with `stage=2` and `step=ready stage=b`.
2. `step=load_movie ... stage=b result=1 movie=<non-zero>`, and `step=sfse_movie_created` for our menu.
3. The open screenshot shows the green rectangle, centred, about 60 % by 50 % of the screen. It carries the dark label
   `FO4SF PIP-BOY PROBE`. The closed screenshot shows the game without it.

### What each failure line means

| Line | Meaning | Next |
| --- | --- | --- |
| `step=off` | `Stage` is not 1 or 2 in the ini next to the dll | set it |
| `refuse step=version` | the runtime is not 1.16.244.0 | nothing to do on that runtime |
| `refuse step=ini key=` | `Key` is 0 or above 0xFE | fix the ini |
| `refuse step=image` | the game image does not look like a PE32+ executable | report |
| `refuse step=address_library reason=missing` | the bin file is not next to the dll | install it |
| `refuse step=address_library reason=header` | wrong format, version or pointer size | the 1.16.244.0 format 5 file is needed |
| `refuse step=id ... reason=...` | an id is beyond the file, zero, outside the image, or libxse gives another offset | `NEEDS-PC lookup <id>` |
| `refuse step=rtti` | a vtable id does not name an IMenu vtable at that subobject offset | the vtable ids are stale: look them up again |
| `refuse step=slots` | a slot is not the function its id names, or LoadMovie is not SFSE's hook address | the precedent's function ids are stale |
| `refuse step=ctor` | the constructor id does not load the primary vtable | the constructor id is stale |
| `refuse step=rtti vtable=GameMenuBase ... reason=offset` | a `GameMenuBase` vtable id has no locator at 0, 0x10 or 0x50, or two share one | `NEEDS-PC lookup` the three ids |
| `refuse step=gmb_slots` | `GameMenuBase`'s primary slots 0x10, 0x11 are not the precedent's stack callbacks, or its destructor is outside the image | the layout differs: report the line |
| `refuse step=listen` | SFSE gave no messaging or task interface | report the SFSE version |
| `refuse step=register reason=name_taken` / `not_taken` / `no_ui` | the menu name is in use, the engine did not take our registration, or no UI singleton | report the log |
| `refuse step=key_thread` | the key thread could not start | report |
| `refuse step=toggle n=<n> reason=no_ui_or_queue` | the key was pressed before the UI or its message queue existed; nothing was sent | press again once in play; report if it repeats |
| `refuse step=create reason=out_of_memory` | allocation failed on open | report |
| `step=create ... vtables=UNEXPECTED` | the constructor set other vtables than the checked ones | stop: the layout differs |
| `step=create ... rtti=UNEXPECTED` | the slot before our object's primary vtable is not the engine's `GameMenuBase` locator | stop before the next press: the engine's cast will read it |
| the log ends after `step=message ... type=show`, and the game stops answering | an unhandled error after the show (at `b3f352b7`: `std::bad_cast` from the engine's cast to `GameMenuBase`) | read the crash watcher's dump first: the exception record of the thread that created the menu |
| `step=state ... match=no` | the menu did not open or close as asked | read the `step=message` lines around it |
| `step=load_movie ... result=0` | (b): the engine's loader did not take our movie | check that the plugin is active and the archive is named after it. Then try the variant with an empty ActionScript 3 document class (the generator gains it then) |
| the log ends without `step=destroy` after a close, then a crash | the engine freed or used our object differently | collect the crash log; try `KeepAlive=1` if it was 0 |

The probe changes no Starfield interface file, and nothing it makes goes into Git: no dll, no movie, no archive.
