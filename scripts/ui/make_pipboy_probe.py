"""The Pip-Boy probe's empty plugin and its movie (FAL-187; sfse/FO4SFPipboyMenu/README.md).

usage: python scripts/ui/make_pipboy_probe.py stage <dir> [--no-label]   FO4SFPipboyProbe.esm + Data/Interface/<movie>
       python scripts/ui/make_pipboy_probe.py check <FO4SFPipboyProbe.esm>
       python scripts/ui/make_pipboy_probe.py twin <dir> <Interface/file.swf>   the same movie again at that path

The plugin has no records. Its only job is to be active, so the game loads the archive named after it
("FO4SFPipboyProbe - Main.ba2"), which holds the stage (b) movie; this PC reads no loose files. It is written by
fo4sf.planet.esm.PluginWriter, the writer of our planet probe, with Starfield.esm as its only master.
`check` refuses anything else: not TES4, no ESM flag, another master, or any record or group. Nothing is written into
the repo. The staged folder is exp_install.py's shape (the plugin plus a Data tree): `exp_install.py install --pack`
packs Data into "FO4SFPipboyProbe - Main.ba2" beside the plugin.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, HERE)
from fo4sf.planet.esm import ESM, EsmError, Plugin, PluginWriter  # noqa: E402
import make_probe_swf  # noqa: E402

PLUGIN = "FO4SFPipboyProbe.esm"
ARCHIVE = "FO4SFPipboyProbe - Main.ba2"
MASTERS = ["Starfield.esm"]
MOVIE = "Interface/FO4SF_PipboyMenu.swf"      # the path FO4SF_PipboyMenu loads at stage (b), relative to Data
AUTHOR = "FO4SF"
DESCRIPTION = "FAL-187 Pip-Boy probe: empty; loads its archive"


def plugin_bytes():
    return PluginWriter(MASTERS, flags=ESM, author=AUTHOR, description=DESCRIPTION).to_bytes()


def stage(out, label=True):
    """Writes <out>/FO4SFPipboyProbe.esm and <out>/Data/Interface/FO4SF_PipboyMenu.swf; returns the two paths."""
    os.makedirs(out, exist_ok=True)
    esm = os.path.join(out, PLUGIN)
    with open(esm, "wb") as f:
        f.write(plugin_bytes())
    movie = os.path.join(out, "Data", *MOVIE.split("/"))
    make_probe_swf.write_movie(movie, label=make_probe_swf.LABEL if label else None)
    return esm, movie


def check(path):
    """The plugin as the probe needs it, or EsmError naming what is wrong."""
    with Plugin(path) as p:
        if not p.flags & ESM:
            raise EsmError(f"{path}: the ESM flag is not set")
        if p.masters != MASTERS:
            raise EsmError(f"{path}: masters {p.masters}, expected {MASTERS}")
        if p.groups:
            raise EsmError(f"{path}: has groups {sorted(p.groups)}, the probe plugin is empty")
        return {"plugin": os.path.basename(path), "flags": p.flags, "masters": p.masters, "groups": 0}


class TwinError(ValueError):
    pass


TWIN_SUFFIXES = (".swf", ".gfx")


def twin_problem(rel):
    """Why `rel` (relative to Data, "/" separated) cannot name a twin, or None. A twin is a vanilla movie's path under
    Interface/, served by the probe archive only; never our own movie's path."""
    parts = rel.split("/")
    if len(parts) < 2 or parts[0].lower() != "interface":
        return f"{rel!r}: a twin lives under Interface/"
    if any(p in ("", ".", "..") for p in parts) or not all(c.isascii() and (c.isalnum() or c in "_.-") for p in parts for c in p):
        return f"{rel!r}: letters, digits, _ . - and / only, no empty, . or .. part"
    if not rel.lower().endswith(TWIN_SUFFIXES):
        return f"{rel!r}: a twin ends in .swf or .gfx"
    if rel.lower() == MOVIE.lower():
        return f"{rel!r}: that is the overlay control's own movie"
    return None


def twin(out, rel):
    """The world candidate's movie (FAL-250; README "World surface"): the bytes of the movie `stage` wrote, label
    included, written again at <out>/Data/<rel>, so a vanilla menu that loads <rel> gets ours from the probe archive.
    Starfield's own Interface archive is not touched. Stage first; returns the twin's path."""
    problem = twin_problem(rel)
    if problem:
        raise TwinError(problem)
    with open(os.path.join(out, "Data", *MOVIE.split("/")), "rb") as f:
        data = f.read()
    make_probe_swf.read_movie(data)
    path = os.path.join(out, "Data", *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("out")
    s.add_argument("--no-label", action="store_true", help="the rectangle alone")
    c = sub.add_parser("check")
    c.add_argument("plugin")
    t = sub.add_parser("twin")
    t.add_argument("out")
    t.add_argument("path", help="relative to Data, e.g. Interface/<vanilla movie>.swf (FAL-250)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stage":
            esm, movie = stage(a.out, label=not a.no_label)
            check(esm)
            print(f"staged {esm} and {movie}; pack into {ARCHIVE}")
        elif a.cmd == "twin":
            print(f"staged twin {twin(a.out, a.path)}; set WorldMovie={a.path} in the ini")
        else:
            print(f"ok: {check(a.plugin)}")
    except (EsmError, make_probe_swf.SwfError, TwinError, OSError) as e:
        print(f"make_pipboy_probe: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
