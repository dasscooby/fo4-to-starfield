"""The power armor probe's user log (FO4SFPAProbe.0.log, written by scripts/planet/FO4SF_PAProbeQuest.psc) read back
into one table and a verdict (docs/research/power-armor-probe.md).

Every line the script writes is "FO4SFPA rt=<real time s> <event> key=value ... end=true", anywhere in the line (the game
puts a time stamp in front). A line without end=true was cut and is left out (and counted). Form ids are Papyrus's
signed decimal ("none" for None); bools "true" / "false"; a reading the game could not give is "na" (the script's
optional readings: camera state, worn item count, IsInPowerArmor, furniture, sit state). Case is ignored, as in
src/fo4sf/planet/probe_log.py (Starfield prints a bool as "true", Fallout 4 as "True", and keeps one spelling per string).

Events: init (once per script instance), start (the script's start line: the form ids it found), state (a reading:
stage 10 / 20 / 30 and when = before, now, settled; stage 0 when=start), step (the call a stage makes), sit (the player's
furniture or sit state changed).

The control comes first. The probe stands next to a vanilla furniture that the player must sit on, and says nothing
about power armor otherwise: with no start line (the script never ran) or no reading of the player on that furniture
(the furniture reference the script found, or sit state 3 within CONTROL_M of it) the verdict is INCONCLUSIVE and the
steps are not judged. With the control read, each step is judged on the log alone, from its before reading to its
last one (settled, else now):
  stage 10  SwitchToPowerArmor   "no logged change" or "changed: <fields>" (race cam worn inpa furn pos); inpa=true
                                 reads "entered (IsInPowerArmor true)". The log cannot say what the screen shows: the
                                 session card's screenshots are the other half.
  stage 20  SetRace to the copy  "race set" when the last race is FO4SF_PARace, else "race unchanged" / "race
                                 became <id>"
  stage 30  SetRace back         "restored" when the last race is the one the player started with, else "not restored"
A step whose step line is missing reads "not run"; one with no state lines "no readings".
"""
import re

LINE = re.compile(r"FO4SFPA rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "start", "state", "step", "sit")
ID_KEYS = {"quest", "suitref", "controlref", "pa_race", "orig_race", "race", "cell", "furn"}
CONTROL_M = 1.5          # sat within this many game units of the control reference
SITTING = 3              # Actor.GetSitState: 3 = sitting (FO4 values: 0 not, 1 wants, 2 going, 3 sitting, 4/5 getting up)
FIELDS = ("race", "cam", "worn", "inpa", "furn", "pos")
ORDER = {"start": 0, "before": 1, "now": 2, "settled": 3}


def u32(v):
    return None if v is None else int(v) & 0xFFFFFFFF


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
    if key == "worn" and text == "-1":        # the script's value when Actor.GetWornItem is not available
        return "na"
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
    """([[parsed whole line]], cut) split at each init line that follows a step (a new script instance after a run that
    got as far as a step), an init with no version (an empty one) never splits; the game logs init and start twice at
    load (PC run of 11 Nov), so an init before any step stays in its run; lines before the first init form a run of their
    own. cut counts the lines that lack end=true (dropped)."""
    out, cur, cut = [], [], 0
    for line in lines:
        p = parse_line(line)
        if p is None:
            continue
        if not p["end"]:
            cut += 1
            continue
        if p["event"] == "init" and p.get("version") is not None and any(e["event"] == "step" for e in cur):
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out, cut


def hexid(v):
    return "none" if v is None else f"{v:08X}" if isinstance(v, int) else str(v)


def control_read(start, events):
    """(True, how) when the player was read on the control furniture, else (False, why)."""
    ctrl = start.get("controlref") if start else None
    if start is None:
        return False, "no start line: the script never ran"
    # controlref is none when the start line is logged at load, before the probe cell is loaded (a temporary reference
    # does not resolve then: PC run of 11 Nov); the furniture-id match is then impossible, the sit-state one still reads
    unreadable = True
    for e in events:
        if e["event"] not in ("sit", "state"):
            continue
        if e.get("furn") not in (None, "na"):
            unreadable = False
            if ctrl is not None and e["furn"] == ctrl:
                return True, f"furniture {hexid(ctrl)} at rt {e['rt']:g}"
        if e.get("sitstate") == SITTING and isinstance(e.get("distc"), (int, float)) and e["distc"] <= CONTROL_M:
            return True, f"sit state {SITTING} {e['distc']:g} from the control at rt {e['rt']:g}"
    if unreadable and not any(e.get("sitstate") not in (None, "na") for e in events):
        return False, "the game gave neither the player's furniture nor a sit state (both na): the control cannot be read"
    return False, "the player was never read sitting on the control furniture" + (
        " (controlref none in the start line: only a sit state 3 near it counts)" if ctrl is None else "")


def changes(a, b):
    """The FIELDS that differ between two state lines (position: moved more than 0.5 units)."""
    out = []
    for f in FIELDS:
        x, y = a.get(f), b.get(f)
        if f == "pos":
            if isinstance(x, tuple) and isinstance(y, tuple) and max(abs(i - j) for i, j in zip(x, y)) > 0.5:
                out.append(f)
        elif x != y and "na" not in (x, y):
            out.append(f)
    return out


def step_result(stage, step, states, start):
    """(result, changed fields) of one stage from its readings."""
    if step is None:
        return "not run", []
    before = states.get("before")
    last = states.get("settled") or states.get("now")
    if before is None or last is None:
        return "no readings", []
    ch = changes(before, last)
    if stage == 10:
        if last.get("inpa") is True and before.get("inpa") is not True:
            return "entered (IsInPowerArmor true)", ch
        return ("changed: " + " ".join(ch), ch) if ch else ("no logged change", ch)
    race, pa, orig = last.get("race"), step.get("race") if stage == 20 else None, start.get("orig_race") if start else None
    if stage == 20:
        if pa is not None and race == pa:
            return "race set", ch
        return ("race unchanged", ch) if race == before.get("race") else (f"race became {hexid(race)}", ch)
    orig = step.get("race", orig)
    return ("restored", ch) if orig is not None and race == orig else ("not restored", ch)


OURS = re.compile(r"FO4SF_PA|FO4SFPowerArmorProbe|FO4SFPAProbe", re.IGNORECASE)
REFUSAL = re.compile(r"SwitchToPowerArmor|power armor furniture", re.IGNORECASE)


def papyrus_errors(lines):
    """The error and warning lines of the game's own Papyrus log (Logs\\Script\\Papyrus.0.log) that name our forms, in
    order, without repeats, the game's time stamp cut. The probe's user log cannot see a refusal: the PC run of 11 Nov
    read "no logged change" while the game wrote "FO4SF_PAProbeSuitRef (09000804): is not valid power armor furniture."
    from Actor.SwitchToPowerArmor()."""
    out = []
    for line in lines:
        t = line.strip()
        m = re.search(r"\b(error|warning)\b", t, re.IGNORECASE)
        if not m or not OURS.search(t):
            continue
        t = t[m.start():]
        if t not in out:
            out.append(t)
    return out


def summarize(lines, run=-1, papyrus=None):
    """{"runs", "run", "cut", "init", "start", "control": (ok, why), "steps": {stage: {"call", "result", "changed",
    "states": {when: line}}}, "unavailable": [reading names logged na], "papyrus": [errors naming our forms],
    "problems", "verdict"} of one run (the latest). papyrus is the lines of the game's Papyrus log (or None, not read):
    a stage-10 refusal in it overrides the probe log's "no logged change"."""
    rs, cut = runs(lines)
    errs = papyrus_errors(papyrus) if papyrus is not None else []
    out = {"runs": len(rs), "cut": cut, "papyrus": errs, "papyrus_read": papyrus is not None, "init": None, "start": None, "control": (False, "no log"), "steps": {},
           "states": [], "unavailable": [], "problems": [], "verdict": "INCONCLUSIVE: no log lines"}
    if not rs:
        return out
    r = rs[run]
    out["run"] = run if run >= 0 else len(rs) + run
    out["init"] = next((e for e in r if e["event"] == "init"), None)
    start = next((e for e in reversed(r) if e["event"] == "start"), None)       # the last: the first is logged at load
    out["start"] = start
    states = [e for e in r if e["event"] == "state"]
    out["states"] = states
    ok, why = control_read(start, [e for e in r if e["event"] in ("sit", "state")])
    out["control"] = (ok, why)
    names = {"cam": "camera state", "worn": "worn item count", "inpa": "IsInPowerArmor", "furn": "player furniture",
             "sitstate": "sit state"}
    out["unavailable"] = [n for k, n in names.items() if states and all(s.get(k) == "na" for s in states)]
    for stage in (10, 20, 30):
        step = next((e for e in r if e["event"] == "step" and e.get("stage") == stage), None)
        by = {s["when"]: s for s in states if s.get("stage") == stage and isinstance(s.get("when"), str)}
        result, ch = step_result(stage, step, by, start)
        refusal = next((e for e in errs if REFUSAL.search(e)), None) if stage == 10 and step else None
        if refusal:                 # the call ran and the game refused it: not "no logged change"
            result = "refused by the game: " + refusal
        out["steps"][stage] = {"call": step.get("call") if step else None, "result": result, "changed": ch, "states": by,
                               "haskw": step.get("haskw") if step else None}
        if step and "settled" not in by and by:
            out["problems"].append(f"stage {stage}: no settled reading (the 4 s timer never ran); judged on the reading right after the call")
    if cut:
        out["problems"].append(f"{cut} line(s) without end=true were left out (cut)")
    if len(rs) > 1:
        out["problems"].append(f"{len(rs)} runs in the log; run {out['run']} is shown")
    if not ok:
        out["verdict"] = f"INCONCLUSIVE: control failed: {why}"
    else:
        s = out["steps"]
        out["verdict"] = (f"CONTROL OK ({why}). SwitchToPowerArmor: {s[10]['result']}; SetRace to the copy: {s[20]['result']}; "
                          f"SetRace back: {s[30]['result']}")
    return out


def table(summary):
    """Lines of one plain text table: a row per reading (stage, when), then each step's result."""
    states = summary.get("states", [])
    if not states:
        return ["no readings"]
    start = summary.get("start") or {}
    pa, orig = start.get("pa_race"), start.get("orig_race")

    def race(v):
        return "PA" if v is not None and v == pa else "orig" if v is not None and v == orig else hexid(v)

    def pos(v):
        return ",".join(f"{c:.1f}" for c in v) if isinstance(v, tuple) else str(v)

    def cell(v):
        return "na" if v == "na" else "none" if v is None else str(v).lower() if isinstance(v, bool) else str(v)
    rows = [["stage", "when", "race", "cam", "worn", "inpa", "furn", "sit", "pos"]]
    for s in sorted(states, key=lambda s: (s.get("stage", 0), ORDER.get(s.get("when"), 9), s["rt"])):
        rows.append([str(s.get("stage")), str(s.get("when")), race(s.get("race")), cell(s.get("cam")), cell(s.get("worn")),
                     cell(s.get("inpa")), hexid(s.get("furn")) if s.get("furn") not in ("na",) else "na",
                     cell(s.get("sitstate")), pos(s.get("pos"))])
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]


def quest_lines(summary):
    """The console lines for the three stages: the console refuses a plugin quest's name in setstage ("not found for
    parameter Quest", seen with the rads probe), so the quest's form id comes from the init line (FAL-212)."""
    q = (summary.get("init") or {}).get("quest")
    if not isinstance(q, int):
        return ["quest form id: not in the log (no init line with quest=)"]
    return [f"quest form id {q:08X}: setstage {q:08X} 10 / 20 / 30"]


def report(summary):
    """The whole printout: the table, each step, notes, the verdict (last line)."""
    lines = quest_lines(summary) + table(summary)
    judged = summary["control"][0]
    for stage, s in summary.get("steps", {}).items():
        shown = s["result"] if judged else f"not judged (control failed; the log shows: {s['result']})"
        lines.append(f"stage {stage} {s['call'] or '-'}: {shown}")
    if summary.get("unavailable"):
        lines.append("readings the game gave as na: " + ", ".join(summary["unavailable"]))
    kw = (summary["steps"].get(10) or {}).get("haskw")
    if kw is False:
        lines.append("suit reference HasKeyword(FurnitureTypePowerArmor) before the call: false: the game does not see the keyword "
                     "on the reference, the call will be refused (PC run of 11 Nov: the base FURN's KWDA list was not seen)")
    elif kw is True:
        lines.append("suit reference HasKeyword(FurnitureTypePowerArmor) before the call: true (a real entry: it can crash the game "
                     "on a null the kit does not yet supply: throwaway sessions only)")
    if summary.get("papyrus"):
        lines += ["game Papyrus log: " + e for e in summary["papyrus"]]
    elif not summary.get("papyrus_read"):
        lines.append("note: the game's Papyrus log was not read (--papyrus): a refusal by the game is not visible in the probe log")
    lines += ["note: " + p for p in summary.get("problems", [])]
    lines.append(summary["verdict"])
    return lines
