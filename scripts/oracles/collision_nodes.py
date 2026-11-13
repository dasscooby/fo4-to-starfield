"""Read-only: which node every collision object of ONE NIF is bound to, and whether a clip on that NIF would move it.

Works on a Fallout 4 source NIF (BS version < 170) and on a converted Starfield NIF (>= 170). For each
bhkNPCollisionObject it prints the target node (name and path to the scene root), the world position of that node,
the body index, the physics system it shares, the motion class of the body and, when the shape can be decoded, the
bounds of its points; then it says whether the target node is, or sits below, a node an NiControllerSequence of the
file animates. This is the question of vault111-moving-platform-note section 8: the lift's moving part rides a clip
only when its collision objects sit on (or under) an animated node.

  python -I scripts/oracles/collision_nodes.py <model.nif> [--json]

Writes nothing; the NIF is game data and stays outside Git. What it does NOT do: say anything about runtime behaviour.
Evidence labels: node names, targets, hierarchy and animated-node names are read from the file (verified by the
parser); the sequence controlled-block layout (29 bytes per block: interpolator, controller, priority byte, five string
indices; the same layout nif.door_hinge reads for its first block) is checked in range only, so a name list shorter
than the block count is printed as such; FO4 motion class follows fo4collision.body_mass (static / keyframed /
dynamic); Starfield motion is the u32 at offset 264 of the body blob (0 static, 1 keyframed, 2 dynamic) with the layer at 240
(research-log 2026-10-10), printed as `motion(layer N)`; verified only for the box layout. Bounds are those of the object's own body index (not the whole shared system); rotated bodies and shape classes other than compressed mesh / convex polytope (e.g. DynamicCompound) print None = unread.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / "src")]
from fo4sf import fo4collision as fc, hkpackfile, nif  # noqa: E402

STARFIELD_BS = 170
SEQ_BLOCK = 29           # interpolator, controller, priority (1), node name, property type, controller type, id, interp id
MOTION_NAMES = {0: "static", 1: "keyframed", 2: "dynamic"}


def _name(f, i):
    try:
        idx, = struct.unpack_from("<i", f.blocks[i], 0)
        return f.strings[idx].decode("latin-1") if 0 <= idx < len(f.strings) else ""
    except (struct.error, IndexError):
        return ""


def _parents(f):
    parent = {}
    for i in range(len(f.blocks)):
        if f.type_of(i).endswith("Node"):
            try:
                for c in nif.node_children(f, i):
                    parent.setdefault(c, i)
            except struct.error:
                pass
    return parent


def animated_names(f):
    """({sequence name: [node names its controlled blocks name]}, notes)"""
    out, notes = {}, []
    for i in range(len(f.blocks)):
        if f.type_of(i) != "NiControllerSequence":
            continue
        blk = f.blocks[i]
        try:
            sname, count = struct.unpack_from("<iI", blk, 0)
            names = []
            for k in range(count):
                at = 12 + SEQ_BLOCK * k + 9
                if at + 4 > len(blk):
                    notes.append(f"sequence block {i}: {count} controlled blocks declared, {len(names)} fit in the block")
                    break
                idx, = struct.unpack_from("<i", blk, at)
                names.append(f.strings[idx].decode("latin-1") if 0 <= idx < len(f.strings) else "?")
            out[f.strings[sname].decode("latin-1") if 0 <= sname < len(f.strings) else f"#{i}"] = names
        except struct.error:
            notes.append(f"sequence block {i}: unreadable")
    return out, notes


def _fo4_motion(blob, body):
    p = hkpackfile.Packfile(blob)
    classes = dict(p.objects())
    sysobj = next(o for o, c in classes.items() if c == "hknpPhysicsSystemData")
    at, n = p.array(sysobj + fc.SYS_BODIES)
    if at is None or not 0 <= body < n:
        return "body index out of range", None, None
    shape = classes.get(p.pointer(at + fc.BODY_SIZE * body), "?")
    mi, = p.unpack("<I", at + fc.BODY_SIZE * body + fc.BODY_MOTION)
    if mi == fc.STATIC_MOTION:
        return "static", shape, n
    cin, nm = p.array(sysobj + fc.SYS_MOTION_CINFOS)
    if cin is None or not 0 <= mi < nm:
        return "motion entry unreadable", shape, n
    pid, inv = p.unpack("<H2xf", cin + fc.MOTION_CINFO_SIZE * mi)
    return ("dynamic" if pid != 0xFFFF and inv > 0 else "keyframed" if pid == 0xFFFF and inv == 0 else "motion odd"), shape, n


def _sf_motion(blob):
    """motionType u32 at 264 (0 static, 1 keyframed, 2 dynamic) of a Starfield box-layout body blob, with the collision layer
    at 240 (docs/ai/research-log.md 2026-10-10; sfcollision.KEYFRAMED_FIELDS). Other layouts (dynamic compound) are not verified
    here, so the word is printed as read plus the layer."""
    if len(blob) < 268:
        return "blob too short"
    layer, = struct.unpack_from("<I", blob, 240)
    motion, = struct.unpack_from("<I", blob, 264)
    return f"{MOTION_NAMES.get(motion, 'motion ' + str(motion))}(layer {layer})"


def _bounds(blob, body):
    """Bounds of body `body` only (the FO4 system can hold many bodies; objects share it and each owns one index).
    Mirrors fo4collision.decode_bodies for one body; rotated bodies and unsupported shape classes are unread (None)."""
    try:
        p = hkpackfile.Packfile(blob)
        classes = dict(p.objects())
        sysobj = next(o for o, c in classes.items() if c == "hknpPhysicsSystemData")
        at, n = p.array(sysobj + fc.SYS_BODIES)
        if at is None or not 0 <= body < n:
            return None
        b = at + fc.BODY_SIZE * body
        if any(abs(x) > 1e-4 for x in p.unpack("<4f", b + fc.BODY_ROT)[:3]):
            return None
        shape = p.pointer(b)
        cls = classes.get(shape, "?")
        if cls == "hknpCompressedMeshShape":
            pts, _ = fc._compressed_mesh(p, p.pointer(shape + fc.CMS_DATA))
        elif cls == "hknpConvexPolytopeShape":
            pts, _ = fc._convex(p, shape)
        else:
            return None
        pos = p.unpack("<3f", b + fc.BODY_POS)
        return _box([tuple(c + t for c, t in zip(v, pos)) for v in pts])
    except Exception:  # noqa: BLE001 - diagnostic: any decode failure means "unread"
        return None


def _box(pts):
    if not pts:
        return None
    return [[round(min(p[a] for p in pts), 4) for a in range(3)], [round(max(p[a] for p in pts), 4) for a in range(3)]]


def read(data):
    f = nif.parse(data)
    sf = f.bs_version >= STARFIELD_BS
    parent, world = _parents(f), nif.world_transforms(f, placed=True)
    roots = set(nif.footer_roots(f))
    seqs, notes = animated_names(f)
    animated = {n for names in seqs.values() for n in names}
    anim_blocks = {i for i in range(len(f.blocks)) if f.type_of(i).endswith("Node") and _name(f, i) in animated}
    under = set().union(*(nif.descendants(f, i) for i in anim_blocks)) if anim_blocks else set()
    has_manager = any(f.type_of(i) == "NiControllerManager" for i in range(len(f.blocks)))
    objs = []
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        target, flags, system, body = struct.unpack_from("<iHiI", f.blocks[i], 0)
        path, j = [], target
        while j in parent or j in roots or not path:
            path.append(_name(f, j) or f"block{j}")
            if j not in parent or len(path) > 64:
                break
            j = parent[j]
        o = {"collision_block": i, "target_block": target, "target": _name(f, target), "path": "/".join(reversed(path)),
             "world_position": [round(x, 4) for x in world(target)[0]] if 0 <= target < len(f.blocks) else None,
             "body_index": body, "system_block": system,
             "binding": "animated" if target in anim_blocks else "under-animated" if target in under else
                        "root" if target in roots else "static-node"}
        try:
            raw = f.blocks[system]
            blob = raw[4:4 + struct.unpack_from("<I", raw)[0]]
            if sf:
                o["motion"], o["shape"] = _sf_motion(blob), None
            else:
                o["motion"], o["shape"], o["bodies_in_system"] = _fo4_motion(blob, body)
            o["bounds_m"] = _bounds(blob, body) if not sf else None
        except Exception as e:  # noqa: BLE001 - diagnostic
            o["motion"], o["shape"], o["error"] = "unread", None, f"{type(e).__name__}: {e}"
        objs.append(o)
    by = {}
    for o in objs:
        by[o["binding"]] = by.get(o["binding"], 0) + 1
    return {"bs_version": f.bs_version, "format": "starfield" if sf else "fo4", "collision_objects": len(objs),
            "by_binding": by, "has_NiControllerManager": has_manager, "sequences": seqs, "notes": notes,
            "objects": objs,
            "reading": _reading(objs, seqs, has_manager)}


def _reading(objs, seqs, has_manager):
    if not seqs:
        return "no NiControllerSequence in this file: no clip can move any of its collision objects"
    moving = [o for o in objs if o["binding"] in ("animated", "under-animated")]
    if not moving:
        return "the file has sequences but no collision object sits on or under an animated node: a clip would leave the collision behind"
    tail = "" if has_manager else " (no NiControllerManager block: nothing plays the sequences from this file alone)"
    return f"{len(moving)} of {len(objs)} collision objects sit on or under an animated node{tail}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("nif", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = read(a.nif.read_bytes())
    if a.json:
        print(json.dumps(rep, indent=2))
        return 0
    print(f"{a.nif.name}: {rep['format']} (BS {rep['bs_version']}), {rep['collision_objects']} collision objects, "
          f"by binding {rep['by_binding']}, NiControllerManager={rep['has_NiControllerManager']}")
    for s, names in rep["sequences"].items():
        print(f"  sequence {s!r}: animates {names}")
    for n in rep["notes"]:
        print("  note:", n)
    for o in rep["objects"]:
        print(f"  coll {o['collision_block']:4} body {o['body_index']:3} sys {o['system_block']:4} {o['binding']:15} "
              f"{o['motion']:10} {o['shape'] or '-':28} {o['path']} @ {o['world_position']} bounds {o['bounds_m']}")
    print("reading:", rep["reading"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
