// FOCCSim's presentation planner (see present.h). Each function names the Python one it copies from
// src/fo4sf/combined/present.py.
#include "present.h"

#include <algorithm>
#include <set>
#include <stdexcept>

namespace foccsim::present {

namespace {

constexpr Int GARRISON_BASE = 1;
constexpr Int GARRISON_PER_DEFENCE = 1;
constexpr Int GARRISON_STRENGTH_SHARE_CAP = 10;
constexpr Int GARRISON_MAX = 8;
constexpr Int SETTLERS_PER_ROLE_MAX = 6;
constexpr Int SQUAD_ACTORS_MAX = 8;
constexpr Int CARAVAN_ACTORS = 2;
const char* const ROLES[] = {"farmer", "guard", "trader", "crafter", "scavenger", "doctor"};   // model.ROLES

Int class_rank(const OptStr& cls) {                    // CLASS_RANK.get(cls, max(CLASS_RANK.values()) + 1)
    static const std::map<std::string, Int> ranks = {{"attack", 0}, {"garrison", 1}, {"settler", 2},
                                                      {"patrol", 3}, {"caravan", 4}, {"player", 5}};
    if (!cls) return 6;
    auto it = ranks.find(*cls);
    return it == ranks.end() ? 6 : it->second;
}

Value opt(const OptStr& s) { return s ? Value::string(*s) : Value::null(); }

Value slots_value(const std::vector<Slot>& slots) {
    Array a;
    for (const Slot& s : slots) a.push_back(s.to_value());
    return Value::array(std::move(a));
}

std::string squad_place(const WorldState& ws, const Squad& q) {   // present._squad_place
    if (!q.goal || *q.goal == q.at) return q.at;
    std::map<std::string, Int> dist = distances(ws, q.at);
    auto it = dist.find(*q.goal);
    if (it == dist.end() || it->second == 0) return q.at;
    Int hours = it->second;
    Int elapsed = ws.hour - (q.eta - hours);
    return 2 * elapsed >= hours ? *q.goal : q.at;
}

std::string id_component(const std::string& value) {   // present._id_component: "%" -> "%25", then ":" -> "%3A"
    std::string out;
    for (char c : value) {
        if (c == '%') out += "%25";
        else if (c == ':') out += "%3A";
        else out.push_back(c);
    }
    return out;
}

void place_slots(const WorldState& ws, const std::string& place, Int dist, std::vector<Slot>& out) {
    const Place& pl = ws.places.at(place);
    Int n = garrison_size(ws, place);
    if (n != 0) out.push_back({"garrison:" + id_component(place) + ":" + id_component(pl.holder.value_or("None")),
                               "garrison", place, pl.holder, n, std::nullopt, dist});
    auto st = ws.settlements.find(place);
    if (st == ws.settlements.end()) return;
    for (const char* role : ROLES) {
        auto r = st->second.roles.find(role);
        Int k = std::min(SETTLERS_PER_ROLE_MAX, r == st->second.roles.end() ? Int(0) : r->second);
        if (k != 0) out.push_back({std::string("settler:") + place + ":" + role, "settler", place, pl.holder, k,
                                   std::string(role), dist});
    }
}

void squad_slots(const WorldState& ws, const std::map<std::string, Int>& dist, Int radius, std::vector<Slot>& out) {
    auto within = [&](const std::string& p) {
        auto it = dist.find(p);
        return (it == dist.end() ? radius + 1 : it->second) <= radius;
    };
    for (const auto& kv : ws.squads) {                  // sorted by id
        const Squad& q = kv.second;
        if (!within(q.at) && !(q.goal && within(*q.goal))) continue;
        std::string where = squad_place(ws, q);
        auto d = dist.find(where);
        if (d == dist.end() || d->second > radius) continue;   // still at its far end: not shown ahead of its ETA
        if (q.kind == "caravan")
            out.push_back({"caravan:" + kv.first, "caravan", where, q.faction, CARAVAN_ACTORS, std::string("caravan"),
                           d->second});
        else
            out.push_back({"squad:" + kv.first, "squad", where, q.faction, std::min(SQUAD_ACTORS_MAX, q.size), q.kind,
                           d->second});
    }
}

}  // namespace

std::tuple<Int, Int, std::string> Slot::rank() const {
    OptStr cls = kind == "squad" ? role : OptStr(kind);
    if (faction && *faction == "player") cls = "player";
    return {distance, class_rank(cls), id};
}

Value Slot::to_value() const {
    return Value::object({{"count", Value::integer(count)}, {"distance", Value::integer(distance)},
                          {"faction", opt(faction)}, {"id", Value::string(id)}, {"kind", Value::string(kind)},
                          {"place", Value::string(place)}, {"role", opt(role)}});
}

Int Plan::actors() const {
    Int n = 0;
    for (const Slot& s : slots) n += s.count;
    return n;
}

Value Plan::to_value() const {
    Array ps;
    for (const std::string& p : places) ps.push_back(Value::string(p));
    return Value::object({{"centre", Value::string(centre)}, {"dropped", slots_value(dropped)},
                          {"hour", Value::integer(hour)}, {"places", Value::array(std::move(ps))},
                          {"radius_hours", Value::integer(radius_hours)}, {"slots", slots_value(slots)}});
}

Value Diff::to_value() const {
    return Value::object({{"dissolve", slots_value(dissolve)}, {"keep", slots_value(keep)},
                          {"spawn", slots_value(spawn)}});
}

Int garrison_size(const WorldState& ws, const std::string& place) {
    const Place& pl = ws.places.at(place);
    if (!pl.holder) return 0;
    Int n = GARRISON_BASE + GARRISON_PER_DEFENCE * pl.defence;
    n += floordiv(std::min(ws.factions.at(*pl.holder).strength, GARRISON_STRENGTH_SHARE_CAP), 2);
    return std::min(GARRISON_MAX, n);
}

Plan plan(const WorldState& ws, const std::string& player_place, Int radius_hours, Int max_actors) {
    if (!ws.places.count(player_place)) throw std::out_of_range("unknown place '" + player_place + "'");
    std::map<std::string, Int> dist = distances(ws, player_place);
    std::vector<std::pair<Int, std::string>> near;
    for (const auto& kv : dist)
        if (kv.second <= radius_hours) near.emplace_back(kv.second, kv.first);
    std::sort(near.begin(), near.end());
    std::vector<Slot> slots;
    for (const auto& dp : near) place_slots(ws, dp.second, dp.first, slots);
    squad_slots(ws, dist, radius_hours, slots);
    std::stable_sort(slots.begin(), slots.end(), [](const Slot& a, const Slot& b) { return a.rank() < b.rank(); });
    Plan out{player_place, ws.hour, radius_hours, {}, {}, {}};
    for (const auto& dp : near) out.places.push_back(dp.second);
    Int used = 0;
    for (Slot& s : slots) {
        if (used + s.count <= max_actors) {
            used += s.count;
            out.slots.push_back(std::move(s));
        } else {
            out.dropped.push_back(std::move(s));
        }
    }
    return out;
}

Diff diff(const Plan* old_plan, const Plan& new_plan) {
    std::map<std::string, const Slot*> before, after;
    if (old_plan)
        for (const Slot& s : old_plan->slots) before[s.id] = &s;
    for (const Slot& s : new_plan.slots) after[s.id] = &s;
    if (old_plan && before.size() != old_plan->slots.size())         // Python's ValueError
        throw std::invalid_argument("old presence plan has duplicate slot ids");
    if (after.size() != new_plan.slots.size())
        throw std::invalid_argument("new presence plan has duplicate slot ids");
    std::set<std::string> ids;
    for (const auto& kv : before) ids.insert(kv.first);
    for (const auto& kv : after) ids.insert(kv.first);
    Diff out;
    for (const std::string& sid : ids) {
        auto a = before.find(sid), b = after.find(sid);
        if (a == before.end()) {
            out.spawn.push_back(*b->second);
        } else if (b == after.end()) {
            out.dissolve.push_back(*a->second);
        } else if (a->second->place == b->second->place && a->second->faction == b->second->faction &&
                   a->second->count == b->second->count) {
            out.keep.push_back(*b->second);
        } else {
            out.dissolve.push_back(*a->second);
            out.spawn.push_back(*b->second);
        }
    }
    return out;
}

}  // namespace foccsim::present
