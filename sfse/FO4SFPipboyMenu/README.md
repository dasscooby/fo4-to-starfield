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
- **(e)** `Stage=5` (FAL-301): the page kit. One movie for every page (staged with `--kit`): main tabs, sub-tabs, a
  scrolling list with a selection bar, value rows, a footer and key hints. The pages are data: sections of this
  plugin's ini. Keys and clicks move between them. Section "Stage (e): the page kit"; the owner's card is
  `docs/spikes/pipboy-page-kit-owner-card.md`.

`Stage=0` (as shipped) logs one line and does nothing else.

| File | What |
| --- | --- |
| `src/main.cpp` | the plugin: version guard, checks before use, the menu object, the key thread |
| `src/pch.h` | precompiled header (libxse's game headers and SFSE layer) |
| `FO4SFPipboyMenu.ini` | `Stage`, `Key` (default `0x79`, F10), `Flags` (0), `KeepAlive` (1); stage (c): `FlagSets` (`0x0,0x8,0x9`), `SnapshotKey` (`0x7A`, F11), `ClickCall` (empty: off); stages (d) and (e): `PageFlagSets` (`0x9`), `CloseKeys` (`0x09,0x1B`), `HoldMenuKeys` (1); stage (e): `KitUp` to `KitNextTab`, and the pages (`[Kit]`, `[Page <TAB>/<SUB>]`) |
| `xmake.lua`, `build.ps1` | the PC build: FOCCPing's build path (`docs/spikes/combined-core-probes.md`, B0-2) |
| `scripts/ui/make_probe_swf.py` | writes the stage (b) movie, with `--channel` the stage (c) one and with `--page` the stage (d) one (pure Python; tests `tests/test_make_probe_swf.py`, `tests/test_pipboy_stat_page.py`) |
| `scripts/ui/make_pipboy_kit.py` | the page kit (stage (e)): reads and checks the pages of the ini (`--check`) and writes the kit's movie for them (pure Python, on `make_probe_swf.py`; tests `tests/test_pipboy_kit.py`) |
| `scripts/ui/make_pipboy_probe.py` | stages the empty `FO4SFPipboyProbe.esm` and the movie (`--channel`, `--page` or `--kit`); `check` checks the plugin |
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
| 0x08 | `ProcessMessage`: the engine's, logged; at (a) our own answer to show; at (c) the data channel, at (d) the page and at (e) the kit, after the engine's handling |
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

**Checked first, at stages (c) to (e) only** (stages (a) and (b) check exactly their 16 ids, as before). Sixteen
more ids, each in the file, non-zero, inside the image and equal through libxse; then `step=channel_ids`. These
thirteen, and the three of the click's section below:

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

### Stage (c) with `ClickCall`: a click reaches a quest (FAL-246, B0-3)

The bridge FOCCPing tests (B0-2) runs from script to native. The Pip-Boy, the perk and S.P.E.C.I.A.L. screens,
lockpicking and a C.A.M.P. menu need the other direction: a click causes a script action. With
`ClickCall=<script>.<function>` (shipped empty: off), each `step=click` also queues, on the main thread through SFSE's
task interface, one call of that global Papyrus function through the script VM's `DispatchStaticCall` (libxse's
`IVirtualMachine` slot 0x2F). The session uses `ClickCall=FOCC_B0.Click`: the combined probe kit's B0 script resolves
its probe quest (`FOCC_Probe.Q`) and logs `b0 click` in `focc.0.log` through that quest's `Trace`.

Three more ids, checked like the others at stage (c) (in the file, non-zero, inside the image, equal through libxse,
the RTTI ids by name in `step=channel_ids`); they are FOCCPing's:

| Name | Id | Source | Checked by |
| --- | --- | --- | --- |
| GameVM.Singleton | 937585 | libxse | file + libxse; the object's RTTI (`GameVM`, offset 0) before the first read |
| GameVM, BSScript.Internal.VirtualMachine RTTI | 865426, 870795 | libxse | the type descriptor's name (`GameVM@@`, `VirtualMachine@Internal@BSScript@@`) |

Before the first call: the VM the GameVM holds (libxse `GameVM::impl`, +0xE0, a guarded read) is a
`BSScript::Internal::VirtualMachine` by RTTI at offset 0 (`IVirtualMachine` is its first base), and its vtable's
slots 0x00 to 0x2F are inside the image (`step=object name=VirtualMachine ... dispatch_static_call=<rva>`). Then each
click logs `step=dispatch n=<k> call=FOCC_B0.Click queued=<0|1>`.

**No arguments, no callback.** Arguments go into a `BSScrapArray` the VM hands over; growing it calls
`ScrapHeap::Allocate`, which libxse 9d090c4 states as `REL::ID{ 0 }` (a lookup of id 0 stops the game). So the
argument function returns true and never touches the array; the function's own line carries the evidence. The
callback is a null functor, as the two public precedents that call `DispatchStaticCall` on libxse pass it (a web-view
UI framework and a co-op mod). Passing values (which item was clicked) needs the scrap heap's ids first: the next step.

**Not verified until the session:** that slot 0x2F is `DispatchStaticCall` on 1.16.244 (libxse's declaration; the
precedent fork's agrees, but it is the same library's lineage, and SFSE 0.2.21 declares no VM vtable). A wrong slot
can stop the game at the first click, so the session card runs this last, in a launch of its own. Also open: whether
the VM runs the call while our menu is open or only after it closes (the card's 10-second hold reads it from the two
logs' clocks), and that the queued call needs no other thread than the main one.

## Stage (d): the STAT page (FAL-272)

The first page the owner uses by hand, on the channel test C proved at `e7925e00` (text in, click out at flag set
`0x9`). The movie (`make_probe_swf.py --page`, no code, under the same name `Interface/FO4SF_PipboyMenu.swf`) is a
green panel of 70 % x 76 % of the screen with the title `FO4SF PIP-BOY  STAT`, a tab line `fo4sfTab`, seven lines
`fo4sfLine0` to `fo4sfLine6`, the hint `F10 OPENS AND CLOSES THIS PAGE` and two buttons the size of test C's CLICK:
`fo4sfTabButton` (NEXT TAB) and `fo4sfCloseButton` (CLOSE). Its embedded font is the 5 x 7 table plus `' , ( ) ? ! + %
& _ # =`; the plugin writes upper case and turns any other character into `?`, at most 54 to a line.

| Tab | Lines |
| --- | --- |
| 1 STATUS | `HEALTH <n>`; `LEVEL <n>   XP <n>`; `CARRY WEIGHT MAX <n>`; `RADS <n>` or `RADS NOT INSTALLED`; `CELL <name> (<form id>)`; `WORLD <name> (<form id>)` or `WORLD NONE (INTERIOR)`; `TIME <hh:mm>   DAY <n>` |
| 2 DATA | `POSITION X Y Z`; `UPDATES <n>   (TWO A SECOND)`; `NEXT TAB CLICKS <n>   CLOSE CLICKS <n>`; `OPENS <n>   FLAGS <f>`; `GAME PAUSED <n>`; `MENUS <n>[...]`; `DAYS PASSED <d.dddd>` |

How it runs, the channel's way:

- **Main thread** (SFSE's task, in `Toggle` before each kShow and in `SendUpdate` before each kUpdate, so about twice
  a second while open): `PageCollect` reads every value and formats both tabs under a lock. All reads of the game and
  the two calls into it (`LookupByID` at the first open, `GetActorValue`) happen here.
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
| health (`Health` `0x2D4`), carry weight (`CarryWeight` `0x2DC`), experience (`Experience` `0x2C9`), `FO4SF_Rads` | the player's `ActorValueOwner::GetActorValue` with that `ActorValueInfo` form | the three of Starfield.esm (the PC's read of the file, 11 Nov): looked up by form id and accepted by their RTTI type `ActorValueInfo` (at `3eb30d71` an editor-ID check passed only Health). `FO4SF_Rads`: by editor ID at local id `0x800` of each full plugin `01`-`FD` and light plugin `FE000`-`FEFFF`. The call: next line |
| the `GetActorValue` slot | the player's `ActorValueOwner` vtable, slot 0x01 | the base's offset from `PlayerCharacter`'s RTTI class hierarchy; that subobject's vtable locator names `PlayerCharacter` at that offset; slot 0x00 is the adjustor thunk to the player's own slot 0x00 (its destructor). libxse declares a virtual destructor before `GetActorValue`, SFSE 0.2.21 none: the thunk decides. Otherwise `refuse step=page what=get_actor_value ...` and every actor value is `?` |
| level | the player's base object (`OBJ_REFR::objectReference`), its `TESActorBaseData`, `ACTOR_BASE_DATA::level` | the base is a `TESNPC` by RTTI; the base class offset from its hierarchy, its subobject checked as above. That the player's level lives there is a **supported hypothesis** (it does in Skyrim and Fallout 4) |
| cell, worldspace | `TESObjectREFR::parentCell`, then `TESObjectCELL::cellWorldspace`; each name through its `TESFullName` (the pool string at +0x08) | `TESObjectCELL` and `TESWorldSpace` by RTTI; `TESFullName`'s offset from the hierarchy, subobject checked. An exterior cell usually has no name: `NO NAME` and its form id, which changes as the player crosses cells |
| game time | the `GameHour` and `GameDaysPassed` globals, each a float at one offset found in the game | looked up by form id, `Starfield.esm`'s `00000038` and `00000039` (docs/ai/test-queue.md; the PC confirmed them), accepted by their RTTI type `TESGlobal` (at `3eb30d71` an editor-ID check refused both). libxse's value offset +0x40 read `DAYS PASSED -3.5924` at `a156037c`, and the 4-byte slot at +0x28 (`TESForm::formID`, `38000000` and `39000000`) read as an hour and a day of about zero and passed at `6de5559a` (`TIME 00:00 DAY 1`). The game's own GetValue reads a float at **+0x48** (bytes `C4 C1 7A 10 40 48 C3`, `vmovss xmm0, [r8+0x48]`; the object is 0x50 bytes, form type 0x0A at +0x2E; FAL-384), so: +0x48 when the hour is in [0, 24), the days above 0 and below a million, and the hour within three game minutes of the days' fraction; else the first other 4-byte slot of +0x30 to +0x4C that passes; never +0x28. Until one is, `TIME ?` and `DAYS PASSED ?`; the 40 bytes (+0x28 to +0x4F) of both are logged once (`step=page_globals from=0x28 game_hour hex=... floats=... game_days_passed ...`), then `step=page_globals value_at=<offset>` |
| editor IDs and names | the `BSStringPool` entry (libxse: an 0x18-byte header, then the characters; flag 0x02 at +0x14 points on at +0x08) | `step=page_strings self_test=ok`: our own menu name read back through the same reader first; if it does not read back, no name and no form list is read |
| the form lookup | the engine's `TESForm::LookupByID` (libxse id 47401), the second call into the game | its address must equal SFSE 0.2.21's `GetFormByNumericID` `0x5DE3B0` (`sfse/GameForms.cpp`), else `refuse step=page_ids` and the plugin stays idle; libxse and SFSE both declare it `TESForm* (u32)`. Called on the main thread only, about 8,400 times once at the first open, never again |
| the data handler's lists (diagnostic only) | `TESDataHandler::formArrays` at +0x70, 0x18 each (libxse and SFSE 0.2.21 agree), which read empty at `5a4e6016` (`refuse step=page_forms list=AVIF reason=array size=0`, PC run 11 Nov) | `TESDataHandler.Singleton` 937572 must equal SFSE's `0x5FD9B28`; the object is a `TESDataHandler` by RTTI. Only its memory is logged, once: `step=page_form_arrays avif=<3 qwords> glob=<3 qwords> nonzero_count=<n> <index>:<3 qwords>...`, so a later page can use the lists |

The page's checks never stop the plugin: a value that fails prints `?` and its reason is logged once, as
`step=page_unknown what=<value> reason=...`. `step=page_forms lookup=by_form_id known=<name>:<id>:form=<0|1>:type=<rtti>:
bytes2c=<4 bytes at +0x2C>:name=<editor id as read>:<used|refused> ... avif_ids=<id>=<editor id>,...` says, for each fixed
form, what the lookup gave, and lists every `ActorValueInfo` among `0x001`-`0xFFF` with its editor ID as read. The
carried weight is not on the page: Starfield.esm has no `InventoryWeight` actor value (the PC's read). Nor are credits:
no plain getter exists for an item count.

**Verified at `5a4e6016` and `3eb30d71` (PC runs, 11 Nov):** the page, both buttons, F10, the string self test, the
slot thunk (`owner_offset=0x70`, slot 0x01), the level (`LEVEL 1` = `player.getlevel`), the cell line, `menus=`, the
form lookup and `HEALTH 205` (= `player.getav health`). **Verified at `a156037c`:** `XP 60` and `CARRY WEIGHT MAX 135`
through their fixed form ids. **Not verified until the next session:** the time (`TIME ?` and `DAYS PASSED -3.5924` at
+0x40 there; the offset is now found and checked as above).

## Stage (e): the page kit (FAL-301)

The owner's order of 11 Nov: several pages and a baseline for making them, with the Fallout 4 look, then the raise
animation. This stage is the baseline. A page is a few lines of data; adding one needs no C++ and no new movie by hand.

**The movie** (`scripts/ui/make_pipboy_kit.py`, staged with `make_pipboy_probe.py stage <exp> --kit` under the same name
`Interface/FO4SF_PipboyMenu.swf`) has no code. It draws one dark screen in one phosphor colour (`--color RRGGBB`,
default `1AFF80`); the screen, the dim text and the footer boxes are derived from that one colour. Its font is stage
(d)'s 5 x 7 table plus `[ ] < > * ;`. The plugin finds each part by name and changes only `text` and `visible`:

| Part | Names | What the plugin does |
| --- | --- | --- |
| title bar | `fo4sfTitle`, `fo4sfHeaderInfo` | the kit's title; on the right, the `[Kit]` `Header=` value (the game time) |
| main tabs | `fo4sfTab<i>`, `fo4sfTabMark<i>`, `fo4sfTabHit<i>` | the label; the bracket around the shown tab (`visible`); the click area |
| sub-tabs | `fo4sfSub<i>`, `fo4sfSubDim<i>`, `fo4sfSubHit<i>` (5 slots) | the shown tab's sub-tabs, the current one bright and the others dim |
| list | `fo4sfRowName<i>`, `fo4sfRowValue<i>`, `fo4sfRowNameSel<i>`, `fo4sfRowValueSel<i>`, `fo4sfBar<i>`, `fo4sfRowHit<i>` (16 rows) | each row's label and right-aligned value; on the selected row the bar and the dark copy of the text are shown and the bright copy is hidden |
| scrolling | `fo4sfMoreUp`, `fo4sfMoreDown` | shown while rows lie above or below the 16 on screen |
| value rows | `fo4sfInfoLabel<i>`, `fo4sfInfoValue<i>` (16 rows) | the selected row's details in two columns |
| footer | `fo4sfFoot<i>` (3 cells), `fo4sfHints`, `fo4sfClose` | the page's footer cells, the key hints, the CLOSE button |
| check | `fo4sfKitId` | the kit's signature, drawn in the screen's colour so it stays invisible; read at each new movie |

The hit areas are sprites filled in the screen's own colour, under the text, so they cannot be seen. A click on a
tab, a sub-tab or a row is reported under one of that row's names, whether it lands on the text or beside it.

**The pages** are sections of `FO4SFPipboyMenu.ini`. The plugin reads them at load (`ReadKit`) and
`make_pipboy_kit.py` reads them to draw the main tabs (`--check` prints them). Both apply the same grammar and checks:

- `[Kit]`: `Title=`, `Header=<value>`, `Hints=`.
- `[Page <TAB>/<SUB>]`: a page. Main tabs come in the order of their first page (up to 5); sub-tabs come in page
  order (up to 5 per tab). A page has exactly one of:
  - `Row=<label>|<value>` lines (up to 64, 16 on screen, scrolled);
  - `List=<list>`;
  - `Notice=<text>` lines (up to 16).
  It may also have up to three `Footer=<label>|<value>` cells and a `Hint=`.
- Labels are upper case, in the kit's font, and fit their field: 33 characters for a row or a notice, 9 for a tab, 13
  for a sub-tab, 10 for a footer cell.

A wrong line stops the kit at load: `refuse step=pages line=<n> reason=<r>`, and the plugin stays idle. A page whose
row value is longer than 8 characters shows that value after its label, in the label's column.

| Page | Content |
| --- | --- |
| STAT / STATUS | rows: health, level, experience, carry weight max, rads, cell, world, time; footer HP, LEVEL, XP |
| STAT / SPECIAL | rows: Strength to Luck, `av:2C2` to `av:2C8` (Starfield.esm keeps Fallout 4's ids); the same footer |
| INV / ITEMS, DATA / QUESTS | notices: the inventory list and the quest list (our mission first) come in the next pull request |
| DATA / KIT TEST | `List=kit_test`: thirty rows to scroll, select and click |
| MAP / WORLD, RADIO / STATIONS | notices: each waits for its own track (the map track, the radio) |

**Value providers.** Every value is read on the main thread, with stage (d)'s reads and two calls only. When one
cannot be read it prints `?`, and its reason is logged once as `step=page_unknown what=<value> reason=<r>`.

| Value | Reads | When it cannot |
| --- | --- | --- |
| `health`, `xp`, `carry_max` | the player's `GetActorValue` with Starfield.esm's `Health` `0x2D4`, `Experience` `0x2C9`, `CarryWeight` `0x2DC` (stage (d)) | `what=health`, `experience`, `carry_weight`: `reason=no_such_actor_value`, `no_get_actor_value` or `not_finite` |
| `rads` | `FO4SF_Rads` the same way; `NOT INSTALLED` without the rads probe | `what=rads reason=actor_values_unread` |
| `level` | the base `TESNPC`'s `ACTOR_BASE_DATA::level` (stage (d)) | `what=level reason=base ...` or `actor_base_data ...` |
| `cell`, `world` | the parent cell and its worldspace, each name with its form id (stage (d)) | `what=cell reason=cell ...`, `what=cell_name`, `what=world reason=...` |
| `time` | `GameHour` `0x38` and `GameDaysPassed` `0x39` at the value offset found and checked as at (d): `hh:mm   DAY n` | `what=time reason=globals_unread`, `no_value_offset` or `out_of_range` |
| `days` | `GameDaysPassed`, two decimals, checked as the time is | `what=days reason=globals_unread`, `no_value_offset` or `out_of_range` |
| `position` | the player's position, whole units | `what=position reason=no_player` |
| `av:<hex>` | the player's `GetActorValue` with the `ActorValueInfo` form of that form id. The form is looked up once by its id and accepted by its RTTI type, with stage (d)'s `AcceptById`, logged as `step=kit_av av:<id>:form=<0 or 1>:type=<rtti>:...:<used or refused>` | `what=av:<hex> reason=no_such_actor_value` |

Lists: `kit_test` (thirty rows, no read of the game). The inventory and the quests come next, as `inventory` and
`quests`.

**How it runs.** The pattern is stage (d)'s:

- On the main thread, `KitCollect` builds the shown page's screen (in `Toggle` before each kShow, and in `SendUpdate`
  before each kUpdate).
- On the menu's thread, `KitWrite` sets only what changed since the last read-back, and reads each change back.
  `step=kit n=<k> update=<u> show=<0 or 1> page=<TAB>/<SUB> root=1 collected=1 changed=<c> set=<s> match=<m> missing=0
  bar=<row> footer="..." rows="..."` is logged for n = 1 to 20, then every 20th, and on the first 20 problems.
- At each new movie, `step=kit_movie id="<read>" expected="<ours>" match=yes` checks that the movie was staged from the
  same pages. Then come `step=listen name=root ... added=1` and `step=listen name=fo4sfClose ... button=1 ... added=1`.
- The state is kept while the page is closed, so the page opens where it was left. It is the main tab, each tab's
  sub-tab, and each page's selection and first row on screen.

**Keys** (`KitUp` to `KitNextTab` in the ini, up to three each, never `Key` or `SnapshotKey`). They are read by the key
thread every 30 ms, only while the page is open and the game is in front. Each press is logged as `step=kit_key vk=<vk>
action=<a> index=0 moved=<0 or 1> page=<TAB>/<SUB> selected=<n>`, and an update follows at once. Up and Down repeat
when held (after 420 ms, every 90 ms). No move wraps around.

| Action | Default keys |
| --- | --- |
| selection up, down | Up arrow or W (`0x26,0x57`), Down arrow or S (`0x28,0x53`) |
| sub-tab left, right | Left arrow or A (`0x25,0x41`), Right arrow or D (`0x27,0x44`) |
| main tab left, right | Q (`0x51`), E (`0x45`) |
| close | F10 (`Key`), as at every stage; Tab and Esc (`CloseKeys`, FAL-404); the CLOSE button |

*Which keys the game lets through at `0x9`:* the plugin reads the keyboard itself (`GetAsyncKeyState`), so it sees
every key whatever the game does with it. The PC runs at `0x9` (FAL-216, FAL-272) showed that W does not move the
player, that the game draws its own pointer, and that F10 and F11 reach the key thread. The kit session of 11 Nov
answered for Tab and Esc: both opened the game's pause menu over the page. They now close it ("Tab and Esc close the
page", below). What the game also does with A, S, D, Q, E and the arrows while the page is open is in the owner's
report.

**Clicks:**

- One listener on the movie's root hears every click. It reads the event's `target`, then that object's `name`
  (`step=kit_click n=<k> args=1 target=1 name=<name> action=<a> ...`).
- A name ending in a number moves the kit: `fo4sfTab*`, `fo4sfTabMark*` and `fo4sfTabHit*` pick a main tab; the
  `fo4sfSub*` names pick a sub-tab; the row names select that row.
- CLOSE keeps stage (d)'s own listener and handler, the proven path.

**Not verified until the session:**

- that `visible` sets and reads back on our sprites and fields;
- that a click event's `target` carries the instance name, for a text field and for a hit sprite;
- that the root's listener hears clicks that land on its children;
- what the keys do in the game at `0x9`;
- how the layout looks at the PC's resolution (ShowAll keeps the 16:9 stage).

**The look (part 3, next):** scan lines, a slight glow, the list highlight, and a better font. The colour is already
one setting. The planned route for the font and the Vault Boy pictures:

- **Font:** ours, generated like this one. Nothing from either game goes into Git, the kit runs with or without
  Fallout 4 installed, and the tests stay byte-exact.
- **Vault Boy pictures:** they are Fallout 4's art and cannot be drawn by us. They come only by converting the
  player's own Fallout 4 interface files on their PC, as the port does for everything else, after the PC survey names
  those files.

## Tab and Esc close the page (FAL-404)

**What the PC saw (11 Nov, the kit at `0x9`):** with the page open, Tab and Esc each opened the game's pause menu over
it, with QUICKSAVE and SAVE greyed, and the plugin's state stayed open; only F10 and CLOSE closed the page. In Fallout 4
Tab puts the Pip-Boy away. The input contexts of the FAL-216 snapshots say why (libxse `UserEvents.h` names them).
Plain play is `0,1` (MainGameplay, ConsoleOpening). The pause menu adds `78,2,11,3,13`: StopContextProcessing first,
which keeps every context under it from the keys, then BasicMenuNav and three more. Our menu at `0x8` and `0x9` adds
only `13` (Cursor). So Tab and Esc still reach the gameplay context, and MenuControls' MenuOpenHandler opens the pause
menu.

**What the plugin does now, at stages (d) and (e):**

- **The close keys** (`CloseKeys`, default `0x09,0x1B`: Tab and Esc; up to three, never `Key`, `SnapshotKey` or a kit
  key). The key thread reads them as it reads F10, only while the page is open and the game is in front. A press
  closes the page by CLOSE's route: `step=close n=<k> by=key vk=<vk> was_open=1 sent=hide`, then `step=state`.
- **The hold** (`HoldMenuKeys=1`). While the page is open, the game's MenuOpenHandler hears no input. Its
  `BSInputEventUser` flag `inputEventHandlingEnabled` (libxse `+0x38`, the flag libxse's
  `MenuControls::RegisterHandler` sets) is 0 from just before the show. It gets its own value back once the page is
  hidden and no close key has been held for three ticks (90 ms), so the key that closed the page cannot open a menu
  after it. Any hide counts: ours, the engine's, our menu's destructor, or a main-thread read that finds the page
  closed. This is the plugin's only write into an object the engine owns. It is one byte, guarded like every read.
  Log: `step=hold n=<k> on=1 was=1`, then `step=hold on=0 by=hide restored=1 ok=1`.

The hold's ids are read from the Address Library file and checked like the others, but they are their own set: a
failure turns off the hold alone (`refuse step=hold ...`), and Tab and Esc still close the page.

| Name | Id | Source | Checked by |
| --- | --- | --- | --- |
| MenuControls.Singleton | 938076 | libxse | file + libxse lookup, `step=hold_id`; the object's RTTI is MenuControls's at offset 0 |
| MenuControls.RTTI | 864851 | libxse `RTTI_MenuControls` | names `.?AVMenuControls@@` |
| MenuOpenHandler.RTTI | 864856 | libxse `RTTI_MenuOpenHandler` | names `.?AVMenuOpenHandler@@` |

Checked once, at the first open, before the first write (`step=hold_target menu_controls=<a> handler=<a>
type=.?AVMenuOpenHandler@@ offset=<o> handlers=<n> index=<i> enabled=1`):

- the handler at MenuControls `+0x48` is a MenuOpenHandler by RTTI;
- it is one of the entries of MenuControls' handler list at `+0x20` (so both offsets are the game's);
- its flag reads 0 or 1.

**What it does not do:**

- It reads the keys, not the game's own cancel event: a player who rebinds Esc in the game's settings sets
  `CloseKeys` too.
- While the page is open, the hold keeps every menu key the MenuOpenHandler serves from opening its menu, as Fallout
  4's Pip-Boy does. The pause menu is one; which others it serves is the session's to see.

**Not verified until the session:**

- that the flag at `+0x38` is what the game's input dispatch reads for this handler on 1.16.244 (libxse sets it on
  registration; the dispatch that reads it has not been read);
- that the pause menu then stays shut on Tab and Esc;
- that the hold is given back (the control: the Esc after, with the page closed, opens the pause menu);
- what the console key does while the page is open.

## Build (PC)

From a checkout at the PR head, in the PC's x64 environment:

```
powershell -File sfse\FO4SFPipboyMenu\build.ps1 -Out <new staging folder> -Lib <libxse-commonlibsf at 9d090c4> -Env <msvc_env.ps1>
```

Exit 0 leaves `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `build.json` (every sha256, both library commits) in
`-Out`. Nothing is installed. Exit 1 after `build.cmd exit 90` (configure) or `91` (build): see `xmake_output.txt`.

Stage the plugin and movie, and check the plugin (stage (c): `stage <exp folder> --channel`; stage (d): `stage <exp
folder> --page`; stage (e): `stage <exp folder> --kit`, from the same ini that is installed beside the dll; the movie
keeps its name):

```
python scripts/ui/make_pipboy_probe.py stage <exp folder>
python scripts/ui/make_pipboy_probe.py check <exp folder>\FO4SFPipboyProbe.esm
```

## Install and uninstall (probe session only, game closed)

Install:

1. Copy `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` and `versionlib-1-16-244-0.bin` into
   `<Starfield>\Data\SFSE\Plugins\`. Set `Stage=1`, `2`, `3`, `4` or `5` in that copy of the ini (at (e) its pages
   must be those the movie was staged from: `step=kit_movie ... match=yes`).
2. Stages (b) to (e): `python scripts/ui/pipboy_probe_install.py install --dir <exp folder> --starfield <game>`.
   This checks the stage, activates `FO4SFPipboyProbe.esm` and packs its `Data` tree into
   `FO4SFPipboyProbe - Main.ba2`, under its own record `Data\FO4SFPipboyProbe.install.json`; the installed
   experiment's `FO4SFExp.install.json` is not read or changed. A `plugin_toggle.py` hold makes it refuse, so run it
   between `plugin_toggle.py on` and `off`. `status`, `order` and `active` take `--starfield <game>` alone.

Uninstall:

1. Stages (b) to (e): `python scripts/ui/pipboy_probe_install.py uninstall --starfield <game>`. This removes
   exactly what its record lists and the Plugins.txt line it added.
2. Delete `FO4SFPipboyMenu.dll` and `FO4SFPipboyMenu.ini` from `Data\SFSE\Plugins\`. Delete
   `versionlib-1-16-244-0.bin` too, unless it was there before the session.
3. Compare with the receipts taken before the install.

**Log:** `Documents\My Games\Starfield\SFSE\Logs\FO4SFPipboyMenu.log`. `SFSE::Init` opens it, named after the plugin.

## World surface (FAL-250)

One question: **can the movie (b) shows as a centred overlay be drawn on a surface in the world**, a mesh you can
walk around? Spec: FAL-248 document `wrist-pipboy`, section 4. Not this probe: the worn Pip-Boy, the arm raise, the
camera, input, power armor, the data channel.

`World=1` next to `Stage=2` adds two things, in `src/world.cpp`. With `World=0` (as shipped) none of it runs and the
log is #704's. It runs only after every check above passed (runtime 1.16.244.0, the Address Library file, the IMenu
ids, vtables and RTTI), and it adds no id and no hook. Its first line, after `step=ready`, is `step=world_config
world_key= world_menu= world_movie=`, or one `refuse step=world` line and the overlay probe runs alone.

- **Census.** When our menu registers, every menu name the UI has registered (`step=census_registered`), then one
  `step=census_registered_done ... leads=` line: the names holding `test`, `dynamic`, `textur`, `geo`, `terminal`,
  `kiosk`, `cockpit`, `screen`, `monitor`, `display`, `watch`, `slate` or `3d`. Then every menu whose movie SFSE's
  own `IMenu::LoadMovie` hook reports, once per name and flag set: `step=census_movie menu= result= class= flags=
  movie= depth= lead=`. `result=1` means the menu holds a movie after the engine's loader returned (SFSE's hook does
  not pass the return value on). `class` is the decorated name the menu's RTTI gives (`outside_image` for ours: its
  vtable is our copy). This is the flag dump the candidate is chosen from; libxse leaves the flag bits unnamed.
- **World candidate.** `WorldKey` (F8) sends show, then hide, to `WorldMenu`, one vanilla menu named from the census,
  with `step=world_toggle` and, 750 ms later, `step=world_state` (open, expected, and the menu's class, flags and
  movie). Each time that menu loads a movie: `step=world_load_movie menu= result= movie_file=`. Its movie comes from
  the probe archive only: `python scripts/ui/make_pipboy_probe.py twin <exp folder> Interface/<file>` writes our movie
  again, byte for byte (label included), at that vanilla path; `WorldMovie` names it in the log.
  `pipboy_probe_install.py` packs a twin with the movie and refuses one that is not byte for byte the movie.
  `Starfield - Interface.ba2` is never changed.

What it reads: the UI's menu map (libxse `UI::menuMap`, the table #704's `IsMenuRegistered` already reads), each
menu's name, flags and movie (libxse's IMenu layout, which #704 uses), and the RTTI locator before a vtable, each
address inside Starfield.exe's image first. What it calls: what the overlay key calls (`UI::IsMenuOpen`,
`UIMessageQueue::AddMessage`), and one `BSFixedString` for the candidate's name.

### Candidates, in order: stop at the first the census makes declarable

| # | Candidate | In this build | Declarable when |
| --- | --- | --- | --- |
| 1 | ~~vanilla `testmenus_dynamictexturedgeo`~~ dropped | | the PC read the file (10 Nov): a 4.9 kB renderer test of shapes with one name, `Scene`, not a movie on an object |
| 2 | a vanilla terminal, kiosk or cockpit screen (first `TerminalMenu`, `GenesisTerminalMenu`, then `DataSlateMenu` with `WorldMenu=`) | use the object in the game, or the key; a twin at the screen's movie path | `step=census_movie` lists the menu that opens with that screen |
| 3 | one throwaway NIF/material in the probe plugin | not built | (1) and (2) give no hook; it needs a dump of a vanilla material first |

Two **hypotheses** the pictures settle: a vanilla menu loads `Interface/<its name>.swf` or `.gfx`, as ours loads
`Interface/FO4SF_PipboyMenu.swf` (names in the notes fit: `hudmenu.gfx`, `monoclemenu.swf`; the PC's interface list
names the real file); and the probe archive wins over `Starfield - Interface.ba2` for the same path. A twin under a
`.gfx` name keeps the SWF header. A menu whose own `LoadMovie` never reaches `IMenu::LoadMovie` is not in the census.

### Job card (FAL-250)

The build, install and uninstall of (b). Two passes; the game is closed between them. No step needs a save of its
own; load one that starts next to a terminal (a ship's cockpit nearby helps).

**Pass 1, the census and the overlay control** (no twin):

1. Plugin ini: `Stage=2`, `World=1`, `WorldMenu=` and `WorldMovie=` empty. Stage and install as (b).
2. Load the save; wait until in control.
3. Overlay control: F10, screenshot, F10.
4. F8 once: `refuse step=world_toggle n=1 reason=no_world_menu` (census only).
5. Use the terminal: activate it, wait for its screen, leave it. If there is a ship: sit in the pilot seat, stand up.
6. Quit. Report, names only: `leads=`, every `step=census_movie` line with `lead=1`, the terminal's and the
   cockpit's `step=census_movie` lines, and the PC's `Starfield - Interface.ba2` list filtered for those names (file
   names, nothing of their content).
7. Pick the candidate by the table above.

**Pass 2, the world candidate** (same build):

1. Uninstall pass 1's archive. `make_pipboy_probe.py stage <exp folder>`, then `make_pipboy_probe.py twin <exp
   folder> Interface/<the candidate's file>`; install.
2. Plugin ini: `WorldMovie=Interface/<that file>`; candidate 1 also `WorldMenu=<its name>`.
3. Load the same save. Overlay control again: F10, screenshot, F10.
4. Candidate 1: F8 (show). Candidate 2: use the terminal or sit in the seat.
5. Screenshot the surface, then a second one after moving the camera: walk round it, or put something in front of
   it.
6. Negative: F8 again (hide), or leave the terminal or the seat. Screenshot the same surface.
7. Quit; uninstall; compare with the receipts.

### PASS (FAL-250): all three, no crash

1. **Overlay control.** The (b) PASS: `step=load_movie ... stage=b result=1`, the green card centred, the label.
2. **World candidate.** The overlay is closed (the last `step=state ... open=0`); the candidate loaded a movie
   (`step=world_load_movie menu=<name> result=1 movie_file=<twin>`, or for a screen its `step=census_movie ...
   result=1`); the screenshot shows `FO4SF PIP-BOY PROBE` on a surface in the world: foreshortened with it, hidden by
   what is in front of it, moving or leaving the frame as the camera moves.
3. **Negative.** After the hide, the surface no longer shows our card (it was the movie, not a baked texture).

### Inconclusive (do not call these PASS)

- The card is still a screen overlay: no perspective, nothing in the world hides it.
- A picture like ours without the label, or no `result=1` line for the candidate: not our movie.
- Vanilla art on the surface: the twin did not reach the menu (path, `.gfx` header or archive order); re-check the
  path in the interface list.
- No second view (camera moved, or something in front).
- A hang or a crash before both views: the last line names the step.
- Any method that changes `Starfield - Interface.ba2`: it would not prove our movie.

**A useful FAIL:** the overlay control passes and the world path is refused with a named step, for example
`refuse step=world_toggle ... reason=not_registered` for every candidate name, or the census shows that the
terminal's menu is a screen overlay. Then the wrist goes to the flat fallback (#704's overlay), unless candidate 3
finds a material that names a render target.

### What each world line means

| Line | Meaning | Next |
| --- | --- | --- |
| `refuse step=world reason=needs_movie_stage` | `World=1` without the movie stage | `Stage=2` |
| `refuse step=world reason=key` | `WorldKey` is 0, above 0xFE, or the menu's key | fix the ini |
| `refuse step=world reason=world_menu` | `WorldMenu` has a character other than letters, digits and `_` | copy the name from the census |
| `refuse step=world reason=world_menu_is_ours` | `WorldMenu` names the overlay control | a vanilla name |
| `refuse step=world reason=world_movie` | `WorldMovie` has a character other than letters, digits and `_ . / \ -` | copy the twin's path |
| `refuse step=world_key_thread` | the key thread could not start | report |
| `refuse step=world_toggle n=<n> reason=no_world_menu` | census only, `WorldMenu` empty | expected in pass 1 |
| `refuse step=world_toggle n=<n> menu=<name> reason=not_registered` | the UI has no menu by that name; nothing was sent | a named FAIL for that candidate |
| `refuse step=world_toggle n=<n> menu=<name> reason=no_ui_or_queue` | pressed before the UI existed | press again once in play |
| `step=world_state ... match=no` | the candidate did not open or close as asked | read the census lines around it |
| `step=world_load_movie ... result=0` | the candidate loaded no movie | the twin's path or header is not what it loads |
| no `step=census_movie` line at all | SFSE gave no menu interface | report the SFSE version |
| `step=census_movie_full` | 256 menu and flag pairs listed | the first 256 are in the log |

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
   snapshot_key=0x7a click_call=none` and, before `step=ready`, `step=channel_ids value_functions=sfse_equal
   rtti_names=ok`.
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
5. **Click to quest** (`ClickCall=FOCC_B0.Click`, its own launch): `step=load_c ... click_call=FOCC_B0.Click`,
   `step=object name=GameVM`, `step=object name=VirtualMachine ... dispatch_static_call=<rva>`, then per click on CLICK
   one `step=click n=<k>` and one `step=dispatch n=<k> call=FOCC_B0.Click queued=1`, and in `focc.0.log` one
   `b0 click` line per dispatch. The control: no `b0 click` line before the first click, none for the click beside
   the button.

### PASS at (d), `Stage=4` (the owner's card: `docs/spikes/pipboy-stat-page-owner-card.md`)

1. Everything in (b), with `stage=4` and `step=ready stage=d`, after `step=load_d flag_sets=0x9 snapshot_key=0x7a`
   and, before `step=ready`, `step=channel_ids value_functions=sfse_equal rtti_names=ok` and `step=page_ids
   data_handler=sfse_equal lookup_by_id=sfse_equal`; 34 `step=id` lines.
2. At the first open: `step=page_strings self_test=ok`, `step=page_actor_values ... get_actor_value_slot=0x01`,
   `step=object name=TESDataHandler`, `step=page_form_arrays ...` and `step=page_forms lookup=by_form_id
   known=GameHour:38:form=1:type=.?AVTESGlobal@@:...:used ...`, each of the five `used`; `step=page_globals from=0x28
   ...` and `step=page_globals value_at=<offset>`; then `step=listen name=fo4sfTabButton ...
   added=1` and `step=listen name=fo4sfCloseButton ... added=1`.
3. **Lines follow the game:** `step=page ... fields=8/8 set=8 match=8` lines whose `text=` changes with the game:
   `TIME` minutes move while the page is open, `HEALTH` after damage, `CELL` after the player crosses a cell or a door,
   `POSITION` and `DAYS PASSED` on tab 2. The controls (console, PC helper only): `player.getav health`,
   `player.getav carryweight`, `player.getlevel`, `player.getpos x` (`getglobalvalue gamehour` answers "not found for parameter Global" in
   this console; use `getglobalvalue 00000039` for days passed and `00000038` for the hour, PC run 11 Nov; TIME's minutes also move).
4. **NEXT TAB:** each click logs `step=click button=tab` and the next `step=page` shows the other tab (`tab=1` and
   `TAB 2 OF 2: DATA`, then back).
5. **CLOSE:** `step=click button=close`, `step=close ... by=button was_open=1 sent=hide`, `step=state ... open=0
   expected=0 match=yes`; F10 then opens the page again.
6. `RADS NOT INSTALLED` without the rads probe; with it (FAL-213), `RADS <n>` equal to `player.getav FO4SF_Rads`.

### PASS at (e), `Stage=5` (the owner's card: `docs/spikes/pipboy-page-kit-owner-card.md`)

1. Everything in (b), with `stage=5` and `step=ready stage=e`. Before it come:
   - `step=load_e flag_sets=0x9 snapshot_key=0x7a`;
   - six `step=kit_keys` lines and seven `step=page_def` lines;
   - `step=pages pages=7 tabs=5 signature="FO4SF KIT 1 16 STAT,INV,DATA,MAP,RADIO"`;
   - `step=channel_ids` and `step=page_ids` as at (d), with 34 `step=id` lines.
2. At the first open:
   - stage (d)'s `step=page_strings self_test=ok`, `step=page_actor_values ... get_actor_value_slot=0x01`,
     `step=page_forms`, `step=page_globals from=0x28 ...` and `step=page_globals value_at=<offset>`;
   - `step=kit_movie ... match=yes`;
   - `step=listen name=root ... added=1` and `step=listen name=fo4sfClose ... button=1 ... added=1`;
   - `step=kit n=1 update=0 show=1 ... missing=0`, with `match` equal to `changed`.
3. **Keys:** `step=kit_key vk=0x53 action=down ... moved=1` and the like. The next `step=kit` line shows the bar on
   the next row (`bar=<n>`, the `>` in `rows=`). D shows `page=STAT/SPECIAL`, with seven `step=kit_av av:2c2` ...
   `av:2c8` lines, each `:used`, and seven numbers equal to `player.getav strength` ... `player.getav luck`.
4. **Scrolling:** on DATA / KIT TEST, holding S takes `rows=` past `TEST ROW 16` with the bar still on screen, and
   it stops at `TEST ROW 30`.
5. **Clicks:** `step=kit_click ... target=1 name=fo4sfRowHit<i>` (or another of that row's names) `action=row ...
   moved=1`, and `name=fo4sfTab3` or `fo4sfTabHit3` `action=tab` for MAP.
6. **CLOSE:** `step=click button=close`, `step=close ... sent=hide` and `step=state ... match=yes`. F10 then opens the
   page where it was left.
7. **Tab and Esc** (FAL-404, "Tab and Esc close the page"): at load `step=close_keys keys=0x9,0x1b hold_menu_keys=1`,
   three `step=hold_id` lines and `step=hold_ids rtti_names=ok`; at the first open `step=hold_target ... enabled=1`,
   and at each open `step=hold n=<k> on=1 was=1`. Tab gives `step=close n=<k> by=key vk=0x9 was_open=1 sent=hide`,
   then `step=state ... match=yes` and `step=hold on=0 by=hide restored=1 ok=1`; Esc the same with `vk=0x1b`. The
   owner saw no game menu on either. *Control:* the Esc after, with the page closed, opens the game's pause menu.

### What each failure line means

| Line | Meaning | Next |
| --- | --- | --- |
| `step=off` | `Stage` is not 1 to 5 in the ini next to the dll | set it |
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
| `refuse step=ini close_keys` | (d), (e): `CloseKeys` holds 0, a code above 0xFE, `Key`, `SnapshotKey` or a kit key | fix the ini |
| `refuse step=hold name=<x> id=<n> reason=<r>` | (d), (e): a hold id is beyond the file, zero, outside the image or differs in libxse; no hold this session, the close keys still close the page | `NEEDS-PC lookup <id>` |
| `refuse step=hold name=<x>.RTTI type=<t>` | (d), (e): a hold RTTI id does not name its type; no hold | the id is stale: look it up again |
| `refuse step=hold what=menu_controls`, `what=menu_open_handler`, `what=layout` or `what=write` | (d), (e): MenuControls is not its type, its handler at +0x48 is not a MenuOpenHandler or not in its handler list, the flag is not 0 or 1, or the write faulted; no hold | report the line: libxse's layout is not the game's |
| `step=hold_target result=no_menu_controls` | (d), (e): MenuControls did not exist yet at that open; asked again at the next | nothing, if a later open logs `step=hold_target` |
| `step=hold ... on=1` with no `step=hold on=0` after a close | (d), (e): the hold was not given back; the game's menu keys stay off | press F10 twice (open and close) and report the log |
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
| `refuse step=ini click_call=` | (c): `ClickCall` is not `<script>.<function>` with two Papyrus names | fix the ini, or empty it |
| `refuse step=object name=GameVM ...` or `name=VirtualMachine ... (no click reaches a script)` | (c): the VM singleton or the VM it holds is not its type, or its vtable leaves the image; no click is dispatched for the rest of the session | report the types the line names |
| `step=dispatch ... result=no_vm` | (c): no script VM yet when the click came | click again once in play |
| `step=dispatch ... queued=0` | (c): the VM did not take the call: the script or the function is unknown to it | check `compile_b0.txt` and that the kit was staged at this head; `Papyrus.0.log` names it |
| `queued=1` but no `b0 click` in `focc.0.log` | (c): the VM took the call and did not run it, or the probe quest is missing (`b0 refused quest=none`) | collect `Papyrus.0.log` |
| the game stops at the first click after `step=dispatch` was due | (c): slot 0x2F is not `DispatchStaticCall` on 1.16.244 | remove the dll; report the crash log's module and offset |
| `refuse step=page_ids name=<TESDataHandler.Singleton or TESForm.LookupByID> rva=<r> sfse_rva=<s>` | (d): a libxse id is not SFSE 0.2.21's address; the plugin stays idle | stop: one of the two is stale for this runtime |
| `refuse step=page what=strings ...` | (d): our own menu name did not read back through the pool-string reader: no editor ID or name is read, every such line is `?` | report the line (it shows what was read) |
| `refuse step=page what=actor_value_owner ...` or `what=get_actor_value ... slot0=... target0=... destructor=...` | (d): the player's ActorValueOwner was not found or its slot 0x00 is not the thunk to the destructor; every actor value is `?` | report the line: its slots and targets settle libxse's against SFSE's declaration |
| `refuse step=object name=TESDataHandler ...` | (d): the data handler is not its type; only the form-list log is skipped | report the line |
| `step=page_forms ... known=...:refused` or `avif_typed=0` | (d): that fixed form id gave no form (`form=0`) or another type (`type=`); its line prints `?`. `rads=not_installed` is `RADS NOT INSTALLED` | report the line; `avif_ids=` lists what the ids hold |
| `step=page_globals from=0x28 ...` but no `value_at=` | (d): no slot from +0x30 holds both globals in range and in step: `TIME ?`, `DAYS PASSED ?` | post the line whole: its hex and floats show where the value is |
| `step=page_unknown what=<value> reason=<r>` | (d): one value could not be read, once per kind; its line shows `?` | report the line |
| `step=page ... fields=0/8` | (d): `getChildByName` found none of the page's fields: the movie is not the `--page` one | re-stage with `--page` |
| `step=listen name=<button> ... added=1` but no `step=click` on a click | (d): the click did not reach the movie | read `step=flags`: the page needs `0x9` |
| `refuse step=pages line=<n> reason=<r> (the kit stays off)` | (e): line n of the ini is not a page line the kit reads | `python scripts/ui/make_pipboy_kit.py --check --ini <that ini>` names the problem |
| `refuse step=ini kit_key=<action> ...` | (e): one of that action's keys is 0, above 0xFE, `Key` or `SnapshotKey` | fix the ini |
| `step=kit_movie ... match=no` | (e): the movie was staged from other pages than those beside the dll | re-stage with `--kit` from the installed ini |
| `step=kit ... missing=<n>` | (e): n names were not found: the movie is not the kit's | re-stage with `--kit` |
| `step=kit ... changed=<c> match=<m>`, m below c | (e): a `text` or a `visible` did not read back; it is set again on the next update | report the line (`visible` is new at this stage) |
| `step=listen name=root ... added=0` | (e): no listener on the root, so clicks do nothing; the keys still work | report the line |
| `step=kit_click ... target=0` or `name=-` | (e): the click's event had no target or no name | report: one listener per object is the fallback |
| `step=kit_av av:<id>:...:refused` | (e): that form id gave no `ActorValueInfo`; its row prints `?` | report the line |

The probe changes no Starfield interface file, and nothing it makes goes into Git: no dll, no movie, no archive.
