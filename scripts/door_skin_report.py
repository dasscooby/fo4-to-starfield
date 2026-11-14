"""Why a door's skinned shapes do not ride its rig: per skinned shape, the bones it uses (name, in the rig plan or not,
parent node), how many drawn vertices follow each bone, how many blend bones (top weight under 0.99, by bone pair), and the triangles that span
two or more bones (by bone set, with how far each pair moves relative to each other over the clips, translation in metres and rotation in
degrees, and rigid_error_m: how far from FO4's skinning the set's vertices end if the whole set rides one bone, per candidate bone): the
ones that keep a shape off the rig.
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
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import door_rig, fo4skin, nif, pipeline  # noqa: E402
from fo4sf.skin_seams import _world_point, bone_poses, relative_motion, rigid_error_m, spanning  # noqa: E402,F401


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


def _rigid_choices(poses, skin, shape, nodes, node_of, slot_of, name):
    """For one set of spanning bones: {bone name: rigid_error_m(...)} for putting every triangle of the set on that bone. The vertices that
    move are those of the set's triangles that follow another bone; a bone with two slots of different skin_to_bone is read through its first
    slot (not distinguished here)."""
    tris = [t for t in shape.triangles if {node_of[i] for i in t} == set(nodes)]
    verts = sorted({i for t in tris for i in t})
    first_slot = {}
    for k, b in enumerate(skin.bones):
        first_slot.setdefault(b, k)
    out = {}
    for x in nodes:
        moved = [(node_of[v], skin.skin_to_bone[slot_of[v]], shape.positions[v]) for v in verts if node_of[v] != x]
        out[name(x)] = rigid_error_m(poses, moved, x, skin.skin_to_bone[first_slot[x]])
    return out


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
        follow, blends, node_of, slot_of = Counter(), Counter(), {}, {}
        for v in used:
            ws, ks = skin.weights[v], skin.indices[v]
            total = sum(ws) or 1.0
            top = max(range(len(ws)), key=lambda j: ws[j])
            follow[name(skin.bones[ks[top]])] += 1
            node_of[v] = skin.bones[ks[top]]
            slot_of[v] = ks[top]
            if ws[top] / total < 0.99:
                pair = sorted({name(skin.bones[k]) for w, k in zip(ws, ks) if w > 0})
                blends[" + ".join(pair)] += 1
        out.append({"shape": (s.name or b"").decode("latin-1"), "block": s.block, "drawn_vertices": len(used),
                    "bones": [{"name": name(b), "in_rig": b in rig, "animated": b in animated,
                               "parent": name(parents[b]) if b in parents else None} for b in skin.bones],
                    "dominant_bone": dict(follow), "blended_vertices": dict(blends),
                    "spanning_triangles": [dict(
                        {"bones": [name(b) for b in nodes], "triangles": n,
                         "relative_motion": [{"pair": [name(x), name(y)], **(m if (m := relative_motion(poses, x, y)) else {"not_in_rig": True})}
                                             for x, y in itertools.combinations(nodes, 2)]},
                        rigid_error_m=_rigid_choices(poses, skin, s, nodes, node_of, slot_of, name))
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
