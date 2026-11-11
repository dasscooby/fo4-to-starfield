"""Install / uninstall / status / order / active of a staged rads probe (scripts/planet/make_rads_probe.py
stage), next to whatever experiment is installed, reversibly (docs/research/rads-probe.md).

usage: python scripts/planet/rads_probe_install.py install --dir <stage> --starfield <game dir>
       python scripts/planet/rads_probe_install.py uninstall|status|order|active --starfield <game dir>

exp_install.py keeps exactly one experiment record (Data\\FO4SFExp.install.json, today the core set); this tool runs the
same installer code against a record of its own, Data\\FO4SFRadsProbe.install.json (scripts/planet/
the other probes' installers do the same, each with its own record), so the probe rides along and the
installed experiment is never read or changed. install first checks the stage against its plan.json and the game's
Data (every file pinned, Starfield.esm unchanged since the stage), then installs FO4SFRadsProbe.esm with its Data
tree packed into "FO4SFRadsProbe - Main.ba2" (loose files are not read on this install) and a
"*FO4SFRadsProbe.esm" line appended to Plugins.txt. Everything else is exp_install.py's behaviour: no existing game
file is overwritten, every added file is recorded before it is published, uninstall removes exactly the recorded files
(unchanged ones only) and the line it added, an interrupted install rolls back, plugin_toggle.py holds make install and
uninstall refuse. order moves the probe's plugin after its master (exp_install.py order); active is the relaunch check
(exit 8 when the plugin was unticked, e.g. by the game's load order dialog).
Game closed for install and uninstall (Starfield rewrites Plugins.txt on launch). Nothing of the game enters the repo.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "game"))
import exp_install  # noqa: E402
import make_rads_probe  # noqa: E402

RECORD = "FO4SFRadsProbe.install.json"


def installer(argv):
    """exp_install.py's main on this tool's own record."""
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def install(a):
    d = os.path.abspath(a.dir)
    plan = make_rads_probe.load_plan(d)
    problems = make_rads_probe.verify_stage(d, plan, os.path.join(a.starfield, "Data"))
    if problems:
        sys.exit("rads probe not installed: the stage does not match its plan.json or Data (re-stage): "
                 + "; ".join(problems))
    names = sorted(n for n in os.listdir(d) if n.lower().endswith(".esm"))
    if sorted(plan["plugins"]) != names:
        sys.exit(f"rads probe not installed: the stage holds {names}, plan.json lists {plan['plugins']}")
    return installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack",
                      "--plugins", ",".join(plan["plugins"])])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="the staged rads probe folder (install)")
    ap.add_argument("--starfield", required=True, help="the game folder (Starfield.exe)")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        return install(a)
    return installer([a.cmd, "--starfield", a.starfield])


if __name__ == "__main__":
    sys.exit(main())
