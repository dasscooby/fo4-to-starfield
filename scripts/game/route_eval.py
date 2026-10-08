"""Score route_run.ps1 results against the expectations from routes.py.

usage: python route_eval.py routes.json results.jsonl
stairs: PASS if the end height is at least low + min_rise and the player did not drop below the start floor;
        STUCK if it rose less; FALL if it ended more than 0.5 m below the ramp's low end.
door:   PASS if the end point is min_past metres beyond the door plane (dot with the plane normal); otherwise NOPROMPT
        if route_run never saw the activation prompt, else BLOCKED.
Unreadable positions are UNREAD. Prints one line per route and a summary; exit code 1 if anything is not PASS.
"""
import json
import math
import sys


def parse(s):
    try:
        v = [float(x) for x in s.split()]
        return v if len(v) == 3 else None
    except (AttributeError, ValueError):
        return None


def judge(route, res):
    end = parse(res.get("end_read"))
    start = parse(res.get("start_read"))
    if end is None:
        return "UNREAD", ""
    # OCR can drop a minus sign or shift columns: reject moves no walk of this length could make
    if start is not None and (abs(end[2] - start[2]) > 6 or abs(end[0] - start[0]) + abs(end[1] - start[1]) > 15):
        return "UNREAD", f"implausible read {res.get('start_read')} -> {res.get('end_read')}"
    # the teleport target was invalid (e.g. under the floor) and the engine put the player at the cell entrance instead
    target = route.get("start")
    if start is not None and target and abs(start[0] - target[0]) + abs(start[1] - target[1]) > 3:
        return "UNREAD", f"start not reached: read {res.get('start_read')}"
    e = route["expect"]
    if route["kind"] == "stairs":
        low, high = e["low"], e["high"]
        rise = end[2] - low[2]
        top_rise = high[2] - low[2]
        if rise > top_rise + 2.0:                     # higher than the stair goes: a misread, not a climb
            return "UNREAD", f"implausible rise {rise:.2f} (stair top is {top_rise:.2f})"
        dx, dy = high[0] - low[0], high[1] - low[1]
        span = math.hypot(dx, dy) or 1.0
        off_axis = abs((end[0] - low[0]) * dy - (end[1] - low[1]) * dx) / span
        if off_axis > 3.0:                            # not on this stair's line: a shifted OCR column
            return "UNREAD", f"end {off_axis:.1f} m off the stair"
        if end[2] < low[2] - 0.5:
            return "FALL", f"z {end[2]:.2f} < floor {low[2]:.2f}"
        return ("PASS" if rise >= e["min_rise"] else "STUCK"), f"rise {rise:.2f} / need {e['min_rise']:.2f}"
    normal = e["plane_normal"]
    length = math.hypot(*normal)
    if length < 1e-6:
        return "UNREAD", "door normal missing"
    unit = tuple(part / length for part in normal)
    delta = tuple(end[i] - e["plane_point"][i] for i in range(3))
    past = sum(delta[i] * unit[i] for i in range(3))
    # Lateral in the horizontal plane only. A door centre is above the floor, so Z is not "off to the side".
    ux, uy = unit[0], unit[1]
    horizontal = math.hypot(ux, uy) or 1.0
    ux, uy = ux / horizontal, uy / horizontal
    side = abs((end[0] - e["plane_point"][0]) * uy - (end[1] - e["plane_point"][1]) * ux)
    if past > 12.0 or side > 3.0:
        return "UNREAD", f"implausible door end past {past:.1f} m, {side:.1f} m off the opening"
    if past >= e["min_past"]:
        return "PASS", f"past plane {past:.2f} m"
    if res.get("prompt") is False:                    # never saw "OPEN (E)": activation, not collision, is the problem
        return "NOPROMPT", f"past plane {past:.2f} m, no activation prompt"
    return "BLOCKED", f"past plane {past:.2f} m"


def main():
    routes = json.load(open(sys.argv[1], encoding="utf-8-sig"))["routes"]
    results = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8-sig") if l.strip()]
    counts = {}
    for res in results:
        r = routes[res["index"]]
        verdict, why = judge(r, res)
        counts[verdict] = counts.get(verdict, 0) + 1
        print(f"{res['index']:3d} {verdict:7s} {r['kind']:6s} {r['ref']} {r['model'].split(chr(92))[-1]:40s} {why}")
    print("summary:", counts)
    sys.exit(0 if set(counts) <= {"PASS"} else 1)


if __name__ == "__main__":
    main()
