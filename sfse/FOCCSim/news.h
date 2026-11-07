// The combined core's news, from src/fo4sf/combined/news.py. So far only the helpers the radiant jobs need for their
// text (step C4): display names, a cargo list and a day stamp. The headlines and the terminal page are step C5.
// Python stays the reference.
#pragma once

#include <map>
#include <string>

#include "foccsim.h"

namespace foccsim::news {

using Names = std::map<std::string, std::string>;   // a pack's display names: id -> name

std::string display_name(const OptStr& ident, const Names* names = nullptr);   // news.display_name
std::string cargo(const Counts& cargo);                                        // news._cargo
std::string stamp(Int hour);                                                   // news._stamp: "Day 3, 06:00"

}  // namespace foccsim::news
