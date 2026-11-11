// FO4SFPipboyMenu world surface (FAL-250; README.md, "World surface"). Can the movie #704 showed as a centred overlay
// be drawn on a surface in the world? The overlay stays the control (Stage=2, its own key). World=1 adds two things:
//   - a census: once, every menu name the UI has registered; then every menu whose movie SFSE's own IMenu::LoadMovie
//     hook reports, once per name and flag set: name, class (by its RTTI), flags, movie, and the result (a movie or
//     none after the engine's loader returned). That is the dump the world candidate is chosen from: libxse leaves
//     the engine's menu flags unnamed, and no file in Git says which menu draws on a mesh;
//   - the world candidate: WorldKey sends show, then hide, to WorldMenu, one vanilla menu named from the census, whose
//     movie only the probe archive replaces, with an identical twin of ours (make_pipboy_probe.py twin; the twin's
//     path is WorldMovie, logged as staged). A state line follows every send; a name that is not registered is one
//     refuse line and nothing is sent.
// Read only: the menu map, the menus SFSE hands over, their vtables and RTTI (every address inside Starfield.exe's
// image, checked before it is read). Called: only what the overlay key already calls, UI::IsMenuOpen and
// UIMessageQueue::AddMessage, plus one BSFixedString for the candidate's name. No hook, no engine object changed.

#include "pch.h"

#include "world.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <mutex>
#include <set>

// as main.cpp: Win32 calls that libxse's REX::W32 does not wrap (libxse refuses a <windows.h> included before it)
REX_W32_IMPORT(std::int16_t, GetAsyncKeyState, std::int32_t);
REX_W32_IMPORT(void*, GetForegroundWindow);
REX_W32_IMPORT(std::uint32_t, GetWindowThreadProcessId, void*, std::uint32_t*);
REX_W32_IMPORT(std::uint32_t, GetCurrentProcessId);

namespace
{
	using namespace std::string_view_literals;

	constexpr auto        kOurMenu = "FO4SF_PipboyMenu"sv;
	constexpr std::size_t kMaxRegistered = 512;   // census lines when our menu registers
	constexpr std::size_t kMaxMovies = 256;       // census lines from SFSE's callback (distinct name and flags)
	constexpr std::size_t kMaxWorldLoads = 32;    // step=world_load_movie lines
	constexpr std::size_t kNameMax = 64;
	constexpr std::size_t kMovieMax = 160;
	constexpr std::size_t kMenuOffsetDepth = 0x110;   // the byte main.cpp's step=create logs as depth

	// census names worth a second look for a movie on a mesh, lower case (FAL-248 `wrist-pipboy` section 2.3)
	constexpr std::array kLeads{ "test"sv, "dynamic"sv, "textur"sv, "geo"sv, "terminal"sv, "kiosk"sv, "cockpit"sv,
		"screen"sv, "monitor"sv, "display"sv, "watch"sv, "slate"sv, "3d"sv };

	bool                       g_on = false;
	std::uintptr_t             g_base = 0;
	std::size_t                g_imageSize = 0;
	std::uint32_t              g_key = 0x77;   // F8
	std::string                g_menu;         // WorldMenu; empty: census only
	std::string                g_movie;        // WorldMovie: the twin's path in the probe archive, as staged
	const SFSE::TaskInterface* g_task = nullptr;
	std::atomic<int>           g_expectOpen{ -1 };
	std::atomic<std::uint32_t> g_worldLoads{ 0 };
	std::mutex                 g_seenLock;
	std::set<std::string>      g_seen;         // name|flags already in the census
	bool                       g_seenFull = false;

	std::string Hex(std::uintptr_t a_value) { return std::format("{:#x}", a_value); }

	bool InImage(std::uintptr_t a_addr, std::size_t a_len)
	{
		return a_addr >= g_base && a_len <= g_imageSize && a_addr - g_base <= g_imageSize - a_len;
	}

	std::string Rva(std::uintptr_t a_addr) { return InImage(a_addr, 1) ? Hex(a_addr - g_base) : "outside_image"; }

	// a string for the log: printable ASCII, at most a_max characters, "?" for anything else, "none" when empty
	std::string Printable(std::string_view a_text, std::size_t a_max)
	{
		std::string out;
		for (const char c : a_text.substr(0, a_max)) {
			out += (c >= 0x20 && c < 0x7F && c != ' ') ? c : '?';
		}
		return out.empty() ? "none" : out;
	}

	bool IsLead(std::string_view a_name)
	{
		std::string lower(a_name);
		std::ranges::transform(lower, lower.begin(), [](unsigned char a_c) { return static_cast<char>(std::tolower(a_c)); });
		return std::ranges::any_of(kLeads, [&](std::string_view a_lead) { return lower.find(a_lead) != std::string::npos; });
	}

	// the class of an object whose primary vtable lies in the image: the decorated type name its RTTI complete object
	// locator points at (the reads main.cpp's CheckVtable makes, every address checked first). Our own menu's vtable is
	// a copy in our dll: outside_image
	std::string ClassOf(const void* a_object)
	{
		const auto vtable = *static_cast<const std::uintptr_t*>(a_object);
		if (!InImage(vtable - 8, 8)) {
			return "outside_image";
		}
		const auto locator = *reinterpret_cast<const std::uintptr_t*>(vtable - 8);
		if (!InImage(locator, 0x14) || *reinterpret_cast<const std::uint32_t*>(locator) != 1) {
			return "no_locator";
		}
		const auto type = g_base + *reinterpret_cast<const std::uint32_t*>(locator + 0x0C);
		std::string name;
		for (std::size_t i = 0; i < kNameMax && InImage(type + 0x10 + i, 1); ++i) {
			const char c = *reinterpret_cast<const char*>(type + 0x10 + i);
			if (!c) {
				return name.empty() ? "no_name" : name;
			}
			name += (c >= 0x20 && c < 0x7F) ? c : '?';
		}
		return name.empty() ? "no_name" : name + "...";
	}

	// one menu object as the census logs it
	std::string Describe(const RE::IMenu* a_menu)
	{
		const auto base = reinterpret_cast<std::uintptr_t>(a_menu);
		return std::format("class={} flags={} movie={} depth={}", ClassOf(a_menu), Hex(a_menu->flags),
			Hex(reinterpret_cast<std::uintptr_t>(a_menu->uiMovie.get())),
			Hex(*reinterpret_cast<const std::uint8_t*>(base + kMenuOffsetDepth)));
	}

	// ------------------------------------------------------------------------------------------- census
	void CensusRegistered(RE::UI* a_ui)
	{
		std::size_t n = 0;
		bool        truncated = false;
		std::string leads;
		for (const auto& entry : a_ui->menuMap) {
			if (n == kMaxRegistered) {
				truncated = true;
				break;
			}
			const auto  name = Printable(entry.key.c_str(), kNameMax);
			const auto* menu = entry.value.menu.get();
			REX::INFO("step=census_registered n={} menu={} create={} instance={}{}{}", ++n, name,
				Rva(reinterpret_cast<std::uintptr_t>(entry.value.initFunc)), menu ? 1 : 0, menu ? " " : "",
				menu ? Describe(menu) : "");
			if (IsLead(name)) {
				leads += (leads.empty() ? "" : ",") + name;
			}
		}
		REX::INFO("step=census_registered_done count={} truncated={} leads={}", n, truncated ? 1 : 0,
			leads.empty() ? "none" : leads);
	}

	// ------------------------------------------------------------------------------------------- the world candidate
	const RE::BSFixedString& WorldName()
	{
		// process lifetime, made on the main thread at the first press (a BSFixedString destructor calls the engine)
		static auto* const name = new RE::BSFixedString(g_menu.c_str());
		return *name;
	}

	void Toggle(std::uint32_t a_n)
	{
		if (g_menu.empty()) {
			REX::ERROR("refuse step=world_toggle n={} reason=no_world_menu (census only; WorldMenu= a name from "
					   "step=census_registered)",
				a_n);
			return;
		}
		auto* ui = RE::UI::GetSingleton();
		auto* queue = RE::UIMessageQueue::GetSingleton();
		if (!ui || !queue) {
			REX::ERROR("refuse step=world_toggle n={} menu={} reason=no_ui_or_queue", a_n, g_menu);
			return;
		}
		if (!ui->IsMenuRegistered(WorldName())) {
			REX::ERROR("refuse step=world_toggle n={} menu={} reason=not_registered", a_n, g_menu);
			return;
		}
		const bool open = ui->IsMenuOpen(WorldName());
		g_expectOpen = open ? 0 : 1;
		queue->AddMessage(WorldName(), open ? RE::UI_MESSAGE_TYPE::kHide : RE::UI_MESSAGE_TYPE::kShow);
		REX::INFO("step=world_toggle n={} menu={} was_open={} sent={} movie_file={}", a_n, g_menu, open ? 1 : 0,
			open ? "hide" : "show", g_movie.empty() ? "none" : g_movie);
	}

	void State(std::uint32_t a_n)
	{
		auto* ui = RE::UI::GetSingleton();
		if (!ui || g_menu.empty() || !ui->IsMenuRegistered(WorldName())) {
			return;   // Toggle logged the refusal
		}
		const int   open = ui->IsMenuOpen(WorldName()) ? 1 : 0;
		const int   expected = g_expectOpen;
		const auto* entry = ui->GetMenuEntry(WorldName());
		const auto* menu = entry ? entry->menu.get() : nullptr;
		REX::INFO("step=world_state n={} menu={} open={} expected={} match={} {}", a_n, g_menu, open, expected,
			open == expected ? "yes" : "no", menu ? Describe(menu) : "instance=none");
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
				g_task->AddTask([n]() { State(n); });
			}
			down = now;
		}
	}

	// ------------------------------------------------------------------------------------------- the ini
	std::string ReadText(const std::filesystem::path& a_ini, const wchar_t* a_key)
	{
		std::array<wchar_t, 256> text{};
		REX::W32::GetPrivateProfileStringW(L"FO4SFPipboyMenu", a_key, L"", text.data(), static_cast<std::uint32_t>(text.size()),
			a_ini.c_str());
		std::string out;
		for (const auto c : std::wstring_view(text.data())) {
			out += (c >= 0x20 && c < 0x7F) ? static_cast<char>(c) : '?';
		}
		return out;
	}

	std::uint32_t ReadNumber(const std::filesystem::path& a_ini, const wchar_t* a_key, std::uint32_t a_default)
	{
		const auto text = ReadText(a_ini, a_key);
		return text.empty() ? a_default : static_cast<std::uint32_t>(std::strtoul(text.c_str(), nullptr, 0));   // 0x.. or decimal
	}

	bool OnlyOf(std::string_view a_text, std::string_view a_extra)
	{
		return std::ranges::all_of(a_text, [&](unsigned char a_c) {
			return std::isalnum(a_c) || a_extra.find(static_cast<char>(a_c)) != std::string_view::npos;
		});
	}

	bool Refuse(const std::string& a_what)
	{
		REX::ERROR("refuse step=world {} (the overlay probe runs alone)", a_what);
		return false;
	}

	bool Read(const std::filesystem::path& a_ini, int a_stage, std::uint32_t a_menuKey)
	{
		if (a_stage < 2) {
			return Refuse(std::format("reason=needs_movie_stage stage={}", a_stage));
		}
		g_key = ReadNumber(a_ini, L"WorldKey", 0x77);
		if (g_key == 0 || g_key > 0xFE || g_key == a_menuKey) {
			return Refuse(std::format("reason=key world_key={} key={}", Hex(g_key), Hex(a_menuKey)));
		}
		g_menu = ReadText(a_ini, L"WorldMenu");
		if (g_menu.size() > kNameMax || !OnlyOf(g_menu, "_")) {
			return Refuse(std::format("reason=world_menu world_menu={} (letters, digits and _ only)", Printable(g_menu, kNameMax)));
		}
		auto lower = g_menu;
		std::ranges::transform(lower, lower.begin(), [](unsigned char a_c) { return static_cast<char>(std::tolower(a_c)); });
		if (lower == "fo4sf_pipboymenu") {
			return Refuse(std::format("reason=world_menu_is_ours world_menu={} (the overlay control is {})", g_menu, kOurMenu));
		}
		g_movie = ReadText(a_ini, L"WorldMovie");
		if (g_movie.size() > kMovieMax || !OnlyOf(g_movie, "_./\\-")) {
			return Refuse(std::format("reason=world_movie world_movie={}", Printable(g_movie, kMovieMax)));
		}
		return true;
	}
}

namespace World
{
	void Configure(const std::filesystem::path& a_ini, int a_stage, std::uint32_t a_menuKey, std::uintptr_t a_base,
		std::size_t a_imageSize)
	{
		if (ReadNumber(a_ini, L"World", 0) == 0) {
			return;   // off: no line, the log is #704's
		}
		g_base = a_base;
		g_imageSize = a_imageSize;
		if (!Read(a_ini, a_stage, a_menuKey)) {
			return;
		}
		g_on = true;
		REX::INFO("step=world_config world_key={} world_menu={} world_movie={}", Hex(g_key), g_menu.empty() ? "none" : g_menu,
			g_movie.empty() ? "none" : g_movie);
	}

	void Start(const SFSE::TaskInterface* a_task)
	{
		if (!g_on) {
			return;
		}
		g_task = a_task;
		if (auto* ui = RE::UI::GetSingleton()) {
			CensusRegistered(ui);
		}
		const auto thread = REX::W32::CreateThread(nullptr, 0, &KeyThread, nullptr, 0, nullptr);
		if (!thread) {
			REX::ERROR("refuse step=world_key_thread reason=create_failed");
			return;
		}
		REX::W32::CloseHandle(thread);
		REX::INFO("step=world_key_thread world_key={} world_menu={}", Hex(g_key), g_menu.empty() ? "none" : g_menu);
	}

	void OnMovieCreated(const RE::IMenu* a_menu)
	{
		if (!g_on || !a_menu) {
			return;
		}
		const auto name = Printable(a_menu->menuName.c_str(), kNameMax);
		// SFSE's hook drops the loader's return value: the movie the menu holds afterwards is the result
		const int  result = a_menu->uiMovie.get() ? 1 : 0;
		if (!g_menu.empty() && name == g_menu && g_worldLoads.fetch_add(1) < kMaxWorldLoads) {
			REX::INFO("step=world_load_movie menu={} result={} movie_file={} {}", name, result,
				g_movie.empty() ? "none" : g_movie, Describe(a_menu));
		}
		{
			std::scoped_lock lock(g_seenLock);
			if (g_seenFull) {
				return;
			}
			if (g_seen.size() == kMaxMovies) {
				g_seenFull = true;
				REX::INFO("step=census_movie_full lines={} (later menus are not listed)", kMaxMovies);
				return;
			}
			if (!g_seen.insert(std::format("{}|{}", name, a_menu->flags)).second) {
				return;
			}
		}
		REX::INFO("step=census_movie menu={} result={} {} lead={}", name, result, Describe(a_menu), IsLead(name) ? 1 : 0);
	}
}
