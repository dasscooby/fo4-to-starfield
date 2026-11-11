# FO4 STAT distant-LOD meshes around Sanctuary, Red Rocket and Concord

Author: Grok, 2026-10-22. Status: **offline scoping**. Nothing written into game Data, staging, or the overlay plugin. No Creation Kit generate. Labels: **verified** = read from files here, **supported** = hypothesis with evidence, **unresolved** = open. Claude (PC) #32 `6348595314` / facts `6348638328`.

This is **re-keyed per-object LOD** for Starfield (`meshes/lod/generated/<converted full mesh path>_lod_<0-3>.nif`), not shipping `meshes/fo4core/lod` as world LOD and not a FO4 `.bto` port. The Map thread owns [object-lod.md](object-lod.md) and [surface-map.md](surface-map.md); this note does not edit them.

Scanner: `scripts/lod/list_fo4_lod_meshes.py` (JSON). Default `--radius 1` FO4 cell around the three Commonwealth markers in [map-markers.md](map-markers.md).

## Short answers

1. **STAT MNAM names distant-LOD models under `LOD\...`.** In the three landmark cells every named file is present in `Fallout4 - Meshes.ba2` as `Meshes\LOD\...`. **verified**, offline.
2. **Starfield per-object target is keyed by the path `convert_static` gives the full mesh**, `meshes/fo4core/<modl stem>_lod_<0-3>.nif` under `meshes/lod/generated/`. `convert_static` can write that nif + hashed `.mesh` if the caller passes the mapped `out_name`; the NIF **references** vanilla placeholder `Materials\Common\Metal\MetalIronCast01.mat` and does not write a `.mat` (generated `.mat` is the pipeline path). pipeline/convert_batch as they stand key from the source nif and would land under `meshes/fo4core/lod/`. **verified** mapping, **supported** that CK generate would use the same key.
3. **`lodsettings/fo4core_commonwealth.lod` is 20 bytes** `-32, -32, 64` then eight zeros: `e0ffffff e0ffffff 40000000 00000000 00000000`. **supported** (overlay cell range **verified**; the three-i32 meaning is the Map thread's supported hypothesis).
4. **Unresolved, Claude in-game:** `distantlod/lodruntimedb.bgsdb` entry; per-world composite LOD; whether the game draws per-object LOD for a world with no CK output; which of the two layouts (per-mesh generated vs per-block `Meshes\Terrain\<world>\Objects\`) a custom world is read from.
5. **Not the surface-map NOT-go.** Re-keying into `meshes/lod/generated/` is a different path and consumer from shipping converted FO4 `*_lod.nif` under `meshes/fo4core/lod`.

## Method (offline)

- Plugin: `Fallout4.esm` 330,745,373 B (depot `app_377160/depot_377163/Data`). World `Commonwealth`. Reader: `fo4land.Plugin`.
- Archives: `Fallout4 - Meshes.ba2` (42,416 names, 3,997 `meshes/lod/*.nif`) and `Fallout4 - MeshesExtra.ba2` (125,837 names, 0 LOD nifs). Presence is a name-table hit, case- and slash-insensitive (`ba2.Ba2.find`).
- Landmarks (FO4 units, same FormIDs as map-markers.md / `make_cw_overlays.py`):

| tag | REFR | FO4 XY | FO4 cell |
|---|---|---|---|
| redrocket | `000211c0` | −69232.0, 80304.0 | (−17, 19) `RedRocketExt` |
| sanctuary | `00072a48` | −80768.19, 88174.80 | (−20, 21) `SanctuaryExt` |
| concord | `00082138` | −60286.01, 72977.79 | (−15, 17) `ConcordExt` |

- `--radius 0` = those three cells. `--radius 1` (script default) = 26 cells. Persistent-cell refs are not in this table (the three landmarks' map-marker REFRs are MapMarker STAT `00000010`, no MNAM).

## 1. Placed STATs whose base names distant-LOD models

**verified.** FO4 STAT `MNAM` is empty (15,931 records) or exactly **1040 bytes** (3,436 records) = four 260-byte null-padded slots (CK leftover bytes after the first NUL are ignored). 3,400 of those have at least one nonempty path. Paths are `LOD\...` without a `Meshes\` prefix; the archive stores `Meshes\LOD\...`.

Radius 1 around the three landmarks: **436 REFR / 129 unique STAT bases** in 26 loaded cells. **746** nonempty MNAM slots; **746 present, 0 missing**. Radius 0 (the three named cells): **63 REFR / 45 cell×EDID pairs**.

Worked example, Red Rocket building `000211c0` (**verified**):

| field | value |
|---|---|
| cell | (−17, 19) `RedRocketExt` |
| base | `01b5f10` `RedRExt_Workshop01` |
| MODL | `Interiors\RedRocket\RedRExt_Workshop01.nif` |
| MNAM 0 and 1 | `LOD\Interiors\RedRocket\RedRExtAll01_LOD.nif` |
| archive | `Meshes\LOD\Interiors\RedRocket\RedRExtAll01_LOD.nif` **present** |

Unique bases in the three landmark cells (radius 0). `n` = placed REFRs of that base in that cell. Every FO4 LOD path in this table is **present**.

| cell | EDID | n | FO4 full mesh | FO4 MNAM (nonempty) |
|---|---|---|---|---|
| SanctuaryExt (−20, 21) | Res01Modern03RR | 2 | Architecture/Buildings/Residential/Res01Modern03RR.nif | LOD/Buildings/Res01Modern03RR_LOD.nif |
| SanctuaryExt | Res01Modern03RRb | 1 | Architecture/Buildings/Residential/Res01Modern03RR.nif | LOD/Buildings/Res01Modern03RRB_LOD.nif |
| SanctuaryExt | Res01ModernCarport01RR | 1 | Architecture/Buildings/Residential/Res01ModernCarport01RR.nif | LOD/Buildings/Res01ModernCarport01RR_LOD.nif |
| SanctuaryExt | Res01ModernCarportgarage01RRb | 1 | Architecture/Buildings/Residential/Res01ModernCarportgarage01RR.nif | LOD/Buildings/Res01ModernCarportGarage01RRB_LOD.nif |
| SanctuaryExt | Res01ModernDormer02RR | 1 | Architecture/Buildings/Residential/Res01ModernDormer02RR.nif | LOD/Buildings/Res01ModernDormer02RR_LOD.nif |
| SanctuaryExt | ResidentialStreetLamp01 | 2 | SetDressing/StreetLamps/ResidentialStreetLamp01.nif | LOD/SetDressing/StreetLamps/ResidentialStreetLamp01_LOD.nif |
| SanctuaryExt | TreeMapleForest1 | 2 | Landscape/Trees/TreeMapleForest1.nif | LOD/Landscape/Trees/Maple/TreeMapleForest01_LOD_1.nif, _LOD_2.nif |
| SanctuaryExt | TreeMapleForest3 | 2 | Landscape/Trees/TreeMapleForest3.nif | LOD/Landscape/Trees/Maple/TreeMapleForest03_LOD_1.nif |
| RedRocketExt (−17, 19) | RedRExt_Workshop01 | 1 | Interiors/RedRocket/RedRExt_Workshop01.nif | LOD/Interiors/RedRocket/RedRExtAll01_LOD.nif |
| RedRocketExt | BillboardSm01 | 2 | SetDressing/Signage/BillboardSm01.nif | LOD/SetDressing/Signage/BillboardSm01_LOD.nif |
| RedRocketExt | RockCliff01 | 1 | Landscape/Rocks/RockCliff01.nif | LOD/Landscape/Rocks/RockCliff01_LOD_0.nif, _LOD_1.nif |
| RedRocketExt | TreeMapleForest2 | 1 | Landscape/Trees/TreeMapleForest2.nif | LOD/Landscape/Trees/Maple/TreeMapleForest02_LOD_1.nif, _LOD_2.nif |
| RedRocketExt | TreeMapleForest3 | 3 | Landscape/Trees/TreeMapleForest3.nif | LOD/Landscape/Trees/Maple/TreeMapleForest03_LOD_1.nif |
| RedRocketExt | TreeMapleblasted02 | 1 | Landscape/Trees/TreeMapleblasted02.nif | LOD/Landscape/Trees/Maple/TreeMapleblasted02_LOD_1.nif, _LOD_2.nif |
| RedRocketExt | TreeMapleblasted04 | 3 | Landscape/Trees/TreeMapleblasted04.nif | LOD/Landscape/Trees/Maple/TreeMapleBlasted04_LOD_1.nif |
| RedRocketExt | TreeMapleblasted05 | 2 | Landscape/Trees/TreeMapleblasted05.nif | LOD/Landscape/Trees/Maple/TreeMapleBlasted05_LOD_1.nif, _LOD_2.nif |
| ConcordExt (−15, 17) | Bld01FreeBrickARes01 | 1 | Architecture/Buildings/SmallTown/Bld01FreeBrickARes01.nif | LOD/Buildings/SmallTown/Bld01FreeBrickARes01_LOD.nif |
| ConcordExt | Bld01FreeBrickBRes01 | 1 | Architecture/Buildings/SmallTown/Bld01FreeBrickARes01.nif | LOD/Buildings/SmallTown/Bld01FreeBrickARes01_LOD.nif |
| ConcordExt | Bld01FrontSidingACom01 | 1 | Architecture/Buildings/SmallTown/Bld01FrontSidingACom01.nif | LOD/Buildings/SmallTown/Bld01FrontSidingACom01_LOD.nif |
| ConcordExt | Bld02AddBalcony01 | 1 | Architecture/Buildings/SmallTown/Bld02AddBalcony01.nif | LOD/Buildings/SmallTown/Bld02AddBalcony01_LOD.nif |
| ConcordExt | Bld02AddBayWin01 | 1 | Architecture/Buildings/SmallTown/Bld02AddBayWin01.nif | LOD/Buildings/SmallTown/Bld02AddBayWin01_LOD.nif |
| ConcordExt | Bld02AddBayWin02 | 2 | Architecture/Buildings/SmallTown/Bld02AddBayWin02.nif | LOD/Buildings/SmallTown/Bld02AddBayWin02_LOD.nif |
| ConcordExt | Bld02CornerBrickACom01 | 1 | Architecture/Buildings/SmallTown/Bld02CornerBrickACom01.nif | LOD/Buildings/SmallTown/Bld02CornerBrickACom01_LOD.nif |
| ConcordExt | Bld02FrontSidingACom01 | 1 | Architecture/Buildings/SmallTown/Bld02FrontSidingACom01.nif | LOD/Buildings/SmallTown/Bld02FrontSidingACom01_LOD.nif |
| ConcordExt | Bld02FrontSidingACom02R | 1 | Architecture/Buildings/SmallTown/Bld02FrontSidingACom02R.nif | LOD/Buildings/SmallTown/Bld02FrontSidingACom02R_LOD.nif |
| ConcordExt | Bld02FrontSidingACom03 | 2 | Architecture/Buildings/SmallTown/Bld02FrontSidingACom03.nif | LOD/Buildings/SmallTown/Bld02FrontSidingACom03_LOD.nif |
| ConcordExt | Bld02FrontSidingACom04 | 2 | Architecture/Buildings/SmallTown/Bld02FrontSidingACom04.nif | LOD/Buildings/SmallTown/Bld02FrontSidingACom04_LOD.nif |
| ConcordExt | Bld03AddPorchSidingA01 | 1 | Architecture/Buildings/SmallTown/Bld03AddPorchSidingA01.nif | LOD/Buildings/SmallTown/Bld03AddPorchSidingA01_LOD.nif |
| ConcordExt | Bld03FrontBrickBCom01 | 1 | Architecture/Buildings/SmallTown/Bld03FrontBrickACom01.nif | LOD/Buildings/SmallTown/Bld03FrontBrickBCom01_LOD.nif |
| ConcordExt | Bld03FrontSidingACom01 | 1 | Architecture/Buildings/SmallTown/Bld03FrontSidingACom01.nif | LOD/Buildings/SmallTown/Bld03FrontSidingACom01_LOD.nif |
| ConcordExt | Bld03FrontSidingACom01R | 1 | Architecture/Buildings/SmallTown/Bld03FrontSidingACom01R.nif | LOD/Buildings/SmallTown/Bld03FrontSidingACom01R_LOD.nif |
| ConcordExt | Bld03FrontSidingACom02 | 1 | Architecture/Buildings/SmallTown/Bld03FrontSidingACom02.nif | LOD/Buildings/SmallTown/Bld03FrontSidingACom02_LOD.nif |
| ConcordExt | Bld03FrontSidingBCom03 | 1 | Architecture/Buildings/SmallTown/Bld03FrontSidingACom03.nif | LOD/Buildings/SmallTown/Bld03FrontSidingACom03_LOD.nif |
| ConcordExt | GreebLarge08 | 1 | SetDressing/Greebs/GreebLarge08.nif | LOD/SetDressing/Greebs/GreebLarge08_LOD_0.nif |
| ConcordExt | IndSmPipe1WayHalf01 | 2 | Interiors/Industrial/SmPipe/IndSmPipe1WayHalf01.nif | LOD/Interiors/Industrial/SmPipe/IndSmPipe1WayHalf01_LOD.nif |
| ConcordExt | PW_02c_SideCover_Complex | 1 | SetDressing/Greebs/PW_02c_SideCover_Complex.nif | LOD/SetDressing/Greebs/PW_02c_SideCover_Complex_LOD.nif |
| ConcordExt | PW_02c_SideCover_Complex_flip | 1 | SetDressing/Greebs/PW_02c_SideCover_Complex_flip.nif | LOD/SetDressing/Greebs/PW_02c_SideCover_Complex_flip_LOD.nif |
| ConcordExt | PW_02d_SideCover_Simple | 1 | SetDressing/Greebs/PW_02d_SideCover_Simple.nif | LOD/SetDressing/Greebs/PW_02d_SideCover_Simple_LOD.nif |
| ConcordExt | PW_03a_Core_Exposed | 2 | SetDressing/Greebs/PW_03a_Core_Exposed.nif | LOD/SetDressing/Greebs/PW_03a_Core_Exposed_LOD.nif |
| ConcordExt | PW_03b_Core_Covered | 2 | SetDressing/Greebs/PW_03b_Core_Covered.nif | LOD/SetDressing/Greebs/PW_03b_Core_Covered_LOD.nif |
| ConcordExt | PW_03c_Strut | 2 | SetDressing/Greebs/PW_03c_Strut.nif | LOD/SetDressing/Greebs/PW_03c_Strut_LOD.nif |
| ConcordExt | PW_03c_Strut_flip | 1 | SetDressing/Greebs/PW_03c_Strut_flip.nif | LOD/SetDressing/Greebs/PW_03c_Strut_flip_LOD.nif |
| ConcordExt | PW_04_Turbine | 1 | SetDressing/Greebs/PW_04_Turbine.nif | LOD/SetDressing/Greebs/PW_04_Turbine_LOD.nif |
| ConcordExt | PW_05_Generator | 1 | SetDressing/Greebs/PW_05_Generator.nif | LOD/SetDressing/Greebs/PW_05_Generator_LOD.nif |
| ConcordExt | PW_07_Turbine_Shell | 2 | SetDressing/Greebs/PW_07_Turbine_Shell.nif | LOD/SetDressing/Greebs/PW_07_Turbine_Shell_LOD.nif |

Many MNAM records repeat the same path in slots 0 and 1. Trees often name `_LOD_1` / `_LOD_2` and leave slot 0 empty. The JSON lists every REFR.

## 2. Starfield path mapping

`convert_batch --prefix fo4core` (core64c) sets `out_name = fo4core/<modl without Meshes/ prefix, lower, no extension>`. `convert_static` writes `meshes/{out_name}.nif` plus `geometries/<sha1[:20]>/<sha1[20:40]>.mesh` and **references** vanilla `Materials\Common\Metal\MetalIronCast01.mat` in the NIF unless the caller passes `material_paths`; it does not write a `.mat`. Generated `.mat` output is `pipeline.convert_nif`. **verified** (`pipeline.convert_nif`, `convert_static.convert_static`).

Per-object form from object-lod.md (Map thread; not edited here): `meshes/lod/generated/<mesh path>_lod_<0-3>.nif`, keyed by the full mesh. Applying that to the converted full mesh:

| | Red Rocket workshop |
|---|---|
| FO4 MODL | `Interiors\RedRocket\RedRExt_Workshop01.nif` |
| converted full mesh | `meshes/fo4core/interiors/redrocket/redrext_workshop01.nif` |
| per-object LOD 0 | `meshes/lod/generated/meshes/fo4core/interiors/redrocket/redrext_workshop01_lod_0.nif` |
| `.mesh` | content-addressed `geometries/<20 hex>/<20 hex>.mesh` |
| material referenced by `convert_static` (not written) | vanilla `Materials\Common\Metal\MetalIronCast01.mat` |
| generated `.mat` if converted as a normal STAT (pipeline) | `materials/fo4core/interiors/redrocket/redrext_workshop01.mat` (**supported**; vanilla per-object LOD keeps the source mesh's materials) |

`convert_static` **as it stands**:

- **Can** write the per-object nif path: pass `out_name=lod/generated/meshes/fo4core/interiors/redrocket/redrext_workshop01_lod_0` and the FO4 LOD nif bytes. Default `collision_template=None` writes no collision (LOD models need none; collision floor #455/#457 is out of scope).
- **Does not** choose that `out_name` itself. `pipeline` / `convert_batch` key from the source nif, so a FO4 `Meshes\LOD\...` file becomes `meshes/fo4core/lod/...`, which is the surface-map NOT-go layout.
- **Cannot** write the per-block composite `Meshes\Terrain\<world>\Objects\<world>.{1,2,4,8}.0.0.nif` (CK `-MockWorldSpaceLOD` output; many refs, transforms on `BSWeakReferenceNode`). Path mapping for that form, for our overlay:

```
meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.1.0.0.nif
meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.2.0.0.nif
meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.4.0.0.nif
meshes/terrain/FO4Core_Commonwealth/objects/FO4Core_Commonwealth.8.0.0.nif
```

Casing follows the world EDID, as `LC172World` did in the mock output. **supported** path, **unresolved** whether a custom world is read from this form, from per-mesh `generated/`, or from `generated/composite/<world>/`.

Including `meshes/` in the generated key matches "keyed by the converted full mesh path". If CK strips the `meshes/` prefix, the target would be `meshes/lod/generated/fo4core/interiors/redrocket/redrext_workshop01_lod_0.nif` instead. **supported**; Claude's CK mock on our core settles it.

## 3. `lodsettings/fo4core_commonwealth.lod`

Overlay `FO4Core_Commonwealth` is 64 × 64 Starfield cells, CW cells **−32..31** on both axes, local frame = FO4 position / 70 (**verified**, commonwealth-scale.md / core64c.md). The 20-byte form is min cell x, min cell y, size in cells, eight zero bytes (**supported**, object-lod.md; `lc172world` is −2, −2, 8).

| field | value |
|---|---|
| path | `lodsettings/fo4core_commonwealth.lod` (`surface_map.lodsettings_rel`) |
| min cell x | −32 |
| min cell y | −32 |
| size in cells | 64 |
| bytes | `e0 ff ff ff e0 ff ff ff 40 00 00 00 00 00 00 00 00 00 00 00` |

## 4. Unresolved (Claude in-game)

- **`distantlod/lodruntimedb.bgsdb`:** 559,956 B, counts 8 and 4,387, records with hashes and the text `nif`. Whether a custom world must be merged in is **unresolved**.
- **Per-world composite LOD** under `meshes/lod/generated/composite/<world>/`. Vanilla has 6,913 of these for 242 worlds. Whether the overlay needs any is **unresolved**.
- **Whether the game draws per-object LOD for a world with no CK output.** Pinned core64k had zero `lodsettings/` and zero `meshes/lod/generated/`; distant view showed BTD only. That does not separate "no `.lod`" from "no generated meshes" from "no bgsdb row".
- **Which layout a custom world is read from:** per-mesh `generated/<mesh path>_lod_N`, per-block `Meshes\Terrain\<world>\Objects\`, or composite. Install/Map mock on our core.

## 5. Surface-map NOT-go

surface-map.md NOT-go (quoted, not edited):

- A custom 3D map renderer, FO4 `.bto` port, or raising `uExterior Cell Buffer`.
- Unparenting from `SSol_PMars_Surface`.
- Shipping the 315 `meshes/fo4core/lod` NIFs as if they were `meshes/lod/generated` world LOD.

This packet is the third item's alternative: same FO4 MNAM nifs (or CK-generated stand-ins from the converted full mesh), **re-keyed** to `meshes/lod/generated/<converted full mesh path>_lod_N`. That is the contract the 3D surface map and the distant view read. It is not a `.bto` port and not `meshes/fo4core/lod` as world LOD. If a later CK mock shows the engine only consumes the per-block `Terrain\<world>\Objects` form and ignores per-mesh generated files, this mapping still applies to that form (section 2) and we stop treating per-mesh generated as the product path.

## What this does not do

No CK, no writes to game Data or staging, no `#326` / `#334` remelt, no collision-floor work, no edit of object-lod.md or surface-map.md.
