"""Build movement test routes for a converted cell from Fallout 4's own data (no guessing from screenshots).

usage: python routes.py --fo4-data <FO4 Data> --cell-json <cell.json> --manifest <manifest.json> --out routes.json

Stairs: every placed model whose FO4 collision has a stair ramp: the L_STAIRHELPER body (layer 31) if present, else the
collision triangles sloped 20-50 degrees. The ramp's low and high ends (node space -> placement) give a start point 0.8 m
before the low end, the heading towards the high end, and the expected height at the top.
Doors: every placed converted door (manifest item with "door"): start 1.6 m in front of the FO4 origin facing through
the opening, press E, walk; pass = the player ends at least 1 m past the door plane.
Coordinates are metres in Starfield cell space (FO4 units / 70); reference rotations use Bethesda's clockwise angles.
"""
import argparse
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import fo4collision, hkpackfile, nif, pipeline  # noqa: E402

UNIT = 1.0 / 70.0
STAIRHELPER = 31


def ref_matrix(rot):
    """Bethesda reference rotation (radians, clockwise), applied X then Y then Z: same as PluginSpike.RotateOffset."""
    cx, sx = math.cos(-rot[0]), math.sin(-rot[0])
    cy, sy = math.cos(-rot[1]), math.sin(-rot[1])
    cz, sz = math.cos(-rot[2]), math.sin(-rot[2])
    rx = (1, 0, 0, 0, cx, -sx, 0, sx, cx)
    ry = (cy, 0, sy, 0, 1, 0, -sy, 0, cy)
    rz = (cz, -sz, 0, sz, cz, 0, 0, 0, 1)
    return nif._matmul(rz, nif._matmul(ry, rx))


def apply(m, v):
    return tuple(m[3 * i] * v[0] + m[3 * i + 1] * v[1] + m[3 * i + 2] * v[2] for i in range(3))


def ramp_points(f):
    """Node-space-transformed (NIF root, metres) points of the stair ramp of a FO4 NIF, or [] if it has none."""
    world = nif.world_transforms(f)
    helper, sloped = [], []
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        target, _, data = struct.unpack_from("<iHi", f.blocks[i], 0)
        body = struct.unpack_from("<I", f.blocks[i], 10)[0] if len(f.blocks[i]) >= 14 else 0
        if not (0 <= data < len(f.blocks)) or f.type_of(data) != "bhkPhysicsSystem":
            continue
        n, = struct.unpack_from("<I", f.blocks[data], 0)
        try:
            p = hkpackfile.Packfile(f.blocks[data][4:4 + n])
        except hkpackfile.PackfileError:
            continue
        classes = dict(p.objects())
        sysobj = next(o for o, c in classes.items() if c == "hknpPhysicsSystemData")
        at, nb = p.array(sysobj + fo4collision.SYS_BODIES)
        tr, rot, _ = world(target)
        to_root = lambda v: tuple(a + b * UNIT for a, b in zip(apply(rot, v), tr))
        for k in ([body] if 0 <= body < nb else []):
            b = at + fo4collision.BODY_SIZE * k
            shape = p.pointer(b)
            layer = p.unpack("<I", b + 20)[0] & 0x7F
            cls = classes.get(shape)
            try:
                if cls == "hknpConvexPolytopeShape":
                    pts, tris = fo4collision._convex(p, shape)
                elif cls == "hknpCompressedMeshShape":
                    pts, tris = fo4collision._compressed_mesh(p, p.pointer(shape + fo4collision.CMS_DATA))
                else:
                    continue
            except (IndexError, hkpackfile.PackfileError):
                continue
            if layer == STAIRHELPER:
                helper += [to_root(v) for v in pts]
                continue
            for t in tris:
                a, b_, c = (pts[x] for x in t)
                u = [b_[q] - a[q] for q in range(3)]
                v = [c[q] - a[q] for q in range(3)]
                nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                ln = math.sqrt(sum(x * x for x in nrm)) or 1
                tilt = math.degrees(math.acos(max(-1, min(1, nrm[2] / ln))))
                if 20 < tilt < 50:
                    sloped += [to_root(x) for x in (a, b_, c)]
    return (helper, "stairhelper") if helper else (sloped, "sloped-collision") if sloped else ([], None)


def ends(points):
    zs = [p[2] for p in points]
    lo_z, hi_z = min(zs), max(zs)
    low = [p for p in points if p[2] <= lo_z + 0.05]
    high = [p for p in points if p[2] >= hi_z - 0.05]
    mean = lambda ps: tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))
    return mean(low), mean(high)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fo4-data", required=True)
    ap.add_argument("--cell-json", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=40)
    a = ap.parse_args()
    src = pipeline.Fo4Archives(a.fo4_data)
    cell = json.load(open(a.cell_json, encoding="utf-8-sig"))
    man = json.load(open(a.manifest))
    items = {it["source"].lower(): it for it in man["items"]}
    routes, cache, skipped = [], {}, {}
    for r in cell["refs"]:
        model = r.get("model") or ""
        key = "meshes\\" + model.lstrip("\\").lower()
        it = items.get(key)
        if not it:
            continue
        pos = tuple(x * UNIT for x in r["pos"])
        R = ref_matrix(r["rot"])
        sc = r.get("scale", 1.0) or 1.0
        place = lambda v: tuple(a_ + b_ for a_, b_ in zip(apply(R, tuple(x * sc for x in v)), pos))
        if it.get("door"):
            n = place((1.0, 0.0, 0.0))
            n = tuple(x - y for x, y in zip(n, pos))
            start = tuple(pos[i] - 1.6 * n[i] for i in range(3))
            routes.append({"cell": cell["cell"], "kind": "door", "ref": r["formkey"], "model": model,
                           "start": [round(start[0], 2), round(start[1], 2), round(pos[2] + 0.3, 2)],
                           "heading": round(math.degrees(math.atan2(n[0], n[1])) % 360, 1), "use": True, "walk_ms": 2600,
                           "expect": {"plane_point": [round(x, 3) for x in pos], "plane_normal": [round(x, 4) for x in n],
                                      "min_past": 1.0}})
            continue
        if "stair" not in model.lower():
            continue
        if key not in cache:
            raw = src.mesh(key)
            cache[key] = ramp_points(nif.parse(raw)) if raw else ([], None)
        pts, how = cache[key]
        if not pts:
            skipped[model] = skipped.get(model, 0) + 1
            continue
        lo, hi = ends([place(p) for p in pts])
        d = (hi[0] - lo[0], hi[1] - lo[1])
        run = math.hypot(*d) or 1.0
        start = (lo[0] - 0.8 * d[0] / run, lo[1] - 0.8 * d[1] / run, lo[2] + 0.3)
        routes.append({"cell": cell["cell"], "kind": "stairs", "ref": r["formkey"], "model": model, "ramp": how,
                       "start": [round(x, 2) for x in start], "heading": round(math.degrees(math.atan2(d[0], d[1])) % 360, 1),
                       # the player runs ~4.6 m/s: walk just past the high end (mirrored flights share landings, a longer
                       # walk goes up one and down the other)
                       "use": False, "walk_ms": int(250 + 1000 * (run + 1.0) / 4.0),
                       "expect": {"low": [round(x, 2) for x in lo], "high": [round(x, 2) for x in hi], "min_rise": round(0.8 * (hi[2] - lo[2]), 2)}})
    routes = routes[:a.max]
    json.dump({"routes": routes, "skipped_stairs_without_ramp": skipped}, open(a.out, "w"), indent=1)
    print(f"{len(routes)} routes ({sum(r['kind'] == 'stairs' for r in routes)} stairs, "
          f"{sum(r['kind'] == 'door' for r in routes)} doors); stairs without a ramp: {skipped}")


if __name__ == "__main__":
    main()
