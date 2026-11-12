// FO4SFBorder: switch Starfield's border regions off while the player is in our world, and back on outside it
// (docs/terrain/border.md, "Per-world switch"; owner's decision of 2026-10-22: fix it for our world only, not with the
// global INI). SFSE plugin, no Address Library, no game structures beyond the one setting it finds by its name.
//
// How:
//   - The setting. "bBorderRegionsEnabled:General" is the INI setting run _f switched live with
//     SetINI "bBorderRegionsEnabled:General" 0 (border.md, verified: the Vault 95 exit then landed). scan.h finds the
//     setting's name string in Starfield.exe's image and the 8-byte pointers to it in writable memory: a Setting holds
//     a pointer to its name, with its value a few bytes before that pointer. Which byte is the value is not assumed:
//     Mode=1 (probe) only watches the 32 bytes before every candidate pointer and logs every change, so typing
//     SetINI 0 and 1 in the console shows the value's offset. Mode=2 (switch) writes the byte at ValueOffset
//     (from the INI; -16, verified by the Mode=1 probe on the PC, 2026-10-24: docs/terrain/border.md).
//   - The signal. SFSE's plugin API has no Papyrus or console bridge (PluginAPI.h, commit 48535cc: Messaging,
//     Trampoline, Menu, Task only), so the world test is in Papyrus: FO4SF_MapMarkers writes "border=off" when the
//     player is in one of the core's exterior cells, the generated land past them in the same world, or an interior
//     entered from there, and "border=on" in any other exterior,
//     to its user log (fo4sf_map.0.log, the log FO4SF_MapMarkers already writes). This plugin tails that file.
//   - The write. Only through SFSE's Task interface (AddTask runs it once on the main thread), never from the worker.
//     "on" restores the value the setting had when the switch first found it, not a hard-coded 1.
//
// Kill switch: FO4SFBorder.ini next to the dll, [FO4SFBorder] Mode=0 (default: loaded, idle, writes nothing),
// 1 = probe (find, watch and log; never writes game memory), 2 = switch. Log (FAL-246 item 2, out of the game's Data
// folder): <Dir>\logs\fo4sf_border.log, one JSON object per line, where Dir is the profile's run-time folder beside
// its saves, read from FO4SF-Runtime.ini next to the dll (../FOCCSidecar/runtime_dir.h; the launcher writes it). With
// Mode 1 or 2 and no usable Dir the plugin stays idle (no worker, no write of game memory, no file) and says why once
// through OutputDebugString: it has no other log of its own, and nothing falls back into Data.
//
// Interface: only SFSE's MIT-licensed sfse/PluginAPI.h (fetched by ..\FOCCSidecar\fetch_pluginapi.ps1 at the pinned
// commit, never committed). Build: build.sh (mingw-w64, static) or MSVC (README.md).

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <initguid.h>
#include <knownfolders.h>
#include <shlobj.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>

#include "PluginAPI.h"
#include "scan.h"
#include "../FOCCSidecar/runtime_dir.h"

namespace {

constexpr std::uint32_t kRuntime_1_16_244 = (1u << 24) | (16u << 16) | (244u << 4);
constexpr std::uint32_t kPluginVersion = 2;           // 1: the log under Data (24 Oct 2026)
constexpr int kWatchBytes = 32;           // bytes before each candidate pointer that the probe watches

HMODULE g_module = nullptr;
std::wstring g_dir;
std::wstring g_signal_path;
int g_mode = 0;
int g_value_offset = -16;
SFSETaskInterface* g_task = nullptr;
std::mutex g_log_mutex;
long long g_seq = 0;
std::atomic<bool> g_data_loaded{false};

std::string narrow(const std::wstring& w) {
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, nullptr, 0, nullptr, nullptr);
    std::string out;
    if (n > 1) {
        out.resize(static_cast<std::size_t>(n - 1));
        WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, out.data(), n, nullptr, nullptr);
    }
    return out;
}

std::wstring widen(const std::string& s) {   // UTF-8 to UTF-16; "" when s is not valid UTF-8
    const int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), nullptr, 0);
    std::wstring out;
    if (n > 0) {
        out.resize(static_cast<std::size_t>(n));
        MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), out.data(), n);
    }
    return out;
}

std::string json_string(const std::string& s) {
    std::string out = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { out += '\\'; out += static_cast<char>(c); }
        else if (c < 0x20) { char b[8]; std::snprintf(b, sizeof b, "\\u%04x", c); out += b; }
        else out += static_cast<char>(c);
    }
    return out + "\"";
}

std::string hex(std::uint64_t v) { char b[24]; std::snprintf(b, sizeof b, "0x%llx", static_cast<unsigned long long>(v)); return b; }

void log_line(const std::string& body) {
    std::lock_guard<std::mutex> lock(g_log_mutex);
    if (g_dir.empty()) return;
    SYSTEMTIME t;
    GetSystemTime(&t);
    char ts[40];
    std::snprintf(ts, sizeof ts, "%04u-%02u-%02uT%02u:%02u:%02u.%03uZ", t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond, t.wMilliseconds);
    std::string line = "{\"seq\": " + std::to_string(++g_seq) + ", \"time\": \"" + ts + "\", " + body + "}\r\n";
    std::wstring path = g_dir + L"\\fo4sf_border.log";
    HANDLE h = CreateFileW(path.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(h, line.data(), static_cast<DWORD>(line.size()), &written, nullptr);
    CloseHandle(h);
}

// FAL-246: the profile's run-time folder from FO4SF-Runtime.ini next to the dll. Its parent must exist (the game's
// save folder); Dir and logs\ are made inside it. On success `logs` is <Dir>\logs; otherwise `why` says what failed.
bool runtime_logs(const std::wstring& base, std::wstring& logs, std::string& why) {
    const std::wstring ini = base + L"\\" + widen(fo4sf_runtime::kIniName);
    HANDLE h = CreateFileW(ini.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) { why = "file=FO4SF-Runtime.ini reason=not found"; return false; }
    std::string text(fo4sf_runtime::kMaxFile + 1, '\0');
    DWORD got = 0;
    const BOOL done = ReadFile(h, text.data(), static_cast<DWORD>(text.size()), &got, nullptr);
    CloseHandle(h);
    if (!done) { why = "file=FO4SF-Runtime.ini reason=read failed"; return false; }
    text.resize(got);
    const fo4sf_runtime::RuntimeDir parsed = fo4sf_runtime::parse_runtime_ini(text);
    if (!parsed.ok) { why = "file=FO4SF-Runtime.ini reason=" + parsed.error; return false; }
    std::wstring root = widen(parsed.dir);
    if (root.empty()) { why = "dir=" + parsed.dir + " reason=not utf-8"; return false; }
    while (root.size() > 3 && (root.back() == L'\\' || root.back() == L'/')) root.pop_back();   // a trailing separator
    const std::size_t cut = root.find_last_of(L"\\/");
    const std::wstring parent = cut == std::wstring::npos ? std::wstring() : root.substr(0, cut == 2 ? 3 : cut);
    const DWORD attr = parent.empty() ? INVALID_FILE_ATTRIBUTES : GetFileAttributesW(parent.c_str());
    if (attr == INVALID_FILE_ATTRIBUTES || !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
        why = "dir=" + parsed.dir + " reason=parent_missing";
        return false;
    }
    const std::wstring folder = root + L"\\" + widen(fo4sf_runtime::kLogs);
    for (const std::wstring& d : {root, folder}) {
        CreateDirectoryW(d.c_str(), nullptr);         // an existing folder is fine
        const DWORD a = GetFileAttributesW(d.c_str());
        if (a == INVALID_FILE_ATTRIBUTES || !(a & FILE_ATTRIBUTE_DIRECTORY)) {
            why = "path=" + narrow(d) + " reason=create error=" + std::to_string(GetLastError());
            return false;
        }
    }
    logs = folder;
    return true;
}

std::wstring module_dir() {
    wchar_t buf[MAX_PATH * 2];
    DWORD n = GetModuleFileNameW(g_module, buf, static_cast<DWORD>(sizeof buf / sizeof buf[0]));
    if (n == 0 || n >= sizeof buf / sizeof buf[0]) return L"";
    std::wstring p(buf, n);
    std::size_t cut = p.find_last_of(L"\\/");
    return cut == std::wstring::npos ? L"" : p.substr(0, cut);
}

// Every read of game memory goes through ReadProcessMemory on this process: a page freed or reprotected after
// VirtualQuery makes it fail (ERROR_PARTIAL_COPY) instead of raising an access violation on the worker, which has no
// SEH (mingw has no __try; Grok on #522).
bool safe_read(std::uintptr_t addr, void* out, std::size_t n) {
    SIZE_T got = 0;
    return ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<LPCVOID>(addr), out, n, &got) && got == n;
}

// Committed, readable, non-guard memory of Starfield.exe's image (VirtualQuery over SizeOfImage), as address ranges;
// `data` is filled per region by copy_region, never pointed at the live image.
std::vector<fo4sfborder::Region> image_regions() {
    std::vector<fo4sfborder::Region> out;
    auto* base = reinterpret_cast<std::uint8_t*>(GetModuleHandleW(nullptr));
    if (!base) return out;
    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    const std::size_t size = nt->OptionalHeader.SizeOfImage;
    std::size_t at = 0;
    while (at < size) {
        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery(base + at, &mbi, sizeof mbi) == 0) break;
        std::size_t len = mbi.RegionSize - static_cast<std::size_t>(base + at - static_cast<std::uint8_t*>(mbi.BaseAddress));
        if (at + len > size) len = size - at;
        const DWORD p = mbi.Protect & 0xFF;
        const bool readable = mbi.State == MEM_COMMIT && !(mbi.Protect & PAGE_GUARD) &&
            (p == PAGE_READONLY || p == PAGE_READWRITE || p == PAGE_WRITECOPY || p == PAGE_EXECUTE_READ ||
             p == PAGE_EXECUTE_READWRITE || p == PAGE_EXECUTE_WRITECOPY);
        const bool writable = p == PAGE_READWRITE || p == PAGE_WRITECOPY || p == PAGE_EXECUTE_READWRITE || p == PAGE_EXECUTE_WRITECOPY;
        if (readable) out.push_back({reinterpret_cast<std::uintptr_t>(base + at), nullptr, len, writable});
        at += len;
    }
    return out;
}

struct Found {
    std::vector<fo4sfborder::Candidate> candidates;
    std::vector<std::vector<std::uint8_t>> watched;   // the kWatchBytes before each pointer, last seen
};

// A copy of one region; a region that cannot be read whole is dropped (data stays null, size 0).
fo4sfborder::Region copy_region(const fo4sfborder::Region& r, std::vector<std::uint8_t>& buf) {
    buf.resize(r.size);
    if (!safe_read(r.base, buf.data(), r.size)) return {r.base, nullptr, 0, r.writable};
    return {r.base, buf.data(), r.size, r.writable};
}

// The name strings, then the pointers to them, one region copy at a time (the whole image is never held twice).
std::vector<fo4sfborder::Candidate> find_candidates(const std::vector<fo4sfborder::Region>& regions, std::size_t& strings_out) {
    std::vector<std::uint8_t> buf;
    std::vector<std::uintptr_t> strings;
    for (const auto& r : regions) {
        auto s = fo4sfborder::find_strings({copy_region(r, buf)}, fo4sfborder::kSettingName);
        strings.insert(strings.end(), s.begin(), s.end());
    }
    strings_out = strings.size();
    std::vector<fo4sfborder::Candidate> out;
    if (strings.empty()) return out;
    for (const auto& r : regions) {
        if (!r.writable) continue;
        auto c = fo4sfborder::find_pointers({copy_region(r, buf)}, strings);
        out.insert(out.end(), c.begin(), c.end());
    }
    return out;
}

// The kWatchBytes before a pointer; empty when they cannot be read.
std::vector<std::uint8_t> bytes_before(std::uintptr_t ptr) {
    std::vector<std::uint8_t> b(kWatchBytes);
    if (!safe_read(ptr - kWatchBytes, b.data(), b.size())) b.clear();
    return b;
}

std::string bytes_hex(const std::vector<std::uint8_t>& b) {
    std::string s;
    char x[4];
    for (std::uint8_t v : b) { std::snprintf(x, sizeof x, "%02x", v); s += x; }
    return s;
}

Found scan(const char* when) {
    Found f;
    auto regions = image_regions();
    std::size_t strings = 0;
    f.candidates = find_candidates(regions, strings);
    std::string list;
    for (const auto& c : f.candidates) {
        f.watched.push_back(bytes_before(c.pointer_addr));
        if (!list.empty()) list += ", ";
        list += "{\"string\": \"" + hex(c.string_addr) + "\", \"pointer\": \"" + hex(c.pointer_addr) +
                "\", \"before\": \"" + bytes_hex(f.watched.back()) + "\"}";
    }
    log_line("\"event\": \"scan\", \"when\": " + json_string(when) + ", \"regions\": " + std::to_string(regions.size()) +
             ", \"strings\": " + std::to_string(strings) +
             ", \"candidates\": [" + list + "]");
    return f;
}

class WriteTask final : public SFSETaskInterface::ITaskDelegate {
public:
    WriteTask(std::uint8_t* addr, std::uint8_t value, int signal) : addr_(addr), value_(value), signal_(signal) {}
    void Run() override {
        const auto at = reinterpret_cast<std::uintptr_t>(addr_);
        std::uint8_t before = 0xFF, after = 0xFF;
        // the byte is checked again here, on the main thread: it must still read 0 or 1 (Grok on #522)
        if (!safe_read(at, &before, 1) || before > 1) {
            log_line("\"event\": \"refuse\", \"why\": \"byte at write time is " + std::to_string(before) + ", not 0 or 1\", \"addr\": \"" + hex(at) + "\"");
            return;
        }
        SIZE_T put = 0;
        const bool ok = WriteProcessMemory(GetCurrentProcess(), addr_, &value_, 1, &put) && put == 1;
        safe_read(at, &after, 1);
        log_line("\"event\": \"write\", \"ok\": " + std::string(ok ? "true" : "false") + ", \"addr\": \"" + hex(at) +
                 "\", \"before\": " + std::to_string(before) + ", \"after\": " + std::to_string(after) + ", \"signal\": " +
                 json_string(signal_ == 0 ? "border=off" : "border=on"));
    }
    void Destroy() override { delete this; }
private:
    std::uint8_t* addr_;
    std::uint8_t value_;
    int signal_;
};

// The signal log: new text since the last poll. A new file (another file index: the game renames the old log to
// .1.log and makes a new one when the script opens it in a new session) or a shorter one is read from its start;
// the file as it is when the plugin loads is the previous session's and is skipped.
struct Tail {
    DWORD vol = 0, idx_hi = 0, idx_lo = 0;
    long long offset = -1;     // -1: not yet seen
    bool known = false;
    std::string carry;         // an unfinished last line, kept for the next poll (Grok on #522)
};

bool read_new(Tail& t, std::string& text, bool baseline) {
    HANDLE h = CreateFileW(g_signal_path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                           nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    BY_HANDLE_FILE_INFORMATION info;
    LARGE_INTEGER size;
    bool ok = GetFileInformationByHandle(h, &info) && GetFileSizeEx(h, &size);
    if (ok) {
        const bool same = t.known && info.dwVolumeSerialNumber == t.vol && info.nFileIndexHigh == t.idx_hi && info.nFileIndexLow == t.idx_lo;
        if (!same || size.QuadPart < t.offset) {
            t.offset = (baseline && !t.known) ? size.QuadPart : 0;
            t.carry.clear();
        }
        t.vol = info.dwVolumeSerialNumber; t.idx_hi = info.nFileIndexHigh; t.idx_lo = info.nFileIndexLow; t.known = true;
        if (size.QuadPart > t.offset) {
            const long long want = std::min<long long>(size.QuadPart - t.offset, 1 << 20);
            std::string buf(static_cast<std::size_t>(want), '\0');
            LARGE_INTEGER pos; pos.QuadPart = size.QuadPart - want;
            DWORD got = 0;
            if (SetFilePointerEx(h, pos, nullptr, FILE_BEGIN) && ReadFile(h, buf.data(), static_cast<DWORD>(want), &got, nullptr)) {
                buf.resize(got);
                if (want < size.QuadPart - t.offset) t.carry.clear();   // skipped the middle: the carry is not before buf
                text = fo4sfborder::complete_lines(t.carry, buf);
                t.offset = size.QuadPart;
            }
        } else if (!t.carry.empty()) {
            // nothing new for a whole poll: the unfinished line was the whole line (a log that writes its newline
            // only before the next line would otherwise hold the newest signal back)
            text = t.carry;
            t.carry.clear();
        }
    }
    CloseHandle(h);
    return ok;
}

DWORD WINAPI worker(LPVOID) {
    Found f;
    Tail tail;
    std::string text;
    read_new(tail, text, true);                  // baseline: skip what the last session wrote
    text.clear();
    std::uint8_t* value = nullptr;
    std::uint8_t original = 0;
    int applied = -1;
    bool refused = false;
    for (unsigned tick = 0;; ++tick) {
        Sleep(500);
        if (f.candidates.empty() && (tick % 4) == 0 && g_data_loaded.load()) {
            f = scan("worker");
            if (g_mode == 2 && !f.candidates.empty() && !refused) {
                if (f.candidates.size() != 1) {
                    refused = true;
                    log_line("\"event\": \"refuse\", \"why\": \"" + std::to_string(f.candidates.size()) + " candidates, want exactly 1\"");
                } else {
                    value = reinterpret_cast<std::uint8_t*>(f.candidates[0].pointer_addr + g_value_offset);
                    if (!safe_read(f.candidates[0].pointer_addr + g_value_offset, &original, 1)) original = 0xFF;
                    if (original > 1) {
                        refused = true;
                        log_line("\"event\": \"refuse\", \"why\": \"byte at value_offset " + std::to_string(g_value_offset) +
                                 " is " + std::to_string(original) + ", not 0 or 1\"");
                        value = nullptr;
                    } else {
                        log_line("\"event\": \"armed\", \"addr\": \"" + hex(reinterpret_cast<std::uintptr_t>(value)) +
                                 "\", \"value_offset\": " + std::to_string(g_value_offset) + ", \"original\": " + std::to_string(original));
                    }
                }
            }
        }
        for (std::size_t i = 0; i < f.candidates.size(); ++i) {   // probe and switch: log every change before a pointer
            auto now = bytes_before(f.candidates[i].pointer_addr);
            if (now.empty() || f.watched[i].empty()) {
                if (now.size() != f.watched[i].size())
                    log_line("\"event\": \"unreadable\", \"candidate\": " + std::to_string(i) + ", \"readable\": " + (now.empty() ? "false" : "true"));
                f.watched[i] = now;
                continue;
            }
            if (now != f.watched[i]) {
                std::string diff;
                for (int k = 0; k < kWatchBytes; ++k) {
                    if (now[k] != f.watched[i][k]) {
                        if (!diff.empty()) diff += ", ";
                        diff += "{\"offset\": " + std::to_string(k - kWatchBytes) + ", \"from\": " + std::to_string(f.watched[i][k]) +
                                ", \"to\": " + std::to_string(now[k]) + "}";
                    }
                }
                log_line("\"event\": \"changed\", \"candidate\": " + std::to_string(i) + ", \"bytes\": [" + diff + "]");
                f.watched[i] = now;
            }
        }
        text.clear();
        if (read_new(tail, text, false) && !text.empty()) {
            const int signal = fo4sfborder::parse_signal(text);
            if (signal >= 0 && signal != applied) {
                log_line("\"event\": \"signal\", \"value\": " + json_string(signal == 0 ? "border=off" : "border=on") +
                         ", \"mode\": " + std::to_string(g_mode));
                if (g_mode == 2 && value && g_task) {
                    g_task->AddTask(new WriteTask(value, signal == 0 ? 0 : original, signal));
                    applied = signal;
                } else if (g_mode != 2) {
                    applied = signal;
                }
            }
        }
    }
    return 0;
}

void OnSFSEMessage(SFSEMessagingInterface::Message* msg) {
    if (msg && msg->type == SFSEMessagingInterface::kMessage_PostDataLoad) {
        g_data_loaded = true;
        log_line("\"event\": \"post_data_load\"");
    }
}

std::wstring documents_signal_path() {
    PWSTR docs = nullptr;
    std::wstring out;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_Documents, 0, nullptr, &docs)) && docs) {
        out = std::wstring(docs) + L"\\My Games\\Starfield\\Logs\\Script\\User\\fo4sf_map.0.log";
    }
    if (docs) CoTaskMemFree(docs);
    return out;
}

}  // namespace

extern "C" {

__declspec(dllexport) SFSEPluginVersionData SFSEPlugin_Version = {
    SFSEPluginVersionData::kVersion,
    kPluginVersion,
    "FO4SFBorder",
    "fo4-to-starfield",
    SFSEPluginVersionData::kAddressIndependence_Signatures,       // the setting is found by its name, no addresses
    SFSEPluginVersionData::kStructureIndependence_1_14_70_Layout, // one assumption (a Setting points at its name),
                                                                  // checked at run time: 0 or 2+ candidates refuse
    { kRuntime_1_16_244, 0 },
    0,
    0, 0,
};

__declspec(dllexport) bool SFSEPlugin_Load(const SFSEInterface* sfse) {
    if (!sfse) return false;
    const std::wstring base = module_dir();
    if (base.empty()) return true;
    const std::wstring ini = base + L"\\FO4SFBorder.ini";
    g_mode = static_cast<int>(GetPrivateProfileIntW(L"FO4SFBorder", L"Mode", 0, ini.c_str()));
    if (g_mode != 1 && g_mode != 2) return true;      // the kill switch: idle, silent
    g_value_offset = static_cast<int>(GetPrivateProfileIntW(L"FO4SFBorder", L"ValueOffset", -16, ini.c_str()));
    if (g_value_offset >= 0 || g_value_offset < -kWatchBytes) g_value_offset = -16;
    wchar_t path[1024] = {0};
    GetPrivateProfileStringW(L"FO4SFBorder", L"SignalLog", L"", path, 1024, ini.c_str());
    g_signal_path = path[0] ? std::wstring(path) : documents_signal_path();
    std::string why;
    if (!runtime_logs(base, g_dir, why)) {            // FAL-246: no run-time folder, nothing at all
        g_dir.clear();
        OutputDebugStringA(("FO4SFBorder: refuse step=runtime_dir " + why + "\n").c_str());
        return true;
    }

    const PluginHandle handle = sfse->GetPluginHandle();
    auto* messaging = static_cast<SFSEMessagingInterface*>(sfse->QueryInterface(kInterface_Messaging));
    g_task = static_cast<SFSETaskInterface*>(sfse->QueryInterface(kInterface_Task));
    const bool registered = messaging && messaging->RegisterListener(handle, "SFSE", OnSFSEMessage);
    log_line("\"event\": \"load\", \"plugin_version\": " + std::to_string(kPluginVersion) + ", \"mode\": " + std::to_string(g_mode) +
             ", \"value_offset\": " + std::to_string(g_value_offset) + ", \"sfse_version\": \"" + hex(sfse->sfseVersion) +
             "\", \"runtime_version\": \"" + hex(sfse->runtimeVersion) + "\", \"registered\": " + (registered ? "true" : "false") +
             ", \"task\": " + (g_task ? "true" : "false") + ", \"signal_log\": " + json_string(narrow(g_signal_path)) +
             ", \"log_dir\": " + json_string(narrow(g_dir)));
    if (!registered) g_data_loaded = true;            // no PostDataLoad will come: scan on the worker's schedule
    HANDLE t = CreateThread(nullptr, 0, worker, nullptr, 0, nullptr);
    if (t) CloseHandle(t);
    return true;
}

}  // extern "C"

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = instance;
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
