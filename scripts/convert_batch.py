"""Convert many Fallout 4 statics straight from the game's archives into a Starfield staging folder.

usage: python convert_batch.py --fo4-data <Fallout 4 Data dir> --staging <out dir> --content-resources <ContentResources.zip>
                               --texconv <Texconvx64.exe> --collision-template <vanilla box-collision Starfield .nif>
                               [--pattern "setdressing/(chair|stool)"] [--limit 40] [--manifest manifest.json]
Writes <staging>/manifest.json: converted items (EditorID + model path for the plugin writer), failures with reasons, stats.
Needs numpy. Deterministic: names are processed in sorted order.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import convert_static, pipeline  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fo4-data", required=True)
    ap.add_argument("--staging", required=True)
    ap.add_argument("--content-resources", required=True)
    ap.add_argument("--texconv", required=True)
    ap.add_argument("--collision-template", required=True)
    ap.add_argument("--pattern", default=r"^meshes[\\/]setdressing[\\/]")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--max-tris", type=int, default=20000, help="skip meshes with more triangles than this")
    a = ap.parse_args()

    t0 = time.time()
    src = pipeline.Fo4Archives(a.fo4_data)
    template = convert_static.collision_template_from_nif(open(a.collision_template, "rb").read())
    conv = pipeline.Converter(src, a.staging, a.texconv, a.content_resources, template)
    names = src.mesh_names(a.pattern)
    print(f"{len(names)} candidate meshes; converting up to {a.limit}")
    items, failures, used = [], [], set()
    for name in names:
        if len(items) >= a.limit:
            break
        if re.search(r"(lod|_dmg|damaged|destr)", name, re.I):
            continue
        r = conv.convert_nif(name)
        if not r["ok"]:
            failures.append({"nif": name, "reason": r["reason"]})
            continue
        stem = re.sub(r"[^A-Za-z0-9_]", "_", os.path.splitext(os.path.basename(name))[0])
        eid, k = "FO4Port_" + stem, 1
        while eid in used:
            k += 1
            eid = f"FO4Port_{stem}_{k}"
        used.add(eid)
        items.append({"editor_id": eid, "model": r["out_name"].replace("/", "\\") + ".nif", "source": name,
                      "shapes": r["shapes"], "fallback_materials": r["fallback_materials"], "form_index": len(items)})
        print(f"  ok  {name} -> {eid} (shapes {r['shapes']}, fallback materials {r['fallback_materials']})")
    for f in failures[:15]:
        print("  FAIL", f["nif"], "-", f["reason"][:110])
    manifest = {"items": items, "failures": failures, "material_fallbacks": conv.material_errors, "stats": conv.stats,
                "seconds": round(time.time() - t0, 1)}
    os.makedirs(a.staging, exist_ok=True)
    json.dump(manifest, open(os.path.join(a.staging, "manifest.json"), "w"), indent=1)
    print(json.dumps({"converted": len(items), "failed": len(failures), **conv.stats, "seconds": manifest["seconds"]}))


if __name__ == "__main__":
    main()
