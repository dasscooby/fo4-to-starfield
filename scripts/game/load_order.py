"""One target load order for our plugins in Plugins.txt: check it, or put it right.

usage: python load_order.py check|fix --starfield <game dir>

The target preserves file order whenever every plugin follows its masters. A plugin before one of its masters
waits for that master; among the ready lines, the earliest in the original file goes next. This applies to every
plugin, including patches, map markers and the bridge. No plugin is forced to the end: a later-installed test kit
must not move ahead of markers or a held bridge just because play runs (FAL-354, 11 Nov 2026).
Inactive lines stay inactive: a plugin held off by plugin_toggle.py is never ticked here. The install tools can
choose positions when installing or explicitly ordering their components; play preserves any already-valid order.

check exits 0 when the order is the target, 9 when it is not (the changes are printed), 6 when it cannot be judged
(an active plugin of ours missing from Data, an active plugin whose master is neither active nor loaded by the game,
a master cycle, a duplicated line). fix writes the target with the same BOM and line ending, after copying the old
file to Plugins.txt.bak-<time>, and refuses (6) as check does.
"""
import argparse
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                                           # isolated Python omits the script's directory
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
import exp_install  # noqa: E402
from fo4sf.core.loadset import OUR_PREFIXES  # noqa: E402,F401  (the project's one list; ours() reads it)


def name(line):
    return line.strip().lstrip("*").strip()


def ours(plugin):
    """True for a plugin of ours (fo4sf.core.loadset.OUR_PREFIXES: the cores, FO4Port, FO4SF* experiments, markers,
    bridge, the slices, the FOCC probes, and the reserved FOSF / FO3SF / FNVSF names): active, it must be in Data."""
    low = plugin.casefold()
    return low.endswith((".esm", ".esp", ".esl")) and low.startswith(OUR_PREFIXES)


def target(lines, masters):
    """(new lines, problems). masters: {plugin casefold: [master, ...]} for the plugins whose headers were read.
    One stable sort over every line: a plugin is placed only after each of its masters that is on a line, and among
    the lines ready to place the next is the earliest in file order. Already-valid orders stay byte-identical,
    including kits after markers/the bridge; any chain of masters keeps every master first (Codex, #487/FAL-354)."""
    problems, seen, nodes = [], set(), []
    for k, ln in enumerate(lines):
        p = name(ln)
        plug = bool(p) and not ln.strip().startswith("#")
        if plug:
            if p.casefold() in seen:
                problems.append(f"{p} is listed more than once")
            seen.add(p.casefold())
        nodes.append((k, p.casefold() if plug else None, ln))
    active = {name(ln).casefold() for ln in lines if ln.strip().startswith("*")}
    for ln in lines:
        p = name(ln)
        if ln.strip().startswith("*"):
            for m in masters.get(p.casefold(), []):
                if m.casefold() not in active and not exp_install.implicit(m):
                    problems.append(f"{p} needs master {m}, which is not active")
    if problems:
        return list(lines), problems
    at = {n: k for k, (_key, n, _ln) in enumerate(nodes) if n}
    needs = {k: {at[m.casefold()] for m in masters.get(n, []) if m.casefold() in at and at[m.casefold()] != k}
             for k, (_key, n, _ln) in enumerate(nodes)}
    self_master = [nodes[k][2].strip() for k, (_key, n, _ln) in enumerate(nodes)
                   if n and any(m.casefold() == n for m in masters.get(n, []))]
    placed, out = set(), []
    while len(out) < len(nodes):
        ready = [k for k in range(len(nodes)) if k not in placed and needs[k] <= placed]
        if not ready:
            left = ", ".join(name(nodes[k][2]) for k in range(len(nodes)) if k not in placed)
            return list(lines), [f"a master cycle among {left}"]
        k = min(ready, key=lambda i: nodes[i][0])
        placed.add(k)
        out.append(nodes[k][2])
    if self_master:
        return list(lines), [f"{p} names itself as a master" for p in self_master]
    return out, problems


def changes(old, new):
    """The lines that moved: [(plugin, old position, new position)] (1-based)."""
    pos = {name(ln).casefold(): k for k, ln in enumerate(old)}
    return [(name(ln), pos[name(ln).casefold()] + 1, k + 1) for k, ln in enumerate(new)
            if pos.get(name(ln).casefold()) != k]


def read_masters(data, lines):
    """({plugin casefold: [master, ...]}, problems) for the plugins on a line that are in Data. One of ours that is
    active must be there and readable; another plugin's header is read when it is there, to find patches for ours."""
    out, problems = {}, []
    for ln in lines:
        p = name(ln)
        if not p or ln.strip().startswith("#"):
            continue
        mine = ours(p)
        f = os.path.join(data, p)
        if not os.path.isfile(f):
            if mine and ln.strip().startswith("*"):
                problems.append(f"{p} is active but not in {data}")
            continue
        try:
            out[p.casefold()] = exp_install.plugin_masters(f)
        except (OSError, ValueError) as e:
            if mine or ln.strip().startswith("*"):
                problems.append(f"{p}: {e}")
    return out, problems


def keep_copy(path, raw):
    """Write raw to path.bak-<time>, never over an earlier copy (two changes in one second get -2, -3, ...); the
    copy's path. (Codex, #487)"""
    stem = path + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for n in range(1, 1000):
        bak = stem if n == 1 else f"{stem}-{n}"
        try:
            with open(bak, "xb") as f:
                f.write(raw)
            return bak
        except FileExistsError:
            continue
    raise OSError(f"no free backup name beside {path}")


def run(cmd, starfield, plugins_txt=None, say=print):
    local = os.environ.get("LOCALAPPDATA", "")
    if not plugins_txt and not os.path.isabs(local):
        say("no LOCALAPPDATA folder (not Windows): no Plugins.txt to order")
        return 0
    p_txt = plugins_txt or os.path.join(local, "Starfield", "Plugins.txt")
    original = exp_install.read_bytes(p_txt)
    if original is None:
        say(f"no Plugins.txt at {p_txt}: nothing to order")
        return 0
    try:
        lines, bom, nl = exp_install.plugin_lines(original)
    except UnicodeDecodeError:
        say(f"{p_txt} is not UTF-8: not judged")
        return 6
    masters, problems = read_masters(os.path.join(starfield, "Data"), lines)
    new, more = target(lines, masters)
    problems += more
    if problems:
        say("load order not judged: " + "; ".join(problems))
        return 6
    moved = changes(lines, new)
    if not moved:
        say("load order ok: our plugins are in the target order")
        return 0
    for p, a, b in moved:
        say(f"  {p}: line {a} -> {b}")
    if cmd == "check":
        say(f"load order differs from the target in {len(moved)} line(s) (fix puts it right)")
        return 9
    bak = keep_copy(p_txt, original)
    exp_install.write_plugins(p_txt, new, bom, nl, expected_current=original)
    say(f"load order fixed: {len(moved)} line(s) moved; the old file is {bak}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("check", "fix"))
    ap.add_argument("--starfield", required=True)
    a = ap.parse_args(argv)
    try:
        return run(a.cmd, a.starfield)
    except (OSError, ValueError) as e:
        print(f"load order not changed: {e}")
        return 6


if __name__ == "__main__":
    sys.exit(main())
