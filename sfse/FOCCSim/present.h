// The combined core's presentation planner, step C3 of docs/combined-core-cpp-port.md, ported from
// src/fo4sf/combined/present.py: what the simulation says is near the player, as abstract spawn slots (garrisons,
// settlers, squads and caravans within a route-hour radius, nearest first, within an actor budget), and what moving
// from one plan to the next spawns, keeps and dissolves. It reads the world state only. Python stays the reference,
// and present.py's docstring has the design and its placeholders.
#pragma once

#include <map>
#include <optional>
#include <string>
#include <tuple>
#include <vector>

#include "foccsim.h"

namespace foccsim::present {

constexpr Int RADIUS_HOURS = 6;                 // present.RADIUS_HOURS (placeholder)
constexpr Int MAX_LIVE_ACTORS = 40;             // present.MAX_LIVE_ACTORS (placeholder)

struct Slot {                                   // present.Slot
    std::string id;                             // garrison:<place>:<holder>, settler:<place>:<role>, squad:<id>, caravan:<id>
    std::string kind;                           // garrison | settler | squad | caravan
    std::string place;
    OptStr faction;
    Int count = 0;
    OptStr role;                                // settler role, or the squad's kind
    Int distance = 0;                           // route hours from the player

    std::tuple<Int, Int, std::string> rank() const;   // Slot.rank: distance, class, id
    Value to_value() const;
};

struct Plan {                                   // present.Plan
    std::string centre;
    Int hour = 0, radius_hours = RADIUS_HOURS;
    std::vector<std::string> places;            // in radius, nearest first
    std::vector<Slot> slots;                    // within budget, in priority order
    std::vector<Slot> dropped;                  // over budget, in priority order
    Int actors() const;
    Value to_value() const;                     // Plan.to_dict()
};

struct Diff {                                   // present.Diff, each list sorted by id
    std::vector<Slot> spawn, keep, dissolve;
    Value to_value() const;                     // {"dissolve", "keep", "spawn"}
};

Int garrison_size(const WorldState& ws, const std::string& place);
// Throws std::out_of_range ("unknown place ...") for a place the world lacks, where Python raises KeyError.
Plan plan(const WorldState& ws, const std::string& player_place, Int radius_hours = RADIUS_HOURS,
          Int max_actors = MAX_LIVE_ACTORS);
// nullptr: nothing is shown yet. Throws std::invalid_argument, where Python raises ValueError, when either plan has
// duplicate slot ids.
Diff diff(const Plan* old_plan, const Plan& new_plan);

}  // namespace foccsim::present
