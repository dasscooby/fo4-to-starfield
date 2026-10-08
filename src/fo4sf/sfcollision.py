"""Starfield box collision (spike S6, tier T3): patch a vanilla box-collision Havok blob to a new axis-aligned box.

`bhkPhysicsSystem` holds a Havok tagfile (`TAG0`). We do not write tagfiles; we take a vanilla blob that contains a single
`hknpBoxShape` (read at run time from the user's own game archives, never committed) and overwrite the floats that depend on the
box. They were found by regressing 369 vanilla identity-rotation box blobs (6,168 bytes each) against the box centre and
half-extents: 36 words depend on the box and fit exactly (6 centre/half-size words, the 8 corner points, 6 face planes; see
docs/spikes/S6-collision.md). Six other varying words are constant/zero and the rest are mass/inertia or padding; they are left as
in the template. In game the resulting props are solid and fixed (the player cannot push them).
"""
import struct
from typing import Tuple

BLOB_SIZE = 6168
# offsets (bytes into the blob) -> coefficients over (cx, cy, cz, hx, hy, hz)
_V = [(1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1), (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1)]


def _build_table():
    t = {540: (0, 0, 0, 1, 0, 0), 556: (0, 0, 0, 0, 1, 0), 572: (0, 0, 0, 0, 0, 1),
         576: (1, 0, 0, 0, 0, 0), 580: (0, 1, 0, 0, 0, 0), 584: (0, 0, 1, 0, 0, 0)}
    for k, (sx, sy, sz) in enumerate(_V):                 # the 8 box corners, hkFloat3 each
        base = 592 + 12 * k
        t[base] = (1, 0, 0, sx, 0, 0)
        t[base + 4] = (0, 1, 0, 0, sy, 0)
        t[base + 8] = (0, 0, 1, 0, 0, sz)
    # six face-plane offsets
    t[700] = (-1, 0, 0, -1, 0, 0)
    t[716] = (1, 0, 0, -1, 0, 0)
    t[732] = (0, -1, 0, 0, -1, 0)
    t[748] = (0, 1, 0, 0, -1, 0)
    t[764] = (0, 0, -1, 0, 0, -1)
    t[780] = (0, 0, 1, 0, 0, -1)
    return t


LINEAR = _build_table()
MIN_HALF = 0.005


class CollisionError(ValueError):
    pass


def check_template(blob: bytes):
    if len(blob) != BLOB_SIZE or not blob.startswith(b"\x00\x00\x18\x18TAG0"):
        raise CollisionError(f"template blob is not a 6,168-byte Havok tagfile (got {len(blob)} bytes)")
    if b"hknpBoxShape" not in blob or b"hknpCompoundShape" in blob or b"hknpCompressedMeshShape" in blob:
        raise CollisionError("template blob is not a plain box shape")
    if struct.unpack_from("<3f", blob, 528) != (1.0, 0.0, 0.0) or struct.unpack_from("<3f", blob, 544) != (0.0, 1.0, 0.0) \
            or struct.unpack_from("<3f", blob, 560) != (0.0, 0.0, 1.0):
        raise CollisionError("template box is rotated; need an identity-rotation template")


def box_blob(template: bytes, center: Tuple[float, float, float], half: Tuple[float, float, float]) -> bytes:
    """Return a copy of `template` describing the axis-aligned box (centre, half-extents) in metres."""
    check_template(template)
    h = tuple(max(MIN_HALF, abs(v)) for v in half)
    feat = (*center, *h)
    out = bytearray(template)
    for off, coef in LINEAR.items():
        struct.pack_into("<f", out, off, sum(c * f for c, f in zip(coef, feat)))
    return bytes(out)


def surface_boxes(points, triangles, thickness=0.15, plane_tol=0.05, gap=0.05, min_area=0.04, max_boxes=48,
                  axis_cos=0.92, leftovers=None, cell=0.25, report=None):
    """Thin boxes behind the flat, axis-aligned surfaces of a mesh (floors, walls, ceilings, stair steps).

    Triangles whose normal is within ~23 degrees of an axis are grouped by (axis, facing, plane offset) and then split into
    spatially connected clusters; each cluster becomes a box spanning its extent, `thickness` deep behind the surface.
    Returns [(centre, half_extents)], largest area first. Sloped / curved geometry is ignored."""
    groups = {}
    for a, b, c in triangles:
        p0, p1, p2 = points[a], points[b], points[c]
        u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
        v = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ln = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5
        if ln < 1e-9:
            continue
        n = (n[0] / ln, n[1] / ln, n[2] / ln)
        ax = max(range(3), key=lambda k: abs(n[k]))
        if abs(n[ax]) < axis_cos:
            if leftovers is not None:
                leftovers.append((a, b, c))
            continue
        sign = 1 if n[ax] > 0 else -1
        d = (p0[ax] + p1[ax] + p2[ax]) / 3
        lo = [min(p0[k], p1[k], p2[k]) for k in range(3)]
        hi = [max(p0[k], p1[k], p2[k]) for k in range(3)]
        groups.setdefault((ax, sign, round(d / plane_tol)), []).append((lo, hi, ln / 2, d, (a, b, c)))
    boxes = []
    for (ax, sign, _), tris in groups.items():
        others = [k for k in range(3) if k != ax]
        parent = list(range(len(tris)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        order = sorted(range(len(tris)), key=lambda i: tris[i][0][others[0]])
        for ii, i in enumerate(order):           # sweep along the first in-plane axis
            for j in order[ii + 1:]:
                if tris[j][0][others[0]] > tris[i][1][others[0]] + gap:
                    break
                if tris[j][0][others[1]] <= tris[i][1][others[1]] + gap and tris[i][0][others[1]] <= tris[j][1][others[1]] + gap:
                    parent[find(i)] = find(j)
        clusters = {}
        for i in range(len(tris)):
            clusters.setdefault(find(i), []).append(tris[i])
        for cl in clusters.values():
            area = sum(t[2] for t in cl)
            if area < min_area:
                if leftovers is not None:
                    leftovers.extend(t[4] for t in cl)
                continue
            d = sum(t[3] for t in cl) / len(cl)
            for (u0, v0, u1, v1) in _plane_rects(points, [t[4] for t in cl], others, cell):
                lo, hi = [0.0] * 3, [0.0] * 3
                lo[others[0]], hi[others[0]] = u0, u1
                lo[others[1]], hi[others[1]] = v0, v1
                if sign > 0:                       # surface faces +axis: solid lies behind it
                    lo[ax], hi[ax] = d - thickness, d
                else:
                    lo[ax], hi[ax] = d, d + thickness
                centre = tuple((lo[k] + hi[k]) / 2 for k in range(3))
                half = tuple((hi[k] - lo[k]) / 2 for k in range(3))
                area_r = half[others[0]] * half[others[1]] * 4
                # priority: walkable floors first (surface facing +Z), then everything else by area
                boxes.append((area_r + (1e6 if (ax == 2 and sign > 0) else 0.0), centre, half))
    boxes.sort(key=lambda b: -b[0])
    if report is not None and len(boxes) > max_boxes:
        report["surface_dropped"] = report.get("surface_dropped", 0) + len(boxes) - max_boxes
        report["surface_dropped_area"] = report.get("surface_dropped_area", 0.0) + sum(b[0] % 1e6 for b in boxes[max_boxes:])
        report["floor_dropped"] = report.get("floor_dropped", 0) + sum(1 for b in boxes[max_boxes:] if b[0] >= 1e6)
    return [(c, h) for _, c, h in boxes[:max_boxes]]


def _plane_rects(points, tris, axes, cell):
    """Rasterise triangles projected on two axes into `cell`-sized squares (a square is solid if its centre is inside a
    triangle, or a triangle's centroid falls in it, so slivers still count), then greedily merge rows into rectangles.
    Holes and concave outlines survive, unlike a bounding box. Returns [(u0, v0, u1, v1)] in world units."""
    a0, a1 = axes
    occ = set()
    for t in tris:
        P = [(points[i][a0], points[i][a1]) for i in t]
        umin, umax = min(p[0] for p in P), max(p[0] for p in P)
        vmin, vmax = min(p[1] for p in P), max(p[1] for p in P)
        (x0, y0), (x1, y1), (x2, y2) = P
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        cu, cv = (x0 + x1 + x2) / 3, (y0 + y1 + y2) / 3
        occ.add((int(cu // cell), int(cv // cell)))
        if abs(den) < 1e-12:
            continue
        for i in range(int(umin // cell), int(umax // cell) + 1):
            for j in range(int(vmin // cell), int(vmax // cell) + 1):
                px, py = (i + 0.5) * cell, (j + 0.5) * cell
                l1 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / den
                l2 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / den
                if l1 >= -1e-6 and l2 >= -1e-6 and 1 - l1 - l2 >= -1e-6:
                    occ.add((i, j))
    rects, used = [], set()
    for (i, j) in sorted(occ, key=lambda c: (c[1], c[0])):
        if (i, j) in used:
            continue
        i1 = i
        while (i1 + 1, j) in occ and (i1 + 1, j) not in used:
            i1 += 1
        j1 = j
        while all((x, j1 + 1) in occ and (x, j1 + 1) not in used for x in range(i, i1 + 1)):
            j1 += 1
        for x in range(i, i1 + 1):
            for y in range(j, j1 + 1):
                used.add((x, y))
        rects.append((i * cell, j * cell, (i1 + 1) * cell, (j1 + 1) * cell))
    return rects

def voxel_boxes(points, triangles, voxel=0.2, max_boxes=96, report=None):
    """Cover arbitrary triangles (slopes, curves, rails, pipes) with axis-aligned boxes: mark the voxels the surface passes
    through, then greedily merge runs of voxels into boxes (x, then y, then z). Coarsens the grid until it fits max_boxes."""
    while True:
        cells = set()
        for a, b, c in triangles:
            p0, p1, p2 = points[a], points[b], points[c]
            edge = max(sum((p[k] - q[k]) ** 2 for k in range(3)) ** 0.5 for p, q in ((p0, p1), (p1, p2), (p2, p0)))
            steps = max(1, int(edge / (voxel * 0.5)) + 1)
            for i in range(steps + 1):
                for j in range(steps + 1 - i):
                    u, v = i / steps, j / steps
                    w = 1 - u - v
                    x = tuple(w * p0[k] + u * p1[k] + v * p2[k] for k in range(3))
                    cells.add(tuple(int((x[k] // voxel)) for k in range(3)))
        boxes, used = [], set()
        for cell in sorted(cells):
            if cell in used:
                continue
            x0, y0, z0 = cell
            x1 = x0
            while (x1 + 1, y0, z0) in cells and (x1 + 1, y0, z0) not in used:
                x1 += 1
            y1 = y0
            while all((x, y1 + 1, z0) in cells and (x, y1 + 1, z0) not in used for x in range(x0, x1 + 1)):
                y1 += 1
            z1 = z0
            while all((x, y, z1 + 1) in cells and (x, y, z1 + 1) not in used for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)):
                z1 += 1
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    for z in range(z0, z1 + 1):
                        used.add((x, y, z))
            lo = (x0 * voxel, y0 * voxel, z0 * voxel)
            hi = ((x1 + 1) * voxel, (y1 + 1) * voxel, (z1 + 1) * voxel)
            boxes.append((tuple((lo[k] + hi[k]) / 2 for k in range(3)), tuple((hi[k] - lo[k]) / 2 for k in range(3))))
        if len(boxes) <= max_boxes or voxel >= 0.45:
            # never coarsen past ~0.5 m (coarse voxels become invisible walls); keep the biggest boxes if still too many
            boxes.sort(key=lambda b: -(b[1][0] * b[1][1] * b[1][2]))
            if report is not None and len(boxes) > max_boxes:
                report["voxel_dropped"] = report.get("voxel_dropped", 0) + len(boxes) - max_boxes
            return boxes[:max_boxes]
        voxel *= 1.5


def mesh_boxes(points, triangles, max_surface=160, max_voxel=96, report=None):
    """Hybrid architecture collision: rasterised thin boxes behind flat axis-aligned surfaces (holes kept), voxel boxes for
    the rest. Anything dropped by a cap is counted in `report` (never silently)."""
    for cell in (0.25, 0.5, 1.0):                  # coarsen the grid until the flat surfaces fit the cap
        rest, trial = [], {}
        boxes = surface_boxes(points, triangles, max_boxes=max_surface, min_area=0.01, leftovers=rest, cell=cell, report=trial)
        if not trial.get("surface_dropped"):
            break
    if report is not None:
        for k, v in trial.items():
            report[k] = report.get(k, 0) + v
        if cell != 0.25:
            report["surface_cell"] = cell
    if rest:
        boxes += voxel_boxes(points, rest, max_boxes=max_voxel, report=report)
    if report is not None:
        report["boxes"] = len(boxes)
    return boxes


def read_box(blob: bytes):
    """Inverse of box_blob for the fields we write: (centre, half-extents) from the 8 corners."""
    pts = [struct.unpack_from("<3f", blob, 592 + 12 * k) for k in range(8)]
    lo = [min(p[a] for p in pts) for a in range(3)]
    hi = [max(p[a] for p in pts) for a in range(3)]
    return tuple((lo[a] + hi[a]) / 2 for a in range(3)), tuple((hi[a] - lo[a]) / 2 for a in range(3))


# Words that differ between the static box template and the body on a vanilla animated door leaf
# (AK_Ext_Bld_WallA_DoorA_01 mesh001, same 6,168-byte box layout) apart from the box geometry: motion type (240: 2 vs 1),
# filter / flags (232, 264), body ids / hashes (448, 456, 472) and the compressed mass properties (1064-1095).
# Copying them from that donor turns a static box into a keyframed one that follows its animated node.
KEYFRAMED_FIELDS = ((232, 4), (240, 4), (264, 4), (448, 4), (456, 4), (472, 4), (1064, 16), (1088, 8))


def keyframed(blob: bytes, donor: bytes) -> bytes:
    """Return blob with the KEYFRAMED_FIELDS taken from donor (a vanilla animated-door body of the same layout)."""
    if len(blob) != len(donor):
        raise ValueError("donor body has a different layout")
    out = bytearray(blob)
    for off, n in KEYFRAMED_FIELDS:
        out[off:off + n] = donor[off:off + n]
    return bytes(out)


def physics_blob_from_nif(sf_nif: bytes, node_name: bytes = b"mesh001") -> bytes:
    """The bhkPhysicsSystem blob attached (via bhkNPCollisionObject) to the named node of a Starfield NIF."""
    from . import nif as nifmod
    f = nifmod.parse(sf_nif)
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        target, _, data = struct.unpack_from("<iHi", f.blocks[i], 0)
        idx, = struct.unpack_from("<i", f.blocks[target], 0)
        if f.strings[idx] == node_name:
            n, = struct.unpack_from("<I", f.blocks[data], 0)
            return f.blocks[data][4:4 + n]
    raise ValueError("no collision body on node %r" % node_name)
