// FOCCSim's settlement management (see manage.h). Each function names the Python one it copies from
// src/fo4sf/combined/manage.py.
#include "manage.h"

#include <algorithm>
#include <cstdio>
#include <stdexcept>
#include <utility>
#include <vector>

namespace foccsim::manage {

namespace {

constexpr Int TICKS_PER_DAY = 24 / 6;                                         // 24 // sim.TICK_HOURS
const char* const GOODS[] = {"food", "water", "scrap", "ammo", "medicine"};  // model.GOODS
const char* const ROLES[] = {"farmer", "guard", "trader", "crafter", "scavenger", "doctor"};   // model.ROLES

template <std::size_t N>
std::string tuple_repr(const char* const (&names)[N]) {                       // repr() of a tuple of str
    std::string out = "(";
    for (std::size_t k = 0; k < N; ++k) out += (k ? ", " : "") + py_repr(names[k]);
    return out + ")";
}

template <std::size_t N>
bool one_of(const char* const (&names)[N], const std::string& x) {
    return std::any_of(std::begin(names), std::end(names), [&](const char* n) { return x == n; });
}

[[noreturn]] void refuse(const std::string& why) { throw std::invalid_argument(why); }

Settlement& settlement_of(WorldState& ws, const std::string& place) {        // manage._settlement
    auto it = ws.settlements.find(place);
    if (it == ws.settlements.end()) refuse(py_repr(place) + " is not a settlement");
    return it->second;
}

const Settlement& settlement_of(const WorldState& ws, const std::string& place) {
    auto it = ws.settlements.find(place);
    if (it == ws.settlements.end()) refuse(py_repr(place) + " is not a settlement");
    return it->second;
}

Int count(Int n, const std::string& what) {                                   // manage._count, for an int
    if (n <= 0) refuse(what + " must be a positive integer, got " + std::to_string(n));
    return n;
}

Value days_left(Int stock, Int population) {                                  // manage._days_left
    if (population <= 0) return Value::null();
    return Value::integer(floordiv(stock, population * TICKS_PER_DAY));
}

Value opt(const OptStr& s) { return s ? Value::string(*s) : Value::null(); }

}  // namespace

std::string py_repr(const std::string& s) {
    char q = (s.find('\'') != std::string::npos && s.find('"') == std::string::npos) ? '"' : '\'';
    std::string out(1, q);
    for (char ch : s) {
        unsigned char c = static_cast<unsigned char>(ch);
        if (ch == q || ch == '\\') { out.push_back('\\'); out.push_back(ch); }
        else if (ch == '\n') out += "\\n";
        else if (ch == '\r') out += "\\r";
        else if (ch == '\t') out += "\\t";
        else if (c < 0x20 || c == 0x7F) {
            char buf[5];
            std::snprintf(buf, sizeof buf, "\\x%02x", c);
            out += buf;
        } else out.push_back(ch);
    }
    out.push_back(q);
    return out;
}

Counts assign_role(WorldState& ws, const std::string& settlement, const std::string& from_role,
                   const std::string& to_role, Int n) {
    Settlement& s = settlement_of(ws, settlement);
    for (const std::string* role : {&from_role, &to_role})
        if (!one_of(ROLES, *role)) refuse("unknown role " + py_repr(*role) + ", want one of " + tuple_repr(ROLES));
    if (from_role == to_role) refuse("from_role and to_role are both " + py_repr(from_role));
    n = count(n, "n");
    Int have = s.roles.at(from_role);
    if (have < n)
        refuse(settlement + " has " + std::to_string(have) + " " + from_role + "(s), cannot move " + std::to_string(n));
    s.roles.at(from_role) -= n;
    s.roles.at(to_role) += n;
    event(ws, "roles_changed", settlement, {{"from_role", Value::string(from_role)}, {"to_role", Value::string(to_role)},
                                            {"n", Value::integer(n)}});
    return s.roles;
}

Int add_beds(WorldState& ws, const std::string& settlement, Int n) {
    Settlement& s = settlement_of(ws, settlement);
    n = count(n, "n");
    if (s.beds + n > BEDS_MAX)
        refuse(settlement + " has " + std::to_string(s.beds) + " beds; " + std::to_string(n) +
               " more would pass the cap of " + std::to_string(BEDS_MAX));
    s.beds += n;
    event(ws, "beds_added", settlement, {{"n", Value::integer(n)}, {"beds", Value::integer(s.beds)}});
    return s.beds;
}

OptStr set_priority(WorldState& ws, const std::string& settlement, const OptStr& good) {
    Settlement& s = settlement_of(ws, settlement);
    if (good && !one_of(GOODS, *good))
        refuse("unknown good " + py_repr(*good) + ", want one of " + tuple_repr(GOODS) + " or None");
    OptStr old = s.priority;
    s.priority = good;
    event(ws, "priority_set", settlement, {{"old", opt(old)}, {"new", opt(good)}});
    return good;
}

std::string send_supplies(WorldState& ws, const std::string& from_settlement, const std::string& to_settlement,
                          const Counts& goods) {
    Settlement& src = settlement_of(ws, from_settlement);
    settlement_of(ws, to_settlement);
    if (from_settlement == to_settlement) refuse(from_settlement + " cannot send supplies to itself");
    const OptStr& holder = ws.places.at(from_settlement).holder;
    if (!holder) refuse(from_settlement + " is held by no faction, nobody to run the caravan");
    if (ws.places.at(to_settlement).holder != holder)
        refuse(to_settlement + " is not held by " + *holder + ", who holds " + from_settlement);
    std::map<std::string, Int> dist = distances(ws, from_settlement);
    auto route = dist.find(to_settlement);
    if (route == dist.end()) refuse("no route connects " + from_settlement + " and " + to_settlement);
    if (goods.empty()) refuse("goods must be a non-empty dict of good -> amount");
    Counts cargo;
    for (const auto& [g, n] : goods) {                                        // sorted, as Python walks sorted(goods)
        if (!one_of(GOODS, g)) refuse("unknown good " + py_repr(g) + ", want one of " + tuple_repr(GOODS));
        Int amount = count(n, "amount of " + g);
        Int have = src.stock.at(g);
        if (have < amount)
            refuse(from_settlement + " has " + std::to_string(have) + " " + g + ", cannot send " + std::to_string(amount));
        cargo[g] = amount;
    }
    for (const auto& [g, amount] : cargo) src.stock.at(g) -= amount;
    Squad q;
    q.id = new_id(ws, "c");
    q.faction = *holder;
    q.size = 2;
    q.at = from_settlement;
    q.goal = to_settlement;
    q.kind = "caravan";
    q.cargo = cargo;
    q.eta = ws.hour + route->second;
    ws.squads[q.id] = q;
    event(ws, "supplies_sent", from_settlement, {{"target", Value::string(to_settlement)},
                                                 {"cargo", counts_value(cargo)}, {"squad", Value::string(q.id)},
                                                 {"eta", Value::integer(q.eta)}});
    return q.id;
}

Value threats(const WorldState& ws, const std::string& settlement, Int hours) {
    settlement_of(ws, settlement);
    const OptStr& holder = ws.places.at(settlement).holder;
    std::vector<std::pair<Int, std::string>> near;                            // by (hours, place)
    for (const auto& [pid, d] : distances(ws, settlement)) near.emplace_back(d, pid);
    std::sort(near.begin(), near.end());
    Array out;
    for (const auto& [d, pid] : near) {
        const Place& pl = ws.places.at(pid);
        if (pid != settlement && d <= hours && pl.holder && hostile(ws, *pl.holder, holder))
            out.push_back(Value::object({{"place", Value::string(pid)}, {"holder", Value::string(*pl.holder)},
                                         {"hours", Value::integer(d)}, {"kind", Value::string(pl.kind)}}));
    }
    return Value::array(std::move(out));
}

Value status(const WorldState& ws, const std::string& settlement) {
    const Settlement& s = settlement_of(ws, settlement);
    Array incoming;                                                           // squad ids, sorted (std::map order)
    for (const auto& [qid, q] : ws.squads)
        if (q.kind == "attack" && q.goal == settlement) incoming.push_back(Value::string(qid));
    return Value::object({
        {"place", Value::string(settlement)},
        {"holder", opt(ws.places.at(settlement).holder)},
        {"population", Value::integer(s.population)},
        {"roles", counts_value(s.roles)},
        {"stock", counts_value(s.stock)},
        {"food_days", days_left(s.stock.at("food"), s.population)},
        {"water_days", days_left(s.stock.at("water"), s.population)},
        {"morale", Value::integer(s.morale)},
        {"stage", Value::integer(s.stage)},
        {"beds", Value::integer(s.beds)},
        {"priority", opt(s.priority)},
        {"defence", Value::integer(defence(ws, settlement))},
        {"incoming_attacks", Value::array(std::move(incoming))},
        {"threats", threats(ws, settlement)},
    });
}

}  // namespace foccsim::manage
