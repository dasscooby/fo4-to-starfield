"""Stage the door and lift controls (docs/research/anim-doorlift-control.md, FAL-489; the Scribe's vault111-gear-door rev 4 section 2c):
FO4SFAnimDoorLift.esm and its script. No clip is written: both controls use the game's own clips where they already are.

Two controls, one session:
  DOOR  ACTI 0x801 of the plugin, a NEW activator with the model, rig (BNAM) and clip folder (CNAM) of the vanilla DOOR
        AK_Ext_Bld_WallA_DoorA_01_Alt02 (000AA24A; its Open/Close clips live on SimpleOpenClose01) whose animation graph is
        genericopenclose01 (0 vanilla users). The vanilla door is not overridden and not placed.
  LIFT  the vanilla ShipQuickLift1 (00010C35, graph twostages), placed unchanged by the quest (its own stage 30), 5 m ahead and 3 m to the right of the player.

usage:
  python make_anim_doorlift.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs, and each optional line's name, looked up in Starfield's base sources.
  python make_anim_doorlift.py stage --out <dir> --starfield <Starfield.esm> [--game-archive <ba2> ...] [--compiler <exe>]
                                     [--content-resources <zip>]
      1. dotnet/AnimDoorLiftControl info + build + check against the Starfield.esm given (offline_check.txt; refuses when the DOOR is not
         there, has no graph component or does not name simpleopenclose01; the LIFT is only read: what it is and which graph it names is
         printed, never refused);
      2. the game's archives (default "Starfield - Meshes*.ba2" and "Starfield - Animations.ba2" next to the Starfield.esm): the graph
         genericopenclose01.agx (its path becomes the ACTI's ANAM); refuses and names it when it is not there;
      3. the Papyrus compile as variant A's (each optional line on its own, the ones that compile are kept);
      4. plan.json (SHA-256 of every file and of Starfield.esm) and README.txt. Built in a new <out>.partial-<time>-<pid> and renamed to
         <out> only when every step passed; an existing <out> is refused.
  python make_anim_doorlift.py log [--file <FO4SFAnimDL.0.log>]
      the run's user log as one table and a verdict (src/fo4sf/anim_probe_log.py, the same reader as variant A).
Nothing here installs anything: scripts/newgame/anim_doorlift_install.py does, on the owner's word, game closed.
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "planet"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
import make_anim_generic as mag  # noqa: E402  (the generic control: info parsing, the archive helpers, the log command's reader)
import make_anim_probe as pa  # noqa: E402
import vault111_anim_graphs as graphs  # noqa: E402
from make_newgame import extract_sources, new_partial, run  # noqa: E402
from make_workshop_probe import compile_text, enable, optional_names, read_sources, sha256  # noqa: E402
from fo4sf import anim_probe_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "AnimDoorLiftControl")
PLUGIN = "FO4SFAnimDoorLift.esm"
SCRIPT = "FO4SF_AnimDoorLiftQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
STARFIELD = pa.STARFIELD
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFAnimDL.0.log")
KIND = "anim-doorlift"
GRAPH = "genericopenclose01"
DEFAULT_ARCHIVES = mag.DEFAULT_ARCHIVES
parse_info = mag.parse_info


def graph_anam(archives):
    """(ANAM as the game stores it, entry name) of genericopenclose01.agx in the archives; (None, None) when it is not there."""
    hits = graphs.graph_index(archives).get(GRAPH)
    if not hits:
        return None, None
    entry = hits[0][1].replace("/", "\\")
    return (entry[len("Meshes\\"):] if entry.lower().startswith("meshes\\") else entry), entry


def stage_list(psc_text):
    """The quest's stages as the README and the card write them: runs of consecutive numbers as a..b, read from the script's StageList lines
    (so the text cannot drift from the quest: 10 20..24 30..36 40 60)."""
    nums = [int(n) for n in re.findall(r"StageList\[\d+\] = (\d+)", psc_text)]
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if j - i < 2 else f"{nums[i]}..{nums[j]}")
        if j - i == 1:
            out.append(str(nums[j]))
        i = j + 1
    return " ".join(out)


def stage_files(out):
    return pa.stage_files(out)


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the door and lift control's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
    for rel in (PLUGIN, f"Data/Scripts/{SCRIPT}.pex"):
        if rel not in plan["outputs"]:
            problems.append(f"{rel} not pinned")
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
        sys.exit(f"{path} missing: stage with make_anim_doorlift.py first")
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
    info_out = run(tool + ["info", a.starfield]).stdout
    info = parse_info(info_out)
    if not info.get("door_cnam"):
        sys.exit("the tool's info says nothing about the vanilla door's clip folder (door_cnam)")
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    wrote = run(tool + ["build", a.starfield, out, anam]).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield, anam]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
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
            "graph": {"anam": anam, "archive_entry": graph_entry}, "vanilla": info, "archives": [os.path.basename(p) for p in paths],
            "optional": fate, "register_returns_bool": pre["register_returns_bool"],
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFAnimDL.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    lift = f"{info.get('lift_type')} {info.get('lift_edid')}; graph: {info.get('lift_graph')}"
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Door and lift controls ({datetime.date.today().isoformat()}). docs/research/anim-doorlift-control.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): QUST FO4SF_AnimDoorLiftQuest (start game enabled, stages {stage_list(text)}: place both,
register for events, one call per stage with 15 s of listening, cleanup at 60) and ACTI FO4SF_AnimDoorControl: a new activator with the model,
rig and clip folder of the vanilla door {info.get('door_edid')} (000AA24A) and the graph {anam}. The vanilla door is not placed. The lift is
the vanilla ShipQuickLift1 (00010C35) placed unchanged, 5 m ahead and 3 m to the right of the player (this Starfield.esm says it is: {lift}).
Master Starfield.esm only; nothing is overridden. Checked against Starfield.esm {before}. Re-stage after a game update.
Optional lines: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}. RegisterForAnimationEvent returns bool: {pre['register_returns_bool']}.
No clip file is copied or written: this folder holds no game asset. The lift is a MOVING PLATFORM: stand well away from where it is placed.
Install (the owner's word, game closed; loose scripts are not read, the installer packs them into a ba2):
  python scripts\\newgame\\anim_doorlift_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\newgame\\anim_doorlift_install.py uninstall --starfield <game dir>
Read:    python scripts\\newgame\\make_anim_doorlift.py log
Session card: docs/research/anim-doorlift-control.md. THROWAWAY STATE ONLY, NO SAVE (the spawned references are persistent and would stay in it).
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, offline_check.txt, plan.json, README.txt; optional lines: {fate}")
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
