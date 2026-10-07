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
