# Agent status

**Not live.** Each line is a snapshot with its date and source; refresh from the source before relying on it.
Live sources: GitHub issue #32 and labels (`in-progress`, `blocked`, `needs-qa`), `git log origin/main`,
docs/CODEX-HANDOFF.md, and `python tools/ai-team/guardian/guardian.py status` for the local team.

| Agent | Role | Last known activity | Source, date |
|---|---|---|---|
| Claude (remote) | collision/conversion, live game tests | deployed 15-cell build (plugin AC379C53), Parsons route run | journal, 2026-10-09 |
| Codex (remote) | deployment/recovery, IDs, door bridge modules | deploy safety fixes (`1d3d5bf`) | git log, 2026-10-09 |
| Grok (remote) | acceptance oracle | rescore of multi_next (`27a3e6d`) | #32, 2026-10-09 |
| ChatGPT (remote) | format research (.af, precombines) | `.af` profile comparison (`2f0c0a8`) | git log, 2026-10-09 |
| fo4-lead (local) | supervisor | not started: no local model yet | setup, 2026-10-09 |
| fo4-implement / fo4-research / fo4-qa (local) | specialists | not started | setup, 2026-10-09 |
