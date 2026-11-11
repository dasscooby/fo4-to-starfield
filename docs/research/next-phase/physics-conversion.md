# Next phase: physics conversion at full-game scale (movable props, ragdolls, weapons)

Claude-cloud, physics thread, 2026-10-19. Labels follow docs/ai/research-log.md: **verified** (file, command, output),
**supported hypothesis**, **unresolved**. Repo state read at origin/main 4492d13.

## 1. How much physics Fallout 4 has (verified)

Counted from the clean `Fallout4.esm` (depot copy, 330,745,373 bytes; `C:\Program Files (x86)\Steam\steamapps\content\app_377160\depot_377163\Data`)
with a Python record walk (scripts in the physics thread's scratch, not committed). Placed references by base type:

| Base type | Placed refs (all) | In interiors | Distinct bases placed | Physics meaning |
|---|---:|---:|---:|---|
| MSTT movable static | 40,140 | 25,057 | 753 | havok props: crates, cans, barrels, skeletons, breakables |
| MISC loose item | 36,710 | 24,955 | 674 | pick-up items, mostly one dynamic body |
| ALCH / BOOK / KEYM / NOTE / AMMO / ARMO | 5,130 / 261 / 50 / 104 / 450 / 627 | | | pick-ups, same body kind as MISC |
| WEAP placed in the world | 505 | 307 | 49 | pick-ups (#329 started this for the core) |
| ACTI (traps, switches, plates among them) | 14,994 | 7,989 | | today written as statics |
| BNDS bendable splines (wires, ropes) | 7,660 | 2,554 | | no physics in FO4 either (static splines) |
| STAT for comparison | 981,804 | 384,561 | | fixed collision |

Base records: 961 MSTT, 2,176 MISC, 252 WEAP, 3,015 NPC_, 45 RACE, 139 PROJ, 238 EXPL. Placed actors (ACHR): 7,615.
Not counted: Far Harbor, Nuka-World, Vault-Tec and Contraptions Workshop (their .esm files are not in the clean depot
copy; only DLCRobot and DLCworkshop01 are). The user's rule is that every DLC is assumed, so these four must be
installed into the clean copy before a full-game build.

So the movable layer is roughly 80,000 references over about 1,500 distinct models: about 7% of all placements but
most of what the player touches.

## 2. What the converter already does (verified from code, in-game where noted)

- **Single-body loose items** (one dynamic FO4 body on the root): become movable with a vanilla-derived dynamic Havok
  body, BSXFlags 0x42, placed as MoveableStatic; FO4 mass kept (`convert_static.py` dynamic_template path,
  `--mass-scale` exists, default 1.0). In game: can, compound cone, book pushed (known-unknowns #6). Moving items PASS
  by hand Oct 17.
- **Multi-body systems** (skeletons, breakables, hose-and-tank): "phase A", merged into ONE rigid compound body with the
  system's total mass (`_rigid_ragdoll`, decisions 2026-10-10). Joints are lost: a skeleton moves as one lump.
- **Placement poses (XRGD)**: 507 references carry ragdoll pose data; 147 articulated ones get a posed model per
  pose (`placed_pose.py`); 214 single-body items are left unposed (frame **unresolved**).
- **Static collision**: FO4 compressed mesh shapes are transplanted to Starfield's format (`meshcollision.py`), convex
  hulls and boxes supported (`sfbodies.py`, `sfcollision.py`).
- **Not done**: constraints (hinges, ball sockets, ragdoll joints), breakage (destructibles), mass properties
  (`hknpShapeMassProperties` absent but bodies still move: supported hypothesis), activators and traps (statics), CONT
  records (containers don't open), actor ragdolls, weapon physics.

## 3. Open questions that block "the same physics as Fallout 4"

1. **Feel and mass** (unresolved, measured partly): FO4 small items are 2-10x heavier than comparable Starfield items;
   the owner liked a 5 kg override by console. Queue `movable_control_1013b` (QASmoke) compares ours with vanilla of
   the same size; not yet judged on the current build. Decision needed: keep FO4 kg, or scale per class to
   Starfield's range (`--mass-scale` is global today; a per-class table is a small change).
2. **Single-body XRGD frame** (unresolved): 214 placed items may sit wrong; a resting test exists for articulated
   models only.
3. **REFR rotation order** (known-unknowns #7): affects posed skeletons and any physics placement check; the shared
   rotation-order correction is gameplay gate 4.
4. **Constraints (phase B)**: Starfield's Havok 2019 tagfile has the hknp constraint types (supported hypothesis: the
   same SDK family as FO4's hk_2014 hknp, which has them), but we have no decoded vanilla Starfield constraint blob yet.
   Without it, ragdolls, hanging lamps, chains and doors-on-hinges stay rigid or static. First step: dump one vanilla
   Starfield NIF with a hinge or ragdoll (a corpse or hanging sign) with `hktagfile.py` and compare to FO4's
   `bhkRagdollConstraint` / `bhkHingeConstraint` data.
5. **Actor ragdolls** (unresolved): Starfield actors ragdoll through their own skeleton and behaviour graph; ported
   NPCs today use Starfield races (raider conversion), so they ragdoll as Starfield humans. A FO4-skeleton ragdoll
   (super mutants, deathclaws, mirelurks) needs the animation/skeleton lane first; physics follows it.
6. **Weapons** (unresolved): a world-placed WEAP is a pick-up after #329; equipping and firing need new weapon records
   and Starfield rigs (PLAN P1). Projectile physics (gravity, impulse on hit) comes from PROJ/EXPL records, not NIFs: a
   record-mapping job, not mesh conversion.
7. **Activation chains** (plates, tripwires, traps): wiring is scripts (#336 Grok census, #337 Codex identities and
   Papyrus plan). Fallout 4's longest plate/tripwire chain in any interior is 2 steps (verified Oct 18, Fallout4.esm
   activate-parent walk), so no vanilla cell is a Rube Goldberg test.

## 4. Recommended order for the next phase (breadth before polish)

1. **Run the whole movable layer through the existing path** on the full-game build (all cells, all DLC): every
   MSTT/MISC/pick-up becomes movable or is listed in `dynamic_kept_static` with a reason. Cost is conversion time only;
   the report gives the real failure classes at scale. Output: a per-base table (movable / merged rigid / kept static,
   reason) for the evidence store.
2. **Judge the mass question once** with the staged QASmoke control queue, then set a per-class mass table (small
   converter change plus tests). Re-run nothing else for it.
3. **Containers and pick-ups as records** (CONT, ALCH, BOOK, AMMO, ARMO, WEAP placements): record mapping, the most
   visible "doesn't work" in play (containers FAIL Oct 17).
4. **Decode one vanilla Starfield constraint** (step 3.4) before promising ragdolls or hinged props.
5. **Physics lab cell** (the owner's Rube Goldberg idea, parked as the last step of this phase): a layout-file test
   cell from vanilla and Contraptions Workshop parts (ball tracks, plates, rolling and tumbling items, a domino row,
   weak planks), ported like an exported cell, with a matching FO4 plugin for side-by-side comparison. Plan posted in
   thread "Rube Goldberg" (memory physics-lab-cell).

## 5. Launcher fit (GAMMA-style, nothing shipped)

Everything above is built on the user's PC from their own Fallout 4 and DLC: the dynamic body template and mesh
templates are read from the user's Starfield install at build time (already the rule in `meshcollision.py` and
`sfcollision.py`). Nothing physics-related needs shipped assets. The launcher needs: the clean FO4 + all-DLC data path,
the mass table version, and the build report per base type kept as evidence.

## Sources
- Repo (origin/main 4492d13): src/fo4sf/convert_static.py, meshcollision.py, sfbodies.py, sfcollision.py,
  placed_pose.py, ragdoll_pose.py; docs/ai/known-unknowns.md #6 #7; docs/ai/decisions.md 2026-10-10, 2026-10-13;
  docs/ai/research-log.md 2026-10-11, 2026-10-16.
- Counts: depot Fallout4.esm record walk, 2026-10-19 (1,244,511 placed REFR in cell groups).
- Starfield tooling seen: [Havok Physics Editor for Starfield (Nexus 8262)](https://www.nexusmods.com/starfield/mods/8262)
  authors cloth (BSClothExtraData) with some constraints, uses The12thAvenger's HKLib; no dynamic-body or ragdoll
  authoring. Possible reference for constraint layouts, not a dependency.
