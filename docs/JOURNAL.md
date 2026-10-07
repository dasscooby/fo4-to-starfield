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
