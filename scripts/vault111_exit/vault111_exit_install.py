"""Install / uninstall / status / order / active of a staged Vault 111 exit kit kit (scripts/vault111_exit/make_vault111_exit.py stage), next
to whatever experiment is installed, reversibly (docs/newgame/vault111-exit-kit.md).

usage: python scripts/vault111_exit/vault111_exit_install.py install --dir <stage> --starfield <game dir>
       python scripts/vault111_exit/vault111_exit_install.py uninstall|status|order|active --starfield <game dir>

The same wrapper as workshop_probe_install.py, on a record of its own, Data\\FO4SFVault111Exit.install.json, so the kit rides
along: it installs FO4SFVault111Exit.esm with its Data tree packed into "FO4SFVault111Exit - Main.ba2" (loose files are not read
on this install) and a "*FO4SFVault111Exit.esm" line appended to Plugins.txt, after checking the stage against its plan.json and
the game's Data (every file pinned, Starfield.esm and the core unchanged since the stage). Everything else is exp_install.py's
behaviour: no existing game file is overwritten, uninstall removes exactly the recorded files and the line it added, an
interrupted install rolls back. Its own record: it rides along with the other kits.
Game closed for install and uninstall. Nothing of the game enters the repo.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "game"))
import exp_install  # noqa: E402
import make_vault111_exit  # noqa: E402

RECORD = "FO4SFVault111Exit.install.json"


def installer(argv):
    """exp_install.py's main on this tool's own record."""
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def prepacked_supported():
    """True when exp_install.py itself knows --prepacked (FAL-274, #723): otherwise the wrapper refuses before anything is installed."""
    with open(exp_install.__file__, encoding="utf-8") as f:
        return "--prepacked" in f.read()


def install(a):
    if getattr(a, "prepacked", "") and not prepacked_supported():
        sys.exit("--prepacked is not supported by this exp_install.py (it lands with FAL-274 / #723); nothing installed. "
                 "Install without --prepacked to pack the archive here.")
    d = os.path.abspath(a.dir)
    plan = make_vault111_exit.load_plan(d)
    problems = make_vault111_exit.verify_stage(d, plan, os.path.join(a.starfield, "Data"))
    if problems:
        sys.exit("Vault 111 exit kit not installed: the stage does not match its plan.json or Data (re-stage): " + "; ".join(problems))
    names = sorted(n for n in os.listdir(d) if n.lower().endswith(".esm"))
    if sorted(plan["plugins"]) != names:
        sys.exit(f"Vault 111 exit kit not installed: the stage holds {names}, plan.json lists {plan['plugins']}")
    return installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack", "--plugins", ",".join(plan["plugins"])] +
                     (["--prepacked", a.prepacked] if getattr(a, "prepacked", "") else []))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="the staged Vault 111 exit kit folder (install)")
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
