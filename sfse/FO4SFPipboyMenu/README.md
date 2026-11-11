# FO4SFPipboyMenu: Pip-Boy step 1 probe (FAL-187)

One question: **can a plugin of ours register a menu of its own and show a movie of its own** on Starfield
1.16.244.0? The plugin registers one named menu, `FO4SF_PipboyMenu`, opens it on one key, closes it on the same key,
and logs every step. The stage is picked by `Stage` in `FO4SFPipboyMenu.ini`:

- **(a)** `Stage=1`: the menu with no movie.
- **(b)** `Stage=2`: the same menu showing `Interface/FO4SF_PipboyMenu.swf`, a filled green rectangle with a
  dot-matrix label, from `FO4SFPipboyProbe - Main.ba2`.

- **(c)** `Stage=3` (FAL-216): (b) with the data channel. The movie (staged with `--channel`) has a text field and a
  button; the plugin writes the player's position into the field while the menu is open, hears the button's click, and
  logs the pause state and who holds input. Section "Stage (c): the data channel".
- **(d)** `Stage=4` (FAL-272): the STAT page, the first page the owner uses by hand. The movie (staged with `--page`)
  has a title, a tab line, seven lines and two buttons; the plugin fills the lines twice a second with the player's
  health, level and experience, carry weight, `FO4SF_Rads`, cell, worldspace and game time (tab 1, STATUS) or with
  live data (tab 2, DATA). NEXT TAB switches the tab, CLOSE closes the menu. Section "Stage (d): the STAT page"; the
  owner's card is `docs/spikes/pipboy-stat-page-owner-card.md`.

`Stage=0` (as shipped) logs one line and does nothing else.

| File | What |
| --- | --- |
| `src/main.cpp` | the plugin: version guard, checks before use, the menu object, the key thread |
| `src/pch.h` | precompiled header (libxse's game headers and SFSE layer) |
| `FO4SFPipboyMenu.ini` | `Stage`, `Key` (default `0x79`, F10), `Flags` (0), `KeepAlive` (1); stage (c): `FlagSets` (`0x0,0x8,0x9`), `SnapshotKey` (`0x7A`, F11); stage (d): `PageFlagSets` (`0x9`) |
| `xmake.lua`, `build.ps1` | the PC build: FOCCPing's build path (`docs/spikes/combined-core-probes.md`, B0-2) |
| `scripts/ui/make_probe_swf.py` | writes the stage (b) movie, with `--channel` the stage (c) one and with `--page` the stage (d) one (pure Python; tests `tests/test_make_probe_swf.py`, `tests/test_pipboy_stat_page.py`) |
| `scripts/ui/make_pipboy_probe.py` | stages the empty `FO4SFPipboyProbe.esm` and the movie; `check` checks the plugin |
| `scripts/ui/pipboy_probe_install.py` | stage (b) install with its own record (test `tests/test_pipboy_probe_install.py`) |

## Design: the engine's menu object, not libxse's IMenu class

The plugin is built on libxse/commonlibsf `9d090c4` for SFSE, the Address Library, the logger, `UI::RegisterMenu`,
`UI::IsMenuOpen`, `UIMessageQueue::AddMessage` and `BSFixedString`. It does **not** use libxse's `IMenu` class: every
`IMenu` virtual there is `REL::ID{ 0 }`, and a lookup of id 0 stops the game. Instead the menu object is the engine's
own: memory of ours, the engine's IMenu constructor, then a copy of the engine's primary IMenu vtable with only our
slots replaced. The two other vtables stay the engine's, as the constructor set them.

The slot before the copy holds the engine's RTTI complete object locator for IMenu, read from the slot before the
engine's primary vtable (the one `step=rtti vtable=primary` checks). MSVC's `dynamic_cast` reads the locator there,
and the engine casts a shown menu from `IMenu` to `GameMenuBase`. Our object is a plain IMenu, so that cast returns
null. The shipped movie-less menu of a public precedent gets null there too: its menu carries its plugin's own RTTI,
and MSVC's cast compares type descriptors by decorated name (`.?AVGameMenuBase@RE@@` is not the game's
`.?AVGameMenuBase@@`). The engine accepts that null: at `782f944a` both stages passed in the game as a plain IMenu,
ten toggles each with `match=yes`, and at (b) our movie drawn (owner PC, 10 Nov, 20:02 and 20:06 UTC). The run at
`b3f352b7` had no locator in that slot: the cast read whatever global lay before the copy, and the game hung right
after the show message (PC hang dump, 10 Nov). A `GameMenuBase` build exists in history only (`d750f393`, never built
or run).

With the constructor's own flags (`Flags=0`) the open menu neither pauses the game nor takes its input: the HUD stays
and the game runs behind it (the same run). Stage (c) records what other flags do.

| Slot | Ours |
| --- | --- |
| 0x00 | destructor wrapper: the engine's destructor without its delete, then our `free` |
| 0x03, 0x04 | `GetName` (`FO4SF_PipboyMenu`), `GetRootPath` (`""`: our movie has no code to bind) |
| 0x05 | `GetViewScaleMode`: ShowAll |
| 0x06 | `LoadMovie`: (a) returns true with no movie; (b) the engine's, logged, with the event dispatcher off |
| 0x08 | `ProcessMessage`: the engine's, logged; at (a) our own answer to show; at (c) the data channel and at (d) the page, after the engine's handling |
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
- **Pause and input:** `step=snapshot tag=<t> paused=<Main::isGameMenuPaused> menus=<n>[name,...]
  contexts=<n>[id,...]`: the open menus among a short list of names, and ControlMap's active input contexts in stored
  order. Tags: `show`, `open` (every tenth update), `hide` (on the menu's thread), `main_after_open` and
  `main_after_close` (main thread, 750 ms after each toggle), and `key` (main thread, on `SnapshotKey`, F11).
  `menus=` asks the engine's own `IsMenuRegistered` and `IsMenuOpen` (the calls `Register` and `Toggle` make) about
  each name, on the main thread only; on the menu's thread it is `-`. The first such snapshot logs `step=menu_names
  registered=... not_registered=...`: only `Console` is a name libxse states, the others are guesses. (At `e7925e00`
  it read libxse's `UI::menuStack` at +0x3F0, which gave `menus=0[]` in every snapshot, in the game's own pause menu
  too: that offset is wrong for 1.16.244, so the read is gone.)
- **Flag sets:** open k gets the constructor's flags OR `Flags` OR entry `(k - 1) mod n` of `FlagSets`, at creation and
  again at kShow (`step=flags show=<k> set=<i> had=<f> now=<f>`). Shipped: `0x0` (the constructor's own), `0x8`
  (libxse's `ShowCursor`, bit 3) and `0x9` (bit 3 and bit 0; bit 0 is Fallout 4's "pauses game", unverified in
  Starfield). The snapshot's `paused=` and `menus=` show what each set does.

**Checked first, at stages (c) and (d) only** (stages (a) and (b) check exactly their 16 ids, as before). Thirteen more
ids, each in the file, non-zero, inside the image and equal through libxse; then `step=channel_ids`:

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
movie's own type is logged. The input contexts, the pause byte and the position are layouts only libxse states; their
reads are guarded, so a wrong offset logs `fault` or a wrong number, not a crash.

**Not verified until the session:** that `getChildByName` finds timeline children of a movie with no code; that the
embedded font draws; that our menu gets the mouse (the flag sets test it); that kUpdate reaches an open menu of ours;
what `isGameMenuPaused` and the context ids mean (the controls below settle it).

## Stage (d): the STAT page (FAL-272)

The first page the owner uses by hand, on the channel test C proved at `e7925e00` (text in, click out at flag set
`0x9`). The movie (`make_probe_swf.py --page`, no code, under the same name `Interface/FO4SF_PipboyMenu.swf`) is a
green panel of 70 % x 76 % of the screen with the title `FO4SF PIP-BOY  STAT`, a tab line `fo4sfTab`, seven lines
`fo4sfLine0` to `fo4sfLine6`, the hint `F10 OPENS AND CLOSES THIS PAGE` and two buttons the size of test C's CLICK:
`fo4sfTabButton` (NEXT TAB) and `fo4sfCloseButton` (CLOSE). Its embedded font is the 5 x 7 table plus `' , ( ) ? ! + %
& _ # =`; the plugin writes upper case and turns any other character into `?`, at most 54 to a line.

| Tab | Lines |
| --- | --- |
| 1 STATUS | `HEALTH <n>`; `LEVEL <n>   XP <n>`; `CARRIED <n>   MAX <n>`; `RADS <n>` or `RADS NOT INSTALLED`; `CELL <name> (<form id>)`; `WORLD <name> (<form id>)` or `WORLD NONE (INTERIOR)`; `TIME <hh:mm>   DAY <n>` |
| 2 DATA | `POSITION X Y Z`; `UPDATES <n>   (TWO A SECOND)`; `NEXT TAB CLICKS <n>   CLOSE CLICKS <n>`; `OPENS <n>   FLAGS <f>`; `GAME PAUSED <n>`; `MENUS <n>[...]`; `DAYS PASSED <d.dddd>` |

How it runs, the channel's way:

- **Main thread** (SFSE's task, in `Toggle` before each kShow and in `SendUpdate` before each kUpdate, so about twice
  a second while open): `PageCollect` reads every value and formats both tabs under a lock. All reads of the game and
  the one call into it (`GetActorValue`) happen here.
- **Menu's thread** (our `ProcessMessage`): kShow sets tab 1, adds our two `FunctionHandler`s as the buttons'
  `"click"` listeners (once per movie, `step=listen name=<button> ... added=1`) and writes the tab; every kUpdate writes
  it again and reads each field back (`step=page n=<k> ... fields=8/8 set=8 match=8 text="<all eight lines>"`, for
  n = 1 to 20, then every 20th, and on the first 20 that do not read back).
- **The buttons:** the handlers only count and raise a flag (`step=click button=tab n=<k> tab=<t>`, `step=click
  button=close n=<k>`). The key thread then sends an update at once (NEXT TAB), or closes the menu on the main thread
  as F10 does (CLOSE: `step=close n=<k> by=button was_open=1 sent=hide`, then `step=state n=<k> open=0 expected=0
  match=yes`; a close counts as a press in the `n` of these lines).
- **Flags:** `PageFlagSets` (default `0x9`, the set at which test C's clicks reached our menu) cycles per open like
  `FlagSets`. DATA's `GAME PAUSED` is the pause byte, live: at `e7925e00` no set paused the game.

Where each value comes from, and what is checked before it is used:

| Value | Read | Checked first |
| --- | --- | --- |
| health, carry weight (`CarryWeight`), carried weight (`InventoryWeight`, if an actor value of that name exists), experience (`Experience`), `FO4SF_Rads` | the player's `ActorValueOwner::GetActorValue` with the `ActorValueInfo` form of that editor ID | the form: found by editor ID in the data handler's AVIF list, typed `ActorValueInfo` by RTTI. The call: next line |
| the `GetActorValue` slot | the player's `ActorValueOwner` vtable, slot 0x01 | the base's offset from `PlayerCharacter`'s RTTI class hierarchy; that subobject's vtable locator names `PlayerCharacter` at that offset; slot 0x00 is the adjustor thunk to the player's own slot 0x00 (its destructor). libxse declares a virtual destructor before `GetActorValue`, SFSE 0.2.21 none: the thunk decides. Otherwise `refuse step=page what=get_actor_value ...` and every actor value is `?` |
| level | the player's base object (`OBJ_REFR::objectReference`), its `TESActorBaseData`, `ACTOR_BASE_DATA::level` | the base is a `TESNPC` by RTTI; the base class offset from its hierarchy, its subobject checked as above. That the player's level lives there is a **supported hypothesis** (it does in Skyrim and Fallout 4) |
| cell, worldspace | `TESObjectREFR::parentCell`, then `TESObjectCELL::cellWorldspace`; each name through its `TESFullName` (the pool string at +0x08) | `TESObjectCELL` and `TESWorldSpace` by RTTI; `TESFullName`'s offset from the hierarchy, subobject checked. An exterior cell usually has no name: `NO NAME` and its form id, which changes as the player crosses cells |
| game time | the `GameHour` and `GameDaysPassed` globals (`TESGlobal::value`) | found by editor ID in the data handler's GLOB list, typed `TESGlobal` by RTTI. `Starfield.esm` has them as `00000038` and `00000039` (docs/ai/test-queue.md) |
| editor IDs and names | the `BSStringPool` entry (libxse: an 0x18-byte header, then the characters; flag 0x02 at +0x14 points on at +0x08) | `step=page_strings self_test=ok`: our own menu name read back through the same reader first; if it does not read back, no name and no form list is read |
| the data handler's lists | `TESDataHandler::formArrays` at +0x70, 0x18 each; AVIF is type 0x6D, GLOB 0x0A (libxse and SFSE 0.2.21 agree on all four) | the one new id, `TESDataHandler.Singleton` 937572, must equal SFSE 0.2.21's own address `0x5FD9B28` (`sfse/GameData.h`), else `refuse step=page_ids` and the plugin stays idle; the object is a `TESDataHandler` by RTTI; every entry is typed before its editor ID is read |

The page's checks never stop the plugin: a value that fails prints `?` and its reason is logged once, as
`step=page_unknown what=<value> reason=...`. `step=page_forms list=AVIF ... found=... missing=... weight_names=...`
also lists every actor value whose editor ID holds WEIGHT, ENCUMB or MASS, so the right carried-weight value can be
named if `InventoryWeight` is missing. Credits are not on the page: no plain getter exists for an item count.

**Not verified until the session:** that the AVIF and GLOB lists keep editor IDs at runtime; the slot thunk; that the
level is the base's; which names the game uses for its menus.

## Build (PC)

From a checkout at the PR head, in the PC's x64 environment:

```
powershell -File sfse\FO4SFPipboyMenu\build.ps1 -Out <new staging folder> -Lib <libxse-commonlibsf at 9d090c4> -Env <msvc_env.ps1>
```

Exit 0 leaves `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `build.json` (every sha256, both library commits) in
`-Out`. Nothing is installed. Exit 1 after `build.cmd exit 90` (configure) or `91` (build): see `xmake_output.txt`.

Stage the plugin and movie, and check the plugin (stage (c): `stage <exp folder> --channel`; stage (d): `stage <exp
folder> --page`; the movie keeps its name):

```
python scripts/ui/make_pipboy_probe.py stage <exp folder>
python scripts/ui/make_pipboy_probe.py check <exp folder>\FO4SFPipboyProbe.esm
```

## Install and uninstall (probe session only, game closed)

Install:

1. Copy `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `versionlib-1-16-244-0.bin` into
   `<Starfield>\Data\SFSE\Plugins\`. Set `Stage=1`, `2`, `3` or `4` in that copy of the ini.
2. Stages (b), (c) and (d): `python scripts/ui/pipboy_probe_install.py install --dir <exp folder> --starfield <game>`.
   This checks the stage, activates `FO4SFPipboyProbe.esm` and packs its `Data` tree into
   `FO4SFPipboyProbe - Main.ba2`, under its own record `Data\FO4SFPipboyProbe.install.json`; the installed
   experiment's `FO4SFExp.install.json` is not read or changed. A `plugin_toggle.py` hold makes it refuse, so run it
   between `plugin_toggle.py on` and `off`. `status`, `order` and `active` take `--starfield <game>` alone.

Uninstall:

1. Stages (b), (c) and (d): `python scripts/ui/pipboy_probe_install.py uninstall --starfield <game>`. This removes
   exactly what its record lists and the Plugins.txt line it added.
2. Delete `FO4SFPipboyMenu.dll` and `FO4SFPipboyMenu.ini` from `Data\SFSE\Plugins\`. Delete
   `versionlib-1-16-244-0.bin` too, unless it was there before the session.
3. Compare with the receipts taken before the install.

**Log:** `Documents\My Games\Starfield\SFSE\Logs\FO4SFPipboyMenu.log`. `SFSE::Init` opens it, named after the plugin.

## Job card

Load a save, wait until in control, then press the key ten times, about two seconds apart: five opens and five closes.
Take a screenshot while the menu is open after the fifth press, and one after the tenth.

### PASS at (a), `Stage=1`

1. The log shows, in this order: `step=load runtime=1.16.244.0 stage=1`, then `step=image`, sixteen `step=id` lines,
   three `step=rtti` lines, `step=slots`, `step=ctor`, `step=ready stage=a ... locator=<rva>`, `step=listen`,
   `step=post_data_load`, `step=register result=ok`, and `step=key_thread`.
2. Toggles: `step=toggle n=1..10`, alternating `sent=show` and `sent=hide`. Each toggle is followed by
   `step=state n=<same> ... match=yes`.
3. At least one `step=create ... vtables=engine rtti=engine`, and `step=message ... type=show` and `type=hide` lines.
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

### PASS at (d), `Stage=4` (the owner's card: `docs/spikes/pipboy-stat-page-owner-card.md`)

1. Everything in (b), with `stage=4` and `step=ready stage=d`, after `step=load_d flag_sets=0x9 snapshot_key=0x7a`
   and, before `step=ready`, `step=channel_ids value_functions=sfse_equal rtti_names=ok` and `step=page_ids
   data_handler=sfse_equal`; 30 `step=id` lines.
2. At the first open: `step=page_strings self_test=ok`, `step=page_actor_values ... get_actor_value_slot=0x01`,
   `step=object name=TESDataHandler`, `step=page_forms list=AVIF ... found=Health,CarryWeight,...` and `step=page_forms
   list=GLOB ... found=GameHour,GameDaysPassed`; then `step=listen name=fo4sfTabButton ... added=1` and `step=listen
   name=fo4sfCloseButton ... added=1`.
3. **Lines follow the game:** `step=page ... fields=8/8 set=8 match=8` lines whose `text=` changes with the game:
   `TIME` minutes move while the page is open, `HEALTH` after damage, `CELL` after the player crosses a cell or a door,
   `POSITION` and `DAYS PASSED` on tab 2. The controls (console, PC helper only): `player.getav health`,
   `player.getav carryweight`, `player.getlevel`, `getglobalvalue gamehour`, `player.getpos x`.
4. **NEXT TAB:** each click logs `step=click button=tab` and the next `step=page` shows the other tab (`tab=1` and
   `TAB 2 OF 2: DATA`, then back).
5. **CLOSE:** `step=click button=close`, `step=close ... by=button was_open=1 sent=hide`, `step=state ... open=0
   expected=0 match=yes`; F10 then opens the page again.
6. `RADS NOT INSTALLED` without the rads probe; with it (FAL-213), `RADS <n>` equal to `player.getav FO4SF_Rads`.

### What each failure line means

| Line | Meaning | Next |
| --- | --- | --- |
| `step=off` | `Stage` is not 1, 2, 3 or 4 in the ini next to the dll | set it |
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
| `step=create ... rtti=UNEXPECTED` | the slot before our object's primary vtable is not the engine's IMenu locator | stop before the next press: the engine's cast will read it |
| the log ends after `step=message ... type=show`, and the picture freezes | the engine's work after the show did not return (at `b3f352b7`: its cast on an object without a locator) | take a hang dump: each thread's instruction pointer as module plus offset, and the stack of the thread that created the menu |
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
| `refuse step=page_ids name=TESDataHandler.Singleton rva=<r> sfse_rva=0x5fd9b28` | (d): libxse's data handler id is not SFSE 0.2.21's address; the plugin stays idle | stop: one of the two is stale for this runtime |
| `refuse step=page what=strings ...` | (d): our own menu name did not read back through the pool-string reader: no editor ID or name is read, every such line is `?` | report the line (it shows what was read) |
| `refuse step=page what=actor_value_owner ...` or `what=get_actor_value ... slot0=... target0=... destructor=...` | (d): the player's ActorValueOwner was not found or its slot 0x00 is not the thunk to the destructor; every actor value is `?` | report the line: its slots and targets settle libxse's against SFSE's declaration |
| `refuse step=object name=TESDataHandler ...` or `refuse step=page_forms list=<l> reason=...` | (d): the data handler or one of its lists is not what libxse and SFSE say; the values from it are `?` | report the line (`other_type=` names what the list holds) |
| `step=page_forms ... missing=<names>` | (d): those editor IDs are not in the list. `FO4SF_Rads` missing is `RADS NOT INSTALLED`; another missing name prints `?` | read `weight_names=` and `sample=` |
| `step=page_unknown what=<value> reason=<r>` | (d): one value could not be read, once per kind; its line shows `?` | report the line |
| `step=page ... fields=0/8` | (d): `getChildByName` found none of the page's fields: the movie is not the `--page` one | re-stage with `--page` |
| `step=listen name=<button> ... added=1` but no `step=click` on a click | (d): the click did not reach the movie | read `step=flags`: the page needs `0x9` |

The probe changes no Starfield interface file, and nothing it makes goes into Git: no dll, no movie, no archive.
