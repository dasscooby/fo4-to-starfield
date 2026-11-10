"""core64c: every Fallout 4 exterior object of the 64 x 64-cell core on the core64 terrain (docs/terrain/core64c.md).

    dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-exterior Commonwealth -55 <y0> 54 <y0+9> <work>/export/band_<y0>_<y0+9>.json
           (11 bands, y0 = -55, -45, ..., 45: one band at a time keeps the exporter's memory small)
    python scripts/terrain/make_core64c.py select  --work <work> --core <terrain_core64>
    python scripts/terrain/make_core64c.py measure --work <work> --fo4-data <FO4 Data>
    python scripts/convert_batch.py --cell-json <work>/convert_input.json --staging <work>/convert --prefix fo4core
           --max-texture <cap> --types <printed by select> --limit 1000000 --resume  + the usual converter arguments
    python scripts/terrain/make_core64c.py stage --work <work> --core <terrain_core64> --out <terrain_core64c> --sf-esm <Starfield.esm>
           [--views] [--cluster <cluster.json: "containers", "items", "activators", "terminals", "workshops", "flora",
           "benches", "lights", "doors">] [--navmesh <navmesh.json>] [--fo4-map-markers <Fo4Land export-mapmarkers json>]
    python scripts/terrain/make_core64c.py check --work <work> --core <terrain_core64> --out <terrain_core64c>
           [--fo4 <Fallout4.esm>] [--fo4-data <FO4 Data>] [--sf-data <Starfield Data>]
    python scripts/terrain/make_core64c.py verify-data --out <terrain_core64c>

select   reads every export band, classifies every reference (exterior.select: convert, or skip with a reason, never
         silently) and writes selected.json (the references to place, slimmed to the fields placing needs),
         convert_input.json (one entry per model: all convert_batch needs) and selection.json (counts, skipped refs).
measure  before converting: models, materials and textures the converter would write (a dry run of its material
         logic over the FO4 archives' DDS headers: no texture is decoded), their size at full resolution and under
         texture caps, the mesh size (from the source NIF sizes) and the references per region; measure.json.
stage    places the converted references (exterior.place) in the core64 worldspace, hard-links the converted files
         into Data\\ (no second copy), copies core64's Data files (BTD, its meshes\\terrain copy, mask), writes
         objects.json and builds FO4TerrainCore.esm + FO4TerrainCore_Mars.esm with dotnet/TerrainOverlays (objects
         after every core64 record: core64's FormIDs do not move, the Mars plugin stays byte-identical), and plan.json:
         core64's probes within 500 m of the arrival re-judged with the objects, object tops at three familiar places
         (each dropped on twice), with --views screenshot spots, and open terrain waypoints so that no teleport moves
         the player more than 2 cells along an axis (build_plan).
check    raw-walks the plugin (core64 records unchanged, REFRs per cell, bases, positions), object z - terrain z under
         every placed origin (BTD; with --fo4 also FO4's own LAND), every model / geometry / material / texture file,
         every plan point re-derived from the converted collision, every runner teleport (cells per axis) and the
         step time, archive size; offline_check.json, and data_manifest.json (size and time of every staged file).
verify-data  is the staged tree still the one check passed? (Data\\ is hard-linked to the conversion work folder.)
Everything this writes stays outside the repo (derived game data).
"""
import argparse
import glob
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import struct
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import btd, exterior, map_markers  # noqa: E402
from fo4sf import terrain_grid as tg  # noqa: E402

sys.path.insert(0, HERE)
import make_exp2c as x2c  # noqa: E402
import overlay_records  # noqa: E402
import vmad_patch  # noqa: E402

EDID_PREFIX = "FO4Core_"
ASSET_PREFIX = "fo4core"
DATA_TREES = ("meshes", "geometries", "materials", "textures")
# fields of an exported reference that placing, reporting and the plan need (the export has about 25)
SLIM_KEYS = ("formkey", "type", "base_editor_id", "base_formkey", "model", "pos", "rot", "scale", "disabled",
             "persistent", "exterior_cell", "open_by_default")
# Every large vanilla Starfield archive stops just below 4 GiB (Starfield - Textures02, Meshes01, Voices01, ...:
# 4,294,061,043 to 4,294,946,755 bytes, never more; read-only directory listing, 2026-10-11): Bethesda's own archives
# split at 2^32 bytes. Whether the engine reads an archive beyond 4 GiB is unresolved, so one archive stays below it.
ARCHIVE_LIMIT = 2 ** 32
ARCHIVE_BUDGET = int(3.8 * 2 ** 30)       # what the staged Data tree may hold (headroom for the archive's own tables)
REGION_CELLS = 16                         # report references per 16 x 16 Starfield cells (1.6 km)


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save(path, value, indent=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=indent)
    os.replace(tmp, path)


def core_params(core):
    """(overlays_params.json, its single overlay) of the staged core64 terrain."""
    prm = load(os.path.join(core, "overlays_params.json"))
    if len(prm["overlays"]) != 1:
        sys.exit(f"{core}: core64c needs exactly one overlay, found {len(prm['overlays'])}")
    return prm, prm["overlays"][0]


def core_params_view(prm):
    """core64c's overlays_params.json without what stage adds to core64's: objects, navmesh, world_data, each overlay's
    map_markers (check compares the rest with core64's)."""
    out = {k: v for k, v in prm.items() if k not in ("objects", "navmesh", "world_data")}
    if "overlays" in out:
        out["overlays"] = [{k: v for k, v in o.items() if k != "map_markers"} for o in out["overlays"]]
    return out


def slim(ref):
    out = {k: ref.get(k) for k in SLIM_KEYS}
    out["enable_parent"] = ref.get("enable_parent")
    if ref.get("type") == "Door" and ref.get("teleport_destination"):
        out["teleports"] = True                    # a load door: convert_list converts its model as one
    return out


def region_of(cell, size=REGION_CELLS):
    return int(math.floor(cell[0] / size)), int(math.floor(cell[1] / size))


# ------------------------------------------------------------------------------------------------------------- select
def select_bands(paths):
    """Every export band through exterior.select: (kept slim references, skipped entries, totals)."""
    kept, skipped = [], []
    tot = {"bands": 0, "cells": 0, "refs": 0, "deferred": 0}
    seen = set()
    for p in paths:
        export = load(p)
        tot["bands"] += 1
        tot["cells"] += len((export.get("exterior") or {}).get("cells") or [])
        tot["refs"] += len(export["refs"])
        tot["deferred"] += len(export.get("deferred_refs", []))
        sub, skip = exterior.select(export)
        for r in sub["refs"]:
            if r["formkey"] in seen:
                raise ValueError(f"{r['formkey']} exported twice (overlapping bands?)")
            seen.add(r["formkey"])
            kept.append(slim(r))
        skipped += skip
        del export, sub
    return kept, skipped, tot


ITEM_TYPES = ("MiscItem", "Ingestible", "Weapon")     # make_cluster.ITEM_TYPES: the references the core places as MISC


def convert_list(kept):
    """One entry per model (convert_batch --cell-json reads "model", "type" and "teleport_destination"). A model FO4
    places anywhere as a teleporting Door (slim "teleports") carries teleport_destination true, so convert_batch converts it as a load door:
    solid, with its own collision for the activation prompt, never a passable animated door (Fort Hagen's and Vault 95's
    elevator entrances could not be used from outside, owner 2026-10-18; confirmed by door_audit.py). A model no reference
    places as an item (ITEM_TYPES: the core's MISC pickups) carries static_body true: the core places it as a STAT, so it
    keeps a static body (v6: 62 models, 6,128 references such as cars, skeletons and cones got dynamic compounds once
    --static-items was dropped; a STAT that falls or slides at cell load would be a regression)."""
    by_model, items = {}, {}
    for r in kept:
        e = by_model.setdefault(exterior.source_key(r["model"]), {"model": r["model"], "type": r["type"],
                                                                   "formkey": r["formkey"]})
        if r.get("teleports"):
            e.update(type="Door", teleport_destination=True)
        items.setdefault(exterior.source_key(r["model"]), False)
        if r["type"] in ITEM_TYPES:
            items[exterior.source_key(r["model"])] = True
    for k, e in by_model.items():
        if not items[k]:
            e["static_body"] = True
    return [by_model[k] for k in sorted(by_model)]


def cmd_select(a):
    t0 = time.time()
    paths = sorted(glob.glob(os.path.join(a.work, "export", "band_*.json")))
    if not paths:
        sys.exit(f"no export bands in {os.path.join(a.work, 'export')}")
    kept, skipped, tot = select_bands(paths)
    _prm, ov = core_params(a.core)
    cmin, cmax = ov["cell_min"], ov["cell_max"]
    regions, cells = {}, {}
    for r in kept:
        c = tg.sf_cell_of(r["pos"][0] / exterior.UNITS_PER_METRE, r["pos"][1] / exterior.UNITS_PER_METRE)
        cells[c] = cells.get(c, 0) + 1
        g = region_of(c)
        regions[g] = regions.get(g, 0) + 1
    models = convert_list(kept)
    save(os.path.join(a.work, "selected.json"), {"core": os.path.abspath(a.core), "refs": kept})
    save(os.path.join(a.work, "convert_input.json"), {"schema_version": 2, "cell": "core64c", "refs": models})
    rep = {"bands": [os.path.basename(p) for p in paths], **tot, "to_convert": len(kept), "models": len(models),
           "skipped": len(skipped), "skip_reasons": exterior.reason_counts(skipped),
           "skip_types": type_counts(skipped), "convert_types": list(exterior.CONVERT_TYPES),
           "sf_cells_with_refs": len(cells), "refs_per_sf_cell_max": max(cells.values()) if cells else 0,
           "densest_sf_cells": [[list(c), n] for c, n in sorted(cells.items(), key=lambda kv: -kv[1])[:10]],
           "outside_core_cells": sum(n for c, n in cells.items() if not (cmin <= c[0] <= cmax and cmin <= c[1] <= cmax)),
           "in_mask_ring": sum(n for c, n in cells.items() if cmin <= c[0] <= cmax and cmin <= c[1] <= cmax
                               and (c[0] in (cmin, cmax) or c[1] in (cmin, cmax))),
           "regions": {f"{g[0]},{g[1]}": n for g, n in sorted(regions.items())}, "region_cells": REGION_CELLS,
           "seconds": round(time.time() - t0, 1), "skipped_refs": skipped}
    save(os.path.join(a.work, "selection.json"), rep)
    print(f"{rep['refs']:,} references + {rep['deferred']:,} deferred in {rep['cells']:,} FO4 cells: convert "
          f"{rep['to_convert']:,} ({rep['models']:,} models), skip {rep['skipped']:,}: {rep['skip_reasons']}")
    print(f"Starfield cells with references {rep['sf_cells_with_refs']}, max {rep['refs_per_sf_cell_max']} per cell; "
          f"outside the core {rep['outside_core_cells']}, in the mask ring {rep['in_mask_ring']}; {rep['seconds']} s")
    print("convert_batch --types " + ",".join(exterior.CONVERT_TYPES))
    return 0


def type_counts(skipped):
    out = {}
    for s in skipped:
        k = f"{s['reason']}:{s.get('type')}"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------------------------------------------------ measure
BC_BYTES_PER_BLOCK = {"BC1": 8, "BC4": 8, "BC5": 16}


def bc_size(fmt, width, height, cap=0):
    """Bytes of a block-compressed DDS (DX10 header, 148 B) with texconv's full mip chain (floor(log2(max side)) + 1
    levels), top levels dropped until both sides are at most `cap` (0 = no cap), exactly as textures.cap_dds does."""
    w, h = max(1, int(width)), max(1, int(height))
    n = max(w, h).bit_length()
    drop = 0
    while cap and max(max(1, w >> drop), max(1, h >> drop)) > cap and drop < n - 1:
        drop += 1
    bb = BC_BYTES_PER_BLOCK[fmt]
    return 148 + sum(max(1, (max(1, w >> i) + 3) // 4) * max(1, (max(1, h >> i) + 3) // 4) * bb for i in range(drop, n))


class DryConverter:
    """The converter's material decisions (pipeline.Converter._shape_material: BGSM, blended decal, texture set,
    effect glass / grime decal, neutral) without converting anything: _convert_texture_set / _convert_glass record
    which outputs a material would get (format, source dimensions read from the archive's DX10 records)."""

    def __init__(self, src):
        from fo4sf import pipeline
        self.pipeline = pipeline
        conv = pipeline.Converter.__new__(pipeline.Converter)    # no texconv, no template, no neutral material
        conv.src, conv.prefix, conv._materials, conv._blend_cache = src, ASSET_PREFIX, {}, {}
        conv.stats = {"assets": 0, "failed": 0, "materials_ok": 0, "materials_fallback": 0}
        conv.material_errors = {}
        conv.neutral = "materials\\neutral.mat"
        conv._convert_texture_set = self._texture_set
        conv._convert_glass = self._glass
        self.conv, self.src = conv, src
        self.outputs = {}                                        # material stem -> [(kind, fmt, w, h)]
        self.mat_stem = {}                                       # material path the shapes get -> stem
        self.dims_cache = {}

    def dims(self, name):
        n = name.replace("\\", "/").lstrip("/")
        n = n if n.lower().startswith("textures/") else "textures/" + n
        if n.lower() not in self.dims_cache:
            got = None
            for a in self.src.textures:
                i = a.find(n)
                if i is not None:
                    e = a.entries[i]
                    got = (e.width, e.height)
                    break
            self.dims_cache[n.lower()] = got
        return self.dims_cache[n.lower()]

    def _texture_set(self, stem, diffuse, normal, spec, smoothness=1.0, spec_mult=1.0, alpha_test=False,
                     alpha_ref=128, decal=False, greyscale=None, palette_scale=1.0, two_sided=False,
                     opacity_scale=1.0):
        d = self.dims(diffuse)
        n = self.dims(normal) if normal else None
        s = self.dims(spec) if spec else None
        if d is None or (n is None and not decal):
            raise FileNotFoundError("diffuse or normal texture missing from archives")
        nd = n or (4, 4)
        out = [("color", "BC1", *d), ("normal", "BC5", *nd),
               ("rough", "BC4", *(s if s else (max(4, nd[0] // 4), max(4, nd[1] // 4))))]
        if alpha_test or decal:
            out.append(("opacity", "BC4", *d))                   # upper bound: only when the alpha really cuts out
        self.outputs[stem] = out
        return self._mat(stem)

    def _mat(self, stem):
        path = f"materials\\{ASSET_PREFIX}\\{stem}.mat"
        self.mat_stem[path] = stem
        return path

    def _glass(self, base, normal):
        d = self.dims(base) if base else None
        if d is None:
            raise FileNotFoundError("glass base texture missing")
        n = self.dims(normal) if normal else None
        stem = "glass/" + base.lower() + "|" + (normal or "").lower()
        self.outputs[stem] = [("color", "BC1", *d)] + ([("normal", "BC5", *n)] if n else []) + [("rough", "BC4", 16, 16)]
        return self._mat(stem)

    def model(self, name):
        """(ok, reason, materials used) for one model, by the converter's own shape and material logic."""
        from fo4sf import nif
        raw = self.src.mesh(name)
        if raw is None:
            return False, "not in the mesh archives", []
        try:
            src = nif.parse(raw)
            shapes = [s for s in nif.fo4_trishapes(src) if s.positions and s.triangles]
        except Exception as e:                                   # noqa: BLE001  (the converter fails it the same way)
            return False, f"{type(e).__name__}: {e}", []
        if not shapes:
            return False, "no static BSTriShape geometry", []
        mats = [self.conv._shape_material(src, s) for s in shapes]
        if all(m is None for m in mats):
            return False, "only effect-shader shapes", []
        return True, "", sorted({m for m in mats if m})


def mesh_entry_size(src, name):
    for a in src.meshes:
        i = a.find(name)
        if i is not None:
            return a.entries[i].unpacked or a.entries[i].packed
    return 0


def cmd_measure(a):
    from fo4sf import pipeline
    t0 = time.time()
    src = pipeline.Fo4Archives(a.fo4_data)
    models = load(os.path.join(a.work, "convert_input.json"))["refs"]
    sel = load(os.path.join(a.work, "selection.json"))
    dry = DryConverter(src)
    ok, failed, mats_of, nif_bytes = [], {}, {}, 0
    for k, m in enumerate(models):
        name = exterior.source_key(m["model"])
        good, why, mats = dry.model(name)
        if good:
            ok.append(name)
            mats_of[name] = mats
            nif_bytes += mesh_entry_size(src, name)
        else:
            failed[name] = why
        if (k + 1) % 2000 == 0:
            print(f"  {k + 1:,} / {len(models):,} models, {len(dry.outputs):,} texture sets, {time.time() - t0:.0f} s",
                  flush=True)
    caps = [int(c) for c in a.caps.split(",") if c.strip()]
    tex = {"materials": len(dry.outputs), "textures": sum(len(v) for v in dry.outputs.values()),
           "by_kind": {}, "full_bytes": 0, "capped_bytes": {str(c): 0 for c in caps}, "max_side": {}}
    for outs in dry.outputs.values():
        for kind, fmt, w, h in outs:
            full = bc_size(fmt, w, h)
            k = tex["by_kind"].setdefault(kind, {"count": 0, "full_bytes": 0})
            k["count"] += 1
            k["full_bytes"] += full
            tex["full_bytes"] += full
            side = str(max(w, h))
            tex["max_side"][side] = tex["max_side"].get(side, 0) + 1
            for c in caps:
                tex["capped_bytes"][str(c)] += bc_size(fmt, w, h, cap=c)
    tex["max_side"] = dict(sorted(tex["max_side"].items(), key=lambda kv: int(kv[0])))
    from fo4sf import textures as tx
    tex["kind_caps"] = {}
    for spec in (x for x in a.kind_caps.split(";") if x.strip()):
        kc = tx.parse_texture_caps(spec)
        tex["kind_caps"][spec] = sum(bc_size(f, w, h, cap=kc.get(k, 0)) for outs in dry.outputs.values()
                                     for k, f, w, h in outs)
    # mesh output size: converted .nif + .mesh bytes per source NIF byte, from a finished conversion (exp2c) if given
    ratio = None
    if a.calibrate and os.path.isfile(os.path.join(a.calibrate, "manifest.json")):
        man = load(os.path.join(a.calibrate, "manifest.json"))
        src_b = sum(mesh_entry_size(src, i["source"]) for i in man["items"])
        out_b = sum(os.path.getsize(os.path.join(r, f)) for t in ("meshes", "geometries")
                    for r, _d, fs in os.walk(os.path.join(a.calibrate, t)) for f in fs)
        ratio = out_b / src_b if src_b else None
    mesh_est = int(nif_bytes * ratio) if ratio else None
    # a split by region (REGION_CELLS x REGION_CELLS Starfield cells, each with its own archive) at full resolution:
    # every region archive needs the textures of every material its models use, so shared materials repeat
    mat_bytes = {st: sum(bc_size(f, w, h) for _k, f, w, h in outs) for st, outs in dry.outputs.items()}
    nif_size = {n: mesh_entry_size(src, n) for n in ok}
    regions = {}
    for r in load(os.path.join(a.work, "selected.json"))["refs"]:
        name = exterior.source_key(r["model"])
        if name not in mats_of:
            continue
        g = region_of(tg.sf_cell_of(r["pos"][0] / exterior.UNITS_PER_METRE, r["pos"][1] / exterior.UNITS_PER_METRE))
        regions.setdefault(g, {"refs": 0, "models": set()})
        regions[g]["refs"] += 1
        regions[g]["models"].add(name)
    split = {}
    for g, v in sorted(regions.items()):
        stems = {dry.mat_stem[m] for n in v["models"] for m in mats_of[n] if m in dry.mat_stem}
        tb = sum(mat_bytes[st] for st in stems)
        mb = int(sum(nif_size[n] for n in v["models"]) * (ratio or 0))
        split[f"{g[0]},{g[1]}"] = {"refs": v["refs"], "models": len(v["models"]), "materials": len(stems),
                                   "texture_bytes_full": tb, "mesh_bytes_estimate": mb, "archive_estimate": tb + mb}
    rep = {"region_split_full_resolution": {
               "region_cells": REGION_CELLS, "regions": split,
               "sum_bytes": sum(v["archive_estimate"] for v in split.values()),
               "largest_region_bytes": max(v["archive_estimate"] for v in split.values()),
               "regions_over_budget": sum(1 for v in split.values() if v["archive_estimate"] > ARCHIVE_BUDGET)},
           "references": sel["refs"] + sel["deferred"], "to_convert_refs": sel["to_convert"], "models": len(models),
           "models_converting": len(ok), "models_failing": len(failed), "failing": failed, "textures": tex,
           "source_nif_bytes": nif_bytes, "mesh_bytes_per_source_byte": ratio, "mesh_bytes_estimate": mesh_est,
           "archive_limit": ARCHIVE_LIMIT, "archive_budget": ARCHIVE_BUDGET,
           "seconds": round(time.time() - t0, 1)}
    rep["data_estimate"] = {"full": tex["full_bytes"] + (mesh_est or 0),
                            **{f"cap_{c}": tex["capped_bytes"][str(c)] + (mesh_est or 0) for c in caps}}
    fits = [c for c in caps if rep["data_estimate"][f"cap_{c}"] <= ARCHIVE_BUDGET]
    rep["largest_cap_within_budget"] = max(fits) if fits else None
    save(os.path.join(a.work, "measure.json"), rep, indent=1)
    gib = 2 ** 30
    print(f"{len(models):,} models: {len(ok):,} convert, {len(failed):,} fail; {tex['materials']:,} materials, "
          f"{tex['textures']:,} textures; {time.time() - t0:.0f} s")
    print(f"textures full resolution {tex['full_bytes'] / gib:.2f} GiB; " +
          ", ".join(f"cap {c}: {tex['capped_bytes'][str(c)] / gib:.2f} GiB" for c in caps))
    print(f"meshes: source {nif_bytes / gib:.2f} GiB, estimate {(mesh_est or 0) / gib:.2f} GiB (ratio {ratio})")
    print(f"largest cap within the {ARCHIVE_BUDGET / gib:.2f} GiB budget: {rep['largest_cap_within_budget']}")
    for spec, b in tex["kind_caps"].items():
        print(f"textures with {spec}: {b / gib:.2f} GiB; with meshes {(b + (mesh_est or 0)) / gib:.2f} GiB")
    rs = rep["region_split_full_resolution"]
    print(f"full resolution split into {len(rs['regions'])} regions of {REGION_CELLS} x {REGION_CELLS} cells: "
          f"{rs['sum_bytes'] / gib:.2f} GiB in all (one archive: {rep['data_estimate']['full'] / gib:.2f}), largest "
          f"{rs['largest_region_bytes'] / gib:.2f} GiB, {rs['regions_over_budget']} over the budget")
    return 0


# ------------------------------------------------------------------------------------------------------------ terrain
class Terrain:
    """The core64 BTD (raw u16 heights), decoded with the formula and edge clamping of make_cw_overlays.decode_at and
    tg.point_interp; the local frame is the CW frame (core64's origin is CW (0, 0): position = FO4 position / 70)."""

    def __init__(self, path):
        t = btd.read(overlay_records.read_bytes(path))
        self.raw, self.hmin, self.hmax, self.n = t.heights_raw, t.hmin, t.hmax, t.ncx
        self.step = (self.hmax - self.hmin) / 65535.0
        self.origin = tg.grid_origin(self.n)

    def window(self, x0, y0, x1, y1):
        """(heights in metres, origin x, origin y) of the samples covering [x0, x1] x [y0, y1] (plus one sample)."""
        last = self.raw.shape[0] - 1
        c0 = min(max(int(math.floor((x0 - self.origin) / tg.SF_STEP_M)) - 1, 0), last)
        c1 = min(max(int(math.ceil((x1 - self.origin) / tg.SF_STEP_M)) + 1, 0), last)
        r0 = min(max(int(math.floor((y0 - self.origin) / tg.SF_STEP_M)) - 1, 0), last)
        r1 = min(max(int(math.ceil((y1 - self.origin) / tg.SF_STEP_M)) + 1, 0), last)
        win = self.hmin + self.raw[r0:r1 + 1, c0:c1 + 1].astype(np.float64) / 65535.0 * (self.hmax - self.hmin)
        return win, self.origin + c0 * tg.SF_STEP_M, self.origin + r0 * tg.SF_STEP_M

    def bilinear(self, xs, ys):
        """Bilinear height at many points at once (tg.point_interp's "bilinear" rule and clamping)."""
        xs, ys = np.asarray(xs, np.float64), np.asarray(ys, np.float64)
        rows, cols = self.raw.shape
        u = np.clip((xs - self.origin) / tg.SF_STEP_M, 0.0, cols - 1.0)
        v = np.clip((ys - self.origin) / tg.SF_STEP_M, 0.0, rows - 1.0)
        c = np.minimum(u.astype(np.int64), cols - 2)
        r = np.minimum(v.astype(np.int64), rows - 2)
        fu, fv = u - c, v - r
        h = lambda rr, cc: self.hmin + self.raw[rr, cc].astype(np.float64) / 65535.0 * (self.hmax - self.hmin)  # noqa: E731
        return (h(r, c) * (1 - fu) * (1 - fv) + h(r, c + 1) * fu * (1 - fv) + h(r + 1, c) * (1 - fu) * fv
                + h(r + 1, c + 1) * fu * fv)


class CoreWorld(x2c.World):
    """make_exp2c.World over a part of the core: the placed references whose origin lies in `area` (x0, y0, x1, y1),
    their converted collision, and a window of the core BTD around it. Indices k are into this local list."""

    def __init__(self, data_dir, bases, placed, terrain, area, margin=60.0):
        x0, y0, x1, y1 = area
        self.bases = bases
        self.placed = [p for p in placed if x0 - margin <= p["pos"][0] <= x1 + margin
                       and y0 - margin <= p["pos"][1] <= y1 + margin]
        self.model_tris, self.collision_errors = {}, {}
        from fo4sf import sfbodies
        for i in sorted({p["base"] for p in self.placed}):
            try:
                with open(os.path.join(data_dir, "meshes", bases[i]["model"]), "rb") as f:
                    bodies = sfbodies.nif_bodies(f.read())
                self.model_tris[i] = np.array([t for body in bodies for t in body["triangles"]],
                                              np.float64).reshape(-1, 3, 3)
            except (OSError, ValueError, struct.error) as e:
                self.collision_errors[bases[i]["model"]] = f"{type(e).__name__}: {e}"
        self.tris, self.owners = exterior.world_triangles(self.model_tris, self.placed)
        self.index = exterior.SurfaceIndex(self.tris, self.owners)
        self.heights, self.ox, self.oy = terrain.window(x0 - margin, y0 - margin, x1 + margin, y1 + margin)
        self.area = (x0, y0, x1, y1)
        self.step, self.hmin, self.n = terrain.step, terrain.hmin, terrain.n
        self.by_src = {p["src"]: k for k, p in enumerate(self.placed)}

    def ground(self, x, y):
        return tg.point_interp(self.heights, self.ox, self.oy, tg.SF_STEP_M, x, y)["bilinear"]

    def ground_all(self, x, y):
        return tg.point_interp(self.heights, self.ox, self.oy, tg.SF_STEP_M, x, y)

    def segment_blocked(self, p0, p1, ignore=(), step=2.0):
        """Does the segment p0 -> p1 (x, y, z) cross a collision triangle of a placed object not in `ignore`, or run
        under the terrain? (Line of sight for a screenshot spot.)"""
        p0, p1 = np.asarray(p0, np.float64), np.asarray(p1, np.float64)
        d = p1 - p0
        n = max(2, int(math.hypot(d[0], d[1]) / step) + 1)
        for t in np.linspace(0.0, 1.0, n):
            q = p0 + t * d
            if self.ground(q[0], q[1]) > q[2]:
                return True
        idx = np.unique(np.concatenate([self.index.near(*(p0 + t * d)[:2], step) for t in np.linspace(0.0, 1.0, n)]))
        if not len(idx):
            return False
        if ignore:
            idx = idx[~np.isin(self.owners[idx], list(ignore))]
        tri = self.tris[idx]
        e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
        h = np.cross(d, e2)
        det = (e1 * h).sum(axis=1)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = p0 - tri[:, 0]
        u = (s * h).sum(axis=1) * inv
        q = np.cross(s, e1)
        v = (q * d).sum(axis=1) * inv
        t = (q * e2).sum(axis=1) * inv
        return bool((ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6) & (t < 1 - 1e-6)).any())


# ---------------------------------------------------------------------------------------------------------------- plan
NEAR_M = 510.0              # core64 probes this close to the arrival (exact in the core64 run, 2026-10-11)
AREA_M = 560.0              # local collision world: arrival +- this (every point and every teleport position)
# --world-border: the WRLD fields TerrainOverlays changes on LC172World's copy (params "world_data", docs/terrain/border.md).
# "city" is NewAtlantis's values (SmallWorld cleared, HNAM 5). Whether they stop "BOUNDARY REACHED" is not yet proven:
# the one city run that passed (2026-10-22) had the markers plugin's template WRLD as the last override; the repeat
# test in border.md decides.
WORLD_DATA = {"template": None, "city": {"small_world": False, "hnam": 5}}
WORLD_SMALL_WORLD = 0x01                                  # WRLD DATA flag bit
DROP_MARGIN = 40.0          # drop at least this far above the highest expected landing of the entry (as core64)
TOP_CLEAR = 10.0            # and at least this far above every collision top within 1 m of a point
REF_LABEL = x2c.REF_LABEL
SHOP = "1B5F12:Fallout4.esm"            # RedRExt_Workshop02: Red Rocket shop floor and roof (exp2c)
STATION = "0211C0:Fallout4.esm"         # RedRExt_Workshop01: the station (rocket tower, canopy)
HOUSE_ROOF = "01DAAC:Fallout4.esm"      # Res01PlayerHouseRoofRR: the player's house in Sanctuary, its roof
MUSEUM = "01CC81:Fallout4.esm"          # ConcordMuseumBLD (ConcordMuseum01.nif): Museum of Freedom, Concord
# familiar object tops (judged: each >= x2c.MIN_DISCRIMINATION above the terrain under it) and screenshot spots
# (terrain south of the landmark: the runner faces north, heading 0, at every point and takes a screenshot there)
TOPS = (("redrocket_roof", SHOP), ("sanctuary_house_roof", HOUSE_ROOF), ("concord_museum_roof", MUSEUM))
VIEWS = (("view_redrocket", (STATION, SHOP)), ("view_sanctuary_house", (HOUSE_ROOF,)), ("view_concord_museum", (MUSEUM,)))
ROOF_FLAT_TOL = (0.02, 0.1, 0.25)       # level first; a low-pitched roof only if no level part is found
AGAIN = "_again"            # entry 2 drops on every roof twice in a row (about 70 s apart): late streaming vs absent
# Teleport rule (supported hypothesis, docs/terrain/core64c.md "Teleport rule", scripts/terrain/teleport_audit.py).
# The runner's Teleport types setpos x, then y, then z (scripts/game/qstep.ps1), so each setpos moves one axis. In the
# overlay runs so far (core64, core64b, exp2b, exp2b2, exp2b3, exp2c, exp2d, exp3: 173 teleports from a position where
# the previous one had landed), 144 of the 145 teleports that moved the player at most 2 cells along each axis landed
# (the other: exp2b's second attempt, where the player fell through the world), while 11 of the 28 that moved 3 or more cells
# along an axis relocated the player 8.2 to 11.8 km further along that axis ("Boundary Reached") or hung at the drop
# height, all 6 in core64 among them. Distance alone does not separate them: exp3 moved 250.5 and 267.0 m along one axis
# within 2 cells and landed, and hung after 248.7 m across 3 cells. A single-axis move of at most 200 m crosses at most
# 2 cell borders whatever the overlay's merge offset, so every teleport of a plan stays within MAX_AXIS_M per axis.
CELL_M = 100.0
MAX_AXIS_CELLS = 2
MAX_AXIS_M = MAX_AXIS_CELLS * CELL_M
# The runner hops legs longer than hop_m (qstep.ps1: ceil(d / hop_m) equal teleports, Euclidean d, none before the
# first point). Its step timeout, 150 + 90 s per point (testqueue.py step_timeout), does not count hops, so a plan keeps
# every leg within HOP_M by adding terrain waypoints (each a judged reading, and 90 s more timeout); hop_m stays a
# safety net for a leg without a usable waypoint.
HOP_M, HOP_WAIT_MS = int(MAX_AXIS_M), 7000
WAYPOINT_SPACING_M = 185.0  # ideal waypoint spacing: 15 m of slack below HOP_M for finding open terrain nearby
WAYPOINT_SEARCH_M = 30.0
WAYPOINT_MAX_SPREAD = 0.1   # m of terrain relief under the 0.6 m landing disc (about an 8 % grade): read within 0.5 m
WAYPOINT_PREFIX = "wp_"
# The runner's step costs (screenshot times of core64 / core64b, 2026-10-11): spawn shot 45 to 49 s after the step
# starts; a point (teleport, fall, read, screenshot) 68 to 73 s at settle 8 to 12 s; a hop 46 s (core64b: +46 s for
# one, +137 s for three); a "still hanging" re-read 28.5 s (core64: two per relocated probe, +57 s). An entry keeps
# MIN_MARGIN_S between its estimated last point and the step timeout: four re-reads (core64b had 138 s).
SPAWN_S, POINT_S, HOP_S, REREAD_S = 49.0, 62.0, 46.0, 29.0
MIN_MARGIN_S = 4 * REREAD_S + 4.0
# core64's merge offset on Mars (spawn read - spawn_local in all seven core64 / core64b runs: -1200.0029,
# -2700.0043 or -2699.9243): whole cells, used only to report cell changes in the frame the runs had
CORE64_OFFSET = (-1200.0, -2700.0)
FIRST_POINT_MAX_M = 100.0
REFR_NOTE = ("owner / nearby_object refr_in_plugin: the reference's FormID inside FO4TerrainCore.esm (6 hex digits). At "
             "run time the game prefixes the plugin's load-order index, which depends on the plugins loaded before it "
             "(the vanilla masters, BlueprintShips, the SFBGS plugins, FO4Port.esm, ...); this plan assumes none and "
             "needs none (no anchor: the merge offset comes from spawn_local)")
RUNNER_KEYS = x2c.RUNNER_KEYS
ENTRY_OWN = ("label", "points", "drop_z", "z_ref", "spawn_local", "settle_ms", "hop_m", "hop_wait_ms")
ROLES = ("terrain within 500 m", "familiar object tops", "informational")


def object_top(world, k, label, drop_z, tols=ROOF_FLAT_TOL):
    """The landing point on placed object k with the most level neighbourhood (exterior.pick_points), level first,
    then up to the next flat tolerance (a pitched roof). Returns a plan point dict or None."""
    for tol in tols:
        picks = exterior.pick_points(world.index, world.ground, k, world.bounds(k), drop_z, count=1, flat_tol=tol)
        if picks:
            x, y, land, free = picks[0]
            return {"label": label, "x": round(x, 4), "y": round(y, 4), "kind": "object_top",
                    "expect": round(land["centre"], 4), "landing": x2c.landing_json(world, land),
                    "above_terrain": round(land["centre"] - land["ground"], 4), "flat_tol": tol,
                    "discrimination": round(x2c.discrimination(world, x, y, land["centre"]), 4),
                    "owner": world.describe(k)}
    return None


def view_spot(world, label, owners, drop_z, dmin=20.0, dmax=90.0):
    """Open terrain south of a landmark (the runner faces north at every point) from where the landmark's middle is
    in sight: the nearest candidate (2 m grid, at most 25 degrees off north) that x2c.reference_ok accepts (level,
    nothing above the terrain within 1 m) and whose line of sight from eye height (1.7 m) is not blocked."""
    ks = [world.by_src[o] for o in owners]
    if not all((world.owners == k).any() for k in ks):
        return None                                      # disabled or without collision: no target to look at
    b = [world.bounds(k) for k in ks]
    cx = (min(v[0] for v in b) + max(v[2] for v in b)) / 2
    cy = (min(v[1] for v in b) + max(v[3] for v in b)) / 2
    y_south = min(v[1] for v in b)
    zs = world.tris[np.isin(world.owners, ks)][:, :, 2]
    target = (cx, cy, float(zs.min() + zs.max()) / 2)
    cands = []
    for d in np.arange(dmin, dmax + 1e-9, 2.0):
        for dx in np.arange(-d * 0.45, d * 0.45 + 1e-9, 2.0):
            x, y = cx + dx, y_south - d
            cands.append((math.hypot(dx, cy - y), round(x, 4), round(y, 4)))
    for _, x, y in sorted(cands):
        g = x2c.reference_ok(world, x, y, clear=1.0)
        if g is None:
            continue
        if world.segment_blocked((x, y, g + 1.7), target, ignore=set(ks)):
            continue
        land = world.landing(x, y, drop_z)
        return {"label": label, "x": x, "y": y, "kind": "view", "expect": round(g, 4), "terrain_expect": round(g, 4),
                "landing": x2c.landing_json(world, land), "target": [round(v, 3) for v in target],
                "distance_to_target_m": round(math.hypot(target[0] - x, target[1] - y), 1),
                "owner": world.describe(ks[0])}
    return None


def setpos_hits(world, cur, target_xy, drop_z, capsule=x2c.CAPSULE):
    """What each position one runner Teleport passes through from cur (x, y, z) to target_xy overlaps (x2c's capsule):
    [(x, y, z, hits)]."""
    return [(x, y, z, exterior.capsule_hits(world.index, world.ground, x, y, z, radius=capsule[0], height=capsule[1]))
            for x, y, z in exterior.setpos_path(cur, target_xy, drop_z)]


def waypoints_needed(d, spacing=None):
    """Waypoints a leg of d metres gets (add_waypoints): legs of up to `spacing` (WAYPOINT_SPACING_M) none, then one
    more per `spacing`."""
    return max(0, math.ceil(d / (spacing or WAYPOINT_SPACING_M) - 1e-9) - 1)


def seq_key(start, seq, legs=None):
    """(extra teleports, teleport position cost, length) of visiting seq (points) from start (x, y, z: where the
    player stands): what order_entry minimises. With legs (a Legs), each leg as add_waypoints will travel it (its
    waypoints, or the runner's hops where none was found, and x2c.position_cost of every position its teleports pass
    through); without, waypoints_needed per leg and no position cost."""
    extra, cost, total, here = 0, 0, 0.0, tuple(start)
    for p in seq:
        if legs is None:
            d = math.hypot(p["x"] - here[0], p["y"] - here[1])
            extra, total = extra + waypoints_needed(d), total + d
        else:
            lp = legs(here, p)
            extra, cost, total = extra + lp["extra"], cost + lp["cost"], total + lp["length"]
        here = (p["x"], p["y"], p["expect"])
    return extra, cost, round(total, 3)


def spoke_order(start, points, sector_deg=45.0):
    """Points near the arrival (< 100 m) first, then by bearing sector around the arrival, outward in one sector and
    inward in the next (a zig-zag over the spokes), so no jump crosses the arrival or skips a sector at 500 m."""
    def bearing(p):
        return math.degrees(math.atan2(p["y"] - start[1], p["x"] - start[0])) % 360.0

    def dist(p):
        return math.hypot(p["x"] - start[0], p["y"] - start[1])
    near = sorted((p for p in points if dist(p) < 100), key=lambda p: (dist(p), p["label"]))
    far = [p for p in points if dist(p) >= 100]
    sectors = {}
    for p in far:
        sectors.setdefault(int(bearing(p) // sector_deg), []).append(p)
    out = list(near)
    for n, s in enumerate(sorted(sectors)):
        out += sorted(sectors[s], key=lambda p: (dist(p), p["label"]), reverse=bool(n % 2))
    return out


def two_opt(order, key):
    """Reverse sub-sequences while that lowers key(sequence)."""
    order = list(order)
    best = key(order)
    improved = True
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                k = key(cand)
                if k < best:
                    order, best, improved = cand, k, True
    return order


def order_entry(start, points, legs=None, exhaustive=8):
    """Visiting order of points from start (x, y, z: where the player stands before the first of them): up to
    `exhaustive` points every order, more points a spoke zig-zag around start improved by 2-opt, both by seq_key
    (fewest extra teleports, then the fewest teleport positions in objects, then the shortest way). Ties keep the
    given order."""
    import itertools

    def key(seq):
        return seq_key(start, seq, legs)
    if len(points) <= exhaustive:
        return list(min(itertools.permutations(points), key=key))
    return two_opt(spoke_order(start, points), key)


def waypoint_ok(world, x, y, drop_z):
    """Can (x, y) be a judged terrain waypoint? The three interpolation rules agree within one quantisation step (as
    check requires of every terrain point), at most WAYPOINT_MAX_SPREAD of relief under the 0.6 m landing disc, no
    object standing above the terrain within x2c.TERRAIN_CLEAR_RADII (1 m) and none reaching into a 3 m column of
    radius 1 m, the drop lands on the terrain. Returns (terrain height, disc spread) or None."""
    hs = world.ground_all(x, y)
    if max(hs.values()) - min(hs.values()) > world.step:
        return None
    disc = [world.ground(x + dx, y + dy) for dx, dy in exterior.disc_offsets(0.6)]
    if max(disc) - min(disc) > WAYPOINT_MAX_SPREAD:
        return None
    if exterior.nearby_object(world.index.top, world.ground, x, y, drop_z, radii=x2c.TERRAIN_CLEAR_RADII) is not None:
        return None
    if any(h != "terrain" for h in exterior.capsule_hits(world.index, world.ground, x, y, hs["bilinear"] + 0.02,
                                                         radius=1.0, height=3.0)):
        return None
    if world.landing(x, y, drop_z)["on_object"]:
        return None
    return hs["bilinear"], max(disc) - min(disc)


def waypoint(world, prev, ideal, target, legs_left, arrival, drop_z, label):
    """The terrain point (waypoint_ok) nearest `ideal` within WAYPOINT_SEARCH_M (2 m grid) that keeps the leg from
    prev (x, y, z) within HOP_M, can still reach target (x, y) in legs_left legs of HOP_M, lies within NEAR_M of the
    arrival and whose teleport from prev overlaps no placed object. A terrain plan point or None."""
    n = int(WAYPOINT_SEARCH_M / 2.0)
    cands = sorted((i * i + j * j, ideal[0] + 2.0 * i, ideal[1] + 2.0 * j)
                   for i in range(-n, n + 1) for j in range(-n, n + 1) if 4.0 * (i * i + j * j) <= WAYPOINT_SEARCH_M ** 2)
    for _, x, y in cands:
        x, y = round(x, 4), round(y, 4)
        if (math.hypot(x - prev[0], y - prev[1]) > HOP_M or math.hypot(target[0] - x, target[1] - y) > HOP_M * legs_left
                or math.hypot(x - arrival[0], y - arrival[1]) > NEAR_M):
            continue
        ok = waypoint_ok(world, x, y, drop_z)
        if ok is None or any(h != "terrain" for *_pos, hits in setpos_hits(world, prev, (x, y), drop_z) for h in hits):
            continue
        g, spread = ok
        return {"label": label, "x": x, "y": y, "kind": "terrain", "expect": round(g, 4), "terrain_expect": round(g, 4),
                "landing": x2c.landing_json(world, world.landing(x, y, drop_z)), "nearby_object": None,
                "waypoint": True, "disc_spread": round(spread, 4)}
    return None


def leg_plan(world, a, b, arrival, drop_z):
    """How the plan travels from a (x, y, z: where the player stands) to point b: waypoints_needed() terrain waypoints
    (waypoint(), unlabelled), each near its evenly spaced place, or none when one is not found (the runner then hops
    the leg, hop_m); "extra": the teleports that adds, "cost": x2c.position_cost of every position the leg's
    teleports pass through (after a hop the player is assumed at the drop height), "length": metres."""
    d = math.hypot(b["x"] - a[0], b["y"] - a[1])
    n = waypoints_needed(d)
    wps, prev = [], tuple(a)
    for i in range(1, n + 1):
        ideal = (a[0] + (b["x"] - a[0]) * i / (n + 1), a[1] + (b["y"] - a[1]) * i / (n + 1))
        w = waypoint(world, prev, ideal, (b["x"], b["y"]), n + 1 - i, arrival, drop_z, "")
        if w is None:
            break
        wps.append(w)
        prev = (w["x"], w["y"], w["expect"])
    left = len(wps) < n or math.hypot(b["x"] - prev[0], b["y"] - prev[1]) > HOP_M
    if left:
        wps = []
    chain = [{"label": "", "x": a[0], "y": a[1], "expect": a[2]}] + wps + [b]
    tps = runner_teleports(chain, HOP_M)[1:]                  # the first is a itself (no hop before it)
    cost, cur, k = 0, tuple(a), 1
    for label, x, y in tps:
        cost += sum(x2c.position_cost(hits) for *_pos, hits in setpos_hits(world, cur, (x, y), drop_z))
        if label is None:
            cur = (x, y, drop_z)
        else:
            cur, k = (x, y, chain[k]["expect"]), k + 1
    return {"waypoints": wps, "left": left, "extra": len(tps) - 1, "cost": cost, "length": round(d, 3)}


class Legs:
    """leg_plan of every leg asked for, computed once: what order_entry weighs and add_waypoints puts in."""

    def __init__(self, world, arrival, drop_z):
        self.world, self.arrival, self.drop_z, self.memo = world, arrival, drop_z, {}

    def __call__(self, a, b):
        key = (round(a[0], 4), round(a[1], 4), round(a[2], 4), round(b["x"], 4), round(b["y"], 4), round(b["expect"], 4))
        if key not in self.memo:
            self.memo[key] = leg_plan(self.world, a, b, self.arrival, self.drop_z)
        return self.memo[key]


def add_waypoints(world, start, seq, arrival, drop_z, legs=None):
    """seq with the terrain waypoints of every leg (leg_plan; start (x, y, z): where the player stands before seq[0]),
    labelled wp_01, wp_02, ... in travel order, so no leg is longer than HOP_M and the runner hops none. Returns
    (points, legs left to the runner's hops)."""
    legs = legs or Legs(world, arrival, drop_z)
    out, cur, left, k = [], tuple(start), [], 0
    for p in seq:
        lp = legs(cur, p)
        if lp["left"]:
            left.append({"to": p["label"], "from": [round(cur[0], 4), round(cur[1], 4)], "length_m": round(lp["length"], 1)})
        for w in lp["waypoints"]:
            k += 1
            out.append(dict(w, label=f"{WAYPOINT_PREFIX}{k:02d}"))
        out.append(p)
        cur = (p["x"], p["y"], p["expect"])
    return out, left


def entry_drop(world, points):
    """Drop height of an entry: DROP_MARGIN above its highest expected landing and TOP_CLEAR above every collision
    top within 1 m of any of its points, rounded up to 5 m."""
    top = max(p["expect"] for p in points) + DROP_MARGIN
    for p in points:
        for dx, dy in exterior.disc_offsets(1.0):
            s = world.index.surfaces(p["x"] + dx, p["y"] + dy)
            if s:
                top = max(top, s[0][0] + TOP_CLEAR)
    return float(math.ceil(top / 5.0) * 5.0)


def settle_for(drop, lowest):
    import make_cw_overlays as cwo
    return cwo.settle_ms(drop, lowest)


def plan_entry(base, label, drop_z, points, z_ref, spawn_local, settle_ms):
    """One runner entry: every key of core64's entry `base` except the ones core64c sets (ENTRY_OWN), then its own."""
    e = {k: v for k, v in base.items() if k not in ENTRY_OWN}
    e.update(label=label, spawn_local=spawn_local, z_ref=z_ref, drop_z=drop_z, settle_ms=settle_ms,
             hop_m=HOP_M, hop_wait_ms=HOP_WAIT_MS, points=[{k: p[k] for k in x2c.POINT_KEYS} for p in points])
    return e


def runner_teleports(points, hop_m=HOP_M):
    """The teleports qstep.ps1 makes for an entry's points, in order: [(label, x, y)], label None for a hop. No hop
    before the first point (its hop origin is the first point itself); a later leg of d metres (Euclidean) becomes
    ceil(d / hop_m) equal teleports."""
    out = []
    if not points:
        return out
    hx, hy = points[0]["x"], points[0]["y"]
    for p in points:
        if hop_m:
            n = math.ceil(math.hypot(p["x"] - hx, p["y"] - hy) / hop_m)
            out += [(None, hx + (p["x"] - hx) * h / n, hy + (p["y"] - hy) * h / n) for h in range(1, n)]
        out.append((p["label"], p["x"], p["y"]))
        hx, hy = p["x"], p["y"]
    return out


def axis_cells(d, cell=CELL_M):
    """The most cell borders a move of d metres along one axis can cross, whatever the frame's offset."""
    return int(math.ceil(abs(d) / cell - 1e-9))


def axis_moves(start, teleports, offset=CORE64_OFFSET):
    """Each teleport from where the player stood (start (x, y): the arrival): {"to", "dx", "dy", "cells": the most
    cells it can move the player along an axis whatever the merge offset, "cells_core64": along an axis in core64's
    measured frame}. qstep.ps1 sets x, then y, then z: each setpos moves one axis."""
    out, cur = [], tuple(start[:2])
    for label, x, y in teleports:
        dx, dy = x - cur[0], y - cur[1]
        core = max(abs(math.floor((x + offset[0]) / CELL_M) - math.floor((cur[0] + offset[0]) / CELL_M)),
                   abs(math.floor((y + offset[1]) / CELL_M) - math.floor((cur[1] + offset[1]) / CELL_M)))
        out.append({"to": label or "hop", "dx": round(dx, 2), "dy": round(dy, 2),
                    "cells": max(axis_cells(dx), axis_cells(dy)), "cells_core64": int(core)})
        cur = (x, y)
    return out


def runner_seconds(n_points, settle_ms, hops):
    """Estimated seconds from the start of a terrain step to its last point saved (SPAWN_S, POINT_S + settle, HOP_S)."""
    return SPAWN_S + n_points * (POINT_S + settle_ms / 1000.0) + hops * HOP_S


def runner_timeout(n_points):
    """testqueue.py step_timeout of a terrain test (claude/integration-1011 dcf8ad6): 150 + 90 * (points + 1) s."""
    return 150 + 90 * (n_points + 1)


def entry_travel(start, entry):
    """The runner's teleports through one plan entry from start (x, y): hops, the longest single-axis move, the most
    cells per axis (any frame and core64's), and the time estimate against the step timeout."""
    tps = runner_teleports(entry["points"], entry.get("hop_m") or 0)
    moves = axis_moves(start, tps)
    hops = sum(1 for t in tps if t[0] is None)
    est = runner_seconds(len(entry["points"]), entry["settle_ms"], hops)
    to = runner_timeout(len(entry["points"]))
    return {"teleports": len(tps), "hops": hops,
            "max_axis_move_m": round(max(max(abs(m["dx"]), abs(m["dy"])) for m in moves), 1),
            "max_axis_cells": max(m["cells"] for m in moves),
            "max_axis_cells_core64": max(m["cells_core64"] for m in moves),
            "estimated_s": round(est), "timeout_s": to, "margin_s": round(to - est), "moves": moves}


def teleport_report(world, start, entry):
    """x2c.path_report over the runner's teleports, hops included: what each position of each teleport overlaps
    (start (x, y, z): where the player stands after the coc). The player is assumed to stand at a point's expected
    landing after it, and at the drop height after a hop. Returns ([{"to", "positions"}], every position clear)."""
    out, ok, cur = [], True, tuple(start)
    want = {p["label"]: p["expect"] for p in entry["points"]}
    for label, x, y in runner_teleports(entry["points"], entry.get("hop_m") or 0):
        steps = []
        for px, py, pz, hits in setpos_hits(world, cur, (x, y), entry["drop_z"]):
            ok = ok and not hits
            steps.append([round(px, 4), round(py, 4), round(pz, 4),
                          [world.placed[h]["src"] if isinstance(h, int) else h for h in hits]])
        out.append({"to": label or "hop", "positions": steps})
        cur = (x, y, entry["drop_z"] if label is None else want[label])
    return out, ok


def validate_plan(plan, base, kinds):
    """Problems of the entries against the runner's keys and core64's entry (x2c.validate_plan's rules with this
    experiment's own keys): unknown keys, a base key not carried, z_ref not this entry's terrain reference, duplicate
    labels, point keys."""
    problems = []
    for i, e in enumerate(plan):
        tag = f"entry {i + 1}"
        problems += [f"{tag}: key {k!r} is not read by the runner" for k in e if k not in RUNNER_KEYS]
        problems += [f"{tag}: core64 key {k!r} not carried" for k, v in base.items() if k not in ENTRY_OWN and e.get(k) != v]
        labels = [p["label"] for p in e.get("points", [])]
        if len(set(labels)) != len(labels):
            problems.append(f"{tag}: duplicate point labels")
        if e.get("z_ref") not in labels or kinds.get((i, e.get("z_ref"))) != "terrain_ref":
            problems.append(f"{tag}: z_ref {e.get('z_ref')!r} is not its terrain reference point")
        problems += [f"{tag}: point {p.get('label')} keys {sorted(p)}" for p in e.get("points", [])
                     if tuple(sorted(p)) != tuple(sorted(x2c.POINT_KEYS))]
    return problems


def scenario_reads(world, entry, meta, scenario):
    """x2c.scenario_reads with this plan's kinds: terrain points (terrain, terrain_ref, terrain_near_object, view)
    read the terrain without objects; object points then land on the highest terrain sample under their disc.
    landing_max: every point reads the highest collision or terrain under its 0.6 m landing disc (what the dropped
    player may rest on: an object reaching into the disc of a terrain point shows here)."""
    reads = []
    for p in entry["points"]:
        on_terrain = meta[p["label"]]["kind"] in ("terrain", "terrain_ref", "terrain_near_object", "view")
        if scenario == "no_objects":
            reads.append(p["expect"] if on_terrain else
                         max(world.ground(p["x"] + dx, p["y"] + dy) for dx, dy in exterior.disc_offsets(0.6)))
        elif scenario == "flat_terrain":
            reads.append(world.hmin if on_terrain else p["expect"])
        elif scenario == "landing_max":
            reads.append(world.landing(p["x"], p["y"], entry["drop_z"])["z"])
        else:
            raise ValueError(scenario)
    return reads


SCENARIOS = (("no_objects", "flat_terrain", "landing_max"), ("no_objects", "landing_max"), ("no_objects", "landing_max"))


def build_plan(world, ov, base, core_exp, views=False):
    """Three entries, each ONE coc arrival at core64's COC marker, heights judged against the terrain reference
    zref_ground read in the same test (z_ref), its first point:
    1 terrain within 500 m  core64's probes within NEAR_M of the arrival that stay clear of objects (exact in core64)
    2 object tops           Red Rocket shop roof, the Sanctuary player house roof, the Concord museum roof (each at
                            least x2c.MIN_DISCRIMINATION above the terrain: without the objects the entry fails), each
                            dropped on twice in a row (<label>_again, about 70 s later: late streaming vs absent)
    3 informational         core64 probes now on or near an object; with views, screenshot spots south of the three
                            places (only useful once the runner sets the time of day: PR #73)
    Points are ordered by order_entry; add_waypoints puts open terrain waypoints (judged like the probes) on every
    leg longer than WAYPOINT_SPACING_M, so every teleport stays within MAX_AXIS_CELLS cells per axis without the
    runner's hops, which its step timeout does not count. Returns (plan, expected-json part)."""
    sx, sy, sz = ov["spawn"]
    land_spawn = world.landing(sx, sy, sz)
    start = (sx, sy, land_spawn["centre"])
    spawn_local = [sx, sy, round(land_spawn["centre"], 4)]
    ref = x2c.reference_point(world, (sx, sy))
    if ref is None:
        sys.exit(f"no open level terrain within {x2c.REF_SEARCH} m of the arrival for {REF_LABEL}")

    near, seen = [], set()
    for e in core_exp["entries"]:
        for p in e["points"]:
            if p["from_arrival_m"] <= NEAR_M and p["label"] not in seen:
                seen.add(p["label"])
                near.append({"label": p["label"], "x": p["x_cw"], "y": p["y_cw"], "expect": p["expect"],
                             "core64": {"kind": p["kind"], "from_arrival_m": p["from_arrival_m"]}})
    terr = x2c.terrain_points(world, near, 300.0)
    for t, p in zip(terr, near):
        t["core64"] = p["core64"]
    judged_terrain = [p for p in terr if p["kind"] == "terrain"]
    info = [p for p in terr if p["kind"] != "terrain"]

    tops, missing = [], []
    for label, src in TOPS:
        k = world.by_src.get(src)
        if k is not None and not (world.owners == k).any():
            k = None                                     # disabled or without collision
        p = object_top(world, k, label, 300.0) if k is not None else None
        if p is None or p["discrimination"] < x2c.MIN_DISCRIMINATION:
            missing.append({"label": label, "src": src, "reason": "not placed or no collision" if k is None else
                            "no landing point" if p is None else f"only {p['discrimination']} m above the terrain"})
            if p is not None:
                info.append(p)
            continue
        p["object_class"] = x2c.object_class(p["discrimination"])
        tops.append(p)
    if not tops:
        sys.exit(f"no familiar object top: {missing}")
    if views:
        for label, owners in VIEWS:
            if all(o in world.by_src for o in owners):
                v = view_spot(world, label, owners, 300.0)
                if v is not None:
                    info.append(v)
                    continue
            missing.append({"label": label, "src": owners[0], "reason": "no open terrain with a clear view south of it"})

    groups, plan, kinds, left = [], [], {}, []
    labels = [f"terrain_core64c 1/3 (terrain within {NEAR_M:.0f} m): core64's probes near the arrival that stay clear "
              f"of objects and open terrain waypoints between them, relative to {REF_LABEL} (a flat or missing BTD "
              f"fails)",
              f"terrain_core64c 2/3 (familiar object tops): Red Rocket shop roof, Sanctuary player house roof, Concord "
              f"museum roof, >= {x2c.MIN_DISCRIMINATION} m above the terrain, each dropped on twice in a row "
              f"(<roof>{AGAIN}), relative to {REF_LABEL} (fails if the objects are missing)",
              "terrain_core64c 3/3 (informational: the runner's verdict is expected to be FAIL HEIGHTS, read point by "
              "point): core64 probes now on or near objects (e_500m: a maple's collision reaches into the landing "
              "disc; ne_200m: 0.8 m from a 7 m cliff)" + (", screenshot spots facing north at Red Rocket, the "
                                                          "Sanctuary house and the Concord museum" if views else "")]
    ref_xyz = (ref["x"], ref["y"], ref["expect"])
    legs = Legs(world, (sx, sy), 300.0)
    for i, pts in enumerate((judged_terrain, tops, info)):
        order = order_entry(ref_xyz, pts, legs)
        if i == 1:
            order = [q for p in order for q in (p, dict(p, label=p["label"] + AGAIN, again_of=p["label"]))]
        order, gaps = add_waypoints(world, ref_xyz, order, (sx, sy), 300.0, legs)
        order = [ref] + order
        drop = entry_drop(world, order)
        settle = settle_for(drop, min(p["expect"] for p in order))
        groups.append(order)
        left.append(gaps)
        plan.append(plan_entry(base, labels[i], drop, order, REF_LABEL, spawn_local, settle))
        kinds.update({(i, p["label"]): p["kind"] for p in order})
    problems = validate_plan(plan, base, kinds)
    if problems:
        sys.exit("plan: " + "; ".join(problems))
    entries = []
    for i, (e, g) in enumerate(zip(plan, groups)):
        meta = {p["label"]: p for p in g}
        pred = {}
        for sc in SCENARIOS[i]:
            v, worst, _ = x2c.judge_heights(e["points"], scenario_reads(world, e, meta, sc), e["z_ref"])
            pred[sc] = {"verdict": v, "worst_m": round(worst, 3)}
        paths, clear = teleport_report(world, start, e)
        travel = entry_travel(start, e)
        if travel["max_axis_cells"] > MAX_AXIS_CELLS or travel["margin_s"] < MIN_MARGIN_S:
            sys.exit(f"entry {i + 1}: a teleport moves {travel['max_axis_cells']} cells along an axis (at most "
                     f"{MAX_AXIS_CELLS}) or the step keeps {travel['margin_s']} s of {travel['timeout_s']} s (at least "
                     f"{MIN_MARGIN_S:.0f})")
        here, legs = start[:2], []
        for p in e["points"]:
            legs.append(round(math.hypot(p["x"] - here[0], p["y"] - here[1]), 1))
            here = (p["x"], p["y"])
        entries.append({"label": e["label"], "role": ROLES[i], "drop_z": e["drop_z"], "settle_ms": e["settle_ms"],
                        "z_ref": e["z_ref"], "predicted": pred, "teleports_clear": clear, "legs_m": legs,
                        "longest_leg_m": max(legs), "waypoints": sum(1 for p in g if p.get("waypoint")),
                        "legs_left_to_runner_hops": left[i],
                        "travel": {k: v for k, v in travel.items() if k != "moves"},
                        "teleport_positions_on_objects": sum(
                            1 for t in paths for pos in t["positions"] if any(h != "terrain" for h in pos[3])),
                        "moves": travel["moves"], "teleports": paths})
    return plan, {"spawn": {"marker": ov["spawn"], "landing": x2c.landing_json(world, land_spawn),
                            "spawn_local": spawn_local, "core64_spawn_local": base["spawn_local"]},
                  "reference": ref, "entries": entries, "missing": missing, "views": bool(views),
                  "points": [dict(p, entry=i) for i, g in enumerate(groups) for p in g]}


# --------------------------------------------------------------------------------------------------------------- stage
def link_tree(src, dst):
    """Hard-link every file of src into dst (same volume: no second copy of the converted files), copying when a link
    is not possible; a file already linked to the same source is kept. Returns (linked, copied, kept)."""
    linked = copied = kept = 0
    for root, _dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for fn in files:
            s, d = os.path.join(root, fn), os.path.join(dst, rel, fn)
            if os.path.exists(d):
                if os.path.samefile(s, d):
                    kept += 1
                    continue
                os.remove(d)
            try:
                os.link(s, d)
                linked += 1
            except OSError:
                shutil.copy2(s, d)
                copied += 1
    return linked, copied, kept


def data_files(out):
    """[(path relative to Data with '/', bytes)] of the staged Data tree, sorted."""
    data = os.path.join(out, "Data")
    files = []
    for root, _dirs, names in os.walk(data):
        for fn in names:
            p = os.path.join(root, fn)
            files.append((os.path.relpath(p, data).replace(os.sep, "/"), os.path.getsize(p)))
    return sorted(files)


def ba2_size(files):
    """Size of a General BA2 holding `files` stored (no compression), as Archive2 writes it: 24-byte header (+ 8 in
    v2/v3), a 36-byte record per file, the data, then the name table (u16 length + name). An estimate within the
    header variant; the dry run in check measures the real one."""
    return 32 + sum(36 + b + 2 + len(n) for n, b in files)


def terrain_edids(prm):
    out = set()
    for o in prm["overlays"]:
        out |= {o["world"], o["block"], o["location"], o["anchor"]["edid"], o["coc"], o["coc"] + "Marker"}
    return {e.lower() for e in out}


def container_source_key(value):
    """Normalize ASCII case without conflating distinct Unicode plugin spellings (e.g. sharp-s and ss).

    Non-ASCII spelling comes from the canonical source export; do not invent a filesystem/ModKey collation here.
    """
    return str(value).translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))


def promoted_edid(kind, base, src):
    """Keep legacy simple-master/R05 names; otherwise include the full source identity.

    Stripping punctuation or extensions aliases distinct plugins. The hashed namespace contains an underscore,
    which cannot occur in a legacy alphanumeric master stem. Promotion callers also refuse any key collision.
    """
    if not base:
        key = container_source_key(src)
        local, _, plugin = key.partition(":")
        if plugin == "fallout4.esm":                     # preserve the original hand-written R05 identity
            return f"{EDID_PREFIX}{kind}_{local}"
        return f"{EDID_PREFIX}{kind}_ref_{hashlib.sha256(key.encode('utf-8')).hexdigest()}"
    key = container_source_key(base)
    local, _, plugin = key.partition(":")
    suffix = plugin[:-4] if re.fullmatch(r"[a-z0-9]+\.esm", plugin) else "key_" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"{EDID_PREFIX}{kind}_{local}_{suffix}"


def container_edid(base, src):
    return promoted_edid("cont", base, src)


def item_edid(base, src):
    return promoted_edid("misc", base, src)


def activator_edid(base, src):
    """The shared ACTI's editor id of an activator: FO4Core_acti_<6 hex>_<plugin> (promoted_edid)."""
    return promoted_edid("acti", base, src)


def terminal_edid(base, src):
    """The shared TERM's editor id of a terminal: FO4Core_term_<6 hex>_<plugin> (promoted_edid)."""
    return promoted_edid("term", base, src)


def terminal_menu_edid(term_edid):
    """The editor id of a TERM's own TMLM menu: its edid with "tmlm" for "term" (FO4Core_tmlm_<6 hex>_<plugin>)."""
    head = f"{EDID_PREFIX}term_"
    if not term_edid.startswith(head):
        raise ValueError(f"{term_edid!r} is not a terminal edid")
    return f"{EDID_PREFIX}tmlm_{term_edid[len(head):]}"


def workshop_edid(base, src):
    """The shared ACTI's editor id of a settlement workshop: FO4Core_wkshp_<6 hex>_<plugin> (promoted_edid)."""
    return promoted_edid("wkshp", base, src)


def flora_edid(base, src):
    """The shared FLOR's editor id of a harvestable plant: FO4Core_flor_<6 hex>_<plugin> (promoted_edid)."""
    return promoted_edid("flor", base, src)


# Red Rocket garage button -> door (playtest row 21, docs/terrain/garage-button.md). FO4 XAPR is not in the cluster
# export; these two Commonwealth pairs are the whole set. Matched on (plugin, numeric id), not the hex spelling.
GARAGE_BUTTON_PAIRS = (
    ("00056331:Fallout4.esm", "00056BBA:Fallout4.esm"),   # garage, button (Red Rocket shop)
    ("000866C7:Fallout4.esm", "000866C0:Fallout4.esm"),   # the other Commonwealth RedRGarageDoor
)
GARAGE_SCRIPT = "DefaultActivateLinkedRefOnActivate"   # vanilla; GetLinkedRef(LinkedRefKeyword)
GARAGE_SCRIPT_PROPERTY = "LinkedRefKeyword"
GARAGE_LINK_KEYWORD = 0x5D5E7                         # KYWD LinkCustom02; XLKR and the VMAD property must agree


def source_identity(src):
    """(plugin.casefold(), numeric form id) of a FO4 source key. ValueError if the key is not <hex>:<plugin>."""
    local, sep, plugin = str(src).partition(":")
    if not sep or not local or not plugin:
        raise ValueError(f"{src}: not a plugin-local form key")
    try:
        fid = int(local, 16)
    except ValueError as e:
        raise ValueError(f"{src}: form id is not hex") from e
    if fid <= 0 or fid > 0xFFFFFF:
        raise ValueError(f"{src}: form id {fid:#x} is not in 1..0xFFFFFF")
    return (plugin.casefold(), fid)


def cluster_garage_buttons(activators):
    """Pairs of already-promoted ACTI whose FO4 XAPR wired a RedRGarageDoor to a RedR_ButtonBox.

    Keys are (plugin, form id): a 6-hex Fallout4.esm source matches the 8-hex pair spelling; Other.esm with the same
    id does not. Two different spellings of one identity raise ValueError; identical keys keep the first.
    """
    by_id = {}
    for e in activators:
        ident = source_identity(e["src"])
        have = by_id.get(ident)
        if have is not None and source_key(have) != source_key(e["src"]):
            raise ValueError(f"garage_buttons: {e['src']} and {have} are the same FO4 source")
        by_id.setdefault(ident, e["src"])
    out = []
    for door, button in GARAGE_BUTTON_PAIRS:
        d, b = source_identity(door), source_identity(button)
        if d in by_id and b in by_id:
            out.append({"door": by_id[d], "button": by_id[b]})
    return out


def garage_button_vmad(keyword=GARAGE_LINK_KEYWORD):
    """REFR VMAD bytes: DefaultActivateLinkedRefOnActivate with edited LinkedRefKeyword = keyword (Starfield master 0)."""
    return vmad_patch.encode([{
        "name": GARAGE_SCRIPT, "status": vmad_patch.STATUS_LOCAL, "properties": [{
            "name": GARAGE_SCRIPT_PROPERTY, "type": vmad_patch.T_OBJECT, "status": vmad_patch.PROP_EDITED,
            "value": {"form": keyword, "alias": -1},
        }],
    }])


def garage_button_xlkr(door_fid, keyword=GARAGE_LINK_KEYWORD):
    """XLKR payload: keyword then the garage REFR (little-endian form ids)."""
    return struct.pack("<II", keyword, door_fid)


def door_edid(base, src):
    """The shared ACTI's editor id of a scripted load door: FO4Core_door_<6 hex>_<plugin> (promoted_edid)."""
    return promoted_edid("door", base, src)


# Scripted load doors (docs/terrain/scripted-doors.md; make_cluster.py doors): the door REFR keeps its slot on an ACTI
# with the converted door mesh and carries the FO4SF_LoadDoor VMAD (DestinationPlugin / DestinationId: the interior
# arrival marker of the port plugin; DestinationX / Y / Z: that marker's position, interior coordinates, with
# UseDestinationPosition true, the script's opt-in for them); an exterior
# arrival XMarker (the interior door's destination: PERSISTENT, in the overlay world's persistent cell, so it resolves
# from inside) takes a new REFR id after every other record, then the ACTI bases, so every id of the build without
# doors stays put.
DOOR_NAME = "Door"                  # the ACTI's FULL when the cluster names none (FO4's door FULLs are localized ids)
XMARKER = overlay_records.XMARKER   # STAT XMarker 00003B:Starfield.esm (verified raw: EDID XMarker, markerx.nif)


TERMINAL_BODY = "FO4 terminal (text not ported yet)"   # as make_cluster.TERMINAL_BODY: one body line per terminal menu
# Stations (docs/terrain/stations.md), as make_cluster.py: the workshop ACTI's FULL and build radius (PRPS
# OutpostBuildAreaRadius, metres: the vanilla OutpostPlayerHouseActivator's 250), the Starfield records the check binds to
WORKSHOP_NAME = "Workshop"
WORKSHOP_RADIUS_M = 250.0
WORKSHOP_KEYWORD = 0x054BA7         # KYWD WorkshopKeyword (Starfield.esm; the same id in Fallout4.esm)
WORKSHOP_RADIUS_AV = 0x063FC5       # AVIF OutpostBuildAreaRadius
WORKSHOP_TEMPLATE = 0x024DC7        # ACTI OutpostPlayerHouseActivator: the OutpostCategory* keywords the writer copies
# bench kind -> (the vanilla Starfield bench, its WBDT bench type, the recipe keyword its COBJs name), as make_cluster.BENCH_KINDS
BENCH_VANILLA = {"weapon": ("2B6A63:Starfield.esm", 2, 0x2CE1C0), "armor": ("2B6A62:Starfield.esm", 7, 0x0657FF),
                 "chem": ("2B6A61:Starfield.esm", 5, 0x102158), "cooking": ("2B6A65:Starfield.esm", 5, 0x102152)}


def cluster_containers(bases, placed, cluster):
    """R05: the placed references named by cluster["containers"] (by FO4 source key) leave the STAT placement and
    become container entries for TerrainOverlays (the converted model of their base, the given name and vanilla
    inventory, the reference's cell / position / rotation / scale and original reference index).
    Returns (placed without them, containers). The writer reserves the source's original REFR identity.
    ValueError for a reference that is not placed by this build or is initially disabled."""
    wanted = {c["src"]: c for c in cluster.get("containers", [])}
    keep, containers, source_by_edid = [], [], {}
    for reference_index, p in enumerate(placed):
        c = wanted.pop(p["src"], None)
        if c is None:
            keep.append(p)
            continue
        if p.get("disabled"):
            raise ValueError(f"{p['src']} is initially disabled in FO4; not a container to open")
        if not c.get("items"):
            raise ValueError(f"{p['src']}: a container needs items")
        for it in c["items"]:
            if not re.fullmatch(r"[A-Za-z0-9_. -]+\.es[mpl]:[0-9A-Fa-f]{6}", str(it.get("form", ""))) or int(it.get("count", 0)) < 1:
                raise ValueError(f"{p['src']}: item {it!r} is not <plugin>:<6 hex> with a count")
        b = bases[p["base"]]
        # one CONT per FO4 base (make_cluster.py entries carry "base", the FO4 base formkey: 5,185 Commonwealth containers
        # over 182 bases): the group is the whole formkey, id and plugin (04B6E9:Fallout4.esm and 04B6E9:SomeDLC.esm are
        # two bases: Codex's review of #167); an entry without "base" (the R05 slice's hand-written one) keeps its
        # per-reference CONT. Entries of one group must agree on name and items: the writer shares one record.
        edid = container_edid(c.get("base"), p["src"])
        identity = ("base" if c.get("base") else "reference", container_source_key(c.get("base") or p["src"]))
        if source_by_edid.setdefault(edid.casefold(), identity) != identity:
            raise ValueError(f"container {edid} aliases distinct source identities")
        containers.append({"src": p["src"], "edid": edid,
                           "reference_index": reference_index,
                           "model": b["model"], "name": c["name"], "items": c["items"],
                           "cell": p["cell"], "pos": p["pos"], "rot": p["rot"], "scale": p["scale"]})
    if wanted:
        raise ValueError(f"references not placed by this build: {sorted(wanted)}")
    seen = {}
    for c in containers:
        sig = (c["name"], tuple(sorted((str(i["form"]).casefold(), int(i["count"])) for i in c["items"])))
        first = seen.setdefault(c["edid"], (c["src"], sig))
        if first[1] != sig:
            raise ValueError(f"{c['src']} and {first[0]} share container {c['edid']} with a different name or inventory")
    return keep, containers


def cluster_items(bases, placed, cluster):
    """Loose items (docs/terrain/commonwealth-build-plan.md section 3): the placed references named by cluster["items"]
    (by FO4 source key; make_cluster.py items: FO4 MiscItem / Ingestible) leave the STAT placement and become item
    entries for TerrainOverlays, exactly as containers: one native MISC per FO4 base (edid FO4Core_misc_<6 hex>_<plugin>,
    item_edid) with the converted model of the reference's base and the entry's name, value (credits) and weight, and
    the reference's cell / position / rotation / scale and original reference index (the writer reserves that slot).
    Returns (placed without them, items). ValueError for a source listed twice, a reference that is not placed by this
    build or is initially disabled, a missing name, a value that is not a whole number >= 0, a weight that is not a
    number >= 0, or two entries of one edid that disagree on name, value, weight or model (the writer shares one record)."""
    wanted = {}
    for e in cluster.get("items", []):
        if e["src"] in wanted:
            raise ValueError(f"{e['src']} is listed twice in items")
        wanted[e["src"]] = e
    keep, items, source_by_edid = [], [], {}
    for reference_index, p in enumerate(placed):
        e = wanted.pop(p["src"], None)
        if e is None:
            keep.append(p)
            continue
        if p.get("disabled"):
            raise ValueError(f"{p['src']} is initially disabled in FO4; not an item to pick up")
        name, value, weight = e.get("name"), e.get("value"), e.get("weight")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{p['src']}: an item needs a name")
        if type(value) is not int or not 0 <= value <= 2 ** 31 - 1:        # the record's DATA value is an int32
            raise ValueError(f"{p['src']}: item value {value!r} is not a whole number in 0..2147483647")
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0 or weight > 3.4028234663852886e38:
            raise ValueError(f"{p['src']}: item weight {weight!r} is not a float32 number >= 0")
        b = bases[p["base"]]
        edid = item_edid(e.get("base"), p["src"])
        identity = ("base" if e.get("base") else "reference", container_source_key(e.get("base") or p["src"]))
        if source_by_edid.setdefault(edid.casefold(), identity) != identity:
            raise ValueError(f"item {edid} aliases distinct source identities")
        items.append({"src": p["src"], "edid": edid, "reference_index": reference_index,
                      "model": b["model"], "name": name, "value": value, "weight": float(weight),
                      "cell": p["cell"], "pos": p["pos"], "rot": p["rot"], "scale": p["scale"]})
    if wanted:
        raise ValueError(f"references not placed by this build: {sorted(wanted)}")
    seen = {}
    for it in items:
        sig = (it["name"], it["value"], struct.unpack("<f", struct.pack("<f", it["weight"]))[0] + 0.0,   # float32 as written; -0.0 == 0.0
               it["model"].casefold())
        first = seen.setdefault(it["edid"], (it["src"], sig))
        if first[1] != sig:
            raise ValueError(f"{it['src']} and {first[0]} share item {it['edid']} with a different name, value, weight or model")
    return keep, items


def one_line(text):
    """A non-empty single-line string (no line break: the writer copies it into one record field)."""
    return isinstance(text, str) and bool(text.strip()) and "\n" not in text and "\r" not in text


def promoted_entries(placed, cluster, key, what, make):
    """The placed references named by cluster[key] (by FO4 source key) as promoted entries, in placement order:
    {"src", "reference_index"} + make(placed reference, cluster entry) + the reference's cell / position / rotation /
    scale. Returns (placed without them, entries). ValueError for a source listed twice, a reference this build did
    not place or one initially disabled in FO4 (the writer would give it no slot / an object nobody can use)."""
    wanted = {}
    for e in cluster.get(key) or []:
        if e["src"] in wanted:
            raise ValueError(f"{e['src']} is listed twice in {key}")
        wanted[e["src"]] = e
    keep, out = [], []
    for reference_index, p in enumerate(placed):
        e = wanted.pop(p["src"], None)
        if e is None:
            keep.append(p)
            continue
        if p.get("disabled"):
            raise ValueError(f"{p['src']} is initially disabled in FO4; not {what} to use")
        out.append(dict({"src": p["src"], "reference_index": reference_index}, **make(p, e),
                        cell=p["cell"], pos=p["pos"], rot=p["rot"], scale=p["scale"]))
    if wanted:
        raise ValueError(f"references not placed by this build: {sorted(wanted)}")
    return keep, out


def shared_base_agrees(entries, key, fields):
    """ValueError when two entries of one edid disagree on `fields` (the model compared case-blind): the writer shares
    one native base record per edid, so a second value would be lost."""
    seen = {}
    for e in entries:
        sig = tuple(e[f].casefold() if f == "model" else e[f] for f in fields)
        first = seen.setdefault(e["edid"], (e["src"], sig))
        if first[1] != sig:
            raise ValueError(f"{e['src']} and {first[0]} share {key} {e['edid']} with a different {' / '.join(fields)}")


def cluster_activators(bases, placed, cluster):
    """Activators (docs/terrain/commonwealth-build-plan.md section 3): the placed references named by
    cluster["activators"] (make_cluster.py activators: FO4 Activator with a model) leave the STAT placement and become
    activator entries for TerrainOverlays: one native ACTI per FO4 base (edid FO4Core_acti_<6 hex>_<plugin>,
    activator_edid) with the converted model of the reference's base and the entry's name (None: an ACTI without a
    name, as an FO4 activator without FULL), in the reference's cell / position / rotation / scale and original
    reference index. Returns (placed without them, activators); ValueError as promoted_entries, for a name that is
    neither None nor a single line, and for two entries of one edid with another name or model."""
    def make(p, e):
        name = e.get("name")
        if name is not None and not one_line(name):
            raise ValueError(f"{p['src']}: activator name {name!r} is neither none nor one line")
        return {"edid": activator_edid(e.get("base"), p["src"]), "model": bases[p["base"]]["model"], "name": name}
    keep, out = promoted_entries(placed, cluster, "activators", "an activator", make)
    shared_base_agrees(out, "activator", ("name", "model"))
    return keep, out


def cluster_terminals(bases, placed, cluster):
    """Terminals (docs/terrain/commonwealth-build-plan.md section 3): the placed references named by
    cluster["terminals"] (make_cluster.py terminals: FO4 Terminal) leave the STAT placement and become terminal entries
    for TerrainOverlays: one native TERM per FO4 base (edid FO4Core_term_<6 hex>_<plugin>, terminal_edid) with the
    converted model and the entry's name, and its own TMLM menu (menu_edid) whose single body text is the entry's
    "body" (default TERMINAL_BODY: the FO4 text is not ported yet), in the reference's cell / position / rotation /
    scale and original reference index. Returns (placed without them, terminals); ValueError as promoted_entries, for
    a name or body that is not one non-empty line, and for two entries of one edid with another name, model or body."""
    def make(p, e):
        name, body = e.get("name"), e.get("body", TERMINAL_BODY)
        if not one_line(name):
            raise ValueError(f"{p['src']}: terminal name {name!r} is not one non-empty line")
        if not one_line(body):
            raise ValueError(f"{p['src']}: terminal body {body!r} is not one non-empty line")
        edid = terminal_edid(e.get("base"), p["src"])
        return {"edid": edid, "menu_edid": terminal_menu_edid(edid), "model": bases[p["base"]]["model"], "name": name,
                "body": body}
    keep, out = promoted_entries(placed, cluster, "terminals", "a terminal", make)
    shared_base_agrees(out, "terminal", ("name", "model", "body"))
    return keep, out


def cluster_workshops(bases, placed, cluster):
    """Settlement workshops (docs/terrain/stations.md): the placed references named by cluster["workshops"]
    (make_cluster.py workshops: FO4 Container with the workshopscript VMAD) leave the STAT placement and become workshop
    entries for TerrainOverlays: one native ACTI per FO4 base (edid FO4Core_wkshp_<6 hex>_<plugin>, workshop_edid) with
    the converted workbench model, the entry's name (default WORKSHOP_NAME) and build radius in metres (default
    WORKSHOP_RADIUS_M; PRPS OutpostBuildAreaRadius), in the reference's cell / position / rotation / scale and original
    reference index; the writer adds WorkshopKeyword and the OutpostCategory keywords of the vanilla
    OutpostPlayerHouseActivator, read from Starfield.esm. Returns (placed without them, workshops); ValueError as
    promoted_entries, for a name that is not one line, a radius that is not a finite number > 0, and for two entries of
    one edid with another name, model or radius."""
    def make(p, e):
        name, radius = e.get("name", WORKSHOP_NAME), e.get("radius", WORKSHOP_RADIUS_M)
        if not one_line(name):
            raise ValueError(f"{p['src']}: workshop name {name!r} is not one non-empty line")
        if type(radius) not in (int, float) or not math.isfinite(radius) or radius <= 0 or radius > 3.4028234663852886e38:
            raise ValueError(f"{p['src']}: workshop radius {radius!r} is not a float32 number > 0")
        return {"edid": workshop_edid(e.get("base"), p["src"]), "model": bases[p["base"]]["model"], "name": name,
                "radius": float(radius)}
    keep, out = promoted_entries(placed, cluster, "workshops", "a workshop", make)
    shared_base_agrees(out, "workshop", ("name", "model", "radius"))
    return keep, out


FLORA_INGREDIENT = "00260DF2:Starfield.esm"     # OrgCommonNutrient_Seed: FloraMaizeCrop01 PFIG until FO4 mapping
FLORA_ORGANIC_KW = 0x222E03                     # KYWD FloraTypeOrganic
FLORA_TEMPLATE = 0xEC886                        # FloraMaizeCrop01


def cluster_flora(bases, placed, cluster):
    """Harvestable plants (docs/terrain/flora.md): the placed references named by cluster["flora"] (make_cluster.py
    flora: FO4 Flora with a model) leave the STAT placement and become flora entries for TerrainOverlays: one native
    FLOR per FO4 base (edid FO4Core_flor_<6 hex>_<plugin>, flora_edid) cloned from FloraMaizeCrop01, with the converted
    model of the reference's base, the entry's name, and PFIG the entry's ingredient (default FLORA_INGREDIENT), in the
    reference's cell / position / rotation / scale and original reference index. Returns (placed without them, flora);
    ValueError as promoted_entries, for a name that is not one non-empty line, an ingredient that is not a
    Starfield.esm formkey, and for two entries of one edid with another name, model or ingredient."""
    def make(p, e):
        name, ing = e.get("name"), e.get("ingredient", FLORA_INGREDIENT)
        if not one_line(name):
            raise ValueError(f"{p['src']}: flora name {name!r} is not one non-empty line")
        try:
            master_fid(ing)
        except (TypeError, ValueError) as err:
            raise ValueError(f"{p['src']}: flora ingredient {ing!r} is not a Starfield.esm formkey") from err
        return {"edid": flora_edid(e.get("base"), p["src"]), "model": bases[p["base"]]["model"], "name": name,
                "ingredient": ing}
    keep, out = promoted_entries(placed, cluster, "flora", "flora", make)
    shared_base_agrees(out, "flora", ("name", "model", "ingredient"))
    return keep, out


def cluster_benches(bases, placed, cluster):
    """Crafting stations (docs/terrain/stations.md): the placed references named by cluster["benches"]
    (make_cluster.py benches: FO4 Furniture with a WBDT bench type and a kind from the bench table) leave the STAT
    placement and become bench entries for TerrainOverlays: the REFR keeps its slot and its base becomes the VANILLA
    Starfield bench of the entry's kind (BENCH_VANILLA: weapon / armor / chem / cooking), position / rotation / scale
    from the source; no record of our own ("fo4_model" records the converted model the STAT placement used). Returns
    (placed without them, benches); ValueError as promoted_entries, for a kind outside BENCH_VANILLA and for a "vanilla"
    that is not the kind's bench."""
    def make(p, e):
        kind = e.get("kind")
        if kind not in BENCH_VANILLA:
            raise ValueError(f"{p['src']}: bench kind {kind!r} is not one of {', '.join(BENCH_VANILLA)}")
        vanilla = e.get("vanilla", BENCH_VANILLA[kind][0])
        if source_key(vanilla) != source_key(BENCH_VANILLA[kind][0]):
            raise ValueError(f"{p['src']}: vanilla {vanilla!r} is not the {kind} bench {BENCH_VANILLA[kind][0]}")
        return {"kind": kind, "vanilla": BENCH_VANILLA[kind][0], "fo4_model": bases[p["base"]]["model"]}
    return promoted_entries(placed, cluster, "benches", "a bench", make)


def door_destination(src, d):
    """The checked destination of a scripted door: {"plugin" (a plain file name), "id" (int, the destination
    reference's plugin-local id, 1..0xFFFFFF), "ref", "cell" (6 hex, the interior door REFR and its CELL: for the
    report and the interior post-pass), "door" (the interior FO4 door), "arrival" {pos, rot} (the interior arrival
    point, metres: the interior marker's place)}; ValueError names the problem."""
    if not isinstance(d, dict):
        raise ValueError(f"{src}: a door needs a destination")
    plugin, local = d.get("plugin"), d.get("id")
    if not one_line(plugin) or any(c in plugin for c in "\\/") or not plugin.lower().endswith((".esm", ".esp", ".esl")):
        raise ValueError(f"{src}: destination plugin {plugin!r} is not a plugin file name")
    if isinstance(local, str) and re.fullmatch(r"[0-9A-Fa-f]{6}", local):
        local = int(local, 16)
    if type(local) is not int or not 1 <= local <= vmad_patch.MAX_LOCAL_ID:
        raise ValueError(f"{src}: destination id {d.get('id')!r} is not a plugin-local id in 1..{vmad_patch.MAX_LOCAL_ID:06X}")
    out = {"plugin": plugin, "id": local}
    for k in ("ref", "cell"):
        v = d.get(f"port_{k}", d.get(k))
        if not isinstance(v, str) or not re.fullmatch(r"[0-9A-Fa-f]{6}", v):
            raise ValueError(f"{src}: destination {k} {v!r} is not 6 hex digits")
        out[k] = v.upper()
    out["door"] = str(d.get("door") or "")
    # the interior arrival point (the exterior door's FO4 XTEL arrival / 70): where the interior marker goes
    # (vmad_patch.py port) and where this door's MoveTo lands the player
    a = door_arrival(src, d.get("arrival"))
    out["arrival"] = {"pos": a["pos"], "rot": a["rot"]}
    return out


def door_arrival(src, a):
    """The checked exterior arrival point of a scripted door, {"pos" (metres), "rot", "cell"} from a cluster entry's
    "return" {"arrival": {"pos", "rot"}} (the interior door's FO4 XTEL arrival / 70): where the interior door's
    MoveTo lands the player. The marker is persistent in the world's persistent cell; "cell" is the grid cell under
    its position (it may differ from the door's) and must be one of the overlay's."""
    try:
        pos = [float(v) for v in a["pos"]]
        rot = [float(v) for v in a["rot"]]
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"{src}: arrival needs pos and rot")
    if len(pos) != 3 or len(rot) != 3 or not all(_num(v) for v in pos + rot):
        raise ValueError(f"{src}: arrival position / rotation not three finite numbers")
    return {"pos": pos, "rot": rot, "cell": list(tg.sf_cell_of(pos[0], pos[1]))}


def cluster_doors(bases, placed, cluster):
    """Scripted load doors (docs/terrain/scripted-doors.md): the placed references named by cluster["doors"]
    (make_cluster.py doors: FO4 load doors whose both sides exist) leave the STAT placement and become door entries
    for TerrainOverlays: one native ACTI per FO4 door base (edid FO4Core_door_<6 hex>_<plugin>, door_edid) with the
    converted door mesh and the entry's name (default DOOR_NAME), the REFR in its slot with the FO4SF_LoadDoor VMAD
    (destination: door_destination), and an exterior arrival XMarker (arrival: door_arrival, from the entry's "return"
    arrival). Returns (placed without them, doors); ValueError as promoted_entries, for a name that is not one line, a
    bad destination or arrival, and for two entries of one edid with another name or model."""
    def make(p, e):
        name = e.get("name") or DOOR_NAME
        if not one_line(name):
            raise ValueError(f"{p['src']}: door name {name!r} is not one non-empty line")
        return {"edid": door_edid(e.get("base"), p["src"]), "model": bases[p["base"]]["model"], "name": name,
                "destination": door_destination(p["src"], e.get("destination")),
                "arrival": door_arrival(p["src"], (e.get("return") or {}).get("arrival"))}
    keep, out = promoted_entries(placed, cluster, "doors", "a door", make)
    shared_base_agrees(out, "door", ("name", "model"))
    seen = {}
    for e in out:
        d = e["destination"]
        for what, key, shown in (("destination", (d["plugin"].casefold(), d["id"]), f"{d['plugin']}:{d['id']:06X}"),
                                 ("interior door", (d["plugin"].casefold(), d["ref"]), f"{d['plugin']}:{d['ref']}")):
            first = seen.setdefault((what, key), e["src"])
            if first != e["src"]:
                raise ValueError(f"{e['src']} and {first} share the {what} {shown}")
    return keep, out


# Step C (docs/spikes/load-door-animations.md; --animated-doors <manifest>, off by default): the exterior side of a
# scripted load door opens before the trip, as the interior side does in a port staged with interior_batch.py
# --animated-doors. The manifest is that port's door_anim manifest (convert_batch --rig-load-doors, load_door_anim.py
# plan / flags / sounds): the rigged NIF it names lives in FO4Port's archive, which the game loads with the port.
ANIM_KEYS = ("anim_graph", "skeleton", "animations", "bounds", "open_sound", "close_sound")


def animate_doors(doors, manifest, source_of):
    """Door entries (cluster_doors) whose FO4 model (source_of[src], the base's FO4 source) has load_door.anim in the
    manifest gain "anim" {anim_graph, skeleton, animations, open_seconds[, bounds, open_sound, close_sound,
    fo4_door_flags]}, the rig's model (the twin's when the rig is borrowed) and the position shifted by the rig's
    origin offset (rotated and scaled as exterior.place shifts a rigged door; the cell follows the shifted position).
    Returns (new entries, rows {"src", "edid", "animated", "reason"}); entries without a rig are returned unchanged.
    ValueError for a rig without its graph, skeleton, clips or a finite open length in 0..30 s."""
    def key(path):                                    # convert_batch's model identity, slashes and case aside
        return str(path).replace("/", "\\").lstrip("\\").lower()
    items = {key(i["source"]): i for i in manifest.get("items", []) if i.get("source")}
    out, rows = [], []
    for e in doors:
        src = source_of.get(e["src"])
        item = items.get(key(src)) if src else None
        ld = (item or {}).get("load_door")
        anim = ld.get("anim") if isinstance(ld, dict) else None
        if not isinstance(anim, dict):
            why = ("no FO4 source" if not src else "model not in the manifest" if item is None
                   else "not a load door in the manifest" if not isinstance(ld, dict) else "no rig (load_door.anim)")
            rows.append({"src": e["src"], "edid": e["edid"], "animated": False, "reason": why})
            out.append(e)
            continue
        missing = [k for k in ("anim_graph", "skeleton", "animations") if not anim.get(k)]
        if missing:
            raise ValueError(f"{e['src']}: load_door.anim of {src} lacks {missing}")
        seconds = anim.get("open_seconds") or 0.0
        if not (isinstance(seconds, (int, float)) and math.isfinite(seconds) and 0.0 <= seconds <= 30.0):
            raise ValueError(f"{e['src']}: open seconds {seconds!r} outside 0..30")
        rig = {k: anim[k] for k in ANIM_KEYS if anim.get(k) is not None}
        rig["open_seconds"] = float(seconds)
        if isinstance(ld.get("fo4_door_flags"), int):
            rig["fo4_door_flags"] = ld["fo4_door_flags"] & 0x7E
        off = anim.get("origin_offset") or [0.0, 0.0, 0.0]
        m = exterior.ref_matrix(e["rot"])
        pos = [round(e["pos"][a] + e["scale"] * sum(m[3 * a + k] * off[k] for k in range(3)), 5) for a in range(3)]
        new = dict(e, model=anim.get("model") or item["model"], anim=rig, pos=pos, cell=list(tg.sf_cell_of(pos[0], pos[1])))
        rows.append({"src": e["src"], "edid": e["edid"], "animated": True, "reason": None})
        out.append(new)
    shared_base_agrees(out, "door", ("name", "model"))
    seen = {}
    for e in out:
        first = seen.setdefault(e["edid"], (e["src"], e.get("anim")))
        if first[1] != e.get("anim"):
            raise ValueError(f"{e['src']} and {first[0]} share door {e['edid']} with a different rig")
    return out, rows


def animated_door_bases(objects, ids):
    """Local ids of the DOOR bases of step C's animated doors (formids.json doors[src]["base"] of entries with "anim")."""
    got = ids.get("doors") or {}
    return {int(got[e["src"]]["base"], 16) for e in objects.get("doors") or []
            if e.get("anim") and isinstance(got.get(e["src"]), dict) and "base" in got[e["src"]]}


def door_arrivals_inside(doors, ov):
    """ValueError for a door whose arrival marker falls outside the overlay's cells (off the overlay's terrain; the
    writer refuses it too)."""
    lo, hi = ov["cell_min"], ov["cell_max"]
    for e in doors:
        c = e["arrival"]["cell"]
        if not (lo <= c[0] <= hi and lo <= c[1] <= hi):
            raise ValueError(f"{e['src']}: arrival marker in cell {c}, outside the overlay's cells {lo}..{hi}")


# objects.json / formids.json key, native base record, in the writer's allocation order (CONT, MISC, ACTI, TERM + TMLM,
# then the workshops' ACTI, then flora FLOR; the doors' ACTI and arrival markers come last, after the lights);
# VANILLA_PROMOTED: classes whose REFR binds to a record of the master (no base of our own)
PROMOTED = (("containers", "CONT"), ("items", "MISC"), ("activators", "ACTI"), ("terminals", "TERM"), ("workshops", "ACTI"),
            ("flora", "FLOR"), ("doors", "ACTI"))
VANILLA_PROMOTED = (("benches", "FURN"),)
ALL_PROMOTED = PROMOTED + VANILLA_PROMOTED
APPENDED = ("doors",)               # promoted classes whose bases (and markers) are allocated after everything else
PROMOTE_FN = {"containers": cluster_containers, "items": cluster_items, "activators": cluster_activators,
              "terminals": cluster_terminals, "workshops": cluster_workshops, "flora": cluster_flora,
              "benches": cluster_benches, "doors": cluster_doors}
SINGULAR = {"containers": "container", "items": "item", "activators": "activator", "terminals": "terminal",
            "workshops": "workshop", "flora": "flora", "benches": "bench", "doors": "door"}


def source_key(value):
    """A FO4 source identity compared ASCII-case-blind (Windows plugin names), other spelling kept as exported."""
    return str(value).translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))


def master_fid(formkey, masters=("Starfield.esm",)):
    """The file-local form id of a master's record ("2B6A63:Starfield.esm" -> 0x002B6A63 with Starfield.esm as master
    0), as a REFR of this plugin names it. ValueError for a plugin that is not a master."""
    local, _, plugin = str(formkey).partition(":")
    names = [m.casefold() for m in masters]
    if plugin.casefold() not in names:
        raise ValueError(f"{formkey}: {plugin} is not a master of this plugin ({', '.join(masters)})")
    return (names.index(plugin.casefold()) << 24) | int(local, 16)


def cluster_promote(bases, placed, cluster):
    """--cluster: every promoted class (ALL_PROMOTED: containers, items, activators, terminals, workshops, flora,
    benches, doors) from one cluster file, each judged on the same unpromoted placement list, so every promoted entry's
    reference_index is its slot in that list whichever class it joins. Returns (placed without every promoted
    reference, {class: entries} for every class). ValueError as the class functions, for a source listed in two
    classes, and for one edid of a class standing for two FO4 sources. Full-source promoted names avoid punctuation
    and extension aliases; this guard still refuses any actual collision rather than merging two FO4 bases."""
    listed = {}
    for k, _sig in ALL_PROMOTED:
        for e in cluster.get(k) or []:
            other = listed.setdefault(e["src"], k)
            if other != k:
                a, b = (("an " if w[0] in "aeiou" else "a ") + w for w in (SINGULAR[other], SINGULAR[k]))
                raise ValueError(f"{e['src']} is listed as both {a} and {b}")
    promoted = {}
    for k, _sig in ALL_PROMOTED:
        _, promoted[k] = PROMOTE_FN[k](bases, placed, cluster)
        base_of = {e["src"]: e.get("base") for e in cluster.get(k) or []}
        source_of = {}
        for e in promoted[k]:
            if "edid" not in e:                               # a vanilla-base class names no record of its own
                continue
            b = base_of.get(e["src"])
            identity = ("base", source_key(b)) if b else ("reference", source_key(e["src"]))
            first = source_of.setdefault(e["edid"].casefold(), identity)
            if first != identity:
                raise ValueError(f"{k}: {e['edid']} would stand for two FO4 sources ({first[1]} and {identity[1]})")
    gone = {e["src"] for entries in promoted.values() for e in entries}
    return [p for p in placed if p["src"] not in gone], promoted


def check_reference_slots(objects, ids):
    """Check declared promotion slots, not native behavior or cross-export persistence. Every promoted class
    (ALL_PROMOTED) is one ordered list of promoted sources: with the remaining refs they rebuild the unpromoted order,
    every promoted source keeps its original slot and every other reference its id; the new bases (CONT, MISC, ACTI,
    TERM, the workshops' ACTI) and the terminals' TMLM menus follow every reserved slot, one base per edid within a
    class (for entries that name one), no base shared by two classes, and one menu per terminal edid that is no base;
    a bench declares its kind's vanilla base (BENCH_VANILLA), no base of this plugin."""
    promoted = [(k, e) for k, _sig in ALL_PROMOTED for e in (objects.get(k) or [])]
    if not promoted:
        return
    total = len(objects["refs"]) + len(promoted)
    indices = [e.get("reference_index") for _k, e in promoted]
    if any(type(i) is not int or not 0 <= i < total for i in indices) or len(set(indices)) != len(indices):
        raise ValueError("invalid or duplicate original reference_index")
    order = [r["src"] for r in objects["refs"]]
    for _k, e in sorted(promoted, key=lambda ke: ke[1]["reference_index"]):
        order.insert(e["reference_index"], e["src"])
    if len({src.casefold() for src in order}) != total:
        raise ValueError("duplicate source reference identity")
    try:
        declared = {}
        if set(ids["refs"]) != {r["src"] for r in objects["refs"]}:
            raise ValueError("declared source reference set differs from objects")
        for k, _sig in ALL_PROMOTED:
            have = ids.get(k) or {}
            if set(have) != {e["src"] for e in (objects.get(k) or [])}:
                raise ValueError(f"declared {k} source reference set differs from objects")
            declared.update(have)
        first = max(int(value, 16) for value in ids["bases"].values()) + 1
        for slot, src in enumerate(order):
            value = declared[src]["ref"] if src in declared else ids["refs"][src]
            if int(value, 16) != first + slot:
                raise ValueError(f"{src}: declared reference moved from original slot {slot}")
        for k, _sig in VANILLA_PROMOTED:
            for e in objects.get(k) or []:
                if source_key(e["vanilla"]) != source_key(BENCH_VANILLA[e["kind"]][0]):
                    raise ValueError(f"{k}: {e['src']} vanilla {e['vanilla']} is not the {e['kind']} bench")
                v = ids[k][e["src"]]
                if source_key(v["base"]) != source_key(e["vanilla"]) or v.get("kind") != e["kind"]:
                    raise ValueError(f"{k}: {e['src']} declared on {v['base']} ({v.get('kind')}), not its vanilla "
                                     f"{e['vanilla']} ({e['kind']})")
        owner = {}                                            # new base -> (class, edid)
        for k, _sig in PROMOTED:
            edid_of = {e["src"]: e.get("edid") for e in (objects.get(k) or [])}
            base_of = {}
            for src, v in (ids.get(k) or {}).items():
                base = int(v["base"], 16)                     # shared by the references of one FO4 base
                if base < first + total:
                    raise ValueError(f"{SINGULAR[k]} base overlaps reserved original identities")
                if k in APPENDED and "arrival" in v and int(v["arrival"], 16) < first + total:
                    raise ValueError(f"{SINGULAR[k]} arrival marker overlaps reserved original identities")
                if owner.setdefault(base, (k, edid_of[src]))[0] != k:
                    raise ValueError(f"{k}: base {v['base']} is also a base of another promoted class ({owner[base][0]})")
                if edid_of[src] is None:
                    continue
                if base_of.setdefault(edid_of[src], base) != base:
                    raise ValueError(f"{k}: {edid_of[src]} declared with two bases")
                if owner[base] != (k, edid_of[src]):
                    raise ValueError(f"{k}: base {v['base']} declared for two edids")
        edid_of = {e["src"]: e["edid"] for e in (objects.get("terminals") or [])}
        menu_of = {}
        for src, v in (ids.get("terminals") or {}).items():
            menu = int(v["menu"], 16)
            if menu < first + total:
                raise ValueError("terminal menu overlaps reserved original identities")
            if menu in owner:
                raise ValueError(f"terminal menu {v['menu']} is also a promoted base ({owner[menu][0]})")
            if menu_of.setdefault(edid_of[src], menu) != menu:
                raise ValueError(f"terminals: {edid_of[src]} declared with two menus")
        if len(set(menu_of.values())) != len(menu_of):
            raise ValueError("terminals: one menu declared for two terminal edids")
    except (KeyError, TypeError) as e:
        raise ValueError("missing or invalid declared reference identities") from e


def close(actual, expected, tol):
    """True when two numbers, or two equally long number lists, are all finite and within tol (NaN never is: a
    comparison with NaN is False, so a check written as "difference > tol" would pass it; Codex's review of #235)."""
    a = list(actual) if isinstance(actual, (list, tuple)) else [actual]
    b = list(expected) if isinstance(expected, (list, tuple)) else [expected]
    return (len(a) == len(b) and all(type(x) in (int, float) and math.isfinite(x) for x in a + b)
            and all(abs(x - y) <= tol for x, y in zip(a, b)))


def record_text(data):
    """A plugin's zero-terminated string field (None when absent): UTF-8 when it decodes, else cp1252."""
    if data is None:
        return None
    raw = bytes(data).split(b"\0", 1)[0]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def promoted_record_check(recs, own_prefix, objects, ids, masters=("Starfield.esm",)):
    """Raw record check of every promoted entry (ALL_PROMOTED): its REFR (formids.json <class>[src]["ref"]) names its
    declared native base, that base is a CONT / MISC / ACTI / TERM with the entry's edid and model, a MISC also its
    name, value and weight, an ACTI its name (no FULL for an entry without one), a TERM its name and, in DNAM, its
    declared TMLM menu, which carries the menu edid, the name and exactly one body text (BTXT) = the entry's body and no
    menu item, a workshop ACTI its name, WorkshopKeyword in KWDA, PRPS OutpostBuildAreaRadius = its radius and no
    VMAD (workshop_problems); a bench REFR names its vanilla FURN of the master (master_fid), which lives outside this
    plugin; position / rotation / scale are as objects.json (finite and within tolerance). Returns problems."""
    from fo4sf import fo4land
    by_fid = {r["fid"]: r for r in recs}
    problems = []
    for k, sig in ALL_PROMOTED:
        for e in objects.get(k) or []:
            v = (ids.get(k) or {}).get(e["src"])
            if v is None:
                problems.append(f"{e['src']}: not in formids.json {k}")
                continue
            ref_fid = own_prefix | int(v["ref"], 16)
            rec = by_fid.get(ref_fid)
            if rec is None or rec["sig"] != "REFR":
                problems.append(f"{e['src']}: no REFR {ref_fid:08X}")
                continue
            if k in dict(VANILLA_PROMOTED):
                if source_key(v["base"]) != source_key(e["vanilla"]) or v.get("kind") != e["kind"]:
                    problems.append(f"{e['src']}: declared on {v['base']} ({v.get('kind')}), objects.json names {e['vanilla']} ({e['kind']})")
                    continue
                try:
                    base_fid = master_fid(v["base"], masters)
                except ValueError as err:
                    problems.append(f"{e['src']}: {err}")
                    continue
                base = None
            else:
                base_fid = own_prefix | int(v["base"], 16)
                base = by_fid.get(base_fid)
                want = "DOOR" if k == "doors" and e.get("anim") else sig                # step C: an animated door
                if base is None or base["sig"] != want:
                    problems.append(f"{e['src']}: base {base_fid:08X} is not a {want}")
                    continue
            q = fo4land.parse_ref(rec["fields"])
            if q["base"] != base_fid:
                named = "no base" if q["base"] is None else f"{q['base']:08X}"         # (a REFR without NAME)
                problems.append(f"{e['src']}: REFR names {named}, declared {base_fid:08X}")
            if not (q["pos"] is not None and close(q["pos"], e["pos"], 1e-3) and close(q["rot"], e["rot"], 1e-5)
                    and close(q["scale"], e["scale"], 1e-4)):
                problems.append(f"{e['src']}: REFR position / rotation / scale differ from objects.json")
            if base is None:
                continue
            if overlay_records.edid(base) != e["edid"]:
                problems.append(f"{e['src']}: {want} edid {overlay_records.edid(base)!r} != {e['edid']!r}")
            if fo4land.zstring(overlay_records.field(base, "MODL", b"")).casefold() != e["model"].casefold():
                problems.append(f"{e['src']}: {want} model differs from {e['model']!r}")
            if want == "MISC":
                data = overlay_records.field(base, "DATA", b"")
                vw = struct.unpack_from("<if", data) if len(data) >= 8 else None
                if vw is None or vw[0] != e["value"] or not close(vw[1], e["weight"], 1e-6 * max(1.0, abs(e["weight"]))):
                    problems.append(f"{e['src']}: MISC DATA {vw} != value {e['value']}, weight {e['weight']}")
            if want in ("MISC", "ACTI", "TERM", "FLOR", "DOOR") and record_text(overlay_records.field(base, "FULL")) != e["name"]:
                problems.append(f"{e['src']}: {want} name {record_text(overlay_records.field(base, 'FULL'))!r} != {e['name']!r}")
            if want == "TERM":
                problems += terminal_menu_problems(by_fid, own_prefix, base, e, v)
            if k == "workshops":
                problems += workshop_problems(base, e, masters)
            if k == "flora":
                problems += flora_problems(base, e, masters)
    problems += door_record_problems(recs, own_prefix, objects, ids)
    return problems


def record_keywords(rec):
    """The KWDA form ids of a raw record (file-local), [] without KWDA."""
    d = overlay_records.field(rec, "KWDA", b"")
    return list(struct.unpack_from(f"<{len(d) // 4}I", d))


def record_properties(rec):
    """The PRPS object properties of a raw record as [(actor value, value, curve table)], [] without PRPS."""
    d = overlay_records.field(rec, "PRPS", b"")
    return [struct.unpack_from("<IfI", d, i) for i in range(0, len(d) - 11, 12)]


def workshop_problems(acti, e, masters=("Starfield.esm",)):
    """A promoted workshop ACTI (promoted_record_check): KWDA carries WorkshopKeyword (WORKSHOP_KEYWORD of the master),
    PRPS carries OutpostBuildAreaRadius (WORKSHOP_RADIUS_AV) = the entry's radius, no VMAD (the vanilla pre-placed
    workshop, OutpostPlayerHouseActivator, has none)."""
    out = []
    kw, av = master_fid(f"{WORKSHOP_KEYWORD:06X}:Starfield.esm", masters), master_fid(f"{WORKSHOP_RADIUS_AV:06X}:Starfield.esm", masters)
    if kw not in record_keywords(acti):
        out.append(f"{e['src']}: ACTI KWDA {[f'{k:08X}' for k in record_keywords(acti)]} lacks WorkshopKeyword {kw:08X}")
    radius = [p[1] for p in record_properties(acti) if p[0] == av]
    if len(radius) != 1 or not close(radius[0], e["radius"], 1e-4 * max(1.0, abs(e["radius"]))):
        out.append(f"{e['src']}: ACTI PRPS OutpostBuildAreaRadius {radius} != {e['radius']}")
    if overlay_records.field(acti, "VMAD") is not None:
        out.append(f"{e['src']}: ACTI carries a VMAD (the vanilla pre-placed workshop has none)")
    return out


def flora_problems(rec, e, masters=("Starfield.esm",)):
    """A promoted FLOR (promoted_record_check): KWDA carries FloraTypeOrganic (FLORA_ORGANIC_KW of the master), PFIG
    is the entry's ingredient (a master formid)."""
    out = []
    organic = master_fid(f"{FLORA_ORGANIC_KW:06X}:Starfield.esm", masters)
    if organic not in record_keywords(rec):
        out.append(f"{e['src']}: FLOR KWDA {[f'{k:08X}' for k in record_keywords(rec)]} lacks FloraTypeOrganic {organic:08X}")
    pfig = overlay_records.field(rec, "PFIG", b"")
    want = master_fid(e["ingredient"], masters)
    have = struct.unpack_from("<I", pfig)[0] if len(pfig) >= 4 else None
    if have != want:
        out.append(f"{e['src']}: FLOR PFIG {None if have is None else f'{have:08X}'} != {want:08X} ({e['ingredient']})")
    return out


def station_master_check(sf_esm, recs, own_prefix, objects, ids, masters=("Starfield.esm",)):
    """The station records against Starfield.esm itself (raw, src/fo4sf/fo4station): every workshop ACTI's KWDA is
    exactly WorkshopKeyword (KYWD WORKSHOP_KEYWORD, edid WorkshopKeyword) followed by the OutpostCategory* keywords the
    vanilla OutpostPlayerHouseActivator (WORKSHOP_TEMPLATE) carries, in its order, its PRPS names AVIF
    OutpostBuildAreaRadius; every bench kind's vanilla base is a FURN whose WBDT bench type and recipe keyword are the
    kind's (BENCH_VANILLA). Returns problems; [] without stations."""
    from fo4sf import fo4station
    workshops, benches = objects.get("workshops") or [], objects.get("benches") or []
    if not workshops and not benches:
        return []
    problems = []
    wanted = {WORKSHOP_TEMPLATE, WORKSHOP_KEYWORD, WORKSHOP_RADIUS_AV} | {int(v[0].split(":")[0], 16) for v in BENCH_VANILLA.values()}
    sf = fo4station.read_bases(sf_esm, wanted, ("ACTI", "KYWD", "AVIF", "FURN"))
    house = sf.get(WORKSHOP_TEMPLATE)
    kyw = fo4station.read_bases(sf_esm, (house or {}).get("keywords") or [], ("KYWD",))
    if workshops:
        if house is None or house["type"] != "ACTI":
            problems.append(f"Starfield.esm: no ACTI {WORKSHOP_TEMPLATE:06X} (OutpostPlayerHouseActivator)")
        if (sf.get(WORKSHOP_KEYWORD) or {}).get("edid") != "WorkshopKeyword":
            problems.append(f"Starfield.esm: KYWD {WORKSHOP_KEYWORD:06X} is not WorkshopKeyword")
        if (sf.get(WORKSHOP_RADIUS_AV) or {}).get("edid") != "OutpostBuildAreaRadius":
            problems.append(f"Starfield.esm: AVIF {WORKSHOP_RADIUS_AV:06X} is not OutpostBuildAreaRadius")
        categories = [k for k in (house or {}).get("keywords") or [] if (kyw.get(k) or {}).get("edid", "").startswith("OutpostCategory")]
        if not categories:
            problems.append(f"Starfield.esm: ACTI {WORKSHOP_TEMPLATE:06X} carries no OutpostCategory keyword")
        want = [master_fid(f"{k:06X}:Starfield.esm", masters) for k in [WORKSHOP_KEYWORD] + categories]
        by_fid = {r["fid"]: r for r in recs}
        seen = set()
        for e in workshops:
            v = (ids.get("workshops") or {}).get(e["src"])
            if v is None or v["base"] in seen:
                continue
            seen.add(v["base"])
            acti = by_fid.get(own_prefix | int(v["base"], 16))
            if acti is None:
                continue                                          # promoted_record_check reports it
            got = record_keywords(acti)
            if got != want:
                problems.append(f"{e['edid']}: KWDA {[f'{k:08X}' for k in got]} != WorkshopKeyword + "
                                f"{[(kyw.get(k) or {}).get('edid') for k in categories]}")
            if [p[0] for p in record_properties(acti)] != [master_fid(f"{WORKSHOP_RADIUS_AV:06X}:Starfield.esm", masters)]:
                problems.append(f"{e['edid']}: PRPS {record_properties(acti)} is not one OutpostBuildAreaRadius property")
    for kind in sorted({e["kind"] for e in benches}):
        key, wbdt, recipe = BENCH_VANILLA[kind]
        b = sf.get(int(key.split(":")[0], 16))
        if b is None or b["type"] != "FURN":
            problems.append(f"{kind}: {key} is not a FURN of Starfield.esm")
        elif b.get("wbdt") != wbdt or recipe not in (b.get("keywords") or []):
            problems.append(f"{kind}: {key} ({b['edid']}) WBDT {b.get('wbdt')} / KWDA {[f'{k:06X}' for k in b['keywords']]} "
                            f"is not bench type {wbdt} with keyword {recipe:06X}")
    return problems


def terminal_menu_problems(by_fid, own_prefix, term, e, v):
    """A promoted TERM's menu binding (promoted_record_check): DNAM = the declared TMLM, which has the entry's menu
    edid and name, one BSIZ = 1 (when written), one BTXT = the entry's body and no menu item (ISIZ 0 when written)."""
    menu_fid = own_prefix | int(v["menu"], 16)
    dnam = overlay_records.field(term, "DNAM", b"")
    if len(dnam) < 4 or struct.unpack_from("<I", dnam)[0] != menu_fid:
        return [f"{e['src']}: TERM DNAM {dnam.hex()} does not name its menu {menu_fid:08X}"]
    menu = by_fid.get(menu_fid)
    if menu is None or menu["sig"] != "TMLM":
        return [f"{e['src']}: menu {menu_fid:08X} is not a TMLM"]
    out = []
    if overlay_records.edid(menu) != e["menu_edid"]:
        out.append(f"{e['src']}: TMLM edid {overlay_records.edid(menu)!r} != {e['menu_edid']!r}")
    if record_text(overlay_records.field(menu, "FULL")) != e["name"]:
        out.append(f"{e['src']}: TMLM name differs from {e['name']!r}")
    bodies = [record_text(d) for s, d in menu["fields"] if s == b"BTXT"]
    if bodies != [e["body"]]:
        out.append(f"{e['src']}: TMLM body texts {bodies!r} != [{e['body']!r}]")
    counts = {s: struct.unpack_from("<I", d)[0] for s, d in menu["fields"] if s in (b"BSIZ", b"ISIZ") and len(d) >= 4}
    if counts.get(b"BSIZ", 1) != 1 or counts.get(b"ISIZ", 0) != 0 or any(s == b"ITXT" for s, _d in menu["fields"]):
        out.append(f"{e['src']}: TMLM counts {counts} (one body, no menu item wanted)")
    return out


def promotion_checks(recs, own_prefix, objects, ids, exp):
    """[what, ok] of the plugin's reference and promoted-base counts (check, section 2): REFR = objects + COC marker +
    anchor + every promoted entry + lights; that total unchanged by promotion (objects + promoted + lights = every
    reference stage placed before --cluster plus the lights, which leave the skipped list: exported - skipped); one
    CONT / MISC / ACTI / TERM per distinct edid of its class and one TMLM per terminal edid; and with promotions
    promoted_record_check's bindings."""
    entries = {k: objects.get(k) or [] for k, _sig in ALL_PROMOTED}
    n_promoted = sum(len(v) for v in entries.values())
    present = [(k, sig) for k, sig in ALL_PROMOTED if entries[k]]
    lights = objects.get("lights") or []
    markers = len(entries["doors"])                   # one exterior arrival XMarker REFR per door
    map_refs = len(map_marker_ids(ids))               # the map markers (docs/terrain/map-markers.md)
    out = []
    refrs = sum(1 for r in recs if r["sig"] == "REFR")
    out.append([f"{refrs:,} REFR = {len(objects['refs']):,} objects + COC marker + anchor"
                + "".join(f" + {len(entries[k]):,} {k}" for k, _sig in present)
                + (f" + {len(lights):,} lights" if lights else "")
                + (f" + {markers} door arrival markers" if markers else "")
                + (f" + {map_refs} map markers" if map_refs else ""),
                refrs == len(objects["refs"]) + 2 + n_promoted + len(lights) + markers + map_refs])
    unpromoted = exp["objects"]["exported"] - sum(exp["objects"]["skipped"].values())
    out.append([f"REFR total unchanged by promotion: {len(objects['refs']):,} objects + "
                + " + ".join(f"{len(entries[k]):,} {k}" for k, _sig in (present or PROMOTED[:2]))
                + (f" + {len(lights):,} lights" if lights else "")
                + f" = {unpromoted:,} placed", len(objects["refs"]) + n_promoted + len(lights) == unpromoted])
    # one record per distinct edid of a signature; classes sharing a signature (activators and workshops: ACTI) count together
    counted = []
    for sig in dict.fromkeys(sig for _k, sig in PROMOTED):
        classes = [k for k, s in PROMOTED if s == sig]
        named = [k for k in classes if entries[k]] or classes[:1]
        # step C's animated doors are DOOR records, counted with the bases (animated_door_bases)
        counted.append((" + ".join(named), sig, [e for k in classes for e in entries[k] if not (k == "doors" and e.get("anim"))],
                        "edid"))
    counted.append(("terminals", "TMLM", entries["terminals"], "menu_edid"))
    for key, sig, es, field in counted:
        n_recs = sum(1 for r in recs if r["sig"] == sig)
        n_edids = len({e[field].casefold() for e in es})
        if es or n_recs:
            what = "edids" if field == "edid" else "menu edids"
            out.append([f"{n_recs:,} {sig} = {n_edids:,} distinct {key} {what} ({len(es):,} {key})", n_recs == n_edids])
    for key, sig in VANILLA_PROMOTED:
        n_recs = sum(1 for r in recs if r["sig"] == sig)
        if entries[key] or n_recs:
            kinds = sorted({e["kind"] for e in entries[key]})
            out.append([f"{n_recs} {sig} of our own ({len(entries[key]):,} {key} bind to the vanilla {sig} of "
                        f"{len(kinds)} kinds: {', '.join(kinds)})", n_recs == 0])
    if present:
        pp = promoted_record_check(recs, own_prefix, objects, ids)
        sigs = list(dict.fromkeys(sig for _k, sig in present))
        detail = "; ".join(x for x in ("names" if set(sigs) - {"CONT"} else "",
                                        "MISC value, weight" if "MISC" in sigs else "",
                                        "TERM menu and body" if "TERM" in sigs else "",
                                        "workshop keyword, radius" if entries["workshops"] else "",
                                        "flora PFIG and FloraTypeOrganic" if entries["flora"] else "",
                                        "bench vanilla base" if entries["benches"] else "",
                                        "door VMAD and arrival marker" if entries["doors"] else "") if x)
        out.append([f"every promoted REFR names its {' / '.join(sigs)} (edid, model{'; ' + detail if detail else ''}) at "
                    f"its position ({len(pp)} problems: {pp[:3]})", not pp])
    return out


def formids_diff(old, new):
    """Section by section, how a build's formids.json differs from an input build's ({section: {"status", ...}}):
    "identical"; "added" / "removed" (the section only in one); for a {src: ...} section the entries kept with the
    same value, those with another value ("changed", with up to three examples), those only in one side; for a list
    (the navmeshes) "shifted" when every id moved by one constant, else "differs". Facts for the report, no verdict."""
    out = {}
    for k in sorted(set(old) | set(new), key=str):
        if k not in old:
            out[k] = {"status": "added", "count": len(new[k]) if isinstance(new[k], (dict, list)) else None}
        elif k not in new:
            out[k] = {"status": "removed", "count": len(old[k]) if isinstance(old[k], (dict, list)) else None}
        elif old[k] == new[k]:
            out[k] = {"status": "identical", "count": len(old[k]) if isinstance(old[k], (dict, list)) else None}
        elif isinstance(old[k], dict) and isinstance(new[k], dict):
            same = sorted(s for s in old[k] if s in new[k] and old[k][s] == new[k][s])
            changed = sorted(s for s in old[k] if s in new[k] and old[k][s] != new[k][s])
            out[k] = {"status": "changed", "same": len(same), "changed": len(changed),
                      "only_old": len(set(old[k]) - set(new[k])), "only_new": len(set(new[k]) - set(old[k])),
                      "examples": [{"src": s, "old": old[k][s], "new": new[k][s]} for s in changed[:3]],
                      "only_old_examples": sorted(set(old[k]) - set(new[k]))[:3]}
            if changed and all(isinstance(old[k][s], dict) and isinstance(new[k][s], dict) for s in changed):
                # a promoted class: how many changed entries keep their REFR id (only the base moved)
                out[k]["ref_kept"] = sum(1 for s in changed if old[k][s].get("ref") == new[k][s].get("ref"))
        elif isinstance(old[k], list) and isinstance(new[k], list) and len(old[k]) == len(new[k]) and old[k] and all(
                isinstance(v, str) for v in old[k] + new[k]):
            deltas = {int(b, 16) - int(a, 16) for a, b in zip(old[k], new[k])}
            out[k] = ({"status": "shifted", "count": len(old[k]), "by": deltas.pop()} if len(deltas) == 1
                      else {"status": "differs", "count": len(old[k])})
        else:
            out[k] = {"status": "differs"}
    return out


def cmd_compare_ids(a):
    """formids.json of --out against --against's, section by section (formids_diff); printed, and written to
    --out/formids_diff.json. Exit 0 always: the facts are the result."""
    old, new = load(os.path.join(a.against, "formids.json")), load(os.path.join(a.out, "formids.json"))
    diff = formids_diff(old, new)
    save(os.path.join(a.out, "formids_diff.json"), {"against": os.path.abspath(a.against), "sections": diff}, indent=1)
    for k, d in diff.items():
        line = f"  {k:<12} {d['status']}"
        if d["status"] == "changed":
            line += (f": {d['same']:,} same, {d['changed']:,} changed"
                     + (f" ({d['ref_kept']:,} of them keep their ref)" if "ref_kept" in d else "")
                     + f", {d['only_old']:,} only in {os.path.basename(a.against)}, "
                     f"{d['only_new']:,} only here; examples {d['examples']}; only there {d['only_old_examples']}")
        elif d["status"] == "shifted":
            line += f": {d['count']:,} ids, every one + 0x{d['by']:X}"
        elif d.get("count") is not None:
            line += f" ({d['count']:,})"
        print(line)
    return 0


# ------------------------------------------------------------------------------------------------------------ lights
# Exterior lights (docs/terrain/exterior-lights.md): make_cluster.py lights lists every FO4 Light reference with its
# base mapped to Starfield light fields. Core64c never placed a light (exterior.TYPE_REASONS), so no light owns a
# reserved slot: TerrainOverlays gives the light REFRs NEW FormIDs after every record of the build without lights
# (reserved REFRs, CONT / MISC / ACTI / TERM bases, TMLM menus, NAVMs), then one LIGH per FO4 base, so every FormID an earlier build had stays put.
# Light REFR header flags carried from the FO4 reference (fo4light.REF_FLAGS_CARRIED; Mutagen's PlacedObject
# LightMajorFlag in both games): 0x100 DoesNotLightWater, 0x10000 NeverFades, 0x20000 DoesNotLightLandscape
LIGHT_REF_FLAGS = 0x100 | 0x10000 | 0x20000
LIGHT_BASE_KEYS = ("time", "radius", "color", "flags", "type", "falloff", "fov", "near_clip", "flicker",
                   "flicker_effect", "lumens", "bounds", "random_anim_start")


def light_edid(base):
    """The shared LIGH's editor id from the FO4 base formkey ("08ADFA:Fallout4.esm" -> FO4Core_ligh_08adfa_fallout4)."""
    local, _, plugin = str(base).partition(":")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", local) or not plugin:
        raise ValueError(f"light base {base!r} is not <6 hex>:<plugin>")
    stem = re.sub(r"[^a-z0-9]+", "", plugin.rsplit(".", 1)[0].lower()) or "x"
    return f"{EDID_PREFIX}ligh_{local.lower()}_{stem}"


def _num(v, lo=-math.inf, hi=math.inf):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi


def check_light_base(key, b):
    """ValueError unless b holds every Starfield light field TerrainOverlays writes, in range."""
    missing = [k for k in LIGHT_BASE_KEYS if k not in b]
    if missing:
        raise ValueError(f"light base {key}: missing {missing}")
    if not (_num(b["radius"], 1e-6) and _num(b["lumens"], 1) and float(b["lumens"]).is_integer()
            and all(type(c) is int and 0 <= c <= 255 for c in b["color"]) and len(b["color"]) == 3
            and type(b["flags"]) is int and 0 <= b["flags"] < 2 ** 32 and b["type"] in (0, 1, 2)
            and b["flicker_effect"] in (0, 1, 2) and type(b["time"]) is int
            and all(_num(b[k]) for k in ("falloff", "fov", "near_clip")) and len(b["flicker"]) == 3
            and all(_num(v) for v in b["flicker"]) and len(b["bounds"]) == 2
            and all(len(c) == 3 and all(_num(v) for v in c) for c in b["bounds"])
            and type(b["random_anim_start"]) is bool):
        raise ValueError(f"light base {key}: a field out of range ({ {k: b[k] for k in LIGHT_BASE_KEYS} })")


def cluster_lights(cluster, ov, placed_srcs):
    """The cluster's "lights" (make_cluster.py lights) as TerrainOverlays entries: (lights, light_bases, skipped).
    lights = [{"src", "edid", "cell", "pos" (metres), "rot", "scale", "disabled", "radius" (delta, metres, or None),
    "lighting" ({"fov", "fade", "near_clip"} or None), "flags" (the FO4 reference's LIGHT_REF_FLAGS bits, from
    make_cluster.py's "record_flags")}] in the cluster's order; light_bases = [{"edid", "fo4_base",
    <LIGHT_BASE_KEYS>}] in first-use order (the writer's order); skipped = lights outside the overlay's cells.
    ValueError for a light that is also a placed reference, a source listed twice, an unknown base or a bad value."""
    bases = cluster.get("light_bases") or {}
    placed = {str(s).casefold() for s in placed_srcs}
    lo, hi = ov["cell_min"], ov["cell_max"]
    seen, lights, used, skipped = set(), [], {}, []
    for e in cluster.get("lights") or []:
        src = e.get("src")
        if not isinstance(src, str) or not src.strip():
            raise ValueError(f"light without a source key: {e!r}")
        if src.casefold() in placed:
            raise ValueError(f"{src}: a placed reference; a light owns no reserved slot")
        if src.casefold() in seen:
            raise ValueError(f"{src}: listed twice")
        seen.add(src.casefold())
        if "reference_index" in e:
            raise ValueError(f"{src}: a light has no original reference_index (core64c never placed it)")
        key = e.get("base")
        if key not in bases:
            raise ValueError(f"{src}: light base {key!r} not in light_bases")
        pos = exterior.metres(e["fo4_pos"])
        rot = [float(v) for v in e["rot"]]
        scale = float(e.get("scale") or 1.0)
        if not (all(_num(v) for v in pos + tuple(rot)) and _num(scale, 1e-6)):
            raise ValueError(f"{src}: position, rotation or scale not finite")
        cell = tg.sf_cell_of(pos[0], pos[1])
        if not (lo <= cell[0] <= hi and lo <= cell[1] <= hi):
            skipped.append({"formkey": src, "type": "Light", "base_editor_id": e.get("editor_id"), "model": None,
                            "exterior_cell": None, "reason": "outside_terrain",
                            "detail": f"Starfield cell {list(cell)} outside {lo}..{hi}"})
            continue
        radius = e.get("radius_delta")
        if radius is not None and not _num(radius):
            raise ValueError(f"{src}: radius delta {radius!r}")
        lig = e.get("lighting")
        if lig is not None:
            if not (all(_num(lig.get(k)) for k in ("fov", "near_clip")) and _num(lig.get("fade"), 0.01 - 1e-9, 1.6 + 1e-9)):
                raise ValueError(f"{src}: lighting {lig!r} (fade must lie in the vanilla XLIG range 0.01..1.6)")
            lig = {k: float(lig[k]) for k in ("fov", "fade", "near_clip")}
        flags = e.get("record_flags")
        if type(flags) is not int or flags < 0 or flags & ~LIGHT_REF_FLAGS:
            raise ValueError(f"{src}: record_flags {flags!r} (only the bits 0x{LIGHT_REF_FLAGS:X}; a cluster written "
                             "before #246's review has none: run make_cluster.py lights again)")
        if key not in used:
            check_light_base(key, bases[key])
            used[key] = dict({k: bases[key][k] for k in LIGHT_BASE_KEYS}, edid=light_edid(key), fo4_base=key)
        lights.append({"src": src, "edid": used[key]["edid"], "cell": list(cell), "pos": [round(v, 5) for v in pos],
                       "rot": rot, "scale": scale, "disabled": bool(e.get("disabled")), "radius": radius, "lighting": lig,
                       "flags": flags})
    return lights, list(used.values()), skipped


def stage_lights(cluster, ov, placed, promoted, skipped):
    """cluster_lights against every placed and promoted (PROMOTED) reference -> (lights, light_bases, skipped,
    outside): the lights leave `skipped` (where the selection put them, type_not_translated), a light outside the
    overlay's cells stays in it as outside_terrain, so placed + promoted + lights + skipped still add up to the export."""
    lights, light_bases, outside = cluster_lights(cluster, ov, [p["src"] for p in placed] + [c["src"] for c in promoted])
    if not lights and not outside:
        return lights, light_bases, skipped, 0
    done = {e["src"] for e in lights} | {s["formkey"] for s in outside}
    listed = {s["formkey"] for s in skipped}
    missing = sorted(done - listed)
    if missing:
        raise ValueError(f"lights the selection did not skip (not in the export, or placed): {missing[:5]}")
    return lights, light_bases, [s for s in skipped if s["formkey"] not in done] + outside, len(outside)


def check_light_identities(objects, ids):
    """Light REFRs take new FormIDs after every other record id formids.json declares (bases, reserved REFRs, CONT,
    MISC, ACTI and TERM bases, TMLM menus, NAVMs), consecutive in objects.json order; the LIGH bases follow, consecutive in first-use order, one per
    edid. ValueError names the first problem."""
    lights, lbases = objects.get("lights") or [], objects.get("light_bases") or []
    if not lights:
        return
    try:
        got = ids["lights"]
        if set(got) != {e["src"] for e in lights}:
            raise ValueError("declared light set differs from objects")
        first = max(ids_before(ids, ("lights",) + APPENDED)) + 1
        for k, e in enumerate(lights):
            if int(got[e["src"]]["ref"], 16) != first + k:
                raise ValueError(f"{e['src']}: light REFR {got[e['src']]['ref']} is not new id {first + k:06X}")
        order = list(dict.fromkeys(e["edid"] for e in lights))
        if [b["edid"] for b in lbases] != order:
            raise ValueError("light_bases not in first-use order")
        base_id = {}
        for e in lights:
            base_id.setdefault(e["edid"], set()).add(int(got[e["src"]]["base"], 16))
        for k, edid in enumerate(order):
            if base_id[edid] != {first + len(lights) + k}:
                raise ValueError(f"{edid}: LIGH {sorted(base_id[edid])} is not the one new id {first + len(lights) + k:06X}")
    except (KeyError, TypeError) as e:
        raise ValueError("missing or invalid declared light identities") from e


def ids_before(ids, appended):
    """Every local id formids.json declares except those of the `appended` classes: bases, reserved REFRs, the
    promoted classes' refs, own bases and menus, the NAVMs; of an appended class only its reserved "ref" (the door
    REFR keeps its slot: its base and arrival marker come after everything)."""
    out = [int(v, 16) for v in ids["bases"].values()] + [int(v, 16) for v in ids["refs"].values()]
    out += [int(v, 16) for v in ids.get("navmeshes") or []]
    for k, v in ids.items():                         # every promoted class ({src: {"base", "ref"}}: containers, ...)
        if k == "map_marker_refs":                   # {world: {tag: id}}, after everything: map_marker_ids
            continue
        if isinstance(v, dict) and v and all(isinstance(x, dict) for x in v.values()):
            for c in v.values():                     # (a terminal also names its TMLM "menu"; a bench a master's base)
                if k in appended:
                    out += [int(c["ref"], 16)] if k != "lights" else []
                    continue
                out += [int(c["ref"], 16)] + ([int(c["base"], 16)] if ":" not in c["base"] else [])
                out += [int(c["menu"], 16)] if "menu" in c else []
    return out


def appended_ids(ids, classes=APPENDED):
    """The local ids an appended class allocates after everything else: the arrival markers and the ACTI bases."""
    out = set()
    for k in classes:
        for c in (ids.get(k) or {}).values():
            out |= {int(c["base"], 16)} | ({int(c["arrival"], 16)} if "arrival" in c else set())
    return out


def check_door_identities(objects, ids):
    """Door REFRs keep their slots (check_reference_slots); the arrival markers take new ids after every other record
    formids.json declares, the lights included, consecutive in objects.json order; the ACTI bases follow, consecutive
    in first-use order, one per edid. ValueError names the first problem."""
    doors = objects.get("doors") or []
    if not doors:
        return
    try:
        got = ids["doors"]
        if set(got) != {e["src"] for e in doors}:
            raise ValueError("declared door set differs from objects")
        others = ids_before(ids, APPENDED)
        others += [int(c[k], 16) for c in (ids.get("lights") or {}).values() for k in ("ref", "base")]
        first = max(others) + 1
        for k, e in enumerate(doors):
            if int(got[e["src"]]["arrival"], 16) != first + k:
                raise ValueError(f"{e['src']}: arrival marker {got[e['src']]['arrival']} is not new id {first + k:06X}")
        order = list(dict.fromkeys(e["edid"] for e in doors))
        base_id = {}
        for e in doors:
            base_id.setdefault(e["edid"], set()).add(int(got[e["src"]]["base"], 16))
        for k, edid in enumerate(order):
            if base_id[edid] != {first + len(doors) + k}:
                raise ValueError(f"{edid}: ACTI {sorted(base_id[edid])} is not the one new id {first + len(doors) + k:06X}")
    except (KeyError, TypeError) as e:
        raise ValueError("missing or invalid declared door identities") from e


def lights_after(recs, own_index, ids):
    """(first id of a light record, last id of any other record of this plugin): the LIGHs and the light REFRs
    (formids.json "lights") must all come after the rest, the doors' appended records excepted (they come after the
    lights: doors_after). own_index = the plugin's master count."""
    light_refs = {int(v["ref"], 16) for v in (ids.get("lights") or {}).values()}
    after = appended_ids(ids) | map_marker_ids(ids)
    own = [r for r in recs if (r["fid"] >> 24) == own_index and r["fid"] & 0xFFFFFF not in after]

    def is_light(r):
        return r["sig"] == "LIGH" or (r["sig"] == "REFR" and r["fid"] & 0xFFFFFF in light_refs)
    first = min((r["fid"] & 0xFFFFFF for r in own if is_light(r)), default=None)
    last = max((r["fid"] & 0xFFFFFF for r in own if not is_light(r)), default=0)
    return first, last


def doors_after(recs, own_index, ids):
    """(first id of a door's appended record, last id of any other record of this plugin): the arrival markers and
    the door ACTIs come after everything, the lights included (the map markers, after them, aside: map_marker_problems)."""
    after = appended_ids(ids)
    marks = map_marker_ids(ids)
    own = [r["fid"] & 0xFFFFFF for r in recs if (r["fid"] >> 24) == own_index and r["fid"] & 0xFFFFFF not in marks]
    first = min((f for f in own if f in after), default=None)
    last = max((f for f in own if f not in after), default=0)
    return first, last


def door_record_problems(recs, own_prefix, objects, ids):
    """Raw door records against objects.json (beyond promoted_record_check's ACTI edid / model / name and the REFR's
    base and placement): every door ACTI carries PNAM cc4c3300, FNAM 0 and JNAM 360 (the vanilla majority, as the
    activators) and no VMAD; every door REFR a VMAD that decodes to one local FO4SF_LoadDoor script whose edited
    DestinationPlugin / DestinationId are the entry's destination and DestinationX / Y / Z its destination.arrival
    position (the interior marker's), with UseDestinationPosition true (vmad_patch.load_door_target: the six-property
    shape; floats without the bool, or a false bool, are refused); every arrival marker (formids.json
    doors[src]["arrival"]) a PERSISTENT (0x400), enabled REFR of XMarker at the arrival position / rotation, no scale
    (its group: check's door_marker_groups). Returns problems, never an exception."""
    from fo4sf import fo4land
    by_fid = {r["fid"]: r for r in recs}
    got = ids.get("doors") or {}
    problems = []
    for e in objects.get("doors") or []:
        v = got.get(e["src"])
        if not isinstance(v, dict) or not all(k in v for k in ("base", "ref", "arrival")):
            problems.append(f"{e['src']}: not declared in formids.json doors (base, ref, arrival)")
            continue
        acti = by_fid.get(own_prefix | int(v["base"], 16))
        if acti is not None and acti["sig"] == "DOOR" and e.get("anim"):           # step C: the rig's graph on the DOOR
            if overlay_records.field(acti, "VMAD") is not None:
                problems.append(f"{e['src']}: the DOOR carries a VMAD (the script goes on the REFR)")
            if e["anim"]["anim_graph"].encode("utf-8") not in b"".join(d for _s, d in acti["fields"]):
                problems.append(f"{e['src']}: DOOR does not name its graph {e['anim']['anim_graph']}")
        if acti is not None and acti["sig"] == "ACTI":
            pnam, fnam, jnam = (overlay_records.field(acti, s) for s in ("PNAM", "FNAM", "JNAM"))
            if pnam != bytes.fromhex("cc4c3300") or fnam != b"\0\0" or jnam != struct.pack("<H", 360):
                problems.append(f"{e['src']}: ACTI PNAM {pnam and pnam.hex()} FNAM {fnam and fnam.hex()} JNAM {jnam and jnam.hex()}")
            if overlay_records.field(acti, "VMAD") is not None:
                problems.append(f"{e['src']}: the ACTI carries a VMAD (the script goes on the REFR)")
        rec = by_fid.get(own_prefix | int(v["ref"], 16))
        if rec is None or rec["sig"] != "REFR":
            problems.append(f"{e['src']}: no REFR {own_prefix | int(v['ref'], 16):08X}")
        else:
            vm = [d for s, d in rec["fields"] if s == b"VMAD"]
            anim = e.get("anim")
            target = vmad_patch.animated_load_door_target if anim else vmad_patch.load_door_target
            try:
                dest = target(vm[0]) if len(vm) == 1 else None
            except ValueError as err:
                dest = f"bad: {err}"
            want = (e["destination"]["plugin"], int(e["destination"]["id"]), e["destination"]["arrival"]["pos"])
            if not (isinstance(dest, tuple) and dest[:2] == want[:2] and vmad_patch.same_position(dest[2], want[2])):
                problems.append(f"{e['src']}: REFR VMAD {dest} != {want}")
            elif anim and not close([dest[3]], [anim["open_seconds"]], 1e-5):
                problems.append(f"{e['src']}: REFR OpenSeconds {dest[3]} != {anim['open_seconds']}")
            if vm and [s for s, _d in rec["fields"]][:2] not in ([b"VMAD", b"NAME"], [b"EDID", b"VMAD"]):
                problems.append(f"{e['src']}: VMAD not first after EDID ({[s.decode() for s, _d in rec['fields']][:3]})")
        mk = by_fid.get(own_prefix | int(v["arrival"], 16))
        if mk is None or mk["sig"] != "REFR":
            problems.append(f"{e['src']}: no arrival marker REFR {own_prefix | int(v['arrival'], 16):08X}")
            continue
        q = fo4land.parse_ref(mk["fields"])
        a = e["arrival"]
        if q["base"] != XMARKER:
            problems.append(f"{e['src']}: arrival marker base {q['base']} is not XMarker {XMARKER:08X}")
        if not (q["pos"] is not None and close(q["pos"], a["pos"], 1e-3) and close(q["rot"], a["rot"], 1e-5)
                and overlay_records.field(mk, "XSCL") is None):
            problems.append(f"{e['src']}: arrival marker position / rotation / scale differ from objects.json")
        if mk["flags"] & (0x400 | 0x800) != 0x400:
            problems.append(f"{e['src']}: arrival marker flags 0x{mk['flags']:X} (persistent and enabled wanted)")
    return problems


def map_marker_ids(ids):
    """Local ids of the map-marker REFRs formids.json declares (TerrainOverlays: "map_marker_refs" {world: {tag: id}},
    and "map_markers" {world: first id}). They come after every other record, the doors' included."""
    out = {int(v, 16) for v in (ids.get("map_markers") or {}).values()}
    out |= {int(v, 16) for tags in (ids.get("map_marker_refs") or {}).values() for v in tags.values()}
    return out


def is_map_marker_ref(rec):
    """A REFR of STAT MapMarker 00000010 (Starfield.esm, master index 0)."""
    return rec["sig"] == "REFR" and (overlay_records.field(rec, "NAME", b"") or b"")[:4] == struct.pack(
        "<I", map_markers.MAPMARKER_STAT)


def without_marker_chain(rec):
    """(sig, flags, fields) to compare a core64 record with its core64c copy: a Location's LCSR / LCID (the map-marker
    chain, rewritten for core64c's own markers) left out."""
    fields = rec["fields"]
    if rec["sig"] == "LCTN":
        fields = [(s, v) for s, v in fields if s not in (b"LCSR", b"LCID")]
    return rec["sig"], rec["flags"], fields


def with_world_data(rec, world_data, world):
    """core64's record as stage --world-border changes it (params "world_data", TerrainOverlays): the overlay world's
    WRLD with SmallWorld cleared from DATA and HNAM set; every other record as it is."""
    if not world_data or rec["sig"] != "WRLD" or overlay_records.edid(rec) != world:
        return rec
    fields = []
    for s, v in rec["fields"]:
        if s == b"DATA" and world_data.get("small_world") is False:
            v = bytes([v[0] & ~WORLD_SMALL_WORLD]) + bytes(v[1:])
        elif s == b"HNAM" and "hnam" in world_data:
            v = bytes([world_data["hnam"]])
        fields.append((s, v))
    return {**rec, "fields": fields}


def map_marker_problems(recs, own_index, ov, ids):
    """The map markers TerrainOverlays wrote for the overlay against its params (stage: "map_markers"; without them one
    at the COC): one REFR per entry, STAT MapMarker, XMRK present, persistent, at the entry's position; one LCSR
    MapMarkerRefType row per marker on the overlay's Location (this world, grid Y then X as the writer writes it, tail
    0xFFFFFFFF), none in LCID (enabled, not initially disabled); every marker id after every other record of the plugin. Returns problems."""
    own = own_index << 24
    want = ov.get("map_markers") or [{"tag": "RedRocket", "pos": ov["spawn"], "cell": ov["spawn_cell"]}]
    got = (ids.get("map_marker_refs") or {}).get(ov["world"])
    if got is None and (ids.get("map_markers") or {}).get(ov["world"]):
        got = {"RedRocket": ids["map_markers"][ov["world"]]}
    if not got:
        return [f"{ov['world']}: formids.json names no map marker"]
    problems = []
    if sorted(got) != sorted(m["tag"] for m in want):
        problems.append(f"{ov['world']}: map markers {sorted(got)} != params {sorted(m['tag'] for m in want)}")
    by = {r["fid"]: r for r in recs}
    from fo4sf import fo4land
    for m in want:
        if m["tag"] not in got:
            continue
        r = by.get(own | int(got[m["tag"]], 16))
        if r is None or not is_map_marker_ref(r):
            problems.append(f"{m['tag']}: no MapMarker REFR {got[m['tag']]}")
            continue
        if overlay_records.field(r, "XMRK") is None:
            problems.append(f"{m['tag']}: no XMRK")
        if not r["flags"] & overlay_records.PERSISTENT or r["flags"] & 0x800:
            # initially disabled (LC172's 0xC00) hid every icon in game (18 Oct): persistent and enabled wanted
            problems.append(f"{m['tag']}: not persistent and enabled (flags 0x{r['flags']:X})")
        pos = fo4land.parse_ref(r["fields"])["pos"]
        if not all(math.isfinite(v) for v in pos) or max(abs(u - v) for u, v in zip(pos, m["pos"])) > 1e-3:
            problems.append(f"{m['tag']}: position {pos} != {m['pos']}")
    wrld = [r for r in recs if r["sig"] == "WRLD" and overlay_records.edid(r) == ov["world"]]
    loc = [r for r in recs if r["sig"] == "LCTN" and overlay_records.edid(r) == ov["location"]]
    if len(wrld) != 1 or len(loc) != 1:
        return problems + [f"{ov['world']}: {len(wrld)} WRLD, {len(loc)} LCTN {ov['location']}"]
    try:
        rows = map_markers.parse_lcsr(overlay_records.field(loc[0], "LCSR", b""))
    except ValueError as e:
        return problems + [f"{ov['location']}: {e}"]
    lcid = overlay_records.field(loc[0], "LCID", b"")
    lcid = set(struct.unpack(f"<{len(lcid) // 4}I", lcid[:len(lcid) // 4 * 4]))
    rows = [e for e in rows if e["lcrt"] == map_markers.MAPMARKER_REF_TYPE]
    cell = {own | int(got[m["tag"]], 16): m["cell"] for m in want if m["tag"] in got}
    if sorted(e["refr"] for e in rows) != sorted(cell):
        have = ["%08X" % e["refr"] for e in rows]
        problems.append(f"{ov['location']}: LCSR MapMarkerRefType rows {have} != the markers "
                        f"{['%08X' % f for f in sorted(cell)]}")
    for e in rows:
        c = cell.get(e["refr"])
        if e["wrld"] != wrld[0]["fid"] or e["tail"] != map_markers.LCSR_TAIL or (
                c is not None and e["pad"] != struct.unpack("<I", struct.pack("<hh", c[1], c[0]))[0]):
            problems.append(f"{ov['location']}: LCSR row {e} (world {wrld[0]['fid']:08X}, cell {c})")
    if set(cell) & lcid:
        problems.append(f"{ov['location']}: LCID (initially disabled) lists {[f'{f:08X}' for f in sorted(set(cell) & lcid)]}")
    mm = {f & 0xFFFFFF for f in cell}
    others = [r["fid"] & 0xFFFFFF for r in recs if (r["fid"] >> 24) == own_index and r["fid"] & 0xFFFFFF not in mm]
    if mm and others and min(mm) < max(others):
        problems.append(f"map marker 0x{min(mm):06X} before the plugin's last other record 0x{max(others):06X}")
    return problems


def door_marker_groups(path, fids):
    """{fid: {"cell": its CELL's id, "grid": (x, y) or None (the world's persistent cell has no XCLC), "group": 8
    persistent / 9 temporary children}} of the wanted REFRs, from the plugin's group structure (raw walk)."""
    from fo4sf import fo4land
    buf = overlay_records.read_bytes(path)
    hsize = struct.unpack_from("<I", buf, 4)[0]
    grids, out = {}, {}

    def walk(start, end, cell, gtype):
        for item in fo4land.iter_items(buf, start, end):
            if item[0] == "GRUP":
                _g, off, gend, label, gt = item
                if gt == 6:
                    walk(off + 24, gend, struct.unpack("<I", label)[0], gt)
                else:
                    walk(off + 24, gend, cell, gt if gt in (8, 9) else gtype)
                continue
            typ, off, _flags, fid = item
            if typ == b"CELL":
                grids[fid] = next((struct.unpack_from("<ii", d) for s, d in fo4land.iter_subrecords(fo4land.record_data(buf, off))
                                   if s == b"XCLC"), None)
            elif typ == b"REFR" and fid in fids:
                out[fid] = {"cell": cell, "grid": grids.get(cell), "group": gtype}
    walk(24 + hsize, len(buf), None, None)
    return out


def door_marker_placement(where, markers, anchor):
    """Problems of the door arrival markers' placement (door_marker_groups of the markers and the anchor): each in the
    persistent children group (8) of the world's persistent cell, the anchor's cell (no grid)."""
    problems = []
    home = where.get(anchor, {}).get("cell")
    if home is None or where[anchor]["grid"] is not None:
        problems.append(f"the anchor {anchor:08X} is not in the world's persistent cell ({where.get(anchor)})")
    for fid in markers:
        w = where.get(fid)
        if w is None or w["cell"] != home or w["grid"] is not None or w["group"] != 8:
            problems.append(f"marker {fid:08X}: {w} (wanted the persistent children of the persistent cell "
                            f"{home if home is None else f'{home:08X}'})")
    return problems


def light_record_problems(recs, own_prefix, objects, ids):
    """Raw LIGH / light REFR records against objects.json: every LIGH (EDID, DAT2 radius, colour, flags, lumens, type,
    flicker effect; offsets as in Starfield.esm's own DAT2, docs/terrain/exterior-lights.md) and every light REFR (base,
    position, rotation, scale, the LIGHT_REF_FLAGS bits and Initially Disabled, XRDS, XLIG fade). Returns problems; a
    light or light base formids.json does not declare is one (check_light_identities says why), never an exception."""
    from fo4sf import fo4land
    by_fid = {r["fid"]: r for r in recs}
    got = ids.get("lights") or {}
    problems = []
    base_fid = {}
    for b in objects.get("light_bases") or []:
        any_src = next((e["src"] for e in objects.get("lights") or [] if e["edid"] == b["edid"]), None)
        if not isinstance(got.get(any_src), dict) or "base" not in got[any_src]:
            problems.append(f"{b['edid']}: no light of this base declared in formids.json")
            continue
        fid = own_prefix | int(got[any_src]["base"], 16)
        base_fid[b["edid"]] = fid
        rec = by_fid.get(fid)
        if rec is None or rec["sig"] != "LIGH":
            problems.append(f"{b['edid']}: no LIGH {fid:08X}")
            continue
        if overlay_records.edid(rec) != b["edid"]:
            problems.append(f"{b['edid']}: EDID {overlay_records.edid(rec)!r}")
        d = overlay_records.field(rec, "DAT2", b"")
        if len(d) < 58:
            problems.append(f"{b['edid']}: DAT2 of {len(d)} bytes")
            continue
        radius, = struct.unpack_from("<f", d, 4)
        flags, = struct.unpack_from("<I", d, 12)
        lumens, = struct.unpack_from("<I", d, 52)
        if (abs(radius - b["radius"]) > 1e-4 or list(d[8:11]) != list(b["color"]) or flags != b["flags"]
                or lumens != b["lumens"] or d[56] != b["type"] or d[57] != b["flicker_effect"]):
            problems.append(f"{b['edid']}: DAT2 radius {radius}, colour {list(d[8:11])}, flags 0x{flags:X}, lumens {lumens}, "
                            f"type {d[56]}, flicker {d[57]}")
    for e in objects.get("lights") or []:
        if not isinstance(got.get(e["src"]), dict) or "ref" not in got[e["src"]]:
            problems.append(f"{e['src']}: not declared in formids.json lights")
            continue
        fid = own_prefix | int(got[e["src"]]["ref"], 16)
        rec = by_fid.get(fid)
        if rec is None or rec["sig"] != "REFR":
            problems.append(f"{e['src']}: no REFR {fid:08X}")
            continue
        q = fo4land.parse_ref(rec["fields"])
        if q["base"] != base_fid.get(e["edid"]):
            problems.append(f"{e['src']}: base {q['base']:08X}")
        if (max(abs(u - v) for u, v in zip(q["pos"], e["pos"])) > 1e-3 or max(abs(u - v) for u, v in zip(q["rot"], e["rot"])) > 1e-5
                or abs(q["scale"] - e["scale"]) > 1e-4):
            problems.append(f"{e['src']}: position / rotation / scale")
        if rec["flags"] & LIGHT_REF_FLAGS != e.get("flags") or bool(rec["flags"] & 0x800) != e["disabled"]:
            problems.append(f"{e['src']}: flags 0x{rec['flags']:X}")
        xrds = overlay_records.field(rec, "XRDS")
        if (xrds is None) != (e["radius"] is None) or (xrds is not None and abs(struct.unpack_from("<f", xrds)[0] - e["radius"]) > 1e-4):
            problems.append(f"{e['src']}: XRDS")
        xlig = overlay_records.field(rec, "XLIG")
        if (xlig is None) != (e["lighting"] is None) or (xlig is not None and (len(xlig) < 24 or abs(
                struct.unpack_from("<f", xlig, 4)[0] - e["lighting"]["fade"]) > 1e-4)):
            problems.append(f"{e['src']}: XLIG")
    return problems


def place_all(a, ov):
    sel = load(os.path.join(a.work, "selected.json"))
    man = load(os.path.join(a.work, "convert", "manifest.json"))
    bases, placed, skipped_conv = exterior.place(sel, man, ov["cell_min"], ov["cell_max"], EDID_PREFIX)
    items = {i["source"].replace("/", "\\").lower(): i for i in man["items"]}
    for b in bases:
        b["collision"] = x2c.collision_kind(items[b["key"]])
    return bases, placed, skipped_conv, man


def navmesh_input(nav, ov):
    """navmesh.json (src/fo4sf/navmesh.py export) checked for stage --navmesh: a non-empty "navmeshes" list, every entry
    with a [x, y] cell inside the overlay's cells and a "triangles" list; returns it. ValueError names the first problem
    (the writer would otherwise fail halfway through a 648,358-reference build)."""
    if not isinstance(nav, dict) or not isinstance(nav.get("navmeshes"), list) or not nav["navmeshes"]:
        raise ValueError("not navmesh.export's output (a non-empty navmeshes list)")
    lo, hi = ov["cell_min"], ov["cell_max"]
    for i, n in enumerate(nav["navmeshes"]):
        c = n.get("cell") if isinstance(n, dict) else None
        if not (isinstance(c, list) and len(c) == 2 and all(isinstance(v, int) for v in c)):
            raise ValueError(f"navmesh {i}: no [x, y] cell")
        if not (lo <= c[0] <= hi and lo <= c[1] <= hi):
            raise ValueError(f"navmesh {i}: cell {c} outside the overlay's cells {lo}..{hi}")
        if not isinstance(n.get("triangles"), list) or not n["triangles"]:
            raise ValueError(f"navmesh {i}: no triangles")
    return nav


def cmd_stage(a):
    t0 = time.time()
    prm, ov = core_params(a.core)
    core_plan = load(os.path.join(a.core, "plan.json"))
    core_exp = load(os.path.join(a.core, "expected.json"))
    selrep = load(os.path.join(a.work, "selection.json"))
    bases, placed, skipped_conv, man = place_all(a, ov)
    skipped = selrep["skipped_refs"] + skipped_conv
    total = selrep["refs"] + selrep["deferred"]
    if len(placed) + len(skipped) != total:
        sys.exit(f"accounting: {len(placed)} placed + {len(skipped)} skipped != {total} exported")
    clash = sorted({b["edid"].lower() for b in bases} & terrain_edids(prm))
    if clash:
        sys.exit(f"base EditorIDs clash with core64's records: {clash}")
    print(f"{len(bases):,} bases, {len(placed):,} references placed, {len(skipped):,} skipped "
          f"({exterior.reason_counts(skipped)}); {time.time() - t0:.0f} s")

    out = a.out
    os.makedirs(out, exist_ok=True)
    base_files = x2c.copy_base_data(a.core, out)                       # BTD, its meshes\terrain copy, mask
    for tree in DATA_TREES:
        ln, cp, kp = link_tree(os.path.join(a.work, "convert", tree), os.path.join(out, "Data", tree))
        print(f"Data\\{tree}: {ln} linked, {cp} copied, {kp} kept")
    files = data_files(out)
    data_bytes = sum(b for _, b in files)
    archive = ba2_size(files)
    print(f"Data tree: {len(files):,} files, {data_bytes / 2 ** 30:.3f} GiB; one stored archive about "
          f"{archive / 2 ** 30:.3f} GiB (limit {ARCHIVE_LIMIT / 2 ** 30:.0f} GiB, budget {ARCHIVE_BUDGET / 2 ** 30:.2f})")
    if archive > ARCHIVE_BUDGET:
        sys.exit("the Data tree does not fit one archive below 4 GiB: lower convert_batch --max-texture, or split it "
                 "into region plugins with their own archives (docs/terrain/core64c.md)")

    # --cluster (R05, docs/slice/r05-cluster-plan.md; docs/terrain/commonwealth-build-plan.md section 3): the listed
    # references leave the STAT placement and become native records: "containers" (a CONT base with the converted model
    # and a vanilla inventory), "items" (loose FO4 MiscItem / Ingestible: a MISC base with the converted model, a
    # name, value and weight), "activators" (FO4 Activator: an ACTI base with the converted model and the name),
    # "terminals" (FO4 Terminal: a TERM base with the converted model and the name, with its own TMLM menu of one body
    # line), "workshops" (FO4 settlement workshop: an ACTI base with the workbench model, WorkshopKeyword, the outpost
    # category keywords and a build radius; docs/terrain/stations.md), "flora" (FO4 Flora: a FLOR base cloned from
    # FloraMaizeCrop01 with the converted model, the name and PFIG the ingredient; docs/terrain/flora.md), one base per
    # FO4 base, one temporary REFR per source reusing its original reference_index (one slot plan for every class); the
    # new CONT, MISC, ACTI, TERM + TMLM, then the workshops' ACTI and flora FLOR records follow all reserved REFRs.
    # "benches" (FO4 crafting station) keep their REFR
    # slot on the VANILLA Starfield bench of their kind: no record of our own.
    # Its "lights" (docs/terrain/exterior-lights.md, make_cluster.py lights) were never placed: new light REFRs and
    # LIGH bases after every other record
    promoted = {k: [] for k, _sig in ALL_PROMOTED}
    lights, light_bases = [], []
    if getattr(a, "cluster", None):
        cluster = load(a.cluster)
        try:
            source_of = {p["src"]: bases[p["base"]].get("source") for p in placed}
            placed, promoted = cluster_promote(bases, placed, cluster)
            if getattr(a, "animated_doors", ""):
                promoted["doors"], door_rows = animate_doors(promoted["doors"], load(a.animated_doors), source_of)
                outside = [e["src"] for e in promoted["doors"] if not (ov["cell_min"] <= e["cell"][0] <= ov["cell_max"]
                                                                       and ov["cell_min"] <= e["cell"][1] <= ov["cell_max"])]
                if outside:
                    raise ValueError(f"animated doors shifted outside the overlay's cells: {outside}")
                print(f"--animated-doors: {sum(r['animated'] for r in door_rows)} of {len(door_rows)} door(s) open before "
                      f"the trip" + "".join(f"; {r['src']}: {r['reason']}" for r in door_rows if not r["animated"]))
            door_arrivals_inside(promoted["doors"], ov)
            # exterior lights (docs/terrain/exterior-lights.md): never placed, so new REFR ids after every reserved one
            lights, light_bases, skipped, n_out = stage_lights(cluster, ov, placed,
                                                               [e for es in promoted.values() for e in es], skipped)
        except ValueError as e:
            sys.exit(f"--cluster: {e}")
        new_edids = {e[f].lower() for es in promoted.values() for e in es for f in ("edid", "menu_edid") if f in e}
        new_edids |= {b["edid"].lower() for b in light_bases}
        clash = sorted(new_edids & ({b["edid"].lower() for b in bases} | terrain_edids(prm)))
        if clash:
            sys.exit(f"--cluster: promoted EditorIDs clash with base or core64 records: {clash[:5]}")

        def summary(entries, what):
            edids = len({e["edid"] for e in entries})
            head = ", ".join(f"{e['src']} -> {e['edid']}" for e in entries[:8])
            return f"{len(entries)} {what} over {edids} base(s)" + (f" ({head}{', ...' if len(entries) > 8 else ''})" if entries else "")
        print(f"cluster {os.path.basename(a.cluster)}: "
              + "; ".join(summary(promoted[k], f"{SINGULAR[k]}(s)") for k, _sig in PROMOTED)
              + f"; {len(promoted['benches'])} bench(es) on {len({e['vanilla'] for e in promoted['benches']})} vanilla base(s)")
        if lights or n_out:
            print(f"cluster: {len(lights):,} light(s) over {len(light_bases)} LIGH bases, {n_out} outside the overlay's cells")
        for e in promoted["doors"]:
            print(f"  door {e['src']} -> {e['edid']} ({e['name']}) cell {e['cell']} -> {e['destination']['plugin']}:"
                  f"{e['destination']['id']:06X} (interior door {e['destination']['ref']} in CELL {e['destination']['cell']}); "
                  f"arrival marker at {e['arrival']['pos']} rot {e['arrival']['rot']} cell {e['arrival']['cell']}")
    objects = {"world": ov["world"], "edid_prefix": EDID_PREFIX,
               "bases": [{k: b[k] for k in ("edid", "model", "door", "source", "collision", "movable") if k in b} for b in bases],
               "refs": [{k: p[k] for k in ("src", "base", "cell", "pos", "rot", "scale", "disabled", "open_by_default")
                         if k in p} for p in placed]}
    for k, _sig in ALL_PROMOTED:
        if promoted[k]:
            objects[k] = promoted[k]
    garage_buttons = cluster_garage_buttons(promoted.get("activators") or [])
    if garage_buttons:
        objects["garage_buttons"] = garage_buttons
        print(f"cluster: {len(garage_buttons)} garage button pair(s) (DefaultActivateLinkedRefOnActivate + XLKR)")
    if lights:
        objects["lights"] = lights
        objects["light_bases"] = light_bases
    save(os.path.join(out, "objects.json"), objects)
    params = dict(prm, objects="objects.json")
    if getattr(a, "navmesh", ""):
        # Commonwealth navmesh (docs/terrain/commonwealth-build-plan.md section 4; docs/actors/navmesh-conversion.md):
        # navmesh.json = src/fo4sf/navmesh.py export over the core's FO4 NAVM (one NAVM per FO4 navmesh and Starfield
        # cell); TerrainOverlays writes the NAVM records after every object and a NAVI override with one NVMI each
        try:
            nav = navmesh_input(load(a.navmesh), ov)
        except ValueError as e:
            sys.exit(f"--navmesh: {a.navmesh}: {e}")
        shutil.copy2(a.navmesh, os.path.join(out, "navmesh.json"))
        params["navmesh"] = "navmesh.json"
        print(f"navmesh: {len(nav['navmeshes']):,} NAVM from {a.navmesh}")
    # Commonwealth map markers (docs/terrain/map-markers.md): Red Rocket on the COC arrival, Sanctuary, Vault 111 and
    # Concord on the BTD ground at their FO4 marker; TerrainOverlays writes one MapMarker REFR + LCSR row for each
    terrain = Terrain(os.path.join(out, *ov["btd_file"].split("/")))
    ground = lambda x, y: float(terrain.bilinear([x], [y])[0])  # noqa: E731
    bounds = (ov["bounds_min_m"], ov["bounds_max_m"])
    try:
        markers = map_markers.overlay_markers(ov["spawn"], bounds, ground)
        if getattr(a, "fo4_map_markers", ""):
            # every other named Commonwealth marker inside the overlay, after the four (their FormIDs stay)
            rows, left = map_markers.load_fo4_markers(load(a.fo4_map_markers))
            extra, outside = map_markers.extra_markers(rows, bounds, ground, fixed=markers)
            markers += extra
            if len({m["tag"] for m in markers}) != len(markers):
                raise ValueError("map marker tags repeat")
            save(os.path.join(out, "map_markers_left_out.json"), {"left_out": left + outside}, indent=1)
            print(f"map markers: {len(extra)} from {a.fo4_map_markers}, {len(left) + len(outside)} left out "
                  "(map_markers_left_out.json)")
    except ValueError as e:
        sys.exit(f"map markers: {e}")
    params["overlays"] = [dict(ov, map_markers=markers)]
    print(f"map markers ({len(markers)}): " + ", ".join(f"{m['name']} {m['pos']} cell {m['cell']}" for m in markers[:4])
          + (f", ... {len(markers) - 4} more" if len(markers) > 4 else ""))
    world_data = WORLD_DATA[getattr(a, "world_border", "template")]
    if world_data:
        params["world_data"] = world_data
        print(f"world border: {a.world_border} {world_data}")
    else:
        params.pop("world_data", None)
    save(os.path.join(out, "overlays_params.json"), params, indent=1)
    save(os.path.join(out, "skipped.json"), {"counts": exterior.reason_counts(skipped), "types": type_counts(skipped),
                                             "refs": skipped})
    for name in ("preview.png",):
        if os.path.isfile(os.path.join(a.core, name)):
            shutil.copy2(os.path.join(a.core, name), os.path.join(out, name))

    t1 = time.time()
    if a.sf_esm:
        subprocess.run(["dotnet", "run", "--project", os.path.join(REPO, "dotnet", "TerrainOverlays"), "-c", "Release",
                        "--", a.sf_esm, out], check=True)
    plugin_s = round(time.time() - t1, 1)

    t2 = time.time()
    sx, sy = ov["spawn"][:2]
    area = (sx - AREA_M, sy - AREA_M, sx + AREA_M, sy + AREA_M)
    world = CoreWorld(os.path.join(out, "Data"), bases, placed, terrain, area)
    if world.collision_errors:
        sys.exit(f"converted collision unreadable: {world.collision_errors}")
    print(f"local world: {len(world.placed):,} references, {len(world.model_tris):,} models, {len(world.tris):,} "
          f"collision triangles ({time.time() - t2:.0f} s)")
    plan, exp = build_plan(world, ov, core_plan[0], core_exp, views=a.views)
    save(os.path.join(out, "plan.json"), plan, indent=1)
    ids = load(os.path.join(out, "formids.json")) if os.path.exists(os.path.join(out, "formids.json")) else None
    for p in exp["points"]:
        for o in (p.get("owner"), (p.get("nearby_object") or {}).get("owner")):
            if o and ids:
                o["refr_in_plugin"] = ids["refs"][o["src"]]
    tex = dict(man["stats"].get("textures") or {})
    log_path = os.path.join(a.work, "convert", "texture_log.json")
    if os.path.isfile(log_path):
        log = load(log_path)
        caps = {}
        for v in log.values():
            caps[v["kind"]] = v["cap"]
        tex.update(caps=caps, by_kind={k: {"textures": sum(1 for v in log.values() if v["kind"] == k),
                                           "full_bytes": sum(v["bytes"] for v in log.values() if v["kind"] == k),
                                           "written_bytes": sum(v["out_bytes"] for v in log.values() if v["kind"] == k)}
                                       for k in sorted(caps)})
    expected = {
        "experiment": "terrain_core64c", "core": os.path.abspath(a.core), "base_files": base_files,
        "hypothesis": "FO4 position / 70 = core64 position in metres for terrain and objects alike (core64's origin is "
                      "CW (0, 0)); an object's collision then sits on the BTD as in FO4",
        "objects": {"exported": total, "placed": len(placed), "bases": len(bases),
                    "promoted": dict({k: len(promoted[k]) for k, _sig in ALL_PROMOTED},
                                     **{f"{SINGULAR[k]}_bases": len({e["edid"] for e in promoted[k]}) for k, _sig in PROMOTED},
                                     **{f"{SINGULAR[k]}_bases": len({e["vanilla"] for e in promoted[k]}) for k, _sig in VANILLA_PROMOTED}),
                    "doors": sum(1 for b in bases if "door" in b),
                    "initially_disabled": sum(p["disabled"] for p in placed),
                    "fo4_persistent_placed_temporary": sum(p["fo4_persistent"] for p in placed),
                    "enable_parent_not_translated": sum(p["enable_parent"] for p in placed),
                    "collision": {k: sum(1 for p in placed if bases[p["base"]]["collision"] == k)
                                  for k in sorted({b["collision"] for b in bases})},
                    **({"lights": len(lights), "light_bases": len(light_bases),
                        "lights_initially_disabled": sum(e["disabled"] for e in lights)} if lights else {}),
                    "skipped": exterior.reason_counts(skipped)},
        "data": {"files": len(files), "bytes": data_bytes, "archive_estimate": archive,
                 "archive_limit": ARCHIVE_LIMIT, "textures": tex,
                 "texture_caps": ",".join(f"{k}={v}" for k, v in sorted((tex.get("caps") or {}).items())) or "none"},
        "times_s": {"stage_place": round(t1 - t0, 1), "plugin": plugin_s, "plan": round(time.time() - t2, 1)},
        "refr_in_plugin": REFR_NOTE,
        **exp}
    save(os.path.join(out, "expected.json"), expected, indent=1)
    readme(out, prm, ov, plan, expected)
    for i, e in enumerate(plan):
        d = expected["entries"][i]
        t = d["travel"]
        print(f"entry {i + 1} ({d['role']}): {len(e['points'])} points ({d['waypoints']} waypoints) from {e['drop_z']} m, "
              f"settle {e['settle_ms']} ms, predicted {d['predicted']}, longest leg {d['longest_leg_m']} m, longest "
              f"single-axis move {t['max_axis_move_m']} m ({t['max_axis_cells']} cells), {t['hops']} runner hops, "
              f"about {t['estimated_s']} s of {t['timeout_s']} s, teleports clear {d['teleports_clear']}")
    print(f"spawn_local {expected['spawn']['spawn_local']}; missing {expected['missing']}; {time.time() - t0:.0f} s")
    return 0


def readme(out, prm, ov, plan, exp):
    pl = [prm["plugin"], prm["mars"]["plugin"]]
    base = os.path.splitext(prm["plugin"])[0]
    o, d = exp["objects"], exp["data"]
    ref = exp["reference"]
    lines = [
        "Terrain core64c (Claude, 2026-10-12). NOT deployed, NOT queued. Recipe: docs/terrain/core64c.md",
        "(branch claude/terrain-core64-objects). Base: core64 (" + exp["core"] + "): the same BTD, mask, Location,",
        "Mars registration, anchor, COC marker and FormIDs, plus EVERY Fallout 4 exterior object of the 64 x 64-cell",
        f"core that converts: {o['placed']:,} references of {o['bases']:,} models (STAT, {o['doors']} rigged DOOR) at",
        f"FO4 position / 70 in {ov['world']}, in the same plugin after core64's records. Skipped and why: skipped.json",
        f"({', '.join(f'{k} {v:,}' for k, v in o['skipped'].items())}).",
        f"Data tree {d['files']:,} files, {d['bytes'] / 2 ** 30:.2f} GiB (textures capped {d['texture_caps']}),",
        f"one stored archive of about {d['archive_estimate'] / 2 ** 30:.2f} GiB (vanilla archives stop below 4 GiB).",
        "",
        "Install (game closed). The runner does it:",
        f"  scripts/game/exp_install.py install --exp-dir <this folder> --starfield <game> --plugins {','.join(pl)} --pack",
        f"  --pack builds \"{base} - Main.ba2\" from Data\\ (Archive2 -format=General -compression=None: every entry",
        "  stored, BTD included; textures load from the General archive, verified with exp2c on 2026-10-11).",
        f"Queue: testqueue.py plan-terrain --staging <build> --exp-dir <this folder> --out <queue> --plugins {','.join(pl)} --fresh",
        "Never install together with another terrain experiment (every Mars plugin overrides MarsPlanetData). core64,",
        "core64b and core64e use the same plugin and archive names: exp_install.py uninstall first (it refuses otherwise).",
        "The installer builds the archive in %TEMP% (C:) and copies it to the game's Data folder.",
        "",
        f"Plan: {len(plan)} entries, each ONE coc {plan[0]['coc']} arrival (fresh launch). spawn_local {plan[0]['spawn_local']}",
        f"= where the player lands under the COC marker {ov['spawn']}. Heights are judged relative to {REF_LABEL}",
        f"({ref['x']}, {ref['y']} -> {ref['expect']}: open level terrain {ref['distance_from_arrival']} m from the arrival,",
        f"nothing above it within {x2c.REF_CLEAR} m), the first point of every entry.",
        f"Teleports: every one moves the player at most {MAX_AXIS_CELLS} cells ({MAX_AXIS_M:.0f} m) along each axis. "
        f"Legs longer than {WAYPOINT_SPACING_M:.0f} m",
        f"get open terrain waypoints ({WAYPOINT_PREFIX}NN: at most {WAYPOINT_MAX_SPREAD:g} m of relief under the landing "
        "disc, no object within 1 m;",
        f"judged like the probes), so the runner hops none; hop_m {HOP_M} ({HOP_WAIT_MS} ms) stays as a safety net.",
        "Why (supported hypothesis, docs/terrain/core64c.md \"Teleport rule\", scripts/terrain/teleport_audit.py):",
        "in the overlay runs so far a teleport of 3 or more cells along an axis relocated the player 8.2 to 11.8 km",
        "(\"Boundary Reached\") or hung 11 of 28 times (all 6 in core64), one of at most 2 cells landed 144 of 145 times.",
        "The runner faces north at every point and takes a screenshot there; every arrival so far was at night on Mars",
        "(the runner on claude/integration-1011 sets no time of day)" + ("." if exp.get("views") else
                                                                       "; the screenshot spots are left out (stage --views)."),
    ]
    meta = {(q["entry"], q["label"]): q for q in exp["points"]}
    for i, e in enumerate(plan):
        dd = exp["entries"][i]
        pr, t = dd["predicted"], dd["travel"]
        lines += ["", f"  {e['label']}",
                  f"  {len(e['points'])} points ({dd['waypoints']} waypoints), drop_z {e['drop_z']}, settle {e['settle_ms']} ms; "
                  f"predicted without the objects: {pr['no_objects']['verdict']} (worst {pr['no_objects']['worst_m']} m)" +
                  (f", on flat terrain: {pr['flat_terrain']['verdict']} (worst {pr['flat_terrain']['worst_m']} m)"
                   if "flat_terrain" in pr else "") +
                  f", resting on the highest surface under each 0.6 m disc: {pr['landing_max']['verdict']} (worst "
                  f"{pr['landing_max']['worst_m']} m)",
                  f"  longest leg {dd['longest_leg_m']} m, longest single-axis move {t['max_axis_move_m']} m (at most "
                  f"{t['max_axis_cells']} cells), {t['hops']} runner hops; about {t['estimated_s']} s to the last point of the "
                  f"{t['timeout_s']} s step timeout ({t['margin_s']} s to spare)"]
        for p in e["points"]:
            m = meta[(i, p["label"])]
            owner = (m.get("owner") or {}).get("edid", "")
            near = m.get("nearby_object") or {}
            what = {"terrain": "terrain (waypoint)" if m.get("waypoint") else "terrain (core64 probe)",
                    "terrain_ref": "terrain, the Z reference",
                    "terrain_covered": "core64 probe now on " + owner,
                    "terrain_near_object": f"terrain, {owner} {near.get('height', 0):.2f} m high at {near.get('distance')} m",
                    "object_top": f"top of {owner}, {m.get('discrimination', 0):.2f} m above the terrain under the disc" +
                                  (" (second drop)" if m.get("again_of") else ""),
                    "view": f"screenshot spot, {m.get('distance_to_target_m')} m south of {owner}"}[m["kind"]]
            lines.append(f"    {p['label']:<30} x {p['x']:>10.4f}  y {p['y']:>10.4f}  -> {p['expect']:.4f}   {what}")
    if o["promoted"].get("doors"):
        lines += ["", f"Scripted load doors (docs/terrain/scripted-doors.md): {o['promoted']['doors']} exterior load doors into converted",
                  f"interiors over {o['promoted']['door_bases']} ACTI bases (the converted door mesh, FULL 'Door'), each REFR in its slot with the",
                  "FO4SF_LoadDoor VMAD (DestinationPlugin / DestinationId = the interior arrival marker of the port plugin,",
                  "DestinationX / Y / Z = its position, UseDestinationPosition true) and an exterior arrival XMarker, PERSISTENT in the world's persistent cell",
                  "(new ids after every other record; formids.json \"doors\" {src: {base, ref, arrival}}).",
                  "The interior side: scripts/terrain/vmad_patch.py port over the pinned port staging (its return VMAD carries the",
                  "exterior marker's merged position, UseDestinationPosition true). The script FO4SF_LoadDoor.pex (PR #243; the",
                  "coordinates need PR #291's properties) must ride an active plugin's archive: not staged here."]
    lines += ["", "Files: " + ", ".join(pl) + ", Data\\ (core64's BTD, its meshes\\terrain copy and mask; converted meshes,",
              "geometries, materials, textures under fo4core\\), objects.json, formids.json, skipped.json, plan.json,",
              "expected.json, offline_check.json (make_core64c.py check). Uninstall: exp_install.py uninstall.",
              "Data\\ is hard-linked to the conversion work folder (no second copy): a rewrite there changes this tree. Before",
              "installing run make_core64c.py verify-data --out <this folder> (sizes and times as checked; exit 1 if any differ)."]
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# --------------------------------------------------------------------------------------------------------------- check
def abs_stats(values):
    v = np.abs(np.asarray(values, np.float64))
    return {"count": int(v.size), "median_mm": round(float(np.median(v)) * 1000, 2),
            "p95_mm": round(float(np.percentile(v, 95)) * 1000, 2), "p99_mm": round(float(np.percentile(v, 99)) * 1000, 2),
            "max_mm": round(float(v.max()) * 1000, 2), "within_1cm": int((v <= 0.01).sum()),
            "within_5cm": int((v <= 0.05).sum())}


def compound_top(fo4_data, owner, x, y, drop_z):
    """FO4's own collision top of `owner` at (x, y) below drop_z, for models whose bodies routes.collision_bodies
    skips (hknpDynamicCompoundShape): every bhkNPCollisionObject body of the source NIF decoded with Codex's
    fo4_compounds.decode_body (instances applied), placed like routes.collision_bodies places a body (node world
    transform, Havok units = metres) and then like the reference. Bodies with their own position or rotation are not
    placed (that convention is unverified, fo4collision.decode_bodies) and are counted. Returns (top, layer, report)."""
    sys.path.insert(0, os.path.join(REPO, "scripts", "game"))
    import routes
    from fo4sf import ba2, fo4_compounds, hkpackfile, nif as nifmod
    name = "meshes\\" + owner["model"].replace("/", "\\").split("\\", 1)[1]
    blob = None
    for fn in sorted(os.listdir(fo4_data)):
        if fn.lower().startswith("fallout4 - meshes") and fn.lower().endswith(".ba2"):
            arc = ba2.Ba2(os.path.join(fo4_data, fn))
            if arc.find(name) is not None:
                blob = arc.read(name)
                break
    rep = {"model": name, "bodies": 0, "leaves": 0, "skipped_body_transform": 0, "errors": []}
    if blob is None:
        rep["errors"].append("not in the FO4 mesh archives")
        return None, None, rep
    f = nifmod.parse(blob)
    world = nifmod.world_transforms(f)
    tops = []
    for i in range(len(f.blocks)):
        if f.type_of(i) != "bhkNPCollisionObject":
            continue
        target, _, data = struct.unpack_from("<iHi", f.blocks[i], 0)
        body = struct.unpack_from("<I", f.blocks[i], 10)[0] if len(f.blocks[i]) >= 14 else 0
        if not (0 <= data < len(f.blocks)) or f.type_of(data) != "bhkPhysicsSystem":
            continue
        n, = struct.unpack_from("<I", f.blocks[data], 0)
        pack_blob = f.blocks[data][4:4 + n]
        try:
            d = fo4_compounds.decode_body(pack_blob, body)
            p = hkpackfile.Packfile(pack_blob)
            sysobj = next(o for o, c in p.objects() if c == "hknpPhysicsSystemData")
            at, _nb = p.array(sysobj + 64)
            layer = p.unpack("<I", at + 96 * body + 20)[0] & 0x7F
        except (hkpackfile.PackfileError, IndexError, StopIteration, ValueError, struct.error) as e:
            rep["errors"].append(f"body {body}: {type(e).__name__}: {e}")
            continue
        rep["bodies"] += 1
        q = d["quaternion_xyzw"]
        if any(abs(v) > 1e-6 for v in d["position_havok_units"]) or abs(abs(q[3]) - 1.0) > 1e-6:
            rep["skipped_body_transform"] += 1
            continue
        tr, rot, _ = world(target)
        for leaf in d["leaves"]:
            rep["leaves"] += 1
            pts = [exterior.to_world(tuple(a + b * routes.UNIT for a, b in zip(routes.apply(rot, v), tr)),
                                     owner["pos"], owner["rot"], owner["scale"]) for v in leaf["points"]]
            z = exterior.top_z([tuple(pts[k] for k in t) for t in leaf["triangles"]], x, y, below=drop_z)
            if z is not None:
                tops.append((z, layer))
    top, layer = max(tops) if tops else (None, None)
    return top, layer, rep


def signed_stats(values):
    v = np.asarray(values, np.float64)
    return {k: round(float(np.percentile(v, q)), 4) for k, q in (("p1", 1), ("median", 50), ("p99", 99))} | {
        "min": round(float(v.min()), 4), "max": round(float(v.max()), 4)}


def archive_dry_run(archive2, out, scratch, files):
    """Build the archive exp_install.py --pack would build (Archive2 -format=General -compression=None, every top-level
    folder of Data) into `scratch`, read its header back and delete it: (report, problems)."""
    from fo4sf import ba2
    data = os.path.join(out, "Data")
    os.makedirs(scratch, exist_ok=True)
    path = os.path.join(scratch, "core64c_dry - Main.ba2")
    folders = sorted(d for d in os.listdir(data) if os.path.isdir(os.path.join(data, d)))
    t0 = time.time()
    r = subprocess.run([archive2, ",".join(folders), f"-create={path}", f"-root={data}", "-format=General",
                        "-compression=None"], cwd=data, capture_output=True, text=True)
    rep = {"seconds": round(time.time() - t0, 1), "returncode": r.returncode}
    problems = []
    try:
        if r.returncode != 0 or not os.path.isfile(path):
            return rep, [f"Archive2 failed: {(r.stdout or '')[-300:]} {(r.stderr or '')[-300:]}"]
        rep["bytes"] = os.path.getsize(path)
        arc = ba2.Ba2(path)
        rep["entries"] = len(arc.entries)
        rep["packed_entries"] = sum(1 for e in arc.entries if e.packed)
        names = {e.name.replace("\\", "/").lower() for e in arc.entries}
        want = {n.lower() for n, _ in files}
        rep["missing"] = sorted(want - names)[:20]
        rep["extra"] = sorted(names - want)[:20]
        if rep["packed_entries"]:
            problems.append(f"{rep['packed_entries']} entries packed")
        if names != want:
            problems.append("archive entries differ from the Data tree")
        return rep, problems
    finally:
        if os.path.exists(path):
            os.remove(path)


def cmd_check(a):
    import make_cw_overlays as cwo
    t0 = time.time()
    out = a.out
    prm, ov = core_params(out)
    cprm, _cov = core_params(a.core)
    plan = load(os.path.join(out, "plan.json"))
    exp = load(os.path.join(out, "expected.json"))
    objects = load(os.path.join(out, "objects.json"))
    ids = load(os.path.join(out, "formids.json"))
    checks, rep = [], {}

    def need(cond, what):
        checks.append([what, bool(cond)])

    promoted = [e for k, _sig in ALL_PROMOTED for e in (objects.get(k) or [])]
    if promoted:
        try:
            check_reference_slots(objects, ids)
        except ValueError as e:
            need(False, f"declared promotion identity: {e}")
        else:
            need(True, "declared source reference slots retained through promotion ("
                 + " + ".join(f"{len(objects.get(k) or []):,} {k}" for k, _sig in ALL_PROMOTED if objects.get(k))
                 + ", one slot plan)")
    lights = objects.get("lights") or []
    if lights:
        try:
            check_light_identities(objects, ids)
        except ValueError as e:
            need(False, f"declared light identities: {e}")
        else:
            need(True, f"{len(lights):,} light REFRs have new ids after every other record, then "
                       f"{len(objects['light_bases'])} LIGH bases")
    doors = objects.get("doors") or []
    if doors:
        try:
            check_door_identities(objects, ids)
        except ValueError as e:
            need(False, f"declared door identities: {e}")
        else:
            need(True, f"{len(doors)} door REFRs keep their slots; their arrival markers have new ids after every other "
                       f"record (lights included), then {len({e['edid'] for e in doors})} door ACTI bases")

    # 1. core64 unchanged: params, Data files, Mars plugin, every core64 record of the main plugin
    need(core_params_view(prm) == cprm and prm.get("objects") == "objects.json"
         and prm.get("navmesh") in (None, "navmesh.json"),
         "overlays_params.json = core64's + objects" + (" + navmesh" if prm.get("navmesh") else "")
         + (" + map markers" if any("map_markers" in o for o in prm["overlays"]) else ""))
    for rel in exp["base_files"] + [prm["mars"]["plugin"]]:
        need(os.path.isfile(os.path.join(a.core, *rel.split("/"))) and
             x2c.sha256(os.path.join(out, *rel.split("/"))) == x2c.sha256(os.path.join(a.core, *rel.split("/"))),
             f"{rel} byte-identical to core64")
    terrain = Terrain(os.path.join(out, *ov["btd_file"].split("/")))
    def need_core64(cond, what):
        # core64's anchor ref in overlays_params.json carries an assumed load-order byte; core64c's plan has no anchor
        need(cond, what + " (core64's anchor; core64c's plan has no anchor and assumes no load-order index)"
             if "load-order byte" in what else what)
    cwo.check_plugins(out, prm, {ov["tag"]: terrain.raw}, need_core64, rep,
                      overlay_records.vanilla_mars_count(a.sf_data))
    mk = cwo.mask_report(out, ov["world"], ov["n"], tuple(ov["mask_outer_edges"]))
    need(mk["pixels_differ"] == 0, f"mask exact ({mk['outer_edges']})")
    old = overlay_records.walk_plugin(os.path.join(a.core, prm["plugin"]))
    new = overlay_records.walk_plugin(os.path.join(out, prm["plugin"]))
    by = {r["fid"]: r for r in new["records"]}
    # core64's own map marker (if its writer made one) is not kept: core64c writes its markers after every object,
    # and its Location's LCSR / LCID point at those (map_marker_problems); with --world-border the world's WRLD must
    # carry exactly the requested DATA / HNAM change (with_world_data)
    kept = [r for r in old["records"] if not is_map_marker_ref(r)]
    wd = prm.get("world_data")
    same = sum(1 for r in kept if r["fid"] in by and without_marker_chain(by[r["fid"]])
               == without_marker_chain(with_world_data(r, wd, ov["world"])))
    need(same == len(kept), f"every core64 record unchanged ({same}/{len(kept)}; "
                            f"{len(old['records']) - len(kept)} core64 map marker(s) replaced"
                            + (f"; {ov['world']} WRLD with world_data {wd}" if wd else "") + ")")
    old_max = max(r["fid"] & 0xFFFFFF for r in old["records"])
    old_fids = {o["fid"] for o in old["records"]}
    own_index = len(new["masters"])                       # this plugin's own records; an override of a master's record
    added = [r for r in new["records"] if r["fid"] not in old_fids and (r["fid"] >> 24) == own_index]   # (the NAVI, 000FF1:Starfield.esm) is not "new"
    need(added and min(r["fid"] & 0xFFFFFF for r in added) > old_max,
         f"every new record's FormID after core64's last (0x{old_max:06X})")
    need(new["masters"] == ["Starfield.esm"], f"masters {new['masters']}")
    del old

    # 2. object records: STAT / DOOR = bases, models, dependencies, REFRs as objects.json, cells
    own = len(new["masters"]) << 24
    recs = new["records"]
    animated = animated_door_bases(objects, ids)
    stats = [r for r in recs if r["sig"] in ("STAT", "MSTT", "DOOR") and r["fid"] & 0xFFFFFF not in animated]
    need(len(stats) == len(objects["bases"]), f"{len(stats):,} STAT/MSTT/DOOR = {len(objects['bases']):,} bases")
    if animated:
        # step C: the animated doors' DOORs (judged in promotion_checks) carry the rigged model of FO4Port's archive,
        # so they are neither bases of objects.json nor in this build's Data\meshes
        got = sorted(r["fid"] & 0xFFFFFF for r in recs if r["fid"] & 0xFFFFFF in animated and r["sig"] == "DOOR")
        need(got == sorted(animated), f"{len(got)} animated door DOOR records = {len(animated)} declared")
    if prm.get("navmesh"):
        # 2b. navmesh records (stage --navmesh, docs/actors/navmesh-conversion.md): NAVM count = navmesh.json's, one NAVI
        # override (000FF1:Starfield.esm), every NAVM after the last object record, formids.json names them
        navj = load(os.path.join(out, prm["navmesh"]))
        navms = [r for r in recs if r["sig"] == "NAVM"]
        navis = [r for r in recs if r["sig"] == "NAVI"]
        need(len(navms) == len(navj["navmeshes"]), f"{len(navms):,} NAVM = navmesh.json's {len(navj['navmeshes']):,}")
        need(len(navis) == 1, f"one NAVI override ({len(navis)})")
        light_ids = {int(v["ref"], 16) for v in (ids.get("lights") or {}).values()}    # appended after the NAVMs
        light_ids |= appended_ids(ids)                                                   # (the doors' markers and ACTIs too)
        light_ids |= map_marker_ids(ids)                                                 # (and the map markers)
        last_obj = max((r["fid"] & 0xFFFFFF for r in recs if r["sig"] in ("STAT", "MSTT", "DOOR", "REFR", "CONT", "MISC", "ACTI",
                                                                          "TERM", "TMLM")
                        and r["fid"] & 0xFFFFFF not in light_ids), default=0)
        need(navms and min(r["fid"] & 0xFFFFFF for r in navms) > last_obj, f"every NAVM FormID after the last object (0x{last_obj:06X})")
        nav_ids = load(os.path.join(out, "formids.json")).get("navmeshes", [])
        need(set(nav_ids) == {f"{r['fid'] & 0xFFFFFF:06X}" for r in navms}, f"formids.json names the {len(nav_ids):,} NAVM")
        tri = sum(len(n.get("triangles", [])) for n in navj["navmeshes"])
        rep["navmesh"] = {"navm": len(navms), "navi": len(navis), "triangles": tri, "first_fid": f"{min(r['fid'] & 0xFFFFFF for r in navms):06X}" if navms else None}
    from fo4sf import fo4land
    missing = [m for m in (fo4land.zstring(overlay_records.field(r, "MODL", b"")) for r in stats)
               if not os.path.isfile(os.path.join(out, "Data", "meshes", m))]
    need(not missing, f"every base model is in Data\\meshes ({len(missing)} missing: {missing[:5]})")
    problems, worst_pos, worst_rot = x2c.ref_record_check(recs, own, objects, ids)
    need(not problems, f"every REFR matches objects.json ({len(problems)} problems: {problems[:3]})")
    need(worst_pos < 1e-3 and worst_rot < 1e-5, f"REFR position / rotation as written (worst {worst_pos:.2e} m, {worst_rot:.2e} rad)")
    for what, good in promotion_checks(recs, own, objects, ids, exp):
        need(good, what)
    stations = (objects.get("workshops") or []) + (objects.get("benches") or [])
    if stations:
        # the station records against Starfield.esm itself (docs/terrain/stations.md): the workshop keywords and PRPS
        # as the vanilla pre-placed workshop's, every bench kind's vanilla FURN with its bench type and recipe keyword
        sf_esm = os.path.join(a.sf_data, "Starfield.esm") if a.sf_data else ""
        if not os.path.isfile(sf_esm):
            need(False, f"stations ({len(stations):,}): Starfield.esm needed for the vanilla record check (check --sf-data)")
        else:
            sp = station_master_check(sf_esm, recs, own, objects, ids, new["masters"])
            need(not sp, f"stations: workshop ACTI keywords = WorkshopKeyword + OutpostPlayerHouseActivator's OutpostCategory "
                         f"set and PRPS OutpostBuildAreaRadius, bench vanilla FURNs with their bench type and recipe keyword, "
                         f"read from Starfield.esm ({len(sp)} problems: {sp[:3]})")
    if lights:
        ligh = [r for r in recs if r["sig"] == "LIGH"]
        need(len(ligh) == len(objects["light_bases"]), f"{len(ligh)} LIGH = {len(objects['light_bases'])} light bases "
                                                        f"(one per FO4 base, {len(lights):,} lights)")
        first_light, last_other = lights_after(recs, len(new["masters"]), ids)
        need(first_light is not None and first_light > last_other,
             f"every light record after the build's other records (first 0x{first_light or 0:06X}, last other 0x{last_other:06X})")
        lp = light_record_problems(recs, own, objects, ids)
        need(not lp, f"every LIGH and light REFR matches objects.json ({len(lp)} problems: {lp[:3]})")
    if doors:
        # scripted load doors (docs/terrain/scripted-doors.md): the arrival markers and the door ACTIs after everything
        # (the lights included); the door REFRs' VMADs and the markers are judged in promotion_checks (door_record_problems)
        first_door, last_other = doors_after(recs, len(new["masters"]), ids)
        need(first_door is not None and first_door > last_other,
             f"every door arrival marker and door ACTI after the build's other records (first 0x{first_door or 0:06X}, "
             f"last other 0x{last_other:06X})")
        rep["doors"] = [{"src": e["src"], "edid": e["edid"], "destination": e["destination"], "arrival": e["arrival"],
                         "ids": (ids.get("doors") or {}).get(e["src"]), "raw": {}} for e in doors]
        for d in rep["doors"]:                        # the raw records, for the report (hex of every field)
            for what, local in (("acti", d["ids"]["base"]), ("refr", d["ids"]["ref"]), ("marker", d["ids"]["arrival"])):
                r = by.get(own | int(local, 16))
                d["raw"][what] = None if r is None else {"sig": r["sig"], "flags": f"{r['flags']:08X}",
                                                         "fields": [[s.decode(), bytes(v).hex()] for s, v in r["fields"]]}
    if map_marker_ids(ids):
        # map markers (docs/terrain/map-markers.md): Red Rocket, Sanctuary, Vault 111, Concord (stage), persistent
        mp = map_marker_problems(recs, own_index, ov, ids)
        need(not mp, f"{len(map_marker_ids(ids))} map markers: MapMarker REFRs at the params' positions, LCSR "
                     f"MapMarkerRefType + LCID on {ov['location']}, after every other record ({len(mp)} problems: {mp[:3]})")
        rep["map_markers"] = {"params": ov.get("map_markers"), "ids": (ids.get("map_marker_refs") or {}).get(ov["world"])}
    rep["plugin_records"] = {s: sum(1 for r in recs if r["sig"] == s) for s in sorted({r["sig"] for r in recs})}
    rep["plugin_bytes"] = new["bytes"]
    del new, recs, by, stats
    cells = x2c.walk_cells(os.path.join(out, prm["plugin"]))
    per_cell = {}
    for r in objects["refs"] + promoted + lights:
        per_cell[tuple(r["cell"])] = per_cell.get(tuple(r["cell"]), 0) + 1
    want = dict(per_cell)
    want[tuple(ov["spawn_cell"])] = want.get(tuple(ov["spawn_cell"]), 0) + 1        # + the COC marker
    got = {c["grid"]: len(c["refs"]) for c in cells.values() if c["grid"] is not None and c["refs"]}
    need(got == want, f"REFRs per exterior cell as objects.json ({len(got):,} cells with references)")
    wrong = [r["src"] for r in objects["refs"] + promoted + lights
             if list(r["cell"]) != list(tg.sf_cell_of(r["pos"][0], r["pos"][1]))]
    need(not wrong, f"every reference in the cell of its written position ({len(wrong)} not: {wrong[:5]})")
    if doors:
        # the exterior arrival markers are persistent references of the world's persistent cell (with the anchor):
        # the interior door's GetFormFromFile resolves them from inside (a temporary one did not, door_trip_sdm_1018)
        anchor = own | ov["anchor"]["form_id"]
        mfids = [own | int(v["arrival"], 16) for v in (ids.get("doors") or {}).values()]
        mapfids = [own | f for f in map_marker_ids(ids)]                    # the map markers share that cell
        where = door_marker_groups(os.path.join(out, prm["plugin"]), set(mfids) | set(mapfids) | {anchor})
        wp = door_marker_placement(where, mfids + mapfids, anchor)
        persistent = [c for c in cells.values() if c["grid"] is None]
        outside = [e["src"] for e in doors if not (ov["cell_min"] <= e["arrival"]["cell"][0] <= ov["cell_max"]
                                                   and ov["cell_min"] <= e["arrival"]["cell"][1] <= ov["cell_max"]
                                                   and list(e["arrival"]["cell"]) == list(tg.sf_cell_of(*e["arrival"]["pos"][:2])))]
        need(not wp and not outside and len(persistent) == 1 and sorted(persistent[0]["refs"]) == sorted([anchor] + mfids + mapfids),
             f"{len(mfids)} door arrival markers in the persistent children of {ov['world']}'s persistent cell, the anchor's "
             f"({len(persistent[0]['refs']) if len(persistent) == 1 else '?'} REFRs there = anchor + markers + "
             f"{len(mapfids)} map markers), each over "
             f"the overlay's cells ({len(wp)} problems: {wp[:3]}; outside {outside[:3]})")
    rep["cells"] = {"with_refs": len(got), "max_refs": max(got.values()), "densest": sorted(
        ([list(k), v] for k, v in got.items()), key=lambda kv: -kv[1])[:5]}
    deps = x2c.dependency_check(os.path.join(out, "Data"), [b["model"] for b in objects["bases"]], prefix=ASSET_PREFIX,
                                vanilla=x2c.vanilla_textures(a.sf_data))
    need(not deps["missing"], f"every geometry / material / texture the models name exists ({deps['missing_count']} "
                              f"missing: {deps['missing'][:5]}; {deps['counts']})")
    rep["dependencies"] = deps

    # 3. object z - terrain z under every placed origin: the BTD, and with --fo4 FO4's own LAND
    pos = np.array([r["pos"] for r in objects["refs"]], np.float64)
    g = terrain.bilinear(pos[:, 0], pos[:, 1])
    dz = pos[:, 2] - g
    rep["object_minus_btd"] = {"objects": int(len(dz)), "abs": abs_stats(dz), "signed_m": signed_stats(dz), "histogram_m": {
        f"{lo}..{hi}": int(((dz >= lo) & (dz < hi)).sum()) for lo, hi in
        ((-500, -1), (-1, -0.25), (-0.25, -0.05), (-0.05, 0.05), (0.05, 0.25), (0.25, 1), (1, 500))}}
    by_src = {r["src"]: i for i, r in enumerate(objects["refs"])}
    k = by_src.get(STATION)
    if k is not None:
        gb = terrain.bilinear([pos[k, 0]], [pos[k, 1]])[0]
        need(abs(pos[k, 2] - gb) <= terrain.step, f"Red Rocket station z - BTD = {(pos[k, 2] - gb) * 1000:.2f} mm "
                                                     f"(within one step {terrain.step * 1000:.2f} mm)")
    if a.fo4:
        xs, ys = pos[:, 0] * 70.0 / 4096.0, pos[:, 1] * 70.0 / 4096.0
        box = (int(math.floor(xs.min())) - 1, int(math.floor(xs.max())) + 1, int(math.floor(ys.min())) - 1,
               int(math.floor(ys.max())) + 1)
        g4 = np.array([np.nan if v is None else v for v in x2c.fo4_ground(a.fo4, objects["refs"], box)], np.float64)
        ok = np.isfinite(g4)
        diff = g[ok] - g4[ok]
        rep["btd_minus_fo4_land_under_objects"] = abs_stats(diff)
        worst = np.argsort(-np.abs(diff))[:5]
        idx = np.nonzero(ok)[0]
        rep["btd_minus_fo4_land_under_objects"]["worst"] = [
            {"src": objects["refs"][idx[j]]["src"], "pos": objects["refs"][idx[j]]["pos"],
             "edid": objects["bases"][objects["refs"][idx[j]]["base"]]["edid"], "btd_minus_fo4_mm": round(float(diff[j]) * 1000, 1)}
            for j in worst]
        rep["btd_minus_fo4_land_under_objects"]["no_fo4_land"] = int((~ok).sum())
        dz4 = pos[ok, 2] - g4[ok]
        rep["object_minus_fo4_land"] = {"abs": abs_stats(dz4), "signed_m": signed_stats(dz4)}
        if k is not None:
            need(abs(pos[k, 2] - g4[k]) < 1e-3, f"Red Rocket station z - FO4 LAND = {(pos[k, 2] - g4[k]) * 1000:.2f} mm (FO4: 0)")
        s = rep["btd_minus_fo4_land_under_objects"]
        print(f"BTD - FO4 LAND under {s['count']:,} origins: median {s['median_mm']} mm, p99 {s['p99_mm']} mm, "
              f"max {s['max_mm']} mm")

    # 4. every plan point re-derived from the converted collision (local world) and the predicted verdicts
    bases, placed = objects["bases"], [dict(r) for r in objects["refs"]]
    sx, sy = ov["spawn"][:2]
    world = CoreWorld(os.path.join(out, "Data"), bases, placed, terrain, (sx - AREA_M, sy - AREA_M, sx + AREA_M, sy + AREA_M))
    need(not world.collision_errors, f"local world: converted collision decodes ({len(world.collision_errors)} errors)")
    metas = {(q["entry"], q["label"]): q for q in exp["points"]}
    kinds = {kk: q["kind"] for kk, q in metas.items()}
    core_plan = load(os.path.join(a.core, "plan.json"))
    pr = validate_plan(plan, core_plan[0], kinds)
    need(not pr, f"plan entries: runner keys, core64's keys carried, z_ref on its terrain reference ({pr[:3]})")
    land0 = world.landing(*ov["spawn"])
    need(all(abs(land0["centre"] - e["spawn_local"][2]) < 1e-3 and e["spawn_local"][:2] == ov["spawn"][:2] for e in plan),
         f"spawn_local = where the player lands under the COC marker ({land0['centre']:.4f})")
    need(exterior.clearance(world.index, ov["spawn"][0], ov["spawn"][1], land0["centre"]) >= x2c.PLAYER_HEIGHT,
         "room for the player above the arrival")
    pts = []
    for e, entry in enumerate(plan):
        need(entry["coc"] == ov["coc"], f"entry {e + 1}: coc {entry['coc']}")
        p0 = entry["points"][0]
        d0 = math.hypot(p0["x"] - sx, p0["y"] - sy)
        need(entry.get("hop_m") == HOP_M and entry.get("hop_wait_ms") == HOP_WAIT_MS and d0 <= FIRST_POINT_MAX_M,
             f"entry {e + 1}: first point {p0['label']} {d0:.1f} m from the arrival (the runner never hops there), "
             f"hop_m {entry.get('hop_m')}, hop_wait_ms {entry.get('hop_wait_ms')}")
        travel = entry_travel((sx, sy), entry)
        need(travel["max_axis_cells"] <= MAX_AXIS_CELLS,
             f"entry {e + 1}: each of the runner's {travel['teleports']} teleports ({travel['hops']} hops) moves the "
             f"player at most {MAX_AXIS_CELLS} cells along each axis whatever the merge offset (longest single-axis move "
             f"{travel['max_axis_move_m']} m; at most {travel['max_axis_cells_core64']} cells in core64's frame)")
        need(travel["margin_s"] >= MIN_MARGIN_S,
             f"entry {e + 1}: about {travel['estimated_s']} s to the last point of the {travel['timeout_s']} s step "
             f"timeout ({travel['margin_s']} s to spare, at least {MIN_MARGIN_S:.0f})")
        rep.setdefault("travel", []).append({k: v for k, v in travel.items() if k != "moves"})
        low = min(p["expect"] for p in entry["points"])
        need(entry["settle_ms"] >= 1000.0 * cwo.fall_seconds(entry["drop_z"], low),
             f"entry {e + 1}: settle {entry['settle_ms']} ms covers the fall")
        here = ov["spawn"][:2]
        for p in entry["points"]:
            meta = metas[(e, p["label"])]
            d = math.hypot(p["x"] - sx, p["y"] - sy)
            need(d <= NEAR_M, f"{p['label']}: {d:.0f} m from the arrival (<= {NEAR_M:.0f})")
            land = world.landing(p["x"], p["y"], entry["drop_z"])
            if meta["kind"] in ("terrain", "terrain_ref", "terrain_near_object", "view"):
                hs = world.ground_all(p["x"], p["y"])
                err = max(abs(v - p["expect"]) for v in hs.values())
                need(not land["on_object"] and err <= world.step, f"{p['label']}: terrain, decoded within one step")
                if meta["kind"] != "terrain_near_object":
                    near = exterior.nearby_object(world.index.top, world.ground, p["x"], p["y"], entry["drop_z"],
                                                  radii=x2c.TERRAIN_CLEAR_RADII)
                    need(near is None, f"{p['label']}: no object within {x2c.TERRAIN_CLEAR_RADII[-1]} m")
                if meta["kind"] == "terrain_ref":
                    need(x2c.reference_ok(world, p["x"], p["y"]) is not None, f"{p['label']} (entry {e + 1}): level open terrain")
            else:
                owner = world.by_src[meta["owner"]["src"]]
                err = abs(land["centre"] - p["expect"])
                need(land["on_object"] and land["owner"] == owner and err < 1e-3,
                     f"{p['label']}: lands on {meta['owner']['edid']} at {p['expect']} (error {err * 1000:.2f} mm)")
                if e == 1:
                    dd = x2c.discrimination(world, p["x"], p["y"], p["expect"])
                    need(dd >= x2c.MIN_DISCRIMINATION, f"{p['label']}: {dd:.2f} m above the terrain under its disc")
            tops = [s[0][0] for dx, dy in exterior.disc_offsets(1.0) if (s := world.index.surfaces(p["x"] + dx, p["y"] + dy))]
            need(entry["drop_z"] >= max(tops + [p["expect"]]) + TOP_CLEAR - 1e-6,
                 f"{p['label']}: drop_z {entry['drop_z']} >= every collision top within 1 m + {TOP_CLEAR:g}")
            pts.append({"entry": e, "label": p["label"], "kind": meta["kind"], "expect": p["expect"],
                        "landing": x2c.landing_json(world, land), "error_mm": round(err * 1000, 3),
                        "from_previous_m": round(math.hypot(p["x"] - here[0], p["y"] - here[1]), 1)})
            here = (p["x"], p["y"])
        meta = {p["label"]: metas[(e, p["label"])] for p in entry["points"]}
        pred = {sc: x2c.judge_heights(entry["points"], scenario_reads(world, entry, meta, sc), entry["z_ref"])[:2]
                for sc in SCENARIOS[e]}
        need(x2c.judge_heights(entry["points"], [p["expect"] for p in entry["points"]], entry["z_ref"])[0] == "PASS",
             f"entry {e + 1} passes on its own expectations")
        if e == 0:
            need(pred["flat_terrain"][0] == "FAIL" and pred["no_objects"][0] == "PASS",
                 f"entry 1 fails on flat terrain ({pred['flat_terrain'][1]:.2f} m) and does not depend on the objects")
        if e == 1:
            need(pred["no_objects"][0] == "FAIL" and pred["no_objects"][1] >= x2c.MIN_DISCRIMINATION,
                 f"entry 2 fails without the objects (worst {pred['no_objects'][1]:.2f} m)")
    rep["points"] = pts
    if a.fo4_data:
        rep["fo4_collision_tops"] = x2c.fo4_collision_tops(a.fo4_data, plan, metas)
        for t in rep["fo4_collision_tops"]:
            t["decoder"] = "routes.collision_bodies"
            if t["fo4_top"] is None:                    # compound bodies: Codex's fo4_compounds decoder instead
                drop = plan[t["entry"]]["drop_z"]
                pt = next(p for p in plan[t["entry"]]["points"] if p["label"] == t["label"])
                top, layer, crep = compound_top(a.fo4_data, metas[(t["entry"], t["label"])]["owner"], pt["x"], pt["y"], drop)
                t.update(fo4_top=None if top is None else round(top, 5), layer=layer, decoder="fo4_compounds.decode_body",
                         compound=crep, diff_mm=None if top is None else round((top - t["expect"]) * 1000, 3))
        for t in rep["fo4_collision_tops"]:
            if t["entry"] == 1:
                need(t["diff_mm"] is not None and abs(t["diff_mm"]) < 1.0 and t["layer"] == 1,
                     f"{t['label']}: FO4's own collision top {t['fo4_top']} (layer {t['layer']}) = expect ({t['diff_mm']} mm)")

    # 5. the archive the installer builds: one General archive, every entry stored, below 4 GiB
    files = data_files(out)
    est = ba2_size(files)
    rep["archive"] = {"files": len(files), "data_bytes": sum(b for _, b in files), "estimate_bytes": est,
                      "by_folder": {f: sum(b for n, b in files if n.split("/")[0].lower() == f)
                                    for f in sorted({n.split("/")[0].lower() for n, _ in files})}}
    need(est < ARCHIVE_LIMIT, f"one stored archive about {est / 2 ** 30:.3f} GiB < 4 GiB")
    need(all(n.isascii() for n, _ in files), "archive paths are plain ASCII")
    # FO4's own file names keep their spaces (e.g. "loose planks 01.nif"); exp2c packed 33 such paths the same way
    # and its objects loaded in game, so they are counted, not refused
    rep["archive"]["paths_with_spaces"] = sum(1 for n, _ in files if " " in n)
    if a.archive2 and a.scratch:
        dry, probs = archive_dry_run(a.archive2, out, a.scratch, files)
        rep["archive"]["dry_run"] = dry
        need(not probs and dry.get("bytes", ARCHIVE_LIMIT) < ARCHIVE_LIMIT,
             f"Archive2 dry run: {dry.get('bytes', 0) / 2 ** 30:.3f} GiB, {dry.get('entries')} entries, "
             f"{dry.get('packed_entries')} packed ({probs})")
    rep["checks"] = checks
    rep["pass"] = all(c[1] for c in checks)
    man = data_manifest(out, [prm["plugin"], prm["mars"]["plugin"]])
    save(os.path.join(out, MANIFEST), {"checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "pass": rep["pass"], "files": man})
    rep["data_manifest"] = {"file": MANIFEST, "files": len(man)}
    rep["seconds"] = round(time.time() - t0, 1)
    save(os.path.join(out, "offline_check.json"), rep, indent=1)
    for what, good in checks:
        if not good or len(checks) < 400:
            print(("  ok   " if good else "  FAIL ") + what)
    print(f"{sum(1 for c in checks if c[1])} of {len(checks)} checks ok; {rep['seconds']} s")
    print("CHECK", "PASS" if rep["pass"] else "FAIL")
    return 0 if rep["pass"] else 1


MANIFEST = "data_manifest.json"


def data_manifest(out, plugins=()):
    """{path under out: [size, mtime_ns]} of every file of out\\Data and the given plugins. Data is hard-linked to the
    conversion work folder: an in-place rewrite there changes the staged file's size or time (a replaced file, a new
    link, leaves it alone)."""
    files = {}
    for root, _dirs, names in os.walk(os.path.join(out, "Data")):
        for n in names:
            path = os.path.join(root, n)
            st = os.stat(path)
            files[os.path.relpath(path, out).replace(os.sep, "/")] = [st.st_size, st.st_mtime_ns]
    for pl in plugins:
        st = os.stat(os.path.join(out, pl))
        files[pl] = [st.st_size, st.st_mtime_ns]
    return files


def manifest_diff(old, new):
    return {"missing": sorted(set(old) - set(new)), "added": sorted(set(new) - set(old)),
            "changed": sorted(k for k in set(old) & set(new) if list(old[k]) != list(new[k]))}


def cmd_verify_data(a):
    """Is the staged tree still the one `check` passed? Exit 0 only if it passed and nothing changed since."""
    path = os.path.join(a.out, MANIFEST)
    if not os.path.isfile(path):
        print(f"no {MANIFEST}: run make_core64c.py check first")
        return 1
    m = load(path)
    prm, _ov = core_params(a.out)
    diff = manifest_diff(m["files"], data_manifest(a.out, [prm["plugin"], prm["mars"]["plugin"]]))
    for k, v in diff.items():
        if v:
            print(f"{len(v)} {k}: {v[:5]}")
    good = m.get("pass") and not any(diff.values())
    print(f"{len(m['files']):,} files as checked on {m.get('checked')} (check {'PASS' if m.get('pass') else 'FAIL'}): "
          + ("unchanged" if good else "NOT the checked tree"))
    return 0 if good else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--work", required=True)
    s.add_argument("--core", required=True, help="the staged core64 terrain (overlays_params.json, plugins, Data)")
    s = sub.add_parser("measure")
    s.add_argument("--work", required=True)
    s.add_argument("--fo4-data", required=True)
    s.add_argument("--caps", default="256,512,1024,2048")
    s.add_argument("--kind-caps", default="color=1024,normal=512,rough=256,opacity=512",
                   help="per-kind cap sets to price, separated by ';' (convert_batch --max-texture syntax)")
    s.add_argument("--calibrate", default="", help="a finished convert_batch staging (e.g. exp2c's) for the mesh size")
    for name in ("stage", "check"):
        s = sub.add_parser(name)
        s.add_argument("--work", required=True)
        s.add_argument("--core", required=True)
        s.add_argument("--out", required=True)
        if name == "stage":
            s.add_argument("--sf-esm", default="", help="Starfield.esm: build the plugins with dotnet/TerrainOverlays")
            s.add_argument("--cluster", default="", help="R05: a cluster json (scripts/terrain/clusters/*.json, "
                           "make_cluster.py) whose \"containers\" become native CONT, \"items\" native MISC, "
                           "\"activators\" native ACTI, \"terminals\" native TERM (+ TMLM menu), \"workshops\" native "
                           "ACTI build stations and \"benches\" references to the vanilla Starfield bench of their "
                           "kind, instead of statics (each in its original reference slot), and whose "
                           "\"lights\" become native LIGH and new light REFRs after every other record")

            s.add_argument("--animated-doors", default="", metavar="MANIFEST",
                           help="off by default (step C, docs/spikes/load-door-animations.md): with --cluster, scripted "
                                "load doors whose FO4 model has load_door.anim in this manifest (a port staged with "
                                "interior_batch.py --animated-doors: door_anim/manifest_*.json) become animated DOOR "
                                "records with FO4SF_AnimatedLoadDoor instead of ACTI with FO4SF_LoadDoor")
            s.add_argument("--navmesh", default="", help="navmesh.json (src/fo4sf/navmesh.py export over the core's FO4 NAVM): "
                           "written as NAVM records in their cells plus the NAVI override (docs/actors/navmesh-conversion.md)")
            s.add_argument("--world-border", choices=sorted(WORLD_DATA), default="template",
                           help="the world's border fields: template = LC172World's (SmallWorld, HNAM 0), city = "
                                "NewAtlantis's (no SmallWorld, HNAM 5; docs/terrain/border.md)")
            s.add_argument("--fo4-map-markers", default="", help="a Fo4Land export-mapmarkers json (Commonwealth): "
                           "every named marker inside the overlay becomes a map marker after the fixed four "
                           "(docs/terrain/map-markers.md)")
            s.add_argument("--views", action="store_true",
                           help="add screenshot spots to entry 3 (useful once the runner sets the time of day, PR #73)")
        else:
            s.add_argument("--sf-data", default="", help="Starfield Data (vanilla Mars entries, texture archives)")
            s.add_argument("--fo4", default="", help="Fallout4.esm: FO4's own terrain under every object")
            s.add_argument("--fo4-data", default="", help="FO4 Data: object tops against FO4's own collision")
            s.add_argument("--archive2", default="", help="Archive2.exe: build the archive into --scratch and measure it")
            s.add_argument("--scratch", default="", help="folder for the Archive2 dry run (deleted afterwards)")
    s = sub.add_parser("verify-data", help="is the staged tree still the one check passed (sizes and times)?")
    s.add_argument("--out", required=True)
    s = sub.add_parser("compare-ids", help="formids.json of --out against another build's, section by section (facts)")
    s.add_argument("--out", required=True)
    s.add_argument("--against", required=True, help="the input build (e.g. the one the cluster was generated from)")
    a = ap.parse_args()
    return {"select": cmd_select, "measure": cmd_measure, "stage": cmd_stage, "check": cmd_check,
            "verify-data": cmd_verify_data, "compare-ids": cmd_compare_ids}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
