"""Install / uninstall / status / order / active of the staged Pip-Boy probe (scripts/ui/make_pipboy_probe.py stage),
next to whatever experiment is installed, reversibly (FAL-187; sfse/FO4SFPipboyMenu/README.md, stage (b)).

usage: python scripts/ui/pipboy_probe_install.py install --dir <stage> --starfield <game dir>
       python scripts/ui/pipboy_probe_install.py uninstall|status|order|active --starfield <game dir>

exp_install.py keeps exactly one experiment record (Data\\FO4SFExp.install.json, today the core set); this tool runs
the same installer code against a record of its own, Data\\FO4SFPipboyProbe.install.json, so the probe rides along
and the installed experiment is never read or changed (the pattern of scripts/planet/planet_probe_install.py).
install first checks the stage: exactly one plugin, FO4SFPipboyProbe.esm, passing make_pipboy_probe.py check, and a
Data tree holding the movie Interface/FO4SF_PipboyMenu.swf, which must read back as a movie, and nothing else but its
twins (make_pipboy_probe.py twin, FAL-250): the same bytes at a vanilla movie's path under Interface/. It then
activates the plugin and packs Data into "FO4SFPipboyProbe - Main.ba2" (loose files are not read on this install),
the "*FO4SFPipboyProbe.esm" line appended to the end of Plugins.txt. Everything else is exp_install.py's behaviour:
no existing game file is overwritten, every added file is recorded before it is published, uninstall removes exactly
the recorded files (unchanged ones only) and the line it added, an interrupted install rolls back, plugin_toggle.py
holds make install and uninstall refuse. order moves the plugin after its master (exp_install.py order); active is
the relaunch check (exit 8 when the plugin was unticked).
The SFSE plugin (dll, ini, Address Library file) is not handled here: README, Install step 1.
Game closed for install and uninstall (Starfield rewrites Plugins.txt on launch). Nothing of the game enters the repo.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "game"))
import exp_install  # noqa: E402
import make_pipboy_probe  # noqa: E402
import make_probe_swf  # noqa: E402

RECORD = "FO4SFPipboyProbe.install.json"


def installer(argv):
    """exp_install.py's main on this tool's own record."""
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def stage_problems(d):
    """What is wrong with the staged folder, as a list (empty: it is the probe as make_pipboy_probe.py stages it)."""
    problems = []
    names = sorted(n for n in os.listdir(d) if n.lower().endswith(".esm"))
    if names != [make_pipboy_probe.PLUGIN]:
        problems.append(f"the stage holds plugins {names}, expected [{make_pipboy_probe.PLUGIN!r}]")
    else:
        try:
            make_pipboy_probe.check(os.path.join(d, make_pipboy_probe.PLUGIN))
        except make_pipboy_probe.EsmError as e:
            problems.append(str(e))
    data = os.path.join(d, "Data")
    found = sorted(os.path.relpath(os.path.join(r, f), data).replace(os.sep, "/")
                   for r, _, fs in os.walk(data) for f in fs)
    twins = [f for f in found if f != make_pipboy_probe.MOVIE]
    if make_pipboy_probe.MOVIE not in found or any(make_pipboy_probe.twin_problem(t) for t in twins):
        problems.append(f"Data holds {found}, expected [{make_pipboy_probe.MOVIE!r}] and twins under Interface/")
    else:
        try:
            make_probe_swf.read_movie(os.path.join(data, *make_pipboy_probe.MOVIE.split("/")))
        except (make_probe_swf.SwfError, OSError) as e:
            problems.append(f"the movie does not read back: {e}")
        else:
            problems += twin_problems(data, twins)
    return problems


def twin_problems(data, twins):
    """Each twin must be the movie byte for byte: a twin that differs would not prove that our movie drew."""
    with open(os.path.join(data, *make_pipboy_probe.MOVIE.split("/")), "rb") as f:
        movie = f.read()
    problems = []
    for t in twins:
        with open(os.path.join(data, *t.split("/")), "rb") as f:
            if f.read() != movie:
                problems.append(f"the twin {t} is not the movie byte for byte (re-run make_pipboy_probe.py twin)")
    return problems


def install(a):
    d = os.path.abspath(a.dir)
    problems = stage_problems(d)
    if problems:
        sys.exit("pipboy probe not installed (re-stage with make_pipboy_probe.py stage): " + "; ".join(problems))
    return installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack",
                      "--plugins", make_pipboy_probe.PLUGIN])


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
