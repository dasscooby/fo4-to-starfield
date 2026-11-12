"""The animation probe's user log (FO4SFAnim.0.log, written by scripts/newgame/FO4SF_AnimProbeQuest.psc) read back into one
table and a verdict (docs/research/anim-probe.md, variant A, the vanilla control).

Every line the script writes is "FO4SFANIM rt=<real time s> <event> key=value ... end=true", anywhere in the line (the game puts a
time stamp in front). A line without end=true was cut and is left out (and counted). Form ids are Papyrus's signed decimal
("none" for None); bools "true" / "false"; "void" when the game's register call returns nothing. Case is ignored.

Events: init (the forms it found), spawn (PlaceAtMe: ref), read (a reading of the reference: stage, when, loaded, disabled, cell,
pos, dist), register (RegisterForAnimationEvent for one name: ok), play (one PlayAnimation name: ok = its return), event (an
animation event that arrived: name, stage = the stage active when it came, since = seconds since the previous event), quiet
(15 s without an event after a stage's call), listened (events did arrive in the window), step (Activate by script), cleanup.

The log cannot say whether the object moved: that is the screenshot before and after a stage. It says what the calls returned and
which events arrived after each name. Verdict (exit 0 when the activator was spawned, 1 when the session is inconclusive):
  EVENTS ARRIVE   a PlayAnimation returned true and at least one animation event arrived (the path works in our setup)
  PLAY, NO EVENTS a PlayAnimation returned true but no event arrived at all (the graph sends none Papyrus can hear, or the
                  registration did not take: see the register lines)
  NO PLAY         the activator was spawned but every PlayAnimation returned false or was not reached
  INCONCLUSIVE    no spawn line with a reference (the script did not run, the plugin was not loaded, or stage 10 was not set)
"""
import re

LINE = re.compile(r"FO4SFANIM rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "spawn", "read", "register", "play", "event", "quiet", "listened", "step", "cleanup")
NAME_KEYS = ("name", "call", "what", "when")       # words, kept as the game printed them apart from case where a reader compares


def value(key, text):
    low = text.lower()
    if low == "none":
        return None
    if low == "void":
        return "void"
    if low in ("true", "false"):
        return low == "true"
    if key in NAME_KEYS:
        return text
    if key == "pos":
        try:
            xyz = tuple(float(v) for v in text.split(","))
            return xyz if len(xyz) == 3 else text
        except ValueError:
            return text
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
        else:
            d[k] = value(k, v)
    return d


def summarize(lines):
    """{"events", "cut", "spawned": ref or None, "registers": [..], "plays": {stage: {...}}, "arrived": [event lines],
    "verdict": (code, text)}"""
    events, cut = [], 0
    for ln in lines:
        d = parse_line(ln)
        if d is None:
            continue
        if not d["end"]:
            cut += 1
            continue
        events.append(d)
    spawned = next((e.get("ref") for e in events if e["event"] == "spawn" and e.get("ref") is not None), None)
    registers = [e for e in events if e["event"] == "register" and "name" in e]
    arrived = [e for e in events if e["event"] == "event"]
    plays = {}
    for e in events:
        if e["event"] == "play":
            plays[e.get("stage")] = {"name": e.get("name"), "ok": e.get("ok"), "events": [], "quiet": False}
        elif e["event"] == "step" and e.get("call") == "Activate":
            plays[e.get("stage")] = {"name": "Activate(player)", "ok": None, "events": [], "quiet": False}
    for e in arrived:
        if e.get("stage") in plays:
            plays[e["stage"]]["events"].append(e)
    for e in events:
        if e["event"] == "quiet" and e.get("stage") in plays:
            plays[e["stage"]]["quiet"] = True
    played = [p for p in plays.values() if p["ok"] is True]
    if spawned is None:
        verdict = ("INCONCLUSIVE", "no spawn line with a reference (the script did not run, the plugin was not loaded, the vanilla "
                                   "activator was not found, or stage 10 was not set)")
    elif played and arrived:
        verdict = ("EVENTS ARRIVE", f"PlayAnimation returned true for {len(played)} name(s) and {len(arrived)} animation event(s) "
                                    f"arrived ({', '.join(sorted({str(e.get('name')) for e in arrived}))})")
    elif played:
        regs = [r for r in registers if r.get("ok") is True]
        verdict = ("PLAY, NO EVENTS", f"PlayAnimation returned true for {len(played)} name(s) but no animation event arrived; "
                                      f"{len(regs)} of {len(registers)} register call(s) returned true")
    else:
        verdict = ("NO PLAY", "the activator was spawned, but no PlayAnimation returned true (all false, or the play stages were not set)")
    return {"events": events, "cut": cut, "spawned": spawned, "registers": registers, "plays": plays, "arrived": arrived, "verdict": verdict}


def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return "none" if v is None else str(v)


def report(s):
    out = []
    for e in s["events"]:
        if e["event"] == "init":
            out.append("init: " + " ".join(f"{k}={fmt(v)}" for k, v in e.items() if k not in ("rt", "event", "end")))
    out.append("spawned: " + (fmt(s["spawned"]) if s["spawned"] is not None else "nothing"))
    regs = s["registers"]
    if regs:
        counts = {}
        for r in regs:
            counts[fmt(r.get("ok"))] = counts.get(fmt(r.get("ok")), 0) + 1
        bad = [str(r.get("name")) for r in regs if r.get("ok") is not True]
        out.append(f"register calls: {len(regs)} (" + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + ")"
                   + (f"; not true: {', '.join(sorted(set(bad)))}" if bad else ""))
    out.append("stage  name              return  events after it")
    for stage, p in sorted(s["plays"].items(), key=lambda kv: kv[0] if isinstance(kv[0], int) else 0):
        evs = ", ".join(f"{e.get('name')}@{e.get('since')}s" for e in p["events"])
        out.append(f"{fmt(stage):<6} {fmt(p['name']):<17} {fmt(p['ok']):<7} " + (evs if evs else ("none (quiet 15 s)" if p["quiet"] else "none")))
    stray = [e for e in s["arrived"] if e.get("stage") not in s["plays"]]
    if stray:
        out.append("events outside a play stage: " + ", ".join(f"{e.get('name')} (stage {fmt(e.get('stage'))})" for e in stray))
    if s["cut"]:
        out.append(f"{s['cut']} line(s) without end=true were cut and left out")
    out.append(f"{s['verdict'][0]}: {s['verdict'][1]}. Whether the object moved is the screenshot before and after, not the log.")
    return out
