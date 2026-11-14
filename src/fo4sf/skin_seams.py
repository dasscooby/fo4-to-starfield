"""Seams of a skinned shape whose vertices follow different bones: which triangles span bones, how far each pair of bones moves relative to the
other over a clip, and how far vertices land from FO4's skinning when one bone carries a whole set rigidly (FAL-489, the Vault 111 cog door's
catwalk). Pure functions over a door_rig plan and fo4skin data; scripts/door_skin_report.py prints them, convert_static.rigid_skinned_parts
uses them to choose the bone a spanning triangle rides."""
import math
from collections import Counter

from . import door_rig, fo4skin


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


def _world_point(pose, point):
    """A point already in the bone's own space, placed by the bone's model-space pose (translation, quaternion_wxyz, scale)."""
    t, q, s = pose
    r = door_rig._qrotate(q, [s * c for c in point])
    return tuple(a + b for a, b in zip(t, r))


def rigid_error_m(poses, moved, x_node, x_skin, unit=1.0 / 70.0):
    """How far, in metres, vertices end up from where FO4's skinning puts them when they are carried rigidly by bone x_node instead of
    by their own bone: the farthest any of them gets over every clip sample, as {"max_m", "vertices_moved"}, or None when a bone is not in
    the plan. moved: [(own bone node, its skin_to_bone transform, the stored position)] for the vertices that follow another bone;
    x_skin: x_node's skin_to_bone. FO4 puts a vertex at pose(own bone) * skin_to_bone(own) * p; rigid on x_node it is at
    pose(x_node) * skin_to_bone(x_node) * p (convert_static.rigid_skinned_parts keeps skin_to_bone(x) * p as the piece's local position).
    Both bones' poses carry their parents' motion, so the lever arm, the pivot's place and every parent's turn are all in the number."""
    worst = 0.0
    for clip in poses.values():
        if x_node not in clip or any(y not in clip for y, _, _ in moved):
            return None
        for n in range(len(clip[x_node])):
            for y, s_y, p in moved:
                a = _world_point(clip[y][n], fo4skin.apply(s_y, p))
                b = _world_point(clip[x_node][n], fo4skin.apply(x_skin, p))
                worst = max(worst, sum((u - v) ** 2 for u, v in zip(a, b)) ** 0.5 * unit)
    return {"max_m": round(worst, 4), "vertices_moved": len(moved)}
