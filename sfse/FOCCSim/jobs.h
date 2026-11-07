// The combined core's radiant work, step C4 of docs/combined-core-cpp-port.md, ported from
// src/fo4sf/combined/jobs.py: the offers the holder of a place makes the player there (defend, escort, retake,
// resupply, clear), each read from what the simulation is doing now, and what completing or giving one up changes.
// complete() throws std::invalid_argument with Python's ValueError message when the offer is expired or moot, and so
// does fail() for an offer that already has an outcome, was superseded, or was read at an hour the world has not
// reached. Python stays the reference, and jobs.py's docstring has the design and its placeholders.
//
// An offer's first character is upper-cased as news::upper_first does it (Python's str.upper for the scripts it
// covers). An offer starts with a display name only for resupply, and only a pack's display names can be non-ASCII.
#pragma once

#include <optional>
#include <string>
#include <vector>

#include "foccsim.h"
#include "news.h"

namespace foccsim::jobs {

constexpr Int OFFER_LIMIT = 5;                  // jobs.OFFER_LIMIT (placeholder)

struct Offer {                                  // jobs.Offer
    std::string id, kind, giver, place, target;
    Int reward_tier = 1, offered_hour = 0, expires_hour = 0;
    std::string text;
    Object detail;                              // the kind's specifics, re-checked by valid()
    Int read_at = 0;                            // ws.events.size() when the instance was read (jobs.Offer.read_at)
    Value to_value() const;                     // Offer.to_dict()
};

// Throws std::out_of_range ("unknown place ...") for a place the world lacks, where Python raises KeyError.
std::vector<Offer> offers(const WorldState& ws, const std::string& place, Int limit = OFFER_LIMIT,
                          const news::Names* names = nullptr);
std::optional<std::string> valid(const WorldState& ws, const Offer& offer);   // why it can no longer be done
Value complete(WorldState& ws, const Offer& offer);                           // what changed
Int fail(WorldState& ws, const Offer& offer);                                 // the infamy applied

}  // namespace foccsim::jobs
