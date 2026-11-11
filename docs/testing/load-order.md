# Load order on the test PC: what writes Plugins.txt, and why ref ids move between sessions

Written 22 Oct 2026 from the code on main and the Install thread's reads of the owner's PC; launcher preservation
updated 11 Nov for FAL-354. This page records who changes the file. Nothing here is verified beyond what each line
says; the dated PC observations below are historical.

## Who writes Plugins.txt

- `scripts/deploy_starfield.py install` activates the port and records in its manifest only the line it owns
  (`plan_plugin_activation`): with no FO4Port line in the file it appends `*FO4Port.esm` and owns it; with an inactive
  `FO4Port.esm` line it activates that line in place and restores it on uninstall; with an active `*FO4Port.esm`
  already there it owns nothing and leaves the line where it is. `uninstall` removes exactly the owned lines. The
  runner's `scripts/game/cycle.ps1:49-50` runs uninstall then install before every cycle, so FO4Port lands after
  every other line only where the manifest owns the appended line (the usual runner case); a FO4Port line the owner
  put in by hand keeps its position through the cycle.
- `scripts/game/exp_install.py install` appends the experiment's plugins; `order` guarantees before launch that each
  experiment plugin comes after all of its active masters (`order_lines`): a plugin that stands before one of its
  masters is moved to just after the last of them, and a plugin already after them is left where it is, so an
  unrelated line can sit between a master and the experiment. It refuses missing or disabled masters.
- `scripts/game/map_markers_install.py order` moves `*FO4SFMapMarkers.esm` to the end; cycle.ps1 runs it before the
  bridge's order, so the planned read indexes of the experiment and FO4Port stay as they were (module doc).
- The launcher (`src/fo4sf/launcher/crashwatch.py`, #449, #481, #487) writes Plugins.txt only before start: when the
  bridge toggle changes, and, since #487 (merged 22 Oct, after the run below), through `scripts/game/load_order.py`
  when the `load_order` setting is `fix` (the default) and the order differs from the target (`apply_load_order`,
  run after the bridge step; `check` refuses a different order instead, `off` leaves the file alone). Since #481 it
  compares the order at start and at exit and reports a change in its own output
  ("Plugins.txt load order changed while the game ran: ..."). The crashwatch.log line for it is written only when the
  crash watcher is on (`crash_watch.enabled`; `play()` has no log path otherwise), so an ordinary launcher run with
  the watcher off leaves no persistent record of the change.
- The game itself: `docs/PLAY-AND-TEST.md` says to choose **Current** at the "load order changed" dialog because
  saving it can switch the port's plugins off, and `map_markers_install.py active` notes that loading a save can
  restore the save's own order after `order` ran.

## What Install read on the owner's PC, 22 Oct

- The map markers install at 05:50 local recorded FO4Port first in Plugins.txt (so the mission's index was 06 in the
  morning session: `prid 06000811` worked for Codsworth).
- At 11:26:20 local, 25 s after the owner started the game through the launcher, Plugins.txt was rewritten (not by
  Install) as: FO4TerrainCore, FO4TerrainCore_Mars, FO4ActorRaider, FO4SFMission, FO4Port, FO4SFMapMarkers,
  FO4SFBridge, all active. The mission became 05, and `prid 05000811` worked in the afternoon session. The launcher
  thread's reading of its own code is that the launcher did not write it (the bridge setting was unchanged, and the
  load-order fixer of #487 did not exist yet), so the rewrite is the game's; the cause is inferred, not traced.

## Consequences

- Console ids of our records (`prid`, `placeatme`) are not stable across sessions. Owner instructions should name the
  object, or Install reads the current Plugins.txt first and gives the index for that session.
- The door judge (`scripts/bridge/door_rounds.py`) plans its read indexes from the order the stage predicted and never
  turns a changed index into a pass or a fail, but it does not always name it: `judge_test` checks the runner's
  activation proof and the ack first, so an index change that breaks the GetIsID proof against the planned door id
  comes back as INCONCLUSIVE NOT_ACTIVATED (or NO_ACK), and only a leg that got as far as resolving its destination
  marker at the wrong index reads INCONCLUSIVE INDEX. Any INCONCLUSIVE after an order change is a cue to read
  Plugins.txt before diagnosing the harness. The walk judge
  (`scripts/game/walk_eval.py`) has no such gate: it judges positions, ground, crossings and screenshots without
  comparing the planned index to the runtime one, so a walk run after an order change needs its indexes checked by
  hand.
- Planner drift (Card J, 22 Oct): `door_rounds.py order` at 7ecc3185 gave `--port-index 07` for the same Plugins.txt
  where main db7c015c gives 06 (a43afefa puts the map markers plugin right after the port, as cycle.ps1 does), and the
  live game had 06 (settling runs activated 06008EB2). The v6i plan made at 07 was discarded unrun. Plans take their
  indices from a checkout at db7c015c or later (the doors plan refuses older ones) and check them against the
  Plugins.txt the game wrote after a launch before staging.
- #481's report is detection only. #487 (merged 22 Oct) adds `scripts/game/load_order.py check|fix`, which defines
  the target order (the order the game wrote on 22 Oct, each plugin after its masters) and a launcher setting that
  runs it before every play; the Launcher thread documents the target order on this page next. Open: the runner
  (cycle.ps1) does not call it yet, so runner and owner installs can still differ.

## Target order

`scripts/game/load_order.py` (module doc) is the definition. Since the FAL-354 correction, it keeps any order in
which each plugin follows all its masters. If repair is needed, the earliest original line whose masters have
already been placed goes next. Markers, bridge and later-installed kits have no special priority. A valid file is
left byte-equal, with no backup or rewrite. Unticked lines stay unticked. This retains the historical valid game
order and runner orders while also accepting kits appended after markers or the bridge.

The runner's explicit `map_markers_install.py order` and `bridge_install.py order` commands still place their
components at the end; those tools are separate from launcher `play` and are unchanged by this correction.
`fix` copies the old file to `Plugins.txt.bak-<time>` before a necessary repair and never ticks or unticks a line;
both `check` and `fix` refuse (exit 6) a missing or inactive master, a master cycle or a duplicated line. In the
launcher, `load_order=fix` (the default) runs it before each start, `check` refuses to start on a different order, and
`off` leaves the file alone; `play --dry-run` only reports what `fix` would move.

## Two ride-along kits, 11 Nov 2026 (FAL-354)

**Verified offline:** at base `ba286735f320a80d10164e0327559bfb68202ba7`, the old `target()` gives markers group 1
and bridge group 2, ahead of their original line positions in the sort key. Given Mission, MapMarkers, an unticked
Bridge, PipboyProbe, RadsProbe, it emits Mission, PipboyProbe, RadsProbe, MapMarkers, Bridge. A synthetic
`plugin_toggle.py off/on` pair alone preserves that original file; adding the launcher's load-order fix reproduces
the reorder. The tests in `tests/test_plugin_toggle.py` and `tests/test_load_order.py` cover the pair and the valid
two-kit order, including BOM/CRLF and LF. Master-order repairs and missing-master/cycle refusals remain tested.

**PC timing unresolved:** the PC helper reports index 0A for the rads kit during the game, with the original order,
and the reordered file after exit. The launcher's fixer runs *before* launch. Reproducing its output does not prove
it wrote that particular post-session snapshot. `BRIDGE_OFF_RESTORED` is not a string in this source tree. Compare
the PC chain's actual commands/heads, launcher output and snapshots before attributing the observed timing.

**Save interpretation:** in the supplied snapshots Mission and NewGame do not move. MapMarkers moves behind two
active kits; the unticked bridge contributes no active load slot. Each kit moves ahead of one active plugin
(MapMarkers). A subsequent launch that uses the reordered list therefore has changed runtime indices for markers
and kits. A file rewrite during an already-running session does not establish that session's runtime indices at
save time: the reported console index is the available runtime evidence. This fix writes only Plugins.txt, not
plugin records, names or local record IDs. Existing save compatibility, including reload with the restored order,
is **NOT_RUN** here; neither corruption nor safe reload is established from the disk diff alone.

Owner test-list line: **Keep one ride-along kit installed until the preservation fix is reviewed, integrated and
the PC confirms a byte-equal two-kit session; two simultaneous kits are not cleared yet.**
