"""Launcher settings: the optional pieces the player turns on and off before playing, each with what it costs
(owner, 2026-10-21: "let the launcher be where I can toggle it off and on, and more settings of that sort that cause
RAM use"). One JSON file per player, written only by `launcher.py settings --set` and read by `launcher.py play`.

Every setting but two starts at the value that changes nothing on the PC (crash watcher off, bridge and Papyrus
logging left as they are, update off: nothing is fetched). The two: load_order=fix puts our plugins in the target order before each start (so their
load-order indexes, and the form ids console commands use, can change once; load_order=off leaves Plugins.txt
alone), and route=sfse starts the game through SFSE. Once the watcher is on,
it also saves a dump at every exit unless crash_watch.dump_on_exit is turned off.
"""
import json
import math
import os

from . import files

DUMP_KINDS = ("mini", "full")
TRISTATE = ("unchanged", "on", "off")

# (key, default, allowed values or type, what it costs)
SPEC = (
    ("starfield", "", str, "the Starfield game folder (holds Starfield.exe); play uses it when --starfield is not given."),
    ("fo4_data", "", str, "Fallout 4 Data folder(s), separated by ;, for the installation check."),
    ("crash_watch.enabled", False, bool,
     "watch the game from launch to exit: ProcDump attached while it runs, the exit code logged when it ends. "
     "ProcDump itself is small; the cost is the dump."),
    ("crash_watch.dump", "mini", DUMP_KINDS,
     "mini (-mm: threads, stacks and loaded modules, small) or full (-ma, the whole game's memory, about 18 GB on the owner's PC; "
     "the game is paused while it is written)."),
    ("crash_watch.catch_assertion", True, bool,
     "also dump on the engine's assertion stop (first-chance 0x80000003), the flags the old crashwatch.cmd used."),
    ("crash_watch.dump_on_exit", True, bool,
     "also dump when the game is terminated without an exception (ProcDump -t): a kill or a silent exit. A normal "
     "quit writes none (ProcDump says \"Dump count not reached\", seen on the PC 2026-10-21); every kill does (a mini "
     "dump is small; with dump=full it is the whole game). On by the owner's choice, 2026-10-21."),
    ("crash_watch.folder", "", str, "where dumps and crashwatch.log go (required when the watcher is on)."),
    ("crash_watch.procdump", "", str, "path to procdump64.exe (required when the watcher is on)."),
    ("crash_watch.min_free_gb", 25.0, float, "the watcher is not armed when the dump folder's drive has less free; with dump=full it also needs about "
     "20 GB for each dump ProcDump may write (two with dump_on_exit on)."),
    ("crash_watch.settle_s", 20.0, float,
     "seconds the game must stay up before ProcDump attaches. The old watcher attached at the instant of start (-w), "
     "the leading lead for Steam's ERROR 84."),
    ("bridge", "unchanged", TRISTATE,
     "the test bridge plugin (FO4SFBridge.esm): its script runs all the time and writes the heartbeat and position "
     "log. off holds it off through plugin_toggle.py; on puts it back."),
    ("papyrus_logging", "unchanged", TRISTATE,
     "Papyrus logging, trace and debug information in StarfieldCustom.ini ([Papyrus] bEnableLogging, bEnableTrace, "
     "bLoadDebugInformation): memory and disk for every script. The bridge needs it on."),
    ("load_order", "fix", ("fix", "check", "off"),
     "our plugins' order in Plugins.txt (scripts/game/load_order.py: the test runner's rules, file order kept, masters "
     "first, map markers then the bridge last): fix puts them in the target order before the "
     "game starts, keeping a copy of the old file; check refuses to start on a different order; off leaves it."),
    ("my_games", "", str, "Documents\\My Games\\Starfield (required when papyrus_logging is on or off)."),
    ("route", "sfse", ("sfse", "steam", "exe"),
     "how play starts the game: sfse (sfse_loader.exe in the game folder, which starts Starfield.exe with SFSE "
     "loaded; SFSE is required, NG-1), steam (steam://rungameid/1716740, as the test runner does) or exe "
     "(Starfield.exe directly). steam and exe start the game without SFSE."),
    ("instance", "", str,
     "the FO4SF game folder (launcher.py instance create; docs/ai/fo4sf-instance.md). Set: play starts the game from "
     "it, our tools use its own Plugins.txt, its own Starfield.ini takes the saves path (Saves\\FO4SF) and the "
     "Papyrus keys, and its Plugins.txt stands in yours only while it runs. Empty (the default): your Starfield folder, "
     "as before."),
    ("update", "off", ("off", "check", "pull"),
     "keep the launcher's own code up to date with GitHub's main (src/fo4sf/launcher/selfupdate.py): pull fetches "
     "main before play and before the window opens, fast-forwards this checkout when it is on main with nothing of "
     "its own uncommitted or unpushed, and starts again on the new code; check only says how far behind it is; off "
     "fetches nothing. A network or git problem never stops play. Built plugins and installs are not updated by it."),
)
KEYS = {k: (d, t, why) for k, d, t, why in SPEC}
# the plain name `settings` shows first on each line, so a toggle reads without knowing its key
LABELS = {
    "starfield": "Starfield game folder",
    "fo4_data": "Fallout 4 Data folders",
    "crash_watch.enabled": "Crash watcher (starts and ends with the game)",
    "crash_watch.dump": "Crash dump size",
    "crash_watch.catch_assertion": "Dump on the engine's assertion stop",
    "crash_watch.dump_on_exit": "Crash dump on every exit (off = log only)",
    "crash_watch.folder": "Dump folder",
    "crash_watch.procdump": "ProcDump path",
    "crash_watch.min_free_gb": "Free space needed for dumps (GB)",
    "crash_watch.settle_s": "Seconds before the watcher attaches",
    "bridge": "Test bridge plugin",
    "papyrus_logging": "Papyrus script logging",
    "load_order": "Load order of our plugins",
    "my_games": "My Games folder",
    "route": "How the game starts",
    "instance": "FO4SF game folder",
    "update": "Update the launcher from GitHub",
}


def defaults():
    return {k: d for k, d, _t, _w in SPEC}


def load(path):
    """The settings at path over the defaults; unknown keys are refused, so a typo is never silently ignored."""
    out = defaults()
    if path and os.path.isfile(path):
        saved = files.load_json(path)
        if not isinstance(saved, dict):
            raise ValueError(f"{path}: expected an object of settings, found {type(saved).__name__}")
        bad = sorted(set(saved) - set(KEYS))
        if bad:
            raise ValueError(f"{path}: unknown setting(s) {', '.join(bad)}")
        for k, v in saved.items():
            out[k] = coerce(k, v)
    return out


def save(path, values):
    """Only the settings that differ from the defaults are written."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    d = defaults()
    files.save_json(path, {k: v for k, v in sorted(values.items()) if v != d[k]})


def one_each(value):
    """A ;-separated folder list with each folder once: Windows paths ignore case, and a list saved before #487 named
    every Fallout 4 depot twice (once under a lower-case Steam path; PC, 2026-10-22)."""
    seen, out = set(), []
    for p in str(value or "").replace("\n", ";").split(";"):
        p = p.strip()
        k = os.path.normcase(os.path.normpath(p)) if p else ""
        if p and k not in seen:
            seen.add(k)
            out.append(p)
    return ";".join(out)


def coerce(key, value):
    if key not in KEYS:
        raise ValueError(f"unknown setting {key!r}; known: {', '.join(KEYS)}")
    _d, t, _w = KEYS[key]
    if t is bool:
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("1", "true", "on", "yes"):
            return True
        if s in ("0", "false", "off", "no"):
            return False
        raise ValueError(f"{key}: {value!r} is not on or off")
    if t is float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key}: {value!r} is not a number") from None
        # nan would make every comparison false (the free-space floor never stops play) and inf would hold the
        # settle wait past the start timeout (Codex, #449)
        if not math.isfinite(v):
            raise ValueError(f"{key}: {value!r} is not a finite number")
        if v < 0:
            raise ValueError(f"{key}: must not be negative")
        return v
    if t is str:
        return one_each(value) if key == "fo4_data" else str(value)
    s = str(value).strip().lower()
    if s not in t:
        raise ValueError(f"{key}: {value!r} is not one of {', '.join(t)}")
    return s


def assign(values, pairs):
    """Apply "key=value" strings; returns the new settings (values is not changed)."""
    out = dict(values)
    for p in pairs:
        if "=" not in p:
            raise ValueError(f"--set {p!r}: expected key=value")
        k, v = p.split("=", 1)
        out[k.strip()] = coerce(k.strip(), v)
    return out


def problems(values):
    """[problems] that stop `play` with these settings."""
    out = []
    if values["crash_watch.enabled"]:
        for k in ("crash_watch.folder", "crash_watch.procdump"):
            if not values[k]:
                out.append(f"{k} is not set (needed while the crash watcher is on)")
    # the bridge reads only what Papyrus logs: turning logging off is allowed only with the bridge held off, and
    # putting the bridge back only with logging turned on, whatever the INI or Plugins.txt hold today (Codex, #449)
    if values["papyrus_logging"] == "off" and values["bridge"] != "off":
        out.append("papyrus_logging=off needs bridge=off: an active bridge would be left blind")
    if values["bridge"] == "on" and values["papyrus_logging"] != "on":
        out.append("bridge=on needs papyrus_logging=on: the bridge only sees what Papyrus logs")
    if values["papyrus_logging"] != "unchanged" and not values["my_games"] and not values["instance"]:
        out.append("my_games is not set (needed to change Papyrus logging)")
    return out


def describe(values):
    """Lines for `settings --show`: each key, its value, and what it costs."""
    d = defaults()
    lines = []
    for k, _d, _t, why in SPEC:
        mark = "" if values[k] == d[k] else "  (changed)"
        lines.append(f"{LABELS[k]}: {k} = {json.dumps(values[k])}{mark}\n    {why}")
    return lines
