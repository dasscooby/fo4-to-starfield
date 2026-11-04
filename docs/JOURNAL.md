# Evidence journal

Newest last. Each entry: date, versions, what was done, the result, and where the evidence is.

## 2026-10-06: WP-00 recon (Fallout 4 1.10.163, Starfield 1.16.244)

**Done:** read-only scan of `Fallout4.esm` and `Starfield.esm` record trees, every BA2 name table in both games, and
sample NIF headers (`scripts/recon.py`, `scripts/recon_physics.py`). About 9 s runtime.

**Result:** see [FORMAT-GAP.md](FORMAT-GAP.md); raw data in [measurements/](measurements/).
Headlines: plugin form versions 131 vs 581; 116 of 137 record types shared but field overlap mostly
25â€“60%; no `LAND` or `SNDR` in Starfield; NIF BS 130 vs 175 with external `.mesh` geometry; Havok packfile vs
tagfile; `.bgsm` vs `.mat`/`.cdb`.

**Open questions it raised:** meaning of the `.mesh` header fields (S1); how Starfield custom worldspaces get
terrain (S5); whether Mutagen's Starfield alpha can write usable plugins (S2).

**Tooling gathered:** NifSkope (fo76utils) dev11 2025-12-30, xEdit 4.1.5f (includes `xSFEdit`),
PyNifly V29.1.0, Blender 5.2.2, .NET SDK 9, Starfield Creation Kit (Steam 2722710), SFSE 0.2.21 (manual from Nexus).

**Prior art search:** no public Fallout 4 â†’ Starfield conversion project was found on GitHub or the web.
Related open tooling is listed in the README.

**Source reading (no code run):** fo76utils/nifskope has `.mesh` readers (`src/io/MeshFile.cpp`), a meshlet
generator (`lib/meshlet.cpp`, spell *Generate Meshlets*), Havok spells (`src/spells/havok.cpp`) and the
full `nif.xml` with Starfield blocks; no `.mesh` writer was found. That is why S1 is the keystone spike.

## 2026-10-06: repo published

Public repo created. Pushing the CI workflow was rejected (token lacks the `workflow` scope), so it ships as `ci/github-actions-ci.yml` and is **not active**; the guard and tests were run locally (5 tests, guard ok, `um publish check` 21 files / 0 failures).

## 2026-10-07: S1 mesh writer (offline part)

Fallout 4 1.10.163, Starfield 1.16.244. Built `sfmesh`, `nif`, `sfnif`, `convert_static` and checked them against vanilla
files: 3,000/3,000 `.mesh` byte-identical round trips; meshlet rule verified on 4,000 meshes; NIF container 1,500 + 1,500;
`BSGeometry` 20,224/20,224; `MaterialID` hash found (CRC32, 60/60); tangent-sign mapping 98.8%. Converted the real FO4
`ChairPatio01.nif` (1,034 verts / 940 tris -> 12 meshlets, 0.91 x 0.83 x 1.04 m) and re-parsed the output successfully.
Details: [spikes/S1-mesh-writer.md](spikes/S1-mesh-writer.md). Corrected an earlier claim: base-game NIFs are BS 173, not 175.
Not done: NifSkope check (L1), in-game check (L2/L3), units (S4).
Environment: Creation Kit copied next to Starfield.exe; .NET 9 SDK installed; Blender still pending; SFSE 0.2.21 and the
Starfield Blender Extension 1.6.0 Beta 5 downloaded to `C:\Modding\tools`.

## 2026-10-07 (later): S2 / S4 / S9 offline results

Mutagen Starfield alpha writes a loadable-looking plugin (form version 576). Unit scale measured at ~70 units/m from
chair/stool/couch/barrel. Controlled Folder Access blocks writes to Documents, so loading uses a `- Main.ba2` built with the
official Archive2 instead of loose files + ini. Installed `FO4Port.esm` + `FO4Port - Main.ba2` into a Starfield test install
(reversible via `scripts/deploy_starfield.py`). **Next: launch the game and run the 5-step check in
[spikes/S2-S4-S9-plugin-units-loading.md](spikes/S2-S4-S9-plugin-units-loading.md).**

## 2026-10-07 (evening): first converted asset renders in Starfield

Launched Starfield 1.16.244 from Steam, loaded an existing save (backed up first to a folder outside the game), opened the
console and ran `player.placeatme 02000800`: the converted Fallout 4 patio chair appeared with correct orientation, size,
lighting and shadow. Plugin slot was 02. Lessons: (1) an early misreading of the console's "selected reference" label as our
FormID wasted two rounds; (2) Starfield ignores `SendInput` keyboard events but accepts `keybd_event`; (3) Windows Controlled
Folder Access blocks writes to Documents, so assets ship in `- Main.ba2`. Next: real materials (S3), collision (S6), then
a record translation framework (WP-08) and a bulk static converter.

## 2026-10-07 (night): S3 materials confirmed in game

Built `textures` (BC4/BC5 decode, DDS writers, texconv wrapper) and `convert_material` (BGSM parse, `.mat` cloning with fresh
object IDs). Archive2 `-includeFilters` ignored in practice (extracted 23 GB + 5 GB into scratch folders; deleted). Chair now
renders with its original texture in Starfield. Deploy script builds `FO4Port - Textures.ba2` (DDS format) as well. Note: first
console use after a launch shows an achievements warning; dismissed with E. See [spikes/S3-materials.md](spikes/S3-materials.md).

## 2026-10-07 (late): S6 box collision confirmed in game

Found a deterministic rule for patching a vanilla box-collision Havok blob (36 box-dependent float words, regressed over 369
vanilla blobs). Chair now has collision: two overlapping copies pushed each other apart and tipped; walking into them moved
them. Body is dynamic (inherited from the template). Lessons: the console achievements dialog needs a long E press and blocks
other input while open; `placeatme` spawns at the player's feet, so the player gets pushed out by the new collision.

## 2026-10-07 (play-test by the user)

Batch build (400 Set Dressing props) installed. Human play-test: shadows look good, props have collision, and they do **not**
move when pushed. Corrected the S6 note that called the bodies dynamic. Batch converter (`src/fo4sf/ba2.py`, `pipeline.py`,
`scripts/convert_batch.py`, manifest-driven plugin writer) committed with this entry: 400 converted in ~30 s, 6 skipped (no
static geometry), 146/151 materials full, 5 placeholder.

## 2026-10-08: Vault 111 first light

Exported `Vault111Cryo` with Mutagen (3,087 refs), converted its 268 models (234 ok), wrote a cell with 1,365 refs + 132 vanilla
lights and loaded it with `coc FO4Port_Vault111Cryo`: layout, scale and textures correct; over-exposed. Confirmed Starfield
placements are in metres. Lessons: Mutagen needs `WithKnownMasters` once Starfield.esm is a master; the achievements dialog
appears on the first console command of a session and steals keystrokes (close console, hold E, reopen); Shift must go through
the same legacy input path as the key. See [spikes/WP10-vault111-first-light.md](spikes/WP10-vault111-first-light.md).

## 2026-10-08: architecture collision (surface boxes)

Thin boxes behind flat surfaces, one body per box on child NiNodes; the player walks on the converted vault floor. Input guard
correctly refused to type when the user's window had focus.

## 2026-10-08: collision v2 (voxel boxes), effects excluded

See spikes/WP10-vault111-first-light.md. Automation lesson: chained keystrokes drift when a dialog or load intervenes; run console steps one at a time with a screenshot between them.


## 2026-10-08: Vault 111 in colour

Material tint strength (Color.w) was 1.0 and replaced every albedo; set to 0. Texture-set materials, effect-shape skipping, neutral fallback, bounded voxel size. See spikes/WP10-vault111-first-light.md.


## 2026-10-08: three interiors in one plugin

Vault 111, Vault 81, Red Rocket cave. Rock smoothness, alpha cutouts, blended overlays skipped, no collision on vegetation. See spikes/WP10-more-interiors.md.


## 2026-10-08: collision maps + glass

Probe maps (teleport + OCR height readback, `scripts/game/probe.ps1`): Vault 81 28 PASS / 2 HELD; Vault 111 17 PASS / 2 HELD / 6
small drops onto lower stair steps (0.6-1.6 m, now classed `LOWER`); Red Rocket cave 8 PASS / 10 HELD (platform and ramp tops
above their origin) / 1 MOVED / 1 unread. **No fall-through anywhere.**
Glass: FO4 effect-shader glass (textures inline in `BSEffectShaderProperty`, or a `.bgem`) is converted by cloning the vanilla
glass material `OPMineMaskBox01Glass.mat` (shader model `1LayerEffectGlassNoFrost`), opacity 0.15, smooth roughness. Vault 111
glass panes and cryo-pod windows convert. Vanilla shader-model survey: `1LayerStandardDecal` (1,133 mats) is the next target for
FO4 alpha-blended overlays/decals (Parsons wallpaper cracks, vault greebles).
In game (Vault 111): the cryo-pod window is see-through to the seat inside ([screenshot](media/vault111-cryopod-glass.jpg)); whether the glass surface itself is drawn (reflection/tint) is not yet confirmed at this distance. 2,551 models, 1,013 materials incl. 12 glass.


## 2026-10-08: interior lighting

Every converted interior looked washed out and pink. The cause was cells with no ImageSpace and no EnvironmentMap: auto-exposure
metered against a bright default sky reflection. The plugin writer now sets both, following vanilla `DR017UndergroundInterior`:
ImageSpace `LGT_LUT_Int_Gen_v01_curve` 122393, EnvironmentMap `Data\Textures\cubemaps\blackcube.dds`. The FO4 lights become
`LGT_ShipInterior_Omni_NS_Neutral_2k` (03D38C) omnis, merged within 2-3 m.

That fixed the wash and the tint but made big rooms very dark. Changing the lighting template to `ShipInteriorLT` (006658)
fixed Parsons, the Prydwen and Vault 114 ([before](media/lighting-parsons-before.jpg) / [after](media/lighting-parsons-after.jpg),
[Vault 114](media/lighting-vault114.jpg)). The same template over-lit Vault 111, which keeps the darker `KreetBase01LGTtemplate`.
Settings are now per cell through `<staging>/lighting.json` ([example](lighting.example.json)). Lookup order is cell, `"*"`,
environment variable, built-in default.
`SfInspect imgs` lists vanilla image spaces by how many cells use them. `LGT_LUT_Int_Gen_v00_curve` gave a green cast and was
rejected.
Open: Vault 111 metal still reads as chrome (likely FO4 spec/gloss -> roughness or metalness, to check next). The tour script
can walk off the edge of a cell into the void.

## 2026-10-08: every material was fully metallic

The "chrome" look on all converted surfaces (and part of the "weird textures" report) came from the template material
`MetalIronCast01.mat`. Its texture set enables a constant metalness of 1.0 (`BSMaterial::TextureReplacement` index 4).
`build_mat` only rewrote the `Summary` block, which is informational: the engine reads the component. `build_mat` now writes the
metalness value into the component (slot map: 0 albedo, 1 normal, 2 opacity, 3 roughness, 4 metalness, 5 AO), with a test.
1,002 staged materials were patched in place. The script is `C:\Modding\research\s3\zero_metal.py`; a full reconversion gives
the same result.
Vault 111 [before](media/metal-v111-before.jpg) / [after](media/metal-v111-after.jpg), [tour frame](media/metal-v111-tour.jpg):
cream walls, blue pipes and orange fittings now read like Fallout 4. [Hotel Rexford](media/rexford-lit.jpg) is readable but
greyer than the warm original (next: image-space LUT / colour check).

## 2026-10-08: doors (experimental, off by default)

Hinged FO4 doors can be rebuilt on the vanilla Akila door rig. In game they sit in their frames, show "DOOR / Open (E)",
toggle Open/Close and block the player, but the leaf does not swing yet. Because a door that blocks the doorway is worse than a
walk-through one, rigging is off by default (`Converter(rig_doors=True)` to test). Details, clues and next steps are in
[WP-doors-research](spikes/WP-doors-research.md). New: `nif.door_hinge` / `descendants`, `sfnif.build_door_nif`,
`convert_static.convert_door`, DOOR records in the plugin writer (with origin offset and bounds), `tests/test_doors.py`,
`SfInspect doorprops`.

## 2026-10-08: doors, attempt 2

A vanilla Starfield door swings inside our converted cell, so the remaining problem is our door NIF or record.
`sfcollision.keyframed()` turns the leaf's static box into a vanilla-style keyframed body. With it the doorway is passable
again and the leaf rests in FO4's rest pose, but I could not aim scripted input at it to confirm a swing. Next: a
one-door test cell with a fixed spawn. Rigging stays off by default; the deployed build has walk-through static doors.

## 2026-10-08: doors open

FO4 hinged doors now open and close in Starfield (24 door models in our 8 cells). The missing piece was the leaf's
collision body: it must be keyframed like a vanilla door leaf, not static. Verified in a one-door test cell and in Hotel
Rexford: closed at rest, swings on E, walk through ([screenshot](media/door-rexford-opens.jpg)). Enable it with
`convert_batch.py --starfield-data`. Next for doors: sounds, frame collision, and a sliding template for vault doors.

## 2026-10-08: alpha-blended overlays become decals

FO4 materials with alpha blending (sign lettering, wall cracks, grime and greeble overlays) were skipped. They now convert
to Starfield decal materials. The diffuse alpha becomes the opacity map, and the `.mat` is cloned from the vanilla decal
`AKDecalPrintedTechWall01.mat` (shader model `1LayerStandardDecal`; `cm.DECAL_TEMPLATE_MAT`,
`Converter.decal_material`). Re-converted 222 models with blended shapes (141 new materials, 0 failures, 84 s).
In game, the Vault 81 wall placards now show their lettering, "OVERSEER / COMMISSARY"
([screenshot](media/decal-vault81-placard.jpg)). It reads dimmer than in FO4, probably because FO4 sign letters use glow
or emissive maps, which are not converted yet.
Seen on the way: FO4 double doors (`PaintedWoodDoorDouble01`, Parsons) rest with their moving leaf open
([comparison](media/decal-parsons-cmp.jpg)). Their FO4 rest pose is not the closed pose. Next door fix: take the leaf pose
from the end of the FO4 `Close` sequence.

## 2026-10-08: door rotation fix (offline; not yet verified in game)

The foreground guard tripped (another app was in front and Starfield was not running), so this tick was offline only.
- The Parsons double doors, which looked like they rested open, are not a rest-pose problem. New
  `nif.door_closed_rotation` reads the end of the FO4 `Close` sequence (Euler or quaternion keys, tested), and for every
  door checked the closed pose equals the rest pose.
- The real suspect is the reference-rotation direction used to shift door origins. Bethesda angles turn clockwise, and the
  plugin writer rotated counter-clockwise. Doors at 0 and 180 degrees (all the Rexford tests) are the same either way.
  Parsons' 135, 225 and 315 degree doors get shifted to the wrong spot.
- `RotateOffset` now uses the clockwise convention. Built in staging only and not deployed. Next in-game check: the Parsons
  double doors sit closed in their frames.

## 2026-10-08: four more interiors converted (offline; tours pending)

The guard tripped again (another app in front), so this was offline only. Exported and converted four more FO4 interiors:
Valentine's Detective Agency (`DmndValentines01`), `SuperDuperMart01`, `Vault95` and `CambridgePolymerLabs01`. Twelve cells
in total.
- Full batch over the 12 cells (with doors and decals on): 3,389 models converted, 18 failed, 408 s.
- Almost all failures are glass-only lab props (beakers, test tubes, chemistry set). Their effect textures are not named
  "glass", so they are skipped; next material fix.
- Plugin: 3,359 statics and 30 doors. New cells: Valentine's 268 refs / 8 lights, Super Duper Mart 4,185 / 113,
  Vault 95 4,353 / 172, Cambridge Polymer 3,206 / 165.
- Staged in `C:\Modding\staging\multi` but not deployed. In-game tours and the Parsons door-rotation check run when the PC
  is free.

## 2026-10-08: more glass (offline)

The guard tripped again, so this tick was offline. FO4 lab and household glass (beakers, test tubes, bottles) uses an
environment-mapped effect shader with its own normal map, and the base texture is not named "glass". Those shapes were
skipped. Glass detection now also accepts effect shaders with a cubemap and a normal map (never textures from the effects
folder).
- Glass materials: 12 -> 33. All are real glass: chemistry set, beakers, test tubes, Nuka bottle, watch and magnifier
  glass, jukebox front, water-cooler jug, light covers, vertibird canopy.
- Batch failures: 18 -> 10. Left: wall-stain gradient effects, a strobe flash, an oil puddle, and two plates without static
  geometry.
- Staged and not deployed yet.

## 2026-10-08: four new interiors toured; static collections; door rotation verified

There had been no user input for 18 minutes, so I ran the in-game checks. The guard still checks before every keystroke.
- **Door rotation fix verified.** The Parsons double doors (135 and 225 degrees) now sit closed in their frames
  ([screenshot](media/parsons-doubledoors-closed.jpg)). Bethesda reference rotations are clockwise.
- **Tours of the four new cells:**
  - [Valentine's](media/tour-valentines.jpg): office, beams, peeling posters as decals.
  - [Super Duper Mart](media/tour-superdupermart.jpg): Nuka-Cherry sign, posters, carts, Protectron pod. The sales floor
    is very dark.
  - [Vault 95](media/tour-vault95.jpg): reads like FO4.
- **Cambridge Polymer Labs: the player fell through the floor at the spawn.** The floor there is inside a FO4
  `StaticCollection` (SCOL, merged mesh `meshes\SCOL\Fallout4.esm\CM*.nif`), and SCOLs were never in the batch's
  `--types`. The 12 cells hold 245 SCOL references (93 meshes), all missing until now.
  - Fix: `StaticCollection` is now a default type, and `meshes\scol\` gets the architecture surface collision.
  - All SCOL meshes convert (3,490 models in total).
  - Cambridge now spawns and stays on the floor (OCR z 3.87, stable after 6 s), and the atrium renders
    ([screenshot](media/cambridge-atrium.jpg)).
  - Earlier cells may also have had gaps from missing SCOLs; worth a re-probe.

## 2026-10-08: FO4's own collision transplanted into Starfield (built; in-game check pending)

The user's report: collision, doors, stairs, "everything". The root cause is that every converted body was an axis-aligned box
guessed from the render mesh, so stairs, ramps and angled surfaces could not be represented. New approach: use the collision
Bethesda authored for FO4.
- `hkpackfile.py` reads FO4's Havok 2014 packfiles and `fo4collision.py` decodes their shapes (compressed meshes, convex
  polytopes, body transforms). Verified: the decoded PryCatwalkStairs01 mesh matches the render bounds exactly, and its
  stair is a 40-degree ramp.
- `hktagfile.py` reads Starfield's Havok 2019 tagfiles, with type layouts taken from the file's own TYPE section.
  Finding: Starfield's `hknpCompressedMeshShapeTree` has the same layout as FO4's (sections, primitives, packed/shared
  vertices, compressed AABB trees). Only a few section fields are packed differently.
- `meshcollision.transplant` rebuilds a Starfield tagfile around FO4's mesh data. A vanilla Starfield static from the
  user's install is the container; the optional SIMD tree is off.
- 1,960 of 3,490 models now carry FO4's exact collision mesh (0 errors). 317 still use oriented/axis boxes (collision not on
  the root or a moved body), and 1,213 props keep a single box or none.
- Oriented-box tools were also added (`sfcollision.oriented_surface_boxes`, `convex_obb`). They are not used by default.

In game: **not verified.** The first launch with this build ended with Starfield gone twice, with no crash log. It may be
a startup crash caused by the new collision, or the user closing it. The mod was uninstalled so the user's game starts
clean. Also: `cycle.ps1` closed the user's own open Starfield session (sitting in the character menu). It now refuses to
close a game it did not launch (PID file).
Next: confirm whether the transplanted collision crashes the game, using a test cell holding one transplanted model.

## 2026-10-08: transplant fixed against vanilla Starfield (offline)

The user was active, so this was offline only. Compared the transplant with 246 vanilla Starfield mesh shapes:
- `numShapeKeyBits` equals the tree's `bitsPerKey` in vanilla (224 of 246; the other 22 not yet examined); the transplant
  had kept the template's 2 (the stair needs 10), a likely cause of the suspected crash.
- `numTriangles` is 0 in vanilla, and the interior bit field holds `maxKeyValue + 1` bits.
- Every vanilla mesh has a SIMD tree. It is now generated (`build_simd_tree`): a 4-wide AABB tree whose leaves are
  triangle shape keys `section << 8 | primitive << 1 | quad half`. That formula reproduces FO4's `maxKeyValue` exactly.
- New `decode_sf_mesh` reads a Starfield blob back. Round trip on the Prydwen stair: 756 / 756 triangles, max vertex
  difference 0.0 m. New tests cover the section mapping, the SIMD tree and the varints.
Reconverted and staged; not deployed. Next: in-game check (startup, a single transplanted model in the test cell, then
stairs and doorways).

## 2026-10-08: native FO4 collision verified in game (Prydwen stairs)

First in-game run of the native collision build (the user freed the PC). The game starts, the Prydwen loads, and the
player stands on native floors.
- **Stair climb (2 flights, PryCatwalkStairs01 + PryCatwalkStairsEnt01):** OCR positions go from z -10.97 at the bottom
  to z -7.31 on the upper deck (3.66 m), then along the deck to y 42.3, where the player is stopped by a crate stack (solid,
  as in FO4). ([stairs](media/prydwen-stairs-native.jpg), [deck](media/prydwen-upper-deck-crates.jpg))
- **What it took** (each found from a failed climb):
  1. Several FO4 collision objects can share one physics system. Each owns one body, given by the body index stored in
     the object, so each object now gets only its own body.
  2. FO4 shapes live in the space of the object's node. The body cinfo transform is not a placement (a vault crate's
     shape already matches its render mesh but carries a 0.29 m body offset). So bodies go on child nodes with the FO4
     node transform, and the Starfield body is identity, as in vanilla.
  3. Collision layers are kept. FO4 and Starfield share layer indices except 37 and 43, which are rejected explicitly.
     The stair's `C_Ramp` body is `L_STAIRHELPER` (31); copied as static, it acted as a wall at the foot of the stairs.
  4. The template is Bethesda's own multi-shape test file (`test_fbx_collision_same_node01.nif`), whose type table covers
     every shape.
- Coverage across 3,490 models: 2,648 native, 154 boxes, 688 single box or none. Recorded fallbacks:
  hknpDynamicCompoundShape 266 (Codex's compounds work), hull topology 60, sphere 9, and an IndexError in 44 (to fix).
- **Doorway (Hotel Rexford door 10AD60) with the native build:** closed at rest, opens on E, and the player walks through
  into the bathroom (OCR x 46.90; the door is at 44.32). ([sheet](media/rexford-door-native.jpg))

## 2026-10-08: route runner (owner issues #29, #30)

A movement test that FO4 data scores, replacing "press W, read once".
- `scripts/game/routes.py` builds routes per cell from FO4's own collision. Stairs use the `L_STAIRHELPER` ramp body, or
  the 20-50 degree collision triangles if there is none: start 0.8 m before the low end, face the high end, expect a rise.
  Doors start 1.6 m in front, press E, and must end 1 m past the door plane.
- `route_run.ps1` walks each route (guarded input, OCR position, screenshot). `route_eval.py` scores PASS / STUCK / FALL /
  BLOCKED / UNREAD and rejects impossible OCR reads.
- Lessons from the first runs, all bugs in the test rather than the port:
  - a long walk crosses mirrored flights (up one, down the other), so walk time is sized to the run at running speed
    (~4.6 m/s);
  - OCR can drop a minus sign or shift columns;
  - the repo's `readpos` needs the numpy venv (`FO4SF_PYTHON`).
- **Prydwen, first 12 stair routes (PryCatwalkStairs01 x10 at 90/180/270 degrees, PryCatwalkStairsEnt01):** 9 PASS (each
  climbs 1.87 m to the landing; the 180-degree flight 2.6 m). 2 UNREAD (OCR misreads x around +0.5, the same end point as
  the passes). 1 harness flake (the console reply was not printed before the screenshot); rerun needed. No STUCK and no
  FALL attributable to collision. ([foot](media/route-prydwen-stair-foot.jpg), [top](media/route-prydwen-stair-top.jpg))
- Collision decoder: degenerate primitives and invalid shared indices are skipped or rejected (the merged-SCOL IndexErrors).

## 2026-10-08: routes for the whole slice (offline)

The user was in the game, so this tick was offline. Reconverted with the decoder fixes: 2,716 native, 137 boxes, 637 single
box or none. 7 merged SCOL meshes carry junk shared-vertex tables and are rejected (recorded), not decoded. Routes built
for 11 cells: about 279 (127 stairs, 102 doors). Red Rocket has none; it is checked with the probe map instead. Stairs
whose FO4 collision has no ramp are listed per model for a separate check: Vault 111 `V111RPit2StairsRaisedMid02` x4,
Rexford `BldWoodBSmStairs03TrimL/R`, Vault 114 `VltStairWellCorIn01`/`VltStairWellDoorHalf01`, Cambridge
`BldWoodPSmStairs02TrimL`. Staged, not deployed; the in-game runs follow when the PC is free.

## 2026-10-08: Vault 111 routes

Ran all 11 Vault 111 routes on the current native build: **8 PASS**, 1 UNREAD (OCR column swap), **2 STUCK**.
- PASS: the pit stairs (`V111RPit2StairsRaisedMid01`, rise ~1.0 m, five copies), the wall stairs (`V111RPitWallStairs01`,
  two), and the door `SwitchDoorExSmLatch01` (opens, player 1.41 m past the plane).
  ([pit stairs](media/route-v111-pit-stairs.jpg), [door](media/route-v111-door.jpg))
- STUCK: both `V111HallStairs01`, rise 0.26 m of 1.55 m ([stuck](media/route-v111-hallstairs-stuck.jpg)). Its FO4 stair
  helper is placed correctly (unrotated `rampdummy` node), but it is about 46 degrees: rise 1.93 m over 1.85 m. The
  passing Prydwen helpers are about 31 degrees. Likely Starfield's character controller does not walk slopes that steep,
  where FO4's did.
- Experiment queued (not run; the user came back): rebuild without the helper (`FO4PORT_DROP_STAIRHELPER=1`, diagnostic
  only) and check whether the 0.30 m treads can be stepped. If not, flatten steep helpers to a walkable angle.
  **The installed build currently has that diagnostic version of V111HallStairs01.**

## 2026-10-08: compound, capsule and sphere collision (offline)

The user had been active within 10 minutes, so this tick was offline.
- **Compounds:** `hknpDynamicCompoundShape` bodies are flattened. Each instance becomes its own native Starfield body, with
  the instance transform baked into the shape: convex children fully, mesh children translation only (a rotated mesh
  instance is rejected and recorded). Instance layout from Codex's `fo4_compounds.py`, which is cross-checked against
  PyNifly and real FO4 files.
- **Capsules:** FO4 capsules carry a full polytope hull plus radius, so they take the convex path.
- **Spheres:** native `hknpSphereShape` from Bethesda's test-file template (one centre vertex, radius as convex radius).
- Coverage: **3,006 of 3,490 models native** (up from 2,716), 117 boxes, 367 single box or none. Recorded errors: 9
  open hulls, 16 junk shared-vertex tables, 2 `hknpConvexShape`.
- **Not yet verified in game.** Next with a free PC: startup, then a prop-heavy room (compounds are mostly props), then the
  Vault 111 hall-stair experiment.

## 2026-10-08: steep FO4 stair helpers flattened; Vault 111 hall stairs climb

In game: the compound / capsule / sphere build starts and loads Vault 111.
- `V111HallStairs01` without its helper is still stuck: the 0.30 m treads are too tall for Starfield's step-up.
- Fix: `meshcollision._flatten_helper`. An `L_STAIRHELPER` hull steeper than 40 degrees (measured in its collision
  node's orientation) is stretched: its whole bottom edge moves by one vector along the ramp, so the top stays where FO4
  put it, the width is unchanged and the slab stays planar. Planes are recomputed from the faces. This helper went from
  44.7 to 38.9 degrees. Starfield's controller stops at roughly 45 degrees; FO4 allowed steeper.
- **Both hall staircases now PASS** (rise 1.94 / 1.95 m) ([screenshot](media/route-v111-hallstairs-pass.jpg)). Vault 111 is
  10 of 11 routes passing; the 11th was an OCR misread.
- New tests: slope limit reached, top and width kept, gentle helpers untouched, plane orientation. Also: `route_eval`
  reads BOM-prefixed route files.

## 2026-10-08: Vault 81 routes; door routes from the leaf

Deployed the full build with stair-helper flattening and ran Vault 81's 16 routes.
- **Stairs: 11 of 11 readable PASS** (2 more UNREAD from OCR). Hall stairs `VltHallResStairs01` / `VltHallUtilStairs01`
  rise 1.83 m; catwalk flights `VltCatwalkStairsFront01` / `...FrontBottom01` rise 1.6-2.8 m.
  ([catwalk](media/route-v81-catwalk-stairs.jpg), [hall](media/route-v81-hall-stairs.jpg))
- **Doors: the three cave stall doors (`BRStallDoor01`) failed because the route was wrong**, not the door: routes assumed
  every door faces along local +x (true for the Rexford wooden doors), and these face along y, so the runner started
  inside rock. Door routes now take the facing from the **closed leaf** (the moving branch's bounds; the leaf spans the
  opening, so its thinnest horizontal axis is the normal), cross the middle of the opening, and run once from each side
  (a leaf may swing towards the player). The verified Rexford door still gets its proven route (x 42.75, heading 90).
- The rerun of the 6 Vault 81 door routes is pending (the user was back).

## 2026-10-08: broken FO4 hull topology rebuilt (offline)

The user had been active within 5 minutes, so this tick was offline. Some FO4 convex hulls have faces that don't close
(an edge without its opposite), so they fell back to boxes. `meshcollision.convex_hull_faces` rebuilds the faces from the
same vertices (convex hull, coplanar points merged into one polygon, wound counter-clockwise from outside as in vanilla
Starfield hulls), then planes and links are recomputed. Test: a cube plus an interior point gives 6 closed outward quads.
Coverage 3,012 native (+6). Left: 3 hulls that are probably flat, 16 merged SCOL meshes with the same junk shared-vertex
index (2130), and 2 `hknpConvexShape` bodies. Staged only; not yet in game.

## 2026-10-09: overnight routes: Vault 81 doors, Vault 114 (partial)

- **Vault 81 stall doors** (corrected door routes: facing from the closed leaf, both sides): 1 of 3 doors passes from both
  sides (1.25 m / 2.95 m through); the other two are BLOCKED from both sides (-0.4 to -0.6 m, i.e. stopped at the door).
  ([pass](media/route-v81-stalldoor-pass.jpg))
- **Vault 114** (24 of 47 routes ran before the user came back; run stopped):
  - Stairs: 7 PASS (subway hall stairs, subway platform, cinder block, stairwell; rise 0.9-5 m)
    ([subway stairs](media/route-v114-subway-stairs.jpg)).
  - 2 STUCK: `IndCatStairsFull01` (rise 0.08) and `VltGearDoorStairs01` (1.41 of 3.22)
    ([stuck](media/route-v114-catwalk-stuck.jpg)).
  - 5 UNREAD (OCR). One "PASS" with an implausible 31 m rise must be treated as unread: the plausibility check has to cover
    the scored rise too.
  - Doors: stall doors and `SubDoor01Right` BLOCKED from both sides ([blocked](media/route-v114-stalldoor-blocked.jpg)).
- Next: why these doors block, from the converted files (leaf swing, frame collision covering the opening), and the
  two stuck staircases.
- Correction: with the rise plausibility check, the Vault 114 "PASS" with a 31 m rise is UNREAD. Vault 114 stairs are
  **6 PASS**, 2 STUCK, 6 UNREAD. Route runner now saves `r<k>_pre.png` (just before E, shows whether the Open prompt is up)
  and `r<k>_open.png` (2.2 s after E) for every door route.

## 2026-10-09: no collision where FO4 has none; Vault 114 doors

- **Invisible walls removed.** 284 converted models have no collision at all in FO4 (rubble, debris, paper, signs,
  posters, plants, ponds, some vault trim). The converter still gave them a guessed bounding box, or surface boxes for
  architecture, which made walk-through clutter into invisible walls. Now they get none, as in FO4
  (`report.source = "fo4-none"`, 243 models in the current batch). Coverage: 3,012 native, 243 none as in FO4, 199
  single box, 36 surface boxes.
- **Found by the door test:** a stall door was blocked by the guessed box of a rubble pile in front of it. After the fix,
  stall door `04BDD2` passes from both sides (2.6 m through). Door results in Vault 114: subway door `SubDoor01Right`
  passes from both sides; stall doors `04BDDA` and `04BDD2` pass from both sides.
- **Evidence screenshots** (runner now steps in before pressing E, and looks straight ahead on doors): the passing doors
  show "DOOR / Open" ([prompt](media/route-v114-stalldoor-prompt.jpg)). Two stall doors placed at 90 degrees
  (`04BF66`, `04BF9D`) stop 0.45 m short from both sides with no prompt; the door's lower edge is at eye height
  ([raised](media/route-v114-stalldoor-raised.jpg)), so these instances seem to sit ~1.3 m too high. Their 270-degree
  twins are fine; suspect the door origin offset vs this placement. Open.
- One game exit without a crash record during a door route (the rerun of the same route was fine): watching for repeats.
- Correction: the "door raised ~1.3 m" reading for stall doors `04BF66` / `04BF9D` is unconfirmed. Follow-up views with pitch 0 looked steeply at the floor, so camera pitch from `setangle x` is not reliable enough to judge door height from one screenshot. These two doors stay open as BLOCKED, cause unknown.

## 2026-10-09: doors are fine, the test runner wasn't (Hotel Rexford 21/26)

Most door "BLOCKED" results today were runner bugs:
1. **Camera pitch.** `player.setangle x` turns the actor, but the first-person camera keeps its own mouse-look pitch.
   After some routes it was left looking at the floor, so E never reached the door; the "door raised 1.3 m" impression
   came from that too. The runner now levels the camera before every route (mouse fully up, which clamps, then down 700
   counts, calibrated in game).
2. **Console desync.** On a failed read the runner pressed the console key "in case it was open". If it was closed, the
   next route's typing went to the game ("p" opened Skills). Removed; `readpos` always leaves the console closed.
3. A brief `setangle x 0` for door routes made it worse; reverted to `x 10`.

With those fixed, **Hotel Rexford doors: 21 PASS / 4 BLOCKED / 1 UNREAD.** Every one of the 13 doors lets the player
through from at least one side ([prompt](media/route-rexford-door-prompt.jpg), [open](media/route-rexford-door-open.jpg)).
The 4 one-sided blocks (refrigerator, `UtilMetalDoor01`, `BldWoodPDoor02`, the entrance load door) are probably the side
the leaf swings towards. To confirm with the open-screenshot, then rerun all earlier door verdicts (Vault 81, Vault
114) with the fixed runner.
Rexford stairs (same session): 8 PASS; `BldWoodBSmRailStairs03L` reached 2.74 of 2.93 m.
- Reruns with the fixed runner: **Vault 114 stall doors `04BF66` / `04BF9D` pass from both sides** (the "raised door" was
  the camera); every Vault 114 door now passes. **Vault 81:** stall doors `19DA3A` (both sides) and `19DA38` pass;
  `19DA36` still BLOCKED (one side never moved, so the start is probably inside cave rock). Open.

## 2026-10-08 (evening): Parsons State Insane Asylum, prompt-seeking runner, load doors

First Parsons run: 26 of 36 door routes BLOCKED at almost exactly -0.48 m (standing at the closed door). Not the doors:
the screenshots show no "DOOR / Open" prompt because the levelled camera aimed over the door
([aim high](media/route-parsons-door-aimhigh.jpg)). Tilting 500 counts lower shows the prompt
([prompt](media/route-parsons-door-prompt.jpg)), so the fixed "up, then down 700" calibration does not carry between
sessions.

Runner changes (`scripts/game`):
- `prompt_visible.py`: detects the prompt's white title bar in a screenshot. `route_run.ps1` tilts down 150 counts at a
  time (up to 9 tries) until the prompt is on screen, then presses E. Results record `prompt`; `route_eval.py` reports
  a door that never showed a prompt as **NOPROMPT** instead of BLOCKED.
- Start reads far from the teleport target are re-read once. The runner stops if the start read equals the last route's
  end (stale read, console out of step). It happened once tonight: a "p" opened the Skills menu and 12 routes read
  the same position; closed with Tab, no skill points touched (0 available).
- `route_eval.py`: a start more than 3 m from the route start is UNREAD ("start not reached"). Starts under the floor
  (sunken `RWResStairs02` retaining-wall stairs, z -2.2) are moved by the engine to the cell entrance.

**Parsons rerun: every hinged door that was tested opens and lets the player through from at least one side**
([open](media/route-parsons-door-open.jpg)). Doors 13/14 to 47/48 pass on one side; the other side stops 0.6-1.7 m short
after the door opened ([swing side](media/route-parsons-door-swingside.jpg)). Same one-sided pattern as Rexford. No
Starfield door graph opens both ways (all 26 `*openclose*.agx` graphs have a single Open/Close), so the next experiment is
whether the runner stands inside the leaf's swing arc when it presses E.

**Real bug found: load doors swung open onto the void.** From the entrance the player walked through the entrance
load door (`BldWoodPDbDoorLoad01`) and fell to z -72. FO4 load doors never swing into the next space: activating one
teleports, and destinations are not ported yet. Fix in `pipeline.py`: `LOAD_DOOR_RE` load doors are not rigged and keep
their native collision (solid and shut). Each is reported per asset as `load_door: teleport not ported`, so the
missing behaviour is listed rather than silently dropped.

Stairs: 7 PASS; `RWResStairs02` STUCK twice (one ends in the dead tree's branches in the atrium); 5 routes start under the
floor (route generator to fix: needs a floor check).
- **Load door fix verified in game.** Rebuilt all 12 cells (only the 9 load-door models changed; no existing FormID moved)
  and deployed. The Parsons entrance double door now fills the doorway and is solid: walking into it stops the player at
  y 5.90, 0.4 m before the door plane ([before](media/route-parsons-loaddoor-before.jpg),
  [after](media/route-parsons-loaddoor-after.jpg)).
- **Test-environment trap: saves keep old references.** The save the test cycle loads still held the entrance door at
  its old rigged position (3.07, 6.37), because doors opened under the previous build are saved as changed references.
  The plugin itself had the right position (0, 5.486), checked by reading the REFR from the deployed ESM. For this
  test I moved the reference to its plugin position in the console. Results after a base-record change need a save
  made before the cell was visited.
- **One-sided door blocks: likely the runner, not the doors.** In each pair the first route opened the door and was
  blocked, and the second found the door already open (no prompt through the doorway) and walked through. With E pressed
  from the route start (no 350 ms step-in, so outside the leaf's swing arc) and only when the prompt says OPEN, the
  first blocked side tried, Parsons door `060990`, **passes (3.83 m through)**. The step-in had put the player inside the
  swing arc. The remaining blocked sides are still to rerun (stopped: another window came to the front).
  A 600 ms back-off after E fixed only 2 of 9, which fits a door stopped by the player mid-swing.
- **Runner safety, second Skills-menu incident, now prevented.** `console_open.ps1` + `hud_visible.py`: the console is
  opened only from plain gameplay (oxygen ring and health bar bright) and must be confirmed open (HUD dimmed) before
  anything is typed. `readpos` and `route_run` stop instead of typing otherwise. Checked both ways in game: a normal
  read works; with the console already open, `readpos` returns `fail console 3` and types nothing.
- Runner options: `-StepIn` (0 = press E from the start), `-BackOff`, `-Only 13,15`. Results record the prompt verb.

## 2026-10-08 (night): door-named walls and grass mounds had no collision (offline, in game next)

While making stair routes start where a sunken ramp leaves the ground, the ground probe found nothing around Parsons'
retaining-wall stairs: the grass mounds there had no collision. An old rule from before native collision ("doors and
vegetation: keep walk-through, a guessed box would be an invisible wall") was also dropping FO4's own collision.
It matched by file name, so it hit **every wall piece around a doorway** (`Bld*WallPlug*Door01`), the vault hall
pieces with door openings (`VltHallResDoorWide`, `VltHallUtilCorInDoorR01`), `PrySmRoomDoorway01`, the trapdoor ladder,
grass mounds, maple trees and hanging lights. That fits the falls to z -56 in the Parsons atrium and walls beside
doors you could walk through.

Fix: these models keep FO4's own collision but never get a guessed box (`convert_static(allow_guess=False)`). The only
deliberately passable models are door leaves that animate in FO4 but aren't rigged here (vault sliding doors,
elevator doors). Each is reported as `door_not_opening: open animation not ported: passable` (collision source
`passable-door`). Rebuild: **114 models gain FO4-native collision**, 41 stay without (none in FO4 either), 8 passable
doors, 1 failed (`SubLight02Hanging`, open). Editor IDs and all 38,314 FormIDs unchanged. Not deployed yet: the
game running now is the owner's session. Next: deploy, rerun Parsons/Vault 111/Vault 114 routes.

`routes.py`: stair routes now start where the ramp comes out of the surrounding ground (sampling the neighbours'
walkable FO4 collision along the ramp; `buried_fraction` per route). Load doors no longer get door routes.
- Route files regenerated for all 12 cells against the new build (in the side staging, ready for deploy). Stair routes
  whose ramp looks almost fully buried (2 Prydwen platform stairs that passed in game before, 1 library stair) keep
  their plain start and are flagged "looks buried, route kept": more likely an overlapping piece than real burial.
- **Broken FO4 hulls: exact rebuild.** `SubLight02Hanging` (a lampshade hull of 60 nearly coplanar points) failed:
  the polygon rebuild made overlapping near-coplanar faces, and a float incremental hull gave 165 faces for 58 points.
  New `meshcollision.convex_hull_triangles` snaps to a 0.1 mm integer grid and uses exact integer orientation tests:
  112 faces (2n - 4, closed). It is only used when the polygon rebuild can't close. Flat point sets become a 1 cm slab
  (`thicken_if_flat`). Side build now: 3,139 models with FO4-native collision (was 3,021 live), 284 with none as in FO4,
  8 passable doors; FormIDs unchanged. Still waiting to deploy (the running game is not mine to restart).
- **Three more interiors converted (item 3, offline):** Vault 75 (6,456 references + 353 lights), Fort Hagen 01
  (3,277 + 165), Museum of Witchcraft (1,176 + 74). 518 new models: 479 with FO4-native collision, 26 none as in FO4,
  2 passable doors (open animation not ported). Existing 3,490 models byte-for-byte unchanged in the manifest; all
  38,314 existing FormIDs unchanged (50,339 total). New routes: Vault 75 48, Fort Hagen 61, Museum 12. Build waits in
  the side staging with the collision fixes; deploying needs a game restart the owner has to OK.
- **Wall stains as decals (item 4, offline, unverified):** FO4 draws its wall streaks (`DecoStain*`, 6 models, 244
  placements) with effect shaders, so they were skipped. Effect shaders whose base texture is grime
  (stain/streak/grime/leak/blood/decal, not from `textures\Effects`) now become Starfield decal materials
  (`effect_decal_material`; flat normal when the effect has none). Caveat: FO4 also maps these through a gradient
  palette (`BldStreakGrad01`) that isn't reproduced; the texture is dark and mostly opaque, so they may render as dark
  sheets. First thing to check in game. Still skipped, and listed as build failures: the animated oil puddle, the
  glowing "Open" sign and the strobe flash (emissive and animated effects aren't ported). Side build: 4,014 models,
  6 failures (was 12), all FormIDs stable.
- **Both-side door activation (runner, offline):** saved runs could never show a door opening from both sides, because
  the first route left it open and the second side saw no OPEN prompt (traversal, not activation; Grok's `632c4dc`).
  `routes.py --formids` now records each door's Starfield ref id (`sf_ref_local`). `route_run.ps1` closes that door
  (`prid <PluginIndex><id>`, `setopenstate 0`) before every door route, so each side records its own OPEN. `-StepIn`
  now defaults to 0 (press E from outside the swing arc). Routes regenerated for all 15 cells in `multi_next`.
  Coordination posted to #32: asking Grok for a deploy window, Codex for the batch-invalidation case.
- **Precombine debris parts (offline):** 36 of the remaining guessed-box models are FO4 precombines (`SCOL\CM*.NIF`) that
  fail with "shared vertex index 2130 out of range". This isn't junk data: those bodies use another primitive encoding
  (packed 0, 4 shared vertices per primitive, shared-index triples (2130, start, x)), thin debris rods ~1 cm thick.
  Such a part is now skipped and reported (`skipped_parts`), and the rest of the model keeps native bodies. Gain is small:
  2 models move from guessed boxes to native (`CM00075A6C` had 182 boxes). 38 guessed remain, mostly precombines made only
  of these rods. Next: decode the encoding (each primitive as the convex hull of its 4 shared vertices is the working guess).
- **Vault 111 guessed boxes cleared (offline):** `V111Glass01` uses FO4's plain `hknpConvexShape` (vertices only, a flat
  pane 3.56 x 0.87 m): it's now converted with the hull rebuild, the flat pane as a 1 cm slab. `V111Generator02OnBroken`
  has compound mesh instances with a rotation: the compressed mesh stays in its own space and the instance transform goes
  on the body's child node (node * instance), instead of re-quantising. Convention check against the render mesh: mean
  distance from collision points to the nearest render vertex is 0.185 m as coded vs 0.24 m transposed. Side build: 3,625
  native, 36 guessed (all precombines made only of the undecoded rod primitives). Unverified in game.
- **Corrections (Grok, #32):** (1) "Vault 111 has no guessed boxes left" (`3a165fa`) was wrong: Vault 111 still places two
  rod-encoding precombines (`CM00140617`, `CM001405FD`) on guessed boxes. (2) The "thin debris rods" reading of that
  encoding is wrong too: of 412 four-vertex groups across the 36 models, many are not thin (`CM00163A1B` has groups
  ~3 m in every axis; median middle extent 0.66 m). So these parts must not be dropped as harmless; they stay
  reported (`skipped_parts`) with guessed boxes until the encoding is decoded. The grouping by 4 is itself unconfirmed.

## 2026-10-09 (evening): Parsons doors open from both sides (pinned build)

Pinned build: `multi_next` deployed with plugin `AC379C53...`, Main.ba2 `B8080348...`, code `1d3d5bf`
(`staging\multi_next\deployed_hashes.txt`). Runner: per-route door reset (`setopenstate 0`), E pressed from the route
start, OPEN read from the prompt (`94d6dcb`), idle-camera wake (`76488be`).

- First full run (45 routes): 3 hinged doors passed both sides with a recorded OPEN, 8 one side, 5 none; stairs 7 PASS,
  1 STUCK, 5 starts not reached (sunken `RWResStairs02`). 9 of the 12 door blocks had the prompt on screen but OCR read
  no verb, so E was never pressed: a runner bug, fixed in `94d6dcb` (crop + enlarge + threshold; 37/37 saved shots read).
- Door re-run (same build, routes 4-35; stopped by the foreground guard at 36 when another window came up):
  **11 hinged doors pass both sides with OPEN recorded on each side** (22 of 25 door routes; all 24 verbs read "OPEN",
  none from the unread fallback) ([side A](media/route-parsons-door-bothsides-a.jpg),
  [side B](media/route-parsons-door-bothsides-b.jpg)). Left: `06CF29` double door stops 0.30 m past the plane (needs 0.8),
  `IndMetalDoor02` blocked on one side, its other start not reached. Routes 36-44 still to run.
- **Vault 111 and Vault 114 on the same pinned build** (`AC379C53...`), cells entered with the verified `coc.ps1`
  (`957ddf2`): **Vault 111: 12 of 12 routes pass** (10 stairs + the caged switch door from both sides,
  [open](media/route-v111-switchdoor-open.jpg)). **Vault 114:** 28 PASS, 1 STUCK, 3 BLOCKED, 1 UNOPENED, 12 UNREAD
  (swapped OCR columns); doors 5 both sides ([subway door](media/route-v114-subdoor-open.jpg)), 3 one side, 3 none
  (`SubDoor01Right` `05C7DC` and two stall doors). A first Vault 111 attempt used a blind console toggle for `coc`,
  missed, and ran inside Parsons (falls to z -4990); those 5 lines were removed from the results before scoring.
- Runner safety this session: routes whose start the engine relocated are skipped (`2794e07`; E at the entrance had
  opened a dialogue with the companion); cells change only through `coc.ps1`, which verifies arrival at the COC
  marker. The companion (Vasco) was told to wait in Vault 81 for this session (in-game dialogue, nothing saved).
- **Finding: FO4 physics objects become fixed obstacles.** Vault 114 door `05C7DC` (`SubDoor01Right`) opens but
  blocks from both sides: a `SkeletonClothed01` lies in the doorway. In FO4 it is a MovableStatic, a physics
  object the player pushes aside. `convert_bodies` gives every FO4 body a static Starfield body, so here it is an
  immovable wall. This is a systematic gameplay change for all FO4 dynamic objects (MovableStatic, loose items), not
  a door bug. Not fixed yet. Plan: read each FO4 body's motion (dynamic vs static), and give dynamic ones a movable
  Starfield body from a vanilla donor (as the keyframed door leaves do), with mass from FO4. Until then they're
  reported, not silently changed.

## 2026-10-09 â€” Codex: checkpoint success-validation parity (#32)

- Verified with synthetic generated NIF/material/texture outputs: a checkpoint with intact output hashes but `fallback_materials: 1` or `door_error` was reused although save rejects it. The new regression fails both cases against baseline `cd94162`.
- Load and save now share the same success predicate; degraded cached results cause reconversion and do not enter batch expectations.
- Validation with the numpy-enabled render venv: `python -m unittest discover -s tests -p test_checkpoints.py` (13 pass), `python -m unittest discover -s tests` (253 tests, one skipped), `python scripts/guard.py` (ok). Tests ran outside the sandbox after temporary-directory permission errors inside it.
- Synthetic/offline only; game versions not applicable, no game assets or live installation changed. QA required before merge.
## 2026-10-10 Session end (owner powering down)
Status summary posted on #32 (comment 6094545513): pinned-build route results per cell, open problems by owner,
open PRs (#34 QA PASS, #35 in progress), local team state, next steps. Removed a stray `needs-qa` label from #32.
docs/ai/agent-status.md refreshed from live sources. Shut down: guardian proxy stopped, local model unloaded, no
background jobs left. Next session: re-run Vault 81 and the library, finish the Prydwen (same pinned build), then
movable bodies for loose items.

## 2026-10-10 Movable loose items (offline; owner at the PC, so no game input)
FO4 loose items (one dynamic body: pencils, cans, clipboards) now convert as movable Starfield objects instead of
fixed obstacles. Evidence and field meanings: docs/ai/research-log.md "how Starfield makes a body movable".
- **Starfield side, decoded by name** with `hktagfile`: motionType 2, flags 0x8a, mass, a motion-properties entry and
  a mass distribution (centre, volume of the shape grown by its convex radius, inertia per kg x 1.5: 30 of 30 vanilla
  boxes). Movable set dressing is a **MoveableStatic** record (a Static never moves; the clutter layer alone does
  nothing) and the NIF has BSXFlags 0x42.
- **Converter:** `meshcollision.convert_bodies` writes a lone dynamic FO4 convex body on a vanilla dynamic item's
  template (`fooddrink_set_container01_empty_lid.nif`, read from the user's install), with FO4's mass and layer and a
  computed mass distribution; `convert_static` puts it on the root node; the manifest marks the item `movable`; the
  plugin writer makes it a MoveableStatic (`DATA 4` as vanilla). Default on with `--starfield-data`;
  `--static-items` turns it off.
- **Not converted (reported, not hidden):** ragdolls and breakables (several bodies: need constraints, e.g. the Vault
  114 skeleton), dynamic compound / mesh / sphere bodies, and dynamic bodies on child nodes stay static, listed in
  `collision_report.dynamic_kept_static`.
- **Correction:** an old comment in `sfcollision.py` called offset 240 the motion type; it is the collision layer
  (232 flags, 264 motionType).
- Offline check: TinCan01 5 kg, Clipboard01 4 kg, Pencil01 0.5 kg read back as dynamic bodies; the skeleton stays
  static with 17 reasons. Tests 262 OK, guard OK. **Not yet seen in game** (next: build, deploy, push a can).
- **First in-game attempt (2026-10-10 16:2x), aborted, nothing learned about pushing yet.** Test build
  `C:\Modding\staging\movable_v111` (Vault 111 only: 219 models, 13 movable = coffee cups, beer bottles, folding chairs,
  clipboards, tools; 10 dynamic-in-FO4 models kept static with reasons: skeletons, gear-room gate, and compound shapes
  such as the cardboard box and traffic cone). `cycle.ps1` loaded the save but Starfield's "console commands disable
  achievements" popup swallowed the `coc`; the follow-up `coc.ps1` was blocked by the focus guard (Explorer had focus;
  also `FO4SF_PYTHON` was unset, so the HUD check had no Pillow). The owner closed the game. The pinned build
  (`AC379C53` / `B8080348`) was redeployed and its hashes verified. Next attempt: set `FO4SF_PYTHON`, dismiss the
  popup inside `cycle.ps1`, and only when the owner is away. Follow-up found by the build: dynamic **compound** bodies
  (several convex parts: boxes, cones, hammers) are common and need one dynamic compound body, not several.
- **Movable compounds (offline, owner at the PC).** FO4 loose items made of several convex pieces (cardboard boxes,
  traffic cones, hammers, wrenches) now convert to one dynamic `hknpCompoundShape` body, laid out exactly as Starfield's
  273 vanilla movable compounds (research log "Starfield dynamic compound bodies"); their mass distribution is the
  compound's bounding box as a solid box, as vanilla. Dynamic bodies now use a vanilla compound item as the template
  (`cb_blackmarketantiquities.nif`). Offline: the cardboard box (9 pieces, 5 kg), traffic cone (8), hammer (2) and
  wrench (4) read back with bounds, tree leaves and mass matching to 1e-8. Vault 111 test build: **18** movable models
  (was 13); only multi-body objects stay fixed (3 skeletons, gear-room gate, oxygen tank: they need joints). Tests 266
  OK. Still not seen in game (the next test waits until the owner is away or says go).

## 2026-10-10 In game: movable items and the Vault 114 skeleton door (owner away, said go)
Test build `movable_v114` (Vault 114 only, PR #41 code: 97 movable models, 7 of them merged multi-body), entered with
the fixed `cycle.ps1` (PR #42) and verified at the COC marker (0.0 m).
- **Door `05C7DC` passes from both sides** (routes 26 and 27, OPEN prompt both): 25.60 -69.71 -> 25.80 -74.80 and
  25.64 -72.95 -> 25.64 -67.63 (5.1 m and 5.3 m through). Before: blocked from both sides by the skeleton.
- **The skeleton moved** (one rigid 115 kg body, phase A): placed at 25.39 -72.55 -15.82 (FO4 position / 70), read
  back with `prid 02002E61` + `getpos` at 24.50 -72.89 -16.70: about 1 m sideways and 0.88 m down. The drop needs a
  visual check (a lower area, or partly through the floor?); the spot is too dark in screenshots. Open question.
- **A tin can is pushed by walking into it**: `02002CCB` 25.30 -67.10 -1.31 -> 24.74 -67.17 -1.30 after the
  player walked into it for 1.6 s. Screenshots are too dark to show it; the console read-back is the evidence.
- Status: dynamic bodies, MoveableStatic records and the walk-push are **verified in game** (one item, one ragdoll);
  the skeleton's resting height is **unresolved**.
- Popup (PR #42): it opens with the console; while the console is open, keys go to the console line; closing the
  console and pressing E closes it. `coc` from the main menu loads cells without a save, but the blank character is
  pulled into the new-game start after a few minutes (load screen, hang), so tests keep using the autosave.
- **Skeleton drop explained (offline; someone was using the PC, so no game input).** The converted skeleton is drawn in
  its skinned bind pose (standing, 1.88 m tall), while FO4 lays placed skeletons down with per-reference ragdoll data
  (`XRGD`, 28 bytes per body; research log). So the phase A rigid skeleton spawns standing and topples, which is the
  ~1 m slide and 0.88 m drop measured in game. Needed: `XRGD` in Fo4Export (Codex) and a posed bake on the converter
  side (skin weights). Until then skeletons are movable but in the wrong pose; reported, not hidden.
## 2026-10-10 Claude: load doors between converted cells get their teleport (offline)
FO4 load doors were kept shut since 2026-10-08. Now `dotnet/PluginSpike` makes every manifest `load_door` a graph-less
DOOR record (collision unchanged) and, after all cells of a build are placed, writes the Starfield XTEL on both ends of
every pair whose destination is placed in the same build; both references become persistent, as all 964 vanilla XTEL
references are (docs/ai/research-log.md 2026-10-10). Unlinked doors stay shut and are listed in `<out>/teleports.json`;
`PluginSpike teleports FO4Port.esm` lists the written links. Offline only: the pinned 15 cells + a scratch export of
FortHagen02 give one pair (FortHagen01 `0CD469` <-> FortHagen02 `0CD46A`), read back from the written plugin. Not yet in
game. Note for the next build: 12 of the 15 pinned cell exports predate the persistent-reference export and hold no
load-door XTEL at all; re-export them before expecting any door to teleport. Branch `claude/load-door-teleport`.

## 2026-10-11 Claude: load-door teleports checked on the re-exported 16 cells
Follow-up to 2026-10-10. With the 15 pinned cells and FortHagen02 re-exported (schema 2, C:\Modding\staging\exports_1011),
the branch writer reports "2 references linked (1 mutual pairs), 28 destinations not in this build, 4 sources not placed,
0 issues": 34 XTELs, one pair (FortHagen01 `0CD469` <-> FortHagen02 `0CD46A`), the rest lead out of the set or sit on
marker doors the converter never places. Read back from the written plugin; 0 existing FormIDs changed against the staging
map. `teleports.json` now lists the unplaced sources too (PluginSpike.Tests asserts it). Still offline, not in game; PR #50
(docs/ai/research-log.md 2026-10-11).
## 2026-10-10: the Prydwen's 7 small falls (offline diagnosis, fix not yet built)
The 7 `FALL` routes of the pinned Prydwen run are two problems, neither a hole in the converted collision
(details and evidence: docs/ai/research-log.md, same date).
- Routes 12, 13, 15, 18: the "stairs" `PryPlatformInCornerStairs01/02` are railing frames. Their post bevels gave the
  planner a fake ramp (ends 0.03 m apart under a 0.91 m rise), and the walk went down the real stair next to them
  (`PryCatwalkStairsEnt01`), ending where FO4's own steps are. `routes.py` now rejects ramps steeper than 60 degrees
  end to end (all real ones are at most 46.4).
- Routes 20, 28, 29: `PryCatwalkStairsEnt02` was converted facing the wrong way. Its NIF root node is turned
  180 degrees, and the game ignores a root node's transform: FO4's precombined physics matches 89 placements of 15 such
  models only without it. The converter applied it, so the first flight climbed away from the second and the routes
  started in mid-air. Now geometry, collision nodes and door pivots leave the root out (`nif.world_transforms
  placed=True`). This also turns back 43 other models (232 placements across the slice), among them diner counters,
  Vault 114/95 catwalk frames, desk lamps, posters and the Cambridge `HitDoorSm01/Lg01` doors.
Next: rebuild, then rerun the Prydwen (routes 12-32 and the regenerated Ent02 routes) and the Cambridge doors in game.
## 2026-10-10 Launch script hardened after QA (offline; owner at the PC)
PR #42's QA agent found that `cycle.ps1` pressed E blind when its screen check could not run. Fixed: a failed prompt
or popup check now stops with exit 5; an activation prompt that stays under the crosshair stops with exit 6; a `coc`
the popup swallowed is retried only after the console is closed and the popup cleared, with the console line emptied
first; the cell name is validated before it is typed. New tests: every `scripts/game/*.ps1` must parse (PowerShell's
parser, skipped where there is none) and `prompt_visible.py` is checked on synthetic screenshots. 258 tests OK on
this branch.
- **Launch script waits on the screen, not timers (offline).** `cycle.ps1` now polls a screenshot every 3 s for the main
  menu text, then for the HUD after Continue and after a blind `coc`, instead of sleeping 30 + 45 + 37 s. The checks
  were validated on today's saved screenshots (menu text read on the menu shot only; HUD seen in game only). Before:
  195-210 s per cycle; after: to be measured on the next run (docs/ai/optimization.md).

## 2026-10-11 Overnight: library and Vault 81 re-run on the pinned build (Lead task 4)
Owner away (PC idle 4.7 h); normal build restored (`AC379C53`), entered with the verified cycle (168 s, from 195-210).
**Boston Public Library, 67 routes (110 min):** 42 PASS, 10 STUCK, 4 FALL, 5 BLOCKED, 6 UNREAD. Doors 12 of 16 both
sides, 1 one side (`0FFCA5`), 3 none: the wooden double doors `100196` and `10019C` block from both sides. The deco
rail stairs (`BldDecoSmRailStairs01L/R`, `03L/R`, `Short01R`) account for 7 STUCK/FALL; brick and block stairs pass.
**Vault 81, 19 routes:** 16 PASS, 2 BLOCKED, 1 UNOPENED; all 13 stair routes pass; stall doors `19DA38` both sides,
`19DA3A` / `19DA36` one side each. Results: `run_lib_1011`, `run_v81_1010` (local). Posted on #32.
## 2026-10-11 Route planner: railings are not stairs; double doors are twins (offline)
Two findings from the library run, both test-side, not converter bugs:
- The 7 STUCK/FALL "rail stairs" routes (`BldDecoSmRailStairs*`) were routes on railings: their FO4 collision has no
  treads at all (6 flat vertices on one level) and no helper; the steps are a separate model. A scan of all 74 "stair"
  models in the pinned build: 45 carry FO4's RampDummy helper, the other 29 are railings, trims and stairwell walls, and
  NONE has treads without a helper, so a synthesized helper (built and then dropped today) has no target. The planner
  now requires 3 tread levels for a model without a helper and skips the rest with a reason (`tread_levels`).
- The library's "double doors" `100196` + `10019C` are two single-leaf `BldWoodPDbDoor01` references on one spot,
  rotated 180 degrees, each hinged at its own jamb; the route activated one and hit the other leaf. The planner marks
  such pairs (`door_twins`, within 0.1 m) and the runner resets and activates the twin leaf too (`+twin:` in the verb).
Tests: tread levels (steps, railing, helper and underside ignored, 4 cm merge) and twins; 260 OK, guard OK. The
twin step is untested in game until the next library run.

## 2026-10-11 Queued test runner verified in game; terrain kickoff (Claude)
- **Runner (PR #59)**: `scripts/game/testqueue.py` + `qstep.ps1`. Supervised batch on the integration build `2470f876`
  (main + #41 #50 #51 #42 #54, local branch `claude/integration-1011`): launch, dedicated save `fo4sf_test_2470f876`
  created and loaded, god mode read from the console ("God Mode enabled."), cell arrival verified; 2 stairs PASS,
  2 falls PASS, 2 doors FAIL (`BldWoodPDoorShutter01` open but the route aims beside the doorway). Six runner bugs found
  and fixed (kind mapping, tgm reply, ceiling pieces as probe floors, OCR without ">>", Steam popup taking the focus,
  HUD recovery). The owner closed the game mid-run; movable and travel steps are not verified in game yet.
- **Queued**: the rest of the supervised batch, then 753 tests on 16 cells (`C:\Modding\testqueue\overnight.ps1`),
  starting only after 15 min without input.
- **Terrain**: PR #56 (FO4 2x2 patch at Red Rocket, two decoders agree exactly, borders match, the building sits on the
  terrain) and PR #57 (Starfield: 430/433 worldspaces use `Data\TERRAIN\<EditorID>.btd`; BTD decoded and re-encoded;
  experiment 1 staged in `C:\Modding\staging\terrain_exp1`, not deployed). Next blocker: the in-game BTD load test.

## 2026-10-11 afternoon: terrain experiment 1 in game (unattended runner)
- **Run 1:** loose BTDs. World01 and World02 (record path; record path + name) load on Mars with procedural ground. The heights are identical in both worlds (4.18 / 11.86 / 15.98 / 10.68 m at our 10 / 35 / 22.5 / 5 m pads), so neither used its BTD. World03 (name only, no surface block) hangs on the loading screen.
- **Cause of run 1:** the loose files were never read. `Starfield.ini` has `sResourceDataDirsFinal=STRINGS\` and there is no StarfieldCustom.ini. The experiment installer now packs the BTDs into the plugin's own `<plugin> - Main.ba2` (`exp_install.py --pack`).
- **Run 1b:** BTDs packed. World01 reads the same procedural heights again, so the packed BTD isn't used either. Registering World01 on Mars (run 1) moves the spawn onto a real Mars mountainside; the pads read flat at about -2.5 m, still procedural.
- **Next (queued):** control drops in two vanilla worldspaces via `cow`, at lc001world and akilacity points whose BTD heights are known. These show whether `coc`/`cow` gives BTD terrain at all, or only the planet landing does. Then the Mars-registration variant with packed BTDs, then the test batches.

## 2026-10-11 late afternoon: terrain measuring method validated on vanilla terrain
- **Console routes into vanilla exteriors:** `coc <exterior cell EditorID>` works (`LC172Ext01`, `LC001Outpost`). `cow`, `coc <worldspace>` and `player.moveto <non-persistent ref>` do not.
- **Control LC172World** (the template our test worlds are cloned from): the overlay is merged into Mars at offset (-500, -2300, -3.62), read from the persistent COC marker 0010238E. Probes in the overlay's own frame:
  - match its BTD within **0.02 m** in the centre cell, which the vanilla overlay mask marks as authored;
  - within 0.3-0.36 m just outside it;
  - 4-6 m off in the border cells, where the mask blends in procedural terrain.
- **Method:** anchor-relative probing measures BTD heights exactly where the overlay is authored, and the overlay mask decides where that is.
- **Research** (`C:\Modding\research\terrain\binding\findings.md`, PR #64): a worldspace's own BTD only applies to an overlay activated on a planet (PNDT CNAM). Our records also differed from vanilla in FNAM size, Location, mask and alignment. The fixed experiments exp1d and exp2b (real Red Rocket heights) are queued after test B.

## 2026-10-11 evening: why our overlay terrain came out flat
- **In game:** every registered overlay test was perfectly flat at exactly its BTD's minimum height:
  - exp2b (29x29 Red Rocket BTD, absolute alignment) read -116.00 m at all 14 probes;
  - World01 / exp1d read -500 m (with relative alignment, -13.94 m).
  The overlay itself was activated (cells merged at whole-cell offsets).
- **Offline diagnosis** (two agents; scratch data in `C:\Modding\research\terrain\zero`):
  - Our BTD layout matches vanilla section by section, and the heights are in every LOD.
  - The one difference is that all 2,112 vanilla BTDs (Shattered Space's 108 included) and every official plugin Main.ba2 are stored **uncompressed**. Ours were zlib-compressed by Archive2 `-compression=Default`.
  - The engine reads BTD blocks by offset straight from the archive, so it decoded nothing and used raw 0.
  - Fix: `exp_install.py` now packs with `-compression=None`.
- **Next candidates** if that is not all:
  - `lodsettings/<edid>.lod` (every vanilla overlay has one);
  - the 29x29 size (the largest vanilla overlay is 14x14).
- **Queued:** exp2b3 (Red Rocket, stored), then exp1f (World01, stored), then the batches.

## 2026-10-11 evening: native Starfield terrain carries the real Commonwealth heights (Red Rocket)
- **exp2b3**, our FO4CW_Commonwealth overlay (29x29 Starfield cells of FO4 LAND around Red Rocket, Absolute alignment, registered on Mars, BTD stored uncompressed in the plugin's Main.ba2): 13 of 14 probes match FO4 height / 70 within 0.08 m, including the Red Rocket origin (105.14 m), slopes, an FO4 cell seam and a Starfield block seam. Overlay Z offset 0.01 m.
  - The 14th probe (resampled_sw) ended 142 m from its target, so it was not measured.
  - Absolute alignment keeps the real world heights.
- **Cause of all the earlier flat results:** a zlib-compressed BTD in the BA2. Stored (uncompressed), as vanilla ships it, works.
- **Next (queued, each test from a fresh launch):**
  - exp2c: 8,069 real FO4 objects around Red Rocket on this terrain (PR #66);
  - exp3: four edge-to-edge 14x14 overlays with seam probes (PR #67);
  - World01 stored; the vanilla NPC navigation control; then the batches.
- **exp2c, same evening:** the real FO4 objects around Red Rocket (8,069 references, 1,385 converted models, one plugin) stand on the native terrain in game. Textures load from the stored plugin archive.
  - Test 1 PASS: the terrain probes are still within 0.08 m with the objects placed.
  - Test 2 PASS: object tops land where FO4 put them, so their collision works: Red Rocket roof 109.73 m (want 109.74), brick building roof 103.87 (103.88), road piece 88.20 (88.21).
  - Probing 100 m past the overlay raised Starfield's "Boundary Reached" popup, the landing area's limit.
- **exp3** (four adjacent 14x14-cell overlays, each registered on Mars): probes in the arrival tile read real terrain. Every probe 500-700 m away, in or near a neighbouring tile, hung at the drop height even after 24 s of re-reads, so nothing loads there.
  - Taken with the "Boundary Reached" popup at the edge of the 29-cell overlay, a landing seems to load only the overlay it arrives in. A Commonwealth made of many small overlays would not be walkable across seams.
  - The candidate is one large overlay. **terrain_core64** (PR #72: 64x64 cells = 6.4 km covering Sanctuary, Vault 111, Red Rocket and Concord, 6 rays of probes out to 3 km) is queued.
- **Navmesh (PR #71):** FO4's navmesh around Red Rocket is converted to 156 Starfield NAVM records with a NAVI override. The N1 NPC tests are queued after the vanilla control N0:
  - N1a: terrain only;
  - N1c: converted navmesh;
  - N1b: the runtime generator.
- **Ground textures (PR #70):** staged. They need a daytime run; every Mars arrival so far was at night.

## 2026-10-11 night: dead man's switch and the huge batch (owner's request)
- **`scripts/game/watchdog.ps1`** runs detached. It is not reboot-proof yet (the owner was asked about a scheduled task).
  - After 3 h with no "Claude:" commit and no heartbeat (`C:\Modding\testqueue\claude_heartbeat.txt`), it starts `C:\Modding\testqueue\chain.ps1` itself. No AI is needed; the runner keeps every owner control.
  - At most every 6 h it calls Codex (`codex exec`, sandbox workspace-write) to follow `docs/ai/codex-runbook.md`: status, reports, one #32 comment, no code changes or game input.
  - At most 3 chain starts per 6 h. An unfinished required queue goes back to the front of `chain_queue.txt`.
  - AGENTS.md records the exception.
- **`batch_full`**, queued last: 1,764 tests on the 16 cells. It covers every route (routes.py `--max 400` -> `routesfull_*.json`) plus 40 falls and 40 movable items per cell, about 30 h.
- **core64** (one 64x64-cell overlay, 6.4 km) in game: every probe within ~500 m of the arrival is exact (Sanctuary 110.27/110.29, Vault 111 127.09/127.09). Single 1-2 km setpos jumps do not load in time, so a hop variant (300 m steps) is queued next.

## 2026-10-11 late night: the "far terrain does not load" result is a 9x9-cell playable border
- **core64, all six rays** (one arrival at Red Rocket each, from a fresh launch): every probe up to ~380 m from the arrival reads the FO4 height within 0.01 m (arrival 105.14, Sanctuary 110.27, Vault 111 127.09, Concord 87.09, se_500m 56.92/56.91, ne_500m 113.38/113.37).
  - The first probe at 500 m straight east, south or west (and 700 m diagonally) raises Starfield's **"Boundary Reached"** popup (screenshot in the test folder). Its position read is garbled, and every later probe stays at its drop height.
  - The allowed probes span local cells x -14..-7 and y 8..14, and the blocked ones sit 5 cells out. That is a window of about 4 cells around the arrival cell (-10, 11), inside an overlay whose 4,096 cells all exist and whose worldspace bounds (NAM0/NAM9) cover the whole 6.4 km.
- **Supported hypothesis:** the limit is Starfield's landing-area border, not our data. Starfield.exe has `bBorderRegionsEnabled:General` (set to 0 by the "Border Regions Unlock" mod), `fPlayableAreaX/Y/Z:General`, `uMaximumPlayableAreaWorldCoord:General` and `uPlayableSpaceOverlayCellBuffer:Planet`. The console has `SetINI` and `GetINI`, so a test can change the border for one session without touching an ini file.
- **This also confounds exp3's "neighbouring overlays do not load" result (500-700 m probes).** That needs a re-run with the border off before the many-overlays option is ruled out.
- **Runner:** core64b (300 m hops) is paused with a queue STOP. Its second hop would only reach the same border. The next queue reads the settings (`GetINI`), sets `bBorderRegionsEnabled` to 0 after the save loads and before the coc, then repeats the rays and hops.
- **Fixed:** an open breaker now skips a test before the "fresh" relaunch (one wasted launch per tripped breaker).
- **Correction, 2026-10-12 00:01: travelling works, so the border limits jumps, not the world.** core64b's north-west ray reached every probe in 300 m hops (11 hops) and PASSED to 2 km:
  - arrival 105.14, Sanctuary 110.27, Vault 111 127.09, 500 m 114.17 (want 114.17), 1,000 m 202.54 (202.51), 2,000 m 188.45 (188.46);
  - no "Boundary Reached" on the way.
- So the popup comes from a **single teleport more than ~4 cells from the current position**, not from a fixed window around the arrival. The 6.4 km overlay streams in as the player moves.
- exp3's neighbouring-overlay probes were single 500-700 m jumps too, so the seam question is open again and needs a hop run.
- The other five core64b rays are pending: its STOP is removed, and it needs to go back into `chain_queue.txt`. terrain_core64e (PR #74, one pebble per cell) now only asks whether content changes the single-jump limit, which is low priority.

## 2026-10-12 early morning: navmesh plugin terrain check passes; the vanilla NPC control is not a control yet
- **exp2d PASS** (Red Rocket terrain + objects + the converted navmesh plugin, PR #71): the ground under all four N1 NPC points (A, B, and A2/B2 across a cell line) reads the expected height within 0.01 m, 5 of 5. The navmesh plugin does not disturb the terrain.
- **N0, the vanilla NPC control in QASmoke** (actor 002B211C, levelled 0000CF96; A (-8, -4) to B (5, 10), 20 m):
  - 2 PASS, 3 FAIL, but **no test shows a commanded walk**. Every actor, with or without a command, stayed in the same patch (x -11..0, y -6..2) and never came within 10.8 m of B.
  - Baseline (no command): wandered 5.4 m towards B, FAIL WANDER.
  - `PathToRef player`: 6.8 m and 9.0 m towards B, counted as PASS, but that is within the wander.
  - `cf "Actor.PathToReference" player 1.0`: the console replied "No script named Actor is attached to the object".
  - `SetPlayerTeammate 1` + `EvaluatePackage`: the actor stood still for 30 s.
  - The robot visible next to the camera in the sample shots is also there in the no-command baseline. It is most likely the save's companion, not the test actor.
- **Next for the NPC tests:**
  - B must be reachable on navmesh from A (supported hypothesis: it is not in QASmoke, or the package overrides PathToRef).
  - The judge must require arrival (end within a few metres of B) or progress beyond the baseline's wander.
  - Add `StartCombat player` (a script command in Starfield.exe: "Forces the currently selected reference to initiate combat with the provided actor") as a control method.
  - The N1 queues still run (moving at all on our terrain with and without navmesh is useful), but their "towards B" verdicts carry the same caveat.

## 2026-10-12 ~02:00: three slice pieces built and reviewed; integration-1012 ready (not yet the chain's runner)
- **Built and adversarially reviewed overnight.** Each reviewer found blocking problems, and each was fixed.
  - **PR #73 (daylight, plus the console hook).** `SetLocalTime` is the runner's time-of-day command, with the reply captured.
    - Light is judged from every probe shot, and NIGHT is retried.
    - A queue lists the runner features it `needs`, so an older runner refuses it at pre-launch instead of running it without the time.
    - The test is staged at the site that was night 18 of 18 times (`terrain_exp2b2_noon`); the daylight site was day 13 of 13.
  - **PR #75 (first converted FO4 NPC):** the Concord raider (FO4 ACHR 00046458, LvlRaider) as one Starfield NPC_ on the Spacer templates.
    - The record now carries PRPS/STON/EDCT/PRON, which all 7,131 vanilla NPC_ have.
    - A calm copy is used for the walk tests (N2a), so the peaceful vanilla control is fair. The hostile copy goes to N2b.
  - **PR #76 (every FO4 exterior object on the 6.4 km core):** 648,358 references of 11,769 models, a 46.1 MB plugin and a 3.63 GiB stored archive (textures capped per kind to stay under 4 GiB).
    - Object z matches FO4's own terrain at the median, +0.22 m.
    - The plan uses waypoints so that every teleport moves at most 2 cells per axis.
- **Teleport rule:** at most 2 cells per axis landed 144 of 145 times; 3 or more cells per axis failed 11 of 28 times (all 6 in core64). The rule is a supported hypothesis from `scripts/terrain/teleport_audit.py`, and "~4 cells" is refuted.
- **`claude/integration-1012`** merges test-queue, daylight, raider and core64-objects. The unit suite and guard pass.
  - It has one semantic fix: NPC plans accept the light and console keys.
  - Queues planned with it: `terrain_core64c`, `terrain_exp2b2_noon` (needs: light), `npc_nav_n2a`, `npc_nav_n2b`. They are not in the chain yet.
  - The chain still runs integration-1011 (N1c, N1b, then the supervised and full batches). Switching the chain's checkout and adding the queues is the owner's call.
- **N1a** (vanilla NPC on our terrain, no navmesh): the NPC never moved (0.0 m), as expected without a navmesh. It counts as INCONCLUSIVE only because N0's control did not pass.
- **N1 (vanilla NPC 002B211C on our Red Rocket terrain, ~03:10): the converted FO4 navmesh carries Starfield's AI.**
  - **N1a (terrain only, no navmesh):** the NPC never moved in 4 of 4 tests. Every read was the same position to 0.1 m for 30 s.
  - **N1c (with the converted navmesh, PR #71):** the NPC moved in 4 of 4 tests, 10.5, 7.2, 11.0 and 14.1 m (paths up to 27.6 m), and its z followed the terrain (105.0 to 105.5 m). It also walked about 9.5 m towards the player before any command.
  - These are **verified movement on converted navmesh**, not commanded navigation: it wandered, as in QASmoke, and never reached B.
  - The cross-cell test stayed in its own cell (x -2194..-2183, cell line at -2200), so the NAVI edge links across cells are still **unresolved**.
  - All N1 verdicts read INCONCLUSIVE CONTROL because N0's control is not a control yet. N0b (navmesh-connected points, StartCombat, arrival judging) is being built and reviewed.
- **N0b, the NPC control redesign (PR #77, reviewed and fixed; merged into integration-1012 at f3dcf5d):**
  - **Why N0 could not tell commands from wandering:** QASmoke's navmesh (one NAVM, 002BE3AA) is a single 555 m2 area. The old pair was connected by a clear straight path. The actors' own drift (up to 14.06 m from t0, measured in N1c) covered most of the 19 m.
  - **New design:** a 24 m pair. The approach before the command is capped at 3 m (otherwise INCONCLUSIVE PRECOMMAND). A PASS needs 18 m of approach from t0 or arrival within 3 m. A control counts only with its own queue's baselines.
  - **Tests:** two citizen baselines, the Spacer baseline, PathToRef and StartCombat.
  - **Queue:** `npc_nav_n0b` (needs runner feature npc_t0, so integration-1012 or later).
  - **Re-plans:** the N1 and N2 re-plans are staged as `npc_nav_*_b`. They are planned only after `npc_control.py ready` confirms N0b passed. The earlier `npc_nav_n2a` / `npc_nav_n2b` queues carry a STOP note (superseded).
- **N1b (the same NPC on our terrain after Starfield's runtime generator `gnm`, no shipped navmesh):** it never moved in 3 of 3 tests where it spawned. The 4th test did not confirm its spawn, twice (INCONCLUSIVE SPAWN, a runner reason).
  - Reading so far: no navmesh means no movement; `gnm` also gives no movement; the converted FO4 navmesh gives movement in 4 of 4 tests.
  - Shipping the converted navmesh is the supported route; `gnm` in a plugin worldspace is refuted for this use, to be rechecked with N1b_b against the N0b control.
  - The chain now runs supervised_1011, then batch_full (integration-1011 runner).
- **supervised_1011 finished (17 tests: 10 PASS, 5 FAIL, 2 INCONCLUSIVE).** Ranked:
  1. **Door BLOCKED, 2 tests:** FortHagen01's wooden shutter door (BldWoodPDoorShutter01, 0BD6A1). It shows OPEN, activates and swings, and the prompt flips to CLOSE. But the panel still covers part of the opening, and the player stops 0.9 m before the door plane. Candidates: the door swings only part of the way, or its collision does not follow the animation. Unresolved.
  2. **Travel NOPROMPT:** FortHagen01 load door 0CD469. The companion stood at the door; the runner now disables it per session (bf01e51, not yet in the chain's runner).
  3. **Stairs STUCK:** Vault 114 CinderBlockStairs02 (rose 0.10 m, needed 0.12 m).
  4. **Movable NOTMOVED:** FortHagen01 CigarettePack. The player reached it, but it moved 0.000 m.
  - The two INCONCLUSIVEs: a fall held 1.5 m above a cave floor, and a movable test the player missed by 2.39 m.
- The chain now runs **batch_full** (1,764 tests, about 30 h) on integration-1011.

## 2026-10-12 morning: multi-part FO4 doors lost every panel but the first (fixed offline, PR #79)
- **Cause (verified offline):**
  - `nif.door_hinge` read only the first node the FO4 `Open` sequence moves.
  - `convert_door` hung that node alone under the Akila template hinge. Every other panel went under the static frame, with no bone and no body.
  - The Akila clip has one track.
  - The FortHagen01 shutter's `Right` panel is one example of a panel that stayed behind.
- **Blast radius:**
  - In the 16 pinned cells: 10 door models, 38 placed doors and 76 batch_full door tests. They include the Parsons double door 06CF29, plus high-tech doors with 3 of 4 sliding panels frozen.
  - In Fallout4.esm: 80 models move geometry outside their first node.
- **Fix:**
  - These doors get their own rig plus Open/Close clips built from FO4's keys with CALUMI: one bone, one track and one keyframed collision box per moving part.
  - Clip keys are offsets from the rest pose, as in 126 vanilla door rigs.
  - Offline result: 40 of 40 moving parts have tracks and bodies (was 23 of 40). 47 of 57 door models are byte-identical. The overlay plugin differs from integ_1011 in exactly 48 records.
- **Review notes (pass-with-notes):**
  - Nested motion is not detected yet (`RRMegaSecurityDoor01` and `Prewar_Locker_Door01`; neither is in the build).
  - One physics system per panel has no vanilla precedent: every vanilla double door shares one system. This is the largest in-game risk.
  - Three rigs use FO4's `@#0` name suffix as bone names.
- **Also:**
  - The FortHagen shutters are windows (the wall is solid to about 1.03 m), so their walk tests cannot pass; the route planner should skip openings above step height.
  - It all needs a new pinned build (overlay `integ_1011_doors`) after batch_full. Commands are in docs/spikes/WP-doors-research.md.
- **Slice: the Red Rocket cave door (PR #78, fixed after review; merged into integration-1012):**
  - **Source (verified):** in FO4, RedRocket01's door 05E844 and the exterior door 08EB65 are AutoloadDoors (the player walks into a marker) linked to each other. Neither end existed in our build: markers are never placed.
  - **Plugin:** FO4SliceRedRocket.esm places the vanilla AutoloadDoor_Cave (24F9CE) at both FO4 spots. Its marker is the FO4 marker / 70 within 0.013 %, and the two doors are persistent and teleport-linked both ways.
    - It sits in the cave mouth 38 m south of exp2d's arrival.
    - Offline checks pass: 27/27 and 28/28.
  - **Runner:**
    - A `door_trip` kind: coc, walk in, read the cell and position, walk out, save, move away, load, read again.
    - FAIL NOLOAD needs the player still within 3 m of the door with no load seen.
    - The position is read after every walk step, so a fast loading screen cannot send the player into the void.
    - `exp_install.py order` puts experiment plugins after their masters.
  - **Queue:** `slice_redrocket_door_b` (needs door_trip, door_check, plugin_order: integration-1012 at 16e21a4 or later).
  - **integration-1012 now (16e21a4):** test-queue + #73 + #75 + #76 + #77 + #78 + #79. The unit suite passes (37 opt-in skipped) and guard passes. Its planned queues wait for the owner to switch the chain's runner.


## 2026-10-12 - Codex: recoverable installer compatibility for the cave slice (#78/#62)

Offline tested, synthetic files only; no game version/runtime acceptance claimed. #62 rejected the cave queue's --needs and cycle's order command. Combining the original ordering code with recovery also skipped pre-existing/reactivated plugins, accepted disabled masters/cycles and could overwrite a concurrent Plugins.txt edit. The new synthetic compatibility suite reproduced these failures plus plugin-only --pack trying to build an empty archive.

Carried #62's independently reviewed journaled publication, pinned SHA inputs and stored General BA2 coverage/content verifier onto #78. Retained the runner feature gate and ordering CLI; receipts now name every selected plugin. Ordering requires complete/non-cleanup state, unchanged selected plugin files, active masters and satisfiable dependencies; its atomic rewrite compares the original snapshot and refuses concurrent edits. Completed-install cleanup restores owned activation lines by text, so ordering requires no whole-file rollback snapshot update. Install/order/uninstall all refuse an interrupted or cleanup-pending main deployment before mutating its activation snapshot or experiment receipt. Plugin-only --pack keeps its requested mode for relaunch checks and builds no archive. Truncated TES4 headers/subrecords cannot hide a master. Two newer upstream packing fixtures now emit valid synthetic BA2 resources; runner implementation is untouched.

Validation: 14 new compatibility tests, 43 recovery, 9 packed-verifier, 4 terrain/mask packing, 18 upstream door-trip and 81 queue tests pass. Final current-main Windows suite: 882 tests, OK (38 skipped); guard/diff checks pass. Independent Codex QA reproduced both order and uninstall invalidating interrupted main recovery; install/order/uninstall now share the refusal guard. Independent final PASS includes distinct activation snapshots, master recovery and later uninstall retry. Hosted CI at e661977 ran 881 tests and failed solely on the existing #66 Linux filesystem separator lookup; terrain file remains Claude-owned. #84 records inherited final compare/replace/unlink race gaps; no interprocess isolation is claimed. No staging, Plugins.txt, game installation, live input, automation or local-model changes.

## 2026-10-11 Public README and About refresh (Codex)

Owner requested immediate publication of the README and GitHub information. Refreshed the existing #36/#37 work
with Claude's latest pinned evidence, queued runner, offline terrain/NPC research and Codex's #62 recovery tests.
Earlier route results and the newer integration batch remain separate. Added the already-installed Steam launch
command, staging deploy/uninstall examples and eight COC commands checked against PluginSpike's naming and the
staged cell filenames. Reused existing published screenshots; no game outputs or new media added.

GitHub About now links the live #32 status and describes experimental interiors, native physics, queued tests and
terrain research; topics retain existing labels and add terrain/game-conversion. Claude, Codex and Grok attribution
is retained. Main publication uses #37 and its required CI, with protections unchanged. No live game changes.
Validation: 254 synthetic tests OK (1 skipped), guard and diff checks OK; all 18 local README links exist.
QA caught a case-insensitive fallback symlink escaping staging in the existing Linux compatibility change.
The resolver now rechecks containment after every component; a synthetic Linux symlink regression covers both
directory and file requests. It is skipped on Windows because that fallback requires case-sensitive lookup.
Final Windows suite: 255 tests OK (2 skipped); guard and diff checks OK. Linux CI executes the new regression.

## 2026-10-11 Terrain CI preview dependency (Codex)

#64's hosted run38177486495 reproduced ModuleNotFoundError: PIL in the synthetic FO4 plane extractor's preview.
CI installed only NumPy; local testing already had Pillow12.3.0. Added the tested public Pillow release range
to requirements-ci.txt without changing terrain records, scripts or tests. Coordination and file claim: #32/#64.
This fixes the missing dependency, not the unresolved in-game terrain binding. No game assets added.
Validation: main-based255 tests OK (2 Windows skips), guard OK. At #64 head1600603, all11 FO4 LAND synthetic
tests pass with Pillow12.3.0, including the failing end-to-end plane/preview case. Hosted dependency CI pending.


## 2026-10-12 Codex: native-door checkpoints follow rig and clip references
- Reproduced on #79 (612b78e), using its production synthetic two-panel converter: dropping the skeleton from both the saved files list and output hashes allowed reuse after the staged skeleton was removed.
- Inventory now independently follows native DOOR skeleton and Open/Close .af/.afx references; missing, changed or invalid dependencies invalidate reuse. Optional extra outputs remain tracked; template doors keep their existing behavior.
- Preserved reviewed main #34/#35 and staging containment when integrating #79 in a separate Codex worktree. New regressions failed before the fix; seven focused tests and 808 full-suite tests pass (28 skipped, including opt-in sandbox checks). Guard/diff checks pass. No game data, staging, installation or input was touched; runtime multi-part animation remains unverified.
- Independent Claude review passed the initial fix and identified an optional rig-tag omission: generated references are now followed even without that tag. Added omission and vanilla-template compatibility regressions; final independent review passes (including custom prefixes and mixed vanilla/generated references). Hosted Linux CI separately exposed an existing make_exp2c dependency path issue; a four-lookup patch passed POSIX-only synthetic probes and was prepared for the Claude-owned file without editing it.

## 2026-10-12 Codex: small authored door binds are rotations
- Synthetic NIF/controller repro: a0.1-degree leaf bind was classified identity by quaternion w alone, so the native first offset retained0.1 degrees even when the closed pose equalled the bind.
- Identity detection now also checks the vector norm; native preparation shares the predicate. Meaningful small binds get a static parent and identity animated bind; sign-equivalent identity/tiny numerical noise remain supported.
- Five regression tests failed before correction and now pass. Independent matrix evaluation agrees at every Open/Close frame for three axes, small/large binds, translation and both possible bind/offset composition orders. Full813 tests OK (28 skipped), guard/diff checks pass. Independent QA PASS (boundary/sign, nested hierarchy, cross-axis and synthetic converter routing probes); no DLL, game assets, staging, install or input touched. Runtime playback remains unverified.


## 2026-10-12 - Codex: portable terrain dependency filesystem lookups (#66)

Offline tested. The owner says Codex is the only agent currently able to work; the exact dependency_check takeover was announced on #66/#32 before editing. Mesh/NIF, geometry, material and own-texture identifiers carry game-resource backslashes, which Linux treats as literal filename characters. Normalize separators only at the four filesystem lookup boundaries; resource/report names, counts, vanilla membership and terrain/converter behavior remain unchanged.

A synthetic POSIX filesystem regression reproduces both failure modes on Windows: backslash NIF lookup raises FileNotFoundError, and a forward-slash NIF still reports a material missing because its derived lookup contains backslashes. After the fix, both resource separator styles cover missing geometry/own texture/material/NIF, complete coverage and missing/unverified vanilla textures. Existing real-filesystem fixture is retained. 18 focused tests OK (3 skips); full current-main Windows suite 360 tests OK (5 skips), 4.775s; guard/diff checks pass. Linux CI and independent review follow in the PR. No game assets, staging, deployment, game input or automation changed.


## 2026-10-12 - Codex: budget-paused game queues must request resume (#88)

Read-only observation: batch_full stopped at its12-hour run budget with1109 tests pending (655 terminal entries included216 BREAKER skips). Runner.run wrote paused state/report but returned0; the existing required-queue chain treats that as completion, rather than retaining it for a later resume. The exact Runner.run exit-status scope was claimed on #88/#32 under current Codex-only availability.

Change: pending work after a budget pause returns4; completed runs and dry-run previews keep0. A complete run can still contain failed/inconclusive tests. Checkpointing, retries, owner/STOP/idle/Guardian checks and game control are unchanged. Two synthetic budget failures reproduce return0 before the fix; four new tests verify test/time limits, pending-only resume, completed/no-budget and dry-run controls. Four focused and81 existing runner tests pass; full suite/independent QA follow.

Measured prior-result intervals: stairs median85s, floors60s, doors100s. Remaining non-movable work estimates~15 active hours, plus waits/retries; the broken movable lane would add more after corrected re-planning. A separate offline133-test diagnostic artifact retains all16 cells and all49 recorded failures, unchanged source payloads/IDs and the old2470f876 plugin pin; estimated3.14 active hours/~3.92 with25% retry margin. This reduced pass does not replace exhaustive acceptance or verify newly staged assets. Source queue/state, live chain/runner/staging/game and automations were not edited or run.

## 2026-10-13 - Codex: corrected diagnostic merge frame in isolated runner

Owner requested continued testing unless Claude needs control. Scoped claim on #32; original af27ce9 runner/campaign remains immutable. qstep's unscored terrain diagnostic now adds the measured X/Y merge offset and uses its computed world drop height. Three synthetic tests evaluate the actual parsed call with a harmless Teleport stub; the two nonzero cases failed before correction. No input helper or game body executes in these tests. Fresh pins and independent QA precede the remaining informational phase; prior boundary captures remain excluded from map-size conclusions.
## 2026-10-13 Replayed ground-reference evidence (Codex, #96)

Synthetic reproduction: two entries sharing only their ground-reference capture were inconclusive but still
counted four dependent roof heights as matches; a final diagnostic reusing the reference left two matches.
After phase-wide capture deduplication, unusable references now invalidate every dependent relative height.
Six new regressions retain valid independent images with identical pixels, limit non-reference replay
to the affected rows and demote stale HEIGHTS issues after reference invalidation (independent QA finding).
Four negative regressions failed before their fixes. Validation:31 evidence tests and308
full-suite tests pass (2 skips); guard passes. Re-reading completed pinned evidence preserves7/7 smoke and29/30
baseline heights and all four POST_FRAME findings. Offline only; no game scripts, assets or live control changed.

## 2026-10-13 Claude: small converted items that "did not move" were out of reach or walked over (offline; a live test was running, so no game input)
- **Not the conversion (verified offline):** the converted BurntBook01, CigarettePack, BobbyPinBox and trash can bodies
  match vanilla Starfield items on every motion, layer, quality, flag and BSXFlags field (6,221 vanilla dynamic bodies
  dumped). Starfield's own collision matrix lets the player's controller collide with their layer (CLUTTER).
- **Most failures were placements** (reads corrected after the verifier of PR #110): the cigarette pack (supervised_1011
  0007, the only FAIL) lay 0.83 m up on a desk and the player stopped at the desk 0.67 m from it; one bobby-pin box
  (batch_full 0098) lay level with the player, who was blocked 1.45 m short of it. The three books (batch_full) lay
  flat on the floor, 4.6 cm thick, and the walk passed 0.02-0.15 m from them. The same book model moved 0.46 m in Vault
  114, where it lay on a bench the player climbed onto (hit side-on, or walked over and pushed off: the reads do not
  tell). **One is not a placement:** the other pin box (0100, 50 kg) lay 0.81 m above the feet at the stand point, but
  the walk passed 0.26 m from it while the player rose 0.28 m, and it did not move. Whether FO4's masses (2-10 times
  Starfield's for items that size) stop the push is unresolved.
- **Runner:** only the walk passes a movable test: a walk that reaches an item and leaves it in place is FAIL NOTMOVED,
  even when `ApplyHavokImpulse` (found in Starfield.exe's script-function table with `scripts/recon_console.py`, which
  now reads those entries) then moves it; the impulse only adds "the body is simulated", or FAIL STUCK when nothing
  moves it. INCONCLUSIVE ELEVATED (final, never counted by the breaker) only for an item more than 0.5 m above the
  player's feet that the walk came no closer than 0.5 m to, or more than 1.8 m above them. New kind `movable_control`
  (`plan-movable`): an item placed in a vanilla cell, walked over, then pushed; a `SetRigidBodyMass` test is judged only
  when `GetMass` reads the mass set back. Synthetic tests and sandbox scenarios; runner features `impulse`, `push_judge`.
- **Staged, not run:** `movable_control_1013b` in QASmoke (replacing `movable_control_1013`, planned before these fixes):
  five vanilla items (a bin, a cigarette pack, notepad stacks 5.7 and 3.8 cm, a folder) next to our trash can, pack, pin
  box and book, plus the book and box at 5 kg via `SetRigidBodyMass`. Each test wrote its expectation first. If the
  vanilla items move where ours do not, or the 5 kg copies (GetMass read 5) move where the originals do not, mass is the
  cause and the converter should scale FO4 masses.

## 2026-10-14 Claude: PR #110 fix pass checked, the console route to the mass confirmed, suite re-run (offline; no game input)
- The verifier's three blocking findings are fixed by 18081d6 (only the walk passes a movable test, ELEVATED only when
  the walk came no closer than 0.5 m to the item, a `SetRigidBodyMass` test judged only on a `GetMass` reading) and its
  minor findings in the docs. This pass re-checked them against the reads and did the check the second finding asked
  for: Starfield.exe 1.16.244's command table, read with `scripts/recon_console.py`, has `CallFunction` (`cf`, "Calls a
  papyrus function on the targeted ref. First parameter is the function, the rest are parameters", one String and up to
  seven optional Strings) and no console entry for `GetMass` (a Papyrus ObjectReference native), so `cf
  "ObjectReference.GetMass"` is the only console route to the mass. The 5 kg tests stay in the queue and are
  INCONCLUSIVE MASS without a number read back (docs/ai/test-queue.md "Movable items", research-log 2026-10-13).
- Full suite with the qstep sandbox: 1013 tests OK (2 skips); `scripts/guard.py` ok.
- Queue `movable_control_1013b` (planned at 18081d6, an ancestor of this head, so the runner takes it as it is) is the one
  to run; `movable_control_1013` is marked superseded in its staging README and must not run.
## 2026-10-13 Failure summary enhancement (Grok)

convert_batch.py now prints failure counts with percentages and unique-reason totals, and writes
staging/failure-summary.json (top 10 reasons) for later review. Synthetic test covers the summary
shape and percentages. Offline only; no game data or format changes. Guard and new test pass.

## 2026-10-13 Codex: preserve evidence before reclaiming storage (#105)

Added a private lossless capsule tool and [storage procedure](testing/progress-storage.md).
It checks every archived byte against a SHA-256 manifest, rechecks the source, and publishes
without overwriting an earlier capsule. It never deletes sources. Independent Ptolemy QA
caught Windows restore-manifest aliases and archive-ancestor junctions; both are fixed with
regressions. Validation:19 focused tests (1 privilege skip),330 suite tests (3 skips), guard
and22 independent adversarial cases pass, including a real Windows junction regression.

Private application preserved846 files/87 images in10 verified capsules:265,527,468 original
bytes stored as185,228,667 archive bytes on a second local volume. A PowerShell restore plus
independent file hashes verified all10 original files in a selected capsule.191 inactive,
ignored Codex build outputs were then individually rechecked and removed, reclaiming
82,490,338 logical bytes on the source volume; archives/index/cleanup receipts retain them.
Temporary restore copies were also individually checked and cleared. Native campaigns,
source pins, saves, recovery data and Claude's active queues remain at their original paths.
This is local storage; no offsite backup or game acceptance is claimed. Private archives and
machine paths are excluded from Git. Shared coordination: #32 comment6159604237.

## 2026-10-13 evening: library stairs STUCKs: mostly the routes; 0002 / 0003 unresolved (Claude, offline)

- **Question (owner):** the player gets stuck on BostonPublicLibrary02's BldDecoSm* stairs (batch_full 0002, 0003, 0006,
  0007, 0021 STUCK, 0022 FALL) and on Vault 114's cinder blocks (supervised_1011 0010).
- **Result:** 0006 / 0007 / 0021 / 0022 / supervised 0010 asked for a walk Fallout 4's own collision does not allow: a
  start wedged in a 0.49 m slot between a wall and a rail (0006 / 0007), a fallen floor chunk across the flight (0021),
  a walk 2 m past a top that ends in the collapsed floor (0022), a 0.15 m remainder of a buried flight (0010);
  batch_full 0423 (rebar on the flight) and 0136 (a start 1.5 m over the floor) likewise. The 16 stair models
  re-converted with this branch read back body for body identical to the pinned build and to FO4's treads; neighbours
  match FO4 to 2 cm; only the steep stair helpers are flattened, as designed.
- **Correction after QA (PR #111):** this entry first said all of them were routes. 0002 / 0003 came up onto the gallery
  slab and stopped 0.01 / 0.05 m before the place where the converted, flattened helper comes up through the slab
  (0.46 / 0.50 m from FO4's own crossing); the slab lift had worked. Why they stopped is unresolved; the converter's
  flattening is a live suspect, the old routes' start under the slab another. The offline walk's agreement with the
  game is 59 of 64 verdicts, 57 also at the same place (0002 had been counted at the wrong place); the 0.35 m capsule
  radius is an assumption again (0002's push-out was read off the wrong face).
- **Fixed in the planner:** `routes.py` walks every lane offline (`src/fo4sf/walksim.py`) and keeps the first one a
  player can climb, or skips the stair with the reason; tilted references are placed Z first, as FO4's precombines show
  (the old order put the library's debris up to 1 m off). Routes carry what the walk cannot vouch for (a converted
  helper crossing, movable objects on the lane); `--probes-out` plans probes around each crossing;
  `scripts/game/stairs_calib.py` replays in-game results and route files. New routes for the 16 cells: 214 (226
  before); every stair that passed in game is still planned, 13 of them on new lanes (their old routes are queued as
  controls).
- **Not run in game.** Routes and probes in `C:\Modding\staging\stairs_fix_1014` (no new plugin or archives); three
  queues planned (probes, old-route replays, the new routes), readings in
  [docs/testing/stairs-routes.md](testing/stairs-routes.md). Left open: VltGearDoorStairs01 (no stair helper, 0.3 m
  treads; STUCK at 1.41 of 3.22 m on 2026-10-09), probably too steep a step for Starfield's controller without a
  helper (supported hypothesis, V111 2026-10-08): a synthesized helper would be a converter change of its own.

## 2026-10-14 evening: integration-1014, the owner's master handoff, tonight's batch (Claude)
- **Owner's handoff** (`team-handoffs/2026-10-14/FO4SF_Extensive_Research_and_Master_Handoff.md`, local): packets R01-R14, the
  roles (Claude lead and live game, Codex review / persistent IDs / deployment, Grok oracle and diagnostics), and the claim
  ladder every report must keep apart: converted, placed, interactive, persistent, campaign-tested.
- **`claude/integration-1014` (ef30495):** integration-1013 (68adac4) plus the reviewed fix heads #107 2e3c961, #103 4e0ad9d,
  #110 612a245, #113 b2af212, #112 507c21f, #111 fa9c5b3. Six conflicts resolved by hand (runner FEATURES now
  door_frames / door_route / walk / impulse / push_judge / npc_combat together; testqueue's plan-walk and plan-movable
  side by side; the sandbox fake game's walk keeps the ground model and the door branch's `walk_dz`; both research-log
  entries). One post-merge fix: `plan()` passed `routes_dir` positionally into `impulse`'s slot. Unit suite 1221 OK
  (69 skipped), qstep sandbox 66 OK (51 min), guard ok, `make_cave_core64c.py check` 11/11 PASS on build 2470f876.
- **Runner checkout:** `fo4-to-starfield-wt\integ` detached at ef30495 (the branch lives in the session worktree). Queues
  planned on it: `walk_core64c_1014` (2 walks, needs light + walk, core64c installed by the runner), `cave_core64c_1014`
  (1 door_trip, fix A plugin, both legs routed), `npc_combat_c1_1014` (3 npc_nav with combat reads), then the three
  night-site texture queues as optional. Chain started 20:23 MDT with the owner away ("run now, I'm stepping away").
- **merge_ctrl_lc172 (2026-10-13, read today):** the vanilla persistent COC marker 0010238E reads **merged** (offset
  -500 / -2300 / -3.62 from its local position, already in door-frames.md); probe lc172_7 matched its BTD height within
  0.02 m, probe lc172_0 read 6.17 m low standing in a hollow between boulders (pt0.png: supported hypothesis). The
  FAIL HEIGHTS is the probe spot, not the merge.
- **R05 plan** (PR #119, docs only): a 12-ref cluster within 21 m of the core64c Red Rocket arrival (medkit container,
  garage cabinet persistent 0.7 m east of x = -1000, stimpak / newspaper / Cram, the shop terminal and button box, one
  trigger box, WoodCrate01 -> 02 enable parent plus MetalTable02 as the opposite-state twin), built as an extension of
  the cave-slice add-on plugin (SliceDoor way, FormIDs 0x810-0x87F), never by inserting bases into TerrainOverlays
  (its `NewKey()` is a positional counter: one inserted base renumbers 648,358 REFRs). Mutagen 0.55.0-alpha.67 has
  CONT / ACTI / TERM / MISC / XPRM / XESP but no ActivateParents (verified by a reflection probe). Not implemented.
- **PR #69 QA (Grok's oracle, 199cf7d):** needs one change: position aliases (`pos` / `xyz` / `position`) take the first
  truthy value and never compare the rest, so a disagreeing or empty alias still passes; huge ints raise OverflowError
  instead of UNREAD. 272 tests OK, guard ok. Posted on the PR.

## 2026-10-14, 21:28-21:36: the observation bridge works in game (Claude; the owner watching)
- **Owner's review and decisions** ("FO4SF Mass Review", 14 Oct): D1 a bridge replaces OCR reads, D2 integration-1014
  lands on main (PR #121; 24 superseded PRs closed), D3 game time only in declared windows, D4 Codex / Grok on R07,
  R02, R06 after their quota resets; the local agent is a librarian for the lead, not a planner.
- **Bridge GO:** FO4SFBridge.esm (a global and a start-game-enabled quest carrying `FO4SF_Bridge.psc`, compiled with the
  game's own PapyrusCompiler against ContentResources.zip) writes `FO4SF rt=.. pos=.. ang=.. cell=.. world=.. loaded=..
  n=..` to `Logs\Script\User\fo4sf.0.log` every 0.66 s. Verified in one 8-minute session on the pinned build: 473
  lines, a 2 s walk read as 1.64 m, the timer and state survive a save/load (the log rotates on each load), and
  `cgf "Debug.TraceUser" "fo4sf" "ack 7"` from the console lands in the same log within a second. Refuted: the console
  cannot `set` our global (no EditorID strings for the plugin; form ids not accepted by `set`). Details:
  docs/ai/test-queue.md "Bridge". Media: docs/media/bridge-console-ack-1014.jpg, bridge-vault111-1014.jpg.
- **Two environment facts:** input.ps1 needs `LEGACY=1` for the console (every runner script sets it; a bare call does
  not); Windows Controlled Folder Access blocks our scripts from writing in Documents, so the Papyrus logging keys live
  in the game folder's `Starfield.ini` (backed up).
- **Earlier tonight:** both walks of walk_core64c_1014 unread (HUD dial split the console lines for OCR; fixed at
  ccddf80, verified on the captures only); chain stopped; the bridge makes that fix the last OCR repair.
- **Next:** runner feature `bridge` (positions from the log, console batches acknowledged by a TraceUser nonce) for
  walk, door_trip and npc_nav; then the three gates in the owner's next window.

## 2026-10-14, 22:00-23:00: the runner reads the bridge; four queues staged for the next window (Claude)
- **Runner feature `bridge`** (e22cf82, dde3ec4, ec9bd40, 31da8cf): `plan-* --bridge <staged bridge>` marks every test
  `bridge_reads` and pins the bridge's files; `bridge_install.py` deploys it before each launch under its own record;
  qstep's `Read-Pos` for the player and the walk's reads come from the game's log (`obs.read_log` `via: bridge`); the
  attempt folder keeps a copy of the log (`bridge.log`). Sandbox: the fake game writes a bridge log; the walk passes
  with bridge reads and types no getpos. The console whitelist takes the bridge's cgf lines (`FO4SF_Probe.Pos / Ack /
  Player`, `Debug.TraceUser "fo4sf"`); `bridge_log.py events | wait-ack` read the probe's replies.
- **Staged, not run (owner's window, D3):** `bridge_probe_1015` (vanilla LC172: does cgf load the unattached
  `FO4SF_Probe` script? five console lines, replies in the log), then `walk_core64c_1015`, `cave_core64c_1015`,
  `npc_combat_c1_1015`, all with bridge reads on build 2470f876; `chain_queue.txt` lists them in that order.
- **Noticed:** `tests/test_archive_identity.py::test_archive_modified_during_hash_is_rejected` fails under CPU load
  (a timing window) and passes alone; not touched. Grok's headless instance of 19:37 never got a reply (credits at
  100 % until 23:44); it now runs in a visible terminal on the owner's PC.

## 2026-10-15, 23:00-02:30: the walk gate passed; the bridge's first night; fix A refuted (Claude)
- **Walk gate (R04 part 1) PASSED both ways** (`walk_core64c_1015`, build 2470f876 + core64c, bridge reads):
  Sanctuary -> Red Rocket 29 legs, 253.8 of 254.33 m, |dz| <= 0.14 m; Red Rocket -> Sanctuary 28 legs, 254.0 m, 7 reads on
  the north bridge deck, cells crossed in route order; every read from the game's log, the console only to aim.
  Media: docs/media/walk-s2rr-*.jpg. One attempt aborted at 00:00:03 when something took the foreground (the guard
  held; the re-run passed).
- **Bridge, first night:** two reader bugs found by the probe runs and fixed (freshness by the line's clock stamp;
  planet form ids print negative and did not parse: every planet read saw the last Vault line); `cgf` loads the
  unattached `FO4SF_Probe` script (three runs); the bridge plugin must load LAST (an earlier line shifted every
  experiment's load index; cycle.ps1 now runs `bridge_install.py order` before launch). A 330 s poll showed the log is
  not buffered (a line is on disk within 1 s while the game runs; nothing while paused).
- **Cave door, A/B (cave_fixA_1015, cave_probes_1015):** fix A (vanilla persistent-cell shape) leaves the persistent
  door reading its unmerged local position: the player stood 1.0 m from it, no load (**refuted**). The probes'
  override of exterior cell (-10, 11) makes `coc FO4Core_RedRocketSpawn` land at (50, 50, 12.6), the centre of cell
  (0, 0): an add-on must not override a core64c exterior cell (**verified twice**; mechanism a supported hypothesis).
  Next candidates for the door: the WRLD OFST / CLSZ fields, or a temporary door ref in the exterior cell.
- **Combat (npc_combat_c1_1015):** reply formats verified and the parser fixed (`GetCombatState` prints "The actor's
  combat state: N.00"; `GetLineOfSight player` prints "<actor> sees / can't see <player>"). Citizen FAIL NOCOMBAT (the
  negative control, as designed); the vanilla Spacer engaged in attempt 1 (state 2 -> 1, target the player) and not
  in attempt 2: engagement of a spawned hostile within 30 s is stochastic; the converted raider never engaged and
  never moved. The gate needs a forced engagement before the raider's result says anything about the conversion.
- Also: docs/ai/first-run-failures-1014.md (twelve first-run failures, causes, guards); `input.ps1` defaults to the
  legacy key path; the walk-plan key `bridge` (the deck) and the test flag `bridge_reads` are different things.

## 2026-10-14 Codex: source-archive read guard (#117, offline tested)

Reproduced a stale archive identity with an equal-size synthetic overwrite and
deterministically unchanged metadata. The original returns the old digest; the
guarded Windows reader refuses the writer. Two earlier full-suite failures remain
preserved rather than replaced by passing retries. Acquisition now denies writes,
writable mappings and deletion/rename during hashing and the final metadata check;
existing readers work. The persisted identity format is unchanged. Sources still
must stay immutable for the entire conversion run; POSIX has no new exclusion.

Independent QA passed21 narrow sharing checks and caught a late stream-construction
failure that could close a reused descriptor. The context manager now keeps explicit
descriptor ownership with a non-owning stream; an actual late `io.open` exception and
descriptor-reuse regression fails before the fix and passes afterward.

Validation:14 focused checks,341 Windows suite tests (3 skips), guard pass. Independent
ownership re-review passed14 narrow checks including the original late-failure counterexamples;
hosted Linux CI passed. [Contract and limits](testing/archive-fingerprints.md). No live game,
source archive, deployment, queue or save was changed.

## 2026-10-15 Codex: preserve bridge deployment recovery (#124, offline tested)

Reproduced an interrupted copy leaving a partial plugin untracked after uninstall
removed its receipt. The installer now uses exclusive source-validated publication,
resource verification, file intent/confirmation and activation/profile journals.
Unknown, changed or unconfirmed files remain with a recoverable receipt. Existing
complete legacy installations stay compatible after validation.

Independent QA passed43 safety probes and found two P2 gaps: incomplete recovery
could touch a different current profile, and a completed uninstall retry could
duplicate a restored inactive line. Both are fixed;17 independent fix probes and7
targeted tests pass. Claude's bridge-last order change c50e87c is integrated with
the recovery-aware caller and ownership checks. Final ordering integration passes
23 independent probes and9 selected tests; hosted CI passes.

Validation:43 scoped/1301 Windows suite tests (70 skips), guard pass. No source
installer was deployed, no game/queue/save changed. Cave a1 remains invalid; a
separate serialized metadata comparison confirms the COC marker is temporary and
the template grid is INT_MAX, supporting Claude's queued A/B without proving cause.
[Recovery boundaries](testing/bridge-recovery.md). Historical negative cases retained.

## 2026-10-15 morning: integration-1014 is main; the next window's queues (Claude)
- **#121 merged (10e7019)** after Codex's bounded merge-preservation review; main 9c291f1 (Codex's archive fingerprint
  guard, #120) merged in first. The runner worktree is pinned on main; new work goes on short branches off main.
- Codex owns the bridge_install recovery correction (#125, found by their review: a failed copy left a partial plugin
  untracked) and the door gate's next candidate (a slice variant whose WRLD override carries OFST / CLSZ like a vanilla
  overlay world). Row 11 of first-run-failures corrected to their verified #117 finding.
- Planned for the next window: `npc_combat_c2_1015` (StartCombat player on the Spacer and the converted raider; the
  citizen uncommanded) and `cave_probes11_1015` (PR #126: the merge probes in neighbour cell (-11, 11): does any
  exterior-cell override move the coc arrival, or only the COC cell's). R05's plan revised (PR #119): the cluster goes
  into core64c's own build; no exterior-cell overrides from add-ons.

## 2026-10-15 Codex: October14 recap and current front-page progress

Owner requested yesterday's progress on GitHub. README separates the October14
Mountain-time load-order and observation-bridge milestones from October15's
lead-reported walk/cave results. Corrected the obsolete phase03 hold and superseded
branch statuses; merged code is distinct from proposed recovery/audit work.
Reused the tracked Red Rocket walk and Vault111 bridge-session JPEGs unchanged;
no media added. Captions distinguish scene illustrations from logged measurements.
No complete-gameplay, ground-texture or native-acceptance claim.

Sources: main10e7019 JOURNAL, bridge session32a5f5b, #32 comments6165570079,
6154661951 and6187749682, current PR/QA records.24 local link/anchor targets and
both unchanged media identities pass; GitHub GFM renders the new sections/images.
Independent factual/link QA passed, with draft status made explicit. Guard passed.
No new unit tests for documentation; hosted CI is checked on the PR. No game,
runner, installation, queue or save changed.

### 2026-10-15 Codex: preserve original reference slots during R05 promotion (proposal)

PR134 removed a source before sequential allocation; the real parent writer reproduces the later-ID shift on a
synthetic master. The isolated companion retains original reference_index, reserves all REFR slots and reuses the
promoted source's key, appending only CONT bases. Canonical Claude checkout/production stages/game are untouched.
29 producer tests and three actual-writer methods pass (four promotion scenarios and five publication refusals).
Survivor IDs/record data/cell ownership match; no-cluster output is byte-identical to parent. The declared-slot
check rejects the parent artifact and accepts the four candidates. Initial anchor-fixture failure is retained.
Release builds pass; the existing CA1831 inventory-parser warning remains. Peer QA, a fresh full-scale candidate,
all-ID/raw-record comparison and newly pinned native plans/save tests remain required. Full persistent allocation
across reordered exports and future promoted bases is still open. See testing/container-reference-identities.md;
private evidence is test-plans/container-reference-identities-20261015. No native acceptance is claimed.

## 2026-10-15 Codex: bridge recovery on consolidated main

Merged main d628b56 into the owned PR125 branch without rewriting history. Resolved
only documentation conflicts: both append-only journal/decision histories remain;
current-main concise ownership status is retained. Bridge installer, deployer,
experiment installer, cycle caller and43 bridge tests have identical Git blobs to
independently reviewed4c8ded6. Bridge-last/no-op exit0 behavior is unchanged.

43 focused bridge/order/recovery tests and1,305 Windows tests(70 skips) pass.
Independent five-invariant integration review passes; original source QA remains
applicable. Guard passes; new-head CI gates ready status. No live profile, archive,
installation, queue, watchdog, controller input or save changed. Source only,
undeployed; Claude retains integration/game ownership.

## 2026-10-15: Codex — reserve stable IDs before plugin output (#132)

Synthetic main d628b56 repro: a directory blocking formids.json caused an error
after a192-byte plugin had already been created without a saved ID map. Two new
writer tests failed in three cases: creating a new plugin, replacing an existing
plugin before map failure, and losing reservations when plugin output fails.
Map publication now flushes a same-directory temporary JSON file and replaces the
map before plugin writing. Map failure leaves plugin bytes untouched; later
plugin failure retains IDs for retry. Existing JSON format and tombstones stay.
No converter/runner, live installation, game input or native data changes. This
is single-writer identity preservation, not a complete plugin transaction or
proof of savegame compatibility. Release build has zero warnings/errors;3 writer
tests,1279 Windows suite tests(69 skips, writer enabled), typed door binary tests
and guard pass. Independent Locke QA passes locked-map preservation, sparse JSON
compatibility and missing-Data-setting controls. Original harness assertion
failure and its correction are retained with results. #132 pins publication.

## 2026-10-15: Codex — custom-prefix checkpoint dependencies (#130)

Offline synthetic repro on main d628b56: with signature prefix `preview`, the
checkpoint tracked only model/geometry. Deleting its material and texture still
returned a reusable result and no final inventory errors. Four new tests produced
13 failing subcases before correction. Checkpoints now passes the signature's
prefix into both inventory calls; namespace matching normalizes separators/case.
Tests cover default/custom/mixed-case/nested prefixes, missing/changed material
and texture dependencies, and rejecting old incomplete inventories. No pipeline,
runner, native data, installation or live game changes.27 focused tests(1 skip)
and1281 Windows suite tests(70 skips), guard and diff checks pass. Independent
Anscombe QA passes three additional controls, including a genuine pre-fix cache
and backslash namespace. #130 records pinned results; native acceptance is
outside this correction.

## 2026-10-15: Codex — validate persistent FormID reservations (#137)

Synthetic binary repro on main4ba5c6a: a stored0x01000800 survived in the
map but serialized as local000800; a uint.MaxValue tombstone wrapped the next
allocation to zero. Valid sparse IDs round-tripped. Four new writer tests
produced seven failing subcases before correction, including duplicate JSON
keys, duplicate inactive reservations, and a failed allocation that still
published its unusable reservation. Original outputs/logs are retained.

PluginSpike now validates the complete map before constructing records:
unique decoded keys and values, integer IDs within this writer's000800..FFFFFF
range, including tombstones. New identities cannot exhaust/wrap the range;
existing IDs at the limit remain reusable. Save independently validates before
atomic publication. Invalid/exhausted inputs preserve both prior map bytes and
plugin bytes. Release build has zero warnings/errors; seven writer checks,
1308 Windows tests(69 skips), guard and independent Mencius QA pass. QA covers
direct Save validation, escaped-equivalent duplicate keys and binary IDs on
an exhausted-map rebuild. Native handling of its one-past-last HEDR.NextFormID
remains unverified; these are offline controls, not native acceptance.
No source IDs were repaired/reassigned, no native campaign was rescored, and
no stages, game installation, controller or input changed.

## 2026-10-15 afternoon window: R05 slice 1 in game, the raider fights, cave probes crash (Claude)

Chain 12:59-14:39 on the pinned build 2470f876 (runner scripts 10e7019), started on the owner's word while away.

- **R05 slice 1 (`r05_medkit_1015`, core64d, PR #134)**: the native container reference loaded at the planned place. The
  bridge's probe reply in both game sessions: `FO4SF ref=34220709 pos=-2193.137207 -1548.338501 105.296318 ang=270
  cell=33557935 disabled=false loaded=true` = local (-993.14, 1151.66, 105.30) + the merge offset (-1200, -2700). Runner
  verdict INCONCLUSIVE for the runner's own reasons: the console_post echoes were unreadable by OCR (the compass dial
  crosses the text; the commands executed), and the bridge log stopped at 13:24:09, exactly at the `by_the_kit`
  teleport, and never resumed in that session, so every later read was stale and the player "stayed" at the arrival.
  Cause open (console left open, so menu mode pauses the script? the script stalled?); the next run captures HUD
  visibility right after the teleport. No kit screenshot yet; the owner's open-the-kit check waits for it.
- **`npc_combat_c2_1015`** (forced `StartCombat player`): the converted FO4 raider PASS ENGAGED from t = 1 s (combat
  state 1, target 00000014, line of sight 1, 5 of 5 reads); the vanilla Spacer PASS on its second attempt (the first:
  spawned 6.06 m away against a 6 m confirm limit; widen to 7 m); the uncommanded citizen FAIL NOCOMBAT as designed.
- **`cave_probes11_1015`** (PR #126's slice variant: merge probes in neighbour cell (-11, 11)): INCONCLUSIVE CRASH twice,
  the game exited during the `coc` into the world (the bridge's last lines are in the Vault at 14:36:24; arrival never
  logged). With the COC cell override the arrival moved (cave_core64c_1015); with a neighbour-cell override the game
  exits. Add-on overrides of core64c exterior cells are out in both forms; the door gate stays on Codex's OFST/CLSZ
  world-level variant or a temporary door inside core64c's own build.
- `chain.ps1` ended without its "chain end" line and without the between-queue uninstall (process gone by 14:39);
  the experiment was uninstalled by hand afterwards. Unexplained; watch the next chain.
- Merged after a local testing state (main + the PRs: 1093 unit tests with the venv, guard, PluginSpike Release build and
  its two writer tests): #69 (Grok's oracle), #126, #119, #127, #131, #133. The owner's "script command not found"
  question answered: `readpos.ps1`'s nonce (first-run-failures row 13).

## 2026-10-15 evening chain: the walk holds on core64d, the raider fights twice, the Red Rocket probes do not move (Claude)

Second chain of the day (16:31-19:00, runner scripts 64d30ad, build 2470f876), on the owner's "keep working never stop".

- **walk_core64d_1015 PASS**: Red Rocket -> Sanctuary on core64d (core64c + the native container), 29 legs, 253.9 of
  254.33 m, |dz| max 0.14 m, every read by the bridge. The R05 build does not regress the walk gate.
- **npc_combat_c3_1015 / c4_1015**: the vanilla Spacer PASS on its first attempt with the spawn confirm limit at 7 m
  (6.06 m had failed it in c2); the citizen control FAIL NOCOMBAT as designed; the converted raider INCONCLUSIVE SPAWN
  twice in c3 (`Item '02F04800' not found`) because c3 was planned without `--install-exp actor_raider2 --plugins
  FO4ActorRaider.esm` (the bridge log shows FO4Port.esm at load index 03 in c2 and 02 in c3), then **PASS ENGAGED** in
  c4 with the plugin installed: two runs, two passes.
- **r05_medkit_1015b / c / e** (two kit-facing probes; c with `time_repin` off; e with no time commands at all): the
  container reply every time (`ref=34220709 pos=-2193.137207 -1548.338501 105.296318 loaded=true`, eight confirmations
  today), and every time the player stayed at the arrival through both probes while the bridge read fresh (read 3 at
  rt 415.9 in b). Not the noon re-typing, not SetLocalTime: on this arrival of our worldspace `player.setpos` has no
  effect, while the same code moved the player on vanilla LC172World (bridge_probe_1015c). The per-attempt papyrus.log
  (#144) shows only vanilla location-script noise. Next: `teleport_console` (the teleport's own console session
  captured: the game's reply to the typed lines) and the `activate` step (#145), both in `r05_medkit_1015d`.
- Runner: #144 (papyrus.log per attempt) merged; #145 open (activate step + teleport_console); #125 (Codex's
  bridge-install recovery) merged after a testing state; the runner worktree moves to main after this chain.
- Lesson of the day, twice: a queue re-planned for one parameter must carry every argument of the queue it replaces
  (c3), and a log watcher must never hold the chain's log open (the morning's "dead chain").

## 2026-10-15 night: the first FO4 container opened in Starfield; why the Red Rocket probes never moved (Claude)

- **R05 slice 1, interaction**: `r05_medkit_1015d` a1 (20:10, runner f60f4d6 with #145): the activate step selected the
  kit's reference in one console session (`prid 020A2AA5`, `GetIsID 020A2AA4 >> 1.00` read before anything else was
  typed: Codex's review), typed `activate player`, and Starfield's container UI opened on the converted FO4 first-aid
  kit: FIRST AID KIT, Credits 25, Digipick 1, OCR'd as `read ['First Aid Kit', 'Credits', 'Digipick']`
  (docs/media/r05-firstaidkit-menu-1015.jpg, #156). Record level (the bridge's probe reply, nine times today) and
  interaction level are done; the owner's own E-press stays the last word.
- **The probes, explained by the teleport captures** (`teleport_console`, #145): the console accepted `player.setpos z
  40` without a word. 40 is an absolute height in the worldspace frame and the Red Rocket ground is at 105.26: my
  acceptance plan had copied LC172's `drop_z 40` (ground at 6), so every probe and the "beyond" jump were sent 65 m
  underground; the player stayed put, the beyond jump fell out of the world and that is what stopped the bridge in
  every r05_medkit run. Not the time commands, not the worldspace. `drop_z` 145 from `r05_medkit_1015f` on. Rule:
  a terrain plan's `drop_z` is absolute; use `drop_above_spawn` when the ground height is not known.
- **The menu exit**: Starfield's container UI says BACK / HOLD TO EXIT on Tab; the step's tap only went back a level,
  the menu stayed open, the next console open failed three times and the attempt stopped (INCONCLUSIVE STOPPED).
  #157: a held Tab (1.2 s), the HUD checked on the closing capture, a second hold when it is not back.
- Merged after testing states: #145 (activate step, teleport_console, selection proof), #138 (Codex), #156, #157.
  Codex's #150 (keep the source REFR's id when a static becomes a container) is the next R05 correctness item: my
  `cluster_containers` removes the kit's placement and appends the container's REFR after every other record, which
  shifts the ids of the references placed after the kit; Codex's draft keeps the id. Taken when it leaves draft.
- **`r05_medkit_1015f` / `1015g`** (runner 2e017aa / e26897c): the teleports work at drop 145 and the activation reproduced
  with the selection proof and the held-Tab exit (the attempt ran to its end). Both kit-side probes landed at 110.2 /
  110.7 and the arrival probe at 110.49: the station roof and the fuel canopy; the kit is inside the building and the
  arrival marker under the canopy, so a drop from above lands on them (plan artifacts, not terrain). The selection proof
  also read the game's `>> 1.00` on the line under the echo once (the OCR splits rows under the compass dial): #158.
  `r05_medkit_1015h` (core64c's verified probes zref_ground / wp_01 next to the activation) was stopped at 21:01 by the
  input guard (another window took the foreground: the owner at the PC) and waits for the next window.

## 2026-10-16: core64n navmesh.convert over the 64 x 64 core (Grok)

Offline. `navmesh.convert` on Commonwealth NAVM in FO4 cells -55..54 (same Fallout4.esm as #163,
sha256 `ae7be31a…`). 7,047 NAVM / 3,439,338 triangles → 12,104 Starfield NAVM / 3,749,066 triangles,
156,549 cell-line pairs, 134,876 FO4-portal pairs, 0 refused ids. #163 inventory: 1,069 overlay cells
all still covered (0 lost / 0 reduced). Red Rocket smoke matched exp2d (105 → 156 NAVM, 2,145 / 1,959
links). Geometry in staging `terrain_core64n_work/navmesh/` (navmesh.json 433,902,356 B), not git.
Report: docs/actors/navmesh-core64n-convert.md. Not in-game; writer into FO4TerrainCore.esm is Claude.

## 2026-10-16 night: from the slice to the Commonwealth: plan, R06, the navmesh writer, bridge ref reads, the cluster lists (Claude)

The owner's direction (15 Oct 21:30): push Grok, get everything ready for Codex's two items (#150 identity-keeping
promotion, the door gate), finish the slice, start the whole Commonwealth.

- **What the Commonwealth is from here** (docs/terrain/commonwealth-build-plan.md, #162, decision recorded): the 64 x 64
  core already covers the playable Commonwealth's exterior (6.4 km; 648,358 references of 11,769 models over 1,708 FO4
  cells, FO4 cells x -53..33, y -49..41); the scale-up is record classes, interiors and navmesh across it, not more
  cells; one plugin for the exterior (the record count is far under the 16.7 M FormID space), interiors stay in
  FO4Port.esm, joined by the door gate.
- **R06 (Grok, #163 merged)**: FO4 authors 7,047 NAVM / 3,439,338 triangles / 9.08 million m2 over 1,069 of the
  overlay's cells; `FO4TerrainCore.esm` has **0 NAVM** (664,229 records walked). Every NPC result so far was on
  interior navmesh or in a vanilla cell. Grok now runs experiment 2d's converter (`navmesh.py convert`) over the whole
  core (11 export bands, C:\Modding\staging\terrain_core64c_work).
- **The navmesh writer (#165 merged)**: experiment 2d's NAVM/NAVI writer ported from TerrainExp2 into TerrainOverlays
  (`overlays_params` `navmesh`, `make_core64c.py stage --navmesh`, `check` 2b), because the NAVM records must come from
  the core's own build (an add-on override of exterior cells is ruled out in game). Dry run on exp2d's navmesh.json:
  156 NAVM, 68,132 triangles, 8,208 edge links, NAVI with 156 NVMI, every NAVM parsed back: the same numbers as 2d.
- **Reference reads through the bridge (#164)**: `Bridge-Ref-Read` types `cgf "FO4SF_Probe.Pos" <ref>` and
  `bridge_log.py wait-ref --since <mark>` returns the reply written after the mark; readpos's OCR only as the
  fallback; the sandbox's fake game answers the probe (actors, statics, the anchor, door refs). A door trip in the
  sandbox passes with every door read `via bridge-ref` and no `prid` typed. Two lessons: a sandbox suite copies the
  worktree's scripts per test, so the branch under it must not change while it runs (one run voided); `dotnet run`
  passes `-nologo` / `-v` through to the program (a dry run read "-nologo" as Starfield.esm).
- **The cluster lists (#166)**: `make_cluster.py` reads the band exports and core64c's placed references: placed by
  FO4 base type, Static 573,663, StaticCollection 33,199, MovableStatic 12,379, MiscItem 10,770, Furniture 3,890,
  Flora 3,520, Activator 2,256, Ingestible 1,688, Container 5,212 (of 5,294), Door 1,262; Light 6,275, IdleMarker
  5,828, BendableSpline 4,982, SoundMarker 878 not placed at all. The containers list: 5,185 entries over **182 distinct
  FO4 bases** (116 named by the table exactly, 1,636 by prefix, 3,433 by its default), so the writer should make one
  CONT per FO4 base, not one per reference as the R05 slice did: that change rides on #150.
- **Loose items (#168)**: `make_cluster.py items`: 12,438 placed MiscItem / Ingestible references over 492 FO4 bases
  (10,754 + 1,684; 441 named by the table's prefixes). **Doors, measured**: 1,286 exported exterior doors, 373 of them
  load doors (a destination door reference); 18 lead into the 16 interiors FO4Port.esm has converted (13 cells; 15 of
  those doors placed by core64c), 355 into interiors not converted yet. So the door gate's first batch is 15 doors and
  the interior conversion backlog, not the gate, is the long pole of a walkable Commonwealth.
- **Ready for Codex's return**: the testing state of #150 passes (tests, TerrainOverlays build, guard);
  `rebuild_core64e.sh` rebuilds the R05 build with the identity-keeping step in one command; the door gate's OFST/CLSZ
  slice is planned as `cave_ofst_1015` (#129 itself needs Codex's rebase over #126). Grok's #148 was already merged.
- **One CONT per base (#167, stacked on #150)**: cluster entries carry the FO4 base; `cluster_containers` names the
  CONT from it, the writer deduplicates CONTs by edid (model must agree), the identity check accepts shared bases;
  the R05 hand-written entry is unchanged. 31 tests on #150's head; TerrainOverlays builds.
- Merged tonight: #162, #163, #161, #165, #166 (and the queue of the day before). Open: #164 (sandbox suite running),
  #167 (on #150), #134 (waits for #150), Codex's drafts #150 / #146 / #153 / #149, cloud-Claude's #136 (needs-qa).
- 22:47: the opt-in sandbox suite passed on #164 (68 of 68, 41 min, run from an idle worktree); #168 merged. Codex is back: full-size validation of #150 / #153 passed (every source REFR id and base id preserved) and an independent review of #167 is under way.

## 2026-10-16: preserve full source-plugin identity in container groups (Codex)

Offline synthetic review of merged1670f128805: disabled-reference refusal and metadata agreement work, but
plugin punctuation/extensions still alias distinct source bases. Three unit controls and all three actual-writer
plugin-pair subcases reproduce the failure. The identity helper now retains unambiguous legacy names and uses
the full key for other groups, normalizing ASCII case without Unicode expansion, with a separate collision refusal.
Four actual-writer methods verify distinct CONTs and preserved original REFR IDs/data/flags/parents.
See [the identity follow-up](testing/container-reference-identities.md#full-source-plugin-grouping-follow-up).
No C# writer, production stage, game input or save changed. Peer review/integration remain pending; existing
mixed-plugin aliases and future promoted-base migrations are not repaired retroactively.

### 2026-10-16: Codex extends full-source grouping to MISC

Merged current main into the owned PR176 branch after PR235 introduced shared CONT/MISC
promotion. Resolved the identity helper conflict by preserving both class wrappers and
full canonical source keys; added the same explicit collision refusal to loose items.
Five synthetic methods produce 13 failing subcases on PR235's reviewed caller; all58
focused Python checks pass with the fix. The compiled-writer tests now include three
MISC source-plugin pairs, preserving original reference slots and serialized placement.
Private evidence: promoted-identity-176-20261016. No writer source, staging or live changes;
independent review remains required. This does not fix the separate NaN output-check finding.
## 2026-10-16: Codex native bases for persistent door relationships

The owner's persistent-door priority led back to PR174's actual ReferenceLinks
rejection. Synthetic CLI controls reproduce two valid native-base cases rejected
(exit2), plus a deleted local DOOR override wrongly accepted (exit0). Resolve from
typed Starfield.esm records with local override precedence; deleted/non-door/missing
bases now refuse. Eight CLI cases and the existing relationship/binary suite pass.
Both persistent endpoints retain identity, transforms, grouping, flags, reciprocal
XTEL/transition links and open state after serialization. Original inputs/map stay
unchanged. No native DOOR cloning or ID allocation. Evidence retained privately at
test-plans/native-door-bases-20261016 (before, after and final).
This optional post-pass remains interior-scoped; PluginSpike owns primary load-door
writing. No exterior merge fix, live install/input, travel or save/reload acceptance
is claimed. Peer QA pending; Claude retains native controller.

## 2026-10-16: Codex both persistent teleport endpoints

PR245 follow-up reproduces three serialized failures: explicit false persistence,
missing persistence and one-way travel all left valid XTEL endpoints temporary.
The optional ReferenceLinks post-pass now applies the same both-endpoint persistent
group/flag rule as primary PluginSpike.TeleportLinks, after link validation. No
return link is invented and IDs/transforms remain unchanged. Eleven CLI/readback
cases plus library refusal-before-promotion/idempotence and prior relationship
checks pass; guard passes. Source failures and current evidence retained privately
at native-door-persistence-20261016. No primary writer, source stage, live input,
installation or game-state claim. Peer QA and merge/native-save gates remain.

## 2026-10-16: Codex independently inspects rebuilt persistent doors

Pinned integ_1011/integ_1016 raw plugins/maps: all54,877 map entries and master order
identical. One FortHagen pair remains the only two persistent DOOR/XTEL references;
endpoint fields/ancestry unchanged. All28 reported unlinked references exist and
lack XTEL (20 DOOR/8 STAT, all temporary); four reported unplaced source endpoints
have no map slots, including Red Rocket05E844. Six malformed flag/group/return-edge
controls detected. First inefficient audit loop stopped; initial all-unlinked-bases-
are-DOOR assumption disproved/corrected; both preserved. See
slice/persistent-door-rebuild.md and private persistent-interior-rebuild-20261016.
No source/game edits, newly connected interiors or native/save acceptance claimed.

## 2026-10-16 — Codex: explicitly selected missing interior door endpoints

ReferenceLinks now accepts --door-bases=JSON keyed by original source reference. Reproduced seven CLI failures: skipped allocation/reservation and ignored invalid selections. Valid selected exported Door records get verified active native/local DOOR bases, stable source-map IDs, persistent grouping, source transforms/disabled/open state; existing conflicting bases/owners and occupied reservations refuse. No guessed bases, synthetic return edges, primary writer changes or live actions. Seven new actual-CLI controls and eleven prior controls plus library/binary checks pass. Peer QA pending; see docs/slice/missing-door-endpoints.md. Private failed/passing fixtures retained under missing-door-endpoints-20261016.

## 2026-10-16 — Codex: actual missing cave endpoint candidate

PR251/code63131c6 exercised against private integ_1016/RedRocket01 snapshots and verified native24F9CE base. Strict mode exit2/no plugin retains missing08EB65 destination; explicitly partial candidate adds05E844 as local00DE5D, preserves54,877 map entries, no XTEL invented. Separate raw parser verifies group/flag/base/transforms/scale and compares all prior records: only header plus three original-export persistent promotions (05F97B/05FAA0/05FAA3), unchanged subrecord bytes. All source pins unchanged. Output cdd69d7b..., private missing-cave-production-20261016; initial wrong net8.0 harness path retained, correctednet9.0 run passes. No stage/install/input change; peer/native/cross-plugin integration pending.
## 2026-10-16: Codex explicit door selection requires an existing cell

Reproduced Claude's PR251 review finding: `--allow-unresolved` published a plugin
without an explicitly selected door when its cell map or CELL record was absent;
report-only also exited successfully for that omitted request. Selection preflight
now requires the mapped cell before mutation. Six new CLI scenarios pass, including
unchanged partial behavior for an unrelated missing cell. The targeted executable
also passes13 missing-door,11 native-base and relationship binary checks; guard and
diff checks pass. Failed/passing synthetic evidence retained privately in
test-plans/door-selection-cells-20261016. No real slots, staging, install or game
input changed; new correction awaits peer QA and carry-forward into stacked253.
## 2026-10-16: Codex scripted cave-door compiler packet

Following Claude's #32 request6222158841, added a separate player-only Papyrus
MoveTo candidate using plugin-local GetFormFromFile destinations, plus a compiler
wrapper that refuses stale output, failed compilation and input drift. Real CK
compile produces1713 bytes (a59e24848b7c3d74158a5cbca84c95ebd9eb70f886550496634ddb1f6eb9fcfc).
Nine synthetic compiler-boundary tests pass; these do not emulate activation or
travel. Private receipts in test-plans/scripted-door-20261016. Compilation remains
non-installable, runtime_accepted=false. No plugin/stage/game/configuration changed.
Current core/port pins and an ACTI interaction model are requested on #32: the old
core skipped source08EB65 and old port lacked05E844, so retained slots are not
assumed. Record attachment and both-way/save-reload acceptance remain pending.

### Codex response to independent PR243 review

Claude's independent review found no blocking code issue and compiled the script
twice. The earlier PEX SHA256 identifies one preserved private file, not a
reproducible build: compiler timestamps/debug/account-machine metadata vary.
Documentation now requires output outside all checkouts and qualifies Moving as a
non-atomic guard. Core64h/integ_1016 pins arrived on #32; ACTI design is pending and
no slots are allocated. Docs-only response; guard/diff checks, no repeated compile
or unchanged suite. Runtime activation, unloaded markers and travel/save remain
unverified. The original private compiler packet remains preserved.
## 2026-10-16: Codex persistent-reference inspector identity

A synthetic master override and local persistent reference sharing low ID800 were
both returned for either000800 or00000800. Keeping the selector's width separate
fixes this; four new methods expose seven failing cases before, all eight targeted
methods pass after. Signed/oversized/seven-digit IDs refuse; optional0x supported.
Preserved OFST cave bytes unchanged: local000800 equals encoded03000800, whereas
runtime-style05000800 selects nothing. Raw file IDs are not runtime load-order IDs.
Initial XCLC concern was disproved by the existing tests: unpack_from already
handles the fixture; no XCLC change made. No writer/stage/game modifications or
retroactive native rescoring. Private evidence: persistent-ref-selectors-20261016;
peer QA pending. Merge placement and native travel/save-reload remain unresolved.
## 2026-10-10 Claude: FO4 skin reader and pose bake (offline)
New `src/fo4sf/fo4skin.py` reads a skinned FO4 shape's skin (bone nodes from `BSSkin::Instance`, skin-to-bone
transforms and bone-space bounding spheres from `BSSkin::BoneData`, f16 weights and u8 bone slots per vertex) and
poses its vertices by linear blend skinning. Checked on `SkeletonClothed01.nif` and on all 16,350 skinned shapes in
the two FO4 mesh archives (0 read errors). Posing the skeleton with its own NIF nodes does **not** give back the stored
positions (max 64.45 units): its node pose is the bind pose with the root bone turned 45 degrees about X, and the
ragdoll bodies are in that node pose. With that one rigid transform taken out, the error is 0.000025 units. The
converter draws skinned shapes from the stored positions but puts collision on the nodes, so mesh and collision
disagree for 346 placements in the pinned build (95 skeletons; vault sink taps drawn at the model origin). Not
changed in this PR. Next: pose skinned shapes with `fo4skin` in `convert_nif` (check in game), then pose ragdoll
skeletons. Evidence: docs/ai/research-log.md.

## 2026-10-10 Skinned props posed as FO4 draws them (offline; owner at the PC touring the library)
Follow-up to PR #45's finding. `convert_static.pose_skinned_shapes` now bakes the NIF's node pose into every skinned
shape (linear blend skinning, normals turned with the heaviest bone), so the mesh lands where FO4 draws it and where
its bone-node collision already is. Real-data check: the Vault 81 sink's tap moves from the floor (model origin) to the
basin rim (1.13-1.19 m) with its water streams under it; the skeleton's mesh now matches its collision box exactly
(z 0.29-1.74 m). Animated NIFs are posed too (their rest pose) and flagged `skinned_posed_animated` in the manifest for
the in-game look. Tests 273 OK, guard OK (guard now skips `.claude/` agent worktrees). Not yet seen in game; expect
346 placements to shift in the next build (PR #45's scan). Ragdoll pose (XRGD, PR #44 export) comes on top of this.

## 2026-10-11 `XRGD` ragdoll pose decoded (offline, no game input)
- FO4's per-placement ragdoll data is readable now: one entry per physics body in body order, each replacing its bone
  node's local transform (parent-node frame, game units), rotation Rx(-x)Ry(-y)Rz(-z) like the NIF itself. Evidence
  and numbers: research log, same date. `src/fo4sf/ragdoll_pose.pose_bones(nif_bytes, entries)` returns the posed bone
  world transforms in reference space; 10 synthetic tests.
- Vault 114: 57 of 62 placements with `XRGD` pose; 53 of them rest on the surface under them (bind pose: 41). The two
  skeletons by door `05C7DC` lie flat (bones within 13 units of height, hull 1 unit under to 22 above the floor) where
  the bind pose stood 129 tall. 5 placements carry entries for another model (stale) and are rejected.
- Next: bake the pose into the converted mesh (skin weights, PR #45 / #46) and the rigid body, rebuild Vault 114, look
  in game. Side finding to check: the REFR rotation order `routes.ref_matrix` uses offline may be the wrong one
  (known unknown #7).

## 2026-10-16 Claude: posed props (owner playtest rows 4 c and 5; offline, no game input)
- Cause, verified: the pinned interior build `integ_1011` was made from `a5bc92e`, which has none of the pose work (PRs
  #45, #46, #52 were never merged), so every skinned prop was drawn in its skin's bind pose and no reference's ragdoll
  pose (XRGD) was used. The lab-coat skeleton of rows 4 c and 5 stands for that reason. The rad scanners are not posed
  models at all: same mesh as FO4, the tilted panel is authored that way and loses FO4's glow quad (a skipped effect
  shape). Details and counts: research log, same date.
- This PR carries #45 / #46 / #52 forward onto current `main` and finishes them: skin posed in the placed frame
  (`world_transforms(placed=True)`, as shapes and bodies), and a posed model of its own for each reference whose XRGD
  moves an articulated model (`placed_pose`, `PosedBases.cs`). Sampling the animated skinned models' sequences showed
  the node pose is an animation state of every one of them and the bind pose of none (the elevator's surface hatch lay
  on the vault floor in the bind pose).
- 16 interiors: 231 placed references change (180 skinned in the node pose, 147 with their own XRGD pose, 96 both);
  214 single-body loose items with XRGD stay as they are (unchecked frame for a root body). Offline end to end: 35
  models + 147 posed models converted in 54 s, plugin written and read back, 147 references on their posed base, 0
  wrong. Renders: docs/media/posed-props/. Not in game yet; the next interior build needs a full convert (the code
  digest changes the checkpoints).

## 2026-10-16 (afternoon and evening, Mountain time) - Claude: wave 1 merged, stations, the shooting crash found

**Builds.** core64h (exterior + navmesh + 5,185 containers + 12,438 loose items; check 253/253) installed packed for the
owner at 12:50; the owner confirmed in game that picking up loose items works (~14:30). integ_1016 (the interiors rebuilt
with #230 collision, #231 LOD triangles, #232 textures: 29 -> 0 collision errors, 54,877 ids unchanged) deployed 13:00.
integ_1017 (plus #242 vault door rigs through the CALUMI animation dll and #244 posed props: 4,346 models = 4,200 + 146
posed variants, 55,033 ids with all 54,877 earlier ones unchanged) deployed ~16:25. core64i (every promotion class:
containers 5,156, items 12,438, activators 2,246, terminals 140, lights 6,249 over 144 LIGH, workshops 29, benches 269 on
the vanilla Starfield FURN stations; check 263/263) installed packed ~17:35. Owner checks of the stations, lights, vault
doors and poses are pending.

**Merged** (each with a testing state: full suite, dotnet builds, guard, CI; wave 1 with one combined state of all six
and an independent adversarial review per PR): #230 #231 #232 #235 #237 #238 #247 #252 (code of conduct) #254 (CodeQL)
#257 #258 #259 #263 #264 #268 (docs), Codex #243 #245 #248 #251 #253, Grok #250, wave 1 #249 #240 #244 #242 #241 #246,
stations #266. GitHub code scanning (CodeQL default setup: actions, csharp, python) is on; its two alerts (header
splitting in the Guardian proxy) fixed in #254; 0 open.

**The shooting crash (owner playtest rows 3 and 18).** Refuted: the impact-material hypothesis (every material-like
value in our Havok bodies is a vanilla value). Found: Havok's assertion "Unknown primitive type in compressed mesh"
(hknpCompressedMeshShapeInternals.cpp:939, the int3 at Starfield.exe+0x36F418B in all 7 WER reports since 12 Oct) in
the compressed-mesh closest-points query of a particle body-collision job. The owner's ProcDump full dump (17.4 GB,
shooting a Vault 111 cog door) names the shape: vault_cart_01.nif (STAT FO4Port_Vault_Cart_01): numPrimitives 40, one
data run {0, 40}, yet the query reached primitive index 40: the converted tree's keys reference more primitives than the
array holds (FO4's key space covers its padding slots); slots with indices[1] == indices[3] (FO4 0xDEAD padding) read as
an unknown special primitive; FO4 section encoding flags&1 never occurs in vanilla. Affected: 18 of 2,946 mesh-bearing
interior models, 63 exterior models. Without a debugger the HK_ASSERT's int3 is the crash (straight to desktop, no WER
entry this afternoon: the engine ends the process). Fix in progress: keys / data runs / primitive array made consistent
in meshcollision.py, a decoder-simulation checker over every model, reconversion of the affected models.

**The landing-zone boundary (row 17).** "Boundary Reached" is Starfield's native BoundaryMenu (no GMST, no MESG, no
script). The owner's three setpos lines were pasted as one, so a single 1,549 m jump applied; this repo's runs of 11-12
Oct showed jumps beyond ~2 cells raise it while 300 m hops reached 2 km with no popup. A real tile edge on foot is
unproven (hypothesis from exe settings: planet-content blocks 3-4 km + uPlayableSpaceOverlayCellBuffer 5). Permanent
route: a list of arrival markers per region.

**Doors.** Design pass: first scripted pair = Super Duper Mart (exterior 0EE661 / core slot 02D22C, interior 0EE5D6 /
Port REFR 01007D0B), both sides real door meshes; the cave and the Vault 111 autoload doors are invisible markers on
both sides. Step 0 (two Probe functions: Resolve, MoveTo) answers the return-trip and merged-position unknowns in one
window before any door record exists. Codex's compiled script (#243) is the contract; Codex's native interior half
(#245 #251 #253) merged. The first build attempt died at 14:51 (unnoticed for three hours); relaunched.

**Stations.** Build mode is engine-side: an ACTI base with WorkshopKeyword (00054BA7) opens workshop mode on activation
(vanilla pre-placed pattern OutpostPlayerHouseActivator 00024DC7, also in the Neon exterior). FO4 benches map by bench
type and recipe keyword id onto 2B6A63 weapon / 2B6A62 armor / 2B6A61 chem / 2B6A65 cooking; power armor stations have
no equivalent. Open in game: whether build mode opens from a temporary REFR in our overlay (vanilla's are persistent).

**Owner playtest rows 10-18** in docs/owner/playtest-issues.md with pictures (the look button: F13 / Ctrl+Alt+L,
snapshots tagged owner-button). Lessons: a Bash heredoc here turns \\r \\n escapes into real characters (patch through a
written script; gate commits on tests); a background workflow can die silently (check the transcripts' modification
times); the owner's three-line console paste became one line (give one line per command).

## 2026-10-17: Grok FLOR harvest research (offline, row 14)

Starfield.esm 1.16.244 still has `FLOR` as the harvest record: 300 bases, `PFIG` ingredient + `PFPC` seasons.
Organic crop template `FloraMaizeCrop01` (keywords `FloraTypeOrganic` + `OutpostCanDomesticate`, seed item
`OrgCommonNutrient_Seed`). Core64c selected 3,520 Flora refs / 48 bases before exclusion (writer 3,518 / 47).
Mutagen 0.55.0-alpha.67 `Flora.Ingredient` writes `PFIG` (default seed and a custom MISC); a STAT ingredient is
refused; no byte patch. `Fallout4.esm` is at depot_377163; a produce table is still unresolved because Starfield
`PFIG` is MISC/LVLI, not FO4 ALCH. Promotion class: `make_cluster.py flora`, `cluster_flora` (edid `FO4Core_flor_*`),
TerrainOverlays Duplicate of `FloraMaizeCrop01`. In-game harvest is Claude's after a scratch overlay
([docs/terrain/flora.md](terrain/flora.md)).

## 2026-10-17: Grok playtest textures, row 15 greyscale-to-palette (offline)

Starfield 1.16.244, convert dir `terrain_core64c_work_fix3` (read-only). FO4 GreyscaleToPalette_Color (nif.xml
flags1 bit 4 = 0x10; BGSM `bGrayscaleToPaletteColor` byte 62) was parsed and never applied, so index maps
shipped as albedo. Converter now bakes the palette lookup into the colour map (green channel as U,
`fGrayscaleToPaletteScale` as V) before BC1. Texture-set slot 3 is only used when the NIF flag is set.
A greyscale string with the flag off is not a palette (ConcreteRoadHW01 names a cubemap there). A named
palette that is missing from the archives is a conversion error, not a grey albedo. Synthetic tests:
palette lookup, flag/scale parse, flag gating, missing-palette failure, cache identity.

Row 15 frames/plaque are **not** palette materials (Claude review, vanilla BA2s): both painting BGSMs have
an empty greyscale string and byte 62 = 0; BrassPlaque flags1 has bit 0x10 clear and slot 4 is a cubemap.
This PR does not change those outputs. The frames need per-reference material swaps (MODS/XMSP), which
nothing in this repo reads. In-game check of real palette materials is Claude's after a scratch reconvert.
Vertex-colour V and GreyscaleToPalette_Alpha are not this PR. Row 11 vines are PR #288; row 13 walls remain
a separate root cause.

## 2026-10-17: Grok playtest textures, row 11 vines (offline)

Starfield 1.16.244, convert dir `terrain_core64c_work_fix3` (read-only). Hanging vines (`vinehanging06/07`,
`vinecreeper*`) use `vine.mat`: opacity slot 2 and AlphaSettings were already written, but the material still clones
`MetalIronCast01` / `PlasticPlainSmooth01` (one-sided opaque). Vanilla foliage uses `TwoSided1Layer`.
`Summary.Layer1.Textures` had no Opacity key. `vine_color.dds` luma 3.8 because 85% of the card is BC1-black
cutout. Converter now clones `ConduitKit01TwoSided.mat` whenever an opacity map exists, writes Summary Opacity, and
zeroes metalness. Synthetic tests in `tests/test_materials.py`. In-game check is Claude's after a reconvert of the
vine family into a scratch folder. Rows 13 (bright wall albedo luma 184) and 15 (dark canvasswap luma 29) are
separate root causes, not this PR.

## 2026-10-17: Grok map-marker research (playtest row 7)

Starfield 1.16.244. Offline walk of `Starfield.esm` and pinned `FO4TerrainCore.esm`. Starfield has no `MAPM` group;
markers are `REFR` of STAT `MapMarker` `00000010` with empty `XMRK`. `LCSR` is 5 × u32 (`LCRT`, `REFR`, `WRLD`, 0,
`0xFFFFFFFF`). LC172WorldLocation already has MapMarkerRefType → persistent `REFR` `003E5E12` and `LCID` that ref.
`TerrainOverlays` Duplicate-copies that location then clears `MasterSpecialReferences` / `MasterInitiallyDisabledReferences`,
so the pinned overlay LCTN has empty `LCSR`/`LCID` and 0 MapMarker refs among 654,600 `REFR`.

Plan: restore one persistent MapMarker at the Red Rocket COC with LC172 `FNAM`/`TNAM`, one `LCSR` + `LCID`; do not stamp
a PCM landing overlay. Frontier hang after that restore is **unresolved** (Claude in-game). FO4 `XMRK` **unresolved**.
Evidence: [docs/terrain/map-markers.md](terrain/map-markers.md), `src/fo4sf/map_markers.py`, `tests/test_map_markers.py`.

Writer (same day, `grok/map-marker-restore`): TerrainOverlays Duplicates LC172's MapMarker `REFR` `003E5E12`, sets it
persistent+initially-disabled (`0xC00`) at the COC spawn, `FULL` "Red Rocket", `LCSR` MapMarkerRefType + `LCID` with
Grid from spawn_cell and Unknown -1 (`0xFFFFFFFF` tail). Skips when the master has no `003E5E12`. New FormIDs after
doors/lights. In-game overlay: Claude.

## 2026-10-16 (night, Mountain time) - Claude: Step 0 probes and the first scripted door

**Probes (queues door_probe_1017 and door_probe_1017e; bridge_t2; core64i / core64k; Starfield 1.16.244).**
(a) From the Red Rocket exterior: `Game.GetFormFromFile(id, plugin)` with a plugin-local id works; the persistent
anchor 0x800 resolves at its unmerged position (-989.26, 1146.51) in world 0x02000803 (our base WRLD, not the runtime
instance); a loaded temporary reference resolves at its merged position; a temporary reference in an unloaded cell
returns none. (b) From inside FO4Port_RedRocket01: the anchor resolves, both temporary exterior references return none.
(c) `MoveTo` onto the anchor from inside puts the player at the anchor's unmerged coordinates in a fresh runtime world
and he falls (no terrain there: y 1146 lies outside the overlay's merged extent). (d) The same with offsets
(-1200, -2700, 0): identical landing, offsets ignored across the world switch (the single far console jump afterwards
raised Boundary Reached). (e) `MoveTo` onto the anchor, then fifteen console hops of <= 200 m to the merged Red Rocket
spot: the player stood at (-2189.30, -1553.54, 110.49) in cell 0x02000DAF of that same runtime world, z steady for 28
samples: the world a persistent reference drops you into is the overlay instance; only the persistent reference's own
coordinates are unmerged.

**First scripted door (queue door_trip_sdm_1018; core64k + integ_1018_doors + bridge_t3 with FO4SF_LoadDoor.pex).**
Forward: four 182 m hops to the Super Duper Mart door (merged -1654.44, -2059.93), `prid 0202D22B`, GetIsID of the
ACTI 020A770B = 1, `activate player`: Papyrus logged `requested fo4port.esm:57087` and `MoveTo returned`; the player
then stood on the interior arrival marker (5.449, 17.291, -3.637) in cell 0x04006C46 for six steady samples. PASS.
Return from inside: `refused: destination unavailable or self` (the temporary exterior marker does not resolve from
an interior); the player stayed. EXPECTED-REFUSED.

**Design that follows.** Exterior arrival markers become persistent; the door script keeps `MoveTo` for the cell /
world switch and adds a `SetPosition` to the destination's merged coordinates (properties per door). Codex owns the
script change; the writer change is Claude's. Evidence folders: C:\Modding\testqueue\door_probe_1017,
door_probe_1017e, door_trip_sdm_1018 (bridge.log, papyrus.log, obs.json, judge outputs). Lesson: the bridge log's
probe lines are case-sensitive to the game's spelling (`FO4SF Resolve`); the reader is case-insensitive since #282.

## 2026-10-17: Codex activation-parent metadata preservation (offline)

Grok's [garage-button investigation](https://github.com/fo4sf/fo4-to-starfield/issues/32#issuecomment-6230797494)
identified dropped activation relationships. A synthetic Fo4Export regression first failed because
`activate_parents` was absent. The shared interior/exterior serializer now retains the raw flags,
ordered source FormKeys and float32 delays, including deferred actors, null links and empty blocks.
ReferenceLinks reports non-null blocks as untranslated even when a reference has no placed target;
it neither invents native wiring nor changes existing links/identities.

Verified with Mutagen Fallout4 0.55.0-alpha.67 and synthetic records: the generated REFR's XAPD
contains byte `81`; its three XAPR payloads are eight bytes each, preserve distinct own/master/null
parent IDs, and store delay 0.1 as float32 `3DCCCCCD`. The production binary-overlay getter retains
the same metadata. `dotnet run --project dotnet/Fo4Export.Tests -c Release` and
`dotnet run --project dotnet/ReferenceLinks.Tests -c Release` pass; the latter also passes its existing
11 native-door and 13 missing-door CLI controls. `dotnet build dotnet/Fo4Land -c Release` succeeds
without warnings, confirming the shared exterior producer compiles; no full exterior export was run.
Initial harness compilation and missing-restore failures are retained alongside the reproduced
missing-field failure and passing results in private evidence. Guard passes. No installed data,
native garage animation, scripts or game control changed; independent review remains pending.

## 2026-10-17 - Claude: the "flat grey floor" in Vault 111 is the water plane (owner playtest row 20)

**Question.** Owner snapshot 20261017-000312 (bridge position -57.91, -7.11, -1.943 in Vault111Cryo, integ_1018 build):
the floor is one flat light-grey surface, no tile or grid detail, white under the flashlight. Which model, which
material, why flat? (Offline only; nothing launched.)

**Finding (verified offline, one in-game read).** It is not a floor model's texture. The surface is the placed
`Water\Water1024.nif` (ref 02D27E, base Water1024IntPondDarkCalm, FO4 position -3832, -200, -136 = -54.743, -2.857,
-1.943 m), a 14.63 m square (UV 0..1) over the gear room's sunken pit:
- The player's z (-1.942875) equals the plane's top (-136/70 = -1.942857) to 2e-5 m. The earlier snapshots 000241 and
  000257 read z 0.0009 and 0.0 on the room floor and show the normal dark vault tiles. The pit's real floor is the
  `V111FloorCementDirty01` shape of `V111GearRoom01` at z -2.38 (the blue generator `GreebGenerator01` stands on it at
  z -2.40, 9.2 m ahead, 16 deg left of the view heading: where the screenshot shows it); the plane hides it.
- FO4's `Water1024.nif` has one BSTriShape with a `BSWaterShaderProperty` (no texture set, no .bgsm: FO4 draws it
  from the WATR record) and one convex body, 14.63 x 14.63 x 14.63 m below the plane, layer 11 = L_WATER ("a water area
  phantom"). `Converter._shape_material` returns the neutral fallback for every shader that is not a
  BSLightingShaderProperty or BSEffectShaderProperty, so the quad became `_neutral.mat`: a 16 x 16 uniform grey colour
  texture (decoded luma std 0.00), a flat normal map, one roughness value. That is "flat grey, no detail", opaque, at
  water level. Manifest: `fo4port\water\water1024.nif`, shapes 1, fallback_materials 1, collision_report bodies 1.
- The converted body keeps layer 11 with the template's hknpMaterial (materialId 0, flags 0, triggerType 0). In
  Starfield's COLL records L_WATER (layer 11) lists L_CHARCONTROLLER among its collision partners and L_CHARCONTROLLER
  lists L_WATER; Fallout4.esm has the same pairing, yet an FO4 player does not stand on water. The FO4 water body is
  the one body here with cinfo flags 0x10 (the room's static and stair-helper bodies have 0); the converter writes
  the template's 0. What bit 0x10 does is **unresolved** (hypothesis: it is what keeps the FO4 body from being solid).
  What is verified is the result: in Starfield the player stood on the sheet, 0.44 m above the pit floor. Same cause
  as T10 in docs/ai/test-gaps-2026-10-13.md (the Red Rocket cave pond is a 5.1 m L_WATER box).
- Not the other candidates: the pit floor's own converted material is fine (`v111floorcementdirty01.mat`: colour,
  normal and roughness exist in the archive; the colour map decodes to the same mean RGB and spread as FO4's
  `V111FloorCementDirty01_d.dds`, 161/156/140, std 12.5). No palette material is involved (#289: the shapes under the
  player have no BGSM and no greyscale-to-palette flag). No texture failed conversion. It is not a lighting effect.

**Fix.** The exterior path already leaves placed water planes out (`exterior.WATER_RE`); the interior path did not
(interior-backlog.md had it as "unresolved whether they look wrong in game"; now resolved). `convert_batch.cell_candidates`
now drops `Water\` models too, so the model is not converted and the plugin writer places no reference for it (PluginSpike
counts a reference as skipped when its model has no manifest item). Five of the 16 interior exports place a Water1024
(Vault111Cryo, Vault75, RedRocket01, CambridgePolymerLabs01, MuseumOfWitchcraft01). Result: a dry pit, as FO4 minus its
0.44 m of water. Real water is a separate feature (FO4 water type -> Starfield water), not attempted. Test:
`CellCandidatesTests.test_water_planes_out_like_the_exterior_path` (fails without the change; also asserts the exterior
classifier agrees). Before/after reconversion of the two refs (room + plane): the before manifest is byte-identical to
integ_1018's (water1024.nif, `_neutral.mat`, gear room all equal by sha256); the after manifest holds the room only.

**Not verified.** In game: that after a rebuild the player stands at the pit floor (z about -2.38) and sees the cement
texture. The first read after the rebuild is the proof; the T10 PHANTOM test covers the cave pond.

## 2026-10-17 — Codex: activation-parent warnings keep interior exports usable (#305)

Claude requested nonblocking, counted warnings for preserved activation-parent metadata.
The previous default returned exit 2 for a synthetic cell with a non-null activation block;
the new eight-case CLI regression reproduced that before the change. ReferenceLinks now
lists these blocks in `Warnings` and stderr, retains all source data, and writes
`partial_with_warnings` rather than claiming complete relationship fidelity. Strict callers
can select `--strict-activation-parents`; `--allow-unresolved` explicitly overrides that gate.
Missing enable-parent targets and other existing issues still block default publication.
Report-only never publishes a plugin or marks the build complete. Synthetic output is reopened
to check identities and that no activation behavior or substitute link was invented.
This is offline export policy, not a native door/activation fix. Delta peer QA remains required.

## 2026-10-17: Grok 3D surface-map research (ROADMAP §3 item 1)

Starfield 1.16.244. Offline. Pinned `terrain_core64k`: LCTN parent `SSol_PMars_Surface`, overlay SNAM 0 / PNAM 4, Mars
PNDT 11 entries including our WRLD; no `lodsettings`; 0 `meshes/lod/generated`; 315 converted FO4 LOD NIFs under
`meshes/fo4core/lod`. The 3D surface map is the May 2024 loading-zone camera, not a mesh we author. GO: marker (#296
after LCSR `FFFFFFFF`) then CK object LOD; NOT go: custom planet or map renderer this stage.
Evidence: [docs/terrain/surface-map.md](terrain/surface-map.md), `src/fo4sf/surface_map.py`, `tests/test_surface_map.py`.

## 2026-10-17: Codex raw light-patch bounds (offline)

Independent PR302 review reproduced a malformed DAT2 declaration extending beyond
its LIGH into a following STAT: scale changed four STAT bytes, then check returned
CHECK PASS. Both commands now validate record/group containment and all LIGH
subrecords before accepting lumens offsets; malformed trailing fields and duplicate
DAT2 are refused. The checker validates both files. The scaling rule is unchanged.

Synthetic reproduction only, no game versions or installed outputs tested.
Seventeen focused tests passed initially; the selected three-method baseline run
produced five failed assertions against the old implementation. This was not a
run of every new test against old code. Valid trailing fields remain supported.
Guard/whitespace pass. Failure/pass evidence is privately retained; independent
QA pending. No game data, staging changes or native brightness claim.

Claude's independent review at 7a31d64 confirmed valid-output parity in 12 synthetic
comparisons and requested a regression for validating checker input B. Added one
test with two cases: A valid, B duplicate-DAT2 or overrun, identical total size and
record layout. Both reject before byte/lumens comparison and retain both inputs.
Removing only B validation causes both cases to fail. All 31 focused light-patch
and FO4-light tests pass; guard and whitespace checks pass. Production source is
unchanged; final test-delta review is pending. No native or staging run.

## 2026-10-17: Grok #288 review fixes (offline)

Codex/Claude on a77edfa: `build_from_template(..., metalness=0)` only updated an existing TextureReplacement
index 4. ConduitKit01TwoSided has none (only MRTextureFile index 4 = conduit metal), so vine.mat kept the metal
map and Summary said UseReplacement/0 — the 2026-10-08 metallic-summary shape. Now the writer drops that metal
file and appends an enabled replacement (MetalIronCast01's shape). Opacity maps stay gated on `alpha_test or
decal`; `two_sided` alone no longer cuts out cars/glass (40 FO4 two-sided materials without alpha test).
DryConverter._texture_set accepts `two_sided` so a core64c dry run no longer TypeErrors every BGSM. One-sided
FO4 cutouts (hair, chain-link) still clone TwoSided1Layer when they have an opacity map. In-game still Claude.

## 2026-10-17: Grok playtest 21/24 (garage button + object LOD)

Row 21: FO4 garage is an ACTI with XAPR to the button, not a DOOR. Writer wires vanilla
`DefaultActivateLinkedRefOnActivate` + XLKR LinkCustom02 on the two Commonwealth pairs (no new FormIDs).
Row 24: object LOD research only (`lodsettings` + generated `_lod_0..3`); do not raise the cell buffer.
[docs/terrain/garage-button.md](terrain/garage-button.md), [docs/terrain/object-lod.md](terrain/object-lod.md).

## 2026-10-17: Codex production garage-link regression (offline)

Added an actual TerrainOverlays writer test for #303. Two synthetic builds, without
and with the button link, must retain all existing identity-map sections and record
IDs, changing only the button REFR. Its serialized VMAD must carry edited
LinkedRefKeyword = Starfield.esm:05D5E7 (alias -1); the one XLKR must use that same
keyword and the garage REFR in the output plugin, not the ACTI base.

The new test fails against the actual pre-fix 7eaab94 writer because its script has
no properties, and passes against 0168350. Both runs and synthetic output bytes are
preserved privately. No game files, stage, installation or native acceptance; the
garage animation/receiver remains a separate gate. Independent test review pending.

## 2026-10-17: Grok #303 wire-only (clip alias out)

Claude 08:04 on #32: the Opening/Closing clip alias in pipeline.py is P2 inside this change, not a lead
item; it turns both FO4 garage meshes into passable statics because RedRGarageDoor.nif is skinned and the
rigger refuses it. Alias, door_motion Opening sequences, door_rig.alias_clips, and the alias test are
out. Button wiring, docs, and Codex's #319 actual-writer test stay. Garage NIF rig is later, Claude on
the build side. No deploy, no game.

- **2026-10-18 Codex PR176 main merge:** retained six owned identity functions and109 current-main function bodies (excluding docs). Updated two stale ACTI/workshop tests from expecting punctuation aliases to checking distinct bases/original slots, retaining injected-collision refusal.89 initial Python passes plus two corrected reruns cover91 cases; eight actual-writer tests pass, including new ACTI/TERM/workshop identity, NAME/ref-slot and terminal-menu controls. Six parent-main helper alias counterexamples reproduced. Two existing C# warnings remain. Original failures and synthetic outputs retained privately; no live stage or save migration, independent integration QA pending.

## 2026-10-18: Grok Ba2.largest_entries

Added `Ba2.largest_entries(n)` returning the top-n entries by unpacked size (GNRL unpacked field; DX10 sum of chunk unpacked). Useful for conversion planning: identify the biggest meshes or textures before a full extract. Synthetic tests in tests/test_ba2_largest.py cover ordering, compression, and limit. No game data; guard ok.
### 2026-10-20 Codex: include ordered plugin masters in same-IDs verification

Scoped identity/output-verification correction to394/774cb7f, coordinated on its PR. The old checker flattened
repeated MAST subrecords and allowed SAME_IDS after master reorder or earlier-entry replacement. The reader now
retains all raw MAST bytes in order; a changed table sets ids.masters_changed and refuses identity equivalence.
This is a strict ordered-table comparison, not runtime load-order or semantic rebasing proof. Other metadata and
content changes with the same masters retain explained SAME_IDS results. Sixteen focused methods pass after
new cases fail on the original source. Sixteen separate controlled actual-CLI calls reproduce/fix five false
PASS cases and retain three positive outcomes; all eight synthetic input pairs remain unchanged. Only reader
header handling and comparison change; launcher driver, restore and other parent findings remain untouched.
No private plugin, real installer, game/stage/input or main merge. Independent QA remains pending.

### 2026-10-20 Codex: distinguish manifest metadata agreement from input content proof

Continued the scoped427 identity proposal for394 finding6. The comparison now includes recorded BA2 versions;
same-sized v1/v7/v8 header captures no longer pass as equal metadata. The existing list API remains, while the
read-only CLI lists unhashed master/archive/game inputs and labels their content unverified. Exit0 still means
no detected compared differences, not a content-proof gate; full matches are stated only for hashed declared
files. Wired the existing optional hash_game_esm capability to --hash-game-esm alongside --hash-archives, leaving
cheap default capture unchanged. Paths/timestamps remain informational across PCs. Seven new methods and the
existing identity/manifest controls pass (28 total). Fourteen controlled actual-CLI replays retain positive
hashed comparisons and qualify hidden same-sized content changes; ten synthetic input files remain unchanged.
No new hashing/build job on private inputs, decoder, driver, restore or native action. Independent QA is pending.

## 2026-10-20: Codex restore Plugins.txt namespace binding (offline)

PR394 finding5: a snapshot could name a different file while its installer always
used LOCALAPPDATA/Starfield/Plugins.txt. Two original-source backend replays
(wrong filename and wrong parent) returned an empty differences list after an
injected installer changed the canonical file. The correction validates and
canonicalizes that address before reading snapshots, planning, verifying, writing
or applying; mismatched snapshots refuse. Valid custom roots, Windows case aliases
of the same namespace, missing files and no-op restores remain supported.

Eight new synthetic methods and seven existing read-only restore methods pass.
Six retained old/new backend calls reproduce both false successes, show refusal
before the callback with all state unchanged, and preserve both valid no-ops.
Install effects were injected in temporary profiles, not performed on a game.
Initial test setup mistakes (imported TestCase discovery and missing LOCALAPPDATA
isolation) and original failures are retained privately; corrected tests pin a
temporary profile in every case. Other PR394 findings and independent QA remain
open. No physical restore, deployment, game input or native acceptance.

## 2026-10-20: Codex detect profile-INI coverage warning (offline)

PR394 finding7: detect could print READY without checking My Games INIs or saying
they were unchecked. It now warns when --my-games is omitted or the supplied
folder is unavailable. Paths remain explicit, never guessed. READY and exit-code
policy are unchanged: the warning is not proof of a clean profile. Supplied
profile and game-folder sTestFile entries still refuse; loose files still warn.

Five new methods plus thirteen existing detect/measure methods pass. Twelve
old/new actual CLI calls cover omitted, missing, clean, blocked, game-blocked and
loose-file profiles on identical synthetic inputs. Only coverage warnings change;
refusals/readiness and all input bytes remain unchanged. The initial four new
methods produced six pre-fix assertion failures, retained with their green runs.
Legacy no-warning tests now explicitly supply an empty synthetic profile, keeping
their original tool/source assertions. Only detect() changes among production
functions; CLI dispatch is unchanged. Independent QA pending; no real profile,
game action, staging, deployment or native acceptance.

## 2026-10-22: Red Rocket crash: Codsworth's shader blocks (in game, Card I1)

Game: Starfield 1.16.244.0 with FO4 1.10.163 data, v6i core (DC751664), mission
03C2A7A8. The bisect is in docs/spikes/red-rocket-crash-bisect.md (v6c to v6i
crashed; v6i without codsworth.nif walked clean). Card I1 rebuilt the model with
`scripts/actors/convert_codsworth.py` and the PC's usual arguments plus
`--plain-shader`; the report says plain_shader true, one_material false. The built
NIF has 56 blocks, and all five BSLightingShaderProperty blocks are 12 bytes (the
.mat name, 0 extras, -1 controller). The mission was restaged with that folder and
folded into the core (50 Codsworth assets; verify ok), then installed.

Result: the walk queue (tag plainshader, crash watcher and 1 s memory log on)
passed both legs from a fresh start. Red Rocket to Sanctuary: 29 of 29 steps,
253.9 of 254.33 m, end error 0.1 m, |dz| max 0.13. Sanctuary to Red Rocket: 253.9 m,
end error 0.0 m, |dz| max 0.14. Each ran about 9 minutes past arrival. The run
exited 0, and the typed-lines audit found nothing outside
ClearConsole/getpos/setangle. The watcher saw a normal exit, plus one forced stop
(0xFFFFFFFF) by the runner's Stop-Process, with no access violation. Working set
peak 8.77 GB, commit peak 14.75 GB, minimum free 4.27 GB. The single-material test
(I2) was not needed.

Conclusion: the crash came from the mini bot template's 166-byte shader block,
carried into our model with only the name swapped. `--plain-shader` is now the
default; `--no-plain-shader` rebuilds the crashing model. Why the game misreads
that block in our file is not shown. Why the model loaded in the mission-off run
(Card D) is open. Nobody has yet checked how Codsworth looks in game.

## 2026-10-22: Phase 0 ledger (what is verified, what is not)

Build on the owner's PC since 03:14 UTC: v6i_plainshader (FO4Port 9AF962D2, core
DC751664, Mars 8BBA3EE9, Raider BED4EF1A, FO4SFMission 03C2A7A8, Bridge 63C746BB)
plus FO4SFMapMarkers pinned to core DC751664 (installed 11:50 UTC). The roadmap's
phase 0 exit (approved 19 Oct) is: the owner's v6 checks and the automated door
rounds pass, and #353 merges after Codex's review. docs/ROADMAP.md carries the
ledger; this entry records the evidence behind it.

In game, 21 Oct, v6e (core 06C0DECD), the doors_out queue (runner 62df40bb, judge
6159dcb): 15 OUT legs, PASS 10 (Vault114 x2, FortHagen01 x2, SuperDuperMart01 x2,
BostonPublicLibrary02, Vault95, MuseumOfWitchcraft01 test 0011, PrydwenHull01),
FAIL 3 WRONG_PLACE (CambridgePolymerLabs01 34.6 m off sideways; MuseumOfWitchcraft01
test 0012 16.4 m too high; FortHagen02 12.2 m too low), INCONCLUSIVE 2 NOT_ACTIVATED
(Vault75: the launch coc failed; ParsonsState01: console not opened safely). The IN
legs (doors_rounds, 30 tests) stopped at test 0000 when the game left at the Red
Rocket spawn; the crash was later traced to Codsworth's model (entry above). Stairs
on v6e: 18 PASS, 0 FAIL, 2 NOCELL. No door round has run on v6i; the Vault 95
OUT-only runs _e and _f are the border evidence below.

In game, 22 Oct, v6i_plainshader: the Red Rocket walks pass both ways (entry
above). The owner's play test: Codsworth renders on the plain-shader model; on the
owner's existing save he was not at his Sanctuary spot until enabled by console
(`prid 05000811`, enable, moveto player). The index was 06 in the morning session
and 05 in the afternoon one: Install read Plugins.txt rewritten 25 s after the
launcher started the game, with FO4Port moved from first to after FO4SFMission
(docs/testing/load-order.md). The map markers: the mover log shows the quest
started at 55 s and moved all four markers at 70 s (first position read FLT_MAX),
and the owner saw the four icons on the surface map after coming back to the area
(placement and fast travel PASS, with the first-read delay open; the icons read the
location name instead of their own, and the Concord arrival was half in the ground,
so the #483 override installed at 19:32 UTC still needs its in-game check). The launcher: the owner's desktop shortcut
opened the window and started the game (the owner's word, "it works").

The boundary (Interiors, PC run _f at a43afef, v6i): the Vault 95 exit after a coc
from Red Rocket ends STAYED with "Boundary reached" while the border is on; with
`SetINI "bBorderRegionsEnabled:General" 0` typed mid-session the same exit lands
0.00 m from its marker. The earlier report of a walking wall north of Vault 111 is
withdrawn (correction entry below): there is no wall on foot. The 8-ray border walk
(cc1d594) got stuck on converted objects 6 to 200 m out and raised no popup, so no
walk has met the border. Owner's decision, 22 Oct: B, a fix for our world only.
BorderProbe (#485, merged) ran on the owner's swap line of 18:13 UTC: none of the
three variants ran (NOT RUN, the owner was active at the PC). The rerun with the
idle wait: city (SmallWorld cleared, HNAM 5) PASSED the Vault 95 OUT leg with the
border on (0.00 m off in xy), hnam5 (HNAM 5 only) FAILED STAYED, nosmall (SmallWorld
cleared only) PASSED (Install's report, 20:46 UTC). Not proven: the markers plugin
loaded after the probe with a copy of the core's WRLD, so the live record may have
been the control's, and a single pass against a single fail may be chance; the
settling test (each variant's fields in the markers plugin, 3 runs each of control,
city and nosmall on one save) is staged and waits on the owner's line. #495 lets
the core build take the city fields; that core, v6j (v6i plus the border fix, no
reconversion), is held until the settling test answers, then the markers, new game,
questprobe_v2 and interiors b10 are restaged on it and Bugs' cards J, K and L run
on it. v6j is installed only after border.md's wider checks (a second long exit, a
long map fast travel, a vanilla planet's border still showing).

Not recorded on v6 (the owner's hand checks): the mission (Missions tab, Preston
friendly, 100 credits; on v6c, 19 Oct, only completion was verified, Preston
targeted the player on that run and the faction fix came after), Codsworth's greeting voice, the map
extent (getpos plus a zoomed-out surface map screenshot; Map dropped the 3D-view
spots on 22 Oct, the border question being answered), the Red Rocket side door, the
elevator entrance prompts, the roof hatch and manhole prompts, cans and books. The
Ctrl+Alt+K box fix (#463) is merged. The results that close the phase are the ones
taken on v6j after its install; a session on v6i before that is a preview.

## 2026-10-22: Correction: no walking wall north of Vault 111

The phase 0 ledger above, README's boundary row, playtest-issues.md row 29 and
the owner's test sheet carried a wall the owner hit on foot at getpos (-2606, -908),
about 490 m north of Vault 111, and put it down to Starfield's border region by
inference. That report was a misreading and is withdrawn: on 22 Oct (18:55 UTC)
the owner said they never hit a wall there and walked far north of Vault 111, past
where Fallout 4's own border would be, without the popup (docs/terrain/border.md,
"What is known", verified). The only border evidence is the Vault 95 exit after a
coc (run _f): STAYED with "Boundary reached" with the border on, 0.00 m off with it
off. The border is read as a limit on how far one teleport may move the player,
not a fence at a position (supported hypothesis, border.md). The four places now
say so, and no on-foot recheck is planned.

## 2026-10-22: Correction: the border settling test is running, not waiting

The phase 0 ledger entry above was written before 20:53 UTC and says the settling
test (each variant's fields in the markers plugin, 3 runs each of control, city and
nosmall on one save) is staged and waits on the owner's line. The owner gave the
line in the Install thread at 20:53 UTC ("Go ahead and run the test"), so the test
is running on the PC. The ROADMAP, README and playtest row 29 say so (#498); this
entry records the change, and the entry above stands as written.

## 2026-10-23: Phase 0: the border fields are shelved, v6i is the closing build

The ledger entry of 22 Oct above planned v6j (v6i plus a border field) if the
settling test proved a field. It did not: with each variant as the last WRLD
override, 3 runs each on one save, the unchanged world passed 3 of 3 and nosmall
and city each failed once (7 of 9; docs/terrain/border.md, Results, merged with
#499). So neither field is a reliable fix, the failure is intermittent, the
fields are shelved (no core is built with #495's flag), there is no v6j, no stage
is restaged for a core change (the new game and the combined-core probe still
restage against v6i), and the installed v6i (core DC751664) is the build the phase
closes on. What follows on the PC: the failure rate over 10 Vault 95 exits (the owner's
line 23:37 UTC 22 Oct), then 10 with FO4SF_LoadDoor's retry of a missed trip
(#499, bridge_t5; the owner's line 00:00 UTC 23 Oct), and the automated door
rounds moved from "on v6j" to the installed build (card J2, running since 22:39
UTC 22 Oct). The ROADMAP's 22 Oct section carries the exit checklist with its
gates and the items that move to the next phase; the entries above stand as
written.

## 2026-10-23: the Vault 95 rate is measured, the retry never fired, the door counts are void

Gate 2 of the phase 0 exit checklist has its numbers (Interiors with Install, on
the owner's lines of 22 Oct 23:37 UTC and 23 Oct 00:00 UTC): 10 Vault 95 exits on
the installed v6i build with bridge_t4 landed 7 of 10, the 3 fails STAYED in the
interior cell with the popup; the same 10 with FO4SF_LoadDoor's retry of a missed
trip (#499, bridge_t5) landed 6 of 10, and the retry never fired in any run: by
Install's trace the engine's bounce back into the cell comes after the script's
check that follows the MoveTo, so the check sees the player gone. 13 of 20 over
both runs. No pass bar was set; whether the rate holds the phase or goes on the
defect list is the owner's call, and the next phase's route is the SFSE per-world
toggle of the border (border.md; unwritten). Gate 1 has no numbers: Bugs' check of
the door-round judge (03:16 UTC) found the positions read after qstep's unscored
"beyond" teleport, not at the door's arrival, so J2's counts and the v6e counts
are void; #504 (merged, main 981c0216) fixes the judge and card J4 reruns both
queues under v6ic after the owner's session. The quest probe (questprobe_v2) is
installed on the owner's 00:14 UTC word; newgame_v7 is built and staged against
v6i, not installed. The entries above stand as written.

## 2026-10-23: correction: the Vault 95 fails were the popup, not a bounce back

The entry above on the Vault 95 rate said the retry never fired because the
engine's bounce back into the cell came after the script's check, and that every
fail STAYED in the interior cell. That reading was wrong (Grok's review of #505,
against border.md "Rate and retry runs" in #512, draft, on the same 20 runs): in
all 7 fails the BOUNDARY REACHED popup came up during the exit and paused the
game; the bridge feed went stale (its newest line 76 to 78 s old) and the judge
fell back to the last read before the door, inside cell 06007D12, so STAYED there
means the popup came up, not a measured bounce back inside. The script's trace
was the same in every PASS and FAIL (the MoveTo lands in the exterior at the
marker's unmerged position), so no check right after the move can tell a failing
trip from a passing one, which is why the retry never fired. Which step raises the
popup is open; #512's door change (the destination marker moved to the merged spot
before the MoveTo, plus a settle step) is the next PC card. The counts stand: 7 of
10 and 6 of 10. The entry above stands as written.

## 2026-10-23: Phase 0: the owner's section A results (gate 3)

The owner played section A of the test sheet on v6i with the bridge door-script
set t4 and the quest probe installed, and reported at 15:46 UTC: the mission
worked, the map markers worked, every A5 door but one at Fort Hagen worked;
Codsworth did not spawn (which save is not stated; the keeper fix #493 is not
installed); cans and books can be moved inside but not outside; the quest probe
ran, its marker away from the door (the port's library has no load door, so the
probe falls back to another door or object); the borders are "wrong for sure",
with the owner's getpos and map screenshot for Map's overlay and city
screenshots to come; New Atlantis is very laggy. Gate 3's pass rule (A2 to A5
as expected) is met by A2 and A4, not by A3 and A5, so those two are defect rows
and the owner's call. Rows 31 to 37 of playtest-issues.md carry each report.
Gate 1 still waits on card J4; gate 2 (13 of 20) is the owner's call. The
entries above stand as written.

## 2026-10-23: the owner's answers on Fort Hagen, Vault 95 and Codsworth

At 16:30 UTC the owner answered the open questions from section A. Fort Hagen:
"the normal floor entrance works, but I couldn't even find the second exit".
Bugs reads the second exit as the roof elevator (FO4 door 16852C): on v6i its
exterior is about 0.18 m deep, and the outer elevator door 16852D has no door row
in Install's door audit. Bugs carries it to the next phase's core rebuild; v6i
stays as is. The sheet's (d) had asked for the roof hatch inside instead, which
the owner did not name. Vault 95: the door lands the owner in the right place
outside; then BOUNDARY REACHED comes up, Tab does not let them move, and it
"teleports me back to where I was". The owner asked that the door not be
described as sending them to the wrong place: it sends them to the right place.
Codsworth: the mission's log from the session shows four moves to his spot,
none failed, with him about 3 km away before each later move; Bugs treats it as a
defect, with a return to unmerged coordinates as the hypothesis for card K1.
playtest-issues.md rows 32 and 33 carry the answers and row 38 the Vault 95 one.
Which save the owner used and their choices on gates 2 and 3 are still to come.
The entries above stand as written.

## 2026-10-23: Phase 0: the owner's calls on gates 2 and 3

At 16:57 UTC the owner chose. Gate 2, the Vault 95 exit: C, phase 0 holds until
the SFSE per-world toggle of the border is written and tested; the 13 of 20 and
the owner's own report (the door lands right, then the popup) stand as the
measured state. Gate 3: D, Codsworth goes on the defect list and the keeper fix
is installed next to check it; F, the Fort Hagen exit goes on the defect list for
the next phase. Neither holds the phase, so gate 3 is ticked. The owner played on
the test save the sheet named, so Codsworth's absence is not only the old-save
case. The Fort Hagen exit the owner looked for was the roof hatch inside the
building (the sheet's (d), FO4 door 0C38BF), not the roof elevator Bugs first
read; the door audit lists both sides of that hatch, so why it could not be found
is open. Phase 0 now waits on gate 1 (card J4) and gate 2 (the SFSE toggle). The
map walls are still being discussed with the owner. The entries above stand as
written.

## 2026-10-23: the map stays open; Bugs' reading of the Fort Hagen hatch

At 16:58 UTC the owner chose L for the map: the land stays open with no walls,
"because the full vision". The SFSE per-world border toggle (Interiors, gate 2) is
the only border fix. Bugs read the door audit for the roof hatch the owner could
not find: the core writes it as a static roofhatch01.nif only 0.83 m tall, so
there is no door to activate, and the fix is to convert it as a door in the next
core rebuild, with the outside roof elevator riding the same fix. That cause is
inferred, not checked in game; the ground entrance is written as a static door
too and works, so row 33 keeps both. The entries above stand as written.

## 2026-10-23: correction: the Fort Hagen hatch's cause is open

Bugs withdrew the reading in the entry above (the hatch written as a static model
with no door to activate): the ground entrance is written the same way and works,
and the owner looked from inside, where the hatch is the port's reference
0100C7A6. The cause is open. Bugs' read-only PC check of that reference (record
type, teleport data, script, ladder collision) runs after card J4. The entry
above stands as written.

## 2026-10-23: correction: the quest probe's target was a far load door

The section A entry above put the probe's marker down to a fallback target in a
library with no load door. Install's log extract (#518) shows otherwise: the
target was a load door 72 m from the start (070049ED), under the stairs, which the
owner reached only with tcl, because the load-door choice had no floor or reach
limit. #518 merged at 16:42 UTC with that limit; it is not compiled or rerun on
the PC yet. playtest-issues.md row 35 carries it. The entries above stand as
written.

## 2026-10-23: the Fort Hagen hatch is a working door out of reach

Directing read the installed FO4Port.esm (read-only): the roof hatch the owner
could not find inside Fort Hagen is a working scripted load door to the roof, set
in the ceiling about 3.2 m above the upper floor with nothing to climb within 4 m.
In FO4 the ladder is part of the trapdoor model, so Bugs' likely cause is that the
converted model lost its hanging ladder or that ladder's collision; that is not
checked. The fix stays in the next phase (the owner's call F): check the converted
model for the ladder and an activation volume reaching the floor, then fix it in
the door conversion. Card H1 (Bugs' PC read of the hatch) is dropped; card J4,
the door rounds, still runs. playtest-issues.md row 33 carries it. The entries above stand as written.

## 2026-10-23: Phase 0: card J4's door rounds (gate 1)

Card J4 reran both door queues on v6i with the fixed judge (runner at main
6c007035, `-Tag v6ic`, core 02 and port 07, the quest probe at 06), finishing at
14:43 PC time with no crash and no "beyond" read on a judged leg. The exits: 14 of
15 PASS, the fifteenth (Vault 95 OUT) INCONCLUSIVE with no feed after the door,
consistent with the BOUNDARY REACHED popup and read under gate 2; Bugs reads from
code (not run) that bridge t4's door first moves the player to the marker's local
position, about 2.95 km from the merged spot, and that the correction raises the
popup, which bridge t6 (#512) addresses. The round trips:
26 of 30 PASS, 4 INCONCLUSIVE (NOT_ACTIVATED: the runner could not open the console
safely; fix draft #530), 0 FAIL. The three wrong-place exits of v6e all passed, and Vault75 passes
both ways. No door failed, but gate 1 stays open until Bugs reruns and judges the
four harness-fault legs (ParsonsState01 and FortHagen02 IN from the Red Rocket
spawn, Museum OUT, Prydwen OUT). Two wording fixes ride along: gate 2 now says the
FO4SFBorder plugin (#522) is written and built, its hashes verified on the PC and
card A pre-staged, not yet run or tested on the PC; and world-and-planet.md no
longer calls exp3 verified, since this journal (11 to 12 Oct) found it confounded
by the border and asked for a hop re-run that has not run. The entries above stand
as written.

## 2026-10-24: Phase 0: gate 1 ticked (card J5)

Card J5 reran all 30 round-trip door legs on v6i with #530's console fix (runner
at main 2eede55d, tag v6id; the run ended at 01:19 UTC). 29 of 30 passed, none
failed and nothing crashed; the four legs J4 could not start (Parsons and Fort
Hagen 02 in from the Red Rocket spawn, Museum out, Prydwen out) all passed, and
the runner never failed to open the console. The one leg that did not pass is
Vault 95 out, whose feed stopped after the door trip began: the border popup that
gate 2 measures. With J4's exits (14 of 15, the fifteenth the same Vault 95 case),
every door leg but Vault 95 out has passed, so gate 1 is ticked by its own rule.
Phase 0 now waits only on gate 2, the per-world border switch, which the owner
asked to see written and tested. The entries above stand as written.

## 2026-10-24: Phase 0: gate 2 ticked (card B, the border switch on in game)

Card A's probe (08:21 UTC) found the border setting's byte 16 before its name
pointer, and #539 made -16 the switch's offset. On card B the owner walked with
FO4SFBorder in Mode 2 (v6i_plainshader, the markers plugin with the border
signal, Starfield 1.16.244) from Red Rocket west and then south past Vault 95,
went in and out through its door, and hit no wall and no popup: "idk what
changed but I didn't hit any walls this time". The door put them at the merged
arrival at 16:24 UTC and they walked on with no stall. The plugin's log, as
Install read it live, has three writes, every one ok: off and then on within a
second on the first load at the Red Rocket spawn, and off again back in our
world at 16:22 UTC after a trip to Cydonia, a vanilla world, where the border
stayed on. The first load is the caveat: the map script's log went border=on,
on, off and on within 0.8 s (each of the markers plugin's quests writing the
signal, #542's reading), and the plugin's two writes followed the last two,
which left the border on in our world until the trip to Cydonia and back, so a
player who never leaves could keep it on. A walk at 15:33 UTC is void, since
Windows' Controlled Folder Access blocked the game's saves and logs. Gate 2's
rule was the toggle tested on the Vault 95 exit, and that is what the owner did,
so gate 2 is ticked and with it every gate of the phase 0 exit. The flicker
stays a defect in the switch. The phase is not called done yet: Interiors' fix
for the flicker (#542, in review) and #512's t6 Vault 95 runs come first, and
calling it done is the owner's word. The entries above stand as written.

## 2026-10-24: Phase 0 done (the owner's word)

Interiors' first-load fix (#542) merged and was installed on the PC at 17:20
UTC on the owner's line. At 18:45 UTC the owner loaded fresh at the Red Rocket
spawn, walked west and south past Vault 95, and reported "no walls"; Install's
log read agrees: the border switched off once at Red Rocket, came back on only
in Cydonia, and switched off again on return. At 18:58 UTC the owner said
"phase 0 is done", with all four exit gates ticked; #512's t6 runs did not run
and no longer hold anything. For the next phase the owner named the map icons
that don't load as the real map issue, possibly a map mod, and likely FO4's map
locations on the Pip-Boy. Also next phase: the owner's Steam Fallout 4 is the
newer update, not 1.10.163, so the launcher's version check needs it added. The
entries above stand as written.

## 2026-10-25: Codex connected-travel risk research

Owner-requested exploratory note in research/framework/travel-and-runtime-risks-oct25.md reconciles Claude's combined-core/world plans with current Warfare/Survival and reusable-support direction. Separates connected regions from continuous terrain, preserves boundary-test limitations, and lists travel/save/AI/vehicle/UI/suit risks and small future experiments. Primary SFSE, Bethesda and framework sources checked; document links/guard checked. No engine-limit verdict, native tests, source implementation, installation or merge. Owner route-preference questions remain pending.

## 2026-10-25: Codex reuse decision brief for Claude

Added a documentation-only owner-requested brief comparing pattern reuse, the existing simulation baseline and optional native/Rust components. No technology or performance result selected. Proposed save/identity/generation contracts and bounded phase gates await owner + Claude decisions. Reconciled the travel note with one-time persistent areas, limited outskirts/corridor/map-selected travel and full walking deferred until all planned locations exist. References/guard/diff checked; no source changes, native tests, installs or agent wake. Scheduled follow-up remains paused.

## 2026-10-25: Codex focused reuse search

Added five ranked research candidates to the Claude decision brief: event scheduling, owned-code profiling, interruptible behavior patterns, navigation diagnostics and bounded noise generation. Checked primary docs and existing prototype/tooling notes; no measured speedup, library selection, implementation or native test. Guard/diff checked; automation stays paused.

## 2026-10-25: Codex practical modding-tool research

Owner-requested follow-up maps the seven suggested tools and additional API, asset, record, editor and native-analysis candidates to existing project gaps. Upstream Caprica has guard generation with unresolved verification TODOs, correcting the older categorical absence claim without changing the official-compiler decision. Cassiopeia API/permission checks, independent asset validation and bounded workflow proposals documented with sources. Decision brief now carries current mode, no-runtime-model, FO76/ghoul and Warfare succession direction. Documentation only; no tools installed, source implementation, proprietary data publication, native execution, merge or agent wake. Automated follow-up remains paused; independent document review pending.

## 2026-10-25: Codex scope and lore coverage audit

Owner requested a broader review of research depth. Audited the available 1176-row lore ledger (206 full/371 partial/599 todo), submitted170 geography records and selected framework coverage/uncertainty sections. Full3844-entry store unavailable in this mirror; no comprehensive lore verification claimed. Documented section exclusions, an84-entry handoff count discrepancy requiring reconciliation, and reproduced two held entries printing adopted without their ruling through the existing formatter. Three fresh wiki opens returned403, not verified. Added scope matrix and prioritized research packets; no store/source edits, game actions, merge, peer wake or automation resume. Private audit evidence preserved separately; independent document review pending.

## 2026-10-28: The combined core's seed, rerun with all seven Fallout 4 plugins

Offline on the owner's PC, read-only on game files, run by the Install thread at
main de91d6d0 into D:\Modding\research\combined_seed3. The data was the owner's
Steam Fallout 4, the newer build, because the 1.10.163 depot copy lacks
DLCCoast, DLCworkshop02, DLCworkshop03 and DLCNukaWorld; the sha256s are in
docs/combined-core.md, "Real pack, all DLC". The seed read 487 locations, and
the generated pack kept 243 places, 42 settlements and 7 holding factions. In
`simulate --seed 1 --days 30`, 36 of 42 settlements ended at stage 3 with 14
people, below their 20 beds; on 21 Oct, 36 of 38 sat at the bed cap. A 10-seed,
30-day `balance` showed no settlement at its cap, population share 0.64 and
morale 99. The command exited 1 on the fixtures' absolute bounds (attacks 3.91
a day, 80.1 holder changes per 30 days). Per place and per faction, the scale
bounds' terms, those are 0.33 and 0.56, inside the bounds and close to the
synthetic baseline. At 30 days, morale above the scale bound's 95 was the one
miss. A 5-seed, 90-day sweep of the same pack passes every scale bound (morale
76.3, 11% of settlements at the cap, 5.1 settlement captures per 30 days) and
sits close to the synthetic column D, so no rule changes. `balance --bounds
scale` now picks that yardstick. Nothing here ran in game.

## 2026-10-28: The combined core's first in-game probes

The Install thread ran the probe plugin on the owner's PC with the stage and
judges at main de91d6d0, each probe from the main menu with FO4SFMission.esm
off. The first P2 attempt failed with "Cannot open store for class FOCC_Probe":
the owner's 24 Oct save had been made with Mission on, and loading it silently
switched Starfield back to that save's load order, probe plugin off, with no
dialog. Started from the main menu instead, P2 and P3 persisted their keyword
data across a relaunch and a load (37 read back as 37, linked locations still
linked, 5 and 6 read back as 5 and 6). The judges first said INCONCLUSIVE,
because OnInit does not run again on loading such a save and the second log
had no init line; since #556 they accept a restarted real-time clock instead,
and both folders then judged PASS. P4 passed: 20 cycles placed and deleted
three actors each, and the save shrank by 1,776 bytes. P6 and P7 passed: the
leveled lists picked base A or B from location keyword data and from our
reputation global. P5 recorded 10 ticks over 50 globals at a median 121 ms,
2.42 ms per place, and the compiler's 128-entry array cap. The P8 judge said
FAIL, wrongly: every child matched its parent, but the three stage calls ran
in one console session, where Utility.Wait does not count down, so all three
readouts saw the last stage. It now says INCONCLUSIVE for that, and P8 is to
be rerun with the console closed between calls. P10 is INCONCLUSIVE: its quest
started at game start, 44 s before the story event was sent. The likely cause
is that our Story Manager branch had no condition, so any vanilla script event
could start it; the builder now copies the keyword filter of Starfield.esm's
own Script Event nodes, and P10 waits on a restage. Details are in
docs/spikes/combined-core-probes.md, "Results on the owner's PC".


## 2026-10-28: The runner's SFSE launch and the installed port

Before T6 and the animated doors checks, the Install thread found two gaps in
the test runner. It launched the game through Steam, which loads no SFSE
plugin, so T6's comparison of the two FO4SFBorder modes compared nothing. And
every launch redeployed the queue's staging, so the animated doors port, once
installed, would have been replaced by the older port without a word. Passing
the doors build's port folder as the staging would have been worse: the
deploy packs archives from loose files that folder does not have, after the
installed port was already removed. Queues can now be planned with
`--launch sfse` (cycle.ps1 starts sfse_loader.exe) and `--port installed`
(cycle.ps1 deploys nothing and checks the installed port against its deploy
record and the plugin pinned at plan time, stopping before launch on any
difference). An older runner refuses such a queue, and cycle.ps1 refuses an
interior batch stage as `-Staging` before it touches anything. Details are in
docs/ai/test-queue.md, "SFSE launch and the installed port".


## 2026-10-28: Door rounds accept the animated doors

T6 stopped at its stage on the PC before touching the game. The door rounds
stager skipped all 13 doors of the installed animated doors port, because it
accepted only `FO4SF_LoadDoor` on a door and the port puts
`FO4SF_AnimatedLoadDoor` on its interior doors. The animated script extends
`FO4SF_LoadDoor`: it waits for the door's open animation, then runs the
parent's own trip, with the same properties and the same trace lines. So T6's
`PlaceDestination` and `SettleSeconds` work, which lives in the parent script
the bridge carries, still applies to these doors. The stager now checks either
script, the animated one with its `OpenSeconds` too, and records which one each
door has. The judge did not need a change. Details are in
docs/terrain/door-rounds.md.

## 2026-10-28: Probe session 2, the P3 cell judge and a scripted driver for P9

P8 ran again with the console closed for about 4 s after each stage call, and
passed: every child followed its parent in each stage's layout, and the save
did not grow. After #557's restage, P10 passed: the story event started our
quest only once it was sent. P3's cell half logged both cells with our two
locations, but the game wrote no editor id for either cell, and the judge
named cells only by editor id, so it said INCONCLUSIVE. The judge now names
them by the form ids the stage recorded for them, and the existing log can be
judged again. P9's first run (600 s with `PathToRef` to a marker 450 m away,
the actor within about 3 m of its start) is INCONCLUSIVE, not FAIL: this
repo's NPC tests never showed `PathToRef` moving a calm citizen beyond its own
wander. The ladder's control then settled the console route: from 16.7 m,
`PathToRef player` left the actor about 22 m from the player. The next driver
is `Actor.PathToReference` called from Papyrus (FOCC_P9Drive), which the
console's `cf` never reached. It is compiled on its own, so if Starfield does
not declare it only P9 waits. The P9 card is the same ladder with that driver,
and the judge gives FAIL only after a scripted control that arrived. Codex's
independent review of that change found three holes in the judges, each shown
through the judge's own command line, and the fixes are in the same PR. The
stage's file proves which source records the two cells are, not which plugin
holds their load slot in a given run, so the probe script now asks the game
(`Game.GetFormFromFile` on FO4Port.esm) whether the cell the player stands in
is that record and logs `port=True`; an unnamed cell counts only with it, and
the 28 Oct log, which has no `port=`, is run again after the restage instead
of judged again. A `p9 go` counts only inside its rung's track, and only the
samples after it answer it, so an actor that arrived before it was commanded
is no control. And a rung with no go may be the actor's own wander, since a
console command leaves no line, so it never stands as the control and a
console-driven rung is judged by its own approach only. Codex's second round
found the last gap: the control's distance came from its start line, so an
actor that wandered from 20 m to 8 m before its go and stayed there passed as
a commanded arrival. The distance that counts is now the go line's, the
control must be found 15 to 30 m out by its go, and a judged rung's route
length is its go's distance too. Four more rounds, from Codex's bot and desktop
reviews, tightened the control: its walk must pass the judged rung's own checks
(a timed go, every sample timed, placed and with a readable loaded flag, the
first sample within a walk's reach of the go, no teleport-fast step, loaded in
at least half of them), and the judged rung's go must name the tracked
destination, since the tracker measures the distance to FOCC_P9_Dest and a long
rung sent to the player by mistake is a different walk than the samples
describe. Details are in docs/spikes/combined-core-probes.md.

## 2026-10-28: The runner finds a batch stage's cell exports

The first T6 door runs on the animated doors port (doors_anim_b00, with
`--port installed`) tested nothing: cycle.ps1 asked coc.ps1 for the launch
cell's export next to FO4Port.esm, as a slice stage lays it out, but an
interior batch stage keeps its exports in base_exports, so r01 exited 4 after
the launch and r02 to r04 never reached a cell (no FO4SF line in the game's
log). The plan now records where the exports are (the staging, the stage's
base_exports when the staging is its port folder, or `--cell-exports`), pins
each export the queue launches into or travels to when they lie outside the
staging, and says so when none can be found; the runner checks the export
before any launch or coc and stops with the reason. The later runs of that
batch hit the focus guard instead: the Claude desktop window was in front
after a Remote Control restart, and Install now minimises its own window
before each launch. Codex on the PR: the runner launches into a test's own
cell, so only a test without a cell needs the launch cell's export, and the
plan asks for just the exports the runner reads; the export is checked after
the staged experiment, so a changed experiment is still the first reason
given. Details: docs/ai/test-queue.md, "SFSE launch and the installed port".

## 2026-10-28: The front page rewritten

The README was a running progress log. After the branch cleanup (160 old
branches deleted, #552) it is rewritten as a front page: what the project is,
where it stands in one table of areas with what was seen, where and when, the
two ways to play, the pipeline, the repository map, why the conversion is
difficult, and the rules. Every row is taken from a document in this
repository; the earlier progress sections are kept verbatim in
docs/history/readme-progress-2026-10.md. The record behind the table's test
count: at #560's merge (main b00b5e63, head cd76c4a5, 28 Oct) `python -m
unittest discover -s tests` ran 3,592 tests, OK with 151 skipped where no .NET
SDK is present, and `python scripts/guard.py` said ok; CI's checks job runs
the same two commands on every pull request. Codex's review of the page
corrected three rows against the docs: the 253 interiors held for install are
the 251 planned base-game cells and Automatron's 2 on top of the 16 installed,
with 4 hook cells left out (docs/terrain/interior-batches.md); the new game is
staged against the installed core and, by the record, not yet run in game
(docs/ROADMAP.md, the owner's test sheet); and the test count needed this
entry as its source.

## 2026-10-28: CI's checks job given 30 minutes

The checks job (guard, then the whole unittest suite with the .NET SDK
present, 3,688 tests) took 886 s on the GitHub runner for the README pull
request and was cancelled by its 15-minute limit right after printing OK;
the run before it, on the runner fix, took 14 min 47 s. The limit is now
30 minutes. The suite itself is unchanged; a faster split of the job is a
later choice, not a fix for a green suite cut off at the line.

## 2026-10-28: P9's driver gets Starfield's third PathToReference argument

The PC's restage of the probe kit from main c0c3c96c compiled everything but
FOCC_P9Drive: "argument afnormalizedrotationspeed is not specified and has no
default value". That line settles what the spike left open: Starfield's
Actor.psc declares PathToReference with three arguments, the target, the
walk-run percent and a normalized rotation speed, the third without a default.
The driver now passes 1.0 for it; the compile on the next stage is the check,
and the P9 ladder shows what the value does to the walk. P3b runs on the stage
as it is, since only this script was left out.

## 2026-10-28: Bridge t6's marker move undone: the Vault 95 exit never left the interior

The first bridge t6 runs (#512's PlaceDestination, with the animated doors
port): 20 Vault 95 exits, 19 FAIL STAYED, 1 not run, 0 landings, with the
border switch off and on alike. The trace of every failure is the door
script's own: marker_placed (the exterior marker set to the merged spot with
SetPosition, 2.9 km from its cell, while unloaded), then MoveTo returned with
the player still in the interior cell, then the retry's MoveTo the same. The
runner makes no such move on the OUT leg (its moves are the coc into the
interior and the drop onto its marker), and without the marker move (t4, t5)
every traced MoveTo of this door landed outside, including the owner's exits
of 23 and 24 Oct. So the marker move is withdrawn from FO4SF_LoadDoor.psc; the
settle trace and the player's SetPosition to the merged spot after the move
stay as they were. Why the engine ignores a MoveTo onto a marker moved that
way is open. A quick check that needs no new build: bridge t5 (retry, no
marker move) on the same port and queue; if it lands, the marker move alone
was the cause, and if not, the animated door wrapper is next.

## 2026-10-28: P1's build scripts learn the portable MSVC; B0's stack checked against 1.16.244

The owner approved C++ build tools on 28 Oct and Install put a portable MSVC
14.44 with the Windows SDK 10.0.26100 under D:\Modding\tools, loaded by
dot-sourcing msvc_env.ps1: no Visual Studio, so nothing for vswhere to find.
FOCCSidecar's check_toolchain.ps1 and build.ps1, the P1 probe's scripts, only
knew vswhere and vcvars64. Both now take a loaded environment first (cl.exe on
PATH with INCLUDE and LIB set, or the script passed as -Env, which they
dot-source), fall back to vswhere, and record which route in toolchain.json
and build.json; the SDK is read from INCLUDE before the registry. The compiler
line is unchanged. Codex's one finding on the PR: an x86 developer prompt
also sets cl.exe, INCLUDE and LIB, so the environment route now reads cl.exe's
banner and refuses anything but x64. tests/test_sfse_sidecar_scripts.py pins
the contract. P1 can run on the PC without CommonLibSF.

For B0 (docs/combined-core-cpp-port.md, section 4) CommonLibSF 9caec20 was
read offline. spdlog: upstream pins no version and names spdlog from a
registry that is gone; its four spdlog surfaces are all in Install's 1.17.0,
so building the library is the whole check. Address Library: SFSE::Init loads
versionlib-<runtime>.bin before anything else and fails the game without it;
v22 covers 1.16.244, a Nexus download. Runtime: the commit is from September
2025, knows runtimes up to 1.14.74, and registers Papyrus natives through a
call hook at REL::ID(169912)+0x514, unverified on 1.16.244. The plan now puts
three stacks to the owner: A, the Address Library and B0 as written; B, a
bridge with no game addresses on the two mechanisms FO4SFBorder already
proved (log tail in, named setting out), with Utility.GetINI* to verify; C,
check libxse first.

## 2026-10-28: B0 kit: the probe plugin's game setting, FOCC_B0 and its judge; P9's driver logs its result code

The owner picked stack A for the bridge spike (16:45 UTC: make sure it does
not break, fix it if it does; B fine as the backup; C when needed, a mod
dependency being no problem unless it restricts modding of the finished
work). The kit side is now in the probe stage: GMST iFOCC_Pong = 7 (0x855,
NextId 0x856) in FO4SFCombinedProbe.esm, FOCC.psc (the native stub the plugin
binds, Ping(v) = v + 1) and FOCC_B0.psc (Gmst reads the setting back with
Game.GetGameSettingInt, declared in Starfield's Game.psc per Install; Ping
traces the sent value, calls the native and traces the answer), both compiled
on their own (compile_b0.txt) and packed only when both compile, so a refusal
leaves only B0 out. probes.py judges b0: B0-1 (7 read back; no SFSE plugin,
so it runs with any probe session and settles B's return leg) and B0-2 (a
pong of sent + 1, or on the setting route a gmst read of sent + 1 after the
ping). Runbook section B0 holds the cards, with the Address Library and the
FOCCPing dll as the owner's lines. The plugin itself (sfse/FOCCPing) is the
next PR.

P9: Install read Starfield's Actor.psc (line 490): PathToReference returns an
int, latent, with PathingResult_Success 0, Failure 1, Stopped 2, Cleared 3,
Timeout 4. The kit d ladder's rung b (28 Oct) returned after 2.89 s with the
actor 26.7 m out and no code logged, so it could not tell a missing path
from a stopped walk. FOCC_P9Drive now puts result= on the `p9 path returned`
line and the judge names the code; the next rung decides between the navmesh
(1) and the AI (2, 4) before any new driver is written.

## 2026-10-28: FOCCPing, the B0 spike's SFSE plugin

sfse/FOCCPing is the plugin half of B0 on the owner's stack A: one Papyrus
native, FOCC.Ping(int) answering int + 1, bound in CommonLibSF's Papyrus
callback (the trampoline hook at REL::ID(169912) + 0x514; the first launch on
1.16.244 is its test). Version data: Address Library, layout dependent,
runtime 1.16.244. CMake links the installed CommonLibSF::CommonLibSF with the
dynamic CRT its triplet uses; build.ps1 takes the install prefix and the
library's vcpkg_installed folder as CMAKE_PREFIX_PATH, the loaded MSVC
environment (x64 only, as FOCCSidecar's scripts), and writes build.json into a
new staging folder. Nothing of CommonLibSF is in the repo; its GPL-with-
exceptions licence review is owed before anything built on it ships. The
Address Library archive turned out to be on the PC already (Install's state
note, 24 Oct), so the runbook's B0-2 card names it there. Not compiled here:
the PC build is the check, and the kit's rule (a dll that keeps the game from
the main menu is deleted at once) stands.

## 2026-10-28: FOCCSidecar build.ps1, the /link half was its own batch line

Install's find on the PC (P1-1, 28 Oct): inside the `@( )` array that
becomes build.cmd, the comma bound tighter than `+`, so the concatenated
`"/link /PDB:... /IMPLIB:..."` half of the cl line became a line of its own.
cl linked without the pdb and import library, cmd then ran `/link` (9009),
and the script reported failure although FOCCSidecar.dll was there. Install
patched it by hand and built (D:\Modding\staging\focc_sfse_20261028c, exit
0). The fix here builds the line in a `$cl` statement and puts the variable
in the array; a test pins the shape. The C4245 at FOCCSidecar.cpp(59) is a
cast: PluginAPI.h's kPluginHandle_Invalid is an int enumerator, PluginHandle
a std::uint32_t. CommonLibSF is built and installed on the PC (prefix
D:\Modding\tools\CommonLibSF-install), so the FOCCPing README and the B0-2
card name the real paths.

## 2026-10-28: the runner loads the dedicated save by name

Install's find, 28 Oct: cycle.ps1 entered the game with the main menu's
Continue, which loads the newest save. The owner's new-game autosaves of
the morning were newer than fo4sf_test_<build>, so every save-based run
landed in ship combat, the HUD guard never passed, and the session's own
named load (setup_session) never ran: door check (a) came out INCONCLUSIVE
NOT_ACTIVATED from a cockpit. The stopgap was touching the dedicated
save's mtime. Now testqueue.py passes -Save fo4sf_test_<build> once that
save exists, cycle.ps1 checks the file before it closes or deploys
anything, opens the console at the main menu and types `load <name>` (the
line qstep.ps1's load step types in game), and stops with exit 11 when no
HUD follows; the session skips its second load. A build's first session,
with no dedicated save yet, still enters through Continue and creates it.

## 2026-10-28: Map markers: a door mid-pass, a pad that will not move, a landing marker to discover

The owner's report on 28 Oct: no map icons after `coc FO4Core_RedRocketSpawn`,
and no Commonwealth location on Mars's map to fast travel to. The 24 Oct Card
B logs show two faults in FO4SF_MapMarkers. The landing pad refuses every
MoveTo ("cannot be moved", Papyrus.0.log), so the fourth quest spent its whole
budget on it and the pad never reached the world the player walks in. And a
Vault 95 door trip during a pass put about 300 markers at their target plus
the trip's offset, because Place read the player once, and the spent budgets
kept them there for that save. The script now reads the player before every
move and stops the pass indoors or in another world, skips a reference the
game refused for the rest of the session, starts the budget over every game
session, and marks the landing marker discovered and visible on the star map
once per session. dotnet/MapMarkers keeps the landing spot's four pieces in
one quest, so the marker is always two places after the pad. Icons on the
first arrival are a separate limit: Skyrim modders find the map takes markers
only on entering a world, so moving them cannot show them at once
(docs/terrain/map-markers.md, "Icons, the pad and the planet map"). A save and
load, and Mars's map, are the PC test.

## 2026-10-28: the Address Library for 1.16.244 is format 5; FOCCPing moves to libxse/commonlibsf

The first PC build of FOCCPing against CommonLibSF 9caec20 compiled on the
first try (570,368 bytes), and Install's header check of the Address Library
before the install found the break: the v22 versionlib-1-16-244-0.bin starts
with 05 00 00 00 01 00 00 00 10 00 00 00 F4 00 00 00, format 5 for game
1.16.244, while 9caec20 (and the archived upstream main) read format 2 only
(src/REL/ID.cpp, kDatabaseVersion = 2). The dll would have stopped the game
at SFSE::Init with "Unsupported address library format: 5"; it was not
installed. The original Starfield-Reverse-Engineering/CommonLibSF repository
is archived and points to libxse/commonlibsf (9d090c4, 6 Oct 2026), whose
shared layer (libxse/commonlib-shared 9fbb74d) reads formats 1, 2 and 5
(IDDB.cpp load_v5: the header, then a flat uint32 offset table indexed by id),
sets SFSE's AddressLibraryV2 version-data bit (the only library bit SFSE
0.2.21's PluginManager counts as address independence; 9caec20 set the v1
bit) and carries the 1.15.216+ ids. It builds with xmake 3.0+, not cmake,
and has no SFSE::SetPapyrusCallback. sfse/FOCCPing is now an xmake project in
the shape of libxse/commonlibsf-template (the library's commonlibsf.plugin
rule writes the version data); main.cpp binds FOCC.Ping on SFSE's
kPostDataLoad message through RE::GameVM::GetSingleton()->GetVM()
->BindNativeMethod, no hook, no trampoline; build.ps1 drives xmake in the
PC's portable MSVC environment, making xmake's Visual Studio-shaped root
(VC and Windows Kits as directory junctions in the staging folder) from
VCToolsInstallDir and WindowsSdkDir, and junctions the library checkout
(D:\Modding\tools\libxse-commonlibsf, with xmake 3.1.2 beside it) into the
staging copy of the project. The runbook's B0-2 card and the port plan
record the finding; the format check now expects 05 00 00 00. Unverified
until the first launch: that the GameVM singleton is set by kPostDataLoad,
and that a native bound after BindEverythingToScript is callable from
FOCC.pex.

## 2026-10-28: Map markers: the pad's refusal is read from its world alone

PC attempts 2 and 3 of the #570 test (a new game, `coc FO4Core_RedRocketSpawn`
from the main menu) logged `FO4Core_CommonwealthLandingPadRedRocketNorth
(090008F0): cannot be moved.` 18 and 27 times and never `refused 9`: after
each failed MoveTo the pad was still in its own world (d float max), but the
rule also asked for its x/y read before and after to match, and that never
held. The rule now refuses a reference still in another world after the move
while the player stayed in theirs (a move that works lands at d 0.8 to 2.9 km
at once), stops the pass instead when the player left, and logs where the
reference was before. Every marker reached the player's world within about
10 s of arrival. Mars's surface map showed one hexagon; the owner, who
watched the run, assumes it is all our icons layered under one, the way
Starfield draws a city, and asked for research; whether it lists our places
for fast travel is the next check.
A save load closes the user logs (`Log closed` in fo4sf_map.0.log); attempt 4
had no map pass after its load because the console stayed open.

## 2026-10-28: Map markers: a short star map list (the owner's pick A)

Research (web and Creation Kit sources, `/mnt/project-files/map/starfield-map-icon-grouping.md`)
supports the owner's reading: Mars's planet view stacks every marker with
Visible on Star Map (`FNAM` 0x10) at one spot on the globe under one icon,
and all our markers had it, so the list held about 309 places. The owner
picked A: `dotnet/MapMarkers --star-map` now keeps that bit only on the
listed markers (the stage's default: Red Rocket Truck Stop, Sanctuary Hills,
Vault 111, Concord, Lexington, The Castle, Vault 81, Bunker Hill) and on the
landing marker; every marker stays on the surface map. xEdit's SF1
definitions name `TNAM` 0x17 "NASA", not a plain diamond. Offline only;
the planet view list and fast travel from it wait on a play test.

## 2026-10-31: Map markers: a reload once every marker is in

The owner's new game v10 run: Mars's map icons were fine, but no Commonwealth
marker showed on the map or could be discovered on the way past until a
trip to Cydonia and back. The map log shows the markers came in after the
player did: out of the elevator at rt 179 s, the first move at 186 s, the
last first move at 233 s (four quests of 100, a marker every 0.45 s each),
and 475 moves for 313 markers, because a move onto a walking player lands
off by their steps. A log from 24 Oct shows the world keeps the markers
through such a trip (same instance id, nothing moved again). Offline fix,
waiting on a play test: quests of 20 instead of 100, fewer reads a marker,
a SetPosition after each move, and with `--reload` (the stage's default) a
small interior of the plugin's own: once every marker is in place and some
came after the player, the first quest takes the player there and back to
the same spot behind a black screen, once a session, so the world loads
again with the markers in it. New log lines say whether fast travel is on
and whether the world stayed the same through the reload.

## 2026-10-31: Map markers: the reload works; the screen stays dark until it is back

The owner's retest of the reload (#624): after waiting outdoors, the
Commonwealth's icons were on the map. The log shows 16 quests placed the 313
markers in 20 s (was 47 s), one move each (was 475 moves), and the round
trip through the stop took 6.3 s with the player back on the same spot in
the same world. The first test had shown nothing because the map was opened
11 s after the arrival, before any reload. Option A (Claude's pick, put to
the owner with B, the elevator only, and C, messages only): from an
arrival, the first quest keeps the screen black until the reload is back
(about 31 s in the retest), with every way out fading back in (60 s at most,
a fight, going indoors, leaving the map). Offline; waits on a play test.

## 2026-10-31: Map markers: the owner's play test of the dark hold: "everything worked"

The owner played #626 (the screen stays black from an arrival until the
reload is back) and reported: "ok everything worked only issue left will be
solved with the pipboy". The owner named neither the icons nor which issue
is left; the hold was built so the Commonwealth's icons are on the first map
the player opens, with no trip to Cydonia. Option A stands; B and C were not
built. The run's log was not read. The issue left is for the Pip-Boy, in the
owner's words.

## 2026-11-01: Map markers: the dark hold's logs read; one Claude session

The game's own script logs still held the play test's map log, so they were
copied to the PC's test-log folder before they rotated out. The play test's
hold ended with the reload after 30.8 s, as in the retest. In a probe
session on 1 Nov (coc to Red Rocket) the last marker move came 23.5 s into
the hold, then the map log went quiet for 38.8 s until the 60 s cap released
the hold; the reload went out 3.5 s later. The cap works as written; why no
reload came in that gap is not known. The roadmap gains a short "since 24
October" update. By the owner's 1 Nov handoff (written by Claude, given by the
owner), one Claude session on the PC
holds every Claude role and the cloud session pauses (decisions.md, 1 Nov).
