// The FOCCSim portable core: the combined core's world state and its 6-hour tick, ported from the Python reference
// (src/fo4sf/combined/model.py, sim.py, reputation.py, modes.py) so it gives byte-identical canonical JSON after every
// tick (docs/combined-core-cpp-port.md: step C1, the parity contract in section 2, what must be copied exactly in
// section 3). No Windows, no SFSE: the in-game plugin wraps this later. Python stays the reference: when the two
// disagree, this file is wrong.
#pragma once

#include <cstdint>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "json.h"

namespace foccsim {

using Int = std::int64_t;
using Counts = std::map<std::string, Int>;
using OptStr = std::optional<std::string>;

struct Place {
    std::string id, region, kind;
    OptStr holder, story_lock;
    Int defence = 0;
};

struct Settlement {
    std::string place;
    Int population = 0;
    Counts roles, stock;
    Int morale = 50, stage = 0, beds = 20;
    OptStr priority;
};

struct Faction {
    std::string id;
    Int strength = 0;
    std::string home;
    Int aggression = 50;
    Counts relations;
};

struct Squad {
    std::string id, faction;
    Int size = 0;
    std::string at;
    OptStr goal;
    std::string kind = "patrol";
    Counts cargo;
    Int eta = 0;
};

struct Route {
    std::string a, b;
    Int hours = 0;
};

struct Reputation {
    Int fame = 0, infamy = 0;
};

struct Settings {
    std::string survival = "off", raid_pressure = "normal";
    bool story_mode = false;
    std::vector<std::string> active_stories;   // sorted, unique

    double raid_multiplier() const;
    bool story_active(const OptStr& story) const;
};

struct WorldState {
    Int seed = 0, hour = 0, next_id = 1;
    std::map<std::string, Place> places;
    std::map<std::string, Settlement> settlements;
    std::map<std::string, Faction> factions;
    std::map<std::string, Squad> squads;
    std::vector<Route> routes;
    std::map<std::string, Reputation> reputation;
    std::vector<Value> events;                 // JSON objects: hour, kind, place, region and per-kind fields
    std::map<std::string, std::map<std::string, Reputation>> regional_reputation;
    Settings settings;

    static WorldState from_json(const std::string& text);   // model.WorldState.from_json; throws on a bad state
    std::string to_json() const;                             // model.WorldState.to_json, byte for byte
};

// sim.py
void tick(WorldState& ws);
void player_helped(WorldState& ws, const std::string& faction, Int amount = 10);
std::string player_defended(WorldState& ws, const std::string& place, Int bonus = 10, Int hours = 72);
Counts player_traded(WorldState& ws, const std::string& settlement, const Counts& goods);

// The harness's scripted player action ({"hour", "do": "help" | "defend" | "trade", ...}), applied when ws.hour equals
// its hour, before that tick (tests/test_combined_cpp_parity.py applies them the same way in Python).
void apply_action(WorldState& ws, const Value& action);

}  // namespace foccsim
