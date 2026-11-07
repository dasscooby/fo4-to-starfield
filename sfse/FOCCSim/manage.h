// The combined core's settlement management, step C4 of docs/combined-core-cpp-port.md, ported from
// src/fo4sf/combined/manage.py: the player's actions on a settlement (move settlers between roles, build beds, set a
// production focus, send supplies as a caravan) and a settlement's status for a UI. Every action checks its arguments
// and throws std::invalid_argument with Python's ValueError message, word for word, before it changes anything; then
// it logs an event. Python stays the reference.
#pragma once

#include <string>

#include "foccsim.h"

namespace foccsim::manage {

constexpr Int BEDS_MAX = 60;                    // manage.BEDS_MAX (placeholder)
constexpr Int THREAT_HOURS = 12;                // manage.THREAT_HOURS (placeholder)

Counts assign_role(WorldState& ws, const std::string& settlement, const std::string& from_role,
                   const std::string& to_role, Int n = 1);                       // the new role counts
Int add_beds(WorldState& ws, const std::string& settlement, Int n = 1);          // the new bed count
OptStr set_priority(WorldState& ws, const std::string& settlement, const OptStr& good);   // nullopt clears it
std::string send_supplies(WorldState& ws, const std::string& from_settlement, const std::string& to_settlement,
                          const Counts& goods);                                  // the caravan squad's id
Value threats(const WorldState& ws, const std::string& settlement, Int hours = THREAT_HOURS);   // [{place, ...}]
Value status(const WorldState& ws, const std::string& settlement);               // manage.status's dict

// Python's repr() of a str, for the messages (quotes as Python picks them; backslash escapes for control characters).
std::string py_repr(const std::string& s);

}  // namespace foccsim::manage
