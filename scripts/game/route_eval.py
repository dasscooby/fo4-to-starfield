"""Score route_run.ps1 results against the expectations from routes.py.

usage: python route_eval.py routes.json results.jsonl
stairs: PASS if the end height is at least low + min_rise and the player did not drop below the start floor;
        STUCK if it rose less; FALL if it ended more than 0.5 m below the ramp's low end.
door:   PASS if the end point is min_past metres beyond the door plane (dot with the plane normal); BLOCKED otherwise.
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
    e = route["expect"]
    if route["kind"] == "stairs":
        low, high = e["low"], e["high"]
        rise = end[2] - low[2]
        top_rise = high[2] - low[2]
        if rise > top_rise + 2.0:                     # higher than the stair goes: a misread, not a climb
            return "UNREAD", f"implausible rise {rise:.2f} (stair top is {top_rise:.2f})"
        off_top = math.hypot(end[0] - high[0], end[1] - high[1])
        if off_top > 4.0:                             # right height in the wrong place is still a bad read
            return "UNREAD", f"end {off_top:.1f} m from the stair top"
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
    lateral = math.sqrt(max(0.0, sum(part * part for part in delta) - past * past))
    if past > 6.0 or lateral > 3.0:                   # a one-second walk cannot finish across the cell
        return "UNREAD", f"implausible door end past {past:.1f} m, {lateral:.1f} m off the opening"
    return ("PASS" if past >= e["min_past"] else "BLOCKED"), f"past plane {past:.2f} m"


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
