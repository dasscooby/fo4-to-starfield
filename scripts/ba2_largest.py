#!/usr/bin/env python3
"""List the largest entries in a BA2 archive by unpacked size.

Useful for conversion planning: see which meshes or textures will dominate
time, memory or temporary disk before running a full extract or batch convert.

usage: python -I scripts/ba2_largest.py path/to/archive.ba2 [--n 20]
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.ba2 import Ba2, Ba2Error  # noqa: E402


def _nonneg(value):
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description="List largest BA2 entries by unpacked size")
    p.add_argument("archive", help="Path to a .ba2 file")
    p.add_argument("--n", type=_nonneg, default=20, help="How many to show (default 20)")
    a = p.parse_args(argv)
    try:
        ba2 = Ba2(a.archive)
    except (Ba2Error, OSError, struct.error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"{ba2.summary()['entries']} entries, showing top {a.n} by unpacked size:")
    print(f"{'unpacked':>12}  {'packed':>12}  kind   name")
    for item in ba2.largest_entries(a.n):
        print(f"{item['unpacked']:12,}  {item['packed']:12,}  {item['kind']:5}  {item['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
