# Object LOD (playtest row 24)

Author: Grok, 2026-10-17. Status: **research + scoped plan, no build**.

The owner, on foot at Red Rocket, sees “extremely long distances you can just see nothingness”. Terrain LOD is in the
BTD (LOD0–4, already authored). **Object LOD is separate.**

## Vanilla (**verified**, Starfield 1.16.244)

`Starfield - LODMeshes.ba2`: 20,400 files = 19,535 `meshes/lod/generated/…_lod_{0-3}.nif` (cities included), **864**
`lodsettings/<world>.lod`, 1 `distantlod/lodruntimedb.bgsdb`. **861 of 864** `.lod` files are **20 bytes** (2 are 22, 1
is 16); e.g. `lc172world` / `landingoverlay01` `FE FF FF FF FE FF FF FF 08 00…`; `newatlantis`
`DD FF FF FF C5 FF FF FF 88 00…` — cell min/size, **supported**. FO4 object LOD is `.bto` (FORMAT-GAP); not this format. FO4 source kinds and conversion go/no-go:
[fo4-lod-meshes.md](fo4-lod-meshes.md).

Pinned core64k `Data\` has **zero** `.lod` / `meshes/lod`. Overlay objects are full STAT/ACTI only, so past the loaded
window Starfield draws BTD terrain and nothing else. Matches the walk.

## INI

`Starfield.ini` `uExterior Cell Buffer=36`; High/Ultra do not override it. Raising it keeps more **full-detail**
converted meshes in memory (648k refs) and still has no distant stand-ins once cells drop. Not the product fix. The
owner’s `setini "fLODFadeOutMultObjects:LOD" 15` is a fade-multiplier experiment, not object LOD.

## Tooling

CK is the **hypothesized** generator of object LOD (plan step 1 is the spike). This repo has no writer. Per-mesh
`sfmesh` LOD index arrays are not world object LOD.

## Plan (no build now)

1. Tiny overlay + CK object-LOD generate as a go/no-go (Claude window).
2. Only then a `lodsettings` stub named for `FO4Core_Commonwealth` plus generated `_lod_0..3` for large STAT.
3. Do not port FO4 `.bto` until that spike. No INI change in the product path.

## Format read from the vanilla archive (Claude-cloud, 2026-10-22, read-only)

Read with `src/fo4sf/ba2.py` from the owner's `Starfield - LODMeshesPatch.ba2` (20,405 entries; `LODMeshes.ba2`
has 20,400). Owner's ask: buildings on the 3D surface map, which needs this object LOD.

- **The common 20-byte `.lod` (861 of 864 files) is three i32 values (verified bytes; their meaning is a
  supported hypothesis):** the minimum cell x, the minimum cell y, and a size in cells, then 8 zero bytes.
  `lc172world` and `landingoverlay01` are `-2, -2, 8`; `cydoniacity` is `-6, -6, 16`; `newatlantis` is
  `-35, -59, 136`. The one 16-byte and two 22-byte files were not read, so their layout is **unresolved**; a writer
  of ours follows the 20-byte form only. Ours would name the Commonwealth overlay's own cell range.
- **Two kinds of LOD mesh.** 12,627 are per object (`meshes/lod/generated/<mesh path>_lod_<0-3>.nif`, keyed by the
  full mesh's name, so they serve any world that places that mesh). 6,913 are per world, under
  `meshes/lod/generated/composite/<world>/` for 242 worlds (for example `packin` 844, `newatlantis` 662,
  `cydoniacity` 530), named `<name>_lod_<x>_<y>_lod_<level>_cell<k>.nif`.
- **The NIFs are small wrappers.** A composite NIF is 769 bytes: `NiNode`, `BSGeometry` and
  `BSLightingShaderProperty` naming a generated material
  (`Materials\LOD\Generated\Composite\CydoniaCity\...mat`) and a geometry hash. The vertices live in a separate
  `.mesh` file, as for the full meshes our converter already writes. A per-object NIF keeps the source mesh's own
  materials.
- **`distantlod/lodruntimedb.bgsdb`** is 559,956 bytes and opens with the counts 8 and 4,387 (0x1123), then records
  that carry hashes and the text `nif`. Whether it is one global database that our LOD must be merged into, or
  whether a world can do without an entry, is **unresolved**.

So a generator, whether the Creation Kit or ours, writes three things: a `.lod` for the overlay, per-object and
composite LOD NIFs with their `.mesh` and `.mat`, and possibly entries in `lodruntimedb.bgsdb`. The Creation Kit
spike above stays the first step: it shows what the CK writes for a world of ours, and that output is the
reference for our own generator.

## The Creation Kit can do it from the command line (Claude-cloud, 2026-10-22, read-only)

Strings in the owner's `CreationKit.exe` (239,885,664 bytes) show these command-line operations (**verified** as
strings; their behaviour is **unresolved** until a run):

- `-MockWorldSpaceLOD:<ESMFilename> <WorldSpaceName0> [WorldSpaceName1] [...]`. "Mock" may mean placeholder LOD;
  the run shows what it writes.
- `-GenerateMeshLODAssociations:<ESMFilename> [AdditionalPlugin]`, plus `-GenerateMeshLODStats` and
  `-GenerateMeshLODFailureReport` (both `<ESMFilename> <DestinationFileName> [AdditionalPlugin]`).
- The output paths named in the program are `Data\LODSettings\%s.LOD`, `Meshes\LOD\Generated\%s.nif`,
  `LOD\Generated\Composite\`, `Materials\LOD\Generated`, `Data\Textures\LOD\Generated\Merged\...`, and an
  `LODRuntimeDB` (`.bgsdb`).
- The window also has a "Generate LOD" command.

So the spike needs no clicking if these work. Its plan:
1. A vanilla oracle first: `CreationKit.exe -MockWorldSpaceLOD:Starfield.esm LC172World`, then compare its output
   with the shipped `lodsettings/lc172world.lod` and the LC172 meshes. The CK writes loose files into the game's
   `Data`, and a name listing cannot tell a new file from one it overwrote (a file left by an interrupted run, or
   another loose-file mod's), so before the run copy every loose file under the output paths above
   (`LODSettings`, `Meshes\LOD\Generated`, `Materials\LOD\Generated`, `Textures\LOD\Generated`, `distantlod`)
   to the staging folder (and `Meshes\Terrain\<World>\Objects`, where the oracle run put its NIFs; see below) and
   record a sha256 listing of all of `Data`'s loose files; after the run, move every
   new file to staging, restore every changed file from the copy, and check the listing matches again. Only then
   is `Data` as it was. This install reads no loose files, so nothing reaches the game meanwhile.
2. The tiny custom-world gate from the plan above, with the same backup: the same command on a plugin of ours
   with one new worldspace of a few cells and a handful of large converted STATs (an experiment core cut to a few
   cells, as the `make_exp2*` plugins are). A vanilla world proves nothing about a new plugin's world, and a
   failure on the full core would not tell custom-world support from scale.
3. Only on a pass there, the same command on our core (`FO4TerrainCore.esm`, world `FO4Core_Commonwealth`). It
   has 648k references, so it is timed, run at Idle, and needs disk room.
4. If it works, the generated files go into a ba2 beside the core, with their own installer, as for the map
   markers.

## What the runs showed (Claude-cloud, 2026-10-22; Install ran them on the PC, read-only, Data restored)

1. **Oracle (verified).** `CreationKit.exe -MockWorldSpaceLOD:Starfield.esm LC172World` exits 0 after 130 s with
   no window. It writes placeholders only: a zeroed 20-byte `LODSettings\LC172World.LOD` and four 10,843-byte
   `Meshes\Terrain\LC172World\Objects\LC172World.{1,2,4,8}.0.0.nif`, real NIFs whose `BSWeakReferenceNode`
   names the full meshes with their transforms. That is the FO4-style per-block layout
   (`<World>.<level>.<x>.<y>.nif`), not the shipped per-mesh `meshes/lod/generated/<mesh>_lod_<n>.nif` form; which
   of the two a custom world is read from is **unresolved**. A mock run shows only what the CK writes; which
   layout the game reads is answered in game only, by staging the output and looking at the surface map (the
   tiny-overlay check in `surface-map.md`).
   Output under `D:\Modding\staging\lod_spike_lc172\out`.
2. **Stats (verified).** `-GenerateMeshLODStats:Starfield.esm stats.csv FO4TerrainCore.esm` (the destination must
   end in `.csv`; the trailing argument loads our plugin) exits 0 after 194 s and writes only `stats.csv`: 3,187
   rows (Name, Template, Form Type, triangle counts, LOD1-3 ratios and sizes), every one a vanilla mesh and none
   of ours. The Template column (Reduction 1,577, Rock 888, Tree 668, Treehorizontal 37, Signage 2, Nozfighting 1)
   is the per-base-record setting the generator reduces by; it lives in the base record's `BGSLodOwner_Component`
   (Mutagen `LodOwnerComponent`, a raw REFL blob), which our STATs do not carry (`new Static { EditorID, Model }`).
   Warnings: "LOD Owner [] is not a TESObject" and a missing
   `Data\LODSimplygonGenerationSettings\GenerationConfig.json`.
3. **No generator found on the PC (verified as a search).** No Simplygon library and no `GenerationConfig.json`
   in the game folder, `ContentResources.zip` or `Reference_Files.zip`. The stats run names the config as missing
   and the Template column as the generator's input.

Supported hypothesis (**unresolved**): the Creation Kit here cannot generate per-object LOD meshes. No generation
was attempted; the window's "Generate LOD" command, or `-GenerateMeshLODAssociations` on a plugin whose STATs
carry a LOD owner template, would establish it (or refute it). Until then the plan assumes it, because the other
route needs no generator: buildings on the surface map for our statics mean converting FO4's own LOD meshes (the
STAT `MNAM` distant models under FO4 `Data\Meshes\LOD\`) into Starfield's layout, with the plain-shader NIF
conversion the Red Rocket crash forced (#460). That is a later phase; Grok is scoping the path mapping
(`fo4-lod-mesh-scoping.md`).

4. **Mock run on our core (verified, 2026-10-22 19:35Z).** `-MockWorldSpaceLOD:FO4TerrainCore.esm
   FO4Core_Commonwealth` (worldspace names only, no plugin fallback: the command has no trailing plugin argument,
   unlike the stats command) exits 0 after 192 s and writes nothing: 732 loose files before, 0 new, 0 changed,
   0 missing (listings in `D:\Modding\staging\lod_mock_cw`, log `lod_mock_cw.log`). `EditorDataFilesLoaded`
   lists 000 Starfield.esm and 001 FO4TerrainCore.esm, so the plugin loaded; `EditorWarnings` says
   `LODGENERATION: Failed to find worldspace: [FO4Core_Commonwealth]` (and an unrelated
   `PARTICLE_ENGINE: Failed to find VFX LOD curve preset for ID: 1`). The WRLD's EDID is `FO4Core_Commonwealth`
   (BorderProbe reads it; 02000803 at run time, local 000803). The backup copy set for this and every later run
   includes `Meshes\Terrain\<World>\Objects`, where the oracle put its NIFs.

Why the CK did not find our world is **unresolved**; the candidates, cheapest first, each one run of about three
minutes with the backup protocol: (A) `-MockWorldSpaceLOD:FO4TerrainCore.esm LC172World`: if the vanilla world
is found with our plugin named, the lookup is global and the fault is in our record or name, not the load; (B)
a zeroed 20-byte `LODSettings\FO4Core_Commonwealth.LOD` placed first (a copy of the oracle's zeroed output,
renamed, removed after the run): if the warning goes away, the LOD generator finds worldspaces through their
`lodsettings` files, not the form table; (C) the form ID in place of the name (`01000803`, then `000803`), in
case the lookup takes IDs. A pass on any of them is generation evidence only: it revives the placeholder route up to the in-game
check (stage the output and look at the surface map; if the game draws the weak-reference placeholders for our
world, the map gets buildings without any LOD mesh; installing those loose files waits for the owner's line). A
fail on all three sends the question to the tiny custom-world gate from the
plan above, which tells custom-world support from anything about the core, before the route is closed.

5. **Lookup runs A, B, C (verified, 2026-10-22 20:51Z-20:58Z; outputs `D:\Modding\staging\lod_mock_cw2\A`, `B`,
   `C`, `C2`).** All three fail for our world. (A) `-MockWorldSpaceLOD:FO4TerrainCore.esm LC172World` exits 0
   after 201 s with `LODGENERATION: Successfully baked worldspace: [LC172World]` and the oracle's five
   placeholder files (`EditorDataFilesLoaded` 000 Starfield.esm, 001 FO4TerrainCore.esm): the lookup is global
   and the plugin named in the argument does not scope it. (B) with a zeroed
   `LODSettings\FO4Core_Commonwealth.LOD` placed first: exit 0 after 197 s, still
   `Failed to find worldspace: [FO4Core_Commonwealth]`, nothing else written: that one zero-filled file did not
   make the world found (whether a valid settings file is consulted at all stays **unresolved**). (C)
   `01000803`, then `000803`, in place of the name: exit 0 after 199 s and 198 s,
   `Failed to find worldspace: [01000803]` / `[000803]`, nothing written: neither of those two spellings
   resolved it (other spellings, `0x...`, decimal or a plugin-qualified form, were not tried, so whether the
   argument can take an ID stays **unresolved**). Only vanilla LC172World bakes; the question goes to the tiny
   custom-world gate.

6. **Tiny custom-world gate (built; run, results in 7).** `dotnet/LodGate build <Starfield.esm> <FO4TerrainCore.esm>
   <out>` writes three plugins, each one new world of nine empty cells around the origin plus three references
   to the three vanilla statics with the widest object bounds (so a bake has objects to write placeholders for;
   the build prints which): `FO4SFLodGate1.esm` (world `FO4SF_LodGate1`, the WRLD record copied from vanilla
   LC172World, the writer's own template, master-flagged like the core, master Starfield.esm);
   `noflag\FO4SFLodGate1.esm` (gate 2: the very same plugin bytes with the Master header flag cleared, same file
   name, world and references, so the flag is the only difference); `FO4SFLodGate3.esm` (world `FO4SF_LodGate3`,
   the WRLD record copied from our core's `FO4Core_Commonwealth`, its location and surface-block links kept,
   masters Starfield.esm and the core). `LodGate show <plugin> <Starfield.esm> [<core>]` reads one back
   (`tests/test_lod_gate.py` covers the three on a synthetic fixture). The run: the plugin copied into `Data`
   for the run and removed after, `CreationKit.exe -MockWorldSpaceLOD:FO4SFLodGate1.esm FO4SF_LodGate1`, the
   backup protocol of run 4, and the log's `EditorDataFilesLoaded` read first: a gate plugin missing from it
   makes that run inconclusive (then it goes into Plugins.txt as the probe builds do, and the run repeats once).
   Reading (hypotheses about these three pinned gates, not proofs: none of them is a plugin-added world known
   to bake, and each changes the template's EditorID and name, replaces both cell trees and drops OFST / CLSZ,
   so a failed gate can also mean a loading or registration prerequisite the gate misses, or a defect in this
   synthetic layout): 1 bakes and 3 does not → the candidates narrow to the fields the two WRLD records differ
   in (diff them next); 1 and 3 bake → the core's own world still differs from gate 3 in its scale and cell
   tree (648k references), but also in its identity (plugin, FormKey, EditorID and name), its dropped OFST /
   CLSZ and its freshly made persistent cell, and each of those stays a candidate; 1 does not bake → the generator did not find this plugin world, and 2 then says whether the
   Master flag alone changes that (gate 2 is run from its own folder under the same file name); nothing bakes → the route stays **unproved**, not closed: a claim that
   custom worlds are unsupported needs a positive control first (a plugin-added world the CK itself made and is
   known to bake) or a narrower follow-up, and meanwhile the surface map's buildings wait on the FO4 LOD mesh
   conversion.

7. **Gate runs G1, G2, G3 (verified, 2026-10-22, Creation Kit log times 16:29-16:34 local, 22:29Z-22:34Z; Install
   ran them on the PC with the backup protocol of run 4; outputs `D:\Modding\staging\lod_gate\G1`, `G2`,
   `G3`).** The three plugins were built on the PC at ceeb558 (statics picked by the widest object bounds:
   `12DFE0:Starfield.esm` HoudiniPlanet_ring, extent 4972; `1C419E` HoudiniPlanet_atmo and `1C41A1`
   HoudiniPlanet_atmo_decal, 1992 each; `FO4SFLodGate1.esm` 1,352 bytes, sha256 9c983ac4…;
   `noflag\FO4SFLodGate1.esm` 1,352 bytes, aa710133…; `FO4SFLodGate3.esm` 1,377 bytes, bd5c95e6…). Each run
   copied its plugin into `Data` after the before-listing and swept it out after; the final listings match the
   before-listings (732 files). **Nothing bakes.** G1: exit 0 after 111 s, `LODGENERATION: Failed to find
   worldspace: [FO4SF_LodGate1]`, `EditorDataFilesLoaded` 000 Starfield.esm, 001 FO4SFLodGate1.esm, nothing
   written. G2 (the noflag twin, from its own folder): exit 0 after 99 s, the same line and the same load list.
   G3: exit 0 after 189 s, `Failed to find worldspace: [FO4SF_LodGate3]`, loaded 000 Starfield.esm,
   001 FO4TerrainCore.esm, 002 FO4SFLodGate3.esm, nothing written. Every gate plugin was in
   `EditorDataFilesLoaded`, so no run was inconclusive and the Plugins.txt rerun was not needed. Where the
   evidence sits: the exit codes, durations, load lists and failure lines are Install's relay of the CK log; the
   three output folders hold the plugin copies (sizes and hash prefixes as above) and the before / after
   inventories (732 entries, identical before and final, the gate plugin the only extra entry while it was in
   `Data`; SHA-256 for 644 entries, size plus mtime for 88), not the CK log itself (Codex desktop's read-only
   check on #501 confirmed the copies and the inventories and could not re-check the log lines). Reading, per
   the key in 6: the command found none of the three plugin worlds, with or without the Master flag, with the
   vanilla record or the core's. The result does not differentiate. Gate 1 fails without the core's scale, cell
   tree or identity, so none of those is needed for a plugin world to be missed; but gate 1 and the core can be
   missed for different reasons (item 6 allows a loading or registration prerequisite the gate lacks, or a defect
   in its synthetic layout), so the core-only differences stay **unresolved** candidates for the core run's
   failure until a controlled variant changes an outcome. Gate 2 shows only that the Master flag alone does not
   change gate 1's outcome. The route stays **unproved**, not closed. The candidates every failed world shares
   (being a plugin-added world at all, the dropped OFST / CLSZ, the freshly made persistent cell, and anything
   the CK registers at save time for a world it made itself) need a positive control first: a world made and
   saved in the CK, then the same command on it. A CK-made world changes those candidates together, so on its
   own it separates none of them: if it bakes, it is the known-good custom world item 6 asks for, and
   one-variable variants between it and gate 1 (OFST / CLSZ kept or dropped, the CK's persistent cell or a fresh
   one, saved by the CK or written by Mutagen) are what then tell the causes apart; if it does not bake, there
   is still no plugin-added world known to bake and the question stays open. That control needs the owner at
   the CK (a new worldspace, the plugin saved, the mock run on it) and is parked as an optional item for a
   future session there, not asked for now: on what runs 1 and 3 showed, even a found world gets the placeholder files of run 1
   unless per-object generation turns out to be possible here (the **unresolved** hypothesis under item 3: no
   generation was attempted), so for now the surface map's buildings wait on the FO4 LOD mesh conversion
   (`fo4-lod-mesh-scoping.md`) either way.
