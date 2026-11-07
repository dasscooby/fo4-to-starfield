// The combined core's news, step C5 of docs/combined-core-cpp-port.md, ported from src/fo4sf/combined/news.py: the
// simulation's events as short lines of our own writing (the templates are ours, as news.py says), for terminals and
// on-screen text. An event reaches a place only after it has had time to travel there along the routes
// (sim.news_for). The terminal page wraps its lines as Python's textwrap does. Python stays the reference.
//
// Known difference: for characters outside ASCII and Latin-1, Python's textwrap asks Unicode which characters are
// letters and digits (for where a hyphenated word may break). This port knows the common letter blocks and a few digit
// blocks, and treats any other character outside those ranges as punctuation. ASCII and Latin-1 text wraps
// identically.
#pragma once

#include <map>
#include <string>
#include <vector>

#include "foccsim.h"

namespace foccsim::news {

using Names = std::map<std::string, std::string>;   // a pack's display names: id -> name

constexpr Int HEADLINE_LIMIT = 12;                  // news.HEADLINE_LIMIT (placeholder)
constexpr Int TERMINAL_WIDTH = 60;                  // news.TERMINAL_WIDTH (placeholder)

std::string display_name(const OptStr& ident, const Names* names = nullptr);   // news.display_name
std::string cargo(const Counts& cargo);                                        // news._cargo
std::string stamp(Int hour);                                                   // news._stamp: "Day 3, 06:00"

// text[0].upper() + text[1:]: exact for ASCII, Latin-1, Latin Extended-A, Cyrillic U+0400 to U+045F and the modern
// Greek letters (not the archaic ones or the two with dialytika and tonos); any other first character is kept as is
std::string upper_first(const std::string& text);

std::vector<Value> news_for(const WorldState& ws, const std::string& place, Int since = 0);   // sim.news_for
OptStr headline(const Value& event, const Names* names = nullptr);   // nullopt for a kind without a template
Value items(const WorldState& ws, const std::string& place, Int since = 0, Int limit = HEADLINE_LIMIT,
            const Names* names = nullptr);                           // [{hour, kind, place, text}], newest first
std::vector<std::string> headlines(const WorldState& ws, const std::string& place, Int since = 0,
                                   Int limit = HEADLINE_LIMIT, const Names* names = nullptr);
std::string terminal_page(const WorldState& ws, const std::string& place, Int since = 0, Int limit = HEADLINE_LIMIT,
                          Int width = TERMINAL_WIDTH, const Names* names = nullptr);

// Python's textwrap.wrap(text, width, subsequent_indent=indent) and textwrap.shorten(text, width,
// placeholder=placeholder), with their other defaults. Both throw std::invalid_argument with textwrap's ValueError
// message for a width below 1 or a placeholder that cannot fit.
std::vector<std::string> wrap(const std::string& text, Int width, const std::string& subsequent_indent = "");
std::string shorten(const std::string& text, Int width, const std::string& placeholder = " [...]");

}  // namespace foccsim::news
