# Float/index layout audit — Codex, #457

Audit base: `4de970923b340852bb8ab11bb2f49b89fb46e89f`, 22 October 2026. **Offline only.**
This PR adds this document only. It changes neither the converter nor a scanner.

No normal conversion path was demonstrated here to write a float into an index field. Three narrower,
reproducible disagreements concern **layout selection**: the inline-mesh discriminator, old meshlet-cull
versions, and the NIF endian flag. Their normal generated profiles and their limits are distinguished below.
A raw `0.02` hit is not evidence of an index error.

## Correct the starting premise

The issue's original door-clamp lead has been superseded by later entries in
[the crash bisect](red-rocket-crash-bisect.md#v6i-result-2026-10-22).
That record reports the same crash after the clamped NIFs had zero `0x3ca3d70a` hits. Its later
[Card I result](red-rocket-crash-bisect.md#card-i-result-2026-10-22) reports both walks passing with the plain
Codsworth shader. The old shader's value being interpreted as a link remains a **supported hypothesis**,
not a demonstrated instruction-level diagnosis. Those are reported PC observations; this audit did not
repeat a game test or independently inspect those dumps.

`actor_rebind.rebind` already defaults to `plain_shader=True` (line 131). Its default shader writer is the
12-byte name/extra-count/controller form, not the copied 166-byte template shader. Do not replace every
occurrence of a valid float, or present the leaf-floor change as a proven crash fix.

## Evidence and classification

- **CONFIRMED** means an offline writer/reader or writer/schema disagreement was reproduced. It does not
  mean Starfield was run, that the ordinary converter reaches that case, or that it explains Red Rocket.
- **PLAUSIBLE** means a concrete unvalidated boundary or opaque-template dependency; no bad normal output
  was demonstrated. Malformed API arguments are identified rather than presented as corpus failures.
- **FINE** means the inspected generated layout/count construction agrees with the cited reader/profile.
  A reader and writer sharing an assumption do not independently prove engine compatibility.

Primary format comparison is pinned to fo76utils/NifSkope
[`380631a408c54f82bfbd70786c75e8bfa4945ecb`](https://github.com/fo76utils/nifskope/tree/380631a408c54f82bfbd70786c75e8bfa4945ecb):
the [`nif.xml` schema](https://github.com/fo76utils/nifskope/blob/380631a408c54f82bfbd70786c75e8bfa4945ecb/build/nif.xml)
and [`MeshFile.cpp`](https://github.com/fo76utils/nifskope/blob/380631a408c54f82bfbd70786c75e8bfa4945ecb/src/io/MeshFile.cpp).
The XML distinguishes the owner flag used for inline geometry, version-dependent cull records, and endian modes.
For Havok, local `hktagfile` TYPE/ITEM/PTCH decoding and `meshcheck` are the comparison, not an independently
reimplemented engine. No private template bytes are in this document.

## Reproduced layout-selection findings

| ID / source | What is written or selected | Expected layout / comparison | Verdict and reach | Proposed scan |
| --- | --- | --- | --- | --- |
| A — `sfnif.py:52–92`, especially 71 and 90 | The reader tests `MeshRef.flags & 512`; the writer always emits an external path. | XML `BSGeometry` passes **the owning AV-object flags** through its four mesh slots to choose external path versus inline mesh data. | **CONFIRMED, offline.** A constructed owner flag `0x200` with mesh flags `0x40` is written/read locally as external, disagreeing with the schema. Conversely, per-mesh `0x200` with an external owner is rejected by the local reader. Normal static/door builders use external-owner defaults and per-mesh `0x40`; no bad ordinary output was shown. | R1: use the owner flag to dispatch; refuse/report unsupported inline data rather than treating it as a path. |
| B — `sfmesh.py:175–195` (`meshlet_cull` / `build_meshlets`), `sfmesh.py:120–145` | New cull records are always six floats describing a box; `build_meshlets` does not gate on `m.version`. | XML `BSCullData` uses a different 24-byte interpretation below version 2: sphere, packed cone, apex; version 2 uses a box. | **CONFIRMED, offline, helper reach.** Calling the builder with version 1 produces bytes accepted by the local opaque reader, but the schema's sphere radius fails to enclose a synthetic meshlet. Version-2 control agrees. `shape_to_mesh` explicitly constructs version 2, so the normal static conversion is not implicated. Existing legacy raw cull bytes may be round-tripped without this rebuild. | R2: gate known-producer rebuilt culls by version; for legacy inputs validate sphere/cone/apex semantics, not six floats. |
| C — `nif.py:77–159`, especially 136 | `serialize` copies `n.endian` into the header but packs all subsequent numeric fields little-endian; `parse` likewise reads little-endian. | XML `EndianType`: flag 0 denotes big-endian, flag 1 little-endian. | **CONFIRMED, offline, unsupported-profile boundary.** `NifFile(endian=0, user_version=12)` advertises one byte order and writes another; the same local reader accepts it. Normal target constructors set 1. No current generated big-endian file was observed. | R3: supported-target endian gate before decoding counts or searching fields. |

All three are proposals for follow-up, **not fixes implemented by this audit**. A and B concern conditional
layouts, not proof that a literal `f` should simply be replaced with `i`.

Minimal independent reproduction, in Python from the audited checkout (memory-only, no game files):

```python
import math, struct, sys
sys.path.insert(0, "src")
from fo4sf import nif, sfmesh, sfnif
g = sfnif.BSGeometry(flags=0x200, meshes=[sfnif.MeshRef(3, 3, 0x40, b"aa\\bb"), None, None, None])
assert sfnif.parse_bsgeometry(sfnif.build_bsgeometry(g)).meshes[0].path == b"aa\\bb"  # A: XML selects inline
m = sfmesh.SfMesh(version=1, positions=[(32767, 0, 0), (0, 32767, 0), (0, 0, 32767)], triangles=[(0, 1, 2)])
sfmesh.build_meshlets(m)
x, y, z, radius = struct.unpack_from("<4f", sfmesh.parse(sfmesh.serialize(m)).cull_data[0])
assert max(math.dist((x, y, z), sfmesh.decode_position(p, m.scale)) for p in m.positions) > radius  # B
b = nif.serialize(nif.NifFile(endian=0, user_version=12))
p = len(nif.MAGIC) + 5
assert struct.unpack_from("<I", b, p)[0] == 12 != struct.unpack_from(">I", b, p)[0]  # C
```

## Writer inventory and field/count review

Locations below refer to the pinned audit base. Related writes with the same field layout share a row; the
call-site index afterwards lists each packing site in the core writers. All verdicts in this table are offline.

| Source / sites | Written values and separately computed counts | Reader/profile expectation | Verdict / reason / scan |
| --- | --- | --- | --- |
| `convert_static.py:68–100` | Unit-scaled positions; quantized coordinates; UV half-floats; packed normals with `w=1/3`, tangent signs 0/1; version 2. | `sfmesh` separates scale `f`, position `hhh`, UV `HH`, packed normal/tangent `I`. | **FINE** for field types; these are real floats/packed directions, not block refs. Current main also rejects empty/nonfinite transformed positions before quantization (merged #385). R4/R8. |
| `convert_static.py:434,656`; `sfcollision.py:37–64` | Leaf half-size floor `0.05`; general box floor `0.005`; 36 linear combinations at fixed box-template offsets. | `LINEAR` / `read_box` profile in collision tests: half-size, centre, corners and plane coefficients are floats. | **FINE** for the recognized box profile; **PLAUSIBLE** on template drift or nonfinite centres. `check_template` checks size/signature/class/rotation, not every TYPE field. A synthetic signature-only buffer accepts a NaN centre; that buffer is not evidence of a valid Havok file. R5/R8. |
| `sfcollision.py:68,346`; `meshcollision.py:482,690–734` | Surface thickness/tolerances, helper-slope adjustment, flat-hull half-thickness `0.005`, recomputed float vertices/planes. | Result feeds typed box/hull float fields; tolerances choose geometry and are not serialized counts. | **FINE** type separation; changed geometry can contain small valid floats. Coverage and physical fidelity need their separate oracles. R5/R8. |
| `sfmesh.py:120–142` | Triangle/LOD index counts `3*len(tris)`; `HHH` indices; `fI` scale/weight count; length-prefixed position/UV/colour/normal/tangent/skin arrays. | `sfmesh.parse:87–116`; primary `BSMeshData` / `BSBoneWeight`. | **FINE** type/order/count derivation on supported objects. **PLAUSIBLE** API validation gap: a deliberately out-of-range vertex index survives serialize/parse; the ordinary meshlet builder dereferences positions and can refuse it. R4. |
| `sfmesh.py:143–145` | Cull count is `len(m.cull_data)`, but each entry is untyped raw bytes; opaque tail follows it. | Reader consumes 24 bytes per cull record; meaning is version-dependent (B). | **PLAUSIBLE** malformed-object boundary: a 20-byte entry is emitted and then rejected by the local reader. Normal `meshlet_cull` emits 24. Require stride/count and full consumption; do not call this a demonstrated generated-file defect. R2/R4. |
| `sfmesh.py:175–195,204–231` | Cull bounds; fallback scale 1; coordinate clamp to ±32767; packed-direction clamps; `e`/`H` bit conversion for UVs. | Float scale/bounds and integer/half payloads occupy different declared fields. | **FINE** bit conversion, with B's version caveat. NaN/Inf and invalid scale need typed-field checks, not a universal byte-pattern ban. R2/R4/R8. |
| `sfnif.py:52–92` | Extra refs `i`, count `I`, translation `3f`, rotation `9f`, scale/ref `fi`, sphere `4f`, box `6f`, skin/shader/alpha `3i`; four mesh slots in normal callers. | Local `parse_bsgeometry`, plus primary BSGeometry schema. | **FINE** generated fixed-field ordering; A is the discriminator exception. **PLAUSIBLE** arity guard gap: passing only three slots emits a block the reader cannot finish. Normal constructors pass four. R1/R6. |
| `sfnif.py:115–162` | Static node identity `3f9ff`; `-1` reference sentinels; per-shape block bases `first+3*i`; extra collisions start after shapes; blob length `I`; collision attachment `iHiI`; footer `(1,0)`. | `nif` AV/node readers, `door_collision.plan`'s 14-byte attachment and exact blob-length checks, primary collision-object/ByteArray schema. | **FINE** generated counts and mixed float/integer ordering; child-list lengths come from the emitted lists. Opaque collision contents remain a separate profile. R5/R6. |
| `sfnif.py:180–275` | Door identities/hinge transforms, pending node children/extras, shape triplets, attach nodes and per-body blob wrappers. | Same node/geometry layouts; frame transform arity/finite/orthonormal checks at 197–212. | **FINE** counts are packed from the final pending lists. Per-node physics-system ownership is a separate native/door-bridge gate, not a demonstrated float/index mismatch. R5/R6. |
| `door_model.py:26–64` | Bone/attachment transforms, quaternion-derived matrices, unit scale, per-shape blocks, node child/extra counts, 14-byte collision refs, blob sizes. | `sfnif` node/geometry conventions; `native_door.prepare` / attachment coverage checks. | **FINE** generated field separation. The caller still owns native collision profile/body semantics. R5/R6. |
| `actor_rebind.py:39–78` | Child lists `I + n*i`; skin instance `iiI + n*i` and retained tail; per-bone sphere `4f` in 68-byte records. | `_raw_children`, `read_instance`, `fo4skin.BONE_ENTRY=68`; size checked before sphere patches. | **FINE** float sphere versus bone/ref integer separation. Retained opaque tail/version compatibility is **PLAUSIBLE**, not independently established by preserving byte length. R6/R7. |
| `actor_rebind.py:183–216` | Mesh count/vertex count from emitted mesh; new skin/data/shader links; MaterialID `I`; default 12-byte shader `iIi`, optional name-only patch into copied shader. | Local geometry/skin readers; `test_actor_rebind` verifies plain and retained-template modes. | **FINE** default field types. **PLAUSIBLE**, high diagnostic priority: optional copied-shader mode retains template-specific fields/references that the simple name patch cannot validate; the recorded crash bisect specifically points here. No independent full shader decoder was used. R6/R7/R8. |
| `nif.py:134–159` | Header block/type/string/group counts; type indices `H`; block sizes `I`; string lengths; opaque footer. | `nif.parse:77–129`. | **FINE** counts normally follow `add_block` / `string_index`; C is an endian exception. **PLAUSIBLE** malformed-object boundary: a type index outside the type table survives parsing until dereference; footer refs and `max_string_len` are not fully validated here. R3/R6. |
| `meshcollision.py:42–77` | `_Writer.add` accepts payload/count separately; 16-byte-aligned DATA; pointer item numbers `Q`; ITEM `(type/flags,offset,count)` as `III`; PTCH lengths/offsets `I`; big-endian section size/flag word. | `hktagfile.sections`, ITEM/PTCH readers at 156–172; actual TYPE supplies element size. | **FINE** declared container types; **PLAUSIBLE** missing central cross-check that `count*TYPE.size` and each patch/ref fit the intended item. Alignment padding is not proof of an element being present. R5. |
| `meshcollision.py:125–135` | 96-byte section mapping: four `I` offsets; byte-sized primitive/run counts; u16 leaf index; copied float domain. | Documented FO4→SF section map at file start and `meshcheck.mesh_records`. | **FINE** explicit field reorder; floats remain in domain/codec area, not count bytes. R5. |
| `meshcollision.py:183–215,896–960` | Mesh key bits/interior-word counts; zeroed pointer/array fields; copied domain/key data; primitive sanitization; per-section float translation at +48. | TYPE fields, `_mesh_fixes`, `meshcheck` section/key/primitive decoder. | **FINE** in the supported profile; **PLAUSIBLE** copied-profile drift and independently supplied array sizes. Scan the declared section and shared-vertex/index ranges, not all words as floats. R5. |
| `meshcollision.py:251–316` | SIMD node: 24 floats, four `I` keys/child indices, two flag bytes and padding, exactly 128 bytes. Unused lanes use ±`FLT_MAX` and null/sentinel data. | `meshcheck.walk_simd_tree`; local `SimdTreeTests`. | **FINE** typed split and fixed stride. ±large finite values are intentional in empty lanes; blanket magnitude/NaN rules must account for sentinel lanes. R5/R8. |
| `meshcollision.py:535–547,666–685,720–820` | Sphere radius/centre; hull `3f` vertices and `4f` planes; face `HBB` offsets/counts; u8 vertex indices; separate nv/nf/nidx, links and vertex-edge counts; cleared `Q` pointers. | TYPE-derived hull fields, `_hull_links`, `_faces_raw`, source decoder. | **FINE** inspected packing/count construction; **PLAUSIBLE** template stride/type drift and unsupported nonfinite geometry. Rebuilt hull updates nv/nf; face/index/plane counts must still be checked against emitted payloads. R5. |
| `meshcollision.py:823–827,1097–1104,1272–1279` | Shifted AABB `8f`; zero body position `4f`; identity orientation `4f`; material `H` and filter `I`. | Named TYPE offsets; source body-transform decoding. | **FINE** float transforms separate from IDs/filter words. Copies outside these patched fields retain template dependencies. R5/R7. |
| `meshcollision.py:1174–1201` | Compound key/count words and null pointers; AABB float4s with w=0; radius; identity instance quaternion/translation/scale; child refs and SIMD count. | TYPE dotted fields; explicit SIMD-node size=128 guard. | **FINE** n comes from emitted children/instances. **PLAUSIBLE** wider TYPE layout changes: resolving an offset does not itself verify the hard-coded packed width. R5. |
| `meshcollision.py:997–1009,1299–1321` | Positive finite mass, float32 representability check; flags use 4-byte width or otherwise 2; motion/material IDs integer; COM/volume, axis quaternion and inertia/pad as float4s. | `require_serialized_mass`, named TYPE fields; local mass-distribution tests. | **FINE** mass guard and typed separation. **PLAUSIBLE** flags-type variant outside the expected 2/4 bytes, or unsupported mass-distribution profile; no normal malformed body demonstrated. R5. |
| `navmesh.py:54–64,173–198,329–355` | Structured little-endian vertex/triangle/link/door records; float height/positions beside signed i16 indices; counts per array, cover-byte count, grid float8, grid-list i16s and outline bounds. | Module NVNM/NVMI layouts, `parse` / `parse_nvmi`; divisor² list guard. | **FINE** inspected schema/type separation for navigation records, with raw cover/traversal/profile lengths to validate. These are plugin records, not NIF block refs; route to their validator rather than a NIF byte scanner. |

### Core packing-site index

This index accounts for all direct `struct.pack` / `pack_into` sites in the audited NIF, external-mesh,
collision and actor-rebind writers, including nested builders. Read-only `unpack`, reader `array()` calls,
`struct.Struct` decoders and numerical tolerances are not extra binary writers.

- `nif.py`: 136, 139, 147, 149, 150, 151, 152, 154, 155.
- `sfnif.py`: 81, 82, 83, 84, 85, 90, 91, 128, 134, 135, 138, 140, 141, 148, 150, 155, 157, 158, 159, 160,
  161, 216, 222, 225, 226, 229, 234, 235, 236, 243, 244, 249, 274.
- `sfmesh.py`: 122, 123, 124, 127, 128, 138, 140, 143, 180, 227, 231.
- `sfcollision.py`: 64.
- `door_model.py`: 30, 33, 34, 38, 57, 58, 61, 62, 63.
- `actor_rebind.py`: 50, 69, 78, 207, 209, 212.
- `meshcollision.py`: 63, 67, 70, 73, 128, 189, 198, 203, 291, 314, 547, 677, 678, 681, 684, 734, 761, 799,
  800, 803, 805, 807, 827, 907, 909, 915, 917, 918, 927, 957, 1005, 1101, 1102, 1103, 1104, 1174, 1189, 1190,
  1191, 1192, 1276, 1277, 1278, 1279, 1305, 1306, 1307, 1316, 1317, 1318.
  For `meshcollision.py`, the dynamic `put` wrapper's individual field calls at 1175–1183 are included in the table. Read-only `hkpackfile`, `fo4collision`, `fo4_compounds`, `door_collision`, `meshcheck` and `ragdoll_pose` are companion readers/planners, not omitted target writers.

The search also encountered `navmesh`'s plugin payloads and other output formats. `textures.py:104–108`,
`ba2.py:42–45` and `overlay.py` generate DDS headers/planes; `btd.py` / `terrain_grid.py` / `fo4land.py`
handle terrain grids; `exterior.py` / `map_markers.py` / `overlay_grid.py` serialize record data or hashes;
launcher manifests encode identity metadata. They do not emit NIF block references. Their integer counts,
float planes or hashes must not be treated as NIF refs by extending a raw needle rule. This is not a complete
terrain/plugin-format audit, a terrain-size approval, or a claim that every converter output format is validated.

## Proposed scanner rules — not implemented

Scanner references in the issue are historical: `scripts/research/nif_float_scan.py` is absent at
the audit base. The current contents of PR #453 are crash research/minidump analysis. The available
[`scripts/game/value_scan.py`](../../scripts/game/value_scan.py) reports raw-byte hits and plugin-record
locations; it does not establish these typed invariants. The rules below are proposals for the scanner
follow-up, not claims about #453's implementation.

| Rule | Search / range / invariant | Coverage and limitations |
| --- | --- | --- |
| R1 — geometry profile | Select inline/external mesh layout from **owner** flags `&0x200`; exactly four slot flags; check the selected payload's size/encoding. | Catches A's known-producer incompatible external-path output. Do not inspect per-mesh flags for the layout switch. Unsupported inline profiles must report unknown/refused, not be parsed with the external layout. |
| R2 — mesh version/cull layout | For known outputs of this box-cull builder, require version 2. For legacy versions use their sphere/cone/apex schema; check positive finite radius and enclosure of referenced meshlet vertices. | Detects B and the reproduced under-enclosing legacy sphere. An arbitrary 24-byte record cannot always reveal which writer produced it; unknown provenance must stay inconclusive. |
| R3 — byte order | Check NIF header endian flag before any following scalar/count: supported target mode is 1; other modes need their own decoder or explicit refusal. | Catches C without reinterpreting wrong-endian counts as allocations. A same-reader round trip is insufficient. |
| R4 — external mesh | Bound each declared count by remaining bytes/stride **before** allocation; triangle/LOD count divisible by 3; every vertex index `< n_positions`; cross-check attribute/skin counts; finite positive scale; finite decoded float/half fields; meshlet ranges; 24-byte cull stride with R2 semantics. | Catches the malformed stride/index probes and structural displacement that could make a later scale word look like a count. Inspect fields, not every packed colour or normal as f32. |
| R5 — Havok | Validate section sizes, ITEM type/offset/count extents against TYPE sizes, PTCH patch locations/target items, array/rel-array strides, section primitive/run/shared-index ranges, hull face offsets/indices, body IDs and SIMD child/leaf ranges. Recognize the exact box profile before using fixed offsets. | Addresses independent counts/template assumptions above. Mask section flag bits; a whole-file float search cannot validate tagged pointers. Permit documented SIMD empty-lane sentinels. |
| R6 — NIF graph | Bound block type indices, string indices, extra/controller/collision/skin/shader/alpha refs and child/footer-root refs by their own tables; accept `-1` only for nullable refs; check blob length exactly, node/geometry consumption and semantic ref type. | A float-like value such as `0x3ca3d70a` in an **actual index field** will normally fail a range/type check regardless of which float produced it. Reject any out-of-range index, not just known needles. |
| R7 — copied blocks | Report type, version, block size and provenance of opaque shader/skin/physics payloads; use a version-specific decoder or known-profile comparison before accepting inherited references. | Prioritize actor template mode. A matching hash/byte count proves identity, not compatibility with the surrounding model. Unknown layouts remain inconclusive; do not rewrite unknown words as guessed refs. |
| R8 — diagnostic needles | Optional little-endian f32 patterns: `0x3ca3d70a` (`0.02`), `0x3d4ccccd` (`0.05`), `0x3ba3d70a` (`0.005`), `0x3f800000` (`1`). Report file, block, offset, decoded field/type and producer profile. | These values are legal in many float fields. Never make “zero hits anywhere” a general correctness gate. Bounds/geometry and half-float or compressed streams can contain coincidental bytes. Scan `.mesh` companions as well as NIFs; raw results alone cannot assign an index interpretation. |

## Reproduction and limits

Private synthetic audit probes executed **12 cases**: normal external geometry carrying scale `0.02`;
both flag-selector counterexamples; legacy cull mismatch and version-2 control; wrong-endian header;
three-slot geometry and short-cull malformed inputs; out-of-range mesh/type indices; signature-only box
with NaN centre; and the four diagnostic bit encodings. The existing reader/writer suites also passed: 77 synthetic tests, zero skips. No probe read a game archive, built a private stage,
installed anything or called Starfield. The malformed-object examples are guard-gap illustrations, not
evidence that valid source content takes those paths.

The proposed acceptance gate is **complete, versioned structural decoding with provenance**, followed by
the separate native test campaign. An unreadable file, unsupported profile, absent companion or unknown
copied-block schema is inconclusive, not a pass. This audit neither rescored an old game result nor proved
any new engine crash cause.
