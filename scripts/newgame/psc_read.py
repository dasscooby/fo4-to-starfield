"""Read-only: print named Papyrus sources from Starfield's ContentResources.zip, numbered, with an outline and who names them.

Written for the moving-platform lane of the Vault 111 animation experiment (FAL-489): MovingPlatformMasterScript and the LoadElevator*
scripts. For each `--script NAME` (the file name without .psc, case-insensitive, an exact match; repeatable) it prints
  1. the whole source with line numbers (nothing is cut, so a read is a read of the file and not of a summary);
  2. an outline from that file only, with line numbers: the Scriptname line (what it extends), Import, Property, Group, State, Function
     and Event lines. It is a line filter on those keywords, not a parse of Papyrus: a declaration it does not recognise (a plain
     variable, a call, a property read) is only in 1.;
  3. the other sources in the zip whose text names this script (file name and line count of the mentions), so the callers and the scripts it
     is linked to are found by name. A mention is a case-insensitive whole-word match.
`--match REGEX` (repeatable) lists the source names that match (case-insensitive search on the file name), e.g. `--match LoadElevator`.
`--grep WORD` (repeatable) lists every line of every source that contains WORD, with file and line number (capped by --grep-limit, default 60).

usage: python psc_read.py --out <report.txt> --script MovingPlatformMasterScript --match LoadElevator --match MovingPlatform
           [--zip <ContentResources.zip>] [--grep WORD] [--grep-limit 60]
It opens the zip read-only and writes only --out. The text of the game's sources goes into the report you post, never into the repo.
"""
import argparse
import os
import re
import sys
import zipfile

STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
OUTLINE = re.compile(
    r"^\s*(?:scriptname\b|import\b|group\b|endgroup\b|(?:auto\s+)?state\b|endstate\b|endfunction\b|endevent\b"
    r"|(?:[\w:]+(?:\[\])?\s+)?(?:function|event)\s+\w|[\w:]+(?:\[\])?\s+property\s+\w|(?:custom)?event\s+\w)", re.I)
MATCH_CAP = 80


def sources(z):
    """{name: text} for every .psc in the zip whose path contains 'source' (as start_read.py reads them)."""
    return {n: z.read(n).decode("utf-8", errors="replace") for n in sorted(z.namelist()) if n.lower().endswith(".psc") and "source" in n.lower()}


def stem(name):
    return os.path.splitext(os.path.basename(name.replace("\\", "/")))[0]


def outline(text):
    return [(i, ln.rstrip()) for i, ln in enumerate(text.splitlines(), 1) if OUTLINE.match(ln)]


def mentions(srcs, script):
    pat = re.compile(r"\b" + re.escape(script) + r"\b", re.I)
    out = []
    for n, t in srcs.items():
        if stem(n).lower() == script.lower():
            continue
        hits = [i for i, ln in enumerate(t.splitlines(), 1) if pat.search(ln)]
        if hits:
            out.append((n, hits))
    return out


def report(srcs, scripts, matches, greps, grep_limit):
    out = [f"psc_read: {len(srcs)} source file(s) read"]
    by_stem = {}
    for n in srcs:
        by_stem.setdefault(stem(n).lower(), []).append(n)
    for s in scripts:
        found = by_stem.get(s.lower(), [])
        if not found:
            out += ["", f"===== {s}: no source of that name in the zip (unread)"]
            continue
        for n in found:
            text = srcs[n]
            lines = text.splitlines()
            out += ["", f"===== {n}  ({len(lines)} lines, {len(text)} characters)  WHOLE, numbered"]
            out += [f"{i:5d}| {ln}" for i, ln in enumerate(lines, 1)]
            out += ["", f"----- outline of {n} (a line filter, not a parse):"]
            out += [f"{i:5d}| {ln}" for i, ln in outline(text)] or ["  (no line matched)"]
            ms = mentions(srcs, s)
            out += ["", f"----- other sources that name {s}: {len(ms)}"]
            for mn, hits in ms:
                out.append(f"  {mn}: line(s) " + ", ".join(map(str, hits[:12])) + (" ..." if len(hits) > 12 else ""))
    for m in matches:
        names = [n for n in srcs if re.search(m, n, re.I)]
        out += ["", f"===== source names matching {m!r}: {len(names)}"] + [f"  {n}  ({len(srcs[n].splitlines())} lines)" for n in names[:MATCH_CAP]]
        if len(names) > MATCH_CAP:
            out.append(f"  ... {len(names) - MATCH_CAP} more not listed")
    for g in greps:
        hits = [(n, i, ln.rstrip()) for n, t in srcs.items() for i, ln in enumerate(t.splitlines(), 1) if g.lower() in ln.lower()]
        out += ["", f"===== lines containing {g!r}: {len(hits)}" + (f" (first {grep_limit})" if len(hits) > grep_limit else "")]
        out += [f"  {n}:{i}: {ln}" for n, i, ln in hits[:grep_limit]]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", default=os.path.join(STARFIELD, "Tools", "ContentResources.zip"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--script", action="append", default=[], help="a script name without .psc (exact, case-insensitive; repeatable)")
    ap.add_argument("--match", action="append", default=[], help="a regex searched in the source file names (repeatable)")
    ap.add_argument("--grep", action="append", default=[], help="a word: every source line that contains it (repeatable)")
    ap.add_argument("--grep-limit", type=int, default=60)
    a = ap.parse_args(argv)
    if not (a.script or a.match or a.grep):
        ap.error("give at least one of --script, --match, --grep")
    if not os.path.isfile(a.zip):
        sys.exit(f"{a.zip} missing")
    with zipfile.ZipFile(a.zip) as z:
        srcs = sources(z)
    text = report(srcs, a.script, a.match, a.grep, a.grep_limit)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"psc_read ok: {len(srcs)} sources; report {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
