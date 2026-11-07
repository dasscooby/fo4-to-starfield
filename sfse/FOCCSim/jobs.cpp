// FOCCSim's radiant work (see jobs.h). Each function names the Python one it copies from
// src/fo4sf/combined/jobs.py.
#include "jobs.h"

#include <algorithm>
#include <map>
#include <set>
#include <stdexcept>
#include <tuple>
#include <utility>

#include "manage.h"

namespace foccsim::jobs {

namespace {

const char* const KINDS[] = {"defend", "escort", "retake", "resupply", "clear"};
constexpr Int RETAKE_OFFER_HOURS = 7 * 24;
constexpr Int RESUPPLY_OFFER_HOURS = 48;
constexpr Int CLEAR_OFFER_HOURS = 72;
constexpr Int RESUPPLY_SHORT_TICKS = 2;
constexpr Int RESUPPLY_FILL_TICKS = 4;
constexpr Int DEFEND_SIZE_PER_TIER = 3;
constexpr Int ESCORT_GOODS_PER_TIER = 10;       // sim.TRADE_GOODS_PER_TIER
constexpr Int RESUPPLY_GOODS_PER_TIER = 10;     // sim.TRADE_GOODS_PER_TIER
constexpr Int RETAKE_TIER = 4;
constexpr Int CLEAR_TIER = 3;
constexpr Int PLAYER_DEFENCE_BONUS = 10;        // sim.PLAYER_DEFENCE_BONUS
constexpr Int PLAYER_DEFENCE_HOURS = 72;        // sim.PLAYER_DEFENCE_HOURS
constexpr Int GAIN_TIERS[] = {1, 2, 4, 7, 12};  // reputation.GAIN_TIERS

Int fail_infamy(const std::string& kind) { return kind == "defend" || kind == "escort" ? 1 : 0; }   // FAIL_INFAMY
bool one_time(const std::string& kind) { return kind == "defend" || kind == "escort" || kind == "retake"; }

const std::map<std::string, std::string>& templates() {                      // jobs.TEMPLATES, our own wording
    static const std::map<std::string, std::string> t = {
        {"defend", "Hold {target} for {giver} against {attacker} fighters expected by {due}."},
        {"escort", "See a caravan safely from {place} to {target} for {giver}, carrying {cargo}."},
        {"retake", "Take {target} back from {holder} for {giver}."},
        {"resupply", "{target} is running out of {good}; bring {amount} more for {giver}."},
        {"clear", "Clear {holder} out of {target}, next door to {near}, for {giver}."},
    };
    return t;
}

Int tier_number(Int amount, Int unit) {                                       // reputation.tier_number
    return std::min<Int>(5, floordiv(std::max<Int>(0, amount), std::max<Int>(1, unit)) + 1);
}

Int tier_points(Int tier) { return GAIN_TIERS[std::min<Int>(5, std::max<Int>(1, tier)) - 1]; }   // reputation.tier_points

Value opt(const OptStr& s) { return s ? Value::string(*s) : Value::null(); }

// jobs._text: str.format of the kind's template, every str or None field through news.display_name first, then the
// first character upper-cased (news::upper_first).
std::string text(const std::string& kind, const news::Names* names,
                 const std::map<std::string, OptStr>& names_of, const std::map<std::string, Int>& numbers = {}) {
    const std::string& t = templates().at(kind);
    std::string out;
    for (std::size_t k = 0; k < t.size();) {
        if (t[k] != '{') { out.push_back(t[k++]); continue; }
        std::size_t end = t.find('}', k);
        std::string key = t.substr(k + 1, end - k - 1);
        auto n = names_of.find(key);
        out += n != names_of.end() ? news::display_name(n->second, names) : std::to_string(numbers.at(key));
        k = end + 1;
    }
    return news::upper_first(out);
}

std::vector<std::string> held(const WorldState& ws, const std::string& fid) {   // jobs._held, sorted
    std::vector<std::string> out;
    for (const auto& [pid, pl] : ws.places)
        if (pl.holder == fid) out.push_back(pid);
    return out;
}

std::set<std::string> homes(const WorldState& ws) {                          // jobs._homes
    std::set<std::string> out;
    for (const auto& kv : ws.factions) out.insert(kv.second.home);
    return out;
}

bool locked(const Place& pl) { return pl.story_lock && !pl.story_lock->empty(); }   // Python: truthy story_lock

const std::string* str_field(const Object& o, const char* key) {             // o.get(key) when it is a str
    auto it = o.find(key);
    return it != o.end() && it->second.is_str() ? &it->second.s : nullptr;
}

// jobs._last_loss: (hour, index in the log) of the latest holder change that took `target` from `giver`
std::optional<std::pair<Int, Int>> last_loss(const WorldState& ws, const std::string& giver, const std::string& target) {
    std::optional<std::pair<Int, Int>> found;
    for (std::size_t i = 0; i < ws.events.size(); ++i) {
        const Object& e = *ws.events[i].o;
        const std::string* prev = str_field(e, "previous");
        if (is_holder_change(e.at("kind").s) && e.at("place").s == target && prev && *prev == giver)
            found = std::make_pair(e.at("hour").i, static_cast<Int>(i));
    }
    return found;
}

Int occupation(const WorldState& ws, const std::string& target) {           // jobs._occupation
    Int found = -1;
    for (std::size_t i = 0; i < ws.events.size(); ++i) {
        const Object& e = *ws.events[i].o;
        if (is_holder_change(e.at("kind").s) && e.at("place").s == target) found = static_cast<Int>(i);
    }
    return found;
}

std::string clear_id(const WorldState& ws, const std::string& giver, const std::string& target) {
    return "clear:" + giver + ":" + target + ":" + std::to_string(occupation(ws, target));
}

Int shortfall(const WorldState& ws, const std::string& sid, const std::string& good) {   // jobs._shortfall
    const Settlement& s = ws.settlements.at(sid);
    if (!s.population || s.stock.at(good) >= s.population * RESUPPLY_SHORT_TICKS) return 0;
    return s.population * RESUPPLY_FILL_TICKS - s.stock.at(good);
}

// jobs._clear_targets: hostile-held places next to the giver's holdings -> the giver's place they were found from
std::map<std::string, std::string> clear_targets(const WorldState& ws, const std::string& giver) {
    std::set<std::string> h = homes(ws), lost = lost_places(ws, giver);
    std::map<std::string, std::string> out;
    for (const std::string& p : held(ws, giver)) {
        for (const auto& nh : neighbours(ws, p)) {
            const std::string& n = nh.first;
            const Place& pl = ws.places.at(n);
            if (out.count(n) || h.count(n) || lost.count(n) || locked(pl) || !hostile(ws, giver, pl.holder)) continue;
            out[n] = p;
        }
    }
    return out;
}

Int read_at(const WorldState& ws) { return static_cast<Int>(ws.events.size()); }   // jobs._read_at

Offer make(std::string id, const char* kind, const std::string& giver, const std::string& place, std::string target,
           Int tier, Int offered, Int expires, std::string words, Object detail, Int at) {
    return Offer{std::move(id), kind, giver, place, std::move(target), tier, offered, expires, std::move(words),
                 std::move(detail), at};
}

void defend(const WorldState& ws, const std::string& giver, const std::string& place, const news::Names* names,
            std::vector<Offer>& out) {
    std::vector<std::string> mine = held(ws, giver);
    std::set<std::string> h(mine.begin(), mine.end());
    for (const auto& [qid, q] : ws.squads) {
        if (q.kind != "attack" || !q.goal || !h.count(*q.goal) || q.eta <= ws.hour || !garrisons(ws, *q.goal).empty())
            continue;
        std::string words = text("defend", names, {{"giver", giver}, {"target", q.goal}, {"attacker", q.faction},
                                                   {"due", news::stamp(q.eta)}});
        out.push_back(make("defend:" + qid, "defend", giver, place, *q.goal, tier_number(q.size, DEFEND_SIZE_PER_TIER),
                           ws.hour, q.eta, words, {{"squad", Value::string(qid)},
                                                   {"attacker", Value::string(q.faction)}}, read_at(ws)));
    }
}

void escort(const WorldState& ws, const std::string& giver, const std::string& place, const news::Names* names,
            std::vector<Offer>& out) {
    for (const auto& [qid, q] : ws.squads) {
        if (q.kind != "caravan" || q.faction != giver || q.at != place || q.eta <= ws.hour) continue;
        Int total = 0;
        for (const auto& kv : q.cargo) total += kv.second;
        std::string words = text("escort", names, {{"giver", giver}, {"place", place}, {"target", q.goal},
                                                   {"cargo", news::cargo(q.cargo)}});
        out.push_back(make("escort:" + qid, "escort", giver, place, q.goal.value(),
                           tier_number(total, ESCORT_GOODS_PER_TIER), ws.hour, q.eta, words,
                           {{"squad", Value::string(qid)}, {"cargo", counts_value(q.cargo)}}, read_at(ws)));
    }
}

void retake(const WorldState& ws, const std::string& giver, const std::string& place, const news::Names* names,
            std::vector<Offer>& out) {
    std::set<std::string> h = homes(ws);
    for (const std::string& target : lost_places(ws, giver)) {                // sorted
        const Place& pl = ws.places.at(target);
        if (locked(pl) || h.count(target) || (pl.holder && !hostile(ws, giver, pl.holder))) continue;
        auto [taken, seq] = last_loss(ws, giver, target).value();
        Int expires = taken + RETAKE_OFFER_HOURS;
        if (expires <= ws.hour) continue;
        std::string words = text("retake", names, {{"giver", giver}, {"target", target}, {"holder", pl.holder}});
        out.push_back(make("retake:" + giver + ":" + target + ":" + std::to_string(taken) + ":" + std::to_string(seq),
                           "retake", giver, place, target, RETAKE_TIER, ws.hour, expires, words,
                           {{"holder", opt(pl.holder)}, {"taken_hour", Value::integer(taken)}}, read_at(ws)));
    }
}

void resupply(const WorldState& ws, const std::string& giver, const std::string& place, const news::Names* names,
              std::vector<Offer>& out) {
    for (const std::string& sid : held(ws, giver)) {
        if (!ws.settlements.count(sid)) continue;
        for (const char* good : {"food", "water"}) {
            Int amount = shortfall(ws, sid, good);
            if (!amount) continue;
            std::string words = text("resupply", names, {{"giver", giver}, {"target", sid}, {"good", std::string(good)}},
                                     {{"amount", amount}});
            out.push_back(make("resupply:" + giver + ":" + sid + ":" + good, "resupply", giver, place, sid,
                               tier_number(amount, RESUPPLY_GOODS_PER_TIER), ws.hour, ws.hour + RESUPPLY_OFFER_HOURS,
                               words, {{"good", Value::string(good)}, {"amount", Value::integer(amount)}},
                               read_at(ws)));
        }
    }
}

void clear(const WorldState& ws, const std::string& giver, const std::string& place, const news::Names* names,
           std::vector<Offer>& out) {
    for (const auto& [target, near] : clear_targets(ws, giver)) {             // sorted by target
        const OptStr& holder = ws.places.at(target).holder;
        std::string words = text("clear", names, {{"giver", giver}, {"target", target}, {"holder", holder},
                                                  {"near", near}});
        out.push_back(make(clear_id(ws, giver, target), "clear", giver, place, target, CLEAR_TIER, ws.hour,
                           ws.hour + CLEAR_OFFER_HOURS, words, {{"holder", opt(holder)}, {"near", Value::string(near)}},
                           read_at(ws)));
    }
}

// jobs._outcome: why this job's outcome is already decided, by log position: any job_done or job_failed event for a
// one-time id, or for a repeating id one carrying this instance's offered hour; another instance's outcome logged at
// or after read_at or carrying a later offered hour (superseded); or a give-up still inside its window
std::optional<std::string> outcome(const WorldState& ws, const Offer& offer) {
    for (std::size_t i = 0; i < ws.events.size(); ++i) {
        const Object& e = *ws.events[i].o;
        const std::string& kind = e.at("kind").s;
        const std::string* id = str_field(e, "offer");
        if ((kind != "job_done" && kind != "job_failed") || !id || *id != offer.id) continue;
        auto offered = e.find("offered");
        bool has_offered = offered != e.end() && offered->second.is_int();
        auto until = e.find("until");
        Int until_hour = until != e.end() && until->second.is_int() ? until->second.i : -1;
        if (one_time(offer.kind) || (has_offered && offered->second.i == offer.offered_hour))
            return "this offer was already handed in or given up";
        Int offered_hour = has_offered ? offered->second.i : -1;               // e.get("offered", -1)
        if (static_cast<Int>(i) >= offer.read_at || offered_hour > offer.offered_hour)
            return "this offer was superseded: an outcome for the job was logged after it was read";
        if (kind == "job_failed" && ws.hour < until_hour) return "this job was given up and its window has not ended";
    }
    return std::nullopt;
}

// jobs._from_later: an instance read at an hour this world has not reached (the game went back to an earlier save)
std::optional<std::string> from_later(const WorldState& ws, const Offer& offer) {
    if (offer.offered_hour > ws.hour)
        return "this offer was read at hour " + std::to_string(offer.offered_hour) + ", later than the world's hour " +
               std::to_string(ws.hour);
    return std::nullopt;
}

}  // namespace

Value Offer::to_value() const {
    return Value::object({{"detail", Value::object(detail)}, {"expires_hour", Value::integer(expires_hour)},
                          {"giver", Value::string(giver)}, {"id", Value::string(id)}, {"kind", Value::string(kind)},
                          {"offered_hour", Value::integer(offered_hour)}, {"place", Value::string(place)},
                          {"read_at", Value::integer(read_at)}, {"reward_tier", Value::integer(reward_tier)},
                          {"target", Value::string(target)}, {"text", Value::string(text)}});
}

std::vector<Offer> offers(const WorldState& ws, const std::string& place, Int limit, const news::Names* names) {
    auto at = ws.places.find(place);
    if (at == ws.places.end()) throw std::out_of_range("unknown place " + manage::py_repr(place));
    if (!at->second.holder) return {};
    const std::string& giver = *at->second.holder;
    std::vector<Offer> found;
    defend(ws, giver, place, names, found);                                   // in KINDS order
    escort(ws, giver, place, names, found);
    retake(ws, giver, place, names, found);
    resupply(ws, giver, place, names, found);
    clear(ws, giver, place, names, found);
    found.erase(std::remove_if(found.begin(), found.end(),
                               [&](const Offer& o) { return outcome(ws, o).has_value(); }),
                found.end());
    std::stable_sort(found.begin(), found.end(), [](const Offer& a, const Offer& b) {
        return std::tie(a.expires_hour, a.kind, a.id) < std::tie(b.expires_hour, b.kind, b.id);
    });
    Int n = static_cast<Int>(found.size());
    Int keep = limit >= 0 ? std::min(limit, n) : std::max<Int>(0, n + limit);    // found[:limit]
    found.resize(static_cast<std::size_t>(keep));
    return found;
}

std::optional<std::string> valid(const WorldState& ws, const Offer& offer) {
    if (std::find_if(std::begin(KINDS), std::end(KINDS), [&](const char* k) { return offer.kind == k; }) ==
        std::end(KINDS))
        return "unknown offer kind " + manage::py_repr(offer.kind);
    if (!ws.factions.count(offer.giver) || !ws.places.count(offer.target)) return "giver or target no longer exists";
    if (ws.hour >= offer.expires_hour) return "offer expired at hour " + std::to_string(offer.expires_hour);
    std::optional<std::string> why = outcome(ws, offer);                 // outcome(...) or from_later(...)
    if (!why) why = from_later(ws, offer);
    if (why) return why;
    const Place& pl = ws.places.at(offer.target);
    const Object& d = offer.detail;
    auto squad = [&]() -> const Squad* {
        const std::string* qid = str_field(d, "squad");
        if (!qid) return nullptr;
        auto it = ws.squads.find(*qid);
        return it == ws.squads.end() ? nullptr : &it->second;
    };
    if (offer.kind == "defend") {
        const Squad* q = squad();
        if (!q || q->kind != "attack" || q->goal != offer.target) return "the attack is over";
        if (pl.holder != offer.giver) return "the giver no longer holds the place";
        if (!garrisons(ws, offer.target).empty()) return "a garrison already stands there";
    } else if (offer.kind == "escort") {
        const Squad* q = squad();
        if (!q || q->kind != "caravan" || q->goal != offer.target) return "the caravan has already arrived or was lost";
        if (pl.holder != offer.giver) return "the destination is no longer held by the giver";
    } else if (offer.kind == "retake") {
        if (pl.holder == offer.giver) return "the giver holds the place again";
        auto loss = last_loss(ws, offer.giver, offer.target);
        if (!loss || "retake:" + offer.giver + ":" + offer.target + ":" + std::to_string(loss->first) + ":" +
                             std::to_string(loss->second) != offer.id)
            return "the place was lost again since: that is a new job";
        if (locked(pl) || homes(ws).count(offer.target)) return "the place cannot change hands";
        if (pl.holder && !hostile(ws, offer.giver, pl.holder)) return "the place is now held by a friend of the giver";
    } else if (offer.kind == "resupply") {
        if (!ws.settlements.count(offer.target) || pl.holder != offer.giver)
            return "the settlement is no longer the giver's";
        const std::string* good = str_field(d, "good");
        if (!shortfall(ws, offer.target, good ? *good : std::string())) return "the settlement is no longer short";
    } else if (offer.kind == "clear") {
        if (!clear_targets(ws, offer.giver).count(offer.target))
            return "the place is no longer a hostile neighbour of the giver";
        auto h = d.find("holder");
        OptStr was = h != d.end() && h->second.is_str() ? OptStr(h->second.s) : std::nullopt;
        if (pl.holder != was || offer.id != clear_id(ws, offer.giver, offer.target))
            return "someone else holds the place now: that is a new job";
    }
    return std::nullopt;
}

Value complete(WorldState& ws, const Offer& offer) {
    if (auto reason = valid(ws, offer)) throw std::invalid_argument("cannot complete " + offer.id + ": " + *reason);
    const Object& d = offer.detail;
    Object changed{{"kind", Value::string(offer.kind)}, {"target", Value::string(offer.target)}};
    if (offer.kind == "defend") {
        const Squad& q = ws.squads.at(d.at("squad").s);         // the garrison outlasts the attack it was asked to meet
        changed["garrison"] = Value::string(player_defended(ws, offer.target, PLAYER_DEFENCE_BONUS,
                                                            std::max(PLAYER_DEFENCE_HOURS, q.eta - ws.hour)));
    } else if (offer.kind == "escort") {
        auto it = ws.squads.find(d.at("squad").s);
        Squad q = it->second;
        ws.squads.erase(it);                                     // delivered now: nothing left to raid
        auto dest = ws.settlements.find(q.goal.value());
        if (dest != ws.settlements.end())
            for (const auto& [g, n] : q.cargo) dest->second.stock.at(g) += n;
        event(ws, "caravan_arrived", *q.goal, {{"faction", Value::string(q.faction)}, {"cargo", counts_value(q.cargo)},
                                               {"escorted", Value::boolean(true)}});
        changed["cargo"] = counts_value(q.cargo);
    } else if (offer.kind == "retake") {
        Place& pl = ws.places.at(offer.target);
        OptStr previous = pl.holder;
        pl.holder = offer.giver;
        changed["previous"] = opt(previous);
        event(ws, "place_taken", offer.target, {{"faction", Value::string(offer.giver)}, {"previous", opt(previous)},
                                                {"retaken", Value::boolean(true)}, {"player", Value::boolean(true)}});
    } else if (offer.kind == "resupply") {
        changed["moved"] = counts_value(player_traded(ws, offer.target, {{d.at("good").s, d.at("amount").i}}));
    } else if (offer.kind == "clear") {
        Place& pl = ws.places.at(offer.target);
        OptStr previous = pl.holder;
        pl.holder = std::nullopt;
        changed["previous"] = opt(previous);
        event(ws, "place_cleared", offer.target, {{"faction", Value::string(offer.giver)}, {"previous", opt(previous)},
                                                  {"player", Value::boolean(true)}});
    }
    Int fame = tier_points(offer.reward_tier);
    player_helped(ws, offer.giver, fame);
    event(ws, "job_done", offer.place, {{"faction", Value::string(offer.giver)}, {"job", Value::string(offer.kind)},
                                        {"target", Value::string(offer.target)}, {"fame", Value::integer(fame)},
                                        {"offer", Value::string(offer.id)}, {"offered", Value::integer(offer.offered_hour)},
                                        {"until", Value::integer(offer.expires_hour)}});
    changed["fame"] = Value::integer(fame);
    return Value::object(std::move(changed));
}

Int fail(WorldState& ws, const Offer& offer) {
    std::optional<std::string> why = outcome(ws, offer);                 // outcome(...) or from_later(...)
    if (!why) why = from_later(ws, offer);
    if (why) throw std::invalid_argument("cannot fail " + offer.id + ": " + *why);
    Int infamy = fail_infamy(offer.kind);
    if (ws.reputation.count(offer.giver) && infamy) rep_add(ws, offer.giver, 0, infamy);
    if (ws.places.count(offer.place))
        event(ws, "job_failed", offer.place, {{"faction", Value::string(offer.giver)}, {"job", Value::string(offer.kind)},
                                              {"target", Value::string(offer.target)}, {"infamy", Value::integer(infamy)},
                                              {"offer", Value::string(offer.id)},
                                              {"offered", Value::integer(offer.offered_hour)},
                                              {"until", Value::integer(offer.expires_hour)}});
    return infamy;
}

}  // namespace foccsim::jobs
