# Exterior lights: FO4 LIGH -> native Starfield LIGH (core64 builds)

Author: Claude, 2026-10-16. Status (checked 2026-11-06, Mountain): **owner night check recorded on core64k / core64l**
("the lights are very bright"); see [Calibration (17 Oct)](#calibration-17-oct). That check does not establish
acceptance of the later 0.375 lumens patch or the comparison screenshots under "Not done / open".
Labels as in the other terrain docs: **verified** means read from files, **supported** means a hypothesis with
evidence, **unresolved** means open. The owner's playtest found the nights dark: core64c placed none of FO4's
6,275 exterior Light references (`exterior.TYPE_REASONS`).

## Path

```
python scripts/terrain/make_cluster.py lights --work <core64c work> --fo4 <Fallout4.esm> --out lights.json [--lumens-per-m2 333]
python scripts/terrain/make_core64c.py stage ... --cluster <cluster with "lights" (and "containers", "items")>
# --cluster takes one file: the dry run below merged the containers and lights lists by hand (no merge step yet)
python scripts/terrain/make_core64c.py check ...
python scripts/terrain/light_census.py --sf-esm <Starfield.esm> --fo4-esm <Fallout4.esm>   # the evidence below
```

1. **`make_cluster.py lights`** reads every exported reference of type `Light` from the band exports. The exports
   carry no light data, so it reads the rest from `Fallout4.esm` with the raw record walker (`src/fo4sf/fo4light.py`
   over `fo4land`; no Mutagen):
   - the LIGH bases;
   - each reference's own light fields (`XRDS`, `XLIG`, `XEMI`), found in the Commonwealth worldspace.

   It maps both to Starfield fields (tables below) and writes `{"light_bases": {FO4 base: fields}, "lights": [...]}`,
   ordered by FO4 source key.
2. **`make_core64c.py stage --cluster`** (`cluster_lights`, `stage_lights`) works in three steps:
   - It converts positions to metres and cells, and drops lights outside the overlay's cells as `outside_terrain`.
   - It names one LIGH per FO4 base, `FO4Core_ligh_<6 hex>_<plugin>`, formed the same way as the container names.
   - It refuses a light whose source is a placed or promoted (container or item) reference, a light listed twice, an
     unknown base, an XLIG fade outside the vanilla range, or `record_flags` missing or holding a bit other than
     0x100 / 0x10000 / 0x20000 (a cluster written before the review of #246: run `make_cluster.py lights` again).

   `objects.json` gets `lights` and `light_bases`. The promoted lights leave `skipped.json`, so placed + promoted +
   lights + skipped still add up to the export.
3. **`TerrainOverlays`** writes the records: `ReferenceIdentityPlan.Lights` validates the input before anything is
   written, then the writer adds the light block after the NAVM block. Each LIGH is a copy of the vanilla
   `LGT_Interior_Omni_NS_Warm_004_2k` (12A74B:Starfield.esm) with the mapped fields. That light is the second
   most-placed omnidirectional light in vanilla exterior cells (328 placements; 3AC1EB LGT_Interior_Omni_NS_Red_002_75k
   has 329, the review of #246), so every Starfield-only field (contact shadow
   component, barndoors, roundness, gobo data, area light, layer, adaptive lighting, volumetric scale) is a vanilla
   value. Its CK object-window filter component is dropped. Each light gets one temporary REFR in its cell.
   `formids.json` gets `"lights": {src: {"base", "ref"}}`, but only when there are lights.
4. **`check`** verifies the result:
   - the light identities (`check_light_identities`), and that every light record comes after the rest
     (`lights_after`);
   - LIGH count = light bases;
   - the REFR total includes the lights;
   - each LIGH's raw `DAT2` (radius, colour, flags, lumens, type, flicker effect) and each light REFR's base,
     position, flags, `XRDS` and `XLIG` (`light_record_problems`);
   - lights per cell, and each light in the cell of its position.

   The NAVM-order check ignores the light REFRs, which come after the NAVMs.

## Reference identities: which FormIDs the lights get, and why

The lights get **new** FormIDs, placed after every other record of the build: first the light REFRs in `lights` order,
then the LIGH bases in first-use order. On core64g's inputs (containers + navmesh) the first light REFR is **0A5AA3**,
right after core64g's last NAVM (0A5AA2).

- **No slot to keep.** `ReferenceIdentityPlan.Order` keeps a promoted source's original REFR slot because that
  source *had* a REFR in the earlier builds (containers are placed statics first). core64c never placed a light, so a
  light has no earlier id. `ReferenceIdentityPlan.Lights` refuses a light that claims a `reference_index`, or whose
  source is one of the reserved ones.
- **Appending moves nothing.** Every id after an inserted record would shift by the number of lights: 6,249 REFRs
  plus 144 bases, landing on CONT bases and NAVMs that a save or the NAVI may already name. Appended at the end,
  every record of the build without lights keeps its id and its bytes:
  - the synthetic writer test compares this byte for byte;
  - the full-scale dry run below compares every `formids.json` entry.
- **REFRs before bases**, as with containers: the ids a save can hold come first.
- **Limit (as for CONT bases, docs/testing/container-reference-identities.md).** A later build that adds records in
  front of the light block moves the whole block. #235's MISC bases (merged into this branch) sit before the NAVMs,
  so a build that adds items shifts the NAVMs and the lights alike, but never onto another record's id; the synthetic
  writer test builds containers, items and lights together. A persistent allocator (#227) would make the
  light ids stable as well.

## Field mapping: LIGH base

The FO4 side was read raw from `Fallout4.esm` (`DATA` offsets in `fo4light.parse_ligh`). On all 146 Commonwealth
exterior bases it agrees field by field with Mutagen.Bethesda.Fallout4 0.55 (**verified**: 146/146 bases and
6,275/6,275 references, cross-checked in C:\Modding\scratch\exterior-lights\crosscheck.py).

The Starfield `DAT2` offsets come from the raw records of six vanilla exterior lights: 07AA05, 0D3DC7, 12A74B, 15AE5B,
1690FC, 363BEF. They agree with Mutagen.Bethesda.Starfield 0.55's typed values (**verified**). `light_census.py`
recomputes the counts in the tables from raw records, and its numbers equal the Mutagen-based scratch dumps. Three
counts are not in its output: 924 (the +48 word), 19,281 (non-zero XLIG FOV) and 328 (template placements); the
review of #246 recomputed them from raw records and found them correct.

"Shared" in the evidence column means the **21 LIGH records that Starfield.esm holds under the same FormID and
EditorID as Fallout4.esm**: MuzFlashLightMachineGun, defaultLight01-04, ExplosionLight*, FXFireLight01 and others.
They show how Bethesda carried FO4 lights over.

| Starfield (`DAT2` offset / Mutagen name) | From FO4 | Rule | Evidence | Label |
|---|---|---|---|---|
| EDID | base formkey | `FO4Core_ligh_<6 hex>_<plugin>` | same scheme as containers | - |
| OBND (6 f32) | OBND (6 i16, units) | / 70 | Starfield OBND are metres (12A74B: +-0.14 to 0.27) | supported |
| +0 Time | DATA time | copied (-1) | 146/146 FO4 bases and the vanilla lights are -1 | verified |
| +4 Radius (f32, m) | DATA radius (u32, units) | / 70, the project's unit (positions are / 70 too) | shared: 400->4, 340->5, 1600->25, 256->4, 128->2 (about / 64, rounded); native radii are 1-8 m | supported |
| +8 Color (RGBA) | DATA colour | RGB copied, A = 0 | 20 of 21 shared copy it; vanilla A = 0 | verified |
| +12 flag 0x1 | FO4 0x1 (dynamic) | carried | 1,560 of 1,575 vanilla set it; every shared FO4 record with 0x1 has it, every other FO4 bit is cleared | supported |
| +12 0x20 OffByDefault | FO4 0x20 | carried (35 refs: workshop bulbs) | Mutagen's name in both schemas; 18 vanilla | supported |
| +12 0x40 DisableSpecular | FO4 0x8000 non specular | carried (1,034 refs) | Mutagen's name only; 66 vanilla | hypothesis |
| +12 0x2 CanBeCarried | FO4 0x2 | carried (none in the Commonwealth) | Mutagen's name | - |
| +16 FalloffExponent | DATA | copied | shared copy it | verified |
| +20 FOV | DATA | copied (degrees) | shared copy it | verified |
| +24 NearClip | DATA (units) | / 70 | shared copy the unit value verbatim (7.2174); native lights use 0.15-0.25 m | unresolved |
| +28 FlickerPeriod, +32 FlickerIntensityAmplitude | DATA | copied | shared copy them; native `LGT_Exterior_Spot_SS_Warm_003_Flicker_4k` uses 1 / 1 | supported |
| +36 FlickerMovementAmplitude | DATA (units) | / 70 (a distance) | shared copy it verbatim but never flicker; 32 units is 32 m if left unconverted | supported |
| +52 PbrLuminousPowerLm | FNAM fade, radius | `333 x fade x scale x radius_m^2`, rounded, at least 1 | `LGT_*_2k / _8k / _75k` hold 2000 / 8000 / 75000; omni lumens / radius^2 over 4,712 vanilla exterior placements: median 333 (p25 78, p75 1,667); scale: next table | supported, needs a night screenshot |
| +56 Type | FO4 0x400 / 0x4000 | 0x400 -> 1 shadow spot (26 refs), 0x4000 -> 2 non-shadow spot (281), else 0 omni (5,942) | Mutagen enum; vanilla LIGH: 459 omni, 649 shadow spot, 467 non-shadow spot | supported |
| +57 FlickerEffect | FO4 0x8 flicker / 0x80 pulse | 1 flicker / 2 pulse (3,069 / 3 refs) | native flicker lights use 1; the shared records dropped flicker altogether (0) | supported |
| record flag 0x10000 | FO4 record 0x10000 | carried (Random Anim Start, 348 refs) | Mutagen's name in both schemas | supported |
| +40 ShadowOffset, +44 InnerFOV, +48 (Mutagen: PbrLightTemperatureK, 0x41200000), adaptive fields, +72 radius falloff exponent, FLCS/FLBD/FLRD/FLGD/LLLD/FLAD/FVLD | - | the template's | 924 vanilla carry the same +48 word without flag 0x200 | supported |
| MODL | FO4 model (424 refs) | **not carried** | 1 of 1,575 vanilla LIGH has a model; the fixtures are separate statics | verified (census) |
| NAM0 gobo (549), LNAM lens (149), WGDR god rays (7), SNAM sound | - | not carried | FO4 gobo textures are not converted; FO4 forms do not exist in Starfield | - |
| FO4 DATA constant / scalar / exponent / god rays near clip / value / weight | - | dropped | no Starfield field | verified |
| FO4 flags no rim (1,087), 0x2000 (1,050), shadow omni (6) / hemisphere (4), attenuation only, ignore roughness | - | dropped | no known Starfield bit | - |
| FO4 flag 0x100000 ambient only | - | **light skipped** (26 refs) | no Starfield equivalent; as a point light it would add white light | - |

## Field mapping: light REFR

| Starfield REFR | From the FO4 REFR | Rule | Evidence | Label |
|---|---|---|---|---|
| NAME | base | the LIGH of its FO4 base | - | - |
| DATA, XSCL | DATA, XSCL | position / 70, rotation copied, scale if != 1 | same rule as the statics | verified (check) |
| record flags | 0x100, 0x10000, 0x20000, 0x800 | **carried**: 0x100 DoesNotLightWater (3,238 refs), 0x10000 NeverFades (345), 0x20000 DoesNotLightLandscape (315), 0x800 = initially disabled (20 refs) | the names of `PlacedObject.LightMajorFlag` on the same bits in Mutagen.Bethesda.Fallout4 0.55 and Mutagen.Bethesda.Starfield 0.55.0-alpha.67 (the review of #246); 28,572 of 28,719 vanilla exterior light REFRs carry 0x100, none 0x10000 or 0x20000, so whether the engine honours those two is open; 3 vanilla have 0x800. Not carried: 0x200 CastsShadows (1 ref), 0x4 (57), 0x80 (34), 0x400 persistent (207; temporary, as the statics) | supported |
| XRDS (f32) | XRDS (units) | **a radius delta**, / 70 (5,816 refs) | FO4: no XRDS equals its base radius, and the smallest is -0.981 x the base, never at or below -1. Starfield: 10,596 of 24,841 vanilla XRDS are negative (FXFireLight01's refs: -0.836 on a 4 m base), but 413 are below -1 x their base radius (451 at -0.99 or below), which a pure delta would make a negative radius (the review of #246) | supported |
| XLIG FOV +/- | XLIG FOV delta | copied (degrees) | 19,281 vanilla non-zero, e.g. -52.6 on a 120 degree base | supported |
| XLIG fade | base fade + XLIG fade delta, XRDS radius | `ref_intensity / scale`, clamped to [0.01, 1.6] (1,671 of 6,249 clamp) | every vanilla XLIG fade lies in [0.01, 1.6] (median 0.45), never <= 0: a multiplier. Against it: Mutagen names the field `Fade1PlusMinus` in both games, and FO4's is a delta (3,709 of its 5,833 XLIG fades are negative) | hypothesis |
| XLIG end distance cap, shadow depth bias, volumetric | - | 0 | FO4: 0 on every Commonwealth light except the bias (1-50); vanilla uses 0 | supported |
| XLIG near clip | XLIG near clip delta (units) | / 70 | - | supported |
| XLIG trailing 8 bytes | - | `ab ab ab ab 00 ab ab ab` | 27,305 of 28,070 vanilla XLIG (all 32 bytes) | verified |
| XEMI (368 refs), enable parent (190) | - | not carried | same as the statics' enable parents | - |

**Intensity scale.** FO4 sets a light's intensity per reference: base fade plus the XLIG fade delta. Its size is per
reference too: base radius plus the XRDS delta (5,816 refs; their radius is 0.19x to 4.40x the base's, p10 to p90).
The lumens rule follows radius^2, so `fo4light.ref_intensity` is the fade ratio times (reference radius / base
radius)^2 (the review of #246: with the base radius alone, 090C85, 3.66 m + 12.43 m, got 4,871 lm where the rule
gives about 94,000). Relative to the base this ratio runs from 0.014 to 376 (p1 to p99) across the Commonwealth. One
LIGH per FO4 base cannot hold that range in the vanilla XLIG band, so each base takes the **median** ratio of its
references (`fo4light.base_scale`) into its lumens, and each reference keeps `ratio / median` as its XLIG fade. Four
cases follow:

- **Clamping.** 1,671 references clamp. If each base kept its own fade, 2,041 would. Against the rule at each
  reference's own radius, 5,298 of 6,249 references are within 2x (2,090 with the base radius alone).
- **References without XLIG.** They get one (fade `1 / median`, times their radius ratio squared) when that is not 1.
- **Lumens across the references.** p10 468, median 4,102, p90 68,391. The most-placed base, defaultLightFire01NSFlicker
  (746 refs whose XRDS shrinks them, scale 0.105), gets 468 lm at 3.66 m.
- **Beyond the vanilla radii.** The rule's 333 lm/m^2 comes from vanilla radii of 1-8 m. References with a large XRDS
  extrapolate it: DN156_DriveInProjectorLight (110 m) gets 12,695,923 lm, DiamondCityStadiumLights01NS (64 m)
  5,434,416 lm, SpotlightSpot01NS (76 refs, 18 m) 1,673,422 lm. The night screenshot should include one of them.

(Numbers from `make_cluster.py lights` on the scratch export with the reviewed rules,
C:\Modding\scratch\prep-246\light_stats.py and err_stats.py; the full-scale dry run below predates them.)

## Evidence files

Scratch files, outside the repo, in C:\Modding\scratch\exterior-lights (derived from game files, so not committed):

- `census.json`: the output of `light_census.py` on both masters.
- `sfbases.txt`, `sf_raw.txt`: the six vanilla lights, typed and raw.
- `fo4bases.txt`, `fo4_table.txt`: the 146 FO4 bases.
- `fo4_light_ref_overrides.json`: Mutagen's reading of the 6,275 references.
- `crosscheck.py`: the raw reader against Mutagen.
- `commonwealth_lights.json`: `make_cluster.py lights` on core64c's work.
- `core64g_lights\`: the full-scale stage and check, described below.

## Full-scale dry run (offline)

core64g's inputs were staged into scratch (`core64g_lights\`) and checked on 2026-10-16, at 4b3918c: before the
review of #246 carried the FO4 REFR flags and put the XRDS radius into the intensity. Those change the light REFRs'
flags and XLIG fades and the LIGH lumens, not any FormID or record count; the run was not repeated after them.

- `--core terrain_core64`;
- `--cluster` = `commonwealth_containers.json` + `commonwealth_lights.json`;
- `--navmesh` = core64g's `navmesh.json`.

**Verified:**

- **Lights.** `make_cluster.py lights` takes 6 s and writes 6,249 lights over 144 LIGH bases. The 26 ambient-only
  references are skipped, and none falls outside the cells.
- **Stage.** 158 s. FO4TerrainCore.esm grows from 192,662,677 to 193,414,549 bytes, and next FormID is 0x0A739C.
- **Check.** 254 of 254 checks pass in 184 s (core64g: 250; the 4 new checks are the light identities, the LIGH
  count, the order and the raw records). REFR total 654,609 = 643,173 + COC marker + anchor + 5,185 containers +
  6,249 lights.
- **Every earlier id kept.** Against core64g's `formids.json`, the plugin, world, bases, refs, containers, navmeshes
  and navi entries are identical. Against core64g's plugin, all **676,516 records are byte-identical** (signature,
  header flags, decompressed fields, parent group). The build adds exactly 6,249 REFR + 144 LIGH at
  **0A5AA3..0A730B** (light REFRs) and **0A730C..0A739B** (LIGH).
- **Unchanged files.** `objects.json` without the two light keys, `plan.json`, `overlays_params.json` and the Mars
  plugin equal core64g's.
- **Mutagen read-back.** A typed read with Starfield.esm as master finds 144 LIGH and 6,249 light REFRs in the
  exterior cells. 5,816 carry XRDS, 5,998 XLIG, 20 are initially disabled, all 6,249 have flag 0x100. By type:
  5,942 omni, 281 non-shadow spot, 26 shadow spot.

## Calibration (17 Oct)

The owner's night check of core64k / core64l: "the lights are very bright". A read-only comparison with the vanilla
exterior placements (Starfield.esm 1.16.244, omnidirectional lights) found why:

- Our lights are `LUMENS_PER_M2` (333, the vanilla median of base lumens / radius^2) x FO4's fade (median 1.0), written
  into the LIGH. Vanilla placements dim their bases with an XLIG fade of median 0.45, which ours (clamped to
  0.01..1.6) cannot make up for, because the base already carries the full 333.
- Omni lumens x fade, median: ours 2,827, vanilla exterior 1,234 (2.3x). Lumens per m^2 of radius, median: ours 211,
  vanilla 78 (2.7x).
- Flags, template fields, radii and overlap are within the vanilla band; only the intensity is off.

Proposal: scale every LIGH base's lumens by **0.375**, which is what `--lumens-per-m2 125` would have written. A full
exterior rebuild takes hours, so it is applied as a raw record patch of the finished plugin
(`scripts/terrain/light_patch.py`), and the build default stays 333 until the owner has looked at a night.

Recipe (the original staging is never written to; several stagings share files by hard links):

1. `python scripts/terrain/light_patch.py scale --in <staging>\FO4TerrainCore.esm --out <new staging>\FO4TerrainCore.esm
   --factor 0.375 --objects <staging>\objects.json --objects-out <new staging>\objects.json`. Every LIGH's DAT2 lumens
   (u32 at offset 52) becomes `max(1, round(lumens * 0.375))`; nothing else changes. It refuses a compressed LIGH, an
   existing `--out` and `--out` = `--in`. The objects copy has the same scaling on `light_bases[*].lumens` and a
   `"lumens_scale": 0.375` key, so `make_core64c.py check` (which compares the raw LIGH to objects.json) stays consistent.
2. `python scripts/terrain/light_patch.py check --a <staging>\FO4TerrainCore.esm --b <new staging>\FO4TerrainCore.esm
   --factor 0.375`: same record count, signatures, FormIDs, flags, sizes and groups, and only LIGH DAT2 bytes 52..56 differ,
   each equal to the rule. Exit 1 otherwise.
3. Every other file of the new staging is a hard link of the old one (formids.json, plan.json, the Mars plugin, Data\),
   then `make_core64c.py check --core <core64> --sf-data <Starfield Data> --out <new staging>`.

terrain_core64l_l125 is that build of terrain_core64l: 144 LIGH, lumens min 153 -> 57, median 4,587 -> 1,720, max
12,695,923 -> 4,760,971. It is not installed by this change; the owner's check is `set gamehour to 22` at the Red Rocket
garage and the Diamond City gate (in-game-test-sheet.md, section 8).

## Not done / open

The raw patcher validates group/record containment and complete LIGH subrecord
framing before accepting writable lumens offsets. Truncated payloads, undersized
groups, duplicate DAT2 fields and malformed fields after DAT2 are refused; `check`
validates both inputs. This closes a synthetic case where a DAT2 length reached
into the next STAT record and both scale/check previously accepted the edit.
Malformed input is rejected before the plugin output is created. These structural
checks do not validate the brightness calibration or establish native acceptance.

- **Not tested in game.** The acceptance is a night screenshot at Red Rocket and in Sanctuary (the runner sets the
  time of day) next to the same view without lights. Brightness then tunes `--lumens-per-m2`.
- **XLIG fade semantics are a hypothesis.** If Starfield computes 1 + fade instead of multiplying by it, a reference
  comes out (1 + fade) / fade too bright: the written fades have p5 0.177, 1,013 are below 0.5 and 176 below 0.1, the
  minimum is 0.01, so a reference at 0.25 would be 5x too bright and the minimum 101x. If it ignores the fade, each base
  shows its median. The in-game check should put a dim reference (fade <= 0.2) next to a fade-1.0 reference of the
  same base, which tells a multiplier from 1 + delta.
- **Light REFR flags NeverFades / DoesNotLightLandscape** (345 / 315 refs) are carried from FO4, but no vanilla
  exterior light REFR sets them: whether the engine honours them is open.
- **Not carried:** light models (bulbs, klaxons, 424 refs), gobos, lens flares, emittance, and FO4 shadow omni and
  hemisphere lights (they become omni lights without shadows).
- **Unknown cost:** the frame-time cost of 6,249 lights, 5,942 of them omni without shadows, in dense cells
  (Diamond City) has not been measured.
