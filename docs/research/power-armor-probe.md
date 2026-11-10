# Power armor probe: does Starfield still run Fallout 4's power armor path?

Research questions A1 to A5 and P1, P2 (docs/research/framework/engine-mechanics-notes/character-systems.md and
fo4-systems-internals.md). Verified on the PC, untested in play: Starfield's own `Actor` script declares
`SwitchToPowerArmor(ObjectReference aArmorFurniture) native`, and Starfield.esm has `FurnitureTypePowerArmor`,
`isPowerArmorBattery`, `LinkPowerArmor`, `PowerArmorKeyword_DO` and `fPowerArmorWorkbenchMaxPowerArmorDistance`.
One session decides whether the climb-in suit (Fallout 4, combined core) is script-only or needs a body swap.
Task: FAL-212. Status: **built offline, not run in game** (no Starfield.esm, no Papyrus compiler, no game on the build box).

## What is built

| Piece | Where |
|---|---|
| Plugin writer (build, check, fixture) | `dotnet/PowerArmorProbe` |
| Quest script | `scripts/planet/FO4SF_PAProbeQuest.psc` |
| Stage (precheck, stage, log) | `scripts/planet/make_power_armor_probe.py` |
| Ride-along installer, its own record `Data\FO4SFPowerArmorProbe.install.json` | `scripts/planet/power_armor_probe_install.py` |
| Log reader | `src/fo4sf/powerarmor/probe_log.py` |
| Tests | `tests/test_power_armor_probe.py`, `_log.py`, `_install.py` |

`FO4SFPowerArmorProbe.esm`, master Starfield.esm only, adds records and overrides none:

* CELL `FO4SF_PAProbeCell` (`coc FO4SF_PAProbeCell`), an interior with TestCell's platform floor and lights and a COC marker.
* FURN `FO4SF_PAProbeSuit`: **a copy of the control furniture** (default `NPCChairTech03_Free_270`, change it with
  `stage --control <editor id>`; every field of it) **plus one keyword, `FurnitureTypePowerArmor`**. Nothing else differs, so
  an effect, or none, is the keyword's. It is placed 2.5 units to the right of the arrival.
* The control: the vanilla furniture itself, 2.5 units to the left. The player must sit on it.
* RACE `FO4SF_PARace`: a copy of HumanRace (own plain-string name; skeleton and graph unchanged).
* QUST `FO4SF_PAProbeQuest`: start game enabled, stages 10 / 20 / 30, the script, no properties (every form is found with
  `Game.GetFormFromFile`, so the temporary references stay temporary).

The script polls the stage once a second (it does not rely on `OnStageSet`, whose behaviour is unresolved, E2 in
docs/questprobe/engine-questions.md) and runs each step once: **10** `SwitchToPowerArmor` on the suit furniture, **20**
`SetRace` to the copy, **30** `SetRace` back to the race the player started with. Each step logs the player's race, cell,
position, camera state, worn item count, `IsInPowerArmor()`, furniture and sit state before the call, right after it and
4 s later. A `sit` line is logged whenever the furniture or sit state changes. Every line ends `end=true`.

### Names that may not exist (reported, never assumed)

The optional readings are `;OPT` lines in the .psc. `make_power_armor_probe.py precheck` looks each name up in
Starfield's base sources (inheritance followed); `stage` then compiles each declared one **on its own**, keeps the ones that
compile and records the fate of every one in `plan.json` ("optional"): `Actor.IsInPowerArmor` (gap table: missing in
Starfield, so probably "not declared"), `Game.GetCameraState`, `Actor.GetWornItem` (the worn count; also needs the
`Actor:WornItem` struct), `Actor.GetFurnitureReference`, `Actor.GetSitState`. A name that does not exist or compile logs
`na`; the reader lists it. The required natives (`SwitchToPowerArmor`, `SetRace`, ...) stop the stage when missing.
**Not run offline:** the real Papyrus compile and the real Starfield.esm. The offline tests use a fake compiler and a
synthetic Starfield.esm; a real HumanRace or furniture may write differently through Mutagen, and `check` reads the
plugin back against the real Starfield.esm at stage time.

## Install and read (the owner's word, game closed)

    python scripts\planet\make_power_armor_probe.py precheck
    python scripts\planet\make_power_armor_probe.py stage --out <dir>
    python scripts\planet\power_armor_probe_install.py install --dir <dir> --starfield <game dir>
    ... session ...
    python scripts\planet\make_power_armor_probe.py log
    python scripts\planet\power_armor_probe_install.py uninstall --starfield <game dir>

The installer runs `exp_install.py`'s code on a record of its own, so the installed core set and the planet probe's
record are never read or changed (the name `planet_probe_install.py` is already the planet probe's own installer and
record, so this one has its own file name). The log is `My Games\Starfield\Logs\Script\User\FO4SFPAProbe.0.log`.

## Session card

**Throwaway state only. Do not save at any point.** The race swap (step 20) can break a save; do not autosave, quicksave
or save on exit. Use a new-game start or a character you will delete.

Screenshots (F12 or the usual key), named with the step: `00-arrival`, `01-control-seated`, `10a-before`, `10b-now`,
`10c-settled` (first and third person for each), `20-after-setrace`, `30-after-restore`, and any message, HUD change or
error text that appears.

1. Start the game with the probe installed (tick it in the load order). Open the console (`~`) and run:

       coc FO4SF_PAProbeCell

   You arrive facing +X in a small platform room. A furniture stands to your left (the control) and one to your right
   (the suit). Screenshot `00-arrival`. Wait 5 s.
2. **Control.** Walk to the left furniture (vanilla), activate it, sit. Screenshot `01-control-seated`. Wait 3 s, stand up.
   If you cannot sit, stop: the session is inconclusive and the reader will say so.
3. Face the right furniture, standing about 2 units from it. Screenshot `10a-before`. Console:

       setstage FO4SF_PAProbeQuest 10

   Screenshot immediately (`10b-now`), again after 5 s (`10c-settled`), once in first person and once in third person. Do not
   move or press anything for those 5 s. Note any climb-in animation, camera change, HUD, speed or jump change.
4. Console: `setstage FO4SF_PAProbeQuest 20`. Wait 5 s. Third-person screenshot `20-after-setrace`. Note any visible change,
   T-pose, missing head or hands, animation stall.
5. Console: `setstage FO4SF_PAProbeQuest 30`. Wait 5 s. Screenshot `30-after-restore`.
6. Quit to the desktop **without saving**. Run the reader command above and paste its output with the screenshots.
7. A retry needs a new game start: each step runs once per script instance.

## What the reader says

One table (a row per reading: stage, when, race, camera, worn count, `inpa`, furniture, sit state, position), one line per
step, and a last line. It is **INCONCLUSIVE** when the script never ran (no start line) or the player was never read on the
vanilla furniture (its reference, or sit state 3 within 1.5 units of it): then no step is judged. Otherwise
`CONTROL OK` and, per step: stage 10 `entered (IsInPowerArmor true)` / `changed: <fields>` / `no logged change`; stage 20
`race set` / `race unchanged` / `race became <id>`; stage 30 `restored` / `not restored`. The log cannot see animation or
rendering: **"no logged change" with a visible climb-in is a pass; the screenshots decide it**, and the reader says so by
naming only the fields it saw change.

## What the answers decide

* Stage 10 changes the player (camera, race, furniture, inpa, screenshots): the Fallout 4 entry path partly survives; the
  climb-in suit is mostly records and scripts (A2, P1). Nothing happens: the call is a stub on this furniture and the
  climb-in needs a body swap (P3).
* Stage 20 sets the race: `SetRace` works at runtime on the player (A3), so a power armor race can carry a skeleton and graph.
  Restored at stage 30 means the swap is reversible in this session; whether a save survives it is **not** tested here.
* Both fail: the combined core's climb-in suit is a worn-suit design only until SFSE or another route is researched.
