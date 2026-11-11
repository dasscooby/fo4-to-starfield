"""Which furniture in Starfield.esm is a real power armor station? (FAL-273, #720: a chair plus the keyword does nothing.)

usage: python scripts/find_power_armor_furniture.py <Starfield.esm> [<out.txt>] [--word PowerArmor ...]

Read only. Steps, all from the plugin's own records:
  1. every KYWD whose editor id contains one of the words (default: PowerArmor, LinkPowerArmor, isPowerArmorBattery);
  2. every FURN that lists one of those keywords (KWDA), with editor id, form id, its model (MODL), whether it has a marker
     model / entry points / a script (VMAD), and the keywords it carries by name;
  3. every other record class that names one of those keywords or one of those FURNs in a subrecord (counts per class and
     the first editor ids): who uses the keywords besides furniture.
The report holds editor ids and form ids only, no record bytes: it can go into a comment. Nothing is written to the plugin.
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from fo4sf.planet import esm  # noqa: E402

DEFAULT_WORDS = ("PowerArmor", "LinkPowerArmor", "isPowerArmorBattery")
OTHER_CLASSES = ("ARMO", "NPC_", "REFR", "ACHR", "MISC", "OMOD", "COBJ", "KYWD", "STAT", "ACTI", "LCTN", "QUST", "PERK", "SPEL")


def kwda_ids(rec):
    """Form ids of the record's KWDA (a list of 4-byte ids), [] when it has none."""
    data = rec.get(b"KWDA")
    if not data:
        return []
    return list(struct.unpack(f"<{len(data) // 4}I", data[:len(data) // 4 * 4]))


def mentions(rec, ids):
    """True when any 4-byte aligned word of any subrecord equals one of ids (a cheap 'names this form' test)."""
    for sub, data in rec.subs:
        if len(data) >= 4 and len(data) % 4 == 0:
            for word in struct.unpack(f"<{len(data) // 4}I", data):
                if word in ids:
                    return True
    return False


def report(path, words=DEFAULT_WORDS, others=OTHER_CLASSES):
    lines = []
    with esm.Plugin(path) as plugin:
        keywords = {}
        for rec in plugin.records("KYWD", ["KYWD"]):
            e = rec.edid
            if any(w.casefold() in e.casefold() for w in words):
                keywords[rec.formid] = e
        lines.append(f"{os.path.basename(path)}: {len(keywords)} keywords match {list(words)}")
        for fid, e in sorted(keywords.items()):
            lines.append(f"  KYWD {fid:08X} {e}")
        names = {fid: e for fid, e in keywords.items()}
        furn = []
        for rec in plugin.records("FURN", ["FURN"]):
            ids = [k for k in kwda_ids(rec) if k in keywords]
            if ids:
                furn.append((rec, ids))
        lines.append("")
        lines.append(f"FURN carrying one of them: {len(furn)}")
        for rec, ids in furn:
            allkw = kwda_ids(rec)
            modl = rec.get(b"MODL") or b""
            lines.append(f"  FURN {rec.formid:08X} {rec.edid}: keywords {[names[k] for k in ids]} of {len(allkw)} total; "
                         f"model {modl.rstrip(bytes(1)).decode('latin-1')!r}; "
                         f"marker-model {'yes' if rec.get(b'XMRK') else 'no'}; entry-points {'yes' if rec.get(b'FNPR') or rec.get(b'FNMK') else 'no'}; "
                         f"script {'yes' if rec.get(b'VMAD') else 'no'}")
        targets = set(keywords) | {rec.formid for rec, _ in furn}
        lines.append("")
        lines.append("other records naming those keywords or furniture (count, first editor ids):")
        for sig in others:
            n, first = 0, []
            for rec in plugin.records(sig, [sig]):
                if rec.formid in targets:
                    continue
                if mentions(rec, targets):
                    n += 1
                    if len(first) < 8:
                        first.append(rec.edid or f"{rec.formid:08X}")
            if n:
                lines.append(f"  {sig}: {n}  {first}")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("esm")
    ap.add_argument("out", nargs="?", default="")
    ap.add_argument("--word", action="append", default=[], help="an editor id fragment to look for (repeatable)")
    a = ap.parse_args(argv)
    lines = report(a.esm, tuple(a.word) or DEFAULT_WORDS)
    text = "\n".join(lines) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {a.out} ({len(lines)} lines)")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
