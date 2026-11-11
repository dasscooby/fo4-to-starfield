"""Install / uninstall / status / order / active of a staged core storage probe (scripts/core_storage/make_core_storage.py
stage), next to the installed core, reversibly (FAL-208).

usage: python scripts/core_storage/core_storage_install.py install --dir <stage> --starfield <game dir>
       python scripts/core_storage/core_storage_install.py uninstall|status|order|active --starfield <game dir>

Runs scripts/game/exp_install.py's installer against a record of its own (Data\\FO4SFCoreStorage.install.json), as
scripts/planet/planet_probe_install.py does, so the installed experiment is never read or changed. install first checks
the stage against its plan.json (every output pinned by sha256); the plugin is added to the end of Plugins.txt and its
Data tree packed into an archive (loose scripts are not read on this install). No existing game file is overwritten;
uninstall removes exactly the recorded files and the Plugins.txt line it added. Game closed for install and uninstall.
Nothing of the game enters the repo.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "game"))
import exp_install  # noqa: E402
import make_core_storage  # noqa: E402

RECORD = "FO4SFCoreStorage.install.json"


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
    plan, problems = make_core_storage.verify_stage(d)
    if problems:
        sys.exit("core storage probe not installed: the stage does not match its plan.json (re-stage): " + "; ".join(problems))
    problems = make_core_storage.core_pin_problems(plan, os.path.join(a.starfield, "Data"))
    if problems:
        sys.exit("core storage probe not installed: " + "; ".join(problems))
    # Plugins.txt is only read for a stage that overrides the core world's persistent cell (a stage without a variant is run 3's)
    problems = (make_core_storage.persistent_cell_conflicts(plan, exp_install.plugins_txt())
                if plan.get("variant", "full") in make_core_storage.PERSISTENT_CELL_VARIANTS else [])
    if problems:
        sys.exit("core storage probe not installed: " + "; ".join(problems))
    names = sorted(n for n in os.listdir(d) if n.lower().endswith(".esm"))
    if sorted(plan["plugins"]) != names:
        sys.exit(f"core storage probe not installed: the stage holds {names}, plan.json lists {plan['plugins']}")
    return installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack", "--plugins", ",".join(plan["plugins"])])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="the staged probe folder (install)")
    ap.add_argument("--starfield", required=True, help="the game folder (Starfield.exe)")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        return install(a)
    return installer([a.cmd, "--starfield", a.starfield])


if __name__ == "__main__":
    sys.exit(main())
