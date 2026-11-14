"""The Pip-Boy probe's empty plugin and its movie (FAL-187; sfse/FO4SFPipboyMenu/README.md).

usage: python scripts/ui/make_pipboy_probe.py stage <dir> [--no-label] [--channel | --page | --kit [--ini <ini>]
                                                                         [--color RRGGBB]]
                                                                         FO4SFPipboyProbe.esm + Data/Interface/<movie>
       python scripts/ui/make_pipboy_probe.py check <FO4SFPipboyProbe.esm>
       python scripts/ui/make_pipboy_probe.py twin <dir> <Interface/file.swf>   the same movie again at that path

The plugin has no records. Its only job is to be active, so the game loads the archive named after it
("FO4SFPipboyProbe - Main.ba2"), which holds the stage (b) movie; this PC reads no loose files. It is written by
fo4sf.planet.esm.PluginWriter, the writer of our planet probe, with Starfield.esm as its only master.
`check` refuses anything else: not TES4, no ESM flag, another master, or any record or group. Nothing is written into
the repo. The staged folder is exp_install.py's shape (the plugin plus a Data tree): `exp_install.py install --pack`
packs Data into "FO4SFPipboyProbe - Main.ba2" beside the plugin. `stage --channel` writes the movie with the data
channel's text field and button (FAL-216, the plugin's Stage=3) under the same name; `stage --page` writes the STAT
page (FAL-272, the plugin's Stage=4) under the same name; `stage --kit` writes the page kit's movie (FAL-301, the
plugin's Stage=5) under the same name, its main tabs drawn from the pages of --ini (the plugin's own ini by default:
install that same file beside the dll) in the colour --color. Both page movies come with the owner's card beside the
plugin: owner-card.txt, the launcher's plain-text card (a title and eight numbered one-line steps;
docs/spikes/pipboy-stat-page-owner-card.md and docs/spikes/pipboy-page-kit-owner-card.md are the full cards). It is
outside Data, so it is neither packed nor installed.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, HERE)
from fo4sf.planet.esm import ESM, EsmError, Plugin, PluginWriter  # noqa: E402
import make_pipboy_kit  # noqa: E402
import make_probe_swf  # noqa: E402

PLUGIN = "FO4SFPipboyProbe.esm"
ARCHIVE = "FO4SFPipboyProbe - Main.ba2"
MASTERS = ["Starfield.esm"]
MOVIE = "Interface/FO4SF_PipboyMenu.swf"      # the path FO4SF_PipboyMenu loads at stage (b), relative to Data
AUTHOR = "FO4SF"
DESCRIPTION = "FAL-187 Pip-Boy probe: empty; loads its archive"
OWNER_CARD = "owner-card.txt"
PAGE_CARD = """Pip-Boy STAT page
1. In a loaded game, standing somewhere safe, press F10: a green panel with seven lines and two buttons appears.
2. Read the seven lines and write down HEALTH, LEVEL, CARRY WEIGHT MAX, TIME and any line that shows a question mark.
3. Touch nothing for ten seconds and say whether the minutes of TIME went up.
4. Move the mouse until the small pointer is on NEXT TAB and click once: TAB 2 OF 2 appears and UPDATES counts up.
5. Click NEXT TAB again and say whether TAB 1 OF 2 came back.
6. Click CLOSE and say whether the panel went away and you can walk again.
7. Walk through a door or about thirty steps, then press F10 and say which lines changed.
8. Press F10 and say whether the panel closed; if anything was odd, say what.
"""

KIT_CARD = """Pip-Boy page kit
1. In a loaded game, standing somewhere safe, press F10: a green screen with STAT INV DATA MAP RADIO at the top.
2. Write down every row that shows a question mark, then press S three times and W once: the bright bar follows.
3. Press D: SPECIAL shows seven rows, STRENGTH to LUCK; write down the seven numbers.
4. Press E twice, then D, then hold S for three seconds: KIT TEST scrolls and stops at TEST ROW 30.
5. Click one TEST ROW line, then click MAP at the top, and say whether both clicks worked.
6. Press Q until the bracket is back on STAT, then click SPECIAL, and say whether Q and the click worked.
7. Press Tab once, then Esc once: say what the game did on each; if Esc opened the game's menu, close it with Esc.
8. Click CLOSE, then press F10 twice, two seconds apart: say whether it reopened on SPECIAL, then closed.
"""


def plugin_bytes():
    return PluginWriter(MASTERS, flags=ESM, author=AUTHOR, description=DESCRIPTION).to_bytes()


def stage(out, label=True, channel=False, page=False, kit=False, ini=make_pipboy_kit.INI,
          color=make_pipboy_kit.PIPBOY_GREEN):
    """Writes <out>/FO4SFPipboyProbe.esm and <out>/Data/Interface/FO4SF_PipboyMenu.swf (with page or kit, also
    <out>/owner-card.txt, that movie's card); returns the plugin's and the movie's paths. kit: the page kit's movie for
    the pages of `ini`, in `color` (the pages are checked first; a wrong one writes nothing)."""
    if kit and (channel or page):
        raise make_probe_swf.SwfError("--kit, --channel and --page are different movies")
    kit_pages = make_pipboy_kit.read_kit(ini) if kit else None
    os.makedirs(out, exist_ok=True)
    esm = os.path.join(out, PLUGIN)
    with open(esm, "wb") as f:
        f.write(plugin_bytes())
    movie = os.path.join(out, "Data", *MOVIE.split("/"))
    if kit:
        os.makedirs(os.path.dirname(movie), exist_ok=True)
        with open(movie, "wb") as f:
            f.write(make_pipboy_kit.kit_movie_bytes(kit_pages, color=color))
    else:
        make_probe_swf.write_movie(movie, label=make_probe_swf.LABEL if label else None, channel=channel, page=page)
    card = os.path.join(out, OWNER_CARD)
    text = KIT_CARD if kit else PAGE_CARD if page else None
    if text:
        with open(card, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    elif os.path.exists(card):
        os.remove(card)
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
    kind = s.add_mutually_exclusive_group()
    kind.add_argument("--channel", action="store_true", help="the data channel's movie (FAL-216, Stage=3)")
    kind.add_argument("--page", action="store_true", help="the STAT page's movie (FAL-272, Stage=4)")
    kind.add_argument("--kit", action="store_true", help="the page kit's movie (FAL-301, Stage=5)")
    s.add_argument("--ini", default=make_pipboy_kit.INI, help="--kit: the ini with the pages (the plugin's own)")
    s.add_argument("--color", default=f"{make_pipboy_kit.PIPBOY_GREEN:06X}", help="--kit: the phosphor colour, RRGGBB")
    c = sub.add_parser("check")
    c.add_argument("plugin")
    t = sub.add_parser("twin")
    t.add_argument("out")
    t.add_argument("path", help="relative to Data, e.g. Interface/<vanilla movie>.swf (FAL-250)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stage":
            if not re.fullmatch(r"[0-9A-Fa-f]{6}", a.color):
                raise make_probe_swf.SwfError(f"--color {a.color!r} is not RRGGBB")
            esm, movie = stage(a.out, label=not a.no_label, channel=a.channel, page=a.page, kit=a.kit, ini=a.ini,
                               color=int(a.color, 16))
            check(esm)
            print(f"staged {esm} and {movie}; pack into {ARCHIVE}")
        elif a.cmd == "twin":
            print(f"staged twin {twin(a.out, a.path)}; set WorldMovie={a.path} in the ini")
        else:
            print(f"ok: {check(a.plugin)}")
    except (EsmError, make_probe_swf.SwfError, make_pipboy_kit.KitError, TwinError, OSError, UnicodeDecodeError) as e:
        print(f"make_pipboy_probe: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
