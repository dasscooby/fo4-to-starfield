"""Stage the generic-graph control (docs/research/anim-generic-control.md, FAL-489; the Scribe's document vault111-console-stages rev 2):
FO4SFAnimGeneric.esm, its script and eight clips.

The question: does `genericstategraph01` (Sequence Names StateA..StateD, each _Idle and _Play; Send Event On End Trans01; no vanilla
ACTI/FURN names it) load on an object of ours, which PlayAnimation names does it take, which events reach Papyrus, and does the object
hold a pose between calls? The object is ACTI 0x801 of the plugin: a COPY of the vanilla holder 001CCAC2 (same model and rig) naming that
graph, with a clip folder of ours holding eight clips: StateA_Idle/Play and StateB_Idle/Play are copies of the vanilla holder's four files
(read from the game's archives at stage time) and StateC_* are copies of A, StateD_* of B (the .afx tag and file name rewritten).

usage:
  python make_anim_generic.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs, and each optional line's name, looked up in Starfield's base sources.
  python make_anim_generic.py stage --out <dir> --starfield <Starfield.esm> [--game-archive <ba2> ...] [--compiler <exe>]
                                    [--content-resources <zip>]
      1. dotnet/AnimGenericControl info + build + check against the Starfield.esm given (offline_check.txt; refuses when ACTI 001CCAC2
         is not there or does not name activatorstategraph01);
      2. the game's archives (default "Starfield - Meshes*.ba2" and "Starfield - Animations.ba2" next to the Starfield.esm): the graph
         genericstategraph01.agx (its path becomes the ACTI's ANAM) and the vanilla holder's four .af and four .afx (refuses and names
         each one it cannot find: nothing is invented); eight clips written under Data/Meshes/FO4SFAnimGeneric/Animations;
      3. the Papyrus compile as variant A's (each optional line on its own, the ones that compile are kept);
      4. plan.json (SHA-256 of every file, of Starfield.esm and of every vanilla file copied) and README.txt. Built in a new
         <out>.partial-<time>-<pid> and renamed to <out> only when every step passed; an existing <out> is refused.
  python make_anim_generic.py log [--file <FO4SFAnimG.0.log>]
      the run's user log as one table and a verdict (src/fo4sf/anim_probe_log.py, the same reader as variant A).
Nothing here installs anything: scripts/newgame/anim_generic_install.py does, on the owner's word, game closed. The kit holds copies of the
game's own clip files: it is never committed (no game assets in Git).
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import shutil
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "planet"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
import make_anim_probe as pa  # noqa: E402  (variant A: the precheck, the register shape and the helpers it takes from make_newgame)
import vault111_anim_graphs as graphs  # noqa: E402  (archive reading, read only)
from make_newgame import extract_sources, new_partial, run  # noqa: E402
from make_workshop_probe import compile_text, enable, optional_names, read_sources, sha256  # noqa: E402
from fo4sf import anim_probe_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "AnimGenericControl")
PLUGIN = "FO4SFAnimGeneric.esm"
SCRIPT = "FO4SF_AnimGenericQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
STARFIELD = pa.STARFIELD
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFAnimG.0.log")
KIND = "anim-generic"
GRAPH = "genericstategraph01"
CNAM = "FO4SFAnimGeneric\\Animations"                 # as the game stores it: relative to Meshes\
CLIP_DIR = "Data/Meshes/FO4SFAnimGeneric/Animations"
DEFAULT_ARCHIVES = ("Starfield - Meshes*.ba2", "Starfield - Animations.ba2")
SOURCES = ("StateA_Idle", "StateA_Play", "StateB_Idle", "StateB_Play")          # the vanilla holder's four clips
# the eight clips of the control: (our name, the vanilla clip it copies)
CLIPS = (("StateA_Idle", "StateA_Idle"), ("StateA_Play", "StateA_Play"), ("StateB_Idle", "StateB_Idle"), ("StateB_Play", "StateB_Play"),
         ("StateC_Idle", "StateA_Idle"), ("StateC_Play", "StateA_Play"), ("StateD_Idle", "StateB_Idle"), ("StateD_Play", "StateB_Play"))


def parse_info(text):
    """{key: value} of the tool's `info` lines (key=value)."""
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def meshes_name(folder, name, ext):
    """The archive name of a clip file: Meshes\\<folder>\\<name><ext> (the game's own CNAM is relative to Meshes\\)."""
    return "Meshes\\" + folder.strip("\\/").replace("/", "\\") + "\\" + name + ext


def read_vanilla(archives, folder):
    """({source name: (af bytes, afx bytes)}, {entry name: sha256}, [problems]) of the vanilla holder's four clips in its CNAM folder."""
    got, hashes, problems = {}, {}, []
    for name in SOURCES:
        pair = []
        for ext in (".af", ".afx"):
            entry = meshes_name(folder, name, ext)
            hit = graphs.find_entry(archives, entry)
            if hit is None:
                problems.append(f"{entry}: not in the archives read")
            elif isinstance(hit[1], Exception):
                problems.append(f"{entry}: found in {hit[0]} but unreadable: {hit[1]}")
            else:
                pair.append(hit[1])
                hashes[entry] = hashlib.sha256(hit[1]).hexdigest()
        if len(pair) == 2:
            got[name] = tuple(pair)
    return got, hashes, problems


def rename_afx(data, name):
    """The .afx bytes of a copy under another clip name: the <tag> and <filename> elements rewritten, everything else as the vanilla file
    has it. ValueError when the file is not the vanilla shape (XML with a <tag> and a <filename>): nothing is guessed."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise ValueError(f"the .afx is not XML ({e}); first bytes {data[:60]!r}")
    tag, filename = root.find("tag"), root.find("filename")
    if tag is None or filename is None:
        raise ValueError(f"the .afx has no <tag> or no <filename> element (children: {[c.tag for c in root]})")
    tag.text = name
    filename.text = name + ".af"
    return ET.tostring(root, encoding="utf-8")


def write_clips(out, vanilla):
    """Write the eight clips under CLIP_DIR; returns {our name: (vanilla name, written .afx tag, written .afx filename)}. A and B are the
    vanilla bytes unchanged; C and D are those bytes with the .afx renamed (the .af bytes are identical to A's and B's)."""
    folder = os.path.join(out, *CLIP_DIR.split("/"))
    os.makedirs(folder)
    report = {}
    for ours, src in CLIPS:
        af, afx = vanilla[src]
        if ours != src:
            afx = rename_afx(afx, ours)
        with open(os.path.join(folder, ours + ".af"), "wb") as f:
            f.write(af)
        with open(os.path.join(folder, ours + ".afx"), "wb") as f:
            f.write(afx)
        try:                                                     # a vanilla .afx that is not XML is refused above for a copy (C, D); A and B stay verbatim
            root = ET.fromstring(afx)
            report[ours] = {"copy_of": src, "afx_tag": root.findtext("tag"), "afx_filename": root.findtext("filename")}
        except ET.ParseError:
            report[ours] = {"copy_of": src, "afx_tag": None, "afx_filename": None}
    return report


def graph_anam(archives):
    """(ANAM as the game stores it, entry name) of genericstategraph01.agx in the archives; (None, None) when it is not there."""
    hits = graphs.graph_index(archives).get(GRAPH)
    if not hits:
        return None, None
    entry = hits[0][1].replace("/", "\\")
    return (entry[len("Meshes\\"):] if entry.lower().startswith("meshes\\") else entry), entry


def stage_files(out):
    """{path relative to the stage, "/" separated: SHA-256} of the plugin and every file under Data/."""
    return pa.stage_files(out)


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    problems = []
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the generic-graph control's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
    now = stage_files(stage_dir)
    for rel, h in plan["outputs"].items():
        if rel not in now:
            problems.append(f"{rel} missing")
        elif now[rel] != h:
            problems.append(f"{rel} changed after the stage (sha256 {now[rel]}, plan {h})")
    extra = sorted(set(now) - set(plan["outputs"]))
    if extra:
        problems.append(f"files not in plan.json: {extra}")
    if PLUGIN not in plan["outputs"]:
        problems.append(f"{PLUGIN} not pinned")
    for name, _ in CLIPS:
        for ext in (".af", ".afx"):
            if f"{CLIP_DIR}/{name}{ext}" not in plan["outputs"]:
                problems.append(f"{CLIP_DIR}/{name}{ext} not pinned")
    if data is not None:
        sf = os.path.join(data, "Starfield.esm")
        if not os.path.isfile(sf):
            problems.append(f"no Starfield.esm in {data}: name the game's Data folder (the install: the game folder)")
        elif sha256(sf) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm changed since the stage: re-stage")
    return problems


def load_plan(stage_dir):
    path = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_anim_generic.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def precheck(a):
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    r = pa.precheck_sources(read_sources(a.content_resources), text)
    for k, ok in r["required"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  {k}")
    for k, ok in r["optional"].items():
        print(f"{'declared' if ok else 'not declared'}  (optional) {k}")
    print(f"RegisterForAnimationEvent returns: {'bool' if r['register_returns_bool'] else ('nothing / other' if r['register_returns_bool'] is False else 'declaration not found')}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print("precheck: " + ("ok" if not r["missing"] else f"{len(r['missing'])} required name(s) missing; do not stage") +
          "".join(f"; optional {k} is not declared (that line stays off)" for k, ok in r["optional"].items() if not ok))
    return 0 if not r["missing"] else 1


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    data_dir = os.path.dirname(os.path.abspath(a.starfield))
    patterns = a.game_archive or list(DEFAULT_ARCHIVES)
    paths = sorted({p for pat in patterns for p in glob.glob(pat if os.path.isabs(pat) else os.path.join(data_dir, pat))})
    if not paths:
        sys.exit(f"no archive matched {patterns} under {data_dir}: name the game's archives with --game-archive")
    archives = graphs.open_archives(paths)
    anam, graph_entry = graph_anam(archives)
    if anam is None:
        sys.exit(f"{GRAPH}.agx is not in the archives read ({', '.join(os.path.basename(p) for p in paths)}): pass the one that holds the graphs "
                 f"(Starfield - Animations.ba2) with --game-archive")
    before = sha256(a.starfield)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    info = parse_info(run(tool + ["info", a.starfield]).stdout)
    if not info.get("cnam"):
        sys.exit("the tool's info says nothing about the vanilla holder's clip folder (cnam)")
    vanilla, hashes, problems = read_vanilla(archives, info["cnam"])
    if problems:
        sys.exit("the vanilla holder's clips cannot all be read, so the control is not built (nothing invented): " + "; ".join(problems))
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    wrote = run(tool + ["build", a.starfield, out, anam, CNAM]).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield, anam, CNAM]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    try:
        clip_report = write_clips(out, vanilla)
    except ValueError as e:
        sys.exit(f"a vanilla .afx is not the shape the copies need: {e} (attempt kept in {out})")
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    sources = read_sources(a.content_resources)
    src = extract_sources(a.content_resources, work)
    pre = pa.precheck_sources(sources, text)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    text = pa.reg_shape(text, pre["register_returns_bool"])
    scripts = os.path.join(out, "Data", "Scripts")
    fate, keep = {}, []
    for opt in optional_names(text):
        if not pre["optional"][opt]:
            fate[opt] = "not declared in the base scripts"
            continue
        ok, err = compile_text(a.compiler, enable(text, [opt]), src, os.path.join(work, "try"), SCRIPT)
        fate[opt] = "kept" if ok else f"declared but did not compile: {err}"
        if ok:
            keep.append(opt)
    final_text = enable(text, keep)
    ok, err = compile_text(a.compiler, final_text, src, scripts, SCRIPT)
    if not ok:
        sys.exit(f"the Papyrus compile of {SCRIPT}.psc with {keep or 'no optional line'} failed: {err} (attempt kept in {out})")
    with open(os.path.join(out, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
        f.write(final_text)
    shutil.rmtree(work)
    if sha256(a.starfield) != before:
        sys.exit(f"Starfield.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": KIND, "version": 1, "plugins": [PLUGIN], "outputs": stage_files(out), "inputs": {"Starfield.esm": {"sha256": before}},
            "graph": {"anam": anam, "archive_entry": graph_entry}, "cnam": CNAM, "vanilla_clips": hashes, "clips": clip_report,
            "archives": [os.path.basename(p) for p in paths], "optional": fate, "register_returns_bool": pre["register_returns_bool"],
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFAnimG.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Generic-graph control ({datetime.date.today().isoformat()}). docs/research/anim-generic-control.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): QUST FO4SF_AnimGenericQuest (start game enabled, stages 10..60: spawn the control ACTI 0x801
in front of the player, register for events, one PlayAnimation name per stage 21..28 with 15 s of listening, Activate by script at 30,
cleanup at 60) and ACTI FO4SF_AnimGenericControl: a copy of the vanilla holder 001CCAC2 whose animation graph is {anam} and whose clip
folder is {CNAM} (eight clips under {CLIP_DIR}: A and B are the vanilla holder's four files, C = A and D = B with the .afx renamed;
the .af bytes of C and D are those of A and B). Master Starfield.esm only; nothing is overridden. Checked against Starfield.esm {before}.
Re-stage after a game update. Optional lines: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}.
RegisterForAnimationEvent returns bool: {pre['register_returns_bool']}.
The clip files are copies of the game's own: this folder is never committed.
Install (the owner's word, game closed; loose scripts are not read, the installer packs them into a ba2):
  python scripts\\newgame\\anim_generic_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\newgame\\anim_generic_install.py uninstall --starfield <game dir>
Read:    python scripts\\newgame\\make_anim_generic.py log
Session card: docs/research/anim-generic-control.md. THROWAWAY STATE ONLY, NO SAVE (the spawned reference is persistent and would stay in it).
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, 8 clips, offline_check.txt, plan.json, README.txt; optional lines: {fate}")
    return 0


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = anim_probe_log.summarize(f)
    print("\n".join(anim_probe_log.report(s)))
    return 0 if s["spawned"] is not None else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--game-archive", action="append", default=[], help='a Starfield archive (absolute, or relative to the Starfield.esm\'s folder, * allowed); '
                   'default "Starfield - Meshes*.ba2" and "Starfield - Animations.ba2"')
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=cr)
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
