# Next phase: lighting across the whole game (breadth, not polish)

Lighting thread, Claude-cloud, 19 Oct (overnight). Lighting polish is a later phase (user, 05:55Z Oct 19).
This file covers only what full-game breadth needs from lighting: every FO4 and DLC cell and worldspace gets light that
is plausible and automatic, built on the user's PC from their own Fallout 4 files, shipping no assets.

Labels follow docs/ai/research-log.md: **verified** (file/command evidence), **supported hypothesis**, **unresolved**.
Claims about FO4 or Starfield record layouts that come from general modding knowledge (xEdit definitions, UESP) and
haven't been read in this project are marked **to check**.

## 1. What the port does today (main 4492d13)

| Area | Now | Evidence |
|---|---|---|
| Interior ambient | Every converted interior gets the same Starfield lighting template, KreetBase01 `06BCF8`, unless lighting.json overrides it. FO4's own cell lighting (XCLL), its lighting template (LTMP) and its image space (XCIM) are ignored. | **verified**: dotnet/PluginSpike/Program.cs:164-200 |
| Interior exposure | Image space `122393` for every cell, taken from vanilla DR017UndergroundInterior. | **verified**: same file |
| Interior reflections / sky light | Hall cubemap `Cell_HiTechHallCube.dds` for every cell (#355, merged). Before that it was black, which made everything black away from lamps. | **verified in game (library only)**, owner 18 Oct: "Lighting looks fine" |
| Placed lights | FO4 LIGH references are converted with radius, fade, FOV and near clip (src/fo4sf/fo4light.py). | **verified** offline; in game they "look really good" (owner) |
| Exterior sky, sun, night, weather | The overlay worldspace copies LC172World (Mars) and its cells set no lighting, so the Commonwealth has Mars's sky, sun, day length and weather. Night is Mars night: very dark, as the owner reported. | **verified** (research log 2026-10-18); the night look is the owner's report |
| FO4 lighting data available | Fo4Export now writes each interior's XCLL, LTMP FormKey and the template's values into the cell JSON (#338). | **verified**: dotnet/Fo4Export/Program.cs:103-107 |
| Starfield-side survey tools | SfInspect `envmaps`, `templates` and `imgs` list what vanilla interiors use. | **verified**: dotnet/SfInspect/Program.cs |
| Day/night testing | The runner can force time of day and weather and judge sky light from screenshots (scripts/game/sky_light.py, qstep.ps1). | **verified** |
| Materials | Alpha-tested FO4 decals now convert as overlays (#355). Without that they drew as black floor and wall patches. | **verified offline**, not yet seen in game |

So breadth today means one fixed look for every interior and Mars for every exterior. That works for walking through
the game. It's wrong for anything where light carries the place: vaults vs. caves vs. sunny ruins, the Glowing Sea, Far
Harbor fog, radstorms and night.

## 2. What FO4 (with all DLC) gives us to convert

**To check** (layouts from xEdit's FO4 definitions; Fo4Export already dumps the cell side):
- **CELL XCLL** (per interior): ambient colour, directional colour and rotation, fog near/far colours and distances,
  fog power and max, a directional ambient cube (6 colours plus specular), light fade begin/end, and inherit flags
  that say which fields come from the template.
- **CELL LTMP**: lighting template (LGTM) with the same field set. FO4 interiors mostly use a small number of shared
  templates, so converting templates instead of every cell is the cheap path. **To measure** how many there are.
- **CELL XCIM**: image space (IMGS): eye adaptation, bloom, saturation, contrast, tint, depth of field.
- **WRLD / CLMT / WTHR** (exteriors): the Commonwealth, FarHarbor, NukaWorld and the smaller worldspaces (Diamond City,
  Goodneighbor, Sanctuary-area variants and others) each name a climate. A climate is a weighted weather list plus
  sunrise/sunset times. A weather (WTHR) has colours for each time of day (sky, fog, ambient, sunlight, stars), fog
  distances, an image space for each time of day, cloud layers, precipitation, lightning, wind and god rays. Radstorms
  and the Glowing Sea are weathers, as are Far Harbor's fog weathers.
- **Interior "show sky" cells** take the region's weather (some FO4 interiors open to the sky). **To count.**

## 3. What Starfield offers on the other side

**To check** (from the Starfield records this project already reads, plus Starfield modding knowledge):
- Interior **CELL** has LTMP, XCIM and XEMP (env map). The writer already sets all three. Whether Starfield's CELL also
  has a usable per-cell XCLL override, the way FO4 does, is **unresolved**. Check the Mutagen Starfield `Cell.Lighting`
  type and a vanilla cell that sets it, with SfInspect. If it exists, FO4's XCLL can map almost field for field.
- **LGTM** exists in Starfield, and a plugin can add new ones. So "one Starfield LGTM per FO4 LGTM" can be generated on
  the user's PC from their FO4 data, with no assets shipped. The main unknown is the colour and intensity scale: FO4 is
  LDR-ish colour plus fade, Starfield is physically based, with lux-like intensities and exposure in the image space.
- **IMGS** exists, but Starfield's exposure is physically based. Converting FO4 image spaces field for field will likely
  look wrong. Picking from a small set of vanilla Starfield image spaces by cell family is the safer breadth option.
- **Exteriors**: Starfield's sky is a physically based atmosphere that comes from the planet (atmosphere, star,
  day length) and the biome's weather list. The FO4 cloud-layer and sky-colour model doesn't carry over directly.
  Breadth here means choosing a host planet/worldspace whose atmosphere and day length are close to Earth's, then
  adding Commonwealth weathers on top as Starfield WTHR records (fog, precipitation, cloud cover, lightning for
  radstorms). Mars (thin red atmosphere, ~24.6 h day) is the current host. **Unresolved**: which vanilla planet has
  Earth-like air and a ~24 h day. That's a cloud-side SfInspect survey of planet records (PNDT and biomes) once the
  PC can run it.

## 4. Breadth plan (suggested order; each step is automatic for every cell)

1. **Inventory (read-only, small, PC):** with the existing Fo4Export output, count distinct FO4 LTMP templates,
   XCIM image spaces, XCLL-overriding cells, "show sky" interiors, and the climates and weathers of every worldspace,
   base game and DLC. Output is one JSON summary of a few KB. This decides whether step 2 converts tens of
   templates or thousands of cells.
2. **Interior families:** map each FO4 lighting template to the nearest of a handful of vanilla Starfield
   template + image space + cubemap sets: vault, cave/metro, lit building, dark ruin, outdoor-like/show-sky, and
   industrial. Rules go in a small table in code (no assets). It replaces today's single default. lighting.json stays
   as the per-cell override.
3. **Interior fidelity (later, optional):** where FO4 XCLL differs strongly from its template, generate a Starfield LGTM
   from the FO4 values with one calibrated scale factor. Calibrate it on 3 to 4 cells with screenshots side by side.
4. **Exterior host:** pick an Earth-like host planet/worldspace for the Commonwealth overlay, so day sky and night
   brightness are Earth-like without converting weathers. This is the biggest single fix for "really dark at night"
   outdoors. **Unresolved** until the planet survey.
5. **Exterior weathers:** generate Starfield WTHR records for FO4's weather families (clear, cloudy, fog, rain,
   radstorm, Glowing Sea, Far Harbor fog, Nuka-World), each with a weight from FO4's climate. Radstorm lightning and
   the radiation hazard tie into gameplay (rads), so this overlaps the gameplay/ecosystem work.
6. **DLC worldspaces:** FarHarbor and NukaWorld get the same treatment with their own climates. The Vault 88 and
   Contraptions/Wasteland Workshop interiors fall under steps 2 and 3.
7. **Acceptance:** runner queues with forced time of day (noon, dusk, midnight) and forced weather per family, judged
   from screenshots by the existing sky_light checks. A cheap numeric gate is mean scene luminance inside a band per
   family. Look checks by the user stay rare.

## 5. Risks and unknowns

- **Unresolved:** whether Starfield honours a per-cell lighting override (step 3 depends on it).
- **Unresolved:** the colour/intensity scale between FO4 and Starfield lighting. Without calibration, converted values
  will be uniformly too dark or too bright.
- **Unresolved:** host planet choice. Changing the host worldspace may shift what the core build copies (its WRLD
  record and persistent cell). Core form ids and the mission plugin depend on the core, so this should be decided
  before the core launcher freezes its layout.
- **Supported hypothesis:** most FO4 interiors share a few dozen templates, so the family table covers the bulk.
  Step 1 confirms or refutes it.
- **Performance:** FO4 cells with many shadow-casting lights may exceed Starfield's shadow budget. fo4light.py already
  converts every light; a per-cell cap on shadowed lights may be needed. **To measure** with the cell inventory.
- **Gameplay overlap:** radstorms (rads, Geiger sounds) and the Glowing Sea hazard are ecosystem features, not only
  lighting. They should be owned by the gameplay work, with lighting supplying the weather records.

## 6. What it costs the PC

Only step 1 needs the PC now: a read-only Fo4Export pass over the depot that writes one small summary file (no
conversion, no new staging folders, negligible disk). Everything else is code that runs inside the normal
conversion. Generated LGTM and WTHR records add a few KB to the plugins, and no textures. The cubemaps and image spaces are
vanilla Starfield records referenced by form id.
