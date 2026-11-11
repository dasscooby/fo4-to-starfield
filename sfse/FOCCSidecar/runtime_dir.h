// Header-only, platform-neutral reader of FO4SF-Runtime.ini, the one file that tells our dlls where their run-time
// files go (FAL-246 item 2; the agreement with the launcher is FAL-247's document native-launcher-contract):
//
//   [Runtime]
//   Dir=<absolute path of the profile's FO4SF-Runtime folder, beside its saves>
//
// The launcher writes the file next to the dlls (Data\SFSE\Plugins\FO4SF-Runtime.ini); a probe card may write it by
// hand. The text is UTF-8 (an optional BOM is skipped) and the value is taken literally: no %VAR% expansion, no
// backslash unescaping, no quotes removed. Anything else refuses, and a dll that refuses writes nothing: there is no
// fallback folder under Data and no guessed Documents path.
//
// This reader only parses. Whether the folder exists, and creating sidecars\ and logs\ inside it, is the dll's part
// (FOCCSidecar's src/main.cpp, FO4SFBorder.cpp). tests/test_sfse_runtime_dir.py compiles it with
// tests/sfse_runtime_dir_test.cpp against tests/data/runtime_dir_vectors.json, the cases the launcher's writer must
// also meet.
#pragma once

#include <cstddef>
#include <string>
#include <string_view>

namespace fo4sf_runtime {

constexpr const char* kIniName = "FO4SF-Runtime.ini";
constexpr const char* kSidecars = "sidecars";
constexpr const char* kLogs = "logs";
constexpr std::size_t kMaxFile = 64 * 1024;   // a larger file is not ours

struct RuntimeDir {
    bool ok = false;
    std::string dir;     // UTF-8, exactly as written after trimming spaces and tabs
    std::string error;   // set when !ok
};

inline char lower(char c) { return (c >= 'A' && c <= 'Z') ? static_cast<char>(c - 'A' + 'a') : c; }

inline bool equal_ci(std::string_view a, std::string_view b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (lower(a[i]) != lower(b[i])) return false;
    }
    return true;
}

inline std::string_view trim(std::string_view s) {
    while (!s.empty() && (s.front() == ' ' || s.front() == '\t')) s.remove_prefix(1);
    while (!s.empty() && (s.back() == ' ' || s.back() == '\t')) s.remove_suffix(1);
    return s;
}

inline bool is_sep(char c) { return c == '\\' || c == '/'; }

// An absolute Windows path, decided on the text alone: a drive ("C:\..." or "C:/...") or a UNC share
// ("\\server\share\..."). No "." or ".." component (the launcher resolves the path before it writes it), no control
// character, no character Windows refuses in a path.
inline bool absolute_windows_path(std::string_view p, std::string& error) {
    if (p.size() >= 3 && ((p[0] >= 'A' && p[0] <= 'Z') || (p[0] >= 'a' && p[0] <= 'z')) && p[1] == ':' && is_sep(p[2])) {
        p.remove_prefix(3);
    } else if (p.size() >= 5 && is_sep(p[0]) && is_sep(p[1]) && !is_sep(p[2])) {
        p.remove_prefix(2);
        const std::size_t server = p.find_first_of("\\/");
        if (server == std::string_view::npos || server + 1 >= p.size() || is_sep(p[server + 1])) {
            error = "not absolute (a UNC path needs \\\\server\\share)";
            return false;
        }
    } else {
        error = "not absolute (a drive or a \\\\server\\share path is needed)";
        return false;
    }
    std::size_t start = 0;
    for (std::size_t i = 0; i <= p.size(); ++i) {
        if (i < p.size()) {
            const unsigned char c = static_cast<unsigned char>(p[i]);
            if (c < 0x20 || c == 0x7F || c == '<' || c == '>' || c == ':' || c == '"' || c == '|' || c == '?' || c == '*') {
                error = "a character Windows refuses in a path";
                return false;
            }
            if (!is_sep(p[i])) continue;
        }
        const std::string_view part = p.substr(start, i - start);
        if (part == "." || part == "..") {
            error = "a . or .. component (the path must be resolved)";
            return false;
        }
        start = i + 1;
    }
    return true;
}

// The file's whole text. Exactly one Dir key under [Runtime]; other sections and keys are ignored; ';' and '#' start
// a comment line. Section and key names are case-insensitive.
inline RuntimeDir parse_runtime_ini(std::string_view text) {
    RuntimeDir out;
    if (text.size() > kMaxFile) {
        out.error = "file too large";
        return out;
    }
    if (text.size() >= 3 && static_cast<unsigned char>(text[0]) == 0xEF && static_cast<unsigned char>(text[1]) == 0xBB &&
        static_cast<unsigned char>(text[2]) == 0xBF) {
        text.remove_prefix(3);
    }
    if (text.find('\0') != std::string_view::npos) {
        out.error = "a NUL byte (the file must be UTF-8, not UTF-16)";
        return out;
    }
    bool in_runtime = false;
    bool seen_section = false;
    int found = 0;
    std::string_view value;
    while (!text.empty()) {
        const std::size_t end = text.find('\n');
        std::string_view line = text.substr(0, end);
        text = end == std::string_view::npos ? std::string_view() : text.substr(end + 1);
        if (!line.empty() && line.back() == '\r') line.remove_suffix(1);
        line = trim(line);
        if (line.empty() || line.front() == ';' || line.front() == '#') continue;
        if (line.front() == '[') {
            if (line.back() != ']') {
                out.error = "a malformed section line";
                return out;
            }
            in_runtime = equal_ci(trim(line.substr(1, line.size() - 2)), "Runtime");
            seen_section = seen_section || in_runtime;
            continue;
        }
        if (!in_runtime) continue;
        const std::size_t eq = line.find('=');
        if (eq == std::string_view::npos) {
            out.error = "a [Runtime] line without '='";
            return out;
        }
        if (equal_ci(trim(line.substr(0, eq)), "Dir")) {
            ++found;
            value = trim(line.substr(eq + 1));
        }
    }
    if (!seen_section) {
        out.error = "no [Runtime] section";
    } else if (found == 0) {
        out.error = "no Dir= under [Runtime]";
    } else if (found > 1) {
        out.error = "more than one Dir= under [Runtime]";
    } else if (value.empty()) {
        out.error = "Dir= is empty";
    } else if (absolute_windows_path(value, out.error)) {
        out.ok = true;
        out.dir = std::string(value);
    }
    return out;
}

}  // namespace fo4sf_runtime
