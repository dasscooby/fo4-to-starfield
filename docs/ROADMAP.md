# Roadmap: from the Commonwealth test slice to a Fallout core on Creation Engine 2

The owner set this direction on 17 October 2026. It extends [docs/PLAN.md](PLAN.md) (phases P0 to P6) with what
comes after the current testing, and it is the brief Codex and Grok work from. Status words: **done**, **in testing**,
**next**, **later**. Dates are Mountain time. Evidence lives in [docs/JOURNAL.md](JOURNAL.md),
[docs/owner/playtest-issues.md](owner/playtest-issues.md) and [issue #32](https://github.com/fo4sf/fo4-to-starfield/issues/32).
Two independent reviews of this document (17 Oct) are folded in; their corrections are the reason several claims
below are narrower than the first draft.

## Update, 1 November 2026: since phase 0 closed (24 October)

Only an in-game PASS on the installed build counts as in game; everything else says offline, in review or next.

- **Living world (combined core).** The 28 Oct calls are in [decisions.md](ai/decisions.md): the whole Commonwealth
  runs offline in the Python reference model, a 20-place slice goes in game first, and in game the simulation is a
  C++ port inside our SFSE plugin with the same results as the Python model. Probes on the PC (28 Oct,
  [results](spikes/combined-core-probes.md)): P2, P3's keyword half, P4 to P8 (P7 minimal, its vendor half
  deferred) and P10 **done** (PASS); P3's cell half and P9 (one actor walking 450 m) INCONCLUSIVE; no P1 verdict yet
  (the SFSE sidecar). The C++ port, steps 1 to C5 (#649, #651 to #654, held to byte-identical output after every
  tick), and its Windows build (#656, byte parity at C5) are **in review**.
- **New game.** Our own start (the new game's quest is Starfield's startup quest) passed run 4 on 31 Oct: newgame_v12
  booted and ran from Vault 111 to the surface (stage 200); MQ101 was not running when checked, and the owner reported "v12 worked fine"
  ([vault111-start.md section 13b](newgame/vault111-start.md)). v11's boot crash came from a script doc comment over
  4 KB (supported hypothesis, section 13a; v12's clean boot with the comment short fits it; the 3 KB rule in
  decisions.md). **Next** (the owner's start picks, decisions.md 1 Nov): the start picked in the launcher, with two
  test starts; the pre-war vault after that, built only once the owner has seen its design.
- **Map markers.** One reload once every marker is in (#624) and a dark screen until the reload is back (#626), so the
  Commonwealth's icons are on the first map the player opens. The owner's play test on 31 Oct: "ok everything worked
  only issue left will be solved with the pipboy"; its log shows the hold ending with the reload
  ([map-markers.md](terrain/map-markers.md), Dark hold). Which issue is left for the Pip-Boy was not said.
- **Strip Starfield down** (the owner, 29 Oct: "too many things are breaking because we are forcing ourselves into the Starfield system").
  Decided (decisions.md, 29 Oct and 1 Nov): our own planet inside Sol, in Earth's orbit in the end, with no other
  planets and those hidden from the star map by our own overrides; our own start (above); the quieting switches go
  straight into the mod; the landing pad and its ship records go; a vanilla baseline New Game tells our errors from
  Starfield's ([baseline.md](testing/baseline.md)). The planet probe's run 1 (29 Oct,
  [planet-probe.md section 8](planet/planet-probe.md)) loaded our planet from our records, but our persistent test
  references stayed in the base world, our biome map was not read (supported) and the location-chain check asked one
  way only (version 2 asks both). **Next**: probe run 2, the vanilla baseline run, hiding the other planets, dropping
  the pad.
- **Launcher.** It can update its own checkout from main, opt-in (#637). **In review**: an FO4SF game folder beside the
  player's Starfield that the launcher installs into and plays from (issue #645; #647 with #657 and #660).

## Update, 22 October 2026: the current phase, what closes it, and what is left

The owner approved the next phases and their order on 19 October (the roadmap page, "yes to all"). The roadmap
page's phase 0 is **finish the current phase**: Codsworth, the mission, the map markers and the boundary, on the v6
build. Its exit, as approved: **the owner's v6 checks and the automated door rounds pass, and #353 merges after
Codex's review.** Phase 1 (the Vault 111 new game) exits when the owner starts a new game on their PC, wakes in
Vault 111 with no Starfield intro, the quest list shows none of Starfield's 144 start-game quests, and they walk out
to Sanctuary. Nothing below counts as in game unless it says so.

Installed on the owner's PC (22 Oct 03:14 UTC): v6i_plainshader on Starfield 1.16.244.0: FO4Port 9AF962D2, core
FO4TerrainCore DC751664, Mars 8BBA3EE9, Raider BED4EF1A, FO4SFMission 03C2A7A8, Bridge 63C746BB, plus FO4SFMapMarkers
(pinned to core DC751664, installed 22 Oct 11:50 UTC).

### Phase 0 ledger

| Criterion | State | Evidence |
|---|---|---|
| #353 merged after Codex review | **done** (20 Oct) | #353, #432 |
| Red Rocket crash | **in game: solved**; both Red Rocket to Sanctuary walks pass on v6i_plainshader | #460, #461; journal 22 Oct |
| Codsworth renders | **in game: yes** (plain-shader model, owner's screenshot) | Bugs thread, 22 Oct |
| Codsworth at his Sanctuary spot on the owner's existing save | **in game: not met.** He was not there until enabled by console (`prid 05000811`, then enable and moveto). Plugins.txt was rewritten 25 s after the launcher started the game, moving FO4Port after FO4SFMission, so his index changed from 06 to 05 between sessions; the writer is inferred to be the game (the launcher's code does not write it then), not traced | playtest row 27; [testing/load-order.md](testing/load-order.md) |
| Map markers on the surface map | **in game: partly checked** (22 Oct 17:40 UTC): the mover quest started 55 s into the session and moved all four markers, the icons drew (only after the owner came back to the area; the first-read delay is open) and fast travel landed on them. Not passed on that run: every icon read "COMMONWEALTH 00 (FO4 TERRAIN)" instead of its own name, and the Concord arrival put the player half in the ground (docs/terrain/map-markers.md, Overrides). The fix #483 merged 19:14 UTC and was installed on the owner's line at 19:32 UTC (mapmarkers_v6i_ovr); its in-game check (the four own names on the map, the Concord arrival above ground; the 2.5 m lift is unresolved until then) is in item 5 | playtest row 28; docs/terrain/map-markers.md (#483, merged) |
| The boundary (the Vault 95 exit) | **in game: cause proven for the Vault 95 exit; no wall on foot.** The Vault 95 exit after a coc stays inside with "Boundary reached" while Starfield's border regions are on; with `SetINI "bBorderRegionsEnabled:General" 0` typed mid-session the same exit lands 0.00 m from its marker (run _f, a43afef). The earlier report of a walking wall north of Vault 111 was a misreading and is withdrawn: the owner walked far north of Vault 111, past where Fallout 4's own border would be, without the popup (22 Oct 18:55 UTC; [terrain/border.md](terrain/border.md); playtest-issues.md row 29; journal correction 22 Oct). The border is read as a limit on how far one teleport may move the player, not a fence at a position (supported hypothesis, border.md). **Owner's decision (22 Oct): B, a fix for our world only, not the global INI.** BorderProbe (#485: three one-field test plugins, nosmall, hnam5, city), one Vault 95 OUT leg each on the PC with the border on: the 18:13 UTC pass ran none of the three (NOT RUN: the owner was active at the PC); the rerun with the idle wait: **city (SmallWorld cleared, HNAM 5) PASSED (0.00 m off in xy, 0.02 m in z; the Red Rocket spawn leg passed too); hnam5 (HNAM 5 only, SmallWorld kept) FAILED STAYED; nosmall (SmallWorld cleared only) PASSED** (city and hnam5 on border.md's results list; nosmall by Install's report through the coordinator at 20:46 UTC). **Not yet proven:** FO4SFMapMarkers.esm was installed in those runs, carries a copy of the core's WRLD (SmallWorld, HNAM 0) and loaded after the probe, so by record order the live WRLD was the control's, and moves of 3 or more cells fail about 11 times in 28 without any border change, so one pass against one fail may be chance. The settling test (border.md, queues `doors_v95_settle_*`; the owner's line 20:53 UTC, done 22:26 UTC): the markers plugin carried each variant's fields as the last WRLD override, no probe plugin, the same save, 3 runs each: **control PASS, PASS, PASS; nosmall PASS, PASS, FAIL; city FAIL, PASS, PASS** (7 of 9; every PASS at the same spot, every FAIL "STAYED" with the popup). **What it shows: city and nosmall are not reliable fixes, and the unchanged world passes too, so the failure is intermittent.** What it does not show: whether the fields change the rate (3 runs cannot tell), or what causes the intermittent failure; the popup still points at the border mechanism. **The border fields are shelved** (`make_core64c.py stage --world-border` stays in the code, `template` the default, no core built with it): **no core rebuild, no v6j; the installed v6i (core DC751664) is the phase 0 build.** Then, on the PC (Interiors, with Install; both ran 23 Oct, results below): the failure rate, 10 Vault 95 exits on the installed build with the FO4SF_LoadDoor trace (card 2; the owner's line "Run the vault 95 test", 23:37 UTC, and after their 23:39 UTC line not to wait 15 minutes per run Install cut the idle wait to 1 minute; queued behind the door rounds), then the same 10 with the door's retry of a missed trip (#499, merged 23:52 UTC, main 9f08155: after the MoveTo the script checks that the player left the cell; if not, it waits 0.5 s, checks again and repeats the MoveTo once if they still have not, tracing `retry 1 of 1`, `phase=after_retry` and `retry gave up`; compiled on the PC at 9f08155, 4,617 bytes, into bridge_t5, a copy of bridge_t4 with only that PEX replaced; the owner authorized the swap to t5 for those runs at 00:00 UTC 23 Oct, t4 goes back after). **Results (23 Oct; border.md "Rate and retry runs", #512, merged 14:02 UTC 23 Oct): card 2 on bridge_t4, 7 of 10 landed (fails r01, r02, r10); card 3 on bridge_t5, 6 of 10 landed (fails r01, r04, r08, r10), and no run traced the retry.** In all 7 fails the BOUNDARY REACHED popup came up during the exit and paused the game: the bridge feed went stale (its newest line 76 to 78 s old) and the judge fell back to the last read before the door, inside cell 06007D12, and called it STAYED, so STAYED in these runs means the popup came up, not a measured bounce back inside. The script's trace was the same in every PASS and FAIL: the MoveTo lands in the exterior at the marker's unmerged position, then a SetPosition goes to the merged spot (the 1,200 / 2,700 gap is the overlay offset), so no check right after the move can tell a failing trip from a passing one, which is why the retry never fired. Which step raises the popup, the MoveTo's 2.9 km landing or the SetPosition jump back, is open. 13 of 20 over both runs; the owner's call on the rate is gate 2 of the exit checklist. Next on the PC: #512's door change (the destination marker moved to the merged spot before the MoveTo, and a settle step whose trace shows which step raised the popup; not yet compiled or run, 10 Vault 95 runs); if it does not help, an SFSE plugin that toggles `bBorderRegionsEnabled` only inside our world (border.md; FO4SFBorder, #522: card A found the setting's byte at offset -16, #539; on card B, 24 Oct, the owner walked west and south of Red Rocket with the switch on and hit no wall, every write logged; the Vault 95 door passed with the switch on too, so gate 2 is ticked; the first-load flicker is fixed by #542, merged and installed, and its check passed; phase 0 done by the owner's word, 24 Oct) | #485 (merged 19:45 UTC; adds docs/terrain/border.md, the method and results); #495 (merged; the shelved core flag); #499 (merged; border.md Results, scripted-doors.md "Retry on a missed trip"); #512 (merged; the rate and retry runs, the door change); #444 |
| Automated door rounds | **passed on v6i; gate 1 ticked 24 Oct.** Card J4 (23 Oct): OUT legs 14 of 15 PASS; card J5 (24 Oct): round-trip legs 29 of 30 PASS; 0 FAIL in both. The one non-PASS leg in each is Vault 95 OUT, the border popup, read under gate 2 (gate 1 below). J4's round trips (26 of 30 PASS, four harness faults) were rerun by J5. Before J4: v6e (21 Oct, 15 OUT legs): PASS 10, FAIL 3, INCONCLUSIVE 2 (below). The IN legs (doors_rounds, 30 tests) never got past test 0000: the game left at the Red Rocket spawn, the crash later traced to Codsworth's model. Bugs' card J runs on the installed v6i set, since no core rebuild comes (item 4): J1 planned it on the PC (22 Oct): a local copy of doors/plan.ps1 pinned to core DC751664 and the build folder terrain_core64v6i_l125, `-Tag v6ib`, load order `--core-index 02 --port-index 06`; stages doors_v6e_rounds_v6ib (15 doors, 30 tests) and doors_v6e_out_v6ib (15 doors), queues doors_out_v6ib (15 tests) and doors_rounds_v6ib (30 tests). Two planning faults were caught and redone before any run: `-Tag` left the 21 Oct OUT stage in place (it is tagged too now), and the runner checkout at 7ecc3185 computed port index 07 where main db7c015c gives 06, the index the settling runs activated. **J2 is running since 22:39 UTC** (wait-for-idle): the 15 OUT legs have run and the 30 round-trip legs (15 round trips, an IN and an OUT leg per door) are in progress; the summary is pending (item 1); **its counts and the v6e counts are void** (the judge read positions after the "beyond" teleport, Bugs 23 Oct; #504 merged with the fix, card J4 reruns after the owner's session, gate 1 below). #500 puts the plan on main with the core as parameters and the OUT stage tagged (Codex approved, CI green, merged 00:28 UTC 23 Oct, main b78bb893) | docs/spikes/door-exit-heights.md; journal 22 Oct (ledger); #500 (merged) |
| The owner's v6 hand checks (test sheet section A) | **done on v6i, 23 Oct (gate 3 below).** The owner's section A session: the mission worked, the map markers worked, every A5 door worked except Fort Hagen's roof hatch inside, which the owner could not find (the ground entrance worked); **Codsworth did not spawn** (on the test save); cans and books can be moved inside but not outside; the quest probe ran (A7). Earlier checks stand: Codsworth renders, the Ctrl+Alt+K box (#463). Not reported field by field: the mission's five checks (the owner wrote that it worked) and Codsworth's greeting (he did not spawn) | test sheet; playtest-issues.md rows 31 to 38; journal 23 Oct |
| Launcher (runs alongside) | **in game by the owner's word (22 Oct):** the desktop shortcut opened the launcher window and started the game. #476 (window), #481 (locations tab, load-order report) merged; #487 (load-order fix before play, Fallout 4 found once, start through SFSE, StarfieldCustom.ini written as bytes so the BOM and CRLF survive) merged 22 Oct (main ab55f272); #497 (the target order on load-order.md, Fallout 4 folders listed once, the start line names SFSE) merged 22 Oct (main c9f0578); the PC re-check at c9f0578 (22 Oct, 21:23 and 22:27 UTC): paths and the play dry run exit 0, detect NOT READY only for the four missing DLC (the Steam install is pending), nothing written; the dry run would swap the FO4SFMapMarkers and FO4SFBridge lines, which is open with Map (item 6) | Launcher thread; #481, #487, #497 (merged) |

v6e door exits, 21 Oct (runner 62df40bb, judged on 6159dcb): PASS Vault114 (both doors), FortHagen01 (both),
SuperDuperMart01 (both), BostonPublicLibrary02, Vault95, MuseumOfWitchcraft01 (test 0011), PrydwenHull01. FAIL, all
WRONG_PLACE: CambridgePolymerLabs01 (34.6 m off sideways), MuseumOfWitchcraft01 test 0012 (16.4 m too high),
FortHagen02 (12.2 m too low); cause open (timing or overlap, a look in game decides). INCONCLUSIVE, both NOT_ACTIVATED
from harness failures at the start of the session: Vault75 (launch coc failed) and ParsonsState01 (console not opened
safely). Stairs on v6e: 18 PASS, 0 FAIL, 2 NOCELL.

### Phase 0 exit checklist (prepared 23 October; fill in as results land)

**Phase 0 is done (the owner's word, 24 Oct 18:58 UTC: "phase 0 is done").** All four gates are ticked. The
first-load flicker fix (#542) is merged and installed, and the owner's first-load check passed: no walls, and the logs agree (below). For
the next phase, the owner's map direction (24 Oct 18:48 UTC): the map icons that don't load are the real map issue,
possibly fixed with a map mod (not every location shows at once, and some show wrong), and likely FO4's map locations
on the Pip-Boy while the Pip-Boy work gets going. Also next phase: the owner's Steam Fallout 4 is the newer update,
not 1.10.163 (the 19 Oct decision), so the launcher's version check needs that version added.

The owner's word (23 Oct 00:14 UTC): once our testing is done they will play and do their own testing (section A, in
the project's reading), and might call the phase basically done "once we get the last few things done and tested".
These are the last few things. The approved exit names the owner's v6 checks, the automated door rounds and #353;
gate 2 below is the Vault 95 door from the door rounds, run on its own on the owner's own orders because it fails now
and then. Phase 0 closes when gates 1, 2 and 3 are ticked (gate 0 already is). Everything under "not a gate" runs now
or moves to the next phase without blocking it. Items 1 to 6 below carry the detail; this list is the summary.

**Gates**

- [x] **Gate 0. #353 merged after Codex review**: done 20 Oct.
- [x] **Gate 1. The automated door rounds on v6i** (Bugs, with Install): queues doors_out (15 OUT legs, one per door)
  and doors_rounds (15 round trips, an IN and an OUT leg per door, 30 tests; [terrain/door-rounds.md](terrain/door-rounds.md)).
  J2's counts and the v6e counts are void (Bugs, 23 Oct 03:16 UTC: the judge read positions after qstep's unscored
  "beyond" teleport, not at the door's arrival); #504 (merged 03:32 UTC 23 Oct, main 981c0216) fixed the judge.
  **Result, card J4** (Install's report, 23 Oct, finished 14:43 PC time): runner at main 6c007035 (with dc3481bd and
  5a2f382c), `-Tag v6ic`, CorePin DC751664, CoreBuild terrain_core64v6i_l125, load indices core 02 and port 07 (the
  quest probe at 06), plan exit 0, crashes 0, no "beyond" read on a judged leg in either queue, Plugins.txt the same
  before and after.
  - doors_out_v6ic: **14 of 15 PASS**, INCONCLUSIVE 1, FAIL 0. The one is 0010, Vault 95 OUT (STALE_FEED): the door's
    last log line has the position after its MoveTo, (-714.6, -1284.1, 61.3), and no feed came after, consistent with
    the BOUNDARY REACHED popup. Bugs' reading from code (23 Oct; not run): that is the exit marker's local position
    (the merged spot minus the overlay offset of -1,200 and -2,700 m); bridge t4's door first moves the player to that
    persistent marker, about 2.95 km from the merged spot, and the correction to the merged spot raises the popup.
    Bridge t6 (#512: the marker placed at the merged spot, then one MoveTo) addresses it, verified in code only and not
    yet run on the PC (it waits on the owner's t6 line). Since #515 the judge gives that stale feed as INCONCLUSIVE rather than STAYED, so the Vault 95
    reading below applies: it is gate 2's case, not a gate 1 fail or a leg to rerun. The three wrong-place exits of v6e
    (CambridgePolymerLabs01, MuseumOfWitchcraft01 0012, FortHagen02 0013) all PASS.
  - doors_rounds_v6ic: **26 of 30 PASS**, INCONCLUSIVE 4, FAIL 0. The four are NOT_ACTIVATED, a harness fault (the
    runner's "console not opened safely (3)", a console-open timeout after about 4 s by Bugs' reading, fix draft #530,
    its cause being confirmed from the HUD check pictures; the last door line is the previous test's): 0002 the Red Rocket spawn IN
    to ParsonsState01, 0023 Museum OUT, 0026 the Red Rocket spawn IN to FortHagen02, 0029 Prydwen OUT. Vault75's IN
    and OUT legs pass (0.00 m; the 14.39 m HEIGHTS line is the prelude's terrain check, not a leg).
  By the rule below a harness fault is not a door result, so the round trips were run again. **Card J5** (Install's
  report, run ended 01:19 UTC 24 Oct): doors_rounds_v6id, all 30 legs, runner at main 2eede55d (with #530's
  console fix; activate.close false in plan.json and obs.json): **29 of 30 PASS**, INCONCLUSIVE 1, FAIL 0, crashes 0,
  no "console not opened safely". The four J4 harness-fault legs (0002, 0023, 0026, 0029) all PASS. The one is 0021,
  Vault 95 OUT (STALE_FEED: the feed stopped after the door trip began), the border popup case, read under gate 2.
  **Gate 1 is ticked (24 Oct)**: every leg but the two Vault 95 OUT legs passes, and those read under gate 2 by the
  rule below. Pass:
  every OUT and IN leg PASS, with two readings set here: a Vault 95 leg that fails STAYED with the popup is the border
  failure gate 2 measures and is read there, not as a gate 1 fail; an INCONCLUSIVE leg (a harness fault, as Vault75
  and ParsonsState01 were on v6e) is not a door result and leaves the gate open until Bugs reruns and judges that leg.
  If the same three wrong-place exits fail again (CambridgePolymerLabs01, MuseumOfWitchcraft01 test 0012, FortHagen02),
  the owner decides: close phase 0 with them on the defect list (card L and the fix follow in the next phase) or hold
  for the fix.
- [x] **Gate 2. The Vault 95 exit** (Interiors, with Install): the owner's own orders, card 2 ("Run the vault 95 test",
  23:37 UTC 22 Oct: 10 exits on the installed build, bridge_t4) and card 3 (the swap to bridge_t5 for 10 more with the
  door's retry, 00:00 UTC 23 Oct), so they finish and are recorded before the owner's session. Result for the owner's
  call (23 Oct): **7 of 10 landed on t4; 6 of 10 landed on t5, retries used 0**; 13 of 20 over both runs. In all 7
  fails the BOUNDARY REACHED popup came up during the exit and paused the game, so the judge's STAYED is its last read
  before the door, not a measured bounce back inside; the retry never fired because the script sees the same landing
  in a passing and a failing trip (border.md "Rate and retry runs", #512, merged 14:02 UTC 23 Oct). #512's door change and its 10 runs
  are the next PC card. In the owner's own play (23 Oct, playtest-issues.md row 38) the door lands them in the right
  place outside; then BOUNDARY REACHED comes up, Tab does not let them move, and "it teleports me back to where I was"
  (the owner). **The owner's call (23 Oct 16:57 UTC): C, phase 0 holds until the SFSE per-world toggle of
  `bBorderRegionsEnabled` is written and tested** (border.md: the INI switch is proven only globally; the per-world
  SFSE plugin is FO4SFBorder, #522; Interiors). The Vault 95 OUT legs of cards J4 and J5 are the same popup case (gate 1). Gate 2 ticks
  once that toggle is tested on the Vault 95 exit; no bar
  is set for that test yet. It is the only border fix: the owner chose to leave the land open with no walls (L, 16:58
  UTC; playtest-issues.md row 36). #512's t6 runs still wait on the owner's swap line.
  **Card A** (24 Oct, Mode 1, watch only): the probe found one candidate setting, and only the byte 16 before its name
  pointer moved with the owner's two `SetINI` lines, 1 to 0 at 08:21:06 UTC and back to 1 at 08:21:30, so ValueOffset
  is -16 (#539, merged; border.md). **Card B, the owner's walk with the switch on** (24 Oct, 16:20 to 16:25 UTC;
  Install's live read through the coordinator, the full log set to follow): v6i_plainshader, the markers plugin with
  the border signal (mapmarkers_v6i_landing_border, esm 79eb6a93) and FO4SFBorder in Mode 2 (DLL 53c60a73, ini
  9dac6712, ValueOffset -16), Starfield 1.16.244, SFSE 0.2.21. On foot west of Red Rocket, south past Vault 95 and out
  through its door the owner hit no wall and no popup: "idk what changed but I didn't hit any walls this time"
  (playtest-issues.md row 39). The plugin's log: one candidate, armed with the value 1; border off (1 to 0) at
  16:20:59 UTC and on (0 to 1) at 16:21:00, both on the first load at the Red Rocket spawn; off (1 to 0) at 16:22:08
  back in our world. Every write ok, no refusal. In Cydonia, a vanilla world, the map script's log has border=on at
  16:21:45 and the plugin wrote nothing, the border being on already. **Caveat, the first load:** at the Red Rocket
  spawn the map script's log has border=on, on, off and on within 0.8 s (each of the markers plugin's quests writing
  the signal, #542's reading) and the plugin acted on two of them, so the border stayed on in our world until the trip
  to Cydonia and back; a player who never leaves our world could keep it on. An earlier walk at 15:33 UTC is void:
  Windows' Controlled Folder Access blocked the game's saves and the logs the switch needs (the owner's screenshots
  from it show the wall south of Vault 95); the owner fixed it and walked again. **The Vault 95 exit with the switch
  on** (Install's read of fo4sf.0.log, its bridge feed and LoadDoor lines, through the coordinator): with the border
  off since 16:22:08 UTC, the owner went into Vault 95 at 16:24:13 and out at 16:24:17 to 16:24:20; the door's line
  logged its after_position (-714.6, -1284.1, 61.3), the exit marker's local position (gate 1), in cell Surface
  02001133, and the feed at 16:24:24 had them at the merged arrival (-1914.6, -3984.1, 61.2) and moving, with no stall
  and no popup; they walked on to (-2829.8, -5493.7, 170.2) by 16:25:36. **Gate 2 is ticked (24 Oct)**: the toggle is
  tested on the Vault 95 exit, which closes the owner's call C. The first-load flicker is a defect in the switch
  (playtest-issues.md row 39; Interiors' fix, #542, merged and installed on the PC at 17:20 UTC 24 Oct), and whether it
  holds the phase is the owner's call. The owner's first-load check (18:45 UTC; a fresh load at the Red Rocket spawn,
  then west and south past Vault 95): "no walls" (the owner); Install's log read: on the fresh load the border switched off once at Red Rocket, came back on only in Cydonia, and switched off again on return.
  With gates 0 to 3 ticked, the exit checklist is met. The owner called the phase done on 24 Oct (18:58 UTC);
  #512's t6 Vault 95 runs did not run and no longer hold anything.
- [x] **Gate 3. The owner's section A checks on v6i** ([owner/in-game-test-sheet.md](owner/in-game-test-sheet.md), the
  same on the live sheet): A2 mission (tab, raiders, Preston friendly, credits, complete), A3 Codsworth (at his house,
  look, greeting), A4 map (getpos, screenshot, the four own names, the Concord arrival on the ground), A5 the six doors
  and prompts, A6 the extras. Result (the owner's report, 23 Oct 15:46 UTC, and answers at 16:30 and 16:57; playtest-issues.md rows 31 to 38): A2 the
  mission worked (the owner's summary, not field by field); A3 **Codsworth did not spawn** (on the test save the sheet named); A4 "the map markers and
  stuff worked", with getpos and the map screenshot taken; A5 at Fort Hagen the ground entrance worked and **the owner
  could not find the roof hatch inside** (the sheet's (d), FO4 door 0C38BF; a working door set in the ceiling with nothing to climb, its ladder likely lost in
  conversion, row 33), the Vault 95 door landed them in
  the right place before the border popup (row 38),
  the other doors worked; A6 cans and books can be
  moved inside, not outside (a defect row, not a gate); A7 the quest probe ran, its marker away from the door (not a
  gate). A2 and A4 pass; A3 and A5 do not, so each is a defect row and the owner's call whether it holds the phase.
  **The owner's calls (23 Oct 16:57 UTC): D, Codsworth goes on the defect list and the keeper fix is installed next
  to check it; F, the Fort Hagen hatch goes on the defect list for the next phase. Neither holds the phase, so gate 3
  is ticked.**
  Pass: A2 to A5 as expected. A6 (cans, books, the Ctrl+Alt+K box, which is already checked on v6, #463) has no report line and does not
  gate; cans or books not picking up is a defect row. A failure in A2 to A5 is a defect row and the owner's call
  whether it holds the phase.

**Not a gate** (where each goes is in its bold lead)

- **Quest probe, runs now, feeds the quest research** (NewGame, with Install): questprobe_v2 is installed (23 Oct, on
  the owner's word at 00:14 UTC, "do whatever with the probe that is ready"; port pin 9AF962D2, three scripts
  compiled). Its result answers the engine questions in docs/questprobe/engine-questions.md (stage fragments,
  OnStageSet, alias markers, our quest-type tab, a Story Manager branch) for the later people-and-story work; it gates
  neither phase 0 nor the new game. The owner ran it in section A (23 Oct, A7): "the probe worked, just placed it in
  the wrong place away from the door". Install's log extract: the alias filled and the target was a load door 72 m
  from the start (070049ED), under the stairs, which the owner reached only with tcl; the load-door choice had no floor
  or reach limit. #518 (merged 16:42 UTC 23 Oct) holds load doors to the same floor and 8 to 60 m reach as the other
  fallbacks; it is not compiled or rerun on the PC yet (engine-questions.md; row 35).
- **The new game, phase 1** (NewGame): newgame_v6 was pinned to the v6e core; newgame_v7 passed its restage against the
  installed v6i core on the PC (23 Oct, NewGame's report: 4 scripts compiled, plan pinned to port 9AF962D2 and core
  DC751664). **Installed and run 28 Oct, the owner's first new game: FAIL.** The build's MQ101Debug = 10 override picked
  Starfield's pirate-fight developer start (MQ101 stage 0 entry 10) and our guard stood down at opening_stage=250; its
  0.25-day limit also fails every Starfield new game (the 8:00 clock reads 0.3335 a second in). Both fixed offline
  (override 2; limit 1.0; the guard's readings logged): [newgame/vault111-start.md section
  10](newgame/vault111-start.md), [playtest-issues row 40](owner/playtest-issues.md). **Run 2 (newgame_v8, 28 Oct):
  FAIL**, the new game never left its loading screen: no MQ101 start entry matches 2, so nothing moved the player.
  Fixed offline in newgame_v9 (no record override; the quest writes 2 after the hold-off; SPECIAL back):
  [section 11](newgame/vault111-start.md), [row 41](owner/playtest-issues.md). **Run 3 (newgame_v9, 28 Oct 18:07 PC
  time): PASS to stage 200**: Vault 111 with no Starfield intro, the quick start, the cog door, the ride, and the owner
  walked to Sanctuary and Concord. Two placement defects of ours, fixed offline in newgame_v10: the player sank at the
  pod's z and the game stood them on the COC marker 8 m away (the start now 0.3 m higher, with a `pod settle` line),
  and the ride's arrival, set in the move's own tick, was ignored until the fallback (now a tick later, read back):
  [section 12](newgame/vault111-start.md), [row 42](owner/playtest-issues.md). The phase exit's quest-list check was
  not looked at. Since then newgame_v11 (29 Oct, the owner's pick F) makes our quest Starfield's startup quest, our own
  start ([section 13](newgame/vault111-start.md)). Installed, newgame_v11 crashed the game on every launch while it
  loaded its data files (29 to 31 Oct): its quest script's doc comment had grown past 4 KB, and the crash dump points
  at Starfield's script loader copying it into a 4 KB buffer (supported hypothesis); newgame_v10 boots and played to
  stage 200 on 31 Oct ([section 13a](newgame/vault111-start.md)). newgame_v12 (v11 with that comment short, #623)
  booted and passed run 4 to stage 200 on 31 Oct, our own start end to end ([section 13b](newgame/vault111-start.md)).
- **The animated doors port, phase 2** (DoorAnim): #489 merged (main f48d340); the PC cards (compile5, the
  doors_anim_b00 port build, the read-only elevator read) are queued after cards J, K and L and had not run at 00:15
  UTC 23 Oct; the owner's line "Install the animated doors port." follows a passing build. Step C (the exterior side)
  needs a core rebuild; none is planned in phase 0.
- **Interiors b10, phase 3** (Interiors, with Install): the restage against v6i stopped at once: interiors_b09, the
  batch it builds on, was removed by the 21 Oct cleanup. In its place a read-only check of b10's door wiring against
  the v6i core is queued on the PC (card 1b). A pass installs b10 as built (with the installer's `--other-core`,
  since it stays wired to v6c) on the owner's line; on a fail Interiors adds a redoors mode first. Detail in the Phase 1 paragraph below.
- **The combined-core probe, after phase 0** (CombinedCore): #431 merged (01:51 UTC 23 Oct, main d05f8fc1); the restage from main goes against v6i; the
  owner's line "Turn off FO4SFMission and install the combined-core probe for one test session."
- **Codsworth on the old saves, right after phase 0** (Bugs, with NPC and Interiors): #493 (the keeper quest) is
  merged but in no installed plugin; without a core rebuild it needs its own FO4SFMission build against the v6i core
  and an install on the owner's line, then card K on an old save as the proof. The section A check uses the test save,
  where the mission starts fresh, so this waits unless the owner plays their 19 Oct save.
- **The three wrong-place exits, next phase unless the owner holds (gate 1)** (Bugs): card L and the fix after J2's
  result.
- **Surface map LOD, open research** (Map): #496 merged (the markers plugin's stale-world check, `--world` variants);
  the Creation Kit's LOD runs on Map's three tiny test plugins (object-lod.md item 7) found none of their worlds
  (#501, docs only, merged 00:45 UTC 23 Oct); the route is unproved,
  and buildings on the surface map wait on the Fallout 4 LOD mesh route (Grok, #490).
- **Launcher, runs alongside** (Launcher): #497 merged (main c9f0578; the target order is on
  [testing/load-order.md](testing/load-order.md), Fallout 4 folders listed once, SFSE start named in the dry run); the
  PC re-check at c9f0578 passed except the four DLC still missing (the Steam install of Fallout 4 is pending) and two
  open points: whether the Meshes.ba2 overlap warning should be silent when the two files are identical, and the
  load-order target, which has FO4SFMapMarkers before FO4SFBridge, the order the game itself wrote after the settling
  runs, while Map's installer puts the markers last, after Bridge, so the dry run would swap those two lines (Launcher
  checks with Map before changing the target).
- **Merges, housekeeping**: #408 (framework, merged 00:17 UTC 23 Oct, main 597ea5f6), #500 (doors plan, 00:28 UTC,
  main b78bb893), #501 (LOD doc, 00:45 UTC, main 7625deaa) and #502 (Bugs: the HUD screenshot is kept when a test step
  cannot open the console, 00:58 UTC, main 564dfa64) are on main, and so are #503 (this checklist, 01:41 UTC, main 7816bb1e) and #431 (combined core, 01:51 UTC, main
  d05f8fc1). Codex (the bot and the desktop app, one account) ran out of usage on 23 Oct until 29 Oct, so on the
  owner's word (23 Oct, 01:25 UTC, option A) Grok reviews this week; a Grok "no major issues" is the review pass, and
  nothing merges without one.

**The owner's install lines.** Typed in the Install thread, one at a time, only when a thread asks. None of them is
a phase 0 gate.

- "Install the quest probe plugin.": not needed; the probe went in on the owner's 00:14 UTC word (23 Oct)
- "Install the new game." (**done 28 Oct, FAIL twice, then PASS to stage 200 with newgame_v9**: the pirate-fight
  developer start, a load that never finished, then run 3, vault111-start.md sections 10 to 12; newgame_v11 crashed
  at every launch, section 13a; "Reinstall the new game." (**done 31 Oct, PASS to stage 200 with newgame_v12**, our
  own start, section 13b))
- "Install the animated doors port." (after the port build passes)
- "Turn off FO4SFMission and install the combined-core probe for one test session." (after the restage from main; #431 is merged)
- the b10 line: Interiors words it after card 1b passes
- the Codsworth keeper line: not worded yet; it follows the FO4SFMission build against v6i (item 3)

### What is left to close phase 0, with an owner

1. **Door rounds on v6i** (Bugs, with Install): the doors plan on the plans branch pinned the v6e core (06C0DECD) and
   its build folder. Bugs' card J is a local copy of doors/plan.ps1 with the installed core's CorePin and CoreBuild and
   `-Tag v6ib`, so doors_out (15) and doors_rounds (30) land in new folders; it runs on v6i, not on a rebuilt core,
   because no rebuild comes (item 4). plan.ps1 does not read the v6e campaign file, so its Red Rocket hold stays as it
   is (only the owner releases it). J2 (22 Oct, 22:39 UTC on) settles Vault75, ParsonsState01 and every IN leg,
   re-measures the three failures, and is the round that closes phase 0: doors_out and doors_rounds both must pass,
   except that a repeat of the three wrong-place exits is the owner's call (gate 1) and a Vault 95 STAYED is read under
   item 4. The v6e campaign and its results stay as they are. #500 (merged 00:28 UTC 23 Oct, main b78bb893) carries
   the plan to main: `-CorePin`, `-CoreBuild` and `-OutMinM` as parameters (v6e's core as the defaults; `-OutMinM` has no default
   and must be given unless `-RoundsOnly` is passed, 0 keeps every exit as the v6e doors did), the OUT stage tagged
   with the rest, a checkout at main db7c015c or later so the load indices come from the live order, and a pins.json in
   every stage it makes (the inputs' sha256s and the indices), reused only on an exact match; stages made before it,
   the v6ib ones included, have none, so a rerun from the main plan needs a new `-Tag`. J2's counts are void (Bugs, 23 Oct
   03:16 UTC: the judge read positions after the "beyond" teleport, not at the arrival; the v6e counts share the flaw);
   #504 (merged, main 981c0216) fixes the judge and card J4 reruns both queues under `-Tag v6ic` after the owner's session (gate 1).
   **J4 ran on 23 Oct: OUT 14 of 15 PASS, round trips 26 of 30 PASS, FAIL 0; Vault75 passes both ways; ParsonsState01's
   IN leg from the spawn is one of the four harness-fault legs to rerun (gate 1).** **Card J5 reran all 30 round-trip
   legs on 24 Oct (29 of 30 PASS, the four included; the other is Vault 95 OUT, gate 2), and gate 1 is ticked.**
2. **The three wrong-place exits** (Bugs): card L, after J2, one in-game look per exit still wrong to tell timing
   from overlap, then the fix (converter collision, core arrival marker or FO4SF_LoadDoor), a rebuild, and an install
   on the owner's line; the exit fix follows L's result and is not a phase 0 gate unless the owner holds for it (gate 1).
   **All three passed their OUT legs on card J4 (23 Oct), so no wrong-place exit is left for L to look at; whether L
   closes is Bugs' call.**
3. **Codsworth on existing saves** (Bugs, with NPC; Interiors for the Mission build): the likely cause is that his
   relocation timer never ran on the owner's existing save (no timer in the mission quest logs); the fix built on that
   reading is a new start-game-enabled keeper quest, because only a new quest runs on an existing save whose timers
   are dead; it also enables him. That fix is #493 (keeper quest FO4SF_CodsworthKeeper, 0x814), **merged 22 Oct (main
   f77c25c)**: CI green and Codex approved at e1f3811; the
   Codex desktop ran the Mission build and selftest and the Papyrus compile offline (compiler 4.7.0.5, one script,
   exit 0), so Bugs' build-only PC card is dropped. It was to fold into a v6j Mission refold; with no core rebuild it
   needs its own FO4SFMission build against the installed v6i core (the mission's WRLD override copies the core's,
   unchanged) and an install on the owner's line. What it does on an existing save (the quest starting,
   OnPlayerLoadGame, Codsworth's placement) is unproven until then, when card K, read-only on a save from before the
   22 Oct console fix, is the in-game proof, folded once with NPC (no console ids in any owner instruction; ids move between sessions).
   In the 23 Oct section A session the owner reported "no Codsworth spawn" (row 32), on the test save the sheet named,
   where the mission starts fresh, so the mission's own path did not show him either, not only old saves. The
   mission's log has four moves of him with no fail and him about 3 km off between them (row 32). The keeper quest
   also enables him, so its Mission build against v6i and the owner's install line are the next step (Bugs). The
   owner's call (23 Oct 16:57 UTC): D, on the defect list, with the keeper fix installed next; it does not hold
   phase 0.
4. **The Vault 95 exit** (Interiors, with Install): the settling test answered on 22 Oct (22:26 UTC): control 3 of 3,
   nosmall 2 of 3, city 2 of 3, so neither world field is a reliable fix and the failure is intermittent
   ([terrain/border.md](terrain/border.md), Results). The border fields are shelved: no core is built with
   `--world-border`, there is no v6j, no stage is restaged for a core change (the new game and the combined-core probe
   still restage against v6i, Phase 1 below), and v6i stays the phase 0 build. The two PC runs on the
   owner's lines ran on 23 Oct: card 2, 10 exits on the installed build with the FO4SF_LoadDoor trace, landed 7 of 10;
   card 3, the same 10 with the door's retry of a missed trip (#499, bridge_t5, swapped back to bridge_t4 after),
   landed 6 of 10, and the retry never fired. In every fail the BOUNDARY REACHED popup came up during the exit and
   paused the game, so the judge's STAYED was its last read before the door, not a measured bounce back; the script's
   trace was the same in every PASS and FAIL (the MoveTo lands at the marker's unmerged spot, then a SetPosition goes
   to the merged one), so no check right after the move can catch the failure (border.md "Rate and retry runs",
   #512, merged). These two runs are gate 2 in the checklist above. **The owner's call (23 Oct 16:57 UTC): C, phase 0
   holds until an SFSE plugin that turns the border off only inside our world is written and tested** (border.md;
   FO4SFBorder, #522: card A's probe found the setting's byte at offset -16, #539; on card B, 24 Oct, the owner
   walked west and south of Red Rocket and out through the Vault 95 door with the switch on, with no wall and no
   popup and every write logged, so gate 2 is ticked; open: a first-load flicker that left the border on until a
   trip out and back, fixed by #542, merged and installed; the first-load check passed). #512's door change (the destination marker moved to the merged spot before the MoveTo,
   plus a settle step that shows which step raises the popup) is not yet compiled or run; its t6 runs wait on the
   owner's swap line. There is nothing to recheck on foot: the wall north of Vault 111 is withdrawn.
5. **The owner's remaining v6 checks** (NPC for the mission and the voice, Map for the map extent, Bugs and Interiors for
   the doors and prompts): written up as section A of [owner/in-game-test-sheet.md](owner/in-game-test-sheet.md)
   (the same text is on the owner's live test sheet, https://claude.ai/artifact/N5ZhYy7zgoxnJ2Fuzhws6b) for their
   next session: a fresh test save, since the mission completed on the 19 Oct save; coc FO4Core_RedRocketSpawn; the
   Missions tab, Preston and the credits; Codsworth's greeting; getpos plus a zoomed-out surface map screenshot, the
   four markers reading their own names (Red Rocket Truck Stop, Sanctuary Hills, Vault 111, Concord) and a fast travel
   to Concord that lands above ground (the #483 override, installed 19:32 UTC); the Fort Hagen elevator, the Vault 95 elevator, the Museum of Witchcraft and Fort Hagen hatches, the Vault 114
   manhole, the Red Rocket side door; cans and books. Results go to playtest-issues.md. **The results that close
   phase 0 are taken on v6i, the installed build**, since no core rebuild comes (item 4); the session follows the PC's
   door rounds and Vault 95 runs, which use the game. Done 23 Oct: the results are under gate 3 and in
   playtest-issues.md rows 31 to 38.
6. **One load order** (Launcher, with Bridge): the runner's deploy appends FO4Port last when it owns the line (a
   hand-placed line keeps its position), the owner's install had it first, and the file was rewritten after start
   (the game is the inferred writer; not traced);
   #481 reports the change. #487 (merged 22 Oct) defines the target in `scripts/game/load_order.py check|fix`:
   lines that are not ours first, then the cores (FO4Terrain*, FO4Actor*), the other FO4SF* experiments, FO4Port,
   FO4SFMapMarkers, FO4SFBridge, each plugin after its masters; that is the order the game wrote on 22 Oct. The
   launcher's new `load_order` setting (default fix; check refuses a mismatch; off) runs it before every play. #497
   (merged 22 Oct, main c9f0578) documents the target on [testing/load-order.md](testing/load-order.md). The PC dry run
   at c9f0578 would swap the FO4SFMapMarkers and FO4SFBridge lines: the installed file has the markers after Bridge,
   where Map's installer puts them, while the target keeps MapMarkers before Bridge, the order the game itself wrote
   after the settling runs; which of the two should stand is open with Map. The runner (cycle.ps1) does not call it
   yet.

### Phase 1 (new game) and the other staged plugins

The new game (newgame_v6, #393 and #435 merged) compiled all four scripts and passed its staging checks on the PC, but
against the v6e core (06C0DECD), not the installed v6i core (DC751664); its installer checks the core pin, so it was
restaged against the installed v6i core as newgame_v7 (passed on the PC, 23 Oct: 4 scripts compiled, pins port 9AF962D2
and core DC751664; no core rebuild, item 4). It was installed and run on 28 Oct: FAIL, Starfield's pirate-fight developer
start (the MQ101Debug = 10 override; the guard's 0.25-day limit too). Its fix, newgame_v8, ran the same day and never
left the loading screen (the override 2 matches no start entry); newgame_v9 overrides nothing and writes the global
after the hold-off, and its run 3 reached stage 200 (Vault 111 to Sanctuary); newgame_v10 fixes its two placement
defects and newgame_v11 makes our quest the startup quest (our own start), restage pending (vault111-start.md sections 10 to 12). The same holds for the focc probe (#431, merged 23 Oct, main d05f8fc1): CombinedCore restages
it from main, with `--core` on the installed FO4TerrainCore.esm into a new staging folder; the core
that ends up installed is v6i (Interiors shelved the border fields on 22 Oct, no v6j); its install needs the mission off (probe_install refuses while FO4SFMission.esm is active), so the
owner's line is "Turn off FO4SFMission and install the combined-core probe for one test session.", and
probe_install.py uninstall restores Plugins.txt afterwards. The quest probe is pinned to the port, which is unchanged
(9AF962D2); it is installed (23 Oct) on the owner's word of 00:14 UTC 23 Oct, no line needed. The object test room and the merge probe
have no install route while the core set holds exp_install's one experiment slot. Interiors b10 (all 253 interiors,
coc-only) gets its installer from #494 (merged 22 Oct; `deploy_starfield.py install --batch <stage>`: the batch's whole set,
companions included, each file checked against its pinned sha256; it refuses when Data's FO4TerrainCore.esm is not the
core the batch's doors were wired to), so b10, built against v6c, needed a restage against the installed core; that restage (card 1, 22 Oct) stopped at
once because interiors_b09, its chain parent, was removed by the 21 Oct cleanup, and Interiors replaced it with a
read-only door-wiring check of b10 against the v6i core (card 1b, vmad_patch check with the #499 fix for the port
folder's second plugin; queued on the PC): a pass installs b10 as built on the owner's line, with the installer's
`--other-core` override (the batch stays wired to v6c), a fail gets a redoors mode; its Commonwealth doors still need a core rebuilt against that port (phase 3). The door animation groups G1 to G3 (#392, switches off) get their
staging path from #489 (`interior_batch.py build --animated-doors`, merged 22 Oct, main f48d340): a recompile
(compile5), a port build into D:\Modding\staging\doors_anim_b00 (about 15 min) and a read-only SfInspect elevator
read, re-pinned to f48d340 and queued for Install after cards J, K and L (not run at 00:15 UTC 23 Oct). G2 (Fort Hagen, port only) and G3 (out through
the animated interior door, back through the core's ACTI) can run on the installed core once that port is in; the
owner's line, only after the build passes, is "Install the animated doors port." (rollback swap_v6i_plainshader.ps1).
G1 waits for the core-side step C (the exterior ACTI becomes the same animated DOOR with FO4SF_AnimatedLoadDoor,
switch off by default), which rides the next core rebuild, none of which is planned in phase 0; Bugs has the plan.

The 19 Oct table below is history: #393, #392, #396, #394 and #399 merged on 21 Oct, #391 and #397 on 22 Oct.

## Update, 20 October 2026

On 19 October the owner set the combined core as the first priority from here on: a GAMMA-style second way to play
around settlements that grow, factions that act and a connected wasteland, built on the Commonwealth first, because
it has value without the open legal questions. The stories are still wanted, and the work in flight continues (the
v6e test, the mission, the Vault 111 start and the approved phases in their order). The owner's decisions for each
phase, and the critical path, are in docs/research/framework/dependencies.md on draft PR #408; they are not repeated
here. The project is not offered for download or play for now.

## Update, 19 October 2026

Phase A and the start of Phase B overlap: the B4 mission ("When Freedom Calls", cut down) has run to completion in
game on the v6c build (#353, notes in docs/mission/when-freedom-calls.md), and Codsworth stands in Sanctuary as a
robot stand-in (#361). Phase A is not closed: v6 crashes near Red Rocket and the Museum of Freedom are under a
bisect (#375; the v6e test build is staged), and the map markers do not draw yet (#376).

On 19 October the owner approved the order of the next phases. It replaces section 2's order where they differ:

1. **New game:** a Vault 111 start with no Starfield intro, which everything else plugs into.
2. **Doors:** load doors with their enter and exit animations.
3. **Interiors:** all of them (about 190 are still unconverted), in batches.
4. **Launcher:** it ships no assets and builds the port from the player's own Fallout 4 and DLC; it may require
   Starfield's free Creation Kit, and the port may require SFSE.

The owner also decided: the Commonwealth, Far Harbor and Nuka-World share one Earth-like planet with real days and
weather; the player is silent by default; Starfield's own animations come first; releases go to GitHub first. The
order after the launcher is open. Research inputs are in draft PR #380 (docs/research/next-phase/), with Grok's
proposals (#381, PR #386) and Codex's review (#382). Offline work on the four phases has started on separate branches;
nothing from it is installed until the current crash test is done.

Offline work in flight (draft PRs, not merged, nothing installed; 19 Oct):

| Phase | Draft PR | What it holds |
|---|---|---|
| 1. New game | #393 | FO4SFNewGame.esm, a Vault 111 start built offline |
| 2. Doors | #392 | load doors that play their opening before the trip, behind a switch that is off by default |
| 3. Interiors | #396 | a census of all interiors, a 9-batch plan, and staged batch builds that keep the installed port's ids |
| 4. Launcher | #394 | the build manifest, a resumable build, a recorded restore and a same-ids check |
| Testing | #391, #397 | the night-chain arm check and direct exe launch; door round trips per interior batch and the v6e test campaign |
| Map | #399 | an installer for FO4SFMapMarkers.esm next to the core set (#376 is merged) |

## 0. Where we are (17 October 2026): Phase A, the Commonwealth slice, in testing

Phase A is "the playable Commonwealth exterior plus the first interiors, running natively in Starfield". It maps to
PLAN.md's P2 (statics + interior) and P4 (exterior) with parts of P3 (actors) and P6 (scale).

Verified in game (the owner, or the runner from the console):

- the whole 64 x 64 cell exterior as native terrain with 648,358 placed objects (build core64k); the owner walked from
  Red Rocket to the Diamond City gate with no crash and no Boundary Reached (playtest row 25);
- containers and loose items work and the hand scanner tags them (rows 12, 16); the Red Rocket workshop opens
  Starfield's build mode (row 12); 6,249 exterior lights are placed but too bright (row 22). Placed but not yet
  checked in game: the other 28 workshops, the crafting menus of the 269 benches, the 140 terminals; activators show
  their prompt but nothing is wired behind them yet (row 21);
- 16 interiors reachable by `coc` (Vault 111, Red Rocket, Super Duper Mart, Valentine's Detective Agency and more,
  build integ_1018); Vault 111's sliding doors work (owner, rows 1 and 6); the cog door VltGearDoor01 is still a solid
  static, so the vault exit stays shut;
- shooting converted objects no longer crashes (the collision mesh key fix, #274; owner, row 18);
- the first scripted load door: activated from the console by the runner, the exterior Super Duper Mart door put the
  player on the interior arrival marker (journal, 16 Oct night); a walked activation and the return trip are not
  proven yet;
- a converted raider fights the player when combat is forced from the console (npc_combat c2 and c4; unprompted it
  never engaged, c1); a spawned vanilla NPC paths on the converted exterior navmesh.

Open before Phase A closes (the [test sheet](owner/in-game-test-sheet.md) is the checklist; it is refreshed first):

| Item | State | Owner |
|---|---|---|
| Door return trip (interior to exterior) | script merged (#291); the writer side #297 (persistent exterior markers, DestinationX/Y/Z and UseDestinationPosition on both door VMADs) is in the merge queue after Codex's clean delta QA at 3446a99; the round-trip queue is staged; one runner window is needed | Claude, Codex QA |
| Exterior lights too bright at night | cause found (median lumens x fade 2.3x vanilla); #302 scales every LIGH by 0.375 as a raw plugin patch, staged as terrain_core64l_l125 for the owner's night check | Claude |
| Vault 111 gear-room gates passable | cause found: frozen leaves keep FO4's clutter-no-cut layer, which Starfield's character controller passes; the fix writes them as static (PR from branch claude/gate-clutter-nocut-static); needs an interior rebuild | Claude |
| Vault 111 flat grey floor | the gear-room pit's water sheet was converted as an opaque plank; #300 leaves water planes out; needs an interior rebuild | Claude |
| Vault 111 cog door (an activator with Stage clips, played from its console) and the exit elevator | not built | Claude |
| Picking up and carrying objects in the world (not into the inventory) | does not work (owner, row 26); hypothesis: FO4 masses are 2 to 10 times Starfield's for small items (research log); the owner's in-game mass experiment decides | Claude |
| Garage button does nothing | #303 (Grok, open, wire-only): FO4's XAPR link becomes the vanilla DefaultActivateLinkedRefOnActivate plus an XLKR on the button; no Opening/Closing clip alias (that made garage meshes passable). Garage NIF rig is later, Claude on the build side | Grok, Codex QA, Claude build |
| Nothing visible beyond the loaded cells | no distant LOD for converted statics; #303 carries the object-LOD plan (no build yet; next a small LOD trial) | Grok research, Claude build |
| Textures: foliage cutouts, greyscale palettes, vines, white walls | Grok's #288/#289 need the review fixes, then Claude reconverts | Grok, Codex QA |
| Map surface view and markers | what the surface map shows over the Commonwealth is not recorded yet (a playtest row with the owner's screenshot comes first); #296 restores the first marker; the 3D view is section 3's first Grok item | Grok |
| Benches show Starfield's models | low priority (owner) | Claude |
| Elevator and power armor rest poses, FLOR harvest, interior lighting | known, queued | Claude, Grok (#290) |

**Exit criterion for Phase A:** from a save made before this build was installed, the owner arrives at Red Rocket by
fast travel to its map marker (until #296 is proven, one noted `coc FO4Core_RedRocketSpawn`), walks the exterior at
day and night, goes in and out through each of the 15 placed exterior load doors into converted interiors, and nothing
crashes. The runner's door_trip (walk in, walk out, save, load) passes for the same doors. Every line of the refreshed
test sheet reads "works" or carries a dated owner note.

## 1. Phase B (next): one playable slice

The owner's words: "once we get the interior made and show we can bring in one complex NPC and get a working playable
area textured with one simple mission (you can make the NPCs for it also do combat)". This is PLAN.md's P3 and the
first half of P5, on the ground we already have.

### B1. The interiors of the slice, finished

The slice is Vault 111, Sanctuary Hills, Red Rocket, Concord (the Museum of Freedom) and the roads between them.
Every interior in it loads, is lit, has correct physics (no passable gates, no planks over water), and its doors work
both ways. The Vault 111 exit works: the cog door opens from its console, and the exit elevator works or is replaced
by a scripted door of the load-door kind. Interior batch 1 (the ranked backlog in docs/terrain) adds the slice's
missing interiors first, the Museum of Freedom among them.

### B2. One complex NPC

"Complex" means all of: a converted appearance (model and outfit, or a Starfield race stand-in while the face
pipeline is open), a name and the NPC's own Fallout 4 voice lines converted from the player's files (no synthetic or
cloned voice of the original actors), a dialogue tree ported from Fallout 4's dialogue records into Starfield's
quest-dialogue form, AI packages (sandbox, follow, travel), combat (weapon, faction, aggression), and persistence
across save and load.

Candidate: **Preston Garvey**, a human on the Starfield human skeleton, built the way the converted raider is (FO4
identity on a Starfield template, a Starfield face stand-in while the face pipeline is open); he also gives "When
Freedom Calls". Stretch: **Codsworth**. A Mr. Handy has no Starfield skeleton and ACTOR-MILESTONE.md puts creature
rigs last, so a first Codsworth would use a Starfield robot body under his name and lines. Voice: FO4's lines need
WP-15 (.fuz to .wem plus lip sync, not started); until it lands, subtitled silent lines are the declared stand-in.
The team confirms the choice with the owner before building.

### B3. A textured, finished playable area

In the slice: no flat, white or placeholder materials; foliage and vines right; lights calibrated for night; distant
objects visible (LOD); the surface map view from section 3, extended to the slice's markers; fast travel inside the
slice or a clear reason why not yet.

### B4. One simple mission, with combat NPCs

A quest record with stages, objectives and quest markers; a giver with dialogue; a combat objective against converted
raiders; a reward; completion without the console. Candidate: a cut-down **"When Freedom Calls"** (reach the Museum of
Freedom, clear the raiders, talk to Preston). The converted raider fights once combat is forced (StartCombat player,
runner queues npc_combat_c2/c4, 15 Oct); unprompted it never engaged (c1), and it wears its Starfield template's look.
The mission needs raiders that are hostile on sight on the converted navmesh of ConcordMuseum01, which waits for the
near-slice interior batch.

**Exit criterion for Phase B:** the owner, without the console and from a save made before the build was installed,
leaves Vault 111, walks to Preston, takes the objective, fights through Concord, completes the mission, saves,
reloads, and everything persists. The runner covers the same path from the console: door_trip with save and reload on
each slice door, npc_nav with combat reads judged ENGAGED with no forced start for the mission's raiders, and quest
stage and objective reads through the bridge after each step and after the reload (a new bridge probe and runner
kind, built in Phase B).

### Who does what in Phase B

- **Claude** (lead, live game): integration builds, the door and interior path, the mission assembly, acceptance runs,
  the owner's installs, every in-game check, this roadmap.
- **Codex** (records, IDs, deploy): the quest, dialogue, package and faction record machinery (Fallout 4 QUST, DIAL,
  INFO, PACK to Starfield), persistent identity across builds, deploy and recovery, the Papyrus for the mission, and
  independent QA on Grok's PRs.
- **Grok** (oracle, diagnostics, research-first build work): textures and materials to completion in the slice,
  distant LOD, the 3D surface map view and map markers, the garage wiring, the face and voice research for B2, and the
  acceptance oracle for claims it did not build.

## 2. Phase C (later): a launcher and a Fallout core on Creation Engine 2

The owner's words, verbatim: "then lets move to making a launcher like fallout london has where it focuses on the core
of what we need removes the starfield unneeded bits and start building what we need for a base core to make a build to
play any fallout from in creation 2 with the base same idea with fallout 4, a second one that allows a playthrough of
all games as one player then a mode an a third build for a stalker gamma style experience the reason for this i
modding it makes it so people have a build or something better to target".

Read as: a launcher, a shared base core, and three builds on it (any Fallout game on Creation Engine 2, made the way
Fallout 4 is; all games as one playthrough; a STALKER GAMMA style build), so that modders have a common target. "Then
a mode" is not yet resolved: whether the all-games playthrough is its own build or a mode of build 1 is confirmed with
the owner before C3 is designed.

### C1. The launcher

The owner's model is the launcher Fallout London has; what it does step by step is Codex's first Phase C research
item (Fallout London's GOG installer copies that team's own original content into the player's Fallout 4 folder, and
Steam owners run a downgrader that asks for their Steam login and rewrites the install; our builds contain Bethesda's
content, so we cannot ship them, and we never ask for store credentials). Ours, for the user's own Starfield: it checks
both game copies and only reads the Fallout 4 install; runs the converters on the user's machine against the user's
own files (the project ships only its own code, scripts and documentation, never converted records, meshes, textures
or audio); sets the plugin list and INI profile; keeps the Starfield content the build does not need out of play
through override records from our own plugin and a start option (Starfield.esm stays loaded because our plugins master
it; nothing is deleted, no executable is touched, and every change is recorded so the vanilla profile restores the
previous plugin list, INIs and Data folder); and launches. For players it replaces today's exp_install step. It ships
the runtime scripts the observation bridge carries today (FO4SF_LoadDoor), not the bridge's test telemetry.

### C2. The base core

One shared foundation under every build: the conversion toolchain, the Fallout systems on Creation Engine 2 (SPECIAL
and perks, radiation, the Pip-Boy-style interface, the workshop, factions, weapon and armor frameworks, dialogue
camera), the launcher, and the acceptance machinery. Modders target the core, not a particular build. This revisits
PLAN.md's non-goal on reimplementing VATS and the Pip-Boy: the base-core note says which systems get Starfield-native
equivalents and which are rebuilt, and PLAN.md is updated once the owner agrees.

### C3. Three builds on the core

| Build | What it is | Notes |
|---|---|---|
| **1. Any Fallout on Creation Engine 2 (the base)** | each Fallout game playable on its own in Starfield's engine, made the same way as Fallout 4; Fallout 4 comes first and is the end state of this port | the Commonwealth, its interiors, actors, quests; other games follow as their converters exist (build 2's notes) |
| **2. All games, one playthrough** | one character through every Fallout world in sequence | each game needs its own converter and the player's own copy of that game. Fallout 3 and New Vegas are Gamebryo-era (a second reader feeding the same pipeline). Fallout 1, 2 and Tactics are 2D, so they would be hand-built recreations outside the deterministic pipeline (PLAN.md section 2), each a project of Fallout London's size. Fallout 76 is an online game under its own terms; whether it is in scope is the owner's call after research |
| **3. STALKER GAMMA style** | original systems built on build 1 and inspired by the STALKER GAMMA modpack: anomalies, artifacts, A-life style spawns, weapon degradation and repair, hunger, thirst, sleep, faction wars, an economy | no assets, scripts or code from STALKER, Anomaly or GAMMA's component mods, which have their own authors and licenses |

### Constraints that hold for all of Phase C

- Players own every game a build reads (Starfield and each Fallout game it converts), and converters read those copies
  on the player's machine. Nothing of Bethesda's or any other studio's is redistributed, and the launcher never changes
  a game's executable or removes anything from an install.
- Each build is useful on its own, in the spirit of PLAN.md section 5.
- Research before machinery: the launcher and each system start as a written design with a go/no-go, reviewed on
  #32, before code. A launcher alone cannot remove engine limits (#286).

### First steps for Phase C (research, after Phase B's exit)

- **Codex:** extend #286 (the open launcher and streaming spike) with what Fallout London's installer and the FO4
  Downgrader actually do step by step and which steps we must not copy; then a design for install, profile, plugin
  order, INI, verification and rollback on top of scripts/game/exp_install.py and the recoverable deployment work.
- **Grok:** a survey of the Fallout systems that have no Starfield equivalent (SPECIAL, VATS, Pip-Boy, radiation,
  settlements) and how other Creation Engine 2 mods approach each; a design note for the STALKER-style systems set.
- **Claude:** the base-core boundary (what is shared, what belongs to a build) and the order of builds.

## 3. Immediate assignments (while Phase A testing finishes)

- **Grok**, in this order, each item research-first with a go/no-go note on #32:
  1. **the 3D surface view in the map, for this testing stage** (the owner: "lets task grok to make a 3d view for the
     surface view in the map view for this stage in testing"): a short research note on what Starfield's surface map
     draws from (the world's terrain and its LOD, the planet's own data, object LOD), why ours would show Mars (the
     overlay's Location is parented to the Mars surface, docs/terrain/map-markers.md) and whether an overlay world can
     appear there from our own plugin and locally generated files; then the build on #296's marker after its LCSR fix.
     Acceptance: a screenshot of the surface map opened at Red Rocket showing the Commonwealth terrain in 3D with the
     Red Rocket marker (Claude takes it);
  2. the review fixes on #288, #289, #290, #296 and the #303 wire-only review (clip alias out); after Codex's QA, Claude runs the reconversion and
     the in-game checks;
  3. the object-LOD trial from #303's plan, with Claude on the build side (the exterior writer and staging are Claude's;
     Grok hands over patches, or the file scope is agreed on #32 first).
- **Codex:** independent QA of Grok's #303 writer change, the round-trip run's evidence review, #301 (the #293
  follow-up) to merge after QA, then the Phase B record machinery design (quest, dialogue, packages) as a written note
  on #32.
- **Claude:** the round-trip runner window and the owner's next install (door-enabled exterior, dimmed lights, the
  door-script bridge), the interior rebuild with the gate and water fixes, the carry-mass experiment with the owner,
  then the NPC and mission plan with the owner.
