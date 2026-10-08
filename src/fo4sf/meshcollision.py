"""Transplant Fallout 4 mesh collision into a Starfield collision blob.

FO4 (Havok 2014 packfile) and Starfield (Havok 2019 tagfile) store hknpCompressedMeshShape data with the same
hkcdStaticMeshTree layout: a compressed AABB tree over sections, each section with its own small tree, quantised packed
vertices, shared vertices, primitives (triangle / quad vertex indices) and primitive data runs. So FO4's finished
collision mesh (authored for gameplay: stairs are ramps, walls are simplified) can be copied across; only the
container format and a few section fields differ:

    FO4 section  @76 (firstShared << 8 | numPacked)  @80 (firstPrimitive << 8 | count)  @84 (firstRun << 8 | count)
                 @88 numPacked  @89 numSharedIndices  @90 leafIndex u16  @92 page  @93 flags  @94 layerData
    SF section   @76 firstSharedVertexIndex  @80 firstPrimitiveIndex  @84 firstDataRunIndex  @88 numPackedVertices
                 @89 numPrimitives  @90 numDataRuns  @91 page  @92 leafIndex u16  @94 layerData  @95 flags

The Starfield side is rebuilt around a template tagfile taken from a vanilla Starfield static (read from the user's
install at conversion time, never shipped): its TYPE section, physics system, material and body are reused; the shape's
data arrays, sections and trees come from FO4. Starfield's optional SIMD tree is left out (hasSimdTree = false).
"""
import struct
from typing import Dict, List, Optional, Tuple

from . import hkpackfile, hktagfile

TEMPLATE_NIF = "meshes/architecture/city/akila/interiorkit/ak_int_wallmid03.nif"   # vanilla static with a mesh body

# FO4 hknpCompressedMeshShapeData (object-relative): mesh tree at +16
FO4_TREE = 16
FO4_ARRAYS = {"nodes": 16, "sections": 80, "primitives": 96, "sharedVerticesIndex": 112, "packedVertices": 128,
              "sharedVertices": 144, "primitiveDataRuns": 160}
ELEM_SIZE = {"nodes": 5, "sections": 96, "primitives": 4, "sharedVerticesIndex": 2, "packedVertices": 4,
             "sharedVertices": 8, "primitiveDataRuns": 4}
FO4_SECTION_NODES = 4                                 # per-section tree: Aabb4BytesCodec


class _Writer:
    """Items (objects / arrays) laid out into a tagfile DATA section; pointers are item numbers patched via PTCH."""

    def __init__(self):
        self.items: List[Tuple[int, int, bytearray, int]] = []     # (type, flags, payload, count)
        self.ptrs: List[Tuple[int, int, int, int]] = []           # (pointer type, item, offset in item, target item)

    def add(self, type_idx: int, flags: int, payload: bytes, count: int) -> int:
        self.items.append((type_idx, flags, bytearray(payload), count))
        return len(self.items)                                     # item numbers start at 1 (0 = null)

    def ptr(self, ptr_type: int, item: int, offset: int, target: Optional[int]):
        if target:
            self.ptrs.append((ptr_type, item, offset, target))

    def build(self, sdk: bytes, type_section: bytes) -> bytes:
        data, offsets = bytearray(), []
        for _, _, payload, _ in self.items:
            data += b"\0" * (-len(data) % 16)
            offsets.append(len(data))
            data += payload
        data += b"\0" * (-len(data) % 16)
        patches: Dict[int, List[int]] = {}
        for ptype, item, off, target in self.ptrs:
            at = offsets[item - 1] + off
            struct.pack_into("<Q", data, at, target)
            patches.setdefault(ptype, []).append(at)
        item_tab = bytearray(12)                                   # item 0: null
        for (ti, fl, _, cnt), off in zip(self.items, offsets):
            item_tab += struct.pack("<III", (fl << 24) | ti, off, cnt)
        ptch = bytearray()
        for ptype, offs in patches.items():
            ptch += struct.pack("<II", ptype, len(offs)) + struct.pack(f"<{len(offs)}I", *sorted(offs))

        def sec(tag, payload, leaf=True):
            return struct.pack(">I", ((1 if leaf else 0) << 30) | (len(payload) + 8)) + tag + payload
        indx = sec(b"ITEM", bytes(item_tab)) + sec(b"PTCH", bytes(ptch))
        body = sec(b"SDKV", sdk) + sec(b"DATA", bytes(data)) + type_section + sec(b"INDX", indx, leaf=False)
        return sec(b"TAG0", body, leaf=False)


def _type(tf: hktagfile.Tagfile, name: str) -> int:
    for t in tf.types:
        if tf.type_name(t.index) == name:
            return t.index
    raise hktagfile.TagfileError(f"template has no type {name}")


def _field(tf: hktagfile.Tagfile, type_idx: int, name: str) -> hktagfile.Field:
    return next(f for f in tf.all_fields(type_idx) if f.name == name)


def _fo4_mesh_body(p: hkpackfile.Packfile):
    """(data object offset, body position) of the first unrotated compressed-mesh body, or None."""
    from . import fo4collision as fc
    classes = dict(p.objects())
    sysobj = next(o for o, c in classes.items() if c == "hknpPhysicsSystemData")
    at, n = p.array(sysobj + fc.SYS_BODIES)
    for k in range(n):
        b = at + fc.BODY_SIZE * k
        shape = p.pointer(b)
        if classes.get(shape) != "hknpCompressedMeshShape":
            continue
        if any(abs(x) > 1e-4 for x in p.unpack("<3f", b + fc.BODY_ROT)):
            continue
        return p.pointer(shape + fc.CMS_DATA), p.unpack("<3f", b + fc.BODY_POS)
    return None


def _convert_section(fo4: bytes) -> bytearray:
    s = bytearray(96)
    s[16:72] = fo4[16:72]                                          # domain + codec parameters
    first_packed, shared_d, prim_d, run_d = struct.unpack_from("<4I", fo4, 72)
    struct.pack_into("<4I", s, 72, first_packed, shared_d >> 8, prim_d >> 8, run_d >> 8)
    s[88] = fo4[88]                                                # numPackedVertices
    s[89] = prim_d & 0xFF                                          # numPrimitives
    s[90] = run_d & 0xFF                                           # numDataRuns
    s[91] = fo4[92]                                                # page
    s[92:94] = fo4[90:92]                                          # leafIndex
    s[94] = fo4[94]                                                # layerData
    s[95] = fo4[93]                                                # flags
    return s


def transplant(fo4_blob: bytes, sf_template_blob: bytes) -> Optional[bytes]:
    """Starfield bhkPhysicsSystem blob holding FO4's compressed mesh collision, or None if the FO4 blob has no unrotated
    mesh body (convex-only collision is handled elsewhere). Body translations are not supported (returns None)."""
    p = hkpackfile.Packfile(fo4_blob)
    found = _fo4_mesh_body(p)
    if found is None:
        return None
    d, pos = found
    if any(abs(x) > 1e-5 for x in pos):
        return None
    tf = hktagfile.Tagfile(sf_template_blob)
    blob = tf.blob
    tmpl = {tf.type_name(it.type): it for it in tf.items[1:]}

    def tmpl_bytes(name):
        it = tmpl[name]
        return blob[tf.data_start + it.offset:tf.data_start + it.offset + tf.size_of(it.type) * it.count]

    T_PSD, T_BODY = _type(tf, "hknpPhysicsSystemData"), _type(tf, "hknpPhysicsSystemData::bodyCinfoWithAttachment")
    T_MAT, T_CMS = _type(tf, "hknpMaterial"), _type(tf, "hknpCompressedMeshShape")
    T_DATA = _type(tf, "hknpCompressedMeshShapeData")
    T_TREE = _type(tf, "hknpCompressedMeshShapeTree")
    T_SEC = _type(tf, "hkcdStaticMeshTree::Section")
    tree_off = _field(tf, T_DATA, "meshTree").offset

    def arr_types(owner, field):
        ft = _field(tf, owner, field).type                         # hkArray<E, ...>
        return ft, dict(tf.types[ft].params)["tT"]

    w = _Writer()
    i_psd = w.add(T_PSD, 0x10, tmpl_bytes("hknpPhysicsSystemData"), 1)
    i_mat = w.add(T_MAT, 0x20, tmpl_bytes("hknpMaterial"), tmpl["hknpMaterial"].count)
    i_body = w.add(T_BODY, 0x20, tmpl_bytes("hknpPhysicsSystemData::bodyCinfoWithAttachment"), 1)
    w.ptr(_field(tf, T_PSD, "materials").type, i_psd, _field(tf, T_PSD, "materials").offset, i_mat)
    w.ptr(_field(tf, T_PSD, "bodyCinfos").type, i_psd, _field(tf, T_PSD, "bodyCinfos").offset, i_body)

    # FO4 arrays
    fo4 = {}
    for name, off in FO4_ARRAYS.items():
        at, n = p.array(d + off)
        fo4[name] = (p.raw(at, ELEM_SIZE[name] * n) if n else b"", n)
    n_tris = sum(1 if q[2] == q[3] else 2 for q in struct.iter_unpack("<4B", fo4["primitives"][0]))

    cms = bytearray(tmpl_bytes("hknpCompressedMeshShape"))
    i_cms = w.add(T_CMS, 0x10, cms, 1)
    w.ptr(_field(tf, T_BODY, "shape").type, i_body, _field(tf, T_BODY, "shape").offset, i_cms)
    struct.pack_into("<ii", w.items[i_cms - 1][2], _field(tf, T_CMS, "numTriangles").offset, n_tris, 0)
    bits = _field(tf, T_CMS, "triangleIsInterior")
    nwords = (n_tris + 31) // 32
    words_ptr_type = _field(tf, bits.type, "storage").type
    words_arr_type = _field(tf, words_ptr_type, "words").type
    i_words = w.add(dict(tf.types[words_arr_type].params)["tT"], 0x20, bytes(4 * nwords), nwords)
    w.ptr(words_arr_type, i_cms, bits.offset + _field(tf, words_ptr_type, "words").offset, i_words)
    struct.pack_into("<i", w.items[i_cms - 1][2], bits.offset + _field(tf, words_ptr_type, "numBits").offset, n_tris)

    data = bytearray(tmpl_bytes("hknpCompressedMeshShapeData"))
    for f in ("nodes", "sections", "primitives", "sharedVerticesIndex", "packedVertices", "sharedVertices",
              "primitiveDataRuns"):
        struct.pack_into("<16x", data, tree_off + _field(tf, T_TREE, f).offset)       # cleared; set by patches
    data[tree_off + 16:tree_off + 48] = p.raw(d + FO4_TREE + 16, 32)                   # domain
    data[tree_off + 48:tree_off + 64] = p.raw(d + FO4_TREE + 48, 16)                   # keys, bits, max key, flat
    simd = _field(tf, T_DATA, "simdTree")
    data[simd.offset:simd.offset + tf.size_of(simd.type)] = bytes(tf.size_of(simd.type))
    conn = _field(tf, T_DATA, "connectivity")
    data[conn.offset:conn.offset + tf.size_of(conn.type)] = bytes(tf.size_of(conn.type))
    data[_field(tf, T_DATA, "hasSimdTree").offset] = 0
    i_data = w.add(T_DATA, 0x10, data, 1)
    w.ptr(_field(tf, T_CMS, "data").type, i_cms, _field(tf, T_CMS, "data").offset, i_data)

    for name in ("nodes", "primitives", "sharedVerticesIndex", "packedVertices", "sharedVertices",
                 "primitiveDataRuns"):
        raw, n = fo4[name]
        if not n:
            continue
        arr_t, elem_t = arr_types(T_TREE, name)
        i = w.add(elem_t, 0x20, raw, n)
        w.ptr(arr_t, i_data, tree_off + _field(tf, T_TREE, name).offset, i)

    sec_raw, nsec = fo4["sections"]
    sec_arr_t, sec_elem_t = arr_types(T_TREE, "sections")
    sections = bytearray()
    for k in range(nsec):
        sections += _convert_section(sec_raw[96 * k:96 * k + 96])
    i_secs = w.add(sec_elem_t, 0x20, sections, nsec)
    w.ptr(sec_arr_t, i_data, tree_off + _field(tf, T_TREE, "sections").offset, i_secs)
    sec_at, _ = p.array(d + FO4_ARRAYS["sections"])
    node_arr_t, node_elem_t = arr_types(T_SEC, "nodes")
    for k in range(nsec):
        at, n = p.array(sec_at + 96 * k)
        if n:
            i = w.add(node_elem_t, 0x20, p.raw(at, FO4_SECTION_NODES * n), n)
            w.ptr(node_arr_t, i_secs, 96 * k + _field(tf, T_SEC, "nodes").offset, i)

    type_sec = next((blob[s - 8:e] for tag, s, e in hktagfile.sections(blob, 8, len(blob)) if tag == "TYPE"))
    sdk = next((blob[s:e] for tag, s, e in hktagfile.sections(blob, 8, len(blob)) if tag == "SDKV"))
    return w.build(sdk, type_sec)
