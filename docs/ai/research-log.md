# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

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
  in-game test. Open: vanilla dynamic shapes also carry `hknpShapeMassProperties`; ours don't (not needed by Havok when
  the body has a mass distribution: **unresolved** until tested).

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
