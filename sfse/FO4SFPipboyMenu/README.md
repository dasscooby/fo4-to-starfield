# FO4SFPipboyMenu: Pip-Boy step 1 probe (FAL-187)

One question: **can a plugin of ours register a menu of its own and show a movie of its own** on Starfield
1.16.244.0? The plugin registers one named menu, `FO4SF_PipboyMenu`, opens it on one key, closes it on the same key,
and logs every step. Two stages, picked by `Stage` in `FO4SFPipboyMenu.ini`:

- **(a)** `Stage=1`: the menu with no movie.
- **(b)** `Stage=2`: the same menu showing `Interface/FO4SF_PipboyMenu.swf`, a filled green rectangle with a
  dot-matrix label, from `FO4SFPipboyProbe - Main.ba2`.

- **(c)** `Stage=3` (FAL-216): (b) with the data channel. The movie (staged with `--channel`) has a text field and a
  button; the plugin writes the player's position into the field while the menu is open, hears the button's click, and
  logs the pause state and who holds input. Section "Stage (c): the data channel".

`Stage=0` (as shipped) logs one line and does nothing else.

| File | What |
| --- | --- |
| `src/main.cpp` | the plugin: version guard, checks before use, the menu object, the key thread |
| `src/pch.h` | precompiled header (libxse's game headers and SFSE layer) |
| `FO4SFPipboyMenu.ini` | `Stage`, `Key` (default `0x79`, F10), `Flags` (0), `KeepAlive` (1); stage (c): `FlagSets` (`0x0,0x8,0x9`), `SnapshotKey` (`0x7A`, F11) |
| `xmake.lua`, `build.ps1` | the PC build: FOCCPing's build path (`docs/spikes/combined-core-probes.md`, B0-2) |
| `scripts/ui/make_probe_swf.py` | writes the stage (b) movie, and with `--channel` the stage (c) one (pure Python; test `tests/test_make_probe_swf.py`) |
| `scripts/ui/make_pipboy_probe.py` | stages the empty `FO4SFPipboyProbe.esm` and the movie; `check` checks the plugin |
| `scripts/ui/pipboy_probe_install.py` | stage (b) install with its own record (test `tests/test_pipboy_probe_install.py`) |

## Design: the engine's menu object, not libxse's IMenu class

The plugin is built on libxse/commonlibsf `9d090c4` for SFSE, the Address Library, the logger, `UI::RegisterMenu`,
`UI::IsMenuOpen`, `UIMessageQueue::AddMessage` and `BSFixedString`. It does **not** use libxse's `IMenu` class: every
`IMenu` virtual there is `REL::ID{ 0 }`, and a lookup of id 0 stops the game. Instead the menu object is the engine's
own: memory of ours, the engine's IMenu constructor, then a copy of the engine's primary IMenu vtable with only our
slots replaced. The two other vtables stay the engine's, as the constructor set them.

| Slot | Ours |
| --- | --- |
| 0x00 | destructor wrapper: the engine's destructor without its delete, then our `free` |
| 0x03, 0x04 | `GetName` (`FO4SF_PipboyMenu`), `GetRootPath` (`""`: our movie has no code to bind) |
| 0x05 | `GetViewScaleMode`: ShowAll |
| 0x06 | `LoadMovie`: (a) returns true with no movie; (b) the engine's, logged, with the event dispatcher off |
| 0x08 | `ProcessMessage`: the engine's, logged; at (a) our own answer to show; at (c) the data channel after the engine's handling |
| 0x0A | (a) only: `IsMovieLoaded` true |

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

libxse's `VTABLE_IMenu` array is `{ 475519, 475517, 475515 }`, not in subobject order. Read on the PC from the
1.16.244.0 executable (FAL-187, 10 Nov): 475519 at rva `0x4d7e938` has locator offset 0x50, 475517 at rva `0x4d7e950`
has 0x10. The first stage (a) run, with the two swapped, stopped at `refuse step=rtti vtable=BSInputEventUser ...
offset=0x50 expected_offset=0x10` before any registration.

Any mismatch logs one `refuse step=<step>` line and the plugin stays idle: no registration, no call into the game.

## Stage (c): the data channel (FAL-216)

The base under the Pip-Boy's pages: native code writes into our movie, and our movie calls native code. Nothing in
the movie is code (`make_probe_swf.py --channel`): the root holds two named children, a one-line text field
`fo4sfPosition` with its own embedded 5 x 7 font (`FO4SFDot`, so no game font is needed) and a button sprite
`fo4sfButton` labelled CLICK. The plugin does all of it from our `ProcessMessage`, after the engine's own handling, on
the engine's thread for this menu:

- **kShow:** the movie's ActionScript 3 root (`GetVariable("root")`), then `getChildByName("fo4sfButton")`, then our
  function (`CreateFunction` with our `FunctionHandler`) added as its `"click"` listener (`addEventListener`). Once per
  movie. Our handler logs `step=click n=<k>`; it is a static object whose count Scaleform raises and lowers but never
  takes to zero.
- **kShow and every kUpdate:** the player's position (the `PlayerCharacter` singleton, `TESObjectREFR::data.location`)
  as `X <x> Y <y> Z <z> CLICKS <k>` into the field's `text`, then read back: `step=field ... set=1 read_back=1
  match=yes`. The key thread sends one kUpdate every 500 ms while the menu is open (only after `IsMenuOpen` on the
  main thread says so), so the field follows the player while the menu is open.
- **Pause and input:** `step=snapshot tag=<t> paused=<Main::isGameMenuPaused> menus=<n>[type/flags,...]
  contexts=<n>[id,...]`: the UI menu stack (each entry's RTTI type, `ours` for our menu, and its flags) and ControlMap's
  active input contexts, both in stored order. Tags: `show`, `open` (every tenth update), `hide` (on the menu's
  thread), `main_after_open` and `main_after_close` (main thread, 750 ms after each toggle), and `key` (main thread, on
  `SnapshotKey`, F11).
- **Flag sets:** open k gets the constructor's flags OR `Flags` OR entry `(k - 1) mod n` of `FlagSets`, at creation and
  again at kShow (`step=flags show=<k> set=<i> had=<f> now=<f>`). Shipped: `0x0` (the constructor's own), `0x8`
  (libxse's `ShowCursor`, bit 3) and `0x9` (bit 3 and bit 0; bit 0 is Fallout 4's "pauses game", unverified in
  Starfield). The snapshot's `paused=` and the menu stack show what each set does.

**Checked first, at stage (c) only** (stages (a) and (b) check exactly their 16 ids, as before). Thirteen more ids, each
in the file, non-zero, inside the image and equal through libxse; then `step=channel_ids`:

| Name | Id | Source | Checked by |
| --- | --- | --- | --- |
| Main.Singleton | 883591 | libxse | file + libxse; the object's RTTI before the first read |
| PlayerCharacter.Singleton | 922868 | libxse | file + libxse; the object's RTTI before the first read |
| ControlMap.Singleton | 938003 | libxse | file + libxse; the object's RTTI before the first read |
| Main, PlayerCharacter, ControlMap RTTI | 859948, 860819, 867481 | libxse | the type descriptor's name (`.?AV` or `.?AU` + `Main@@`, `PlayerCharacter@@`, `ControlMap@@`) |
| GFx MovieImpl, GFx AS3 MovieRoot RTTI | 841612, 842209 | libxse | the type descriptor's name (`MovieImpl@GFx@Scaleform@@`, `MovieRoot@AS3@GFx@Scaleform@@`) |
| GFx Value ObjectAddRef, ObjectRelease, GetMember, SetMember, Invoke | 169745, 169746, 169748, 169749, 169750 | libxse | each equal to SFSE 0.2.21's own 1.16.244 address (`sfse/ScaleformValue.h` at 48535cc: `0x3352400`, `0x33524A0`, `0x33528A0`, `0x3352C90`, `0x33530B0`) |

Before first use: `Main`, `PlayerCharacter` and `ControlMap` are their types by RTTI at offset 0 (`step=object`), and
the pointer at movie + 0x18 is a `GFx::AS3::MovieRoot` by RTTI whose slots 0x30 (`CreateFunction`) and 0x32
(`GetVariable`) are inside the image (`step=movie_root`; libxse and SFSE 0.2.21 declare both at those slots). The
movie's own type is logged. The menu stack, the input contexts, the pause byte and the position are layouts only
libxse states; their reads are guarded, so a wrong offset logs `fault` or a wrong number, not a crash.

**Not verified until the session:** that `getChildByName` finds timeline children of a movie with no code; that the
embedded font draws; that our menu gets the mouse (the flag sets test it); that kUpdate reaches an open menu of ours;
what `isGameMenuPaused` and the context ids mean (the controls below settle it).

## Build (PC)

From a checkout at the PR head, in the PC's x64 environment:

```
powershell -File sfse\FO4SFPipboyMenu\build.ps1 -Out <new staging folder> -Lib <libxse-commonlibsf at 9d090c4> -Env <msvc_env.ps1>
```

Exit 0 leaves `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `build.json` (every sha256, both library commits) in
`-Out`. Nothing is installed. Exit 1 after `build.cmd exit 90` (configure) or `91` (build): see `xmake_output.txt`.

Stage the plugin and movie, and check the plugin (stage (c): `stage <exp folder> --channel`; the movie keeps its name):

```
python scripts/ui/make_pipboy_probe.py stage <exp folder>
python scripts/ui/make_pipboy_probe.py check <exp folder>\FO4SFPipboyProbe.esm
```

## Install and uninstall (probe session only, game closed)

Install:

1. Copy `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `versionlib-1-16-244-0.bin` into
   `<Starfield>\Data\SFSE\Plugins\`. Set `Stage=1`, `2` or `3` in that copy of the ini.
2. Stages (b) and (c): `python scripts/ui/pipboy_probe_install.py install --dir <exp folder> --starfield <game>`.
   This checks the stage, activates `FO4SFPipboyProbe.esm` and packs its `Data` tree into
   `FO4SFPipboyProbe - Main.ba2`, under its own record `Data\FO4SFPipboyProbe.install.json`; the installed
   experiment's `FO4SFExp.install.json` is not read or changed. A `plugin_toggle.py` hold makes it refuse, so run it
   between `plugin_toggle.py on` and `off`. `status`, `order` and `active` take `--starfield <game>` alone.

Uninstall:

1. Stages (b) and (c): `python scripts/ui/pipboy_probe_install.py uninstall --starfield <game>`. This removes exactly
   what its record lists and the Plugins.txt line it added.
2. Delete `FO4SFPipboyMenu.dll` and `FO4SFPipboyMenu.ini` from `Data\SFSE\Plugins\`. Delete
   `versionlib-1-16-244-0.bin` too, unless it was there before the session.
3. Compare with the receipts taken before the install.

**Log:** `Documents\My Games\Starfield\SFSE\Logs\FO4SFPipboyMenu.log`. `SFSE::Init` opens it, named after the plugin.

## Job card

Load a save, wait until in control, then press the key ten times, about two seconds apart: five opens and five closes.
Take a screenshot while the menu is open after the fifth press, and one after the tenth.

### PASS at (a), `Stage=1`

1. The log shows, in this order: `step=load runtime=1.16.244.0 stage=1`, then `step=image`, sixteen `step=id` lines,
   three `step=rtti` lines, `step=slots`, `step=ctor`, `step=ready stage=a`, `step=listen`, `step=post_data_load`,
   `step=register result=ok`, and `step=key_thread`.
2. Toggles: `step=toggle n=1..10`, alternating `sent=show` and `sent=hide`. Each toggle is followed by
   `step=state n=<same> ... match=yes`.
3. At least one `step=create ... vtables=engine`, and `step=message ... type=show` and `type=hide` lines.
4. No crash: the game is still running after the tenth press, and the second screenshot is the game in play.
5. Nothing of ours is visible at (a), because there is no movie. The open state is the log's `open=1`.

### PASS at (b), `Stage=2`

1. Everything in (a), with `stage=2` and `step=ready stage=b`.
2. `step=load_movie ... stage=b result=1 movie=<non-zero>`, and `step=sfse_movie_created` for our menu.
3. The open screenshot shows the green rectangle, centred, about 60 % by 50 % of the screen. It carries the dark label
   `FO4SF PIP-BOY PROBE`. The closed screenshot shows the game without it.

### PASS at (c), `Stage=3` (steps: `docs/spikes/pipboy-channel-bridge-session.md`)

1. Everything in (b), with `stage=3` and `step=ready stage=c`, after `step=load_c flag_sets=0x0,0x8,0x9
   snapshot_key=0x7a` and, before `step=ready`, `step=channel_ids value_functions=sfse_equal rtti_names=ok`.
2. **Text field in:** `step=movie_root ... root_type=.?AVMovieRoot@AS3@GFx@Scaleform@@`, then `step=field n=0 root=1
   field=1 set=1 read_back=1 match=yes text="X ... Y ... Z ... CLICKS 0"`, and further `step=field n=<k>` lines with
   changing numbers while the player moves with the menu open. The screenshot shows the line inside the green box. The
   control: the console's `player.getpos x`, `y` and `z` give the same numbers to the first decimal.
3. **Click out:** `step=listen root=1 button=1 function_type=<t> added=1 event=click`, then one `step=click n=1` per
   click on CLICK, and the next `step=field` reads `CLICKS 1`. The control: a click beside the button logs no
   `step=click`.
4. **Pause and input:** a `step=snapshot` line at `show`, `open`, `hide`, `main_after_open`, `main_after_close` and on
   each F11, for each flag set (opens 1 to 3: `set=0`, `1`, `2`). This stage records them; it passes or fails nothing
   on its own. Its controls are F11 in play with no menu, and F11 with the game's own pause menu open (Esc).

### What each failure line means

| Line | Meaning | Next |
| --- | --- | --- |
| `step=off` | `Stage` is not 1, 2 or 3 in the ini next to the dll | set it |
| `refuse step=version` | the runtime is not 1.16.244.0 | nothing to do on that runtime |
| `refuse step=ini key=` | `Key` is 0 or above 0xFE | fix the ini |
| `refuse step=image` | the game image does not look like a PE32+ executable | report |
| `refuse step=address_library reason=missing` | the bin file is not next to the dll | install it |
| `refuse step=address_library reason=header` | wrong format, version or pointer size | the 1.16.244.0 format 5 file is needed |
| `refuse step=id ... reason=...` | an id is beyond the file, zero, outside the image, or libxse gives another offset | `NEEDS-PC lookup <id>` |
| `refuse step=rtti` | a vtable id does not name an IMenu vtable at that subobject offset | the vtable ids are stale: look them up again |
| `refuse step=slots` | a slot is not the function its id names, or LoadMovie is not SFSE's hook address | the precedent's function ids are stale |
| `refuse step=ctor` | the constructor id does not load the primary vtable | the constructor id is stale |
| `refuse step=listen` | SFSE gave no messaging or task interface | report the SFSE version |
| `refuse step=register reason=name_taken` / `not_taken` / `no_ui` | the menu name is in use, the engine did not take our registration, or no UI singleton | report the log |
| `refuse step=key_thread` | the key thread could not start | report |
| `refuse step=toggle n=<n> reason=no_ui_or_queue` | the key was pressed before the UI or its message queue existed; nothing was sent | press again once in play; report if it repeats |
| `refuse step=create reason=out_of_memory` | allocation failed on open | report |
| `step=create ... vtables=UNEXPECTED` | the constructor set other vtables than the checked ones | stop: the layout differs |
| `step=state ... match=no` | the menu did not open or close as asked | read the `step=message` lines around it |
| `step=load_movie ... result=0` | (b): the engine's loader did not take our movie | check that the plugin is active and the archive is named after it. Then try the variant with an empty ActionScript 3 document class (the generator gains it then) |
| the log ends without `step=destroy` after a close, then a crash | the engine freed or used our object differently | collect the crash log; try `KeepAlive=1` if it was 0 |
| `refuse step=ini snapshot_key=` | (c): `SnapshotKey` above 0xFE or equal to `Key` | fix the ini |
| `refuse step=channel_ids name=GFx.Value.<f> rva=<r> sfse_rva=<s>` | (c): libxse's id for a Scaleform Value function is not SFSE 0.2.21's address | stop: one of the two is stale for this runtime |
| `refuse step=channel_ids name=<x>.RTTI type=<t>` | (c): an RTTI id does not name its type | the id is stale: look it up again |
| `refuse step=object name=<x> ... (its reads stay off)` | (c): a singleton is not its type; that reading logs `?` from then on | report the type the line names |
| `refuse step=channel what=movie_root ...` or `what=root_slots` | (c): the movie's root is not an ActionScript 3 MovieRoot, or its slots leave the image; no Scaleform call is made for the rest of the session | report the types the line names |
| `step=listen ... button=0` or `step=field ... field=0` | (c): `getChildByName` did not find the child | the movie needs a document class that declares its children (the generator gains it then) |
| `step=field ... set=1 read_back=1 match=yes` but no text on screen | (c): the field took the text and the embedded font did not draw | screenshot; the font is the next item |
| `step=listen ... added=1` but no `step=click` on a click | (c): the click did not reach the movie (no cursor or no mouse input to our menu) | compare the flag sets' opens: the cursor bit is set 1 |
| `step=field ... text="NO POSITION ..."` | (c): the player singleton was not readable as a PlayerCharacter | read the `step=object name=PlayerCharacter` line |

The probe changes no Starfield interface file, and nothing it makes goes into Git: no dll, no movie, no archive.
