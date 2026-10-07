"""Starfield (BS 173/175) NIF blocks we need to write, decoded from nif.xml and checked against vanilla files.

A minimal static prop is five blocks (see build_static_nif):
    0 NiNode            root, one child, extra data -> BSXFlags
    1 BSXFlags
    2 BSGeometry        bounds + `Meshes[0]` = path of an external .mesh (relative to Data/geometries, no extension)
    3 NiIntegerExtraData "MaterialID" = crc32_bethesda(lowercase material path)
    4 BSLightingShaderProperty   whose *name* is the .mat path
"""
import struct
import zlib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import nif as nifmod

NIL = 0xFFFFFFFF


def material_id(path: str) -> int:
    """CRC32 (poly 0xEDB88320, init 0, no final xor) of the lowercase path, backslashes, latin-1.
    Verified against 60/60 vanilla NIFs."""
    return zlib.crc32(path.lower().replace("/", "\\").encode("latin-1"), 0xFFFFFFFF) ^ 0xFFFFFFFF


@dataclass
class MeshRef:
    indices_size: int
    num_verts: int
    flags: int
    path: bytes            # e.g. b"<20 hex>\\<20 hex>"


@dataclass
class BSGeometry:
    name_idx: int = 0
    extra_refs: List[int] = field(default_factory=list)
    controller: int = -1
    flags: int = 0xE
    translation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, ...] = (1, 0, 0, 0, 1, 0, 0, 0, 1)
    scale: float = 1.0
    collision: int = -1
    sphere: Tuple[float, float, float, float] = (0, 0, 0, 0)       # centre xyz, radius
    box: Tuple[float, ...] = (0, 0, 0, 0, 0, 0)                     # centre xyz, half-extent xyz
    skin: int = -1
    shader: int = -1
    alpha: int = -1
    meshes: List[Optional[MeshRef]] = field(default_factory=lambda: [None] * 4)


def parse_bsgeometry(b: bytes) -> BSGeometry:
    g = BSGeometry()
    g.name_idx, n = struct.unpack_from("<iI", b, 0)
    p = 8
    g.extra_refs = list(struct.unpack_from(f"<{n}i", b, p)); p += 4 * n
    g.controller, g.flags = struct.unpack_from("<iI", b, p); p += 8
    g.translation = struct.unpack_from("<3f", b, p); p += 12
    g.rotation = struct.unpack_from("<9f", b, p); p += 36
    g.scale, g.collision = struct.unpack_from("<fi", b, p); p += 8
    g.sphere = struct.unpack_from("<4f", b, p); p += 16
    g.box = struct.unpack_from("<6f", b, p); p += 24
    g.skin, g.shader, g.alpha = struct.unpack_from("<3i", b, p); p += 12
    g.meshes = []
    for _ in range(4):
        has = b[p]; p += 1
        if not has:
            g.meshes.append(None)
            continue
        isz, nv, fl = struct.unpack_from("<3I", b, p); p += 12
        if fl & 512:
            raise nifmod.NifError("embedded mesh data not supported")
        ln, = struct.unpack_from("<I", b, p); p += 4
        g.meshes.append(MeshRef(isz, nv, fl, b[p:p + ln])); p += ln
    if p != len(b):
        raise nifmod.NifError(f"BSGeometry: {len(b) - p} unparsed bytes")
    return g


def build_bsgeometry(g: BSGeometry) -> bytes:
    out = [struct.pack("<iI", g.name_idx, len(g.extra_refs)), struct.pack(f"<{len(g.extra_refs)}i", *g.extra_refs),
           struct.pack("<iI", g.controller, g.flags), struct.pack("<3f", *g.translation),
           struct.pack("<9f", *g.rotation), struct.pack("<fi", g.scale, g.collision),
           struct.pack("<4f", *g.sphere), struct.pack("<6f", *g.box),
           struct.pack("<3i", g.skin, g.shader, g.alpha)]
    for m in g.meshes:
        if m is None:
            out.append(b"\x00")
        else:
            out.append(b"\x01" + struct.pack("<3I", m.indices_size, m.num_verts, m.flags)
                       + struct.pack("<I", len(m.path)) + m.path)
    return b"".join(out)


def bounds_from_points(points):
    lo = [min(p[a] for p in points) for a in range(3)]
    hi = [max(p[a] for p in points) for a in range(3)]
    c = [(lo[a] + hi[a]) / 2 for a in range(3)]
    ext = [(hi[a] - lo[a]) / 2 for a in range(3)]
    radius = max(((p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2) ** 0.5 for p in points)
    return (*c, radius), (*c, *ext)


@dataclass
class StaticShape:
    name: bytes
    mesh_path: bytes        # b"<20 hex>\\<20 hex>"
    indices_size: int
    num_verts: int
    material_path: str
    sphere: tuple
    box: tuple


def build_static_nif(node_name: bytes, shapes: List[StaticShape], bs_version: int = 173,
                     collision_blob: Optional[bytes] = None) -> nifmod.NifFile:
    """A static prop NIF laid out like vanilla `setdressing` props: NiNode, BSXFlags, [bhkNPCollisionObject,
    bhkPhysicsSystem,] then per shape BSGeometry + NiIntegerExtraData("MaterialID") + BSLightingShaderProperty
    (named by its .mat path). The root node owns the collision object; BSXFlags is 2 when there is collision."""
    f = nifmod.NifFile(endian=1, user_version=12, bs_version=bs_version, author=b"\x00", unknown_int=0,
                       export_script=b"\x00", sf_data=b"\x7a\x00")
    s_node = f.string_index(node_name)
    s_bsx = f.string_index(b"BSX")
    s_matid = f.string_index(b"MaterialID")
    ident = struct.pack("<3f9ff", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0)
    first = 4 if collision_blob is not None else 2
    children = [first + 3 * i for i in range(len(shapes))]
    coll_ref = 2 if collision_blob is not None else -1
    f.add_block("NiNode", struct.pack("<iIiiI", s_node, 1, 1, -1, 0xE) + ident
                + struct.pack("<iI", coll_ref, len(children)) + struct.pack(f"<{len(children)}i", *children))
    f.add_block("BSXFlags", struct.pack("<iI", s_bsx, 2 if collision_blob is not None else 0))
    if collision_blob is not None:
        f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 0, 0x80, 3, 0))      # target = root node, data = block 3
        f.add_block("bhkPhysicsSystem", struct.pack("<I", len(collision_blob)) + collision_blob)
    for i, s in enumerate(shapes):
        base = first + 3 * i
        g = BSGeometry(name_idx=f.string_index(s.name), extra_refs=[base + 1], sphere=s.sphere, box=s.box,
                       shader=base + 2,
                       meshes=[MeshRef(s.indices_size, s.num_verts, 0x40, s.mesh_path), None, None, None])
        f.add_block("BSGeometry", build_bsgeometry(g))
        f.add_block("NiIntegerExtraData", struct.pack("<iI", s_matid, material_id(s.material_path)))
        f.add_block("BSLightingShaderProperty",
                    struct.pack("<iIi", f.string_index(s.material_path.encode("latin-1")), 0, -1))
    f.footer = struct.pack("<II", 1, 0)
    return f
