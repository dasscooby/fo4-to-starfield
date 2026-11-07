# The combined core (GAMMA-style way to play): what is in the repo

The design lives in the project's framework, `docs/research/framework/combined-core.md` (draft PR #408; until it
merges, the Combined core thread holds it). This page says what `src/fo4sf/combined/` implements today and how to
run it. Owner of the design, quoted from its header: "the Combined core thread (Claude-cloud)".

## What it is

The second way to play: one curated Fallout on Starfield's engine, built like S.T.A.L.K.E.R. GAMMA on Anomaly, for
players who own every included game plus Starfield. Its pillars are settlements that grow, factions that act and hold
territory, and a connected wasteland; survival is one layer. Everything is built on the player's PC from their own
installs; nothing of Bethesda's is shipped, and `scripts/guard.py` fails the build if game data lands in the repo.

It is **not** the leader core: `src/fo4sf/core/` is the build-and-test orchestrator (ledger, lease, preflight).
The combined core is game runtime; its records and packages are kept apart from the leader core's.

## Layer map (from the design)

| Layer | Content | Here now |
|---|---|---|
| L5 content packs | Commonwealth pack first, other worlds and community packs later; packs only add data | `pack.py`, `fixtures.py` (synthetic) |
| L4 player systems | reputation UI, settlement management, survival, RP SPECIAL | `reputation.py`, `modes.py`, `manage.py` (data, no UI) |
| L3 presentation | materialize squads and caravans near the player, radiant quests, radio and terminal news | `present.py`, `news.py`, `jobs.py` (data, no spawns) |
| L2 simulation | faction AI, settlement growth, supply and trade, events; coarse ticks, deterministic per seed | `sim.py` |
| L1 world-state model | places, holders, settlements, factions, routes, events; game-neutral data | `model.py` (schema 2) |
| engine edge | records the save keeps, plus the plugin's sidecar (CC-02 C') | `adapter.py`, `sidecar.py` (plan and codec only) |
| L0 converted worlds | per-game modules from the single-game pipeline | the rest of the repo |

## Implemented now (M1, all offline, pure Python stdlib)

- `model.py`: L1 dataclasses and `WorldState` with a versioned JSON round trip.
- `pack.py`: `validate_pack` and `load_pack`; a pack is JSON that only adds; a second region plugs into the first
  through a gateway place without the first knowing about it.
- `sim.py`: L2 ticks of 6 game hours; the RNG is seeded from (seed, hour), so a state saved and resumed replays
  exactly. Invariants kept: story-locked places and faction homes never change hands; values stay in range.
- `seed.py`: a read-only reader that drafts a pack from the player's own Fallout 4 plugins (LCTN, FACT, KYWD, LCRT,
  then the REFR map markers the locations name; field layouts cited from xEdit dev-4.1.6 in the module docstring).
  Settlement and faction classification are regex guesses; the first real run (below) supports them. Its output
  stays on the player's PC.
- `__main__.py`: the command line below.

## Implemented now (M2, still offline, pure Python stdlib)

- `present.py`: the L3 presence planner. `plan(ws, player_place)` lists what to materialize within a route radius of
  the player as abstract spawn slots under an actor budget (attackers, garrisons, settlers, squads, caravans);
  `diff(old, new)` says what a replan spawns, keeps and dissolves. Nothing is spawned; it is data for an adapter.
- `news.py`: L3 terminal news. The simulation's events, as reached along the routes (`sim.news_for`), become short
  lines in our own words; `terminal_page` wraps them for a terminal. Text only, no voice, quotes no game's writing.
- `reputation.py`: L4 New Vegas-style fame and infamy per faction (two scales, four levels each, tiered gains cited
  from `settlements-factions-precedents.md`), an optional per-region layer (CC-22) that is empty in a one-world game,
  and abstract effects (price, refusal, hostility) as placeholder tiers for probe P7.
- `modes.py`: L4 play settings stored in the save (schema 2): survival presets off/light/full (data only, no needs
  model yet), raid pressure low/normal/high scaling the attack and raid rolls, and the chronological story mode
  (CC-50), which shields places near an active story's locked place from attack.
- `adapter.py`: the engine edge as a record plan, not records: `record_plan(ws)` names the `FOCC_` slots a pack
  needs (one keyword per place for holder keyword data, our choice where the note plans a single `FOCC_Holder`
  keyword, probe P2; one global per faction for the reputation tier;
  globals for the settings), `game_view(ws)` gives each slot's value, `changes(old, new)` the minimal writes.
  Holder codes are small ints from sorted faction ids. Nothing writes a plugin.
- `sidecar.py`: the reference codec for the per-save file an SFSE plugin would keep (no co-save exists; SFSE's
  save and load messages carry the save name, `engine-feasibility.md`): a sanitised file name per save, JSON body
  with a sha256 of the canonical state, atomic `write`, `read` that refuses a wrong format, schema or checksum, and
  `orphans` that lists sidecars whose save is gone and never deletes.

## Implemented now (M3, still offline, pure Python stdlib)

- `jobs.py`: L3 radiant work. `offers(ws, place)` lists what the faction holding the place asks of the player right
  now (defend, escort, retake, resupply, clear), each derived from something the simulation is doing; `complete`
  goes through the simulation's player hooks (defend, escort, resupply) or a logged direct change of holder (retake,
  clear) so the next tick runs on a changed world, following the verified criticism in `gamma-anatomy.md` 2.6 and
  our own anti-lesson 1 (section 5, H) that faction tasks should change territory or supply state. A cleared place
  counts as lost to its old holder everywhere (`sim.holder_changes`). No money, no quest records, our own text.
- `manage.py`: L4 settlement management as pure functions: `assign_role`, `add_beds`, `set_priority` (a production
  focus the simulation honours), `send_supplies` (a caravan the simulation resolves and raiders may hit), `threats`,
  `status`. Every action validates, then logs an event the news (`news.TEMPLATES` has a line for each) and a resumed
  save see.
- `balance.py`: the tuning harness. `metrics(ws)` reads one finished world (places changing hands per 30 days,
  attacks per day, caravans raided share, empty settlements, mean morale, per-faction share of time landless and
  home-only, story-lock and home violations, frozen regions); `sweep(packs, seeds, days, overrides)` runs fresh
  worlds per seed with `sim` constants overridden inside a context manager that always restores them (a value of
  the wrong kind, a string for a number, is refused before the sweep runs);
  `check(aggregate, bounds)` lists the bounds broken. `DEFAULT_BOUNDS` is a placeholder envelope around the fixture
  baseline below, not a balance decision. `__main__.py` gains `balance`, `news` and `present` (Run it, below).

### Balance baseline (before-number, per AGENTS.md's measured-before-and-after rule)

Fixtures, 20 seeds x 90 days, `PYTHONPATH=src python3 -m fo4sf.combined balance --seeds 20 --days 90` (under a
second). "Before" is the M3 constants, 2026-10-20; "after" is the same command on 2026-10-21 with the two settlement
rules added below (`sim.REROLE_ON_SHORTAGE`, `sim.RESETTLE_*`), everything else unchanged; "scale rules" is the same
command later that day with the four growth rules from the Commonwealth-scale baseline below (`sim.FARM_SLOTS_PER_BEDS`,
`LEAVE_ONLY_WHEN_SHORT`, `MORALE_DRIFT`, `ARRIVAL_SLOWDOWN_POP`). Later tuning changes add a column the same way.

| Metric | Before (2026-10-20) | After (2026-10-21) | Scale rules (2026-10-21) | Reads as |
|---|---|---|---|---|
| changes_per_30_days | 15.0 | 12.5 | 12.6 | places change hands about every two and a half days across 11 places |
| attacks_per_day | 1.08 | 1.09 | 1.04 | about one attack squad launched per game day (unchanged) |
| caravans_raided_share | 0.13 | 0.10 | 0.135 | one caravan in ten is intercepted |
| empty_settlements | 1.6 of 4 | 0.0 of 4 | 0.0 of 4 | no run ends with an empty settlement |
| settlements_emptied (new) | 2.3 | 2.35 | 2.2 | a settlement still falls empty about twice per run (per 4 settlements, 90 days) |
| resettlements (new) | 0 | 1.75 | 1.25 | and is resettled; the rest refill through the older arrival rule |
| empty_share (new) | 0.32 | 0.024 | 0.025 | share of settlement-hours with nobody home: a third of the run, now one fortieth |
| mean_morale | 48.2 | 85.9 | 90.2 | settlers were flat or starving; now most settlements are fed and growing |
| landless_share_max | 0.0 | 0.0 | 0.0 | 0 by construction while homes never change hands |
| home_only_share | slavers 1.0, traders 0.62, order 0.53, raiders 0.35, settlers 0.0 | slavers 1.0, traders 0.62, order 0.47, raiders 0.40, settlers 0.0 | slavers 1.0, traders 0.59, order 0.60, raiders 0.36, settlers 0.0 | see note |
| story_lock_violations, home_violations | 0, 0 | 0, 0 | 0, 0 | invariants hold over all seeds |
| frozen_regions | none | none | none | both regions saw a change of holder in every seed |

The fixtures barely move under the scale rules (their settlements are small and fought over; `river_town` now stops
at its food edge of 15 instead of its 20 beds) and `DEFAULT_BOUNDS` still passes; `mean_morale` rises because the new
drift lifts a fed place that has no surplus.

The three new metrics are rebuilt from two new event kinds, `settlement_emptied` (the last settler leaves, or a
capture removes the last people; carries `holder`) and `settlement_resettled` (carries `faction`, the holder), so a
resumed save measures the same; a save from before 2026-10-21 has neither and measures `empty_share` 0 until
something happens. The "before" column's new metrics come from the same command with the rules switched off
(`--set sim.REROLE_ON_SHORTAGE=0 --set sim.RESETTLE_SAFE_HOURS=1000000000`).

**Diagnosis of the 1.6 (traces in the per-seed harness, 20 seeds x 90 days, old rules).** 40 emptyings: 31 were
the last settler leaving after a morale collapse, 8 a capture removing the last one or two people, 1 both. The
collapse was always starvation after capture: `_remove_settler` takes from the biggest role, which on a farm is
the farmers, so a capture of `farm_a` (3 farmers, 1 guard, 1 trader) removed all three farmers, the guard and
trader ate the stock down (seed 9: dead at hour 126), and nothing could recover because the arrival rule needs
morale 70 and a surplus. Once empty, 96% of the empty settlement-hours had food or water at 0, and with nobody
producing and no caravan going to a raider-held farm, morale stays frozen and the place is dead for the rest of
the run (32% of all settlement-hours were empty). Not beds (20, never the cap at the time), not raided caravans
(13%). Judged a rule problem: people do not starve beside a field, and an empty place a faction holds should be
able to be lived in again.

**Rules added (placeholder constants in `sim.py`, overridable in sweeps):**
- `REROLE_ON_SHORTAGE = 1`: on a tick short of food or water, one settler of the biggest non-farmer role takes up
  farming while `3 * farmers < population + 2` (the food rule `_add_settler` grows by). Logged as `roles_changed`
  with the same fields as `manage.set_roles`. Capture still halves the population and caps morale at 30, and the
  larder still drains for a tick or two (the `resupply` job window stays), but the place feeds itself again.
  Rejected alternative, measured: taking non-farmers first on removal gave the same emptiness numbers but no
  shortage ever, so `resupply` jobs never appeared and caravans grew to 74 goods (which also exposed that
  `jobs.Offer.reward_tier` stores points, not a 1..5 tier, so a cargo of 30 or more fails the offer-shape test; a `jobs.py` finding for its owner, not reached by the rules kept).
- `RESETTLE_SAFE_HOURS = 48`, `RESETTLE_KIT = 6`, `RESETTLE_MORALE = 50`: an empty settlement a faction holds (and
  with beds) draws one wanderer on a day tick when no attack squad is bound for it and no `place_taken`,
  `attack_failed` or `place_cleared` touched it within the window; the wanderer is a farmer, brings the kit in
  food and water, and morale restarts at no less than 50. Logged as `settlement_resettled`. No random draw, so
  the RNG sequence of every other rule is unchanged.

Variants measured for the decision (same command, 20 seeds x 90 days): re-role only gives empty_share 0.031 and
resettlements 0 (the older arrival rule refills a place that still has stock); resettle only gives 0.037 with 4.45
emptyings and 3.65 resettlements per run (farms keep dying and being reseeded); both give 0.024 with 2.35 and 1.75.
`DEFAULT_BOUNDS` tightened to match: `empty_settlements` at most 1.0 (was 2.5), `empty_share` at most 0.15 (new).

Findings for the lead, not fixed here: `slavers` never leave home because `slaver_pit`'s one route leads to
`river_town`, the traders' home, which can never be attacked (fixture shape, so `home_only_share` is reported but
not bounded). `market` never grows past its starting 6 in any seed under either rule set: its two farmers make exactly
the 6 water its 6 settlers drink, and caravans carry only food, so the morale rule's surplus test (`stock > 2 * need`
for both goods) never passes; `river_town` reaches its 20 beds at hour 432 (day 18) in every seed and stays there (slavers cannot attack a home). Both are fixture-shape
findings; a water cargo or a lower morale threshold would be a tuning question. Mean morale 86 reads as generous:
whether settlements should thrive this easily between raids is for the lead to judge against the design, and
`RAID`/`ATTACK` pressure and `REROLE_ON_SHORTAGE` are the knobs.

### Commonwealth-scale baseline (synthetic fixture, before and after)

The first real `simulate --seed 1 --days 30` on the generated pack (owner's PC, 2026-10-21, 233 places, 38
settlements) ended with 36 of 38 settlements at morale 100, population 20 (the bed cap) and stage 3, and 441 of
446 routes at 1 hour. To work on that offline, `tests/test_combined_seedpack.py` has `commonwealth_scale_draft()`:
a synthetic seed draft that mirrors only that run's **counts** (38 settlement candidates of which 6 have no marker,
29 + 22 + 19 + 12 enemy bases, 7 unheld bases, 106 landmarks carrying the run's unmapped keyword counts, 164 places
without a marker that are dropped) with invented ids and uniformly random marker positions on a plane. It says
nothing about any map; it is a load at the right scale. The sweeps below are 5 seeds x 90 days on the pack
`seedpack.generate` makes from it (`balance.sweep`; about 10 s).

**Diagnosis (throwaway traces, not kept).** Not the caravans. A settlement alone, with no routes at all, reaches 20
of 20 beds on day 18 with food at 440 and climbing: three farmers make 9 food and 9 water a tick against 5 eaten,
`_add_settler` keeps farmers at about a third of the population, so production always beats consumption, stock
only grows, morale gains 2 a tick to 100, and one settler arrives every day until the beds are full (the real run's
583 arrivals over 38 settlements in 30 days is 15 each: 5 to 20). Route hours did not matter for that; the 1-hour
collapse (a placeholder speed of 20000 units an hour against real marker distances) only made caravans and attacks
instant. Captures (a dozen per 90 days over 38 settlements) halve a population that is back at the cap within weeks.

**Routes first (`seedpack.py`).** Hours are now data-relative: in each world the median k-nearest route distance
maps to `median_route_hours` (3, placeholder), the rest scale linearly, rounded half up, never below
`min_route_hours` (1). No claim about what a marker unit measures is needed, and scaling every marker by 1000 changes
no hour (tested). On the synthetic fixture the histogram goes from {1: 359, 2: 54, 3: 4} to {1: 53, 2: 96, 3: 120,
4: 90, 5: 40, 6: 13, 7: 1, 8: 2, 9: 2}. Measured alone (column C below) it changes nothing about saturation, as the
diagnosis predicted, so the simulation rules changed too.

**Sim rules added (placeholder constants, overridable in sweeps; every random draw still comes from the (seed, hour)
RNG and none of these add a draw):**
- `FARM_SLOTS_PER_BEDS = 4`: only `beds // 4` farmers find land to work, so a place feeds about three quarters of
  its beds on its own (3 food per farmer) and fills the rest only with caravans or the player's beds
  (`manage.add_beds` adds slots too). Arrivals beyond the slots take the other roles. 0 disables. Alone it gives boom
  and bust (83 emptyings per run at scale: the old "morale 10, one leaves every tick" rule cascades a place at its
  food edge to zero), hence the next two.
- `LEAVE_ONLY_WHEN_SHORT = 1`: at morale 10 a settler leaves only on a tick that was short of food or water.
- `MORALE_DRIFT = 1`: a tick that is neither short nor in surplus adds 1 morale, so a fed place at its edge climbs
  back to the arrival threshold instead of freezing at 10 (without it: mean morale 27 at scale).
- `ARRIVAL_SLOWDOWN_POP = 3`: a settler may arrive only every `1 + population // 3` days, days counted from hour 0 so
  a resumed save judges the same. A place fills fast while small and slowly when nearly full, and the larder gets
  time to build the surplus caravans carry (caravans finished per run at scale: 509 without it, 1391 with it).
- `SETTLEMENT_TARGET_WEIGHT = 1`: a hostile or empty settlement counts this many times when a faction picks a
  target. Left at 1 (unchanged behaviour); measured at 3 it raises settlement captures from 19 to 39 per 90 days and
  cuts enemy takes, a knob for the lead, not a change made here.

Variants rejected, same sweep: the slowdown alone (2, 3 or 4) only delays the saturation (cap share 0.64 to 0.90,
median population still 20, morale 98); farm slots per 5 beds (with the leave and drift rules, no slowdown) leaves
the median population at 9 of 20; the full set with slowdown 2 or 4 gives mean morale 55 or 62 against 81 with 3.

| Metric (5 seeds, synthetic Commonwealth fixture) | A: 1 h routes, old sim, 30 d | B: same, 90 d | C: median-3 h routes, old sim, 90 d | D: median-3 h routes, new sim, 90 d |
|---|---|---|---|---|
| settlements_at_cap_share | 0.91 | 0.97 | 0.98 | 0.14 |
| mean_population_share (of beds) | 0.97 | 0.99 | 0.99 | 0.75 |
| population quartiles at day 90 (min, p25, median, p75, max) | - | 14.6, 20, 20, 20, 20 | 14.6, 20, 20, 20, 20 | 6, 13, 13.6, 17.8, 20 |
| mean_morale | 98.7 | 98.9 | 99.5 | 80.8 |
| settlement_captures_per_30_days | 8.0 | 4.6 | 4.1 | 6.5 |
| enemy_takes_per_30_days / enemy_losses_per_30_days | 75 / 21 | 58 / 27 | 57 / 28 | 59 / 28 |
| changes_per_30_days_per_place | 0.34 | 0.26 | 0.26 | 0.27 |
| attacks_per_day_per_faction | 0.56 | 0.56 | 0.56 | 0.55 |
| caravans_raided_share | 0.42 | 0.38 | 0.40 | 0.35 |
| empty_settlements, settlements_emptied | 0, 0 | 0, 0 | 0, 0 | 0, 0 |
| story_lock_violations, home_violations | 0, 0 | 0, 0 | 0, 0 | 0, 0 |
| `check(agg, SCALE_BOUNDS)` | - | - | 3 broken (cap share, population share, morale) | clean |

Column A is the offline stand-in for the real 30-day run (`median_route_hours` 1 emulates the collapse; the real run's
36 of 38 at the cap reads as 0.95 here against 0.91). In D every enemy faction both takes and loses ground over the
sweep (per-faction `places_taken_by` and `places_lost_by` are in the metrics now), settlements are captured about
every five days somewhere, and the settlements spread from 6 to 20 people instead of all sitting at 20.

New in `balance.py` for this: scale-free metrics (`changes_per_30_days_per_place`, `attacks_per_day_per_faction`,
`settlement_captures[_per_30_days]`, `enemy_takes_per_30_days`, `enemy_losses_per_30_days`, where "enemy" is every
faction but the one holding the most settlements at the end, `settlements_at_cap_share`, `mean_population_share`,
`places_taken_by`, `places_lost_by`), the aggregate averaging any per-faction table, and `SCALE_BOUNDS`, a placeholder
envelope around column D that the test `CommonwealthScaleSweepTests` holds the synthetic fixture inside (and shows
the old rules breaking). `DEFAULT_BOUNDS` stays the fixtures' envelope; the `balance` command still checks only that.

Open for the lead: the equilibrium is uniform where the data is uniform (every generated settlement has 20 beds and
the same start, so most settle near 13 to 15 people); real variation needs per-settlement beds or stats, which the
draft has no data for. The model has no "runs no caravans" flag, so a settlement a wild faction takes trades like
any other. `caravans_raided_share` 0.35 at scale is high for a world with no player.

### Real pack, all DLC (owner's PC, 2026-10-28)

The rerun card below, run by the Install thread at main `de91d6d0` into `D:\Modding\research\combined_seed3` (the
21 Oct folders untouched). The Fallout 4 data is the owner's **Steam install, the newer build**, not 1.10.163: the
1.10.163 depot copy has no `DLCCoast`, `DLCworkshop02`, `DLCworkshop03` or `DLCNukaWorld`. First 16 hex of each sha256:
`Fallout4.esm` a3fa1e66d75f80f3, `DLCRobot` 465b904603caf18c, `DLCworkshop01` 9e645faa8620b5e2, `DLCCoast`
b8817779595f3576, `DLCworkshop02` 9e907c7429da3d7c, `DLCworkshop03` 08ece321cc224a48, `DLCNukaWorld` 8adb27458d10b1f0.

- `seed`: 7 plugins, 487 locations, 46 settlement and 87 base candidates, 233 markers found and none missing, 58
  regions, no problems or unresolved references.
- `seed-pack`: 243 of 487 places kept (244 dropped for no marker position), 42 settlements, 111 bases, 90
  landmarks, 455 routes, 9 isolated places, 7 factions holding places (settlers 42, raiders 29, ghouls 21,
  supermutants 18, creatures 17, gunners 12, robots 8), 96 unheld, 20 story-locked, no validation problems.
  Worlds: fallout4 226, dlccoast 5, dlcnukaworld 2.
- `simulate --seed 1 --days 30`: 36 of the 42 settlements end at stage 3 with population 14, below their 20 beds.
- `balance --seeds 10 --days 30`, judged on the command's default bounds (the 11-place fixtures' `DEFAULT_BOUNDS`):
  exit 1, with `attacks_per_day` 3.91 above 3.0 and `changes_per_30_days` 80.1 above 30. Aggregate:
  `settlements_at_cap_share` 0.0, `mean_population_share` 0.644, `mean_morale` 99.0, `settlement_captures` 10.4,
  `enemy_takes` 77.0, `caravans_raided_share` 0.227, no empty settlements, no story-lock violations.

Reading. The saturation fix holds on real data. On 21 Oct, 36 of 38 settlements sat at the 20-bed cap. Now none
do: they stop at the food edge the farm-slot rule sets (`beds // 4` farmers, so 15 food a tick for 20 beds).

The two broken lines come from the wrong yardstick. `DEFAULT_BOUNDS` holds absolute counts for 11 places. A
Commonwealth pack is judged by `SCALE_BOUNDS`, now `balance --bounds scale`. On that yardstick, churn is 80.1 / 243
= 0.33 per place per 30 days (bound 0.02 to 0.6; the synthetic baseline's column D: 0.27). Attacks are 3.91 / 7 =
0.56 per faction per day (bound 0.1 to 2.0; column D: 0.55).

At 30 days the one miss on the scale bounds is `mean_morale` 99 (bound 40 to 95). At 90 days, which is column D's
length, that is gone. The run was `balance --seeds 5 --days 90` on the same pack (Install thread, main `de91d6d0`,
saved as `balance_5x90.json` beside the pack). It passes `check(agg, SCALE_BOUNDS)` with nothing broken. Column D
(synthetic) is beside it:

| Metric | Real pack, 5 seeds x 90 days | Column D |
|---|---|---|
| settlements_at_cap_share | 0.11 | 0.14 |
| mean_population_share | 0.73 | 0.75 |
| mean_morale | 76.3 | 80.8 |
| settlement_captures_per_30_days | 5.13 | 6.5 |
| enemy_takes / enemy_losses per 30 days | 56.7 / 30.0 | 59 / 28 |
| changes_per_30_days_per_place | 0.25 | 0.27 |
| attacks_per_day_per_faction | 0.56 | 0.55 |
| caravans_raided_share | 0.16 | 0.35 |
| empty_settlements, empty_share | 0, 0.0 | 0, - |
| story_lock_violations, home_violations | 0, 0 | 0, 0 |

Every faction both takes and loses ground. Places taken / lost per 90 days:
- creatures 25.2 / 29.6
- ghouls 30 / 11.2
- gunners 33.2 / 4.4
- raiders 29.2 / 13.4
- robots 22.6 / 23.4
- settlers 11.4 / 22.4
- supermutants 30 / 8

`frozen_region_count` is 10.8 of 58 regions. No rule changes follow from this run. Still open:
- the plateau is uniform because the data is (per-settlement beds would vary it);
- settlers lose about twice what they take;
- about 11 regions see no change of holder in 90 days.

These are tuning questions for the lead, not failures.

## From draft to a pack that runs (`seedpack.py`)

The first real `seed` run (owner's PC, 2026-10-21, `Fallout4.esm` + `DLCRobot.esm` + `DLCworkshop01.esm`; the other
four DLC were not installed) read 397 locations, 38 settlement candidates, 84 base candidates and 710 factions. Its
keyword counts included `LocTypeWorkshop` 30, `LocTypeWorkshopSettlement` 30, `LocTypeSettlement` 24,
`LocEncRaiders` 39, `LocEncSuperMutants` 24, `LocEncGhouls` 27, and the ref type `WorkshopRefType` 31. That supports
the regex guesses in `seed.CLASSIFY` (a supported hypothesis, not proof). A draft still could not run: holders were
null, faction homes empty, no routes.

Two additions close that gap, both offline and stdlib only:

- `seed.py` now also reads **map-marker positions**. LCTN `MNAM` names the location's world map marker REFR; a
  second pass enters only the WRLD trees and decodes only the REFR records some MNAM names (the rest cost one header
  read each), taking x, y from REFR `DATA` (position then rotation floats, xEdit) and the worldspace from the
  enclosing World Children group (type 1, labelled with the WRLD form id). Each draft place gets
  `marker: {x, y, world}` or null; the report counts `markers_found` and `markers_missing`; malformed data goes to
  `problems`, never a crash.
- `seedpack.py`: `generate(draft, rules=DEFAULT_RULES) -> (pack, report)`. Deterministic (the same draft gives
  byte-identical JSON), and the output passes `pack.validate_pack`, loads, and runs under `sim.run` with the balance
  invariants kept. **Every rule is a placeholder** in `DEFAULT_RULES`, labelled in code, except where the first run
  supports it:
  - keep a place if it is a settlement candidate or has a marker position; drop the rest (quest and virtual
    locations, unplaced parents) and count each drop reason;
  - story locks (CC-21: a story place is locked to its story holder until the story passes it): `story_lock` maps
    a placeholder story id to a regex searched on place ids; a matching place gets `story_lock` set, kind landmark,
    no holder and no settlement stats, so no pack faction claims it and it never changes hands. The placeholder
    patterns are `^Prydwen`, `^Vault111`, `^Institute`, `^DiamondCity`, `^Goodneighbor`: the first two ids are ones
    the first run's report listed (`PrydwenLocation`, which the settlement regex had turned into a settlers
    settlement that the 30-day run then held as settlers, and `Goodneighbor`), the other three the lead named.
    `Vault81` and `TheCastle` were left unlocked: nothing in the run's report needs them, and a lock also removes a
    place from growth and jobs and shields its neighbours under story mode. Unheld rather than a placeholder
    faction because the story holder is the owner's call (CC-20) and the pack's factions are only those holding
    sandbox ground. The report's `story_locked` lists which ids matched, so an over-wide pattern is visible;
  - holders: a place with a `LocEnc<X>` keyword is held by the pack faction `enc_factions` maps `<X>` to
    (`Raiders`, `SuperMutants`, `Ghouls` from the first run's keyword counts, `Gunners` from its seed-pack report);
    the creature keywords that report listed as unmapped (`Bugs`, `Deathclaw`, `Mirelurks`, `Molerats`, `Wildlife`,
    17 places) share one placeholder `creatures` faction and `Robots` (8) a placeholder `robots` faction, both
    "wild": hostile to every faction at -80 both ways, aggression 50 and 40. A place with keywords for several mapped
    factions goes to the first in `enc_priority` (the organised enemies before the wild ones). Deliberately still
    unmapped and reported: `BoS` (2) and `CoA` (2), player factions whose holder is the owner's design decision
    (CC-20), and `Synths` (5), the same kind of decision. Settlement candidates start held by `settlers`; the rest are
    unheld. The model has no "runs no caravans" flag, so a settlement a wild faction takes trades like any other;
  - factions are the pack's own small set (`settlers` plus each mapped faction that holds a place), not the 710 FACT
    records. FACT relation data is carried only where a FACT editor id matches a `fact_patterns` regex (unverified
    guesses); otherwise the placeholder applies (enemy of settlers at -80, enemies neutral to one another, wild
    factions hostile to all);
  - each faction's home is its held place with the most neighbours held by the same faction, ties to the smaller
    id; strength is `8 + 2 * places held`, capped by the model; aggression 20 for settlers, 70 for enemies;
  - routes: per worldspace, each place with a marker joins its 3 nearest by marker distance, undirected and
    deduplicated; hours are data-relative: the world's median route distance maps to `median_route_hours` (3), the
    rest scale linearly, rounded half up, never below `min_route_hours` (1). The unit is the marker's own and no
    claim about what it measures is needed (the first run's absolute 20000 units an hour put 441 of 446 routes at 1
    hour). The report's `route_scale` gives, per world, the distance quantiles, the derived units per hour and the
    hour histogram; `route_hours` is the histogram over all routes. A kept place without a marker joins its parent
    location's place at the minimum when that is kept; isolated places are listed;
  - settlements get the fixtures' `farm_a` starting stats (population 5, 3 farmers, 1 guard, 1 trader, food and
    water 20, ammo 10, 20 beds, morale 50); defence 2 for settlements, 4 for bases.

  `python -m fo4sf.combined seed-pack DRAFT.json OUT_DIR` writes `commonwealth.pack.json` and
  `seedpack_report.json` (drop reasons, holders per faction, homes, story-locked ids, route count, hour histogram
  and per-world route scale, isolated places, unmapped keywords, FACT ids matched, validation problems, the rules
  used) and prints one line.

### PC rerun card (read-only on game files)

Outputs under `D:\Modding\research\combined_seed`; nothing is written into the game folder and nothing is committed.

```powershell
cd <repo>
$env:PYTHONPATH = 'src'
python -m fo4sf.combined seed D:\Modding\research\combined_seed "<Fallout 4>\Data\Fallout4.esm" "<Fallout 4>\Data\DLCRobot.esm" "<Fallout 4>\Data\DLCworkshop01.esm"
python -m fo4sf.combined seed-pack D:\Modding\research\combined_seed\commonwealth_seed.draft.json D:\Modding\research\combined_seed
python -m fo4sf.combined simulate --pack D:\Modding\research\combined_seed\commonwealth.pack.json --seed 1 --days 30
```

Add the other DLC `.esm` files to the first line when they are installed (the 28 Oct run read all seven: see "Real
pack, all DLC"; each run gets a new output folder). Judge a sweep of the real pack on the scale bounds:
`python -m fo4sf.combined balance --seeds 5 --days 90 --pack <out>\commonwealth.pack.json --bounds scale`. What to
send back: `seed_report.json` (now with `markers_found` and `markers_missing`), `seedpack_report.json`, the one-line
`seed-pack` summary, the `simulate` summary and the `balance` output; the drafts and packs themselves stay on the PC.

## Next after the current phase (owner, 2026-10-22)

The owner set the order for after the current phase: "We will probably wait to use Starfield world generation for
later, because there are a few pretty complex systems we need to get working: our own A-Life sim style system, a
system that allows going between these areas without direct walking paths, and building the overall game system of
our GAMMA." New items continue the design's numbering (CC-60 to CC-62 are in the framework file, PR #408). No code yet.

- **CC-63. Our own A-Life style simulation.** The persistent world sim prototyped here (L2 `sim.py`, L3 `present.py`)
  grows into the full system: factions, squads, caravans and settlements living off-screen and becoming real actors
  near the player. Open: where its state lives in the save (probes P1 to P3, CC-02; save identity, card P1b); the tick
  in game (one tick per 6 game hours, card P1b; P5 measures only its latency); how far out actors are real (the design's L2/L3 split); how
  many squads a cell can carry, which no probe measures yet (P4
  only spawns and removes three actors, judging spawn reliability and save growth; a load-scaling probe is needed).
  **How far out actors are real, measured (P9 and P9u, 2 Nov 2026, #644; judges in #663 and #669).** One citizen on
  the converted Commonwealth was sent by its linked ref alone (`SetLinkedRef` and `EvaluatePackage`; Starfield's
  `DefaultMaster_PatrolPackage` then walks it; no alias package, no `PathToReference`). Distances below are from the
  player's start to the spawn point (the session logs 643.1, 710 and 898.5 m; the judges print the distance to the
  marker at the go: 652, 712 and 898 m). One run per distance.

  - Loaded (on the measured route the loaded area reached about 470 m from the player: the 643 m run's actor
    read loaded again from 473 m): it walks the converted navmesh across cells at about 1.2 m/s and arrives (P9 PASS
    twice: 439 m, 7 cells, 440 s and 443 s). Near the player it may stand still: in the P9 loaded runs that logged
    the player's distance, stops of 40-92 s came with the player 18-30 m away and none with the player 83 m off;
    earlier runs, with the follow helper set 25 m behind, had stops of up to 220 s. The package never changed during
    the logged stops, so their cause is not logged, and a cause at the destination is not excluded (three of the four
    longest stops were 27-31 m from the marker). The owner's call: stops near the player are acceptable, and P9's
    stuck rule ignores stops within 35 m.
  - Unloaded, out to somewhere between 643 m and 710 m: the engine still walks it at about 1 m/s (`cell` reads none
    while unloaded, as in every unloaded sample) and hands it back cleanly at the loaded edge (P9u PASS from 643 m).
  - Farther out the engine's handling turns abstract. From 710 m the actor walked 151 m unloaded as before, then, when
    it was loaded again, it was placed 41 m from the player in one step of about 420 m. From 899 m its position jumped
    to a point 6.5 km from the player, outside the world, and stayed there.

  So the L2/L3 split is set by measurement, not by the engine's unloaded handling: L2 owns a travelling actor's
  position while it is outside the loaded area; L3 materializes the real actor only inside it (a conservative 400 m)
  at the simulated position and hands over with the linked-ref walk. Cost: with one walking actor the game
  averaged 5-7% of the machine's CPU per phase (peaks 13-15% while loading, under 10% while walking) and stayed under
  8.6 GB in every run (no run without an actor was measured as a baseline); how many actors a cell carries is still
  the open load-scaling probe.

  **Far-travel layer (design, 6 Nov 2026; `travel.py`).** An atlas gives each place a position in metres in the
  converted world; it is recorded when a world is converted, not stored in the pack, because L1 has no coordinates.
  A travelling squad's simulated position is the straight line between its two anchors at its route progress, from
  the same elapsed formula `present._squad_place` uses (departure is eta minus the shortest route hours). The real
  actor materializes within 400 m of the player (inside the about 470 m loaded edge measured above) and dissolves
  only beyond 500 m; the gap stops it flickering at the edge, and 500 m stays under the 643 m out to which the engine
  still walked it unloaded, so a dissolving actor is never left in the abstract band. Hand-back: on a dissolve, L2
  would take its progress from the real actor's position projected onto the straight line between the two anchors
  (an approximation: a multi-hop route and the navmesh path are not that line) and recompute the eta. The
  module changes neither WorldState nor the tick, sits outside the C++ parity path and becomes a later port step. The
  in-game check is a proposed probe P11 (card to follow): create the actor at the simulated position inside 400 m,
  hand over with the P9 Link driver, dissolve it beyond 500 m and re-materialize it from L2 with continuity.
- **CC-64. Travel between areas without walking paths.** The converted worlds (L0) will be separate worldspaces or
  interiors, not one continuous map, so the core needs a travel layer between them: the player moves area to area,
  and the sim moves squads, caravans and news along the same links. Open: how the player travels (map, vertibird or
  ship (CC-61), a scripted transition (NG-9), doors); how much time passes and what can happen on the way; how
  off-screen movement between worldspaces is shown. P9 does not answer this: it drives one actor by its linked ref
  across one converted exterior (actor pathing within one worldspace; CC-63 has the measured numbers).
  Building note (owner): a large place may be better built as an interior than as an exterior; check how Starfield
  and its mods build their big city spaces (the owner named Cydonia and the city people compare to Cyberpunk) before
  choosing, place by place.
- **CC-65. The overall GAMMA-style game system.** Tie the pillars (settlements, factions, connected wasteland,
  survival, stories) into one way to play: start options, difficulty and mode presets (`modes.py`), progression and
  what the player works toward. Open: what a run's goal is, and which systems are on by default.
- **CC-62 deferred.** Starfield world generation stays later, after CC-63 to CC-65 work.

## Lifecycle fixture (3 Nov 2026)

`tests/test_combined_lifecycle.py` follows one resupply job from its offer to its one outcome through every way it
can go wrong, and checks three cross-module properties. The cases are the rules the reference mods describe
(the review on #32: SSaW's encounter tokens and load recovery, StarSim's reservation and elapsed-time catch-up),
written against what `jobs.py`, `present.py` and `sim.py` do today:

- one outcome per job: a hand-in pays once; a replay, a cancel after a hand-in or a hand-in after a cancel is
  refused and leaves no trace; a late hand-in is refused without a trace;
- stale ownership: a holder change under an open job refuses the hand-in while it lasts, and the giver getting the
  place back makes the same need work again;
- the save is the acknowledgement: a save made after the hand-in refuses it again; a save made before it is a world
  where the job is still open, where the hand-in happens exactly once and ends in the same world;
- catch-up: 48 hours as one call, two or eight give one world and one offer list;
- reservation: a caravan's cargo leaves its source's stock at dispatch, so no second job can carry it, and one
  caravan per source is out at a time;
- materialize once: a plan names each group once by the L2 entity's own id, replanning the same world spawns and
  dissolves nothing, and every slot names a place, faction and squad the world still has.

**Built from the fixture (4 Nov 2026): the superseded offer instance.** A repeating job read twice (same id,
different offered hours), one instance handed in, the need back by a different amount, used to accept the other
instance and pay by its own, stale, amount. `Offer` now carries `read_at`, the event log's length when the
instance was read, and another instance's outcome for its id logged at or after that position refuses it
(superseded; SSaW ignores a result whose token is not the live one). Its own outcome, any outcome carrying its
offered hour, refuses it at any position as before (#431): that holds an instance read after a save against the
world reloaded from that save, where its own hand-in lands below `read_at` (review of 084f68cc), and it keeps the
once-per-hour cap on a repeating id, the only limit on handing in, taking the goods back and handing in again;
that cap is a design knob this change leaves alone. Ordered by log position, as `_last_loss` orders losses and
retake ids carry `seq`, not only "the newer offered hour wins", which alone would miss the shape where the handed-in
instance is the older one. `read_at` is in `to_dict`; an offer record without it reads as 0, so any outcome for
its id counts against an instance rebuilt from such a record. A reload can also put a later instance's hand-in
below a stale instance's `read_at` (the stale one read from a longer log): an outcome carrying a later offered
hour supersedes too, since it was logged at that hour or after; and an instance whose offered hour the world has
not reached is refused outright by `valid()` and `fail()`, the game having gone back to a save from before it
was read (delta review of bda0d0e3). The case is in the fixture as a passing test in both shapes, with its
preconditions in a test of their own, beside the reloaded-save (three shapes), same-hour and inclusive-position
cases.

**Contracts the modules do not have yet** (found by the fixture; recorded, not built):

- Acceptance: nothing in the world state says the player is on a job (SSaW keeps one accepted operation at a
  time). Offers are read on demand and only outcomes are logged.
- Engine acknowledgement: a slot has no applied/failed channel back from the adapter (StarSim's package-to-task
  handshake); the planner's diff is the whole contract.
- A live encounter at save time: L2 has no mid-encounter state, so there is nothing to recover on load (SSaW
  cleans up a battle or patrol that a save left live). This becomes real once L3 stages fights.
- Single-fire staging: `present.plan` lists everything in radius within the budget; there is no ordered chain that
  stages at most one encounter on arrival with exclusions (indoors, in a scene, a live fight).

One thing the modules have that SSaW does not: place-based protection of story places (`Place.story_lock`,
`sim._story_shielded`), which the review found SSaW approximates by the player's own state.

## Not implemented (and not claimed)

No game runtime, no Papyrus or SFSE plugin outside the probe kit (docs/spikes/combined-core-probes.md, not run yet), no plugin records written (the adapter is a plan), nothing installed or
deployed, no UI, no spawning, no voice, no quest records behind the job offers, no player-needs model behind the
survival presets, no reputation globals per region, only one tuning pass (empty settlements, see "Balance baseline"; the other constants are
still the first prototype's placeholders). Whether keyword data survives a save (P2) and the sidecar's behaviour under SFSE (P1) are untested on the PC.
The fixtures use placeholder names (`farm_a`, `raiders`); they are not game facts.

## Run it

```
python3 -m unittest discover -s tests -p 'test_combined*'
python3 scripts/guard.py
python3 -m fo4sf.combined demo --seed 3 --days 30
python3 -m fo4sf.combined simulate --pack r1.json --pack r2.json --seed 5 --days 20 --out state.json
python3 -m fo4sf.combined simulate --resume state.json --days 10
python3 -m fo4sf.combined seed OUT_DIR Fallout4.esm DLCRobot.esm ...   # read-only; writes two JSON files
python3 -m fo4sf.combined seed-pack OUT_DIR/commonwealth_seed.draft.json OUT_DIR   # a pack that runs, by placeholder rules
python3 -m fo4sf.combined balance --seeds 20 --days 90                    # fixtures; exit 1 when a bound breaks
python3 -m fo4sf.combined balance --seeds 20 --days 90 --pack r1.json --set sim.UPKEEP_PER_PLACE=2
python3 -m fo4sf.combined news --resume state.json --place market         # the terminal page at a place
python3 -m fo4sf.combined present --resume state.json --place market      # present.plan(...) as JSON
```

`balance` prints aggregate metrics, overrides and broken bounds as JSON; `--set NAME=VALUE` takes a bare `sim`
constant or `sim.NAME`, with the value as JSON (a value that is not JSON is an error, not a string). `news` and
`present` also take repeatable `--pack`.

Run the module with `src/` on `PYTHONPATH` (the tests insert it themselves). `seed` writes
`commonwealth_seed.draft.json` (places and factions with their evidence) and `seed_report.json` (counts of every
keyword and ref type locations use, overrides, deleted records, compressed records, markers found and missing, odd
input). `seed.to_pack()` strips a draft to the pack shape for a human to fill holders and faction homes;
`seed-pack` fills them by the placeholder rules above and writes `commonwealth.pack.json` and `seedpack_report.json`.

## Waiting on the PC (on the owner's word, after the v6e test)

- Done once (2026-10-21, three plugins): the seed reader's read-only run; its counts support `seed.CLASSIFY`. Next:
  the rerun card above with markers, then `seed-pack`, so the draft becomes the first Commonwealth pack.
- Probes P1 to P10 from the design (one at a time, read-only or staged): P1 SFSE sidecar on save and load, P2 keyword
  data persistence, P3 location data on our interiors, P4 squad spawn and dissolve over 20 cycles, P5 Papyrus tick
  over 50 places, P6 leveled list conditioned on location keyword data, P7 vendor refusal by reputation tier,
  P8 enable-parent stage swap at a converted settlement, P9 a caravan on a travel package across 4 exterior cells,
  P10 SendStoryEvent starting our quest. P1 to P3 decide where the world state lives (CC-02).
