"""List placed refs whose FO4 collision did not become a native body.

`no_collision` means the conversion failed and no box was written. `guessed` means
it failed and a box fallback was written instead. A model FO4 shipped with no
collision, a passable door, and a rigged door (an empty report plus a door record)
are not this list. Exit 1 when either list is non-empty. This does not score a walk.

usage: python scripts/oracles/placed_collision.py --cell cell.json --manifest manifest.json
"""
import argparse
import json


_OK = {"fo4-native", "fo4-none", "fo4-mesh", "passable-door"}


def _items(manifest):
    return {item.get("source", "").lower(): item for item in manifest.get("items", [])}


def failure_kind(item):
    """`no_collision`, `guessed`, or None when this item is not a placed-collision failure."""
    report = item.get("collision_report")
    if not isinstance(report, dict) or not report:
        return None if item.get("door") else "no_collision"
    source = report.get("source")
    if source in _OK:
        return None
    if source == "fo4-native-failed":
        return "no_collision"
    if report.get("fo4_collision_error"):
        boxes = report.get("boxes") or 0
        return "guessed" if boxes else "no_collision"
    return None


def placed(cell, items):
    """Refs in the cell whose manifest item failed native collision."""
    no_collision = []
    guessed = []
    for ref in cell.get("refs", []):
        model = ref.get("model") or ""
        if not model:
            continue
        key = "meshes\\" + model.lstrip("\\").lower()
        item = items.get(key)
        if not item:
            continue
        kind = failure_kind(item)
        if kind is None:
            continue
        report = item.get("collision_report") or {}
        row = {"ref": ref.get("formkey") or ref.get("ref"), "model": model,
               "reason": report.get("source") or report.get("fo4_collision_error") or "empty report"}
        (no_collision if kind == "no_collision" else guessed).append(row)
    return {"no_collision": no_collision, "guessed": guessed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    with open(args.cell, encoding="utf-8-sig") as handle:
        cell = json.load(handle)
    with open(args.manifest, encoding="utf-8-sig") as handle:
        items = _items(json.load(handle))
    report = placed(cell, items)
    print(json.dumps(report, indent=2))
    return 1 if report["no_collision"] or report["guessed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
