#!/usr/bin/env python3
"""Print a compact census of a BA2 archive for conversion planning.

Usage:
    python scripts/ba2_census.py path/to/archive.ba2 [--top N]

Emits JSON with summary counts and the largest entries. Offline only.
"""
import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fo4sf.ba2 import Ba2, Ba2Error  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="BA2 census for conversion planning")
    ap.add_argument("archive", type=Path, help="Path to a .ba2 file")
    ap.add_argument("--top", type=int, default=5, help="Number of largest entries to include")
    args = ap.parse_args()

    if not args.archive.is_file():
        print(f"error: {args.archive} not found", file=sys.stderr)
        return 1
    try:
        a = Ba2(str(args.archive))
    except Ba2Error as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    report = {
        "summary": a.summary(),
        "largest": a.largest_entries(args.top),
    }
    # Drop the full path from the public report to keep it portable
    report["summary"].pop("path", None)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
