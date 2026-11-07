// FOCCSim's news helpers (see news.h), each named after its Python original in src/fo4sf/combined/news.py.
#include "news.h"

namespace foccsim::news {

namespace {
constexpr Int HOURS_PER_DAY = 24;                   // news.HOURS_PER_DAY
}  // namespace

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

}  // namespace foccsim::news
