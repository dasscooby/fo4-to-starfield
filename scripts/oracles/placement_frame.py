"""Offline placement-frame oracle for plugins that add refs to a core worldspace.

Reports every REFR/ACHR placed into the shared worldspace: position, exterior cell
computed from that position (Starfield 100 m grid), whether the core has coverage
in that cell, and optional distance to a named anchor. Flags any ref that lands
outside core coverage or whose computed cell disagrees with its parent CELL's XCLC
(persistent cell XCLC is ignored for spatial checks).

Exits 1 when any flag or inconclusive (missing position) is raised.

Usage:
  python scripts/oracles/placement_frame.py --plugin mission.esp --core core.esp \\
      --world-edid TestWorld [--anchor Good]
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fo4sf.fo4land import Plugin  # noqa: E402
from fo4sf.terrain_grid import sf_cell_of, SF_CELL_M  # noqa: E402


def collect_refs(plugin_path, world_edid):
    """Return coverage cells, refs, world_fid, and whether the persistent cell was seen."""
    with Plugin(plugin_path) as p:
        data = p.read_world(world_edid, cells=None, refs=True)
        cells_with_coverage = set()
        sources = list(data["cells"].values())
        persistent = data.get("persistent_cell")
        if persistent:
            sources.append(persistent)
        for cell in sources:
            if not cell:
                continue
            # Coverage: VHGT/LAND or any SFBK/BTD indicator (supported hypothesis for writer output)
            has_terrain = (cell.get("vhgt") is not None or cell.get("land_fid") is not None
                           or cell.get("sfbk") or cell.get("btd"))
            xy = (cell["x"], cell["y"]) if cell.get("x") is not None else None
            if xy and has_terrain and not cell.get("persistent_cell"):
                cells_with_coverage.add(xy)
        refs = []
        for cell in sources:
            if not cell:
                continue
            is_persistent = bool(cell.get("persistent_cell"))
            parent = (cell["x"], cell["y"]) if cell.get("x") is not None else None
            for bucket in ("refs", "persistent_refs"):
                for r in cell.get(bucket, []):
                    rr = dict(r)
                    rr["parent_xy"] = parent
                    rr["parent_fid"] = cell["fid"]
                    rr["is_persistent_parent"] = is_persistent
                    refs.append(rr)
        return cells_with_coverage, refs, data["world_fid"], bool(persistent)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plugin", required=True)
    ap.add_argument("--core", required=True)
    ap.add_argument("--world-edid", required=True, help="EDID of the shared worldspace")
    ap.add_argument("--anchor", help="EDID of an anchor ref (distance reported if found; limited)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        core_cells, _, core_fid, _ = collect_refs(args.core, args.world_edid)
        _, plugin_refs, plugin_fid, _ = collect_refs(args.plugin, args.world_edid)
    except Exception as exc:
        print(f"failed to read plugins: {exc}", file=sys.stderr)
        return 2

    # Identity check: world fids should match (or plugin is master-index rebased; flag if different)
    identity_ok = (plugin_fid == core_fid)
    if not identity_ok:
        print(f"warning: world_fid mismatch plugin={plugin_fid:08X} core={core_fid:08X}", file=sys.stderr)

    flags = []
    report = []
    for r in plugin_refs:
        pos = r.get("pos")
        has_pos = pos and len(pos) >= 3 and all(math.isfinite(float(v)) for v in pos[:3])
        if not has_pos:
            entry = {
                "fid": f"{r.get('fid', 0):08X}",
                "type": r.get("type"),
                "pos": None,
                "computed_cell": None,
                "parent_cell": list(r.get("parent_xy")) if r.get("parent_xy") else None,
                "core_has_coverage": False,
                "flag": True,
                "reason": "missing_or_invalid_position",
            }
            report.append(entry)
            flags.append(entry)
            continue

        # Positions are treated as Starfield metres (core worldspace)
        computed = sf_cell_of(pos[0], pos[1])
        parent = r.get("parent_xy")
        is_persistent = r.get("is_persistent_parent", False)
        has_coverage = computed in core_cells
        # Persistent parent XCLC is not a spatial constraint
        disagree = (not is_persistent) and parent is not None and tuple(parent) != computed
        flag = (not has_coverage) or disagree or not identity_ok
        entry = {
            "fid": f"{r.get('fid', 0):08X}",
            "type": r.get("type"),
            "pos": [round(float(v), 2) for v in pos],
            "computed_cell": list(computed),
            "parent_cell": list(parent) if parent else None,
            "core_has_coverage": has_coverage,
            "flag": flag,
            "reason": ("no_coverage" if not has_coverage else
                       "parent_mismatch" if disagree else
                       "world_identity" if not identity_ok else None),
        }
        report.append(entry)
        if flag:
            flags.append(entry)

    out = {
        "world_fid": f"{core_fid:08X}",
        "plugin_world_fid": f"{plugin_fid:08X}",
        "identity_ok": identity_ok,
        "core_coverage_cells": len(core_cells),
        "refs": report,
        "flagged": len(flags),
        "cell_size_m": SF_CELL_M,
    }
    if args.json:
        print(json.dumps(out, indent=2, allow_nan=False))
    else:
        print(f"world {out['world_fid']} (plugin {out['plugin_world_fid']})  "
              f"core coverage cells: {out['core_coverage_cells']}  cell={SF_CELL_M}m")
        print(f"refs: {len(report)}  flagged: {len(flags)}")
        for e in report:
            mark = "FLAG" if e["flag"] else "ok  "
            print(f"  {mark} {e['fid']} {e['type']} pos={e['pos']} "
                  f"cell={e['computed_cell']} parent={e['parent_cell']} "
                  f"coverage={e['core_has_coverage']} reason={e.get('reason')}")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main())
