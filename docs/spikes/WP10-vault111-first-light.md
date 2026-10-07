# WP-10 first light: Vault 111 in Starfield (2026-10-07)

**Result: the Fallout 4 `Vault111Cryo` interior loads in Starfield 1.16.244 as a new cell you can stand in.**
Screenshots: [entrance](../media/vault111-entrance-in-starfield.png), [stairs to the machinery](../media/vault111-stairs-in-starfield.png).

## Pipeline

1. `dotnet/Fo4Export`: reads `Fallout4.esm` with Mutagen and exports a cell's placed references (base type, base EditorID,
   model, position, rotation, scale) to JSON. `Vault111Cryo`: 3,087 references (1,034 statics, 849 lights, 540 texture-set
   decals, 371 movable statics, 63 furniture, 39 doors, ...), 268 distinct models.
2. `scripts/convert_batch.py --cell-json`: converts every model of the chosen base types straight from the FO4 archives
   (native BA2 reader). 234 converted, 12 failed (animated/skinned furniture, lockers, desks), editor markers skipped.
   Box collision for props only; architecture (`meshes/Interiors`, `meshes/Architecture`) gets none for now, because one AABB
   would fill a whole corridor.
3. `dotnet/PluginSpike` (plugin writer): one `STAT` per model plus an interior `CELL` `FO4Port_Vault111Cryo` with 1,365 placed
   references at the FO4 position **/ 70** (Starfield placements are in metres: vanilla nearest-neighbour spacing 0.91 vs 72 units
   in FO4), same rotation (radians) and scale. Lighting: vanilla `ShipInteriorLT` template and a vanilla neutral 8 m omni light
   (`LGT_ShipInterior_Omni_NS_Neutral_2k`) at each FO4 light position, merged within 3 m (132 lights). This makes `Starfield.esm`
   a master; Mutagen then needs `WithKnownMasters(new KeyedMasterStyle(Starfield.esm, MasterStyle.Full))` when writing.
4. `scripts/deploy_starfield.py`, then in game: `coc FO4Port_Vault111Cryo`.

## What it looks like

- The layout is right: entrance hoses, staircase up to the vault-door machinery, cryo-pod hall, consoles, crates; everything
  where Fallout 4 put it, at the right scale and orientation, textured.
- **Over-exposed**: too much light (132 overlapping 8 m omnis + a bright template) and a white void where there is no geometry.
- Colour looks desaturated. The vault is mostly grey concrete and steel in FO4 too; to be checked once exposure is fixed.
- Player can stand on the floor at the arrival point; elsewhere floors have no collision yet.

## Next

1. Lighting: fewer/dimmer lights matched to FO4 light radius/colour, a darker template, fill the void (skybox/fog).
2. Real collision for architecture (mesh or convex-decomposition shapes), then navmesh.
3. Doors, furniture, the 12 failed models (animated/skinned), decals (texture sets), movable statics.
4. Load doors / a way in other than `coc`.

## Architecture collision: thin boxes behind flat surfaces (2026-10-08)

Single AABBs cannot work for rooms, so `sfcollision.surface_boxes` groups each mesh's axis-aligned triangles by (axis, facing,
plane offset), splits them into connected clusters and gives each cluster a box 15 cm deep behind the surface. Each box is its
own body on a child `NiNode` (`sfnif.build_static_nif(child_collision_blobs=...)`). Vault floor tile `VltFloor01` -> one
3.66 x 3.66 x 0.15 m slab; heavy machinery hits the 48-box cap. In game the player walks across the vault floor without falling
through ([screenshot](../media/vault111-walking-on-floor.png)); stairs, sloped and curved surfaces are not covered yet
(no boxes for non-axis-aligned triangles). Lights reduced to 60 dimmer omnis + `DefaultLightingTemplate`; the scene is still
over-exposed, but FO4's own Vault 111 concrete textures are genuinely light (mean ~200-220/255), so exposure, not texture
conversion, is the cause.
