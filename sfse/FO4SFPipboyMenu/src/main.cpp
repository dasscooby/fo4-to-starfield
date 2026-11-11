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
// both) must be inside the image. Reads of engine objects whose layout only libxse states (menu stack, input
// contexts, the pause byte, the position) are guarded: a fault logs "fault" instead of stopping the game.
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

#include "pch.h"

#include <cmath>

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
	constexpr std::size_t   kMenuStackAt = 0x3F0;            // libxse RE::UI::menuStack (BSTArray: size, capacity, data)
	constexpr std::size_t   kMenuFlagsAt = 0xC0;             // libxse RE::IMenu::flags
	constexpr std::size_t   kContextsAt = 0x2A8;             // libxse RE::ControlMap::activeInputContexts (16-byte items)
	constexpr std::size_t   kPositionAt = 0x80 + 0x0C;       // libxse RE::TESObjectREFR::data (0x80), OBJ_REFR::location
	constexpr std::size_t   kMaxListed = 16;                 // menus and contexts listed per snapshot
	constexpr std::size_t   kMaxFlagSets = 4;
	constexpr std::size_t   kGameVmImplAt = 0xE0;            // libxse RE::GameVM::impl (BSTSmartPointer<IVirtualMachine>)
	constexpr std::size_t   kDispatchStaticCallSlot = 0x2F;  // libxse IVirtualMachine::DispatchStaticCall
	constexpr std::size_t   kMaxName = 64;                   // ClickCall: each of the script's and function's names

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

	// INI (FO4SFPipboyMenu.ini next to the dll)
	int           g_stage = 0;      // 0 off, 1 = (a), 2 = (b), 3 = (c)
	std::uint32_t g_key = 0x79;     // F10
	std::uint32_t g_flags = 0;      // OR'ed into the flags the constructor set
	bool          g_keepAlive = true;

	std::uintptr_t                           g_base = 0;
	std::size_t                              g_imageSize = 0;
	std::array<std::uint32_t, kIdCount>      g_rva{};
	PrimaryVtable                            g_vtbl{};
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

	std::uintptr_t Address(std::size_t a_id) { return g_base + g_rva[a_id]; }

	std::size_t IdCount() { return g_stage == 3 ? kIdCount : kIdCountB; }

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

	// the UI menu stack in stored order: each entry's type (ours: "ours") and flags
	std::string ReadMenuStack()
	{
		const auto ui = reinterpret_cast<std::uintptr_t>(RE::UI::GetSingleton());
		ArrayHead stack{};
		if (!ui || !Peek(ui + kMenuStackAt, stack)) {
			return "fault";
		}
		std::string out = std::format("{}[", stack.size);
		for (std::uint32_t i = 0; i < stack.size && i < kMaxListed; ++i) {
			std::uintptr_t menu = 0;
			std::uintptr_t vt = 0;
			std::uint32_t  flags = 0;
			std::string    name = "fault";
			if (Peek(stack.data + 8ull * i, menu) && menu && Peek(menu, vt)) {
				ObjectType type;
				name = vt == reinterpret_cast<std::uintptr_t>(g_vtbl.slots.data()) ? "ours" :
				       TypeOf(menu, type)                                         ? ShortName(type.name) :
				                                                                    "unknown";
			}
			const bool hasFlags = menu && Peek(menu + kMenuFlagsAt, flags);
			out += std::format("{}{}/{}", i ? "," : "", name, hasFlags ? Hex(flags) : "?");
		}
		return out + "]";
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

	// pause state and who holds input, on whichever thread calls it
	void Snapshot(std::string_view a_tag)
	{
		const auto n = ++g_snapshots;
		const auto paused = ReadPaused();
		const auto menus = ReadMenuStack();
		const auto contexts = ReadContexts();
		REX::INFO("step=snapshot n={} tag={} paused={} menus={} contexts={} expected_open={}", n, a_tag, paused, menus,
			contexts, g_expectOpen.load());
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
		if (g_stage == 3 && type == RE::UI_MESSAGE_TYPE::kShow) {
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
		if (g_stage == 3) {   // stage c: after the engine's own handling, on its thread for this menu
			if (type == RE::UI_MESSAGE_TYPE::kShow) {
				ChannelListen(a_self);
				ChannelWrite(a_self, 0);
				Snapshot("show");
			} else if (type == RE::UI_MESSAGE_TYPE::kUpdate) {
				const auto n = ++g_updates;
				ChannelWrite(a_self, n);
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
		// what the engine's dynamic_cast reads on our object: the locator one slot before its primary vtable
		const auto rtti = *reinterpret_cast<const std::uintptr_t*>(*reinterpret_cast<const std::uintptr_t*>(base) - 8) ==
		                  *reinterpret_cast<const std::uintptr_t*>(Address(kVtblPrimary) - 8);
		auto* imenu = static_cast<RE::IMenu*>(menu);
		imenu->menuName = MenuName();
		const auto ctorFlags = imenu->flags;
		const auto extra = g_flags | (g_stage == 3 ? FlagSet(n) : 0);   // stage c: this open's FlagSets entry
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
			g_stage == 3 ? std::format(" set={}", FlagSetIndex(n)) : "");
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

	bool CheckEverything(const std::filesystem::path& a_dir)
	{
		if (!CheckImage() || !ReadAddressLibrary(a_dir / "versionlib-1-16-244-0.bin") ||
			!CheckVtable(kVtblPrimary, 0x00, "primary") || !CheckVtable(kVtblInput, 0x10, "BSInputEventUser") ||
			!CheckVtable(kVtblSink, 0x50, "BSTEventSink") || !CheckSlots() || !CheckCtor() ||
			(g_stage == 3 && !CheckChannelIds())) {
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
		if (g_stage == 1) {
			g_vtbl.slots[0x0A] = reinterpret_cast<std::uintptr_t>(&MenuIsMovieLoaded);
		}
		REX::INFO("step=ready stage={} replaced=0x00,0x03,0x04,0x05,0x06,0x08{} locator={}",
			g_stage == 1 ? "a" : g_stage == 2 ? "b" : "c", g_stage == 1 ? ",0x0A" : "", Hex(g_vtbl.locator - g_base));
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
		g_expectOpen = open ? 0 : 1;
		queue->AddMessage(MenuName(), open ? RE::UI_MESSAGE_TYPE::kHide : RE::UI_MESSAGE_TYPE::kShow);
		REX::INFO("step=toggle n={} was_open={} sent={}", a_n, open ? 1 : 0, open ? "hide" : "show");
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
		if (g_stage == 3) {
			Snapshot(open ? "main_after_open" : "main_after_close");
		}
	}

	// stage c, every 500 ms while the menu is open: one kUpdate, on which our ProcessMessage refreshes the field
	void SendUpdate()
	{
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue || !ui->IsMenuOpen(MenuName())) {
			g_open = false;
			return;
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
			if (g_stage != 3) {
				continue;
			}
			// stage c: the snapshot key (a main-thread snapshot, the control), and the refresh while open
			const bool snap = g_snapshotKey && (W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_snapshotKey)) & 0x8000) != 0;
			if (snap && !snapDown && GameInFront()) {
				g_task->AddTask([]() { Snapshot("key"); });
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
		REX::INFO("step=key_thread key={}{}", Hex(g_key), g_stage == 3 ? std::format(" snapshot_key={}", Hex(g_snapshotKey)) : "");
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

	// stage c: FlagSets=<n>,<n>,... (up to four, 0x.. or decimal); open k uses entry (k - 1) mod count
	void ReadFlagSets(const std::filesystem::path& a_ini)
	{
		std::array<wchar_t, 128> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", L"FlagSets", L"0x0,0x8,0x9", text.data(),
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
	const auto runtime = a_sfse->RuntimeVersion();
	REX::INFO("step=load runtime={} stage={} key={} flags={} keep_alive={}", runtime.string(), g_stage, Hex(g_key),
		Hex(g_flags), g_keepAlive ? 1 : 0);

	// true in every case: a plugin that stays loaded and idle leaves its refusal line, the finding the job card reads
	if (g_stage != 1 && g_stage != 2 && g_stage != 3) {
		REX::INFO("step=off (Stage=1, 2 or 3 in FO4SFPipboyMenu.ini to probe)");
		return true;
	}
	std::string clickCall;
	bool        clickCallOk = true;
	if (g_stage == 3) {
		g_snapshotKey = ReadNumber(ini, L"SnapshotKey", 0x7A);
		ReadFlagSets(ini);
		clickCall = ReadText(ini, L"ClickCall");
		clickCallOk = ParseClickCall(clickCall);
		std::string sets;
		for (std::size_t i = 0; i < g_flagSetCount; ++i) {
			sets += std::format("{}{}", i ? "," : "", Hex(g_flagSets[i]));
		}
		REX::INFO("step=load_c flag_sets={} snapshot_key={} click_call={}", sets.empty() ? "none" : sets, Hex(g_snapshotKey),
			clickCall.empty() ? "none" : clickCall);
	}
	if (runtime != kRuntime) {
		Refuse("version", std::format("runtime={} expected={}", runtime.string(), kRuntime.string()));
		return true;
	}
	if (g_key == 0 || g_key > 0xFE) {
		Refuse("ini", std::format("key={}", Hex(g_key)));
		return true;
	}
	if (g_stage == 3 && (g_snapshotKey > 0xFE || g_snapshotKey == g_key)) {
		Refuse("ini", std::format("snapshot_key={} key={}", Hex(g_snapshotKey), Hex(g_key)));
		return true;
	}
	if (!clickCallOk) {
		Refuse("ini", std::format("click_call={} (<script>.<function>: two Papyrus names, or empty)", clickCall));
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
