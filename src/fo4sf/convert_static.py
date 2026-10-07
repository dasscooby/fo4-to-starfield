"""Fallout 4 static NIF -> Starfield NIF + .mesh files (spike S1, fidelity tier T1: geometry + placeholder material).

    files = convert_static(open("chair.nif", "rb").read(), "fo4port/setdressing/chair")
    # {"meshes/fo4port/setdressing/chair.nif": b"...", "geometries/<20hex>/<20hex>.mesh": b"...", ...}

Unverified assumptions (see docs/RISKS.md S4): 1 Fallout 4 unit = 1/70 m, same handedness / winding / UV
convention, Z-up in both. Collision, materials and skinning are not converted yet.
"""
import hashlib
import struct
from typing import Dict

from . import nif as nifmod
from . import sfcollision, sfmesh, sfnif

UNIT_SCALE = 1.0 / 70.0           # Fallout 4 units -> metres (Starfield .mesh coordinates are metres)
PLACEHOLDER_MATERIAL = "Materials\\Common\\Metal\\MetalIronCast01.mat"   # vanilla material, T0 look


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def tangent_signs(positions, uvs, normals, tangents, triangles):
    """Per-vertex handedness bit (1 = positive) derived from the UV gradient; the Starfield tangent's top two
    bits are 3 for positive and 0 for negative (verified against 99% of 22k vanilla vertices)."""
    sign = [None] * len(positions)
    for a, b, c in triangles:
        if all(s is not None for s in (sign[a], sign[b], sign[c])):
            continue
        e1, e2 = _sub(positions[b], positions[a]), _sub(positions[c], positions[a])
        du1, dv1 = uvs[b][0] - uvs[a][0], uvs[b][1] - uvs[a][1]
        du2, dv2 = uvs[c][0] - uvs[a][0], uvs[c][1] - uvs[a][1]
        det = du1 * dv2 - du2 * dv1
        if abs(det) < 1e-12:
            continue
        bit = tuple((e2[k] * du1 - e1[k] * du2) / det for k in range(3))
        for v in (a, b, c):
            if sign[v] is None:
                h = _dot(_cross(normals[v], tangents[v]), bit)
                if abs(h) > 1e-12:
                    sign[v] = 1 if h > 0 else 0
    return [1 if s is None else s for s in sign]


def shape_to_mesh(shape: nifmod.Fo4Shape, unit_scale: float = UNIT_SCALE) -> sfmesh.SfMesh:
    pts = []
    r = shape.rotation
    for x, y, z in shape.positions:
        # NIF rotation is row-major; apply scale, rotation and translation of the shape node
        px = shape.scale * (r[0] * x + r[1] * y + r[2] * z) + shape.translation[0]
        py = shape.scale * (r[3] * x + r[4] * y + r[5] * z) + shape.translation[1]
        pz = shape.scale * (r[6] * x + r[7] * y + r[8] * z) + shape.translation[2]
        pts.append((px * unit_scale, py * unit_scale, pz * unit_scale))
    m = sfmesh.SfMesh(version=2)
    m.scale, m.positions = sfmesh.encode_positions(pts)
    m.triangles = [tuple(t) for t in shape.triangles]
    if shape.uvs:
        m.uv1 = [(sfmesh.float_to_half(u), sfmesh.float_to_half(v)) for u, v in shape.uvs]
    if shape.normals:
        m.normals = [sfmesh.encode_packed(*n, w=1.0 / 3.0) for n in shape.normals]
    if shape.normals and shape.tangents and shape.uvs:
        signs = tangent_signs(shape.positions, shape.uvs, shape.normals, shape.tangents, shape.triangles)
        m.tangents = [sfmesh.encode_packed(*t, w=float(s)) for t, s in zip(shape.tangents, signs)]
    if shape.colors:
        m.colors = [(c[2]) | (c[1] << 8) | (c[0] << 16) | (c[3] << 24) for c in shape.colors]   # RGBA -> BGRA u32
    sfmesh.build_meshlets(m)
    return m


def mesh_file_path(mesh_bytes: bytes):
    h = hashlib.sha1(mesh_bytes).hexdigest()
    return h[:20], h[20:40]


def collision_template_from_nif(sf_nif: bytes) -> bytes:
    """Pull the Havok blob out of a vanilla Starfield NIF that has plain box collision (run-time input, not committed)."""
    n = nifmod.parse(sf_nif)
    for i, b in enumerate(n.blocks):
        if n.type_of(i) == "bhkPhysicsSystem":
            size, = struct.unpack_from("<I", b, 0)
            blob = b[4:4 + size]
            sfcollision.check_template(blob)
            return blob
    raise nifmod.NifError("template NIF has no bhkPhysicsSystem")


def convert_static(fo4_nif: bytes, out_name: str, material_path: str = PLACEHOLDER_MATERIAL,
                   unit_scale: float = UNIT_SCALE, collision_template: bytes = None,
                   material_paths: list = None, collision_mode: str = "box",
                   include_skinned: bool = False) -> Dict[str, bytes]:
    """collision_mode: "box" = one AABB on the root; "surfaces" = thin boxes behind flat surfaces, one body each."""
    src = nifmod.parse(fo4_nif)
    shapes = [s for s in nifmod.fo4_trishapes(src) if (include_skinned or not s.skinned) and s.positions and s.triangles]
    if not shapes:
        raise nifmod.NifError("no static BSTriShape geometry found")
    files, static_shapes, all_pts, all_tris = {}, [], [], []
    for i, s in enumerate(shapes):
        if material_paths and material_paths[i] is None:      # caller asked to drop this shape (e.g. effect shader)
            continue
        m = shape_to_mesh(s, unit_scale)
        data = sfmesh.serialize(m)
        d, f = mesh_file_path(data)
        files[f"geometries/{d}/{f}.mesh"] = data
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        all_tris += [(a + len(all_pts), b + len(all_pts), c + len(all_pts)) for a, b, c in m.triangles]
        all_pts += pts
        sphere, box = sfnif.bounds_from_points(pts)
        name = s.name or f"Shape{i}".encode()
        static_shapes.append(sfnif.StaticShape(name, f"{d}\\{f}".encode(), len(m.triangles) * 3, len(m.positions),
                                               material_paths[i] if material_paths else material_path, sphere, box))
    node_name = out_name.rsplit("/", 1)[-1].encode()
    blob, child_blobs = None, []
    if collision_template is not None and collision_mode == "surfaces":
        for c, h in sfcollision.mesh_boxes(all_pts, all_tris):
            child_blobs.append(sfcollision.box_blob(collision_template, c, h))
    elif collision_template is not None:     # T3: one axis-aligned box around all geometry
        lo = [min(p[a] for p in all_pts) for a in range(3)]
        hi = [max(p[a] for p in all_pts) for a in range(3)]
        blob = sfcollision.box_blob(collision_template, tuple((lo[a] + hi[a]) / 2 for a in range(3)),
                                    tuple((hi[a] - lo[a]) / 2 for a in range(3)))
    out = sfnif.build_static_nif(node_name, static_shapes, collision_blob=blob, child_collision_blobs=child_blobs)
    files[f"meshes/{out_name}.nif"] = nifmod.serialize(out)
    return files
