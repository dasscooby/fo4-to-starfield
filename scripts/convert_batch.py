"""Convert many Fallout 4 statics straight from the game's archives into a Starfield staging folder.

usage: python convert_batch.py --fo4-data <Fallout 4 Data dir> --staging <out dir> --content-resources <ContentResources.zip>
                               --texconv <Texconvx64.exe> --collision-template <vanilla box-collision Starfield .nif>
                               [--pattern "setdressing/(chair|stool)"] [--limit 40] [--manifest manifest.json]
Writes <staging>/manifest.json: converted items (EditorID + model path for the plugin writer), failures with reasons, stats.
Needs numpy. Deterministic: names are processed in sorted order.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import ba2, checkpoints, convert_static, meshcollision, pipeline, sfcollision, sfnif  # noqa: E402


def checkpoint_signature(a):
    import importlib.metadata
    from pathlib import Path
    archives = sorted(p for p in Path(a.fo4_data).iterdir()
                      if p.name.lower().startswith("fallout4 - ") and p.suffix.lower() == ".ba2")
    if a.starfield_data:
        archives.append(Path(a.starfield_data) / "Starfield - Meshes01.ba2")
    code = sorted(Path(__file__).resolve().parents[1].joinpath("src", "fo4sf").glob("*.py")) + [Path(__file__)]
    packages = {}
    for name in ("numpy", "Pillow"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"version": 1, "python": sys.version, "packages": packages,
            "archives": [checkpoints.archive_identity(p) for p in archives],
            "content": {str(p.resolve()): checkpoints.digest(p) for p in
                        [*code, Path(a.texconv), Path(a.content_resources), Path(a.collision_template)]},
            "rig_doors": bool(a.starfield_data), "movable_items": bool(a.starfield_data) and not a.static_items}


def source_identity(source):
    return source.replace("\\", "/").lower()


def load_editor_ids(staging):
    path = os.path.join(staging, "editorids.json")
    ids = {}
    def adopt(source, value):
        if not isinstance(source, str) or not source or not isinstance(value, str) or not value:
            raise ValueError("source and editor ID must be nonempty strings")
        key = source_identity(source)
        if key in ids and ids[key] != value:
            raise ValueError(f"conflicting editor ID for {key}")
        ids[key] = value

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            mapping = json.load(f)
        if not isinstance(mapping, dict):
            raise ValueError("persistent source mapping must be an object")
        for source, value in mapping.items():
            adopt(source, value)
    # Adopt existing plugin names rather than renaming deployed records on upgrade.
    manifest = os.path.join(staging, "manifest.json")
    if os.path.exists(manifest):
        with open(manifest, encoding="utf-8") as f:
            for item in json.load(f)["items"]:
                adopt(item["source"], item["editor_id"])
    if len({v.lower() for v in ids.values()}) != len(ids):
        raise ValueError("duplicate editor IDs in persistent source mapping")
    return ids


def editor_id(source, ids):
    key = source_identity(source)
    if key not in ids:
        basename = key.rsplit("/", 1)[-1]
        stem = re.sub(r"[^A-Za-z0-9_]", "_", os.path.splitext(basename)[0])
        name = "FO4Port_" + stem
        reserved = {v.lower() for v in ids.values()}
        if name.lower() in reserved:
            name += "_" + hashlib.sha256(key.encode()).hexdigest()[:16]
        if name.lower() in reserved:
            raise ValueError(f"editor ID collision for {key}")
        ids[key] = name
    return ids[key]


def write_json_atomic(path, value):
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".fo4port-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fo4-data", required=True)
    ap.add_argument("--staging", required=True)
    ap.add_argument("--content-resources", required=True)
    ap.add_argument("--texconv", required=True)
    ap.add_argument("--collision-template", required=True)
    ap.add_argument("--starfield-data", default="",
                    help="Starfield Data folder: enables opening doors (needs the vanilla door body as a keyframed donor)")
    ap.add_argument("--static-items", action="store_true",
                    help="keep FO4 loose items fixed (default with --starfield-data: movable, as in FO4)")
    ap.add_argument("--resume", action="store_true", help="reuse content-verified per-model checkpoints")
    ap.add_argument("--pattern", default=r"^meshes[\\/]setdressing[\\/]")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--max-tris", type=int, default=20000, help="skip meshes with more triangles than this")
    ap.add_argument("--cell-json", default="", help="convert the models placed in a cell exported by dotnet/Fo4Export")
    ap.add_argument("--types", default="Static,StaticCollection,MovableStatic,Furniture,Door,Activator,Container,MiscItem,Terminal",
                    help="base record types to take from --cell-json")
    a = ap.parse_args()

    ids = load_editor_ids(a.staging)

    t0 = time.time()
    src = pipeline.Fo4Archives(a.fo4_data)
    with open(a.collision_template, "rb") as f:
        template = convert_static.collision_template_from_nif(f.read())
    donor = None
    if a.starfield_data:                          # opening doors: leaf body copied from a vanilla animated door
        donor = sfcollision.physics_blob_from_nif(ba2.Ba2(os.path.join(a.starfield_data, "Starfield - Meshes01.ba2")).read(
            sfnif.DOOR_TEMPLATE["nif"]))
    mesh_template = None
    if a.starfield_data:                          # FO4's own collision meshes, transplanted into a vanilla container
        mesh_template = meshcollision.template_from_nif(ba2.Ba2(os.path.join(a.starfield_data, "Starfield - Meshes01.ba2")).read(
            meshcollision.UNIVERSAL_TEMPLATE_NIF))
    dynamic_template = None
    if a.starfield_data and not a.static_items:   # FO4 loose items movable: built on a vanilla dynamic item's body
        dynamic_template = meshcollision.check_dynamic_template(meshcollision.template_from_nif(
            ba2.Ba2(os.path.join(a.starfield_data, "Starfield - Meshes01.ba2")).read(meshcollision.DYNAMIC_TEMPLATE_NIF)))
    cache =checkpoints.Checkpoints(a.staging, checkpoint_signature(a)) if a.resume else None
    conv = None
    if a.cell_json:
        with open(a.cell_json, encoding="utf-8-sig") as f:
            cell = json.load(f)
        wanted = set(a.types.split(","))
        names = sorted({"meshes\\" + r["model"].lstrip("\\") for r in cell["refs"] if r["model"] and r["type"] in wanted
                        and not re.search(r"marker|^\\?effects[\\/]", r["model"], re.I)},   # editor markers, fog/light volumes
                       key=str.lower)
    else:
        names = src.mesh_names(a.pattern)
    print(f"{len(names)} candidate meshes; converting up to {a.limit}")
    os.makedirs(a.staging, exist_ok=True)
    state_path = os.path.join(a.staging, "build-state.json")
    write_json_atomic(state_path, {"complete": False, "status": "converting"})
    items, failures, reused = [], [], 0
    for name in names:
        if len(items) >= a.limit:
            break
        if not a.cell_json and re.search(r"(lod|_dmg|damaged|destr)", name, re.I):
            continue
        r = cache.load(name) if cache else None
        if r is not None:
            reused += 1
        else:
            if conv is None:
                conv = pipeline.Converter(src, a.staging, a.texconv, a.content_resources, template,
                                          rig_doors=donor is not None, door_physics_donor=donor,
                                          sf_mesh_template=mesh_template, dynamic_template=dynamic_template)
            r = conv.convert_nif(name)
            if cache:
                try:
                    cache.save(name, r)
                except (OSError, ValueError) as e:
                    print(f"  checkpoint unavailable for {name}: {e}")
        if not r["ok"]:
            failures.append({"nif": name, "reason": r["reason"]})
            continue
        eid = editor_id(name, ids)
        if cache:
            os.makedirs(a.staging, exist_ok=True)
            write_json_atomic(os.path.join(a.staging, "editorids.json"), ids)
        items.append({"editor_id": eid, "model": r["out_name"].replace("/", "\\") + ".nif", "source": name,
                      "shapes": r["shapes"], "fallback_materials": r["fallback_materials"], "form_index": len(items),
                      "collision_report": r.get("collision_report") or {}, **({"door": r["door"]} if "door" in r else {}),
                      **({"load_door": r["load_door"]} if "load_door" in r else {}),
                      **({"movable": r["movable"]} if "movable" in r else {}),
                      **({"door_not_opening": r["door_not_opening"]} if "door_not_opening" in r else {})})
        print(f"  ok  {name} -> {eid} (shapes {r['shapes']}, fallback materials {r['fallback_materials']})")
    for f in failures[:15]:
        print("  FAIL", f["nif"], "-", f["reason"][:110])
    if cache:
        inconsistent = cache.verify_batch()
        if inconsistent:
            write_json_atomic(state_path, {"complete": False, "status": "dependency_conflict", "errors": inconsistent})
            raise RuntimeError(f"{len(inconsistent)} generated dependencies changed after model conversion; build not deployable")
    stats = dict(conv.stats) if conv else {"materials_ok": 0, "materials_fallback": 0}
    stats.update(assets=len(items), failed=len(failures), reused=reused)
    manifest = {"items": items, "failures": failures, "material_fallbacks": conv.material_errors if conv else {}, "stats": stats,
                "seconds": round(time.time() - t0, 1)}
    os.makedirs(a.staging, exist_ok=True)
    write_json_atomic(os.path.join(a.staging, "editorids.json"), ids)
    write_json_atomic(os.path.join(a.staging, "manifest.json"), manifest)
    write_json_atomic(state_path, {"complete": True, "status": "finished", "assets": len(items), "failed": len(failures)})
    print(json.dumps({"converted": len(items), **stats, "seconds": manifest["seconds"]}))


if __name__ == "__main__":
    main()
