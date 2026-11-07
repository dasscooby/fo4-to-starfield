// foccsim: the parity harness's command line (tests/test_combined_cpp_parity.py).
//   foccsim <state.json> <ticks> [--actions <actions.json>] [--results <file>] [--dump-at <tick>] [--dump <file>]
//           [--out <file>] [--adapter <file>] [--prefix <editor id prefix>] [--walk <walk.json> --present <file>]
// Reads a world state Python wrote, runs <ticks> ticks, and prints one line per tick: "<tick> <hour> <sha256 of the
// canonical JSON>". Each scripted action whose hour is the state's hour runs before that tick, in file order, and
// --results gets one line per action: "[<hour>, <do>, {"ok": <result>}]", or {"error": <message>} where Python
// raises ValueError (see run_action). --dump-at writes that tick's JSON to --dump; --out writes the final JSON. --adapter writes the engine adapter's output as canonical
// JSON lines: first {"changes", "plan", "view"} for the start (the record plan made with --prefix, the game view, and
// the writes from nothing), then "[<tick>, <writes since the tick before>]" after each tick. --walk lists where the
// player stands ([{"tick", "place", "radius", "max_actors"}, ...]; tick 0 is the start, tick t is after tick t), and
// --present writes one line per entry, in order: "[<tick>, <present.plan>, <present.diff from the entry before>]".
// Exit 0, or 2 with the reason on stderr.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "../FOCCSidecar/sha256.h"
#include "adapter.h"
#include "foccsim.h"
#include "jobs.h"
#include "manage.h"
#include "news.h"
#include "present.h"

namespace fa = foccsim::adapter;

static std::string slurp(const std::string& path) {
    std::ifstream f(path, std::ios::binary);
    if (!f) throw std::runtime_error("cannot read " + path);
    std::ostringstream s;
    s << f.rdbuf();
    return s.str();
}

static void spit(const std::string& path, const std::string& text) {
    std::ofstream f(path, std::ios::binary);
    f << text;
    if (!f) throw std::runtime_error("cannot write " + path);
}

namespace {

using foccsim::Int;
using foccsim::Value;

const Value* field(const Value& a, const char* k) {
    auto it = a.o->find(k);
    return it == a.o->end() ? nullptr : &it->second;
}
std::string text(const Value& a, const char* k) {
    const Value* v = field(a, k);
    if (!v || !v->is_str()) throw std::runtime_error(std::string("action needs a string ") + k);
    return v->s;
}
Int number(const Value& a, const char* k, Int dflt) {
    const Value* v = field(a, k);
    return v ? v->i : dflt;
}
foccsim::Counts counts(const Value& a, const char* k) {
    foccsim::Counts out;
    const Value* v = field(a, k);
    if (v)
        for (const auto& kv : *v->o) out[kv.first] = kv.second.i;
    return out;
}
// One scripted action, as the test's run() does it in Python: the player hooks (help, defend, trade), the settlement
// actions of manage (assign, beds, priority, send, status, threats), the radiant jobs (offers, then complete or fail
// one of the last offers by its position, where a position past the end does nothing, or an offer given in full), the
// news at a place (its items and terminal page), and textwrap and the capital letter on their own (wrap, shorten,
// upper) for the fuzz test.
Value run_action(foccsim::WorldState& ws, const Value& a, std::vector<foccsim::jobs::Offer>& last) {
    namespace fm = foccsim::manage;
    namespace fj = foccsim::jobs;
    std::string what = text(a, "do");
    if (what == "help") { foccsim::player_helped(ws, text(a, "faction"), number(a, "amount", 10)); return Value(); }
    if (what == "defend")
        return Value::string(foccsim::player_defended(ws, text(a, "place"), number(a, "bonus", 10), number(a, "hours", 72)));
    if (what == "trade") return foccsim::counts_value(foccsim::player_traded(ws, text(a, "settlement"), counts(a, "goods")));
    if (what == "assign")
        return foccsim::counts_value(fm::assign_role(ws, text(a, "settlement"), text(a, "from"), text(a, "to"),
                                                     number(a, "n", 1)));
    if (what == "beds") return Value::integer(fm::add_beds(ws, text(a, "settlement"), number(a, "n", 1)));
    if (what == "priority") {
        const Value* g = field(a, "good");
        foccsim::OptStr good = g && g->is_str() ? foccsim::OptStr(g->s) : std::nullopt;
        foccsim::OptStr set = fm::set_priority(ws, text(a, "settlement"), good);
        return set ? Value::string(*set) : Value();
    }
    if (what == "send") return Value::string(fm::send_supplies(ws, text(a, "from"), text(a, "to"), counts(a, "goods")));
    if (what == "status") return fm::status(ws, text(a, "settlement"));
    if (what == "threats") return fm::threats(ws, text(a, "settlement"), number(a, "hours", fm::THREAT_HOURS));
    if (what == "offers") {
        foccsim::news::Names names;
        if (const Value* n = field(a, "names"))
            for (const auto& kv : *n->o) names[kv.first] = kv.second.s;
        last = fj::offers(ws, text(a, "place"), number(a, "limit", fj::OFFER_LIMIT), field(a, "names") ? &names : nullptr);
        foccsim::Array out;
        for (const fj::Offer& o : last) out.push_back(o.to_value());
        return Value::array(std::move(out));
    }
    if (what == "complete" || what == "fail") {
        fj::Offer given;
        const fj::Offer* o = nullptr;
        if (const Value* v = field(a, "offer")) {                      // an offer written out earlier, e.g. a stale one
            given = fj::Offer{text(*v, "id"), text(*v, "kind"), text(*v, "giver"), text(*v, "place"), text(*v, "target"),
                              number(*v, "reward_tier", 1), number(*v, "offered_hour", 0), number(*v, "expires_hour", 0),
                              text(*v, "text"), *field(*v, "detail")->o, number(*v, "read_at", 0)};
            o = &given;
        } else {
            Int pick = number(a, "pick", 0);
            if (pick < 0 || pick >= static_cast<Int>(last.size())) return Value();
            o = &last[static_cast<std::size_t>(pick)];
        }
        return what == "complete" ? fj::complete(ws, *o) : Value::integer(fj::fail(ws, *o));
    }
    if (what == "news") {
        foccsim::news::Names names;
        if (const Value* n = field(a, "names"))
            for (const auto& kv : *n->o) names[kv.first] = kv.second.s;
        const foccsim::news::Names* np = field(a, "names") ? &names : nullptr;
        std::string place = text(a, "place");
        Int since = number(a, "since", 0), limit = number(a, "limit", foccsim::news::HEADLINE_LIMIT);
        return Value::object({{"items", foccsim::news::items(ws, place, since, limit, np)},
                              {"page", Value::string(foccsim::news::terminal_page(
                                           ws, place, since, limit, number(a, "width", foccsim::news::TERMINAL_WIDTH),
                                           np))}});
    }
    if (what == "wrap") {                                              // textwrap itself, for the fuzz test
        foccsim::Array lines;
        for (const std::string& l : foccsim::news::wrap(text(a, "text"), number(a, "width", 70), text(a, "indent")))
            lines.push_back(Value::string(l));
        return Value::array(std::move(lines));
    }
    if (what == "shorten")
        return Value::string(foccsim::news::shorten(text(a, "text"), number(a, "width", 70), text(a, "placeholder")));
    if (what == "upper") return Value::string(foccsim::news::upper_first(text(a, "text")));
    throw std::runtime_error("unknown action " + what);
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc < 3)
            throw std::runtime_error("usage: foccsim <state.json> <ticks> [--actions f] [--dump-at n --dump f] [--out f] "
                                     "[--adapter f] [--prefix p] [--walk f --present f] [--results f]");
        std::string actions_p, dump_p, out_p, adapter_p, walk_p, present_p, results_p;
        std::string prefix = fa::PREFIX;
        long dump_at = -1;
        for (int k = 3; k + 1 < argc; k += 2) {
            std::string o = argv[k];
            if (o == "--actions") actions_p = argv[k + 1];
            else if (o == "--dump-at") dump_at = std::strtol(argv[k + 1], nullptr, 10);
            else if (o == "--dump") dump_p = argv[k + 1];
            else if (o == "--out") out_p = argv[k + 1];
            else if (o == "--adapter") adapter_p = argv[k + 1];
            else if (o == "--prefix") prefix = argv[k + 1];
            else if (o == "--walk") walk_p = argv[k + 1];
            else if (o == "--present") present_p = argv[k + 1];
            else if (o == "--results") results_p = argv[k + 1];
            else throw std::runtime_error("unknown option " + o);
        }
        foccsim::WorldState ws = foccsim::WorldState::from_json(slurp(argv[1]));
        foccsim::Value actions = actions_p.empty() ? foccsim::Value::array() : foccsim::parse(slurp(actions_p));
        long ticks = std::strtol(argv[2], nullptr, 10);
        std::string adapter_out;
        fa::Plan plan;
        fa::View view;
        if (!adapter_p.empty()) {
            plan = fa::record_plan(ws, prefix);
            view = fa::game_view(ws, plan);
            adapter_out = foccsim::dumps(foccsim::Value::object({
                {"changes", fa::writes_value(fa::changes(nullptr, view))},
                {"plan", plan.to_value()},
                {"view", fa::view_value(view)}})) + "\n";
        }
        foccsim::Value walk = walk_p.empty() ? foccsim::Value::array() : foccsim::parse(slurp(walk_p));
        std::string present_out;
        std::optional<foccsim::present::Plan> shown;
        auto present_at = [&](long t) {                 // the walk's entries for tick t, in order
            for (const foccsim::Value& w : *walk.a) {
                if (w.o->at("tick").i != t) continue;
                foccsim::present::Plan next = foccsim::present::plan(ws, w.o->at("place").s, w.o->at("radius").i,
                                                                     w.o->at("max_actors").i);
                foccsim::present::Diff d = foccsim::present::diff(shown ? &*shown : nullptr, next);
                present_out += foccsim::dumps(foccsim::Value::array({foccsim::Value::integer(t), next.to_value(),
                                                                     d.to_value()})) + "\n";
                shown = std::move(next);
            }
        };
        present_at(0);
        std::string results_out;
        std::vector<foccsim::jobs::Offer> last_offers;
        for (long t = 1; t <= ticks; ++t) {
            for (const foccsim::Value& a : *actions.a) {
                if (a.o->at("hour").i != ws.hour) continue;
                foccsim::Value result;
                try {
                    result = foccsim::Value::object({{"ok", run_action(ws, a, last_offers)}});
                } catch (const std::invalid_argument& e) {                // Python's ValueError
                    result = foccsim::Value::object({{"error", foccsim::Value::string(e.what())}});
                }
                results_out += foccsim::dumps(foccsim::Value::array({foccsim::Value::integer(ws.hour),
                                                                     a.o->at("do"), result})) + "\n";
            }
            foccsim::tick(ws);
            std::string text = ws.to_json();
            std::printf("%ld %lld %s\n", t, static_cast<long long>(ws.hour), focc::sha256_hex(text).c_str());
            if (t == dump_at && !dump_p.empty()) spit(dump_p, text);
            if (!adapter_p.empty()) {
                fa::View next = fa::game_view(ws, plan);
                adapter_out += foccsim::dumps(foccsim::Value::array({
                    foccsim::Value::integer(t), fa::writes_value(fa::changes(&view, next))})) + "\n";
                view = std::move(next);
            }
            present_at(t);
        }
        if (!present_p.empty()) spit(present_p, present_out);
        if (!results_p.empty()) spit(results_p, results_out);
        if (!adapter_p.empty()) spit(adapter_p, adapter_out);
        if (!out_p.empty()) spit(out_p, ws.to_json());
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "foccsim: %s\n", e.what());
        return 2;
    }
}
