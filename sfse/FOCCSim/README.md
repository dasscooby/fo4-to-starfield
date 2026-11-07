# FOCCSim: the combined core's simulation in portable C++

Steps C1 to C5 of `docs/combined-core-cpp-port.md`, as plain C++17 with no Windows and no SFSE:
- the world state and its 6-hour tick, from the Python reference (`src/fo4sf/combined/model.py`, `sim.py`,
  `reputation.py`, `modes.py`);
- the engine adapter (`adapter.py`): which keyword data and globals Papyrus must write;
- the presentation planner (`present.py`): what to spawn and dissolve near the player;
- settlement management (`manage.py`) and the radiant jobs (`jobs.py`): the player's actions on a settlement, and
  the work a faction offers, done or given up;
- the news (`news.py`): events as headlines in our own words once they have travelled to a place, and the terminal
  page, wrapped as Python's `textwrap` wraps it.

The in-game plugin wraps it later.

Python stays the reference. The contract is byte-identical canonical JSON after every tick, from the same state, the
same number of ticks and the same player actions. `tests/test_combined_cpp_parity.py` checks that on every CI run.

| File | What |
|---|---|
| `pyrandom.h` | CPython's `random.Random`: MT19937 seeded with `init_by_array` over the seed's 32-bit words; `random()`, `getrandbits` and `choice` through `_randbelow` |
| `json.h` | a reader for the world state Python writes, and a writer that matches `json.dumps(..., sort_keys=True)` byte for byte (separators `", "` and `": "`, `\uXXXX` for everything outside space to `~`). Integers only: a float is refused |
| `foccsim.h`, `foccsim.cpp` | the state (`WorldState::from_json` / `to_json`, with the reference's checks), `tick`, and the player hooks `player_helped`, `player_defended`, `player_traded` |
| `adapter.h`, `adapter.cpp` | step C2, the engine adapter (`adapter.py`): the record plan (a keyword per place for its holder, a global per faction for the reputation tier, a global per play setting), the game view for a state, and the fewest writes between two views |
| `present.h`, `present.cpp` | step C3, the presentation planner (`present.py`): garrisons, settlers, squads and caravans within a route-hour radius of the player, nearest first, within an actor budget (the rest listed as dropped), and the spawn, keep and dissolve lists between two plans |
| `manage.h`, `manage.cpp` | step C4, `manage.py`: move settlers between roles, build beds, set a production focus, send supplies as a caravan, a settlement's threats and status. Refusals throw `std::invalid_argument` with Python's ValueError message, word for word |
| `jobs.h`, `jobs.cpp` | step C4, `jobs.py`: the offers (defend, escort, retake, resupply, clear) with their text, why an offer is moot, and completing or giving one up |
| `news.h`, `news.cpp` | step C5, `news.py` and `sim.news_for`: headlines, items, the terminal page; with a port of `textwrap.wrap` and `textwrap.shorten` (textwrap's defaults) and of `str.upper` for a first letter. Known differences, both outside the common scripts: which characters textwrap treats as letters for hyphen breaks (exact for ASCII and Latin-1, common letter blocks beyond), and the capital of a first letter (exact for ASCII, Latin-1, Latin Extended-A, Cyrillic U+0400 to U+045F and modern Greek) |
| `main.cpp` | the harness's command line: `foccsim <state.json> <ticks> [--actions f] [--dump-at n --dump f] [--out f] [--adapter f] [--prefix p]`, printing `<tick> <hour> <sha256>` per tick; `--adapter` writes the plan and view at the start, then each tick's writes, as canonical JSON lines |

The SHA-256 comes from `../FOCCSidecar/sha256.cpp`, which is already portable.

## Build

```
g++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra -o foccsim *.cpp ../FOCCSidecar/sha256.cpp
```

clang++ takes the same flags. `-ffp-contract=off` matters: a fused multiply-add would change the rounding of the three
float rolls (port plan section 3, "Floats"). For MSVC the plan names `/fp:precise` without `/fp:contract`; the code
avoids `__int128` and GCC-only features for it, but it has not been built with cl.exe yet (unverified).

## What is checked

On CI, with the compiler on PATH (`tests/test_combined_cpp_parity.py`):
- **Fixture world:** the two-region world for seeds 0 to 9 over 90 days.
- **Variants on it:** raid pressure low and high, story mode with an active story, and a script of player actions
  (help, defend, trade) at fixed hours.
- **Commonwealth scale:** the Commonwealth-scale draft (234 places, 38 settlements, 7 factions) for 30 days.
- **Round trip:** a state is read and written back byte for byte, including escapes, non-ASCII text and nested event
  fields.
- **Refusals:** a seed outside 64 bits, a float, an unknown field, an unknown schema, a non-ASCII id, an unknown
  preset.
- **Engine adapter (C2), on every run above:** the record plan and game view at the start, then each tick's writes,
  compared as text after every tick. Writes chain from the start, so the game view matches after every tick too. Also:
  ids with other characters (`farm-c`, `ruin.2 x`) and one exactly at the 64-character limit, a second prefix, every
  setting's value, the reputation thresholds, and Python's own messages for a colliding id, a too-long id and an
  invalid prefix.
- **Presentation planner (C3), on every run above:** the player walks one route step a tick. Every 5th tick has a wide
  view on a 15-actor budget (so slots are dropped), and every 7th tick a second look from elsewhere (a fast travel).
  Each plan and its diff from the plan before are compared as text. Also: the player's own garrison ranked last at
  its distance, a role above the per-role cap, budgets that cut at each slot boundary, and Python's message for an
  unknown place.
- **Settlements and jobs (C4):** a scripted player on the fixture world (seeds 0 and 3; all ten with
  `FO4SF_PARITY_FULL=1`) and the Commonwealth-scale draft (seed 0). Each day it asks for a status and the offers
  somewhere, does the first offer and gives up the second, sometimes at once and sometimes too late. It also moves
  settlers, builds beds, sets and clears a focus, sends supplies, and on day 2 tries every refusal manage has. Each
  action's result or Python's refusal message is compared as text, and the state after every tick as before. Also:
  every reason an offer is moot (taken from a world changed after the offer), each kind done and then done again
  and given up, the offers' text with a pack's display names, limits of 0 and -2, each manage action exactly at its
  limit and one past it, and a defence whose attack is due after 72 hours.
- **News (C5):** the scripted player also reads the news somewhere each day, at widths from 60 down to 7, with and
  without display names (some with hyphens and a non-ASCII letter). Items and terminal page are compared. Also: a
  headline for every template and the variants between them, an unknown kind, exact repeats, news not yet arrived,
  since and limit, empty pages, and widths too small for the title. And a fuzz test: `wrap` and `shorten` against
  Python's `textwrap` on 3,000 random texts (hyphens, em-dashes, punctuation, tabs and every other whitespace,
  a no-break space, non-ASCII letters, widths -1 to 40, indents, placeholders), plus `upper_first` against
  `str.upper` for every first character it covers.

`FO4SF_PARITY_FULL=1` compares after every tick, runs every variant for seeds 0 to 9, and runs the
Commonwealth-scale draft for 90 days.

Not here yet (later steps of the plan): the SFSE plugin around the core; the event-log indexes that would let the log be trimmed.
