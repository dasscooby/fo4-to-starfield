#!/usr/bin/env python3
"""Where the mission keeps its current stage and its objectives' states, from F11 dumps of the Pip-Boy kit (FAL-446).

At stage (e) (`Stage=5`) the snapshot key (F11) logs the mission's bytes from +0x38 to +0x338, 64 to a line:
`step=kit_quest_bytes n=<snapshot> form=<id> at=+<offset> bytes=<hex, a comma every 8>`. Open the quests page once,
press F11, set the mission to another stage in the console (`setstage <its form id, as the page's FORM shows it> <n>`,
the first two digits the plugin's load index: the console refuses its editor ID), press F11 again; then run this on
the plugin's log. It lists every 2-byte word that differs between two dumps (the first and the last in the log, or
--before/--after), with both values in decimal, and marks a word that went from the first stage to the second
(--stages 20,30) as `stage?`.
When exactly one word is marked it prints the line for the plugin's ini, `MissionStageAt=<hex>` in [Kit] (FAL-527):
the quests page's STAGE then reads that word.

The objectives (FAL-571, --objective <n>): the same F11 press also logs each 0x40-byte block, one or two pointers away
from the mission, that points back to it, `step=kit_quest_obj n= form= path=+<offset>[/+<offset>] at=<address>
bytes=<hex>`, and a count, `step=kit_quest_objs n= form= followed=<k> owned=<m>`. Press F11, change one objective in
the console (`setobjectivedisplayed <form id> <n> 1`, or `setobjectivecompleted <form id> <n> 1`), press F11 again; this
lists every byte that differs in a block both dumps logged at the same address and marks one in a block that holds the
objective's number as a 2-byte word as `objective?`. When exactly one byte is marked it prints the line for [Kit],
`MissionObjective=<n>|<path>/<byte>`: the quests page then shows that byte as OBJECTIVE <n>.
Reads the log only; pure Python, test tests/test_pipboy_quest_bytes.py."""
import argparse
import re
import sys

LINE = re.compile(r"step=kit_quest_bytes n=(\d+) form=([0-9A-F]{8}) at=\+([0-9A-F]+) bytes=([0-9a-f,]+)")
OBJ = re.compile(r"step=kit_quest_obj n=(\d+) form=([0-9A-F]{8}) path=(\+[0-9A-F]+(?:/\+[0-9A-F]+)?) at=(0x[0-9a-f]+) "
                 r"bytes=([0-9a-f,]+)")
OBJS = re.compile(r"step=kit_quest_objs n=(\d+) form=([0-9A-F]{8}) followed=(\d+) owned=(\d+)")


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


def blocks(lines):
    """{n: (form, {path: (address, bytes)}, (followed, owned) or None)} from the log's kit_quest_obj and kit_quest_objs
    lines (FAL-571); an unreadable block is left out."""
    found = {}
    for line in lines:
        match = OBJ.search(line)
        if match:
            entry = found.setdefault(int(match[1]), [match[2], {}, None])
            entry[1][match[3]] = (int(match[4], 16), bytes.fromhex(match[5].replace(",", "")))
            continue
        match = OBJS.search(line)
        if match:
            found.setdefault(int(match[1]), [match[2], {}, None])[2] = (int(match[3]), int(match[4]))
    return {n: tuple(entry) for n, entry in found.items()}


def holds(data, index):
    """True when the block holds index as a little-endian 2-byte word at an even offset."""
    return any(data[i] | data[i + 1] << 8 == index for i in range(0, len(data) - 1, 2))


def objective_changes(before, after, index=None):
    """[(path, offset, before, after, marked)] for each byte that differs in a block both dumps logged at the same
    address; marked when the block (after) holds index."""
    rows = []
    for path in sorted(set(before) & set(after), key=lambda p: [int(part[1:], 16) for part in p.split("/")]):
        (at_a, a), (at_b, b) = before[path], after[path]
        if at_a != at_b:
            continue
        mark = index is not None and holds(b, index)
        rows.extend((path, i, a[i], b[i], mark) for i in range(min(len(a), len(b))) if a[i] != b[i])
    return rows


def objective_line(index, rows):
    """The [Kit] line for the one byte marked as the objective's state, else None (none marked, or several)."""
    marked = [(path, at) for path, at, _, _, mark in rows if mark]
    if len(marked) != 1:
        return None
    path, at = marked[0]
    return f"MissionObjective={index}|{'/'.join(f'{int(part[1:], 16):X}' for part in path.split('/'))}/{at:X}"


def main_objective(args, found):
    """--objective: the bytes that changed behind the mission's pointers between two F11 presses (FAL-571)."""
    if not found:
        print("no kit_quest_obj or kit_quest_objs lines: the plugin at this head logs them on F11 at stage (e)",
              file=sys.stderr)
        return 2
    counts = {n: entry[2] for n, entry in found.items() if entry[2] is not None}
    if counts and not any(owned for _, owned in counts.values()):
        print(f"no block one or two pointers from the mission points back to it ({len(counts)} presses, followed="
              f"{max(followed for followed, _ in counts.values())}): the objectives need a wider dump (README, quests)")
        return 1
    if len(found) < 2:
        print(f"need two F11 presses with kit_quest_obj lines, found {len(found)}", file=sys.stderr)
        return 2
    before = args.before if args.before is not None else min(found)
    after = args.after if args.after is not None else max(found)
    if before not in found or after not in found:
        print(f"no press n={before if before not in found else after}; presses: {sorted(found)}", file=sys.stderr)
        return 2
    if found[before][0] != found[after][0]:
        print(f"different forms: n={before} {found[before][0]}, n={after} {found[after][0]}", file=sys.stderr)
        return 2
    a, b = found[before][1], found[after][1]
    rows = objective_changes(a, b, args.objective)
    moved = sum(1 for path in set(a) & set(b) if a[path][0] != b[path][0])
    print(f"form={found[before][0]} n={before} -> n={after}: {len(a)} and {len(b)} blocks, {moved} moved, "
          f"{len(rows)} bytes differ")
    for path, at, a, b, mark in rows:
        print(f"{path} +0x{at:02X} {a} -> {b}{'  objective?' if mark else ''}")
    line = objective_line(args.objective, rows)
    print(f"in [Kit] of FO4SFPipboyMenu.ini: {line}" if line else
          f"{sum(row[4] for row in rows)} bytes marked: no MissionObjective line (one is needed)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", help="the plugin's log (FO4SFPipboyMenu.log)")
    parser.add_argument("--before", type=int, help="the snapshot n before setstage (default: the first dumped)")
    parser.add_argument("--after", type=int, help="the snapshot n after setstage (default: the last dumped)")
    parser.add_argument("--stages", help="the two stages, before and after, e.g. 20,30")
    parser.add_argument("--objective", type=int,
                        help="the objective changed between the two presses, e.g. 10 (FAL-571)")
    args = parser.parse_args(argv)
    with open(args.log, encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    if args.objective is not None:
        return main_objective(args, blocks(lines))
    found = dumps(lines)
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
