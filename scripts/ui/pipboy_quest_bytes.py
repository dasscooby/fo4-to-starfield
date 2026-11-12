#!/usr/bin/env python3
"""Where the mission keeps its current stage, from two F11 dumps of the Pip-Boy kit (FAL-446).

At stage (e) (`Stage=5`) the snapshot key (F11) logs the mission's bytes from +0x38 to +0x338, 64 to a line:
`step=kit_quest_bytes n=<snapshot> form=<id> at=+<offset> bytes=<hex, a comma every 8>`. Open the quests page once,
press F11, set the mission to another stage in the console (`setstage <its form id, as the page's FORM shows it> <n>`:
the console refuses its editor ID), press F11 again; then run this on the plugin's log. It
lists every 2-byte word that differs between two dumps (the first and the last in the log, or --before/--after), with
both values in decimal, and marks a word that went from the first stage to the second (--stages 20,30) as `stage?`.
When exactly one word is marked it prints the line for the plugin's ini, `MissionStageAt=<hex>` in [Kit] (FAL-527):
the quests page's STAGE then reads that word. Reads the log only; pure Python, test tests/test_pipboy_quest_bytes.py."""
import argparse
import re
import sys

LINE = re.compile(r"step=kit_quest_bytes n=(\d+) form=([0-9A-F]{8}) at=\+([0-9A-F]+) bytes=([0-9a-f,]+)")


def dumps(lines):
    """{n: (form, {offset: byte})} from the log's kit_quest_bytes lines; unreadable lines are left out."""
    found = {}
    for line in lines:
        match = LINE.search(line)
        if not match:
            continue
        n, form, at, hexes = int(match[1]), match[2], int(match[3], 16), match[4].replace(",", "")
        _, data = found.setdefault(n, (form, {}))
        for i in range(len(hexes) // 2):
            data[at + i] = int(hexes[2 * i:2 * i + 2], 16)
    return found


def words(data):
    """{offset: u16} for each even offset whose two bytes were read (little-endian)."""
    return {at: data[at] | data[at + 1] << 8 for at in sorted(data) if at % 2 == 0 and at + 1 in data}


def changed(before, after, stages=None):
    """[(offset, before, after, is_stage)] for each word read in both dumps that differs."""
    a, b = words(before), words(after)
    rows = []
    for at in sorted(set(a) & set(b)):
        if a[at] != b[at]:
            rows.append((at, a[at], b[at], stages is not None and (a[at], b[at]) == stages))
    return rows


def stage_line(rows):
    """The [Kit] line for the one word marked as the stage, else None (none marked, or several)."""
    marked = [at for at, _, _, is_stage in rows if is_stage]
    return f"MissionStageAt={marked[0]:X}" if len(marked) == 1 else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", help="the plugin's log (FO4SFPipboyMenu.log)")
    parser.add_argument("--before", type=int, help="the snapshot n before setstage (default: the first dumped)")
    parser.add_argument("--after", type=int, help="the snapshot n after setstage (default: the last dumped)")
    parser.add_argument("--stages", help="the two stages, before and after, e.g. 20,30")
    args = parser.parse_args(argv)
    with open(args.log, encoding="utf-8", errors="replace") as handle:
        found = dumps(handle)
    if len(found) < 2:
        print(f"need two kit_quest_bytes dumps, found {len(found)}", file=sys.stderr)
        return 2
    before = args.before if args.before is not None else min(found)
    after = args.after if args.after is not None else max(found)
    if before not in found or after not in found:
        print(f"no dump n={before if before not in found else after}; dumps: {sorted(found)}", file=sys.stderr)
        return 2
    if found[before][0] != found[after][0]:
        print(f"different forms: n={before} {found[before][0]}, n={after} {found[after][0]}", file=sys.stderr)
        return 2
    stages = tuple(int(s) for s in args.stages.split(",")) if args.stages else None
    if stages is not None and len(stages) != 2:
        print("--stages takes two numbers, before,after", file=sys.stderr)
        return 2
    rows = changed(found[before][1], found[after][1], stages)
    print(f"form={found[before][0]} n={before} -> n={after}: {len(rows)} words differ")
    for at, a, b, is_stage in rows:
        print(f"+0x{at:03X} {a} -> {b}{'  stage?' if is_stage else ''}")
    if stages is not None:
        line = stage_line(rows)
        print(f"in [Kit] of FO4SFPipboyMenu.ini: {line}" if line else
              f"{sum(row[3] for row in rows)} words marked: no MissionStageAt line (one is needed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
