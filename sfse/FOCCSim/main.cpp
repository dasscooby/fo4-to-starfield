// foccsim: the parity harness's command line (tests/test_combined_cpp_parity.py).
//   foccsim <state.json> <ticks> [--actions <actions.json>] [--dump-at <tick>] [--dump <file>] [--out <file>]
// Reads a world state Python wrote, runs <ticks> ticks (applying each scripted action whose hour is the state's hour,
// before that tick), and prints one line per tick: "<tick> <hour> <sha256 of the canonical JSON>". --dump-at writes
// that tick's JSON to --dump; --out writes the final JSON. Exit 0, or 2 with the reason on stderr.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>

#include "../FOCCSidecar/sha256.h"
#include "foccsim.h"

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
        if (argc < 3) throw std::runtime_error("usage: foccsim <state.json> <ticks> [--actions f] [--dump-at n --dump f] [--out f]");
        std::string actions_p, dump_p, out_p;
        long dump_at = -1;
        for (int k = 3; k + 1 < argc; k += 2) {
            std::string o = argv[k];
            if (o == "--actions") actions_p = argv[k + 1];
            else if (o == "--dump-at") dump_at = std::strtol(argv[k + 1], nullptr, 10);
            else if (o == "--dump") dump_p = argv[k + 1];
            else if (o == "--out") out_p = argv[k + 1];
            else throw std::runtime_error("unknown option " + o);
        }
        foccsim::WorldState ws = foccsim::WorldState::from_json(slurp(argv[1]));
        foccsim::Value actions = actions_p.empty() ? foccsim::Value::array() : foccsim::parse(slurp(actions_p));
        long ticks = std::strtol(argv[2], nullptr, 10);
        for (long t = 1; t <= ticks; ++t) {
            for (const foccsim::Value& a : *actions.a)
                if (a.o->at("hour").i == ws.hour) foccsim::apply_action(ws, a);
            foccsim::tick(ws);
            std::string text = ws.to_json();
            std::printf("%ld %lld %s\n", t, static_cast<long long>(ws.hour), focc::sha256_hex(text).c_str());
            if (t == dump_at && !dump_p.empty()) spit(dump_p, text);
        }
        if (!out_p.empty()) spit(out_p, ws.to_json());
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "foccsim: %s\n", e.what());
        return 2;
    }
}
