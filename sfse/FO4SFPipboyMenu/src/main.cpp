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

#include "pch.h"

// Win32 calls that libxse's REX::W32 does not wrap, imported the way REX/W32.cpp imports its own (REX/W32/BASE.h):
// libxse refuses a <windows.h> included before it
REX_W32_IMPORT(std::int16_t, GetAsyncKeyState, std::int32_t);
REX_W32_IMPORT(void*, GetForegroundWindow);
REX_W32_IMPORT(std::uint32_t, GetWindowThreadProcessId, void*, std::uint32_t*);
REX_W32_IMPORT(std::uint32_t, GetCurrentProcessId);

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
	int           g_stage = 0;      // 0 off, 1 = (a), 2 = (b)
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

	std::uintptr_t Address(std::size_t a_id) { return g_base + g_rva[a_id]; }

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

	// ------------------------------------------------------------------------------------------- the menu's slots
	void* MenuDestroy(void* a_self, std::uint32_t a_flags)
	{
		REX::INFO("step=destroy menu={} flags={}", Hex(reinterpret_cast<std::uintptr_t>(a_self)), a_flags);
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
		if (g_stage == 2 && type == RE::UI_MESSAGE_TYPE::kShow && !MovieOf(a_self)) {
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
		if (g_flags) {
			imenu->flags |= g_flags;
			imenu->flagsUpdated = true;
		}
		if (g_keepAlive && ctorRefs == 1) {
			REX::W32::InterlockedIncrement(refs);   // a public precedent's count: never released to zero
		}
		REX::INFO("step=create n={} menu={} vtables={} rtti={} refcount={} keep_alive={} ctor_flags={} flags={} depth={}", n,
			Hex(base), vtables ? "engine" : "UNEXPECTED", rtti ? "engine" : "UNEXPECTED", ctorRefs, g_keepAlive ? 1 : 0,
			Hex(ctorFlags), Hex(imenu->flags),
			Hex(*reinterpret_cast<const std::uint8_t*>(base + 0x110)));
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
		for (std::size_t i = 0; i < kIdCount; ++i) {
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
		for (std::size_t i = 0; i < kIdCount; ++i) {
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

	bool CheckEverything(const std::filesystem::path& a_dir)
	{
		if (!CheckImage() || !ReadAddressLibrary(a_dir / "versionlib-1-16-244-0.bin") ||
			!CheckVtable(kVtblPrimary, 0x00, "primary") || !CheckVtable(kVtblInput, 0x10, "BSInputEventUser") ||
			!CheckVtable(kVtblSink, 0x50, "BSTEventSink") || !CheckSlots() || !CheckCtor()) {
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
		REX::INFO("step=ready stage={} replaced=0x00,0x03,0x04,0x05,0x06,0x08{} locator={}", g_stage == 1 ? "a" : "b",
			g_stage == 1 ? ",0x0A" : "", Hex(g_vtbl.locator - g_base));
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
		REX::INFO("step=state n={} open={} expected={} match={}", a_n, open, expected, open == expected ? "yes" : "no");
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
		bool          down = false;
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
		const auto thread = REX::W32::CreateThread(nullptr, 0, &KeyThread, nullptr, 0, nullptr);
		if (!thread) {
			Refuse("key_thread", "reason=create_failed");
			return;
		}
		REX::W32::CloseHandle(thread);
		REX::INFO("step=key_thread key={}", Hex(g_key));
	}

	void OnMovieCreated(RE::IMenu* a_menu)
	{
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
	if (g_stage != 1 && g_stage != 2) {
		REX::INFO("step=off (Stage=1 or 2 in FO4SFPipboyMenu.ini to probe)");
		return true;
	}
	if (runtime != kRuntime) {
		Refuse("version", std::format("runtime={} expected={}", runtime.string(), kRuntime.string()));
		return true;
	}
	if (g_key == 0 || g_key > 0xFE) {
		Refuse("ini", std::format("key={}", Hex(g_key)));
		return true;
	}
	if (!CheckEverything(dir)) {
		return true;
	}
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
