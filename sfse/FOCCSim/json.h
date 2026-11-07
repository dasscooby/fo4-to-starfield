// JSON for the FOCCSim core: the world state Python wrote (model.WorldState.to_json) read back, and written again
// byte for byte as Python's json.dumps(..., sort_keys=True) writes it: separators ", " and ": ", keys sorted by code
// point (byte order of UTF-8), non-ASCII written as \uXXXX (ensure_ascii), lower-case hex. Integers only: the state
// holds no float, so a number with a fraction or an exponent is refused. No third-party library
// (docs/combined-core-cpp-port.md section 3, "JSON").
#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace foccsim {

struct Value;
using Object = std::map<std::string, Value>;
using Array = std::vector<Value>;

struct Value {
    enum class Kind { Null, Bool, Int, String, Array, Object };
    Kind kind = Kind::Null;
    bool b = false;
    std::int64_t i = 0;
    std::string s;
    std::shared_ptr<Array> a;
    std::shared_ptr<Object> o;

    Value() = default;
    static Value null() { return Value(); }
    static Value boolean(bool v) { Value x; x.kind = Kind::Bool; x.b = v; return x; }
    static Value integer(std::int64_t v) { Value x; x.kind = Kind::Int; x.i = v; return x; }
    static Value string(std::string v) { Value x; x.kind = Kind::String; x.s = std::move(v); return x; }
    static Value array(Array v = {}) { Value x; x.kind = Kind::Array; x.a = std::make_shared<Array>(std::move(v)); return x; }
    static Value object(Object v = {}) { Value x; x.kind = Kind::Object; x.o = std::make_shared<Object>(std::move(v)); return x; }

    bool is_null() const { return kind == Kind::Null; }
    bool is_int() const { return kind == Kind::Int; }
    bool is_str() const { return kind == Kind::String; }
    bool is_obj() const { return kind == Kind::Object; }
    bool is_arr() const { return kind == Kind::Array; }
};

class JsonError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

namespace detail {

struct Parser {
    const std::string& t;
    std::size_t p = 0;

    [[noreturn]] void fail(const std::string& why) { throw JsonError("JSON at byte " + std::to_string(p) + ": " + why); }
    void ws() { while (p < t.size() && (t[p] == ' ' || t[p] == '\t' || t[p] == '\n' || t[p] == '\r')) ++p; }
    bool eat(char c) { ws(); if (p < t.size() && t[p] == c) { ++p; return true; } return false; }
    void need(char c) { if (!eat(c)) fail(std::string("expected '") + c + "'"); }

    static void utf8(std::string& out, std::uint32_t cp) {
        if (cp < 0x80) out.push_back(static_cast<char>(cp));
        else if (cp < 0x800) { out.push_back(static_cast<char>(0xC0 | (cp >> 6))); out.push_back(static_cast<char>(0x80 | (cp & 0x3F))); }
        else if (cp < 0x10000) {
            out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        }
    }

    std::uint32_t hex4() {
        if (p + 4 > t.size()) fail("short \\u escape");
        std::uint32_t v = 0;
        for (int k = 0; k < 4; ++k) {
            char c = t[p++];
            v <<= 4;
            if (c >= '0' && c <= '9') v |= static_cast<std::uint32_t>(c - '0');
            else if (c >= 'a' && c <= 'f') v |= static_cast<std::uint32_t>(c - 'a' + 10);
            else if (c >= 'A' && c <= 'F') v |= static_cast<std::uint32_t>(c - 'A' + 10);
            else fail("bad \\u escape");
        }
        return v;
    }

    std::string str() {
        ws();
        if (p >= t.size() || t[p] != '"') fail("expected a string");
        ++p;
        std::string out;
        while (true) {
            if (p >= t.size()) fail("unterminated string");
            char c = t[p++];
            if (c == '"') return out;
            if (static_cast<unsigned char>(c) < 0x20) fail("control character in a string");
            if (c != '\\') { out.push_back(c); continue; }
            if (p >= t.size()) fail("unterminated escape");
            char e = t[p++];
            switch (e) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                case 'u': {
                    std::uint32_t cp = hex4();
                    if (cp >= 0xD800 && cp < 0xDC00 && p + 1 < t.size() && t[p] == '\\' && t[p + 1] == 'u') {
                        std::size_t save = p;
                        p += 2;
                        std::uint32_t lo = hex4();
                        if (lo >= 0xDC00 && lo < 0xE000) cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                        else p = save;
                    }
                    utf8(out, cp);
                    break;
                }
                default: fail("bad escape");
            }
        }
    }

    Value number() {
        std::size_t start = p;
        if (t[p] == '-') ++p;
        if (p >= t.size() || t[p] < '0' || t[p] > '9') fail("bad number");
        while (p < t.size() && t[p] >= '0' && t[p] <= '9') ++p;
        if (p < t.size() && (t[p] == '.' || t[p] == 'e' || t[p] == 'E'))
            fail("a fraction or an exponent: the world state holds integers only");
        std::string digits = t.substr(start, p - start);
        try {
            std::size_t used = 0;
            long long v = std::stoll(digits, &used);
            if (used != digits.size()) fail("bad number");
            return Value::integer(v);
        } catch (const std::out_of_range&) {
            fail("integer outside 64 bits: " + digits);
        }
    }

    Value value() {
        ws();
        if (p >= t.size()) fail("unexpected end");
        char c = t[p];
        if (c == '{') {
            ++p;
            Object o;
            if (eat('}')) return Value::object(std::move(o));
            do {
                std::string k = str();
                need(':');
                o[k] = value();                                   // a repeated key: the last wins, as in Python
            } while (eat(','));
            need('}');
            return Value::object(std::move(o));
        }
        if (c == '[') {
            ++p;
            Array a;
            if (eat(']')) return Value::array(std::move(a));
            do { a.push_back(value()); } while (eat(','));
            need(']');
            return Value::array(std::move(a));
        }
        if (c == '"') return Value::string(str());
        if (t.compare(p, 4, "true") == 0) { p += 4; return Value::boolean(true); }
        if (t.compare(p, 5, "false") == 0) { p += 5; return Value::boolean(false); }
        if (t.compare(p, 4, "null") == 0) { p += 4; return Value::null(); }
        if (c == '-' || (c >= '0' && c <= '9')) return number();
        fail("unexpected character");
    }
};

inline void write_string(std::string& out, const std::string& s) {
    static const char* hex = "0123456789abcdef";
    out.push_back('"');
    for (std::size_t k = 0; k < s.size();) {
        unsigned char c = static_cast<unsigned char>(s[k]);
        std::uint32_t cp;
        std::size_t len;
        if (c < 0x80) { cp = c; len = 1; }
        else if ((c >> 5) == 0x6) { cp = c & 0x1F; len = 2; }
        else if ((c >> 4) == 0xE) { cp = c & 0x0F; len = 3; }
        else { cp = c & 0x07; len = 4; }
        if (k + len > s.size()) throw JsonError("truncated UTF-8 in a string");
        for (std::size_t m = 1; m < len; ++m) cp = (cp << 6) | (static_cast<unsigned char>(s[k + m]) & 0x3F);
        k += len;
        auto u = [&](std::uint32_t v) {
            out += "\\u";
            for (int sh = 12; sh >= 0; sh -= 4) out.push_back(hex[(v >> sh) & 0xF]);
        };
        switch (cp) {
            case '"': out += "\\\""; continue;
            case '\\': out += "\\\\"; continue;
            case '\n': out += "\\n"; continue;
            case '\r': out += "\\r"; continue;
            case '\t': out += "\\t"; continue;
            case '\b': out += "\\b"; continue;
            case '\f': out += "\\f"; continue;
            default: break;
        }
        if (cp < 0x20 || (cp > 0x7E && cp < 0x10000)) u(cp);      // Python escapes all but ' ' to '~'
        else if (cp >= 0x10000) {
            std::uint32_t v = cp - 0x10000;
            u(0xD800 | (v >> 10));
            u(0xDC00 | (v & 0x3FF));
        } else out.push_back(static_cast<char>(cp));
    }
    out.push_back('"');
}

inline void write(std::string& out, const Value& v) {
    switch (v.kind) {
        case Value::Kind::Null: out += "null"; return;
        case Value::Kind::Bool: out += v.b ? "true" : "false"; return;
        case Value::Kind::Int: out += std::to_string(v.i); return;
        case Value::Kind::String: write_string(out, v.s); return;
        case Value::Kind::Array: {
            out.push_back('[');
            bool first = true;
            for (const Value& x : *v.a) { if (!first) out += ", "; first = false; write(out, x); }
            out.push_back(']');
            return;
        }
        case Value::Kind::Object: {
            out.push_back('{');
            bool first = true;
            for (const auto& kv : *v.o) {                   // std::map: byte order, Python's sort for UTF-8 keys
                if (!first) out += ", ";
                first = false;
                write_string(out, kv.first);
                out += ": ";
                write(out, kv.second);
            }
            out.push_back('}');
            return;
        }
    }
}

}  // namespace detail

inline Value parse(const std::string& text) {
    detail::Parser p{text};
    Value v = p.value();
    p.ws();
    if (p.p != text.size()) p.fail("text after the value");
    return v;
}

inline std::string dumps(const Value& v) {
    std::string out;
    detail::write(out, v);
    return out;
}

}  // namespace foccsim
