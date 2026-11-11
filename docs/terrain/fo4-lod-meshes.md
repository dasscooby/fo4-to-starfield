# Converting FO4 LOD meshes for the Starfield surface map

Author: Grok, 2026-10-22. Status: **scope only, no build**. Labels: **verified**, **supported**, **unresolved**.
Owner ask: how to convert Fallout 4's LOD meshes so the 3D surface map shows Commonwealth structures.
Claude owns CK generate / staging / game. This note does not run CK.

See also [surface-map.md](surface-map.md) (what the map draws) and [object-lod.md](object-lod.md) (Starfield
world object LOD trial). Do not remelt those plans.

## Short answer

The surface map shows **Starfield world object LOD** (`lodsettings/<edid>.lod` +
`meshes/lod/generated/…_lod_0..3.nif`), not FO4's own LOD files. FO4 LOD assets convert, if at all, as **source
meshes** for that CK generate. Copying FO4 `.bto` / `.btr` / `LODSettings/*.lod` into the Starfield generated
paths is **not go**.

## Four FO4 LOD kinds (**verified**, depot 377163 `Fallout4 - Meshes.ba2`, 42,416 GNRL entries)

Read with `src/fo4sf/ba2.py` (`Ba2.read`). No files copied into Git.

| Kind | Count / samples | Header | Convert? |
| --- | --- | --- | --- |
| Per-object LOD NIF `meshes/lod/**/*.nif` | **3,997** (architecture 1,537, buildings 995, landscape 497, interiors 470, neighborhoods 321, setdressing 93, unique 81) | Gamebryo NIF (`Gamebryo File Fo…`), e.g. `Financial15_Bld01LOD.nif` 11,854 B | Convert as ordinary STAT under `meshes/fo4core/lod/` (core64k already has 315). **Not** Starfield world LOD. |
| World object-LOD tiles `.bto` | **497** (Commonwealth 465, SanctuaryHillsWorld 22, DiamondCity 10), path `Meshes\Terrain\<world>\Objects\<world>.<quad>.<x>.<y>.BTO` | Gamebryo NIF (tile of many objects) | **Not go** as `meshes/lod/generated`. FORMAT-GAP vs Starfield composite tiles. |
| Terrain LOD tiles `.btr` | **6,205** (Commonwealth 3,060, SanctuaryHillsWorld 3,060, DiamondCity 85) | Gamebryo NIF | **Not go**. Overlay BTD already has LOD0–4. |
| FO4 `LODSettings/<world>.lod` | **3**: Commonwealth, DiamondCity, SanctuaryHillsWorld | Commonwealth **16 bytes** `a0ffa0ffa00100000400000020000000` | **Not go**. Starfield overlay `.lod` is commonly **20 bytes** (three i32 + 8 zeros, [object-lod.md](object-lod.md)). Different size and layout. |

29 other `*lod*.nif` sit outside `meshes/lod/` (explode-limb names and similar). Ignore for this map.

## What the surface map needs

**Verified** (surface-map.md, core64k `Data\`): overlay BTD + mask exist; **0** `lodsettings/`; **0**
`meshes/lod/generated/`; **315** converted FO4 LOD NIFs under `meshes/fo4core/lod/`. Those 315 are ordinary
meshes. The map camera and the distant world view sample Starfield generated world LOD, so the Commonwealth
looks like empty BTD.

## Conversion path (this testing stage)

### GO

1. Keep converting FO4 `meshes/lod/*.nif` as STAT (existing `meshes/fo4core/lod/` pipeline). They are cheap
   stand-ins in loaded cells; they do not fill the surface map by themselves.
2. Claude CK trial in [object-lod.md](object-lod.md): `-MockWorldSpaceLOD` (or Generate LOD) on a tiny overlay,
   then `FO4Core_Commonwealth`, writing Starfield `lodsettings` + `meshes/lod/generated`. Source STAT should be
   the **full** converted buildings first (Red Rocket, sanctuary houses), not the FO4 LOD NIFs.
3. Path classifiers in `src/fo4sf/surface_map.py` so a later writer cannot ship a `.bto` or `fo4core/lod` NIF
   as `meshes/lod/generated`.

### Supported, later, only if the CK trial wants cheaper source meshes

Point a STAT DistantLOD / extra-model slot at a converted `meshes/fo4core/lod/…` NIF so CK bakes from the
low-poly FO4 LOD instead of the full mesh. **Unresolved** until Claude's CK run shows whether those flags
exist on overlay STAT and whether the generator reads them.

### NOT go

- Rename or copy FO4 `.bto` into `meshes/lod/generated/…_lod_0.nif`.
- Copy FO4 `LODSettings/Commonwealth.LOD` (16 bytes) over Starfield `lodsettings/fo4core_commonwealth.lod`.
- Port `.btr` as a substitute for BTD LOD.
- Hand-authored Starfield `.lod` stubs without a CK fixture ([object-lod.md](object-lod.md) writer gate).
- Raising `uExterior Cell Buffer` as the product fix.

## Acceptance (offline)

This PR: classifiers + this note + tests. In-game surface-map buildings wait on Claude's CK generate and
screenshot. Offline `check` cannot see the map camera.
