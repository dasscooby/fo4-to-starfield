"""Why a door's skinned shapes do not ride its rig: per skinned shape, the bones it uses (name, in the rig plan or not,
parent node), how many drawn vertices follow each bone, how many blend bones (top weight under 0.99, by bone pair), and the triangles that span
two or more bones (by bone set, with how far each pair moves relative to each other over the clips, translation in metres and rotation in
degrees): the ones that keep a shape off the rig.
Read-only; prints JSON.

  python scripts/door_skin_report.py --fo4-data <Fallout 4 Data> <mesh name, e.g. Meshes\\Interiors\\RedRocket\\Doors\\RedRPedDoor.nif>

A model whose sequences are not named Open / Close (the Vault 111 cog door VltGearDoor01.nif plays Stage2 as Open) has those sequences skipped
by the plan unless it is given the clip alias the converter uses (pipeline.OWN_RIG_ALIASES, looked up by the file name): the report still runs
without it, but its plan has no Open clip. The alias, from that table or by hand (--alias "Stage2=Open"), is what makes the plan select that
sequence as Open, as the converter's own plan does.
"""
import argparse
import itertools
import json
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import door_rig, fo4skin, nif, pipeline  # noqa: E402


def aliases_for(mesh, hand=None):
    """{FO4 sequence: Open/Close} for a model: the one named by hand (--alias), else the converter's own table by file name; None for a plain door."""
    if hand:
        out = {}
        for part in hand.split(","):
            seq, _, clip = part.partition("=")
            if clip not in ("Open", "Close") or not seq.strip():
                raise SystemExit(f"--alias {hand!r}: expected <FO4 sequence>=Open or <FO4 sequence>=Close, comma separated")
            out[seq.strip()] = clip
        return out
    return pipeline.OWN_RIG_ALIASES.get(re.split(r"[\\/]", mesh)[-1].lower())


def spanning(triangles, node_of):
    """Triangles whose drawn vertices follow more than one bone: {sorted tuple of bone nodes: triangle count}. These are what
    convert_static.rigid_skinned_parts refuses ('a triangle across two bones'): one rigid piece per bone cannot hold them together."""
    out = Counter()
    for t in triangles:
        nodes = {node_of[i] for i in t}
        if len(nodes) > 1:
            out[tuple(sorted(nodes))] += 1
    return dict(out)


def bone_poses(plan):
    """{bone node: [(translation, quaternion_wxyz, scale) in MODEL space, one per sample]} for every bone of the plan, per clip, as
    {clip name: {...}}. A bone with no track holds its bind; a bone's world pose is its parent's world pose composed with its own local
    pose (door_rig's frame: translation in source units, parent scale included). Every track of a clip is sampled at the same times."""
    q_mul, q_rot = door_rig._qmul, door_rig._qrotate
    bones = plan["bones"]
    out = {}
    for clip in plan["clips"]:
        tracks = {tr["node"]: tr["samples"] for tr in clip["tracks"]}
        count = max((len(s) for s in tracks.values()), default=1)
        world = {}
        for i, bone in enumerate(bones):
            seq = []
            for n in range(count):
                if bone.get("node") in tracks:
                    s = tracks[bone["node"]][min(n, len(tracks[bone["node"]]) - 1)]
                    lt, lq, ls = s["translation_source_units"], s["quaternion_wxyz"], s["scale"]
                else:
                    b = bone["bind"]
                    lt, lq, ls = b["translation_source_units"], b["quaternion_wxyz"], b["scale"]
                if bone["parent"] == -1:
                    seq.append((tuple(lt), tuple(lq), ls))
                else:
                    pt, pq, ps = world[bone["parent"]][n]
                    r = q_rot(pq, [ps * x for x in lt])
                    seq.append((tuple(p + x for p, x in zip(pt, r)), tuple(q_mul(pq, lq)), ps * ls))
            world[i] = seq
        out[clip["name"]] = {bone.get("node"): world[i] for i, bone in enumerate(bones) if bone.get("node") is not None}
    return out


def relative_motion(poses, a, b, unit=1.0 / 70.0):
    """How far bone b moves relative to bone a (a's own frame) over every clip, from its pose at the clip's first sample:
    {"translation_m": largest change of b's position in a's frame, "rotation_deg": largest turn of b's orientation in a's frame}, or None when
    either bone is not in the plan. Both 0 means the pair keeps one fixed pose to each other, so a triangle across them is never stretched,
    whatever each does in the world; a pair that moves apart (two sliding panels) or folds (a hinge) reads above 0, which a per-bone
    local translation cannot show. The metres are the model-space separation: the poses already carry every parent's scale, and nothing is divided
    back out (a bone 1 m along under a parent of scale 2 is 2 m of model); only the rotation of a's frame is applied."""
    t_max = r_max = 0.0
    seen = False
    for clip in poses.values():
        if a not in clip or b not in clip:
            return None
        seen = True
        rel = []
        for (ta, qa, _sa), (tb, qb, _sb) in zip(clip[a], clip[b]):
            qc = (qa[0], -qa[1], -qa[2], -qa[3])
            rel.append((tuple(door_rig._qrotate(qc, [y - x for x, y in zip(ta, tb)])), tuple(door_rig._qmul(qc, qb))))
        t0, q0 = rel[0]
        for tr, q in rel:
            t_max = max(t_max, sum((x - y) ** 2 for x, y in zip(tr, t0)) ** 0.5 * unit)
            dot = min(1.0, abs(sum(x * y for x, y in zip(q, q0))))
            r_max = max(r_max, math.degrees(2 * math.acos(dot)))
    return {"translation_m": round(t_max, 4), "rotation_deg": round(r_max, 3)} if seen else None


def report(src, aliases=None):
    plan = door_rig.animated_identity_binds(door_rig.plan(src, placed=True, aliases=aliases))
    rig = {b["node"] for b in plan["bones"] if b.get("node") is not None}
    parents = {c: n for n in range(len(src.blocks)) if src.type_of(n).endswith("Node") for c in nif.node_children(src, n)}
    animated = {t["node"] for c in plan["clips"] for t in c["tracks"]}
    poses = bone_poses(plan)

    def name(b):
        return fo4skin._block_name(src, b).decode("latin-1") if 0 <= b < len(src.blocks) else str(b)
    out = []
    for s in nif.fo4_trishapes(src):
        if not (s.skinned and s.positions and s.triangles):
            continue
        skin = fo4skin.read_skin(src, s.block)
        used = {i for t in s.triangles for i in t}
        follow, blends, node_of = Counter(), Counter(), {}
        for v in used:
            ws, ks = skin.weights[v], skin.indices[v]
            total = sum(ws) or 1.0
            top = max(range(len(ws)), key=lambda j: ws[j])
            follow[name(skin.bones[ks[top]])] += 1
            node_of[v] = skin.bones[ks[top]]
            if ws[top] / total < 0.99:
                pair = sorted({name(skin.bones[k]) for w, k in zip(ws, ks) if w > 0})
                blends[" + ".join(pair)] += 1
        out.append({"shape": (s.name or b"").decode("latin-1"), "block": s.block, "drawn_vertices": len(used),
                    "bones": [{"name": name(b), "in_rig": b in rig, "animated": b in animated,
                               "parent": name(parents[b]) if b in parents else None} for b in skin.bones],
                    "dominant_bone": dict(follow), "blended_vertices": dict(blends),
                    "spanning_triangles": [{"bones": [name(b) for b in nodes], "triangles": n,
                                            "relative_motion": [{"pair": [name(x), name(y)], **(m if (m := relative_motion(poses, x, y)) else {"not_in_rig": True})}
                                                                for x, y in itertools.combinations(nodes, 2)]}
                                           for nodes, n in sorted(spanning(s.triangles, node_of).items(), key=lambda kv: -kv[1])]})
    return {"rig_bones": [b["name"] for b in plan["bones"]], "shapes": out}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fo4-data", required=True)
    ap.add_argument("--alias", default=None, help='sequence aliases by hand, e.g. "Stage2=Open" (default: the converter\'s own table for the model)')
    ap.add_argument("mesh")
    a = ap.parse_args()
    data = pipeline.Fo4Archives(a.fo4_data).mesh(a.mesh)
    if data is None:
        sys.exit(f"{a.mesh} not in the FO4 archives")
    print(json.dumps(report(nif.parse(data), aliases_for(a.mesh, a.alias)), indent=1))


if __name__ == "__main__":
    main()
