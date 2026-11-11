"""Print a short summary of a BA2 archive, including total sizes.

Useful for conversion planning: see entry counts and how much data is in the archive
without listing every file or ranking by size.

usage: python -I scripts/ba2_summary.py <archive.ba2>
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf.ba2 import Ba2  # noqa: E402


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    path = argv[1]
    if not os.path.isfile(path):
        print(f"not a file: {path}", file=sys.stderr)
        return 1
    try:
        a = Ba2(path)
        print(json.dumps(a.summary(), indent=2))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
