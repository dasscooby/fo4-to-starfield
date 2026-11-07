// The combined core's engine adapter, step C2 of docs/combined-core-cpp-port.md, ported from
// src/fo4sf/combined/adapter.py. It names the records the game reads (one keyword per place for its holder, one global
// per faction for the reputation tier, one global per play setting), gives the value each should hold for a world
// state, and lists the fewest writes from one view to the next. It writes nothing itself: Papyrus or the plugin does
// the writes. Python stays the reference, and adapter.py's docstring has the design and its assumptions.
#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "foccsim.h"

namespace foccsim::adapter {

inline const std::string PREFIX = "FOCC_";      // adapter.PREFIX (design CC-03's default)
constexpr std::size_t EDITOR_ID_MAX = 64;       // adapter.EDITOR_ID_MAX (an assumption there too)
constexpr Int EMPTY_HOLDER = 0;                 // the holder code of a place nobody holds

struct Slot {                                   // adapter.Slot
    std::string id, kind, purpose, subject;     // kind: keyword | global; purpose: holder | reputation | setting
    OptStr probe;                               // the PC probe its viability waits on ("P2" for keyword data)
};

struct Plan {                                   // adapter.Plan
    std::string prefix;
    std::map<std::string, Int> holder_codes;    // faction id -> 1, 2, ... in sorted order
    std::vector<Slot> slots;                    // sorted by id
    Value to_value() const;                     // Plan.to_dict(), for canonical JSON
};

using View = std::map<std::string, Int>;                     // slot id -> value
using Writes = std::vector<std::pair<std::string, Int>>;     // (slot id, value), sorted by id

// These throw std::invalid_argument where Python raises ValueError.
std::string editor_id(const std::vector<std::string>& parts, const std::string& prefix = PREFIX);
std::map<std::string, Int> holder_codes(const WorldState& ws);
Int reputation_level(Int points);                            // reputation.level
Int reputation_tier(const WorldState& ws, const std::string& faction);
Plan record_plan(const WorldState& ws, const std::string& prefix = PREFIX);
View game_view(const WorldState& ws, const Plan& plan);
Writes changes(const View* old_view, const View& new_view);  // nullptr: nothing is written yet

Value view_value(const View& view);                          // {slot id: value}
Value writes_value(const Writes& writes);                    // [[slot id, value], ...]

}  // namespace foccsim::adapter
