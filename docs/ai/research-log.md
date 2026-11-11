# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-22 Grok: FO4 LOD mesh kinds vs Starfield surface-map world LOD

- Question: how to convert Fallout 4 LOD meshes so the 3D surface map shows Commonwealth structures.
- Method: `Ba2.read` on depot 377163 `Fallout4 - Meshes.ba2` (42,416 GNRL). Path counts + 16-byte headers.
  Offline. No CK, no assets in Git.
- **Verified** counts: 3,997 `meshes/lod/**/*.nif` (Gamebryo); 497 `.bto` (Commonwealth 465 / Sanctuary 22 /
  Diamond City 10, Gamebryo tiles); 6,205 `.btr`; 3 FO4 `LODSettings/*.lod`. Commonwealth `.lod` is **16 bytes**
  `a0ffa0ffa00100000400000020000000`. Starfield overlay `.lod` is commonly 20 bytes ([object-lod.md](../terrain/object-lod.md)).
- **Supported**: convert per-object `meshes/lod/*.nif` as STAT under `meshes/fo4core/lod/` only. Surface map
  still needs CK `lodsettings` + `meshes/lod/generated`. Using those STAT as DistantLOD sources is **unresolved**
  until the CK trial.
- **Not go**: copy `.bto` / `.btr` / FO4 16-byte `.lod` into Starfield generated paths.
- Plan: [docs/terrain/fo4-lod-meshes.md](../terrain/fo4-lod-meshes.md).

## 2026-10-18 Grok: #359 collision-vs-mesh AABB oracle (fo4-native bounds decode)

- Question: can `sfcollision.py` and `fo4collision.py` decode the Havok blobs the converter writes for `fo4-native` collision far enough to compare a converted model's collision AABB with its drawn-mesh AABB.
- Method: synthetic 6,168-byte identity `hknpBoxShape` (`tests/test_collision.py` `fake_template` + `sfcollision.box_blob`) and synthetic Starfield compressed-mesh tagfile (`tests/test_sfbodies.py` `mesh_blob`). No game assets.
- Box templates, **verified**: `sfcollision.read_box` reads centre/half from the 8 corners at blob offset 592 (`<3f` × 8). `check_template` requires `TAG0`, length 6168, `hknpBoxShape`, identity axes at 528/544/560. Existing `test_collision.test_box_roundtrip`.
- FO4 packfile decoder, **verified**: `fo4collision.decode` / `decode_bodies` parse Havok 2014 packfiles (`hkpackfile.MAGIC` `57e0e05710c0c010`). A Starfield box blob starts `\x00\x00\x18\x18TAG0`; `fo4collision.decode(blob)` raises `PackfileError: not a Havok packfile`. Command: `python -m unittest tests.test_collision_bounds_oracle.CollisionBoundsOracleTests.test_fo4collision_rejects_starfield_box_blob`.
- Compressed-mesh / convex `fo4-native` output, **verified**: `meshcollision.convert_bodies` writes Starfield TAG0 tagfiles (`hknpCompressedMeshShape` / convex / compound), not the 6168-byte box template. `sfcollision.check_template` raises `CollisionError` on a synthetic CMS blob (`hknpCompressedMeshShape` present). `fo4collision` cannot parse them either (same packfile magic miss).
- Existing readback, **verified**: `sfbodies.blob_bodies` / `nif_bodies` already decode converted Starfield tagfiles (CMS via section @48/@60/@72, hulls, and `sfcollision.read_box` when `len(blob)==6168`). `scripts/oracles/collision_bounds.py` uses that path; it does not add a new Havok layout.
- GO: the oracle. NOT go: treating `fo4collision.decode` as a Starfield output decoder, or inventing a second CMS parser.

## 2026-10-17 Grok: FO4 FLOR harvest -> Starfield FLOR (playtest row 14)

- Question: what Starfield record harvests like FO4 flora, and how many placed plants the core would promote.
- Method: raw walk of `Starfield.esm` 1.16.244 `FLOR` group (`fo4land.Plugin`); keyword / `PFIG` targets resolved to
  EDID; `terrain_core64c_work_fix3/selected.json` type counts (read-only). `Fallout4.esm` is at the Steam
  depot_377163 path (**verified** exists).
- Starfield, **verified**: 300 `FLOR`. Harvest fields are still `PFIG` (ingredient) and `PFPC` (four seasonal
  percentages). 169 carry `FloraTypeOrganic` 00222E03; 106 of those also `OutpostCanDomesticate` 002AC11D. Crop
  templates `FloraMaizeCrop01` 000EC886 (and wheat) `PFIG` `OrgCommonNutrient_Seed` 00260DF2. `PNAM` `CC 4C 33 00` and
  `JNAM` 360 match the ACTI marker colour / activation angle TerrainOverlays already writes.
- Core placed flora, **verified**: 3,520 refs, 48 bases before exclusion; writer emits 3,518 / 47 (2 initially
  disabled dropped, FloraInstituteGourdVine01 leaves). Crops: tato 320, mutfruit 328, gourd 251, corn 230, melon
  199, tarberry 134, razorgrain 106.
- Mutagen `Flora.Ingredient`, **verified** on 0.55.0-alpha.67: default seed and custom MISC both serialize to
  `PFIG`; a STAT ingredient is refused. No byte patch.
- FO4 `PFIG` per base: master **verified** present; a produce table is **unresolved** (FO4 targets are ALCH,
  Starfield `PFIG` is MISC/LVLI). Shared field names make a native FLOR promotion **supported**. In-game harvest
  on a converted FO4 mesh: **unresolved**.
- Plan: [docs/terrain/flora.md](../terrain/flora.md). Promotion class built on `grok/flor-research` (make_cluster
  `flora`, `cluster_flora`, TerrainOverlays Duplicate of FloraMaizeCrop01). Overlay not run in game.

## 2026-10-17 Grok: greyscale-to-palette bake (playtest row 15)

- Question: why Museum of Freedom picture frames and the brass plaque render as flat grey-black boards, and
  whether a greyscale-to-palette bake is the fix.
- Method: converted NIFs and DDS under `C:\Modding\staging\terrain_core64c_work_fix3\convert` (read-only);
  Claude's review against vanilla FO4 BA2s at depot_377163; Material-Editor `BaseMaterialFile` (byte 62) and
  NifSkope `fo4_default.frag`.
- Row 15 frames/plaque, **verified not palette materials** (Claude, vanilla BA2s):
  `PaintingGeneric_CanvasSwap.BGSM` / `CanvasPainting01.BGSM` have empty greyscale and byte 62 = 0;
  `BrassPlaque.nif` flags1 `0x80400281` (bit 0x10 clear), slot 4 a cubemap. Before/after this bake they are
  byte-identical. The frames are a per-reference material swap (`PaintingGeneric*` / `PaintingAbstract*`);
  nothing in this repo reads MODS/XMSP. That is the row 15 root cause and is outside this PR.
- Converter gap, **verified** on other materials: 278 v2 BGSMs have the greyscale string **and** the flag.
  5 have the string with the flag off (e.g. `ConcreteRoadHW01.BGSM` names a cubemap). Gating on the string
  alone made that road a fallback. Bake is gated on byte 62 / NIF flags1 0x10.
- Lookup, **supported hypothesis**: U = green channel, V = `clamp(round(scale * H - 0.5))` from
  `fGrayscaleToPaletteScale` (BGSM last float) or the NIF lighting-shader scale (nif.xml after rimlight;
  optional backlight when rim is FLT_MAX). Texture-set cache identity includes that scale. Vertex-colour V
  is **unresolved**. A missing palette texture is a conversion error. GreyscaleToPalette_Alpha (bit 0x20)
  is not baked. v2 `parse_bgsm` reads texture strings at byte 63 so a decoy `.dds` in the header cannot
  steal the greyscale slot.
- Status: bake is for flagged palette materials. Row 15 needs material swaps, not this PR. In-game colour
  after a scratch reconvert **unresolved** (Claude).

## 2026-10-17 Grok: playtest rows 11/13/15 materials (core64c convert, work_fix3)

- Question: why hanging vines at Red Rocket are black jagged strands (row 11), Sanctuary interior walls washed
  white (row 13), and Museum of Freedom picture frames / brass plaque are grey-black boards (row 15).
- Method: converted NIFs under `C:\Modding\staging\terrain_core64c_work_fix3\convert` (read-only), `vine.mat` /
  house / frame / plaque `.mat` files, `texture_log.json`, `manifest.json` (0 fallbacks on these models), texconv
  decode of the colour DDS, vanilla Starfield templates in `ContentResources.zip`
  (`GrassTropicalPlant01`, `FloraBaseLeafyGreen01`, `ConduitKit01TwoSided` / `TwoSided1Layer`).
- Row 11 vines, **verified**: `vinehanging06/07` and `vinecreepermed01` all use `materials\fo4core\landscape\plants\vine.mat`.
  That file already has slot-2 `vine_opacity.dds` and `AlphaSettingsComponent {AlphaTestThreshold 0.361, HasOpacity true}`
  (BGSM alpha test was converted). It still parents `PlasticPlainSmooth01` via the `MetalIronCast01` clone;
  `Summary.Layer1.Textures` has no `Opacity` key. Vanilla foliage parents `TwoSided1Layer` /
  `TranslucentTwoSided1Layer` / `VegetationTranslucent1Layer` and names Opacity in Summary. `two_sided` is parsed from
  BGSM byte 48 and was never passed to `_convert_texture_set`. `vine_color.dds` luma mean 3.8 (85% of texels
  alpha < 128, BC1-black in the cutout); opaque texels still only luma 26. Without a two-sided cutout shader the
  metal material draws the whole card, which is black. Fix: clone `ConduitKit01TwoSided.mat` when an opacity map
  exists, write Summary Opacity, force metalness 0 so the conduit metal map does not leak.
  **Correction (review #288):** forcing metalness 0 only updated Summary plus an existing TextureReplacement
  index 4. The real ConduitKit01TwoSided template has no such component (verified in ContentResources.zip), so
  the conduit MRTextureFile/index 4 stayed. The writer now creates the enabled replacement and drops that file.
  Opacity generation is gated on `alpha_test or decal`; `two_sided` alone is not a cutout.
- Row 13 walls, **supported hypothesis**: `res01playerhouseinteriorrr.nif` wall shapes use
  `metalpanelsresidential01rr` (colour luma 184) and `wallpanelmetalrubble02` (luma 164), 0 fallbacks. These are
  bright beige maps, not missing colour (Starfield missing colour is flat white). Separate from the vine shader bug.
- Row 15 frames / plaque, **supported hypothesis**: `pictureframe03` canvas
  `paintinggeneric_canvasswap_color.dds` and `canvaspainting01_color.dds` are identical, luma 29 max 59; plaque
  texset colour luma 15 max 59. Converted as regular albedo, they are dark grey boards. `canvasswap` names a
  greyscale-to-palette path the converter does not implement. Separate root cause from vines.
- Power armor on that roof is out of this pass (skinned rest pose / furniture class).

## 2026-10-17 Grok: Red Rocket garage button (playtest row 21) and object LOD (row 24)
- Row 21, **verified**: FO4 button `056BBA` is `Default1StateActivator`; garage `056331` is ACTI `Default2StateActivator`
  with XAPR→button. core64k promotes both as inert ACTI. Native wire: vanilla `DefaultActivateLinkedRefOnActivate` +
  XLKR `LinkCustom02` `0005D5E7` (Paradiso `000C7311`; debug ACTI `002CBE61` has the script name and no extra
  properties). Writer implements that on the two Commonwealth pairs; no new FormIDs, no .pex.
- Garage animation, **supported**: sequences are Opening/Closing, not Open/Close. **Not in this PR**: treating
  `Opening` as an animated door in `pipeline.py` turns both FO4 garage meshes into passable statics because
  `RedRGarageDoor.nif` is skinned and the rigger refuses it. Garage NIF rig is a later Claude build item.
- Row 24, **verified**: object LOD is `lodsettings/*.lod` (861 of 864 are 20 bytes; 2 are 22, 1 is 16) +
  `meshes/lod/generated/…_lod_0..3.nif`; core64k has none. `uExterior Cell Buffer=36` is not the product fix. Plan:
  CK generate on a tiny overlay (Claude; **hypothesis** that CK is the generator); no build now. Docs:
  [garage-button.md](../terrain/garage-button.md), [object-lod.md](../terrain/object-lod.md).

## 2026-10-17 Grok: 3D surface map for this testing stage (ROADMAP §3 item 1)
- Question: what Starfield's surface map draws from, why the Commonwealth overlay would show Mars, and whether an
  overlay world can appear there from our plugin and locally generated files; go/no-go for a 3D map this stage.
- Method: pinned `terrain_core64k` read-only (`fo4land.Plugin` on `FO4TerrainCore.esm` / `_Mars.esm`, walk of staged
  `Data\`); cross-check [map-markers.md](../terrain/map-markers.md), [overlay-records.md](../terrain/overlay-records.md),
  [architecture.md](../terrain/architecture.md), journal 11 Oct lodsettings note. No game input.
- Surface map, **supported**: May 2024 3D map draws the current loading zone (overlay BTD + planet procgen + world
  object LOD). WRLD `MapData` is all zero; there is no separate map-mesh group. World object LOD is
  `lodsettings/<edid>.lod` + `meshes/lod/generated/…_lod_0..3.nif`, not converted FO4 `*_lod.nif`.
- Why Mars, **verified** on core64k: LCTN `01000802` parent `SSol_PMars_Surface` `0001B736`, LocTypeOverlay; WRLD
  overlay SNAM 0 / PNAM 4; Mars PNDT `0003F59A` 11 `CNAM` entries, last lat 0.3 lon −1.2 WRLD `01000803`. Staged Data:
  BTD 103,172,485 B, overlay mask present, **0** `lodsettings`, **0** `meshes/lod/generated`, **315**
  `meshes/fo4core/lod`. LCSR/LCID still empty.
- Overlay on the 3D map, **supported**: unique overlays already activate and merge (owner walked core64k). Vanilla
  cities of the same family show on the surface map. Marker + CK object LOD still required for the acceptance
  screenshot. Map camera sampling overlay BTD vs planet SFTR is **unresolved** until Claude's screenshot.
- GO: this note; then #296 LCSR tail `0xFFFFFFFF` and Claude screenshot; then CK object-LOD trial (ROADMAP item 3).
  NOT go: custom map renderer, unparent from Mars, FO4 `.bto`, treating `fo4core/lod` as world LOD.
  Doc: [docs/terrain/surface-map.md](../terrain/surface-map.md).

## 2026-10-17 Grok: overlay map markers / fast travel (owner playtest row 7)
- Question: why the Commonwealth overlay has no map / fast-travel data, and whether restoring a vanilla marker chain
  is the first writer change (Claude 04:07 packet, after textures and FLOR).
- Method: raw walk of `Starfield.esm` 1.16.244 (`fo4land.Plugin`, no Mutagen) for top groups, STAT MapMarker, LCTN
  `LCSR`/`LCID`, LC172 and LandingOverlay01; read-only walk of pinned `FO4TerrainCore.esm`; writer
  `dotnet/TerrainOverlays/Program.cs` Duplicate of `LC172WorldLocation` then `MasterSpecialReferences.Clear()`.
- Map markers, **verified**: Starfield has no `MAPM` group (176 top groups). Markers are `REFR` of STAT `MapMarker`
  `00000010` with empty `XMRK`, `FNAM`/`TNAM`/`UNAM`. LC172 persistent `REFR` `003E5E12`: `NAME` `00000010`, empty
  `XMRK`, `FNAM` `0x1B`, `TNAM` `0x17`, flags `00000C00`.
- Location link, **verified**: `LCSR` is 5 × u32 (`LCRT`, `REFR`, `WRLD`, 0, `0xFFFFFFFF`). LC172WorldLocation
  `003807BE` has two rows (Landmark_SnowGlobe_RefType `00009A42` → `00009A32`, MapMarkerRefType `0002271F` →
  `003E5E12`) and `LCID` `003E5E12`. LandingOverlay01Location adds ShipLandingMarkerRefType / `_Large` on the pad.
  Mutagen names: `MasterSpecialReferences` = `LCSR`, `MasterInitiallyDisabledReferences` = `LCID`.
- Our overlay, **verified**: writer clears both lists after Duplicate; pinned LCTN `FO4Core_CommonwealthLocation`
  `01000802` has empty `LCSR`/`LCID`; 654,600 `REFR`, 0 `XMRK`, 0 MapMarker `NAME`. One COC marker at overlay-local
  (−989.257, 1146.514, 107.143).
- Playtest hang, **supported hypothesis**: missing MapMarker/`LCSR` is why the overlay does not match LC172 on the
  planet map. Whether restoring one marker unsticks Frontier travel (a ship location) is **unresolved** until Claude
  runs a scratch overlay.
- FO4 `XMRK` bytes: **unresolved** (`Fallout4.esm` not on this machine).
- GO, **implemented offline**: TerrainOverlays Duplicates LC172 MapMarker `003E5E12`, parks it at the COC in
  `TopCell.Persistent`, fills `LCSR` MapMarkerRefType + `LCID`; FormIDs after doors/lights. Do not stamp a PCM landing
  overlay. NOT go: FO4 marker promotion, ship pads, swapping unique overlay for landing overlay. In-game icon / Frontier
  hang: **unresolved** until Claude's scratch overlay.
  Doc: [docs/terrain/map-markers.md](../terrain/map-markers.md).

## 2026-10-16 Claude: posed props in the pinned interiors (owner playtest rows 4 c and 5)
- Question: why does the pinned interior build (`integ_1011`) show the Vault 111 radiation scanners with "swung out"
  panels and the lab-coat skeleton `Vault111SkeletonScientist02` standing, and how many models and references of the
  16 interiors share the cause?
- Method: the build's provenance (`integ_1011/build.log` line 1, `git branch --contains`), its `manifest.json`, the 16
  cell exports, the FO4 NIFs (`nif`, `fo4skin`, `ragdoll_pose`, the door sequence samplers), an offline conversion of
  every affected model into a scratch folder (`convert_batch.py --cell-json` on the affected references, then
  `dotnet/PluginSpike`, the plugin read back record by record), flat-shaded renders of the converted meshes as placed
  ([docs/media/posed-props/](../media/posed-props/)). Census and render scripts stayed in the scratch folder.
- Cause, **verified**: `integ_1011` was built from `a5bc92e`, which has neither `fo4skin.py` (PR #45) nor the node-pose
  bake (#46) nor `ragdoll_pose.py` (#52); all three were still open, so `main` drew every skinned shape from its stored
  positions (the skin's bind pose, `pipeline.convert_nif`: "taken in bind pose") and had no XRGD path at all, although
  the cell exports carry the `ragdoll` entries (`Vault111Cryo.json` 1A6736: 17 entries). The skeleton's converted mesh
  box equals its stored positions (z 0.6..131.8 units: standing, arms out), while its merged rigid body sits on the
  bone nodes (node pose: root bone turned 45 degrees). Posed with the reference's XRGD, the converted mesh lies on the
  floor: world z -3.4..31.4 at reference z 13.7 (bind 14.3..145.5). `Vault111SkeletonVaultSuit` 1A6737 (reference
  rotation x = pi, i.e. upside down) runs from 117 below to 100 above the floor in the bind pose and lies at -2.4..19.4
  posed.
- Rad scanner, **verified** not a pose problem; the "panels swing out" hypothesis of row 5 is **refuted**:
  `V111RadScanner01.nif` has no skin (2 BSTriShapes without VF_SKIN), two NiNodes (root, SoundNode), and its four
  sequences animate only the `GlowPanel:0` effect shader (BSEffectShaderProperty colour / float controllers; the
  NiMultiTargetTransformController's 4 targets are all -1). The converted mesh's box equals FO4's exactly (x +-15.6,
  y -25.2..37.0, z 0..185.5). The tall panel is authored 10 degrees off vertical (y 20.2 -> 36.9 over z 88.9 -> 183.6);
  in FO4 the glow quad (`V111RadScanner01FX_d.dds`) lies on it, and the converter skips that effect shape (neither
  glass nor grime, `_shape_material`), so the bare slab shows. Its colour textures are in the texture archive.
- Animated skinned models, **verified** offline: the node pose, not the bind pose, is a state of their animations.
  Sampling every NiControllerSequence at its start and stop (bones it animates take the sampled local transform, the
  rest their NIF transform) for the 9 animated models in the census: the stored positions match no state of any
  sequence (59..6,661 units off), the node pose matches the start of at least one sequence exactly for every skinned
  shape (VltElevator `stage1`, VltGearDoor01 / 02 `Stage1`, generator `autoPlay`, sinks / fountain `partA`, grenade bouquet,
  holly shrub). Examples: the elevator's bind pose puts the surface hatch (`Hatch:28`, 7.4 x 7.1 m) on the vault floor
  (z -8..8); every sequence keeps it at 6,570..6,586 (row 6's yellow square may be this hatch: **supported
  hypothesis**); its platform is 1,279..1,391 at `stage1` start, -232..-121 in `Stage2Idle` and 1,418..1,530 in the
  bind pose, so it stays wrong until the elevator animates (row 6). The gear door's walkway is extended with its ramp
  through the floor in the bind pose and retracted in the node pose (= `Stage1` start; the extended end state of
  `Stage2` / `Stage3` / `Stage0` is 120 units from the bind pose). Which sequence a graph starts in: **unresolved**.
- Fix (this PR): skinned shapes are posed with the bone nodes' placed transforms (`world_transforms(placed=True)`, the
  frame the shapes and collision bodies already use: a moved scene root no longer offsets the skin alone); a reference
  whose XRGD moves an articulated model (two or more bodies) gets a model of its own built in that pose
  (`placed_pose.plan`, `convert_static pose=`: the entries replace the bone nodes' local transforms for the skin, the
  shapes under the nodes and the bodies, so the merged rigid body is posed too), named `<base>_xrgd_<pose hash>`; the
  plugin writer gives exactly those references that base (`PosedBases.cs`). Single-body items keep the shared model:
  an entry on the root body would turn the whole item against its reference, which no resting test has checked.
- Counts (16 interiors: the `integ_1011` manifest and the 16 cell exports, 60,268 references, 47,619 placed with a
  converted model):
  - node pose: 97 converted models have skinned shapes, 20 move 2 units or more in the node pose (9 animated), the other
    77 move less than 0.1; 180 of the 1,192 placed skinned references use the 20 (73 animated): `Vault_Sink_01` 32,
    `SkeletonClothedVaultsuit` 28, `HollyShrubSmall01Trimmed` 20, `SkeletonClothed01` 17, `SkeletonBareBody01` 17,
    `Vault_Fountain01` 13, `SkeletonClothed02` 12, `SkeletonClothedScientist` 7, `skeletonclothedarmy02` 7,
    `skeletonclothedarmy01` 6, `SkeletonClothedScientist02` 5, `PowerArmorFurniture` 4, `SkeletonBareBodyHeadless` 3,
    `V111Generator02On` 3, one each of `GrenadeBouquet_LongTriple`, `Tricycle01`, `PlayerHouse_Sink01`, `VltGearDoor01`,
    `VltElevator`, `VltGearDoor02`.
  - XRGD: 507 references carry ragdoll data. 147 get a posed model (147 distinct poses of 24 models: 112 skeletons,
    `SawHorse01Dest` 17, `ConstructionBarrier01Dest` 10 / `02Dest` 8, `Jangles01` 3, `Gurney01Cushion` 3, ...,
    `V111GearRoomGate01` 1); 48 pose within 0.5 units of the node pose (shared model); 214 are single-body loose items
    (`Pillow01`, `NukaColaBottleEmpty`, `Pen01`, ...) left as they are; 45 are rejected (19 entry count != body count:
    stale XRGD; 26 models without collision bodies); 53 sit on models that were not converted.
  - Together 231 placed references change (96 through both): Vault 95 48, Vault 75 35, Vault 114 33, Boston Public
    Library 30, Vault 81 15, Vault 111 14, FortHagen01 12, SuperDuperMart01 12, FortHagen02 9, CambridgePolymerLabs01 8,
    MuseumOfWitchcraft01 5, ParsonsState01 4, PrydwenHull01 4, RedRocket01 2.
- Offline end to end: the scratch conversion (35 models + 147 posed models, 0 failures, 54 s) and plugin (275
  references): read back, 147 references sit on their own posed base and 128 on the shared one, 0 wrong.
- Review fixes (PR #244 review): only a vertex move of 0.5 units or more makes a variant (moved body nodes alone carry
  only collision), and a multi-body pose with a body on the scene root is refused. **Verified** by rerunning
  `placed_pose.plan` on the same inputs: 146 posed (`SmallSandbagPile01` 1A4857 drops out: stale entries with a fitting
  count, vertex shift 0; the review measured its posed collision about 4 m off the pile), 46 unchanged, 48 rejected (the 45 above plus 3 with a
  root body, which were unchanged before; the shared model either way). Single-body, not-converted and door counts unchanged.
- Status: cause **verified**; "FO4 shows a placed ragdoll in its XRGD pose" **supported hypothesis** (PR #52's Vault 114
  resting test, the Vault 111 skeletons lie on the floor posed, 1A6737's upside-down reference rotation only makes sense
  posed); how Starfield shows the posed models (and whether the movable posed bodies stay put) **unresolved** until a
  build is looked at in game. Single-body XRGD: **unresolved**.

## 2026-10-16 Claude: which vanilla doors slide or lift, and can one drive the FO4 vault / elevator doors? (owner rows 1, 6)
- Question: the 10 FO4 door bases the pinned build leaves passable (`door_not_opening`: V111Door01, V111DoorSpecial01,
  VltDoorRes01A/B/C, VltElevatorDoor02, VltElevatorDoorCarInt02, UtilMetalElevatorIn01/Out01/Hatch01; 106 placed refs in
  the 16 cells): is there a vanilla Starfield door whose rig moves like each of them, as the Akila rig drives hinged
  leaves?
- Method (read-only; extracted files only under `C:\Modding\scratch\slide_doors`): `SfInspect doortsv` (every DOOR's
  ANAM / BNAM / CNAM); each of the 123 distinct rig + clip folders read back with CALUMI (rig bones, per-track rotation
  and translation keys of every `.af`); end offsets put in model space with the parent's global bind; FO4 side with
  `door_motion.inspect` / `door_rig.plan` on `Fallout4 - Meshes.ba2`; vanilla collision layout from 9 door NIFs.
- **verified**: 339 DOOR records, 310 with a graph; 215 use `SimpleOpenClose01.agx`, load variants `*_Load`. Of the 123
  rigs, 51 move a bone sideways or diagonally by 0.25 m or more, 12 lift one (5 both), 59 only rotate, 4 move no bone
  that far, 2 are state graphs (corrected 2026-10-16 after the PR #242 review: the first count, 47 / 12 / 59 / 2, left
  diagonal moves out). Sliding and lifting doors (`ElvGen_ExSm_DoorInner01`, `StsGenIntRmSmWallMid_DoorD01`,
  `HangarDoor_4x4`) use `SimpleOpenClose01.agx` like hinged ones; the motion is their own rig and clips. No vanilla rig
  drops a panel straight down or splits two panels up and down; 5 rigs end a bone 0.25 m or more lower (docking-door
  release helpers -0.26 m, the ExLg door latch -0.32 m, `LC017NASA_GravDrivePrototype_Door01`'s two panels 0.52 m down
  and 0.52 m sideways). The first wording here ("no door panel moves down") was wrong.
  Vanilla multi-panel doors keep one physics system with a body per panel (9 of 9 NIFs).
- **verified** (FO4): vault doors lift the upper panel +2.116 m and drop the lower -0.976 m (V111 also flips 2 floor
  slats 90 degrees); the elevator pairs slide +-0.64 / 0.68 / 0.80 / 0.914 m; the hatch flips 100.5 degrees about -y.
  VltDoorRes01A/B/C failed `door_rig.plan` only because their Open / Close also drive a shader float
  (`BSLightingShaderPropertyFloatController` on the override-box shapes), which `inspect` reported as a binding issue.
- Result: no vanilla rig reproduces any of the 10 (elevator pairs travel 1.00 / 1.50 / 4.00 m: 9-56 % too far; no
  downward panel for the vault doors). Implemented instead: own rig + FO4 keys (the #79 multi-part path) for
  `NOT_HINGED_RE` doors when `--door-anim-dll` is given; non-transform tracks listed, not issues; manifest
  `open_motion`. **verified offline**: without the library byte-identical to main (57 door models); with it the 10
  doors rig (CALUMI read-back of our clips gives FO4's offsets), door_panels 72 of 72 parts move, door_bodies 0 errors,
  plugin overlay: 10 STAT -> 10 DOOR, 106 REFR change only their base. In game: **unresolved** (our rig and clips have
  never played; #79's doors neither).
- Elevator: **verified** what vanilla uses (`ElevatorMasterScript` 2 refs with a `PlatformHelperFree01` helper driven
  by graph variables; `MovingPlatformMasterScript` 22 refs moving a helper with `TranslateToRef` between floor markers,
  parts attached by AttachRef; load elevators). That the in-cell ride can be built from records only is a **supported
  hypothesis**; the surface exit waits for the interior-exterior door gate. Details: docs/spikes/sliding-doors.md.

## 2026-10-16 Claude: BSMeshLODTriShape triangle groups are parts, not alternative LODs (Vault 111 tables without tops)
- Question: why do Vault 111's NpcTableVaultSit02 tables (`SetDressing\Vault\Vault_Table_02.nif`) show their frames
  but no tops in the playtest build (integ_1011)?
- **verified** (source from `Fallout4 - Meshes.ba2` via `fo4sf.ba2`, decoded with `nif.parse`): one
  BSMeshLODTriShape (block 4, 2,210 vertices, 1,702 triangles, 12 trailing bytes = LOD0/1/2 Size **(684, 0, 1018)**).
  The 684-triangle LOD0 group holds the top (4 up-facing triangles at z 55-60, 10,467 sq units) and a shelf (z 30-35,
  7,445); the 1,018-triangle LOD2 group is frame only (129 sq units facing up). The two groups share no vertex and
  together use all 2,210.
- **verified**: `nif.fo4_trishapes` kept only the largest group ("triangles hold all LOD levels back to back: keep
  the most detailed", added 2026-10-07 without evidence). The shipped mesh
  `integ_1011\geometries\96785ef3080773180767\0f2d4812a8477d5e5f63.mesh` has 1,018 triangles, 666 vertices no
  triangle uses (exactly the LOD0 group's) and 0.016 m2 facing up above 0.7 m. Converted with the fix: 1,702
  triangles, 0 unused vertices, 2.153 m2 facing up above 0.7 m. Not a material, alpha or winding problem: the top's
  triangles were missing from the mesh.
- **verified** (scan of every NIF in Meshes.ba2 + MeshesExtra.ba2, 63 s): 5,292 BSMeshLODTriShapes in 3,319 NIFs
  (all in Meshes.ba2; the 95,856 precombined NIFs' LOD shapes store no geometry) have more than one non-empty group.
  5,290 of them share no vertex between groups and use every vertex exactly once, the layout of one mesh cut into
  parts; alternative LOD versions would each cover the whole surface, but the old rule dropped a median 42 % of a
  shape's surface area (up to 98 %, e.g. `IndFrame1024x1024EmptyShapeEdge01.nif` keeps 800 small triangles and drops
  the 68 that make the panels). nif.xml (fo76utils NifSkope) describes the Skyrim form BSLODTriShape as "visibility
  control over vertex groups".
- **supported hypothesis**: the game draws the LOD0 group at every distance and adds the LOD1 / LOD2 groups closer
  in (NifSkope's renderer is recalled to draw all three at its highest detail level; not checked against source
  here). Either way the full-detail mesh is all groups, which is what the converter now writes.
- Scope: 534 of the 4,201 models in integ_1011's manifest lose triangles under the old rule (623 shapes, 187,752 of
  874,690 triangles); 486 lose at least 10 % of some shape's surface, 345 at least half. Fix: keep every triangle
  (tests/test_lod_trishape.py). Not yet seen in game: needs a rebuild and the Vault 111 tables checked in a playtest.

## 2026-10-13 Claude: the first live door_trip runs, and why our persistent refs read unmerged
- Question: why did the first live Red Rocket cave door runs (queue `slice_door_1013`, exp2d + FO4SliceRedRocket.esm,
  runner 129b9ae) end INCONCLUSIVE UNREAD (a1) and FAIL NOLOAD (a2), and what must change in the runner and the
  plugin? Details: [docs/slice/door-frames.md](../slice/door-frames.md).
- **verified** (a1 obs.json and captures): a garbled read "99.74 -2195.27 99.41" (the previous read's z, this read's
  x and z; the default parser's bare-number fallback) made the step declare a load 3 m before the door; another read
  turned "-1 593.51" into -1.59; `player.GetInCell FO4Port_RedRocket01` was refused ("Item 'FO4Port_RedRocket01' not
  found for parameter Cell." / "Compiled script not saved!"): the PR #78 GetInCell hypothesis is **refuted** for
  EditorIDs; the door's getpos read its unmerged local position (a1 and a2). The console selection "DOOR 'FO4SL_F..."
  in the capture is the getpos diagnostic's `prid`, not a crosshair pick (**supported**).
- Runner fixes (runner features `door_frames`, `door_route`): strict labelled reads (`parse_getpos.py --strict`), no
  load from one read (a second far read must agree within 1 m; swapped axes rejected), GetInCell only with a form id
  and never judged, the side of the door from position frames, the facing on arrival and after the load
  (`getangle z`, reply format **supported**), routes walked from the arrival (no start teleport), merge probes.
  Synthetic tests and sandbox scenarios reproduce the a1 garble and the GetInCell refusal.
- **verified** (`scripts/slice/persistent_refs.py`, raw walk): all 432 worldspace persistent cells in Starfield.esm
  have record flag 0x400 and DATA XCLC LTMP XCLW XILS; ours (TerrainOverlays, exp2) have flag 0 and DATA only.
  LC172World's persistent COC marker 0010238E (NAME DATA, in the persistent cell like our anchors) read merged in
  game (terrain_A2_lc172, 2026-10-11). 432 of 433 vanilla WRLD records have OFST / CLSZ, ours none. Vanilla keeps
  overlay-world doors in the persistent cell and writes XTEL arrivals into overlay worlds in the local frame (44 of
  44 within 19.6 m of the destination door's local position), as we do.
- **supported hypothesis (fix A):** the merge moves a world's persistent refs only when its persistent cell has the
  vanilla shape. `SliceDoor build` can now give the slice plugin's persistent-cell override LC172World's record
  (`persistent_cell` template; checked offline) and place merge probes (a persistent and a temporary XMarker in an
  exterior cell). The discriminating test is read by the door_trip step after the coc arrival: the door, core64c's
  anchor, both probes; vanilla control: `merge_ctrl_lc172`. **unresolved:** whether A works, the OFST / CLSZ
  alternative, GetInCell with a form id, the GetAngle reply.

## 2026-10-13 Claude: a walkable Red Rocket <-> Sanctuary route on core64c, and a runner kind that walks it
- Question: can the runner make the player walk (no teleports) from Red Rocket over the Sanctuary bridge into
  Sanctuary and back on core64c, and what proves the terrain and objects stay loaded and walkable on the way? Details:
  [docs/terrain/walk-redrocket-sanctuary.md](../terrain/walk-redrocket-sanctuary.md).
- Method: `scripts/terrain/walk_route.py` (Fallout4.esm NAVM of FO4 cells x -21..-15, y 17..24, A* and funnel; a
  0.5 m walkability raster from that navmesh and core64c's converted collision; line-of-sight smoothing; exact capsule
  checks with `exterior.capsule_hits`); runner kind `walk` (`qstep.ps1`, `walk_eval.py` controller and judge,
  `input.ps1` guarded `holdg`); synthetic unit tests, qstep sandbox scenarios and an ideal walker through the staged
  plan judged against the real ground file.
- Evidence (offline, verified): Fallout 4's own shortest navmesh path is 248.73 m (152 NAVM records, 99,419
  triangles, 223 in the corridor), but a standing capsule (0.35 m radius, 0.4 m step) meets core64c's converted
  collision at 33 of its 499 samples (guardrails, a station wagon, a trash can, a fence post, a swing set, a tree
  stump, the elm at the cul-de-sac): the baked navmesh runs under these objects. The raster path is 254.33 m, clear at
  all 510 samples and on navmesh at all of them, 44.47 m on the NorthBridge deck (01F970, 107.8 -> 109.9 -> 107.9 m),
  across the local cell borders x = -1000, x = -1100, y = 1200, x = -1100; tallest step 0.335 m. The planner's
  output is byte-identical when run again. The "BOUNDARY REACHED" box leaves the HUD's oxygen ring and health bar
  visible, so a HUD check cannot see it; Windows OCR of the screen centre of Codex's capture read the title in 0.5 s
  (the walk checks it after every leg). An ideal walker through the staged plan: 27 to 32 legs, PASS both ways
  against the real walk_ground.json.
- Status: route and runner **verified offline / in the sandbox only**; whether the player walks it in game (speed,
  steering, the 0.335 m step, loading and popups at the borders and on the bridge) is **unresolved** until the queue
  `C:\Modding\testqueue\walk_core64c` runs. Why Fallout 4's navmesh passes under those objects is **unresolved**.

## 2026-10-13 Claude: why some converted loose items did not move when the player walked into them
- Question: converted FO4 loose items are MoveableStatic records with dynamic bodies (2026-10-10 entries below). In the
  queued tests a trash can and a book moved, a cigarette pack, three books and two bobby-pin boxes did not. The only
  FAIL was supervised_1011 0007 (FAIL NOTMOVED). In batch_full every movable test was MISSED or skipped by the movable
  circuit breaker (about 610 tests); judged by the walk's closest approach (the 2026-10-12 fix), 0095 / 0096 / 0099 /
  0100 were within reach and would be FAIL NOTMOVED. Is it our conversion (fixable), Starfield's character controller
  (vanilla items the same), or unresolved?
- Method (read-only, local scripts not in the repo): field dumps (`hktagfile`) of the converted NIFs of the pinned build
  `integ_1011` (build 2470f876) and of 2,379 vanilla NIFs used by Starfield.esm MiscItem / Book / MoveableStatic records
  (record list from `SfInspect models`, NIFs from the mesh archives with `fo4sf.ba2` / `nif`); Starfield.esm `COLL`
  records (the collision matrix) and `MSTT` subrecords of FO4Port.esm and Starfield.esm by a raw group walk; the cell
  exports' REFR entries; `obs.json` and the screenshots of supervised_1011 0006 / 0007 / 0015 and batch_full 0095-0100;
  Starfield.exe 1.16.244 (`scripts/recon_console.py`, which now also reads the stack-built script-function entries);
  the Papyrus sources in `Tools\ContentResources.zip`.
- Evidence, bodies: all 6,221 vanilla dynamic item bodies have motionType 2, flags 0x8a, qualityId 255,
  collisionCntrl 0, collisionLookAheadDistance 0, activationPriority 0; 5,389 use the motion properties gravity 1,
  linear / angular damping 0.1 / 0.05, max speed 100 / 200, deactivation 0.0025 / 0.0025 / 4 passes; 4,788 are on layer
  4 (CLUTTER). The converted BurntBook01, CigarettePack, BobbyPinBox and TrashcanMetalOffice01 have exactly these values,
  layer 4, BSXFlags 0x42 with the collision on the root node (vanilla: 1,698 dynamic bodies under BSXFlags 0x42, all on
  the root node; 4,140 under 0x4A and 36 under 0x6A on child nodes; 347 under 0x4A on the root) and one
  hknpRefMassDistribution each.
- Evidence, collision matrix: Starfield.esm `L_CLUTTER` (index 4) collides with `L_CHARCONTROLLER` (30) and
  `L_BIPED_NO_CC`; `L_DEBRIS_SMALL` (19) does not. The player's controller collides with our items.
- Evidence, records: our MSTTs carry DATA 04 like vanilla, but OBND all zero and no FLLD (vanilla: real bounds, FLLD 1);
  the trash can that moved has the same zero OBND.
- Evidence, masses: converted (FO4's inverse mass): BurntBook01 25 kg, CigarettePack 10 kg, BobbyPinBox 50 kg, trash
  can 15 kg. Vanilla items of a similar size: BookMedium02 / BookSmall02 10 kg, ContemporaryCigarettesPack01 5 kg
  (8.5 x 4.6 x 15.7 cm upright; our pack 7 x 3.7 x 14.5 cm upright), Office_NotePad_Stack01 / 02 5 kg (3.8 / 5.7 cm),
  Office_Folder01 8 kg, DataSlate01 5 kg; vanilla dynamic item masses: median 10 kg, 10th percentile 2 kg. Both games
  make small clutter heavy; FO4's small items are 2-10 times Starfield's.
- Evidence, placements (corrected after the verifier of PR #110; the reads are obs.json's): one model moved and did
  not move. BurntBook01 `217AC5` (Vault 114 0015, scale 0.86) lay on a bench seat 0.45 m above the player's feet at the
  stand point (item z -0.91, player -1.36); the player climbed onto the bench and ended 0.07 m from where the book had
  lain (z -0.68), and the book moved 0.46 m and dropped 0.29 m off the bench (`before.png`, `after.png`). The reads fit a
  side-on hit just as well as the book being walked over and pushed off; they do not tell which. `0FE25A`, `0FE259`,
  `100D9D` (BostonPublicLibrary02 0095 / 0096 / 0099, scale 1) lay flat on the floor, 4.6 cm thick; the walk passed
  0.02, about 0.13 and about 0.15 m from them and they moved 0.000 m. Same record, same body. CigarettePack `1CBEF6`
  (supervised_1011 0007) lay 0.83 m above the player's feet on a desk (`after.png`: the pack on the desktop, the player
  stopped at the desk 0.67 m from it). BobbyPinBox `1015BB` (0100: item 33.62 68.45 11.78) lay 0.81 m above the
  player's feet at the stand point, but the walk (32.94 67.36 10.97 to 34.31 71.12 11.25) passed 0.26 m from it and the
  player rose 0.28 m on the way, ending 0.53 m below it: inside a capsule's reach and height (supported hypothesis), and
  it moved 0.000 m. BobbyPinBox `100164` (0098) lay level with the player's feet (item z 11.78, player 11.77: the stand
  point is on the item's own surface); the player moved 0.17 m and stopped 1.45 m short of it, blocked by something
  else, not by elevation (MISSED). The trash can (moved 2.21 m, 0.64 m tall, lying on its side in FO4) and the tin can
  of 2026-10-10 (0.56 m) stood on the floor and were hit side-on.
- Evidence, console: `ApplyHavokImpulse` (opcode 0x1251, four Floats, "Applies an impulse of the passed magnitude to the
  reference along a passed axis.") and `SetRigidBodyMass` (0x1156, one Float, "Sets the Havok mass for an object.") are
  in the script-function table, built on the stack like `SetPos` / `PlaceAtMe` / `GetIsID`; `PushActorAway` too (actors).
  `CallFunction` (`cf`) is a console command (decoded 2026-10-14: "Calls a papyrus function on the targeted ref. First
  parameter is the function, the rest are parameters", one String and up to seven optional Strings) **verified**;
  `GetMass` has no console command entry, its name sits among the ObjectReference Papyrus natives (`GetLocRefTypes`,
  `GetMass`, `GetNthLinkedRef`) **verified**: `cf "ObjectReference.GetMass"` is the only console route to the mass, and
  whether it reaches the native and prints the value is **unresolved** (the judge needs the number; else MASS).
  Papyrus `ObjectReference.psc`: `ApplyHavokImpulse(afX, afY, afZ, afMagnitude)`, `float GetMass()`,
  `SetMotionType(.., abImmediatelySimulate)` ("as if the player bumped into it"). `LC012NASAGravTrigger.psc` uses
  magnitude = `GetMass()` x 0.25..0.5, so the magnitude is an impulse in kg m/s (supported hypothesis). The exe has the
  INI setting `fCharacterMaxSlope:HAVOK` and the layer `L_CHARBUMPER` (it collides only with itself and the controller).
- Status: "the converted items' bodies and records match vanilla MiscItem / MoveableStatic bodies on every motion,
  layer, quality, flag and BSXFlags field" **verified** (the mass is the one field that differs); "the same converted
  body moved in one placement (on the Vault 114 bench) and not in another (flat on the library floor)" **verified**
  (BurntBook01), how it was hit there **unresolved**; "the cigarette pack lay on a desk the walk did not reach"
  **verified** (reads and screenshot); "the pin box 0098 was blocked short of it, not elevated" **verified** (reads);
  "the three flat books were walked over and did not move" **verified** (reads); "the pin box 0100 lay on furniture the
  walk could not reach" **refuted** (the walk passed 0.26 m from it): it is the one NOTMOVED that placement does not
  explain, a FAIL NOTMOVED under the corrected judge; "Starfield's controller does not push light or small bodies at
  all" **refuted** as stated (a 25 kg book and 5-15 kg cans moved); "a flat item lower than the step the capsule
  climbs is pressed down, not pushed, vanilla items too" **supported hypothesis**, weakened (the only book that moved
  may have been walked over and pushed too); "FO4's higher masses play no part" **unresolved** (the 50 kg pin box 0100,
  ten times a vanilla box's mass, did not move when the walk passed through it). Both are tested by the staged queue
  `movable_control_1013b` (vanilla notepads 3.8 / 5.7 cm and a folder 0.7 cm next to ours, the converted book and box
  again at 5 kg through `SetRigidBodyMass`, judged only when `GetMass` reads 5 kg back, `fCharacterMaxSlope` through
  `GetINI`).
- Consequence: no converter change yet. The bodies match vanilla, but whether FO4's masses stop the player pushing small
  items is unresolved, and answer (a), scale FO4 masses, stays open until `movable_control_1013b` runs. The movable test
  changes (verifier of PR #110, 2026-10-13): only the walk passes a movable test; a walk that reaches an item and leaves
  it in place is FAIL NOTMOVED with or without the impulse ladder, which only tells a simulated body (noted in the
  detail) from one nothing moves (FAIL STUCK); INCONCLUSIVE ELEVATED (final, not counted by the breaker) only for an item
  more than 0.5 m above the player's highest feet read that the walk came no closer than 0.5 m to, or more than 1.8 m
  above them. docs/ai/test-queue.md "Movable items: walk, then impulse"; decisions.md 2026-10-13. If the queue shows
  vanilla items of a size pushed where ours are not, or the 5 kg variants (GetMass read 5) pushed where the full-mass
  ones are not, mass is the cause: then (a). If `cf "ObjectReference.GetMass"` gets the reply `cf
  "Actor.PathToReference"` got in N0_cf ("No script named ... is attached to the object", supported hypothesis), the
  5 kg tests are INCONCLUSIVE MASS and the mass question needs another reading.
- Correction (verifier of PR #110, 2026-10-13): this entry first said both pin boxes lay 0.81 m up, that the batch_full
  movable tests were FAILs, that the Vault 114 book was hit side-on, and that the books were walked over at
  0.02-0.27 m; the reads give the figures above.

## 2026-10-13 Claude: stairs: where the player got stuck, and why (corrected after QA on PR #111)
- Question: why do batch_full 0002 / 0003 / 0006 / 0007 / 0021 (STUCK), 0022 (FALL) on BostonPublicLibrary02's
  BldDecoSm* stairs and supervised_1011 0010 (Vault114 CinderBlockStairs02) fail, when 12 library stairs tests of the
  same models pass? Conversion or test? Details, per-test table and in-game plan:
  [docs/testing/stairs-routes.md](../testing/stairs-routes.md).
- Method: OCR reads from each test's `obs.json`; the FO4 collision (archives) and the converted collision of the pinned
  build `integ_1011` (`fo4sf.sfbodies` read-back) placed per reference around each route: lane sections, what touches a
  0.35 x 1.8 m player at the read positions, FO4-vs-converted bounds per neighbour, where each stair helper's top face
  comes out of the floors it pierces (FO4's, flattened as the planner models it, converted); the reference rotation
  order checked against FO4's precombined physics of the cell; an offline player walk (`src/fo4sf/walksim.py`)
  replayed on all 64 decided in-game stairs results with `scripts/game/stairs_calib.py` (a stop agrees only at the same
  place: within 0.75 m across and 0.5 m in height); the 16 stair models re-converted with this branch.
- Evidence: 0006 / 0007 start in a 0.49 / 0.48 m slot between BldDecoMdWall01 `0EBEEB` / `0EBEE8` and
  BldDecoSmRailStraightShort01 `0F02AD` / `0F02AC` on the landing (player moved 0.07 m); 0021's flight is crossed by
  the fallen floor chunk `0F0279` (the game stopped 0.57 m before it, the offline walk at it); 0022 walked 6.5 m (old
  `walk_ms` 1410), 2 m past the top into the collapsed floor; supervised 0010's two cinder blocks rise 0.15 m out of
  the cave floor (walked 2.7 m over them; rise 0.10 of 0.12); batch_full 0423 (FortHagen02) stops at the rebar chunk
  `099CC8`. 0002 / 0003 started under the gallery slab at the foot of BldDecoSmStairs03 / Block03, came up onto the
  slab and stopped 0.01 / 0.05 m before the place where the converted (flattened) helper comes up through the slab top
  (x 24.34; FO4's helper at 23.89; the mirrored 0004 passed its crossing at x 34.20); the offline walk lifts the player
  onto the slab 1.3 m earlier and climbs on, also from the game's stop points. Other converted crossings walked into
  from a floor: 7 of 7 passed (Fort Hagen HalfTiny03 / BlockTiny03, moved 0.08-0.18 m, 37.0 degrees; Diamond City
  ShackStairs01 0248, moved 0.54 m, 39.7 degrees). 0002's teleport point overlaps the closed load door `1828D6` (face
  y 28.00), not the wall plug `1828D7` (first version: "face y 27.77"). Re-converted stair models: 16 of 16 bodies
  identical to `integ_1011`, treads / layers / bounds as FO4's, helpers > 40 degrees flattened as designed. Rotation:
  of the library's tilted references found in its precombine, 312 match only R = Rx(-x) Ry(-y) Rz(-z), 3 only the order
  `routes.ref_matrix` used (Rz Ry Rx), 85 both; the debris and chunks on the library stairs 93-100 % vs 0-13 %; 0005's
  in-game start z 3.07 fits the Z-first debris (QA). Offline walk vs game: same verdict 59 of 64, same verdict and
  place 57 (converted collision; 60 / 58 in the planner's scene); first version: "59 of 64 agree", counting 0002,
  whose offline walk stopped 1.95 m from the game's stop.
- Status: 0006 / 0007 / 0021 / 0022 / supervised 0010 / 0423 / 0136 are route errors, FO4's own collision has no usable
  lane on `0F032C`, `09992E`, `170F9F`, `0EBECE`: **verified offline**. 0002 / 0003: why the player stopped at the
  converted helper's slab crossing is **unresolved**; the converter's flattening there (H1) and the under-slab approach
  of the old routes (H2) are both live; probes that tell them apart are planned (page, section 5). The converted
  collision equals FO4's except the flattened helpers: **verified**; whether a flattened helper's crossing of a floor
  behaves in Starfield as FO4's: **unresolved**. `routes.ref_matrix`'s X-first order for tilted references:
  **refuted** (verified Z-first, as PR #102 found on 146,463 of 146,728 tilted precombined references;
  `exterior.ref_matrix` and `PluginSpike.RotateOffset` still X-first, not changed). Player capsule radius 0.35 m:
  **assumed** (first version: supported hypothesis from 0002's push-out, withdrawn: the game pushed the player 0.23 m
  further than a 0.35 m capsule needs from the door's face). One-sided floors that lift a player through them:
  **supported hypothesis** (0004 passed through the slab; 0002 / 0003 were read on it). The offline walk as a model of
  the game: **supported hypothesis** (57 of 64 same verdict and place; it cannot predict the 0002 / 0003 stops). That
  the player pushes movable objects aside (the walk leaves them out): **supported hypothesis** (2026-10-10). Starfield's
  step-up below 0.30 m without a helper (V111, 2026-10-08) leaves VltGearDoorStairs01 (no helper, 0.29-0.31 m treads)
  **unresolved**.

## 2026-10-12 Claude: the Red Rocket cave load door on the converted terrain (slice: working door -> interior -> save)
- Question: which Fallout 4 load door links RedRocket01 with the Commonwealth, where is it relative to the converted
  terrain of experiment 2d, what does our side hold of it, and how is it written so a player can walk through it and
  back on the merged overlay? Details: [docs/slice/redrocket-door.md](../slice/redrocket-door.md).
- Method: new `dotnet/SliceDoor` (read-only verbs `fo4` on Fallout4.esm, `sf-door` on Starfield.esm, `port` on the
  pinned FO4Port.esm; `build` / `check` for the link plugin); the two marker NIFs read from the FO4 and Starfield mesh
  archives (`src/fo4sf/ba2.py`, `nif.py`); GMSTs with `SfInspect form`; exp2d's `skipped.json` / `objects.json`;
  `scripts/slice/make_redrocket_door.py` (ground, floor and walk against exp2d's BTD and converted collision and the
  build's converted interior collision); a raw group walk comparing the override records with their masters.
- Evidence: Fallout4.esm `05E844` (RedRocket01, persistent) <-> `08EB65` (Commonwealth persistent cell, FO4 cell -18,
  18), both base `01ED77` AutoloadDoor ("Auto Door", Automatic, `AutoLoadMarker01.nif`, no script), XTELs naming each
  other, flags 0; converted: exterior door (-994.948, 1109.490, 98.684) m, 38.2 m south of exp2d's arrival, in the
  hole of `CaveEntrGround01_Grass` (floor 97.73); arrival outside (-995.530, 1104.143, 99.771) over terrain 99.734;
  interior door (-1.659, 2.416, 0), arrival inside (0.049, -6.622, -0.006). The pinned build's `FO4Port_RedRocket01`
  (`002338`) has 0 persistent references and no XTEL / DOOR reference; exp2d skipped `08EB65` (`editor_marker`).
  Starfield `AutoloadDoor_Cave` (24F9CE): "Auto Door", Automatic, `Meshes\autoloadmarker01.nif`, script
  `ENV_NotSealedLocationDoorScript`; 92 references, the 45 in worldspaces all in overlay worldspaces' persistent
  cells (all 345 worldspace XTEL references are in the persistent cell); its marker's bounds (half 0.9144, 0.1143,
  1.3716 m, i.e. 3 ft, 4.5 in, 4.5 ft) are the FO4 marker's (64, 8, 96 units) / 70 to within 0.013 % (corrected after
  QA: first written "exactly"). GMST `fAutoDoorActivateDistance` 3,
  `fAutoDoorDisplayDistance` 12. `FO4SliceRedRocket.esm` (1,123 B): WRLD and persistent-cell overrides byte-identical
  to FO4TerrainExp2.esm's records, the RedRocket01 CELL override byte-identical to FO4Port.esm's, doors 0x800 / 0x801
  persistent with XTELs both ways; Mutagen read-back 28 of 28, Python check 25 of 25 (27 of 27 after the fix pass;
  two labels claimed more than the code checks: the interior door's origin stands 0.27 m inside a column's rock base,
  allowed down to -0.3 m, and the interior XTEL arrival z -0.006 is 0.25 m below a rock mound's top, not over it, as in
  Fallout 4; the interior walk's capsule first touches a column 2.26 m from the door's origin, so walking out needs
  the 3 m range measured to the origin: supported, not shown). Plugins.txt of the last exp2d
  run: `*FO4TerrainExp2.esm`, `*FO4TerrainExp2_Mars.esm`, `*FO4Port.esm` (the deploy re-appends FO4Port.esm after the
  experiment on every launch).
- Status: the Fallout 4 link, our missing ends and the plugin's records **verified** (offline); vanilla's layout for
  automatic cave doors in overlays **verified** (data), that it works for ours **supported hypothesis**; whether the
  persistent door stands at the merged position and whether the XTEL arrival into the overlay gets the merge offset
  **unresolved** (the runner's new `door_trip` test tells: UNMERGED / REMERGED); a master loading after its plugin
  in Starfield **unresolved** and avoided (cycle.ps1 now runs `exp_install.py order`); `player.GetInCell` from the
  console **supported** (GetInCell is in Starfield.exe beside "Is the reference in the specified cell?", like GetIsID,
  whose console reply is verified). Staged `C:\Modding\staging\slice_redrocket_door`; queue
  `C:\Modding\testqueue\slice_redrocket_door` planned (needs `door_trip`, `plugin_order`), not run. After QA (fix
  pass, decision of the same day): staged `..._b`, queue `C:\Modding\testqueue\slice_redrocket_door_b` planned at
  95552f8 (needs `door_check`, `door_trip`, `plugin_order`), not run; the first staging and queue are superseded.

## 2026-10-12 Claude: where the shutter door's second panel is lost (multi-part FO4 doors)
- Question: FortHagen01 `0BD6A1` (`BldWoodPDoorShutter01`) shows OPEN, flips to CLOSE, but only one louvered panel
  swings (supervised_1011 tests 0004/0005, `r4_pre.png` / `r4_open.png`). The FO4 source animates two nodes; where is the
  second panel lost, and how many doors share the defect?
- Method (offline, local scripts; no game data in the repo): `door_motion.inspect` / `door_rig.plan` on the FO4 NIF;
  the converted NIF, manifest entry and FO4Port.esm of the pinned build `integ_1011` read back; vanilla Starfield doors
  from `Starfield - Meshes01.ba2` / `Starfield - Animations.ba2` (rig + `.af` read back with the external CALUMI library,
  `LoadAnimationSceneFromSFBGSFormatAndSaveToJsonC`) and their DOOR records from Starfield.esm; Fallout4.esm DOOR
  records (MODL) and the 16 pinned cell exports scanned with `door_motion.inspect`.
- Evidence, source: `Open` and `Close` each drive two nodes, `Left` (pivot 17.87, -24, 123.89 units, -107 degrees about z)
  and `Right` (pivot 17.87, +24, 123.89, +114 degrees), 1.0 / 0.97 s; each node holds one shape and its own
  `bhkNPCollisionObject` (body 0 / 1 of one compressed-mesh physics system).
- Evidence, converted (`integ_1011`): the manifest's door entry names the Akila template rig and animations; the NIF is
  root > `AK_Door_Anim_02_Root` > `Hinge01_Point` > `mesh001` (keyframed box, layer 2) > `Left:30`, and root > `Frame` >
  `Right:30` with no bone and no body. The template's own clip (Akila `open.af` read back) has **one track** of its 6
  bones: `Hinge01_Point`, 16 rotation keys to -90 degrees, no translation. So the Right panel has 0 bones, 0 tracks and
  0 bodies; nothing could move it.
- Cause in code: `nif.door_hinge` reads only the first controlled block of `Open` (offset 12 + 9), and
  `convert_static.convert_door` moves only that node's descendants; every other shape lands under the static `Frame`.
  The pipeline gate (`pipeline.Converter.convert_nif`) checks `door_hinge` alone and never consulted
  `door_motion.inspect`, which already reports `requires_additional_motion_support: true` for this model.
- Evidence, vanilla double door `IndIntRmSmWallMid_DoorA01` (`2BF4DA`): the same graph as the Akila door
  (`SimpleOpenClose01.agx`) but its own rig (7 bones) and clips: `Open` has one track per leaf (`Hinge01_Point` -93,
  `Hinge02_Point` +93 degrees, 48 rotation and 39 translation keys, a 0.149 m outward slide, frames 0-60); the NIF holds
  one physics system with 3 bodies: 0 on the root (frame), 1 on `Door02_Mesh`, 2 on `Door01_Mesh`. The graph is not
  the limit; a door moves as many parts as its own rig and clips have tracks.
- Evidence, clip convention (126 vanilla door rigs, first clip each): no clip has a track for every bone (tracks for
  animated bones only); all 391 translation tracks of bones with a nonzero bind start at 0 and all 83 rotation tracks
  of bones with a rotated bind start at identity, none at the bind: **clip keys are offsets from the bind**. CALUMI
  stores the values as given (no bind arithmetic in `SFBGS_AnimationScene.cpp`), and the independent `.af` reader of
  PR #53 (`claude/af-channel-layout`, 2026-10-11 entry there, 9 door families) found the same. `native_door.prepare`
  wrote absolute local keys for every bone, which would apply each bind twice; it had never run in game.
- Side finding: both FortHagen01 shutters (`0BD6A1`, `0BD69F`) are window shutters. Their walls
  (`BldWoodPSmWallWindowHole01`, render triangles within 12 units of the door plane projected onto it) are solid from
  the floor to 1.03 m above the reference; the opening is the panels' own span, 1.08-2.46 m high and about 0.65 m wide.
  The walk test cannot pass with both panels open. Side 1 stopped at x 12.16, beside a fallen static
  `FederalistChair01` (origin x 12.09, y 58.52, z 7.80; probably what stopped it), side -1 0.37 m before the plane,
  about one capsule radius from the wall below the sill.
- Blast radius, 16-cell build: 59 placed door models, 36 animate more than one node; 10 rigged models (38 references,
  76 batch_full door tests) have geometry outside the first node and lose it: `BldWoodPDbDoor01` (second leaf + knob),
  `BldWoodPDoorShutter01`, `HitDoorSm01` / `HitDoorLg01` (3 of 4 sliding panels frozen; the 4th swings on the Akila
  hinge instead of sliding), `IndMetalDbDoor01`, `UtilMetalDbDoor01`, `PaintedWoodDoorDouble01` (Parsons `06CF29`, the
  0.30 m block in the journal), `SwitchDoorExSmLatch01/02` (latches), `FancyBureauDoor01`. Fallout4.esm: 369 DOOR
  records, 227 models; 106 models (175 records) animate more than one node, 80 (139 records) have geometry outside the
  first node: 33 models (48 records) take the rig path, 17 are load doors (static by design), 18 not hinged (passable),
  12 not door-named (static).
- Fix (branch `claude/door-two-panels`): rigged doors with parts outside the first node
  (`convert_static.frozen_door_parts`) get their own rig and clips when `convert_batch.py --door-anim-dll` names the
  CALUMI library: `convert_static.convert_multipart_door` makes one rig bone per FO4 node (placed: root transform left
  out), one clip track per animated node keyed from the bind (`native_door.prepare`; animated bones get identity binds,
  `door_rig.animated_identity_binds`), one keyframed box per moving bone, the rig and `Open`/`Close` `.af` + `.afx` under
  `meshes/<model>/characterassets` and `/animations`, and a DOOR entry with origin offset 0 whose BNAM / CNAM point there.
  Without the library the template door stays and the manifest lists `door_frozen_parts`.
- Offline checks (re-conversion of every placed door model into `C:\Modding\staging\door_two_panels`, 57 models, 17 s):
  47 models byte-identical to `integ_1011` (NIF and manifest entry), the 10 above changed. `scripts/oracles/door_panels.py`
  with CALUMI read-back: before 23 of 40 parts move (17 frozen), after 40 of 40 have an Open and a Close track and a
  moving body; `door_bodies.py` 0 errors (moving bodies per door 1 -> 2 or 4). Shutter: rig 3 bones, `Open.af` 2 tracks
  (`Left` -107, `Right` +114 degrees, 31 rotation keys, no translation), `Close.af` 2 tracks (30 keys), bodies on `Left`
  and `Right`. Plugin overlay (`C:\Modding\staging\door_two_panels_esm`, pinned manifest with the 10 items swapped):
  54,271 records, 48 changed: 10 DOOR (BNAM, CNAM, OBND) and their 38 REFR (position only; shutter `00BE6A` now at the
  FO4 position 12.8, 58.514, 7.314); FormIDs unchanged.
- Status: where the panel is lost **verified** (offline: code path, converted NIF, manifest, template clip read-back;
  symptom from the in-game screenshots). Vanilla clips store offsets from the bind: **verified** offline (two readers);
  that the engine applies ours that way: **supported hypothesis** (no clip of ours has played yet; the composition order
  with a rotated bind stays open, which identity binds on animated bones make moot). "Our rig + clips + per-leaf
  keyframed boxes open both panels in game" **unresolved** (in-game test plan: docs/spikes/WP-doors-research.md,
  "Multi-part doors"). Shutter walk test impossible **verified** for `0BD6A1` (wall geometry), **supported** for
  `0BD69F` (same wall pieces).

## 2026-10-12 Claude: why the NPC control N0 could not tell a commanded walk from wandering
- Question: N0 (`npc_nav_n0`, QASmoke) passed `PathToRef` twice and failed its no-command baseline; is that a walk, a
  navmesh problem, or wander? What pair and rule would separate them (N0b)?
- Method: N0's obs.json reads and console OCR (read only); `scripts/actors/navmesh_points.py analyze` on Starfield.esm:
  QASmoke's NAVM parsed with `src/fo4sf/navmesh.py`, triangle graph and components, every reference's OBND (Starfield:
  6 f32, metres) placed and classified, free space at 0.1 m, corridor path (funnel), free path, segment clearance and
  "drift progress" (how much closer to B an actor gets by going where actors went on their own); NPC_ AIDT bytes.
  Details: [docs/actors/npc-navigation.md](../actors/npc-navigation.md) section 5.
- Evidence: every N0 actor, commanded or not, stayed in x -11.4..0.0, y -6.1..2.0 and never came closer than 10.8 m to B
  (5, 10); base 5.4 m, PathToRef 6.8 / 9.0 m, `cf "Actor.PathToReference"` replied "No script named Actor is attached to
  the object", SetPlayerTeammate + EvaluatePackage stood still 30 s. NAVM 002BE3AA: 12 vertices, 14 triangles, no
  links, one component of 554.7 m^2; the old straight path = navmesh path = free path, 3.8 m clear of every wall and
  pillar; going to the arrival marker (COCMarkerHeading 002BE3AF, -3.4, -1.1) gains 5.2 m, to the navmesh centre 8.5 m.
  No sandbox furniture or idle marker on the navmesh. AIDT: EncCitizen01Template Unaggressive / Cowardly, EncSpacer01Template
  Unaggressive / Brave.
- Status: the navmesh did not block N0 (**verified**); the `cf` method as written cannot reach PathToReference
  (**verified**); "N0's PathToRef PASSes were a walk" **refuted** (wander pattern, judged by a 5 m rule); what moved
  the citizens (their package towards the middle of the room, the player, or both) **unresolved** (fix pass: N0_base
  ended 4.3 m from the marker and 7.4 m from the centre, and three citizens walked up to the player before the
  command: N0_cf 4.4 m, N1c_ptr_player 9.5 m, N1c_follow_player 3.4 m; the largest move from t0 on record is 14.1 m,
  N1c_cross_ptr); whether PathToRef or StartCombat walks an actor to the player (**unresolved**, N0b: A (5.5, -4.5, 0)
  -> B (-12, 12, 0), 24 m, the walk judged from t0, PASS = within 3 m after 18 m or 18 m closer, staged
  `C:\Modding\staging\npc_nav_n0b`, queue `npc_nav_n0b`). Also found: QASmoke's 16 ceiling panels (rotation 0, 90,
  270 degrees) lie flat only when rotated Z first; `fo4sf.exterior.ref_matrix` (X, Y, Z) stands them on edge
  (**unresolved** for references that combine Y and Z rotations; no effect on this analysis).
## 2026-10-11 Claude: `XRGD` ragdoll pose decoded (bone world transforms from per-placement data)
- Question: which body each 28-byte `XRGD` entry belongs to, what its position / rotation are relative to, and the
  Euler convention (follow-up of "why the converted skeleton spawns standing", below).
- Method: all 8,919 `XRGD` subrecords of Fallout4.esm (75,292 entries; local script: linear record walk, zlib records)
  against the node trees, `hknpPhysicsSystemData` bodies and constraints of the placed models (`nif`, `hkpackfile`;
  `SkeletonClothed01.nif`, `SkeletonBareBody01.nif`, the destructible saw horses and barriers). Acceptance on the 62
  Vault 114 placements (cell `0428E4`) with ragdoll data, the floor taken from the cell's static collision
  (`routes.walkable_triangles`). Implementation: `src/fo4sf/ragdoll_pose.py` (`pose_bones`), 10 synthetic tests.
- Evidence (order): entry k belongs to physics body k (the `body` field of the `bhkNPCollisionObject` that attaches it
  to a node, i.e. the system's body-cinfo order); the clothed skeleton's 17 collision objects are bodies 0..16 in block
  order (TorsoLower, LeftUpperLeg, LeftLowerLeg, LeftFoot, RightUpperLeg, ..., LeftHand). Entry count = body count
  for 57 of the 62 placements; the other 5 carry entries for a different model (`Sawhorse01`: 6 entries, 1 body;
  `TrashCanMetal` 2/1; two `MetalBarrel01Fire*_Static` 3/1; `TrapGrenadeBouquet` 40/27): stale data, rejected.
  The first 4 bytes of an entry are uninitialised memory, not a bone id: ESM-wide the u8 is 0 in 71% of the entries
  and the 3 bytes after it are non-zero in 45%, often ASCII fragments of file paths (`617465 69616c 5c4d61 576561`
  = "ate", "ial", "\Ma", "Wea"); only 314 of 8,919 records happen to count 0..n-1.
- Evidence (frame): an entry replaces its body's node **local** transform (relative to the parent node; to the
  reference for a node under the root). For the 69 Vault 114 joints whose parent node is also a body, |entry position|
  equals the NIF bone length (relative error mean 0.36%, median 0.11%, max 3.7%: joint slack of a settled ragdoll)
  and the entry sits 0.12 units (mean; max 0.89) from the NIF local translation. 8 bodies (gear-room gate, oxygen
  tank, skeletons) with a non-trivial bind rotation kept their NIF translation to 0.01 units; 6 of them also keep the
  NIF rotation exactly (0.0001 rad), the other 2 turned in place (0.72 rad). The skeleton's constraints use the same frame: pivot A is
  the child node origin, pivot B the child's NIF local translation in the parent (c8: B (-0.100, 0.027, -0.191) m =
  LeftUpperLegBone01 (-6.99, 1.87, -13.39) units), B's axes are the child's local rotation columns (z, y, -x). Shape
  vertices are in the node frame (a leg hull spans z -0.8..30.7 along its node with the child joint at 32.9; the torso
  hull lies at z -18.9..-0.6 under the pelvis node); the body cinfo position is the node origin for torso / skull
  bodies and the hull centre for limbs, and is not needed for posing.
- Evidence (Euler): R = Rx(-x) Ry(-y) Rz(-z), the NIF's own NiMatrix3 convention. Of the 8 unmoved bodies above
  (selected by position only), 6 match their NIF rotation within 0.002 rad under this order; 4 under
  Ry(-y)Rx(-x)Rz(-z), 2 under Rz(-z)Ry(-y)Rx(-x) and Rz(-z)Rx(-x)Ry(-y), 0 under Rz(z)Ry(y)Rx(x) and Rx(x)Ry(y)Rz(z)
  (mean errors 0.11 / 0.15 / 1.46 / 1.46 / 2.15 / 2.99 rad). The 29
  posed limited hinges (knees, elbows, saw-horse legs): the hinge axis of the child frame mapped by the posed local
  rotation meets the parent's axis within 0.08 deg median (mean 0.60, max 5.8); the three alternatives 1.4-9.8 deg
  median, 13-77 max.
- Acceptance (57 posed placements, game units): the lowest posed collision point is within +/-3 of the surface under
  it for **53 of 57** (bind pose: 41), and within +/-3 of the placement's floor for 44 (median -0.01; bind 35).
  Skeletons: `05C942` (SkeletonClothed, placed z -1107.4, floor -1120) posed bones span z -1115.5..-1102.7 (spread
  12.8, pelvis->skull -12 deg), hull from 1.1 below to 21.7 above the floor, where the bind pose stands 129 tall;
  `05C94F` spread 10.9, hull -0.75..21.5; `1B4E17` -1.6..34.1; `1B4F92` rests 150 above the cave floor on the stone
  coffin beside it (clearance -0.36). The 4 of 57 off their surface are saw horses / a barrier posed partly through
  FO4 geometry (`171007`: 4.9 under the floor) or with no surface found under the lowest point.
- Side finding (REFR `DATA` rotation order): placing the cell's 164 tilted placements (|rx| or |ry| > 0.05 rad: 149
  loose items, 15 ragdolls) with each of the 12 Euler orders, Rx(-x)Ry(-y)Rz(-z) rests the most of them on their
  support (gap within +/-3: 129 of 164, median |gap| 0.56) against 100 (median 1.60) for the project's
  `routes.ref_matrix` order Rz(-z)Ry(-y)Rx(-x). **Supported hypothesis**; `routes.py` is not changed here (the route
  runs are its in-game check). Known unknown #7.
- Status: entry order = body index, entry = node local transform in the parent frame, Euler Rx(-x)Ry(-y)Rz(-z):
  **verified** offline (bind-exact entries and hinge axes on real data, floor test on 57 placements). First 4 bytes
  are garbage: **verified** (ESM-wide). Whether Starfield shows the posed skeletons lying as FO4 does: **unresolved**
  until the pose is baked into the converted mesh and body (needs the skin weights of PR #45 / #46) and seen in game.
  Both skeleton NIFs have an identity root; `pose_bones` composes a root transform like any node: **unresolved** for
  models with a non-identity root.

## 2026-10-10 Claude: how Starfield makes a body movable
- Question: what must a converted body and record carry so Starfield simulates it (FO4 loose items, known unknown #6)?
- Method: field-level dumps with `hktagfile` (field names from the files' own type tables) of vanilla Static, MiscItem,
  MoveableStatic and animated-door bodies; `SfInspect models` / `mstt` for which records use which meshes; scans of
  ~10,400 vanilla item NIFs and 400 models per record type (local scripts, not in the repo).
- Evidence (body cinfo): `motionType` static 0 / keyframed 1 / **dynamic 2**; `flags` 0 / 0x4 / **0x8a**;
  `collisionFilterInfo` = collision layer (1 STATIC, 2 ANIMSTATIC, 4 CLUTTER, 26); dynamic bodies have `mass` (kg),
  `motionPropertiesId` 0 into the system's `motionProperties` array (Bethesda defaults: gravity 1, max speed 100 / 200,
  damping 0.1 / 0.05) and an `hknpRefMassDistribution`. Static box blob offsets: 232 flags, 240 layer, 264 motionType
  (an older comment called 240 the motion type: **corrected**).
- Evidence (mass distribution, 30 of 30 vanilla box items): centre of mass = box centre; volume = the box grown by its
  convex radius (ratio 1.000); inertia = per-kg inertia of that grown box x **1.5** (ratios 1.499-1.500); axes identity.
- Evidence (records / NIF): layer CLUTTER alone does not move anything (the ingot `Ingot_PreciousMetal_01` is a Static);
  movable set dressing is **MoveableStatic** (`DATA = 4` on every vanilla one checked) or MiscItem. 145 of 150 MiscItem
  NIFs have **BSXFlags 0x42** (statics mostly 0x2); the collision object is on the root node. MiscItem physics layouts
  add exactly one class over the static ones: `hknpMassDistribution`.
- FO4 side: motion cinfo stride **112** bytes (skeleton: ids 0..16, inverse masses 0.1 / 0.2); pencil 0.5 kg, tin can
  5 kg, clipboard 4 kg.
- Status: field meanings **verified** (named by the type tables, consistent across samples); inertia factor 1.5
  **verified** (30 items); "a dynamic body on a MoveableStatic is pushable in game" **supported hypothesis** until the
  in-game test. Vanilla dynamic shapes also carry `hknpShapeMassProperties`; ours don't: a converted can, a compound cone and the rigid skeleton moved when pushed in game (journal 2026-10-10), so the body's mass distribution is enough: **supported hypothesis**. Principal axes of non-box hulls come out in ascending-moment order where vanilla keeps the near-identity order; the tensors agree (QA on PR #41, 12 items, |dot| >= 0.988): a convention difference, not an error.

## 2026-10-10 Claude: why the converted skeleton spawns standing (FO4 `XRGD` ragdoll pose)
- Question: in game the rigid skeleton (Vault 114 `05C942`) ended about 1 m sideways and 0.88 m lower than placed. Why?
- Method: render bounds vs collision bounds of the converted NIF; `XRGD` of the Vault 114 skeleton REFRs read straight
  from Fallout4.esm (local script: linear record walk, zlib records, `recon.iter_subrecords`).
- Evidence: the converted render mesh is the skinned mesh in its bind pose, a standing figure (z 0.01-1.88 m, 0.44 m
  deep); the collision built from the NIF's bone nodes does not match it (y -0.54..0.92). FO4 lays placed skeletons down
  with per-reference ragdoll data: `05C942` (SkeletonClothed01, 17 bodies) has `XRGD` of 476 bytes = 17 x 28; `05C94F`
  (SkeletonBareBody01) 504 = 18 x 28. Entry: u8 0 (+3 bytes that look like garbage), 3 floats position, 3 floats
  rotation; the first entry has position 0 and a rotation, the others bone-length offsets (13-33 game units) and
  rotations in radians. Loose bone props (BonesSkull, BonesRibCage) have no `XRGD`. Mutagen's Fallout 4 library reads
  it (`PlacedObject.RagdollData`, type `RagdollData`).
- Status: "one 28-byte entry per ragdoll body, in body order, local position (game units) + rotation (radians)":
  **supported hypothesis** (2 references; parent order and Euler convention unverified). Consequence: phase A spawns
  skeletons in bind pose (standing) and they topple; FO4 shows them lying. Fix: export `XRGD` (Fo4Export, Codex's file)
  and bake each placement's pose into its mesh and rigid body (needs skin weights: phase B work).

## 2026-10-10 Claude: Starfield dynamic compound bodies
- Question: how does Starfield store one movable body made of several convex pieces (FO4 boxes, cones, tools)?
- Method: field dumps (`hktagfile`) of vanilla single-body dynamic MiscItem / MoveableStatic NIFs; checks against the
  children decoded through the instance pointers (local scripts).
- Evidence: single-body dynamic shapes in vanilla: convex 540, **compound 273**, box 109, LOD 19, cylinder 17, sphere 2.
  A dynamic compound is one `hknpCompoundShape` (type 11, dispatch 3): instances (identity transforms in every sample;
  vertices are already in compound space), `numShapeKeyBits` = bit length of the instance count (2->2, 3->2, 4->3,
  8->4, 19->5; 40 of 40), `estimatedNumShapeKeys` = `numAllocated` = count, `aabb` = union of child boxes (child
  vertices +/- child convex radius; 25 of 25 exact), a SIMD tree whose root is always an inner node and whose leaf boxes
  are the child boxes (exact), `boundingRadius` between 0.78 and 1.0 of the aabb half-diagonal.
- Mass distribution: a compound's is a **solid box equal to its aabb** (centre, volume, inertia per kg x 1.5, identity
  axes; 40 of 40 exact). A single convex body's is the grown hull (40 vanilla convex items: volume 0.98-1.0 for most,
  worst 0.82; centre within 7 mm), not its aabb.
- Status: compound layout and both mass rules **verified** on vanilla files; converted FO4 compounds pass the same checks
  offline. In-game behaviour: **supported hypothesis** until tested.
## 2026-10-11 Claude: load-door teleports checked against the re-exported 16 cells (follow-up to 2026-10-10)
- Question: the 2026-10-10 entry left open which load-door pairs exist among the pinned cells, because 12 of the 15 cell
  exports predated the exporter's persistent-reference export and held no XTEL.
- Method: the 15 pinned cells plus FortHagen02 re-exported with the current Fo4Export (schema 2; owner's local copy
  C:\Modding\staging\exports_1011, read-only, not in Git); `teleport_destination` entries counted per cell (Python over
  the JSON); then `dotnet/PluginSpike` (branch claude/load-door-teleport) offline on the staging manifest (4,014 items,
  10 load doors) + those 16 exports into a scratch folder seeded with the staging formids.json; the written FO4Port.esm
  read back with `PluginSpike teleports`. No deploy, no game.
- Evidence: 34 XTELs in the 16 exports (1 to 4 per cell). Exactly 2 have their destination reference in the set:
  FortHagen01 `0CD469` <-> FortHagen02 `0CD46A` (UtilMetalDbDoorLoad01, flags 0). Of the other 32, 28 lead to references
  outside the set (4 of them FO4 elevator doors with transition_interior set) and 4 sit on marker-based doors the
  converter never places (RedRocket01 `05E844` AutoloadDoor `autoloadmarker01.nif`; Vault111Cryo `248AAD` and `148B69`
  InvisibleLoad01HiddenMinUse `invisibledoor01.nif`, `01F180` AutoloadDoorNoText). XTEL flags: 32 x 0, 2 x NoLoadScreen.
  Writer output: "2 references linked (1 mutual pairs, 0 one-way), 28 destinations not in this build, 4 sources not
  placed, 0 issues"; `teleports.json` now carries `SourceNotPlaced` and `UnplacedSources` (new, so all 34 are accounted
  for: 2 + 28 + 4; PluginSpike.Tests asserts it). Read-back: FO4Port_FortHagen01 `00C7A7` <-> FO4Port_FortHagen02 `00DA69`,
  base FO4Port_utilmetaldbdoorload01, both persistent, record flags 0x400, back=True, arrival (-54.52, 19.27, -7.31) m
  and (-10.05, 43.95, -10.97) m, rotZ +1.571 / -1.571, transition Null. Stable FormIDs against the staging map: 0 changed,
  0 removed, 3,317 new (3,312 REFR from the now-exported persistent references and FortHagen02, 4 `DOOR:`, 1 `CELL:`).
- Status: "the next build of these 16 cells has exactly one teleporting pair (FortHagen01 <-> FortHagen02); every other
  load door stays shut and solid": **verified** offline; closes the 2026-10-10 unresolved item. That the pair teleports
  in game: **unresolved** (not deployed).

## 2026-10-10 Claude: how Starfield load doors teleport (XTEL), and what the port now writes
- Question: how is a vanilla Starfield load door set up (base record, flags, destination, persistence), so an FO4 load
  door between two converted cells can teleport instead of standing shut (docs/JOURNAL.md 2026-10-08, "load doors swung
  open onto the void")?
- Method: new SfInspect verbs, read-only on Starfield.esm: `teleports` (every placed object with a TeleportDestination in
  interior and worldspace cells, its base record, its destination; 17 s for 3,291,860 placed objects) and
  `doorrec <EditorID>` (all properties of a DOOR record).
- Evidence: 964 placed objects carry an XTEL. All 964: the base is a DOOR; the reference is in its cell's persistent group
  with record flag 0x400; the destination reference exists (619 sources in interiors, 244 destinations in the same cell)
  and its own XTEL links back. TransitionInterior: 0 of 964. XTEL flags: 0 for 960, NoLoadScreen (2) for 4,
  RelativePosition never. Arrival point to the destination door's position: median 1.00 m, p10 0.00, p90 5.67 m, so it
  is a separate absolute position in the destination cell. DOOR bases: 506 with an AnimationGraphComponent (visible load
  doors, e.g. `IndIntRmSmWallMid_DoorA01_Load` 2AC325: graph SimpleOpenClose06_Load.agx, Flags 0, SoundLevel Normal,
  FacingAxisOverride BasedOnBounds, Name "Door"), 458 without any component (`LoadElevator_InvisibleDoor` 21F2A7: 322
  references, Flags Hidden, MarkerDummyA.nif; `AutoloadDoor_Cave` 24F9CE: 89, Flags Automatic, scripted).
- Status: "Starfield load door = persistent DOOR reference (flag 0x400) + XTEL (destination door reference, absolute
  arrival position/rotation, flags), both ends linking each other, no TransitionInterior": **verified** (964 of 964).
  "A DOOR without an animation graph teleports": **verified** for the vanilla graph-less bases (458 references), which are
  hidden or automatic; "a visible graph-less DOOR teleports on the player's activation" (what the port writes):
  **supported hypothesis** (same engine lineage as FO4, where XTEL doors teleport whatever their animation); in-game
  check pending.
- Implemented (dotnet/PluginSpike, new TeleportLinks.cs): manifest `load_door` items become graph-less DOOR records
  (Flags 0, SoundLevel Normal, FacingAxisOverride BasedOnBounds, OBND from the model bounds `pipeline.py` now writes
  into the manifest). After all cells are placed, every exported XTEL whose destination reference is placed in the same
  build (any cell JSON given on the command line) is written on the reference (position / 70, rotation and flags as
  exported, TransitionInterior never) and both ends move to the persistent group with flag 0x400. Doors whose other end
  is not in the build get no XTEL (they stay shut and solid) and are listed in `<out>/teleports.json`.
  `PluginSpike teleports <FO4Port.esm>` reads a plugin back (CreateFromBinaryOverlay) and lists its links.
- Offline check: staging manifest (4,014 items, 10 load doors) + the 15 pinned cell JSONs + a fresh export of FortHagen02
  (scratch, not staging): "2 references linked (1 mutual pairs, 0 one-way), 6 destinations not in this build, 0 issues";
  read-back: FO4Port_FortHagen01 0043B7 <-> FO4Port_FortHagen02 00D6C6 (both `FO4Port_utilmetaldbdoorload01`, persistent,
  flags 0x400, back=True), arrival (-10.05, 43.95, -10.97) m = FO4 (-703.2, 3076.6, -768) / 70. Rebuilt on the staging
  formids.json: 0 existing FormIDs changed; new keys are FortHagen02, 4 `DOOR:` ids for load doors that never had one
  (6 others reuse the DOOR: id they had before 2026-10-08) and 54 REFR keys that the origin/main writer adds as well.
  Synthetic test: dotnet/PluginSpike.Tests (pair, one-way, destination outside the build, STAT source, relative-position
  flag, idempotence, binary round trip); tests/test_load_door_policy.py covers the manifest bounds.
- Finding on the pinned build: 12 of the 15 cell JSONs predate the exporter's persistent-group export (no
  `schema_version`, 2026-10-07) and contain no persistent reference at all, so no FO4 load door with an XTEL (they are
  persistent in FO4) and nothing to link. Only FortHagen01, MuseumOfWitchcraft01 and Vault75 (schema 2, 2026-10-08) carry
  XTELs: 6, of which 5 lead to the Commonwealth worldspace (cell 018AA2) and 1 to FortHagen02. **Unresolved** until the
  cells are re-exported: which pairs among the 15 exist at all (resolved 2026-10-11, entry above: one pair). Also open: FO4 teleport "doors" that are not door-named
  (`MetalTrapdoorLadder01`, `RoofHatch01` here) stay STAT bases and would be reported as issues, not linked.
## 2026-10-10 Claude: the 7 Prydwen route falls; FO4 ignores a NIF's root-node transform
- Question: what collision lies under the 7 `FALL` routes of the pinned build's Prydwen run
  (`staging\multi_next\run_PrydwenHull01`, `route_eval`: routes 12, 13, 15, 18, 20, 28, 29)?
- Method (offline; scratch scripts, not in the repo): placed every nearby model's FO4 collision
  (`routes.collision_bodies`) and sampled it under each route's start, its walk (heading, 4.6 m/s x `walk_ms`) and its
  end read; vertical sections and top views; compared with FO4's own cell collision, the precombined physics
  `Meshes\PreCombined\0005C92E_Physics.NIF` (one compressed-mesh body, 209,035 triangles, cell space), and with the
  staged NIFs.
- **A. Routes 12, 13, 15, 18 (`PryPlatformInCornerStairs01/02`): route-planning error.** These models are railing
  frames around a stairwell. Their only 20-50 degree triangles are small bevels on the posts; the planner's
  `sloped-collision` ramp had its low and high ends 0.03-0.04 m apart under a 0.91 m rise (88 degrees), so the heading
  was meaningless. Each walk (2.3 m) left the deck (z -7.31) into the stairwell next to it and went down
  `PryCatwalkStairsEnt01`: end z -7.98 / -7.99 / -7.99 at points where FO4's own Ent01 treads are at z -8.06
  (routes 13, 15, 18). Route 12's end repeats its start y (likely OCR); its x and z fit the same walk down Ent01
  `06E066`. The converted collision did what FO4's does. Same bogus ramp on `PryPlatformWallStairs01` (route 14 STUCK,
  rise 0.02 m; routes 33, 43 not run). Every other stair ramp in the 15 cells is at most 46.4 degrees end to end
  (`V111HallStairs01`'s helper). **Verified** (offline, FO4 data).
- **B. Routes 20, 28, 29 (`PryCatwalkStairs01` 068A2A, 06E03B, 06E03D): converter bug.** Each flight continues a
  `PryCatwalkStairsEnt02` (068A29, 06E03A, 06E03E). Ent02's NIF root node is rotated 180 degrees about z and its
  `Stairs` node another 180. The converter (and routes.py) composed the root, so the converted Ent02 climbs north
  instead of south: its foot hangs over the deck opening and the next flight's foot is 1.8 m above it. The three
  starts (z -5.23, 0.8 m before the flight) were over the converted Ent02's lower steps: start reads z -6.86 / -6.90,
  then 0.3 m of walking into the flight's underside, end z -7.04. Staged `prycatwalkstairsent02.nif`: render treads
  rise towards +y (z 0.03 to 1.86) and the helper node sits at y -1.738; staged `prycatwalkstairs01.nif` rises towards
  -y with its helper at +1.73. The same turn explains routes 19, 27, 30 ("start not reached", starts fell through the
  opening to z -12.3 / -14.95).
- **Evidence that the root transform is not applied in game:** all 89 references (15 models, 6 cells) with a rotated
  root whose collision is in their cell's precombined physics match it only with the root left out: 100% of sampled
  collision vertices within 2 cm, against 0-18% with it applied. None matches the other way. 97 references are in no
  precombine; 8 door references (`HitDoorSm01/Lg01`, Cambridge, frame only) match 34-38%, again only without the root. Ent02 itself is not precombined: without
  its root it joins its flight into one straight stair from the deck (z -7.31) to the catwalk (z -3.65), and routes
  20/28/29 then start 0.33 m above its top steps. Posters with rotated roots (`PosterAbraxo`, `PosterCivil`) only hang
  upright without the root. Status: collision **verified** (FO4's precombined physics); render geometry **supported
  hypothesis** (posters, stair layout; no in-game check yet).
- Scope in the pinned build: 44 of 4,014 converted models have a rotated root (none has a root translation or scale),
  232 placements. 30 carry their collision on the root node, so the render was turned and the collision was not
  (`DinerIntCounter01`, `IndFrameCat256x256*` (Vault 114, Vault 95), `DeskLamp01`, `VltCatwalkRailStraight01`, ...).
  4 carry it on child nodes and were turned with the render (Ent02, `Jukebox01`, `HitDoorSmBroken01`,
  `GoreHumanLegR`). 2 are rigged doors (`HitDoorSm01/Lg01`, Cambridge). 8 are render-only posters.
- Fix: `nif.world_transforms(placed=True)` (and `fo4_trishapes` / `door_hinge`) leaves out the scene root's own
  transform. `convert_static` uses it for geometry, native collision nodes and door pivots; `routes.py` uses it, and
  rejects a ramp whose ends are steeper than 60 degrees. Offline reconversion of Ent02: render and collision rise
  towards -y, helper node at y +1.738, as Stairs01. Routes regenerated for all 15 cells (scratch): 510 to 501;
  9 bogus Prydwen platform-stair routes removed; 23 changed (4 Prydwen Ent02 routes now start on the deck at
  y 15.31 / 37.25 heading south; 19 Cambridge routes for `HitDoorSm01/Lg01` and `HitFloorRailStairsFront01L/R`);
  the other 478 are identical.
- Not done: no rebuild or deploy (the pinned build is unchanged), no in-game run. The door modules owned by Codex
  (`door_motion`, `door_rig`) still use the default composition.
## 2026-10-11 Claude: Fallout 4 navmesh converted onto the native Red Rocket terrain (exp2d), NAVI for plugins, N1
- Question: can FO4's NAVM records around Red Rocket become Starfield NAVM records in the overlay worldspace's 100 m
  cells (links across the new cell lines included), does a plugin need navmesh info (NAVI / NVMI) and in what form, and
  which N1 tests separate world, navigation and actor failures? Write-up:
  [docs/actors/navmesh-conversion.md](../actors/navmesh-conversion.md).
- Method: `src/fo4sf/navmesh.py` (both NVNM layouts, NVMI, cell cut with canonical point keys, grid, validator),
  `dotnet/TerrainExp2` navmesh mode (NAVM + NAVI override), `scripts/terrain/make_exp2d.py` (stage / check / npc), raw
  scans of Fallout4.esm, Starfield.esm and the official Starfield plugins (scratch scripts), Mutagen round trips;
  `tests/test_navmesh.py` (synthetic). Staged `C:\Modding\staging\terrain_exp2d`, `terrain_exp2b2_npc`,
  `npc_nav_n1a` / `n1b` / `n1c`. Not deployed, not run in game.
- Evidence:
  - **verified**: triangle field order height, u8 extra, u16 flags, u16 cover (edge-link bits agree with the edge
    values in 63,875 FO4 and 256,726 Starfield triangles, 5,970 / 1 disagreements one byte earlier): corrects PR #61's
    reading of the flags offset; edge links name the target triangle's edge and come in symmetric pairs (7,606 FO4,
    7,196 CydoniaCity); parent grid is y then x (105 + 2,708 of 105 + 2,708).
  - **verified**: the search grid rule (divisor, bounds, cell size) on 1,004 / 1,004 akilacity navmeshes; lists
    identical in 873, a superset in all.
  - **verified**: NVMI layout on all 56,631 Starfield.esm entries (traversals and a 5-byte tail of cell-border bits
    after the doors / outline); merged-to = link targets (56,502 / 56,563), location = vertex mean (56,490), border bits.
  - **verified**: every official plugin with navmesh overrides NAVI `00000FF1` with only its own entries (SFBGS003 920,
    SFBGS00D 4,126, BlueprintShips 507, SFBGS006 71 vs 56,631): the engine merges NVMI per navmesh (**supported**).
  - **verified** (offline): 105 FO4 navmeshes -> 156 NAVM, 68,132 triangles, 4,104 link pairs, every NVNM byte-identical
    to the Python reference writer, 0 structural problems, cell-line links exact, exp2c's 10,301 records unchanged;
    41,207 of 43,901 vertices within 0.5 m of the BTD or the converted collision, 2,674 of the rest equally off FO4's
    own LAND and source collision.
  - **verified**: Mutagen 0.55.0-alpha.67 needs the grid lists as one raw array, the parent coordinates swapped, an
    empty MNAM list; vanilla NAVM/NAVI form version 581.
- Status: conversion and records **verified** offline; that the engine uses them (and the merged-world offset for
  navmesh) **unresolved** until N1c runs; vertex i32 meaning **supported**; triangle extra byte, NVMI f32, cover,
  outline algorithm, traversals **unresolved**. PR #68's staged N1 requires a terrain test that read INCONCLUSIVE MOVED
  and would never run; N1a / N1b / N1c bring their own world checks.

## 2026-10-12 Claude: correction, which teleports raise "Boundary Reached" in a merged overlay
- Question: core64c's first plan (PR #76) and PR #74's commonwealth-scale.md said a single teleport more than about
  4 cells from where the player stood raised "Boundary Reached", and that core64b's 300 m hops were verified safe.
  What do the runner reports actually show?
- Method: `scripts/terrain/teleport_audit.py` (new, synthetic test `test_teleport_audit`) rebuilds every teleport of
  the eight overlay queues (core64, core64b, exp2b, exp2b2, exp2b3, exp2c, exp2d, exp3) from spec.json + obs.json,
  hops as qstep.ps1 makes them, and judges it by the read that follows; counted only from a position where the
  previous teleport landed. qstep types setpos x, then y, then z, so each setpos moves one axis.
- Evidence (**verified** counts): of 145 teleports that moved the player at most 2 cells (100 m) along each axis, 144
  landed (the other in exp2b's second attempt, where the player fell through the world at most points); of 28 that
  moved 3 or more cells, 11 relocated the player 8.2 to 11.8 km further along that axis or hung at the drop height
  (all 6 in core64: 292.6 m east, 303.5 m south, 296.2 m west and three diagonals of 3 to 4 cells), 17 landed. In
  exp3, 250.5 and 267.0 m single-axis moves within 2 cells landed and a 248.7 m move across 3 cells hung. core64b's
  hops were at most 187.4 m per axis.
- Status: "about 4 cells" and "300 m hops are safe" **refuted**; a per-setpos distance limit (230 to 292 m, which
  core64 alone fits) **refuted** by exp3; "at most 2 cells per axis lands, 3 or more is a risk" **supported
  hypothesis**; the mechanism (a 5 x 5 loaded grid?) **unresolved**. core64c's plan now keeps every teleport within
  200 m per axis (docs/terrain/core64c.md "Teleport rule"); PR #74's commonwealth-scale.md still states the old claim.

## 2026-10-12 Claude: core64c, every Fallout4.esm exterior object of the 64-cell core on core64, staged
- Question: can ALL Fallout 4 exterior objects of the core (which covers the whole playable Commonwealth) go onto the
  core64 terrain as one experiment, how large is that, and what has to give? Write-up:
  [docs/terrain/core64c.md](../terrain/core64c.md).
- Method: `Fo4Land export-exterior` in 11 bands, `scripts/terrain/make_core64c.py` (select, measure, stage, check),
  `convert_batch.py --prefix fo4core --max-texture` (new: top mip levels dropped per texture kind, full and written
  size logged), `dotnet/TerrainOverlays` objects mode (new), synthetic tests `test_make_core64c`, `test_texture_cap`.
  Staged `C:\Modding\staging\terrain_core64c`. Not deployed, not run in game.
- Evidence:
  - **verified**: 706,579 FO4 references in the covered cells (701,754 placed objects + 4,825 actors / hazards /
    traps); 649,596 convert-eligible references of 11,887 models; 56,983 skipped with a reason (decals 13,118, lights
    6,275, idle markers 5,828, power lines 4,982, editor markers 13,542, actors 3,685, trigger volumes 2,414, effects
    2,087, water planes 721, ...); 11,769 models convert and 118 do not (exactly the dry run's prediction), so
    **648,358 references** are placed (1,238 more skipped as `conversion_failed`). Conversion 2,499 s, one process.
  - **verified** (directory listing): every large vanilla Starfield archive is 4,294,061,043 to 4,294,946,755 bytes,
    never 2^32 or more. **unresolved**: whether the engine reads past 4 GiB, and whether numbered per-plugin archives
    (`.* - Main[0-9]*\.ba2` in Starfield.exe) load.
  - **verified** (dry run of the converter's material logic over the FO4 texture archives' DX10 records): 2,632
    materials, 8,635 textures, 7.30 GiB at full resolution; the converted set at full resolution with meshes,
    geometries, terrain and materials is 8.47 GiB (an earlier "about 8.3 GiB" left out the terrain and materials).
    **supported** (estimate): a
    split into the 15 occupied 1.6 km regions needs 28.8 GiB (shared materials repeat) and the four central regions
    5.6 to 6.2 GiB each, so a region split does not fit 4 GiB archives either.
  - **verified**: with per-kind caps (color 1024, normal 512, rough 256, opacity 512 px; top mip levels dropped) the
    converted textures are 2.42 GiB (7.26 GiB before the caps, logged per texture); the Data tree is 3.63 GiB and
    Archive2 with the installer's arguments builds one stored archive of 3,899,305,077 bytes (51,821 entries, 0 packed).
  - **verified**: `FO4TerrainCore.esm` 46,114,630 B = core64's 4,102 records, all unchanged, + 11,699 STAT + 70 DOOR
    + 648,358 REFR in 1,708 cells (up to 6,049 per cell); BTD, mask and Mars plugin byte-identical to core64; 0 missing
    model, geometry, material or texture files.
  - **verified**: BTD minus FO4 LAND under all 648,358 origins: median 2.78 mm, p99 86.7 mm, max 3.19 m; 97.3 % within
    5 cm, 673 above 0.25 m. **supported**: the tail is steep FO4 relief (median 3.54 m per terrain quad there, 0.46 m
    overall: quarry walls, cliffs, terrain under building floors) rounded off by the 0.78 m BTD grid.
  - **verified**: plan of 3 entries (terrain probes clear of objects; the Sanctuary player house, Red Rocket shop and
    Concord museum roofs, 4.72 to 14.10 m above the terrain under the landing disc, each dropped on twice;
    informational probes, screenshot spots only with `stage --views`), every teleport at most 2 cells per axis with
    19 terrain waypoints and no runner hops (fix pass, entry below); the judged roofs equal FO4's own collision within
    0.045 mm (the museum's compound bodies through Codex's `fo4_compounds.decode_body`); 252 of 252 offline checks.
- Status: offline **verified**; everything in game **unresolved** (load and streaming of ~1,700 populated cells,
  frame time, whether objects merge with the terrain's offset everywhere, night-time screenshots).

## 2026-10-11 Claude: core64, one 64-cell Commonwealth overlay staged
- Question: does ONE large overlay (option a) load its real heights everywhere around a single arrival? exp2b (one
  29-cell overlay, stored BTD) read FO4 heights within 0.08 m and FO4 objects within 0.02 m in game; exp3 (four
  14-cell overlays) read real terrain only in the arrival tile, probes 500-700 m away in the neighbours hung at the
  drop height even after the runner's two 8 s re-reads, so separate overlays cannot be walked between.
- Method: `make_cw_overlays.py build --plan rays` (new: one overlay, `--world`, `--coc`, `--btd-copy-meshes`, ray
  entries), `dotnet/TerrainOverlays`, `make_cw_overlays.py check` (new: ray entry contract, COC marker, archive inputs,
  CNAM uniqueness), an Archive2 dry run into the scratch folder, 8 new synthetic tests (43 in test_overlay_grid).
- Evidence (**verified** offline, `C:\Modding\staging\terrain_core64`): FO4Core_Commonwealth, 64 x 64 cells = CW
  cells -32..31 (6.4 km, local frame = FO4 / 70), BTD 103,172,485 B, range -120 / 503 m (step 9.506 mm), Absolute
  (INAM 1, HNAM 0), mask ring 255 on all four edges (6400 px BC4, 20,480,128 B); FO4TerrainCore.esm 183,160 B (4,096
  cells), FO4TerrainCore_Mars.esm 6,512 B (MarsPlanetData CNAM 10 vanilla + 1 at exp2b's lat/long 0.3, -1.2, unique,
  nearest other entry 33,561 cells away). Check 208 of 208; 37 plan points decode within one step (worst 9.29 mm).
  Archive2 dry run: 3 entries, all stored (packed 0), byte-identical to the staged files, 226,825,369 B. Build 9.3 s,
  peak working set 2,049 MiB (commit 2,788 MiB); rebuild byte-identical.
- **unresolved** until the run: whether a 64-cell overlay activates and streams everywhere (6 entries, one direction
  each from the Red Rocket arrival, probes at 0 / 200 / 500 / 1000 / 2000 / 3000 m where inside, plus Sanctuary,
  Vault 111, the Sanctuary bridge and Concord).

## 2026-10-11 Claude: the whole Commonwealth at Starfield scale
- Question: can the whole Commonwealth (LAND 192 x 192 FO4 cells, 11.23 km) become native Starfield terrain with
  exact geography, as one overlay, a grid of overlays, a custom planet surface or static meshes, and what limits the
  size? Write-up: [docs/terrain/commonwealth-scale.md](../terrain/commonwealth-scale.md).
- Method: raw scans of Starfield.esm (PNDT, SFBK, SFPT, SFTR, WRLD) and the BTD header survey; INI defaults decoded
  from the setting initialisers in Starfield.exe and the CK (code that references each name string); Fallout4.esm
  placed-reference extents; fits of lat/long -> planet cell against the two measured registrations; vanilla overlay
  clusters under a true-scale model. Then `src/fo4sf/overlay_grid.py`, `scripts/terrain/make_cw_overlays.py`,
  `dotnet/TerrainOverlays`, `tests/test_overlay_grid.py` (35 after QA's review), and experiment 3 staged in
  `C:\Modding\staging\terrain_exp3`. Scratch scripts in `C:\Modding\research\terrain\scale\`.
- Evidence:
  - **verified**: overlay blocks are 3 to 14 cells (430: 207 / 121 / 77 of 3 / 4 / 5, two of 14); procedural surface
    blocks 14 (616) and 26 (217) cells; the 108 BTDs of 100 x 100 cells are editor / test worlds with the default
    -500 / 1000 range, none registered on a planet.
  - **verified** values (meaning supported): `uDefaultGameTerrainWidthInCells` 100, `uPlayableSpaceOverlayCellBuffer`
    5, `uOverlayMergeZoneSize` 1, `uBlockSize` 10, `uBlockMergeZoneSize` 2, `uPlanetBiomMapFaceDim` 256,
    `uAlignment:Overlay` 4; CK `iBlockCutRecommendedMaxDimensionExclusive` 6 (the "maximum recommended cut
    dimensions" message).
  - **verified**: PNDT `CNAM` = latitude first, then longitude, radians (Earth overlays at Kyoto, Hong Kong, Cairo, St.
    Louis, Orlando; CydoniaCity at real Cydonia). Mutagen's names are swapped.
  - **verified**: the playable Commonwealth (cells with >= 20 references) is FO4 x -34..31, y -39..31 = 39 x 42
    Starfield cells; the LAND grid is 114.
  - **unresolved**: the absolute lat/long -> planet cell rule (0 of 7 projections x 13 scales x 20 origin grids fit
    World01 (+30, -35), LC172World (-5, -23) and exp2b (-12, -27)). World01's (+30, -35) holds for the first attempt
    of all five registered runs only; the three second cocs in the same session arrived at non-whole-cell offsets
    (**unresolved**). **supported**: true planet scale locally, bounded only: Cydonia's 8 overlays fit one landing
    without overlap for scale 0.5 to about 1.1 to 1.2.
  - **verified** (raw BA2 headers): the terrain-only vanilla archives (Terrain01..04, TerrainPatch) store all 2,004 of
    their BTDs uncompressed; SFBGS00D Main stores its 108 BTDs uncompressed too, but stores all 11,974 of its entries
    that way, so it says nothing about BTDs in particular; Meshes01 is fully packed; our `--pack` archive held the BTD
    zlib-packed (27,375,606 of 27,612,888 bytes). exp2b attempt 1 (runner obs.json) read z = -116.00, the BTD
    minimum, at 14 of 14 probes, the spawn and the beyond probe outside the overlay; attempt 2 read its spawn mid-fall
    (-354.13), started every drop near -309 m, and 10 of 14 probes fell through (no evidence either way). **unresolved**: why the BTD
    read flat (packed BTDs not readable is one hypothesis; the BTD not used at all is not excluded; exp1c's flat -13.94
    is not raw 0 of its -500..1000 range). The installer stores archives uncompressed since `claude/test-queue`
    f210b91; the rerun exp2b3 is queued and gates experiment 3.
  - **verified** (runner obs.json): our persistent anchors read back their unmerged local position in 4 of 4 attempts
    (exp1d a1, a2; exp2b a1, a2); the vanilla LC172World anchor moved with its merge. So experiment 3 no longer reads
    one tile's anchor from another tile's landing (those "position" entries could not measure anything): every entry
    uses the coc'd tile's own spawn (x, y) and a z_ref probe, and three locate transects find where each tile really
    sits from the heights read (`make_cw_overlays.py analyse`; on simulated runs over the real BTDs it recovers H_ll,
    off-by-one, scale 0.5 and scale 1.2 placements uniquely).
  - **verified** offline: experiment 3 (2 x 2 tiles of 14 cells, Sanctuary / Vault 111 / Red Rocket), re-staged: 9
    entries, 115 points, 490 of 490 checks, worst point 5.167 mm (step 5.173 mm); BTDs and plugins byte-identical to
    the first staging; masks north / south symmetric (mask row order unresolved); synthetic test: four tiles side by
    side = one BTD of the region, sample for sample.
- Status: recommendation (one overlay of the playable core plus surroundings, grid of 14-cell overlays as fallback)
  is a **supported hypothesis** pending exp2b3 and exp3 in game. Why exp2b read flat, landing size, seam blending, the
  lat/long rule, large-overlay behaviour, the even-size grid origin and the mask row order are **unresolved**.

## 2026-10-11 Claude: terrain experiment 2c, the FO4 objects around Red Rocket on the native terrain
- Question: can the real FO4 exterior references (cells x -20..-15, y 16..21) be placed on the exp2b terrain so the
  runner measures object-on-terrain alignment, and what does the converted collision say they stand on?
  Write-up: [docs/terrain/experiment2c.md](../terrain/experiment2c.md).
- Method: new `dotnet/Fo4Land export-exterior` (Fo4Export's serializers compiled in unchanged), `src/fo4sf/exterior.py`
  (skip reasons, placement, surface queries), `src/fo4sf/sfbodies.py` (reads back converted collision),
  `convert_batch.py --prefix`, `dotnet/TerrainExp2` objects mode, `scripts/terrain/make_exp2c.py` (select / stage /
  check); synthetic tests `test_exterior`, `test_sfbodies`, `test_make_exp2c`, `test_batch_prefix`. Staged
  `C:\Modding\staging\terrain_exp2c`. Not deployed, not run in game.
- Evidence:
  - **verified**: export = 8,960 references + 48 actors, the same 9,008 FormIDs, cells and positions (0.004 units)
    as the raw Python reader; 496 persistent references live in the world's persistent cell.
  - **verified**: 8,069 placed (1,385 models), 939 skipped with a reason (decals, lights, power lines, markers,
    effects, triggers, actors, 15 models that do not convert, 2 water planes); trees convert (STAT + BSTriShape).
  - **verified**: converted collision read back = FO4's own (RedRExt_Workshop01: 5,898 triangles, 0 differ).
    Workshop01 has no floor; the shop floor is RedRExt_Workshop02 at origin + 0.0286 m. (Corrected in the fix pass:
    Workshop02 also holds the canopy roof; the COC marker stands 2 m above the terrain and the player falls 1.88 m onto
    the pump island, 0.117 m above the terrain.)
  - **verified**: clockwise heading (PluginSpike / routes.py): 33 references at floor height fall inside the shop
    footprint, 0 with the opposite sign.
  - **verified**: building z - BTD = -0.56 mm (FO4 LAND: 0.00 mm); BTD vs FO4 terrain under all 8,069 origins:
    median 1.43 mm, p99 56.6 mm, max 482 mm (sharp FO4 edge).
  - **verified**: raw walk: all 847 exp2b records unchanged, Mars plugin / BTD / mask byte-identical, 8,071 REFR in
    16 cells as written, 0 missing geometry / material / texture files; 109 checks PASS.
- Status: offline **verified**. Whether overlay references merge with the terrain's offset, texture archive needs,
  object bounds in exteriors and the capsule radius used for point choice are **unresolved** (in-game run pending).
- Fix pass after QA (same day): the first plan lost the runner's new `z_ref` key (its entries copied six keys by
  hand), judged points 0.10 to 0.31 m above the terrain that the 0.5 m tolerance cannot tell from terrain, and mixed
  terrain probes with object probes, while exp2b's first attempt read flat ground (-116.00, the BTD minimum, at all
  14 probes) with its anchor unmerged. Now (**verified** offline, `offline_check.json` 137 checks PASS):
  - every entry carries every key of the base entry and has its own terrain reference `zref_ground` as `z_ref`;
    four entries: terrain gate, object tops >= 1.0 m above the terrain, shop floor (informational), informational;
  - with the runner's own formula: entry 1 fails on flat ground (5.49 m), entry 2 fails without objects (15.99 m),
    entry 3 passes either way (0.142 m: informational); the integ runner plans all four tests with `z_ref`;
  - the judged tops and the floor equal FO4's own collision (source NIFs, `routes.collision_bodies`) within 0.035 mm,
    all on layer 1; the low-drop entry's teleport positions are clear with a 0.4 m x 1.8 m cylinder (walls included);
  - `exterior.place` takes the cell after the rigged-door hinge shift (door `077A83` moved from cell (-10, 10) to
    (-10, 11)); `check` tests every reference's cell against its written position;
  - re-staged on `terrain_exp2b2` (exp2b + BTD also under `meshes/terrain`); not queued until an exp2b-family run
    shows the BTD relief (**unresolved**: compressed BTD storage is the supported cause, PR #67).

## 2026-10-11 Claude: overlay record fixes
- Question: in which records do our terrain experiment plugins differ from vanilla unique overlays, and what must
  SFBK `FNAM` hold? Write-up: [docs/terrain/overlay-records.md](../terrain/overlay-records.md).
- Method: raw walks of Starfield.esm (SFBK, WRLD, LCTN, PNDT, STAT) and per-cell statistics of the raw u16 heights of
  every decodable vanilla BTD with 1..30 cells (1,711 SFBK; scratch scripts, outputs not in the repo); vanilla overlay
  masks decoded with the new BC4 decoder. Then `src/fo4sf/overlay.py`, `scripts/terrain/overlay_records.py`,
  `dotnet/TerrainExp1` overlay mode, `dotnet/TerrainExp2` params, `make_exp2.py restage`, `tests/test_overlay.py`.
  Staged `C:\Modding\staging\terrain_exp1d` and `terrain_exp2b`. Not deployed, not run in game.
- Evidence:
  - **verified**: `FNAM` = `DNAM.x * DNAM.y` u16 in all 1,730 vanilla SFBK with an FNAM. Value = raw height of each
    cell's south-west corner sample, cells from the south row: every cell exact in 1,464 of 1,711 records, 94.6 % of
    all cells; min / max / mean / median / midrange / centre / north-first order: 0 records exact. lc172world 9/9,
    akilacity 89 % of cells, NewAtlantis 91 %, lc001world 4/25.
  - **verified**: all 430 overlay WRLDs have `XLCN`; `LocTypeOverlay` on the location in 11 of the 72 registered
    ones (LC172World among them), city / settlement keywords on the rest. LC172WorldLocation: parent
    `SSol_PMars_Surface` 01B736.
  - **verified**: vanilla masks are DNAM cells x 100 px, legacy `BC4U`, one mip, in a General BA2; ours match the
    format. `INAM` 1 (Absolute) in 10 vanilla blocks, `HNAM` -239..0; 1,743 Relative.
  - **verified**: PNDT `CNAM` entry = f64 (Mutagen Longitude), f64 (Latitude), u32 WRLD; Mars 10 entries + ours.
  - **verified** (offline check, both folders PASS): FNAM 50 B / 1,682 B equal to the rule for every cell, XLCN ->
    LCTN (2CA99D, 01B736), INAM/HNAM 0/0 (exp1d) and 1/0 (exp2b), persistent XMarker anchor `01000800`
    (plan `02000800`), Mars entry, mask decodes exactly, plan points within one quantisation step.
- Status: records **verified** offline. Whether any of the four differences matters in game, the meaning of `HNAM`,
  the stale FNAM of 247 vanilla blocks, mask row order and the run-time load-order byte (02 assumed) are
  **unresolved**.

## 2026-10-11 Claude: terrain experiment 2 staged
- Question: can the real Commonwealth terrain around Red Rocket be one native Starfield BTD at absolute positions,
  ready for the unattended runner, whichever BTD lookup experiment 1 finds?
  Write-up: [docs/terrain/experiment2.md](../terrain/experiment2.md).
- Method:
  - `src/fo4sf/terrain_grid.py`: grid rule, choice of n, separable bilinear resampling with edge clamping, and
    interpolation rules for check points.
  - `scripts/terrain/make_exp2.py`: reads the FO4 cells with the PR #56 `fo4land` module, writes the BTD with
    `btd.py`, then `plan.json` and `expected.json`.
  - `dotnet/TerrainExp2`: writes the plugin from experiment 1's template.
  - Survey of the LTEX quadrant maps of the 753 top-level vanilla BTDs (scratch).
  - Staged in `C:\Modding\staging\terrain_exp2`. Not deployed.
- Evidence (**verified** offline):
  - n = 29: Starfield cells -14..14, samples -1400..1499.22 m. That covers the PR #56 patch plus 300 m.
  - FO4 cells x/y -24..25 (2,500) read, so the whole BTD holds real heights.
  - BTD 27,612,888 B. Heights -114.46..140.67 m, header -116/142, step 3.937 mm.
  - Base texture `001235C2` LDirtFootprints01: the base of 2,334,675 quadrants in vanilla BTDs, and the only texture
    of TempJemisonWorld.
  - Plugin 36,742 B, checked with a raw walk:
    - WRLD `FO4CW_Commonwealth`, overlay `BNAM` pointing to SFBK `ANAM Data\TERRAIN\FO4CW_Commonwealth.btd`
      (record path and name both match), `DNAM` 29 x 29, `ENAM` -116/142;
    - `NAM0`/`NAM9` raw -1400/1500 m (Mutagen shows metres / 4096);
    - 841 cells;
    - COC cell `FO4CW_RedRocketSpawn` (-10, 11) with a marker at (-989.03, 1147.20, 107.14).
  - 14 check points at FO4 vertices (Red Rocket, flat, slope, both seam kinds, resampled). The decoded BTD returns
    every expected height within 3.221 mm under bilinear and both triangle splits.
  - Over all 4,225 patch vertices: median error 1.58 cm, p99 13.4 cm, max 1.42 m at a 75 deg cliff.
  - Rebuilds are byte-identical.
  - SFBK `FNAM[0]` = the BTD's SW corner raw height in 3 of 3 vanilla blocks.
- Status:
  - BTD, plugin and plan are **verified** offline.
  - H (BTD z = FO4 z / 70) and the grid rule remain **supported hypotheses** until experiment 1 or 2 runs in game.
  - **Unresolved**: `FNAM[1..7]`, whether `SmallWorld` or 841 empty cells matter, FO4's triangle split, and cliff
    accuracy at a 0.78 m grid.
  - Next (plan): an exterior exporter for the Red Rocket statics. Fo4Export is interior-only.

## 2026-10-11 Claude: Starfield terrain architecture
- Question: how can native Starfield terrain carry the exact Commonwealth geography (S5 / WP-12)?
  Full write-up: [docs/terrain/architecture.md](../terrain/architecture.md).
- Method: raw record walk of both ESMs; new read-only SfInspect commands (`wrld`, `sfbk`, `planetworlds`, `wcells`,
  `form`); index-only listing of the terrain BA2s and a 44-byte header survey of all 2,112 `.btd`; BTD decoder after
  fo76utils (MIT) checked byte-for-byte on vanilla files; ref-vs-terrain fits; xEdit's Starfield definitions read for
  field names; FO4 `LAND.VHGT` decoded for all Commonwealth cells.
- Evidence: Starfield.esm has 0 `LAND` (Fallout4.esm 37,020). 430/433 WRLD point through an overlay component to an
  SFBK whose `ANAM` is `Data\TERRAIN\<EditorID>.btd`; 72 WRLD are registered by planets (`PNDT.MasterWorldspaces`,
  lat/long). BTD: 128 samples per 100 m cell, u16 heights linear in metres between a per-file min/max, LOD0-4,
  vanilla up to 100 x 100 cells. Commonwealth LAND: 192 x 192 cells, -118.86..641.03 m.
- Status: format, record chain and sizes **verified**; height scale in metres and grid alignment (BTD cell i = world
  cell i - n//2) **supported hypothesis** (pad at 111.4 m vs refs at 112-113.5 m; 130/133 NewAtlantis object cells inside
  the predicted footprint); whether a plugin worldspace with its own BTD loads, and whether it needs a planet entry,
  **unresolved** until experiment 1 (staged in `C:\Modding\staging\terrain_exp1`, not deployed). Recommendation:
  option A, a dedicated worldspace with a native BTD.

## 2026-10-11 Claude: FO4 terrain source patch
- Question: can we read absolute Fallout 4 terrain heights for a small patch, and prove them right, by reusing
  existing work before writing a LAND parser?
- Method:
  - Read fo76utils `fo4land` (MIT, commit `c52da18`) as the reference. It cannot be built here: there is no
    compiler or scons, and nothing was installed.
  - Wrote `src/fo4sf/fo4land.py`, which follows its VHGT algorithm, and `dotnet/Fo4Land`, a Mutagen-based second
    decode.
  - Extracted cells x -18..-17, y 18..19 of `Commonwealth` around the Red Rocket Truck Stop
    (REFR `000211C0`, `RedRExt_Workshop01`).
  - Details and commands: [docs/terrain/source-patch.md](../terrain/source-patch.md).
- Evidence (report.json; all **verified**):
  - Python vs Mutagen decode: max abs difference 0.0 over 4,356 vertices, and the same 1,315 refs.
  - All 1,315 temporary refs lie inside their XCLC cell (min margin 0.21 units).
  - Patch seams: max difference 0.0.
  - The Red Rocket floor z 7360 equals the terrain at its origin (residual 0). Over its footprint the max abs
    residual is 8 units.
  - 100 rocks, stumps, saplings and shrubs: z minus terrain median -7.4 units. Flipped or transposed grids give
    367-653.
  - Patch relief 1840 units, slope median 11.3 deg, max 76.5 deg.
  - Whole world: 36,864 cells. 649 of 73,344 neighbour seams (0.88%) do not match, the worst by 13,056 units in the
    far north-west (x -68..-62, y 76..77).
- Status: VHGT layout and orientation (row 0 = south, col 0 = west, height = 8 * (offset + accumulated gradient),
  origin = XCLC * 4096) are **verified** for Fallout4.esm.
  - The large maple trees sit 266 units deep. That they are planted deep on purpose is a **supported hypothesis**.
  - **Unresolved**: FO4's triangle split (bilinear vs either diagonal differs by up to 19 units at the refs),
    whether the big seams matter (are they in the playable area), and how any of this maps to Starfield terrain
    scale or format. 70 units/m is only the object scale.

## 2026-10-12 Claude: what every vanilla Starfield NPC_ carries; corrections to the raider entry (QA on PR #75)
- Question: which subrecords and header values does every vanilla NPC_ have, and which of them did the converted raider
  (FO4ActorRaider.esm, 2026-10-11) lack? Write-up: docs/actors/raider-conversion.md sections 3, 4 and 8.
- Method: `ActorRaider rawcount` and a read-only Python scan of Starfield.esm's raw NPC_ records (headers, zlib
  data, subrecords); `ActorRaider check`, which now compares each written NPC_ with the list; a scratch Mutagen
  probe for what writes EDCT.
- Evidence and status:
  - **Verified:** 16 subrecord types are in all 7,131 NPC_ (EDID in 7,130), also in all 2,821 that inherit Traits:
    EDID OBND ODTY ACBS RNAM PRPS AIDT DATA DNAM NAM5 NAM6 NAM4 MWGT EDCT STON PRON. The first raider build lacked
    PRPS, STON, EDCT and PRON (`check`: 2 problems for actor_raider1, 0 for actor_raider2).
  - **Verified:** all 7,131 NPC_ have record header form version 581; Mutagen writes 576 unless told (the first
    build); its round trip keeps 581.
  - **Verified:** templated records carry their template's values: PRPS equals the Stats template's in 2,692 of 4,046
    Stats-templated NPC_ whose template is an NPC_; STON / PRON / EDCT equal the Traits template's in 2,287 / 2,317 /
    2,274 of 2,318. EDCT equals the number of tint blocks (MNAM) in all 7,131; Mutagen writes it from a set `Tints`
    list (an empty one: EDCT 0).
  - **Verified:** STOP is in exactly the 4,310 NPC_ that do not inherit Traits (1,722 right after AIDT, 32 after RDSA)
    and in none of the 2,821 that do. Mutagen's round trip adds it to all 3 Traits-inheriting records it copied
    (LvlSpacer_Male and LvlSpacer after RDSA, LvlCitizen_NoOld after KWDA). That a STOP in a Traits-inheriting record
    is harmless is a **supported hypothesis** only.
  - **Verified:** 74 of 84 vanilla NPC_ with a WEAP directly in CNTO carry no AMMO (the companions among them), so
    "an NPC needs no ammo for its weapon" is a **supported hypothesis** (the Coachman's NpcsUseAmmo False is verified).
  - **Verified:** HEFA is in 29 NPC_, never null. A Mutagen link set to FormKey.Null is written as a null subrecord.
  - **Supported hypothesis (xEdit's Skyrim / FO4 template semantics):** the death item goes with Traits and the
    combat style with AI Data; the raider inherits both, so its own INAM is probably overridden (EncSpacerFaceM01 has
    none) and its ZNAM equals the inherited csSpacer_Assault anyway (verified).
  - **Unresolved:** whether the game needed any of these; whether `GetIsID` confirms a templated actor whose chain has
    no leveled list (N2a_base answers it first; every other N2 test waits for that).

## 2026-10-11 Claude: converting one Fallout 4 raider into a native Starfield NPC_
- Question: what does a converted FO4 actor need to run on Starfield's own actor systems, and can Mutagen write it?
  Full write-up: docs/actors/raider-conversion.md.
- Method: `dotnet/ActorRaider` (read-only on both ESMs): `export-fo4` follows the template chain of ACHR 00046458
  `DN092concordRaider01` (Concord); `sf-dump`, `sf-tplstats`, `rawcount`, and `roundtrip` (Mutagen writes 6 vanilla
  NPC_ records back; every subrecord is compared with Starfield.esm).
- Evidence and status:
  - **Verified:** the FO4 chain is LvlRaider 0002898B -> LCharRaider 00022E48 -> EncRaider01Template 0003183A at
    player level 1, with traits from LCharRaiderFaceAndGender 000FD3A3 (14 faces). Starfield's LvlSpacer 0027BB7B ->
    LCharSpacer 0027BB7D (10 tiers) + LCharSpacerFaceAndGender 0027BB7C (7 faces) has the same shape.
  - **Verified:** hostility works differently. FO4 RaiderFaction has no relation to PlayerFaction (9 relations); its
    raiders are VeryAggressive. SpacerFaction 0027BB8C is Enemy to PlayerFaction 01C21C; Spacers are Unaggressive /
    Brave and carry 6 RDSA reaction radii.
  - **Verified:** Starfield NPC_ have 15 template slots; Mutagen 0.55.0-alpha.67 names 13 of them (slots 13 and 14 are
    `TemplateActors.Unknown1/2`, flag bits unnamed). 5,445 of 7,131 NPC_ use templates (bit 13: 2,825, bit 14: 4,253).
    Slots 13 and 14 almost always share the behaviour template, never Traits alone. What they mean is **unresolved**.
  - **Verified:** Mutagen round trip. 1 of 6 records came back byte-identical. 2 differ only in FULL (localized string
    ID -> inline string). 3 gain an empty STOP (corrected 2026-10-12: 2 after RDSA, LvlCitizen_NoOld after KWDA; no
    vanilla NPC_ that inherits Traits has a STOP, see the 2026-10-12 entry), so that it is harmless is a **supported
    hypothesis**. Everything else matched, including TPTA, AIDT, RDSA and the raw subrecords.
  - **Verified:** the Coachman WEAP 0026D96B has `NpcsUseAmmo` False (that the NPC therefore needs no ammo is a
    supported hypothesis, see 2026-10-12). FO4Port.esm's highest local FormID is DE5C, so the raider's F04800 cannot
    collide.
  - **Supported hypothesis:** the plugin's console ID is 02F04800 (first plugin in Plugins.txt = slot 02, as for the
    terrain anchor 02000800).
  - ~~**Supported hypothesis:** a direct NPC_ template, with no leveled list in the chain, keeps `GetIsID` working.~~
    Corrected 2026-10-12: **unresolved**. No evidence supported it (N0_ptr_lvl tests a chain WITH a leveled list).
  - **Unresolved until N2a / N2b run:** whether Starfield spawns, animates and paths the converted record, and
    whether it engages the player.
## 2026-10-11 Claude: NPC navigation and minimal actor conversion research
- Question: will an NPC walk in a plugin worldspace with BTD terrain only; can FO4 navmesh be converted; which vanilla
  NPCs and console steps give the smallest NPC test; how does a FO4 raider map to a Starfield NPC_?
- Method: read-only scans of Starfield.esm / Fallout4.esm (GRUP walk, byte-exact `NVNM` parse), `SfInspect`
  (`navm`, `npcfind`, `npc`, `props`), strings in Starfield.exe and CreationKit.exe. Details:
  [docs/actors/npc-navigation.md](../actors/npc-navigation.md). Nothing run in game.
- Evidence: NAVM 56,576 (Starfield) / 7,893 (FO4); 424 of 433 Starfield worldspaces have NAVM, cities 820..2,708,
  landing overlays 1 each, `DefaultWorld` 0; interiors 7,959 NAVM in 475 of 11,985 cells. `NVNM` v17 vs v15: vertices
  16 B (metres) vs 12 B (units), cover 12 B vs 8 B, +4 trailing bytes; all FO4 records parse exactly, 56,570 of 56,576
  Starfield records; Mutagen's Starfield `NavmeshGeometry` schema has the same fields. Exe: runtime generator settings
  (`bDisableNavMeshRuntimeGen`, `PlanetNavMeshGen`, `bIgnoreMissingNavMeshSeed`), console `GenerateNavMesh` (`gnm`),
  `PickLastRef` (`plr`); CK: `-UpdateNavmeshGeneration` / `-FinalizeNavmeshes:<esm> (cell ids...)`. FormIDs verified:
  `LvlCitizen_NoOld` 0000CF96, `PCM_Narion_Kreet_GrazerPreyA` 001F3E88, `LvlSpacer_Male` 0010DD71, control cell
  `QASmoke` (one flat 554.7 m^2 navmesh).
- Status: Starfield `NVNM` v17 layout **verified** (56,570 records + Mutagen schema); FORMAT-GAP's "NAVM overlap 1.0"
  **verified for subrecord signatures only**, the inner layout differs. "No movement without authored NAVM in a plugin
  worldspace": **supported hypothesis**. Runtime generation for plugin worldspaces (`gnm`, seed markers): **unresolved**,
  probes N1-N3. Meaning of the vertex i32, triangle byte 20, cover and trailing fields: **unresolved**. FO4 navmesh
  conversion for Red Rocket: **supported hypothesis** (FO4 cell (-17,19) lies inside one 100 m Starfield cell).
## 2026-10-10 Claude: skinned props are drawn in the node pose (converter now bakes it)
- Question: FO4 skinned props (skeletons, sinks) were converted in their stored bind pose; is that what FO4 shows?
- Method: `convert_static.pose_skinned_shapes` (fo4skin, PR #45) on the real files, stored vs posed vertex heights.
- Evidence: `Vault_Sink_01.nif`: the tap is stored at the model origin (z -0.03..0.03 m) and posed on the basin rim
  (1.13..1.19 m), the two water-stream shapes posed falling from it (0.82..1.07 m); stored, they sit in the floor.
  `SkeletonClothed01.nif`: posed z 0.29..1.74 m and y -0.53..0.92 m, the same box as its 17 bone nodes / converted
  collision (0.30..1.74, -0.54..0.92); stored it stands 0.01..1.88 m with collision 0.3 m above its feet.
- Status: "FO4 draws placed skinned props in the NIF's node pose": **supported hypothesis** (the sink makes no sense
  otherwise; the skeleton's collision agrees; not yet seen in game). Animated NIFs (NiControllerManager) are posed too:
  the node pose is their rest pose; **unresolved** whether every animated prop looks right (counted in the manifest as
  `skinned_posed_animated` for the in-game check). The pinned build has 2,272 skinned placements, 346 of which move by
  2 units or more (PR #45's scan).

## 2026-10-10 Claude: FO4 skin reader (BSSkin::Instance, BSSkin::BoneData, vertex weights) and pose bake
- Question: where does a skinned FO4 shape keep its bone nodes, skin-to-bone transforms and per-vertex weights, and
  does posing it with the NIF's own bone nodes give back its stored positions? (Prerequisite for posing ragdoll
  skeletons; reader and linear blend skinning in `src/fo4sf/fo4skin.py`.)
- Method: decoded `Meshes\SetDressing\Skeletons\SkeletonClothed01.nif` (`Fallout4 - Meshes.ba2`, 51 blocks; skinned
  shapes `Skeleton:0` block 40 and `Shirt:0` block 45), then ran the reader over every skinned shape in
  `Fallout4 - Meshes.ba2` and `Fallout4 - MeshesExtra.ba2` (local scripts, not in the repo).
- Layouts in SkeletonClothed01:
  - `BSSkin::Instance` (blocks 41, 46; 84 bytes): skeleton root i32 @0 = 0 (root NiNode), bone data ref @4 = 42 / 47,
    bone count u32 @8 = 17, 17 i32 bone node refs @12 (TorsoLowerBone01 ... RightHandBone01), count u32 @80 = 0.
    84 = 12 + 4 x 17 + 4.
  - `BSSkin::BoneData` (blocks 42, 47; 1160 bytes): count u32 @0 = 17, then 17 entries of 68 bytes: sphere centre xyz +
    radius @+0, rotation 9 f32 @+16, translation 3 f32 @+52, scale f32 @+64. 1160 = 4 + 68 x 17.
  - Vertex skin data: descriptor `0x7b00065430209` (`Skeleton:0`: 36-byte vertex, attributes 0x7b, skin nibble
    (bits 28-31) 6, so byte 24) and `0x5b00050430208` (`Shirt:0`: 32 bytes, no colour, skin at byte 20): 4 f16 weights,
    then 4 u8 bone slots. Vertex 0 of `Skeleton:0`: weights (0.693, 0.307, 0, 0), slots (8, 7) = TorsoUpperBone01,
    TorsoMidBone01.
- Rotation convention: bone world x skin-to-bone gives one and the same transform for all 17 bones when the stored
  rotation is read row-major like NiAVObject in nif.py (spread 0.00004 units, 0 in rotation); read transposed, the
  bones disagree (rotation entries off by 0.68 to 0.78). Bounding spheres are in bone space: 7,108 of 7,112 weighted
  vertex/bone pairs are inside in bone space (worst overshoot 0.023 units), 113 of 7,112 in skin space.
- Weights: per-vertex sums 0.999695 to 1.000244 (f16 rounding), 1 to 3 influences, no vertex without weight.
- Pose: posing with `nif.world_transforms` does **not** give the stored positions here: max error 64.45 units
  (`Skeleton:0`) and 61.46 (`Shirt:0`), mean about 20. The node pose isn't the bind pose: the 16 child bones' local
  transforms equal the bind pose exactly (difference 0), only the root bone TorsoLowerBone01 is turned 45.0 degrees
  more about +X around its own origin (-0.105, -2.558, 84.044). With that one rigid transform taken out, posed vs
  stored max error is 0.000025 units for both shapes. Posing with the bind pose (inverse skin-to-bone) gives back the
  stored positions to 0.000026 units (0.028 without weight normalisation). `pose_vertices` takes 5 ms for 5,503
  vertices.
- The ragdoll is authored in the node pose: in the skeleton's `hknpPhysicsSystemData`, all 17 body rotations
  (quaternion x, y, z, w) equal their bone node's world rotation (entries within 0.0001; transposed, up to 1.58 off),
  and body origins are 0.01 to 12.4 units from the bone node origins, vs up to 63.8 from the bind-pose bones.
- Archive scan (159,856 NIFs, 60 s): 3,588 NIFs with 16,350 skinned shapes (15,325 BSSubIndexTriShape, 1,025
  BSTriShape) read with 0 errors (instance and bone data sizes match their counts in every block). Skin offset nibble
  = offset from walking the preceding vertex fields in all 15,727 shapes the walk covers (the other 623 are FaceGen
  shapes with eye data, 0x100); 0 mismatches. Every skin-to-bone scale is 1. The instance's trailing array has 0
  entries (4,557 instances) or one per bone (11,793, all FaceGen heads), 12 bytes each; all 53,452 values are
  (0, 1, 1). 57 vertices in 11 shapes have no weight; none is used by a triangle (`pose_vertices` lets such a vertex
  follow its first slot). Node pose vs bind pose per shape: identical for 616, one rigid offset shared by all bones for
  9,606, bones disagree (a real pose) for 6,128.
- Converter impact (not changed here): `pipeline.convert_nif` draws skinned shapes from their stored (bind pose)
  positions but puts collision bodies on the bone nodes (node pose). Example: `Vault_Sink_01.nif`'s `tap:0` is stored
  as a 2 x 2 x 4 unit piece at the model origin (z -2.1 to 2.1); posed with the node pose it sits on the basin rim
  (z 79.4 to 83.5; the unskinned basin tops out at 83.6). Of the 701 skinned models outside Actors, Armor and Weapons,
  523 have a skinned shape that the node pose moves 2 units or more. In the pinned `multi_next` cells, 346 of 2,272
  placements of models with skinned shapes use such a model: 95 skeletons (9 models, e.g. 28
  `SkeletonClothedVaultSuit`, 15 `SkeletonClothed01`), 32 `vault_sink_01`, 13 `vault_fountain01`, ...
- Status: the three layouts **verified** (SkeletonClothed01 plus the 16,350-shape scan); row-major skin-to-bone rotation
  **verified** (17 of 17 bones in two shapes); bounding spheres in bone space **verified**. "FO4 draws placed skinned
  models in the node pose, so the converter should pose them": **supported hypothesis** (ragdoll bodies and the sink
  tap fit it; no in-game check; animated models such as doors and elevators depend on their controllers).
  **Unresolved:** the meaning of the instance's trailing (0, 1, 1) vectors, and whether FO4 renormalises f16 weights
  (0.028 units at most here).

## 2026-10-09 Claude: which FO4 collision bodies are movable?
- Question: how does an FO4 `bhkPhysicsSystem` mark a body as movable (pushable), so the converter can stop turning
  physics objects into fixed obstacles (Vault 114 door `05C7DC` is blocked by a ragdoll skeleton)?
- Method: compared `SkeletonClothed01.nif` (ragdoll) with `SubPlatformWall01.nif` (static) in the
  `hknpPhysicsSystemData` packfile, then scanned all 4,014 converted models (local script, not in the repo).
- Evidence: body cinfo +12 (u32) is a motion index: skeleton bodies 0..16 with 17 motion entries and 16 constraints
  (`hkpRagdollConstraintData`, `hkpLimitedHingeConstraintData`), layer 10; static wall `0x7FFFFFFF`, layer 1.
- Scan (motion index != 0x7FFFFFFF): 490 models / 5,340 placements with one moving body; 59 / 345 with several and no
  joints (cryo pods, roof hatches); 29 / 167 ragdolls with joints (skeletons, V111 gear-room gates, gurney).
- Status: "+12 = motion index, 0x7FFFFFFF = static": **supported hypothesis** (2 files). "Motion index means
  pushable": **refuted as stated**: placed Statics like `BldgShellWoodStairsRailing01` also have one, so it also covers
  keyframed / animated bodies. **Unresolved:** the motion entries' mass / motion type, which separates pushable
  (dynamic) from keyframed bodies.
- Follow-up (same day): system +32 holds motion *properties* (present only for dynamic bodies; values like 104.375 /
  31.57 / 0.1 / 0.05 identical in skeleton and pencil) and +48 the motion *cinfos*: u16 motion-properties id at +0,
  inverse mass f32 at +4. Skeleton: id 0, inverse mass 0.1 (10 kg); pencil: id 0, 2.0 (0.5 kg); stair railing and cryo
  pod: id 0xFFFF, inverse mass 0 (keyframed). Rule "dynamic = motion index != 0x7FFFFFFF, its cinfo id != 0xFFFF and
  inverse mass > 0": **supported hypothesis** (4 files, consistent across the scan). Rescan of 4,014 models: 373 single
  dynamic (4,642 placements: loose items), 22 multi-body without joints (156: breakable railings, gore), 29 ragdolls
  (167). Railings and cryo pods move to static, which is correct for them.

## 2026-10-09 Starfield `.af` animation header (door rigs)
- Question: what are the u16 fields at 0x28 of `open.af`?
- Method: compared four door families' `open.af` with their `characterassets\skeleton.rig` name tables
  (docs/spikes/WP-doors-research.md, "Header fields vs rig bone tables").
- Evidence: Akila 6 bones / field 6; generic 21/21; ship small 24/24; ship large 49/49.
- Status: field 2 = rig bone count: **verified** (4 of 4). Field 1 = format version: **supported hypothesis**.
  Field 3 = frame count: **supported hypothesis** (30 fps unconfirmed). Field 4: **unresolved**.

## 2026-10-09 FO4 precombine collision bodies with "shared vertex index out of range"
- Question: what primitive encoding do these `SCOL\CM*.NIF` bodies use?
- Evidence: 0 packed vertices, shared-index entries in triples (2130, start, x), primitives like (3,2,2,2);
  docs/JOURNAL.md "Precombine debris parts" and its correction.
- Status: **unresolved**. The "thin rods" reading was **refuted** (groups up to ~3 m in every axis).

## 2026-10-14 Claude: the merge offset is not planet-scale linear in the registration (H_ll refuted at a second site)
- Question (owner's review, proposal P5): can the overlay be registered so that its merge offset is zero, so persistent
  references, probes and teleports stop needing a frame conversion?
- **verified** (two measured registrations): World01 at (0.2, 1.2) rad merged at planet cell (+30, -35); exp2b /
  core64c at (0.3, -1.2) rad merged at (-12, -27). `overlay_grid.predicted_offset` (H_ll, true planet scale from the
  World01 reference) predicts (-29,902, -47,460) cells for the second site: **refuted** as a global model (it was only
  ever claimed "near a registration"). Under H_ll a zero offset would need (0.2010324, 1.1990970) rad; that prediction
  has no support now.
- **unresolved**: how the engine maps a PNDT CNAM latitude/longitude to a surface cell (a block grid with wrapping, or
  a coarse quantisation, would give small offsets at both sites). Two cheap discriminating runs when a window allows:
  the same overlay at (0.2, 1.2) (does it reproduce +30/-35, i.e. is the offset a function of the site alone?) and at
  (0.3 + 1/33900, -1.2) (one cell north under any linear local model). Until then fix A (vanilla persistent-cell
  shape, cave_core64c_1015) is the route to persistent references, and the runner keeps converting frames.

## 2026-10-16 Claude: Starfield's compressed-mesh decoder and our SIMD tree keys (the collision crash)
- Question: why does Havok assert "Unknown primitive type in compressed mesh" (hknpCompressedMeshShapeInternals.cpp:939,
  Starfield.exe+0x36F418B, every WER report since 10-12) and why did the owner's crash dump show the closest-points
  query of vault_cart_01's mesh (40 primitives, one data run {0, 40}) searching the data runs for primitive 40?
- Method: FO4 source (hkpackfile) and converted blob (hktagfile) of vault_cart_01 side by side; 837 vanilla compressed
  meshes (random 1,500-NIF sample of Starfield - Meshes01.ba2) decoded the same way; src/fo4sf/meshcheck.py.
- **verified** (837 of 837 vanilla meshes, 0 exceptions): the SIMD tree holds ONE leaf per primitive with key
  section << 8 | primitive << 1 (triangle bit 0), unique, one for every primitive of every section; the per-section
  Aabb4BytesCodec tree (leaf when hiData bit 0 clear, primitive = hiData >> 1, right child at +(hiData & 0xFE)) names
  every primitive once; the data runs (value u16, index u8, count u8) cover 0..numPrimitives-1 exactly; section flags
  always 0; primitiveStoresIsFlatConvex (tree + 60) always 0xFF; no primitive has indices[1] == indices[3];
  numPrimitiveKeys = triangles + 2 x quads and maxKeyValue = the last primitive's key (the key SPACE keeps the triangle
  bit; only the tree leaves drop it). FO4 (vault_cart_01) uses the same tree codec, key space and header values.
- **verified** (our builds): fo4collision.compressed_mesh_keys gave the SIMD tree one leaf per TRIANGLE, so every quad
  also had an odd key: vault_cart_01 had keys 0..79 for primitives 0..39. integ_1017: 2,947 of 4,346 models,
  181,738 odd keys, 4,045 of them the last primitive of a section; terrain_core64h: 7,861 of 11,769 models, 761,426
  odd keys, 13,650 past the end (C:\Modding\scratch\meshkeys\baseline_*.json).
- **supported hypothesis** (the crash dump: index 40 = (79 + 1) >> 1 for a 40-primitive section; the stale assert
  frame on v111rpit2raisedmid01, 3 primitives, keys 0..5; vanilla never has odd keys): the decoder takes a leaf key K
  as the primitive's first triangle and K + 1 as a quad's second one, so an odd K steps into the next primitive slot
  (an FO4 DE AD DE AD slot asserts; past the end of the section the data-run search returns NULL: the owner's AV).
- **verified** (35 sections in integ_1017 and core64h): FO4 section flag bit 0 is set exactly on the sections that
  hold FO4's own special primitives (a, b, b, b) with b outside the section's vertex slots; vanilla has neither.
  Their meaning is **unresolved**; the converter replaces them (and DE AD DE AD slots) with a copy of the nearest valid
  primitive of the section and clears the flag, so the section is byte-for-byte in the vanilla shape.
- **unresolved**: what primitiveStoresIsFlatConvex changes in the engine (the crashing function does not read it; vanilla
  quads with it set are not flat or convex). The converter now writes the vanilla value so no vanilla-untested code
  path is exercised.

## 2026-10-17 Claude: why the player walks through the Vault 111 gear-room gates (static bodies on layer 55)
- Question: the gear-room gates (`V111GearRoomGate01` in Vault111Cryo, `02` in Vault114) let the player through in
  integ_1018 (playtest row 19) although since #230 their NIFs hold FO4's native bodies. Wrong place, wrong filter
  word, or something the engine refuses?
- Method: FO4 source (hkpackfile) and the deployed blobs (hktagfile, the session's hkdump.py) side by side, hull
  vertices transformed through the collision nodes; COLL records of Fallout4.esm and Starfield.esm; every body of
  every vanilla Starfield NIF (Meshes01 + MeshesPatch: 40,613 files with physics, 46,413 bodies, 50 s) and of every
  FO4 NIF (Meshes + MeshesExtra: 63,327 files, 218,882 bodies); the Starfield.esm records placing the only vanilla
  layer-55 models. Scratch: C:\Modding\scratch\gatefix (gate_dump.txt, coll_records.json, full_scan_*.json).
- **verified** (geometry): each leaf's FO4 body cinfo equals its node transform (GateR at (-7.082, -0.044, 0.719) m,
  z -90 deg), so the converter's identity body on a node with that transform puts the hulls where FO4 has them: top
  rail x -7.10..-7.06, y -0.08..1.28, z 0.80..1.03 m, lower stub z 0.40..0.79 m (render leaf z 0.39..1.05); the XRGD
  variant (`_xrgd_e3c6933a65`) lifts both by 0.147 m as the reference's pose does. The two leaves span the whole
  2.78 m opening at x -47.76 m world; the owner's bridge positions (00:02:57 at -44.84, -4.00; 00:03:12 at -57.91)
  cross that line through the middle. integ_1011's 39 guessed boxes sat there too (0x1, hknpBoxShape); whether the
  owner walked through those is **unresolved** (row 6 reported the elevator, not a walk).
- **verified** (the word): the leaves' only difference from a working static is `collisionFilterInfo` 0x8037 (layer 55
  L_CLUTTER_NOCUT + bit 15); flags 0, collisionCntrl 0, quality 255, hknpConvexShape flags 0x43, material and
  motionType 0 are the template's, as on vanilla statics and on BldDecoSmStairsBlock03's helper hull (a convex body
  on a child Collision node, climbed in batch_full 0004).
- **verified** (COLL): in both ESMs layer 55 lists 30 L_CHARCONTROLLER and 30 lists 55 (so does 1), GNAM 0 for 55
  and 0x4 for 4 / 29 / 2 (the navmesh-cutting layers). The layer matrix alone does not explain a pass-through.
- **verified** (vanilla use): Starfield writes layer 55 on 4 bodies in 2 files only, `na_lobbyoffice_reception_
  turnstile_01_door01a/b.nif`, static, word 0x8037 exactly; they are STAT records (00040DD7/8) placed 29 times across
  New Atlantis lobby walkways (e.g. four turnstiles in a row at y -33.39, refs 000C1BEA..F2). Bit 15 on L_STATIC is
  walked on: `nathemastbase_01..04(_grass).nif` (the MAST plaza) are one 0x8001 body each; stair helpers carry 0x801f.
  FO4 writes layer 55 on 9 bodies in 4 files, all dynamic hinged leaves (the two gates, CarHulk01 doors, BollardDest01).
  Static bodies on 4 / 29 are common in both games (asteroid caves on 0x1d; static ladders and ingots on 0x4).
- **supported hypothesis** (the cause): Starfield's character controller passes through a static body on layer 55,
  as it must through the turnstile leaves; FO4's gate is passable too, but by swinging (10 kg leaves on hinges).
  Freezing the leaves (joints not converted) on that layer gives a ghost gate. Fix: a body we write static on layer 55
  becomes 1 L_STATIC, the layer alone (meshcollision.static_filter; report "relayered"); every other word is kept.
  Blast radius in integ_1018: the 3 gate NIFs (12 leaf bodies), nothing else. The drop-in NIFs in
  C:\Modding\scratch\gatefix\after differ from the deployed ones by 2 bytes per leaf blob (0x8037 -> 0x0001).
- In-game check (one walk): from the owner's spot (-44.8, -4.0, 0) walk west along y -4.0; PASS = stopped at
  x about -47.4 (capsule 0.35 m before the rail at -47.76), FAIL = x beyond -48. The diagnostic variant
  `after\variant_bit15_cleared` (0x0037, layer kept) tells layer from bit if wanted. The gate then blocks the walkway to
  the exit elevator (1.18 m rail, jumpable with the pack); a swinging gate needs the hinge conversion.

## 2026-10-17 Claude: spike B4, mission anatomy, the Vault 111 exit, grab mass limits (offline)
- Question: what the cut-down "When Freedom Calls" needs (input to Codex's QUST / DIAL / INFO / PACK design), what
  Preston adds beyond the converted raider, how FO4 runs the Vault 111 exit, and which grab limits apply to carrying.
- Method: read-only. The repo's fo4land.Plugin walker and ba2 reader on Fallout4.esm, `Fallout4 - Voices.ba2` (voice
  files per INFO) and `Fallout4 - Misc.ba2` (call lists of the compiled scripts); Mutagen `ActorRaider fo4-dump` as a
  cross-check; GMST groups of both ESMs; the setting initializers in both executables; Starfield's vanilla Papyrus
  sources. Full tables: docs/spikes/B4-mission-anatomy.md.
- **verified:** the mission is four quests: Min00 001A001C (name, 19 stages, 14 objectives, 20 external aliases),
  MQ102 0001CC2A (the driver, also the Vault 111 exit), DN092 0001D806 (the fight), DialogueConcordArea 000179F3 (255
  DIAL, 397 INFO, Preston's 102 lines, the reward of 100 caps and 50 fusion cells). The 7 counted raiders are placed
  ACHRs in ConcordMuseum01, 4 of them initially disabled. Preston (NPC_ 00019FD9, voice NPCMPrestonGarvey) has 2,421
  base-game voice files over 2,264 INFOs in 99 quests and no default package list.
- **verified:** FO4 ends the elevator ride with an automatic load door (Vault111InteriorAutoLoadDoorREF 0001F180, base
  AutoloadDoorNoText FNAM 0x42, to 000998E3); the cog door's Stage2 is played by MQ03QuestScript on the console's
  "stage4" animation event. Verdict: GO for a scripted load door in place of the ride and for the cog door as a door
  rig; NO-GO for B1 on an activator rig.
- **verified:** neither ESM sets fGrabMaxWeightWalking / Running; both exes default to 100 / 50 (Starfield also
  fGrabRagdollMaxWeightWalking 200, fZKeyActorMassTheshold 6). **supported hypothesis:** the converted items measured
  on 13 Oct (10-50 kg) are under the walking limit, so mass alone should not block a walking grab; the owner's
  SetRigidBodyMass test plus `SetGS fGrabMaxWeightWalking 1000` decides it. No converter change.
- **unresolved:** Preston's friendly Starfield template; whether quest targets route through our scripted doors; the
  cog door's clip in game; whether the cut-down quest may force combat (FO4 does, DN092 stages 13 / 76).

## 2026-10-18 Claude-cloud: converted interiors get no natural (sky) light, only placed lights
- Report (owner, 18 Oct 00:58Z): "where there is lights stuff looks really good, but ... the natural lighting doesn't
  affect textures yet so it's really dark". His snapshot a minute earlier (`C:\Modding\snapshots\20261017-185720`,
  owner button, interior cell 050049B4 = the Boston Public Library on the installed integ_1019_doors set) shows the hall
  black except where the helmet lamp falls; the lamp-lit wall reads correctly (texture, normal, roughness fine).
- **verified (code):** the interior writer (dotnet/PluginSpike/Program.cs, cell loop) gives every converted interior the
  same light set-up, whatever FO4 had: lighting template KreetBase01LGTtemplate 06BCF8 (underground) unless
  lighting.json says otherwise, image space 122393, and EnvironmentMap `Data\Textures\cubemaps\blackcube.dds`
  (journal 2026-10-08, chosen to stop the pink wash from a bright default sky). FO4's own cell lighting (XCLL ambient,
  directional and directional-ambient colours, fog, its lighting template) is never exported (Fo4Export wrote only refs),
  so the window-lit FO4 interiors and the vaults get the same light set-up. (Correction, PC check 18 Oct: the installed
  integ_1019 lighting.json sets ShipInteriorLT 006658 for every cell through `"*"`, so the library already had the
  brighter template; only the black cubemap is in question.)
- **supported hypothesis:** the black cubemap removes the image-based (sky) light a Starfield PBR surface gets, and the
  underground template adds little ambient, so a surface away from a placed light is near black. Not a material bug:
  the same materials look right under the lamp and under the exterior sun (playtest row 11 picture).
- **unresolved:** the exterior at night. The overlay worldspace copies LC172World (Mars) and its cells set no lighting,
  so night there is Mars's own night; no capture compares a converted object with vanilla ground at night yet.
- **verified (PC, 18 Oct, SfInspect envmaps on Starfield.esm):** 302 vanilla interiors use blackcube.dds too (11,176
  set none, 425 LGT_CubeMap_ShipEditor_001, 25 Cell_CaveCube); hall-type cube Cell_HiTechHallCube.dds is used once
  (ssPirateShip01Interior). A black cubemap alone is therefore not proof of the cause; the in-game A/B decides. If the
  hall cube leaves the library dark, the next suspects are the template's ambient and the image space.
- Comparison build (PC, offline, not installed): integ_1019_liblight_doors, FO4Port.esm 5204188f, one record changed
  against integ_1019_doors (CELL FO4Port_BostonPublicLibrary02 XEMP blackcube -> Cell_HiTechHallCube); a control
  rebuild with nothing set is byte-identical to integ_1019.
- Change (this branch): Fo4Export writes the FO4 cell's lighting block (cell XCLL + template, by reflection) into each
  export; SfInspect `envmaps` lists the environment maps vanilla interiors use; ENV_MAP is a per-cell lighting.json key.
  Next: pick a dim vanilla interior cubemap and a brighter template from `envmaps` / `templates`, rebuild the library
  only with `{"BostonPublicLibrary02": {"ENV_MAP": "<vanilla>", "LIGHTING_TEMPLATE": "006658"}}` and compare in game
  against the current build, then map FO4's ambient level to the template per cell.
- **verified (in game, owner, 18 Oct 19:32Z):** with only the library's ENV_MAP changed to
  `Data\Textures\Cubemaps\Cell_HiTechHallCube.dds` (FO4Port.esm 5204188f, template ShipInteriorLT 006658, image space
  122393 unchanged) the owner reported "Lighting looks fine". The hall cube becomes PluginSpike's default ENV_MAP for
  every converted interior; the other interiors (Vault 111 above all, on the darker template) are not yet seen with it.
  Variants B (image space 005322) and C (B + DefaultLightingTemplate 0300E2) were built and not needed.

## 2026-10-18 Claude-cloud: black patches on floors and walls (debris decals drawn opaque)
- **Seen (owner, 18 Oct):** hard-edged black patches in debris and decal patches: library, Cambridge Polymer and Concord
  road floors, Fort Hagen 01 walls.
- **verified (converted files, integ_1011):** `bldfloorconcdebris02alpha.mat` was a cutout at AlphaTestThreshold 0.024.
  Its opacity map never goes below 28, so nothing is cut. The texels with alpha 64-128 (half the map) have colour
  luminance 1 of 255, so they are black.
- **verified (PC probe, clean-master depot, main 2906601):** DebrisPileLargeConc01-06 shape `Decals:10` uses
  BldFloorConcDebris02Alpha.BGSM, header bytes 32..51 = `00 06000000 07000000 06 01 01 01 00 00 01 00 01 ...`: no blend,
  alpha test ref 6, alpha test on, decal (47) on, decal no fade (49) on. The shape has flags2 0x21 (vertex colours), no
  NiAlphaProperty, and vertex alpha 0..48. Its other shapes (BldConcChunkies01, DirtRubbleBrick01) have ref 128 and no
  alpha test, blend or decal flag.
- **supported hypothesis:** FO4 draws decal-flagged alpha-tested materials as overlays, with opacity = texture alpha
  times vertex alpha, so this one is at most 19 % opaque. The converter treated it as an opaque cutout.
- **Change:** a BGSM that is decal plus alpha test now converts like a blended one, through the decal template. A shape
  with vertex colours that never reach full alpha gets its own decal material with the opacity map multiplied by its
  peak vertex alpha under `vadecals/a48/` (a peak of 0 skips the shape). The rim fade itself is not reproduced. Not yet seen in game.

## 2026-10-20 Claude-cloud: doors_out2, the first door-exit campaign (job 6, #383)
- **Run (Install session's report, 20 Oct 04:33Z):** queue `D:\Modding\testqueue_v6c_out\doors_out2`, pinned build
  9af962d2 from wt_nightrun c0024fa, installed v6c set, 19 Oct 18:02 to 18:43 local; 8 OUT legs, no crash, no dump.
  The judge at c0024fa gave PASS 0, FAIL 1, INCONCLUSIVE 7: all 7 were `WORLD` (player in FF00552F, marker in 02000803).
- **verified (judge fault, fixed in #383 daff232):** a persistent reference reports our base WRLD while the player stands in
  the overlay's runtime instance (JOURNAL 2026-10-16 "Step 0 probes" (a) and (e); docs/terrain/door-arrival-position.md
  already warned that equal world ids are not the success check). daff232 accepted any runtime (FF) player world for
  any plugin marker world; Codex held that (an FF prefix does not say which WRLD it instantiates), so from the next
  commit the judge crosses worlds only for a pair the operator pins: `judge --world-instance FF00552F=02000803`.
  Without a pin an OUT leg in another world stays INCONCLUSIVE WORLD, as at c0024fa.
- **verified (re-judged on the PC at daff232, read-only, 20 Oct ~04:50Z; the c0024fa output kept as
  door_rounds_judge.c0024fa.json):** PASS 5, FAIL 3, INCONCLUSIVE 0, NOT_RUN 0. The run saw only the one pair
  FF00552F / 02000803, so the pinned rule should give the same verdicts (supported; not re-run).
  PASS: 0000 ParsonsState01 (0.00 m xy, 0.01 m z), 0001 Vault114 (0.04, 0.10), 0002 Vault114 (0.28, 0.02),
  0003 BostonPublicLibrary02 (0.00, 0.00), 0005 MuseumOfWitchcraft01 (0.00, 0.02).
  FAIL: 0004 Vault95 STAYED (interior cell 06007D12); 0006 MuseumOfWitchcraft01 WRONG_PLACE (0.0 m xy, 16.4 m z);
  0007 PrydwenHull01 WRONG_PLACE (0.0 m xy, 71.7 m z). The world check had hidden 0006 and 0007. An earlier version of
  this entry and of #383's description guessed "7 PASS" before the re-judge: **wrong**, corrected here.
- **What the code says about 0006 and 0007 (verified from source):** the expected position is the exterior marker's own
  record position plus the build's merge, and the merge has no z (`vmad_patch.merge_offset` returns (dx, dy, 0.0)), so
  the expected z is the marker's record z. The judge's tolerance is 3.0 m on z. The runner never scores the exterior
  arrival: an OUT leg's only runner point is `inside_arrival`, the start inside after the coc, so its PASS says nothing
  about where the door put the player, in z or otherwise. With 16.4 m and 71.7 m off, the tolerance is not the question;
  the marker height or the landing is.
- **supported hypothesis, unchecked:** the player arrived exactly over a marker that sits on a raised structure (the
  Prydwen's hull on its mooring, an upper level at the museum) and ended at another height, most likely below it with
  that structure missing or without collision in the converted exterior. **unresolved:** the sign of each z miss
  (`got.pos` against `pos` in door_rounds_judge.json) and what stands under each marker in game.
- **FAIL STAYED stands, 0004 Vault95 OUT:** after an activation the runner proved, the ack and the exterior marker's
  resolve, the player was still in interior cell 06007D12. The runner's PASS is only its check of the leg's start
  point (`inside_arrival` z -11.20 against -11.14). **unresolved:** why the exit door left the player inside (that
  attempt's papyrus.log: a `refused` line, or no `MoveTo returned`).
