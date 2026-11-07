// foccsim: the parity harness's command line (tests/test_combined_cpp_parity.py).
//   foccsim <state.json> <ticks> [--actions <actions.json>] [--dump-at <tick>] [--dump <file>] [--out <file>]
//           [--adapter <file>] [--prefix <editor id prefix>] [--walk <walk.json> --present <file>]
// Reads a world state Python wrote, runs <ticks> ticks (applying each scripted action whose hour is the state's hour,
// before that tick), and prints one line per tick: "<tick> <hour> <sha256 of the canonical JSON>". --dump-at writes
// that tick's JSON to --dump; --out writes the final JSON. --adapter writes the engine adapter's output as canonical
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
#include <string>

#include "../FOCCSidecar/sha256.h"
#include "adapter.h"
#include "foccsim.h"
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

int main(int argc, char** argv) {
    try {
        if (argc < 3)
            throw std::runtime_error("usage: foccsim <state.json> <ticks> [--actions f] [--dump-at n --dump f] [--out f] "
                                     "[--adapter f] [--prefix p] [--walk f --present f]");
        std::string actions_p, dump_p, out_p, adapter_p, walk_p, present_p;
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
        for (long t = 1; t <= ticks; ++t) {
            for (const foccsim::Value& a : *actions.a)
                if (a.o->at("hour").i == ws.hour) foccsim::apply_action(ws, a);
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
        if (!adapter_p.empty()) spit(adapter_p, adapter_out);
        if (!out_p.empty()) spit(out_p, ws.to_json());
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "foccsim: %s\n", e.what());
        return 2;
    }
}
