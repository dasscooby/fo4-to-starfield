// FOCCSim's news (see news.h). Each function names the Python one it copies, from src/fo4sf/combined/news.py,
// sim.py (news_for) and Python's textwrap (wrap, shorten).
#include "news.h"

#include <algorithm>
#include <optional>
#include <set>
#include <stdexcept>
#include <utility>

namespace foccsim::news {

namespace {

constexpr Int HOURS_PER_DAY = 24;                   // news.HOURS_PER_DAY
constexpr Int NEWS_HOURS_PER_ROUTE_HOUR = 1;        // sim.NEWS_HOURS_PER_ROUTE_HOUR

const std::map<std::string, std::string>& templates() {   // news.TEMPLATES, our own wording
    static const std::map<std::string, std::string> t = {
        {"place_taken", "{faction} took {place} from {previous}."},
        {"place_retaken", "{faction} took back {place} from {previous}."},
        {"place_claimed", "{faction} moved into {place}."},
        {"attack_launched", "{faction} sent fighters from {place} toward {target}."},
        {"attack_failed", "An attack by {faction} on {place} was beaten off."},
        {"attack_called_off", "{faction} called off an attack on {place}."},
        {"caravan_raided", "A caravan from {origin} to {place} was raided by {raider}."},
        {"caravan_arrived", "A caravan reached {place} carrying {cargo}."},
        {"caravan_lost", "A caravan bound for {place} never arrived."},
        {"stage_grew", "{place} has grown."},
        {"stage_shrank", "{place} has shrunk."},
        {"settler_left", "A settler left {place}."},
        {"settler_arrived", "A new settler arrived at {place}."},
        {"settlement_emptied", "The last settler has left {place}; it stands empty."},
        {"settlement_resettled", "Settlers of {faction} have moved back into {place}."},
        {"player_defended", "A traveller stood guard at {place}."},
        {"player_gave", "A traveller brought supplies to {place}."},
        {"player_took", "A traveller bought supplies at {place}."},
        {"place_cleared", "{faction} drove {previous} out of {place}."},
        {"job_done", "A traveller finished a job for {faction} at {place}."},
        {"job_failed", "A traveller let {faction} down at {place}."},
        {"roles_changed", "Settlers at {place} were moved from {from_role} work to {to_role} work."},
        {"beds_added", "New beds were built at {place}."},
        {"priority_set", "{place} is now putting its effort into {good}."},
        {"priority_cleared", "{place} has gone back to working as usual."},
        {"supplies_sent", "A caravan left {place} for {target} carrying {cargo}."},
    };
    return t;
}

const Value* get(const Value& e, const char* key) {        // e.get(key)
    auto it = e.o->find(key);
    return it == e.o->end() ? nullptr : &it->second;
}

bool truthy(const Value* v) {                              // Python's bool() of a JSON value
    if (!v) return false;
    switch (v->kind) {
        case Value::Kind::Null: return false;
        case Value::Kind::Bool: return v->b;
        case Value::Kind::Int: return v->i != 0;
        case Value::Kind::String: return !v->s.empty();
        case Value::Kind::Array: return !v->a->empty();
        case Value::Kind::Object: return !v->o->empty();
    }
    return false;
}

OptStr as_name(const Value& v) {                           // a str or None field, as display_name takes it
    if (v.is_null()) return std::nullopt;
    if (!v.is_str()) throw std::runtime_error("an event's name field is not a string");   // Python: AttributeError
    return v.s;
}

Counts counts_of(const Value* v) {
    Counts out;
    if (v && v->is_obj())
        for (const auto& kv : *v->o) out[kv.first] = kv.second.i;
    return out;
}

OptStr template_key(const Value& e) {                     // news._template_key
    const Value* k = get(e, "kind");
    if (!k || !k->is_str()) return std::nullopt;
    const std::string& kind = k->s;
    if (kind == "place_taken") {
        const Value* prev = get(e, "previous");
        if (!prev || prev->is_null()) return std::string("place_claimed");
        return std::string(truthy(get(e, "retaken")) ? "place_retaken" : "place_taken");
    }
    if (kind == "stage_changed") {
        const Value* n = get(e, "new");
        const Value* o = get(e, "old");
        return std::string((n ? n->i : 0) >= (o ? o->i : 0) ? "stage_grew" : "stage_shrank");
    }
    if (kind == "player_traded") {
        Int given = 0;
        for (const auto& kv : counts_of(get(e, "goods")))
            if (kv.second > 0) given += kv.second;
        return std::string(given ? "player_gave" : "player_took");
    }
    if (kind == "priority_set") {
        const Value* n = get(e, "new");
        return std::string(!n || n->is_null() ? "priority_cleared" : "priority_set");
    }
    if (templates().count(kind)) return kind;
    return std::nullopt;
}

// --- textwrap ------------------------------------------------------------------------------------------------------
using U = std::u32string;

U decode(const std::string& s) {
    U out;
    for (std::size_t k = 0; k < s.size();) {
        unsigned char c = static_cast<unsigned char>(s[k]);
        std::size_t len = c < 0x80 ? 1 : (c >> 5) == 0x6 ? 2 : (c >> 4) == 0xE ? 3 : 4;
        char32_t cp = len == 1 ? c : len == 2 ? (c & 0x1F) : len == 3 ? (c & 0x0F) : (c & 0x07);
        for (std::size_t m = 1; m < len && k + m < s.size(); ++m)
            cp = (cp << 6) | (static_cast<unsigned char>(s[k + m]) & 0x3F);
        out.push_back(cp);
        k += len;
    }
    return out;
}

std::string encode(const U& u) {
    std::string out;
    for (char32_t cp : u) {
        if (cp < 0x80) out.push_back(static_cast<char>(cp));
        else if (cp < 0x800) {
            out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else if (cp < 0x10000) {
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
    return out;
}

bool in(char32_t c, char32_t lo, char32_t hi) { return c >= lo && c <= hi; }

bool is_digit(char32_t c) {                                // re's \d (Unicode Nd): ASCII and a few common blocks
    return in(c, '0', '9') || in(c, 0x660, 0x669) || in(c, 0x6F0, 0x6F9) || in(c, 0x966, 0x96F) ||
           in(c, 0xFF10, 0xFF19);
}

bool is_word(char32_t c) {                                 // re's \w: exact for ASCII and Latin-1, see news.h
    if (c < 0x80) return in(c, 'a', 'z') || in(c, 'A', 'Z') || in(c, '0', '9') || c == '_';
    if (c < 0x100)
        return c == 0xAA || c == 0xB2 || c == 0xB3 || c == 0xB5 || c == 0xB9 || c == 0xBA || in(c, 0xBC, 0xBE) ||
               (c >= 0xC0 && c != 0xD7 && c != 0xF7);
    return is_digit(c) || in(c, 0x100, 0x2AF) || c == 0x386 || (in(c, 0x388, 0x3FF) && c != 0x3F6) ||
           in(c, 0x400, 0x481) || in(c, 0x48A, 0x52F) || in(c, 0x531, 0x556) || in(c, 0x561, 0x587) ||
           in(c, 0x5D0, 0x5EA) || in(c, 0x620, 0x64A) || in(c, 0x1E00, 0x1EFF) || in(c, 0x3041, 0x3096) ||
           in(c, 0x30A1, 0x30FA) || in(c, 0x4E00, 0x9FFF) || in(c, 0xAC00, 0xD7A3);
}

bool is_letter(char32_t c) { return is_word(c) && !is_digit(c); }   // [^\d\W]
bool is_word_punct(char32_t c) {                           // [\w!"'&.,?]
    return is_word(c) || c == '!' || c == '"' || c == '\'' || c == '&' || c == '.' || c == ',' || c == '?';
}
bool is_wrap_space(char32_t c) {                           // textwrap's _whitespace: '\t\n\x0b\x0c\r '
    return c == '\t' || c == '\n' || c == 0x0B || c == 0x0C || c == '\r' || c == ' ';
}
bool is_py_space(char32_t c) {                             // str.isspace(), for strip() and split()
    return in(c, 0x09, 0x0D) || in(c, 0x1C, 0x20) || c == 0x85 || c == 0xA0 || c == 0x1680 || in(c, 0x2000, 0x200A) ||
           c == 0x2028 || c == 0x2029 || c == 0x202F || c == 0x205F || c == 0x3000;
}

U strip(const U& s, bool left = true, bool right = true) {
    std::size_t b = 0, e = s.size();
    if (left) while (b < e && is_py_space(s[b])) ++b;
    if (right) while (e > b && is_py_space(s[e - 1])) --e;
    return s.substr(b, e - b);
}
bool blank(const U& s) { return strip(s).empty(); }        // s.strip() == ''

U munge(const U& text) {                                   // TextWrapper._munge_whitespace: expandtabs(8), then spaces
    U out;
    std::size_t column = 0;
    for (char32_t c : text) {
        if (c == '\t') {
            std::size_t n = 8 - column % 8;
            out.append(n, U' ');
            column += n;
        } else if (c == '\n' || c == '\r') {
            out.push_back(c);
            column = 0;
        } else {
            out.push_back(c);
            ++column;
        }
    }
    for (char32_t& c : out)
        if (is_wrap_space(c)) c = U' ';
    return out;
}

// TextWrapper._split with break_on_hyphens: the pieces wordsep_re.split leaves, which here are always its matches
std::vector<U> split_chunks(const U& t) {
    const std::size_t n = t.size();
    auto at = [&](std::size_t k) -> char32_t { return k < n ? t[k] : 0; };
    auto hyphens = [&](std::size_t k) { std::size_t m = 0; while (k + m < n && t[k + m] == '-') ++m; return m; };
    auto dash_then_word = [&](std::size_t k) {             // (?=-{2,}\w)
        std::size_t m = hyphens(k);
        return m >= 2 && k + m < n && is_word(t[k + m]);
    };
    std::vector<U> out;
    for (std::size_t s = 0; s < n;) {
        std::size_t end;
        if (is_wrap_space(t[s])) {                         // any whitespace
            end = s;
            while (end < n && is_wrap_space(t[end])) ++end;
        } else if (s > 0 && is_word_punct(t[s - 1]) && dash_then_word(s)) {   // em-dash between words
            end = s + hyphens(s);
        } else {                                           // a word, possibly hyphenated: the shortest that ends well
            end = n;
            for (std::size_t e = s + 1; e <= n; ++e) {
                if (e < n && t[e] == '-' &&
                    ((e >= 2 && is_letter(t[e - 2]) && is_letter(t[e - 1])) ||
                     (e >= 3 && is_letter(t[e - 3]) && t[e - 2] == '-' && is_letter(t[e - 1]))) &&
                    is_letter(at(e + 1)) && (is_letter(at(e + 2)) || (at(e + 2) == '-' && is_letter(at(e + 3))))) {
                    end = e + 1;                           // hyphenated word: up to and with the hyphen
                    break;
                }
                if (e == n || is_wrap_space(t[e])) { end = e; break; }      // end of word
                if (is_word_punct(t[e - 1]) && dash_then_word(e)) { end = e; break; }   // before an em-dash
            }
        }
        out.push_back(t.substr(s, end - s));
        s = end;
    }
    return out;
}

[[noreturn]] void refuse(const std::string& why) { throw std::invalid_argument(why); }

std::size_t len(const U& s) { return s.size(); }

// TextWrapper._wrap_chunks with drop_whitespace, break_long_words and break_on_hyphens on (textwrap's defaults)
std::vector<U> wrap_chunks(std::vector<U> chunks, Int width_all, const U& initial_indent, const U& subsequent_indent,
                           std::optional<Int> max_lines, const U& placeholder) {
    std::vector<U> lines;
    if (width_all <= 0) refuse("invalid width " + std::to_string(width_all) + " (must be > 0)");
    if (max_lines) {
        const U& indent = *max_lines > 1 ? subsequent_indent : initial_indent;
        if (static_cast<Int>(len(indent) + len(strip(placeholder, true, false))) > width_all)
            refuse("placeholder too large for max width");
    }
    std::reverse(chunks.begin(), chunks.end());
    while (!chunks.empty()) {
        std::vector<U> cur_line;
        Int cur_len = 0;
        const U& indent = lines.empty() ? initial_indent : subsequent_indent;
        Int width = width_all - static_cast<Int>(len(indent));
        if (blank(chunks.back()) && !lines.empty()) chunks.pop_back();
        while (!chunks.empty()) {
            Int l = static_cast<Int>(len(chunks.back()));
            if (cur_len + l <= width) {
                cur_line.push_back(chunks.back());
                chunks.pop_back();
                cur_len += l;
            } else {
                break;
            }
        }
        if (!chunks.empty() && static_cast<Int>(len(chunks.back())) > width) {   // _handle_long_word
            Int space_left = width < 1 ? 1 : width - cur_len;
            Int end = space_left;
            U& chunk = chunks.back();
            if (static_cast<Int>(len(chunk)) > space_left) {
                std::size_t limit = static_cast<std::size_t>(std::max<Int>(0, space_left));
                std::size_t hyphen = chunk.substr(0, limit).rfind(U'-');
                if (hyphen != U::npos && hyphen > 0 &&
                    std::any_of(chunk.begin(), chunk.begin() + static_cast<std::ptrdiff_t>(hyphen),
                                [](char32_t c) { return c != '-'; }))
                    end = static_cast<Int>(hyphen) + 1;
            }
            std::size_t cut = static_cast<std::size_t>(std::max<Int>(0, end));
            cur_line.push_back(chunk.substr(0, cut));
            chunk = chunk.substr(std::min(cut, chunk.size()));
            cur_len = 0;
            for (const U& c : cur_line) cur_len += static_cast<Int>(len(c));
        }
        if (!cur_line.empty() && blank(cur_line.back())) {
            cur_len -= static_cast<Int>(len(cur_line.back()));
            cur_line.pop_back();
        }
        if (cur_line.empty()) continue;
        auto joined = [&](const std::vector<U>& parts) {
            U out = indent;
            for (const U& p : parts) out += p;
            return out;
        };
        bool rest_blank = chunks.empty() || (chunks.size() == 1 && blank(chunks[0]));
        if (!max_lines || static_cast<Int>(lines.size()) + 1 < *max_lines || (rest_blank && cur_len <= width)) {
            lines.push_back(joined(cur_line));
            continue;
        }
        bool placed = false;
        while (!cur_line.empty()) {
            if (!blank(cur_line.back()) && cur_len + static_cast<Int>(len(placeholder)) <= width) {
                cur_line.push_back(placeholder);
                lines.push_back(joined(cur_line));
                placed = true;
                break;
            }
            cur_len -= static_cast<Int>(len(cur_line.back()));
            cur_line.pop_back();
        }
        if (!placed) {
            bool joined_prev = false;
            if (!lines.empty()) {
                U prev = strip(lines.back(), false, true);
                if (static_cast<Int>(len(prev) + len(placeholder)) <= width_all) {
                    lines.back() = prev + placeholder;
                    joined_prev = true;
                }
            }
            if (!joined_prev) lines.push_back(indent + strip(placeholder, true, false));
        }
        break;
    }
    return lines;
}

}  // namespace

std::string upper_first(const std::string& text) {
    U t = decode(text);
    if (t.empty()) return text;
    char32_t c = t[0];
    U first(1, c);
    if (in(c, 'a', 'z') || (in(c, 0xE0, 0xFE) && c != 0xF7) || in(c, 0x3B1, 0x3C1) || in(c, 0x3C3, 0x3CB) ||
        in(c, 0x430, 0x44F))
        first[0] = c - 0x20;
    else if (c == 0xFF) first[0] = 0x178;
    else if (c == 0xDF) first = U(U"SS");
    else if (c == 0xB5) first[0] = 0x39C;
    else if (c == 0x3C2) first[0] = 0x3A3;
    else if (in(c, 0x450, 0x45F)) first[0] = c - 0x50;
    else if (c == 0x3AC) first[0] = 0x386;
    else if (in(c, 0x3AD, 0x3AF)) first[0] = c - 0x25;
    else if (c == 0x3CC) first[0] = 0x38C;
    else if (in(c, 0x3CD, 0x3CE)) first[0] = c - 0x3F;
    else if (c == 0x131) first[0] = 'I';
    else if (c == 0x149) first = U{0x2BC, 'N'};
    else if (c == 0x17F) first[0] = 'S';
    else if ((in(c, 0x101, 0x137) && c % 2 == 1) || (in(c, 0x13A, 0x148) && c % 2 == 0) ||
             (in(c, 0x14B, 0x177) && c % 2 == 1) || (in(c, 0x17A, 0x17E) && c % 2 == 0))
        first[0] = c - 1;
    return encode(first + t.substr(1));
}

std::string display_name(const OptStr& ident, const Names* names) {
    if (!ident) return "no one";
    if (names) {
        auto it = names->find(*ident);
        if (it != names->end()) return it->second;
    }
    std::string out = *ident;
    for (char& c : out)
        if (c == '_') c = ' ';
    return out;
}

std::string cargo(const Counts& cargo) {
    if (cargo.empty()) return "nothing";
    std::string out;
    for (const auto& kv : cargo) {                  // sorted by good; a zero amount is left out
        if (kv.second == 0) continue;
        if (!out.empty()) out += ", ";
        out += std::to_string(kv.second) + " " + kv.first;
    }
    return out;
}

std::string stamp(Int hour) {
    Int day = floordiv(hour, HOURS_PER_DAY) + 1, h = hour - floordiv(hour, HOURS_PER_DAY) * HOURS_PER_DAY;
    std::string hh = std::to_string(h);
    return "Day " + std::to_string(day) + ", " + (hh.size() < 2 ? "0" + hh : hh) + ":00";
}

std::vector<Value> news_for(const WorldState& ws, const std::string& place, Int since) {
    std::map<std::string, Int> dist = distances(ws, place);
    std::vector<Value> out;
    for (const Value& e : ws.events) {
        Int hour = e.o->at("hour").i;
        auto d = dist.find(e.o->at("place").s);
        if (hour < since || d == dist.end()) continue;
        if (hour + d->second * NEWS_HOURS_PER_ROUTE_HOUR <= ws.hour) out.push_back(e);
    }
    return out;
}

OptStr headline(const Value& e, const Names* names) {
    OptStr key = template_key(e);
    if (!key) return std::nullopt;
    std::map<std::string, std::string> fields;                // news._fields
    for (const char* k : {"place", "faction", "previous", "target", "origin", "raider", "defender", "holder",
                          "from_role", "to_role"})
        if (const Value* v = get(e, k)) fields[k] = display_name(as_name(*v), names);
    const Value* c = get(e, "cargo");
    fields["cargo"] = truthy(c) ? cargo(counts_of(c)) : "nothing";
    if (e.o->at("kind").s == "priority_set") {
        const Value* g = get(e, "new");
        fields["good"] = display_name(g ? as_name(*g) : std::nullopt, names);
    }
    const std::string& t = templates().at(*key);
    std::string text;
    for (std::size_t k = 0; k < t.size();) {
        if (t[k] != '{') { text.push_back(t[k++]); continue; }
        std::size_t end = t.find('}', k);
        auto f = fields.find(t.substr(k + 1, end - k - 1));
        if (f == fields.end())                                 // Python: KeyError from str.format
            throw std::out_of_range("event " + e.o->at("kind").s + " lacks " + t.substr(k + 1, end - k - 1));
        text += f->second;
        k = end + 1;
    }
    return upper_first(text);
}

Value items(const WorldState& ws, const std::string& place, Int since, Int limit, const Names* names) {
    std::vector<Value> reached = news_for(ws, place, since);
    std::vector<std::size_t> order(reached.size());
    for (std::size_t k = 0; k < order.size(); ++k) order[k] = k;
    std::stable_sort(order.begin(), order.end(), [&](std::size_t a, std::size_t b) {   // newest first, ties in log order
        return reached[a].o->at("hour").i > reached[b].o->at("hour").i;
    });
    Array out;
    std::set<std::string> seen;
    for (std::size_t k : order) {
        if (static_cast<Int>(out.size()) >= limit) break;
        const Value& e = reached[k];
        OptStr text = headline(e, names);
        if (!text || seen.count(*text)) continue;
        seen.insert(*text);
        out.push_back(Value::object({{"hour", e.o->at("hour")}, {"kind", e.o->at("kind")}, {"place", e.o->at("place")},
                                     {"text", Value::string(*text)}}));
    }
    return Value::array(std::move(out));
}

std::vector<std::string> headlines(const WorldState& ws, const std::string& place, Int since, Int limit,
                                   const Names* names) {
    std::vector<std::string> out;
    for (const Value& i : *items(ws, place, since, limit, names).a) out.push_back(i.o->at("text").s);
    return out;
}

std::string terminal_page(const WorldState& ws, const std::string& place, Int since, Int limit, Int width,
                          const Names* names) {
    std::string title = display_name(place, names) + " news, " + stamp(ws.hour);
    std::vector<std::string> lines{shorten(title, width, "...")};
    Int rule = std::min<Int>(width, static_cast<Int>(decode(title).size()));
    lines.push_back(std::string(static_cast<std::size_t>(std::max<Int>(0, rule)), '-'));
    Value found = items(ws, place, since, limit, names);
    if (found.a->empty())
        for (const std::string& l : wrap("No news has reached " + display_name(place, names) + ".", width))
            lines.push_back(l);
    for (const Value& i : *found.a)
        for (const std::string& l : wrap(stamp(i.o->at("hour").i) + ": " + i.o->at("text").s, width, "  "))
            lines.push_back(l);
    std::string out;
    for (std::size_t k = 0; k < lines.size(); ++k) out += (k ? "\n" : "") + lines[k];
    return out;
}

std::vector<std::string> wrap(const std::string& text, Int width, const std::string& subsequent_indent) {
    std::vector<std::string> out;
    for (const U& line : wrap_chunks(split_chunks(munge(decode(text))), width, U(), decode(subsequent_indent),
                                     std::nullopt, U()))
        out.push_back(encode(line));
    return out;
}

std::string shorten(const std::string& text, Int width, const std::string& placeholder) {
    U words, t = decode(text);                                 // ' '.join(text.strip().split())
    for (std::size_t k = 0; k < t.size();) {
        while (k < t.size() && is_py_space(t[k])) ++k;
        std::size_t b = k;
        while (k < t.size() && !is_py_space(t[k])) ++k;
        if (k > b) {
            if (!words.empty()) words.push_back(U' ');
            words += t.substr(b, k - b);
        }
    }
    std::vector<U> lines = wrap_chunks(split_chunks(munge(words)), width, U(), U(), 1, decode(placeholder));
    std::string out;
    for (std::size_t k = 0; k < lines.size(); ++k) out += (k ? "\n" : "") + encode(lines[k]);
    return out;
}

}  // namespace foccsim::news
