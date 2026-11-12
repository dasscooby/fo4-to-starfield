#!/usr/bin/env python3
"""Which of the player's floats is the heading, and how wide a cell is, from F11 dumps of the Pip-Boy kit (FAL-595).

At stage (e) (`Stage=5`) the snapshot key (F11) also logs the player's bytes from +0x80 to +0xC0 and the six floats at
+0x80 (libxse's OBJ_REFR: angle x y z, then location x y z), `step=kit_map_bytes n=<snapshot> at=+080 bytes=<hex>
floats=<six, comma separated>`, and the player's cell with its own grid (libxse TESObjectCELL::cellData at +0x58, an
EXTERIOR_DATA with cellX and cellY), `step=kit_map_cell n=<snapshot> cell=<addr> world=<addr> flags=<hex> data=<addr>
cell_x=<x> cell_y=<y>`.

Heading (the default): F11 standing still, turn on the spot about 90 degrees to the right, F11 again; this compares the
first and the last dump (or --before/--after) and marks the angle float that moved by 45 to 135 degrees while the other
two stayed (within 3 degrees) and the position stayed (within 64 units). When exactly one is marked it prints the line
for [Kit], `HeadingAt=<80|84|88>`, with '-' before the offset when the float fell as the player turned right: the MAP
page's HEADING then shows it in compass degrees.

Grid (--grid): F11 in one cell, walk until POSITION's x or y on the MAP page has crossed a multiple of --units (4096,
the hypothesis) by a few hundred units, F11 again. For each dump in a cell with a worldspace it compares the cell's own
grid with POSITION's x and y over --units, rounded down. When every such dump matches and they cover two cells or more
it prints `GridUnits=<units>`: the MAP page's GRID then shows POSITION over it. If the cell's grid was unreadable it
says whether the cell's address changed exactly where the rounded position did, which is weaker and prints nothing.
Reads the log only; pure Python, test tests/test_pipboy_map_bytes.py."""
import argparse
import math
import re
import sys

BYTES = re.compile(r"step=kit_map_bytes n=(\d+) at=\+080 bytes=\S+ floats=([-0-9.,a-z]+)")
CELL = re.compile(r"step=kit_map_cell n=(\d+) cell=(0x[0-9a-f]+) world=(\S+) flags=(\S+) data=(0x[0-9a-f]+) "
                  r"(?:cell_x=(-?\d+) cell_y=(-?\d+)|cell_xy=unreadable)")
ANGLES = (0x80, 0x84, 0x88)              # the plugin's kAngleAt and the two floats after it
TURN = (math.radians(45), math.radians(135))
STILL = math.radians(3)
STEP = 64.0                              # game units the position may move while turning on the spot


def dumps(lines):
    """{n: {"floats": [6 floats] or None, "cell": {...} or None}} from the log's kit_map lines."""
    found = {}
    for line in lines:
        match = BYTES.search(line)
        if match:
            parts = match[2].split(",")
            floats = [float(p) for p in parts] if len(parts) == 6 and match[2] != "unreadable" else None
            found.setdefault(int(match[1]), {"floats": None, "cell": None})["floats"] = floats
            continue
        match = CELL.search(line)
        if match:
            cell = {"cell": match[2], "world": match[3], "flags": match[4], "data": match[5],
                    "xy": (int(match[6]), int(match[7])) if match[6] is not None else None}
            found.setdefault(int(match[1]), {"floats": None, "cell": None})["cell"] = cell
    return found


def turned(a, b):
    """b - a in radians, brought into (-pi, pi]."""
    d = math.fmod(b - a, 2 * math.pi)
    if d <= -math.pi:
        d += 2 * math.pi
    elif d > math.pi:
        d -= 2 * math.pi
    return d


def heading(before, after):
    """[(offset, before, after, degrees turned, is_heading)] for the three angle floats, and the position moved."""
    rows = []
    for i, at in enumerate(ANGLES):
        d = turned(before[i], after[i])
        rows.append((at, before[i], after[i], math.degrees(d), TURN[0] <= abs(d) <= TURN[1]))
    moved = math.dist(before[3:5], after[3:5])
    return rows, moved


def heading_line(rows, moved):
    """`HeadingAt=[-]<offset>` when exactly one float turned by about 90 degrees, the others stayed and the player did
    not walk; else None."""
    marked = [r for r in rows if r[4]]
    still = all(abs(math.radians(r[3])) <= STILL for r in rows if not r[4])
    if len(marked) != 1 or not still or moved > STEP:
        return None
    at, _, _, degrees, _ = marked[0]
    return f"HeadingAt={'-' if degrees < 0 else ''}{at:X}"


def grid(found, units):
    """[(n, x, y, (floor x, floor y), cell grid or None, cell address, matches)] for each dump in a cell with a
    worldspace whose floats were read."""
    rows = []
    for n in sorted(found):
        floats, cell = found[n]["floats"], found[n]["cell"]
        if not floats or not cell or cell["world"] in ("0x0", "unreadable"):
            continue
        x, y = floats[3], floats[4]
        rounded = (math.floor(x / units), math.floor(y / units))
        rows.append((n, x, y, rounded, cell["xy"], cell["cell"], cell["xy"] == rounded))
    return rows


def grid_line(rows, units):
    """`GridUnits=<units>` when every row's cell grid was read and matches, over two cells or more; else None."""
    if not rows or any(r[4] is None or not r[6] for r in rows) or len({r[3] for r in rows}) < 2:
        return None
    return f"GridUnits={units}"


def cell_changes_agree(rows):
    """For rows without the cell's grid: True when the cell's address changed between consecutive dumps exactly where
    the rounded position did (and it did at least once), else False."""
    pairs = list(zip(rows, rows[1:]))
    return bool(pairs) and any(a[3] != b[3] for a, b in pairs) and \
        all((a[3] != b[3]) == (a[5] != b[5]) for a, b in pairs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("log", help="the plugin's log (FO4SFPipboyMenu.log)")
    parser.add_argument("--before", type=int, help="the first dump's n (default: the first in the log)")
    parser.add_argument("--after", type=int, help="the second dump's n (default: the last in the log)")
    parser.add_argument("--grid", action="store_true", help="the cell's width instead of the heading")
    parser.add_argument("--units", type=int, default=4096, help="the cell width to test (default 4096)")
    args = parser.parse_args(argv)
    with open(args.log, encoding="utf-8", errors="replace") as f:
        found = dumps(f)
    if args.grid:
        rows = grid(found, args.units)
        if not rows:
            print("no kit_map_bytes and kit_map_cell pair in a cell with a worldspace")
            return 1
        for n, x, y, rounded, xy, cell, ok in rows:
            print(f"n={n} x={x:.1f} y={y:.1f} over {args.units}={rounded[0]},{rounded[1]} "
                  f"cell={cell} cell_grid={'unreadable' if xy is None else f'{xy[0]},{xy[1]}'}"
                  f"{'' if xy is None else ' match' if ok else ' DIFFERS'}")
        line = grid_line(rows, args.units)
        if line:
            print(line)
            return 0
        if all(r[4] is None for r in rows) and cell_changes_agree(rows):
            print(f"the cell's grid was unreadable; its address changed where POSITION over {args.units} did "
                  "(weaker: no line printed)")
        elif len({r[3] for r in rows}) < 2:
            print("one cell only: walk across a border and press F11 again")
        else:
            print(f"no line: the cell's grid does not follow POSITION over {args.units}")
        return 1
    read = sorted(n for n in found if found[n]["floats"])
    if len(read) < 2 and (args.before is None or args.after is None):
        print("fewer than two kit_map_bytes dumps with floats")
        return 1
    before = args.before if args.before is not None else read[0]
    after = args.after if args.after is not None else read[-1]
    if not (found.get(before) or {}).get("floats") or not (found.get(after) or {}).get("floats"):
        print(f"dump {before} or {after} has no floats")
        return 1
    rows, moved = heading(found[before]["floats"], found[after]["floats"])
    for at, a, b, degrees, mark in rows:
        print(f"+{at:03X} {a:.4f} -> {b:.4f} turned {degrees:+.1f} deg{'  heading?' if mark else ''}")
    print(f"position moved {moved:.1f} units")
    line = heading_line(rows, moved)
    if line:
        print(line)
        return 0
    print("no line: exactly one float should turn by 45 to 135 degrees while the rest and the position stay")
    return 1


if __name__ == "__main__":
    sys.exit(main())
