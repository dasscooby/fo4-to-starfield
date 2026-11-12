"""The planet probe's user log (FO4SFPlanetProbe.0.log, written by scripts/planet/FO4SF_PlanetProbeQuest.psc) read
back into arrivals, readings and a verdict per test reference (docs/planet/planet-probe.md section 5).

Every line the script writes holds "FO4SFPP rt=<real time s> <event> key=value ...", anywhere in the line (the game
puts a time stamp in front). Values: form ids as Papyrus prints them (signed decimal, so a load index of 0x80 or more
and the runtime FF ids are negative), floats, bools, "none" for a None form, and lists of form ids joined by commas
("none" for an empty list). Events: init (once per new script instance: the quest's own id gives the probe plugin's
load index), chain (the location chain as the game resolves it), arrive, then player / planet / ref / location
lines at 2, 10, 30 and 60 s after each arrival.

The chain line (chain_reading) gives every link of our location chain more than one reading, because two things it
leans on are untested: which way IsChild reads, and GetParentLocations with no keyword. Starfield's Location.psc says
IsChild "Returns whether the other location is a child of this one" (ContentResources.zip, read 29 Oct), and
ObjectReference.IsInLocation calls it so (the parent asks), but some vanilla quest scripts call it the other way (the
child asks: MQ204_NA_StateChangeHandlerScript, UC04_QuestScript), so version 2 of the script asks it both ways
(<caller>_ischild_<argument>). It also lists the parents the game gives each of our three locations
(probe_parents, surface_parents, planet_parents: GetParentLocations with no keyword, a form no vanilla script uses),
and asks the way SQ_ParentScript finds a planet location's star system and a site's planet and star system
(planet_systems, probe_orbitals, probe_systems: with LocTypeStarSystem or LocTypeMajorOrbital). The reader looks
for each location's own parent in our records in that location's own lists, so the answer does not depend on how far
a list goes. A link is broken (a problem) only when every reading of it says so; readings that disagree are a note.
The lookups from the probe location (reach) and the way IsChild answered are notes too. Version 2 ends the line with
end=true; a line without it was cut, so its last value (perhaps a list cut short) is left out. Version 1 (probe run 1,
29 Oct) asked IsChild one way only, the child about its parent (probe_child_of_surface, surface_child_of_planet):
those two values settle nothing until a version 2 log shows which way IsChild reads, and the reader says so instead
of judging them.

Case: Starfield's Papyrus prints a bool as "true" / "false" (verified: the bridge log of 14 Oct and the new game log
of 28 Oct, docs/ai/test-queue.md and docs/newgame/vault111-start.md), Fallout 4's as "True" / "False". It also keeps
one spelling per string, so literal text can come back in another case (the 28 Oct log printed "FO4Port.esm" as
"fo4port.esm"). So the reader ignores case: in the prefix, the events, the keys, the bools, "none" and the tags
(read as upper case: T1 .. T7, MERGE, LC172COC).

The verdict a reference gets at an arrival, from its last reading there:
  with player   found, in the player's worldspace (sameworld true, the worldspace not None)
  left behind   found, in another worldspace (for ours: the base probe world the game never plays)
  not loaded    GetFormFromFile returned None: a temporary reference whose cell is not loaded, or a missing record
  not installed its plugin is not loaded
  unknown       the line lacks a value the verdict needs (a cut line), or both are in interiors
Probe run 2 adds T7, a persistent marker stored in the spawn cell's own persistent group (merge-diff, FAL-188),
and t7_result() reads it at each arrival on our planet (at the last reading), after the LC172 control (an arrival
elsewhere where MERGE and LC172COC are both with player, else "control failed" or, never read, "control not read":
the session proves nothing):
  PASS         T7 with player and T1 left behind (the offset of T7 is then a whole-cell overlay shift, not ~0)
  FAIL         T7 left behind, or not loaded while T5 (the cell-content control) was found (with player or left
               behind): rank 2 is wrong, no exterior-persistent markers as the map fix
  cell not loaded  T7 and T5 both not loaded at that arrival: the spawn cell never loaded, so T7 says nothing
               (probe run 2, FAL-207: not a FAIL)
  confounded   T1 and T7 both with player (the whole world started instancing: not a result for T7's placement)
  unknown      anything else (T7 or T1 unread, or not installed)

The offset is the reference's position minus its position in the plugin (plan.json "refs" / "merge"): (0, 0) is a
reference where the plugin put it; a merged reference moves with its world (LC172World's COC marker moved by about
(-500, -2300) on 11 Oct). The distance is GetDistance to the player; for a reference in another worldspace the game
returns the largest float, 3.4e38 (verified: probe run 1, 31 of 33 readings), which the table leaves out.
"""
import re

LINE = re.compile(r"FO4SF(?:PP|CS) rt=(?P<rt>[-+\d.eE]+) (?P<event>\w+)(?P<rest>.*)$", re.IGNORECASE)
TOKEN = re.compile(r"(\w+)=(\S*)")
EVENTS = ("init", "chain", "arrive", "player", "planet", "ref", "location")
ID_KEYS = {"quest", "world", "loc", "planet", "surface", "planetloc", "cell", "id", "editorloc", "type", "atmos",
           "probe_planet", "surface_planet", "planet_location"}
LISTS = {"probe_parents": "the probe location's parents",                  # key: the list (GetParentLocations)
         "surface_parents": "our surface's parents",
         "planet_parents": "our planet location's parents",
         "planet_systems": "our planet location's LocTypeStarSystem parents",
         "probe_orbitals": "the probe location's LocTypeMajorOrbital parents",
         "probe_systems": "the probe location's LocTypeStarSystem parents"}
LIST_KEYS = set(LISTS)
ISCHILD = (("surface_ischild_probe", "probe_ischild_surface"),      # version 2: (the parent asks, the child asks)
           ("planet_ischild_surface", "surface_ischild_planet"))
CHAIN_V1 = ("probe_child_of_surface", "surface_child_of_planet")     # version 1: the child asked only; no evidence
LINKS = (("the probe location under our surface", ISCHILD[0], "our surface", ("probe_parents",)),
         ("our surface under our planet location", ISCHILD[1], "our planet location", ("surface_parents",)),
         ("our planet location under the system location", None, "the system location",
          ("planet_parents", "planet_systems")))         # (link, its IsChild pair, the parent, the lists to hold it)
REACH = (("the planet lookup from the probe location", "probe_orbitals", "our planet location"),
         ("the star system lookup from the probe location", "probe_systems", "the system location"))
READINGS = (2, 10, 30, 60)
T7_CONTROLS = ("MERGE", "LC172COC")      # the LC172 arrival's controls: both must be with player
OTHER_WORLD_M = 1e30                     # GetDistance's answer for another worldspace is 3.4e38 (FLT_MAX)


def u32(v):
    """A form id as Papyrus printed it (signed decimal) as the unsigned 32-bit id, None for none."""
    return None if v is None else int(v) & 0xFFFFFFFF


def id_list(text):
    """A list of form ids as the script joins them ("<id>,<id>,...", signed decimal; "none" for an empty list),
    unsigned; a "none" entry is None and an entry that is no number stays text. An empty value is None, not a list:
    the script never writes one, so the line was cut there."""
    if text == "":
        return None
    if text.lower() == "none":
        return []
    out = []
    for v in text.split(","):
        try:
            out.append(None if v.lower() == "none" else u32(int(v)))
        except ValueError:
            out.append(v)
    return out


def value(key, text):
    low = text.lower()
    if key in LIST_KEYS:
        return id_list(text)
    if low == "none":
        return None
    if low in ("true", "false"):
        return low == "true"
    if key in ID_KEYS or key in ("n", "at", "local", "version", "actors"):
        try:
            return int(text)
        except ValueError:
            pass
    try:
        return float(text)
    except ValueError:
        return text


def parse_line(line):
    """{"rt", "event", key: value ...} of one probe line, None for any other line."""
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
    if isinstance(out.get("tag"), str):
        out["tag"] = out["tag"].upper()
    for k in ID_KEYS & set(out):
        if isinstance(out[k], int):
            out[k] = u32(out[k])
    return out


def runs(lines):
    """[[parsed line]] split at each init line (each a new script instance); lines before the first init are kept
    as a run of their own (a log that lost its start)."""
    out, cur = [], []
    for line in lines:
        p = parse_line(line)
        if p is None:
            continue
        if p["event"] == "init" and cur and not twin_init(cur, p):
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


INIT_FORMS = ("world", "loc", "planet", "surface", "planetloc")     # the init line's forms: all present = complete


def init_forms(p):
    """How many of the init line's forms it holds (the others read none: GetFormFromFile found nothing)."""
    return sum(1 for k in INIT_FORMS if p.get(k) is not None)


def twin_init(cur, p):
    """Whether the init line p is OnInit logging a second time in the run cur (probe run 2: an empty second line):
    only before the run's first arrival (a later init is a new session, which must not borrow this run's init or
    control), and only when p or every init so far is incomplete (a complete line never joins an earlier complete one)."""
    if any(x["event"] == "arrive" for x in cur):
        return False
    inits = [x for x in cur if x["event"] == "init"]
    if not inits:                                # a headerless prefix (the log lost its start) is a run of its own
        return False
    return init_forms(p) < len(INIT_FORMS) or all(init_forms(x) < len(INIT_FORMS) for x in inits)


def best_init(lines):
    """The init line to read: when OnInit logged more than once (probe run 2: the second line came out empty), the
    first one holding the most forms, so a complete line wins over an empty one; None without an init line."""
    inits = [p for p in lines if p["event"] == "init"]
    return max(inits, key=init_forms, default=None)      # max keeps the first of equal lines


def hexid(v):
    return None if v is None else f"{v:08X}"


def load_index(init):
    """The probe plugin's load index from the init line's quest id (the quest is local id 0x814 of
    FO4SFPlanetProbe.esm), None without an init line."""
    q = (init or {}).get("quest")
    return None if q is None else q >> 24


def name_of(fid, names):
    """A known id's label ("probe world", "Mars", ...), "runtime FF instance" for an FF id, else the hex id."""
    if fid is None:
        return "none"
    if fid in names:
        return names[fid]
    if fid >> 24 == 0xFF:
        return f"runtime {fid:08X}"
    return f"{fid:08X}"


def known_names(plan, init):
    """{form id: label} of the ids the plan and the init line name (runtime ids of our plugins come from init)."""
    names = {}
    for label, fid in ((plan or {}).get("known_ids") or {}).items():
        if isinstance(fid, str):
            fid = int(fid, 16)
        names[fid] = label
    for key, label in (("world", "probe world"), ("loc", "probe location"), ("planet", "our planet"),
                       ("surface", "our surface"), ("planetloc", "our planet location")):
        v = (init or {}).get(key)
        if v is not None:
            names[v] = label
    planetloc = (init or {}).get("planetloc")
    if planetloc is not None and plan is not None and plan.get("system", "own") == "own":     # a stage before route
        names[(planetloc & 0xFF000000) | OWN_SYSTEM_LOC] = "our system location"     # B was route A's: in our master
    return names


OWN_SYSTEM_LOC = 0x801                   # records.SYSTEM_LOC: route A's system location in FO4SFPlanet.esm


def ids_named(names, label):
    """The ids names gives label; "the system location" is the star system's location under any name (route A's
    "our system location", from the init line; route B's "<EditorID> system location", from plan.json)."""
    if label == "the system location":
        return [f for f, n in names.items() if n.endswith("system location")]
    return [f for f, n in names.items() if n == label]


def list_reading(chain, key, want):
    """Whether the list under key holds one of want's ids: False for an empty list (it holds no parent at all), None
    without the list or when want is empty (the id is not known)."""
    got = chain.get(key)
    if not isinstance(got, list):
        return None
    if not got:
        return False
    return any(f in got for f in want) if want else None


def ischild_reading(chain, pair):
    """(the link by IsChild: True when either way answered true, False only when both ways answered false (one way
    alone settles nothing), else None; the way it answered: "parent asks" as Location.psc's comment reads, "child
    asks", "both", or None)."""
    asked = tuple(chain.get(k) if isinstance(chain.get(k), bool) else None for k in pair or ())
    if True in asked:
        return True, {(True, False): "parent asks", (False, True): "child asks", (True, True): "both"}.get(asked)
    if asked and all(v is False for v in asked):
        return False, None
    return None, None


def chain_reading(chain, names, version=None):
    """What the chain line shows, None without one: the IsChild answers as logged (ischild); each list by its label
    (parents); each link with a reading per source (IsChild, a list: True / False, None when the parent's id is not
    known) and whether it holds (True / False only when every known reading agrees, else None); the way IsChild
    answered (ischild_reads: "parent asks", "child asks", "both", "mixed" or None); the lookups from the probe
    location the way SQ_ParentScript does them (reach); whether the probe location's own list goes past its parent
    (ancestors: None when unknown, or when that list lacks its parent); the key of a cut line's last value, left out
    (cut); and (problems, notes). version: the script's, from the init line (None: told by the line's keys). A
    version 2 line without end=true was cut, so its last value is left out (a note), unless it is a bool: a cut "true"
    or "false" never reads as one, so a bool is whole."""
    if chain is None:
        return None, [], []
    problems, notes, cut = [], [], None
    if (isinstance(version, int) and version < 2) or any(k in chain for k in CHAIN_V1):
        if any(k in chain for k in CHAIN_V1):
            notes.append("chain: this log's script (version 1) asked IsChild one way only, the child about its "
                         "parent, so " + " and ".join(k for k in CHAIN_V1 if k in chain) + " settle nothing until a "
                         "version 2 log shows which way IsChild reads")
    elif "end" not in chain:                         # version 2 ends the line with end=true: the last value may be cut
        last = [k for k in chain if k not in ("rt", "event")][-1:]
        if last and not isinstance(chain[last[0]], bool):
            cut = last[0]
            chain = {k: v for k, v in chain.items() if k != cut}
        notes.append("chain: the line is cut (no end=true)" + (f": its last value, {cut}, is left out" if cut else ""))
    out = {"ischild": {k: chain[k] for pair in ISCHILD for k in pair if k in chain}}
    out["parents"] = {LISTS[k]: [p if isinstance(p, str) else name_of(p, names) for p in chain[k]]
                      for k in LISTS if isinstance(chain.get(k), list)}
    out["links"], ways = {}, {}
    for label, pair, parent, keys in LINKS:
        want = ids_named(names, parent)
        readings = {}
        held, way = ischild_reading(chain, pair)
        if held is not None:
            readings["IsChild"] = held
        if way:
            ways[label] = way
        for k in keys:
            if k in chain:
                readings[LISTS[k]] = list_reading(chain, k, want)
        if not readings:
            continue
        known = {v for v in readings.values() if v is not None}
        holds = next(iter(known)) if len(known) == 1 else None
        out["links"][label] = {"holds": holds, "readings": readings}
        if holds is False:
            problems.append(f"chain: {label}: every reading says no (" + ", ".join(
                k for k, v in readings.items() if v is not None) + ")")
        elif len(known) > 1:
            notes.append(f"chain: {label}: the readings disagree (" + ", ".join(
                f"{k} {'yes' if v else 'no'}" for k, v in readings.items() if v is not None) + ")")
    kinds = set(ways.values())
    out["ischild_reads"] = next(iter(kinds)) if len(kinds) == 1 else "mixed" if kinds else None
    if out["ischild_reads"] == "child asks":
        notes.append("chain: IsChild answered true when the child asks (the caller is the child), as MQ204's and "
                     "UC04's scripts call it, the other way round from Location.psc's comment")
    elif out["ischild_reads"] == "both":
        notes.append("chain: IsChild answered true both ways round")
    elif out["ischild_reads"] == "mixed":
        notes.append("chain: IsChild answered differently for the two links (" + "; ".join(
            f"{k}: {v}" for k, v in ways.items()) + ")")
    out["reach"] = {}
    for label, key, target in REACH:
        if key in chain:
            found = out["reach"][label] = list_reading(chain, key, ids_named(names, target))
            if found is False:
                notes.append(f"chain: {label} does not find {target}")
    probe = chain.get("probe_parents")
    parent = ids_named(names, "our surface")
    has_parent = isinstance(probe, list) and any(f in probe for f in parent)
    out["ancestors"] = any(f is not None and f not in parent for f in probe) if has_parent else None
    out["cut"] = cut
    return out, problems, notes


def ref_verdict(r):
    if r.get("installed") is False:
        return "not installed"
    found = r.get("found")
    if found is False:
        return "not loaded"
    if found is True:
        same = r.get("sameworld")
        if same is True and r.get("world") is not None:
            return "with player"
        if same is False:
            return "left behind"
    return "unknown"


def control_held(arrivals):
    """Whether the LC172 control held: True when an arrival that is not on our planet has MERGE and LC172COC both
    with player, False when such arrivals read the controls and none has both, None when no other arrival read them."""
    seen = False
    for a in arrivals:
        if a["kind"] == "our planet" or not all(t in a["refs"] for t in T7_CONTROLS):
            continue
        seen = True
        if all(a["refs"][t]["verdict"] == "with player" for t in T7_CONTROLS):
            return True
    return False if seen else None


def t7_result(refs, control=None):
    """PASS, FAIL, "cell not loaded" (T7 and T5 both not loaded), confounded, unknown, "control failed" (control False: the LC172 control did not hold, so nothing
    is proved), "control not read" (control None: no LC172 arrival was read) or None (no T7 reading) for one arrival's refs ({tag: {"verdict": ...}}, as summarize() files them)."""
    t7 = (refs.get("T7") or {}).get("verdict")
    if t7 is None:
        return None
    if control is False:
        return "control failed"
    if control is None:
        return "control not read"                # no LC172 arrival read MERGE and LC172COC: PASS would prove nothing
    t1 = (refs.get("T1") or {}).get("verdict")
    if t7 == "not loaded" and (refs.get("T5") or {}).get("verdict") == "not loaded":
        return "cell not loaded"                 # the cell control is not loaded either: the spawn cell never loaded
    if t7 in ("left behind", "not loaded"):
        return "FAIL"
    if t7 == "with player" and t1 == "left behind":
        return "PASS"
    if t7 == "with player" and t1 == "with player":
        return "confounded"
    return "unknown"


def core_storage_result(lines, run=-1):
    """The core storage probe's verdict per arrival (FAL-208, scripts/core_storage/FO4SF_CoreStorageQuest.psc: lines
    "FO4SFCS rt=... player|ref n=.. at=.. tag=CS_P|CS_T ...", read like the planet probe's) at each arrival's last
    reading: [{"n", "cs_p", "cs_t", "result"}], the result by the control first: CS_T not loaded is "cell not loaded"
    (the cell never loaded: CS_P is not judged); CS_T found and CS_P with player is PASS; CS_T found and CS_P left
    behind or not loaded is FAIL; "not installed" for a missing plugin; "unknown" for anything else (a cut line, a
    tag unread, CS_T in an interior). One run only (default the last; runs() splits at each init line), so an earlier
    session's readings never complete a later, cut one. The offset of CS_P is for the reader of the log (core merge about -1200, -2700)."""
    last = {}
    order = []
    rs = runs(lines)
    for p in (rs[run] if rs else []):
        if p["event"] != "ref" or not isinstance(p.get("tag"), str) or p["tag"] not in ("CS_P", "CS_T"):
            continue
        n = p.get("n")
        if n not in last:
            last[n] = {}
            order.append(n)
        last[n][p["tag"]] = ref_verdict(p)
    out = []
    for n in order:
        p_v, t_v = last[n].get("CS_P"), last[n].get("CS_T")
        if "not installed" in (p_v, t_v):
            res = "not installed"
        elif t_v == "not loaded":
            res = "cell not loaded"
        elif t_v in ("with player", "left behind") and p_v == "with player":
            res = "PASS"
        elif t_v in ("with player", "left behind") and p_v in ("left behind", "not loaded"):
            res = "FAIL"
        else:
            res = "unknown"
        out.append({"n": n, "cs_p": p_v, "cs_t": t_v, "result": res})
    return out


def local_positions(plan):
    """{tag: (x, y, z)} of the references' positions in their plugins (plan.json)."""
    out = {}
    for r in (plan or {}).get("refs", []):
        out[r["tag"]] = tuple(r["pos"])
    m = (plan or {}).get("merge") or {}
    if m.get("local"):
        out["MERGE"] = tuple(m["local"])
    c = (plan or {}).get("lc172_coc") or {}
    if c.get("local"):
        out["LC172COC"] = tuple(c["local"])
    return out


def summarize(lines, plan=None, run=-1):
    """The chosen run (default the last) as a JSON-ready summary: init, chain, and per arrival the player's world and
    planet and each reference's verdict at its last reading."""
    rs = runs(lines)
    if not rs:
        return {"runs": 0, "arrivals": [], "problems": ["no FO4SFPP line in the log"]}
    lines_ = rs[run]
    init = best_init(lines_)
    chain = next((p for p in lines_ if p["event"] == "chain"), None)
    names = known_names(plan, init)
    reading, chain_problems, notes = chain_reading(chain, names, (init or {}).get("version"))
    local = local_positions(plan)
    arrivals = {}
    order = []
    for p in lines_:
        if p["event"] == "arrive":
            n = p.get("n")
            arrivals[n] = {"n": n, "rt": p["rt"], "world": name_of(p.get("world"), names),
                           "world_id": hexid(p.get("world")), "cell_id": hexid(p.get("cell")),
                           "pos": [p.get("x"), p.get("y"), p.get("z")], "probeworld": p.get("probeworld"),
                           "readings": [], "player": None, "planet": None, "refs": {}, "location": None}
            order.append(n)
            continue
        n = p.get("n")
        if n not in arrivals:
            continue
        a = arrivals[n]
        if p["event"] == "player":
            a["readings"].append(p.get("at"))
            a["player"] = {"at": p.get("at"), "world": name_of(p.get("world"), names), "world_id": hexid(p.get("world")),
                           "planet": name_of(p.get("planet"), names), "planet_id": hexid(p.get("planet")),
                           "loc": name_of(p.get("loc"), names), "pos": [p.get("x"), p.get("y"), p.get("z")],
                           "ourplanet": p.get("ourplanet"), "probeloc": p.get("probeloc"),
                           "probeworld": p.get("probeworld")}
        elif p["event"] == "planet":
            a["planet"] = {k: p.get(k) for k in ("at", "gravity", "day", "temp", "pressure")}
            a["planet"].update(id=hexid(p.get("id")), type=hexid(p.get("type")), atmos=hexid(p.get("atmos")),
                               loc=name_of(p.get("loc"), names))
        elif p["event"] == "ref":
            tag = p.get("tag")
            if not isinstance(tag, str):                     # a cut line: nothing to file it under
                continue
            v = ref_verdict(p)
            r = {"at": p.get("at"), "verdict": v, "plugin": p.get("plugin"), "local_id": p.get("local")}
            if p.get("found") is True:
                pos = (p.get("x"), p.get("y"), p.get("z"))
                r.update(id=hexid(p.get("id")), world=name_of(p.get("world"), names), world_id=hexid(p.get("world")),
                         loc=name_of(p.get("loc"), names), editorloc=name_of(p.get("editorloc"), names),
                         pos=list(pos), dist=p.get("dist"), loaded=p.get("loaded"), disabled=p.get("disabled"),
                         actor=p.get("actor"))
                if tag in local and all(isinstance(v, float) for v in pos[:2]):
                    r["offset"] = [round(pos[0] - local[tag][0], 2) + 0.0, round(pos[1] - local[tag][1], 2) + 0.0]
            a["refs"][tag] = r
        elif p["event"] == "location":
            a["location"] = {"at": p.get("at"), "loaded": p.get("loaded"), "actors": p.get("actors")}
    out_arrivals = []
    for n in order:
        a = arrivals[n]
        pl = a["player"] or {}
        a["complete"] = all(t in a["readings"] for t in READINGS)
        ours = pl.get("ourplanet") is True or a["probeworld"] is True or pl.get("probeworld") is True
        a["kind"] = "our planet" if ours else pl.get("planet", "unknown")
        out_arrivals.append(a)
    control = control_held(out_arrivals)
    for a in out_arrivals:
        a["t7"] = t7_result(a["refs"], control) if a["kind"] == "our planet" else None
    problems = []
    if init is None:
        problems.append("no init line in this run (the log lost its start)")
    elif init.get("world") is None or init.get("planet") is None:
        problems.append("init: the probe world or our planet was not found by GetFormFromFile")
    problems += chain_problems
    if not any(a["kind"] == "our planet" for a in out_arrivals):
        problems.append("no arrival on our planet")
    return {"runs": len(rs), "run": run if run >= 0 else len(rs) + run, "load_index": load_index(init),
            "init": init, "chain": chain, "chain_reading": reading, "arrivals": out_arrivals, "problems": problems,
            "notes": notes}


def verdict_table(summary, tags=None):
    """Lines of a plain text table: one row per reference, one column per arrival (its verdict and offset)."""
    arr = summary.get("arrivals", [])
    if not arr:
        return ["no arrivals"]
    tags = tags or sorted({t for a in arr for t in a["refs"]}, key=lambda t: (not t.startswith("T"), t))
    head = ["tag"] + [f"#{a['n']} {a['kind']}" for a in arr]
    rows = [head]
    for t in tags:
        row = [t]
        for a in arr:
            r = a["refs"].get(t)
            if r is None:
                row.append("-")
                continue
            cell = r["verdict"]
            if r.get("offset") is not None:
                cell += f" ({r['offset'][0]:g}, {r['offset'][1]:g})"
            if isinstance(r.get("dist"), float) and r["dist"] < OTHER_WORLD_M:     # 3.4e38: another worldspace
                cell += f" {r['dist']:.0f} m"
            row.append(cell)
        rows.append(row)
    widths = [max(len(r[i]) for r in rows) for i in range(len(head))]
    return ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
