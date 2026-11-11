// FO4SFPipboyMenu: Pip-Boy step 1 (FAL-187; README.md in this folder). Can a plugin of ours register a menu of its
// own and show a movie of its own on Starfield 1.16.244? One named menu, FO4SF_PipboyMenu, opened and closed on one
// key, every step in its own log. Stage=1 (a): the menu with no movie; Stage=2 (b): the same menu showing
// Interface/FO4SF_PipboyMenu.swf (scripts/ui/make_probe_swf.py), loaded from "FO4SFPipboyProbe - Main.ba2".
//
// Built on libxse/commonlibsf 9d090c4 for SFSE, the Address Library, the logger, UI::RegisterMenu, UI::IsMenuOpen,
// UIMessageQueue::AddMessage and BSFixedString, but NOT on its IMenu class: every IMenu virtual there is
// REL::ID{ 0 } (include/RE/IDs.h), and a lookup of id 0 stops the game with a message box. The menu object is the
// engine's own: the engine's IMenu constructor, then a copy of the engine's IMenu primary vtable with only our
// slots replaced, and the engine's RTTI locator in the slot before the copy (the two other vtables are the engine's,
// as the constructor set them).
//
// Nothing is called before it is checked (README, "Where every id comes from"):
//   - the runtime is 1.16.244.0 (SFSE's), else nothing but the refusal line;
//   - the Address Library file next to this dll is read here first (format 5, game version 1.16.244.0, every id we
//     use below its count, non-zero and inside Starfield.exe's image), so libxse's own lookup can never hit a
//     missing id; then each id is looked up again through libxse and must give the same offset;
//   - the three IMenu vtables carry IMenu's RTTI (complete object locator: x64, subobject offsets 0, 0x10, 0x50, type
//     ".?AVIMenu@@", the type descriptor libxse's RTTI id names);
//   - the primary vtable's slots are the functions their ids name: 0x00 the scalar deleting destructor, 0x06
//     LoadMovie (also SFSE 0.2.21's own hook address, 0x2551AB0), 0x08 ProcessMessage, 0x0A IsMovieLoaded; 0x03 and
//     0x04 (GetName, GetRootPath) are the same pure-virtual stub;
//   - the constructor's first 0x200 bytes load the primary vtable's address (lea r64, [rip+disp32]).
// Any mismatch is one "refuse step=<step>" line and the plugin stays idle: no registration, no call into the game.
//
// Slots replaced in the copy: 0x00 (our destructor wrapper: the engine's destructor without its delete, then our
// free, since the object is ours), 0x03 GetName, 0x04 GetRootPath (""), 0x05 GetViewScaleMode (ShowAll), 0x06 LoadMovie
// (stage a: true without a movie; stage b: the engine's, logged, with addEventDispatcher forced off: our movie has no
// engine event backend), 0x08 ProcessMessage (logged; stage a answers kShow itself, as the engine's refuses a menu
// without a movie), and in stage a 0x0A IsMovieLoaded (true). The key is polled on a worker thread; every UI call runs
// on the main thread through SFSE's task interface.
//
// Stage=3 (c), FAL-216: stage (b) plus the data channel, with the movie make_probe_swf.py --channel writes. Inside our
// ProcessMessage, on the engine's own thread for this menu: at kShow the plugin finds the movie's two named children
// (getChildByName) and adds a click listener on the button whose handler is ours; at kShow and at every kUpdate (sent
// every 500 ms while the menu is open) it writes the player's position into the text field and reads it back. Pause
// state and the input holders (the UI menu stack and ControlMap's active input contexts) are logged at show, while
// open, at hide, on the main thread after each toggle, and on a second key. FlagSets cycles the menu flags per open.
// Checked first, at stage c only: 13 more ids (singletons of Main, the player and ControlMap; five RTTI type
// descriptors, by name; five Scaleform Value functions, each equal to SFSE 0.2.21's own address for 1.16.244), then,
// before first use, the type of every object: Main, the player, ControlMap, the movie (GFx::MovieImpl) and its root
// (GFx::AS3::MovieRoot), whose two slots we call (0x30 CreateFunction, 0x32 GetVariable; libxse and SFSE agree on
// both) must be inside the image. Reads of engine objects whose layout only libxse states (input contexts, the pause
// byte, the position) are guarded: a fault logs "fault" instead of stopping the game. A snapshot's menus= lists the
// open menus among a few known names, through the engine's IsMenuRegistered and IsMenuOpen, on the main thread only
// (libxse's menu stack at UI+0x3F0 read empty in every FAL-216 snapshot, the pause menu's too); off it, "-".
//
// Stage c with ClickCall set (FAL-246, native to script): each click also reaches a quest. On the main thread (SFSE's
// task interface) the plugin asks the script VM to run one global Papyrus function with no arguments
// (ClickCall=FOCC_B0.Click: the combined probe's B0 script, which resolves its probe quest and logs "b0 click" there)
// through IVirtualMachine::DispatchStaticCall, libxse's slot 0x2F. Checked first, at stage c: 3 more ids (FOCCPing's
// GameVM singleton and two RTTI ids, the RTTI ids by name); before the first call, the GameVM singleton is a GameVM by
// RTTI, the VM it holds (libxse GameVM::impl, +0xE0) a BSScript::Internal::VirtualMachine by RTTI at offset 0, and its
// vtable's slots 0x00 to 0x2F are inside the image. No arguments: a BSScrapArray that grows calls
// ScrapHeap::Allocate, which libxse 9d090c4 states as REL::ID{ 0 }, so the argument function never touches the array.
// No callback: a null functor, as the public precedents pass.
//
// Stage=4 (d), FAL-272: the STAT page, the first page the owner uses by hand. Stage (c)'s checks, with the movie
// make_probe_swf.py --page writes: a tab line and seven lines the plugin writes at kShow and every kUpdate, and two
// buttons, NEXT TAB (the other set of lines) and CLOSE (the menu closes, as on F10). The values are collected on the
// main thread (SFSE's task, before each kShow and kUpdate) and only written on the menu's thread. Every value is read,
// not called for, except two calls: the player's own GetActorValue, and the engine's lookup of a form by its form id
// (TESForm::LookupByID, equal to SFSE 0.2.21's GetFormByNumericID). The health, carry weight and experience are the
// actor values Starfield.esm's ActorValueInfo forms 0x2D4, 0x2DC and 0x2C9 name, and the game time its GameHour (0x38)
// and GameDaysPassed (0x39) globals: each accepted by its form id and RTTI type (at 3eb30d71 four of them did not pass
// an editor-ID check). FO4SF_Rads is found by editor ID at local id 0x800 of any plugin; the level is the player's base
// TESNPC's TESActorBaseData; the place is the parent cell's and its worldspace's names. (The data handler's per-type
// form lists, read at 5a4e6016, were empty: their raw entries are logged once, step=page_form_arrays, to settle the
// layout.)
// Checked before use: each form's type by its RTTI name; each base class's offset (ActorValueOwner, TESActorBaseData,
// TESFullName) from the RTTI class hierarchy, and that subobject's vtable naming the same complete type there; the
// string reader on our own menu name first; and which ActorValueOwner slot is GetActorValue (libxse declares a virtual
// destructor before it, SFSE 0.2.21 does not): slot 0 must be the adjustor thunk to the player's destructor. A value
// that fails its check prints "?" and its reason is logged once. PageFlagSets (default 0x9, the flag set at which the
// FAL-216 clicks reached our menu) cycles per open like FlagSets.
//
// Stage=5 (e), FAL-301: the page kit. One movie for every page (make_pipboy_kit.py, staged with --kit: a title bar,
// main tabs with a bracket, sub-tabs, a list of 16 rows with a selection bar and scrolling, 16 two-column value rows, a
// footer and key hints) and the pages as data: the [Kit] and [Page <TAB>/<SUB>] sections of this plugin's ini, read
// once at load with the grammar and checks of make_pipboy_kit.py's parse_kit (a wrong line: refuse step=pages, the kit
// stays off). A page is rows (Row=<label>|<value>), a list from a list provider or a notice. The values come from
// named value providers, stage d's reads (health, level, xp, carry_max, rads, cell, world, time, days, position) and
// av:<form id>, any actor value accepted by its RTTI type. The screen is built on the main thread and written on the
// menu's through `text` and `visible` only, each change read back. Keys (polled while the page is open and the game in
// front) and clicks (one listener on the movie's root, which reads the click's target name) move the selection, the
// sub-tab and the main tab; CLOSE keeps stage d's handler. Stage (d)'s checks and ids; nothing new is called.

#include "pch.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <unordered_map>
#include <vector>

// Win32 calls that libxse's REX::W32 does not wrap, imported the way REX/W32.cpp imports its own (REX/W32/BASE.h):
// libxse refuses a <windows.h> included before it
REX_W32_IMPORT(std::int16_t, GetAsyncKeyState, std::int32_t);
REX_W32_IMPORT(void*, GetForegroundWindow);
REX_W32_IMPORT(std::uint32_t, GetWindowThreadProcessId, void*, std::uint32_t*);
REX_W32_IMPORT(std::uint32_t, GetCurrentProcessId);

#include "world.h"   // FAL-250: the world-surface census and candidate (World=1; README.md, "World surface")

namespace
{
	using namespace std::string_view_literals;

	constexpr auto          kMenuName = "FO4SF_PipboyMenu";
	constexpr REL::Version  kRuntime{ 1, 16, 244, 0 };
	constexpr std::uint32_t kLoadMovieRva = 0x2551AB0;       // SFSE 0.2.21 sfse/Hooks_Scaleform.cpp: IMenu_LoadMovie
	constexpr std::uint32_t kPrecedentCtorRva = 0x25516B0;   // a public precedent's base IMenu constructor (logged only)
	constexpr std::size_t   kMenuBytes = 0x400;              // IMenu is 0x138; the engine's own menus are larger
	constexpr std::size_t   kSlots = 0x20;                   // primary vtable entries copied (IMenu declares 0x00-0x1A)
	constexpr std::size_t   kCtorScan = 0x200;
	constexpr std::size_t   kHeaderBytes = 96;               // Address Library format 5 header (libxse REL/IDDB.cpp)
	constexpr char          kTypeName[] = ".?AVIMenu@@";
	constexpr auto          kFieldName = "fo4sfPosition";    // make_probe_swf.py FIELD_NAME
	constexpr auto          kButtonName = "fo4sfButton";     // make_probe_swf.py BUTTON_NAME
	constexpr std::size_t   kMovieRootAt = 0x18;             // GFx::Movie: RefCountBase 0x00, StateBag 0x10, root 0x18
	constexpr std::size_t   kCreateFunctionSlot = 0x30;      // GFx::ASMovieRootBase (libxse and SFSE 0.2.21 agree)
	constexpr std::size_t   kGetVariableSlot = 0x32;
	constexpr std::size_t   kMainPausedAt = 0x448;           // libxse RE::Main::isGameMenuPaused
	constexpr std::size_t   kContextsAt = 0x2A8;             // libxse RE::ControlMap::activeInputContexts (16-byte items)
	constexpr std::size_t   kPositionAt = 0x80 + 0x0C;       // libxse RE::TESObjectREFR::data (0x80), OBJ_REFR::location
	constexpr std::size_t   kMaxListed = 16;                 // contexts listed per snapshot
	constexpr std::size_t   kMaxFlagSets = 16;   // FAL-414: a flag sweep (one set per open) needs more than four
	constexpr std::size_t   kGameVmImplAt = 0xE0;            // libxse RE::GameVM::impl (BSTSmartPointer<IVirtualMachine>)
	constexpr std::size_t   kDispatchStaticCallSlot = 0x2F;  // libxse IVirtualMachine::DispatchStaticCall
	constexpr std::size_t   kMaxName = 64;                   // ClickCall: each of the script's and function's names

	// stage d (the STAT page)
	constexpr std::uint32_t kDataHandlerRva = 0x5FD9B28;     // SFSE 0.2.21 sfse/GameData.h: TESDataHandler::GetSingleton
	constexpr std::uint32_t kLookupByIdRva = 0x5DE3B0;       // SFSE 0.2.21 sfse/GameForms.cpp: TESForm::GetFormByNumericID
	constexpr std::uint32_t kCoreFormIds = 0x1000;           // Starfield.esm form ids searched for the actor values
	constexpr std::uint32_t kRadsLocalId = 0x800;            // FO4SF_Rads in FO4SFRadsProbe.esm (dotnet/RadsProbe AvifId)
	constexpr std::uint32_t kGameHourId = 0x38;              // Starfield.esm GLOB GameHour (docs/ai/test-queue.md)
	constexpr std::uint32_t kGameDaysPassedId = 0x39;        // Starfield.esm GLOB GameDaysPassed
	constexpr std::uint32_t kHealthId = 0x2D4;               // Starfield.esm AVIF Health (the PC's read, 11 Nov)
	constexpr std::uint32_t kCarryWeightId = 0x2DC;          // Starfield.esm AVIF CarryWeight
	constexpr std::uint32_t kExperienceId = 0x2C9;           // Starfield.esm AVIF Experience
	constexpr std::size_t   kFormArrayEntries = 0xE0;        // form-list entries logged (SFSE: 0xDA before unk14E0)
	constexpr std::size_t   kFormArraysAt = 0x70;            // TESDataHandler::formArrays, libxse and SFSE agree: 0x18
	constexpr std::size_t   kFormArrayBytes = 0x18;          //   each, a lock, then a BSTArray of TESForm*
	constexpr std::size_t   kGlobType = 0x0A;                // FormType kGLOB, libxse and SFSE agree
	constexpr std::size_t   kAvifType = 0x6D;                // FormType kAVIF, libxse and SFSE agree
	constexpr std::size_t   kFormIdAt = 0x28;                // TESForm::formID, libxse and SFSE agree
	constexpr std::size_t   kGlobalEditorIdAt = 0x30;        // libxse RE::TESGlobal::formEditorID (a BSFixedString first)
	constexpr std::size_t   kGlobalBytesAt = 0x28;           // the TESGlobal bytes logged: from the form id to the end of
	constexpr std::size_t   kGlobalObjectBytes = 0x50;      //   the object (the game's own size for a GLOB, form type 0x0A at +0x2E)
	constexpr std::size_t   kGlobalBytes = kGlobalObjectBytes - kGlobalBytesAt;
	constexpr std::size_t   kGlobalValueAt = 0x48;           // the float the game's GetValue reads (vmovss xmm0, [r8+0x48]); libxse's
	constexpr std::size_t   kGlobalSearchFrom = 0x30;        //   +0x40 read -3.5924 at a156037c, and the slot at +0x28 is the form id
	constexpr float         kGlobalMinutes = 3.0f;           // GameHour and GameDaysPassed's fraction agree this close
	constexpr float         kMaxDays = 1000000.0f;           // GameDaysPassed below this
	constexpr std::size_t   kAvifEditorIdAt = 0x40;          // libxse RE::ActorValueInfo::editorID
	constexpr std::size_t   kBaseObjectAt = 0x80 + 0x18;     // libxse RE::TESObjectREFR::data, OBJ_REFR::objectReference
	constexpr std::size_t   kParentCellAt = 0xB0;            // libxse RE::TESObjectREFR::parentCell
	constexpr std::size_t   kCellWorldAt = 0x118;            // libxse RE::TESObjectCELL::cellWorldspace
	constexpr std::size_t   kLevelAt = 0x08 + 0x06;          // libxse RE::TESActorBaseData::actorData, ACTOR_BASE_DATA::level
	constexpr std::size_t   kFullNameAt = 0x08;              // libxse RE::TESFullName::fullName (a BSFixedStringCS)
	constexpr std::size_t   kPageLines = 7;                  // make_probe_swf.py PAGE_LINES
	constexpr std::size_t   kPageColumns = 54;               // make_probe_swf.py page_columns(): the characters of a line
	constexpr std::string_view kPageChars = " !#%&'()+,-./0123456789:=?ABCDEFGHIJKLMNOPQRSTUVWXYZ_";   // PAGE_FONT
	constexpr auto          kTabFieldName = "fo4sfTab";      // make_probe_swf.py TAB_FIELD
	constexpr auto          kLineFieldName = "fo4sfLine";    // make_probe_swf.py LINE_FIELD, then 0 to 6
	constexpr auto          kTabButtonName = "fo4sfTabButton";       // make_probe_swf.py TAB_BUTTON
	constexpr auto          kCloseButtonName = "fo4sfCloseButton";   // make_probe_swf.py CLOSE_BUTTON

	// stage e (the kit): make_pipboy_kit.py's sizes, columns, font and names
	constexpr std::size_t   kKitTabs = 5;                    // TABS: main tabs
	constexpr std::size_t   kKitSubs = 5;                    // SUBS: sub-tab slots
	constexpr std::size_t   kKitRows = 16;                   // ROWS: list rows on screen, and value rows
	constexpr std::size_t   kKitFooter = 3;                  // FOOTER: footer cells
	constexpr std::size_t   kKitMaxPageRows = 64;            // MAX_PAGE_ROWS: Row= lines per page
	constexpr std::size_t   kKitTitleColumns = 42;           // TITLE_COLUMNS (the header's too)
	constexpr std::size_t   kKitTabColumns = 9;              // TAB_COLUMNS
	constexpr std::size_t   kKitSubColumns = 13;             // SUB_COLUMNS
	constexpr std::size_t   kKitNameColumns = 33;            // NAME_COLUMNS
	constexpr std::size_t   kKitValueColumns = 8;            // VALUE_COLUMNS
	constexpr std::size_t   kKitInfoLabelColumns = 16;       // INFO_LABEL_COLUMNS
	constexpr std::size_t   kKitInfoValueColumns = 12;       // INFO_VALUE_COLUMNS
	constexpr std::size_t   kKitFooterColumns = 23;          // FOOTER_COLUMNS
	constexpr std::size_t   kKitFooterLabelColumns = 10;     // FOOTER_LABEL_COLUMNS
	constexpr std::size_t   kKitHintColumns = 72;            // HINT_COLUMNS
	constexpr std::uint32_t kKitVersion = 1;                 // KIT_VERSION
	constexpr std::size_t   kKitTestRows = 30;               // the kit_test list
	constexpr std::size_t   kInventoryListAt = 0xA0;         // libxse RE::TESObjectREFR::inventoryList (BSGuarded: the pointer first)
	constexpr std::size_t   kInventoryDataAt = 0x28;         // libxse RE::BGSInventoryList::data, BSTArray<BGSInventoryItem>
	constexpr std::size_t   kInventoryItemSize = 0x28;       // libxse sizeof(RE::BGSInventoryItem)
	constexpr std::size_t   kItemStacksAt = 0x10;            // libxse RE::BGSInventoryItem::stacks, BSTArray<Stack>
	constexpr std::size_t   kItemFlagsAt = 0x20;             // libxse RE::BGSInventoryItem::flags (bits 0-2: the equip slot)
	constexpr std::size_t   kStackSize = 0x10;               // libxse sizeof(RE::BGSInventoryItem::Stack)
	constexpr std::size_t   kStackCountAt = 0x08;            // a u32: the PC's step=kit_inventory read 01000000 here (11 Nov)
	constexpr std::size_t   kKitMaxItems = 512;              // the inventory list's rows, at most
	constexpr std::size_t   kFileCollectionAt = 0x1580;      // libxse RE::TESDataHandler::compiledFileCollection
	constexpr std::size_t   kFileNameAt = 0x38;              // libxse RE::TESFile::fileName, char[260]
	constexpr std::size_t   kFileNameSize = 260;
	constexpr std::size_t   kFileCompileIndexAt = 0x1B7;     // libxse RE::TESFile::compileIndex
	constexpr std::size_t   kFileIndexAt = 0x218;            // libxse RE::TESFile::fileIndex: full u8, medium u8, small u16
	constexpr std::size_t   kKitMaxFiles = 4096;             // a file list's entries, at most
	constexpr std::size_t   kQuestFlagsAt = 0x10C;           // libxse RE::TESQuest QUEST_DATA flags, u16 (bits: the PC's log)
	constexpr std::size_t   kQuestBytesAt = 0x100;           // the quest's bytes logged once (flags and stage among them)
	constexpr std::string_view kKitChars = " !#%&'()*+,-./0123456789:;<=>?ABCDEFGHIJKLMNOPQRSTUVWXYZ[]_";   // KIT_FONT
	constexpr auto          kKitTitle = "fo4sfTitle";        // NAMES
	constexpr auto          kKitHeader = "fo4sfHeaderInfo";
	constexpr auto          kKitTab = "fo4sfTab";            // then 0 to 4, as each name below with a number
	constexpr auto          kKitTabMark = "fo4sfTabMark";
	constexpr auto          kKitTabHit = "fo4sfTabHit";
	constexpr auto          kKitSub = "fo4sfSub";
	constexpr auto          kKitSubDim = "fo4sfSubDim";
	constexpr auto          kKitSubHit = "fo4sfSubHit";
	constexpr auto          kKitRowName = "fo4sfRowName";
	constexpr auto          kKitRowValue = "fo4sfRowValue";
	constexpr auto          kKitRowNameSel = "fo4sfRowNameSel";
	constexpr auto          kKitRowValueSel = "fo4sfRowValueSel";
	constexpr auto          kKitBar = "fo4sfBar";
	constexpr auto          kKitRowHit = "fo4sfRowHit";
	constexpr auto          kKitMoreUp = "fo4sfMoreUp";
	constexpr auto          kKitMoreDown = "fo4sfMoreDown";
	constexpr auto          kKitInfoLabel = "fo4sfInfoLabel";
	constexpr auto          kKitInfoValue = "fo4sfInfoValue";
	constexpr auto          kKitFoot = "fo4sfFoot";
	constexpr auto          kKitHints = "fo4sfHints";
	constexpr auto          kKitClose = "fo4sfClose";
	constexpr auto          kKitId = "fo4sfKitId";
	// VALUE_PROVIDERS and LIST_PROVIDERS; av:<hex> is the actor value of that form id
	constexpr std::array<std::string_view, 10> kKitValues{ "health", "level", "xp", "carry_max", "rads", "cell", "world",
		"time", "days", "position" };
	constexpr std::array<std::string_view, 3> kKitLists{ "kit_test", "inventory", "quests" };
	constexpr std::string_view kKitActorValue = "av:";
	// the menus a main-thread snapshot asks the engine about (IsMenuRegistered, IsMenuOpen); only Console is named by
	// libxse, the rest are guesses, and the first snapshot logs which of them are registered
	constexpr std::array<const char*, 14> kKnownMenus{ "FO4SF_PipboyMenu", "HUDMenu", "CursorMenu", "PauseMenu",
		"Console", "LoadingMenu", "FaderMenu", "DataMenu", "InventoryMenu", "MainMenu", "DialogueMenu", "ContainerMenu",
		"BarterMenu", "SleepWaitMenu" };

	struct Id
	{
		const char*   name;
		std::uint32_t id;
		const char*   source;
	};

	enum : std::size_t
	{
		kUISingleton,
		kRegisterMenu,
		kIsMenuOpen,
		kQueueSingleton,
		kAddMessage,
		kStringGetEntry,
		kStringRelease,
		kVtblPrimary,
		kVtblInput,
		kVtblSink,
		kRtti,
		kCtor,
		kDtor,
		kLoadMovie,
		kProcessMessage,
		kIsMovieLoaded,
		kIdCountB,                       // stages a and b check the ids above; stage c all of them
		kMainSingleton = kIdCountB,
		kPlayerSingleton,
		kControlMapSingleton,
		kMainRtti,
		kPlayerRtti,
		kControlMapRtti,
		kMovieImplRtti,
		kMovieRootRtti,
		kValueAddRef,
		kValueRelease,
		kValueGetMember,
		kValueSetMember,
		kValueInvoke,
		kGameVmSingleton,                // FAL-246: the click reaches a quest
		kGameVmRtti,
		kVmRtti,
		kIdCountC,                       // stage c checks the ids above; stage d all of them
		kDataHandlerSingleton = kIdCountC,
		kLookupById,
		kIdCount
	};

	// README, "Where every id comes from": libxse = libxse/commonlibsf 9d090c4 include/RE/IDs*.h; precedent = a
	// public precedent's CommonLibSF fork, annotated for 1.16.244 (its offsets are logged here, never assumed)
	constexpr std::array<Id, kIdCount> kIds{ {
		{ "UI.Singleton", 937580, "libxse" },
		{ "UI.RegisterMenu", 130463, "libxse" },
		{ "UI.IsMenuOpen", 130475, "libxse" },
		{ "UIMessageQueue.Singleton", 937897, "libxse" },
		{ "UIMessageQueue.AddMessage", 130659, "libxse" },
		{ "BSStringPool.GetEntry", 1186742, "libxse" },
		{ "BSStringPool.Entry.Release", 139340, "libxse" },
		{ "IMenu.vtable.primary", 475515, "libxse VTABLE_IMenu, checked by RTTI" },
		{ "IMenu.vtable.BSInputEventUser", 475517, "libxse VTABLE_IMenu[1], checked by RTTI" },  // +0x10, 10 slots
		{ "IMenu.vtable.BSTEventSink", 475519, "libxse VTABLE_IMenu[0], checked by RTTI" },     // +0x50, 2 slots
		{ "IMenu.RTTI", 844868, "libxse RTTI_IMenu" },
		{ "IMenu.ctor", 130615, "precedent" },
		{ "IMenu.scalar_deleting_dtor", 130616, "precedent" },
		{ "IMenu.LoadMovie", 130618, "precedent" },
		{ "IMenu.ProcessMessage", 130624, "precedent" },
		{ "IMenu.IsMovieLoaded", 130619, "precedent" },
		{ "Main.Singleton", 883591, "libxse" },
		{ "PlayerCharacter.Singleton", 922868, "libxse" },
		{ "ControlMap.Singleton", 938003, "libxse" },
		{ "Main.RTTI", 859948, "libxse RTTI_Main, checked by name" },
		{ "PlayerCharacter.RTTI", 860819, "libxse RTTI_PlayerCharacter, checked by name" },
		{ "ControlMap.RTTI", 867481, "libxse RTTI_ControlMap, checked by name" },
		{ "GFx.MovieImpl.RTTI", 841612, "libxse RTTI_Scaleform__GFx__MovieImpl, checked by name" },
		{ "GFx.AS3.MovieRoot.RTTI", 842209, "libxse RTTI_Scaleform__GFx__AS3__MovieRoot, checked by name" },
		{ "GFx.Value.ObjectAddRef", 169745, "libxse, equal to SFSE's" },
		{ "GFx.Value.ObjectRelease", 169746, "libxse, equal to SFSE's" },
		{ "GFx.Value.GetMember", 169748, "libxse, equal to SFSE's" },
		{ "GFx.Value.SetMember", 169749, "libxse, equal to SFSE's" },
		{ "GFx.Value.Invoke", 169750, "libxse, equal to SFSE's" },
		{ "GameVM.Singleton", 937585, "libxse, as FOCCPing" },
		{ "GameVM.RTTI", 865426, "libxse RTTI_GameVM, checked by name" },
		{ "BSScript.Internal.VirtualMachine.RTTI", 870795, "libxse RTTI_BSScript__Internal__VirtualMachine, checked by name" },
		{ "TESDataHandler.Singleton", 937572, "libxse, equal to SFSE's" },
		{ "TESForm.LookupByID", 47401, "libxse, equal to SFSE's" },
	} };

	// stage c: each RTTI id's type name after its ".?AV" (class) or ".?AU" (struct) prefix, and SFSE 0.2.21's own
	// 1.16.244 address of each Value function (sfse/ScaleformValue.h at 48535cc, ObjectInterface); the Address Library
	// offset must equal it
	constexpr std::array<std::pair<std::size_t, std::string_view>, 7> kRttiNames{ {
		{ kMainRtti, "Main@@"sv },
		{ kPlayerRtti, "PlayerCharacter@@"sv },
		{ kControlMapRtti, "ControlMap@@"sv },
		{ kMovieImplRtti, "MovieImpl@GFx@Scaleform@@"sv },
		{ kMovieRootRtti, "MovieRoot@AS3@GFx@Scaleform@@"sv },
		{ kGameVmRtti, "GameVM@@"sv },
		{ kVmRtti, "VirtualMachine@Internal@BSScript@@"sv },
	} };
	constexpr std::array<std::pair<std::size_t, std::uint32_t>, 5> kSfseRvas{ {
		{ kValueAddRef, 0x3352400 },
		{ kValueRelease, 0x33524A0 },
		{ kValueGetMember, 0x33528A0 },
		{ kValueSetMember, 0x3352C90 },
		{ kValueInvoke, 0x33530B0 },
	} };

	using Ctor_t = void* (*)(void*);
	using Dtor_t = void* (*)(void*, std::uint32_t);
	using LoadMovie_t = bool (*)(void*, bool, bool);
	using ProcessMessage_t = RE::UI_MESSAGE_RESULT (*)(void*, RE::UIMessageData&);

	// the primary vtable copy, with the engine's RTTI complete object locator in the slot before it, where MSVC's
	// dynamic_cast reads it. The engine casts a shown menu from IMenu to GameMenuBase (FAL-187 hang dump at b3f352b7);
	// without the locator the cast read the global that happened to lie before the copy, and the game hung
	struct PrimaryVtable
	{
		std::uintptr_t                     locator;
		std::array<std::uintptr_t, kSlots> slots;
	};
	static_assert(sizeof(PrimaryVtable) == (1 + kSlots) * sizeof(std::uintptr_t));   // no padding: locator is slots[-1]

	// FAL-414: the BSInputEventUser vtable copy (subobject 0x10, ten slots; the locator again one slot before it)
	constexpr std::size_t kInputSlots = 10;
	struct InputVtable
	{
		std::uintptr_t                          locator;
		std::array<std::uintptr_t, kInputSlots> slots;
	};
	static_assert(sizeof(InputVtable) == (1 + kInputSlots) * sizeof(std::uintptr_t));

	// INI (FO4SFPipboyMenu.ini next to the dll)
	int           g_stage = 0;      // 0 off, 1 = (a), 2 = (b), 3 = (c), 4 = (d), 5 = (e)
	std::uint32_t g_key = 0x79;     // F10
	std::uint32_t g_flags = 0;      // OR'ed into the flags the constructor set
	bool          g_keepAlive = true;

	std::uintptr_t                           g_base = 0;
	std::size_t                              g_imageSize = 0;
	std::array<std::uint32_t, kIdCount>      g_rva{};
	PrimaryVtable                            g_vtbl{};
	InputVtable                              g_inputVtbl{};
	bool (*g_engineShouldHandle)(void*, const void*) = nullptr;   // input vtable [01], called with this = menu + 0x10
	void (*g_engineOnButton)(void*, const void*) = nullptr;       // input vtable [08]
	std::array<std::uint32_t, 4>             g_cancelCodes{ 0x1B, 0x09, 0, 0 };   // INI CancelCodes: Esc, Tab (Windows virtual-key codes: the PC's game run, #738)
	std::size_t                              g_cancelCount = 2;
	std::atomic<bool>                        g_cancelHeld{ false };    // a Tab or Esc press already closed the menu, not yet released
	std::atomic<bool>                        g_cancelNow{ false };     // Tab or Esc heard while open: the key thread closes the menu
	std::atomic<std::uint32_t>               g_cancelLogged{ 0 };
	Ctor_t                                   g_ctor = nullptr;
	Dtor_t                                   g_engineDtor = nullptr;
	LoadMovie_t                              g_engineLoadMovie = nullptr;
	ProcessMessage_t                         g_engineProcessMessage = nullptr;
	const SFSE::TaskInterface*               g_task = nullptr;
	std::atomic<bool>                        g_registered{ false };
	std::atomic<std::uint32_t>               g_created{ 0 };
	std::atomic<std::uint32_t>               g_otherMessages{ 0 };
	std::atomic<int>                         g_expectOpen{ -1 };

	// stage c (INI FlagSets, SnapshotKey)
	std::array<std::uint32_t, kMaxFlagSets>  g_flagSets{};
	std::size_t                              g_flagSetCount = 0;
	std::uint32_t                            g_snapshotKey = 0x7A;   // F11; 0 = none
	std::atomic<std::uint32_t>               g_ctorFlags{ 0 };
	std::atomic<std::uint32_t>               g_shows{ 0 };
	std::atomic<std::uint32_t>               g_updates{ 0 };
	std::atomic<std::uint32_t>               g_clicks{ 0 };
	std::atomic<std::uint32_t>               g_snapshots{ 0 };
	std::atomic<bool>                        g_open{ false };          // the main thread's last IsMenuOpen
	std::atomic<bool>                        g_channelOff{ false };    // a channel check refused: no more channel calls
	std::atomic<const void*>                 g_listenedMovie{ nullptr };   // the movie our click listener is on
	std::atomic<const void*>                 g_checkedMovie{ nullptr };    // the movie whose root RootOf checked
	std::atomic<int>                         g_mainOk{ -1 };           // -1 unchecked, 0 refused, 1 checked
	std::atomic<int>                         g_playerOk{ -1 };
	std::atomic<int>                         g_controlMapOk{ -1 };

	// stage c, FAL-246 (INI ClickCall=<script>.<function>; empty = off)
	std::string                              g_clickScript;
	std::string                              g_clickFunction;
	std::atomic<int>                         g_gameVmOk{ -1 };
	std::uintptr_t                           g_checkedVm = 0;          // main thread only: the VM whose type was checked
	bool                                     g_vmOff = false;          // main thread only: a VM check refused

	// stage d (INI PageFlagSets): the page. The text is collected on the main thread and written on the menu's
	std::atomic<std::uint32_t>               g_tab{ 0 };               // the shown tab: 0 STATUS, 1 DATA
	std::atomic<std::uint32_t>               g_tabClicks{ 0 };
	std::atomic<std::uint32_t>               g_closeClicks{ 0 };
	std::atomic<std::uint32_t>               g_pageWrites{ 0 };
	std::atomic<bool>                        g_refreshNow{ false };    // NEXT TAB: the key thread sends an update now
	std::atomic<bool>                        g_closeNow{ false };      // CLOSE: the key thread closes the menu
	std::mutex                               g_pageLock;
	std::array<std::array<std::string, kPageLines + 1>, 2> g_pageText;   // [tab][0] the tab line, [1..7] the lines

	std::uintptr_t Address(std::size_t a_id) { return g_base + g_rva[a_id]; }

	std::size_t IdCount() { return g_stage >= 4 ? kIdCount : g_stage == 3 ? kIdCountC : kIdCountB; }   // (e): (d)'s ids

	bool InImage(std::uintptr_t a_addr, std::size_t a_len)
	{
		return a_addr >= g_base && a_len <= g_imageSize && a_addr - g_base <= g_imageSize - a_len;
	}

	std::string Hex(std::uintptr_t a_value) { return std::format("{:#x}", a_value); }

	const RE::BSFixedString& MenuName()
	{
		// process lifetime: a BSFixedString destructor calls the engine (the main thread makes it first)
		static auto* const name = new RE::BSFixedString(kMenuName);
		return *name;
	}

	bool IsOurs(const void* a_menu)
	{
		return a_menu && *static_cast<const std::uintptr_t*>(a_menu) == reinterpret_cast<std::uintptr_t>(g_vtbl.slots.data());
	}

	const void* MovieOf(const void* a_menu)
	{
		return static_cast<const RE::IMenu*>(a_menu)->uiMovie.get();
	}

	bool Refuse(std::string_view a_step, const std::string& a_what);

	// ------------------------------------------------------------------------------------------- stage c: reading
	// A read behind a pointer the engine handed us, or of a layout only libxse states: an access fault returns false
	// instead of stopping the game (a structured exception handler; no C++ object lives in this frame)
	bool Peek(std::uintptr_t a_addr, void* a_out, std::size_t a_len)
	{
		__try {
			std::memcpy(a_out, reinterpret_cast<const void*>(a_addr), a_len);
			return true;
		} __except (1 /* EXCEPTION_EXECUTE_HANDLER */) {
			return false;
		}
	}

	template <class T>
	bool Peek(std::uintptr_t a_addr, T& a_out)
	{
		return Peek(a_addr, &a_out, sizeof(T));
	}

	// the mangled name in an RTTI type descriptor (inside the image), or "" if it leaves the image unterminated
	std::string TypeNameAt(std::uintptr_t a_descriptor)
	{
		std::string name;
		for (std::size_t i = 0; i < 96 && InImage(a_descriptor + 0x10 + i, 1); ++i) {
			const char c = *reinterpret_cast<const char*>(a_descriptor + 0x10 + i);
			if (!c) {
				return name;
			}
			name += (c >= 0x20 && c < 0x7F) ? c : '?';
		}
		return {};
	}

	bool NameIs(std::string_view a_name, std::string_view a_tail)   // ".?AV" + tail (a class) or ".?AU" + tail (a struct)
	{
		return a_name.size() == 4 + a_tail.size() && (a_name.starts_with(".?AV") || a_name.starts_with(".?AU")) &&
		       a_name.substr(4) == a_tail;
	}

	struct ObjectType
	{
		std::uintptr_t descriptor = 0;
		std::uintptr_t hierarchy = 0;   // the complete type's class hierarchy descriptor
		std::uint32_t  offset = 0;
		std::string    name;
	};

	// an object's type through its vtable's complete object locator; false if a read faults or leaves the image
	bool TypeOf(std::uintptr_t a_object, ObjectType& a_out)
	{
		std::uintptr_t vt = 0;
		if (!a_object || !Peek(a_object, vt) || !InImage(vt - 8, 8)) {
			return false;
		}
		const auto col = *reinterpret_cast<const std::uintptr_t*>(vt - 8);
		if (!InImage(col, 0x14) || *reinterpret_cast<const std::uint32_t*>(col) != 1) {
			return false;
		}
		a_out.offset = *reinterpret_cast<const std::uint32_t*>(col + 0x04);
		a_out.descriptor = g_base + *reinterpret_cast<const std::uint32_t*>(col + 0x0C);
		a_out.hierarchy = g_base + *reinterpret_cast<const std::uint32_t*>(col + 0x10);
		a_out.name = TypeNameAt(a_out.descriptor);
		return !a_out.name.empty();
	}

	std::string ShortName(std::string_view a_name)   // ".?AVHUDMenu@@" -> "HUDMenu@@" -> "HUDMenu"
	{
		if (a_name.size() > 4) {
			a_name.remove_prefix(4);
		}
		if (a_name.ends_with("@@")) {
			a_name.remove_suffix(2);
		}
		return std::string(a_name);
	}

	// a singleton is the type its RTTI id names (the same descriptor, at subobject offset 0), checked once; a null
	// singleton is not cached (it may not exist yet)
	bool CheckSingleton(std::string_view a_what, std::size_t a_singleton, std::size_t a_rtti, std::atomic<int>& a_state)
	{
		const auto state = a_state.load();
		if (state >= 0) {
			return state == 1;
		}
		std::uintptr_t object = 0;
		if (!Peek(Address(a_singleton), object) || !object) {
			REX::INFO("step=object name={} result=null", a_what);
			return false;
		}
		ObjectType type;
		const bool known = TypeOf(object, type);
		if (!known || type.descriptor != Address(a_rtti) || type.offset != 0) {
			a_state = 0;
			Refuse("object", std::format("name={} object={} type={} offset={} (its reads stay off)", a_what, Hex(object),
				known ? type.name : "unreadable", Hex(type.offset)));
			return false;
		}
		a_state = 1;
		REX::INFO("step=object name={} object={} type={}", a_what, Hex(object), type.name);
		return true;
	}

	std::uintptr_t Singleton(std::size_t a_singleton)
	{
		std::uintptr_t object = 0;
		Peek(Address(a_singleton), object);
		return object;
	}

	struct ArrayHead   // BSTArray (libxse): size, capacity, data
	{
		std::uint32_t  size;
		std::uint32_t  capacity;
		std::uintptr_t data;
	};

	std::string ReadPaused()
	{
		if (!CheckSingleton("Main", kMainSingleton, kMainRtti, g_mainOk)) {
			return "?";
		}
		std::uint8_t paused = 0;
		return Peek(Singleton(kMainSingleton) + kMainPausedAt, paused) ? std::to_string(paused) : "fault";
	}

	// which of kKnownMenus are open, through the engine's own IsMenuRegistered and IsMenuOpen (the calls Register and
	// Toggle make): main thread only. The first call logs which names are registered, so a wrong guess shows
	std::string ReadMenus()
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return "no_ui";
		}
		// process lifetime, as MenuName(): made once, on the main thread
		static const auto* const names = [] {
			auto* list = new std::vector<RE::BSFixedString>();
			for (const auto* name : kKnownMenus) {
				list->emplace_back(name);
			}
			return list;
		}();
		static bool logged = false;
		std::string open;
		std::string registered;
		std::string unknown;
		std::size_t count = 0;
		for (std::size_t i = 0; i < names->size(); ++i) {
			const auto& name = (*names)[i];
			if (!ui->IsMenuRegistered(name)) {
				unknown += std::format("{}{}", unknown.empty() ? "" : ",", kKnownMenus[i]);
				continue;
			}
			registered += std::format("{}{}", registered.empty() ? "" : ",", kKnownMenus[i]);
			if (ui->IsMenuOpen(name)) {
				open += std::format("{}{}", count++ ? "," : "", kKnownMenus[i]);
			}
		}
		if (!logged) {
			logged = true;
			REX::INFO("step=menu_names registered={} not_registered={}", registered.empty() ? "none" : registered,
				unknown.empty() ? "none" : unknown);
		}
		return std::format("{}[{}]", count, open);
	}

	// ControlMap's active input contexts in stored order (their ids)
	std::string ReadContexts()
	{
		if (!CheckSingleton("ControlMap", kControlMapSingleton, kControlMapRtti, g_controlMapOk)) {
			return "?";
		}
		ArrayHead list{};
		if (!Peek(Singleton(kControlMapSingleton) + kContextsAt, list)) {
			return "fault";
		}
		std::string out = std::format("{}[", list.size);
		for (std::uint32_t i = 0; i < list.size && i < kMaxListed; ++i) {
			std::uint8_t id = 0;
			out += std::format("{}{}", i ? "," : "", Peek(list.data + 16ull * i, id) ? std::to_string(id) : "fault");
		}
		return out + "]";
	}

	// FAL-414 diagnostic, main thread, on the snapshot key: each known menu the UI has open, with its flags and the four
	// unnamed IMenu words at +0xC4..+0xD0 (read with Peek), so a run with our menu, the data menu and the pause menu open
	// shows what a real menu asks the control map for
	void LogOpenMenuDetails()
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return;
		}
		static const auto* const names = [] {
			auto* list = new std::vector<RE::BSFixedString>();
			for (const auto* name : kKnownMenus) {
				list->emplace_back(name);
			}
			return list;
		}();
		for (std::size_t i = 0; i < names->size(); ++i) {
			const auto& name = (*names)[i];
			if (!ui->IsMenuRegistered(name) || !ui->IsMenuOpen(name)) {
				continue;
			}
			const auto menu = ui->GetMenu(name);
			const auto at = reinterpret_cast<std::uintptr_t>(menu.get());
			std::uint32_t flags = 0;
			std::array<std::uint32_t, 4> words{};
			const bool ok = at && Peek(at + 0xC0, flags) && Peek(at + 0xC4, words);
			REX::INFO("step=menu_detail name={} menu={} {}", kKnownMenus[i], Hex(at),
				ok ? std::format("flags={} c4={} c8={} cc={} d0={}", Hex(flags), Hex(words[0]), Hex(words[1]), Hex(words[2]), Hex(words[3])) :
				     std::string("unreadable"));
		}
	}

	// pause state and who holds input, on whichever thread calls it (a_main: the main thread, where menus= is read)
	void Snapshot(std::string_view a_tag, bool a_main = false)
	{
		const auto n = ++g_snapshots;
		const auto paused = ReadPaused();
		const auto menus = a_main ? ReadMenus() : "-";
		const auto contexts = ReadContexts();
		REX::INFO("step=snapshot n={} tag={} paused={} menus={} contexts={} expected_open={}", n, a_tag, paused, menus,
			contexts, g_expectOpen.load());
		if (a_main && a_tag == "key") {
			LogOpenMenuDetails();
		}
	}

	bool ReadPosition(std::array<float, 3>& a_xyz)
	{
		return CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) &&
		       Peek(Singleton(kPlayerSingleton) + kPositionAt, a_xyz);
	}

	// ------------------------------------------------------------------------------------------- stage c: the channel
	// our movie's ActionScript 3 root, checked once per movie: the pointer at +0x18 of the movie is a
	// GFx::AS3::MovieRoot by RTTI, and its slots 0x30 and 0x32 are inside the image. The movie's own type is logged.
	RE::Scaleform::GFx::ASMovieRootBase* RootOf(const void* a_menu)
	{
		const auto movie = reinterpret_cast<std::uintptr_t>(MovieOf(a_menu));
		if (!movie || g_channelOff) {
			return nullptr;
		}
		std::uintptr_t root = 0;
		if (g_checkedMovie != MovieOf(a_menu)) {
			ObjectType movieType;
			ObjectType rootType;
			std::uintptr_t vt = 0;
			const bool movieKnown = TypeOf(movie, movieType);
			if (!Peek(movie + kMovieRootAt, root) || !TypeOf(root, rootType) || rootType.descriptor != Address(kMovieRootRtti)) {
				g_channelOff = true;
				Refuse("channel", std::format("what=movie_root movie={} movie_type={} root={} root_type={}", Hex(movie),
					movieKnown ? movieType.name : "unreadable", Hex(root), rootType.name.empty() ? "unreadable" : rootType.name));
				return nullptr;
			}
			Peek(root, vt);
			const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
			if (!InImage(vt, (kGetVariableSlot + 1) * 8) || !InImage(slot[kCreateFunctionSlot], 1) || !InImage(slot[kGetVariableSlot], 1)) {
				g_channelOff = true;
				Refuse("channel", std::format("what=root_slots root={} vtable={}", Hex(root), Hex(vt)));
				return nullptr;
			}
			REX::INFO("step=movie_root movie={} movie_type={} root={} root_type={} root_offset={} create_function={} get_variable={}",
				Hex(movie), movieKnown ? movieType.name : "unreadable", Hex(root), rootType.name, Hex(rootType.offset),
				Hex(slot[kCreateFunctionSlot] - g_base), Hex(slot[kGetVariableSlot] - g_base));
			g_checkedMovie = MovieOf(a_menu);
		} else {
			Peek(movie + kMovieRootAt, root);
		}
		return reinterpret_cast<RE::Scaleform::GFx::ASMovieRootBase*>(root);
	}

	int TypeCode(const RE::Scaleform::GFx::Value& a_value) { return static_cast<int>(a_value.GetType()); }

	// the root's child of that instance name (getChildByName, an ActionScript 3 DisplayObjectContainer method)
	bool ChildOf(RE::Scaleform::GFx::Value& a_root, const char* a_name, RE::Scaleform::GFx::Value& a_out)
	{
		const RE::Scaleform::GFx::Value name(a_name);
		return a_root.Invoke("getChildByName", &a_out, &name, 1) && a_out.IsObject();
	}

	// ------------------------------------------------------------------------------------------- stage c: click to quest
	// FAL-246, main thread only. The script VM: the GameVM singleton is a GameVM (RTTI, offset 0, once), the VM it holds a
	// BSScript::Internal::VirtualMachine (RTTI at offset 0: IVirtualMachine is its first base), and its vtable's slots up
	// to DispatchStaticCall's are inside the image. nullptr while there is none (logged) or after a refusal
	RE::BSScript::IVirtualMachine* ScriptVm()
	{
		if (g_vmOff || !CheckSingleton("GameVM", kGameVmSingleton, kGameVmRtti, g_gameVmOk)) {
			return nullptr;
		}
		std::uintptr_t vm = 0;
		if (!Peek(Singleton(kGameVmSingleton) + kGameVmImplAt, vm) || !vm) {
			REX::INFO("step=object name=VirtualMachine result=null");
			return nullptr;
		}
		if (vm != g_checkedVm) {
			ObjectType     type;
			std::uintptr_t vt = 0;
			const bool     known = TypeOf(vm, type) && Peek(vm, vt);
			if (!known || type.descriptor != Address(kVmRtti) || type.offset != 0 ||
				!InImage(vt, (kDispatchStaticCallSlot + 1) * 8)) {
				g_vmOff = true;
				Refuse("object", std::format("name=VirtualMachine object={} type={} offset={} vtable={} (no click reaches a script)",
					Hex(vm), known ? type.name : "unreadable", Hex(type.offset), Hex(vt)));
				return nullptr;
			}
			const auto* slot = reinterpret_cast<const std::uintptr_t*>(vt);
			for (std::size_t i = 0; i <= kDispatchStaticCallSlot; ++i) {
				if (!InImage(slot[i], 1)) {
					g_vmOff = true;
					Refuse("object", std::format("name=VirtualMachine vtable={} slot={} reason=outside_image", Hex(vt), Hex(i)));
					return nullptr;
				}
			}
			g_checkedVm = vm;
			REX::INFO("step=object name=VirtualMachine object={} type={} dispatch_static_call={}", Hex(vm), type.name,
				Hex(slot[kDispatchStaticCallSlot] - g_base));
		}
		return reinterpret_cast<RE::BSScript::IVirtualMachine*>(vm);
	}

	// after click n: the VM queues one call of the ClickCall function and runs it on its own schedule; that function's
	// own log line says when it ran
	void DispatchClick(std::uint32_t a_n)
	{
		auto* const vm = ScriptVm();
		if (!vm) {
			REX::INFO("step=dispatch n={} call={}.{} result=no_vm", a_n, g_clickScript, g_clickFunction);
			return;
		}
		const RE::BSFixedString                                        script(g_clickScript.c_str());
		const RE::BSFixedString                                        function(g_clickFunction.c_str());
		const RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> noCallback{};
		// no arguments: growing the array would call ScrapHeap::Allocate, REL::ID{ 0 } in libxse 9d090c4
		const auto noArguments = [](RE::BSScrapArray<RE::BSScript::Variable>&) { return true; };
		const bool queued = vm->DispatchStaticCall(script, function, noArguments, noCallback, 0);
		REX::INFO("step=dispatch n={} call={}.{} queued={}", a_n, g_clickScript, g_clickFunction, queued ? 1 : 0);
	}

	// the button's click handler: Scaleform calls it from the movie. Static and never released by us: the movie holds
	// its own references (Scaleform's count at +0x08) on top of ours, so the count never reaches zero
	class ClickHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto n = ++g_clicks;
			REX::INFO("step=click n={} args={} movie={}", n, a_params.argCount, Hex(reinterpret_cast<std::uintptr_t>(a_params.movie)));
			if (!g_clickScript.empty()) {   // FAL-246: on to the script VM, from the main thread
				g_task->AddTask([n]() { DispatchClick(n); });
			}
		}
	};
	ClickHandler g_clickHandler;

	// once per movie, at kShow: our function as the button's "click" listener
	void ChannelListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || g_listenedMovie == movie) {
			return;
		}
		g_listenedMovie = movie;
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value button;
		RE::Scaleform::GFx::Value function;
		const bool gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		const bool gotButton = gotRoot && ChildOf(top, kButtonName, button);
		bool       added = false;
		if (gotButton) {
			root->CreateFunction(&function, &g_clickHandler);
			if (!function.IsUndefined()) {
				std::array<RE::Scaleform::GFx::Value, 2> args;
				args[0] = "click";
				args[1] = function;
				added = button.Invoke("addEventListener", nullptr, args.data(), args.size());
			}
		}
		REX::INFO("step=listen root={} button={} function_type={} added={} event=click", gotRoot ? 1 : 0, gotButton ? 1 : 0,
			TypeCode(function), added ? 1 : 0);
	}

	// at kShow and every kUpdate: the player's position into the field, then read back
	void ChannelWrite(const void* a_menu, std::uint32_t a_n)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		std::array<float, 3> xyz{};
		const bool  havePosition = ReadPosition(xyz) && std::isfinite(xyz[0]) && std::isfinite(xyz[1]) && std::isfinite(xyz[2]);
		const auto  clicks = g_clicks.load();
		const auto  text = havePosition ? std::format("X {:.1f} Y {:.1f} Z {:.1f} CLICKS {}", xyz[0], xyz[1], xyz[2], clicks) :
		                                  std::format("NO POSITION CLICKS {}", clicks);
		RE::Scaleform::GFx::Value top;
		RE::Scaleform::GFx::Value field;
		RE::Scaleform::GFx::Value back;
		const bool gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		const bool gotField = gotRoot && ChildOf(top, kFieldName, field);
		const bool set = gotField && field.SetMember("text", RE::Scaleform::GFx::Value(text.c_str()));
		const bool got = gotField && field.GetMember("text", &back) && back.IsString();
		const std::string read = got ? back.GetString() : "";
		if (a_n <= 20 || a_n % 20 == 0 || read != text) {
			REX::INFO("step=field n={} root={} field={} set={} read_back={} match={} text=\"{}\" read=\"{}\"", a_n,
				gotRoot ? 1 : 0, gotField ? 1 : 0, set ? 1 : 0, got ? 1 : 0, read == text ? "yes" : "no", text, read);
		}
	}

	std::uint32_t FlagSetIndex(std::uint32_t a_n) { return g_flagSetCount ? (a_n - 1) % static_cast<std::uint32_t>(g_flagSetCount) : 0; }
	std::uint32_t FlagSet(std::uint32_t a_n) { return g_flagSetCount ? g_flagSets[FlagSetIndex(a_n)] : 0; }

	// at kShow, before the engine handles it: the constructor's flags | Flags | this open's FlagSets entry
	void ApplyFlagSet(void* a_self, std::uint32_t a_show)
	{
		auto*      imenu = static_cast<RE::IMenu*>(a_self);
		const auto had = imenu->flags;
		const auto want = g_ctorFlags.load() | g_flags | FlagSet(a_show);
		if (had != want) {
			imenu->flags = want;
			imenu->flagsUpdated = true;
		}
		REX::INFO("step=flags show={} set={} had={} now={}", a_show, FlagSetIndex(a_show), Hex(had), Hex(imenu->flags));
	}

	// ------------------------------------------------------------------------------------------- stage d: the page
	// Up to PageCollect, everything runs on the main thread (SFSE's task, before each kShow and kUpdate): the reads,
	// the two calls into the game (LookupByID, GetActorValue) and the text. PageWrite and the click handlers run on the
	// menu's.

	bool SameText(std::string_view a_left, std::string_view a_right)   // ASCII, either case
	{
		return a_left.size() == a_right.size() &&
		       std::equal(a_left.begin(), a_left.end(), a_right.begin(), [](char a_l, char a_r) {
				   return std::toupper(static_cast<unsigned char>(a_l)) == std::toupper(static_cast<unsigned char>(a_r));
			   });
	}

	// a line as the page's font draws it: upper case, a character the font lacks as "?", at most kPageColumns
	std::string PageText(std::string_view a_text)
	{
		std::string out;
		for (const char c : a_text.substr(0, kPageColumns)) {
			const auto up = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
			out += kPageChars.find(up) != std::string_view::npos ? up : '?';
		}
		return out;
	}

	// a page value that could not be read: "?", and its reason logged once per kind
	std::string Unknown(std::string_view a_what, const std::string& a_why)
	{
		static std::set<std::string, std::less<>> noted;
		if (noted.emplace(a_what).second) {
			REX::INFO("step=page_unknown what={} {}", a_what, a_why);
		}
		return "?";
	}

	// the characters of a BSStringPool entry (libxse BSStringPool::Entry: 0x18 bytes, then the characters; an external
	// entry, flag 0x02 at +0x14, points on at +0x08; the last one's length is at +0x08). An entry of 0 is "". False if
	// a read faults or the chain is longer than four
	bool ReadPoolString(std::uintptr_t a_entry, std::string& a_out)
	{
		a_out.clear();
		for (int hop = 0; a_entry; ++hop) {
			std::uint8_t flags = 0;
			if (hop == 4 || !Peek(a_entry + 0x14, flags)) {
				return false;
			}
			if (!(flags & 0x02)) {
				break;
			}
			if (!Peek(a_entry + 0x08, a_entry)) {
				return false;
			}
		}
		if (!a_entry) {
			return true;
		}
		std::uint32_t          length = 0;
		std::array<char, 128>  text{};
		if (!Peek(a_entry + 0x08, length)) {
			return false;
		}
		const auto n = std::min<std::size_t>(length, text.size());
		if (n && !Peek(a_entry + 0x18, text.data(), n)) {
			return false;
		}
		a_out.assign(text.data(), std::find(text.data(), text.data() + n, '\0'));
		return true;
	}

	static_assert(sizeof(RE::BSFixedString) == sizeof(std::uintptr_t));   // the pool entry pointer alone

	// the string reader on a string of ours before any of the game's: our menu name, as the engine's pool holds it
	bool CheckStrings()
	{
		std::string read;
		const auto  entry = *reinterpret_cast<const std::uintptr_t*>(&MenuName());
		if (!ReadPoolString(entry, read) || !SameText(read, kMenuName)) {
			return Refuse("page", std::format("what=strings entry={} read=\"{}\" (no names, no form lists)", Hex(entry),
				PageText(read)));
		}
		REX::INFO("step=page_strings self_test=ok read=\"{}\"", read);
		return true;
	}

	// the object is a complete a_tail (".?AV" or ".?AU" + tail) by its RTTI
	bool IsType(std::uintptr_t a_object, std::string_view a_tail, ObjectType& a_type)
	{
		return a_object && TypeOf(a_object, a_type) && NameIs(a_type.name, a_tail) && a_type.offset == 0;
	}

	// the offset of the base class a_tail inside the complete type, from its RTTI class hierarchy descriptor (+0x08
	// the count, +0x0C the base class array; each base class descriptor: +0x00 its type descriptor, +0x08 mdisp, +0x0C
	// pdisp). None if the base is absent, virtual (pdisp not -1) or listed more than once
	std::optional<std::uint32_t> BaseOffset(const ObjectType& a_type, std::string_view a_tail)
	{
		const auto hierarchy = a_type.hierarchy;
		if (!InImage(hierarchy, 0x10)) {
			return std::nullopt;
		}
		const auto count = *reinterpret_cast<const std::uint32_t*>(hierarchy + 0x08);
		const auto array = g_base + *reinterpret_cast<const std::uint32_t*>(hierarchy + 0x0C);
		if (count == 0 || count > 512 || !InImage(array, 4ull * count)) {
			return std::nullopt;
		}
		std::optional<std::uint32_t> found;
		std::size_t                  matches = 0;
		for (std::uint32_t i = 0; i < count; ++i) {
			const auto base = g_base + reinterpret_cast<const std::uint32_t*>(array)[i];
			if (!InImage(base, 0x1C)) {
				return std::nullopt;
			}
			if (!NameIs(TypeNameAt(g_base + *reinterpret_cast<const std::uint32_t*>(base)), a_tail)) {
				continue;
			}
			const auto mdisp = *reinterpret_cast<const std::int32_t*>(base + 0x08);
			const auto pdisp = *reinterpret_cast<const std::int32_t*>(base + 0x0C);
			if (pdisp != -1 || mdisp < 0) {
				return std::nullopt;
			}
			found = static_cast<std::uint32_t>(mdisp);
			++matches;
		}
		return matches == 1 ? found : std::nullopt;
	}

	// the subobject at a_offset is a base of the object's complete type: its vtable's locator names that same
	// complete type at that offset
	bool CheckSubobject(std::uintptr_t a_object, const ObjectType& a_type, std::uint32_t a_offset)
	{
		ObjectType sub;
		return TypeOf(a_object + a_offset, sub) && sub.descriptor == a_type.descriptor && sub.offset == a_offset;
	}

	// the target of an adjustor thunk, rcx moved down by a_adjust (sub rcx, imm; add rcx, -imm; or lea rcx,
	// [rcx-imm]) then jmp rel32: what MSVC puts in a secondary base's vtable for a virtual the complete class
	// overrides. 0 if the code is not one
	std::uintptr_t ThunkTarget(std::uintptr_t a_code, std::uint32_t a_adjust)
	{
		if (!InImage(a_code, 12)) {
			return 0;
		}
		const auto* code = reinterpret_cast<const std::uint8_t*>(a_code);
		const auto  imm8 = static_cast<std::int8_t>(code[3]);
		std::int32_t imm32;
		std::memcpy(&imm32, code + 3, sizeof imm32);
		const auto  adjust = static_cast<std::int64_t>(a_adjust);
		std::size_t at = 0;
		if (code[0] != 0x48) {
			return 0;
		} else if ((code[1] == 0x83 && code[2] == 0xE9 && imm8 == adjust) || (code[1] == 0x83 && code[2] == 0xC1 && imm8 == -adjust) ||
				   (code[1] == 0x8D && code[2] == 0x49 && imm8 == -adjust)) {
			at = 4;
		} else if ((code[1] == 0x81 && code[2] == 0xE9 && imm32 == adjust) || (code[1] == 0x81 && code[2] == 0xC1 && imm32 == -adjust) ||
				   (code[1] == 0x8D && code[2] == 0x89 && imm32 == -adjust)) {
			at = 7;
		} else {
			return 0;
		}
		if (code[at] != 0xE9) {
			return 0;
		}
		std::int32_t rel;
		std::memcpy(&rel, code + at + 1, sizeof rel);
		return a_code + at + 5 + static_cast<std::intptr_t>(rel);
	}

	struct PageForms
	{
		bool           scanned = false;
		bool           strings = false;    // ReadPoolString read our menu name back
		bool           avifs = false;      // the actor values were looked up: a name not found is not installed
		bool           globals = false;    // the globals were looked up
		std::uintptr_t health = 0;         // ActorValueInfo forms
		std::uintptr_t carryWeight = 0;
		std::uintptr_t experience = 0;
		std::uintptr_t rads = 0;
		std::uintptr_t gameHour = 0;       // TESGlobal forms
		std::uintptr_t gameDaysPassed = 0;
		std::size_t    globalValueAt = 0;  // the TESGlobal value's offset, once FindGlobalValue found it (0: not yet)
		bool           globalBytes = false;  // the globals' bytes were logged
		std::uint32_t  ownerOffset = 0;    // ActorValueOwner inside PlayerCharacter
		std::uintptr_t ownerVtable = 0;
		std::uintptr_t getActorValue = 0;  // its checked GetActorValue slot
	};
	PageForms g_forms;   // main thread only

	struct Want
	{
		std::string_view editorId;
		std::uintptr_t*  form;
	};

	// the data handler (its id is SFSE's own address, CheckPageIds), a TESDataHandler by its RTTI; only its form-list
	// memory is logged
	std::uintptr_t DataHandler()
	{
		const auto handler = Singleton(kDataHandlerSingleton);
		ObjectType type;
		if (!IsType(handler, "TESDataHandler@@", type)) {
			Refuse("object", std::format("name=TESDataHandler object={} type={} offset={} (the page's form lists stay unread)",
				Hex(handler), type.name.empty() ? "unreadable" : type.name, Hex(type.offset)));
			return 0;
		}
		REX::INFO("step=object name=TESDataHandler object={} type={}", Hex(handler), type.name);
		return handler;
	}

	// the data handler's form lists as raw memory, once: at 5a4e6016 the size read at +0x70 + type x 0x18 + 0x08 was 0
	// for AVIF and GLOB, so the next run logs the three qwords of every entry that is not all zero (the first 48) and
	// of those two types, to settle the layout. Reads only, guarded
	void LogFormArrays(std::uintptr_t a_handler)
	{
		std::array<std::uint64_t, 3> avif{};
		std::array<std::uint64_t, 3> glob{};
		std::string                  nonzero;
		std::size_t                  count = 0;
		for (std::size_t i = 0; i < kFormArrayEntries; ++i) {
			std::array<std::uint64_t, 3> q{};
			if (!Peek(a_handler + kFormArraysAt + i * kFormArrayBytes, q)) {
				nonzero += std::format(" {:#x}:fault", i);
				break;
			}
			if (i == kAvifType) {
				avif = q;
			}
			if (i == kGlobType) {
				glob = q;
			}
			if ((q[0] || q[1] || q[2]) && count++ < 48) {
				nonzero += std::format(" {:#x}:{:x}/{:x}/{:x}", i, q[0], q[1], q[2]);
			}
		}
		REX::INFO("step=page_form_arrays avif={:x}/{:x}/{:x} glob={:x}/{:x}/{:x} nonzero_count={}{}", avif[0], avif[1],
			avif[2], glob[0], glob[1], glob[2], count, nonzero);
	}

	using LookupById_t = void* (*)(std::uint32_t);

	// a form by its form id, through the engine's own lookup (libxse TESForm::LookupByID and SFSE 0.2.21
	// GetFormByNumericID: the same address, CheckPageIds, and the same TESForm* (u32) declaration); main thread only
	std::uintptr_t FormById(std::uint32_t a_formId)
	{
		return reinterpret_cast<std::uintptr_t>(reinterpret_cast<LookupById_t>(Address(kLookupById))(a_formId));
	}

	// the editor ID of a form of type a_type by its RTTI (a BSFixedString at a_editorIdAt), or "" if the form is not
	// that type or its name does not read
	std::string EditorIdOf(std::uintptr_t a_form, std::string_view a_type, std::size_t a_editorIdAt)
	{
		ObjectType     type;
		std::uintptr_t entry = 0;
		std::string    id;
		if (!IsType(a_form, a_type, type) || !Peek(a_form + a_editorIdAt, entry) || !ReadPoolString(entry, id)) {
			return {};
		}
		return id;
	}

	// a Want gets the form if its editor ID is the Want's name and it has none yet
	template <std::size_t N>
	void Match(std::array<Want, N>& a_want, std::uintptr_t a_form, std::string_view a_editorId)
	{
		for (auto& want : a_want) {
			if (!*want.form && SameText(a_editorId, want.editorId)) {
				*want.form = a_form;
			}
		}
	}

	// a form by its fixed form id, accepted by its RTTI type alone (at 3eb30d71 the editor-ID check passed Health 0x2D4
	// and not 0x2C9, 0x2DC, 0x38 or 0x39): what the lookup gave is logged in full, its type name, the four bytes at
	// +0x2C (the form type byte among them) and the editor ID as read
	std::string AcceptById(std::uint32_t a_id, std::string_view a_name, std::string_view a_type, std::size_t a_editorIdAt,
		std::uintptr_t& a_out)
	{
		const auto     form = FormById(a_id);
		ObjectType     type;
		std::uintptr_t entry = 0;
		std::string    name;
		std::uint32_t  bytes = 0;
		if (IsType(form, a_type, type)) {
			a_out = form;
			if (Peek(form + a_editorIdAt, entry)) {
				ReadPoolString(entry, name);
			}
		}
		if (form) {
			Peek(form + 0x2C, bytes);
		}
		return std::format("{}:{:x}:form={}:type={}:bytes2c={:08x}:name={}:{}", a_name, a_id, form ? 1 : 0,
			type.name.empty() ? "unreadable" : type.name, bytes, name.empty() ? "-" : name, a_out ? "used" : "refused");
	}

	// the page's forms by form id: the globals and actor values by their fixed ids and RTTI type (AcceptById); every
	// ActorValueInfo among Starfield.esm's ids 0x001 to 0xFFF listed with its editor ID as read, once; FO4SF_Rads by its
	// editor ID at local id 0x800 of each full plugin (01 to FD) and each light plugin (FE000 to FEFFF)
	void FindForms()
	{
		std::string known = AcceptById(kGameHourId, "GameHour", "TESGlobal@@", kGlobalEditorIdAt, g_forms.gameHour);
		known += " " + AcceptById(kGameDaysPassedId, "GameDaysPassed", "TESGlobal@@", kGlobalEditorIdAt, g_forms.gameDaysPassed);
		known += " " + AcceptById(kHealthId, "Health", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.health);
		known += " " + AcceptById(kCarryWeightId, "CarryWeight", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.carryWeight);
		known += " " + AcceptById(kExperienceId, "Experience", "ActorValueInfo@@", kAvifEditorIdAt, g_forms.experience);
		g_forms.globals = true;
		std::uint32_t typed = 0;
		std::string   avifs;
		for (std::uint32_t id = 1; id < kCoreFormIds; ++id) {
			const auto form = FormById(id);
			ObjectType type;
			if (!form || !IsType(form, "ActorValueInfo@@", type)) {
				continue;
			}
			++typed;
			const auto name = EditorIdOf(form, "ActorValueInfo@@", kAvifEditorIdAt);
			if (avifs.size() < 2000) {
				avifs += std::format("{}{:x}={}", avifs.empty() ? "" : ",", id, name.empty() ? "-" : name);
			}
		}
		std::array<Want, 1> rads{ { { "FO4SF_Rads", &g_forms.rads } } };
		std::uint32_t       radsId = 0;
		for (std::uint32_t i = 0; i < 0xFD + 0x1000 && !g_forms.rads; ++i) {
			const auto id = i < 0xFD ? ((i + 1) << 24) | kRadsLocalId : 0xFE000000u | ((i - 0xFD) << 12) | kRadsLocalId;
			const auto form = FormById(id);
			if (form) {
				Match(rads, form, EditorIdOf(form, "ActorValueInfo@@", kAvifEditorIdAt));
				radsId = g_forms.rads ? id : 0;
			}
		}
		g_forms.avifs = typed > 0;
		REX::INFO("step=page_forms lookup=by_form_id known={} avif_typed={} rads={} avif_ids={}", known, typed,
			g_forms.rads ? std::format("{:08X}", radsId) : "not_installed", avifs.empty() ? "none" : avifs);
	}

	// the player's ActorValueOwner and its GetActorValue slot: the base's offset from PlayerCharacter's RTTI
	// hierarchy, its vtable's locator naming PlayerCharacter at that offset, and slot 0x00 the adjustor thunk to the
	// player's own slot 0x00, its destructor. Then GetActorValue is slot 0x01, libxse's declaration (SFSE 0.2.21
	// declares no destructor and would put it at 0x00). Anything else: no actor values on the page
	bool CheckActorValues()
	{
		ObjectType type;
		const auto player = Singleton(kPlayerSingleton);
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk) || !TypeOf(player, type)) {
			return false;
		}
		const auto     at = BaseOffset(type, "ActorValueOwner@@");
		std::uintptr_t primary = 0;
		std::uintptr_t owner = 0;
		if (!at || !CheckSubobject(player, type, *at) || !Peek(player, primary) || !Peek(player + *at, owner) ||
			!InImage(primary, 8) || !InImage(owner, 2 * 8)) {
			return Refuse("page", std::format("what=actor_value_owner offset={} (no actor values)", at ? Hex(*at) : "none"));
		}
		const auto* slots = reinterpret_cast<const std::uintptr_t*>(owner);
		const auto  destructor = *reinterpret_cast<const std::uintptr_t*>(primary);
		const auto  target0 = ThunkTarget(slots[0], *at);
		const auto  target1 = ThunkTarget(slots[1], *at);
		const auto  rva = [](std::uintptr_t a_addr) { return InImage(a_addr, 1) ? Hex(a_addr - g_base) : Hex(a_addr); };
		if (target0 != destructor || !InImage(slots[1], 1)) {
			return Refuse("page", std::format("what=get_actor_value offset={} slot0={} target0={} slot1={} target1={} "
				"destructor={} (no actor values)", Hex(*at), rva(slots[0]), rva(target0), rva(slots[1]), rva(target1),
				rva(destructor)));
		}
		g_forms.ownerOffset = *at;
		g_forms.ownerVtable = owner;
		g_forms.getActorValue = slots[1];
		REX::INFO("step=page_actor_values owner_offset={} destructor_slot=0x00 get_actor_value_slot=0x01 slot={} target={}",
			Hex(*at), rva(slots[1]), rva(target1));
		return true;
	}

	// once a player exists: the string reader, the actor-value slot, the form-list layout and the forms, each logged once
	void PageScan()
	{
		if (g_forms.scanned || !Singleton(kPlayerSingleton)) {
			return;
		}
		g_forms.scanned = true;
		g_forms.strings = CheckStrings();
		CheckActorValues();
		if (const auto handler = DataHandler()) {
			LogFormArrays(handler);
		}
		if (g_forms.strings) {
			FindForms();
		}
	}

	using GetActorValue_t = float (*)(void*, const void*);

	// the player's value of an actor value, as a whole number: the engine's GetActorValue (the slot CheckActorValues
	// checked, called only while the player's ActorValueOwner vtable is still the checked one), or "?"
	std::string ActorValueText(std::string_view a_what, std::uintptr_t a_info)
	{
		if (!a_info) {
			return Unknown(a_what, std::format("reason={}", g_forms.avifs ? "no_such_actor_value" : "actor_values_unread"));
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t vtable = 0;
		if (!g_forms.getActorValue || !player || !Peek(player + g_forms.ownerOffset, vtable) || vtable != g_forms.ownerVtable) {
			return Unknown(a_what, "reason=no_get_actor_value");
		}
		const auto value = reinterpret_cast<GetActorValue_t>(g_forms.getActorValue)(
			reinterpret_cast<void*>(player + g_forms.ownerOffset), reinterpret_cast<const void*>(a_info));
		return std::isfinite(value) ? std::format("{:.0f}", value) : Unknown(a_what, "reason=not_finite");
	}

	// the player's level: the base TESNPC's TESActorBaseData (its offset from the RTTI hierarchy), ACTOR_BASE_DATA::level
	std::string LevelText()
	{
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t base = 0;
		ObjectType     type;
		std::uint16_t  level = 0;
		if (g_playerOk != 1 || !Peek(player + kBaseObjectAt, base) || !IsType(base, "TESNPC@@", type)) {
			return Unknown("level", std::format("reason=base base={} type={}", Hex(base), type.name.empty() ? "unreadable" : type.name));
		}
		const auto at = BaseOffset(type, "TESActorBaseData@@");
		if (!at || !CheckSubobject(base, type, *at) || !Peek(base + *at + kLevelAt, level)) {
			return Unknown("level", std::format("reason=actor_base_data offset={}", at ? Hex(*at) : "none"));
		}
		return std::to_string(level);
	}

	// a form's name, read through its TESFullName base (offset from the RTTI hierarchy, checked like the player's), and
	// its form id: "NAME (0001ABCD)", "NO NAME (...)" when it has none
	std::string NameText(std::string_view a_what, std::uintptr_t a_form, const ObjectType& a_type)
	{
		const auto     at = BaseOffset(a_type, "TESFullName@@");
		std::uintptr_t entry = 0;
		std::uint32_t  formId = 0;
		std::string    name;
		Peek(a_form + kFormIdAt, formId);
		if (!at || !CheckSubobject(a_form, a_type, *at) || !Peek(a_form + *at + kFullNameAt, entry) || !ReadPoolString(entry, name)) {
			return std::format("{} ({:08X})", Unknown(a_what, std::format("reason=full_name offset={}", at ? Hex(*at) : "none")), formId);
		}
		return std::format("{} ({:08X})", name.empty() ? "NO NAME" : name, formId);
	}

	// the player's parent cell and its worldspace ("NONE (INTERIOR)" when it has none)
	std::pair<std::string, std::string> PlaceText()
	{
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t cell = 0;
		std::uintptr_t world = 0;
		ObjectType     cellType;
		ObjectType     worldType;
		if (g_playerOk != 1 || !Peek(player + kParentCellAt, cell) || !IsType(cell, "TESObjectCELL@@", cellType)) {
			return { Unknown("cell", std::format("reason=cell cell={} type={}", Hex(cell),
						 cellType.name.empty() ? "unreadable" : cellType.name)),
				"?" };
		}
		auto cellText = NameText("cell_name", cell, cellType);
		if (!Peek(cell + kCellWorldAt, world)) {
			return { cellText, Unknown("world", "reason=fault") };
		}
		if (!world) {
			return { cellText, "NONE (INTERIOR)" };
		}
		if (!IsType(world, "TESWorldSpace@@", worldType)) {
			return { cellText, Unknown("world", std::format("reason=type world={} type={}", Hex(world),
								   worldType.name.empty() ? "unreadable" : worldType.name)) };
		}
		return { cellText, NameText("world_name", world, worldType) };
	}

	// GameHour and GameDaysPassed read as floats at one offset: both in range (an hour in [0, 24), a day count above 0
	// and below kMaxDays) and the hour within kGlobalMinutes of the day count's fraction, else false
	bool ReadTime(std::size_t a_at, float& a_hour, float& a_days)
	{
		if (!a_at || !g_forms.gameHour || !g_forms.gameDaysPassed || !Peek(g_forms.gameHour + a_at, a_hour) ||
			!Peek(g_forms.gameDaysPassed + a_at, a_days) || !std::isfinite(a_hour) || !std::isfinite(a_days) ||
			a_hour < 0.0f || a_hour >= 24.0f || a_days <= 0.0f || a_days >= kMaxDays) {
			return false;
		}
		const auto apart = std::fabs(std::fmod(a_days, 1.0f) * 24.0f - a_hour);
		return std::min(apart, 24.0f - apart) * 60.0f <= kGlobalMinutes;
	}

	// the kGlobalBytes (40) bytes of a TESGlobal from kGlobalBytesAt, as hex and as ten floats
	std::string GlobalBytes(std::uintptr_t a_form)
	{
		std::array<std::uint8_t, kGlobalBytes> bytes{};
		if (!a_form || !Peek(a_form + kGlobalBytesAt, bytes.data(), bytes.size())) {
			return "unreadable";
		}
		std::string hex;
		std::string floats;
		for (std::size_t i = 0; i < bytes.size(); i += 4) {
			float value = 0.0f;
			std::memcpy(&value, bytes.data() + i, sizeof(value));
			hex += std::format("{}{:02x}{:02x}{:02x}{:02x}", i ? "," : "", bytes[i], bytes[i + 1], bytes[i + 2],
				bytes[i + 3]);
			floats += std::format("{}{:.4f}", i ? "," : "", value);
		}
		return std::format("hex={} floats={}", hex, floats);
	}

	// which slot of a TESGlobal holds the value, given a_accepts(offset) (ReadTime at that offset): kGlobalValueAt when it
	// passes, else the first other slot from kGlobalSearchFrom to the end of the object that does; never kFormIdAt (the
	// form ids 0x38 and 0x39 read as floats of about zero, and passed). 0 when none does
	template <class Accepts>
	std::size_t ChooseGlobalSlot(Accepts a_accepts)
	{
		if (kGlobalValueAt != kFormIdAt && a_accepts(kGlobalValueAt)) {
			return kGlobalValueAt;
		}
		for (std::size_t at = kGlobalSearchFrom; at + sizeof(float) <= kGlobalObjectBytes; at += 4) {
			if (at != kFormIdAt && at != kGlobalValueAt && a_accepts(at)) {
				return at;
			}
		}
		return 0;
	}

	// the TESGlobal value's offset, chosen by ChooseGlobalSlot over ReadTime on both globals. Tried at each collect until
	// found; both globals' bytes are logged at the first try
	void FindGlobalValue()
	{
		if (g_forms.globalValueAt || !g_forms.gameHour || !g_forms.gameDaysPassed) {
			return;
		}
		if (!g_forms.globalBytes) {
			g_forms.globalBytes = true;
			REX::INFO("step=page_globals from={} game_hour {} game_days_passed {}", Hex(kGlobalBytesAt),
				GlobalBytes(g_forms.gameHour), GlobalBytes(g_forms.gameDaysPassed));
		}
		float hour = 0.0f;
		float days = 0.0f;
		const auto at = ChooseGlobalSlot([&](std::size_t a_at) { return ReadTime(a_at, hour, days); });
		if (at) {
			ReadTime(at, hour, days);   // the chosen slot's values, for the log (the search leaves the last try's)
			g_forms.globalValueAt = at;
			REX::INFO("step=page_globals value_at={} game_hour={:.4f} game_days_passed={:.4f}", Hex(at), hour, days);
		}
	}

	// the game time from the GameHour and GameDaysPassed globals, at the offset FindGlobalValue found: "08:23   DAY 1"
	std::string TimeText()
	{
		float hour = 0.0f;
		float days = 0.0f;
		if (!ReadTime(g_forms.globalValueAt, hour, days)) {
			const auto reason = !g_forms.globals        ? "globals_unread" :
			                    !g_forms.globalValueAt ? "no_value_offset" :
			                                             "out_of_range";
			return Unknown("time", std::format("reason={}", reason));
		}
		const auto minutes = static_cast<int>(hour * 60.0f);
		return std::format("{:02}:{:02}   DAY {}", minutes / 60 % 24, minutes % 60, static_cast<long long>(days) + 1);
	}

	// both tabs' text, on the main thread before each kShow and kUpdate; the menu's thread copies one tab of it
	void PageCollect()
	{
		PageScan();
		FindGlobalValue();
		const auto [cell, world] = PlaceText();
		const auto rads = g_forms.rads ? ActorValueText("rads", g_forms.rads) :
		                  g_forms.avifs ? std::string("NOT INSTALLED") :
		                                  Unknown("rads", "reason=actor_values_unread");
		std::array<float, 3> xyz{};
		float                hour = 0.0f;
		float                days = 0.0f;
		const bool           position = ReadPosition(xyz) && std::isfinite(xyz[0]) && std::isfinite(xyz[1]) && std::isfinite(xyz[2]);
		const bool           haveDays = ReadTime(g_forms.globalValueAt, hour, days);
		const auto           shows = g_shows.load();
		std::array<std::array<std::string, kPageLines + 1>, 2> text{ {
			{ "TAB 1 OF 2: STATUS",
				std::format("HEALTH {}", ActorValueText("health", g_forms.health)),
				std::format("LEVEL {}   XP {}", LevelText(), ActorValueText("experience", g_forms.experience)),
				std::format("CARRY WEIGHT MAX {}", ActorValueText("carry_weight", g_forms.carryWeight)),
				std::format("RADS {}", rads),
				std::format("CELL {}", cell),
				std::format("WORLD {}", world),
				std::format("TIME {}", TimeText()) },
			{ "TAB 2 OF 2: DATA",
				position ? std::format("POSITION X {:.1f} Y {:.1f} Z {:.1f}", xyz[0], xyz[1], xyz[2]) : "POSITION ?",
				std::format("UPDATES {}   (TWO A SECOND)", g_updates.load()),
				std::format("NEXT TAB CLICKS {}   CLOSE CLICKS {}", g_tabClicks.load(), g_closeClicks.load()),
				std::format("OPENS {}   FLAGS {}", shows, Hex(FlagSet(shows ? shows : 1))),
				std::format("GAME PAUSED {}", ReadPaused()),
				std::format("MENUS {}", ReadMenus()),
				haveDays ? std::format("DAYS PASSED {:.4f}", days) : "DAYS PASSED ?" },
		} };
		for (auto& tab : text) {
			for (auto& line : tab) {
				line = PageText(line);
			}
		}
		std::scoped_lock lock(g_pageLock);
		g_pageText = std::move(text);
	}

	// the two buttons' click handlers, called by Scaleform on the menu's thread (static, never released, as the
	// channel's): they only count and raise a flag; the key thread acts on it through the main thread
	class TabHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto n = ++g_tabClicks;
			const auto tab = (g_tab.fetch_add(1) + 1) % 2;
			g_refreshNow = true;
			REX::INFO("step=click button=tab n={} args={} tab={}", n, a_params.argCount, tab);
		}
	};
	TabHandler g_tabHandler;

	class CloseHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto n = ++g_closeClicks;
			g_closeNow = true;
			REX::INFO("step=click button=close n={} args={}", n, a_params.argCount);
		}
	};
	CloseHandler g_closeHandler;

	// once per movie, at kShow: our two functions as the buttons' "click" listeners
	void PageListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || g_listenedMovie == movie) {
			return;
		}
		g_listenedMovie = movie;
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		const std::array<std::pair<const char*, RE::Scaleform::GFx::FunctionHandler*>, 2> buttons{ {
			{ kTabButtonName, &g_tabHandler }, { kCloseButtonName, &g_closeHandler } } };
		for (const auto& [name, handler] : buttons) {
			RE::Scaleform::GFx::Value button;
			RE::Scaleform::GFx::Value function;
			const bool                gotButton = gotRoot && ChildOf(top, name, button);
			bool                      added = false;
			if (gotButton) {
				root->CreateFunction(&function, handler);
				if (!function.IsUndefined()) {
					std::array<RE::Scaleform::GFx::Value, 2> args;
					args[0] = "click";
					args[1] = function;
					added = button.Invoke("addEventListener", nullptr, args.data(), args.size());
				}
			}
			REX::INFO("step=listen name={} root={} button={} function_type={} added={} event=click", name, gotRoot ? 1 : 0,
				gotButton ? 1 : 0, TypeCode(function), added ? 1 : 0);
		}
	}

	// at kShow and every kUpdate, on the menu's thread: the shown tab's text into the tab line and the seven lines,
	// each read back. Logged for n = 1 to 20, then every 20th, and on the first 20 that do not read back
	void PageWrite(const void* a_menu, std::uint32_t a_update)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		static std::atomic<std::uint32_t>        mismatches{ 0 };
		const auto                               tab = g_tab.load() % 2;
		std::array<std::string, kPageLines + 1> text;
		{
			std::scoped_lock lock(g_pageLock);
			text = g_pageText[tab];
		}
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		std::size_t               found = 0;
		std::size_t               set = 0;
		std::size_t               match = 0;
		for (std::size_t i = 0; gotRoot && i < text.size(); ++i) {
			const auto                name = i == 0 ? std::string(kTabFieldName) : std::format("{}{}", kLineFieldName, i - 1);
			RE::Scaleform::GFx::Value field;
			RE::Scaleform::GFx::Value back;
			if (!ChildOf(top, name.c_str(), field)) {
				continue;
			}
			++found;
			set += field.SetMember("text", RE::Scaleform::GFx::Value(text[i].c_str())) ? 1 : 0;
			match += field.GetMember("text", &back) && back.IsString() && text[i] == back.GetString() ? 1 : 0;
		}
		const auto n = ++g_pageWrites;
		if (n <= 20 || n % 20 == 0 || (match != text.size() && mismatches++ < 20)) {
			std::string all;
			for (const auto& line : text) {
				all += std::format("{}{}", all.empty() ? "" : " | ", line);
			}
			REX::INFO("step=page n={} update={} tab={} root={} fields={}/{} set={} match={} text=\"{}\"", n, a_update, tab,
				gotRoot ? 1 : 0, found, text.size(), set, match, all);
		}
	}

	// ------------------------------------------------------------------------------------------- stage e: the kit
	// FAL-301. The pages are read once at load (ReadKit) and never change after. KitCollect builds the shown page's
	// screen on the main thread (stage d's reads and its two calls, nothing else); KitWrite writes it on the menu's
	// thread. The state (main tab, each tab's sub-tab, each page's selection and first row on screen) moves on keys (the
	// key thread) and clicks (the menu's thread), always under g_pageLock, and each move asks for an update at once.

	struct KitCell   // a Row= or Footer= line
	{
		std::string label;
		std::string value;   // a value provider: one of kKitValues, or av:<hex>
	};

	struct KitPage
	{
		std::string              tab;
		std::string              sub;
		std::vector<KitCell>     rows;
		std::string              list;     // a list provider, or ""
		std::vector<std::string> notice;
		std::vector<KitCell>     footer;
		std::string              hint;
		std::size_t              line = 0;
	};

	struct KitConfig
	{
		std::string                                    title = "FO4SF PIP-BOY";
		std::string                                    header;   // a value provider, or ""
		std::string                                    hints;
		std::string                                    missionFile;   // Mission=: our mission's plugin file, or ""
		std::uint32_t                                  missionId = 0;   // and its form's local id in that file
		std::vector<KitPage>                           pages;
		std::vector<std::string>                       tabs;     // in the order of their first page
		std::array<std::vector<std::size_t>, kKitTabs> subs;     // each tab's pages, in order
	};
	KitConfig g_kit;   // ReadKit, at load; read only after

	struct KitState
	{
		std::size_t                       tab = 0;
		std::array<std::size_t, kKitTabs> sub{};      // the sub-tab each main tab shows, kept while another tab is shown
		std::vector<std::size_t>          selected;   // per page: the selected row
		std::vector<std::size_t>          top;        // per page: the first row on screen
		std::vector<std::size_t>          count;      // per page: its selectable rows, as last collected
		std::uint32_t                     keys = 0;   // moves by key and by click (the kit_test list shows them)
		std::uint32_t                     clicks = 0;
	};

	struct KitScreen
	{
		std::size_t                          page = 0;
		std::string                          title;
		std::string                          header;
		std::string                          hints;
		std::array<std::string, kKitTabs>    tabs;
		std::size_t                          tab = 0;
		std::array<std::string, kKitSubs>    subs;
		std::size_t                          sub = 0;
		std::array<std::string, kKitRows>    names;
		std::array<std::string, kKitRows>    values;
		std::optional<std::size_t>           bar;      // the selected row's place on screen, none on a notice
		std::array<std::string, kKitRows>    infoLabels;
		std::array<std::string, kKitRows>    infoValues;
		std::array<std::string, kKitFooter>  footer;
		bool                                 moreUp = false;
		bool                                 moreDown = false;
	};

	struct KitRow
	{
		std::string                                      name;
		std::string                                      value;
		std::vector<std::pair<std::string, std::string>> info;   // the value rows beside the list while it is selected
	};

	enum class KitMove : std::size_t { kUp, kDown, kPrevSub, kNextSub, kPrevTab, kNextTab, kTab, kSub, kRow };
	constexpr std::array<std::string_view, 9> kKitMoveNames{ "up", "down", "prev_sub", "next_sub", "prev_tab", "next_tab",
		"tab", "sub", "row" };

	struct KitKey   // INI KitUp ... KitNextTab
	{
		KitMove                      move;
		const wchar_t*               ini;
		const wchar_t*               keys;   // the default
		std::array<std::uint32_t, 3> vk{};
		std::size_t                  count = 0;
	};
	std::array<KitKey, 6> g_kitKeys{ { { KitMove::kUp, L"KitUp", L"0x26,0x57" }, { KitMove::kDown, L"KitDown", L"0x28,0x53" },
		{ KitMove::kPrevSub, L"KitPrevSub", L"0x25,0x41" }, { KitMove::kNextSub, L"KitNextSub", L"0x27,0x44" },
		{ KitMove::kPrevTab, L"KitPrevTab", L"0x51" }, { KitMove::kNextTab, L"KitNextTab", L"0x45" } } };

	KitState                                     g_kitState;        // under g_pageLock
	KitScreen                                    g_kitScreen;       // under g_pageLock: built on the main thread
	bool                                         g_kitCollected = false;   // under g_pageLock
	std::vector<bool>                            g_kitPageLogged;   // main thread only
	std::unordered_map<std::uint32_t, std::uintptr_t> g_kitActorValues;   // main thread only: av:<id>'s form, once
	std::unordered_map<std::string, std::string> g_kitTexts;        // menu's thread only: each field as last set and read
	std::unordered_map<std::string, bool>        g_kitShown;        // menu's thread only: each object's visible, likewise
	std::atomic<std::uint32_t>                   g_kitWrites{ 0 };
	std::atomic<std::uint32_t>                   g_kitClicks{ 0 };

	std::string_view KitTrim(std::string_view a_text)
	{
		const auto first = a_text.find_first_not_of(" \t\r");
		if (first == std::string_view::npos) {
			return {};
		}
		return a_text.substr(first, a_text.find_last_not_of(" \t\r") - first + 1);
	}

	// ReadKit's label check, parse_kit's _fits: 1 to a_columns characters, each in the kit's font (upper case)
	bool KitLabel(std::string_view a_text, std::size_t a_columns)
	{
		return !a_text.empty() && a_text.size() <= a_columns &&
		       std::ranges::all_of(a_text, [](char a_c) { return kKitChars.find(a_c) != std::string_view::npos; });
	}

	// parse_kit's check_value: a name of kKitValues, or av:<1 to 8 hex digits, not zero>
	bool KitValueName(std::string_view a_spec)
	{
		if (std::ranges::find(kKitValues, a_spec) != kKitValues.end()) {
			return true;
		}
		if (!a_spec.starts_with(kKitActorValue)) {
			return false;
		}
		const auto hex = a_spec.substr(kKitActorValue.size());
		return !hex.empty() && hex.size() <= 8 &&
		       std::ranges::all_of(hex, [](char a_c) { return std::isxdigit(static_cast<unsigned char>(a_c)) != 0; }) &&
		       std::strtoul(std::string(hex).c_str(), nullptr, 16) != 0;
	}

	// <label>|<value>, parse_kit's _cell: exactly one '|', the label in a_columns, the value a value provider
	bool KitCellOf(std::string_view a_text, std::size_t a_columns, KitCell& a_out)
	{
		const auto bar = a_text.find('|');
		if (bar == std::string_view::npos || a_text.find('|', bar + 1) != std::string_view::npos) {
			return false;
		}
		const auto label = KitTrim(a_text.substr(0, bar));
		const auto value = KitTrim(a_text.substr(bar + 1));
		if (!KitLabel(label, a_columns) || !KitValueName(value)) {
			return false;
		}
		a_out = { std::string(label), std::string(value) };
		return true;
	}

	// parse_kit's check_mission: <plugin file>|<local id, 1 to 6 hex digits, not zero>; the file 1 to 64 characters
	// (letters, digits, space _ - .) ending .esm, .esp or .esl
	bool KitMission(std::string_view a_text)
	{
		const auto bar = a_text.find('|');
		if (bar == std::string_view::npos || a_text.find('|', bar + 1) != std::string_view::npos) {
			return false;
		}
		const auto file = KitTrim(a_text.substr(0, bar));
		const auto hex = KitTrim(a_text.substr(bar + 1));
		const auto lower = [](std::string_view a_s) {
			std::string out(a_s);
			std::ranges::transform(out, out.begin(), [](unsigned char a_c) { return static_cast<char>(std::tolower(a_c)); });
			return out;
		};
		const auto fileChar = [](char a_c) {
			return std::isalnum(static_cast<unsigned char>(a_c)) != 0 || std::string_view(" _-.").find(a_c) != std::string_view::npos;
		};
		const auto ext = file.size() > 4 ? lower(file.substr(file.size() - 4)) : std::string{};
		if (file.size() > 64 || (ext != ".esm" && ext != ".esp" && ext != ".esl") || !std::ranges::all_of(file, fileChar) ||
			hex.empty() || hex.size() > 6 ||
			!std::ranges::all_of(hex, [](char a_c) { return std::isxdigit(static_cast<unsigned char>(a_c)) != 0; })) {
			return false;
		}
		const auto id = static_cast<std::uint32_t>(std::strtoul(std::string(hex).c_str(), nullptr, 16));
		if (!id) {
			return false;
		}
		g_kit.missionFile = file;
		g_kit.missionId = id;
		return true;
	}

	std::string KitSignature()   // make_pipboy_kit.py signature(): the movie's fo4sfKitId
	{
		std::string tabs;
		for (const auto& tab : g_kit.tabs) {
			tabs += std::format("{}{}", tabs.empty() ? "" : ",", tab);
		}
		return std::format("FO4SF KIT {} {} {}", kKitVersion, kKitRows, tabs);
	}

	bool KitRefuse(std::size_t a_line, std::string_view a_why)
	{
		return Refuse("pages", std::format("line={} reason={} (the kit stays off)", a_line, a_why));
	}

	// the [Kit] and [Page <TAB>/<SUB>] sections of the ini, with parse_kit's grammar and checks; other sections are
	// skipped. Any wrong line refuses the whole kit, at load
	bool ReadKit(const std::filesystem::path& a_ini)
	{
		std::ifstream in(a_ini, std::ios::binary);
		if (!in) {
			return KitRefuse(0, "no_ini");
		}
		enum class Section { kOther, kKit, kPage };
		auto        section = Section::kOther;
		std::string raw;
		std::size_t n = 0;
		while (std::getline(in, raw)) {
			++n;
			const auto line = KitTrim(raw);
			if (line.empty() || line[0] == ';' || line[0] == '#') {
				continue;
			}
			if (line[0] == '[') {
				if (line.back() != ']') {
					return KitRefuse(n, "section");
				}
				const auto name = KitTrim(line.substr(1, line.size() - 2));
				section = Section::kOther;
				if (name == "Kit") {
					section = Section::kKit;
				} else if (name.starts_with("Page ")) {
					const auto path = KitTrim(name.substr(5));
					const auto slash = path.find('/');
					if (slash == std::string_view::npos || path.find('/', slash + 1) != std::string_view::npos) {
						return KitRefuse(n, "page_name");
					}
					KitPage page;
					page.tab = KitTrim(path.substr(0, slash));
					page.sub = KitTrim(path.substr(slash + 1));
					page.line = n;
					if (!KitLabel(page.tab, kKitTabColumns) || !KitLabel(page.sub, kKitSubColumns)) {
						return KitRefuse(n, "tab_or_sub_label");
					}
					for (const auto& other : g_kit.pages) {
						if (other.tab == page.tab && other.sub == page.sub) {
							return KitRefuse(n, "page_twice");
						}
					}
					g_kit.pages.push_back(std::move(page));
					section = Section::kPage;
				}
				continue;
			}
			if (section == Section::kOther) {
				continue;
			}
			const auto eq = line.find('=');
			if (eq == std::string_view::npos) {
				return KitRefuse(n, "no_equals");
			}
			const auto key = KitTrim(line.substr(0, eq));
			const auto value = KitTrim(line.substr(eq + 1));
			if (section == Section::kKit) {
				if (key == "Title" && KitLabel(value, kKitTitleColumns)) {
					g_kit.title = value;
				} else if (key == "Header" && KitValueName(value)) {
					g_kit.header = value;
				} else if (key == "Hints" && KitLabel(value, kKitHintColumns)) {
					g_kit.hints = value;
				} else if (key == "Mission" && g_kit.missionFile.empty() && KitMission(value)) {
					// KitMission kept it
				} else {
					return KitRefuse(n, std::format("kit_key key={}", key));
				}
				continue;
			}
			auto&   page = g_kit.pages.back();
			KitCell cell;
			if (key == "Row" && page.rows.size() < kKitMaxPageRows && KitCellOf(value, kKitNameColumns, cell)) {
				page.rows.push_back(std::move(cell));
			} else if (key == "List" && page.list.empty() && std::ranges::find(kKitLists, value) != kKitLists.end()) {
				page.list = value;
			} else if (key == "Notice" && page.notice.size() < kKitRows && KitLabel(value, kKitNameColumns)) {
				page.notice.emplace_back(value);
			} else if (key == "Footer" && page.footer.size() < kKitFooter && KitCellOf(value, kKitFooterLabelColumns, cell)) {
				page.footer.push_back(std::move(cell));
			} else if (key == "Hint" && KitLabel(value, kKitHintColumns)) {
				page.hint = value;
			} else {
				return KitRefuse(n, std::format("page_key key={}", key));
			}
		}
		if (g_kit.pages.empty()) {
			return KitRefuse(n, "no_pages");
		}
		for (std::size_t i = 0; i < g_kit.pages.size(); ++i) {
			const auto& page = g_kit.pages[i];
			const auto  kinds = (page.rows.empty() ? 0 : 1) + (page.list.empty() ? 0 : 1) + (page.notice.empty() ? 0 : 1);
			if (kinds != 1) {
				return KitRefuse(page.line, "page_kind (exactly one of Row, List and Notice)");
			}
			auto tab = std::ranges::find(g_kit.tabs, page.tab);
			if (tab == g_kit.tabs.end()) {
				if (g_kit.tabs.size() == kKitTabs) {
					return KitRefuse(page.line, "tabs");
				}
				g_kit.tabs.push_back(page.tab);
				tab = std::prev(g_kit.tabs.end());
			}
			auto& subs = g_kit.subs[static_cast<std::size_t>(std::distance(g_kit.tabs.begin(), tab))];
			if (subs.size() == kKitSubs) {
				return KitRefuse(page.line, "subs");
			}
			subs.push_back(i);
			REX::INFO("step=page_def n={} page={}/{} kind={} rows={} footer={}", i, page.tab, page.sub,
				!page.rows.empty() ? "rows" : !page.list.empty() ? page.list : "notice",
				page.rows.empty() ? page.notice.size() : page.rows.size(), page.footer.size());
		}
		g_kitState.selected.assign(g_kit.pages.size(), 0);
		g_kitState.top.assign(g_kit.pages.size(), 0);
		g_kitState.count.assign(g_kit.pages.size(), 0);
		g_kitPageLogged.assign(g_kit.pages.size(), false);
		REX::INFO("step=pages pages={} tabs={} signature=\"{}\"", g_kit.pages.size(), g_kit.tabs.size(), KitSignature());
		return true;
	}

	// the kit's keys (INI KitUp ... KitNextTab): up to three virtual-key codes each, none 0, above 0xFE, Key or
	// SnapshotKey
	bool ReadKitKeys(const std::filesystem::path& a_ini)
	{
		for (auto& binding : g_kitKeys) {
			std::array<wchar_t, 64> text{};
			REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", binding.ini, binding.keys, text.data(),
				static_cast<std::uint32_t>(text.size()), a_ini.c_str());
			const wchar_t* at = text.data();
			binding.count = 0;
			while (*at && binding.count < binding.vk.size()) {
				wchar_t*   end = nullptr;
				const auto vk = static_cast<std::uint32_t>(std::wcstoul(at, &end, 0));
				if (end == at || vk == 0 || vk > 0xFE || vk == g_key || vk == g_snapshotKey) {
					return Refuse("ini", std::format("kit_key={} (1 to 0xFE, not Key or SnapshotKey)",
						kKitMoveNames[static_cast<std::size_t>(binding.move)]));
				}
				binding.vk[binding.count++] = vk;
				at = end;
				while (*at == L',' || *at == L' ') {
					++at;
				}
			}
			std::string keys;
			for (std::size_t i = 0; i < binding.count; ++i) {
				keys += std::format("{}{}", i ? "," : "", Hex(binding.vk[i]));
			}
			REX::INFO("step=kit_keys action={} keys={}", kKitMoveNames[static_cast<std::size_t>(binding.move)],
				keys.empty() ? "none" : keys);
		}
		return true;
	}

	// a kit field's text, as the kit's font draws it: upper case, a character the font lacks as "?", at most a_columns
	std::string KitText(std::string_view a_text, std::size_t a_columns)
	{
		std::string out;
		for (const char c : a_text.substr(0, a_columns)) {
			const auto up = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
			out += kKitChars.find(up) != std::string_view::npos ? up : '?';
		}
		return out;
	}

	std::string KitRight(std::string_view a_text, std::size_t a_columns)   // right-aligned: the font is monospaced
	{
		const auto text = KitText(a_text, a_columns);
		return std::string(a_columns - text.size(), ' ') + text;
	}

	std::string KitCentre(std::string_view a_text, std::size_t a_columns)
	{
		const auto text = KitText(a_text, a_columns);
		return std::string((a_columns - text.size()) / 2, ' ') + text;
	}

	std::size_t KitPageIndex(const KitState& a_state) { return g_kit.subs[a_state.tab][a_state.sub[a_state.tab]]; }

	// the first row on screen that keeps the selected row on screen
	std::size_t KitTop(std::size_t a_top, std::size_t a_selected, std::size_t a_count)
	{
		if (a_count <= kKitRows) {
			return 0;
		}
		if (a_selected < a_top) {
			a_top = a_selected;
		}
		if (a_selected >= a_top + kKitRows) {
			a_top = a_selected + 1 - kKitRows;
		}
		return std::min(a_top, a_count - kKitRows);
	}

	// av:<id>'s ActorValueInfo form, looked up once by form id and accepted by its RTTI type (stage d's AcceptById,
	// logged whole as step=kit_av); main thread only
	std::uintptr_t KitActorValue(std::uint32_t a_id)
	{
		if (const auto known = g_kitActorValues.find(a_id); known != g_kitActorValues.end()) {
			return known->second;
		}
		std::uintptr_t form = 0;
		REX::INFO("step=kit_av {}", AcceptById(a_id, "av", "ActorValueInfo@@", kAvifEditorIdAt, form));
		g_kitActorValues.emplace(a_id, form);
		return form;
	}

	// one value provider's text (README, "Stage (e)": what each reads, and its step=page_unknown line when it cannot);
	// main thread only
	std::string KitValueRead(std::string_view a_spec)
	{
		if (a_spec == "health") {
			return ActorValueText("health", g_forms.health);
		}
		if (a_spec == "xp") {
			return ActorValueText("experience", g_forms.experience);
		}
		if (a_spec == "carry_max") {
			return ActorValueText("carry_weight", g_forms.carryWeight);
		}
		if (a_spec == "rads") {
			return g_forms.rads ? ActorValueText("rads", g_forms.rads) :
			       g_forms.avifs ? std::string("NOT INSTALLED") :
			                       Unknown("rads", "reason=actor_values_unread");
		}
		if (a_spec == "level") {
			return LevelText();
		}
		if (a_spec == "cell") {
			return PlaceText().first;
		}
		if (a_spec == "world") {
			return PlaceText().second;
		}
		if (a_spec == "time") {
			return TimeText();
		}
		if (a_spec == "days") {   // checked as the time is: both globals in range at the offset FindGlobalValue found
			float hour = 0.0f;
			float days = 0.0f;
			if (!ReadTime(g_forms.globalValueAt, hour, days)) {
				const auto reason = !g_forms.globals        ? "globals_unread" :
				                    !g_forms.globalValueAt ? "no_value_offset" :
				                                             "out_of_range";
				return Unknown("days", std::format("reason={}", reason));
			}
			return std::format("{:.2f}", days);
		}
		if (a_spec == "position") {
			std::array<float, 3> xyz{};
			return ReadPosition(xyz) && std::isfinite(xyz[0]) && std::isfinite(xyz[1]) && std::isfinite(xyz[2]) ?
			           std::format("{:.0f} {:.0f} {:.0f}", xyz[0], xyz[1], xyz[2]) :
			           Unknown("position", "reason=no_player");
		}
		if (a_spec.starts_with(kKitActorValue)) {   // ReadKit checked the hex
			const auto id = static_cast<std::uint32_t>(std::strtoul(std::string(a_spec.substr(kKitActorValue.size())).c_str(), nullptr, 16));
			return ActorValueText(a_spec, KitActorValue(id));
		}
		return Unknown(a_spec, "reason=no_such_value");
	}

	// each value once per screen (a footer cell that repeats a row's value reads it once)
	std::string KitValue(std::string_view a_spec, std::unordered_map<std::string, std::string>& a_memo)
	{
		std::string key(a_spec);
		if (const auto known = a_memo.find(key); known != a_memo.end()) {
			return known->second;
		}
		auto value = KitValueRead(a_spec);
		a_memo.emplace(std::move(key), value);
		return value;
	}

	// the kit_test list: thirty rows to scroll, select and click, with the kit's move counts beside the selected one
	std::vector<KitRow> KitTestRows(const KitState& a_state)
	{
		std::vector<KitRow> rows;
		for (std::size_t i = 1; i <= kKitTestRows; ++i) {
			rows.push_back({ std::format("TEST ROW {:02}", i), std::to_string(i * 7),
				{ { "ROW", std::format("{} OF {}", i, kKitTestRows) }, { "KEY MOVES", std::to_string(a_state.keys) },
					{ "CLICK MOVES", std::to_string(a_state.clicks) }, { "UPDATES", std::to_string(g_updates.load()) } } });
		}
		return rows;
	}

	// a_len bytes as hex, a comma every 8, for the log; "unreadable" if the read faults
	std::string KitBytes(std::uintptr_t a_at, std::size_t a_len)
	{
		std::array<std::uint8_t, 0x40> bytes{};
		if (!a_at || a_len > bytes.size() || !Peek(a_at, bytes.data(), a_len)) {
			return "unreadable";
		}
		std::string hex;
		for (std::size_t i = 0; i < a_len; ++i) {
			hex += std::format("{}{:02x}", i && i % 8 == 0 ? "," : "", bytes[i]);
		}
		return hex;
	}

	// the inventory list (FAL-426; README, "Stage (e)", lists): the player's BGSInventoryList by its RTTI, each item's
	// name and count (the sum of its stacks), sorted by name. Reads only, guarded, no lock taken: a torn read shows ?
	// and never faults. The first read logs the list and its first item's and stack's bytes once (step=kit_inventory),
	// which settles kStackCountAt on the PC; a list not read is one row and one step=page_unknown what=inventory line
	std::vector<KitRow> KitInventoryRows()
	{
		static bool logged = false;
		const auto  unread = [](std::string_view a_why, const std::string& a_detail) {
			Unknown("inventory", std::format("reason={} {}", a_why, a_detail));
			return std::vector<KitRow>{ { "INVENTORY NOT READ", "", { { "REASON", std::string(a_why) } } } };
		};
		if (!CheckSingleton("PlayerCharacter", kPlayerSingleton, kPlayerRtti, g_playerOk)) {
			return unread("no_player", "");
		}
		const auto     player = Singleton(kPlayerSingleton);
		std::uintptr_t list = 0;
		ObjectType     listType;
		if (!Peek(player + kInventoryListAt, list) || !IsType(list, "BGSInventoryList@@", listType)) {
			return unread("list_type", std::format("list={} type={}", Hex(list), listType.name.empty() ? "unreadable" : listType.name));
		}
		ArrayHead items{};
		if (!Peek(list + kInventoryDataAt, items) || items.size > items.capacity || items.size > kKitMaxItems ||
			(items.size && !items.data)) {
			return unread("items", std::format("size={} capacity={} data={}", items.size, items.capacity, Hex(items.data)));
		}
		if (!logged) {
			logged = true;
			ArrayHead first{};
			const bool stacked = items.size && Peek(items.data + kItemStacksAt, first) && first.size;
			REX::INFO("step=kit_inventory list={} type={} size={} capacity={} first_item={} first_stack={}", Hex(list),
				listType.name, items.size, items.capacity, items.size ? KitBytes(items.data, kInventoryItemSize) : "none",
				stacked ? KitBytes(first.data, kStackSize) : "none");
		}
		std::vector<KitRow> rows;
		for (std::uint32_t i = 0; i < items.size; ++i) {
			const auto     item = items.data + i * kInventoryItemSize;
			std::uintptr_t object = 0;
			ObjectType     type;
			if (!Peek(item, object) || !TypeOf(object, type) || !BaseOffset(type, "TESBoundObject@@")) {
				rows.push_back({ "?", "?", { { "ITEM", std::to_string(i + 1) }, { "OBJECT", Hex(object) } } });
				continue;
			}
			std::uint32_t  formId = 0;
			std::uintptr_t entry = 0;
			std::string    name;
			Peek(object + kFormIdAt, formId);
			const auto at = BaseOffset(type, "TESFullName@@");
			if (!at || !CheckSubobject(object, type, *at) || !Peek(object + *at + kFullNameAt, entry) ||
				!ReadPoolString(entry, name) || name.empty()) {
				name = std::format("{:08X}", formId);   // no name read: its form id
			}
			ArrayHead     stacks{};
			std::uint64_t count = 0;
			bool          counted = Peek(item + kItemStacksAt, stacks) && stacks.size <= stacks.capacity &&
			                        stacks.size <= kKitMaxItems && (!stacks.size || stacks.data);
			for (std::uint32_t s = 0; counted && s < stacks.size; ++s) {
				std::uint32_t n = 0;
				counted = Peek(stacks.data + s * kStackSize + kStackCountAt, n);
				count += n;
			}
			std::uint32_t flags = 0;
			const bool    equipped = Peek(item + kItemFlagsAt, flags) && (flags & 0x7);
			rows.push_back({ name, counted ? std::to_string(count) : "?",
				{ { "FORM", std::format("{:08X}", formId) }, { "TYPE", ShortName(type.name) },
					{ "STACKS", counted ? std::to_string(stacks.size) : "?" }, { "EQUIPPED", equipped ? "YES" : "NO" } } });
		}
		std::ranges::stable_sort(rows, {}, &KitRow::name);
		if (rows.empty()) {
			rows.push_back({ "NO ITEMS", "", {} });
		}
		return rows;
	}

	// a plugin file's form: its TESFile by name in the data handler's compiled file collection (libxse 9d090c4: files,
	// smallFiles, mediumFiles at +0x00, +0x10, +0x20, each a BSTArray<TESFile*>; a file accepted by its RTTI), then
	// the form id that file gives a_localId (full: the compile index, then fileIndex's full byte; small FE + 12 bits;
	// medium FD + 16 bits), accepted only if the engine's lookup gives a form of RTTI type a_type. a_detail logs the
	// file and every id tried
	std::uint32_t KitFileForm(std::string_view a_file, std::uint32_t a_localId, std::string_view a_type, std::string& a_detail)
	{
		const auto handler = Singleton(kDataHandlerSingleton);
		ObjectType type;
		if (!IsType(handler, "TESDataHandler@@", type)) {
			a_detail = "reason=data_handler";
			return 0;
		}
		for (std::size_t kind = 0; kind < 3; ++kind) {   // full, small, medium
			ArrayHead files{};
			if (!Peek(handler + kFileCollectionAt + kind * 0x10, files) || files.size > files.capacity ||
				files.size > kKitMaxFiles || (files.size && !files.data)) {
				a_detail = std::format("reason=files kind={} size={} capacity={}", kind, files.size, files.capacity);
				return 0;
			}
			for (std::uint32_t i = 0; i < files.size; ++i) {
				std::uintptr_t                  file = 0;
				ObjectType                      fileType;
				std::array<char, kFileNameSize> name{};
				if (!Peek(files.data + i * sizeof(std::uintptr_t), file) || !IsType(file, "TESFile@@", fileType) ||
					!Peek(file + kFileNameAt, name.data(), name.size()) ||
					!SameText(std::string_view(name.data(), strnlen(name.data(), name.size())), a_file)) {
					continue;
				}
				std::uint8_t                compile = 0;
				std::array<std::uint8_t, 4> index{};
				Peek(file + kFileCompileIndexAt, compile);
				Peek(file + kFileIndexAt, index.data(), index.size());
				const std::uint32_t smallIndex = index[2] | (index[3] << 8);
				std::vector<std::uint32_t> ids;
				if (kind == 0) {
					ids = { (std::uint32_t{ compile } << 24) | (a_localId & 0xFFFFFF), (std::uint32_t{ index[0] } << 24) | (a_localId & 0xFFFFFF) };
				} else if (kind == 1) {
					ids = { 0xFE000000u | ((smallIndex & 0xFFF) << 12) | (a_localId & 0xFFF) };
				} else {
					ids = { 0xFD000000u | (std::uint32_t{ index[1] } << 16) | (a_localId & 0xFFFF) };
				}
				a_detail = std::format("file_kind={} file={} compile_index={:02x} file_index={}", kind, Hex(file), compile,
					KitBytes(file + kFileIndexAt, 4));
				for (const auto id : ids) {
					ObjectType formType;
					const auto form = FormById(id);
					a_detail += std::format(" tried={:08X}:{}", id, form && TypeOf(form, formType) ? ShortName(formType.name) : "none");
					if (IsType(form, a_type, formType)) {
						return id;
					}
				}
				return 0;
			}
		}
		a_detail = "reason=file_not_loaded";
		return 0;
	}

	// the quest list (FAL-431; README, "Stage (e)", lists): our mission first, the quest [Kit] Mission= names, by its
	// file and local id (KitFileForm), accepted by its RTTI (TESQuest); its name (TESFullName, at +0x40 in Starfield's
	// RTTI) and its QUEST_DATA flags as read (u16 at +0x10C, the running and completed bits not named until the PC's
	// log does). The first read logs the quest's bytes from +0x100 once (step=kit_quest), where the flags and the
	// current stage are; the stage shows ? until then. Starfield's own quests are not listed yet
	std::vector<KitRow> KitQuestRows()
	{
		static std::uint32_t formId = 0;
		static bool          logged = false;
		const auto           unread = [](std::string_view a_why, const std::string& a_detail) {
			Unknown("quests", std::format("reason={} {}", a_why, a_detail));
			return std::vector<KitRow>{ { "QUESTS NOT READ", "", { { "REASON", std::string(a_why) } } } };
		};
		if (g_kit.missionFile.empty()) {
			return unread("no_mission", "");
		}
		std::string detail;
		if (!formId) {
			formId = KitFileForm(g_kit.missionFile, g_kit.missionId, "TESQuest@@", detail);
		}
		const auto quest = formId ? FormById(formId) : 0;
		ObjectType type;
		if (!IsType(quest, "TESQuest@@", type)) {
			if (!logged) {
				logged = true;
				REX::INFO("step=kit_quest mission={}|{:X} found=no {}", g_kit.missionFile, g_kit.missionId, detail);
			}
			formId = 0;
			return unread("mission_not_found", std::format("mission={}|{:X}", g_kit.missionFile, g_kit.missionId));
		}
		std::string    name;   // its TESFullName as the inventory reads one, else its form id
		std::uintptr_t entry = 0;
		const auto     at = BaseOffset(type, "TESFullName@@");
		if (!at || !CheckSubobject(quest, type, *at) || !Peek(quest + *at + kFullNameAt, entry) || !ReadPoolString(entry, name) ||
			name.empty()) {
			name = std::format("{:08X}", formId);
		}
		std::uint16_t flags = 0;
		const bool    flagged = Peek(quest + kQuestFlagsAt, flags);
		if (!logged) {
			logged = true;
			REX::INFO("step=kit_quest mission={}|{:X} found=yes form={:08X} quest={} type={} full_name_at={} name=\"{}\" flags={} "
				"bytes100={} {}", g_kit.missionFile, g_kit.missionId, formId, Hex(quest), type.name, at ? Hex(*at) : "none", name,
				flagged ? std::format("{:04x}", flags) : "unreadable", KitBytes(quest + kQuestBytesAt, 0x40), detail);
		}
		std::string file = g_kit.missionFile;
		std::ranges::transform(file, file.begin(), [](unsigned char a_c) { return static_cast<char>(std::toupper(a_c)); });
		return { { name, "", { { "FORM", std::format("{:08X}", formId) }, { "FILE", file },
			{ "FLAGS", flagged ? std::format("{:04X}", flags) : "?" }, { "STAGE", "?" } } } };
	}

	// the selected row's value rows: a label and its value right-aligned, or, for a value longer than its column,
	// the label alone and the value on the lines below across both columns
	void KitInfoLines(const std::vector<std::pair<std::string, std::string>>& a_info, KitScreen& a_screen)
	{
		constexpr auto width = kKitInfoLabelColumns + kKitInfoValueColumns;
		std::size_t    line = 0;
		for (const auto& [label, value] : a_info) {
			if (line == kKitRows) {
				break;
			}
			const auto text = KitText(value, width * 3);
			a_screen.infoLabels[line] = KitText(label, kKitInfoLabelColumns);
			if (text.size() <= kKitInfoValueColumns) {
				a_screen.infoValues[line++] = KitRight(text, kKitInfoValueColumns);
				continue;
			}
			++line;
			for (std::size_t at = 0; at < text.size() && line < kKitRows; at += width, ++line) {
				const auto part = std::string_view(text).substr(at, width);
				a_screen.infoLabels[line] = std::string(part.substr(0, kKitInfoLabelColumns));
				a_screen.infoValues[line] = part.size() > kKitInfoLabelColumns ? std::string(part.substr(kKitInfoLabelColumns)) : "";
			}
		}
	}

	// the shown page's screen, on the main thread before each kShow and kUpdate (Toggle, SendUpdate)
	void KitCollect()
	{
		PageScan();
		FindGlobalValue();
		KitState state;
		{
			std::scoped_lock lock(g_pageLock);
			state = g_kitState;
		}
		const auto                                   index = KitPageIndex(state);
		const auto&                                  page = g_kit.pages[index];
		std::unordered_map<std::string, std::string> memo;
		std::vector<KitRow>                          rows;
		if (!page.rows.empty()) {
			for (const auto& cell : page.rows) {
				auto value = KitValue(cell.value, memo);
				rows.push_back({ cell.label, value, { { "VALUE", value }, { "FROM", cell.value } } });
			}
		} else if (page.list == "kit_test") {
			rows = KitTestRows(state);
		} else if (page.list == "inventory") {
			rows = KitInventoryRows();
		} else if (page.list == "quests") {
			rows = KitQuestRows();
		} else {
			for (const auto& line : page.notice) {
				rows.push_back({ line, "", {} });
			}
		}
		const auto count = page.notice.empty() ? rows.size() : std::size_t{ 0 };   // a notice has no selection
		const auto selected = count ? std::min(state.selected[index], count - 1) : std::size_t{ 0 };
		const auto top = KitTop(state.top[index], selected, count);
		KitScreen  screen;
		screen.page = index;
		screen.title = KitText(g_kit.title, kKitTitleColumns);
		screen.header = g_kit.header.empty() ? "" : KitRight(KitValue(g_kit.header, memo), kKitTitleColumns);
		screen.hints = KitText(page.hint.empty() ? g_kit.hints : page.hint, kKitHintColumns);
		for (std::size_t i = 0; i < g_kit.tabs.size(); ++i) {
			screen.tabs[i] = KitText(g_kit.tabs[i], kKitTabColumns);
		}
		screen.tab = state.tab;
		const auto& subs = g_kit.subs[state.tab];
		for (std::size_t i = 0; i < subs.size(); ++i) {
			screen.subs[i] = KitText(g_kit.pages[subs[i]].sub, kKitSubColumns);
		}
		screen.sub = state.sub[state.tab];
		for (std::size_t i = 0; i < kKitRows && top + i < rows.size(); ++i) {
			const auto& row = rows[top + i];
			if (row.value.size() <= kKitValueColumns) {
				screen.names[i] = KitText(row.name, kKitNameColumns);
				screen.values[i] = row.value.empty() ? "" : KitRight(row.value, kKitValueColumns);
			} else {   // a long value follows its label in the name's column
				screen.names[i] = KitText(std::format("{} {}", row.name, row.value), kKitNameColumns);
			}
		}
		if (count) {
			screen.bar = selected - top;
			KitInfoLines(rows[selected].info, screen);
		}
		screen.moreUp = top > 0;
		screen.moreDown = top + kKitRows < rows.size();
		for (std::size_t i = 0; i < page.footer.size(); ++i) {
			screen.footer[i] = KitCentre(std::format("{} {}", page.footer[i].label, KitValue(page.footer[i].value, memo)),
				kKitFooterColumns);
		}
		if (!g_kitPageLogged[index]) {
			g_kitPageLogged[index] = true;
			REX::INFO("step=kit_page page={}/{} rows={} selectable={} first=\"{}\"", page.tab, page.sub, rows.size(), count,
				rows.empty() ? "" : KitText(std::format("{} {}", rows[0].name, rows[0].value), kKitNameColumns));
		}
		std::scoped_lock lock(g_pageLock);
		if (KitPageIndex(g_kitState) == index) {   // keep a move made since the copy; only bound it
			auto& s = g_kitState;
			s.count[index] = count;
			s.selected[index] = count ? std::min(s.selected[index], count - 1) : std::size_t{ 0 };
			s.top[index] = KitTop(s.top[index], s.selected[index], count);
		}
		g_kitScreen = std::move(screen);
		g_kitCollected = true;
	}

	// one move of the state, from a key (the key thread) or a click (the menu's thread), then an update at once.
	// Returns what it did, for the log line of its caller
	std::string KitAct(KitMove a_move, std::size_t a_index, bool a_key)
	{
		std::scoped_lock lock(g_pageLock);
		auto&      s = g_kitState;
		const auto page = KitPageIndex(s);
		const auto tabs = g_kit.tabs.size();
		const auto subs = g_kit.subs[s.tab].size();
		const auto count = s.count[page];
		auto&      selected = s.selected[page];
		auto&      sub = s.sub[s.tab];
		bool       moved = false;
		switch (a_move) {   // a move past either end changes nothing (no wrap)
		case KitMove::kUp:
			moved = selected > 0;
			if (moved) {
				--selected;
			}
			break;
		case KitMove::kDown:
			moved = selected + 1 < count;
			if (moved) {
				++selected;
			}
			break;
		case KitMove::kPrevSub:
			moved = sub > 0;
			if (moved) {
				--sub;
			}
			break;
		case KitMove::kNextSub:
			moved = sub + 1 < subs;
			if (moved) {
				++sub;
			}
			break;
		case KitMove::kPrevTab:
			moved = s.tab > 0;
			if (moved) {
				--s.tab;
			}
			break;
		case KitMove::kNextTab:
			moved = s.tab + 1 < tabs;
			if (moved) {
				++s.tab;
			}
			break;
		case KitMove::kTab:
			moved = a_index < tabs && a_index != s.tab;
			if (moved) {
				s.tab = a_index;
			}
			break;
		case KitMove::kSub:
			moved = a_index < subs && a_index != sub;
			if (moved) {
				sub = a_index;
			}
			break;
		case KitMove::kRow:
			moved = s.top[page] + a_index < count && s.top[page] + a_index != selected;
			if (moved) {
				selected = s.top[page] + a_index;
			}
			break;
		}
		s.top[page] = KitTop(s.top[page], s.selected[page], count);
		if (moved) {
			++(a_key ? s.keys : s.clicks);
			g_refreshNow = true;   // the key thread sends an update at once
		}
		const auto& shown = g_kit.pages[KitPageIndex(s)];
		return std::format("action={} index={} moved={} page={}/{} selected={}", kKitMoveNames[static_cast<std::size_t>(a_move)],
			a_index, moved ? 1 : 0, shown.tab, shown.sub, s.selected[KitPageIndex(s)]);
	}

	// a click's target, by its instance name: a main tab, a sub-tab or a row (its hit area, its bar or its text).
	// CLOSE has its own listener; any other name (the screen, a value row) changes nothing
	std::string KitClick(std::string_view a_name)
	{
		const auto indexAfter = [&](std::string_view a_prefix) -> std::optional<std::size_t> {
			if (!a_name.starts_with(a_prefix)) {
				return std::nullopt;
			}
			const auto digits = a_name.substr(a_prefix.size());
			if (digits.empty() || digits.size() > 2 ||
				!std::ranges::all_of(digits, [](char a_c) { return a_c >= '0' && a_c <= '9'; })) {
				return std::nullopt;
			}
			return static_cast<std::size_t>(std::strtoul(std::string(digits).c_str(), nullptr, 10));
		};
		for (const auto* prefix : { kKitTab, kKitTabMark, kKitTabHit }) {
			if (const auto i = indexAfter(prefix)) {
				return KitAct(KitMove::kTab, *i, false);
			}
		}
		for (const auto* prefix : { kKitSub, kKitSubDim, kKitSubHit }) {
			if (const auto i = indexAfter(prefix)) {
				return KitAct(KitMove::kSub, *i, false);
			}
		}
		for (const auto* prefix : { kKitRowName, kKitRowValue, kKitRowNameSel, kKitRowValueSel, kKitBar, kKitRowHit }) {
			if (const auto i = indexAfter(prefix)) {
				return KitAct(KitMove::kRow, *i, false);
			}
		}
		return a_name == kKitClose ? "action=close (its own listener)" : "action=none";
	}

	// every click in the kit's movie reaches this listener on the root (Scaleform calls it on the menu's thread, the
	// event as the only argument): the event's target, then its instance name
	class KitClickHandler final : public RE::Scaleform::GFx::FunctionHandler
	{
	public:
		void Call(const Params& a_params) override
		{
			const auto                n = ++g_kitClicks;
			RE::Scaleform::GFx::Value target;
			RE::Scaleform::GFx::Value name;
			const bool                gotTarget = a_params.argCount >= 1 && a_params.args && a_params.args[0].IsObject() &&
			                                      a_params.args[0].GetMember("target", &target) && target.IsObject();
			const bool                gotName = gotTarget && target.GetMember("name", &name) && name.IsString();
			const std::string         what = gotName ? name.GetString() : "";
			const auto                action = gotName ? KitClick(what) : std::string("action=none");
			REX::INFO("step=kit_click n={} args={} target={} name={} {}", n, a_params.argCount, gotTarget ? 1 : 0,
				what.empty() ? "-" : what, action);
		}
	};
	KitClickHandler g_kitClickHandler;

	// our function as a_target's "click" listener (CreateFunction, addEventListener), as stage d adds its buttons'
	bool KitAddListener(RE::Scaleform::GFx::ASMovieRootBase* a_root, RE::Scaleform::GFx::Value& a_target,
		RE::Scaleform::GFx::FunctionHandler* a_handler, RE::Scaleform::GFx::Value& a_function)
	{
		a_root->CreateFunction(&a_function, a_handler);
		if (a_function.IsUndefined()) {
			return false;
		}
		std::array<RE::Scaleform::GFx::Value, 2> args;
		args[0] = "click";
		args[1] = a_function;
		return a_target.Invoke("addEventListener", nullptr, args.data(), args.size());
	}

	// once per movie, at kShow: the movie's signature against ours, our listener on the root, and stage d's CLOSE
	// handler on the CLOSE button
	void KitListen(const void* a_menu)
	{
		auto* const root = RootOf(a_menu);
		const auto  movie = MovieOf(a_menu);
		if (!root || g_listenedMovie == movie) {
			return;
		}
		g_listenedMovie = movie;
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		RE::Scaleform::GFx::Value idField;
		RE::Scaleform::GFx::Value id;
		const bool        gotId = gotRoot && ChildOf(top, kKitId, idField) && idField.GetMember("text", &id) && id.IsString();
		const std::string read = gotId ? id.GetString() : "";
		REX::INFO("step=kit_movie id=\"{}\" expected=\"{}\" match={}", read, KitSignature(), read == KitSignature() ? "yes" : "no");
		RE::Scaleform::GFx::Value rootFunction;
		const bool                rootAdded = gotRoot && KitAddListener(root, top, &g_kitClickHandler, rootFunction);
		REX::INFO("step=listen name=root root={} function_type={} added={} event=click", gotRoot ? 1 : 0,
			TypeCode(rootFunction), rootAdded ? 1 : 0);
		RE::Scaleform::GFx::Value close;
		RE::Scaleform::GFx::Value closeFunction;
		const bool                gotClose = gotRoot && ChildOf(top, kKitClose, close);
		const bool                closeAdded = gotClose && KitAddListener(root, close, &g_closeHandler, closeFunction);
		REX::INFO("step=listen name={} root={} button={} function_type={} added={} event=click", kKitClose, gotRoot ? 1 : 0,
			gotClose ? 1 : 0, TypeCode(closeFunction), closeAdded ? 1 : 0);
	}

	struct KitCount
	{
		std::size_t found = 0;     // children found for a change
		std::size_t set = 0;       // SetMember returned true
		std::size_t match = 0;     // and the value read back
		std::size_t missing = 0;   // no child of that name
	};

	// a field's text, set only if it changed since the last read-back on this movie
	void KitSetText(RE::Scaleform::GFx::Value& a_root, const std::string& a_name, const std::string& a_text, KitCount& a_count)
	{
		if (const auto known = g_kitTexts.find(a_name); known != g_kitTexts.end() && known->second == a_text) {
			return;
		}
		RE::Scaleform::GFx::Value field;
		RE::Scaleform::GFx::Value back;
		if (!ChildOf(a_root, a_name.c_str(), field)) {
			++a_count.missing;
			return;
		}
		++a_count.found;
		a_count.set += field.SetMember("text", RE::Scaleform::GFx::Value(a_text.c_str())) ? 1 : 0;
		if (field.GetMember("text", &back) && back.IsString() && a_text == back.GetString()) {
			++a_count.match;
			g_kitTexts[a_name] = a_text;   // one that did not read back is set again on the next write
		}
	}

	// an object's `visible`, likewise
	void KitSetShown(RE::Scaleform::GFx::Value& a_root, const std::string& a_name, bool a_shown, KitCount& a_count)
	{
		if (const auto known = g_kitShown.find(a_name); known != g_kitShown.end() && known->second == a_shown) {
			return;
		}
		RE::Scaleform::GFx::Value object;
		RE::Scaleform::GFx::Value back;
		if (!ChildOf(a_root, a_name.c_str(), object)) {
			++a_count.missing;
			return;
		}
		++a_count.found;
		a_count.set += object.SetMember("visible", RE::Scaleform::GFx::Value(a_shown)) ? 1 : 0;
		if (object.GetMember("visible", &back) && back.IsBoolean() && back.GetBoolean() == a_shown) {
			++a_count.match;
			g_kitShown[a_name] = a_shown;
		}
	}

	// at kShow (everything, a_show) and every kUpdate (what changed), on the menu's thread: the screen KitCollect built.
	// Logged for n = 1 to 20, then every 20th, and on the first 20 with a child missing or a value not read back
	void KitWrite(const void* a_menu, std::uint32_t a_update, bool a_show)
	{
		auto* const root = RootOf(a_menu);
		if (!root) {
			return;
		}
		static std::atomic<std::uint32_t> problems{ 0 };
		KitScreen                         screen;
		bool                              collected = false;
		{
			std::scoped_lock lock(g_pageLock);
			screen = g_kitScreen;
			collected = g_kitCollected;
		}
		if (a_show) {   // a new movie, or the same one shown again: set everything once
			g_kitTexts.clear();
			g_kitShown.clear();
		}
		RE::Scaleform::GFx::Value top;
		const bool                gotRoot = root->GetVariable(&top, "root") && top.IsObject();
		KitCount                  count;
		if (gotRoot && collected) {
			const auto named = [](const char* a_name, std::size_t a_i) { return std::format("{}{}", a_name, a_i); };
			KitSetText(top, kKitTitle, screen.title, count);
			KitSetText(top, kKitHeader, screen.header, count);
			KitSetText(top, kKitHints, screen.hints, count);
			for (std::size_t i = 0; i < g_kit.tabs.size(); ++i) {
				KitSetText(top, named(kKitTab, i), screen.tabs[i], count);
				KitSetShown(top, named(kKitTabMark, i), i == screen.tab, count);
			}
			for (std::size_t i = 0; i < kKitSubs; ++i) {
				KitSetText(top, named(kKitSub, i), screen.subs[i], count);
				KitSetText(top, named(kKitSubDim, i), screen.subs[i], count);
				KitSetShown(top, named(kKitSub, i), i == screen.sub, count);
				KitSetShown(top, named(kKitSubDim, i), i != screen.sub, count);
			}
			for (std::size_t i = 0; i < kKitRows; ++i) {
				const bool selected = screen.bar && *screen.bar == i;
				KitSetText(top, named(kKitRowName, i), screen.names[i], count);
				KitSetText(top, named(kKitRowValue, i), screen.values[i], count);
				KitSetText(top, named(kKitRowNameSel, i), screen.names[i], count);
				KitSetText(top, named(kKitRowValueSel, i), screen.values[i], count);
				KitSetShown(top, named(kKitRowName, i), !selected, count);
				KitSetShown(top, named(kKitRowValue, i), !selected, count);
				KitSetShown(top, named(kKitRowNameSel, i), selected, count);
				KitSetShown(top, named(kKitRowValueSel, i), selected, count);
				KitSetShown(top, named(kKitBar, i), selected, count);
				KitSetText(top, named(kKitInfoLabel, i), screen.infoLabels[i], count);
				KitSetText(top, named(kKitInfoValue, i), screen.infoValues[i], count);
			}
			KitSetShown(top, kKitMoreUp, screen.moreUp, count);
			KitSetShown(top, kKitMoreDown, screen.moreDown, count);
			for (std::size_t i = 0; i < kKitFooter; ++i) {
				KitSetText(top, named(kKitFoot, i), screen.footer[i], count);
			}
		}
		const auto n = ++g_kitWrites;
		const bool problem = count.missing || count.match != count.found;
		if (n <= 20 || n % 20 == 0 || (problem && problems++ < 20)) {
			std::string rows;
			for (std::size_t i = 0; i < kKitRows && rows.size() < 900; ++i) {
				if (!screen.names[i].empty()) {
					rows += std::format("{}{}{}{}", rows.empty() ? "" : " | ", screen.bar && *screen.bar == i ? ">" : "",
						screen.names[i], screen.values[i]);
				}
			}
			const auto& page = g_kit.pages[screen.page];
			REX::INFO("step=kit n={} update={} show={} page={}/{} root={} collected={} changed={} set={} match={} missing={} "
					  "bar={} footer=\"{}|{}|{}\" rows=\"{}\"",
				n, a_update, a_show ? 1 : 0, page.tab, page.sub, gotRoot ? 1 : 0, collected ? 1 : 0, count.found, count.set,
				count.match, count.missing, screen.bar ? std::to_string(*screen.bar) : "-", screen.footer[0], screen.footer[1],
				screen.footer[2], rows);
		}
	}

	// the kit's keys, every 30 ms on the key thread while the page is open and the game in front: a press moves once; a
	// held Up or Down repeats after 420 ms, every 90 ms. Each press is logged with what it did
	void KitKeys(std::array<std::uint32_t, 6>& a_held)
	{
		for (std::size_t i = 0; i < g_kitKeys.size(); ++i) {
			const auto&   binding = g_kitKeys[i];
			std::uint32_t vk = 0;
			for (std::size_t k = 0; k < binding.count && !vk; ++k) {
				if (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(binding.vk[k])) & 0x8000) {
					vk = binding.vk[k];
				}
			}
			if (!vk) {
				a_held[i] = 0;
				continue;
			}
			const auto ticks = ++a_held[i];
			const bool repeats = binding.move == KitMove::kUp || binding.move == KitMove::kDown;
			if (ticks == 1) {
				REX::INFO("step=kit_key vk={} {}", Hex(vk), KitAct(binding.move, 0, true));
			} else if (repeats && ticks > 14 && (ticks - 14) % 3 == 0) {
				KitAct(binding.move, 0, true);
			}
		}
	}

	// ------------------------------------------------------------------------------------------- the menu's slots
	void* MenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		REX::INFO("step=destroy menu={} flags={}", Hex(reinterpret_cast<std::uintptr_t>(a_self)), a_flags);
		if (const auto movie = MovieOf(a_self)) {   // stage c: a later movie at the same address is checked again
			if (g_listenedMovie == movie) {
				g_listenedMovie = nullptr;
			}
			if (g_checkedMovie == movie) {
				g_checkedMovie = nullptr;
			}
		}
		g_engineDtor(a_self, a_flags & ~1u);   // the engine's IMenu destructor, without its delete: the memory is ours
		if (a_flags & 1) {
			std::free(a_self);
		}
		REX::INFO("step=destroyed menu={}", Hex(reinterpret_cast<std::uintptr_t>(a_self)));
		return a_self;
	}

	const char* MenuGetName(const void*) { return kMenuName; }

	// "" binds no menu object in the movie: our movie has no code (a file path here is read as a clip path)
	const char* MenuGetRootPath(const void*) { return ""; }

	std::int32_t MenuGetViewScaleMode(void*) { return 1; }   // Scaleform ShowAll: the whole stage, aspect kept

	bool MenuLoadMovie(void* a_self, bool a_dispatcher, bool a_arg2)
	{
		const auto menu = Hex(reinterpret_cast<std::uintptr_t>(a_self));
		if (g_stage == 1) {
			REX::INFO("step=load_movie menu={} dispatcher={} arg2={} stage=a result=skipped", menu, a_dispatcher, a_arg2);
			return true;
		}
		if (MovieOf(a_self)) {
			REX::INFO("step=load_movie menu={} dispatcher={} arg2={} stage=b result=already_loaded", menu, a_dispatcher, a_arg2);
			return true;
		}
		REX::INFO("step=load_movie menu={} dispatcher={} arg2={} stage=b calling", menu, a_dispatcher, a_arg2);
		const bool loaded = g_engineLoadMovie(a_self, false, a_arg2);
		REX::INFO("step=load_movie menu={} stage=b result={} movie={}", menu, loaded ? 1 : 0,
			Hex(reinterpret_cast<std::uintptr_t>(MovieOf(a_self))));
		return loaded;
	}

	RE::UI_MESSAGE_RESULT MenuProcessMessage(void* a_self, RE::UIMessageData& a_message)
	{
		const auto type = a_message.type;
		if (g_stage >= 3 && type == RE::UI_MESSAGE_TYPE::kShow) {
			ApplyFlagSet(a_self, ++g_shows);
		}
		if (g_stage >= 2 && type == RE::UI_MESSAGE_TYPE::kShow && !MovieOf(a_self)) {
			REX::INFO("step=load_movie menu={} caller=plugin before=show", Hex(reinterpret_cast<std::uintptr_t>(a_self)));
			MenuLoadMovie(a_self, false, false);
		}
		const auto result = g_stage == 1 && type == RE::UI_MESSAGE_TYPE::kShow ?
		                        RE::UI_MESSAGE_RESULT::kHandled :
		                        g_engineProcessMessage(a_self, a_message);
		const bool showOrHide = type == RE::UI_MESSAGE_TYPE::kShow || type == RE::UI_MESSAGE_TYPE::kHide;
		if (showOrHide || g_otherMessages.fetch_add(1) < 20) {
			const auto name = type == RE::UI_MESSAGE_TYPE::kShow ? "show"sv :
			                  type == RE::UI_MESSAGE_TYPE::kHide ? "hide"sv :
			                  type == RE::UI_MESSAGE_TYPE::kUpdate ? "update"sv :
			                                                         "other"sv;
			REX::INFO("step=message menu={} type={} raw={} result={}", Hex(reinterpret_cast<std::uintptr_t>(a_self)), name,
				static_cast<std::uint32_t>(type), static_cast<std::int64_t>(result));
		}
		if (g_stage >= 3) {   // stages c, d and e: after the engine's own handling, on its thread for this menu
			if (type == RE::UI_MESSAGE_TYPE::kShow) {
				if (g_stage == 5) {   // the kit opens on the page it showed last
					KitListen(a_self);
					KitWrite(a_self, 0, true);
				} else if (g_stage == 4) {   // the page opens on its first tab
					g_tab = 0;
					PageListen(a_self);
					PageWrite(a_self, 0);
				} else {
					ChannelListen(a_self);
					ChannelWrite(a_self, 0);
				}
				Snapshot("show");
			} else if (type == RE::UI_MESSAGE_TYPE::kUpdate) {
				const auto n = ++g_updates;
				if (g_stage == 5) {
					KitWrite(a_self, n, false);
				} else if (g_stage == 4) {
					PageWrite(a_self, n);
				} else {
					ChannelWrite(a_self, n);
				}
				if (n % 10 == 1) {
					Snapshot("open");
				}
			} else if (type == RE::UI_MESSAGE_TYPE::kHide) {
				Snapshot("hide");
			}
		}
		return result;
	}

	bool MenuIsMovieLoaded(void*) { return true; }   // stage a: the admission check the engine's answers with uiMovie

	// the creator UI calls on kShow. The engine passes uninitialised storage for a Scaleform::Ptr<IMenu> (MSVC's hidden
	// return slot); the menu pointer is written there owning the constructor's reference, as the engine's own creators do
	// FAL-414: the menu's own cancel handling. Both input slots are called with this = menu + 0x10 (BSInputEventUser).
	// A keyboard button whose id is in CancelCodes (or whose user event is "Cancel"), while the menu is open, is ours:
	// [01] says we handle it, [08] marks it kStop (the pause menu's ShouldHandleEvent refuses a stopped event) and, on the
	// press (value > 0, heldDownSecs == 0), asks the key thread to close the menu. Everything else goes to the engine's.
	struct CancelLook
	{
		bool          mine = false;
		bool          press = false;
		std::uint32_t code = 0;
	};

	CancelLook LookAtEvent(const void* a_event, bool a_log)
	{
		CancelLook look;
		if (!a_event || !g_open) {
			return look;
		}
		const auto* base = static_cast<const RE::InputEvent*>(a_event);
		if (base->eventType != RE::InputEvent::EventType::kButton || base->deviceType != RE::InputEvent::DeviceType::kKeyboard) {
			return look;
		}
		const auto* button = static_cast<const RE::ButtonEvent*>(a_event);
		look.code = static_cast<std::uint32_t>(button->idCode);
		const std::string_view user = button->strUserEvent.c_str() ? std::string_view(button->strUserEvent.c_str()) : std::string_view{};
		bool cancel = user == "Cancel";
		for (std::size_t i = 0; i < g_cancelCount; ++i) {
			cancel = cancel || look.code == g_cancelCodes[i];
		}
		look.mine = cancel;
		look.press = button->value > 0.0f && button->heldDownSecs == 0.0f;
		if (a_log && g_cancelLogged.load() < 40 && (cancel || look.press)) {   // the first presses: which id and user event the game sends
			++g_cancelLogged;
			REX::INFO("step=input id={} user_event=\"{}\" value={} held={} status={} cancel={}", Hex(look.code), user, button->value,
				button->heldDownSecs, static_cast<std::uint32_t>(base->status), cancel ? 1 : 0);
		}
		return look;
	}

	bool a_eventValueIsRelease(const void* a_event)
	{
		return static_cast<const RE::ButtonEvent*>(a_event)->value == 0.0f;
	}

	bool MenuShouldHandleEvent(void* a_input, const void* a_event)
	{
		const auto look = LookAtEvent(a_event, false);
		if (look.mine && static_cast<const RE::InputEvent*>(a_event)->status != RE::InputEvent::Status::kStop) {
			return true;
		}
		return g_engineShouldHandle(a_input, a_event);
	}

	void MenuOnButtonEvent(void* a_input, const void* a_event)
	{
		const auto look = LookAtEvent(a_event, true);
		if (!look.mine) {
			g_engineOnButton(a_input, a_event);
			return;
		}
		const_cast<RE::InputEvent*>(static_cast<const RE::InputEvent*>(a_event))->status = RE::InputEvent::Status::kStop;
		// the game sends one press as several events (held=0, 0.009, 0.017, ...): close on the first only, and
		// not again until a release (value == 0) has been seen
		if (look.press && !g_cancelHeld.exchange(true)) {
			g_cancelNow = true;
		} else if (a_eventValueIsRelease(a_event)) {
			g_cancelHeld = false;
		}
	}

	RE::Scaleform::Ptr<RE::IMenu>* Create(RE::Scaleform::Ptr<RE::IMenu>* a_out)
	{
		const auto n = ++g_created;
		void*      menu = std::calloc(1, kMenuBytes);
		if (!menu) {
			REX::ERROR("refuse step=create n={} reason=out_of_memory", n);
			std::construct_at(a_out);
			return a_out;
		}
		g_ctor(menu);
		const auto base = reinterpret_cast<std::uintptr_t>(menu);
		const auto vtables = *reinterpret_cast<const std::uintptr_t*>(base) == Address(kVtblPrimary) &&
		                     *reinterpret_cast<const std::uintptr_t*>(base + 0x10) == Address(kVtblInput) &&
		                     *reinterpret_cast<const std::uintptr_t*>(base + 0x50) == Address(kVtblSink);
		auto*      refs = reinterpret_cast<volatile std::uint32_t*>(base + 0x08);   // Scaleform RefCountImplCore
		const auto ctorRefs = *refs;
		*reinterpret_cast<std::uintptr_t*>(base) = reinterpret_cast<std::uintptr_t>(g_vtbl.slots.data());
		if (g_stage >= 4) {
			*reinterpret_cast<std::uintptr_t*>(base + 0x10) = reinterpret_cast<std::uintptr_t>(g_inputVtbl.slots.data());
		}
		// what the engine's dynamic_cast reads on our object: the locator one slot before its primary vtable
		const auto rtti = *reinterpret_cast<const std::uintptr_t*>(*reinterpret_cast<const std::uintptr_t*>(base) - 8) ==
		                  *reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary) - 8);
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = MenuName();
		const auto ctorFlags = imenu->flags;
		const auto extra = g_flags | (g_stage >= 3 ? FlagSet(n) : 0);   // stages c to e: this open's flag set
		g_ctorFlags = ctorFlags;
		if (extra) {
			imenu->flags |= extra;
			imenu->flagsUpdated = true;
		}
		if (g_keepAlive && ctorRefs == 1) {
			REX::W32::InterlockedIncrement(refs);   // a public precedent's count: never released to zero
		}
		REX::INFO("step=create n={} menu={} vtables={} rtti={} refcount={} keep_alive={} ctor_flags={} flags={} depth={}{}",
			n, Hex(base), vtables ? "engine" : "UNEXPECTED", rtti ? "engine" : "UNEXPECTED", ctorRefs, g_keepAlive ? 1 : 0,
			Hex(ctorFlags), Hex(imenu->flags), Hex(*reinterpret_cast<const std::uint8_t*>(base + 0x110)),
			g_stage >= 3 ? std::format(" set={}", FlagSetIndex(n)) : "");
		std::memcpy(static_cast<void*>(a_out), &menu, sizeof(menu));
		return a_out;
	}

	// ------------------------------------------------------------------------------------------- checks before use
	bool Refuse(std::string_view a_step, const std::string& a_what)
	{
		REX::ERROR("refuse step={} {}", a_step, a_what);
		return false;
	}

	bool CheckImage()
	{
		g_base = reinterpret_cast<std::uintptr_t>(REX::W32::GetModuleHandleW(nullptr));
		if (!g_base) {
			return Refuse("image", "reason=no_module");
		}
		const auto nt = g_base + *reinterpret_cast<const std::int32_t*>(g_base + 0x3C);
		if (*reinterpret_cast<const std::uint32_t*>(nt) != 0x00004550 ||               // "PE\0\0"
			*reinterpret_cast<const std::uint16_t*>(nt + 0x18) != 0x20B) {              // PE32+
			return Refuse("image", "reason=not_pe32plus");
		}
		g_imageSize = *reinterpret_cast<const std::uint32_t*>(nt + 0x18 + 0x38);       // SizeOfImage
		REX::INFO("step=image base={} size={}", Hex(g_base), Hex(g_imageSize));
		return true;
	}

	bool ReadAddressLibrary(const std::filesystem::path& a_file)
	{
		std::ifstream in(a_file, std::ios::binary);
		if (!in) {
			return Refuse("address_library", std::format("reason=missing file={}", a_file.filename().string()));
		}
		std::array<std::uint8_t, kHeaderBytes> head{};
		in.read(reinterpret_cast<char*>(head.data()), head.size());
		if (!in) {
			return Refuse("address_library", "reason=short_header");
		}
		const auto u32 = [&](std::size_t a_at) {
			std::uint32_t v;
			std::memcpy(&v, head.data() + a_at, sizeof v);
			return v;
		};
		// format, game version [4], name [64], pointer size, data format, offset count (libxse HEADER_V5)
		const auto format = u32(0);
		const REL::Version version{ static_cast<std::uint16_t>(u32(4)), static_cast<std::uint16_t>(u32(8)),
			static_cast<std::uint16_t>(u32(12)), static_cast<std::uint16_t>(u32(16)) };
		const auto pointerSize = u32(84);
		const auto count = u32(92);
		REX::INFO("step=address_library file={} format={} version={} pointer_size={} count={}", a_file.filename().string(),
			format, version.string(), pointerSize, count);
		if (format != 5 || version != kRuntime || pointerSize != 8) {
			return Refuse("address_library", "reason=header (format 5, version 1.16.244.0 and pointer size 8 expected)");
		}
		for (std::size_t i = 0; i < IdCount(); ++i) {
			const auto& id = kIds[i];
			if (id.id >= count) {
				return Refuse("id", std::format("name={} id={} reason=beyond_count count={}", id.name, id.id, count));
			}
			std::uint32_t offset = 0;
			in.seekg(static_cast<std::streamoff>(kHeaderBytes + 4ull * id.id));
			in.read(reinterpret_cast<char*>(&offset), sizeof offset);
			if (!in) {
				return Refuse("id", std::format("name={} id={} reason=short_file", id.name, id.id));
			}
			if (!offset) {
				return Refuse("id", std::format("name={} id={} reason=missing", id.name, id.id));
			}
			if (offset >= g_imageSize) {
				return Refuse("id", std::format("name={} id={} rva={} reason=outside_image", id.name, id.id, Hex(offset)));
			}
			g_rva[i] = offset;
			REX::INFO("step=id name={} id={} rva={} source={}", id.name, id.id, Hex(offset), id.source);
		}
		// the same ids through libxse (the lookups RE::UI and BSFixedString make): same file, same offsets
		for (std::size_t i = 0; i < IdCount(); ++i) {
			const auto viaLibrary = REL::ID(kIds[i].id).offset();
			if (viaLibrary != g_rva[i]) {
				return Refuse("id", std::format("name={} id={} reason=library_mismatch file={} libxse={}", kIds[i].name,
					kIds[i].id, Hex(g_rva[i]), Hex(viaLibrary)));
			}
		}
		return true;
	}

	bool CheckVtable(std::size_t a_id, std::uint32_t a_subobject, std::string_view a_which)
	{
		const auto vt = Address(a_id);
		if (!InImage(vt - 8, 8 + kSlots * 8)) {
			return Refuse("rtti", std::format("vtable={} reason=outside_image", a_which));
		}
		const auto col = *reinterpret_cast<const std::uintptr_t*>(vt - 8);
		if (!InImage(col, 0x14)) {
			return Refuse("rtti", std::format("vtable={} reason=locator_outside_image locator={}", a_which, Hex(col)));
		}
		const auto signature = *reinterpret_cast<const std::uint32_t*>(col);
		const auto offset = *reinterpret_cast<const std::uint32_t*>(col + 0x04);
		const auto typeDescriptor = g_base + *reinterpret_cast<const std::uint32_t*>(col + 0x0C);
		if (signature != 1 || offset != a_subobject) {
			return Refuse("rtti", std::format("vtable={} reason=locator signature={} offset={} expected_offset={}", a_which,
				signature, Hex(offset), Hex(a_subobject)));
		}
		if (!InImage(typeDescriptor + 0x10, sizeof kTypeName)) {
			return Refuse("rtti", std::format("vtable={} reason=type_outside_image", a_which));
		}
		const auto* name = reinterpret_cast<const char*>(typeDescriptor + 0x10);
		if (std::memcmp(name, kTypeName, sizeof kTypeName) != 0) {
			std::string seen;
			for (std::size_t i = 0; i < 48 && InImage(typeDescriptor + 0x10 + i, 1) && name[i]; ++i) {
				seen += (name[i] >= 0x20 && name[i] < 0x7F) ? name[i] : '?';
			}
			return Refuse("rtti", std::format("vtable={} reason=type type={}", a_which, seen));
		}
		if (typeDescriptor != Address(kRtti)) {
			return Refuse("rtti", std::format("vtable={} reason=type_descriptor locator={} rtti_id={}", a_which,
				Hex(typeDescriptor - g_base), Hex(g_rva[kRtti])));
		}
		REX::INFO("step=rtti vtable={} offset={} type={}", a_which, Hex(offset), kTypeName);
		return true;
	}

	bool CheckSlots()
	{
		const auto* slot = reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary));
		const auto  want = [&](std::size_t a_slot, std::size_t a_id, std::string_view a_what) {
            if (slot[a_slot] == Address(a_id)) {
				return true;
			}
			return Refuse("slots", std::format("slot={} what={} have={} want={}", Hex(a_slot), a_what,
				InImage(slot[a_slot], 1) ? Hex(slot[a_slot] - g_base) : Hex(slot[a_slot]), Hex(g_rva[a_id])));
		};
		if (!want(0x00, kDtor, "scalar_deleting_dtor") || !want(0x06, kLoadMovie, "LoadMovie") ||
			!want(0x08, kProcessMessage, "ProcessMessage") || !want(0x0A, kIsMovieLoaded, "IsMovieLoaded")) {
			return false;
		}
		if (g_rva[kLoadMovie] != kLoadMovieRva) {
			return Refuse("slots", std::format("what=LoadMovie rva={} sfse_hook_rva={}", Hex(g_rva[kLoadMovie]), Hex(kLoadMovieRva)));
		}
		if (slot[0x03] != slot[0x04]) {
			return Refuse("slots", "what=GetName_GetRootPath reason=not_one_pure_virtual_stub");
		}
		std::string all;
		for (std::size_t i = 0; i <= 0x1A; ++i) {
			all += std::format("{}{}", i ? "," : "", InImage(slot[i], 1) ? Hex(slot[i] - g_base) : "outside");
		}
		REX::INFO("step=slots dtor=ok load_movie=ok process_message=ok is_movie_loaded=ok slot5_pure={} rvas={}",
			slot[0x05] == slot[0x03] ? "yes" : "no", all);
		return true;
	}

	bool CheckCtor()
	{
		const auto ctor = Address(kCtor);
		if (!InImage(ctor, kCtorScan + 7)) {
			return Refuse("ctor", "reason=outside_image");
		}
		const auto* code = reinterpret_cast<const std::uint8_t*>(ctor);
		for (std::size_t i = 0; i + 7 <= kCtorScan; ++i) {
			// lea r64, [rip+disp32]: REX.W (0x48-0x4F), 0x8D, ModRM mod=00 rm=101
			if ((code[i] & 0xF8) == 0x48 && code[i + 1] == 0x8D && (code[i + 2] & 0xC7) == 0x05) {
				std::int32_t disp;
				std::memcpy(&disp, code + i + 3, sizeof disp);
				if (ctor + i + 7 + static_cast<std::intptr_t>(disp) == Address(kVtblPrimary)) {
					REX::INFO("step=ctor rva={} vtable_ref_at={} precedent_offset={}", Hex(g_rva[kCtor]), Hex(i),
						g_rva[kCtor] == kPrecedentCtorRva ? "match" : "differs");
					return true;
				}
			}
		}
		return Refuse("ctor", std::format("rva={} reason=no_primary_vtable_reference first={}", Hex(g_rva[kCtor]), Hex(kCtorScan)));
	}

	// stage c: each Value function's offset is SFSE 0.2.21's own address for it, and each RTTI id names its type
	bool CheckChannelIds()
	{
		for (const auto& [id, rva] : kSfseRvas) {
			if (g_rva[id] != rva) {
				return Refuse("channel_ids", std::format("name={} rva={} sfse_rva={}", kIds[id].name, Hex(g_rva[id]), Hex(rva)));
			}
		}
		for (const auto& [id, tail] : kRttiNames) {
			const auto name = TypeNameAt(Address(id));
			if (!NameIs(name, tail)) {
				return Refuse("channel_ids", std::format("name={} type={} expected=.?AV{}", kIds[id].name,
					name.empty() ? "unreadable" : name, tail));
			}
		}
		REX::INFO("step=channel_ids value_functions=sfse_equal rtti_names=ok");
		return true;
	}

	// stage d: the data handler's id and the form lookup's id are SFSE 0.2.21's own addresses for them
	bool CheckPageIds()
	{
		for (const auto& [id, rva] : { std::pair{ kDataHandlerSingleton, kDataHandlerRva }, std::pair{ kLookupById, kLookupByIdRva } }) {
			if (g_rva[id] != rva) {
				return Refuse("page_ids", std::format("name={} rva={} sfse_rva={}", kIds[id].name, Hex(g_rva[id]), Hex(rva)));
			}
		}
		REX::INFO("step=page_ids data_handler=sfse_equal lookup_by_id=sfse_equal");
		return true;
	}

	bool CheckEverything(const std::filesystem::path& a_dir)
	{
		if (!CheckImage() || !ReadAddressLibrary(a_dir / "versionlib-1-16-244-0.bin") ||
			!CheckVtable(kVtblPrimary, 0x00, "primary") || !CheckVtable(kVtblInput, 0x10, "BSInputEventUser") ||
			!CheckVtable(kVtblSink, 0x50, "BSTEventSink") || !CheckSlots() || !CheckCtor() ||
			(g_stage >= 3 && !CheckChannelIds()) || (g_stage >= 4 && !CheckPageIds())) {
			return false;
		}
		const auto* engine = reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary));
		g_vtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary) - 8);   // checked by CheckVtable
		std::copy_n(engine, kSlots, g_vtbl.slots.begin());
		g_ctor = reinterpret_cast<Ctor_t>(Address(kCtor));
		g_engineDtor = reinterpret_cast<Dtor_t>(engine[0x00]);
		g_engineLoadMovie = reinterpret_cast<LoadMovie_t>(engine[0x06]);
		g_engineProcessMessage = reinterpret_cast<ProcessMessage_t>(engine[0x08]);
		g_vtbl.slots[0x00] = reinterpret_cast<std::uintptr_t>(&MenuDestroy);
		g_vtbl.slots[0x03] = reinterpret_cast<std::uintptr_t>(&MenuGetName);
		g_vtbl.slots[0x04] = reinterpret_cast<std::uintptr_t>(&MenuGetRootPath);
		g_vtbl.slots[0x05] = reinterpret_cast<std::uintptr_t>(&MenuGetViewScaleMode);
		g_vtbl.slots[0x06] = reinterpret_cast<std::uintptr_t>(&MenuLoadMovie);
		g_vtbl.slots[0x08] = reinterpret_cast<std::uintptr_t>(&MenuProcessMessage);
		if (g_stage >= 4) {   // FAL-414: copy the input vtable, replace [01] ShouldHandleEvent and [08] OnButtonEvent
			const auto* input = reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput));
			g_inputVtbl.locator = *reinterpret_cast<const std::uintptr_t*>(Address(kVtblInput) - 8);   // checked by CheckVtable
			std::copy_n(input, kInputSlots, g_inputVtbl.slots.begin());
			if (!InImage(input[1], 1) || !InImage(input[8], 1)) {
				return Refuse("slots", "what=input_vtable reason=slot_outside_image");
			}
			g_engineShouldHandle = reinterpret_cast<decltype(g_engineShouldHandle)>(input[1]);
			g_engineOnButton = reinterpret_cast<decltype(g_engineOnButton)>(input[8]);
			g_inputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&MenuShouldHandleEvent);
			g_inputVtbl.slots[8] = reinterpret_cast<std::uintptr_t>(&MenuOnButtonEvent);
			REX::INFO("step=input_vtable replaced=0x01,0x08 should_handle={} on_button={} cancel_codes={}", Hex(input[1] - g_base),
				Hex(input[8] - g_base), g_cancelCount);
		}
		if (g_stage == 1) {
			g_vtbl.slots[0x0A] = reinterpret_cast<std::uintptr_t>(&MenuIsMovieLoaded);
		}
		REX::INFO("step=ready stage={} replaced=0x00,0x03,0x04,0x05,0x06,0x08{} locator={}",
			g_stage == 1 ? "a" : g_stage == 2 ? "b" : g_stage == 3 ? "c" : g_stage == 4 ? "d" : "e", g_stage == 1 ? ",0x0A" : "",
			Hex(g_vtbl.locator - g_base));
		return true;
	}

	// ------------------------------------------------------------------------------------------- open, close, state
	void Toggle(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			REX::ERROR("refuse step=toggle n={} reason=no_ui_or_queue", a_n);
			return;
		}
		const bool open = ui->IsMenuOpen(MenuName());
		g_cancelHeld = false;   // FAL-414: a release heard while the page was closed must not keep the gate shut
		if (g_stage == 4 && !open) {
			PageCollect();   // the page's text before the show
		}
		if (g_stage == 5 && !open) {
			KitCollect();    // the kit's screen before the show
		}
		g_expectOpen = open ? 0 : 1;
		queue->AddMessage(MenuName(), open ? RE::UI_MESSAGE_TYPE::kHide : RE::UI_MESSAGE_TYPE::kShow);
		REX::INFO("step=toggle n={} was_open={} sent={}", a_n, open ? 1 : 0, open ? "hide" : "show");
	}

	// stage d: the CLOSE button, heard on the menu's thread, closes the menu here, on the main thread, as F10 does
	void Close(std::uint32_t a_n, const char* a_by = "button")
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			REX::ERROR("refuse step=close n={} reason=no_ui_or_queue", a_n);
			return;
		}
		const bool open = ui->IsMenuOpen(MenuName());
		g_cancelHeld = false;   // FAL-414: every close clears the cancel gate
		g_expectOpen = 0;
		if (open) {
			queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kHide);
		}
		REX::INFO("step=close n={} by={} was_open={} sent={}", a_n, a_by, open ? 1 : 0, open ? "hide" : "none");
	}

	void CheckState(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			return;
		}
		const int open = ui->IsMenuOpen(MenuName()) ? 1 : 0;
		const int expected = g_expectOpen;
		g_open = open == 1;
		REX::INFO("step=state n={} open={} expected={} match={}", a_n, open, expected, open == expected ? "yes" : "no");
		if (g_stage >= 3) {
			Snapshot(open ? "main_after_open" : "main_after_close", true);
		}
	}

	// stages c, d and e, every 500 ms while the menu is open (and at once after NEXT TAB or a kit move): one kUpdate, on
	// which our ProcessMessage refreshes the field, the page or the kit; their text is collected here first
	void SendUpdate()
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue || !ui->IsMenuOpen(MenuName())) {
			g_open = false;
			return;
		}
		if (g_stage == 4) {
			PageCollect();
		}
		if (g_stage == 5) {
			KitCollect();
		}
		queue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kUpdate);
	}

	bool GameInFront()
	{
		std::uint32_t pid = 0;
		W32_IMPL_GetWindowThreadProcessId(W32_IMPL_GetForegroundWindow(), &pid);
		return pid == W32_IMPL_GetCurrentProcessId();
	}

	std::uint32_t KeyThread(void*)
	{
		std::uint32_t presses = 0;
		std::uint32_t ticks = 0;
		bool          down = false;
		bool          snapDown = false;
		std::array<std::uint32_t, 6> kitHeld{};   // stage e: how many 30 ms ticks each kit key has been held
		for (;;) {
			REX::W32::Sleep(30);
			const bool now = (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_key)) & 0x8000) != 0;
			if (now && !down && GameInFront()) {
				const auto n = ++presses;
				g_task->AddTask([n]() { Toggle(n); });
				REX::W32::Sleep(750);   // the engine handles the message on a later frame
				g_task->AddTask([n]() { CheckState(n); });
			}
			down = now;
			if (g_stage < 3) {
				continue;
			}
			if (g_stage == 5) {   // the kit's keys, only while the page is open and the game in front
				if (g_open && GameInFront()) {
					KitKeys(kitHeld);
				} else {
					kitHeld.fill(0);
				}
			}
			if (g_stage >= 4) {   // the buttons (and the kit's moves), heard on the menu's thread; a close counts as a press
				if (g_refreshNow.exchange(false)) {   // SendUpdate sends nothing once the menu is closed
					g_task->AddTask([]() { SendUpdate(); });
				}
				if (g_closeNow.exchange(false)) {
					const auto n = ++presses;
					g_task->AddTask([n]() { Close(n); });
					REX::W32::Sleep(750);
					g_task->AddTask([n]() { CheckState(n); });
				}
				if (g_cancelNow.exchange(false)) {   // Tab or Esc heard by our input handler (FAL-414)
					const auto n = ++presses;
					g_task->AddTask([n]() { Close(n, "cancel"); });
					REX::W32::Sleep(750);
					g_task->AddTask([n]() { CheckState(n); });
				}
			}
			// stage c: the snapshot key (a main-thread snapshot, the control), and the refresh while open
			const bool snap = g_snapshotKey && (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_snapshotKey)) & 0x8000) != 0;
			if (snap && !snapDown && GameInFront()) {
				g_task->AddTask([]() { Snapshot("key", true); });
			}
			snapDown = snap;
			if (g_open && ++ticks % 17 == 0) {   // 17 x 30 ms
				g_task->AddTask([]() { SendUpdate(); });
			}
		}
	}

	void Register()
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui) {
			Refuse("register", "reason=no_ui");
			return;
		}
		if (ui->IsMenuRegistered(MenuName())) {
			Refuse("register", "reason=name_taken");
			return;
		}
		ui->RegisterMenu(kMenuName, &Create);
		if (!ui->IsMenuRegistered(MenuName())) {
			Refuse("register", "reason=not_taken");
			return;
		}
		g_registered = true;
		const auto hooked = *reinterpret_cast<const std::uint8_t*>(Address(kLoadMovie)) == 0xE9;   // SFSE's branch
		REX::INFO("step=register result=ok name={} load_movie_hooked_by_sfse={}", kMenuName, hooked ? "yes" : "no");
		World::Start(g_task);
		const auto thread = REX::W32::CreateThread(nullptr, 0, &KeyThread, nullptr, 0, nullptr);
		if (!thread) {
			Refuse("key_thread", "reason=create_failed");
			return;
		}
		REX::W32::CloseHandle(thread);
		REX::INFO("step=key_thread key={}{}", Hex(g_key), g_stage >= 3 ? std::format(" snapshot_key={}", Hex(g_snapshotKey)) : "");
	}

	void OnMovieCreated(RE::IMenu* a_menu)
	{
		World::OnMovieCreated(a_menu);
		if (IsOurs(a_menu)) {
			REX::INFO("step=sfse_movie_created menu={} movie={}", Hex(reinterpret_cast<std::uintptr_t>(a_menu)),
				Hex(reinterpret_cast<std::uintptr_t>(MovieOf(a_menu))));
		}
	}

	void OnMessage(SFSE::MessagingInterface::Message* a_msg)
	{
		if (a_msg && a_msg->type == SFSE::MessagingInterface::kPostDataLoad) {
			REX::INFO("step=post_data_load");
			g_task->AddTask([]() { Register(); });   // the first main-thread task after game data loaded
		}
	}

	std::uint32_t ReadNumber(const std::filesystem::path& a_ini, const wchar_t* a_key, std::uint32_t a_default)
	{
		std::array<wchar_t, 64> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, L"", text.data(), static_cast<std::uint32_t>(text.size()),
			a_ini.c_str());
		return text[0] ? static_cast<std::uint32_t>(std::wcstoul(text.data(), nullptr, 0)) : a_default;   // 0x.. or decimal
	}

	// a value as ASCII; any other character as '?'
	std::string ReadText(const std::filesystem::path& a_ini, const wchar_t* a_key)
	{
		std::array<wchar_t, 160> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, L"", text.data(), static_cast<std::uint32_t>(text.size()),
			a_ini.c_str());
		std::string out;
		for (const wchar_t* at = text.data(); *at; ++at) {
			out += (*at > 0x20 && *at < 0x7F) ? static_cast<char>(*at) : '?';
		}
		return out;
	}

	// stage c, FAL-246: ClickCall=<script>.<function>, two Papyrus names of up to 64 letters, digits and '_' (no digit
	// first); "" = off. False if malformed
	bool ParseClickCall(std::string_view a_call)
	{
		const auto name = [](std::string_view a_name) {
			if (a_name.empty() || a_name.size() > kMaxName || (a_name[0] >= '0' && a_name[0] <= '9')) {
				return false;
			}
			for (const char c : a_name) {
				if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_')) {
					return false;
				}
			}
			return true;
		};
		if (a_call.empty()) {
			return true;
		}
		const auto dot = a_call.find('.');
		if (dot == std::string_view::npos || !name(a_call.substr(0, dot)) || !name(a_call.substr(dot + 1))) {
			return false;
		}
		g_clickScript = a_call.substr(0, dot);
		g_clickFunction = a_call.substr(dot + 1);
		return true;
	}

	// stage c: FlagSets=<n>,<n>,..., stages d and e: PageFlagSets (up to four, 0x.. or decimal); open k uses entry
	// (k - 1) mod count
	void ReadFlagSets(const std::filesystem::path& a_ini, const wchar_t* a_key, const wchar_t* a_default)
	{
		std::array<wchar_t, 256> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, a_default, text.data(),
			static_cast<std::uint32_t>(text.size()), a_ini.c_str());
		const wchar_t* at = text.data();
		while (*at && g_flagSetCount < kMaxFlagSets) {
			wchar_t*   end = nullptr;
			const auto value = std::wcstoul(at, &end, 0);
			if (end == at) {
				break;
			}
			g_flagSets[g_flagSetCount++] = static_cast<std::uint32_t>(value);
			at = end;
			while (*at == L',' || *at == L' ') {
				++at;
			}
		}
	}
}

SFSE_PLUGIN_LOAD(const SFSE::LoadInterface* a_sfse)
{
	SFSE::Init(a_sfse, { .trampoline = false, .hook = false });

	std::array<wchar_t, 1024> path{};
	const auto len = REX::W32::GetModuleFileNameW(REX::W32::GetCurrentModule(), path.data(), static_cast<std::uint32_t>(path.size()));
	const auto dir = std::filesystem::path(std::wstring(path.data(), len)).parent_path();
	const auto ini = dir / "FO4SFPipboyMenu.ini";
	g_stage = static_cast<int>(ReadNumber(ini, L"Stage", 0));
	g_key = ReadNumber(ini, L"Key", 0x79);
	g_flags = ReadNumber(ini, L"Flags", 0);
	g_keepAlive = ReadNumber(ini, L"KeepAlive", 1) != 0;
	// FAL-414: up to four keyboard ids that close the menu while it is open (0 = unused)
	g_cancelCodes = { ReadNumber(ini, L"CancelCode1", 0x1B), ReadNumber(ini, L"CancelCode2", 0x09), ReadNumber(ini, L"CancelCode3", 0),
		ReadNumber(ini, L"CancelCode4", 0) };
	g_cancelCount = 4;
	while (g_cancelCount && g_cancelCodes[g_cancelCount - 1] == 0) {
		--g_cancelCount;
	}
	const auto runtime = a_sfse->RuntimeVersion();
	REX::INFO("step=load runtime={} stage={} key={} flags={} keep_alive={}", runtime.string(), g_stage, Hex(g_key),
		Hex(g_flags), g_keepAlive ? 1 : 0);

	// true in every case: a plugin that stays loaded and idle leaves its refusal line, the finding the job card reads
	if (g_stage < 1 || g_stage > 5) {
		REX::INFO("step=off (Stage=1, 2, 3, 4 or 5 in FO4SFPipboyMenu.ini to probe)");
		return true;
	}
	std::string clickCall;
	bool        clickCallOk = true;
	if (g_stage >= 3) {
		g_snapshotKey = ReadNumber(ini, L"SnapshotKey", 0x7A);
		if (g_stage >= 4) {   // (d) and (e)
			ReadFlagSets(ini, L"PageFlagSets", L"0x19");   // FAL-414: bit 4 (0x10) puts StopContextProcessing (78) on the control map stack, so Tab arrives as Cancel
		} else {
			ReadFlagSets(ini, L"FlagSets", L"0x0,0x8,0x9");
			clickCall = ReadText(ini, L"ClickCall");
			clickCallOk = ParseClickCall(clickCall);
		}
		std::string sets;
		for (std::size_t i = 0; i < g_flagSetCount; ++i) {
			sets += std::format("{}{}", i ? "," : "", Hex(g_flagSets[i]));
		}
		REX::INFO("step=load_{} flag_sets={} snapshot_key={} click_call={}", g_stage == 5 ? "e" : g_stage == 4 ? "d" : "c",
			sets.empty() ? "none" : sets, Hex(g_snapshotKey), clickCall.empty() ? "none" : clickCall);
	}
	if (runtime != kRuntime) {
		Refuse("version", std::format("runtime={} expected={}", runtime.string(), kRuntime.string()));
		return true;
	}
	if (g_key == 0 || g_key > 0xFE) {
		Refuse("ini", std::format("key={}", Hex(g_key)));
		return true;
	}
	if (g_stage >= 3 && (g_snapshotKey > 0xFE || g_snapshotKey == g_key)) {
		Refuse("ini", std::format("snapshot_key={} key={}", Hex(g_snapshotKey), Hex(g_key)));
		return true;
	}
	if (!clickCallOk) {
		Refuse("ini", std::format("click_call={} (<script>.<function>: two Papyrus names, or empty)", clickCall));
		return true;
	}
	if (g_stage == 5 && (!ReadKitKeys(ini) || !ReadKit(ini))) {   // the kit's keys and pages, before any check of the game
		return true;
	}
	if (!CheckEverything(dir)) {
		return true;
	}
	World::Configure(ini, g_stage, g_key, g_base, g_imageSize);
	const auto messaging = SFSE::GetMessagingInterface();
	g_task = SFSE::GetTaskInterface();
	if (!messaging || !g_task || !messaging->RegisterListener(&OnMessage)) {
		Refuse("listen", std::format("messaging={} task={}", messaging ? 1 : 0, g_task ? 1 : 0));
		return true;
	}
	if (const auto menus = SFSE::GetMenuInterface()) {
		menus->Register(&OnMovieCreated);
	}
	REX::INFO("step=listen (the menu registers on the first main-thread task after PostDataLoad)");
	return true;
}
