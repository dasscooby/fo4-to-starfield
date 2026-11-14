"""Install / uninstall / status / order / active of a staged cog door probe (scripts/newgame/make_cog_door.py
stage), next to whatever experiment is installed, reversibly (docs/research/cog-door-probe.md).

usage: python scripts/newgame/cog_door_install.py install --dir <stage> --starfield <game dir>
       python scripts/newgame/cog_door_install.py uninstall|status|order|active --starfield <game dir>

exp_install.py keeps exactly one experiment record (Data\\FO4SFExp.install.json, today the core set); this tool runs the
same installer code against a record of its own, Data\\FO4SFCogDoor.install.json (the workshop and planet
probes do the same with records of their own), so the probe rides along and the
installed experiment is never read or changed. install first checks the stage against its plan.json and the game's
Data (every file pinned, Starfield.esm unchanged since the stage), then installs FO4SFCogDoor.esm with its Data
tree packed into "FO4SFCogDoor - Main.ba2" (loose files are not read on this install) and a
"*FO4SFCogDoor.esm" line appended to Plugins.txt. Everything else is exp_install.py's behaviour: no existing game
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
sys.path.insert(0, os.path.join(HERE, "..", "planet"))
import exp_install  # noqa: E402
import make_cog_door  # noqa: E402

RECORD = "FO4SFCogDoor.install.json"


def installer(argv):
    """exp_install.py's main on this tool's own record."""
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def prepacked_supported():
    """True when exp_install.py itself knows --prepacked (FAL-274, #723). Without it the flag would reach an installer that
    rejects it, or one that builds its own archive: the wrapper refuses before anything is installed."""
    with open(exp_install.__file__, encoding="utf-8") as f:
        return "--prepacked" in f.read()


def install(a):
    if getattr(a, "prepacked", "") and not prepacked_supported():
        sys.exit("--prepacked is not supported by this exp_install.py (it lands with FAL-274 / #723); nothing installed. "
                 "Install without --prepacked to pack the archive here.")
    d = os.path.abspath(a.dir)
    plan = make_cog_door.load_plan(d)
    problems = make_cog_door.verify_stage(d, plan, os.path.join(a.starfield, "Data"))
    if problems:
        sys.exit("cog door probe not installed: the stage does not match its plan.json or Data (re-stage): "
                 + "; ".join(problems))
    names = sorted(n for n in os.listdir(d) if n.lower().endswith(".esm"))
    if sorted(plan["plugins"]) != names:
        sys.exit(f"cog door probe not installed: the stage holds {names}, plan.json lists {plan['plugins']}")
    return installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack",
                      "--plugins", ",".join(plan["plugins"])] +
                     (["--prepacked", a.prepacked] if getattr(a, "prepacked", "") else []))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="the staged cog door probe folder (install)")
    ap.add_argument("--prepacked", default="", help="verify and install this existing archive; never build")
    ap.add_argument("--starfield", required=True, help="the game folder (Starfield.exe)")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        return install(a)
    return installer([a.cmd, "--starfield", a.starfield])


if __name__ == "__main__":
    sys.exit(main())
