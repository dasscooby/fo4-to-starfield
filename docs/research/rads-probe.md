# Rads base probe: one value, one effect, RadAway, one route to maximum health

The owner's stage scope (10 Nov): "a base for the radiation, mutations and more". Nothing is built yet; the base is one
question first: **can a value of our own hold rads, lower maximum health, and be lowered again?** Mutations, chems and
needs hang from the same value pattern. Verified on the PC, untested in play: Starfield.esm has `ENV_*` hazards, hazard
spells and effects, `AFFL_*` affliction values and addiction effects; nothing is named mutation. Research rows R1 to R4,
C1 to C3, V1 to V5 (docs/research/framework/engine-mechanics-notes).
Task: FAL-213. Status: **run in game once (head b9ad9081); this head fixes what that session found.**

## What the first game session found (head b9ad9081, owner PC, 10 Nov 20:49 and 20:58 UTC)

* The plugin loads; our actor value `FO4SF_Rads` exists and reads 0 (Health 205, base 200). **Verified.**
* The console does **not** find the quest by its editor id (`setstage FO4SF_RadsProbeQuest 10`: "Item ... not found for
  parameter Quest"). With the form id from the init line (`setstage 0B000804 10`) stage 10 runs. **Verified.** The card
  and `make_rads_probe.py console` now use the form id.
* **Control passed**: vanilla Health 205 to 215 with `ModValue +10` and back to 205 (`Actor.ModValue` exists and works on
  Health). **Verified.**
* **Stage 20 crashed the game** (0xC0000005, a read of 0x15c in the game's own code) right after the `before` line, i.e. at
  `Spell.Cast` of our spell. **Verified.** Cause **unresolved**. Stage 10 wrote 0 to a value that is 0, so whether our value
  takes a number was not shown.

What this head changes, and why (supported hypothesis, not a finding): the spell, the effect and RadAway were written from
nothing. Read back, the spell lacked `ETYP` (equip type), the effect ids `MAGF`/`EFIF`/`MUID` and, for the effect,
`DNAM`; in the sampled vanilla records (`docs/measurements/sf_esm.json`) every one of 300 SPEL carries `OBND`, `ODTY`,
`ETYP`, `DESC`, `SPIT` and `EFIF`/`MUID` on each of 661 effect entries, and every one of 300 MGEF carries `DATA` and
`DNAM`. A null equip type or effect id read by the cast is the likeliest reading of a null at +0x15c, **but the crash
address is not mapped to any field**, so this is a guess. The writer now **copies a vanilla self-cast value-modifier spell
and its effect, and a vanilla medicine ingestible, from Starfield.esm** (found by what they are, or named with
`--template-spell` / `--template-aid`; the build prints and `plan.json` records which) and changes only the editor id, the
name, the effect's actor value and the magnitude; conditions, scripts, keywords, the effect's resist/skill values and an
addiction are cleared. If the game still crashes on `Cast`, the template choice is the next variable
(`stage --template-spell <edid>`), then the script-free route below.
Stage 10 now also writes a non-zero number (50) to our value, reads it, and writes 0 (`set` lines; the reader's
"own value takes a number" line).

## What is built

| Piece | Where |
|---|---|
| Plugin writer (build, check, fixture) | `dotnet/RadsProbe` |
| Quest script | `scripts/planet/FO4SF_RadsProbeQuest.psc` |
| Stage (precheck, stage, log, console) | `scripts/planet/make_rads_probe.py` |
| Ride-along installer, its own record `Data\FO4SFRadsProbe.install.json` | `scripts/planet/rads_probe_install.py` |
| Log reader | `src/fo4sf/rads/probe_log.py` |
| Tests | `tests/test_rads_probe.py`, `_log.py`, `_install.py` |

The installer is `rads_probe_install.py`, not `planet_probe_install.py`: that name is already the planet probe's own
installer and record. It runs `exp_install.py`'s code on a record of its own, so neither the installed core set nor the
planet probe is read or changed (a test pins both records byte for byte).

`FO4SFRadsProbe.esm`, master Starfield.esm only, adds records and overrides none. No hazard record: no writer exists.

* AVIF `FO4SF_Rads` "Rads": our own actor value on the pattern of the seven S.P.E.C.I.A.L. values in
  `dotnet/NewGame/Program.cs` (name, abbreviation, type, default, min, max, flags). Default 0, 0 to 1000, flag
  DefaultToZero. Type `Variable` (the one open choice: `stage --type DerivedAttribute` or `Resource` writes another, and
  `check` follows the same option).
* MGEF `FO4SF_RadsEffect`: archetype ValueModifier on `FO4SF_Rads`, FireAndForget, Self, instant (no duration). **One
  effect for both directions**: the magnitude is in the effect entry, so the spell uses it at +100 and RadAway at -200.
* SPEL `FO4SF_RadsSpell`: one entry, +100.
* ALCH `FO4SF_RadAway` "RadAway" (Medicine): one entry, -200. No model, sound or keywords (not needed to test the value).
* QUST `FO4SF_RadsProbeQuest`: start game enabled, stages 10 / 20 / 30 / 40, script with four properties: `RadsAV` (ours),
  `HealthAV` (Starfield.esm's `Health` AVIF, found by EditorID; `stage --health <edid>` names another), `RadsSpell`,
  `RadAway`. Properties are fine here: there are no cells and no references, so nothing is made persistent.

## The route from rads to maximum health

**Taken: the script's own permanent modifier.** After each step the script reads our value and moves Health with
`Actor.ModValue(Health, delta)` so that Health carries **minus one tenth of the rads** (100 rads: -10; 300: -30; RadAway
back to 100: -10). Simplest thing that needs no native code, no perk and no new record type. It also fits the control: the
vanilla Health value is set and read with the very same call.

Not taken, and why:

1. **A Health-modifying ability spell** (a ValueModifier effect on Health, magnitude from a global the script updates).
   More like what a game would ship, but whether a running effect re-reads its global is unknown; it needs dispel and
   recast per change. Next candidate if `ModValue` does not hold on Health.
2. **A perk entry point** (a PERK that mods maximum health from a condition on our value). The right shape for a shipped
   system and needs no script, but no writer or reading of a Starfield PERK exists in this repo (unverified).
3. **Native code** (SFSE or a hook on the rads value). Excluded by the brief (no native code); also would not run in the
   unattended chain.

## The script, step by step

The owner sets a stage from the console; the script polls the stage once a second (no `OnStageSet`: E2 in
docs/questprobe/engine-questions.md) and runs each step once.

| Stage | Step | Expected rads |
|---|---|---|
| 10 | the **control** (below), then `SetValue(rads, 50)` read back and `SetValue(rads, 0)` | 0 |
| 20 | the spell, once | 100 |
| 30 | the spell, twice | 300 |
| 40 | `AddItem` + `EquipItem` RadAway | 100 |

Every reading logs `rads`, `health` (`GetValue`), `base` (`GetBaseValue`), `max` (`GetValueMax`), `applied` (the route's
modifier) and `fx`, **the ids of the active magic effects on the player** (to see whether Starfield's own radiation acts in
our world). `base`, `max` and `fx` are **optional readings** (`;OPT` lines): `make_rads_probe.py precheck` looks each name
up in Starfield's base scripts, `stage` compiles each declared one on its own, keeps those that compile and records the
fate of every one in `plan.json` (`optional`); one that does not exist logs `na` and the reader says so. `Actor.ModValue`
is optional too: if it does not exist, the control fails and the session is **INCONCLUSIVE**, by design. Required natives
(`GetValue`, `SetValue`, `AddItem`, `EquipItem`, `Spell.Cast`, the log and timer calls) stop the stage when missing.
`Actor.SetValue/GetValue` with an own AVIF and `AddItem/EquipItem` were compiled on the PC by the new game script.

Per step: *before*, *now* (right after the call), *settled* (3 s later, the effect has had its time), a `fix` line (was the
step's number there, or did the script **force** it with `SetValue`, `forced=true`, so that the route is still tested when the
effect does nothing), a `route` line, *routed*, and *final* 3 s later. Each line ends `end=true`; a line without it was cut.
The log is `My Games\Starfield\Logs\Script\User\FO4SFRadsProbe.0.log`, under `OneDrive\Documents` on the owner's PC (the reader tries that first, then `Documents`; `--file` names it).

**Offline tests** use a synthetic Starfield.esm (with synthetic template records), a fake compiler and fake base sources. The Mutagen shapes of the MGEF archetype (the actor value sits in
`Association`), the ingestible and the AVIF are checked by read-back through Mutagen only; whether Starfield accepts them
is the session's question.

## The reader

`python scripts\planet\make_rads_probe.py log` prints one table (a row per reading: stage, when, rads, health, base,
max, applied, effects), the control, one line each for effect, route and RadAway, notes, and a last line.

**The control comes first**: a vanilla actor value (Health) set and read in the same step with the call the route uses
(`ModValue +10`, read, `-10`, read, at stage 10). When the call was not made, the read did not move by +10 or did not come
back, or there is no start or control line, the verdict is `INCONCLUSIVE: control failed: <why>` and nothing is judged.
Otherwise `CONTROL OK` and:

* effect: each of stage 20 and 30 "gave N without help", "did not move the value (...); the script forced it" or "moved it
  to X, not N; the script forced it"; RadAway likewise.
* route: the maximum health (the `max` reading, else `base`, else `health`; the source is named and `health` is only the
  current value) at the end of stage 10 against the ends of stages 20, 30 and 40: moved by the expected tenth of the rads,
  unchanged, or by another amount.
* active effect ids at a stage that were not there at stage 10 are listed. The log cannot say which id is radiation:
  the owner looks the ids up. Exit 0 when the control held, 1 when inconclusive, 2 with no log.

## Install and read (the owner's word, game closed)

    python scripts\planet\make_rads_probe.py precheck
    python scripts\planet\make_rads_probe.py stage --out <dir>
    python scripts\planet\rads_probe_install.py install --dir <dir> --starfield <game dir>
    ... session ...
    python scripts\planet\make_rads_probe.py log
    python scripts\planet\rads_probe_install.py uninstall --starfield <game dir>

## Session card

Tick the probe in the load order. Each step runs **once per script instance**: a retry needs a new game start (variant A)
or a reload of the save made before stage 10 (variant B).

### Variant A: no save (throwaway state; do not save, autosave, quicksave or save on exit)

Start the game with the probe ticked and wait until the log has an `init` line (the quest starts with the game). The console
does not find the quest by name: get this session's lines with

    python scripts\planet\make_rads_probe.py console

which prints `setstage <quest form id> 10` to `40` and the two `player.getav` lines (the form id follows the load order, so
take it fresh each session). Below, `<Q>` is that form id. Open the console (`~`).

1. `player.getav FO4SF_Rads`  (expect 0) and `player.getav health`. Note both. Screenshot `00-start`.
2. `setstage <Q> 10`. Wait 10 s. Then `player.getav FO4SF_Rads`, `player.getav health`. Screenshot `10`.
3. `setstage <Q> 20`. Wait 10 s. The same two console lines, screenshot `20` (the HUD, the health bar, any
   message or effect icon).
4. `setstage <Q> 30`. Wait 10 s. The same two lines, screenshot `30`.
5. `setstage <Q> 40`. Wait 10 s. The same two lines, screenshot `40`. Open the inventory once: is there
   a RadAway left, and does the effect list or Pip-Boy/Scanner show anything?
6. Quit to the desktop **without saving**. Run the reader command above and paste its output with the screenshots.

### Variant B: save and reload (only where the owner allows a save)

Does the value, and the route's effect on Health, survive a save? Use a character that may be saved.

1. Steps 1 to 4 of variant A (stages 10, 20, 30; rads 300, Health carrying -30). Note the console reads at 30.
2. Save by hand (name it `rads-30`). **Do not** set stage 40 yet.
3. Quit to the desktop. Start the game, load `rads-30`. Wait 10 s.
4. `player.getav FO4SF_Rads`, `player.getav health`. Screenshot `31-reloaded`. Are they the values at 30 (300 and
   the reduced health) or defaults (0 and the original)?
5. `setstage <Q> 40`. Wait 10 s. The same two lines, screenshot `40`.
6. Quit **without saving**. Run the reader command. The user log may have started a new file after the reload: run
   `make_rads_probe.py log --file` on each file, and paste both. Lines after the reload carry no `init`; that is expected.

## What the answers decide

* Control OK, effect gave the numbers, route moved max health, RadAway lowered it, route gave it back: the value pattern
  works end to end with no native code; mutations, chems and needs can use it. Next: hazards, and whether a save keeps it.
* Effect does nothing but the forced steps are fine: our AVIF works, the effect/spell shape needs work (R-rows on MGEF).
* Control fails: `ModValue` is missing or Health is not set that way; take the route alternatives 1 or 2 above.
* Route moves `health` but not `max`/`base`: the permanent modifier does not touch the maximum; alternative 1 or 2.
* `fx` lists effects at stage 20 and later that are not ours: Starfield's own radiation or hazard logic acts on a value
  named like ours, or something else applies at the same time; look the ids up before the next step.
