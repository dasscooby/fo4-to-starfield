"""Judges for the combined-core PC probes P1 to P10 (docs/spikes/combined-core-probes.md is the runbook).

The probes themselves run on the owner's PC (the plugin FO4SFCombinedProbe.esm with its Papyrus scripts, and the SFSE
plugin FOCCSidecar.dll for P1); what comes back is text: the user log the scripts write, the SFSE plugin's JSON-lines
log and sidecar files, a `saves.json` listing, and the stage's compile receipts. This module reads that text and gives
one verdict per probe, by the queue's rule (scripts/game/README.md, docs/terrain/door-rounds.md): **PASS only from the
attempt's own evidence, FAIL from contradicting evidence, INCONCLUSIVE whenever a read, log or file is missing.** Empty
input is never a PASS. Every verdict quotes the lines it rests on with file and line number, and labels the thresholds
it used as placeholders (they are not design numbers). Nothing here touches a game.

Trace format (the contract group A's scripts write; `Trace()` in FOCC_ProbeQuest.psc):

    [21:29:40] FOCC rt=12.345 p2 set loc=50331649 local=2054 value=37.000000 readback=37.000000
    FOCC init variant=default
    FOCC p10 quest started id=-16707575 local=2080

An optional `[clock]` prefix (the game's clock), the word `FOCC`, an optional `rt=<seconds>` (Utility.GetCurrentRealTime),
then words naming the event (`p2 set`, `init`, `where`, ...) and `key=value` fields. Papyrus prints a form id as a SIGNED
decimal int (a runtime id FFxxxxxx comes out negative), floats with six decimals, bools as True / False; `pos=x y z` is
three numbers. `hex2dec` / `dec2hex` convert ids both ways for the console (`cgf` takes ints, `prid` takes hex).

P1's inputs are the SFSE plugin's log, one JSON object per line, e.g. `{"event":"pre_save","save":"focc_p1_a","counter":3}`,
`{"event":"post_load","save":"focc_p1_a","found":true,"valid":true,"counter":3}`, its `sidecars/*.focc` files (the
sidecar.py envelope with the stub world state `{"probe":"P1","counter":k}`), and `saves.json` (`Get-ChildItem ... *.sfs |
Select Name,Length | ConvertTo-Json`: a list of {"Name","Length"}, or one object when PowerShell saw one file).

Collection folder (`python -m fo4sf.combined.probes pN DIR`, or `pN --collect DIR`): `focc_session1.log` and
`focc_session2.log` for the two-launch probes P2 and P3, `focc.0.log` (or `focc_session1.log`) for the one-launch probes,
`saves.json` for P1, P4 and P8, `compile_p5_array129.txt` for P5, `offline_check.txt`, `plan.json` and `FOCC_Probe.psc`
(copied from the stage) for P10, the p3cells stage's `offline_check.txt` for P3's cell half (its cell form ids), and `sfse/focc_sidecar.log` plus `sfse/sidecars/` for P1. `pN FILE` with a single
log file works for the one-launch probes; a two-launch probe given one file is INCONCLUSIVE by construction. B0, the
plugin bridge spike (docs/combined-core-cpp-port.md section 4), is judged from its `b0 gmst`, `b0 ping` and `b0 pong`
lines in the same logs (`b0`).

Exit codes: 0 PASS, 1 FAIL, 2 INCONCLUSIVE (for `all`: the worst of the probes that had any input).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
from dataclasses import dataclass, field

from . import sidecar

PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"
_RANK = {PASS: 0, FAIL: 1, INCONCLUSIVE: 2}
PROBES = ("p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "b0")

# Placeholder thresholds (plan item 8): labelled in every verdict that uses them, never design numbers.
PLACEHOLDERS = {
    "save_growth_bytes": 2 * 1024 * 1024,     # P4, P8: after - before may grow by at most max(2 MB, 5 % of before)
    "save_growth_share": 0.05,
    "p4_min_loaded_cycles": 18,               # P4: actors seen loaded in at least 18 of 20 cycles
    "p4_max_unloaded_cycles": 2,              # P4: loaded=0 in more than 2 cycles is a spawn problem (INCONCLUSIVE)
    "p5_max_tick_ms": 1000.0,                 # P5: a single tick above this fails
    "p9_arrive_m": 10.0,                      # P9: arrived when dist < 10 m
    "p9_seconds": 600.0,                      # P9: within 600 s
    "p9_start_m": 400.0,                      # P9: the route must start at least 400 m out
    "p9_min_cells": 4,                        # P9: distinct parent cells among the samples
    "p9_stuck_m": 2.0,                        # P9: dist unchanged within 2 m ...
    "p9_stuck_s": 120.0,                      # ... for 120 s while loaded = stuck
    "p9_jump_m_per_s": 15.0,                  # P9: faster than this between samples reads as a teleport, not a walk
    "p9_progress_m": 20.0,                    # P9: a FAIL needs the actor this much closer on its own route (N1c's
                                              # uncommanded drift reached 14.06 m) ...
    "p9_control_m": 30.0,                     # ... or a ladder rung started this close that arrived after the baseline
                                              # rung (the first such start) had not
    "p9_control_min_m": 15.0,                 # P9: a scripted control's `p9 go` must find the actor at least this far
                                              # out, so the command has 5 m or more to close (an actor already under
                                              # 10 m at the go has arrived on its own; Codex review of #560)
    "p10_start_window_s": 10.0,               # P10: the quest must start within 10 s (rt) of the send
    "float_eq": 1e-3,                         # readback equals value within this
}

# Plugin-local ids of the probe records (plan "records"); the scripts log the local id they resolved, we only compare.
LOCAL = {"p2_loc": 2054, "p3_noparent": 2055, "p3_chained": 2056, "p10_quest": 2080,
         "p4_marker": 0x80B, "p8_parent0": 0x80C, "p8_child0": 0x80F, "p9_dest": 0x81B, "p10_event": 0x81F,
         "holder": 0x805, "p6_list": 0x81C, "p7_list": 0x81D, "p7_rep": 0x81E,
         "route": 0x809, "p5_first": 0x823, "p5_last": 0x854}   # dotnet/CombinedProbe ids
# what the cards ask for (docs/spikes/combined-core-probes.md P4 / P5): a shorter run is INCONCLUSIVE, not a PASS, so
# a typo in `cgf "FOCC_Probe.P4Run" 3 8.0` is never recorded as the 20-cycle bloat answer
P4_CYCLES = 20
P5_TICKS = 10

_NUM = r"-?\d+(?:\.\d+)?"
_LINE = re.compile(r"^(?:\[[^\]]*\]\s*)?FOCC(?:\s+rt=(?P<rt>" + _NUM + r"))?(?P<rest>(?:\s+\S+)*)\s*$")
_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


# ----------------------------------------------------------------------------------------------- id conversions

def hex2dec(h: str) -> int:
    """`FF012345` (the console's spelling) -> the SIGNED int Papyrus prints and `cgf` wants."""
    v = int(h.strip().lower().removeprefix("0x"), 16) & 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def dec2hex(d) -> str:
    """A Papyrus signed int (as int or text) -> eight upper-case hex digits."""
    return f"{int(d) & 0xFFFFFFFF:08X}"


# ----------------------------------------------------------------------------------------------- trace parsing

@dataclass
class Event:
    file: str
    line: int
    text: str
    kind: str                          # the words before the first key=value, lower case, e.g. "p2 set", "init"
    rt: float | None
    fields: dict = field(default_factory=dict)

    def cite(self) -> dict:
        return {"file": self.file, "line": self.line, "text": self.text}

    def num(self, key: str):
        v = self.fields.get(key)
        try:
            x = float(v) if v is not None else None
        except (TypeError, ValueError):
            return None
        return x if x is None or math.isfinite(x) else None   # nan or inf is no reading (Codex review of #431)

    def count(self, key: str):
        """A whole-number field as an int, None when missing, malformed or fractional (Codex review of #431)."""
        x = self.num(key)
        return int(x) if x is not None and x.is_integer() else None

    def flag(self, key: str):
        v = self.fields.get(key)
        if isinstance(v, str) and v.lower() in ("true", "false", "1", "0"):
            return v.lower() in ("true", "1")
        return None

    def form(self, key: str):
        """A form id field as 8 hex, None for `none` or a missing / unparsable value."""
        v = self.fields.get(key)
        if v is None or v == "none":
            return None
        try:
            return dec2hex(v)
        except ValueError:
            return None


def parse_line(text: str, file: str = "-", line: int = 0) -> Event | None:
    """One trace line as an Event, or None for anything that is not a FOCC line (Papyrus warnings, a torn line)."""
    m = _LINE.match(text.rstrip("\r\n"))
    if not m:
        return None
    words, fields, key = [], {}, None
    for tok in m.group("rest").split():
        k, eq, v = tok.partition("=")
        if eq and _WORD.match(k):
            key = k.lower()
            fields[key] = v
        elif key is None:
            words.append(tok.lower())
        else:
            fields[key] = (fields[key] + " " + tok).strip()      # `pos=x y z`: the bare numbers after a value
    if not words and not fields:
        return None
    rt = float(m.group("rt")) if m.group("rt") else None
    return Event(file, line, text.rstrip("\r\n"), " ".join(words), rt, fields)


def parse_log(lines, file: str = "-") -> list[Event]:
    out = []
    for n, s in enumerate(lines, 1):
        e = parse_line(s, file, n)
        if e is not None:
            out.append(e)
    return out


def pos(e: Event, key: str = "pos"):
    v = e.fields.get(key)
    if not v:
        return None
    parts = v.split()
    if len(parts) != 3:
        return None
    try:
        p = [float(x) for x in parts]
    except ValueError:
        return None
    return p if all(math.isfinite(x) for x in p) else None


# ----------------------------------------------------------------------------------------------- inputs

@dataclass
class Collection:
    """Everything a checker may read, as text already loaded: logs by name (lists of lines), the SFSE log, sidecar
    bodies by file name, saves.json parsed, and other text files by name. Tests build one from strings; `collect()`
    reads a folder."""
    logs: dict = field(default_factory=dict)        # name -> list[str]
    sfse_log: list | None = None                    # lines of sfse/focc_sidecar.log
    sidecars: dict | None = None                    # file name -> text (None when the folder is missing)
    saves: list | None = None                       # [{"Name": "x.sfs", "Length": 123}, ...]
    files: dict = field(default_factory=dict)       # other text files by name
    plan: dict | None = None                        # plan.json parsed
    source: str = ""

    def events(self, name: str) -> list[Event]:
        return parse_log(self.logs.get(name, []), name)

    def session(self, n: int) -> list[Event] | None:
        """Events of focc_session<n>.log; for n == 1 also focc.0.log. None when the file is absent."""
        for name in ([f"focc_session{n}.log", "focc.0.log"] if n == 1 else [f"focc_session{n}.log"]):
            if name in self.logs:
                return self.events(name)
        return None

    def any_logs(self) -> list[list[Event]]:
        return [self.events(n) for n in sorted(self.logs)]


_LOG_NAMES = ("focc_session1.log", "focc_session2.log", "focc.0.log")
_TEXT_NAMES = ("compile_p5_array129.txt", "offline_check.txt", "FOCC_Probe.psc")


def _read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def collect(path: str) -> Collection:
    """Load a collection folder (module docstring layout) or a single log file."""
    c = Collection(source=path)
    if os.path.isfile(path):
        c.logs[os.path.basename(path)] = _read_lines(path)
        return c
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    for name in _LOG_NAMES:
        p = os.path.join(path, name)
        if os.path.isfile(p):
            c.logs[name] = _read_lines(p)
    for name in _TEXT_NAMES:
        p = os.path.join(path, name)
        if os.path.isfile(p):
            c.files[name] = "\n".join(_read_lines(p))
    p = os.path.join(path, "saves.json")
    if os.path.isfile(p):
        c.saves = load_saves("\n".join(_read_lines(p)))
    p = os.path.join(path, "plan.json")
    if os.path.isfile(p):
        try:
            c.plan = json.loads("\n".join(_read_lines(p)))
        except ValueError:
            c.plan = None
    p = os.path.join(path, "sfse", "focc_sidecar.log")
    if os.path.isfile(p):
        c.sfse_log = _read_lines(p)
    d = os.path.join(path, "sfse", "sidecars")
    if os.path.isdir(d):
        c.sidecars = {}
        for name in sorted(os.listdir(d)):
            if name.endswith(sidecar.EXTENSION):
                c.sidecars[name] = "\n".join(_read_lines(os.path.join(d, name)))
    return c


def load_saves(text: str) -> list | None:
    """saves.json as a list of {"Name", "Length"}; PowerShell writes one object (not a list) for a single file. None
    when the text is not that shape."""
    text = text.lstrip("﻿")
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(x, dict) and "Name" in x for x in data):
        return None
    return data


def save_sizes(saves: list | None) -> dict:
    """{stem: Length} for every entry whose Length is an int; a missing Length is left out."""
    out = {}
    for s in saves or []:
        name = str(s.get("Name", ""))
        stem = name[:-4] if name.lower().endswith(".sfs") else name
        if isinstance(s.get("Length"), int):
            out[stem] = s["Length"]
    return out


# ----------------------------------------------------------------------------------------------- verdicts

@dataclass
class Verdict:
    probe: str
    verdict: str
    reasons: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def cite(self, *events: Event) -> None:
        for e in events:
            if e is not None and e.cite() not in self.evidence:
                self.evidence.append(e.cite())

    def to_dict(self) -> dict:
        d = {"probe": self.probe, "verdict": self.verdict, "reasons": self.reasons, "evidence": self.evidence}
        d.update(self.extra)
        return d


def _worst(*verdicts: str) -> str:
    return max(verdicts, key=lambda v: _RANK[v]) if verdicts else INCONCLUSIVE


def _by_kind(events: list[Event], kind: str) -> list[Event]:
    return [e for e in events if e.kind == kind]


def _close(a, b) -> bool:
    return a is not None and b is not None and abs(a - b) <= PLACEHOLDERS["float_eq"]


def _has_init(events: list[Event]) -> Event | None:
    inits = _by_kind(events, "init")
    return inits[0] if inits else None


def _relaunch(s1: list[Event], s2: list[Event]) -> tuple[Event, int] | None:
    """Where session2's own launch begins, as (the event that proves it, the first session2 line that counts), or None
    when nothing proves session2 is a later process than session1.

    Proof is an `init` line (reads count after it), or the real-time clock. OnInit does not fire again when a save
    made after the quest started is loaded (owner's PC, 28 Oct 2026, P2 and P3 launch 2: "focc log opened" and the
    reads, no init). rt is Utility.GetCurrentRealTime, seconds since the game process started. So a session2 that shares
    no line with session1 and whose first rt is below session1's highest rt cannot be the same process (every line of
    session2 counts). A later copy of the same process's log fails both tests: it repeats session1's lines, and its rt
    only grows."""
    init = _has_init(s2)
    if init is not None:
        return init, init.line + 1
    rts1 = [e.rt for e in s1 if e.rt is not None]
    first2 = next((e for e in s2 if e.rt is not None), None)
    if not rts1 or first2 is None or {e.text for e in s1} & {e.text for e in s2}:
        return None
    return (first2, 1) if first2.rt < max(rts1) else None


def _growth(v: Verdict, sizes: dict, before: str, after: str) -> str:
    """Save growth judged against the placeholder bound; records the numbers. Returns a verdict for that part."""
    v.extra["save_growth"] = {"before": sizes.get(before), "after": sizes.get(after),
                              "bound_placeholder": {"bytes": PLACEHOLDERS["save_growth_bytes"],
                                                    "share": PLACEHOLDERS["save_growth_share"]}}
    if before not in sizes or after not in sizes:
        v.reasons.append(f"saves.json lacks {before!r} or {after!r} (or their Length)")
        return INCONCLUSIVE
    growth = sizes[after] - sizes[before]
    bound = max(PLACEHOLDERS["save_growth_bytes"], PLACEHOLDERS["save_growth_share"] * sizes[before])
    v.extra["save_growth"]["growth"] = growth
    v.extra["save_growth"]["bound"] = int(bound)
    if growth > bound:
        v.reasons.append(f"save grew by {growth} bytes, above the placeholder bound {int(bound)}")
        return FAIL
    v.reasons.append(f"save growth {growth} bytes within the placeholder bound {int(bound)} (the number is the finding)")
    return PASS


# ----------------------------------------------------------------------------------------------- P1

def _is_int(x) -> bool:
    """A JSON integer, not a bool (True == 1 in Python)."""
    return isinstance(x, int) and not isinstance(x, bool)


def _sfse_events(lines: list[str] | None) -> list[tuple[int, dict, str]]:
    out = []
    for n, s in enumerate(lines or [], 1):
        s = s.strip()
        if not s:
            continue
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if isinstance(d, dict) and "event" in d:
            out.append((n, d, s))
    return out


def decode_stub_sidecar(text: str, save_name: str | None = None) -> dict:
    """The P1 sidecar envelope with its stub world state: checks what sidecar.decode checks (format, schema, save
    name, sha256 over the sorted-keys JSON of world_state) without model.WorldState. Returns world_state; ValueError
    on any mismatch."""
    try:
        body = json.loads(text)
    except ValueError as e:
        raise ValueError(f"not JSON: {e}") from None
    if not isinstance(body, dict) or body.get("format") != sidecar.FORMAT:
        raise ValueError("format is not focc-sidecar")
    if body.get("schema") != sidecar.SCHEMA:
        raise ValueError(f"schema {body.get('schema')!r} is not {sidecar.SCHEMA}")
    if save_name is not None and body.get("save_name") != save_name:
        raise ValueError(f"save_name {body.get('save_name')!r} is not {save_name!r}")
    if "world_state" not in body or "sha256" not in body:
        raise ValueError("lacks world_state or sha256")
    state = json.dumps(body["world_state"], sort_keys=True)
    if sidecar.checksum(state) != body["sha256"]:
        raise ValueError("sha256 mismatch over the sorted-keys JSON of world_state")
    return body["world_state"]


def orphans(sidecar_names, save_names) -> list[str]:
    """Sidecar file names whose save is not among `save_names` (stems without .sfs), sorted; mirrors
    sidecar.orphans on names instead of a folder and never deletes."""
    wanted = {sidecar.sidecar_name(s) for s in save_names if s}
    return sorted(n for n in sidecar_names if n.endswith(sidecar.EXTENSION) and n not in wanted)


def check_p1(c: Collection) -> Verdict:
    v = Verdict("p1", INCONCLUSIVE)
    v.extra["settles"] = "CC-02: sidecar viability and orphan handling (engine-feasibility.md P1)"
    if c.sfse_log is None:
        v.reasons.append("sfse/focc_sidecar.log missing: the plugin's log was not collected")
        return v
    evs = _sfse_events(c.sfse_log)
    for n, d, s in evs:
        v.evidence.append({"file": "sfse/focc_sidecar.log", "line": n, "text": s})
    if not evs:
        v.reasons.append("the SFSE log has no JSON event lines (the plugin did not load or did not log)")
        return v
    pre, pre_line = {}, {}
    for n, d, s in evs:
        if d.get("event") == "pre_save" and isinstance(d.get("save"), str):
            pre[d["save"]], pre_line[d["save"]] = d, n
    post_line = {}
    for n, d, s in evs:
        name = d.get("save")
        if (d.get("event") == "post_save" and isinstance(name, str) and name in pre_line and n > pre_line[name]
                and name not in post_line):
            post_line[name] = n
    post_saves = set(post_line)
    # The log is appended across launches: a load only counts for a saved name when it follows that name's completed
    # save (its last pre_save and the post_save after it), so neither an older attempt's read-back nor a read between
    # PreSave and the save's completion stands in for this one's (Codex review of #431).
    loads = [d for n, d, s in evs if d.get("event") == "post_load"
             and (d.get("save") not in pre_line or n > post_line.get(d.get("save"), float("inf")))]
    if not loads:
        v.reasons.append("no post_load line: the plugin never saw a load (check the SFSE loader output)")
        return v
    if not pre:
        v.reasons.append("no pre_save line: nothing was saved while the plugin ran")
        return v
    if c.sidecars is None:
        v.reasons.append("sfse/sidecars folder missing")
        return v
    failed = False
    for name, d in sorted(pre.items()):
        fn = sidecar.sidecar_name(name)
        if name not in post_saves:
            v.reasons.append(f"pre_save {name!r} without post_save")
            failed = True
        if not _is_int(d.get("counter")):
            v.reasons.append(f"pre_save {name!r} logs no integer counter: its sidecar and read-back cannot be tied to "
                             "this save event")       # Codex review of #431
            failed = True
        if d.get("written") is not True:        # an older sidecar may still sit under that name (Codex, #431)
            v.reasons.append(f"pre_save {name!r} reports written={d.get('written')!r}: this run's sidecar was not "
                             "written, so any file under its name is not this run's")
            failed = True
        if fn not in c.sidecars:
            v.reasons.append(f"pre_save {name!r} has no sidecar {fn} (name rule mismatch or write failed)")
            failed = True
            continue
        try:
            ws = decode_stub_sidecar(c.sidecars[fn], name)
        except ValueError as e:
            v.reasons.append(f"sidecar {fn} does not decode: {e}")
            failed = True
            continue
        if ws.get("probe") != "P1" or not _is_int(ws.get("counter")):
            v.reasons.append(f"sidecar {fn} world_state is not the P1 stub")
            failed = True
        elif ws.get("counter") != d.get("counter"):
            v.reasons.append(f"sidecar {fn} counter {ws.get('counter')} differs from pre_save counter {d.get('counter')}")
            failed = True
    for d in loads:
        name = d.get("save")
        if name in pre:
            if d.get("found") is not True or d.get("valid") is not True:
                v.reasons.append(f"post_load {name!r} found={d.get('found')} valid={d.get('valid')} for a saved name")
                failed = True
            elif not _is_int(d.get("counter")) or d.get("counter") != pre[name].get("counter"):   # True == 1 (Codex)
                v.reasons.append(f"post_load {name!r} counter {d.get('counter')} is not the last pre_save counter "
                                 f"{pre[name].get('counter')}")
                failed = True
    if failed:
        v.verdict = FAIL
        return v
    read_back = [d for d in loads if d.get("save") in pre]
    if not read_back:
        v.reasons.append("no post_load of a saved name: the read-back half was not exercised (the post_load names "
                         f"were {sorted({str(d.get('save')) for d in loads})}; the saved names {sorted(pre)})")
        return v
    # Orphans after the delete: needs the save names to match .sfs stems, which is unverified (plan P1 risks).
    if c.saves is None:
        v.reasons.append("saves.json missing: every save event has its sidecar, but the orphan question is open")
        return v
    stems = list(save_sizes(c.saves)) or [str(s.get("Name", ""))[:-4] for s in c.saves]
    matched = sorted(set(pre) & set(stems))
    v.extra["save_names_logged"] = sorted(pre)
    v.extra["save_files"] = sorted(stems)
    if not matched:
        v.reasons.append("no SFSE save name equals a .sfs stem: the mapping between the message's name and the file "
                         "name is unverified; orphan handling left open")
        return v
    deleted = sorted(set(pre) - set(stems))
    expected = sorted(sidecar.sidecar_name(n) for n in deleted)
    got = orphans(c.sidecars, stems)
    v.extra["deleted_saves"] = deleted
    v.extra["orphans"] = got
    if got != expected:
        v.reasons.append(f"orphans {got} are not the deleted saves' sidecars {expected}")
        v.verdict = FAIL
        return v
    v.reasons.append(f"every pre_save has its post_save and a valid sidecar; {len(read_back)} post_load(s) of a saved "
                     f"name found it valid with the right counter; orphans are exactly {expected}")
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P2

def _same_launch(c: Collection, v: Verdict) -> bool:
    """True (with the reason appended) when focc_session2.log is a copy of focc_session1.log: the card says to copy
    focc.0.log twice, so the same log under both names is an easy mistake and never proves a relaunch."""
    a, b = c.logs.get("focc_session1.log"), c.logs.get("focc_session2.log")
    if a is not None and a == b:
        v.reasons.append("focc_session1.log and focc_session2.log are identical: one launch copied twice, not a relaunch")
        return True
    return False


def _set_before(s2: list[Event], set_kind: str, rd: Event, v: Verdict) -> bool:
    """True (with the reason appended) when session2 holds a `<set_kind>` line before the read: the value read back
    was written in the same launch, so persistence across a relaunch is not what was measured."""
    before = [e for e in s2 if e.kind == set_kind and e.line < rd.line]
    if before:
        v.cite(before[-1])
        v.reasons.append(f"the read follows a `{set_kind}` in the same launch (session2 line {before[-1].line}): not a "
                         "relaunch")
        return True
    return False


def _local(e: Event, key: str):
    """The plugin-local id of a form id field, or None: a full plugin's ids carry its load index in the top byte
    (local = low 24 bits), a light plugin's are FE + a 12-bit slot (local = low 12 bits)."""
    f = e.form(key)
    if f is None:
        return None
    n = int(f, 16)
    return n & 0xFFF if n >> 24 == 0xFE else n & 0xFFFFFF


def _foreign(e: Event, ids: dict) -> list[str]:
    """The form id fields of `e` that are missing or not the probe record's local id (`ids`: field -> local). A
    stale or foreign property binding must never stand in for the probe's own record (Codex review of #431)."""
    return [f for f, n in ids.items() if _local(e, f) != n]


def _foreign_reason(what: str, e: Event, bad: list[str], ids: dict) -> str:
    return (f"{what}: " + ", ".join(f"{f}={e.fields.get(f, 'missing')}" for f in bad) + " is not the probe's record "
            "(locals " + ", ".join(f"{f} {hex(ids[f])}" for f in bad) + ")")


def _is_plan_form(e: Event, field: str, want) -> bool | None:
    """Whether the logged form id `field` is plan.json's `plugin:hexid`: a Starfield.esm form (load index 00) by its
    whole id, another plugin's by its local id. None when either side is missing or unparsable."""
    plugin, _, hexid = str(want or "").rpartition(":")
    got = e.form(field)
    try:
        want_id = int(hexid, 16)
    except ValueError:
        return None
    if not plugin or got is None:
        return None
    got_id = int(got, 16)
    if plugin.lower() == "starfield.esm":
        return got_id == want_id
    return _local(e, field) == (want_id & (0xFFF if got_id >> 24 == 0xFE else 0xFFFFFF))


def check_p2(c: Collection) -> Verdict:
    v = Verdict("p2", INCONCLUSIVE)
    v.extra["settles"] = "CC-02: location keyword data persists across save/load, linked locations (P2)"
    s1, s2 = c.session(1), c.session(2)
    if s1 is None or s2 is None:
        v.reasons.append("needs focc_session1.log and focc_session2.log (two launches); persistence is never inferred "
                         "from one session")
        return v
    if _same_launch(c, v):
        return v
    sets, links = _by_kind(s1, "p2 set"), _by_kind(s1, "p2 link")
    refused = [e for e in s1 + s2 if e.kind.startswith("p2") and "refused" in e.kind.split()]
    v.cite(*refused)
    if refused:
        v.reasons.append("the script logged refused (a None property): the plugin's records did not resolve")
        return v
    if not sets:
        v.reasons.append("session1 has no `p2 set` line")
        return v
    st = sets[-1]
    v.cite(st)
    value, readback = st.num("value"), st.num("readback")
    if _local(st, "loc") != LOCAL["p2_loc"]:
        v.reasons.append(f"p2 set loc {st.fields.get('loc')} is not the probe location (local {LOCAL['p2_loc']})")
        return v
    for e, ids in ((st, {"holder": LOCAL["holder"]}),) + (((links[-1], {"route": LOCAL["route"]}),) if links else ()):
        bad = _foreign(e, ids)
        if bad:
            v.reasons.append(_foreign_reason(e.kind, e, bad, ids))
            return v
    if value is None or readback is None:
        v.reasons.append("p2 set lacks its value or readback")
        return v
    if not _close(value, readback):
        v.reasons.append(f"set value {value} and immediate readback {readback} differ: SetKeywordData did not take")
        v.verdict = FAIL
        return v
    link_ok = None
    want_link = (LOCAL["p2_loc"], LOCAL["p3_chained"])
    if links:
        v.cite(links[-1])
        if (_local(links[-1], "a"), _local(links[-1], "b")) != want_link:
            v.reasons.append(f"p2 link a/b are not the probe locations (locals {want_link[0]} and {want_link[1]})")
            return v
        link_ok = links[-1].flag("linked")
    launch = _relaunch(s1, s2)
    if launch is None:
        v.reasons.append("session2 has no `FOCC init` line, and its rt does not restart below session1's: a relaunch "
                         "is not proven")
        return v
    proof, first = launch
    v.cite(proof)
    reads = [e for e in s2 if e.kind == "p2 read" and e.line >= first]
    linkreads = [e for e in s2 if e.kind == "p2 linkread" and e.line >= first]
    if not reads:
        v.reasons.append("session2 has no `p2 read` line in its own launch")
        return v
    rd = reads[-1]
    v.cite(rd)
    if _set_before(s2, "p2 set", rd, v):
        return v
    rv = rd.num("value")
    if _foreign(rd, {"holder": LOCAL["holder"]}):
        v.reasons.append(_foreign_reason("p2 read", rd, ["holder"], LOCAL))
        return v
    if _local(rd, "loc") != LOCAL["p2_loc"] or rv is None:
        v.reasons.append(f"p2 read is not on the probe location (local {LOCAL['p2_loc']}) or lacks a value")
        return v
    if not _close(rv, value):
        v.reasons.append(f"after relaunch the datum reads {rv}, set value was {value}: keyword data did not persist")
        v.verdict = FAIL
        return v
    v.reasons.append(f"datum {value} set in session1 (readback {readback}) read back as {rv} after a relaunch")
    if link_ok is True:
        if not linkreads:
            v.reasons.append("p2 link was True in session1 but session2 has no `p2 linkread`")
            return v
        v.cite(linkreads[-1])
        if _set_before(s2, "p2 link", linkreads[-1], v):   # relinked in the same launch (Codex review of #431)
            return v
        if _foreign(linkreads[-1], {"route": LOCAL["route"]}):
            v.reasons.append(_foreign_reason("p2 linkread", linkreads[-1], ["route"], LOCAL))
            return v
        if (_local(linkreads[-1], "a"), _local(linkreads[-1], "b")) != want_link:
            v.reasons.append(f"p2 linkread a/b are not the probe locations (locals {want_link[0]} and "
                             f"{want_link[1]})")
            return v
        if linkreads[-1].flag("linked") is not True:
            v.reasons.append("linked location was True in session1 and not True after relaunch")
            v.verdict = FAIL
            return v
        v.reasons.append("linked location survived the relaunch")
    elif link_ok is False:
        v.reasons.append("AddLinkedLocation did not link in session1 (IsLinkedLocation False)")
        v.verdict = FAIL
        return v
    else:
        v.reasons.append("no `p2 link` line: the linked-location half was not run, so P2 is not settled (run "
                         "P2Set in full; PASS needs set, link, read and linkread)")
        v.extra["linked_locations"] = "not run"
        return v
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P3

_P3_CELLS = ("fo4port_redrocket01", "fo4port_superdupermart01")
# the p3cells stage's offline_check.txt names both cells by Mutagen FormKey (id:plugin), in the builder's summary
# ("CELL overrides FO4Port_RedRocket01 002338:FO4Port.esm -> 0x807, ...") and in the check ("CELL FO4Port_RedRocket01
# 002338:FO4Port.esm: location ...")
_P3_CELL_KEY = re.compile(r"\b(FO4Port_RedRocket01|FO4Port_SuperDuperMart01) ([0-9A-Fa-f]{6}):([^\s:,]+\.es[mlp])\b", re.I)


def _p3_cell_ids(c: Collection):
    """({cell editor id, lower case: FO4Port.esm-local id}, None) from the p3cells stage's offline_check.txt, or
    (None, why). The game may log no editor id for a cell (PC, 28 Oct 2026: `cellname=` empty on both `where` lines,
    as the bridge's feed reads for its cells, scripts/game/bridge_log.py), so the stage's record names them by id."""
    text = c.files.get("offline_check.txt")
    if text is None:
        return None, "the collection has no offline_check.txt from the p3cells stage"
    if "variant=p3cells" not in text:
        return None, "offline_check.txt is not the p3cells stage's (no variant=p3cells)"
    seen = {}
    for name, hexid, plugin in _P3_CELL_KEY.findall(text):
        seen.setdefault(name.lower(), set()).add((plugin.lower(), int(hexid, 16)))
    ids = {}
    for name in _P3_CELLS:
        got = seen.get(name, set())
        if len(got) != 1:
            return None, f"offline_check.txt gives {len(got)} form ids for {name}, not one"
        ((plugin, local),) = got
        if plugin != "fo4port.esm":
            return None, f"offline_check.txt puts {name} in {plugin}, not FO4Port.esm"
        ids[name] = local
    return ids, None


def check_p3(c: Collection) -> Verdict:
    v = Verdict("p3", INCONCLUSIVE)
    v.extra["settles"] = "CC-02 / interiors D1: keyword data on an unparented vs a chained LCTN; a cell's current location"
    v.extra["explored_state"] = {"status": "unresolved",
                                 "reason": "no verified Papyrus read of explored/cleared state in Starfield (FO4's "
                                           "IsCleared is missing, PC job 15); not judged"}
    parts = []
    # Keyword half: two sessions, default variant.
    s1, s2 = c.session(1), c.session(2)
    kw = None
    if s1 is not None and _by_kind(s1, "p3 set"):
        st = _by_kind(s1, "p3 set")[-1]
        v.cite(st)
        va, ra, vb, rb = st.num("va"), st.num("ra"), st.num("vb"), st.num("rb")
        if (_local(st, "a"), _local(st, "b")) != (LOCAL["p3_noparent"], LOCAL["p3_chained"]):
            v.reasons.append(f"p3 set a/b are not the probe locations (locals {LOCAL['p3_noparent']} and "
                             f"{LOCAL['p3_chained']})")
            kw = INCONCLUSIVE
        elif _foreign(st, {"holder": LOCAL["holder"]}):
            v.reasons.append(_foreign_reason("p3 set", st, ["holder"], LOCAL))
            kw = INCONCLUSIVE
        elif None in (va, ra, vb, rb):
            v.reasons.append("p3 set lacks va/ra/vb/rb")
            kw = INCONCLUSIVE
        elif not (_close(va, ra) and _close(vb, rb)):
            v.reasons.append(f"p3 set immediate readbacks ({ra}, {rb}) differ from the values ({va}, {vb})")
            kw = FAIL
        elif s2 is None:
            v.reasons.append("p3 keyword half needs focc_session2.log (a relaunch)")
            kw = INCONCLUSIVE
        elif _same_launch(c, v):
            kw = INCONCLUSIVE
        else:
            launch = _relaunch(s1, s2)
            reads = [e for e in s2 if e.kind == "p3 read" and launch is not None and e.line >= launch[1]]
            if launch is None or not reads:
                v.reasons.append("session2 proves no relaunch (no init line, and its rt does not restart below "
                                 "session1's) or has no `p3 read` in its own launch")
                kw = INCONCLUSIVE
            else:
                rd = reads[-1]
                v.cite(launch[0], rd)
                a_ok, b_ok = _close(rd.num("ra"), va), _close(rd.num("rb"), vb)
                if _set_before(s2, "p3 set", rd, v):
                    kw = INCONCLUSIVE
                elif _foreign(rd, {"holder": LOCAL["holder"]}):
                    v.reasons.append(_foreign_reason("p3 read", rd, ["holder"], LOCAL))
                    kw = INCONCLUSIVE
                elif (_local(rd, "a"), _local(rd, "b")) != (LOCAL["p3_noparent"], LOCAL["p3_chained"]):
                    # The relaunch read names its locations too (Codex review of #431).
                    v.reasons.append(f"p3 read a/b are missing or not the probe locations (locals "
                                     f"{LOCAL['p3_noparent']} and {LOCAL['p3_chained']})")
                    kw = INCONCLUSIVE
                elif rd.num("ra") is None or rd.num("rb") is None:   # no reading contradicts nothing (Codex, #431)
                    v.reasons.append("p3 read lacks ra or rb: the relaunch read-back is incomplete")
                    kw = INCONCLUSIVE
                elif a_ok and b_ok:
                    v.reasons.append("keyword data persisted on both the unparented and the chained location")
                    kw = PASS
                else:
                    v.reasons.append(f"after relaunch unparented reads {rd.num('ra')} (set {va}), chained reads "
                                     f"{rd.num('rb')} (set {vb})")
                    kw = FAIL
        v.extra["keyword_half"] = kw
        parts.append(kw)
    # Cell half: any log of the p3cells variant.
    cell = None
    for evs in c.any_logs():
        init = _has_init(evs)
        if init is None or init.fields.get("variant", "").lower() != "p3cells":
            continue
        v.cite(init)
        wheres = _by_kind(evs, "where")
        want = {"fo4port_redrocket01": LOCAL["p3_noparent"], "fo4port_superdupermart01": LOCAL["p3_chained"]}
        # A `where` line names its cell by cellname or, when the game logged none, by the stage's form id for it, and
        # then only with the game's own word that the id is FO4Port.esm's in this run: `port=True` says
        # Game.GetFormFromFile(local id, "FO4Port.esm") returned this very cell. The stage's file proves the source
        # FormKeys, not which plugin sits in that load slot at run time (Codex review of #560).
        ids, why = _p3_cell_ids(c)

        def named(w, name):
            cn = w.fields.get("cellname", "").lower()
            return cn == name if cn else (ids is not None and _local(w, "cell") == ids[name]
                                          and w.flag("port") is True)
        # One traversal = the latest Red Rocket `where` and the first Super Duper Mart `where` after it, so an
        # interrupted retry never borrows an older attempt's second cell (Codex review of #431).
        seen = {}
        firsts = [w for w in wheres if named(w, "fo4port_redrocket01")]
        if firsts:
            seen["fo4port_redrocket01"] = firsts[-1]
            later = [w for w in wheres if w.line > firsts[-1].line and named(w, "fo4port_superdupermart01")]
            if later:
                seen["fo4port_superdupermart01"] = later[0]
        v.cite(*seen.values())
        unnamed = [w for w in wheres if not w.fields.get("cellname")]
        unbound = [w for w in unnamed if ids is not None and _local(w, "cell") in ids.values()
                   and w.flag("port") is not True]
        by_id = any(not w.fields.get("cellname") for w in seen.values())
        if len(seen) < 2:
            more = ""
            if unnamed and ids is None:
                more = f"; the lines carry no cellname and {why}: copy it from the stage folder"
            elif unbound:
                more = (f"; {len(unbound)} unnamed `where` line(s) carry the stage's cell id but not `port=True`, the "
                        "game's own check (since #560) that the id is FO4Port.esm's in this run: a log from before that "
                        "restage, or another plugin in that load slot; run P3b again with the restaged kit")
            v.reasons.append("cell half: both `where` lines (FO4Port_RedRocket01, FO4Port_SuperDuperMart01) are needed"
                             + more)
            cell = INCONCLUSIVE
        else:
            if by_id:
                v.extra["cells_named_by"] = ("form id (offline_check.txt), bound to FO4Port.esm by the game's port=True; "
                                             "the game logged no cellname")
            # The logged form id, not the script's local= label, names the location (Codex review of #431).
            bad = [n for n, w in seen.items() if _local(w, "loc") != want[n]]
            if bad:
                v.reasons.append(f"cell half: current location is none or another location for {bad}")
                cell = FAIL
            else:
                v.reasons.append("cell half: each overridden cell reports our location as the player's current one")
                cell = PASS
        v.extra["cell_half"] = cell
        parts.append(cell)
        break
    if not parts:
        v.reasons.append("neither the keyword half (p3 set / p3 read over two sessions) nor the p3cells variant was found")
        return v
    v.verdict = _worst(*parts)
    return v


# ----------------------------------------------------------------------------------------------- P4

def check_p4(c: Collection) -> Verdict:
    v = Verdict("p4", INCONCLUSIVE)
    v.extra["settles"] = "L3 spawn reliability and save bloat over 20 materialize/dissolve cycles (P4, rule L3)"
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    starts = _by_kind(evs, "p4 start")
    if not starts:                              # no attempt boundary, no verdict (Codex review of #431)
        v.reasons.append("no `p4 start` line: the cycles cannot be tied to one run of the probe's marker")
        return v
    evs = [e for e in evs if e.line >= starts[-1].line]   # the latest run only: an older one never fills its gaps
    v.cite(starts[-1])
    if _local(starts[-1], "marker") != LOCAL["p4_marker"]:   # the probe's own marker (Codex review of #431)
        v.reasons.append(f"p4 start marker {starts[-1].fields.get('marker')} is not FOCC_P4_SpawnMarker "
                         f"(local {LOCAL['p4_marker']})")
        return v
    if _is_plan_form(starts[-1], "base", _plan_bases(c.plan).get("npc")) is not True:
        v.reasons.append(f"p4 start base {starts[-1].fields.get('base', 'missing')} is not plan.json's npc base "
                         f"({_plan_bases(c.plan).get('npc')}): cannot tell the spawns are the probe's")
        return v
    done = _by_kind(evs, "p4 done")[:1]         # the run's own done closes it: later rows never count (Codex, #431)
    cycles = [e for e in _by_kind(evs, "p4 cycle") if not done or e.line < done[0].line]
    v.cite(*cycles, *done)
    if not done:
        v.reasons.append("no `p4 done` line: the run did not finish")
        return v
    want = done[0].count("cycles")
    if want is None:                            # cycles=20.5 is not a count the script logs (Codex review of #431)
        v.reasons.append("`p4 done` has no whole-number cycles=")
        return v
    if want < P4_CYCLES:
        v.reasons.append(f"only {want} cycles, the probe asks {P4_CYCLES} (cgf \"FOCC_Probe.P4Run\" {P4_CYCLES} 8.0): "
                         "not the bloat answer")
        return v
    if any(e.count("n") is None for e in cycles):   # n=1.5 is not cycle 1 (Codex review of #431)
        v.reasons.append("a p4 cycle line has no whole-number n=")
        return v
    seen = {e.count("n"): e for e in cycles}
    modes = sorted({e.fields.get("mode", "?") for e in cycles})
    v.extra["modes"] = modes
    missing = [n for n in range(1, want + 1) if n not in seen]
    if missing:
        v.reasons.append(f"cycles missing: {missing}")
        return v
    numbers = sorted(e.count("n") for e in cycles)
    if numbers != list(range(1, want + 1)):        # P5's rule: one row per cycle, no extras (Codex review of #431)
        v.reasons.append(f"the cycle lines are not numbered 1..{want} once each: repeated or extra cycles")
        return v
    blank = [n for n, e in seen.items() if None in (e.num("placed"), e.num("deleted"), e.num("loaded"))]
    if blank:                                   # a missing count is no evidence either way (Codex review of #431)
        v.reasons.append(f"cycles without placed=, deleted= or loaded=: {sorted(blank)}")
        return v
    odd = [n for n, e in seen.items() if not all(0 <= e.num(k) <= 3 for k in ("placed", "deleted", "loaded")) or not all(float(e.num(k)).is_integer() for k in ("placed", "deleted", "loaded"))]
    if odd:                                     # the script places exactly three: more is malformed (Codex, #431)
        v.reasons.append(f"cycles with counts the script cannot log (placed, deleted or loaded outside 0..3, or "
                         f"fractional): {sorted(odd)}")
        return v
    short = [n for n, e in seen.items() if e.num("placed") < 3 or e.num("deleted") < 3]
    unloaded = [n for n, e in seen.items() if e.num("loaded") < 1]
    if short:
        v.reasons.append(f"cycles with placed<3 or deleted<3: {sorted(short)}")
        v.verdict = FAIL
        return v
    if len(unloaded) > PLACEHOLDERS["p4_max_unloaded_cycles"]:
        v.reasons.append(f"actors never loaded in cycles {sorted(unloaded)} (placeholder: more than "
                         f"{PLACEHOLDERS['p4_max_unloaded_cycles']} such cycles is a spawn problem, not a bloat answer)")
        return v
    v.reasons.append(f"{want} cycles each placed 3 and deleted 3; loaded in {want - len(unloaded)} cycles")
    sizes = save_sizes(c.saves)
    if c.saves is None:
        v.reasons.append("saves.json missing")
        return v
    v.verdict = _growth(v, sizes, "focc_p4_before", "focc_p4_after")
    return v


# ----------------------------------------------------------------------------------------------- P5

def array_cap(text: str | None) -> dict:
    """`compile_p5_array129.txt` -> {"array_cap": 128 | None | "unknown", "detail": ...}. None when the compiler
    reported 'Compilation succeeded'; 128 only when it did not AND one of its own lines names the array (`129`,
    `128` or `array`): a compile that failed for another reason (flags file missing, bad include path) is "unknown"
    with the first error line, never the cap. The stage's own header line (`FOCC_P5_Array129.psc: new float[129] ...`,
    make_combined_probe.compile_array129) is left out of the search."""
    if text is None:
        return {"array_cap": "unknown", "detail": "compile_p5_array129.txt missing"}
    if "Compilation succeeded" in text:
        return {"array_cap": None, "detail": "new float[129] compiled: no compile-time cap at 128 "
                                             "(runtime growth still open)"}
    own = re.compile(r"^FOCC_P5_Array129\.psc: new float\[129\]|^exit code \d+$|^(compiled|refused):")
    lines = [l for l in text.splitlines() if l.strip() and not own.search(l.strip())]
    about = [l for l in lines if re.search(r"\b129\b|\b128\b|array", l, re.I)]
    if about:
        return {"array_cap": 128, "detail": "compiler refused new float[129]: " + about[0].strip()}
    err = next((l for l in lines if re.search(r"error|unable|cannot|fail|no output", l, re.I)), lines[0] if lines else "")
    return {"array_cap": "unknown", "detail": "compile failed for another reason (not the array size): " + err.strip()}


def check_p5(c: Collection) -> Verdict:
    v = Verdict("p5", INCONCLUSIVE)
    v.extra["settles"] = "Papyrus tick latency baseline over 50 places (L2 fallback), array cap at compile time (P5)"
    v.extra.update(array_cap(c.files.get("compile_p5_array129.txt")))
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    starts = _by_kind(evs, "p5 start")
    if not starts:
        v.reasons.append("no `p5 start` line")
        return v
    start = starts[-1]
    # the run's own done line closes it: ticks after it (appended or reordered evidence) never count (Codex, #431)
    dones = [e for e in _by_kind(evs, "p5 done") if e.line > start.line]
    done = dones[0] if dones else None
    ticks = [e for e in _by_kind(evs, "p5 tick") if e.line > start.line and (done is None or e.line < done.line)]
    v.cite(start, *ticks)
    ids = {"first": LOCAL["p5_first"], "last": LOCAL["p5_last"]}
    bad = _foreign(start, ids)
    if bad or (start.num("places") or 0) != 50:
        v.reasons.append(_foreign_reason("p5 start", start, bad, ids) if bad else
                         f"p5 start places={start.fields.get('places')}, want the probe's 50 globals")
        return v
    want = start.count("ticks")
    if want is None:                            # ticks=10.5 is not a count the script logs (Codex review of #431)
        v.reasons.append("`p5 start` has no whole-number ticks=")
        return v
    if want < P5_TICKS:
        v.cite(*ticks)
        v.reasons.append(f"the run asked for {want} ticks, the probe asks {P5_TICKS} (cgf \"FOCC_Probe.P5Tick\" "
                         f"{P5_TICKS}): too few for a baseline")
        return v
    blank = [e for e in ticks if e.num("ms") is None or e.num("places") is None]
    if blank:                                   # a tick without its readings settles nothing (Codex review of #431)
        v.cite(*blank[:3])
        v.reasons.append(f"{len(blank)} p5 tick line(s) lack ms= or places=")
        return v
    if any(e.count("n") is None for e in ticks):    # an unnumbered tick cannot be placed (Codex review of #431)
        v.reasons.append("a p5 tick line has no whole-number n=")
        return v
    if len(ticks) >= want and sorted(e.count("n") for e in ticks) != list(range(1, want + 1)):
        # every tick row, not only the good ones, is exactly 1..want once each: an extra or interleaved row would
        # hide in the recorded baseline (Codex review of #431)
        v.reasons.append(f"the tick lines are not numbered 1..{want} once each: repeated, extra or missing ticks")
        return v
    short = [e for e in ticks if e.num("places") != 50]
    if short:
        v.cite(*short[:3])
        v.reasons.append(f"{len(short)} tick line(s) read fewer or more than the probe's 50 globals")
        v.verdict = FAIL
        return v
    ms = [e.num("ms") for e in ticks]
    if any(m < 0 for m in ms):                  # elapsed real time is never negative (Codex review of #431)
        v.reasons.append("a p5 tick reports a negative ms= reading")
        return v
    if len(ms) < want:
        v.reasons.append(f"{len(ms)} tick lines with places=50 after start, want {want}")
        v.verdict = FAIL if ticks else INCONCLUSIVE
        return v
    if done is None or (done.count("ticks") or 0) < want:   # a truncated copy never settles P5 (Codex review of #431)
        v.reasons.append(f"no `p5 done ticks={want}` after the ticks: the run did not finish or the log was cut")
        return v
    v.cite(done)
    v.extra["baseline_ms"] = {"min": min(ms), "median": statistics.median(ms), "max": max(ms),
                              "per_place_median": statistics.median(ms) / 50, "ticks": len(ms),
                              "note": "record under docs/ai/optimization.md's before/after rule"}
    if max(ms) > PLACEHOLDERS["p5_max_tick_ms"]:
        v.reasons.append(f"a tick took {max(ms)} ms, above the placeholder {PLACEHOLDERS['p5_max_tick_ms']} ms")
        v.verdict = FAIL
        return v
    v.reasons.append(f"{len(ms)} ticks over 50 globals, median {statistics.median(ms):.3f} ms (recorded, not judged "
                     f"beyond the placeholder cap)")
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P6 / P7

def _plan_bases(plan: dict | None) -> dict:
    """plan.json's base mapping: make_combined_probe nests lvln_a / lvln_b under `bases`; a flat plan is accepted too."""
    if not plan:
        return {}
    bases = plan.get("bases")
    return bases if isinstance(bases, dict) else plan


def _skipped(plan: dict | None, group: str, flag: str) -> bool:
    """True when the stage left a record group out: plan.json `"<flag>": false` (the runbook's spelling) or `group`
    in its `skip` list (what make_combined_probe writes from --skip)."""
    if not plan:
        return False
    skip = plan.get("skip")
    return plan.get(flag) is False or (isinstance(skip, list) and group in skip)


def _base_match(e: Event, plan: dict | None, key_a: str, key_b: str):
    """Which list entry a spawned actor's base is. FOCC_ProbeQuest.SpawnTrials writes `baselocal=a|b|other|none`
    (its BaseName(): the base compared with the P6BaseA / P6BaseB properties), which decides on its own; an explicit
    `match=A|B|none` field is honoured too; a `baselocal=<plugin:hexid>` is mapped through plan.json's bases
    (`lvln_a` / `lvln_b`). "other" is a base that is neither entry; None when it cannot be told."""
    m = e.fields.get("match")
    if m is not None:
        m = m.upper()
        return m if m in ("A", "B") else "none"
    bl = e.fields.get("baselocal", "none")
    if bl.lower() == "none" or e.fields.get("base", "none").lower() == "none":
        return "none"
    bases = _plan_bases(plan)
    if bl.lower() in ("a", "b"):
        # The label is only the script's comparison with its own properties, so the logged runtime id must agree with
        # plan.json's base (Codex review of #431): a Starfield.esm base (load index 00) by its whole id, a base in
        # another plugin by its local id. No plan, no base mapping or a mismatch: cannot be told.
        ok = _is_plan_form(e, "base", bases.get(key_a if bl.lower() == "a" else key_b))
        return bl.upper() if ok else None
    if bl.lower() == "other":
        return "other"
    if bases.get(key_a) and bases.get(key_b):
        if bl.lower() == str(bases[key_a]).lower():
            return "A"
        if bl.lower() == str(bases[key_b]).lower():
            return "B"
    return None


def _conditioned_list(v: Verdict, evs: list[Event], kind: str, key: str, cases: dict, plan, pa, pb, readback_key,
                      ids: dict):
    """Shared P6/P7 judge: for each value in `cases` (value -> expected entry), 3 trials naming that entry. `ids` maps
    a trial line's form id field to the probe record's local id (the list and what its conditions read)."""
    trials = _by_kind(evs, kind)
    refused = [e for e in evs if e.kind == f"{kind} refused"]
    v.cite(*trials, *refused)
    if refused:
        v.reasons.append("the script refused: " + "; ".join(e.text for e in refused))
        return INCONCLUSIVE
    if not trials:
        v.reasons.append(f"no `{kind}` trial lines")
        return INCONCLUSIVE
    for value, want in cases.items():
        mine = [e for e in trials if _close(e.num(key), value)][-3:]     # the latest call's trials only
        if len(mine) < 3 or [e.num("trial") for e in mine] != [1.0, 2.0, 3.0]:
            v.reasons.append(f"{key}={value}: the latest trials are {[e.num('trial') for e in mine]}, want 1, 2, 3 "
                             "from one call")
            return INCONCLUSIVE
        for e in mine:
            # the script's properties must be the probe's own records, or a stale or foreign binding passes without
            # exercising our LVLN / KYWD / GLOB (Codex review of #431)
            bad = _foreign(e, ids)
            if bad:
                v.reasons.append(_foreign_reason(f"{key}={value}", e, bad, ids))
                return INCONCLUSIVE
            rb = e.num(readback_key)
            if rb is None:                          # no read-back, no proof the condition saw the value (Codex, #431)
                v.reasons.append(f"{key}={value}: a trial line carries no {readback_key}= read-back")
                return INCONCLUSIVE
            if not _close(rb, value):
                v.reasons.append(f"{key}={value}: readback {rb} differs ({readback_key})")
                return INCONCLUSIVE
            if kind == "p6" and e.form("loc") is None:     # the datum lives on the player's location
                v.reasons.append(f"{key}={value}: no loc= on the trial line, or loc=none")
                return INCONCLUSIVE
        got = [_base_match(e, plan, pa, pb) for e in mine]
        if any(g is None for g in got):
            v.reasons.append(f"{key}={value}: cannot tell which entry spawned (baselocal is neither a/b/other nor a "
                             f"plugin:id that plan.json's bases {pa}/{pb} name)")
            return INCONCLUSIVE
        if any(g == "none" for g in got):
            v.reasons.append(f"{key}={value}: a spawn resolved to no base")
            return FAIL
        if any(g == "other" for g in got):
            v.reasons.append(f"{key}={value}: a spawn resolved to a base that is neither entry A nor B")
            return FAIL
        if any(g != want for g in got):
            v.reasons.append(f"{key}={value}: expected entry {want}, got {got}")
            return FAIL
    v.reasons.append("every trial spawned the entry its condition selects: " +
                     ", ".join(f"{key}={k} -> {w}" for k, w in cases.items()))
    return PASS


def check_p6(c: Collection) -> Verdict:
    v = Verdict("p6", INCONCLUSIVE)
    v.extra["settles"] = "data-only territory spawns: LVLN entries conditioned on GetKeywordDataForCurrentLocation (P6)"
    if _skipped(c.plan, "lvln", "lvln_conditions_written"):
        v.reasons.append("the stage says the LVLN entry conditions could not be written (Mutagen): P6 blocked")
        v.extra["blocked"] = True
        return v
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    v.verdict = _conditioned_list(v, evs, "p6", "datum", {1.0: "A", 2.0: "B"}, c.plan, "lvln_a", "lvln_b", "readback",
                                 {"list": LOCAL["p6_list"], "holder": LOCAL["holder"]})
    return v


def check_p7(c: Collection) -> Verdict:
    v = Verdict("p7", INCONCLUSIVE)
    v.extra["settles"] = "conditions read our reputation global (P7 minimal form)"
    v.extra["p7b_vendor"] = {"status": "deferred",
                             "reason": "a vendor refusing service needs an NPC_ with VEND/PLVD, a merchant container "
                                       "and conditioned dialogue; no converter of ours produces them yet"}
    if _skipped(c.plan, "lvln", "lvln_conditions_written"):
        v.reasons.append("the stage says the LVLN entry conditions could not be written (Mutagen): P7 blocked")
        v.extra["blocked"] = True
        return v
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    v.verdict = _conditioned_list(v, evs, "p7", "tier", {3.0: "A", 9.0: "B"}, c.plan, "lvln_a", "lvln_b", "glob",
                                 {"list": LOCAL["p7_list"], "rep": LOCAL["p7_rep"]})
    return v


# ----------------------------------------------------------------------------------------------- P8

def check_p8(c: Collection) -> Verdict:
    v = Verdict("p8", INCONCLUSIVE)
    v.extra["settles"] = "build stages without player building: enable-parent swap and its save cost (P8)"
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    moves = _by_kind(evs, "p8 move")
    firsts = [e for e in moves if e.num("stage") == 0.0]
    if firsts:                                  # judge only the latest P8Move: an older run's lines never count
        evs = [e for e in evs if e.line >= firsts[-1].line]
    elif moves:
        evs = [e for e in evs if e.line >= moves[-1].line]
    move = _by_kind(evs, "p8 move")
    v.cite(*move)
    if not move:
        v.reasons.append("no `p8 move` line: the refs were not brought into the player's merged frame")
        return v
    # P8Move logs stage 0, 1, 2 in one call; a call that stopped early leaves stages unmoved (Codex review of #431).
    moved = [e.num("stage") for e in move]
    if moved[:3] != [0.0, 1.0, 2.0]:
        v.reasons.append(f"the latest P8Move logged stages {moved}, want 0, 1, 2: not every stage was moved")
        return v
    wrong = [k for k, e in enumerate(move[:3]) if _local(e, "parent") != LOCAL["p8_parent0"] + k]
    if wrong:                                   # the probe's own parents, by logged id (Codex review of #431)
        v.reasons.append(f"p8 move stage {wrong}: parent is not FOCC_P8_Stage<k>Parent (locals "
                         f"{LOCAL['p8_parent0']}..{LOCAL['p8_parent0'] + 2})")
        return v
    evs = [e for e in evs if e.line > move[2].line]
    stages = [e for e in evs if e.kind == "p8" and set(e.fields) == {"stage"}]      # `FOCC p8 stage=<s>`
    children = _by_kind(evs, "p8 child")
    v.cite(*stages, *children)
    if len(stages) < 3 or len(children) < 36:
        v.reasons.append(f"{len(stages)} stage lines and {len(children)} child lines, want 3 and 36")
        return v
    seq = [st.num("stage") for st in stages[-3:]]
    if seq != [1.0, 2.0, 0.0]:
        v.reasons.append(f"the last three stage commands were {seq}, the card asks for 1, 2, 0 in that order")
        return v
    stages = stages[-3:]
    children = [e for e in children if e.line > stages[0].line]
    failed, overlapped = [], []
    for i, st in enumerate(stages):
        s = st.num("stage")
        end = stages[i + 1].line if i + 1 < len(stages) else float("inf")
        rows = [e for e in children if st.line < e.line < end]
        if len(rows) != 12:
            v.reasons.append(f"stage={s}: {len(rows)} child lines, want 12")
            return v
        pairs = {(e.num("stage"), e.num("j")) for e in rows}
        if pairs != {(float(k), float(j)) for k in range(3) for j in range(4)}:   # every child once (Codex, #431)
            v.reasons.append(f"stage={s}: the child lines do not name each of the 12 children once")
            return v
        for e in rows:
            k, dis, pdis = e.num("stage"), e.flag("disabled"), e.flag("parent_disabled")
            if dis is None or pdis is None:
                v.reasons.append(f"stage={s}: child line without disabled/parent_disabled")
                return v
            j = e.num("j")
            if k is None or j is None or _local(e, "id") != LOCAL["p8_child0"] + 4 * int(k) + int(j):
                v.reasons.append(f"stage={s}: child k={k} j={j} id={e.fields.get('id')} is not FOCC_P8_Child_<k>_<j>")
                return v
        # Owner's PC, 28 Oct 2026: the three P8Stage calls ran from one console session, Utility.Wait(1.0) does not
        # count down while the console is open, so every readout saw the last call's parents (stage 0's layout).
        # Parents in the layout of a stage commanded later mean the calls overlapped: nothing was measured.
        layout = {}
        for e in rows:
            layout.setdefault(int(e.num("stage")), set()).add(e.flag("parent_disabled"))
        later = [t.num("stage") for t in stages[i + 1:]]
        stale = False
        if all(len(x) == 1 for x in layout.values()):
            seen = tuple(next(iter(layout[k])) for k in range(3))
            if seen != tuple(k != s for k in range(3)) and any(seen == tuple(k != t for k in range(3)) for t in later):
                overlapped.append(f"stage={s} read in a later stage's layout (parents disabled {list(seen)})")
                stale = True
        for e in rows:
            k, dis, pdis = e.num("stage"), e.flag("disabled"), e.flag("parent_disabled")
            if dis != pdis:                         # a child against its own parent counts in any readout
                failed.append(f"stage={s} child k={k} j={e.num('j')}: disabled={dis} but parent_disabled={pdis}")
            elif not stale and dis != (k != s):
                failed.append(f"stage={s} child k={k} j={e.num('j')}: disabled={dis}, expected {k != s}")
    if failed:
        v.reasons.append("enable parents not honoured: " + "; ".join(failed[:6]))
        v.verdict = FAIL
        return v
    if overlapped:
        v.extra["overlapping_stage_calls"] = overlapped
        v.reasons.append("every child follows its parent, but " + "; ".join(overlapped) + ": the P8Stage calls "
                         "overlapped (Utility.Wait does not count down while the console is open), so the swaps were "
                         "not measured. Run each P8Stage with the console closed for about 3 s in between")
        return v
    v.reasons.append("all 36 child lines follow their parent's state across the three stage swaps")
    if c.saves is None:
        v.reasons.append("saves.json missing")
        return v
    v.verdict = _growth(v, save_sizes(c.saves), "focc_p8_before", "focc_p8_after")
    return v


# ----------------------------------------------------------------------------------------------- P9

P9_RESULTS = {0: "Success", 1: "Failure", 2: "Stopped", 3: "Cleared", 4: "Timeout"}   # Actor.psc PathingResult_* (PC, 28 Oct 2026)


def _p9_result_note(attempt: dict) -> str:
    """The return code FOCC_P9Drive logs as result= since 28 Oct 2026 (Starfield's Actor.psc, line 490: PathToReference
    returns an int, latent; 1 Failure is an unsuccessful request, 2 Stopped and 4 Timeout a walk that did not finish).
    These codes alone do not isolate a navmesh fault. Missing result= retains the legacy note."""
    r = attempt.get("path_result")
    if r is None:
        if attempt.get("path_result_raw") is not None:
            return f" with invalid result={attempt['path_result_raw']}"
        return " (no result= on the line: a driver from before 28 Oct 2026)"
    return f" with result {r} ({P9_RESULTS.get(r, 'unknown code')})"


def _p9_returned(evs: list[Event], go: Event) -> Event | None:
    """The `p9 path returned` of a `p9 go`: the same actor and call= (the call's start time) after it, or None.
    FOCC_P9Drive.Go's call is latent, so its return may land after the rung's `p9 done`, the next start or the next go."""
    call = go.fields.get("call")
    if not call:
        return None
    for e in evs:
        if e.line <= go.line:
            continue
        if e.kind != "p9 path returned":
            # A malformed timestamp must not turn an explicit return into a legacy missing one.
            text = re.sub(r"^((?:\[[^\]]*\]\s*)?FOCC)\s+rt=\S+\s+(?=p9 path returned\b)", r"\1 ", e.text)
            e = parse_line(text, e.file, e.line) if text != e.text else None
        if e is not None and e.kind == "p9 path returned" and e.fields.get("call") == call \
                and e.form("actor") == go.form("actor"):
            return e
    return None


def _p9_continuous(samples: list[Event], origin: Event) -> bool | None:
    """Whether a rung's samples read as one continuous, loaded walk from its origin (the `p9 go` when the script sent
    the actor, else the `p9 start`), by the latest rung's own checks: the origin carries rt= and dist=; each sample
    carries rt=, pos=, dist= and a readable loaded=; the first sample is no earlier than the origin and no closer than
    a walk gets in the time since it (p9_stuck_m plus p9_jump_m_per_s per second); real time strictly increasing; no
    step faster than p9_jump_m_per_s; loaded=True in at least half the samples. Applied to a control before it may
    stand as proof that the command walks the actor: a control that could not pass the judged rung's own checks cannot
    decide that the judged rung failed (Codex review of #560). None with fewer than 2 samples."""
    P = PLACEHOLDERS
    if len(samples) < 2:
        return None
    if origin.rt is None or origin.num("dist") is None:
        return False
    rows = [(e.rt, pos(e), e.num("dist"), e.flag("loaded")) for e in samples]
    if any(None in r for r in rows):
        return False
    t0, _, d0, _ = rows[0]
    if t0 < origin.rt or abs(origin.num("dist") - d0) > P["p9_stuck_m"] + P["p9_jump_m_per_s"] * (t0 - origin.rt):
        return False
    for (t0, p0, _, _), (t1, p1, _, _) in zip(rows, rows[1:]):
        if t1 <= t0 or sum((a - b) ** 2 for a, b in zip(p0, p1)) ** 0.5 / (t1 - t0) > P["p9_jump_m_per_s"]:
            return False
    return sum(1 for r in rows if r[3] is True) / len(rows) >= 0.5


def _p9_attempts(evs: list[Event], starts: list[Event]) -> list[dict]:
    """One summary per `p9 start` in the log, oldest first: the ladder's rungs. A start's track is the started actor's
    samples up to its own `p9 done` or the next start. driver "script" when FOCC_P9Drive.Go sent this actor inside the
    track (its `p9 go` after the start and before the done), else None: a console command, or none, leaves no line. When
    the script sent it, only the samples after the go count: where the actor stood before the command says nothing about
    the command, and a go after the done commanded nothing the track saw (Codex review of #560). Readings only; the
    verdict is the latest start's."""
    P = PLACEHOLDERS
    out = []
    for k, s in enumerate(starts):
        end = starts[k + 1].line if k + 1 < len(starts) else None
        part = [e for e in evs if e.line > s.line and (end is None or e.line < end)]
        done = _by_kind(part, "p9 done")[:1]
        track_end = done[0].line if done else end
        go = next((e for e in _by_kind(part, "p9 go") if e.form("actor") == s.form("actor")
                   and (track_end is None or e.line < track_end)), None)
        back = _p9_returned(evs, go) if go is not None else None
        samples = [e for e in _by_kind(part, "p9 sample")
                   if (not done or e.line < done[0].line) and e.form("actor") == s.form("actor")
                   and (go is None or e.line > go.line)]
        dists = [d for d in (e.num("dist") for e in samples) if d is not None]
        ps = [p for p in (pos(e) for e in samples) if p is not None]
        dest = [e for e in evs if e.kind == "p9 dest" and e.line < s.line][-1:]
        start = s.num("dist")
        # The distance the command found the actor at: the go line's dist= when the script sent it (what the actor
        # did between the start and the go was not the command's doing; Codex review of #560), else the start's.
        cmd = go.num("dist") if go is not None else None
        base = cmd if cmd is not None else start
        closest = min(dists, default=None)
        # Every explicit return ends its request, including Success. Retain the full track
        # for diagnostics, but never credit later wandering as approach or arrival.
        command_samples = samples
        if back is not None and "result" in back.fields:
            command_samples = [e for e in samples if e.rt is not None and back.rt is not None
                               and go.rt is not None and go.rt <= e.rt <= back.rt]
        command_dists = [e.num("dist") for e in command_samples if e.num("dist") is not None]
        command_closest = min(command_dists, default=None)
        command_approach = base - min([base] + command_dists) if base is not None else None
        state = [e for e in part if go is not None and e.line < go.line and e.kind == "p9 state"
                 and e.form("actor") == s.form("actor")][-1:]
        state_ok = (state[-1].flag("loaded") is True and all(state[-1].flag(key) is False
                    for key in ("dead", "disabled", "targetdisabled"))) if state else None
        out.append({"line": s.line, "rt": s.rt, "actor": s.form("actor"), "start_dist_m": start,
                    "go_dist_m": cmd,
                    "seconds": s.num("seconds"), "samples": len(samples), "done": bool(done),
                    "dest_ok": bool(dest) and _local(dest[-1], "id") == LOCAL["p9_dest"],
                    "closest_m": closest,
                    "approach_m": round(base - closest, 1) if None not in (base, closest) else None,
                    "command_approach_m": command_approach,
                    "command_closest_m": command_closest,
                    "moved_m": round(max(sum((a - b) ** 2 for a, b in zip(ps[0], p)) ** 0.5 for p in ps), 1) if ps else None,
                    "cells": len({e.form("cell") for e in samples if e.form("cell")}),
                    "arrived": command_closest is not None and command_closest < P["p9_arrive_m"],
                    "state_ok": state_ok,
                    "continuous": _p9_continuous(samples, go if go is not None else s),
                    "driver": "script" if go is not None else None,
                    "go_line": go.line if go is not None else None,
                    "go_rt": go.rt if go is not None else None,
                    "target": go.fields.get("target") if go is not None else None,
                    "go_id": go.form("id") if go is not None else None,
                    # True when the go named the tracked destination itself (target=dest with the `p9 dest` line's id):
                    # P9Sample measures the distance to FOCC_P9_Dest, so a go aimed anywhere else (the player, another
                    # reference) is not the route the samples describe (Codex bot on 8dbfef8d)
                    "to_dest": (go.fields.get("target") == "dest" and bool(dest) and go.form("id") is not None
                                and go.form("id") == dest[-1].form("id")) if go is not None else None,
                    "path_returned_s": back.num("after") if back is not None else None,
                    "path_return_line": back.line if back is not None else None,
                    "path_return_rt": back.rt if back is not None else None,
                    "path_result_raw": back.fields.get("result") if back is not None else None,
                    "path_succeeded": (back.count("result") == 0
                                       if back is not None and "result" in back.fields else None),
                    "path_result": back.count("result") if back is not None else None})
    return out


def _p9_driver(attempts: list[dict], actor, driver=None) -> str | None:
    """Why the log shows the command walking this actor, from the ladder's short rungs before the judged one, else None.
    Only the scripted driver can show it: a `p9 go` inside a rung's track is the command's receipt and the samples after
    it the answer. A console command leaves no line, so a rung without a go may be the actor's own wander (N1c drifted
    14 m) and neither stands as the control nor is judged against one (Codex review of #560). The first rung started
    within p9_control_m is the baseline (no go): it must have samples and not have arrived. The control is a later
    scripted rung whose go found the actor between p9_control_min_m and p9_control_m out and that arrived after the go
    through continuous samples (`continuous`: readings complete, time increasing, no teleport-fast step, loaded): an actor
    already under the arrival distance when commanded arrived on its own, whatever its start line said, and a jump to
    the destination is a setup fault, not the command walking (Codex review of #560). The control's go names the player
    (who stands at the destination for that rung, per the card) or the tracked destination itself (`to_dest`); a go to
    another reference commanded a different walk than the one the samples measure. Each a finished track of the same
    actor to FOCC_P9_Dest. A recorded unsuccessful request cannot qualify as the successful control."""
    P = PLACEHOLDERS
    if driver != "script":
        return None
    cands = [a for a in attempts[:-1] if a["done"] and a["dest_ok"] and a["actor"] == actor]
    base = next((a for a in cands if a["start_dist_m"] is not None and a["start_dist_m"] <= P["p9_control_m"]), None)
    if base is None or base["closest_m"] is None or base["arrived"] or base["driver"] is not None:
        return None
    ctl = next((a for a in cands if a["line"] > base["line"] and a["driver"] == "script" and a["go_dist_m"] is not None
                and P["p9_control_min_m"] <= a["go_dist_m"] <= P["p9_control_m"] and a["arrived"]
                and a["path_succeeded"] is not False
                and a["state_ok"] is not False
                and a["continuous"] is True and (a["target"] == "player" or a["to_dest"] is True)), None)
    if ctl is None:
        return None
    return (f"the baseline rung (line {base['line']}) stayed {base['closest_m']:.1f} m or more away and the scripted "
            f"commanded rung (line {ctl['line']}) came from {ctl['go_dist_m']:.1f} m at its `p9 go` to "
            f"{ctl['closest_m']:.1f} m after it")


def check_p9(c: Collection) -> Verdict:
    v = Verdict("p9", INCONCLUSIVE)
    v.extra["settles"] = "long-route pathing on the converted navmesh over >= 4 exterior cells (P9)"
    P = PLACEHOLDERS
    v.extra["placeholders"] = {k: P[k] for k in P if k.startswith("p9_")}
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    starts = _by_kind(evs, "p9 start")
    if not starts:                              # no attempt boundary, no verdict (Codex review of #431)
        v.reasons.append("no `p9 start` line: the samples cannot be tied to one walk to the destination")
        return v
    attempts = _p9_attempts(evs, starts)        # the ladder's rungs, for the record (docs/spikes/combined-core-probes.md)
    v.extra["attempts"] = attempts
    latest = attempts[-1]
    driver = latest["driver"]
    v.extra["driver"] = ("FOCC_P9Drive.Go (Actor.PathToReference from Papyrus)" if driver
                         else "none logged (a console command, or none)")
    if latest["path_return_line"] is not None:
        elapsed = (f"after {latest['path_returned_s']:.1f} s" if latest["path_returned_s"] is not None
                   else "with unreadable after=")
        v.reasons.append(f"FOCC_P9Drive's PathToReference returned {elapsed}{_p9_result_note(latest)}")
        v.cite(*[e for e in evs if e.line == latest["path_return_line"]])
    # judge only the latest attempt: a retry in one launch drops the old one
    dest = [e for e in _by_kind(evs, "p9 dest") if e.line < starts[-1].line][-1:]   # P9Dest runs before P9Track
    evs = [e for e in evs if e.line >= starts[-1].line]
    done = _by_kind(evs, "p9 done")[:1]         # the tracker's own done closes it: later samples never count
    # When the script sent the actor, the walk starts at its `p9 go`: earlier samples show an actor not yet commanded
    # (Codex review of #560), and the clock below runs from the go's rt=.
    go_line = latest["go_line"]
    samples = [e for e in _by_kind(evs, "p9 sample") if (not done or e.line < done[0].line)
               and (go_line is None or e.line > go_line)]
    origin = latest["go_rt"] if go_line is not None else starts[-1].rt
    v.cite(*dest, *done)
    if not dest:
        v.reasons.append("no `p9 dest` line")
        return v
    if _local(dest[-1], "id") != LOCAL["p9_dest"]:  # the probe's own destination (Codex review of #431)
        v.reasons.append(f"p9 dest id {dest[-1].fields.get('id')} is not FOCC_P9_Dest (local {LOCAL['p9_dest']})")
        return v
    actor = starts[-1].form("actor")
    if actor is None:
        v.reasons.append("p9 start names no actor")
        return v
    if go_line is not None and latest["to_dest"] is not True:
        # P9Sample measures the distance to FOCC_P9_Dest, so a go aimed at the player (`Go <id> 1`, the control's form)
        # or at another reference commanded a different walk than the samples describe: its distance, clock and the
        # ladder's proof say nothing about the route to the destination (Codex bot on 8dbfef8d)
        v.cite(*[e for e in evs if e.line == go_line])
        v.reasons.append(f"the judged rung's `p9 go` targets {latest['target'] or 'nothing named'} (id "
                         f"{latest['go_id'] or 'none'}), not the tracked FOCC_P9_Dest (id {dest[-1].form('id')}): "
                         f"P9Track measures the distance to the destination, so this command's walk is not the route "
                         f"judged here (the long rungs take `FOCC_P9Drive.Go <actor> 0`)")
        return v
    if latest["state_ok"] is False:
        v.reasons.append("the logged p9 state does not establish a loaded, living, enabled actor and enabled target: "
                         "setup problem, not pathing evidence")
        return v
    others = [e for e in samples if e.form("actor") != actor]
    if others:                                  # every sample is the started actor's (Codex review of #431)
        v.cite(*others[:3])
        v.reasons.append(f"{len(others)} p9 sample line(s) name another actor than the start's "
                         f"{starts[-1].fields.get('actor')}")
        return v
    if origin is None or any(e.rt is None for e in samples):
        v.reasons.append("a p9 start, go or sample line carries no rt=: the walk's real time is unknown")
        return v
    rows = []
    for e in samples:
        # real seconds since the start (the go, when scripted), not the script's nominal t: late timers must not
        # shorten the walk (Codex review of #431)
        t = e.rt - origin
        if t < 0:                               # a sample before its start is not this walk (Codex review of #431)
            v.cite(starts[-1], e)
            v.reasons.append(f"a p9 sample is timed {t:.1f} s before the {'go' if go_line is not None else 'start'}")
            return v
        d, p, cell, loaded = e.num("dist"), pos(e), e.form("cell"), e.flag("loaded")
        if None in (d, p) or loaded not in (True, False):   # a gap would hide a stall (Codex review of #431)
            v.cite(e)
            v.reasons.append("a p9 sample lacks a parsable dist=, pos= or loaded= reading")
            return v
        rows.append((t, d, p, cell, loaded, e))
    if len(rows) < 2:
        v.reasons.append("fewer than 2 parsable `p9 sample` lines")
        return v
    v.cite(rows[0][5], rows[-1][5])
    if not done:
        v.reasons.append("no `p9 done` line: the tracker did not finish")
        return v
    # The route's length is the distance at the command: the go's dist= when the script sent the actor, else the
    # start's (P9Track logs it just before its first sample; Codex reviews of #431 and #560).
    start = latest["go_dist_m"] if go_line is not None else starts[-1].num("dist")
    # The first counted sample may be as much closer as a walk covers in the time since the origin: P9Track's own
    # first sample precedes the go, so after a go the first counted one is about 2 s later (Codex review of #560).
    slack = P["p9_stuck_m"] + P["p9_jump_m_per_s"] * rows[0][0]
    if start is None or abs(start - rows[0][1]) > slack:
        v.cite(starts[-1], rows[0][5])
        v.reasons.append(f"p9 {'go' if go_line is not None else 'start'} dist={start} is missing or disagrees with the "
                         f"first sample's {rows[0][1]} m ({rows[0][0]:.1f} s later)")
        return v
    v.extra["start_dist_m"] = start
    v.extra["start_dist_from"] = "p9 go" if go_line is not None else "p9 start"
    if start < P["p9_start_m"]:
        v.reasons.append(f"start dist {start} m < {P['p9_start_m']} (the card asked for 450)")
        return v
    loaded_share = sum(1 for r in rows if r[4] is True) / len(rows)
    v.extra["loaded_share"] = round(loaded_share, 3)
    if loaded_share < 0.5:
        v.reasons.append(f"loaded=True in only {loaded_share:.0%} of samples: the actor unloaded (setup problem)")
        return v
    # Continuity: a jump faster than a walk between two samples is a teleport, never a pass for pathing.
    for (t0, _, p0, _, _, e0), (t1, _, p1, _, _, e1) in zip(rows, rows[1:]):
        dt = t1 - t0
        if dt <= 0:                             # repeated or backward time cannot show a walk (Codex review of #431)
            v.cite(e0, e1)
            v.reasons.append(f"p9 sample real times are not strictly increasing ({t0} then {t1} s after the start)")
            return v
        step = sum((a - b) ** 2 for a, b in zip(p0, p1)) ** 0.5
        if step / dt > P["p9_jump_m_per_s"]:
            v.cite(e0, e1)
            v.reasons.append(f"a {step:.1f} m jump in {dt:.1f} s between samples: teleport-like, not a continuous "
                             f"walk (placeholder {P['p9_jump_m_per_s']} m/s)")
            return v
    # Samples after the latent request returned describe the actor's later behaviour.
    # They cannot prove arrival, cell crossings or a stall during that request.
    if latest["path_result_raw"] is not None:
        end = latest["path_return_rt"]
        rows = [r for r in rows if end is not None and r[5].rt <= end]
        if len(rows) < 2:
            v.reasons.append("fewer than 2 samples before the explicit path return; later movement is not this request")
            return v
    cells = {r[3] for r in rows if r[3]}
    v.extra["distinct_cells"] = len(cells)
    first_cell = rows[0][3]
    arrived = [r for r in rows if r[1] < P["p9_arrive_m"] and r[0] <= P["p9_seconds"]]
    approach = start - min(r[1] for r in rows)
    moved = max(sum((a - b) ** 2 for a, b in zip(rows[0][2], r[2])) ** 0.5 for r in rows)
    v.extra["approach_m"], v.extra["moved_m"] = round(approach, 1), round(moved, 1)
    # A FAIL is a failed route test, so it needs proof the command moves this actor at all: progress
    # on this route, or the ladder's short control. Without it a still actor is the command's failure as much as the
    # path's (28 Oct: 600 s within about 3 m; no console command had ever walked a calm citizen beyond its own wander,
    # docs/actors/npc-navigation.md section 5)
    command_approach = latest["command_approach_m"]
    shown = (f"it came {command_approach:.1f} m closer on this route"
             if command_approach is not None and command_approach >= P["p9_progress_m"]
             else _p9_driver(attempts, actor, driver))
    failed = None
    if len(cells) <= 1 and rows[-1][0] >= P["p9_seconds"]:
        failed = ([], f"the actor never left its first cell {first_cell} within {P['p9_seconds']} s")
    else:
        # Stuck: dist within 2 m of a value for 120 s while loaded.
        anchor = rows[0]
        for r in rows:
            if abs(r[1] - anchor[1]) > P["p9_stuck_m"] or r[4] is not True:
                anchor = r
            elif r[0] - anchor[0] >= P["p9_stuck_s"]:
                failed = ([anchor[5], r[5]], f"dist stayed within {P['p9_stuck_m']} m of {anchor[1]:.1f} for "
                                             f"{r[0] - anchor[0]:.0f} s while loaded: stuck")
                break
    if failed:
        v.cite(*failed[0])
        v.reasons.append(failed[1])
        if latest["path_result_raw"] is not None and latest["path_result"] != 1:
            v.reasons.append("the path request ended without an explicit Failure result; an interrupted, invalid or "
                             "inconsistent return does not establish a navmesh failure")
            return v
        if shown:
            v.reasons.append(f"the command does move this actor: {shown}")
            v.verdict = FAIL
        else:
            v.reasons.append(f"but the actor came at most {approach:.1f} m closer (moved {moved:.1f} m at most) and no "
                             f"ladder rung in this log shows the command walking it (a baseline rung within "
                             f"{P['p9_control_m']:g} m with no `p9 go` that stayed away, then a scripted one, its "
                             f"`p9 go` inside its track finding it {P['p9_control_min_m']:g} m or more out, aimed at "
                             f"the player or at the destination, that arrived after that go through continuous "
                             f"samples; a console command leaves no line and never stands as the control): the "
                             f"command cannot be told from the navmesh")
        return v
    if latest["path_succeeded"] is False:
        v.reasons.append("the logged path request did not succeed; later movement cannot establish a successful "
                         "commanded route")
        return v
    if not arrived:
        v.reasons.append(f"dist never fell below {P['p9_arrive_m']} m within {P['p9_seconds']} s (last {rows[-1][1]} m)")
        return v
    if len(cells) < P["p9_min_cells"]:
        v.reasons.append(f"only {len(cells)} distinct cells among the samples, want {P['p9_min_cells']}")
        return v
    v.cite(arrived[0][5])
    v.extra["arrived_at_s"] = arrived[0][0]
    v.reasons.append(f"walked from {start:.0f} m to under {P['p9_arrive_m']} m in {arrived[0][0]:.0f} s through "
                     f"{len(cells)} cells with no jump")
    v.verdict = PASS
    return v


# ----------------------------------------------------------------------------------------------- P10

def sendstoryevent_compiles(files: dict, plan: dict | None):
    """True when the staged FOCC_Probe.psc calls SendStoryEvent and the stage's receipts say FOCC_Probe compiled;
    False when the receipts show the compile failed; None when either file is missing."""
    psc = files.get("FOCC_Probe.psc")
    if psc is None or "SendStoryEvent" not in psc:
        return None
    if plan:
        comp = plan.get("compiled")
        if isinstance(comp, dict) and "FOCC_Probe" in comp:
            return bool(comp["FOCC_Probe"])
        outs = plan.get("sha256") or plan.get("outputs") or {}
        if isinstance(outs, dict) and any(k.replace("\\", "/").endswith("Scripts/FOCC_Probe.pex") for k in outs):
            return True
    oc = files.get("offline_check.txt")
    if oc is None:
        return None
    for block in re.split(r"\n(?=\S)", oc):
        if "FOCC_Probe.psc" in block or "FOCC_Probe " in block:
            if "Compilation succeeded" in block:
                return True
            if "failed" in block.lower() or "error" in block.lower():
                return False
    return None


def check_p10(c: Collection) -> Verdict:
    v = Verdict("p10", INCONCLUSIVE)
    v.extra["settles"] = "event plumbing: Keyword.SendStoryEvent compiles; our SM branch starts our quest (P10)"
    v.extra["sendstoryevent_compiles"] = sendstoryevent_compiles(c.files, c.plan)
    if _skipped(c.plan, "sm", "sm_nodes_written"):
        v.reasons.append("the stage says the SMBN/SMQN nodes were not written: only the compile verdict is given")
        v.extra["blocked"] = True
        return v
    evs = c.session(1)
    if evs is None:
        v.reasons.append("no log (focc.0.log)")
        return v
    sent = _by_kind(evs, "p10 sent")
    started = _by_kind(evs, "p10 quest started")
    state = _by_kind(evs, "p10 state")
    v.cite(*sent, *started, *state)
    if not sent:
        v.reasons.append("no `p10 sent` line")
        return v
    s = sent[-1]
    if _local(s, "event") != LOCAL["p10_event"]:   # the probe's own keyword was sent (Codex review of #431)
        v.reasons.append(f"p10 sent event={s.fields.get('event')} is not FOCC_P10_Event (local {LOCAL['p10_event']})")
        return v
    if s.flag("result") is False:           # older stages logged a bool result; Starfield's is not a bool (2d53642)
        v.reasons.append("SendStoryEvent returned False")
        v.verdict = FAIL
        return v
    # Only lines whose logged id is FOCC_P10_Quest count: local=2080 is a literal the scripts print (Codex, #431).
    ours = [e for e in started if _local(e, "id") == LOCAL["p10_quest"]]
    after = [e for e in ours if e.line > s.line]
    before = [e for e in ours if e.line < s.line]
    state = [e for e in state if _local(e, "id") == LOCAL["p10_quest"]]
    running = state[-1].flag("running") if state and state[-1].line > s.line else None
    pre = [e for e in state if e.line < s.line]
    if after:
        e = after[0]
        # IsRunning counts only when read after that OnQuestInit; an earlier read says nothing (Codex review of #431).
        running = state[-1].flag("running") if state and state[-1].line > e.line else None
        if s.rt is None or e.rt is None:        # no times, no proof the send started it (Codex review of #431)
            v.reasons.append("the p10 sent or quest started line carries no rt=: the start window cannot be checked")
            return v
        if not 0 <= e.rt - s.rt <= PLACEHOLDERS["p10_start_window_s"]:
            v.reasons.append(f"the quest started {e.rt - s.rt:.1f} s after the send, outside the placeholder "
                             f"0 to {PLACEHOLDERS['p10_start_window_s']} s window")
            return v
        if running is False:
            v.reasons.append("OnQuestInit fired but IsRunning read False afterwards")
            v.verdict = FAIL
            return v
        if running is None:
            v.reasons.append("SendStoryEvent ran and FOCC_P10_Quest's OnQuestInit fired, but there is no "
                             "`p10 state` line after the send: run cgf \"FOCC_Probe.P10State\" (the card's PASS needs "
                             "running=True)")
            return v
        v.reasons.append("SendStoryEvent ran, FOCC_P10_Quest's OnQuestInit fired and IsRunning is True")
        v.verdict = PASS
        return v
    # The latest word before the send decides: a start line or running=True means the quest was already running,
    # a running=False read after the last start means it had stopped and could be started again (Codex, #557).
    last = max(before + pre, key=lambda e: e.line, default=None)
    if last is not None and (last.kind == "p10 quest started" or last.flag("running") is True):
        # Owner's PC, 28 Oct 2026: OnQuestInit logged at rt 59.1, the send at rt 103.5. A quest already running
        # cannot be started by the send, so the run says nothing about our branch.
        e = last
        v.extra["running_before_send"] = {"line": e.line, "rt": e.rt}
        v.reasons.append(f"FOCC_P10_Quest was already running before the send (line {e.line}, rt {e.rt}; the send "
                         f"is line {s.line}, rt {s.rt}): something else started it, so this run cannot show what the "
                         "send does")
        return v
    if running is False:
        v.reasons.append("SendStoryEvent ran, the quest did not start after it, and IsRunning is False")
        v.verdict = FAIL
        return v
    if running is True:
        v.reasons.append("SendStoryEvent ran and FOCC_P10_Quest is running, but no `p10 quest started` line follows "
                         "the send: what started it is not shown")
        return v
    v.reasons.append("SendStoryEvent ran; no `p10 quest started` line and no `p10 state` line follow it")
    return v


# ----------------------------------------------------------------------------------------------- B0

B0_PONG = 7                 # dotnet/CombinedProbe: GMST iFOCC_Pong (0x855), int 7, as the stage writes it


def check_b0(c: Collection) -> Verdict:
    """B0, the plugin bridge spike (docs/combined-core-cpp-port.md section 4; runbook section B0), from the `b0` lines of
    the one-launch log (focc_session1.log, else focc.0.log, else any log holding `b0` lines). B0-1: Papyrus reads the probe plugin's own game setting (`b0 gmst name=iFOCC_Pong
    value=7`, FOCC_B0.Gmst; no SFSE plugin). B0-2: a value crosses into the plugin and back, on the native route as a
    `b0 pong sent=N got=N+1` after the `b0 ping sent=N` (FOCC.Ping bound by FOCCPing.dll, stack A) or on the setting
    route as a `b0 gmst` after the ping reading N+1 (the plugin wrote the setting by its name, stack B). The last ping
    is judged (a save and a load between pings is the card's persistence check; every ping's answer is in `extra`).
    A ping's window runs to the next ping (or the log's end): its pong and its setting reads are taken from there, any
    read of N+1 in the window is the answer (a read that came too early shows the old value and is harmless), and a
    window whose reads all show the value held before the ping is "unchanged" (nothing wrote the setting: nothing does
    on stack A, and on stack B the bridge did not answer), which settles nothing rather than counting as a wrong answer.
    A setting answer counts only when it is fresh: N+1 must differ from the value the setting held before the ping
    (the last `b0 gmst` before it), or the read after the ping is the stale value and settles nothing (Codex review of
    #568: `gmst 7, ping 6, gmst 7` and a repeated `Ping 41` after a 42 are not answers). The first gmst read must come
    before the first ping of the launch, since B0-1 reads the stage's 7 and a read after a ping on stack B is the
    plugin's answer. PASS = B0-1 and one route. INCONCLUSIVE = B0-1 alone, a ping with neither answer readable, a stale
    setting answer, an unchanged setting, or a first read after a ping. FAIL = the first gmst read is not 7 (0 = the
    setting is unknown to the game), or the native answered wrong and the setting changed to a wrong value too."""
    v = Verdict("b0", INCONCLUSIVE)
    v.extra["settles"] = "a value crosses from Papyrus into the SFSE plugin and back on 1.16.244 (B0)"
    evs = c.session(1)
    if evs is None or not any(e.kind.split()[:1] == ["b0"] for e in evs):
        evs = next((log for log in c.any_logs() if any(e.kind.split()[:1] == ["b0"] for e in log)), None)
    if evs is None:
        v.reasons.append("no `b0` line in any log: FOCC_B0 was not run")
        return v
    gmst, pings, pongs = _by_kind(evs, "b0 gmst"), _by_kind(evs, "b0 ping"), _by_kind(evs, "b0 pong")
    refused = _by_kind(evs, "b0 refused")
    if not gmst and not pings:
        v.cite(*refused[:1])
        v.reasons.append("FOCC_B0 found no probe quest (refused quest=none): the probe plugin is not loaded" if refused
                         else "no `b0 gmst` or `b0 ping` line")
        return v
    if not gmst:
        v.reasons.append("no `b0 gmst` line before the ping: run FOCC_B0.Gmst first (B0-1)")
        return v
    first = gmst[0]
    if pings and first.line > pings[0].line:
        v.cite(pings[0], first)
        v.reasons.append(f"the first `b0 gmst` read (line {first.line}) comes after the first `b0 ping` (line "
                         f"{pings[0].line}): run FOCC_B0.Gmst before the first ping of each launch (every launch rewrites "
                         "focc.0.log), since B0-1 reads the stage's 7 and a read after a ping on stack B is the plugin's answer")
        return v
    value = first.count("value")
    v.cite(first)
    v.extra["gmst_first"] = value
    if value is None:
        v.reasons.append("the first `b0 gmst` line has no readable value=, so B0-1 cannot be read (a torn line): run "
                         "FOCC_B0.Gmst again")
        return v
    if value != B0_PONG:
        v.verdict = FAIL
        v.reasons.append(f"Papyrus read iFOCC_Pong as {first.fields.get('value')}, not {B0_PONG}: the probe plugin's game "
                         f"setting did not reach Game.GetGameSettingInt (0 = a name the game does not know)")
        return v
    v.reasons.append(f"B0-1: Papyrus read the plugin's game setting iFOCC_Pong = {B0_PONG}")
    if not pings:
        v.reasons.append("no `b0 ping` line: the bridge itself was not tried (B0-2 waits for the SFSE plugin)")
        return v
    rounds = []
    for i, ping in enumerate(pings):
        sent = ping.count("sent")
        end = pings[i + 1].line if i + 1 < len(pings) else float("inf")     # this ping's window ends at the next ping
        pong = next((e for e in pongs if ping.line < e.line < end and e.count("sent") == sent), None)
        before = [e for e in gmst if e.line < ping.line][-1]          # exists: the first read precedes the first ping
        values = [e.count("value") for e in gmst if ping.line < e.line < end]
        got = pong.count("got") if pong is not None else None
        held = before.count("value")
        expect = sent + 1 if sent is not None else None
        fresh = (expect != held) if None not in (expect, held) else None
        readable = [x for x in values if x is not None]
        if expect is not None and expect in readable:
            read = expect                                           # the answer, wherever it is in the window
            setting_ok = True if fresh is True else None            # the stale value, or an unreadable one before: no answer
        elif not readable or expect is None:
            read, setting_ok = (readable[-1] if readable else None), None
        else:
            read = readable[-1]                                     # the setting's last state in the window
            setting_ok = None if held is None or read == held else False   # unchanged (or no held value to compare): no answer
        rounds.append({"line": ping.line, "sent": sent, "native_got": got, "gmst_before": held, "gmst_after": read,
                       "gmst_reads": values, "fresh": fresh,
                       "native_ok": (got == expect) if None not in (got, expect) else None, "setting_ok": setting_ok})
    v.extra["pings"] = rounds
    last = rounds[-1]
    ping = pings[-1]
    v.cite(ping, *[e for e in pongs if e.line > ping.line][:1],
           *([e for e in gmst if e.line > ping.line and e.count("value") == last["gmst_after"]] or
             [e for e in gmst if e.line > ping.line])[:1])
    if last["sent"] is None:
        v.reasons.append("the last `b0 ping` has no readable sent=")
        return v
    if last["native_ok"] is True:
        v.reasons.append(f"B0-2, native route: FOCC.Ping({last['sent']}) answered {last['native_got']} "
                         f"({sum(1 for r in rounds if r['native_ok'])} of {len(rounds)} pings answered sent + 1)")
        v.verdict = PASS
    if last["setting_ok"] is True:
        v.reasons.append(f"B0-2, setting route: iFOCC_Pong read {last['gmst_after']} after the ping of {last['sent']}")
        v.verdict = PASS
    if v.verdict == PASS:
        return v
    if last["native_ok"] is False:
        v.reasons.append(f"FOCC.Ping({last['sent']}) answered {last['native_got']}, not {last['sent'] + 1}"
                         + (": no plugin bound the native (Papyrus.0.log names it) or it answered wrong"
                            if last["native_got"] == 0 else ""))
    else:
        v.reasons.append("no `b0 pong` with a readable got= after the last ping")
    if last["setting_ok"] is False:
        v.reasons.append(f"iFOCC_Pong read {last['gmst_after']} after the ping of {last['sent']}, not {last['sent'] + 1} and "
                         f"not the {last['gmst_before']} it held before the ping: something wrote a wrong value")
        v.verdict = FAIL if last["native_ok"] is False else INCONCLUSIVE
    elif last["gmst_after"] is None:
        v.reasons.append("no `b0 gmst` read after the last ping: the setting route was not read (run FOCC_B0.Gmst after "
                         "the ping on stack B); on stack A the native answer above is the finding once the plugin's log "
                         "shows it loaded")
    elif last["gmst_after"] == last["gmst_before"] and last["gmst_after"] != last["sent"] + 1:
        v.reasons.append(f"iFOCC_Pong still reads {last['gmst_after']} after the ping of {last['sent']}, the value it held "
                         f"before the ping: nothing wrote the setting (nothing does on stack A; on stack B the bridge did "
                         f"not answer), so the setting route settles nothing; on stack A the plugin's own log says whether "
                         f"the dll loaded at all")
    elif last["fresh"] is None:
        v.reasons.append(f"the `b0 gmst` read before the last ping has no readable value=, so whether the read of "
                         f"{last['gmst_after']} after it is a fresh answer cannot be told")
    else:
        v.reasons.append(f"iFOCC_Pong read {last['gmst_after']} after the ping of {last['sent']}, the value it already "
                         f"held before the ping: a stale read is no answer; ping a value whose answer differs from the "
                         f"setting's current value (the judge counts a setting answer only when it is fresh)")
    return v


CHECKS = {"p1": check_p1, "p2": check_p2, "p3": check_p3, "p4": check_p4, "p5": check_p5,
          "p6": check_p6, "p7": check_p7, "p8": check_p8, "p9": check_p9, "p10": check_p10, "b0": check_b0}


def check(probe: str, c: Collection) -> Verdict:
    return CHECKS[probe.lower()](c)


def _attempted(p: str, c: Collection) -> bool:
    """Whether the collection holds any input for probe `p`: one of its own log lines (kind `p<n> ...`, or P3's
    p3cells `where` lines), the SFSE log for P1, the array-cap compile output for P5. Decided from the inputs, not
    from what a checker cited, so a probe that stops before citing still counts (Codex review of #431)."""
    if p == "p1" and c.sfse_log is not None:
        return True
    if p == "p5" and c.files.get("compile_p5_array129.txt") is not None:
        return True
    for evs in c.any_logs():
        cells = any(e.kind == "init" and e.fields.get("variant", "").lower() == "p3cells" for e in evs)
        if any(e.kind.split()[:1] == [p] or (p == "p3" and cells and e.kind == "where") for e in evs):
            return True
    return False


def check_all(c: Collection) -> dict:
    """Every probe; the summary verdict is the worst among probes that saw any input (an untouched probe is listed as
    INCONCLUSIVE but does not drag `all` down on its own)."""
    out, touched = {}, []
    for p in PROBES:
        v = check(p, c)
        out[p] = v.to_dict()
        if v.evidence or _attempted(p, c):
            touched.append(v.verdict)
    return {"probes": out, "verdict": _worst(*touched) if touched else INCONCLUSIVE,
            "note": "verdict is the worst of the probes with any evidence; the others had no input"}


# ----------------------------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fo4sf.combined.probes",
                                 description="judge a combined-core probe from its collected text; exit 0 PASS, "
                                             "1 FAIL, 2 INCONCLUSIVE")
    ap.add_argument("check", help="p1..p10, b0, all, hex2dec, dec2hex")
    ap.add_argument("path", nargs="?", help="collection folder or a single log file (or the id to convert)")
    ap.add_argument("--collect", help="collection folder (same as the positional path)")
    a = ap.parse_args(argv)
    cid = a.check.lower()
    if cid in ("hex2dec", "dec2hex"):
        if a.path is None:
            ap.error(f"{cid} needs a value")
        try:
            print(hex2dec(a.path) if cid == "hex2dec" else dec2hex(a.path))
        except ValueError:
            ap.error(f"not a form id: {a.path!r}")
        return 0
    if cid not in CHECKS and cid != "all":
        ap.error(f"unknown check {a.check!r}; want one of {', '.join(PROBES)} or all")
    path = a.collect or a.path
    if not path:
        ap.error("a collection folder or log file is needed")
    try:
        c = collect(path)
    except FileNotFoundError:
        print(json.dumps({"probe": cid, "verdict": INCONCLUSIVE, "reasons": [f"{path}: not found"], "evidence": []},
                         indent=1, sort_keys=True))
        return 2
    result = check_all(c) if cid == "all" else check(cid, c).to_dict()
    print(json.dumps(result, indent=1, sort_keys=True))
    return _RANK[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
