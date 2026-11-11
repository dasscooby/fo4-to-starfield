// FOCCSidecar: the P1 probe plugin for SFSE (docs/spikes/combined-core-probes.md, engine-feasibility.md "PC probes").
//
// What it does, and nothing more:
//   - On SFSE's PreSaveGame message it writes a sidecar file for the save name SFSE passes (../codec.h mirrors
//     src/fo4sf/combined/sidecar.py: name rule, canonical JSON, checksum) with the stub world state
//     {"counter": k, "probe": "P1"}, k counting pre-save events in this process.
//   - On PostLoadGame it reads the sidecar for the loaded save back and verifies it.
//   - Every event is appended as one JSON object per line to focc_sidecar.log, which group C's checker reads.
//   - It never deletes anything but its own temp file (SFSE sends no delete message; sidecar.orphans() lists orphans
//     offline).
//   - Kill switch: without `bEnabled=1` under [FOCCSidecar] in FOCCSidecar.ini next to the dll it registers nothing
//     and writes nothing of its own; its SFSE log then reads `step=off`.
//
// Since FAL-216 it is built like FO4SFPipboyMenu (PR #704) and FOCCPing: libxse/commonlibsf 9d090c4 through xmake,
// the same version guard and the same refusal lines. It touches no game address and no game structure, so it reads no
// Address Library id (the commonlibsf.plugin rule still marks it as an Address Library user, so SFSE wants the file in
// the plugin folder, which the probe session installs anyway). Checked before anything is registered:
//   - the runtime is 1.16.244.0 (SFSE's), else nothing but the refusal line;
//   - the kill switch, then the plugin folder and its sidecars\ folder can be created;
//   - SFSE gives a messaging interface and takes the listener.
// Any failure is one "refuse step=<step>" line in FOCCSidecar.log (SFSE's log folder) and the plugin stays idle.
//
// The save and load messages are not in libxse's MessagingInterface enum (it names 0 to 3); their numbers are SFSE's
// own, from the MIT-licensed sfse/PluginAPI.h at 48535cc (lines 103-110): PreSaveGame 4, PostSaveGame 5, PreLoadGame 6,
// PostLoadGame 7. The save-name payload is a const char* with dataLen = strlen (sfse/Hooks_Serialization.cpp, read, not
// copied). Whether that name is the save's display name or its file stem is UNVERIFIED: the log carries the raw bytes
// and their hex so the checker can compare with the .sfs names.
//
// Files (all under <dll folder>\FOCCSidecar\): focc_sidecar.log, sidecars\<name>.focc. The dll folder is found with
// GetModuleFileNameW on this module.

#include "pch.h"

#include <chrono>
#include <fstream>
#include <mutex>

#include "codec.h"

namespace
{
	constexpr REL::Version  kRuntime{ 1, 16, 244, 0 };
	constexpr std::uint32_t kPluginVersion = 2;   // 1 was the PluginAPI.h build of 21-28 Oct 2026

	// sfse/PluginAPI.h (MIT) at 48535cc, SFSEMessagingInterface: kMessage_PreSaveGame .. kMessage_PostLoadGame
	constexpr std::uint32_t kPreSaveGame = 4;
	constexpr std::uint32_t kPostSaveGame = 5;
	constexpr std::uint32_t kPreLoadGame = 6;
	constexpr std::uint32_t kPostLoadGame = 7;

	std::filesystem::path g_dir;        // <dll folder>\FOCCSidecar
	std::filesystem::path g_sidecars;   // <dll folder>\FOCCSidecar\sidecars
	std::mutex            g_mutex;
	long long             g_counter = 0;   // pre-save events seen in this process (set from the sidecar on a valid load)
	long long             g_seq = 0;       // log line sequence

	bool Refuse(std::string_view a_step, const std::string& a_what)
	{
		REX::ERROR("refuse step={} {}", a_step, a_what);
		return false;
	}

	std::string Utf8(const std::filesystem::path& a_path)   // the log's text; the game folder may not be ASCII
	{
		const auto u8 = a_path.u8string();
		return std::string(u8.begin(), u8.end());
	}

	std::string UtcNow()
	{
		const auto now = std::chrono::floor<std::chrono::milliseconds>(std::chrono::system_clock::now());
		return std::format("{:%Y-%m-%dT%H:%M:%S}Z", now);
	}

	// Append one line to the log (open, write at end, close: the game may be killed at any time and a partial line is
	// the worst case). Each line also goes to the SFSE log as `step=event`.
	void LogLine(const std::string& a_fields)
	{
		std::lock_guard lock(g_mutex);
		++g_seq;
		const auto line = std::format("{{\"seq\": {}, \"time\": {}, {}}}", g_seq, focc::json_string(UtcNow()), a_fields);
		std::ofstream out(g_dir / "focc_sidecar.log", std::ios::binary | std::ios::app);
		out << line << "\r\n";
		REX::INFO("step=event {}{}", line, out ? "" : " (focc_sidecar.log not written)");
	}

	// Atomic write like sidecar.write: a temp file in the same folder, flushed and closed, then renamed over the target
	// (std::filesystem::rename replaces an existing file, as MoveFileExW with MOVEFILE_REPLACE_EXISTING does)
	bool WriteFileAtomic(const std::filesystem::path& a_path, const std::string& a_body, std::string& a_error)
	{
		auto tmp = a_path;
		tmp += ".tmp";
		{
			std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
			out.write(a_body.data(), static_cast<std::streamsize>(a_body.size()));
			out.flush();
			if (!out) {
				a_error = "write failed";
				out.close();
				std::error_code ec;
				std::filesystem::remove(tmp, ec);   // our own temp file of this write, nothing else is ever removed
				return false;
			}
		}
		std::error_code ec;
		std::filesystem::rename(tmp, a_path, ec);
		if (ec) {
			a_error = "rename failed " + std::to_string(ec.value());
			return false;
		}
		return true;
	}

	bool ReadWhole(const std::filesystem::path& a_path, std::string& a_out, std::string& a_error)
	{
		std::error_code ec;
		if (!std::filesystem::exists(a_path, ec)) {
			a_error = "not found";
			return false;
		}
		const auto size = std::filesystem::file_size(a_path, ec);
		if (ec || size > (16u << 20)) {
			a_error = "unreadable size";
			return false;
		}
		std::ifstream in(a_path, std::ios::binary);
		a_out.assign(static_cast<std::size_t>(size), '\0');
		if (size && !in.read(a_out.data(), static_cast<std::streamsize>(size))) {
			a_error = "read failed";
			return false;
		}
		return true;
	}

	std::string SaveNameOf(const SFSE::MessagingInterface::Message* a_msg)
	{
		if (!a_msg || !a_msg->data) {
			return {};
		}
		const auto* p = static_cast<const char*>(a_msg->data);
		// dataLen is strlen(a_name) upstream; trust the shorter of dataLen and the terminator, never read past dataLen
		std::size_t n = 0;
		while (n < a_msg->dataLen && p[n] != '\0') {
			++n;
		}
		return std::string(p, n);
	}

	std::string NameFields(const std::string& a_save)
	{
		return "\"save\": " + focc::json_string(a_save) + ", \"save_hex\": " + focc::json_string(focc::hex_bytes(a_save));
	}

	void OnPreSave(const std::string& a_save)
	{
		if (a_save.empty()) {
			LogLine("\"event\": \"pre_save\", \"error\": \"empty save name\"");
			return;
		}
		long long k;
		{
			std::lock_guard lock(g_mutex);
			k = ++g_counter;
		}
		const auto  file = focc::sidecar_name(a_save);
		std::string error;
		const bool  ok = WriteFileAtomic(g_sidecars / file, focc::encode_sidecar(a_save, k), error);
		LogLine("\"event\": \"pre_save\", " + NameFields(a_save) + ", \"counter\": " + std::to_string(k) +
				", \"file\": " + focc::json_string(file) + ", \"written\": " + (ok ? "true" : "false") +
				(ok ? "" : ", \"error\": " + focc::json_string(error)));
	}

	void OnPostLoad(const std::string& a_save)
	{
		if (a_save.empty()) {
			LogLine("\"event\": \"post_load\", \"error\": \"empty save name\"");
			return;
		}
		const auto    file = focc::sidecar_name(a_save);
		std::string   text;
		std::string   error;
		const bool    found = ReadWhole(g_sidecars / file, text, error);
		focc::Decoded d;
		if (found) {
			d = focc::decode_sidecar(text, a_save);
		}
		if (d.valid) {
			std::lock_guard lock(g_mutex);
			g_counter = d.counter;
		}
		LogLine("\"event\": \"post_load\", " + NameFields(a_save) + ", \"file\": " + focc::json_string(file) +
				", \"found\": " + (found ? "true" : "false") + ", \"valid\": " + (d.valid ? "true" : "false") +
				", \"counter\": " + std::to_string(d.valid ? d.counter : -1) +
				(found && !d.valid ? ", \"error\": " + focc::json_string(d.error) : "") +
				(!found ? ", \"error\": " + focc::json_string(error) : ""));
	}

	void OnMessage(SFSE::MessagingInterface::Message* a_msg)
	{
		if (!a_msg) {
			return;
		}
		switch (a_msg->type) {
		case SFSE::MessagingInterface::kPostLoad:
			LogLine("\"event\": \"sfse_post_load\"");
			break;
		case kPreSaveGame:
			OnPreSave(SaveNameOf(a_msg));
			break;
		case kPostSaveGame:
			LogLine("\"event\": \"post_save\", " + NameFields(SaveNameOf(a_msg)));
			break;
		case kPreLoadGame:
			LogLine("\"event\": \"pre_load\", " + NameFields(SaveNameOf(a_msg)));
			break;
		case kPostLoadGame:
			OnPostLoad(SaveNameOf(a_msg));
			break;
		default:
			break;   // data-load messages carry pointers we do not look at
		}
	}
}

SFSE_PLUGIN_LOAD(const SFSE::LoadInterface* a_sfse)
{
	SFSE::Init(a_sfse, { .trampoline = false, .hook = false });

	std::array<wchar_t, 1024> path{};
	const auto len = REX::W32::GetModuleFileNameW(REX::W32::GetCurrentModule(), path.data(), static_cast<std::uint32_t>(path.size()));
	const auto dir = std::filesystem::path(std::wstring(path.data(), len)).parent_path();
	std::array<wchar_t, 16> enabled{};
	REX::W32::GetPrivateProfileStringW(L"FOCCSidecar", L"bEnabled", L"0", enabled.data(), static_cast<std::uint32_t>(enabled.size()),
		(dir / "FOCCSidecar.ini").c_str());
	const auto runtime = a_sfse->RuntimeVersion();
	const bool on = std::wstring_view(enabled.data()) == L"1";
	REX::INFO("step=load runtime={} sfse={:#x} plugin_version={} enabled={}", runtime.string(), a_sfse->SFSEVersion(),
		kPluginVersion, on ? 1 : 0);

	// true in every case: a plugin that stays loaded and idle leaves its refusal line, the finding the P1 card reads
	if (runtime != kRuntime) {
		Refuse("version", std::format("runtime={} expected={}", runtime.string(), kRuntime.string()));
		return true;
	}
	if (!on) {
		REX::INFO("step=off (bEnabled=1 under [FOCCSidecar] in FOCCSidecar.ini to probe)");
		return true;
	}
	g_dir = dir / "FOCCSidecar";
	g_sidecars = g_dir / "sidecars";
	std::error_code ec;
	std::filesystem::create_directories(g_sidecars, ec);   // existing folders are fine
	if (ec || !std::filesystem::is_directory(g_sidecars, ec)) {
		Refuse("folder", std::format("path={} error={}", Utf8(g_sidecars), ec.value()));
		return true;
	}
	const auto messaging = SFSE::GetMessagingInterface();
	const bool registered = messaging && messaging->RegisterListener(&OnMessage);
	LogLine(std::format("\"event\": \"load\", \"plugin\": \"FOCCSidecar\", \"plugin_version\": {}, \"sfse_version\": {}, "
						"\"runtime_version\": {}, \"messaging\": {}, \"registered\": {}, \"dir\": {}",
		kPluginVersion, focc::json_string(std::format("{:#010x}", a_sfse->SFSEVersion())), focc::json_string(runtime.string()),
		messaging ? "true" : "false", registered ? "true" : "false", focc::json_string(Utf8(g_dir))));
	if (!registered) {
		Refuse("listen", std::format("messaging={}", messaging ? 1 : 0));
		return true;
	}
	REX::INFO("step=listen (pre_save writes a sidecar, post_load reads it back)");
	return true;
}
