# The planet probe: our planet and a test world, before the Commonwealth moves (29 Oct 2026)

For: the Install session on the owner's PC, and anyone reading the result. Plan: the "Strip Starfield down and give
the Commonwealth its own planet" plan of 29 Oct, step 1 of its order of work. The plan recommended route A (our own
star system); the owner picked route B (29 Oct, typos fixed): "B, but in the end there should be no other planets",
that is our planet in Sol. Since PR 4 the kit builds route B by default (section 3a) and keeps route A as an option
(`stage --system own`). Nothing here runs by itself, and nothing installs until the owner types the line in section 6
in the Install thread.

Status: **probe run 1 (route A) ran on 29 Oct** (section 8); **route B is built and checked offline only.** The C#
tool and the checks pass on synthetic masters and on a Bethesda Creation's records (cloud, 29 Oct). Every Starfield
fact below says how it is known: verified (read from a file or log), supported (a strong hint, not proven) or
hypothesis.

## 1. The question

Starfield never plays our worldspace directly. On a planet it plays a runtime copy of the planet's world (for
example MarsPlanetWorld, `FF00C482` on 29 Oct) and merges our overlay world into it. Our persistent references
(Codsworth, doors, markers) stay behind in the base world, so every system of ours needs a script that moves things
(verified from the 29 Oct mission log: the Codsworth keeper moved him at 00:10:21Z; by 00:13:39Z he was back in
`04000803`).

The offset is not the cause: vanilla LC172World also lands off-centre, about (-500, -2300), and its own persistent COC
marker `0010238E` moves with the merge (verified, 11 Oct). Two fixes failed (A, the persistent cell's shape; E, the
OFST / CLSZ tables). Two ideas were never tried:

* the **location links**: an LCPR row on the world's location and an XLCN on the reference. Bethesda's own Creations
  do this, and our records do not (verified: SFBGS00D.esm SFFLDR022World keeps 18 of 18 actors as **temporary**
  ACHRs with XLCN and an LCPR row; our core's location has no LCPR and our markers no XLCN);
* **MergeProbe**: one persistent marker of a plugin of ours inside vanilla LC172World's own persistent cell.

The probe answers one question above all: **which persistent test reference is in the player's world with no script
moving it?** It asks it on our own planet (in Sol with route B; run 1 used our own star system), so the same session
also shows whether that move works at all.

## 2. The six test references

All six stand in the spawn cell (0, 0) of the test world, around the arrival, on flat ground:

| Tag | Record | Placed | Location links | Stands for |
|---|---|---|---|---|
| T1 | REFR XMarker | persistent | none | our core's markers today |
| T2 | REFR XMarker | persistent | XLCN + LCPR row | a fix for markers and doors |
| T3 | ACHR citizen | temporary, in the spawn cell | XLCN + LCPR row | Bethesda's Creation pattern |
| T4 | ACHR citizen | persistent | none | our Codsworth today |
| T5 | REFR XMarker | temporary, in the spawn cell | none | the control: plain cell content |
| T6 | ACHR citizen | persistent | XLCN + LCPR row | a fix for Codsworth |
| T7 | REFR XMarker | persistent, stored in the spawn cell's own persistent group (run 2) | none | rank 2 of the `merge-diff` document (FAL-188): a persistent reference kept as a child of our own exterior cell |

Run 2 reads T7 as PASS (T7 with player, T1 left behind), FAIL (T7 left behind or not loaded) or confounded (T1 and T7
both with player), after the LC172 control (MERGE and LC172COC with player); `probe_log.t7_result`. The stage option
`--alignment relative` (default `absolute`) builds the second kit with the block's INAM 0, as vanilla's LC overlays.

The citizen is Starfield.esm's EncCitizen01Template (`2B211C`), the calm NPC the combined-core probes placed. The
same session also reads two references in LC172World: `MERGE` (FO4SFMergeProbe.esm's marker, persistent, in vanilla's
persistent cell) and `LC172COC` (vanilla's own persistent COC marker `0010238E`, the control that moved on 11 Oct).

## 3. What gets built

Everything is cloned at stage time from the user's own game files. No Bethesda bytes enter the repo or ship.

**FO4SFPlanet.esm** (master Starfield.esm only; adds records, overrides none; `src/fo4sf/planet/records.py`). Route
B, the default (section 3a):

* `0x802` to `0x804` LCTN, the planet, orbit and surface locations, with the DATA of Jemison's locations they copy
  and the keyword of each (checked by EditorID). The planet location's parent is **Sol's own system location** (a
  Starfield.esm record, found at stage time: the one location with the LocTypeStarSystem keyword and Sol's system id);
* `0x805` PNDT, a clone of Jemison with our name, Sol's system id and our planet id, no master worldspaces (Jemison's
  register New Atlantis), no edited worldspaces, no unique space cell, and no fauna or flora in its biomes. Gravity,
  day length, atmosphere, temperature and the orbit stay Jemison's.

Route A (`--system own`, run 1's) adds `0x800` STDT, a clone of Sol's star with our name, our own system id `0xF04F1`
(checked against every star of every plugin in Data: Starfield.esm, the DLC, the built-in Creations and any mod) and
a free map position 2 / 2 / 1 parsecs from Sol, and `0x801`, its system location (parent Universe), the parent of
`0x802`.

The master is written with our own raw writer (`src/fo4sf/planet/esm.py`), not Mutagen: Mutagen 0.55's Starfield
schema lacks some star fields (STDT SNAM, HNAM and WED0), so a Mutagen copy would drop them. A clone keeps every
subrecord of its template byte for byte, except the ones listed above.

**FO4SFPlanetProbe.esm** (masters Starfield.esm and FO4SFPlanet.esm; `dotnet/PlanetProbe`, layout in
`src/fo4sf/planet/probe.py`):

* `0x800` to `0x805` the six test references, `0x806` a COCMarkerHeading (`coc FO4SF_PlanetProbeSpawn`);
* `0x807` SFBK, the overlay block: our 3 x 3-cell BTD, Absolute alignment (BTD heights are world z);
* `0x808` LCTN, the probe location: LC172WorldLocation's fields without its references, keyword LocTypeOverlay,
  parent our surface location, one LCPR row per linked reference;
* `0x809` WRLD, a copy of LC172World without its cells, offset tables, large references or parent. Its overlay
  component names **our** system id, planet id and block. Its climate stays LC172's (Mars), so the sky tells whether
  the world record or the planet decides it. Its biome is one of the planet's (`--world-biome planet`, the default:
  New Atlantis's own biome when it is one of Jemison's);
* `0x80A` the persistent cell, `0x80B` to `0x813` the nine exterior cells (-1..1), `0x814` the quest
  FO4SF_PlanetProbe (start game enabled, script FO4SF_PlanetProbeQuest, no properties).

**FO4SFPlanetProbe_Reg.esm**: our planet again, with one master worldspace (the test world at latitude 0,
longitude 0), the separate registration plugin the terrain core also uses.

**FO4SFMergeProbe.esm** (`dotnet/MergeProbe`, unchanged): the marker in LC172World's persistent cell, at vanilla's COC
marker + (3, 0, 0).

### 3a. Route B: our planet in Sol

* **The system id** is Sol's star's DNAM: 0 on 1.16.244 (verified: run 1's census read SolStar `0005E5CB`, system id
  0, and Mars's GNAM is (0, 0, 4)). The stage reads it again from the user's Starfield.esm.
* **The planet id** is the first free one in Sol: one more than the largest body id there (planets and moons share
  one numbering; a moon's GNAM names its planet as the parent), the largest location YNAM there and the largest
  planet id an overlay world names there (the game merges an overlay world into the planet whose id it names, as
  LC172World into Mars), counting Starfield.esm and every other plugin in Data, overrides too (`records.sol_facts`).
  An id that reads negative as a signed number is taken for unset and not counted (our convention, a hypothesis
  about the game; our own id stays below it either way); the census lists such bodies, and the bodies without a
  readable GNAM, under `not_counted`. An installed copy of our own master, registration or probe plugin is left out:
  their records are the ones rebuilt. Taking one more than the largest id is a hypothesis about what the game
  expects; the census's precedent list (section 4) shows whether the bodies the Creations add follow it.
  `check --stage <stage> --data <Data>` (section 6) and the install itself read every plugin again and stop when one
  installed or updated since the stage takes the id, or when one cannot be read that the stage did not already note
  as unreadable.
* **The parent** of our planet location is Sol's system location, as a vanilla planet location names its own
  system's location (supported: Starfield's scripts find a planet location's star system among its parents; the
  stage records the parents of Jemison's own locations in `master_report.json`, so the PC's stage shows it). A system
  location's layout is verified on Algorab's `SAlgorab`, which SFBGS00D.esm carries: XNAM 60776, YNAM 0, parent
  Universe. We add no star and no system location, and override none.
* **The orbit** stays Jemison's: mean 224.96 million km (1.50 AU), very close to Mars's 227.94 million km (1.52 AU;
  both read from the records: Jemison in run 1's census, Mars in FO4TerrainCore_Mars.esm's copy), and both start at
  angle 0. On the system map ours may sit next to Mars. That is fine for the probe. For the final planet the owner
  picked Earth's orbit (29 Oct); it comes with the move of the Commonwealth.

**Data files**, packed into "FO4SFPlanet - Main.ba2" at install (loose files are not read on this install, verified
in October): the BTD (flat ground at 10 m and a 30 x 15 m block 25 m high north of the arrival, so a screenshot tells
our ground from the planet's), its overlay mask, the script, and the biome map.

**The biome map** (`src/fo4sf/planet/biom.py`): Jemison's `.biom` copied out of the user's own
"Starfield - PlanetData.ba2" under our planet's name. Which folder the game reads for a plugin's planet is not known
(hypothesis), so the copy goes to both `Data/PlanetData/BiomeMaps/fo4sf probe.biom` and
`Data/PlanetData/BiomeMaps/fo4sfplanet.esm/fo4sf probe.biom`. Verified in the cloud on the real archive: Jemison's map
is there and lists five biomes. Whether they are the planet record's biomes is checked at stage time and recorded in
`offline_check.json` (a difference would be Jemison's own, so the copy is kept).

## 4. The census

`make_planet_probe.py census` (and the first step of `stage`) reads, without writing anything
(`src/fo4sf/planet/census.py`): the template star and planet; every star id in use; the three records the test world
copies and the three bases it places, each checked by EditorID (a missing or renamed one stops the stage);
LC172World's references (how many are persistent, how many carry XLCN / XLRL, and whether `0010238E` is in
LC172WorldLocation's LCPR rows); Mars's master worldspaces; the planet of every overlay world; and the coc cells of
the other arrivals (an exterior cell with an EditorID and a COC marker in TempJemisonWorld and in New Atlantis). It
goes into `census.json` in the stage.

For route B it also reads Sol (the `sol` part): its system id and system location, every body, location and overlay
world id in use there (with the ones not counted, `not_counted`) and the first free planet id, and **the
precedent**: each body a plugin adds, with the largest vanilla body
id of its system, and what each plugin's override of a vanilla star system location changes. What the staged
Creations hold (verified in the cloud, 29 Oct): SFBGS00D.esm adds three bodies to vanilla systems (Anchorpoint,
planet id 10 in Algorab; two more with parent 1) and SFBGS003.esm one (the Chop Shop, planet id 13 around planet 8 of
its system). All four are body type 4 (the planets read are type 2), so none is a planet with a surface, and none
comes with a planet, orbit or surface location. SFBGS00D.esm also overrides `SAlgorab`, the system location of the
system it adds Anchorpoint to, with a second keyword (`00061990`); it adds the other two bodies without such an
override. Whether those ids are one above each system's vanilla ones, and what the `SAlgorab` override changes, need
Starfield.esm: the census on the PC records both. If the census cannot find Sol's system location exactly once, it
says so in `sol` and a route B stage stops.

## 5. Reading the run

`make_planet_probe.py log --stage <stage>` reads `FO4SFPlanetProbe.0.log` in `My Games\Starfield\Logs\Script\User`
under `OneDrive\Documents` (where the owner's PC keeps it), else under `Documents`; `--file` names another
(`src/fo4sf/planet/probe_log.py`). The script logs each arrival (another worldspace, another interior cell, or a jump
over 500 m) and reads everything 2, 10, 30 and 60 s later. Each reference gets a verdict at each arrival:

* **with player**: found, in the player's worldspace;
* **left behind**: found, in another worldspace (for ours: the base probe world the game never plays);
* **not loaded**: not found, a temporary reference whose cell is not loaded;
* **not installed**: its plugin is not loaded;
* **unknown**: the line lacks a value the verdict needs (a cut line), or the reference and the player are both in
  interiors (none of the four arrivals is one).

Starfield prints a bool as `true` / `false`, and it can print literal text in another case (both verified: the
bridge log of 14 Oct and the new game log of 28 Oct, which printed `FO4Port.esm` as `fo4port.esm`). The reader
ignores case everywhere, so the verdicts do not depend on how a word comes back.

The offset (position now minus position in the plugin) shows whether a merged reference moved with its world. The
distance to the player is left out of the table for a reference in another worldspace: the game returns the largest
float there, 3.4e38 (verified: run 1, 31 of 33 readings).

**The chain line**, written once at the start, shows how the game joins our locations. Two things it leans on are
untested, so each link gets more than one reading.

* **Which way IsChild reads** (unresolved). Starfield's Location.psc says it "Returns whether the other location is
  a child of this one", and ObjectReference.IsInLocation calls it so: the parent asks (supported). Some vanilla
  quest scripts call it the other way round, the child asking about its parent (MQ204's and UC04's; supported too).
  So version 2 of the script asks it both ways, named `<caller>_ischild_<argument>`: `surface_ischild_probe` and
  `probe_ischild_surface`, `planet_ischild_surface` and `surface_ischild_planet`.
* **GetParentLocations with no keyword**, which no vanilla script calls. The script lists what it gives each of our
  three locations (`probe_parents`, `surface_parents`, `planet_parents`), and also asks the way SQ_ParentScript finds
  a planet location's star system and a site's planet and star system, with a keyword: `planet_systems` and
  `probe_systems` with LocTypeStarSystem, `probe_orbitals` with LocTypeMajorOrbital (the script reads both keywords by
  id, so the stage stops if either id differs in the user's Starfield.esm). SQ_ParentScript's site lookups suggest a
  list holds every ancestor, not only the direct parent (supported, not proven).

The reader looks for each location's own parent in our records in that location's own lists: the probe location under
our surface, our surface under our planet location, and our planet location under the system location (Sol's with
route B, named from `plan.json`). So the answer does not depend on how far a list goes. A link is a `PROBLEM` line only
when every reading of it says no. Readings that disagree are a `NOTE`, and so are an IsChild that answered when the
child asks (or both ways) and a keyword lookup from the probe location that does not find our planet location or the
system location. The reader also prints whether the probe location's own list goes past its parent. The line ends
with `end=true`: a line without it was cut, so the reader leaves its last value out unless it is a bool (a list cut
short could miss a parent; a cut `true` or `false` never reads as a bool) and says so in a `NOTE`. Run 1's chain line
came from version 1, which asked IsChild one way only (the child about its parent): the reader prints a `NOTE` that
those two values settle nothing (section 8).

What each result means for the move (section 5 of the plan):

| At our planet | Meaning | Next |
|---|---|---|
| T2 and T6 with player, T1 and T4 left behind | the location links carry persistent references into the played world | the re-home patch adds LCPR rows and XLCN to our core's persistent references; the movers can go |
| T3 with player, T2 and T6 left behind | only temporary references with links follow, as in Bethesda's Creations | our actors become temporary references with links |
| all six with player | our planet's world is played as it is, no copy | owning the planet fixes the split by itself |
| T1 to T6 all left behind | no plugin persistent reference follows the merge | the movers stay, or a standalone world (TempJemisonWorld's result) |
| no arrival on our planet, or a crash | our planet record is wrong (with route A, our star system's too) | read the crash and the census; run 1 arrived with route A, so a stage with `--system own` tells what Sol changes (the planet id, the parent) from the rest |
| a chain `PROBLEM` line | the game does not join our locations where the line says | fix that link first: the linked references (T2, T3, T6) hang from the probe location |

| At LC172 | Meaning |
|---|---|
| MERGE with player | a plugin's persistent reference merges in a vanilla world: the cause is in our own WRLD / LCTN records |
| MERGE left behind, LC172COC with player | only Starfield.esm's own persistent references merge |

The planet line at our planet gives the gravity, day length and temperature the game uses there: Jemison's values
mean our cloned record is read. TempJemisonWorld shows whether a standalone world (no overlay component) is played
directly. New Atlantis is the vanilla baseline on the planet ours copies. The sky in the screenshots shows which
record decides the climate (ours keeps Mars's on purpose).

## 6. Stage, install, run, take out

The owner's line, typed in the Install thread (the PC's guard needs the owner's own words for builds, installs and
holds):

> Stage the planet probe (build its tools, compile its script), install it for one test session, run its four
> arrivals and read the log, then take it out.

The same line serves every run. Run 2 (after PR 4) builds route B, our planet in Sol, because `stage` does so by
default; `stage --system own` builds run 1's route A again.

Steps for the Install session (PowerShell, repo at main after the PR merges):

```powershell
$sf = 'D:\SteamLibrary\steamapps\common\Starfield'
$stage = "D:\Modding\staging\planet_probe_$(Get-Date -Format yyyyMMdd_HHmm)"
python scripts\planet\make_planet_probe.py precheck
python scripts\planet\make_planet_probe.py stage --data "$sf\Data" --out $stage
python scripts\planet\make_planet_probe.py check --stage $stage --data "$sf\Data"
# game closed:
python scripts\planet\planet_probe_install.py install --dir $stage --starfield $sf
```

Then in game, from the session's dedicated test save (never the owner's own, and never saved over one), in the
order `plan.json` and the stage's README give: `coc LC172Ext01`, `coc FO4SF_PlanetProbeSpawn`, then the census's
TempJemisonWorld and New Atlantis cells. Stay 75 s at each, with one screenshot after 10 s and one after 60 s. The
LC172 control goes first, so its readings are in the log before our planet is tried.

```powershell
python scripts\planet\make_planet_probe.py log --stage $stage --out "$stage\run_summary.json"
# game closed:
python scripts\planet\planet_probe_install.py uninstall --starfield $sf
```

Rules:

1. **Game closed** for install and uninstall: Starfield rewrites Plugins.txt on launch.
2. **It rides along.** `planet_probe_install.py` runs exp_install.py's code against its own record
   (`Data\FO4SFPlanetProbe.install.json`); the installed experiment (the core set) is not read or changed. The four
   plugins go to the end of Plugins.txt; `order` and `active` work as for exp_install.py.
3. **No holds needed.** Our core keeps LC172World registered on Mars (verified: the installed FO4TerrainCore_Mars.esm
   lists 02DF8C first, then the core world). A plugin_toggle.py hold makes install and uninstall refuse; install
   first, hold after, and put the holds back before the uninstall.
4. **A failed launch is a result.** If the game does not reach the main menu, uninstall (game closed), launch once
   clean, and send the crash dump's name.
5. **Send back**: the log summary (`run_summary.json` and the printed table), the screenshots, `census.json`,
   `master_report.json` and `offline_check.json`. Nothing from the PC is committed.

## 7. Assumptions and gaps

* Route A: the game plays a planet in a star system that only a plugin adds: verified for a coc arrival in run 1
  (section 8); the star map and travel there were not tried. Community precedent: SFStarEditor's systems (read as a
  layout reference only, its code is CC BY-NC-SA and none is copied). Bethesda's Creations add bodies to existing
  systems but no star (verified: no STDT in the built-in Creations).
* Route B: the game takes a planet that a plugin adds to Sol: supported, not proven. The Creations add bodies to
  vanilla systems (section 4), but all four are body type 4 and none has a surface. Taking one more than the largest
  id in use: hypothesis, which the census's precedent tests against the Creations' bodies.
* Sol's system location is the one location with the LocTypeStarSystem keyword and Sol's system id, or the one of
  them whose parent is Universe: hypothesis about Starfield.esm, checked at stage time (the stage stops otherwise).
* The coc into our planet's world builds the planet from our records: verified for route A in run 1 (our planet's id,
  Jemison's gravity, day length and temperature, our name on the HUD); a landing from orbit was not tried.
* The biome map's folder for a plugin's planet: hypothesis (both are staged). Run 1's icy ground outside our cells
  suggests that neither copy was read (supported, not proven).
* Which way IsChild reads: unresolved (the parent asks, by Location.psc's comment and IsInLocation; the child asks, by
  MQ204's and UC04's calls). The script asks both ways; run 2's chain line settles it (section 5).
* GetParentLocations with no keyword: untried in vanilla (every vanilla call passes one). A list may hold every
  ancestor (supported: SQ_ParentScript asks a site's location for its planet and star system with a keyword). The
  reader depends on neither (section 5).
* A user log stays open only in the game session that opened it (Skyrim and Fallout 4); the script reopens it when a
  write fails.
* Mutagen 0.55 writes the LCPR grid as Y then X (verified on a written plugin with a nonzero grid, 29 Oct).
* Form ids in the log are signed decimal; the reader converts them, and names the probe's from the init line.

## 8. Probe run 1 (29 Oct, route A)

Run by the Install session on the owner's PC on 29 Oct, about 05:05Z, with PR 1's kit (route A: our own star and
planet). The probe was taken out afterwards and Plugins.txt was back as it was. Read from the run's log, its
`run_summary.json` and the Install session's report; nothing from the PC is in the repo.

* **Our planet loaded from our records** (verified). At arrival 3 (`coc FO4SF_PlanetProbeSpawn`) the player stood on
  our planet (`0B000805`) in a runtime world (`FF0102FE`), with Jemison's gravity 0.91, day length 50 and temperature
  21, and the HUD showed our planet's name, not Mars. The player's parent cell (`0C00080A`, our persistent cell) and
  location (`0C000808`, the probe location) were ours.
* **No test reference of ours came along** (verified). T1 and T2, the persistent markers, stayed in the base probe
  world (`0C000809`) and our persistent cell, not loaded; T4 and T6, the persistent actors, read no world; T3 and T5,
  the temporary ones, were never found. So neither our own planet nor the location links (T2, T6) brought a
  persistent reference into the played world in this run.
* **MERGE and LC172COC came along at LC172** (verified). Both stood in LC172's runtime world (`FF008DFC`) at the offset
  (-500, -2300), as the COC marker did on 11 Oct. A plugin's persistent reference in vanilla LC172World's persistent
  cell merges like Starfield.esm's own, so the cause of the split is in our own world and location records, not in
  being a plugin.
* **The chain line settles nothing yet.** Version 1 of the script asked IsChild one way only, the child about its
  parent, and read false and false. If the parent asks (Location.psc's comment), a working chain reads so; if the
  child asks (as some vanilla quest scripts call it), the chain was broken. Its GetCurrentPlanet readings (the probe
  and surface locations both on our planet `0B000805`) point to a chain that works (supported). Version 2 asks both
  ways and lists every location's parents (section 5).
* **Icy ground outside our cells**: our copy of the biome map was not read (supported, not proven).
* **The session itself**: only three arrivals were logged (the start on Mars, LC172 and our planet; not the
  TempJemisonWorld and New Atlantis ones), with readings up to 30 s at most. The session's own driver script took
  every console command for refused, so it skipped the 75 s stays and the timed screenshots; the Install session has
  fixed that script. There was also one LandingPad "cannot be moved" error and a burst of None errors after the spawn
  arrival.

Open after run 1: why our persistent references read our persistent cell as their parent cell (in the base world)
while the merged LC172 ones read none (in the played world), when `dotnet/PlanetProbe` writes ours into the world's
persistent cell as Bethesda's are; whether
our exterior cells load at all in the played world (T5, plain cell content, never loaded); and where the game reads a
plugin planet's biome map. Run 2 (route B, section 6) answers whether our planet works in Sol and what the chain
really is.
