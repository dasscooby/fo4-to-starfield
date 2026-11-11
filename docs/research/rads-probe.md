# Rads base probe: one value, one effect, RadAway, one route to maximum health

The owner's stage scope (10 Nov): "a base for the radiation, mutations and more". Nothing is built yet; the base is one
question first: **can a value of our own hold rads, lower maximum health, and be lowered again?** Mutations, chems and
needs hang from the same value pattern. Verified on the PC, untested in play: Starfield.esm has `ENV_*` hazards, hazard
spells and effects, `AFFL_*` affliction values and addiction effects; nothing is named mutation. Research rows R1 to R4,
C1 to C3, V1 to V5 (docs/research/framework/engine-mechanics-notes).
Task: FAL-213. Status: **run in game five times; the crash is fixed; our spell has not yet moved the value; this head keeps Detrimental, flags the value damage-is-positive and builds RadAway as a mirror when a restore effect is found (an ingestible's or, on the real file, a spell's), else as the old shared -200 fallback.**

## What the first game session found (head b9ad9081, owner PC, 10 Nov 20:49 and 20:58 UTC)

* The plugin loads; our actor value `FO4SF_Rads` exists and reads 0 (Health 205, base 200). **Verified.**
* The console does **not** find the quest by its editor id (`setstage FO4SF_RadsProbeQuest 10`: "Item ... not found for
  parameter Quest"). With the form id from the init line (`setstage 0B000804 10`) stage 10 runs. **Verified.** The card
  and `make_rads_probe.py console` now use the form id.
* **Control passed**: vanilla Health 205 to 215 with `ModValue +10` and back to 205 (`Actor.ModValue` exists and works on
  Health). **Verified.**
* **Stage 20 crashed the game** (0xC0000005, a read of 0x15c in the game's own code) right after the `before` line, i.e. at
  `Spell.Cast` of our spell. **Verified.** Cause: see the second session below. Stage 10 wrote 0 to a value that is 0, so whether our value
  takes a number was not shown.

## The second session (head 41d3f968): cause found

Same crash at stage 20 (0xC0000005, read of 0x15c at `Starfield.exe+0x17850f4`), with the spell and effect already copied
from vanilla records. Stage 10 passed, **including our own value taking a number**: `wrote=50 read=50`, then `wrote=0 read=0`.
**Verified.** The owner PC's reading of the crash dump (a disassembly reading, not a game test): at `Spell.Cast` the engine
starts our effect, asks its MGEF for its **actor value**, gets null, and reads that actor value's flags.

* The effect's actor value is **DATA word 14** of the MGEF (Mutagen: `MagicEffect.SecondActorValue`). 321 of Starfield.esm's
  853 effects carry an AVIF there (`RestoreHealthFood_OBSOLETE` -> Health); 72 carry one in word 16 (the resist value);
  **none in word 0**, the archetype's `Association`, which is where both earlier kits put our AVIF. The owner PC's count of Starfield.esm, not re-run here; the template copy even dropped the template's own value. Word 14 stayed 0.
* This head sets `SecondActorValue` to our AVIF (and leaves the association empty, as every vanilla value modifier does).
  `check` now **fails the kit** when the MGEF's actor value is not our AVIF, when the association is set, or when a resist,
  skill or third actor value is named; a test reads word 14 out of the raw bytes and another corrupts it and expects `check`
  to refuse. Each of the two crashes would have been caught offline.
* **Sign of the magnitude** (the same disassembly, untested in play): the engine negates an effect's magnitude when exactly
  one of two flags is set, the MGEF's `Detrimental` (0x4) and the actor value's "damage is positive". Our AVIF has only
  `DefaultToZero`, so this head **clears `Detrimental`** on the effect (both on the template copy, which otherwise keeps the
  template's flags, and on the no-template path): neither flag is set, the spell should give **+100** and RadAway **-200**.
  If stage 20 shows a negative sign, the other choice is `Detrimental` on and the AVIF flagged damage-is-positive (how Fallout 4
  declares Rads).
* Side fact: the first template's actor value `000002E0` has no AVIF record in Starfield.esm (1107 AVIF, none with that id).

Since the first session the writer **copies a vanilla self-cast value-modifier spell and its effect, and a vanilla medicine
ingestible, from Starfield.esm** (found by what they are, or named with `--template-spell` / `--template-aid`; the build
prints and `plan.json` records which) and changes the editor id, name, the effect's actor value and the magnitude;
conditions, scripts, keywords, resist/skill values and an addiction are cleared. That alone did not stop the crash (above).
## The third session (head 5e6ae1bc): the crash is gone, the effect does nothing

Owner PC run, all four stages, no crash. **Verified in the game log:** control OK; our value takes 50 and 0; `Cast` ran
(`rads=0` three seconds after, so the spell did not move the value; the script forced 100); the two casts and RadAway by
`EquipItem` likewise left the value where it was (forced to 300 and 100); the script's own route works (rads 100 / 300 / 100:
Health 195 / 175 / 195, `applied` -10 / -30 / -10). `fx na`: no list of active effects exists to read.
Two honest limits: the route **lowers current Health, not the maximum** (`GetValueMax` is not declared in Starfield's
scripts and `base` stayed 200), so "lower maximum health" is **not shown**; and whether RadAway's `EquipItem` consumed the
item at all is not shown either (the value did not move, and the log has no inventory reading).
Why the effect does nothing (**the owner PC's reading of the records, untested**): the loose template was a timed effect
that recovers, our entry has duration 0, so the change is applied and taken back at once. The strict template search
(fire and forget, self, no duration) found none.
This head makes the effect **instant and non-recovering** (`NoDuration` set, `Recover` cleared, `Detrimental` still clear);
`check` refuses a kit that is not, and compares every other flag with the template. One cheap experiment, one game session.
**If the value still does not move**, the next step is not another flag: it is the owner PC's proposal, the script owns the
value and a consumable reaches it through a script effect (an effect whose script calls `ModValue` on start) or through an
item that calls the script directly, or an instant vanilla template found by search (every MGEF whose DATA word 14 is an
AVIF and whose spell entries have duration 0). The hand kit (#719) should not be handed over until this is settled.

Stage 10 now also writes a non-zero number (50) to our value, reads it, and writes 0 (`set` lines; the reader's
"own value takes a number" line).

## The fourth session (head 88e99c4d): the vanilla spell works, ours does not

Owner PC run with `--control-spell DamageHealthSpell` (0029AAE9: one effect, `DamageHealthContact` on Health, magnitude 40,
duration 0). **Verified in the game log:** no crash; the vanilla spell, cast by the same script, moved Health 6195 to 6155
(-40): **`Cast` from a quest script applies value modifiers**. Our spell (stages 20, 30) still moved nothing, so the fault
is in our records. The two spells differ in `ETYP` (`00013F43` ours, copied from the artifact power; `00013F44` the working
one) and in `SPIT` (ours 15 and 1 in the first two words, byte 14 zero; the working one 0, 0 and byte 14 one). Why ours is
refused is **unresolved**: the owner PC's guess is a cost the player cannot pay, or the delivery byte; neither tested.
RadAway (stage 40) **did** apply, about once per frame: 300 x -200 = -59,700 read after the settle, then -59,900 after the
script's force. The AVIF minimum (0) is not enforced for a change made by an effect. **Verified** (the readings); "once per
frame" is a reading of the size, frames not counted. Cause: with `NoDuration` set and `Recover` cleared on a timed template the
effect stayed live and subtracted every update.
This head: the effect and the spell are copied from **`DamageHealthSpell` and its effect** (preferred; the build prints
`templates (preferred)`; `--template-spell` still overrides) with only the actor value changed and `Detrimental` cleared; the
effect's own duration flags are **kept** (the forced `NoDuration` / no `Recover` of 222e2a45 is gone, `check` compares every
other flag with the template). RadAway's item template prefers a vanilla medicine whose one effect has duration 0. The script
**clamps our value at 0** before the route (`clamped=true` in the route line), and the reader notes a value below zero or a
clamp. Untested in play. The `Detrimental` clearing is the sign rule (owner PC's disassembly reading): `DamageHealthContact`
presumably carries it (Health lost 40 with magnitude +40), so without clearing it ours would be negative.

### The one flag bit that differs from the template (9bc3ec25, owner PC's read-back; **superseded by the fifth session below: Detrimental is now kept**)

The staged effect's DATA words 24 to 26 read `00000003 00000101 09013F80`; the template `DamageHealthContact` has `09053F80`.
The difference is the bit `0x00040000` of word 26, the bit `0x4` of the upper half (`0x0905` against `0x0901`). In Mutagen's
`MagicEffect.Flag` that bit is **`Detrimental`** (`Hostile 0x1`, `Recover 0x2`, `Detrimental 0x4`, ...; read from the
enum), and it is the only flag the writer clears. The check prints the copy's flags as `Hostile, DispelWithKeywords, NoArea`,
which are exactly `0x901` (`0x1 + 0x100 + 0x800`); with `Detrimental` the template reads `0x905`. **That the upper half of
word 26 is the flags field is an inference** from these numbers matching, not a layout read from Starfield's format.
Why it is cleared: the owner PC's reading of the engine (disassembly, not tested in play) negates an effect's magnitude when
exactly one of the effect's `Detrimental` and the actor value's "damage is positive" is set. The vanilla spell lowers Health
by its +40 magnitude, which fits `Detrimental` set on a value without the other flag; our value (`AVFL 00000400`) lacks
the second, so with `Detrimental` kept the spell would give -100 and the value would stay at 0; cleared it should give +100.
If stage 20 shows a negative sign, set `Detrimental` again and flag the AVIF damage-is-positive instead.

## The fifth session (head c5412b0c): the last difference was Detrimental

Owner PC run, no crash. **Verified in the game log:** our SPEL was byte for byte `DamageHealthSpell` in `SPIT` and `ETYP`, and our
MGEF equalled `DamageHealthContact` except the actor value (word 14) and the **cleared Detrimental bit**; the vanilla spell
(stage 50) took 40 off Health and kept it off; **ours still moved nothing** (stages 20 and 30 forced to 100 and 300); RadAway
(stage 40) again read -59,700 (300 x -200 in the 3 s settle, then -59,900); the new clamp worked (Health stayed 205).
The owner PC's reading (**untested; it fits all five sessions**): in this engine a Detrimental value modifier with no
`Recover` is *damage* that lands once and stays; a non-Detrimental one is a *buff for its duration*, which with duration 0 is
applied and taken back at once. An effect on an ingestible is a third behaviour (kept and repeated every update).
This head changes exactly what that reading says to change, and nothing else:
1. **`Detrimental` is kept** on our effect (the template's flags are kept untouched; our MGEF now differs from
   `DamageHealthContact` in the actor value (word 14) and in what `CopyEffect` clears on purpose: resist, skill and third values, keywords,
   conditions, the script and the counter effects, with the archetype rebuilt as a plain value modifier; the owner PC's read-back of the
   staged DATA, not of those other fields, is what showed word 14 and the flag bit). `check` compares every flag with the template.
2. **The value is flagged "damage is positive"** (`AVFL` bit 26, `0x04000000`, Mutagen `DamageIsPositive`, Fallout 4's own way of
   declaring Rads; the AVIF now reads `DefaultToZero | DamageIsPositive`). By the sign rule the owner PC read from the engine
   (negate when exactly one of the effect's Detrimental and the value's bit 26 is set), Detrimental + bit 26 is **no
   negation: +100 stays +100**. With bit 26 left clear the same effect would give -100; the raw read at stage 20 (`settled`,
   before any force) shows whichever sign it is.
3. **RadAway is the mirror**: its own effect, `FO4SF_RadAwayEffect`, a copy of a vanilla *restore Health* effect (value
   modifier on Health, **not Detrimental**, an entry of duration 0 in a vanilla ingestible; found by search, or named with
   `--template-aid`), pointed at our value, at **+200**. By the same rule a non-Detrimental +200 on a damage-is-positive value
   becomes -200 on the number. At head 9cba25ad the search looked at ingestibles only; the owner PC's build on the real
   Starfield.esm then took the **fallback** (the real file has one Health ingestible, `ShipRepairKit`, entry duration 10): one
   MGEF, RadAway at -200 in the ShipRepairKit shell, so stage 40 would not have tested the mirror (found in review FAL-318).
   This head also takes the restore effect from a **spell** when no ingestible has one (`Dueling_RestoreHealth_Spell`
   001E1171 first), copies it into RadAway's own effect, and tests the three paths (ingestible, spell, fallback) on three
   synthetic masters. **Not confirmed on the real file**: that the spell path finds a match there.
4. Stage 50 and the clamp stay.
If stage 20 then reads 100 **without the script's force** (`fix ... forced=false`), the base is settled: rads is damage on a
value that counts up, as in Fallout 4. If it still reads 0, the remaining suspect is that a value modifier from a spell does not
act on a plugin's own AVIF at all, and the script-owned route is the base (a script effect that calls `ModValue`, or an item
that calls the script). With the mirror the plugin holds two MGEFs (the spell's and RadAway's); the brief's "one effect" held until here. With the fallback
it holds one.
Still not shown: that the route lowers **maximum** Health (it lowers the current value), and that RadAway's `EquipItem` consumes the
item.

## The sixth session (head 9cba25ad): the spell moves the value

Owner PC run on the real Starfield.esm with `--control-spell DamageHealthSpell`. **Verified in the game log:** stage 20 read
**rads 100** and stage 30 **rads 300** three seconds after the casts, **with no force** (`forced=false`); the route then lowered
current Health 205 to 195 and 175 (`applied` -10, -30); stage 50's vanilla spell took Health 165 to 125. So a value of our own
**takes a spell's change and holds it**; this is the base's first answer. **Which of the two changes did it is not separated**:
the effect's `Detrimental` bit was kept and the value flagged `DamageIsPositive` in the same head.
RadAway (stage 40) did **nothing** on that head: the real file took the fallback (old shell, shared Detrimental effect, -200), and
a negative magnitude on a Detrimental effect moved nothing. The head after it (6925a548) builds the mirror from a spell's restore
effect instead; **not yet run in the game**.
Two faults of the script and the reader, found in the same table and fixed in this head:
* **The force was wrong:** `fix stage=40 forced=true want=100 had=300 now=400`. **Arithmetic reading, untested:** `SetValue`
  writes the base while the cast's change is kept apart from it, so the value read 100 + the 300 already stored. At stage 10 the
  stored part was 0, which is why `SetValue 50` read back 50. The force is now a **difference** (`ModValue(want - have)`),
  which reaches the number whichever of the two the call moves; `SetValue` only when `ModValue` is not declared. The `fix`
  line says `how=ModValue` or `how=SetValue`.
* **The reader's "base unchanged at 200" was misleading:** the route lowers **current** Health (195, 175, 165) and the base never
  moves. With no maximum reading (`GetValueMax` is not declared) the reader now judges the route on current Health, names that
  in a note ("not the maximum") and lists the base readings.
Still not shown: that the route lowers **maximum** Health, that RadAway lowers the value, and an active-effect list (`fx` is `NA`).

## The seventh session (head bc2e8a57): the force works, RadAway still moves nothing

**Verified in the game log (owner PC):** spell 100 and 300 unforced again; the force by difference took 300 to 100
(`how=ModValue`) and the route followed back up (Health 175 to 195); the vanilla control worked. RadAway with the mirror effect
(`FO4SF_RadAwayEffect`, not Detrimental, +200) left rads at 300. Across sessions: old shell with a non-Detrimental shared effect
applied about once a frame (-59,700); shared Detrimental effect at -200 did nothing; mirror at +200 did nothing.
**Unresolved:** whether `EquipItem` used the item up at all (the probe did not log the count). This head adds
`item stage=40 when=added|now|settled count=N`; the reader appends `item count a to b: consumed|NOT consumed` to the stage 40
line, so "not consumed" and "consumed, effect inert" separate in one run. **Not taken yet:** a script effect or a quest-handled
use (`ModValue(-200)`, remove one), which would make RadAway work whatever the effect does; and a RadAway spell cast from the
script as a control beside the item. Both are named in Claude's note and left for the result of this run.

## The eighth session (head 216667ed): RadAway is consumed and its effect is inert

**Verified in the game log (owner PC):** `item` counts 1, 0, 0 (`EquipItem` uses the item up at once); rads stayed 300 through the
3 s settle; the force (`how=ModValue`) then took it to 100. So the item is used and a non-Detrimental +200 effect from an ingestible
changes nothing on our value, while `ModValue` and a Detrimental duration-0 spell do move it. **Unresolved:** whether the effect
is inert on our value in general or only as delivered by an ingestible (needs the restore effect cast as a spell; **not built**,
it needs a writer change).
**Route taken (head after this one):** RadAway's use ends in the script. In stage 40, when the item's own effect left the value
where it was, the script applies `ModValue` of -200 (clamped at 0). The `radaway` line logs `item_had` (the item's own result),
`applied`, `delta` and `now`; the reader says "the item's own effect did not move the value (still 300); the script route (ModValue -200)
took it to 100". This is **not the pure effect**: the item's effect stays a research line. Not run in the game.

## Second control: a vanilla instant effect (stage 50)

Asked by the owner PC so one session separates "our effect is wrong" from "Cast on the player from a quest script applies no
value modifier at all". `stage --control-spell <SPEL editor id>` binds a fifth, optional property, `ControlSpell`; stage 50
reads Health, casts that vanilla spell on the player, reads Health 3 s later and logs one `vcontrol` line; the reader prints
"stage 50 vanilla control": Health moved (Cast works, so our effect is at fault), Health did not move (Cast may apply no
value modifier from a script at all), or not run. Not part of the verdict line and not run without the option. Candidate
wanted: a self-cast SPEL whose one effect is a value modifier on Health (MGEF DATA word 14 = Health) with an EFIT duration of
0 (instant), editor id named by the owner PC from Starfield.esm; nothing here reads Starfield.esm.
Console: `setstage <Q> 50` (the `console` command prints it).

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
  `dotnet/NewGame/Program.cs` (name, abbreviation, type, default, min, max, flags). Default 0, 0 to 1000, flags
  `DefaultToZero | DamageIsPositive` (since the fifth session). Type `Variable` (the one open choice: `stage --type DerivedAttribute` or `Resource` writes another, and
  `check` follows the same option).
* MGEF `FO4SF_RadsEffect`: a copy of the vanilla `DamageHealthContact`, the actor value (DATA word 14) changed to ours and its
  own flags kept (`Detrimental` included), archetype ValueModifier, association empty. The spell uses it at +100.
* SPEL `FO4SF_RadsSpell`: a copy of the vanilla `DamageHealthSpell`, one entry, +100.
* ALCH `FO4SF_RadAway` "RadAway" (Medicine): the shell of a vanilla medicine (on the real Starfield.esm `ShipRepairKit`), one
  entry. **Two shapes**, chosen at build time and printed in the build's `templates` line and in `plan.json`:
  *mirror*: its own effect `FO4SF_RadAwayEffect`, a copy of a vanilla restore-Health effect (not Detrimental, entry duration 0) found on
  an ingestible or, when no ingestible has one, on a spell (`Dueling_RestoreHealth_Spell` on the real file; `--restore-spell`
  names another), pointed at our value, at **+200** (the plugin holds two MGEF); *fallback* (no restore effect anywhere): the
  rads effect shared, at **-200** (one MGEF). The real Starfield.esm has one Health ingestible only (`ShipRepairKit`, entry
  duration 10), so the ingestible search never matches there; whether the spell search does is **not confirmed offline** (the
  owner PC's scan names `Dueling_RestoreHealth_Spell` 001E1171, which this build looks for by that editor id first). The
  fallback is covered by a test since this head. No sound or keywords (not needed to test the value).
* QUST `FO4SF_RadsProbeQuest`: start game enabled, stages 10 / 20 / 30 / 40 / 50, script with four properties: `RadsAV` (ours),
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
step's number there, or did the script **force** it, `forced=true`, by the difference with `ModValue` (`how=ModValue`; `SetValue` only
when `ModValue` is not declared), so that the route is still tested when the effect does nothing), a `route` line, *routed*, and *final* 3 s later. Each line ends `end=true`; a line without it was cut.
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
* route: the maximum health (the `max` reading, else `health`; the source is named, `health` is only the current value and the
  report says so; the base is not used, only listed in a note) at the end of stage 10 against the ends of stages 20, 30 and 40: moved by the expected tenth of the rads,
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

## By hand (FAL-273): no console, messages on screen

The same plugin carries a second quest, `FO4SF_RadsHandQuest` (script `FO4SF_RadsHandQuest.psc`), and a test item, ALCH
`FO4SF_RadDose` "Rad Dose" (a copy of the same vanilla template as RadAway, the same effect at **+100**). Nothing needs a
stage: the probe's own quest sits idle until a stage is set. The script gives three RadAway and three Rad Dose once (at the
quest's first run), then polls once a second and shows, on every change of our rads value, `Rads 100, max health 190`
(`max health` is Actor.GetValueMax when the game has it; otherwise the text says `health N`, the current value). Health
carries minus a tenth of the rads, as in the probe, so 100 rads show 10 lower than before. When an item is used and the
value is not what the effect should have given 3 s later, the screen says `Rad Dose used, but rads stayed 0 (expected 100).
Setting 100` and the script sets the value, so the health part is still seen. Every message is also a line in
`FO4SFRadsHand.0.log` (`FO4SFRADSHAND ... end=true`). Offline only: the script's compile and the game are the PC's.

### Owner card (eight steps, no console)

1. Tick `FO4SFRadsProbe.esm` in the load order and start a new game (or load a save you may throw away; do not save).
2. After the intro, wait 10 s. Messages: "Rads kit: 3 RadAway and 3 Rad Dose added ..." then "Rads 0, max health N". Write N down.
3. Open the inventory (Aid or Medicine): is there a **Rad Dose** and a **RadAway**, three of each?
4. Use one **Rad Dose**. Within 5 s a message: "Rads 100, max health ...". Max health should be 10 lower than N.
5. Use a second Rad Dose. Message "Rads 200, ...", max health 20 lower than N.
6. Use one **RadAway**. Message "Rads 0, ..." (200 minus 200), max health back to N.
7. Watch for a message that says "used: the effect left rads at X, expected Y": that means the item's effect gave a wrong number (the PC run of the probe saw RadAway applied once per frame, rads -59,700) and the script set the right one. Until the 3 s settle the screen shows nothing for that item, and rads are kept between 0 and 1000 by the script. Screenshot the message.
8. Quit without saving. Screenshot each message you saw (or write them down), and tell which of steps 4 to 6 showed a message.
