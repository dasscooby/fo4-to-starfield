# The front page's status, 3 November 2026

This is the section "Where it stands (3 November 2026)" as it stood on the repository's front page. The front page
replaced it on 10 November 2026; it is kept here word for word, with links repointed from this folder and nothing else changed.

## Where it stands (3 November 2026)

**Phase 0, the Commonwealth test slice, is done by the owner's word (24 October).** Its exit gates were ticked in
game: the mission's pull request merged after review; the automated door rounds passed (29 of 30 round-trip legs, 0
failures; the one non-pass was the border popup); with the border switch on, the Vault 95 exit landed and the owner
walked west and south of Red Rocket with no wall; and the owner's own hand checks of the mission, the map markers and
the doors were done. Since then the work has moved to the combined core (below)
and to the next phase of the single-game conversion. Every row here says whether it was seen in the game or only in
offline tests; dates are UTC.

| Area | State | Seen |
|---|---|---|
| **Commonwealth exterior** | the 64 × 64 cell core as native terrain with 648,358 placed objects; the owner walked from Red Rocket to the Diamond City gate with no crash and no boundary | in game, 17 Oct |
| **No walls** | an SFSE plugin (`FO4SFBorder`) switches Starfield's landing border off inside our world only; with it on the owner walked west and south of Red Rocket and hit no wall, and the first-load flicker that left the border on is fixed | in game, 24 Oct |
| **Interiors** | 16 interiors reached in game so far (Vault 111, Vault 81, the Red Rocket cave, Vault 114, the Prydwen, Hotel Rexford, the Boston Public Library, Parsons and more), with working stairs, hinged and sliding doors and posed props; 253 more (the 251 planned base-game interiors and Automatron's 2; 4 odd hook cells are left out) are built in batches and held for install | in game (16), offline (253 more) |
| **Load doors with animation** | load doors that open before the trip (`FO4SF_AnimatedLoadDoor`); the port carrying them is installed and its automated door rounds are queued | installed 28 Oct, rounds pending |
| **First mission** | a cut-down "When Freedom Calls" ran to completion: stages 20, 30 (5 of 5 raiders), 40, 200 and complete; this historical test does not establish full quest coverage | in game, 19 Oct |
| **Codsworth** | a robot stand-in at his Sanctuary spot, rendering with plain shader blocks (the fix that solved the Red Rocket crash); 20 of his voice lines converted from the owner's files; his spawn on an existing save is on the defect list | in game, 22 to 23 Oct |
| **Map markers** | one reload after marker placement and a dark hold through that reload are merged; the owner reported the 31 Oct test worked, with a remaining issue left for the Pip-Boy whose exact scope was not stated | in game, 31 Oct; [record](../terrain/map-markers.md) |
| **New game** | run 4, newgame_v12, reached the surface at stage 200; MQ101 was not running when checked and the owner reported it worked. Launcher start choices and the pre-war vault remain later work | in game, 31 Oct; [record](../newgame/vault111-start.md#13b-in-game-run-4-31-oct-2026-newgame_v12-pass-to-stage-200-our-own-start) |
| **Launcher** | checkout updating, recorded restore and a separate FO4SF game folder are on main. The follow-up that retains crash evidence when settings restoration fails is still under review in [#668](https://github.com/fo4sf/fo4-to-starfield/pull/668); source-version support remains tied to the checked source/runtime tables | merged machinery; follow-up reviewed offline |
| **Combined core, offline** | the 28 Oct Commonwealth seed contains 243 places, 42 settlements and 7 factions from 487 locations and all six DLC. The C++ port through C5 is written and has selected Windows byte-parity checks; [#649](https://github.com/fo4sf/fo4-to-starfield/pull/649), [#651–#654](https://github.com/fo4sf/fo4-to-starfield/pull/654) and the Windows build [#656](https://github.com/fo4sf/fo4-to-starfield/pull/656) remain in review | offline; not a game runtime |
| **Combined core, in game** | P2, P3's keyword half, P4, P6, P7, P8 and P10 passed their scoped probes, and P5 recorded timings. P3's cell half and a complete P1 sidecar verdict remain open | in game, 28 Oct; [probe record](../spikes/combined-core-probes.md) |
| **NPC travel** | Claude reports two loaded walks of 439 m across 7 cells, and an unloaded approach from a 643 m spawn that arrived after 796 s. Longer starts showed a jump or parking; these are route observations, not universal engine distances. Judge corrections remain open in [#663](https://github.com/fo4sf/fo4-to-starfield/pull/663#pullrequestreview-5733485009) and [#669](https://github.com/fo4sf/fo4-to-starfield/pull/669#pullrequestreview-5746648639) | reported in game, 2 Nov; [runs and corrections](https://github.com/fo4sf/fo4-to-starfield/issues/644) |
| **Own Fallout world** | the first planet probe loaded a planet from project records; persistent-reference placement and biome/location checks still need the next test. Reversible stripping and cross-game staging plans are drafts [#665](https://github.com/fo4sf/fo4-to-starfield/pull/665) and [#667](https://github.com/fo4sf/fo4-to-starfield/pull/667) | partial native probe; further staging pending |
| **Tests and CI** | fixture tests and the asset guard run in CI. Check each PR's exact head and review; selected offline or hosted passes do not establish a passing full Windows suite or native gameplay | [pull requests](https://github.com/fo4sf/fo4-to-starfield/pulls) |

Current work covers review of the C++ port, the engine gates before a 20-place living-world slice, the separate
Fallout world and launcher recovery. More start choices, Pip-Boy/map work and verified source-version support remain
on the roadmap. The full ledger, with evidence for every row, is [docs/ROADMAP.md](../ROADMAP.md); the day-by-day
record is [docs/JOURNAL.md](../JOURNAL.md); the owner's own findings are
[docs/owner/playtest-issues.md](../owner/playtest-issues.md). The front page's earlier progress tables are kept in
[docs/history/readme-progress-2026-10.md](readme-progress-2026-10.md).
