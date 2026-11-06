// Header-only, platform-neutral part of the FOCCSidecar probe plugin: the sidecar file-name rule, the canonical JSON
// text and the envelope reader. It mirrors src/fo4sf/combined/sidecar.py byte for byte for ASCII save names (see
// README.md "Name and checksum rule" for the non-ASCII caveat) and was compiled on Linux and checked against sidecar.py by hand
// on 2026-10-21 (README.md "Verified offline"). tests/test_sfse_sidecar_codec.py compiles it against the Python
// reference and malformed inputs; FOCCSidecar.cpp adds the Windows file I/O and the SFSE glue around it.
//
// Python reference (sidecar.py):
//   sidecar_name(n) = re.sub(r"[^A-Za-z0-9_.-]", "_", n)[:80].strip(".") or "save"  +  "-"  +  sha256(n)[:8]  +  ".focc"
//   encode(n, ws)   = json.dumps({"format": "focc-sidecar", "schema": 1, "save_name": n,
//                                 "world_state": <ws>, "sha256": sha256(json.dumps(ws, sort_keys=True))}, sort_keys=True)
// json.dumps defaults: separators ", " and ": ", sort_keys gives the key order format, save_name, schema, sha256,
// world_state. The P1 world state is the stub {"counter": k, "probe": "P1"}, not a model.WorldState (the probe plan,
// P1 pass rule); group C's checker verifies the envelope, not the world state's schema.
#pragma once

#include <cstddef>
#include <cstdint>
#include <charconv>
#include <string>
#include <system_error>

#include "sha256.h"

namespace focc {

constexpr const char* kFormat = "focc-sidecar";
constexpr int kSchema = 1;
constexpr const char* kExtension = ".focc";
constexpr std::size_t kSafeNameMax = 80;   // sidecar.SAFE_NAME_MAX (an assumption there, mirrored here)
constexpr std::size_t kHashChars = 8;      // sidecar.HASH_CHARS

inline bool is_safe_char(unsigned char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '.' || c == '-';
}

// sidecar.sidecar_name. Byte-wise: every byte outside [A-Za-z0-9_.-] becomes "_" (Python replaces per character, so
// a non-ASCII save name gives one "_" per character there and one per UTF-8 byte here: README.md caveat). The result
// is always ASCII, so it widens to a Windows path without conversion.
inline std::string sidecar_name(const std::string& saveName) {
    std::string safe;
    for (unsigned char c : saveName) safe.push_back(is_safe_char(c) ? static_cast<char>(c) : '_');
    if (safe.size() > kSafeNameMax) safe.resize(kSafeNameMax);
    std::size_t b = 0, e = safe.size();
    while (b < e && safe[b] == '.') ++b;
    while (e > b && safe[e - 1] == '.') --e;
    safe = safe.substr(b, e - b);
    if (safe.empty()) safe = "save";
    return safe + "-" + sha256_hex(saveName).substr(0, kHashChars) + kExtension;
}

// JSON string literal as Python json.dumps writes it for ASCII input: \" \\ \n \r \t \b \f and \u00XX for other
// control characters. Bytes >= 0x80 pass through unchanged (valid JSON when the name is UTF-8; Python would write
// \uXXXX escapes instead, which decode to the same value, so the checker's parsed comparison still matches).
inline std::string json_string(const std::string& s) {
    static const char* hex = "0123456789abcdef";
    std::string out = "\"";
    for (unsigned char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            default:
                if (c < 0x20) { out += "\\u00"; out.push_back(hex[c >> 4]); out.push_back(hex[c & 0xF]); }
                else out.push_back(static_cast<char>(c));
        }
    }
    out.push_back('"');
    return out;
}

// Lower-case hex of raw bytes, logged beside the save name so a checker can settle encoding questions.
inline std::string hex_bytes(const std::string& s) {
    static const char* hex = "0123456789abcdef";
    std::string out;
    for (unsigned char c : s) { out.push_back(hex[c >> 4]); out.push_back(hex[c & 0xF]); }
    return out;
}

// The P1 stub world state, as json.dumps({"probe": "P1", "counter": k}, sort_keys=True) writes it.
inline std::string stub_world_state(long long counter) {
    return "{\"counter\": " + std::to_string(counter) + ", \"probe\": \"P1\"}";
}

// sidecar.encode for the stub state: the full sidecar body.
inline std::string encode_sidecar(const std::string& saveName, long long counter) {
    const std::string state = stub_world_state(counter);
    return std::string("{\"format\": ") + json_string(kFormat) + ", \"save_name\": " + json_string(saveName) +
           ", \"schema\": " + std::to_string(kSchema) + ", \"sha256\": " + json_string(sha256_hex(state)) +
           ", \"world_state\": " + state + "}";
}

struct Decoded {
    bool valid = false;
    long long counter = -1;
    std::string error;   // empty when valid
};

// Minimal reader for a body this plugin wrote (the stub layout above), with the same checks as sidecar.decode:
// format, schema, save name and the sha256 over the world_state text. It is a shape check, not a JSON parser: a body
// written by anything else is reported invalid with the reason, never trusted.
inline Decoded decode_sidecar(const std::string& text, const std::string& saveName) {
    Decoded d;
    auto field = [&](const char* key) -> std::string {   // the raw text after `"key": ` up to the next , or }
        std::string k = std::string("\"") + key + "\": ";
        std::size_t p = text.find(k);
        if (p == std::string::npos) return "";
        p += k.size();
        std::size_t e = p;
        if (text[p] == '"') {   // a JSON string: skip escaped characters to the closing quote
            e = p + 1;
            while (e < text.size() && text[e] != '"') e += (text[e] == '\\') ? 2 : 1;
            return e >= text.size() ? "" : text.substr(p, e + 1 - p);
        }
        if (text[p] == '{') { e = text.find('}', p); return e == std::string::npos ? "" : text.substr(p, e + 1 - p); }
        while (e < text.size() && text[e] != ',' && text[e] != '}') ++e;
        return text.substr(p, e - p);
    };
    if (field("format") != json_string(kFormat)) { d.error = "not a focc-sidecar body"; return d; }
    if (field("schema") != std::to_string(kSchema)) { d.error = "unknown sidecar schema"; return d; }
    if (field("save_name") != json_string(saveName)) { d.error = "sidecar belongs to another save"; return d; }
    const std::string state = field("world_state");
    const std::string sum = field("sha256");
    if (state.empty() || sum.empty()) { d.error = "sidecar lacks world_state or sha256"; return d; }
    if (json_string(sha256_hex(state)) != sum) { d.error = "sidecar checksum mismatch"; return d; }
    const std::string c = "\"counter\": ";
    std::size_t p = state.find(c);
    if (p == std::string::npos) { d.error = "world_state lacks counter"; return d; }
    p += c.size();
    std::size_t e = p;
    while (e < state.size() && (state[e] == '-' || (state[e] >= '0' && state[e] <= '9'))) ++e;
    if (e == p) { d.error = "counter is not a number"; return d; }
    long long counter = 0;
    const auto parsed = std::from_chars(state.data() + p, state.data() + e, counter);
    if (parsed.ec != std::errc{} || parsed.ptr != state.data() + e) {
        d.error = "counter is not a signed 64-bit integer";
        return d;
    }
    // This probe reads only its own canonical writer's shape. A checksum alone does not establish valid JSON,
    // the P1 marker, unique fields or an integer token (e.g. 1.5 must not silently become counter 1).
    if (text != encode_sidecar(saveName, counter)) {
        d.error = "not a canonical P1 sidecar body";
        return d;
    }
    d.counter = counter;
    d.valid = true;
    return d;
}

}  // namespace focc
