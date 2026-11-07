// FOCCSim: the combined core's world state and tick (see foccsim.h). Each function names the Python one it copies.
#include "foccsim.h"

#include <algorithm>
#include <stdexcept>
#include <utility>

#include "pyrandom.h"

// GCC 13's -Wdangling-reference flags obj(value, "what" + name) below: the reference it returns is into the Value, not
// into the temporary message string, so the warning is a false positive here.
#if defined(__GNUC__) && !defined(__clang__) && __GNUC__ >= 13
#pragma GCC diagnostic ignored "-Wdangling-reference"
#endif

namespace foccsim {

namespace {

// --- constants (sim.py, model.py, modes.py, reputation.py) --------------------------------------------------------
constexpr Int TICK_HOURS = 6;
constexpr Int STAGE_POP[] = {0, 4, 8, 14, 22};
constexpr Int STRENGTH_CAP = 60;
constexpr Int STRENGTH_INCOME_PER_PLACE = 2;
constexpr Int UPKEEP_PER_PLACE = 1;
constexpr Int RETAKE_WEIGHT = 3;
constexpr Int SETTLEMENT_TARGET_WEIGHT = 1;
constexpr double ATTACK_CHANCE_PER_AGGRESSION = 0.25;
constexpr double RAID_CHANCE_PER_STRENGTH = 0.01;
constexpr double RAID_CHANCE_CAP = 0.35;
constexpr Int RAID_STRENGTH_GAIN = 1;
constexpr Int PLAYER_DEFENCE_FAME = 4;
constexpr Int TRADE_GOODS_PER_TIER = 10;
constexpr Int PRIORITY_BONUS_PER_WORKER = 1;
constexpr Int REROLE_ON_SHORTAGE = 1;
constexpr Int RESETTLE_SAFE_HOURS = 48;
constexpr Int RESETTLE_KIT = 6;
constexpr Int RESETTLE_MORALE = 50;
constexpr Int ARRIVAL_SLOWDOWN_POP = 3;
constexpr Int FARM_SLOTS_PER_BEDS = 4;
constexpr Int LEAVE_ONLY_WHEN_SHORT = 1;
constexpr Int MORALE_DRIFT = 1;
constexpr Int STORY_SHIELD_HOURS = 6;
constexpr Int GAIN_TIERS[] = {1, 2, 4, 7, 12};
constexpr Int ENEMY_INFAMY_DIVISOR = 2;
const char* const GOODS[] = {"food", "water", "scrap", "ammo", "medicine"};
const char* const ROLES[] = {"farmer", "guard", "trader", "crafter", "scavenger", "doctor"};

std::string priority_role(const std::string& good) {          // sim.PRIORITY_ROLE
    if (good == "food" || good == "water") return "farmer";
    if (good == "scrap") return "scavenger";
    if (good == "ammo") return "crafter";
    if (good == "medicine") return "doctor";
    throw std::runtime_error("unknown priority good " + good);
}

// sim.rng_seed: seed * 1000003 + hour must fit in 64 unsigned bits (written without 128-bit integers, for MSVC)
bool rng_seed_ok(Int seed, Int hour) {
    if (seed < 0 || hour < 0) return false;
    const std::uint64_t top = ~std::uint64_t(0);
    return static_cast<std::uint64_t>(seed) <= (top - static_cast<std::uint64_t>(hour)) / 1000003u;
}

bool is_attack_event(const std::string& k) { return k == "place_taken" || k == "attack_failed" || k == "place_cleared"; }
bool is_holder_change(const std::string& k) { return k == "place_taken" || k == "place_cleared"; }

// Python's // (floor); every operand in the sim is non-negative today, so this is a guard as much as a helper.
Int floordiv(Int a, Int b) {
    Int q = a / b;
    if ((a % b != 0) && ((a < 0) != (b < 0))) --q;
    return q;
}

Int& at(Counts& m, const std::string& k) {                    // Python's d[k]: a missing key is an error, not a 0
    auto it = m.find(k);
    if (it == m.end()) throw std::runtime_error("missing key " + k);
    return it->second;
}
Int at(const Counts& m, const std::string& k) {
    auto it = m.find(k);
    if (it == m.end()) throw std::runtime_error("missing key " + k);
    return it->second;
}

template <class M> auto& must(M& m, const std::string& k, const char* what) {
    auto it = m.find(k);
    if (it == m.end()) throw std::runtime_error(std::string("unknown ") + what + " " + k);
    return it->second;
}

Value str_or_null(const OptStr& s) { return s ? Value::string(*s) : Value::null(); }
Value counts_value(const Counts& c) {
    Object o;
    for (const auto& kv : c) o[kv.first] = Value::integer(kv.second);
    return Value::object(std::move(o));
}

// --- events (sim._event, _new_id) ---------------------------------------------------------------------------------
void event(WorldState& ws, const std::string& kind, const std::string& place, Object info = {}) {
    info["hour"] = Value::integer(ws.hour);
    info["kind"] = Value::string(kind);
    info["place"] = Value::string(place);
    info["region"] = Value::string(must(ws.places, place, "place").region);
    ws.events.push_back(Value::object(std::move(info)));
}

std::string new_id(WorldState& ws, const char* prefix) {
    Int i = ws.next_id++;
    return std::string(prefix) + std::to_string(i);
}

const std::string& ev_str(const Value& e, const char* key) { return e.o->at(key).s; }

// --- graph (model.WorldState.neighbours, sim._distances) ----------------------------------------------------------
std::vector<std::pair<std::string, Int>> neighbours(const WorldState& ws, const std::string& place) {
    std::vector<std::pair<std::string, Int>> out;
    for (const Route& r : ws.routes) {
        if (r.a == place) out.emplace_back(r.b, r.hours);
        else if (r.b == place) out.emplace_back(r.a, r.hours);
    }
    std::sort(out.begin(), out.end());
    return out;
}

std::map<std::string, Int> distances(const WorldState& ws, const std::string& start) {
    // the shortest route-hours from start; Python's own walk (sort, pop the nearest) settles on the same numbers
    std::map<std::string, Int> best{{start, 0}};
    std::set<std::pair<Int, std::string>> todo{{0, start}};
    while (!todo.empty()) {
        auto [d, p] = *todo.begin();
        todo.erase(todo.begin());
        if (d != best[p]) continue;
        for (const auto& [n, h] : neighbours(ws, p)) {
            auto it = best.find(n);
            if (it == best.end() || d + h < it->second) {
                best[n] = d + h;
                todo.insert({d + h, n});
            }
        }
    }
    return best;
}

std::set<std::string> story_shielded(const WorldState& ws) {  // sim._story_shielded
    std::set<std::string> out;
    for (const auto& [pid, pl] : ws.places)
        if (ws.settings.story_active(pl.story_lock))
            for (const auto& [p, h] : distances(ws, pid))
                if (h <= STORY_SHIELD_HOURS) out.insert(p);
    return out;
}

bool hostile(const WorldState& ws, const std::string& a, const OptStr& b) {   // sim._hostile
    if (!b || a == *b) return false;
    const Counts& rel = must(ws.factions, a, "faction").relations;
    auto it = rel.find(*b);
    return (it == rel.end() ? 0 : it->second) < 0;
}

std::set<std::string> lost_places(const WorldState& ws, const std::string& fid) {   // sim._lost_places
    std::set<std::string> out;
    for (const Value& e : ws.events) {
        if (!is_holder_change(ev_str(e, "kind"))) continue;
        auto prev = e.o->find("previous");
        if (prev == e.o->end() || !prev->second.is_str() || prev->second.s != fid) continue;
        const std::string& place = ev_str(e, "place");
        const OptStr& holder = must(ws.places, place, "place").holder;
        if (!holder || *holder != fid) out.insert(place);
    }
    return out;
}

// --- settlements --------------------------------------------------------------------------------------------------
std::optional<Int> farm_slots(const Settlement& s) {
    if (FARM_SLOTS_PER_BEDS <= 0) return std::nullopt;
    return floordiv(s.beds, FARM_SLOTS_PER_BEDS);
}

bool wants_farmer(const Settlement& s) {
    auto slots = farm_slots(s);
    Int farmers = at(s.roles, "farmer");
    return 3 * farmers < s.population + 2 && (!slots || farmers < *slots);
}

void add_settler(Settlement& s) {
    s.population += 1;
    if (wants_farmer(s)) { at(s.roles, "farmer") += 1; return; }
    const char* order[] = {"crafter", "doctor", "guard", "scavenger", "trader"};   // sorted, ties go to the first
    const char* pick = nullptr;
    for (const char* r : order)
        if (!pick || at(s.roles, r) < at(s.roles, pick)) pick = r;
    at(s.roles, pick) += 1;
}

void remove_settler(Settlement& s) {
    s.population -= 1;
    const std::string* biggest = nullptr;                    // max(sorted(roles), key=count): the first of the largest
    for (const auto& kv : s.roles)
        if (!biggest || kv.second > s.roles.at(*biggest)) biggest = &kv.first;
    if (biggest && s.roles.at(*biggest)) s.roles[*biggest] -= 1;
}

std::map<std::string, Int> reroles_to_farming(Settlement& s, Int n) {
    std::map<std::string, Int> moved;
    for (Int k = 0; k < std::max<Int>(0, n); ++k) {
        if (!wants_farmer(s)) break;
        const std::string* role = nullptr;
        for (const auto& kv : s.roles)
            if (kv.first != "farmer" && kv.second > 0 && (!role || kv.second > s.roles.at(*role))) role = &kv.first;
        if (!role) break;
        std::string r = *role;
        s.roles[r] -= 1;
        s.roles["farmer"] += 1;
        moved[r] += 1;
    }
    return moved;
}

bool arrival_due(const WorldState& ws, const Settlement& s) {
    if (ARRIVAL_SLOWDOWN_POP <= 0) return true;
    return floordiv(ws.hour, 24) % (1 + floordiv(s.population, ARRIVAL_SLOWDOWN_POP)) == 0;
}

bool resettle_safe(const WorldState& ws, const std::string& sid) {
    for (const auto& [id, q] : ws.squads)
        if (q.kind == "attack" && q.goal && *q.goal == sid) return false;
    Int since = ws.hour - RESETTLE_SAFE_HOURS;
    for (auto it = ws.events.rbegin(); it != ws.events.rend(); ++it) {
        if (it->o->at("hour").i < since) break;
        if (ev_str(*it, "place") == sid && is_attack_event(ev_str(*it, "kind"))) return false;
    }
    return true;
}

void settlement_tick(WorldState& ws) {
    for (auto& [sid, s] : ws.settlements) {
        Counts& r = s.roles;
        auto slots = farm_slots(s);
        Int farming = slots ? std::min(at(r, "farmer"), *slots) : at(r, "farmer");
        at(s.stock, "food") += 3 * farming;
        at(s.stock, "water") += 3 * farming;
        at(s.stock, "scrap") += 2 * at(r, "scavenger");
        Int made = std::min(at(r, "crafter"), floordiv(at(s.stock, "scrap"), 2));
        at(s.stock, "scrap") -= 2 * made;
        at(s.stock, "ammo") += 3 * made;
        at(s.stock, "medicine") += at(r, "doctor");
        if (s.priority) {
            Int workers = *s.priority == "ammo" ? made : at(r, priority_role(*s.priority));
            at(s.stock, *s.priority) += PRIORITY_BONUS_PER_WORKER * workers;
        }
        Int need = s.population, short_ = 0;
        for (const char* g : {"food", "water"}) {
            Int& have = at(s.stock, g);
            if (have >= need) have -= need;
            else { short_ += need - have; have = 0; }
        }
        if (short_) {
            s.morale = std::max<Int>(0, s.morale - 5);
            for (const auto& [role, n] : reroles_to_farming(s, REROLE_ON_SHORTAGE))
                event(ws, "roles_changed", sid, {{"from_role", Value::string(role)}, {"to_role", Value::string("farmer")},
                                                 {"n", Value::integer(n)}});
        } else if (at(s.stock, "food") > 2 * need && at(s.stock, "water") > 2 * need) {
            s.morale = std::min<Int>(100, s.morale + 2);
        } else {
            s.morale = std::min<Int>(100, s.morale + MORALE_DRIFT);
        }
        const OptStr& holder = ws.places.at(sid).holder;
        if (s.morale <= 10 && s.population > 0 && (short_ || !LEAVE_ONLY_WHEN_SHORT)) {
            remove_settler(s);
            event(ws, "settler_left", sid);
            if (s.population == 0) event(ws, "settlement_emptied", sid, {{"holder", str_or_null(holder)}});
        } else if (s.population > 0 && s.morale >= 70 && ws.hour % 24 == 0 && !short_ && s.population < s.beds &&
                   arrival_due(ws, s)) {
            add_settler(s);
            event(ws, "settler_arrived", sid);
        } else if (s.population == 0 && s.beds > 0 && ws.hour % 24 == 0 && holder && resettle_safe(ws, sid)) {
            add_settler(s);
            at(s.stock, "food") += RESETTLE_KIT;
            at(s.stock, "water") += RESETTLE_KIT;
            s.morale = std::max(s.morale, RESETTLE_MORALE);
            event(ws, "settlement_resettled", sid, {{"faction", str_or_null(holder)}});
        }
        Int stage = -1;
        for (Int i = 0; i < 5; ++i)
            if (s.population >= STAGE_POP[i]) stage = i;
        if (stage < 0) throw std::runtime_error("settlement " + sid + " has a negative population");
        if (stage != s.stage) {
            event(ws, "stage_changed", sid, {{"old", Value::integer(s.stage)}, {"new", Value::integer(stage)}});
            s.stage = stage;
        }
    }
}

// --- caravans -------------------------------------------------------------------------------------------------------
void dispatch_caravans(WorldState& ws) {
    for (auto& [sid, s] : ws.settlements) {
        const OptStr holder = ws.places.at(sid).holder;
        if (!at(s.roles, "trader") || !holder) continue;
        bool busy = false;
        for (const auto& [id, q] : ws.squads)
            if (q.kind == "caravan" && q.at == sid) { busy = true; break; }
        if (busy) continue;
        const std::pair<std::string, Int>* target = nullptr;     // min(friends, key=(food, id)): the first smallest
        auto nbrs = neighbours(ws, sid);
        for (const auto& nh : nbrs) {
            auto st = ws.settlements.find(nh.first);
            if (st == ws.settlements.end() || ws.places.at(nh.first).holder != holder) continue;
            if (!target) { target = &nh; continue; }
            Int a = at(st->second.stock, "food"), b = at(ws.settlements.at(target->first).stock, "food");
            if (a < b || (a == b && nh.first < target->first)) target = &nh;
        }
        if (!target) continue;
        Int surplus = at(s.stock, "food") - 3 * s.population;
        if (surplus < 6) continue;
        Int food = floordiv(surplus, 2);
        at(s.stock, "food") -= food;
        Squad q;
        q.id = new_id(ws, "c");
        q.faction = *holder;
        q.size = 2;
        q.at = sid;
        q.goal = target->first;
        q.kind = "caravan";
        q.cargo = {{"food", food}};
        q.eta = ws.hour + target->second;
        ws.squads[q.id] = q;
    }
}

OptStr raider(WorldState& ws, const Squad& q, PyRandom& rng) {   // sim._raider
    std::set<std::string> ends{q.at, *q.goal}, near;
    for (const std::string& end : ends)
        for (const auto& nh : neighbours(ws, end)) near.insert(nh.first);
    for (const std::string& end : ends) near.erase(end);
    for (const auto& [fid, f] : ws.factions) {
        if (!hostile(ws, fid, q.faction)) continue;
        bool holds = false;
        for (const std::string& n : near)
            if (ws.places.at(n).holder == fid) { holds = true; break; }
        if (!holds) continue;
        double x = static_cast<double>(f.strength) * RAID_CHANCE_PER_STRENGTH;
        x = x * ws.settings.raid_multiplier();
        double chance = x < RAID_CHANCE_CAP ? x : RAID_CHANCE_CAP;
        if (rng.random() < chance) return fid;
    }
    return std::nullopt;
}

// --- factions -------------------------------------------------------------------------------------------------------
void faction_tick(WorldState& ws, PyRandom& rng) {
    double pressure = ws.settings.raid_multiplier();
    std::set<std::string> shielded = story_shielded(ws);
    for (auto& [fid, f] : ws.factions) {
        std::vector<std::string> held;
        for (const auto& [p, pl] : ws.places)
            if (pl.holder && *pl.holder == fid) held.push_back(p);
        if (ws.hour % 24 == 0) {                                     // sim._daily_strength
            Int n = static_cast<Int>(held.size());
            f.strength = std::min(STRENGTH_CAP, f.strength + STRENGTH_INCOME_PER_PLACE * n);
            f.strength = std::max<Int>(0, f.strength - UPKEEP_PER_PLACE * n);
        }
        if (f.strength < 6) continue;                                // no draw then (Python's `or` stops here)
        double roll = rng.random() * 100;
        double bar = static_cast<double>(f.aggression) * ATTACK_CHANCE_PER_AGGRESSION;
        bar = bar * pressure;
        if (roll > bar) continue;
        std::set<std::string> lost = lost_places(ws, fid);
        std::vector<std::tuple<std::string, Int, std::string>> targets;
        for (const std::string& p : held) {
            for (const auto& [n, hours] : neighbours(ws, p)) {
                const Place& pl = ws.places.at(n);
                if ((pl.story_lock && !pl.story_lock->empty()) || shielded.count(n)) continue;
                bool home = false;
                for (const auto& kv : ws.factions)
                    if (kv.second.home == n) { home = true; break; }
                if (home) continue;
                if (!pl.holder || hostile(ws, fid, pl.holder)) {
                    Int weight = (lost.count(n) ? RETAKE_WEIGHT : 1) *
                                 (ws.settlements.count(n) ? SETTLEMENT_TARGET_WEIGHT : 1);
                    for (Int k = 0; k < weight; ++k) targets.emplace_back(n, hours, p);
                }
            }
        }
        if (targets.empty()) continue;
        std::sort(targets.begin(), targets.end());
        const auto& [target, hours, origin] = targets[rng.randbelow(targets.size())];
        Int size = floordiv(f.strength, 3);
        f.strength -= size;
        Squad q;
        q.id = new_id(ws, "s");
        q.faction = fid;
        q.size = size;
        q.at = origin;
        q.goal = target;
        q.kind = "attack";
        q.eta = ws.hour + hours;
        ws.squads[q.id] = q;
        event(ws, "attack_launched", origin, {{"faction", Value::string(fid)}, {"target", Value::string(target)},
                                              {"size", Value::integer(size)},
                                              {"retake", Value::boolean(lost.count(target) > 0)}});
    }
}

std::vector<std::string> garrisons(const WorldState& ws, const std::string& place) {
    std::vector<std::string> out;
    for (const auto& [id, q] : ws.squads)
        if (q.kind == "garrison" && q.at == place) out.push_back(id);
    return out;
}

Int defence(const WorldState& ws, const std::string& place) {
    const Place& pl = ws.places.at(place);
    Int d = pl.defence;
    if (pl.holder) d += floordiv(std::min<Int>(must(ws.factions, *pl.holder, "faction").strength, 10), 2);
    auto st = ws.settlements.find(place);
    if (st != ws.settlements.end()) d += 2 * at(st->second.roles, "guard") + floordiv(at(st->second.stock, "ammo"), 10);
    for (const std::string& g : garrisons(ws, place)) d += ws.squads.at(g).size;
    return d;
}

void resolve_arrivals(WorldState& ws, PyRandom& rng) {
    std::set<std::string> shielded = story_shielded(ws);
    std::vector<std::string> order;                          // garrisons last, then by id
    for (const auto& kv : ws.squads) if (kv.second.kind != "garrison") order.push_back(kv.first);
    for (const auto& kv : ws.squads) if (kv.second.kind == "garrison") order.push_back(kv.first);
    for (const std::string& qid : order) {
        auto it = ws.squads.find(qid);
        if (it == ws.squads.end() || it->second.eta > ws.hour) continue;   // gone: a garrison an attack spent
        Squad q = it->second;
        ws.squads.erase(it);
        if (q.kind == "garrison") continue;
        if (!q.goal) throw std::runtime_error("squad " + qid + " arrived with no goal");   // Python: KeyError
        Place& pl = must(ws.places, *q.goal, "place");
        if (q.kind == "caravan") {
            OptStr r = raider(ws, q, rng);
            auto dest = ws.settlements.find(*q.goal);
            if (r) {
                Faction& rf = ws.factions.at(*r);
                rf.strength = std::min(STRENGTH_CAP, rf.strength + RAID_STRENGTH_GAIN);
                event(ws, "caravan_raided", *q.goal, {{"faction", Value::string(q.faction)}, {"raider", Value::string(*r)},
                                                      {"origin", Value::string(q.at)}, {"cargo", counts_value(q.cargo)}});
            } else if (dest != ws.settlements.end() && pl.holder == q.faction) {
                for (const auto& [g, n] : q.cargo) at(dest->second.stock, g) += n;
                event(ws, "caravan_arrived", *q.goal, {{"faction", Value::string(q.faction)}, {"cargo", counts_value(q.cargo)}});
            } else {
                event(ws, "caravan_lost", *q.goal, {{"faction", Value::string(q.faction)}});
            }
            continue;
        }
        Faction& f = must(ws.factions, q.faction, "faction");
        if (pl.holder == q.faction) {
            f.strength = std::min(STRENGTH_CAP, f.strength + q.size);
            continue;
        }
        bool locked = pl.story_lock && !pl.story_lock->empty();
        if ((shielded.count(*q.goal) && !locked) || (pl.holder && !hostile(ws, q.faction, pl.holder))) {
            f.strength = std::min(STRENGTH_CAP, f.strength + q.size);
            event(ws, "attack_called_off", *q.goal, {{"faction", Value::string(q.faction)}, {"defender", str_or_null(pl.holder)}});
            continue;
        }
        Int d = defence(ws, *q.goal);
        for (const std::string& g : garrisons(ws, *q.goal)) ws.squads.erase(g);
        if (locked || rng.random() * static_cast<double>(q.size + d) >= static_cast<double>(q.size)) {
            event(ws, "attack_failed", *q.goal, {{"faction", Value::string(q.faction)}, {"defender", str_or_null(pl.holder)}});
            continue;
        }
        OptStr old = pl.holder;
        bool retaken = lost_places(ws, q.faction).count(*q.goal) > 0;
        pl.holder = q.faction;
        auto st = ws.settlements.find(*q.goal);
        if (st != ws.settlements.end() && st->second.population) {
            Settlement& s = st->second;
            for (Int k = 0, n = floordiv(s.population + 1, 2); k < n; ++k) remove_settler(s);
            s.morale = std::min<Int>(s.morale, 30);
            if (s.population == 0) event(ws, "settlement_emptied", *q.goal, {{"holder", Value::string(q.faction)}});
        }
        f.strength = std::min(STRENGTH_CAP, f.strength + floordiv(q.size, 2));
        event(ws, "place_taken", *q.goal, {{"faction", Value::string(q.faction)}, {"previous", str_or_null(old)},
                                           {"retaken", Value::boolean(retaken)}});
    }
}

// --- reputation (reputation.add, helped, tier_for) ------------------------------------------------------------------
void rep_add(WorldState& ws, const std::string& faction, Int fame, Int infamy) {
    std::vector<Reputation*> targets{&must(ws.reputation, faction, "reputation row")};
    for (auto& [region, layer] : ws.regional_reputation) {
        auto it = layer.find(faction);
        if (it != layer.end()) targets.push_back(&it->second);
    }
    for (Reputation* r : targets) {
        r->fame = std::max<Int>(0, r->fame + fame);
        r->infamy = std::max<Int>(0, r->infamy + infamy);
    }
}

Int tier_for(Int amount, Int unit) {
    Int k = floordiv(std::max<Int>(0, amount), std::max<Int>(1, unit));
    return GAIN_TIERS[std::min<Int>(4, k)];
}

// --- loading (model.WorldState._from_dict, _check_state; modes.Settings.from_dict) ---------------------------------
[[noreturn]] void bad(const std::string& why) { throw std::runtime_error("world state is malformed: " + why); }

const Object& obj(const Value& v, const std::string& what) {
    if (!v.is_obj()) bad(what + " must be an object");
    return *v.o;
}

void only(const Object& o, std::initializer_list<const char*> keys, const std::string& what) {
    for (const auto& kv : o) {
        bool ok = false;
        for (const char* k : keys) ok = ok || kv.first == k;
        if (!ok) bad(what + " has an unknown field " + kv.first);
    }
}

Int get_int(const Object& o, const char* k, const std::string& what, std::optional<Int> dflt = std::nullopt) {
    auto it = o.find(k);
    if (it == o.end()) { if (dflt) return *dflt; bad(what + "." + k + " is missing"); }
    if (!it->second.is_int()) bad(what + "." + k + " must be an integer");
    return it->second.i;
}

std::string get_str(const Object& o, const char* k, const std::string& what) {
    auto it = o.find(k);
    if (it == o.end()) bad(what + "." + k + " is missing");
    if (!it->second.is_str()) bad(what + "." + k + " must be a string");
    return it->second.s;
}

OptStr get_opt(const Object& o, const char* k, const std::string& what) {
    auto it = o.find(k);
    if (it == o.end() || it->second.is_null()) return std::nullopt;
    if (!it->second.is_str()) bad(what + "." + k + " must be a string or null");
    return it->second.s;
}

Counts get_counts(const Object& o, const char* k, const std::string& what, const Counts& dflt) {
    auto it = o.find(k);
    if (it == o.end()) return dflt;
    Counts out;
    for (const auto& kv : obj(it->second, what + "." + k)) {
        if (!kv.second.is_int()) bad(what + "." + k + " values must be integers");
        out[kv.first] = kv.second.i;
    }
    return out;
}

bool ascii(const std::string& s) {
    for (unsigned char c : s) if (c > 0x7F) return false;
    return true;
}

Reputation get_rep(const Value& v, const std::string& what) {
    const Object& o = obj(v, what);
    only(o, {"fame", "infamy"}, what);
    return {get_int(o, "fame", what, 0), get_int(o, "infamy", what, 0)};
}

}  // namespace

double Settings::raid_multiplier() const {                    // modes.RAID_PRESSURE_MULTIPLIER
    if (raid_pressure == "low") return 0.5;
    if (raid_pressure == "high") return 2.0;
    return 1.0;
}

bool Settings::story_active(const OptStr& story) const {
    return story_mode && story && std::binary_search(active_stories.begin(), active_stories.end(), *story);
}

WorldState WorldState::from_json(const std::string& text) {
    Value root = parse(text);
    const Object& d = obj(root, "the world state");
    Int schema = get_int(d, "schema", "world state", -1);
    if (schema != 1 && schema != 2) bad("unknown schema");
    WorldState ws;
    ws.seed = get_int(d, "seed", "world state");
    ws.hour = get_int(d, "hour", "world state");
    ws.next_id = get_int(d, "next_id", "world state");
    // sim.rng_seed: seed * 1000003 + hour must fit in 64 unsigned bits
    if (!rng_seed_ok(ws.seed, ws.hour)) bad("seed and hour are outside the RNG's range");
    Counts no_roles, no_stock;
    for (const char* r : ROLES) no_roles[r] = 0;
    for (const char* g : GOODS) no_stock[g] = 0;
    for (const auto& [k, v] : obj(d.at("places"), "places")) {
        const Object& o = obj(v, "places[" + k + "]");
        only(o, {"id", "region", "kind", "holder", "story_lock", "defence"}, "places[" + k + "]");
        Place p{get_str(o, "id", k), get_str(o, "region", k), get_str(o, "kind", k), get_opt(o, "holder", k),
                get_opt(o, "story_lock", k), get_int(o, "defence", k, 0)};
        ws.places[k] = p;
    }
    for (const auto& [k, v] : obj(d.at("settlements"), "settlements")) {
        const Object& o = obj(v, "settlements[" + k + "]");
        only(o, {"place", "population", "roles", "stock", "morale", "stage", "beds", "priority"}, "settlements[" + k + "]");
        Settlement s;
        s.place = get_str(o, "place", k);
        s.population = get_int(o, "population", k, 0);
        s.roles = get_counts(o, "roles", k, no_roles);
        s.stock = get_counts(o, "stock", k, no_stock);
        s.morale = get_int(o, "morale", k, 50);
        s.stage = get_int(o, "stage", k, 0);
        s.beds = get_int(o, "beds", k, 20);
        s.priority = get_opt(o, "priority", k);
        ws.settlements[k] = s;
    }
    for (const auto& [k, v] : obj(d.at("factions"), "factions")) {
        const Object& o = obj(v, "factions[" + k + "]");
        only(o, {"id", "strength", "home", "aggression", "relations"}, "factions[" + k + "]");
        Faction f;
        f.id = get_str(o, "id", k);
        f.strength = get_int(o, "strength", k);
        f.home = get_str(o, "home", k);
        f.aggression = get_int(o, "aggression", k, 50);
        f.relations = get_counts(o, "relations", k, {});
        ws.factions[k] = f;
    }
    for (const auto& [k, v] : obj(d.at("squads"), "squads")) {
        const Object& o = obj(v, "squads[" + k + "]");
        only(o, {"id", "faction", "size", "at", "goal", "kind", "cargo", "eta"}, "squads[" + k + "]");
        Squad q;
        q.id = get_str(o, "id", k);
        q.faction = get_str(o, "faction", k);
        q.size = get_int(o, "size", k);
        q.at = get_str(o, "at", k);
        q.goal = get_opt(o, "goal", k);
        auto kind = o.find("kind");
        if (kind != o.end()) { if (!kind->second.is_str()) bad(k + ".kind must be a string"); q.kind = kind->second.s; }
        q.cargo = get_counts(o, "cargo", k, {});
        q.eta = get_int(o, "eta", k, 0);
        ws.squads[k] = q;
    }
    const Value& routes = d.at("routes");
    if (!routes.is_arr()) bad("routes must be a list");
    for (const Value& v : *routes.a) {
        const Object& o = obj(v, "a route");
        only(o, {"a", "b", "hours"}, "a route");
        ws.routes.push_back({get_str(o, "a", "route"), get_str(o, "b", "route"), get_int(o, "hours", "route")});
    }
    for (const auto& [k, v] : obj(d.at("reputation"), "reputation")) ws.reputation[k] = get_rep(v, "reputation[" + k + "]");
    const Value& events = d.at("events");
    if (!events.is_arr()) bad("events must be a list");
    for (const Value& e : *events.a) {
        if (!e.is_obj()) bad("an event must be an object");
        auto h = e.o->find("hour"), kd = e.o->find("kind"), pl = e.o->find("place");
        if (h == e.o->end() || !h->second.is_int() || kd == e.o->end() || !kd->second.is_str() || pl == e.o->end() ||
            !pl->second.is_str())
            bad("events must be objects with an integer hour and string kind and place");
        ws.events.push_back(e);
    }
    auto rr = d.find("regional_reputation");
    if (rr != d.end())
        for (const auto& [region, layer] : obj(rr->second, "regional_reputation"))
            for (const auto& [k, v] : obj(layer, "regional_reputation[" + region + "]"))
                ws.regional_reputation[region][k] = get_rep(v, region + "/" + k);
    auto st = d.find("settings");
    if (st != d.end() && !st->second.is_null()) {
        const Object& o = obj(st->second, "settings");
        auto sv = o.find("survival"), rp = o.find("raid_pressure"), sm = o.find("story_mode"), as = o.find("active_stories");
        if (sv != o.end()) { if (!sv->second.is_str()) bad("settings.survival"); ws.settings.survival = sv->second.s; }
        if (rp != o.end()) { if (!rp->second.is_str()) bad("settings.raid_pressure"); ws.settings.raid_pressure = rp->second.s; }
        if (sm != o.end()) {
            if (sm->second.kind != Value::Kind::Bool) bad("settings.story_mode must be a bool");
            ws.settings.story_mode = sm->second.b;
        }
        if (as != o.end()) {
            if (!as->second.is_arr()) bad("settings.active_stories must be a list");
            std::set<std::string> u;
            for (const Value& x : *as->second.a) { if (!x.is_str()) bad("active_stories"); u.insert(x.s); }
            ws.settings.active_stories.assign(u.begin(), u.end());
        }
    }
    const auto& sv = ws.settings.survival;
    const auto& rp = ws.settings.raid_pressure;
    if (sv != "off" && sv != "light" && sv != "full") bad("unknown survival preset " + sv);
    if (rp != "low" && rp != "normal" && rp != "high") bad("unknown raid pressure " + rp);
    // _check_state: ids, references, routes
    auto ids_ascii = [](const auto& m, const char* table) {
        for (const auto& kv : m) if (!ascii(kv.first)) bad(std::string(table) + " id " + kv.first + " must be ASCII");
    };
    ids_ascii(ws.places, "places");
    ids_ascii(ws.settlements, "settlements");
    ids_ascii(ws.factions, "factions");
    ids_ascii(ws.squads, "squads");
    ids_ascii(ws.reputation, "reputation");
    for (const auto& [k, p] : ws.places)
        if (p.id != k || (p.holder && !ws.factions.count(*p.holder))) bad("places[" + k + "] id or holder");
    for (const auto& [k, s] : ws.settlements)
        if (s.place != k || !ws.places.count(k)) bad("settlements[" + k + "] place");
    for (const auto& [k, f] : ws.factions)
        if (f.id != k || !ws.places.count(f.home)) bad("factions[" + k + "] id or home");
    for (const auto& [k, q] : ws.squads)
        if (q.id != k || !(ws.factions.count(q.faction) || q.faction == "player") || !ws.places.count(q.at) ||
            (q.goal && !ws.places.count(*q.goal)))
            bad("squads[" + k + "] faction, place or goal");
    for (const auto& [k, r] : ws.reputation) if (!ws.factions.count(k)) bad("reputation names an unknown faction");
    for (const auto& [region, layer] : ws.regional_reputation)
        for (const auto& [k, r] : layer) if (!ws.factions.count(k)) bad("reputation names an unknown faction");
    for (const auto& [k, f] : ws.factions) if (!ws.reputation.count(k)) bad("reputation needs a row for every faction");
    for (const Route& r : ws.routes)
        if (!ws.places.count(r.a) || !ws.places.count(r.b) || r.hours <= 0) bad("a route must join two known places");
    return ws;
}

std::string WorldState::to_json() const {
    Object d;
    d["seed"] = Value::integer(seed);
    d["hour"] = Value::integer(hour);
    d["next_id"] = Value::integer(next_id);
    d["schema"] = Value::integer(2);
    Object ps;
    for (const auto& [k, p] : places)
        ps[k] = Value::object({{"id", Value::string(p.id)}, {"region", Value::string(p.region)}, {"kind", Value::string(p.kind)},
                               {"holder", str_or_null(p.holder)}, {"story_lock", str_or_null(p.story_lock)},
                               {"defence", Value::integer(p.defence)}});
    d["places"] = Value::object(std::move(ps));
    Object ss;
    for (const auto& [k, s] : settlements)
        ss[k] = Value::object({{"place", Value::string(s.place)}, {"population", Value::integer(s.population)},
                               {"roles", counts_value(s.roles)}, {"stock", counts_value(s.stock)},
                               {"morale", Value::integer(s.morale)}, {"stage", Value::integer(s.stage)},
                               {"beds", Value::integer(s.beds)}, {"priority", str_or_null(s.priority)}});
    d["settlements"] = Value::object(std::move(ss));
    Object fs;
    for (const auto& [k, f] : factions)
        fs[k] = Value::object({{"id", Value::string(f.id)}, {"strength", Value::integer(f.strength)},
                               {"home", Value::string(f.home)}, {"aggression", Value::integer(f.aggression)},
                               {"relations", counts_value(f.relations)}});
    d["factions"] = Value::object(std::move(fs));
    Object qs;
    for (const auto& [k, q] : squads)
        qs[k] = Value::object({{"id", Value::string(q.id)}, {"faction", Value::string(q.faction)},
                               {"size", Value::integer(q.size)}, {"at", Value::string(q.at)}, {"goal", str_or_null(q.goal)},
                               {"kind", Value::string(q.kind)}, {"cargo", counts_value(q.cargo)},
                               {"eta", Value::integer(q.eta)}});
    d["squads"] = Value::object(std::move(qs));
    Array rs;
    for (const Route& r : routes)
        rs.push_back(Value::object({{"a", Value::string(r.a)}, {"b", Value::string(r.b)}, {"hours", Value::integer(r.hours)}}));
    d["routes"] = Value::array(std::move(rs));
    auto rep_value = [](const Reputation& r) {
        return Value::object({{"fame", Value::integer(r.fame)}, {"infamy", Value::integer(r.infamy)}});
    };
    Object rep;
    for (const auto& [k, r] : reputation) rep[k] = rep_value(r);
    d["reputation"] = Value::object(std::move(rep));
    d["events"] = Value::array(events);
    Object rr;
    for (const auto& [region, layer] : regional_reputation) {
        Object l;
        for (const auto& [k, r] : layer) l[k] = rep_value(r);
        rr[region] = Value::object(std::move(l));
    }
    d["regional_reputation"] = Value::object(std::move(rr));
    Array stories;
    for (const std::string& s : settings.active_stories) stories.push_back(Value::string(s));
    d["settings"] = Value::object({{"survival", Value::string(settings.survival)},
                                   {"raid_pressure", Value::string(settings.raid_pressure)},
                                   {"story_mode", Value::boolean(settings.story_mode)},
                                   {"active_stories", Value::array(std::move(stories))}});
    return dumps(Value::object(std::move(d)));
}

void tick(WorldState& ws) {                                   // sim.tick
    ws.hour += TICK_HOURS;
    if (!rng_seed_ok(ws.seed, ws.hour)) throw std::runtime_error("seed and hour are outside the RNG's range");
    PyRandom rng(static_cast<std::uint64_t>(ws.seed) * 1000003u + static_cast<std::uint64_t>(ws.hour));
    resolve_arrivals(ws, rng);
    settlement_tick(ws);
    dispatch_caravans(ws);
    faction_tick(ws, rng);
}

void player_helped(WorldState& ws, const std::string& faction, Int amount) {   // reputation.helped
    rep_add(ws, faction, amount, 0);
    for (const auto& [other, rel] : must(ws.factions, faction, "faction").relations)
        if (rel < 0 && ws.reputation.count(other)) rep_add(ws, other, 0, floordiv(amount, ENEMY_INFAMY_DIVISOR));
}

std::string player_defended(WorldState& ws, const std::string& place, Int bonus, Int hours) {
    Squad q;
    q.id = new_id(ws, "g");
    q.faction = "player";
    q.size = bonus;
    q.at = place;
    q.goal = place;
    q.kind = "garrison";
    q.eta = ws.hour + hours;
    ws.squads[q.id] = q;
    OptStr holder = must(ws.places, place, "place").holder;
    if (holder && ws.reputation.count(*holder)) player_helped(ws, *holder, PLAYER_DEFENCE_FAME);
    event(ws, "player_defended", place, {{"holder", str_or_null(holder)}, {"bonus", Value::integer(bonus)}});
    return q.id;
}

Counts player_traded(WorldState& ws, const std::string& settlement, const Counts& goods) {
    Settlement& s = must(ws.settlements, settlement, "settlement");
    for (const auto& [g, n] : goods) {
        bool known = false;
        for (const char* x : GOODS) known = known || g == x;
        if (!known) throw std::runtime_error("unknown good " + g);
    }
    Counts moved;
    for (const auto& [g, want] : goods) {
        Int n = std::max(want, -at(s.stock, g));
        if (n) { at(s.stock, g) += n; moved[g] = n; }
    }
    Int given = 0;
    for (const auto& kv : moved) if (kv.second > 0) given += kv.second;
    const OptStr& holder = ws.places.at(settlement).holder;
    if (given && holder && ws.reputation.count(*holder)) rep_add(ws, *holder, tier_for(given, TRADE_GOODS_PER_TIER), 0);
    event(ws, "player_traded", settlement, {{"goods", counts_value(moved)}});
    return moved;
}

void apply_action(WorldState& ws, const Value& action) {
    const Object& a = obj(action, "an action");
    std::string what = get_str(a, "do", "action");
    if (what == "help") player_helped(ws, get_str(a, "faction", "action"), get_int(a, "amount", "action", 10));
    else if (what == "defend")
        player_defended(ws, get_str(a, "place", "action"), get_int(a, "bonus", "action", 10), get_int(a, "hours", "action", 72));
    else if (what == "trade") player_traded(ws, get_str(a, "settlement", "action"), get_counts(a, "goods", "action", {}));
    else throw std::runtime_error("unknown action " + what);
}

}  // namespace foccsim
