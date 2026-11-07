// FOCCSim's engine adapter (see adapter.h). Each function names the Python one it copies from
// src/fo4sf/combined/adapter.py.
#include "adapter.h"

#include <algorithm>
#include <stdexcept>

namespace foccsim::adapter {

namespace {

const char* const PLACE_PART = "Place";                                       // adapter.PLACE_PART
const char* const REP_PART = "Rep";                                           // adapter.REP_PART
const char* const SETTINGS_GLOBALS[] = {"Survival", "RaidPressure", "StoryMode", "StoryActive"};
const char* const PROBE_KEYWORD_DATA = "P2";                                  // keyword data's save persistence
const char* const SURVIVAL_PRESET_NAMES[] = {"off", "light", "full"};         // modes.SURVIVAL_PRESET_NAMES
const char* const RAID_PRESSURE_NAMES[] = {"low", "normal", "high"};          // modes.RAID_PRESSURE_NAMES
constexpr Int LEVEL_THRESHOLDS[] = {0, 10, 25, 50};                           // reputation.LEVEL_THRESHOLDS
constexpr Int LEVELS = 4;                                                     // reputation.LEVELS

bool continuation(unsigned char c) { return (c & 0xC0) == 0x80; }            // a UTF-8 byte after a lead byte
bool word(unsigned char c) {
    return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_';
}

// re.sub(r"[^A-Za-z0-9_]", "_", part): one underscore per character, so a non-ASCII character is one underscore too
std::string sanitize(const std::string& part) {
    std::string out;
    for (char ch : part) {
        unsigned char c = static_cast<unsigned char>(ch);
        if (continuation(c)) continue;
        out.push_back(word(c) ? ch : '_');
    }
    return out;
}

std::size_t characters(const std::string& s) {                               // Python's len() of the str
    return static_cast<std::size_t>(std::count_if(s.begin(), s.end(), [](char c) {
        return !continuation(static_cast<unsigned char>(c));
    }));
}

bool valid(const std::string& eid) {                                         // adapter.EDITOR_ID_RE
    if (eid.empty()) return false;
    unsigned char first = static_cast<unsigned char>(eid[0]);
    if (!word(first) || (first >= '0' && first <= '9')) return false;
    return std::all_of(eid.begin(), eid.end(), [](char c) { return word(static_cast<unsigned char>(c)); });
}

std::string quoted(const std::string& s) { return "'" + s + "'"; }          // repr() of a plain ASCII id

template <std::size_t N>
Int index_of(const char* const (&names)[N], const std::string& name) {      // tuple.index
    for (std::size_t k = 0; k < N; ++k)
        if (name == names[k]) return static_cast<Int>(k);
    throw std::invalid_argument(quoted(name) + " is not in the list");
}

Int setting_value(const WorldState& ws, const std::string& name) {          // adapter._setting_value
    const Settings& s = ws.settings;
    if (name == "Survival") return index_of(SURVIVAL_PRESET_NAMES, s.survival);
    if (name == "RaidPressure") return index_of(RAID_PRESSURE_NAMES, s.raid_pressure);
    if (name == "StoryMode") return s.story_mode ? 1 : 0;
    if (name == "StoryActive") return s.story_mode && !s.active_stories.empty() ? 1 : 0;   // as Settings.story_active
    throw std::out_of_range(name);                                           // Python: KeyError
}

}  // namespace

std::string editor_id(const std::vector<std::string>& parts, const std::string& prefix) {
    std::string body;
    for (const std::string& p : parts) {
        if (p.empty()) continue;
        if (!body.empty()) body.push_back('_');
        body += sanitize(p);
    }
    if (body.empty()) throw std::invalid_argument("editor id needs at least one non-empty part");
    std::string eid = prefix + body;
    if (characters(eid) > EDITOR_ID_MAX)
        throw std::invalid_argument("editor id " + quoted(eid) + " longer than " + std::to_string(EDITOR_ID_MAX));
    if (!valid(eid)) throw std::invalid_argument("invalid editor id " + quoted(eid));
    return eid;
}

std::map<std::string, Int> holder_codes(const WorldState& ws) {
    std::map<std::string, Int> codes;
    Int n = EMPTY_HOLDER;
    for (const auto& kv : ws.factions) codes[kv.first] = ++n;                // std::map walks the ids sorted
    return codes;
}

Int reputation_level(Int points) {
    Int p = std::max<Int>(0, points), best = 0;
    for (Int k = 0; k < LEVELS; ++k)
        if (p >= LEVEL_THRESHOLDS[k]) best = k;
    return best;
}

Int reputation_tier(const WorldState& ws, const std::string& faction) {
    const Reputation& rep = ws.reputation.at(faction);
    return reputation_level(rep.fame) * LEVELS + reputation_level(rep.infamy);
}

Plan record_plan(const WorldState& ws, const std::string& prefix) {
    std::vector<Slot> slots;
    for (const auto& kv : ws.places)
        slots.push_back({editor_id({PLACE_PART, kv.first}, prefix), "keyword", "holder", kv.first, PROBE_KEYWORD_DATA});
    for (const auto& kv : ws.factions)
        slots.push_back({editor_id({REP_PART, kv.first}, prefix), "global", "reputation", kv.first, std::nullopt});
    for (const char* name : SETTINGS_GLOBALS)
        slots.push_back({editor_id({name}, prefix), "global", "setting", name, std::nullopt});
    std::map<std::string, std::string> seen;                                 // id -> the first subject that took it
    for (const Slot& s : slots) {
        auto [it, fresh] = seen.emplace(s.id, s.subject);
        if (!fresh)
            throw std::invalid_argument("editor id " + quoted(s.id) + " collides: " + quoted(it->second) + " and " +
                                        quoted(s.subject));
    }
    std::sort(slots.begin(), slots.end(), [](const Slot& a, const Slot& b) { return a.id < b.id; });  // ids unique
    return Plan{prefix, holder_codes(ws), std::move(slots)};
}

View game_view(const WorldState& ws, const Plan& plan) {
    View out;
    for (const Slot& s : plan.slots) {
        if (s.purpose == "holder") {
            const OptStr& holder = ws.places.at(s.subject).holder;
            out[s.id] = holder ? plan.holder_codes.at(*holder) : EMPTY_HOLDER;
        } else if (s.purpose == "reputation") {
            out[s.id] = reputation_tier(ws, s.subject);
        } else {
            out[s.id] = setting_value(ws, s.subject);
        }
    }
    return out;
}

Writes changes(const View* old_view, const View& new_view) {
    Writes out;
    for (const auto& kv : new_view) {                                        // sorted by id, as Python sorts
        if (old_view) {
            auto it = old_view->find(kv.first);
            if (it != old_view->end() && it->second == kv.second) continue;
        }
        out.emplace_back(kv.first, kv.second);
    }
    return out;
}

Value Plan::to_value() const {
    Object codes;
    for (const auto& kv : holder_codes) codes[kv.first] = Value::integer(kv.second);
    Array rows;
    for (const Slot& s : slots)
        rows.push_back(Value::object({{"id", Value::string(s.id)}, {"kind", Value::string(s.kind)},
                                      {"probe", s.probe ? Value::string(*s.probe) : Value::null()},
                                      {"purpose", Value::string(s.purpose)}, {"subject", Value::string(s.subject)}}));
    return Value::object({{"holder_codes", Value::object(std::move(codes))}, {"prefix", Value::string(prefix)},
                          {"slots", Value::array(std::move(rows))}});
}

Value view_value(const View& view) {
    Object o;
    for (const auto& kv : view) o[kv.first] = Value::integer(kv.second);
    return Value::object(std::move(o));
}

Value writes_value(const Writes& writes) {
    Array a;
    for (const auto& w : writes) a.push_back(Value::array({Value::string(w.first), Value::integer(w.second)}));
    return Value::array(std::move(a));
}

}  // namespace foccsim::adapter
