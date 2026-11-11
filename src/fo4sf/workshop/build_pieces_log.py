"""The build pieces kit's user log (FO4SFBP.0.log, written by scripts/planet/FO4SF_BPQuest.psc) read back into a verdict
(docs/research/build-pieces.md).

Every line is "FO4SFBP rt=<real time s> <event> key=value ... end=true", anywhere in the line (the game puts a time stamp in
front). A line without end=true was cut and is left out (and counted). Form ids are Papyrus's signed decimal ("none" for
None). Case is ignored.

Events: init (installed, core, quest), piece (when = init / ready, n, shell, recipe, coreid, core), found (when, pieces, named).

The log cannot say what the build menu shows: whether the pieces are listed, in which tab, with which cost, is the card's
screenshot. It says what the game FOUND: for each piece the stager named, the shell and the recipe of the plugin (the plugin
loaded and the records exist) and the core static the shell's model was taken from. Verdicts:
  ok            every named piece has its shell and its recipe (exit 0)
  PARTIAL       some do, some do not
  NONE FOUND    none does: the plugin is not loaded, or not this one
  NO PIECES     the script names no piece (the stager did not put the core ids in)
  INCONCLUSIVE  no "ready" reading in the log
"""
import re

LINE = re.compile(r"FO4SFBP rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "piece", "found")


def value(text):
    low = text.lower()
    if low == "none":
        return None
    if low in ("true", "false"):
        return low == "true"
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def parse_line(line):
    """{"rt", "event", key: value ..., "end": bool} of one kit line, None for any other line."""
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
            d[k] = value(v)
    return d


def summarize(lines):
    """{"init": {...} | None, "pieces": {when: {n: {...}}}, "found": {when: {...}}, "cut": int, "verdict": str, "ok": bool}."""
    init, pieces, found, cut = None, {}, {}, 0
    for line in lines:
        d = parse_line(line)
        if d is None:
            continue
        if not d["end"]:
            cut += 1
            continue
        if d["event"] == "init":
            init = d
        elif d["event"] == "piece":
            pieces.setdefault(str(d.get("when", "")).lower(), {})[d.get("n")] = d
        elif d["event"] == "found":
            found[str(d.get("when", "")).lower()] = d
    ready = found.get("ready")
    if ready is None:
        verdict = "INCONCLUSIVE: no ready reading (the game was closed before 20 s, or the quest never started)"
    elif not ready.get("named"):
        verdict = "NO PIECES: the script names no core static (stage with make_build_pieces.py stage, which puts the ids in)"
    elif ready.get("pieces") == ready.get("named"):
        verdict = f"ok: all {ready['named']} pieces have their shell and recipe"
    elif not ready.get("pieces"):
        verdict = "NONE FOUND: no shell or recipe of the plugin was found (is FO4SFBuildPieces.esm in the load order?)"
    else:
        verdict = f"PARTIAL: {ready['pieces']} of {ready['named']} pieces found"
    return {"init": init, "pieces": pieces, "found": found, "cut": cut, "verdict": verdict, "ok": verdict.startswith("ok")}


def report(s):
    out = []
    i = s["init"]
    if i:
        out.append(f"init: plugin installed={i.get('installed')}, core={i.get('core')}, quest={i.get('quest')}")
    for when in ("init", "ready"):
        for n in sorted(k for k in s["pieces"].get(when, {}) if isinstance(k, int)):
            p = s["pieces"][when][n]
            fmt = lambda v: "none" if v is None else v  # noqa: E731
            out.append(f"  {when:5} piece {n}: shell {fmt(p.get('shell'))}  recipe {fmt(p.get('recipe'))}  core static {fmt(p.get('coreid'))} -> {fmt(p.get('core'))}")
    if s["cut"]:
        out.append(f"{s['cut']} line(s) cut (no end=true) left out")
    out.append("The menu is the card's screenshot: is each piece listed (which tab), what does it cost, does it place?")
    out.append(s["verdict"])
    return out
