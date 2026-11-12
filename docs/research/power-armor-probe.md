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

## Result of the PC run (11 Nov, 01:24 to 01:29 UTC, test save, no save made; owner's set restored)

Head 9e252a4a, run by the owner PC (Claude), evidence `probe-pa-20261111T012358Z` on the PC. **Verified:**

* Control: seated on the vanilla chair (sit state 3 at 0.12 units), stood up again.
* Stage 10, `SwitchToPowerArmor` on the keyword-only furniture (player 2 units away, facing it): **no field changed**
  (race, camera na, worn na, inpa na, furniture na, sit state 0); screenshots before, right after and 5 s later identical
  (first person: no animation, camera or HUD change). Not tried: third person, a furniture that is more than a chair plus
  the keyword.
* Stage 20 `SetRace` to `FO4SF_PARace`: the race id changes at once and stays; stage 30 restores it. Nothing visible in
  first person (the copy has HumanRace's skeleton). Whether a save survives the swap is untested.
* Reading: the Fallout 4 entry call is not a ready path on a keyword-only furniture (a climb-in needs more than the
  keyword: a real power armor furniture record if Starfield has one to copy, or a body swap); a power armor race can be
  set on the player at run time and taken back in the same session.

Reader findings from that run, fixed after it: the start line is logged at load, before the probe cell is loaded, so its
`controlref` is none and the reader called the control failed although the `sit` lines (state 3 within 1.5 units) met its
own rule: a none `controlref` no longer fails the control, only a sit state 3 near the control counts then; init and start
are logged twice at load, which made "2 runs": an init is a new run only after a step.

## Next test: the empty default objects (variants)

The owner PC read both games' own files (names and ids only, 11 Nov): Starfield.esm keeps Fallout 4's power armor default
objects (DFOB) under the **same form ids**, and five are empty (DATA none): `PowerArmorRace_DO` 0005C254,
`PowerArmorDefaultFrameFurniture_DO` 0022BC97, `PowerArmorDefaultFrameArmor_DO` 0015503E, `PowerArmorArmorKeyword_DO`
00140C44, `PowerArmorDefaultBatteryObject_DO` 000BD5C5. The keywords are wired (`FurnitureTypePowerArmor`,
`isPowerArmorFrame`, `LinkPowerArmor`, `isPowerArmorBattery`, `NoPowerArmorUse`); no FURN, ARMO, RACE, NPC_, ACTI, MISC,
WEAP or PERK record carries any of them. **Supported hypothesis, untested:** `SwitchToPowerArmor` did nothing because the
objects it should lead to are not set. The test: our plugin overrides them (a record override in a ride-along plugin, no
native code), each as its own variant so the log names which one the call needs.

    python scripts\planet\make_power_armor_probe.py stage --out <dir> --variant race
    python scripts\planet\make_power_armor_probe.py stage --out <dir2> --variant race,furniture,keyword

| variant | overrides | needs |
|---|---|---|
| `race` | `PowerArmorRace_DO` -> `FO4SF_PARace` | (first run) |
| `furniture` | `PowerArmorDefaultFrameFurniture_DO` -> the suit furniture, which also gets `isPowerArmorFrame` | |
| `keyword` | `PowerArmorArmorKeyword_DO` -> `FO4SF_PAArmorKeyword` (ours, 000807) | |

Run `race` first, then stage 10 again on the same card (control, step 3): does `SwitchToPowerArmor` now change the race,
sit state or camera?

**What a stage-10 result would and would not prove.** `FO4SF_PARace` is a copy of HumanRace: same skeleton, graph and
meshes. A race id that changes at stage 10 (before / now / settled in the log) proves the call now reaches the default
object and sets the race (the entry path works with that object); it will probably show **nothing on screen**, so the log
is the evidence and the screenshots are only the second half. No change proves only that this object alone is not enough
(try the next variant), not that the call is dead. A visible climb-in or a camera change would be more than this kit is
built to produce. Neither outcome says anything about a power armor body, the frame armor or the battery.

If the race (or sit state, or camera) changes, add the other two (and name in the log which one made the difference). The frame armor
(001909D6 in Fallout 4) and the battery are not set by any variant: their record shapes are not read yet (the owner PC
offered `NEEDS-PC dump <ids>`). The check refuses a plugin whose default objects are not exactly the variant's; the
script and the reader are unchanged (the reader already prints race before, right after and 4 s later). A variant stage
is its own folder and its own plan.json ("variant"); install one at a time (same plugin name, same record).

## Result of the variant runs (11 Nov, 03:37 to 03:49 UTC)

Kits built at 5133e77c (the delta to 67521dd8 is the doc only), run by the owner PC (Claude), evidence
`probe-pa-20261111T033742Z` and `probe-pa-20261111T034412Z` on the PC. **Verified:** filling the empty default objects does
**not** wake `SwitchToPowerArmor`.

| variant | stage 10 `SwitchToPowerArmor` on the suit | stage 20 / 30 `SetRace` | control |
|---|---|---|---|
| `race` | race, sit state, cell, position unchanged before / now / settled | set, restored | sit state 3 at 0.12 |
| `race,furniture,keyword` | unchanged, same lines | set, restored | sit state 3 at 0.12 |

**Correction (owner PC, 11 Nov 03:55 UTC): the call is not dead, the game refuses our suit and says so.** Both sessions'
`Papyrus.0.log` hold `error: FO4SF_PAProbeSuitRef (09000804): is not valid power armor furniture.` from
`Actor.SwitchToPowerArmor() - "<native>"`. The probe's own user log cannot see that, so "no logged change" hid a refusal;
the reader now also reads the game's Papyrus log (below). Offline read of Starfield.exe 1.16.244.0 beside Fallout4.exe
(names and offsets only, owner PC): the Actor registrar binds `SwitchToPowerArmor` to live code (rva 0x1fcb100, 0x1F6
bytes) with the same branches and error strings as Fallout 4's; on success it calls a large function (rva 0x12d4b20) that
creates the actor's power armor extra data and reads `PowerArmorRace_DO`; the default objects are read by code
(`PowerArmorKeyword_DO` 38 reads, `PowerArmorRace_DO` 16, `PowerArmorArmorKeyword_DO` 11, ...). There is no
`IsInPowerArmor` native in either game. The first reading of the validity check ("a FURN carrying `PowerArmorKeyword_DO`'s
keyword") is not enough: our suit carried `FurnitureTypePowerArmor` (and, in the `all` kit, `isPowerArmorFrame`) and was
refused in both; what else it reads is being re-read (which object each test applies to, whether a linked reference with
`LinkPowerArmor` or loaded 3D is required). **Unresolved:** the exact condition list; the next kit change follows it.

`race,furniture` alone was not run (the full set already shows nothing on the log's side). The three default objects are
therefore not the only gate (the success path reads the race slot, so they stay worth having), and the gate in front is the
furniture validity check. The game still gives `na` for camera state, worn
count, `IsInPowerArmor` and the player's furniture. The fallback (race swap plus our own armor and camera, by script) stays available and `SetRace` works both ways.

## The gate and the crash (owner PC, 11 Nov 04:07 to 04:12 UTC, `race` kit with console steps added)

**Verified (owner PC):**

* **Why the suit was refused.** In the console on the suit reference 09000804, `haskeyword 0003430B` printed
  `HasKeyword: FurnitureTypePowerArmor >> 0.00` (and `isPowerArmorFrame` 0.00) although the base FURN `FO4SF_PAProbeSuit`
  lists 0003430B in its KWDA: **the game did not see the base record's keyword list.** The native's validity test (read from
  the exe): the base object is furniture, and the **reference** has the keyword held by `PowerArmorKeyword_DO`
  (FurnitureTypePowerArmor in Starfield.esm). So the writer's FURN keywords were the bug, not the default objects.
* **The gate passes with the keyword on the reference:** `addkeyword 0003430B` on the reference, `haskeyword` then prints 1.00;
  stage 10 then logs `step` and one `before` state line, no "not valid power armor furniture" in Papyrus.0.log, and **the game
  died one second later**: 0xC0000005 at `Starfield.exe+0xb6508b`, `cmp byte ptr [r15+2Eh],0CFh` with r15 = 0 (a null form
  pointer; the byte compared is a form type). Evidence `probe-pa-20261111T040702Z` on the PC.
* Reading: the entry call is alive in Starfield and does real work once the furniture is valid. It then needs something the
  kit does not supply (only the race slot was filled; frame furniture, frame armor, armor keyword and battery default objects
  were empty, and the suit is a copied chair). **Which piece is the null is unresolved** (the owner PC is reading the dump and the exe).

**Writer change (supported hypothesis, untested in game):** Starfield also keeps a record's keywords in a keyword form
component (`BGSKeywordForm_Component`, a BFCB block in the record's components). The writer now writes the suit's keywords in
that component as well as in the KWDA list, so `HasKeyword` may be true on the reference without the console; whether the game
reads the component for a FURN is not known (the owner PC compares a vanilla keyworded FURN with ours). The script logs
`haskw=` (`ObjectReference.HasKeyword` of 0003430B on the suit reference, an optional reading) on the stage-10 step line before the call,
and the reader prints it: **false** = the call will be refused; **true** = a real entry.

> **WARNING: do not run stage 10 of this kit on a game anyone cares about, and do not stage it for a normal session.** If the
> keyword is seen, `SwitchToPowerArmor` goes into the engine's power armor code and **crashes the game on a null** until the
> missing default objects or pieces are supplied (the next kit follows the owner PC's dump note). Throwaway sessions only,
> no save, uninstall afterwards. Since the owner PC's 04:17 request the
> script adds the keyword itself when `HasKeyword` is false (see "The frame armor" below); that forces the entry.

## The frame armor (owner PC, 11 Nov 04:17 UTC) and the `armor` variant

**Verified (owner PC, offline read of the recorder dump and Starfield.exe 1.16.244.0; names and offsets only):** the 04:12
crash is on the Papyrus thread inside the native call itself (return addresses inside the success path 0x12d4b20 and the
native 0x1fcb100). The crashing function (0xb64fc0) tests the form type of its second argument, an item form, without a
null check, and that argument is null. The null comes from `0x12cb810(actor, 0)`, which returns **the frame armor**: it starts
from `PowerArmorDefaultFrameArmor_DO` (accepted only if it is an ARMO); if the actor already has power armor extra data and
the power armor race it searches the actor's inventory for armor carrying the keyword of `PowerArmorFrameKeyword_DO`
(`isPowerArmorFrame` 0015503F); one more inventory branch is not decoded. With the default object empty it returned null.
So the order of gates so far: (1) the suit base is furniture, (2) the reference has `FurnitureTypePowerArmor`, (3) a frame
armor exists; the race slot is read later in the same function. **Unresolved:** the undecoded inventory branch; the
battery and armor-keyword reads (inferred to be read on exit and for the pieces).

The `armor` variant (built from the owner PC's note, untested in game):

    python scripts\planet\make_power_armor_probe.py stage --out <dir> --variant race,furniture,keyword,armor --armor <armor editor id>

| variant | overrides | needs |
|---|---|---|
| `armor` | `PowerArmorDefaultFrameArmor_DO` 0015503E -> `FO4SF_PAFrameArmor` (ours, 000808): **a copy of a plain vanilla armor** plus `isPowerArmorFrame` 0015503F, in its KWDA list and its keyword form component | `--armor <armor editor id>` |

**Which armor is copied is not chosen here:** this box has no Starfield.esm, so no editor ID of a real plain armor can be
named from evidence. `--armor` is required with the variant; without it the tool refuses and lists the first 12 ARMO
editor IDs of the Starfield.esm it was given. The owner PC picks one (a plain suit or clothing record without power or
special behavior) and writes it in the stage's README. The check requires the copy to keep the armor's rating, value and
keywords. The set to run is `race,furniture,keyword,armor` (the owner PC's note: keep the race, fill frame furniture and
armor keyword, add the frame armor).

**Script change (the owner PC's request):** before the call, stage 10 logs `haskw` (`HasKeyword(FurnitureTypePowerArmor)` on
the suit reference); if it is false the script calls `AddKeyword` on the reference (optional reading `ObjectReference.AddKeyword`,
`na` when the name does not exist or compile), logs `addkw` (`done` / `na`) and reads `haskw2`, all on the one step line
that is written before the call. This replaces the console line of the 04:07 session. The owner PC is separately checking
whether the base FURN's keywords are simply not visible through `HasKeyword` on a reference (one of the copied chair's own
keywords, 00144A65, on our reference and on the vanilla control); if so `AddKeyword` is the way. The keyword form component
change of a05fbc4d stays until that is known.

**Reader:** a log that stops after the stage-10 `before` reading is reported as a result, `no reading after the call: the log
ends inside it, the game may have ended during the call (a crash is a result: see the Papyrus log and the crash dump)`, and
the verdict stays `CONTROL OK`; the later stages read `not run`. The session is not a failed one.

## The keyword that is not seen (owner PC, 11 Nov 04:23 to 04:27 UTC, `race` kit, console only)

**Verified (owner PC):** `haskeyword` on the suit reference 09000804 (base `FO4SF_PAProbeSuit`, KWDA with both) prints 1.00 for
`AnimFurnChair` 00021BF1 (the copied chair's own keyword) and **0.00** for `FurnitureTypePowerArmor` 0003430B; on the control
09000805 (vanilla `NPCChairTech03_Free_270`) 1.00 and 0.00. So base furniture keywords are visible through a reference, and
exactly the keyword the writer appended is not. The staged record lists it (KSIZ 7, KWDA `00144A65 00021BF1 0018F692
0012F848 001736FF 002A8007 0003430B`; the vanilla chair has the first six). **Unresolved why:** candidates, none tested: the
copy keeps something that still describes the original six; the game filters this keyword on furniture; a cached list per
source form. Evidence `probe-pa-20261111T042249Z\session\kw-base.png` on the PC.

Two cheap tries (built, untested in game): **`stage --kw-first`** puts FurnitureTypePowerArmor first in the suit's keyword list
(KWDA and component; the check follows the order); and the script keeps `AddKeyword` on the reference as the working route
(the console showed it flips to 1.00 and the native then accepts the suit). The step line also logs `haskwc=`
(`HasKeyword(AnimFurnChair)` on the suit reference), so one session shows both readings; the reader says which case it is.
Not built: a blank furniture record with only the two keywords (a different record shape; say if you want it as the next try).

## The armor-variant session (owner PC, 11 Nov 05:09 to 05:15 UTC, 18b34a0d) and the keyword readings' names

**Verified (owner PC):** staged on the real Starfield.esm with `--armor Clothes_Crowd_Akila_Fatigues_01_NOTPLAYABLE` (0017C68D, a
body outfit, two keywords, no script, no enchantment, not playable); the plugin has the four default objects, the frame armor
000808 with `isPowerArmorFrame` in list and component, and the suit's keyword component equal to its KWDA list. Stage 10 line:
`haskw=false addkw=NA haskw2=false haskwc=true`: **the rebuilt component does not make the appended keyword visible** (the
chair's own keyword still is), and the script did not add it. Papyrus.0.log again: `FO4SF_PAProbeSuitRef (09000804): is not
valid power armor furniture.` No crash, nothing else changed.

**Why `addkw=NA`:** the optional reading was keyed on `Form.AddKeyword`, which does not exist. In Starfield's base sources the
function is on the reference: `ObjectReference.psc` declares `Function AddKeyword(Keyword apKeyword) native` (also `RemoveKeyword`,
`ResetKeyword`) and its own `bool Function HasKeyword(Keyword apKeyword) native`. The stage output had said so (`'Form.AddKeyword':
'not declared in the base scripts'`): the name was wrong, not the idea. **Fixed:** both keyword readings are now keyed on
`ObjectReference.HasKeyword` and `ObjectReference.AddKeyword`, and the offline test's base sources declare them where the real ones
do, so a name keyed on the wrong script fails the stage test instead of logging `na` in game.

**Reader and the Papyrus log:** `python scripts\planet\make_power_armor_probe.py log --papyrus <path to Papyrus.0.log>` (the flag
takes the session folder's copy; the default is the game's own `Logs\Script\Papyrus.0.log`). With it the stage-10 result reads
`refused by the game: error: FO4SF_PAProbeSuitRef (09000804): is not valid power armor furniture.` instead of `no logged change`.

## Result of the probe: the entry is alive, its content is missing (owner PC, 11 Nov 05:16 to 05:27 UTC)

**Verified (owner PC; offline read of the recorder dump and Starfield.exe 1.16.244.0, names and offsets only).** Same kit
(18b34a0d, `race,furniture,keyword,armor`) with the console `addkeyword` in front of stage 10: step line `haskw=true addkw=NA
haskw2=true haskwc=true` (the `addkw=NA` was the script's wrong name, fixed at 51a03e53: `ObjectReference.AddKeyword`);
no "not valid power armor furniture" in Papyrus.0.log; about one second later 0xC0000005 at `Starfield.exe+0x12cf1c0`
(`movzx eax, byte ptr [r8+9]`, r8 = 0). Evidence `probe-pa-20261111T051557Z` on the PC.

What the second null is: the engine has already switched the player to the power armor race (our `FO4SF_PARace`) and is
equipping the frame armor; the equip routine (0x12cf130, called with the actor and the frame armor) takes the race's body
part data (race+0x910) and, for each of six engine actor values (a table at 0x5fb49a0; the plugin library names them power
armor head, torso, left arm, right arm, left leg and right leg condition), scans the parts for one carrying that value and
reads its limb type without a null check. It failed on the first (head) after scanning all 26 parts: Starfield's
`HumanBodyPartData` (00003481), which our race copy uses, has 13 parts and none of those values. Fallout 4's `PowerArmorRace`
uses `PowerArmorBodyPartData` (0001D322), whose parts carry them (00060BDD to 00060BE2 there).

**The order of gates, as found:** (1) the suit base is furniture, (2) the reference has `FurnitureTypePowerArmor`, (3) a frame
armor exists (`PowerArmorDefaultFrameArmor_DO`), (4) the player's race has power armor body part data. Inferred from the
same functions, not yet met: the armor's biped slots against a second race's body part data, `PowerArmorArmorKeyword_DO`,
battery handling, the furniture's 3D and the enter animations. The success path has 141 calls and assumes real power armor
content (a skeleton, armor addons for the power armor race, animations); Starfield ships none of it, and each missing piece
costs one game crash to find.

**Answer to the question of this probe (A2, P1, A3):** Fallout 4's power armor entry is alive in Starfield, gated by the
furniture base, `FurnitureTypePowerArmor` on the **reference**, a frame armor, power armor body part data on the race, and then
assets. The engine side exists; the content side has to be brought. `SetRace` on the player works both ways (the race swap is
reversible within a session; a save through it is untested). **Open:** why the keyword appended to the base FURN's list is not
seen through `HasKeyword` on the reference while the copied chair's own keywords are (neither the reordering nor the keyword
form component changed it); `AddKeyword` on the reference is the working route.

**Reproduced from the card alone (owner PC, 11 Nov 05:38 to 05:43 UTC, 51a03e53, `armor` kit, no console help).** Stage 10 line
`haskw=false addkw=Done haskw2=true haskwc=true`: `ObjectReference.AddKeyword` from Papyrus works on the reference, and the base
keyword is still not seen before it. No "not valid power armor furniture" line; the game ends about seven seconds after the stage
line with 0xC0000005 at `Starfield.exe+0x12cf1c0`, r8 = 0, the same place as at 05:20. The reader reports stage 10 as `no reading
after the call: the log ends inside it` (a crash is a result), stages 20 and 30 `not run`, `CONTROL OK`. No save. Evidence on the PC:
`pc-708-51a03e53\stage-armor`, `probe-pa-20261111T053843Z`.

**Recommendation of the owner PC for the stage scope:** the climb-in by script now: `SetRace` (proven both ways), equip our
frame and armor pieces, our own sit or camera flow, a flag of ours for "in power armor"; keep the native as a research line
that becomes useful once Fallout 4's power armor race, skeleton and addons are converted. One more variant is possible for the
record and was **not built**: our race with its own body part data (a copy of `HumanBodyPartData` with six parts' actor
values set to the engine's six); its form ids must be read from Starfield.esm, not assumed from Fallout 4, and there is no
Starfield.esm on the box that built this kit. Nothing further is planned by crash-and-read.

## Session card

**Throwaway state only. Do not save at any point.** The race swap (step 20) can break a save; do not autosave, quicksave
or save on exit. Use a new-game start or a character you will delete.

**A variant kit (`--variant`) is for a throwaway session only, never for a save the owner keeps.** A default-object
override changes what the engine's power armor default objects point at for every save loaded with the plugin ticked, not
just for this session's test: the plugin changes the game's rules for as long as it is in the load order. Install it for
the test, quit without saving, uninstall it (`power_armor_probe_install.py uninstall`) before playing a real save.

Screenshots (F12 or the usual key), named with the step: `00-arrival`, `01-control-seated`, `10a-before`, `10b-now`,
`10c-settled` (first and third person for each), `20-after-setrace`, `30-after-restore`, and any message, HUD change or
error text that appears.

0. **The quest's form id.** The console refuses a plugin quest's name in `setstage` ("not found for parameter Quest"), so
   every stage line below uses the form id, `<load index>000803`. Read it first: after the game has loaded with the probe
   ticked, run `python scripts\planet\make_power_armor_probe.py log`; its first line is `quest form id <hex>: setstage <hex>
   10 / 20 / 30` (from the init line's `quest=`, which Papyrus prints as signed decimal; the reader converts it). Or take the
   probe's load index from the load order (hex, two digits) and append `000803`. Below, `<Q>` is that id.
1. Start the game with the probe installed (tick it in the load order). Open the console (`~`) and run:

       coc FO4SF_PAProbeCell

   You arrive facing +X in a small platform room. A furniture stands to your left (the control) and one to your right
   (the suit). Screenshot `00-arrival`. Wait 5 s.
2. **Control.** Walk to the left furniture (vanilla), activate it, sit. Screenshot `01-control-seated`. Wait 3 s, stand up.
   If you cannot sit, stop: the session is inconclusive and the reader will say so.
3. Face the right furniture, standing about 2 units from it. Screenshot `10a-before`. Console:

       setstage <Q> 10

   Screenshot immediately (`10b-now`), again after 5 s (`10c-settled`), once in first person and once in third person. Do not
   move or press anything for those 5 s. Note any climb-in animation, camera change, HUD, speed or jump change.
4. Console: `setstage <Q> 20`. Wait 5 s. Third-person screenshot `20-after-setrace`. Note any visible change,
   T-pose, missing head or hands, animation stall.
5. Console: `setstage <Q> 30`. Wait 5 s. Screenshot `30-after-restore`.
6. Quit to the desktop **without saving**. Run the reader command above and paste its output with the screenshots. The reader
   also reads the game's own `Logs\Script\Papyrus.0.log` (`--papyrus <file>` for another path) and prints every error or
   warning that names our forms: **a refusal by the game is only there** (11 Nov: `FO4SF_PAProbeSuitRef (09000804): is not
   valid power armor furniture.`), and the reader then says `refused by the game` for stage 10 instead of `no logged
   change`. By hand: search that file for `FO4SF_PA` and keep the lines.
**The quick way the PC used** (walking is not needed): `coc FO4SF_PAProbeCell` (the game closes the console by itself on the
`coc`; open it again); `prid <load index>000805` then `activate player` seats the player on the control; W stands up;
`player.setpos x -2`, `player.setpos y -2.5`, `player.setangle z 90` puts the player 2 units from the suit, facing it. The
HUD is dimmer in this bright room, so `hud_visible.py` can read "no HUD" and `console_open.ps1` may not confirm. The load
index depends on the load order (09 on the PC on 11 Nov: `setstage 09000803 10`).
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

## By hand (FAL-273): no console, the answers on screen

The same plugin carries a second quest, `FO4SF_PAHandQuest` (0x809, script `FO4SF_PAHandQuest.psc`, no properties). It asks
the probe's stage 10 question, `SwitchToPowerArmor` on the suit furniture, and shows what the engine answered as messages on
screen. **The furniture is not in the vanilla world**: it stands in the probe's own cell `FO4SF_PAProbeCell`, so the smallest
thing the owner can use is that room. The script moves the player there itself 30 s after the quest starts
(`ObjectReference.MoveTo` on the arrival marker, an optional name; the target is `FO4SF_PAProbeArrival` (0x80A), an XMarker in the cell's *persistent* group at the COC marker's place, because a temporary reference of a cell that is not loaded cannot be found by the script (FAL-316 finding): when the game has no such call the screen says to type
`coc FO4SF_PAProbeCell`, the one console line left). The race swap (stages 20 and 30) is **not** in the hand version, because
it can break a save; it stays with the console probe.

In the room, on screen: what stands where; every change of the furniture the player is on (the control chair: "Sitting
works"; the suit: sit state and `in power armor`); and, when the player walks within 2 units of the suit (or after 60 s in the
room), the call (the 60 s fallback only while standing, never while seated on the control chair) and its answer 1 s and 4 s later: in power armor, furniture, sit state, camera, race unchanged or not, worn
armor slots. A reading the game has no call for says `not in this game's scripts`. Every message is also a line of
`FO4SFPAHand.0.log`. Offline only: the Papyrus compile and the game are the PC's.

### Owner card (seven steps, no console; follows the #708 PC run: the call is expected to do nothing)

1. Tick `FO4SFPowerArmorProbe.esm`. Load a save of a **throwaway** character already in the world (not the opening); do not save.
2. Wait. Message: "Power armor test: in 30 s you are moved into a small test room." Then "Moving you into the test room." (If instead you read "type coc FO4SF_PAProbeCell", do that, nothing else.)
3. In the room a message names the two furnitures: vanilla chair on your left (control), suit on your right. Walk to the left one and sit (activate it). Message "You are seated (sit state 3) ... sitting works." (`Actor.GetFurnitureReference` is not in Starfield's scripts, so the screen goes by the sit state.) If you cannot sit, say so and stop.
4. Stand up. Walk up to the right-hand furniture and stand next to it (do not activate it yet). Message "You walked up to the suit: calling SwitchToPowerArmor on it now."
5. Watch the screen and the character for 5 s: any climb-in animation, camera change, or HUD change. Three messages follow ("Suit 1 s after the call: ...", "Suit 4 s after the call: ...", then "Result: nothing changed ..." or "Result: something CHANGED ..."). The PC run of the probe (11 Nov, #708 at 9e252a4a) saw **nothing change** on this chair-plus-keyword furniture, so "nothing changed" is the expected result; a change is the news. Screenshot each.
6. Now activate the suit furniture once. Does a message say "You are on the SUIT furniture ..."? Did anything animate?
7. Quit without saving. Tell: step 3 worked or not; the two "Suit ..." messages as read; what you saw at steps 5 and 6.

## Entry by script (FAL-361, piece B of FAL-359): kit, hand mode, card

Status: **built offline, not run in game.** The #708 run showed that `SwitchToPowerArmor` on a keyword furniture does nothing,
and the console probe showed `SetRace` to a copy of HumanRace works on the player both ways. So the entry here does not ask the
engine to climb in: a script does the four things that make up "being in a suit" for our own design, and undoes them.

Same plugin (`FO4SFPowerArmorProbe.esm`, still master Starfield.esm only, adds records, overrides none), new records:

| Record | What |
|---|---|
| QUST `FO4SF_PAEntryQuest` (0x80B), script `FO4SF_PAEntryQuest.psc` | start game enabled, one stage, no properties; hand mode (no console) with an on-screen line for every step and a line of `FO4SFPAEntry.0.log` for each |
| FURN `FO4SF_PAEntryFurn` (0x80C), reference 0x80D 3 units ahead of the arrival | **the furniture of ours**: every field of the control chair (`NPCChairTech03_Free_270`), and **no** power armor keyword, so the engine has nothing power-armor-shaped to react to |
| AVIF `FO4SF_PAInPowerArmor` (0x80E) | our value for "in power armor": variable, default 0, min 0, max 1 |
| ARMO `FO4SF_PAFrame` (0x80F, slot BODY), `FO4SF_PAPieceHelm` (0x810, Hat), `FO4SF_PAPieceTorso` (0x811, UpperBody1VisOnly) | our frame and two pieces: a name, a slot, weight and value 0, no script |
| RACE `FO4SF_PARace` (0x802, from the console probe) | the kit race: a copy of HumanRace |

**The entry** (sit on the entry chair; the script waits 2 s): `AddItem` and `EquipItem` of the frame and
both pieces, `SetValue` of our value to 1; **no race swap** (see "PC rerun" below). It reads the state back after 1 s and 4 s and says on screen which held, and whether the race changed.
**The exit** (sit on the vanilla chair on the left, or 120 s in the suit): value to 0, `UnequipItem` and `RemoveItem` of the three,
read back after 1 s and 4 s. Sit state 3 within 1.5 units of the
chair is the trigger (the console probe's seated control was 0.12 units away); when the game has no `GetSitState` the first walk up to
the entry chair is the trigger, once, and the exit is the 120 s timer.

**Stage options (art now defaults, see "PC runs at 1a6096e1").** `--with-hand` keeps the by-hand quest (`FO4SF_PAHandQuest`) start game enabled: it is **off by default** now,
because it and the entry quest both move the player into the room at 30 s and both talk. `--frame-art <ARMO editor id>` and
`--piece-art <ARMO editor id>` copy a vanilla ARMO (every field, so its armatures, which are the look) into the frame / the two
pieces; `check` is given the same options as `build` and refuses a plugin that does not match.

Names the script guesses are `;OPT` lines (the stager compiles each alone and keeps what compiles, in `plan.json` `optional_entry`):
`Actor.GetValue`, `Actor.SetValue` (our value; **the value is the least certain native**), `Actor.IsEquipped`, `Actor.GetSitState`,
`ObjectReference.MoveTo`. Required, in the stager's list: `Actor.EquipItem`, `Actor.UnequipItem`, `ObjectReference.AddItem`,
`RemoveItem`, `GetItemCount`. **Not run offline:** the Papyrus compile (the PC's compiler), the real Starfield.esm, and the game.

### What the player sees, and what is honestly missing

* **Third person with `--frame-art none --piece-art none` (the offline opt-out; no longer the default):** the player stays HumanRace, and the three ARMO have **no armature**, so nothing
  changes on the body. The only visible results are the on-screen lines, three items appearing
  in and leaving the inventory, and (if the game can read it) the value. **First person:** the same, no arms or camera change.
* **With `--frame-art` / `--piece-art`:** the vanilla armor's armatures are worn: third person shows that armor over the character
  (a copied suit's own slots and look decide whether it looks like a frame); a vanilla ARMA names HumanRace (or the races it was made
  for), which the player is, so the equip should be accepted; unknown until run.
* **Missing, not attempted:** a climb-in animation (the engine's own did nothing); a power armor HUD or camera; a steel frame as art
  (no frame model is made here); a fusion core, damage or carry-weight rules (the value is only ours: nothing reads it, so
  nothing changes in play); the Starfield power armor state (`IsInPowerArmor` is not in Starfield's scripts); stopping the player
  from taking the pieces off by hand (`EquipItem` is called with prevent-removal false); a save made while in the suit. Throwaway state only,
  no save (a first-time script that adds items is still not a save-safe design).

### Card (eight steps; throwaway character, no console, game closed first for the install)

1. Stage with the defaults (the suit art is built in; no `--with-hand`) and install (`power_armor_probe_install.py install --dir <stage> --starfield <game dir>`) and tick `FO4SFPowerArmorProbe.esm`. Load a save of a **throwaway** character already in the world (not the opening). Do not save at any point.
2. Wait 30 s. Messages: "Power armor entry test: in 30 s you are moved into a small test room", then "Moving you into the test room." (If you read "type coc FO4SF_PAProbeCell", do that and nothing else.) Screenshot third person and the inventory (armor tab) now: the **before**.
3. The message "Test room: the ENTRY chair is 3 units ahead of you" appears. Walk to the chair ahead and sit (activate it). Message "You sat on the entry chair (sit state 3): the suit goes on in 2 s." If you cannot sit, say so and stop.
4. Two seconds later "Suit ON requested ...", then "Suit 1 s after the entry: ..." and "Suit 4 s after the entry: ..." and "Result: the suit is ON" or "only partly on. Did not hold: ...". Copy every line.
5. Stand up. Screenshot first person and third person, and the inventory (three FO4SF items, equipped or not). Note any visible change, T-pose, missing head or hands, stall, speed or jump change.
6. Walk to the vanilla chair on your left and sit. Message "You sat on the exit chair ...", 2 s later "Suit OFF requested ...", "1 s after the exit ...", "4 s after the exit ..." and "Result: the suit is OFF" or "the exit did NOT undo everything. Still set: ...". Copy them.
7. Stand up. Screenshots again, same three views, and the inventory: the **after** (the character should wear what it wore before; the log has `saved worn=` and `restored worn=`). Optionally enter and leave a second time (sit on the entry chair again).
8. Quit to the desktop **without saving**. The entry's own log is `FO4SFPAEntry.0.log` in `My Games\Starfield\Logs\Script\User` (no reader for it yet: every line is plain text ending `end=true`); paste it with the screenshots and the eight copied lines. Tell: which of step 4's four held, whether step 6 undid them, what the screenshots show.

### PC run of #733 at e9acb003 and the fixes (FAL-361)

Verified by the PC (Claude, 11 Nov 09:37 to 09:43 UTC, test save, no save): the entry runs end to end; race became the kit race, 3 of 3
in the bag, value 1.0; the exit restored race, bag and value. **The equip failed**: `armor cannot be equipped by the passed in actor's race`
(Papyrus.0.log, three ARMO). Fixes, offline only, awaiting a second PC run: (1) the three ARMO now name the kit race (`FO4SF_PARace`) as
their race, and `check` refuses otherwise; (2) a quest script's OnInit runs although the quest is not start game enabled (the hand
quest moved the player and called `SwitchToPowerArmor` over the entry run), so the hand script is now **left off the record** unless
`--with-hand` is given. Not changed: `init` logs `entryref=none controlref=none` because `Game.GetFormFromFile` cannot resolve a
temporary reference of a cell that is not loaded (FAL-316); the entry quest looks the chairs up again once the player is in the room,
where they resolve, so the log's init line is expected to say none. Third person and the inventory were not captured; with the race
fix the equip should now put the (art-less) pieces on, still nothing visible without `--frame-art`.

### PC rerun of #733 at f5d38adb: the race swap is dropped (FAL-361)

Verified by the PC (10:15 to 10:21 UTC): naming the copied race on the ARMO did not help (same three equip errors, `RNAM` was the copy).
The cause is the armature: a race is accepted by an ARMA's race list, the ARMO here had none, and the copy is in no vanilla ARMA. Worse,
**third person in the copied race showed only a floating head and hair**: HumanRace's skin (`Skin_Naked` 000D64, armatures 012204 and
030580) names HumanRace and two other races, not the copy. The hand quest stayed silent (no hand log); `init` still logs refs none
(unresolved temporary refs, as before). So the race copy is the wrong tool without its own skin and armatures.

Changed (option b of the PC's two, offline only, awaiting a third PC run): **the entry no longer calls `SetRace`**; the player stays
HumanRace; the three ARMO name HumanRace (with `--frame-art` / `--piece-art` they keep the copied vanilla ARMO's own race and armature);
the value stays as it was; `check` refuses an ARMO that names the copied race. The screen says "race CHANGED" if anything else changes
it. `FO4SF_PARace` stays in the plugin for the console probe (its stage 20/30 swap is the PC-proven both-ways result) and is only
logged at init. **Not done:** (a) the own-skin kit race (copies of Skin_Naked and its two ARMA naming the copy, plus armatures per
piece); worth it only if the suit needs its own skeleton or size. **Equip may still be refused** with no art: an ARMO with no armature
may not equip even for HumanRace; the rerun decides, and `--frame-art` is the fallback (give it any vanilla ARMO).

### PC runs of #733 at 1a6096e1: PASS with art, FAIL without (FAL-361)

Verified by the PC (10:51 and 11:01 UTC, test save, no save): **without art** the equip is refused again (`armor cannot be equipped by the
passed in actor's race`) although the race is untouched and the ARMO read HumanRace: an ARMO with no armature cannot be worn, whatever
race it names; the character stays whole in third person. **With `--frame-art Spacesuit_Mark1_Body --piece-art Spacesuit_Mark1_Helmet`
the whole entry passes**: equipped 3 of 3, value 1.0, race unchanged, "the suit is ON"; the exit gives bag 0 of 3, equipped 0 of 3, value
0, "the suit is OFF"; no Papyrus error. Third person: a suit body and pack with a **bare head** (the helmet copy was forced into the Hat
slot and drew nothing); after the exit the character looked as before.

Changed offline (awaiting a fourth PC run), the PC's four findings:

1. **Art is not optional.** The tool and the stager default to `Spacesuit_Mark1_Body` (frame) and `Spacesuit_Mark1_Helmet` (both pieces);
   a missing name refuses the stage by name; `none` is the offline tests' explicit opt-out and `check` then refuses nothing else.
2. **A copied piece keeps its own slot** (the helmet's), not the slot we named; only an armature-less piece (`none`) gets our slot.
   Both pieces carry the helmet art by default, so the "torso" piece is a second helmet: if a body plate is wanted, give a real one.
3. **What the player wore is recorded and put back.** At entry the script records every distinct worn item (`Actor.GetWornItem`, `;OPT`,
   up to 64) before the suit goes on and logs `saved worn=N`; at exit, after our pieces are removed, it equips them again and logs
   `restored worn=N` and says so on screen. When the game cannot list the worn items it says so at entry and nothing is put back.
4. **`init` refs none** is unchanged: unresolved temporary references of an unloaded cell (FAL-316); not a fault of the entry.

Card changes: step 1 stages with the defaults (no art options needed); step 7 adds "the character wears what it wore before".
Not yet seen: first-person arms, the inventory screen, a second enter and leave, the 120 s exit, the restore of a changed outfit.

### PC run of #733 at 8fe7c27e: FAIL, and the fixes (FAL-361)

Verified by the PC (11:37 to 11:44 UTC, test save, no save): equipped **2 of 3** (both pieces were the helmet copy in the same slot, one
pushed the other off); in third person with the suit ON the character stood in plain clothes (the copies took the place of the own
suit, pack and helmet, and none of the copies was drawn); after the exit the own gear **did not come back** (`Actor.GetWornItem` is not
declared in Starfield's scripts, so nothing was recorded). The best state so far stays 1a6096e1 with art (PASS, slots BODY / Hat).

Changed offline (awaiting a fifth PC run):

1. **Two pieces, two slots.** New `--pack-art` (default `Spacesuit_Mark1_Backpack`, 01754E on the PC, one armature) for the second piece;
   the helmet piece keeps `Spacesuit_Mark1_Helmet`. Each copy keeps its own slot.
2. **Worn gear by events, not by listing.** `GetWornItem` is removed. Just before the three `EquipItem` calls the script registers for the
   player's `OnItemUnequipped` (`RegisterForRemoteEvent`, `;OPT`, with the handler `Event Actor.OnItemUnequipped` also `;OPT`, each
   compiled on its own), records every base object that comes off for 1 s (ours excluded), logs `saved worn=N watch=<bool>` and shows
   "your gear that came off: N"; the exit equips them again (`restored worn=N`). If the registration does not compile, the screen says
   the gear will not be put back. **Not run offline:** whether the player's event fires for an unequip caused by a slot clash, and the
   Papyrus compile of the remote event form.
3. **A frame-only stage** (does a copied suit body draw at all in the SSBODY slot?): `--piece-art none --pack-art none`. The two
   pieces then have no armature and their equip is refused (an error in Papyrus.0.log, expected), the frame equips alone, and the
   screen reads "equipped 1 of 3".

Not changed: the look. Whether copies of the vanilla suit pieces draw over the character's own gear is what the PC run decides; the
gear-restore should be read from the outfit in third person after the exit, not only from the log.

### PC run of #733 at 59a76008: the logic passes, the copies are not drawn (FAL-361)

Verified by the PC (12:02 to 12:09 UTC, test save, no save): entry `unequipped item=` x3 (the character's own suit, helmet and pack),
`saved worn=3 watch=true`, equipped 3 of 3, value 1, "the suit is ON"; exit `restored worn=3`, bag 0, equipped 0, value 0; **in third
person after the exit the character's own suit, pack and helmet are back** (the `OnItemUnequipped` record works). With the suit ON the
character is in plain clothes: the three copies are worn and not drawn. A console `additem` + `equipitem` of the vanilla Mark 1 body
01754D, helmet 01754F and pack 01754E draws fully, so the game draws a vanilla set and the fault is in the copies. A record compare
(staged FO4SF_PAFrame against 01754D): the copy had **no KSIZ / KWDA** (vanilla: five keywords) and a DATA of twelve zero bytes (vanilla
value, weight 7.5, health); the five armature links, RNAM, BO64 and templates matched.

Changed offline (awaiting a seventh PC run): the tool no longer strips the copied ARMO: keywords, value, weight and health stay the
source's (only an armature-less piece, `none`, is built bare); `check` prints them and refuses a copy whose keywords, value, weight or
health differ from its source. **Whether the keywords are the whole cause is the PC's inference, not yet shown**: if the copies still
do not draw, the next suspect is the copy's missing instance data (templates and object-template combinations) or a keyword the game
reads from the FormID of the original. Not seen yet: first person, the inventory screen, a second enter and leave, the 120 s exit.
