# Preparing the Fallout shell and the move off Mars

Owner-requested preparation, 1 November 2026, tracked in [#664](https://github.com/fo4sf/fo4-to-starfield/issues/664).
Source baseline: `d07ba146`. This is a test handoff, not an installer or a native acceptance result.
Codex prepared it offline on Windows; Claude PC retains game and deployment control.

## The intended world

The [roadmap](../ROADMAP.md#update-19-october-2026) puts the Commonwealth, Far Harbor and Nuka-World on one Earth-like
planet. Mars is the current host and a useful control, not the final setting. One planet does not require the three
regions, every interior and every simulation area to become one WRLD record or one continuously loaded area.
The [world research](../research/framework/world-and-planet.md) keeps those distinctions and the later travel choices.

There is already an [own-planet probe](../planet/planet-probe.md). Route A loaded our planet on 29 October, but its
references stayed behind or were not found; that is not a passed Commonwealth migration. Route B puts a new test
planet in Sol. Its template properties and orbit are experimental, not the final Earth settings. The important next
question is whether the test world and its temporary/persistent references actually join the player's world there.
Moving every Commonwealth system before that answer would move the same unresolved problem to another host.

## Preparation completed

The fresh private route-B candidate was built from the baseline above using the existing tool:

- Papyrus precheck, `stage --system sol` and `check --data` all returned zero. The selected C# projects built and the
  diagnostic Papyrus script compiled. Four plugins, the biome maps, terrain and overlay mask are pinned in `plan.json`.
- A read-only audit parsed 22 installed/candidate plugin headers: none unreadable, no master **file** missing.
  This does not prove activation order or account for runtime script/native/asset dependencies.
- Installed top-level plugin/archive/receipt metadata and the Plugins.txt SHA-256 were identical before and after
  staging. This observation is not a recovery snapshot and says nothing about native play.
- **Full four-arrival ladder: HOLD.** This PC census found no COC cells for TempJemisonWorld or NewAtlantis, so this
  candidate's plan lists only LC172 and our planet. Do not invent commands or report four controls as staged. Claude
  must either bind the two missing controls to verified destinations or explicitly run and report the bounded
  two-arrival experiment. The latter does not close the missing controls.

The private kit path and hashes are in the desktop checkpoint. No staged asset, extracted script, installed inventory
or local settings belong in this repository. Nothing was installed, stopped, unticked or removed.

## Strip one layer at a time

The companion [matrix](fallout-shell-matrix.json) records dependencies and required evidence; it contains no executable
actions. Order is for isolating failures, not a new authorization gate. Independent offline preparation can overlap.

| Step | Change to test | Keep while testing | Evidence needed |
|---|---|---|---|
| S0: recovery baseline | None; pin the exact candidate and installed state at the game-closed handoff | Existing recovery sources and installer records | Fresh snapshot, readable unchanged source stages and pins, dry-run restore without conflicts; a recovery rehearsal before destructive trials |
| S1: vanilla error control | Existing baseline tool temporarily disables non-built-in plugins in its recorded run | Official plugins/archives, player files and baseline lock/open-note controls | One plain New Game/log capture and exact profile restoration, following the existing baseline card |
| S2: Fallout startup | Existing NewGame startup and only its reviewed hold list | Character creation, controls, HUD, saving, actor/AI and service systems until individually audited | New disposable save reaches Vault 111 and Sanctuary; saving/loading and HUD work; compare Papyrus errors with S1 |
| S3: own-planet references | Existing route-B PlanetProbe, independently of broader strip-down | Vanilla LC172 control and its masters; current Mars build retained for recovery | Actual planned arrivals, full dwell/readings, T1-T6 and MERGE/LC172COC identities; missing controls explicit; restore and verify |
| S4: content and travel restrictions | One reviewed quest/system/map restriction per candidate | Record masters, scripts and assets that retained Fallout and engine systems still use | Before/after quest and map readings, preserved Fallout start/doors/AI/save smoke checks, explicit uncertainty about unseen runtime references |
| S5: Commonwealth host migration | A separately reviewed core/registration and dependent-plugin build on the proven host | Old build/stages, persistent identity history, paired core/port recovery | Correct host/frame, actor/marker resolution, interior OUT/IN legs and save/reload; compatible identities or an explicit new-save migration boundary |

S1 reuses [baseline.py and its runbook](baseline.md), not another profile-changing tool. S2 reuses
[the existing startup](../newgame/vault111-start.md#13-our-own-start-newgame_v11-29-oct-2026-what-run-4-must-show).
The current startup/hold list is not evidence that every Starfield start-game quest has been suppressed. Classify the
remaining quests by concrete dependencies and test small changes; a quest's unfamiliar name is not a removal rule.

## What stripping means here

Keep `Starfield.esm`, required masters, archives, Papyrus/native runtime, actor/navigation/animation, physics,
controls, time, menus needed by retained features and save/load support. The first implementation should prevent
unwanted story/content/travel from participating, while preserving the underlying records and assets its replacement
still needs. A header master graph alone cannot authorize removing an archive or a service quest.

Hiding whole star systems is not proof that other individual Sol planets can be hidden while keeping ours.
[#583](https://github.com/fo4sf/fo4-to-starfield/issues/583) and
[#586](https://github.com/fo4sf/fo4-to-starfield/issues/586) leave that case unresolved. Do not turn a community mod's
description into an accepted record-edit recipe or delete vanilla planet records to make the map look finished.
The broader map restriction is separate from proving that our own planet loads correctly.

## Claude PC handoff

Use an isolated Windows PowerShell checkout of the recorded source. Read
the environment handoff (`Join-Path $env:USERPROFILE 'Desktop/codehell/ENVIRONMENT-HANDOFF.md'` in PowerShell)
and its current checkpoint; use this PC's tools and paths.
The owner has requested preparation here; a live swap/test remains with Claude under a separately explicit release.
Coordinate with the current P9 session rather than changing its installed probe or reusing its save.

These preparation commands write only a **new staging folder**; they do not install:

```powershell
# Set $sf and a NEW $stage explicitly for the authorized PC environment.
python scripts\planet\make_planet_probe.py precheck --content-resources "$sf\Tools\ContentResources.zip"
python scripts\planet\make_planet_probe.py stage --data "$sf\Data" --out $stage --system sol `
  --content-resources "$sf\Tools\ContentResources.zip" `
  --compiler "$sf\Tools\Papyrus Compiler\PapyrusCompiler.exe"
python scripts\planet\make_planet_probe.py check --stage $stage --data "$sf\Data"
```

Before an authorized live run, use the supported snapshot/restore tooling from
[the launcher backbone](../ai/launcher-backbone.md#recorded-restore), and recheck the candidate against current Data.
Capture a fresh log/session identity so previous planet/P9 readings cannot count as this run. Honor `plan.json`'s
actual arrivals, the 75-second dwell and 10/60-second readings in the existing probe card. Do not infer success from
the generic `log` command's exit code: inspect all reference, location-chain and arrival results.

Return a short table: exact candidate/source/input pins; native results for each planned arrival and T1-T6; controls
not run; any new errors; restoration verification. A failure keeps partial outputs, logs, reservations and the prior
build. Never reset identities, silently roll back a partial result, or remove the only recovery source.
