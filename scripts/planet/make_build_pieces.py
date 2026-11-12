"""Stage the build pieces kit (docs/research/build-pieces.md): FO4SFBuildPieces.esm and its quest script.

usage:
  python make_build_pieces.py menu [--starfield <Starfield.esm>] [--cobj <editor id>]
      read only, no game: how the outpost build menu lists a buildable, read from the real COBJ (default
      co_Outpost_Crafting_WorkbenchIndustrialStation 2E2F2C): its created object, workbench keyword, filters, build limit,
      components, the other recipes under the same workbench keyword, the outpost category keywords (dotnet/BuildPieces).
  python make_build_pieces.py core [--core <FO4TerrainCore.esm>] [--pieces a,b,c]
      read only: the statics of the installed core and the pieces a build would use (editor id, local id, model).
  python make_build_pieces.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only: every native the script needs, looked up in Starfield's base sources. Exit 1 when one is missing.
  python make_build_pieces.py stage --out <dir> [--starfield ..] [--core ..] [--compiler ..] [--content-resources ..]
                                     [--pieces a,b,c] [--shell clone|plain] [--category vanilla|add|replace] [--cobj ..]
                                     [--tab ..] [--workbench <kywd>] [--filter <kywd|own>] [--variants (EXPERIMENTAL: crashes the game at load)] [--inner same|bare] [--lead none|shells]
                                     [--pictures N (default: every piece with --set fo4)] [--template-filing] [--set fo4]
      1. dotnet/BuildPieces build + check against the Starfield.esm and core given (offline_check.txt);
      2. the Papyrus compile of FO4SF_BPQuest with the core ids put in (the ;COREIDS line);
      3. plan.json (SHA-256 of every file and of both inputs, the variant, the pieces) and README.txt. Built in a new
         <out>.partial-<time>-<pid> and renamed to <out> only when every step passed; an existing <out> is refused.
  python make_build_pieces.py log [--file <FO4SFBP.0.log>]
      the run's user log and a verdict (src/fo4sf/workshop/build_pieces_log.py); exit 0 when every named piece was found.
The variants are a ladder (the real menu is not readable offline): --shell clone (default) copies the template's created object,
plain is a bare Activator; --category vanilla (default) keeps the template's filters (the CRAFTING tab), add appends a keyword
of our own, replace swaps the first filter for it. Stage the next variant when the last one shows nothing.
Nothing here installs anything: scripts/planet/build_pieces_install.py does, on the owner's word, game closed.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
sys.path.insert(0, os.path.join(REPO, "src"))
from make_newgame import extract_sources, new_partial, run  # noqa: E402
import make_workshop_probe as wp  # noqa: E402
from fo4sf.workshop import build_pieces_log, piece_icons  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "BuildPieces")
PLUGIN = "FO4SFBuildPieces.esm"
SCRIPT = "FO4SF_BPQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
STARFIELD = wp.STARFIELD
CORE_NAME = "FO4TerrainCore.esm"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFBP.0.log")
DEFAULT_COBJ = "co_Outpost_Crafting_WorkbenchIndustrialStation"
REQUIRED = {
    "Game": ["GetFormFromFile", "IsPluginInstalled"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
    "Utility": ["GetCurrentRealTime"],
    "ScriptObject": ["StartTimer"],
    "Form": ["GetFormID"],
}
CORE_LINE = re.compile(r"^    ;COREIDS$", re.M)
MAX_PIECES = 40
# the default placement of --set fo4 (rung A, PC pass at 211dae28): the recipes keep workbench keyword 2CFDE6 (the workshop offers them)
# and are filed by filter 06D72D (the MISCELLANEOUS tab, after its two vanilla entries); --template-filing keeps the template's instead
FO4_WORKBENCH, FO4_FILTER = "2CFDE6", "06D72D"


def set_core_ids(text, pieces):
    """The script's text with the pieces' core local ids put in at the ;COREIDS line (an array of len(pieces))."""
    if len(CORE_LINE.findall(text)) != 1:
        sys.exit("the script has not exactly one '    ;COREIDS' line to put the ids into")
    if not 0 < len(pieces) <= MAX_PIECES:
        sys.exit(f"{len(pieces)} pieces: 1 to {MAX_PIECES} are possible")
    lines = [f"    CoreIds = new int[{len(pieces)}]"] + [f"    CoreIds[{i}] = 0x{p['core_id']:06X}" for i, p in enumerate(pieces)]
    lines += [f"    RecipeIds = new int[{len(pieces)}]"] + [f"    RecipeIds[{i}] = 0x{p['recipe_id']:06X}" for i, p in enumerate(pieces)]
    return CORE_LINE.sub(lambda m: "\n".join(lines), text)


def tool(args, **kw):
    return run(["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"] + args, **kw)


def variant_opts(a):
    o = ["--shell", a.shell, "--category", a.category, "--cobj", a.cobj]
    if a.pieces:
        o += ["--pieces", a.pieces]
    if a.set:
        o += ["--set", a.set]
    if a.tab:
        o += ["--tab", a.tab]
    if a.workbench:
        o += ["--workbench", a.workbench]
    if a.filter:
        o += ["--filter", a.filter]
    if a.variants:
        o += ["--variants", "--inner", a.inner, "--lead", a.lead]
    return o


VARIANTS_WARNING = ("WARNING: --variants is EXPERIMENTAL. At 47dc064b the game crashed before the main menu (0xC0000005) with it, "
                    "with and without pictures. Do not use it in a kit you want to keep; the default stage (no --variants) works.")


def default_filing(a):
    """--set fo4 without any filing switch of its own: workbench 2CFDE6 and filter 06D72D (the MISCELLANEOUS tab). Returns True when it applied."""
    if a.set == "fo4" and not (a.workbench or a.filter or a.tab or a.template_filing) and a.category == "vanilla":
        a.workbench, a.filter = FO4_WORKBENCH, FO4_FILTER
        return True
    return False


def write_pictures(out, pieces, count):
    """The first `count` pieces' pictures under Data/Textures/Interface/WorkshopIcons/<plugin>/<shell id, 8 hex>cl.dds (128 x 128 BC3, DX10 header)."""
    paths = []
    for p in pieces[:count]:
        rel = piece_icons.icon_path(PLUGIN, 0x802 + p["n"] - 1)
        full = os.path.join(out, "Data", *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(piece_icons.dds(p["n"], p["edid"], p["name"]))
        paths.append(rel)
    return paths


def menu(a):
    tool(["menu", a.starfield, "--cobj", a.cobj])
    return 0


def core(a):
    tool(["core", a.core] + (["--pieces", a.pieces] if a.pieces else []) + (["--set", a.set] if a.set else []))
    return 0


def precheck(a):
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    sources = wp.read_sources(a.content_resources)
    from make_newgame import declares  # noqa: E402
    req = {f"{b}.{n}": declares(sources, b, n) for b, ns in REQUIRED.items() for n in ns}
    for k, ok in req.items():
        print(f"{'ok  ' if ok else 'MISSING'}  {k}")
    missing = [k for k, ok in req.items() if not ok]
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"required": req, "missing": missing}, f, indent=1)
    print("precheck: " + ("ok" if not missing else f"{len(missing)} required name(s) missing; do not stage") + f" ({len(text.splitlines())} script lines read)")
    return 0 if not missing else 1


def stage_files(out):
    return wp.stage_files(out)


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    if plan.get("kind") != "build-pieces" or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the build pieces kit's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
    problems = []
    now = stage_files(stage_dir)
    for rel, h in plan["outputs"].items():
        if rel not in now:
            problems.append(f"{rel} missing")
        elif now[rel] != h:
            problems.append(f"{rel} changed after the stage (sha256 {now[rel]}, plan {h})")
    extra = sorted(set(now) - set(plan["outputs"]))
    if extra:
        problems.append(f"files not in plan.json: {extra}")
    if data is not None:
        sf = os.path.join(data, "Starfield.esm")
        if not os.path.isfile(sf):
            problems.append(f"no Starfield.esm in {data}: name the game's Data folder (the install: the game folder)")
        elif wp.sha256(sf) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm changed since the stage: re-stage")
        cp = os.path.join(data, CORE_NAME)
        if os.path.isfile(cp) and wp.sha256(cp) != plan["inputs"]["core"]["sha256"]:
            problems.append(f"{CORE_NAME} changed since the stage: re-stage (the pieces' models were read from it)")
    return problems


def load_plan(stage_dir):
    path = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_build_pieces.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage(a):
    final = os.path.abspath(a.out)
    default_applied = default_filing(a)
    if a.variants:
        print(VARIANTS_WARNING, file=sys.stderr)
    if a.pictures is not None and not 0 <= a.pictures <= MAX_PIECES:
        sys.exit(f"--pictures is 0 to {MAX_PIECES}")
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    sf_before, core_before = wp.sha256(a.starfield), wp.sha256(a.core)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    opts = variant_opts(a)
    pj = tool(["pieces", a.core] + (["--pieces", a.pieces] if a.pieces else []) + (["--set", a.set] if a.set else []) + (["--variants"] if a.variants else []), check=True).stdout
    pieces = json.loads([l for l in pj.splitlines() if l.startswith("[")][-1])
    wrote = tool(["build", a.starfield, a.core, out] + opts).stdout
    check = tool(["check", os.path.join(out, PLUGIN), a.starfield, a.core] + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = set_core_ids(f.read(), pieces)
    src = extract_sources(a.content_resources, work)
    from make_newgame import declares  # noqa: E402
    sources = wp.read_sources(a.content_resources)
    missing = [f"{b}.{n}" for b, ns in REQUIRED.items() for n in ns if not declares(sources, b, n)]
    if missing:
        sys.exit(f"the base scripts do not declare {missing}: do not stage (attempt kept in {out})")
    scripts = os.path.join(out, "Data", "Scripts")
    ok, err = wp.compile_text(a.compiler, text, src, scripts, SCRIPT)
    if not ok:
        sys.exit(f"the Papyrus compile of {SCRIPT}.psc failed: {err} (attempt kept in {out})")
    with open(os.path.join(out, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    shutil.rmtree(work)
    pictures = write_pictures(out, pieces, len(pieces) if a.pictures is None and a.set else (a.pictures or 0))   # --set fo4: a picture for every piece unless --pictures N says otherwise
    menu_txt = tool(["menu", a.starfield, "--cobj", a.cobj], check=False).stdout
    with open(os.path.join(out, "menu.txt"), "w", encoding="utf-8") as f:
        f.write(menu_txt)
    if wp.sha256(a.starfield) != sf_before or wp.sha256(a.core) != core_before:
        sys.exit(f"Starfield.esm or the core changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": "build-pieces", "version": 1, "plugins": [PLUGIN], "outputs": stage_files(out),
            "inputs": {"Starfield.esm": {"sha256": sf_before}, "core": {"name": os.path.basename(a.core), "sha256": core_before}},
            "variant": {"shell": a.shell, "category": a.category, "tab": a.tab or None, "set": a.set or None, "cobj": a.cobj,
                         "workbench": a.workbench or None, "filter": a.filter or None, "variants": bool(a.variants),
                         "inner": a.inner if a.variants else None, "lead": a.lead if a.variants else None, "pictures": pictures, "default_filing": default_applied}, "pieces": pieces,
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFBP.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    names = "; ".join(f"{p['n']}: {p['name']} (core {p['core_id']:06X} {p['edid']})" for p in pieces)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Build pieces ({datetime.date.today().isoformat()}). docs/research/build-pieces.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): {len(pieces)} buildables for the outpost build menu, one recipe each (a copy of {a.cobj}),
variant shell={a.shell} category={a.category} tab={a.tab or 'none'} workbench={a.workbench or 'template'} filter={a.filter or 'template'} variants={'EXPERIMENTAL (inner recipes ' + a.inner + ', list lead ' + a.lead + '): crashed the game at load at 47dc064b' if a.variants else 'no'} set={a.set or 'none'} pictures={len(pictures)}. Pieces: {names}.
Master Starfield.esm only; adds records, overrides none; the installed core is not a master (its model paths were read at stage time).
Checked against Starfield.esm {sf_before} and {os.path.basename(a.core)} {core_before}. Re-stage after a game or core update.
{('Pictures: ' + ', '.join(pictures) + ' (the installer packs them into FO4SFBuildPieces - Textures.ba2).' + chr(10)) if pictures else ''}Install (the owner's word, game closed; loose scripts are not read, the installer packs them into ba2 archives):
  python scripts\\planet\\build_pieces_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\planet\\build_pieces_install.py uninstall --starfield <game dir>
Read:    python scripts\\planet\\make_build_pieces.py log
Card: docs/research/build-pieces.md. THROWAWAY STATE ONLY, NO SAVE. menu.txt is what the real COBJ reads as.
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, offline_check.txt, menu.txt, plan.json, README.txt; variant {plan['variant']}")
    return 0


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = build_pieces_log.summarize(f)
    print("\n".join(build_pieces_log.report(s)))
    return 0 if s["ok"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    sfp = os.path.join(STARFIELD, "Data", "Starfield.esm")
    corep = os.path.join(STARFIELD, "Data", CORE_NAME)

    def variant(sp):
        sp.add_argument("--pieces", default="", help="comma separated editor ids (* allowed) of core statics, 3 to 40 (default: the tool's four)")
        sp.add_argument("--set", default="", choices=("", "fo4"), help="a named set of core statics (fo4: junk walls, pier shack walls and roofs, sandbags, bed, table, crates, barrel)")
        sp.add_argument("--tab", default="", help="file the recipes under a vanilla outpost category keyword (structures, furniture, decorations, miscellaneous, storage, defenses or an editor id); needs --category add|replace")
        sp.add_argument("--workbench", default="", help="the recipes' workbench keyword (a keyword editor id or 6 hex digits of its form id), chosen apart from the filter; not with --tab or --category add|replace")
        sp.add_argument("--filter", default="", help="the recipes' only filter keyword (editor id, 6 hex digits, or 'own' = a keyword of our own with a full name); the template's workbench stays unless --workbench")
        sp.add_argument("--variants", action="store_true", help="EXPERIMENTAL, OFF by default: crashed the game before the main menu at 47dc064b (PC, 11 Nov). One recipe per group (junk walls 01..07, pier shack walls, roofs) whose created object is a form list of recipes; stage it only to test the crash, one --inner/--lead rung at a time")
        sp.add_argument("--lead", choices=("none", "shells"), default="none", help="--variants: the form list holds only the recipes (none) or the shells first and then the recipes (as the vanilla list)")
        sp.add_argument("--shell", choices=("clone", "plain"), default="clone")
        sp.add_argument("--category", choices=("vanilla", "add", "replace"), default="vanilla")
        sp.add_argument("--cobj", default=DEFAULT_COBJ)
        sp.add_argument("--inner", choices=("same", "bare"), default="same", help="--variants: the filing of the recipes inside the list: same as the list's recipe, or bare (no workbench keyword, no filter)")
        sp.add_argument("--pictures", type=int, default=None, help="draw 128 x 128 pictures for the first N pieces' shells (BC3, DX10 header); the installer puts them in a texture archive. Default: every piece with --set fo4 (the game showed them at 47dc064b), none otherwise; 0 = none")
        sp.add_argument("--template-filing", action="store_true", help="--set fo4: keep the template's workbench keyword and filters (the CRAFTING tab) instead of the default 2CFDE6 / 06D72D")
    m = sub.add_parser("menu")
    m.add_argument("--starfield", default=sfp)
    m.add_argument("--cobj", default=DEFAULT_COBJ)
    c = sub.add_parser("core")
    c.add_argument("--core", default=corep)
    c.add_argument("--pieces", default="")
    c.add_argument("--set", default="", choices=("", "fo4"))
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--starfield", default=sfp)
    s.add_argument("--core", default=corep)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=cr)
    variant(s)
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"menu": menu, "core": core, "precheck": precheck, "stage": stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
