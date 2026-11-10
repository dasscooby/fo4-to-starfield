"""Offline plugin-load check for built plugins: python scripts/verify_plugin.py PLUGIN... [--known NAME] [--json]

Plugins given together are one kit, in load order. Exit 0: nothing found (not a PASS in game); 1: problems.
Rules and limits: src/fo4sf/plugin_verify.py."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from fo4sf import plugin_verify  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plugins", nargs="+")
    ap.add_argument("--known", action="append", default=[], help="a further master name the game provides")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    reports = plugin_verify.verify_kit(a.plugins, known=a.known)
    if a.json:
        print(json.dumps([r.as_dict() for r in reports], indent=1))
    else:
        for r in reports:
            print(f"{r.name}: {'nothing found' if r.ok else 'PROBLEMS'} ({r.records} records, masters {r.masters})")
            for t in r.problems:
                print("  PROBLEM", t)
            for t in r.warnings:
                print("  warn", t)
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
