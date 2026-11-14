"""The workshop probe's user log (FO4SFWorkshop.0.log, written by scripts/planet/FO4SF_WSProbeQuest.psc) read back into one
table and a verdict (docs/research/workshop-probe.md).

Every line the script writes is "FO4SFWS rt=<real time s> <event> key=value ... end=true", anywhere in the line (the game
puts a time stamp in front). A line without end=true was cut and is left out (and counted). Form ids are Papyrus's signed
decimal ("none" for None); bools "true" / "false"; a reading the game has no call for is "na". Case is ignored.

Events: init (once per script instance: the forms it found), spawn (PlaceAtMe: stage, what = bench / pad / beacon, ref),
read (a reading of one reference: stage, when = before / after / now / settled / arrival / arrival+2s / arrival+10s /
stage50, what, loaded, haskw, disabled, ws, cell, pos, dist), step (a call made: stage, call, name; name=na when the game
has no such call), cell (the player's cell changed), cleanup.

The log cannot say what the screen shows: whether E gives WORKSHOP / BUILD [E] is the session card's screenshot. It says
which readings the script could take and which call changed any of them (loaded, haskw, ws, disabled), per stage, and
what the bench read on return to its cell. The verdict is ok (exit 0) when the bench and the control pad were both
placed (spawn lines with a reference), else INCONCLUSIVE.
"""
import re

LINE = re.compile(r"FO4SFWS rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "spawn", "read", "step", "cell", "cleanup")
FIELDS = ("loaded", "haskw", "ws", "disabled")
ORDER = {"before": 1, "now": 2, "after": 2, "settled": 3}


def value(key, text):
    low = text.lower()
    if low == "none":
        return None
    if low == "na":
        return "na"
    if low in ("true", "false"):
        return low == "true"
    if key == "pos":
        try:
            xyz = tuple(float(v) for v in text.split(","))
            return xyz if len(xyz) == 3 else text
        except ValueError:
            return text
    if key in ("rt",):
        return float(text)
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def parse_line(line):
    """{"rt", "event", key: value ..., "end": bool} of one probe line, None for any other line."""
    m = LINE.search(line)
    if not m or m.group("event").lower() not in EVENTS:
        return None
    try:
        rt = float(m.group("rt"))
    except ValueError:
        return None
    d = {"rt": rt, "event": m.group("event").lower(), "end": False}
    for k, v in TOKEN.findall(m.group("rest")):
        k = k.lower()
        if k == "end":
            d["end"] = v.lower() == "true"
        elif k == "text":
            d[k] = v
        elif k in ("what", "when"):
            d[k] = v.lower()                 # the game may print the word in another case (PC 11 Nov: what=Bench)
        else:
            d[k] = value(k, v)
    return d


def summarize(lines):
    """{"events": [...], "cut": n, "spawned": {what: ref or None}, "stages": {(stage, what): {...}}, "returns": [...],
    "control": (bool, text)}"""
    events, cut = [], 0
    for ln in lines:
        d = parse_line(ln)
        if d is None:
            continue
        if not d["end"]:
            cut += 1
            continue
        events.append(d)
    spawned, steps, reads, returns = {}, {}, {}, []
    for e in events:
        ev = e["event"]
        if ev == "spawn":
            spawned[e.get("what")] = e.get("ref")
        elif ev == "step" and "call" in e:
            steps[(e["stage"], e.get("what"))] = e.get("name")
        elif ev == "read":
            when = str(e.get("when"))
            if when.startswith("arrival") or when == "stage50":
                returns.append(e)
            else:
                reads.setdefault((e.get("stage"), e.get("what")), []).append(e)
    stages = {}
    for key in sorted(set(reads) | set(steps), key=lambda k: (k[0], str(k[1]))):
        rs = sorted(reads.get(key, []), key=lambda r: ORDER.get(str(r.get("when")), 0))
        first = next((r for r in rs if r.get("when") in ("before",)), rs[0] if rs else None)
        last = rs[-1] if rs else None
        changed = []
        if first and last and first is not last and first.get("ref") is not None:
            changed = [f for f in FIELDS if first.get(f) != last.get(f)]
        stages[key] = {"call": steps.get(key), "readings": len(rs), "changed": changed, "first": first, "last": last}
    # the bench is any of the bench spawns (stage 10 bench, 12 bench_temp, 13 bench_still); the pad is a control the PC
    # dropped (no model, no prompt to photograph), so its absence is said but does not make the session inconclusive
    benches = {k: v for k, v in spawned.items() if str(k).startswith("bench") and v is not None}
    placed = bool(benches)
    pad = spawned.get("pad") is not None
    control = (placed, ("bench placed (" + ", ".join(sorted(benches)) + ")" + ("; control pad placed" if pad else "; no pad placed") if placed else
               "no placed bench in the log (the script did not run, the core's workshop base was not found, or stages 10, 12 and 13 were not set)"))
    return {"events": events, "cut": cut, "spawned": spawned, "stages": stages, "returns": returns, "control": control}


def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return "none" if v is None else str(v)


def report(s):
    out = []
    for e in s["events"]:
        if e["event"] == "init":
            out.append("init: " + " ".join(f"{k}={fmt(v)}" for k, v in e.items() if k not in ("rt", "event", "end")))
    out.append("spawned: " + (", ".join(f"{k}={fmt(v)}" for k, v in s["spawned"].items()) or "nothing"))
    out.append("stage  what    call            readings  changed")
    for (stage, what), st in s["stages"].items():
        call = st["call"]
        callt = "-" if call is None else ("not in this game" if call == "na" else str(call))
        ch = "no readings" if not st["readings"] else "no logged change" if not st["changed"] else "changed: " + ", ".join(
            f"{f} {fmt(st['first'].get(f))}->{fmt(st['last'].get(f))}" for f in st["changed"])
        out.append(f"{stage:<6} {fmt(what):<7} {callt:<15} {st['readings']:<9} {ch}")
    if s["returns"]:
        out.append("readings after a cell change / stage 50:")
        for r in s["returns"]:
            out.append(f"  {r.get('when')} {r.get('what')}: loaded={fmt(r.get('loaded'))} haskw={fmt(r.get('haskw'))} ws={fmt(r.get('ws'))} "
                       f"cell={fmt(r.get('cell'))} dist={fmt(r.get('dist'))}")
    if s["cut"]:
        out.append(f"{s['cut']} line(s) without end=true were cut and left out")
    out.append(("ok: " if s["control"][0] else "INCONCLUSIVE: ") + s["control"][1] +
               ". The prompt on the object (E) is the screenshot, not the log.")
    return out


# ---------------------------------------------------------------- the by-hand log (FO4SFWSHand.0.log)

HAND = re.compile(r"FO4SFWSHAND rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*?)\s*end=true\s*$", re.IGNORECASE)
HAND_EVENTS = ("init", "say", "placed", "placed_beacon", "resources")


def parse_hand_line(line):
    """{"rt", "event", key: value ...} of one by-hand line, None for any other or a cut line (no end=true). A say line's text
    runs to end=true (it holds spaces)."""
    m = HAND.search(line)
    if not m or m.group("event").lower() not in HAND_EVENTS:
        return None
    d = {"rt": float(m.group("rt")), "event": m.group("event").lower()}
    rest = m.group("rest").strip()
    if d["event"] == "say":
        d["text"] = rest[5:] if rest.lower().startswith("text=") else rest
        return d
    for k, v in TOKEN.findall(rest):
        d[k.lower()] = value(k.lower(), v)
    return d


def summarize_hand(lines):
    """{"events", "cut", "benches": [placed lines], "beacons": [...], "resources": [...], "gave_kits": bool, "ok": (bool, text)}"""
    events, cut = [], 0
    for ln in lines:
        d = parse_hand_line(ln)
        if d is not None:
            events.append(d)
        elif re.search(r"FO4SFWSHAND", ln, re.IGNORECASE):
            cut += 1
    benches = [e for e in events if e["event"] == "placed"]
    beacons = [e for e in events if e["event"] == "placed_beacon"]
    res = [e for e in events if e["event"] == "resources"]
    gave = any(e["event"] == "say" and "you have" in e.get("text", "").lower() for e in events)
    what = [f"{len(benches)} bench(es)" if benches else None, f"{len(beacons)} beacon(s)" if beacons else None,
            f"resources given {len(res)} time(s)" if res else None]
    placed = [w for w in what if w]
    ok = (bool(placed), ", ".join(placed) if placed else
          ("kits were given but none was dropped" if gave else "no kit was given and nothing was dropped (the quest did not run, or the plugin was not loaded)"))
    return {"events": events, "cut": cut, "benches": benches, "beacons": beacons, "resources": res, "gave_kits": gave, "ok": ok}


def report_hand(s):
    out = []
    for e in s["events"]:
        if e["event"] == "say":
            out.append(f"{e['rt']:>8.1f}  say  {e.get('text', '')}")
        elif e["event"] in ("placed", "placed_beacon"):
            out.append(f"{e['rt']:>8.1f}  {e['event']} n={e.get('n')} ref={fmt(e.get('ref'))} moved={fmt(e.get('moved'))} loaded={fmt(e.get('loaded'))}" +
                       (f" haskw={fmt(e.get('haskw'))}" if "haskw" in e else ""))
        elif e["event"] == "resources":
            out.append(f"{e['rt']:>8.1f}  resources n={e.get('n')} have_iron={fmt(e.get('have_iron'))} have_aluminum={fmt(e.get('have_aluminum'))}")
    if s["cut"]:
        out.append(f"{s['cut']} line(s) without end=true were cut and left out")
    out.append(("ok: " if s["ok"][0] else "INCONCLUSIVE: ") + s["ok"][1] + ". The prompt on the object (E) is the screenshot, not the log.")
    return out
