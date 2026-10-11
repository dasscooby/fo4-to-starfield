# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

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
