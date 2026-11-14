// tests/test_sfse_runtime_dir.py's harness for sfse/FOCCSidecar/runtime_dir.h: one hex-encoded file text per line on
// stdin, one answer per line on stdout ("ok\t<hex of Dir>" or "err\t<error>"). Hex keeps the bytes exact across
// console encodings.
#include <iostream>
#include <string>

#include "runtime_dir.h"

namespace {

int nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

std::string from_hex(const std::string& hex) {
    std::string out;
    for (std::size_t i = 0; i + 1 < hex.size(); i += 2) {
        out += static_cast<char>(nibble(hex[i]) * 16 + nibble(hex[i + 1]));
    }
    return out;
}

std::string to_hex(const std::string& text) {
    static const char* digits = "0123456789abcdef";
    std::string out;
    for (const unsigned char c : text) {
        out += digits[c >> 4];
        out += digits[c & 15];
    }
    return out;
}

}  // namespace

int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const auto r = fo4sf_runtime::parse_runtime_ini(from_hex(line));
        std::cout << (r.ok ? "ok\t" + to_hex(r.dir) : "err\t" + r.error) << "\n";
    }
    return 0;
}
