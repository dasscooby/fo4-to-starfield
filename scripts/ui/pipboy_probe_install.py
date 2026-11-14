"""Install / uninstall / status / order / active of the staged Pip-Boy probe (scripts/ui/make_pipboy_probe.py stage),
next to whatever experiment is installed, reversibly (FAL-187; sfse/FO4SFPipboyMenu/README.md, stage (b)).

usage: python scripts/ui/pipboy_probe_install.py install --dir <stage> [--extra-movie <name> [--page-movie <page>]...]
                                                       --starfield <game dir>
       python scripts/ui/pipboy_probe_install.py uninstall|status|order|active --starfield <game dir>

exp_install.py keeps exactly one experiment record (Data\\FO4SFExp.install.json, today the core set); this tool runs
the same installer code against a record of its own, Data\\FO4SFPipboyProbe.install.json, so the probe rides along
and the installed experiment is never read or changed (the pattern of scripts/planet/planet_probe_install.py).
install first checks the stage: exactly one plugin, FO4SFPipboyProbe.esm, passing make_pipboy_probe.py check, and a
Data tree holding the movie Interface/FO4SF_PipboyMenu.swf, which must read back as a movie, and nothing else but its
twins (make_pipboy_probe.py twin, FAL-250): the same bytes at a vanilla movie's path under Interface/, and, only when
named with --extra-movie <name> (FAL-614, proof 1), one private movie Interface/<name>.swf that the player copied in
for the plugin's Movie= setting: <name> is FO4SF_ and 1 to 58 of A-Z a-z 0-9 _ (never our own movie's name), and the
file must read back as a SWF; its bytes are the player's, never checked against ours and never in Git. With the extra
movie only, each --page-movie <page> (FAL-614, S1) packs one of Fallout 4's five tab movies, Interface/<page>.swf, under
the very name Fallout 4's shell PipboyMenu.swf loads it by: <page> is one of PAGE_MOVIES, named once, and the file must
read back as a SWF, the player's own as above. It then
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
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "game"))
import exp_install  # noqa: E402
import make_pipboy_probe  # noqa: E402
import make_probe_swf  # noqa: E402

RECORD = "FO4SFPipboyProbe.install.json"
EXTRA_PREFIX = "FO4SF_"   # an extra movie can never take a vanilla movie's name
# FAL-614 S1: the tab movies the shell (the extra movie) loads by these names; Fallout 4's own names, none of Starfield's
PAGE_MOVIES = ("Pipboy_StatsPage", "Pipboy_InvPage", "Pipboy_DataPage", "Pipboy_MapPage", "Pipboy_RadioPage")


def installer(argv):
    """exp_install.py's main on this tool's own record."""
    saved = exp_install.RECORD
    exp_install.RECORD = RECORD
    try:
        return exp_install.main(argv)
    finally:
        exp_install.RECORD = saved


def extra_movie_problem(name):
    """Why `name` cannot be the extra movie (the plugin's Movie= value), or None."""
    if not (len(EXTRA_PREFIX) < len(name) <= 64 and name.startswith(EXTRA_PREFIX)
            and all(c.isascii() and (c.isalnum() or c == "_") for c in name)):
        return f"--extra-movie {name!r}: {EXTRA_PREFIX} then letters, digits and _ only, 64 at most"
    if f"Interface/{name}.swf".lower() == make_pipboy_probe.MOVIE.lower():
        return f"--extra-movie {name!r}: that is our own movie"
    return None


def page_movies_problem(pages, extra_movie):
    """Why `pages` cannot ride with the extra movie (the shell), or None."""
    if pages and not extra_movie:
        return "--page-movie needs --extra-movie <name>, the shell that loads the pages"
    for page in pages:
        if page not in PAGE_MOVIES:
            return f"--page-movie {page!r}: one of {', '.join(PAGE_MOVIES)}"
    if len(set(pages)) != len(pages):
        return "--page-movie: each page once"
    return None


def swf_problem(path):
    """Why the file at `path` is not a whole SWF, or None. Only the container is read: the signature (CWS or FWS), the
    FileLength against the body, the frame header, and each tag's code and length up to the End tag at the body's end.
    No tag's contents are read (the extra movie is the player's own, not one our writer made)."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        return str(e)
    if len(raw) < 8 or raw[:3] not in (b"CWS", b"FWS"):
        return "the signature is not CWS or FWS"
    length = int.from_bytes(raw[4:8], "little")
    try:
        body = zlib.decompress(raw[8:]) if raw[:3] == b"CWS" else raw[8:]
    except zlib.error as e:
        return f"the body does not decompress: {e}"
    if 8 + len(body) != length:
        return f"FileLength {length} but the body is {len(body)} bytes + 8"
    if not body:
        return "no frame header"
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4                     # the frame RECT, then frame rate and frame count
    while pos + 2 <= len(body):
        head = int.from_bytes(body[pos:pos + 2], "little")
        code, size, pos = head >> 6, head & 0x3F, pos + 2
        if size == 0x3F:
            if pos + 4 > len(body):
                return "a tag's long length runs past the body"
            size, pos = int.from_bytes(body[pos:pos + 4], "little"), pos + 4
        if pos + size > len(body):
            return f"tag {code} runs past the body"
        pos += size
        if code == 0:
            return None if pos == len(body) else f"{len(body) - pos} bytes after the End tag"
    return "no End tag"


def stage_problems(d, extra_movie="", pages=()):
    """What is wrong with the staged folder, as a list (empty: it is the probe as make_pipboy_probe.py stages it, plus
    the one extra movie when named, and its named pages)."""
    problems = []
    extra = ""
    why = page_movies_problem(pages, extra_movie)
    if why:
        return [why]
    if extra_movie:
        why = extra_movie_problem(extra_movie)
        if why:
            return [why]
        extra = f"Interface/{extra_movie}.swf"
    paged = [f"Interface/{page}.swf" for page in pages]
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
    if extra and extra not in found:
        return problems + [f"the extra movie {extra} is not in the stage's Data"]
    missing = [p for p in paged if p not in found]
    if missing:
        return problems + [f"the page movie {missing[0]} is not in the stage's Data"]
    twins = [f for f in found if f not in (make_pipboy_probe.MOVIE, extra, *paged)]
    if make_pipboy_probe.MOVIE not in found or any(make_pipboy_probe.twin_problem(t) for t in twins):
        problems.append(f"Data holds {found}, expected [{make_pipboy_probe.MOVIE!r}] and twins under Interface/")
    else:
        try:
            make_probe_swf.read_movie(os.path.join(data, *make_pipboy_probe.MOVIE.split("/")))
        except (make_probe_swf.SwfError, OSError) as e:
            problems.append(f"the movie does not read back: {e}")
        else:
            problems += twin_problems(data, twins)
    if extra:
        why = swf_problem(os.path.join(data, *extra.split("/")))
        if why:
            problems.append(f"the extra movie {extra} does not read back as a SWF: {why}")
    for p in paged:
        why = swf_problem(os.path.join(data, *p.split("/")))
        if why:
            problems.append(f"the page movie {p} does not read back as a SWF: {why}")
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
    problems = stage_problems(d, a.extra_movie, a.page_movie)
    if problems:
        sys.exit("pipboy probe not installed (re-stage with make_pipboy_probe.py stage): " + "; ".join(problems))
    return installer(["install", "--exp-dir", d, "--starfield", a.starfield, "--pack",
                      "--plugins", make_pipboy_probe.PLUGIN])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order", "active"))
    ap.add_argument("--dir", default="", help="the staged probe folder (install)")
    ap.add_argument("--extra-movie", default="", help="install: also pack Interface/<name>.swf from the stage, the "
                    "player's private movie for the plugin's Movie= setting (FAL-614 proof 1)")
    ap.add_argument("--page-movie", action="append", default=[], help="install, with --extra-movie: also pack "
                    "Interface/<page>.swf, one of Fallout 4's tab movies the shell loads by name (FAL-614 S1); repeat "
                    "for each page")
    ap.add_argument("--starfield", required=True, help="the game folder (Starfield.exe)")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir <stage>")
        return install(a)
    if a.extra_movie or a.page_movie:
        sys.exit("--extra-movie and --page-movie belong to install")
    return installer([a.cmd, "--starfield", a.starfield])


if __name__ == "__main__":
    sys.exit(main())
