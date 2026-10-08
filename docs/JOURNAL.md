# Evidence journal

Newest last. Each entry: date, versions, what was done, the result, and where the evidence is.

## 2026-10-06: WP-00 recon (Fallout 4 1.10.163, Starfield 1.16.244)

**Done:** read-only scan of `Fallout4.esm` and `Starfield.esm` record trees, every BA2 name table in both games, and
sample NIF headers (`scripts/recon.py`, `scripts/recon_physics.py`). About 9 s runtime.

**Result:** see [FORMAT-GAP.md](FORMAT-GAP.md); raw data in [measurements/](measurements/).
Headlines: plugin form versions 131 vs 581; 116 of 137 record types shared but field overlap mostly
25–60%; no `LAND` or `SNDR` in Starfield; NIF BS 130 vs 175 with external `.mesh` geometry; Havok packfile vs
tagfile; `.bgsm` vs `.mat`/`.cdb`.

**Open questions it raised:** meaning of the `.mesh` header fields (S1); how Starfield custom worldspaces get
terrain (S5); whether Mutagen's Starfield alpha can write usable plugins (S2).

**Tooling gathered:** NifSkope (fo76utils) dev11 2025-12-30, xEdit 4.1.5f (includes `xSFEdit`),
PyNifly V29.1.0, Blender 5.2.2, .NET SDK 9, Starfield Creation Kit (Steam 2722710), SFSE 0.2.21 (manual from Nexus).

**Prior art search:** no public Fallout 4 → Starfield conversion project was found on GitHub or the web.
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
