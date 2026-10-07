# More interiors: Vault 81 and the Red Rocket cave (2026-10-08)

The pipeline is not specific to Vault 111. `dotnet/Fo4Export` exports any interior, `scripts/convert_batch.py --cell-json`
converts the union of models, and the plugin writer takes several cell files. One plugin now holds `FO4Port_Vault111Cryo`,
`FO4Port_Vault81` (3,289 refs) and `FO4Port_RedRocket01` (the mole-rat cave under Red Rocket, 590 refs): **932 models,
508/512 materials, about 2.5 minutes**. Screenshots: [Vault 81](../media/vault81-booth.jpg), [Red Rocket cave](../media/redrocket-cave.jpg).

## Fixes found by playing the cave

1. **"Snow" on rock = mirror-smooth material.** FO4 cave rock gloss maps are 255 everywhere; the `.bgsm` scales them by a
   *smoothness* scalar (0.5 here) and a *specular multiplier* (0.14-0.4). Both are read from the lighting block after the
   nine texture strings (offsets +28 / +32, verified on PatioFurniture: mult 0.8, smoothness 1.0). Roughness is now
   `255 - G * smoothness * sqrt(spec_mult)`.
2. **Black slabs = missing alpha cutouts.** Roots and foliage use alpha test. Starfield does it with an opacity texture in
   `MRTextureFile` slot 2 plus `BSMaterial::AlphaSettingsComponent {AlphaTestThreshold, HasOpacity}` on the root object (as in
   vanilla `GrassTropicalPlant01.mat`). The diffuse alpha becomes a BC4 opacity map; threshold = BGSM alpha ref (byte 41) / 255.
   73 opacity maps in these three cells.
3. **Alpha-blended overlay/decal shells** (`...Alpha.BGSM`, BGSM byte 32 set) are skipped until blending is supported.
4. **Hanging roots blocked the player** (user play-test): vegetation (`landscape\trees|plants|grass`, roots, cobwebs, vines)
   no longer gets collision. Walk test: 4 s through the roots, uphill, no fall-through.
