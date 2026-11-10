"""Dump real Starfield records for the shared record writer (src/fo4sf/record_writer.py).

usage: python scripts/dump_starfield_records.py <Starfield.esm> <out dir> [--classes SPEL MGEF ...] [--per-class N]
                                                 [--keep N] [--edid NAME ...]

Writes <out dir>/starfield_records.json (every subrecord of the kept records in hex, plus per-signature layouts: which
bytes differ between records) and starfield_records.txt (the same as a table). Read only; Starfield.esm is not
changed. The output holds game bytes: keep it out of Git (the guard refuses plugins and archives; this is JSON, so
the rule is yours: it goes on the PC and into the issue as a path, not into a commit).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from fo4sf import record_writer as rw  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("esm")
    ap.add_argument("out")
    ap.add_argument("--classes", nargs="+", default=list(rw.CLASSES))
    ap.add_argument("--per-class", type=int, default=40)
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--edid", action="append", default=[], help="a record to write out whole, by editor id")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    dump = rw.dump_records(a.esm, a.classes, a.per_class, a.edid, a.keep)
    rw.save_dump(dump, os.path.join(a.out, "starfield_records.json"))
    text = rw.dump_text(dump)
    with open(os.path.join(a.out, "starfield_records.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(text)
    return 1 if any(c["missing_edids"] for c in dump["classes"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
