"""Synthetic builders for the collision bug hunt: a Havok 2014 packfile (what hkpackfile reads) and a Starfield
tagfile "universal template" with the types/fields meshcollision.convert_bodies and sfbodies need. Layouts follow the
offsets hard-coded in src/fo4sf/fo4collision.py and meshcollision.py; nothing here comes from game data."""
import struct


MAGIC = b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10"


# ---------------------------------------------------------------- FO4 packfile ---------------------------------------
class PackWriter:
    """Section 0 __classnames__, section 1 __data__ with local fixups (pointers) and virtual fixups (class names)."""

    def __init__(self):
        self.data = bytearray()
        self.local = []
        self.virtual = []
        self.names = {}
        self.namebuf = bytearray()

    def _name(self, cls):
        if cls not in self.names:
            self.names[cls] = len(self.namebuf)
            self.namebuf += cls.encode() + b"\0"
        return self.names[cls]

    def align(self, n=16):
        self.data += b"\0" * (-len(self.data) % n)

    def obj(self, cls, payload):
        self.align(16)
        off = len(self.data)
        self.data += payload
        if cls:
            self.virtual.append((off, cls))
        return off

    def raw(self, payload, align=16):
        self.align(align)
        off = len(self.data)
        self.data += payload
        return off

    def ptr(self, src, dst):
        self.local.append((src, dst))

    def hkarray(self, obj, field, data_off, count):
        struct.pack_into("<i", self.data, obj + field + 8, count)
        struct.pack_into("<I", self.data, obj + field + 12, count | 0x80000000)
        if count:
            self.ptr(obj + field, data_off)

    def relarray(self, obj, field, data_off, count):
        """hkRelArray: u16 count, u16 offset from the field."""
        struct.pack_into("<HH", self.data, obj + field, count, data_off - (obj + field))

    def build(self):
        for _, cls in self.virtual:
            self._name(cls)
        names = bytes(self.namebuf) + b"\0" * (-len(self.namebuf) % 16)
        self.align(16)
        data = bytes(self.data)
        loc = b"".join(struct.pack("<ii", a, b) for a, b in self.local)
        vir = b"".join(struct.pack("<iii", a, 0, self.names[c]) for a, c in self.virtual)
        hdr = bytearray(64)
        hdr[0:8] = MAGIC
        struct.pack_into("<i", hdr, 12, 11)
        hdr[16] = 8
        struct.pack_into("<i", hdr, 20, 2)
        hdr[40:56] = b"hk_2014.1.0-r1\0\0"
        s0_start = 64 + 64 * 2
        s0 = bytearray(64)
        s0[0:14] = b"__classnames__"
        n0 = len(names)
        struct.pack_into("<7i", s0, 20, s0_start, n0, n0, n0, n0, n0, n0)
        s1_start = s0_start + n0
        s1 = bytearray(64)
        s1[0:8] = b"__data__"
        l0 = len(data)
        g0 = l0 + len(loc)
        v0 = g0
        e0 = v0 + len(vir)
        struct.pack_into("<7i", s1, 20, s1_start, l0, g0, v0, e0, e0, e0)
        return bytes(hdr) + bytes(s0) + bytes(s1) + names + data + loc + vir


# FO4 object layouts (from fo4collision.py / meshcollision.py)
def fo4_system(w, bodies, motions=()):
    """hknpPhysicsSystemData with bodyCinfos @64 (96 bytes each) and motionCinfos @48 (112 bytes each).
    bodies: [(shape_off, pos, quat, filt, motion_index)]."""
    sysobj = w.obj("hknpPhysicsSystemData", bytes(96))
    body_raw = bytearray(96 * len(bodies))
    for k, (shape, pos, quat, filt, mi) in enumerate(bodies):
        b = 96 * k
        struct.pack_into("<I", body_raw, b + 12, mi)
        struct.pack_into("<I", body_raw, b + 20, filt)
        struct.pack_into("<4f", body_raw, b + 48, *pos, 0.0)
        struct.pack_into("<4f", body_raw, b + 64, *quat)
    at = w.raw(bytes(body_raw))
    for k, (shape, *_rest) in enumerate(bodies):
        w.ptr(at + 96 * k, shape)
    w.hkarray(sysobj, 64, at, len(bodies))
    if motions:
        m_raw = bytearray(112 * len(motions))
        for k, (pid, inv) in enumerate(motions):
            struct.pack_into("<H2xf", m_raw, 112 * k, pid, inv)
        mat = w.raw(bytes(m_raw))
        w.hkarray(sysobj, 48, mat, len(motions))
    return sysobj


def fo4_convex(w, verts, faces, radius=0.0, cls="hknpConvexPolytopeShape", planes=None):
    """hknpConvexPolytopeShape: radius @20, vertices relarray @48 (hkVector4), planes @64, faces @68, indices @72."""
    import math
    shape = w.obj(cls, bytes(80))
    struct.pack_into("<f", w.data, shape + 20, radius)
    va = w.raw(b"".join(struct.pack("<4f", *v, 0.0) for v in verts))
    w.relarray(shape, 48, va, len(verts))
    if faces:
        if planes is None:
            c = [sum(v[a] for v in verts) / len(verts) for a in range(3)]
            planes = []
            for f in faces:
                a, b, d = verts[f[0]], verts[f[1]], verts[f[2]]
                u = [b[i] - a[i] for i in range(3)]
                v = [d[i] - a[i] for i in range(3)]
                n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
                ln = math.sqrt(sum(x * x for x in n)) or 1.0
                n = [x / ln for x in n]
                if sum(n[i] * (c[i] - a[i]) for i in range(3)) > 0:
                    n = [-x for x in n]
                planes.append((*n, -sum(n[i] * a[i] for i in range(3))))
        pa = w.raw(b"".join(struct.pack("<4f", *pl) for pl in planes))
        w.relarray(shape, 64, pa, len(planes))
        fr, idx = b"", b""
        for f in faces:
            fr += struct.pack("<HBB", len(idx), len(f), 127)
            idx += bytes(f)
        fa = w.raw(fr, 4)
        w.relarray(shape, 68, fa, len(faces))
        ia = w.raw(idx, 4)
        w.relarray(shape, 72, ia, len(idx))
    return shape


def fo4_mesh(w, sections, prims, packed, shared_idx=(), shared=(), domain=((0, 0, 0), (1, 1, 1)), keys=(0, 8, 0)):
    """hknpCompressedMeshShape (data ptr @96) -> hknpCompressedMeshShapeData (tree @16: nodes @16, domain @32,
    keys @48, sections @80, primitives @96, sharedVerticesIndex @112, packedVertices @128, sharedVertices @144,
    primitiveDataRuns @160).
    sections: [dict(off, scale, first_packed, shared_start, n_shared_idx, prim_start, n_prim, n_packed)]
    prims: [(a, b, c, d)]; packed: [(qx, qy, qz)] 11/11/10 bits; shared_idx: [u16]; shared: [u64]."""
    data = w.obj("hknpCompressedMeshShapeData", bytes(176))
    struct.pack_into("<4f", w.data, data + 32, *domain[0], 0.0)
    struct.pack_into("<4f", w.data, data + 48, *domain[1], 0.0)
    struct.pack_into("<iiI", w.data, data + 64, *keys)
    sec_raw = bytearray(96 * len(sections))
    for k, s in enumerate(sections):
        so = 96 * k
        struct.pack_into("<4f", sec_raw, so + 16, *s.get("dmin", (0, 0, 0)), 0.0)
        struct.pack_into("<4f", sec_raw, so + 32, *s.get("dmax", (1, 1, 1)), 0.0)
        struct.pack_into("<3f", sec_raw, so + 48, *s["off"])
        struct.pack_into("<3f", sec_raw, so + 60, *s["scale"])
        struct.pack_into("<4I", sec_raw, so + 72, s["first_packed"], (s["shared_start"] << 8) | s["n_shared_idx"],
                         (s["prim_start"] << 8) | s["n_prim"], 0)
        sec_raw[so + 88] = s["n_packed"]
        sec_raw[so + 89] = s["n_shared_idx"]
    sa = w.raw(bytes(sec_raw))
    w.hkarray(data, 80, sa, len(sections))
    pr = w.raw(b"".join(bytes(p) for p in prims), 4)
    w.hkarray(data, 96, pr, len(prims))
    if shared_idx:
        si = w.raw(b"".join(struct.pack("<H", i) for i in shared_idx), 4)
        w.hkarray(data, 112, si, len(shared_idx))
    pk = w.raw(b"".join(struct.pack("<I", q[0] | (q[1] << 11) | (q[2] << 22)) for q in packed), 4)
    w.hkarray(data, 128, pk, len(packed))
    if shared:
        sh = w.raw(b"".join(struct.pack("<Q", v) for v in shared), 8)
        w.hkarray(data, 144, sh, len(shared))
    shape = w.obj("hknpCompressedMeshShape", bytes(112))
    w.ptr(shape + 96, data)
    return shape


def fo4_compound(w, instances):
    """hknpDynamicCompoundShape: instances hkArray @96, 128 bytes each: rotation columns @0/16/32, translation @48,
    scale @64, child shape ptr @80. instances: [(child_off, R row-major 3x3, t)]."""
    shape = w.obj("hknpDynamicCompoundShape", bytes(112))
    raw = bytearray(128 * len(instances))
    for k, (child, R, t) in enumerate(instances):
        b = 128 * k
        for c in range(3):
            struct.pack_into("<4f", raw, b + 16 * c, R[c], R[3 + c], R[6 + c], 0.0)     # column c
        struct.pack_into("<4f", raw, b + 48, *t, 0.0)
        struct.pack_into("<4f", raw, b + 64, 1.0, 1.0, 1.0, 1.0)
    at = w.raw(bytes(raw))
    for k, (child, _, _) in enumerate(instances):
        w.ptr(at + 128 * k + 80, child)
    w.hkarray(shape, 96, at, len(instances))
    return shape


def pack_blob(build):
    """build(w) -> list of bodies (as fo4_system wants) and motions; returns the packfile bytes."""
    w = PackWriter()
    bodies, motions = build(w)
    fo4_system(w, bodies, motions)
    return w.build()


# ---------------------------------------------------------------- Starfield tagfile template -------------------------
def _v(x):
    assert 0 <= x < 0x4000
    return bytes([x]) if x < 0x80 else bytes([0x80 | (x >> 8), x & 0xFF])


def _sec(tag, payload, leaf=True):
    return struct.pack(">I", ((1 if leaf else 0) << 30) | (len(payload) + 8)) + tag + payload


class TagWriter:
    """TAG0 writer with template parameters (tT) so meshcollision's arr_types / hkRelArray lookups work."""

    def __init__(self):
        self.types = []          # (name, size, fields [(fname, offset, tname)], params [(pname, tname)])
        self.items = []
        self.ptrs = []

    def type(self, name, size, fields=(), params=()):
        self.types.append((name, size, list(fields), list(params)))

    def item(self, tname, payload, count=1):
        self.items.append((tname, bytearray(payload), count))
        return len(self.items)

    def ptr(self, item, offset, target):
        self.ptrs.append((item, offset, target))

    def build(self):
        names = [t[0] for t in self.types]
        tidx = {n: i + 1 for i, n in enumerate(names)}
        pnames = sorted({p for t in self.types for p, _ in t[3]})
        strs = names + [p for p in pnames if p not in names]
        sidx = {s: i for i, s in enumerate(strs)}
        fields = sorted({f for t in self.types for f, _, _ in t[2]})
        fidx = {f: i for i, f in enumerate(fields)}
        tst = b"".join(s.encode() + b"\0" for s in strs)
        fst = b"".join(f.encode() + b"\0" for f in fields)
        tna = _v(len(names) + 1)
        for name, _, _, params in self.types:
            tna += _v(sidx[name]) + _v(len(params))
            for pn, pt in params:
                tna += _v(sidx[pn]) + _v(tidx[pt])
        tbdy = b""
        for name, size, fl, _ in self.types:
            opt = 0x8 | (0x20 if fl else 0)
            tbdy += _v(tidx[name]) + _v(0) + _v(opt) + _v(size) + _v(16)
            if fl:
                tbdy += _v(len(fl)) + b"".join(_v(fidx[f]) + _v(0) + _v(o) + _v(tidx[t]) for f, o, t in fl)
        data, offsets = bytearray(), []
        for _, payload, _ in self.items:
            data += b"\0" * (-len(data) % 16)
            offsets.append(len(data))
            data += payload
        data += b"\0" * (-len(data) % 16)
        pt = []
        for item, off, target in self.ptrs:
            at = offsets[item - 1] + off
            struct.pack_into("<Q", data, at, target)
            pt.append(at)
        item_tab = bytes(12) + b"".join(struct.pack("<III", (0x10 << 24) | tidx[t], o, c)
                                         for (t, _, c), o in zip(self.items, offsets))
        ptch = struct.pack("<II", 1, len(pt)) + struct.pack(f"<{len(pt)}I", *pt) if pt else b""
        types = (_sec(b"TST1", tst) + _sec(b"TNA1", tna) + _sec(b"FST1", fst) + _sec(b"TBDY", tbdy))
        body = (_sec(b"SDKV", b"20190200") + _sec(b"DATA", bytes(data)) + _sec(b"TYPE", types, leaf=False)
                + _sec(b"INDX", _sec(b"ITEM", item_tab) + _sec(b"PTCH", ptch), leaf=False))
        return _sec(b"TAG0", body, leaf=False)


BODY = "hknpPhysicsSystemData::bodyCinfoWithAttachment"


def universal_template(dynamic=False):
    """Template with one item of every type convert_bodies / _dynamic_body copy from (sizes synthetic)."""
    w = TagWriter()
    for n, s in (("u8", 1), ("u16", 2), ("u32", 4), ("i32", 4), ("f32", 4), ("ptr", 8), ("float3", 12),
                 ("float4", 16), ("face", 4), ("edge", 4), ("u64", 8), ("node5", 5), ("hknpMaterial", 32),
                 ("hkcdSimdTree::Node", 128), ("hknpShapeInstance", 128)):
        w.type(n, s)
    w.type("hknpMotionProperties", 64 if dynamic else 0)
    w.type("hknpMassDistribution", 48, [("centerOfMassAndVolume", 0, "float4"), ("majorAxisSpace", 16, "float4"),
                                        ("inertiaTensor", 32, "float4")])
    w.type("hknpRefMassDistribution", 64 if dynamic else 0, [("massDistribution", 16, "hknpMassDistribution")])
    w.type("hkArray<hknpMaterial>", 16, params=[("tT", "hknpMaterial")])
    w.type("hkArray<hknpMotionProperties>", 16, params=[("tT", "hknpMotionProperties")])
    w.type(BODY, 128, [("shape", 0, "ptr"), ("materialId", 8, "u16"), ("motionPropertiesId", 10, "u16"),
                       ("motionType", 12, "u8"), ("flags", 16, "u32"), ("mass", 20, "f32"),
                       ("collisionFilterInfo", 24, "u32"), ("position", 32, "float4"), ("orientation", 48, "float4"),
                       ("massDistribution", 64, "ptr")])
    w.type("hkArray<body>", 16, params=[("tT", BODY)])
    w.type("hknpPhysicsSystemData", 96, [("materials", 0, "hkArray<hknpMaterial>"),
                                         ("motionProperties", 16, "hkArray<hknpMotionProperties>"),
                                         ("bodyCinfos", 32, "hkArray<body>")])
    for e in ("float3", "float4", "face", "u8", "edge"):
        w.type(f"hkRelArray<{e}>", 8, params=[("tT", e)])
    w.type("hknpConvexHull", 48, [("vertices", 0, "hkRelArray<float3>"), ("planes", 8, "hkRelArray<float4>"),
                                  ("faces", 16, "hkRelArray<face>"), ("indices", 24, "hkRelArray<u8>"),
                                  ("faceLinks", 32, "hkRelArray<edge>"), ("vertexEdges", 40, "hkRelArray<edge>")])
    for n in ("hknpConvexShape", "hknpSphereShape"):
        w.type(n, 80, [("convexRadius", 8, "f32"), ("properties", 16, "ptr"), ("hull", 32, "hknpConvexHull")])
    # compressed mesh
    for e in ("u32", "u16", "u64", "node5", "u8", "hkcdSimdTree::Node"):
        w.type(f"hkArray<{e}>", 16, params=[("tT", e)])
    w.type("hkBitFieldStorage", 24, [("words", 0, "hkArray<u32>"), ("numBits", 16, "i32")])
    w.type("hkBitField", 24, [("storage", 0, "hkBitFieldStorage")])
    w.type("hkcdStaticMeshTree::Section", 96, [("nodes", 0, "hkArray<u8>")])
    w.type("hkArray<sec>", 16, params=[("tT", "hkcdStaticMeshTree::Section")])
    w.type("hknpCompressedMeshShapeTree", 160, [("nodes", 0, "hkArray<node5>"), ("sections", 64, "hkArray<sec>"),
                                                ("primitives", 80, "hkArray<u32>"),
                                                ("sharedVerticesIndex", 96, "hkArray<u16>"),
                                                ("packedVertices", 112, "hkArray<u32>"),
                                                ("sharedVertices", 128, "hkArray<u64>"),
                                                ("primitiveDataRuns", 144, "hkArray<u32>")])
    w.type("hkcdSimdTree", 32, [("nodes", 0, "hkArray<hkcdSimdTree::Node>"), ("isCompact", 16, "u8")])
    w.type("hkcdStaticMeshTreeConnectivity", 16)
    w.type("hknpCompressedMeshShapeData", 240, [("meshTree", 0, "hknpCompressedMeshShapeTree"),
                                                ("simdTree", 176, "hkcdSimdTree"),
                                                ("connectivity", 208, "hkcdStaticMeshTreeConnectivity"),
                                                ("hasSimdTree", 224, "u8")])
    w.type("hkArray<extern>", 16, params=[("tT", "ptr")])
    w.type("hknpCompressedMeshShape", 96, [("properties", 8, "ptr"), ("numTriangles", 16, "i32"),
                                           ("numShapeKeyBits", 24, "u8"), ("triangleIsInterior", 32, "hkBitField"),
                                           ("data", 56, "ptr"), ("externShapes", 64, "hkArray<extern>")])
    # compound (dynamic template)
    w.type("hkFreeListArrayElement<hknpShapeInstance>", 128, [("rotation", 0, "float4"), ("translation", 16, "float3"),
                                                              ("scale", 32, "float3"), ("shape", 48, "ptr")])
    w.type("hkFreeListArray", 24, [("elements", 0, "ptr"), ("firstFree", 8, "i32"), ("numAllocated", 12, "u32")])
    w.type("hkAabb", 32, [("min", 0, "float4"), ("max", 16, "float4")])
    w.type("bvdata", 48, [("simdTree", 0, "hkcdSimdTree")])
    w.type("hknpCompoundShape", 192, [("properties", 8, "ptr"), ("numShapeKeyBits", 16, "u8"),
                                      ("estimatedNumShapeKeys", 20, "i32"), ("instances", 24, "hkFreeListArray"),
                                      ("instanceVelocities", 48, "ptr"), ("aabb", 64, "hkAabb"),
                                      ("boundingRadius", 96, "f32"), ("boundingVolumeData", 112, "bvdata")])
    w.item("hknpPhysicsSystemData", bytes(96))
    w.item("hknpMaterial", bytes(32), 1)
    w.item(BODY, bytes(128), 1)
    w.item("hknpConvexShape", bytes(80))
    w.item("hknpSphereShape", bytes(80))
    w.item("hknpCompressedMeshShape", bytes(96))
    w.item("hknpCompressedMeshShapeData", bytes(240))
    if dynamic:
        w.item("hknpMotionProperties", bytes(64), 1)
        w.item("hknpCompoundShape", bytes(192), 1)
        w.item("hkFreeListArrayElement<hknpShapeInstance>", bytes(128), 1)
    return w.build()


CUBE = [(x, y, z) for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)]
CUBE_FACES = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]


def cube(lo, hi):
    v = [(x, y, z) for z in (lo[2], hi[2]) for y in (lo[1], hi[1]) for x in (lo[0], hi[0])]
    return v, [list(f) for f in CUBE_FACES]
