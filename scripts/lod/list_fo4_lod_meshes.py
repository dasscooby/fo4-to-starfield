"""Read-only table of FO4 STAT distant-LOD meshes around Sanctuary, Red Rocket and Concord.

Walks Fallout4.esm (Commonwealth) and Fallout4 - *.ba2 name tables. Does not write game Data
or staging, does not call convert_static, and does not generate CK LOD.

usage: python -I scripts/lod/list_fo4_lod_meshes.py --plugin <Fallout4.esm> --fo4-data <Data dir> [--radius N]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import struct
import sys

# python -I ignores PYTHONPATH; add this checkout's src like the other scripts.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))

USAGE = (
    "usage: python -I scripts/lod/list_fo4_lod_meshes.py "
    "--plugin <Fallout4.esm> --fo4-data <Data dir> [--radius N]"
)

FO4_CELL = 4096.0
MNAM_SLOT = 260
MNAM_LEVELS = 4
CONVERT_PREFIX = "fo4core"
OVERLAY_WORLD = "FO4Core_Commonwealth"
OVERLAY_MIN_CELL = -32
OVERLAY_SIZE = 64
PER_BLOCK_QUADS = (1, 2, 4, 8)
PLACEHOLDER_MATERIAL = "Materials\\Common\\Metal\\MetalIronCast01.mat"
WORLD_EDID = "Commonwealth"

# Positions from scripts/terrain/make_cw_overlays.py LANDMARKS / RAY_LANDMARKS
# (same FormIDs as docs/terrain/map-markers.md Commonwealth markers). FO4 units.
LANDMARKS = (
    {"tag": "redrocket", "ref": 0x000211C0, "x": -69232.0, "y": 80304.0},
    {"tag": "sanctuary", "ref": 0x00072A48, "x": -80768.19, "y": 88174.80},
    {"tag": "concord", "ref": 0x00082138, "x": -60286.01, "y": 72977.79},
)


def slash(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def cell_xy(x: float, y: float) -> tuple[int, int]:
    return int(math.floor(x / FO4_CELL)), int(math.floor(y / FO4_CELL))


def parse_stat_mnam(data: bytes) -> list[str]:
    """FO4 STAT MNAM is four 260-byte null-padded slots (1040 bytes) or empty."""
    out = []
    for i in range(MNAM_LEVELS):
        chunk = data[i * MNAM_SLOT:(i + 1) * MNAM_SLOT]
        if not chunk:
            out.append("")
            continue
        out.append(chunk.split(b"\0", 1)[0].decode("cp1252", "replace"))
    return out


def fo4_lod_archive_path(mnam_path: str) -> str:
    """STAT MNAM names LOD\\...; archives store Meshes\\LOD\\..."""
    rel = slash(mnam_path)
    if not rel.lower().startswith("meshes/"):
        rel = "meshes/" + rel
    return rel


def converted_full_mesh_path(fo4_modl: str, prefix: str = CONVERT_PREFIX) -> str:
    """Path convert_static / pipeline writes for the STAT full mesh (convert_batch --prefix fo4core)."""
    rel = slash(fo4_modl)
    rel = re.sub(r"^meshes/", "", rel, flags=re.I)
    stem, _ext = os.path.splitext(rel)
    return f"meshes/{prefix}/{stem.lower()}.nif"


def per_object_generated_lod_path(converted_full_mesh: str, level: int) -> str:
    """Starfield per-object form: meshes/lod/generated/<converted full mesh path>_lod_<0-3>.nif."""
    if not 0 <= level <= 3:
        raise ValueError(f"LOD level must be 0..3, got {level}")
    stem = slash(converted_full_mesh)
    if stem.lower().endswith(".nif"):
        stem = stem[:-4]
    return f"meshes/lod/generated/{stem}_lod_{level}.nif"


def convert_static_out_name(converted_full_mesh: str, level: int) -> str:
    """out_name such that convert_static writes the per-object generated nif path."""
    generated = per_object_generated_lod_path(converted_full_mesh, level)
    rel = slash(generated)
    rel = re.sub(r"^meshes/", "", rel, flags=re.I)
    if rel.lower().endswith(".nif"):
        rel = rel[:-4]
    return rel


def per_block_object_lod_paths(world_edid: str = OVERLAY_WORLD) -> list[str]:
    """CK -MockWorldSpaceLOD per-block form: Meshes\\Terrain\\<world>\\Objects\\<world>.{1,2,4,8}.0.0.nif."""
    if not world_edid or "/" in world_edid or "\\" in world_edid:
        raise ValueError("world editor id required")
    return [
        f"meshes/terrain/{world_edid}/objects/{world_edid}.{quad}.0.0.nif"
        for quad in PER_BLOCK_QUADS
    ]


def overlay_lodsettings_bytes(
    min_x: int = OVERLAY_MIN_CELL, min_y: int = OVERLAY_MIN_CELL, size: int = OVERLAY_SIZE
) -> bytes:
    """20-byte lodsettings form: min cell x, min cell y, size in cells, eight zero bytes."""
    if size < 1:
        raise ValueError("size in cells must be >= 1")
    return struct.pack("<iii", min_x, min_y, size) + b"\x00" * 8


def overlay_lodsettings_rel(world_edid: str = OVERLAY_WORLD) -> str:
    if not world_edid or world_edid != world_edid.strip() or "/" in world_edid or "\\" in world_edid:
        raise ValueError("world editor id required")
    return f"lodsettings/{world_edid.lower()}.lod"


def landmark_cell_map(radius: int) -> dict[tuple[int, int], list[str]]:
    if radius < 0:
        raise ValueError("radius must be >= 0")
    out: dict[tuple[int, int], list[str]] = {}
    for mark in LANDMARKS:
        cx, cy = cell_xy(mark["x"], mark["y"])
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                out.setdefault((cx + dx, cy + dy), []).append(mark["tag"])
    return out


def form_hex(fid: int) -> str:
    return f"{fid:08x}"


def starfield_targets(fo4_modl: str, prefix: str = CONVERT_PREFIX) -> dict:
    full = converted_full_mesh_path(fo4_modl, prefix)
    per_object = [per_object_generated_lod_path(full, level) for level in range(MNAM_LEVELS)]
    return {
        "converted_full_mesh": full,
        "per_object_lod": per_object,
        "convert_static_out_name": [convert_static_out_name(full, level) for level in range(MNAM_LEVELS)],
        "geometry": "geometries/<sha1[:20]>/<sha1[20:40]>.mesh (content-addressed; convert_static.mesh_file_path)",
        "material": PLACEHOLDER_MATERIAL,
        "convert_static_as_stands": (
            "convert_static(fo4_lod_nif, out_name=convert_static_out_name[level]) writes the "
            "per-object nif path plus hashed .mesh and references PLACEHOLDER_MATERIAL; it "
            "does not write a .mat. Generated .mat output is the pipeline path. It does not "
            "pick that out_name itself (pipeline keys from the source nif under --prefix). No "
            "collision unless a template is passed. It cannot write the per-block Terrain\\"
            "<world>\\Objects form."
        ),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--plugin", required=True)
    p.add_argument("--fo4-data", required=True)
    p.add_argument("--radius", type=int, default=1)
    p.add_argument("--world", default=WORLD_EDID)
    p.add_argument("--prefix", default=CONVERT_PREFIX)
    return p.parse_args(argv)


def _stat_lod_index(plugin) -> dict[int, dict]:
    from fo4sf import fo4land

    start_end = plugin.top_group(b"STAT")
    if start_end is None:
        raise SystemExit("no STAT group")
    start, end = start_end
    out = {}
    for item in fo4land.iter_items(plugin.buf, start, end):
        if item[0] == "GRUP":
            continue
        typ, off, _flags, fid = item
        if typ != b"STAT":
            continue
        edid, modl, mnam = "", "", None
        for sig, d in fo4land.iter_subrecords(fo4land.record_data(plugin.buf, off)):
            if sig == b"EDID":
                edid = fo4land.zstring(d)
            elif sig == b"MODL":
                modl = fo4land.zstring(d)
            elif sig == b"MNAM":
                mnam = parse_stat_mnam(d)
        if mnam and any(mnam):
            out[fid] = {"edid": edid, "modl": modl, "mnam": mnam}
    return out


def _mesh_index(data_dir: str):
    from fo4sf import ba2

    archives = []
    try:
        names = os.listdir(data_dir)
    except OSError as exc:
        raise SystemExit(f"cannot read --fo4-data: {exc}") from exc
    for fn in sorted(names):
        low = fn.lower()
        if low.endswith(".ba2") and low.startswith("fallout4 - ") and "mesh" in low:
            archives.append(os.path.join(data_dir, fn))
    index = {}
    loaded = []
    for path in archives:
        a = ba2.Ba2(path)
        loaded.append({"path": os.path.basename(path), "entries": len(a.names)})
        for name in a.names:
            index[a._norm(name)] = name
    return index, loaded


def _archive_hit(index: dict, mnam_path: str):
    from fo4sf import ba2

    stored = index.get(ba2.Ba2._norm(fo4_lod_archive_path(mnam_path).replace("/", "\\")))
    return stored


def scan(plugin_path: str, data_dir: str, radius: int = 1, world: str = WORLD_EDID, prefix: str = CONVERT_PREFIX) -> dict:
    from fo4sf import fo4land

    if radius < 0:
        raise SystemExit("radius must be >= 0")
    cells = landmark_cell_map(radius)
    mesh_index, archives = _mesh_index(data_dir)
    with fo4land.Plugin(plugin_path) as plugin:
        stats = _stat_lod_index(plugin)
        world_data = plugin.read_world(world, cells=set(cells), refs=True)
        rows = []
        for xy in sorted(cells):
            cell = world_data["cells"].get(xy)
            if cell is None:
                continue
            for ref in cell["refs"] + cell["persistent_refs"]:
                base = ref.get("base")
                st = stats.get(base)
                if not st:
                    continue
                lod_paths = []
                for level, path in enumerate(st["mnam"]):
                    if not path:
                        lod_paths.append({"level": level, "path": "", "archive_path": "", "present": False})
                        continue
                    archive_path = fo4_lod_archive_path(path)
                    stored = _archive_hit(mesh_index, path)
                    lod_paths.append({
                        "level": level,
                        "path": path.replace("/", "\\"),
                        "archive_path": (stored or archive_path.replace("/", "\\")),
                        "present": stored is not None,
                    })
                rows.append({
                    "cell": [xy[0], xy[1]],
                    "cell_edid": cell.get("edid") or "",
                    "landmarks": cells[xy],
                    "ref": form_hex(ref["fid"]),
                    "base": form_hex(base),
                    "base_edid": st["edid"],
                    "fo4_modl": st["modl"].replace("/", "\\"),
                    "fo4_lod_paths": lod_paths,
                    "starfield": starfield_targets(st["modl"], prefix),
                })
    lod_bytes = overlay_lodsettings_bytes()
    return {
        "world": world,
        "overlay_world": OVERLAY_WORLD,
        "radius_cells": radius,
        "landmarks": [
            {
                "tag": m["tag"],
                "ref": form_hex(m["ref"]),
                "fo4_xy": [m["x"], m["y"]],
                "cell": list(cell_xy(m["x"], m["y"])),
            }
            for m in LANDMARKS
        ],
        "wanted_cells": len(cells),
        "loaded_cells": len(world_data["cells"]),
        "archives": archives,
        "lodsettings": {
            "path": overlay_lodsettings_rel(),
            "min_cell_x": OVERLAY_MIN_CELL,
            "min_cell_y": OVERLAY_MIN_CELL,
            "size_cells": OVERLAY_SIZE,
            "bytes_hex": lod_bytes.hex(),
        },
        "per_block_targets": per_block_object_lod_paths(),
        "rows": rows,
        "row_count": len(rows),
        "unique_bases": len({row["base"] for row in rows}),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "-h" in argv or "--help" in argv:
        print(USAGE)
        print("Print JSON: cell, ref, base EDID, FO4 LOD paths, present/missing, Starfield target paths.")
        print("Read-only. Requires --plugin and --fo4-data for a scan; mapping helpers need no game files.")
        return 0
    args = _parse_args(argv)
    if args.radius < 0:
        print("radius must be >= 0", file=sys.stderr)
        return 2
    if not os.path.isfile(args.plugin):
        print(f"plugin not found: {args.plugin}", file=sys.stderr)
        return 2
    if not os.path.isdir(args.fo4_data):
        print(f"fo4-data is not a directory: {args.fo4_data}", file=sys.stderr)
        return 2
    report = scan(args.plugin, args.fo4_data, radius=args.radius, world=args.world, prefix=args.prefix)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
