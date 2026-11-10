# Save probe prototype (not for merge)

Read-only prototype from the PC save analysis of 10 Nov 2026 (FAL-128). It reads a Starfield `.sfs` save in
memory and prints the mission quest's stage and script state, its timers, and the saved positions of the
mission actors and the player. It was validated against one 31 Oct session: positions and distances agree
with the game's own log lines.

- `sfs_lib.py`: the BCPS container (chunk table, zlib or stored chunks).
- `sfs_report.py`: heuristics for the Papyrus string table, the script type and instances, timers, the
  form-id array and actor change forms. The mission spots are hard-coded.

This is reference material for a tested tool (`scripts/game/save_probe.py`), not a tool itself: it has no
tests, its lookups are heuristic, and it assumes one mission plugin. Do not merge this folder into main.
