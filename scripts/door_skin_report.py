"""Why a door's skinned shapes do not ride its rig: per skinned shape, the bones it uses (name, in the rig plan or not,
parent node), how many drawn vertices follow each bone, and how many blend bones (top weight under 0.99, by bone pair).
Read-only; prints JSON.

  python scripts/door_skin_report.py --fo4-data <Fallout 4 Data> <mesh name, e.g. Meshes\\Interiors\\RedRocket\\Doors\\RedRPedDoor.nif>

A model whose sequences are not named Open / Close needs the clip alias the converter gives it (pipeline.OWN_RIG_ALIASES, looked up by the file
name: the Vault 111 cog door VltGearDoor01.nif plays Stage2 as Open); without it door_rig.plan refuses ("absent or ambiguous animation bindings")
and the report cannot run. --alias "Stage2=Open" names one by hand for any other model.
"""
import argparse
import json
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


def report(src, aliases=None):
    plan = door_rig.animated_identity_binds(door_rig.plan(src, placed=True, aliases=aliases))
    rig = {b["node"] for b in plan["bones"] if b.get("node") is not None}
    parents = {c: n for n in range(len(src.blocks)) if src.type_of(n).endswith("Node") for c in nif.node_children(src, n)}
    animated = {t["node"] for c in plan["clips"] for t in c["tracks"]}

    def name(b):
        return fo4skin._block_name(src, b).decode("latin-1") if 0 <= b < len(src.blocks) else str(b)
    out = []
    for s in nif.fo4_trishapes(src):
        if not (s.skinned and s.positions and s.triangles):
            continue
        skin = fo4skin.read_skin(src, s.block)
        used = {i for t in s.triangles for i in t}
        follow, blends = Counter(), Counter()
        for v in used:
            ws, ks = skin.weights[v], skin.indices[v]
            total = sum(ws) or 1.0
            top = max(range(len(ws)), key=lambda j: ws[j])
            follow[name(skin.bones[ks[top]])] += 1
            if ws[top] / total < 0.99:
                pair = sorted({name(skin.bones[k]) for w, k in zip(ws, ks) if w > 0})
                blends[" + ".join(pair)] += 1
        out.append({"shape": (s.name or b"").decode("latin-1"), "block": s.block, "drawn_vertices": len(used),
                    "bones": [{"name": name(b), "in_rig": b in rig, "animated": b in animated,
                               "parent": name(parents[b]) if b in parents else None} for b in skin.bones],
                    "dominant_bone": dict(follow), "blended_vertices": dict(blends)})
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
