"""The rads probe's user log (FO4SFRadsProbe.0.log, written by scripts/planet/FO4SF_RadsProbeQuest.psc) read back into
one table and a verdict (docs/research/rads-probe.md).

Every line the script writes is "FO4SFRADS rt=<real time s> <event> key=value ... end=true", anywhere in the line (the
game puts a time stamp in front). A line without end=true was cut and is left out (and counted). Form ids are Papyrus's
signed decimal ("none" for None); bools "true" / "false"; a reading the game could not give is "na". Case is ignored.

Events: init (once per script instance), start (the forms the script was given), step (the stage's call and what it
expects), state (a reading: stage 10 / 20 / 30 / 40 and when = before, now, settled, routed, final; stage 0 when=start),
control, set (stage 10: a non-zero number written to our value, then 0; each with what was read back), fix (after the effect had 3 s: was the step's value there, or was it forced), route (the modifier on Health).

The control comes first: a vanilla actor value (Health) set and read in the same step, with the very call the route uses
(Actor.ModValue +10, read, -10, read; stage 10). When the call was not made, the first read did not move by +10, or the
second did not return, the verdict is INCONCLUSIVE and nothing else is judged; so is a log with no start line or no
control line. With the control read, three things are judged on the log alone:
  effect  stage 20 and 30: did the spell's effect raise our value to the step's number without help (fix forced=false)
  route   the maximum health of stage 10 (final) against stages 20, 30 and 40 (final): did it fall by a tenth of the rads
  RadAway stage 40: did the consumable lower our value to the step's number without help, and did the route give back
Maximum health is the "max" reading when the game declares one, else "health" (the current value, so a hit taken during
the session reads as a change: the report names the source and says it is not the maximum). The base is never used: the
route moves the current value and the base stays put (sixth session); the base readings are only listed in a note. The log cannot say what the screen shows.
Active effect ids are listed per stage; ids that were not there at stage 10 are named, as the way to see whether
Starfield's own radiation acts in our world (the log cannot say which id is radiation: the owner looks them up).
"""
import re

LINE = re.compile(r"FO4SFRADS rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "start", "step", "state", "control", "set", "fix", "route", "vcontrol", "item")
WRITE_TEST = 50.0         # the script's WriteTest: stage 10 writes this to our value and reads it
ID_KEYS = {"quest", "rads_av", "health_av", "spell", "radaway", "av"}
WHENS = ("start", "before", "now", "settled", "routed", "final")
ORDER = {w: i for i, w in enumerate(WHENS)}
STAGES = (10, 20, 30, 40, 50)
EXPECT = {10: 0.0, 20: 100.0, 30: 300.0, 40: 100.0}
PENALTY = 0.1            # the script's PenaltyPerRad
CONTROL_DELTA = 10.0
EPS = 0.01
HEALTH_EPS = 0.51        # maximum health compared to within half a point (the script rounds the penalty down to a whole)


def u32(v):
    return None if v is None else int(v) & 0xFFFFFFFF


def value(key, text):
    low = text.lower()
    if key == "fx":
        return low if low in ("none", "na") else [u32(int(x)) if re.fullmatch(r"-?\d+", x) else x for x in text.split(",") if x]
    if low == "none":
        return None
    if low == "na":
        return "na"
    if low in ("true", "false"):
        return low == "true"
    if key in ID_KEYS:
        try:
            return u32(int(text))
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
    out = {"rt": rt, "event": m.group("event").lower()}
    for k, v in TOKEN.findall(m.group("rest")):
        k = k.lower()
        out[k] = value(k, v)
    out["end"] = out.get("end") is True
    return out


def runs(lines):
    """([[parsed whole line]], cut) split at each init line (each a new script instance), an init with no version (an
    empty one) never splits; lines before the first init form a run of their own. cut counts the lines without end=true."""
    out, cur, cut = [], [], 0
    for line in lines:
        p = parse_line(line)
        if p is None:
            continue
        if not p["end"]:
            cut += 1
            continue
        if p["event"] == "init" and cur and p.get("version") is not None:
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out, cut


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt(v):
    if v is None:
        return "none"
    if v == "na":
        return "na"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def control_check(ctl):
    """(True, how) when the vanilla Health actor value moved by +10 and came back, else (False, why)."""
    if ctl is None:
        return False, "no control line: stage 10 never ran (the vanilla Health value was not set and read)"
    if ctl.get("called") is not True:
        return False, "the control's call (Actor.ModValue on Health) was not made: the game declares none, or the script was cut"
    b, a, r = ctl.get("before"), ctl.get("after"), ctl.get("restored")
    if not (num(b) and num(a) and num(r)):
        return False, f"the control's readings are not numbers (before {fmt(b)}, after {fmt(a)}, restored {fmt(r)})"
    d = ctl.get("delta", CONTROL_DELTA)
    if not num(d):
        d = CONTROL_DELTA
    if abs((a - b) - d) > EPS:
        return False, f"vanilla Health read {fmt(b)} then {fmt(a)} after ModValue +{fmt(d)}: it did not move by {fmt(d)}"
    if abs(r - b) > EPS:
        return False, f"vanilla Health read {fmt(b)} before and {fmt(r)} after the control undid itself: it did not come back"
    return True, f"vanilla Health {fmt(b)} to {fmt(a)} with ModValue +{fmt(d)} and back to {fmt(r)}"


def max_health(s):
    """(value, source) of one state line: max, else health (the current value), else (None, None). The base is not used:
    the route moves the current value (sixth session: base stayed 200 while health read 195, 175, 165) and the report says so."""
    for k in ("max", "health"):
        if num(s.get(k)):
            return s[k], k
    return None, None


def by_stage(states):
    """{stage: {when: state line}} (the last of each)."""
    out = {}
    for s in states:
        if num(s.get("stage")) and isinstance(s.get("when"), str):
            out.setdefault(int(s["stage"]), {})[s["when"]] = s
    return out


def judge(events):
    """(effect results, route results, RadAway result), each a list/str of plain sentences; only called with the control read."""
    states = by_stage([e for e in events if e["event"] == "state"])
    fixes = {int(e["stage"]): e for e in events if e["event"] == "fix" and num(e.get("stage"))}
    routes = [e for e in events if e["event"] == "route"]
    eff, rad, route = {}, "not run", {}
    for stage in (20, 30, 40):
        st, fx = states.get(stage, {}), fixes.get(stage)
        if fx is None or "before" not in st or "settled" not in st:
            res = "not run" if not st and fx is None else "no readings"
        else:
            b, have, want = st["before"].get("rads"), fx.get("had"), EXPECT[stage]
            if not (num(b) and num(have)):
                res = "no readings"
            elif abs(have - want) <= EPS:
                res = f"gave {fmt(have)} without help ({fmt(b)} to {fmt(have)})"
            elif abs(have - b) <= EPS:
                res = f"did not move the value (still {fmt(have)}, expected {fmt(want)}); the script forced it"
            else:
                res = f"moved it to {fmt(have)}, not {fmt(want)}; the script forced it"
        if stage == 40:
            rad = res
        else:
            eff[stage] = res
    items = {e.get("when"): e.get("count") for e in events if e["event"] == "item" and e.get("stage") == 40}
    if rad not in ("not run", "no readings") and num(items.get("added")) and num(items.get("settled")):
        a, z = items["added"], items["settled"]
        rad += (f"; item count {fmt(a)} to {fmt(z)}: consumed" if z < a else f"; item count {fmt(a)} to {fmt(z)}: NOT consumed")
    # the route: maximum health at the end of each stage against stage 10's
    base_s = states.get(10, {}).get("final") or states.get(10, {}).get("routed")
    base, src = max_health(base_s) if base_s else (None, None)
    for stage in (20, 30, 40):
        last = states.get(stage, {}).get("final") or states.get(stage, {}).get("routed")
        if base is None or last is None:
            route[stage] = "no readings"
            continue
        v, vsrc = max_health(last)
        rads = last.get("rads")
        if v is None or vsrc != src or not num(rads):
            route[stage] = "no readings"
            continue
        want = -int(rads * PENALTY)
        got = v - base
        if abs(got - want) <= HEALTH_EPS:
            route[stage] = f"{src} {fmt(base)} to {fmt(v)} ({got:+g}, expected {want:+g} at {fmt(rads)} rads)"
        elif abs(got) <= HEALTH_EPS and want != 0:
            route[stage] = f"{src} unchanged at {fmt(v)} (expected {want:+g} at {fmt(rads)} rads)"
        else:
            route[stage] = f"{src} {fmt(base)} to {fmt(v)} ({got:+g}, expected {want:+g} at {fmt(rads)} rads)"
    bad = [r for r in routes if r.get("ok") is False]
    return eff, route, rad, src, bad


def extra_effects(by):
    """{stage: [effect ids]} that were active at some reading of the stage and were not at stage 10's final reading."""
    ref = by.get(10, {}).get("final") or by.get(10, {}).get("before") or {}
    fx0 = ref.get("fx")
    base = set(fx0) if isinstance(fx0, list) else set()
    out = {}
    for stage in (20, 30, 40):
        seen = []
        for s in by.get(stage, {}).values():
            if isinstance(s.get("fx"), list):
                seen += [i for i in s["fx"] if i not in base and i not in seen]
        if seen:
            out[stage] = seen
    return out


def setvalue_check(events):
    """Did our own actor value take a number that is not zero (stage 10)? A sentence."""
    sets = [e for e in events if e["event"] == "set"]
    if not sets:
        return "not run (no set line)"
    nz = [e for e in sets if num(e.get("wrote")) and e["wrote"] != 0]
    if not nz:
        return "not run (no non-zero write)"
    e = nz[0]
    if not num(e.get("read")):
        return f"no reading (wrote {fmt(e.get('wrote'))}, read {fmt(e.get('read'))})"
    if abs(e["read"] - e["wrote"]) <= EPS:
        back = next((x for x in sets if num(x.get("wrote")) and x["wrote"] == 0 and num(x.get("read"))), None)
        tail = "" if back is None else f"; set back to 0 reads {fmt(back['read'])}"
        return f"yes (wrote {fmt(e['wrote'])}, read {fmt(e['read'])}{tail})"
    return f"NO (wrote {fmt(e['wrote'])}, read {fmt(e['read'])})"


def vcontrol_check(events):
    """The second control (stage 50, only when the kit was built with --control-spell): did a vanilla spell move Health
    when cast from the quest script? A sentence; "not run" when stage 50 was not set."""
    v = next((e for e in events if e["event"] == "vcontrol"), None)
    if v is None:
        return "not run (stage 50 not set)"
    if v.get("cast") is not True:
        return "not run (the kit was built without --control-spell)"
    b, a = v.get("before"), v.get("after")
    if not (num(b) and num(a)):
        return f"no reading (before {fmt(b)}, after {fmt(a)})"
    if abs(a - b) <= EPS:
        return f"Health did not move (cast of {hexid(v.get('spell'))}: {fmt(b)} to {fmt(a)}): Cast from a quest script may apply no value modifier at all"
    return f"Health moved {fmt(b)} to {fmt(a)} ({a - b:+g}) with the vanilla spell {hexid(v.get('spell'))}: Cast works, so a value that stays put is our effect's fault"


def hexid(v):
    return "none" if v is None else f"{v:08X}" if isinstance(v, int) else str(v)


def summarize(lines, run=-1):
    """{"runs", "run", "cut", "init", "start", "control": (ok, why), "effect": {stage: text}, "route": {stage: text},
    "radaway": text, "maxsource", "states", "extra_effects", "problems", "verdict"} of one run (the latest)."""
    rs, cut = runs(lines)
    out = {"runs": len(rs), "cut": cut, "init": None, "start": None, "control": (False, "no log"), "effect": {}, "route": {},
           "radaway": "not run", "setvalue": "not run", "vanilla_control": "not run", "maxsource": None, "states": [], "extra_effects": {}, "problems": [],
           "verdict": "INCONCLUSIVE: no log lines"}
    if not rs:
        return out
    r = rs[run]
    out["run"] = run if run >= 0 else len(rs) + run
    out["init"] = next((e for e in r if e["event"] == "init"), None)
    start = next((e for e in r if e["event"] == "start"), None)
    out["start"] = start
    states = [e for e in r if e["event"] == "state"]
    out["states"] = states
    ctl = next((e for e in r if e["event"] == "control"), None)
    if start is None:
        ok, why = False, "no start line: the script never ran"
    else:
        ok, why = control_check(ctl)
    out["control"] = (ok, why)
    if cut:
        out["problems"].append(f"{cut} line(s) without end=true were left out (cut)")
    if len(rs) > 1:
        out["problems"].append(f"{len(rs)} runs in the log; run {out['run']} is shown")
    if not ok:
        out["verdict"] = f"INCONCLUSIVE: control failed: {why}"
        return out
    eff, route, rad, src, bad = judge(r)
    out.update(effect=eff, route=route, radaway=rad, maxsource=src, setvalue=setvalue_check(r), vanilla_control=vcontrol_check(r))
    by = by_stage(states)
    out["extra_effects"] = extra_effects(by)
    if all(isinstance(s.get("fx"), str) and s.get("fx") == "na" for s in states if "fx" in s) and states:
        out["problems"].append("the game gave no list of active effects (fx na): Starfield's own radiation cannot be seen")
    if src == "health":
        bases = sorted({s["base"] for s in states if num(s.get("base"))})
        out["problems"].append("no maximum reading for Health (GetValueMax is not declared): the route is judged on current Health, not the maximum"
                               + (f"; base read {', '.join(fmt(b) for b in bases)} throughout" if bases else ""))
    if any(num(x.get("rads")) and x["rads"] < 0 for x in states):
        out["problems"].append("our value read below zero (the AVIF minimum is not enforced for an effect's change): an effect applied more than once per cast")
    if any(e.get("clamped") is True for e in r if e["event"] == "route"):
        out["problems"].append("the script clamped our value at 0 before routing it (a route line has clamped=true)")
    for e in bad:
        out["problems"].append(f"the route's ModValue was not called at rads {fmt(e.get('rads'))} (delta {fmt(e.get('delta'))})")
    out["verdict"] = (f"CONTROL OK ({why}). Own value takes a number: {out['setvalue']}; effect +100: {eff.get(20)}; effect +200: {eff.get(30)}; "
                      f"route at 100 rads: {route.get(20)}; at 300 rads: {route.get(30)}; RadAway: {rad}; "
                      f"route after RadAway: {route.get(40)}")
    return out


def table(summary):
    """Lines of one plain text table: a row per reading (stage, when)."""
    states = summary.get("states", [])
    if not states:
        return ["no readings"]
    rows = [["stage", "when", "rads", "health", "base", "max", "applied", "effects"]]
    for s in sorted(states, key=lambda s: (s.get("stage", 0), ORDER.get(s.get("when"), 9), s["rt"])):
        fx = s.get("fx")
        fxt = fx if isinstance(fx, str) or fx is None else (",".join(f"{i:08X}" if isinstance(i, int) else str(i) for i in fx) or "none")
        rows.append([fmt(s.get("stage")), fmt(s.get("when")), fmt(s.get("rads")), fmt(s.get("health")), fmt(s.get("base")),
                     fmt(s.get("max")), fmt(s.get("applied")), fmt(fxt)])
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]


def report(summary):
    """The whole printout: the table, the control, each judgement, notes, the verdict (last line)."""
    lines = table(summary)
    lines.append("control: " + ("ok: " if summary["control"][0] else "FAILED: ") + summary["control"][1])
    if summary["control"][0]:
        for stage, t in summary["effect"].items():
            lines.append(f"stage {stage} effect: {t}")
        for stage in (20, 30, 40):
            if stage in summary["route"]:
                lines.append(f"stage {stage} route (maximum health, source {summary['maxsource']}): {summary['route'][stage]}")
        lines.append(f"stage 10 own value takes a number: {summary['setvalue']}")
        lines.append(f"stage 40 RadAway: {summary['radaway']}")
        lines.append(f"stage 50 vanilla control: {summary['vanilla_control']}")
        for stage, ids in summary["extra_effects"].items():
            lines.append(f"stage {stage} active effects not there at stage 10: " + ", ".join(f"{i:08X}" if isinstance(i, int) else str(i) for i in ids))
    lines += ["note: " + p for p in summary.get("problems", [])]
    lines.append(summary["verdict"])
    return lines
