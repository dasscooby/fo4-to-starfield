# FOCCSim: the combined core's simulation in portable C++

Step C1 of `docs/combined-core-cpp-port.md`. This is the world state and its 6-hour tick from the Python reference
(`src/fo4sf/combined/model.py`, `sim.py`, `reputation.py`, `modes.py`) as plain C++17, with no Windows and no SFSE.
The in-game plugin wraps it later.

Python stays the reference. The contract is byte-identical canonical JSON after every tick, from the same state, the
same number of ticks and the same player actions. `tests/test_combined_cpp_parity.py` checks that on every CI run.

| File | What |
|---|---|
| `pyrandom.h` | CPython's `random.Random`: MT19937 seeded with `init_by_array` over the seed's 32-bit words; `random()`, `getrandbits` and `choice` through `_randbelow` |
| `json.h` | a reader for the world state Python writes, and a writer that matches `json.dumps(..., sort_keys=True)` byte for byte (separators `", "` and `": "`, `\uXXXX` for everything outside space to `~`). Integers only: a float is refused |
| `foccsim.h`, `foccsim.cpp` | the state (`WorldState::from_json` / `to_json`, with the reference's checks), `tick`, and the player hooks `player_helped`, `player_defended`, `player_traded` |
| `main.cpp` | the harness's command line: `foccsim <state.json> <ticks> [--actions f] [--dump-at n --dump f] [--out f]`, printing `<tick> <hour> <sha256>` per tick |

The SHA-256 comes from `../FOCCSidecar/sha256.cpp`, which is already portable.

## Build

```
g++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra -o foccsim foccsim.cpp main.cpp ../FOCCSidecar/sha256.cpp
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

`FO4SF_PARITY_FULL=1` compares after every tick, runs every variant for seeds 0 to 9, and runs the
Commonwealth-scale draft for 90 days.

Not here yet (later steps of the plan): C2 `adapter.py`, C3 `present.py`, C4 `manage.py` and `jobs.py`, C5 `news.py`;
the SFSE plugin around the core; the event-log indexes that would let the log be trimmed.
