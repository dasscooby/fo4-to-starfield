"""Stage the converted Vault 111 console on genericstategraph01, four states in a row (docs/research/anim-console-four.md, FAL-489; the
Scribe's vault111-console-stages rev 4).

The generic control (PR #756; PC session 12 Nov 22:35 to 22:47 UTC) showed that genericstategraph01 loads on an object of ours, that Play01..Play04
and the direct StateC_Play / StateC_Idle / StateD_Idle answer true and that every Idle slot holds. There the C and D clips were copies of A and B, so
they could not be told apart by eye. This kit puts the port's own console on that graph with eight DIFFERENT clips:
  StateA_Idle  rest (lid shut, button up): the first frame of the first mapped sequence
  StateA_Play  the first mapped sequence (default Stage2, the lid, 1.633 s)           -> StateB_Idle: the pose after it (lid open)
  StateB_Play  the second (default Stage3, the button, 0.633 s)                       -> StateC_Idle: the pose after it (button down)
  StateC_Play  the third (default Stage4, 0.033 s)                                    -> StateD_Idle: the pose after it (the end pose)
  StateD_Play  spare: a one-frame hold of the last pose (nothing should move)
Each clip starts from the pose the one before it ended in (a bone a clip leaves standing is held at that pose: src/fo4sf/anim_object.py
add_chain_idles). Which pose each state SHOULD show is on the card; what the game shows is the session's result.

usage:
  python make_anim_console_four.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs against ContentResources.zip, and the register call's return type.
  python make_anim_console_four.py clips --fo4-data <Fallout 4 Data> [--port-data <dir>] [--model <FO4 mesh path>] [--edid <EditorID>]
      read only (make_anim_console.py clips): the console's Fallout 4 sequences with seconds, bones and the motion of every track.
  python make_anim_console_four.py stage --out <new dir> --starfield-data <Starfield Data> --fo4-data <Fallout 4 Data>
         --door-anim-dll <CALUMI.Animation dll> --collision-template <nif> --texconv <texconv.exe> --content-resources <zip>
         [--states "Stage2=StateA_Play,Stage3=StateB_Play,Stage4=StateC_Play"] [--port-data <dir with FO4Port.esm and its archives>]
         [--game-archive <ba2> ...] [--foley <name>] [--model <FO4 mesh path>] [--edid <EditorID>] [--compiler <exe>]
      1. genericstategraph01.agx in the game's archives (default "Starfield - Meshes*.ba2" and "Starfield - Animations.ba2" in --starfield-data):
         its path becomes the ANAM; refuses and names it when it is not there;
      2. the plugin tool's `info` on FO4Port.esm; the conversion of the console (pipeline.Converter.convert_anim_object, idles="chain", the real
         graph path): model, rig, eight clips, materials; only meshes, geometries and materials go in the kit (every texture must already be in
         the port's archives, or the stage refuses and lists them);
      3. dotnet/AnimConsoleFour build + check (offline_check.txt), the Papyrus compile (optional lines kept when they compile; the register call in
         the shape the game declares; BaseId written into the script), plan.json with a SHA-256 of every file, anim_manifest.json, README.txt.
         Built in a new <out>.partial-<time>-<pid> and renamed to <out> only when every step passed.
  python make_anim_console_four.py inspect --stage <staged kit folder>      (make_anim_console.py inspect: rig, tracks, predicted poses)
  python make_anim_console_four.py dump --stage <staged kit folder> --dll <CALUMI.Animation.dll>      (make_anim_console.py dump)
  python make_anim_console_four.py log [--file <FO4SFAnimF.0.log>]
      the run's user log as one table and a verdict (src/fo4sf/anim_probe_log.py, the same reader as variant A).
Nothing here installs anything: scripts/newgame/anim_console_four_install.py does, on the owner's word, game closed. Needs numpy, the CALUMI.Animation
library and the game's archives: the PC's part. Nothing of the game enters the repo.
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
import make_anim_console as mac  # noqa: E402  (variant D: info parsing, the original, the converter, the kit files, inspect, dump)
import make_anim_probe as probe_a  # noqa: E402
import vault111_anim_graphs as graphs  # noqa: E402  (archive reading, read only)
from make_newgame import extract_sources, new_partial, run  # noqa: E402
from make_workshop_probe import compile_text, enable, optional_names, read_sources, sha256  # noqa: E402
from fo4sf import anim_object, anim_probe_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "AnimConsoleFour")
PLUGIN = "FO4SFAnimConsoleFour.esm"
SCRIPT = "FO4SF_AnimConsoleFourQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
KIND = "anim-console-four"
GRAPH = "genericstategraph01"
# The map of the SCENE (FAL-489, PC session 12 Nov 23:57 UTC): the graph returns from StateB_Play to the rest pose (Play02 ended at rest), so the button
# clip goes on StateC_Play, whose Idle (StateC_Idle) is the pose "lid open, button down". The three held poses are the same as with the Scribe's rev 4
# map (Stage2=StateA_Play,Stage3=StateB_Play,Stage4=StateC_Play); only the slot of the button and of Stage4 change, StateB_Play becomes the spare.
STATES_DEFAULT = "Stage2=StateA_Play,Stage3=StateC_Play,Stage4=StateD_Play"
SLOW_DEFAULT = "Stage3=4"             # the button clip four times slower (0.633 s -> 2.533 s), so a shot 1.2 s after the call still catches it; "" = as authored
DEFAULT_ARCHIVES = ("Starfield - Meshes*.ba2", "Starfield - Animations.ba2")
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFAnimF.0.log")
STARFIELD = mac.STARFIELD
EDID = mac.EDID
IDLES = ("StateA_Idle", "StateB_Idle", "StateC_Idle", "StateD_Idle")


def graph_anam(archives):
    """(ANAM as the game stores it, entry name) of genericstategraph01.agx in the archives; (None, None) when it is not there."""
    hits = graphs.graph_index(archives).get(GRAPH)
    if not hits:
        return None, None
    entry = hits[0][1].replace("/", "\\")
    return (entry[len("Meshes\\"):] if entry.lower().startswith("meshes\\") else entry), entry


def pose_lines(clips):
    """One line per Idle slot, what the clip table says it holds: 'StateB_Idle holds the last frame of StateA_Play'."""
    by = {c["name"]: c for c in clips}
    out = []
    for idle in IDLES:
        c = by.get(idle)
        out.append(f"{idle}: " + (f"holds the {c.get('hold_frame') or 'last'} frame of {c['hold_of']}" if c and c.get("hold_of") else "not in the clip table"))
    return out


def stage_files(out):
    return probe_a.stage_files(out)


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    problems = []
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the four-state console kit's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
    if data is not None:
        for name in ("Starfield.esm",):
            p = os.path.join(data, name)
            if not os.path.isfile(p):
                problems.append(f"no {name} in {data}: name the game's Data folder (the install: the game folder)")
            elif sha256(p) != plan["inputs"][name]["sha256"]:
                problems.append(f"{name} changed since the stage: re-stage")
    return problems


def load_plan(stage_dir):
    path = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_anim_console_four.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scene_slot(states):
    """The slot of the scene's button call: the SECOND clip of the chain (the first is the lid), or the first when the chain has one clip."""
    chain = anim_object.chain_slots(states)
    return chain[1] if len(chain) > 1 else chain[0]


def set_scene(text, clips, states):
    """The script's text with the scene's button slot, its Idle and the clip's seconds (from the clip table) in the three ;BUTTON... lines (each once)."""
    play = scene_slot(states)
    seconds = [c["seconds"] for c in clips if c["name"] == play]
    if len(seconds) != 1:
        sys.exit(f"the clip table has no single clip {play}: {[c['name'] for c in clips]}")
    for tag, line in (("BUTTONPLAY", f'string ButtonPlay = "{play}"   ;BUTTONPLAY'), ("BUTTONIDLE", f'string ButtonIdle = "{anim_object.IDLE_OF4[play]}"   ;BUTTONIDLE'),
                      ("BUTTONS", f"float ButtonS = {seconds[0]}   ;BUTTONS")):
        new, n = re.subn(r"^[^\n;]*;" + tag + r"(?=\s|$)[^\n]*$", line, text, count=1, flags=re.M)
        if n != 1:
            sys.exit(f"the script has no ;{tag} line to put the scene's value into")
        text = new
    return text


def stage(a, converter=None):
    """converter: (a, staging) -> (src, conv) for tests; default mac.build_converter."""
    try:
        states = anim_object.parse_states(a.states, anim_object.PLAY_SLOTS4)
        anim_object.chain_slots(states)
    except ValueError as e:
        sys.exit(f"--states: {e}")
    try:
        slow = anim_object.parse_slow(a.slow, states)
    except ValueError as e:
        sys.exit(f"--slow: {e}")
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    patterns = a.game_archive or list(DEFAULT_ARCHIVES)
    paths = sorted({p for pat in patterns for p in glob.glob(pat if os.path.isabs(pat) else os.path.join(a.starfield_data, pat))})
    if not paths:
        sys.exit(f"no archive matched {patterns} under {a.starfield_data}: name the game's archives with --game-archive")
    anam, graph_entry = graph_anam(graphs.open_archives(paths))
    if anam is None:
        sys.exit(f"{GRAPH}.agx is not in the archives read ({', '.join(os.path.basename(p) for p in paths)}): pass the one that holds the graphs "
                 f"(Starfield - Animations.ba2) with --game-archive")
    port_data = a.port_data or a.starfield_data
    sf_esm, port_esm = os.path.join(a.starfield_data, "Starfield.esm"), os.path.join(port_data, "FO4Port.esm")
    before = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    out = new_partial(final)
    work = os.path.join(out, "work")
    staging = os.path.join(work, "conversion")
    os.makedirs(staging)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    info = mac.parse_info(run(tool + ["info", port_esm, sf_esm, "--edid", a.edid]).stdout)
    src, conv = (converter or mac.build_converter)(a, staging)
    original, _raw = mac.find_original(src, info["model"], a.model)
    res = conv.convert_anim_object(original, states, a.foley or None, idles="chain", graph=anam, slow=slow)
    if not res.get("ok"):
        sys.exit(f"the console did not convert: {res.get('reason')} (attempt kept in {out})")
    anim = res["anim"]
    model_path = res["out_name"].replace("/", "\\") + ".nif"
    out_data = os.path.join(out, "Data")
    copied, textures = mac.collect_kit_files(staging, out_data)
    lacking = mac.missing_textures(textures, mac.port_archive_names(port_data))
    if lacking:
        sys.exit(f"the conversion wrote {len(lacking)} texture(s) the port's archives do not hold (the kit ships none): {lacking[:8]} (attempt kept in {out})")
    margs = ["--model", model_path, "--rig", anim["skeleton"], "--anims", anim["animations"], "--graph", anam, "--edid", a.edid]
    wrote = run(tool + ["build", port_esm, sf_esm, out] + margs).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), port_esm, sf_esm] + margs).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = set_scene(mac.set_base_id(f.read(), info["base_id"]), anim["clips"], states)
    sources = read_sources(a.content_resources)
    src_dir = extract_sources(a.content_resources, work)
    pre = probe_a.precheck_sources(sources, text)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    text = probe_a.reg_shape(text, pre["register_returns_bool"])
    scripts = os.path.join(out_data, "Scripts")
    fate, keep = {}, []
    for opt in optional_names(text):
        if not pre["optional"][opt]:
            fate[opt] = "not declared in the base scripts"
            continue
        ok, err = compile_text(a.compiler, enable(text, [opt]), src_dir, os.path.join(work, "try"), SCRIPT)
        fate[opt] = "kept" if ok else f"declared but did not compile: {err}"
        if ok:
            keep.append(opt)
    final_text = enable(text, keep)
    ok, err = compile_text(a.compiler, final_text, src_dir, scripts, SCRIPT)
    if not ok:
        sys.exit(f"the Papyrus compile of {SCRIPT}.psc with {keep or 'no optional line'} failed: {err} (attempt kept in {out})")
    with open(os.path.join(out, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
        f.write(final_text)
    manifest = {"original": original, "port_model": info["model"], "base_edid": a.edid, "base_id": info["base_id"], "model": model_path,
                "states": states, "slow": slow, "foley": a.foley or "", "graph": {"anam": anam, "archive_entry": graph_entry}, "anim": anim,
                "kit_files": copied, "textures_not_shipped": textures}
    with open(os.path.join(out, "anim_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    shutil.rmtree(work)
    after = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    if after != before:
        sys.exit(f"Starfield.esm or FO4Port.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": KIND, "version": 1, "plugins": [PLUGIN], "outputs": stage_files(out), "inputs": {k: {"sha256": v} for k, v in before.items()},
            "optional": fate, "register_returns_bool": pre["register_returns_bool"], "states": states,
            "graph": {"anam": anam, "archive_entry": graph_entry}, "archives": [os.path.basename(p) for p in paths],
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFAnimF.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    table = "\n".join(f"  {c['name']}: {c['seconds']} s ({c['frames']} frames), bones {', '.join(c['bones']) or 'none moving'}"
                      + (f", held from the {c.get('hold_frame') or 'last'} frame of {c['hold_of']}" if c["hold_of"] else "")
                      + (f", starts from {c['starts_from']} (bones held at its pose: {', '.join(c.get('held_at_idle_pose') or []) or 'none'})"
                         if c.get("starts_from") else "") for c in anim["clips"])
    poses = "\n".join("  " + line for line in pose_lines(anim["clips"]))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Converted console on four states ({datetime.date.today().isoformat()}). docs/research/anim-console-four.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): an override of the port's console base {a.edid} (0x{info['base_id']}) with the converted model
{model_path}, its own rig and the graph component of {GRAPH} (ANAM {anam}), plus QUST FO4SF_AnimConsoleFourQuest (stages 10 11 20 21..30 40 60).
Masters Starfield.esm + FO4Port.esm. Original: {original}. State map: {states}. Slowed: {slow or 'none'} (a whole factor on the clip's times). Foley: {a.foley or 'none (no sound frames)'}.
Clips (eight; the graph's four play slots and four idle slots):
{table}
What each Idle slot holds, from the clip table:
{poses}
{len(copied)} mesh / geometry / material files in Data (no textures). Checked against Starfield.esm {before['Starfield.esm']}, FO4Port.esm {before['FO4Port.esm']}.
Optional lines: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}. RegisterForAnimationEvent returns bool: {pre['register_returns_bool']}.
Session: stages 10 (spawn) 11 (side copy) 20 (register) 21..24 Play01..Play04, 25..28 StateA_Idle..StateD_Idle, 29 StateD_Play, 30 the scene (StateA_Idle, Play01, {scene_slot(states)}, then its Idle: lid opens and stays open, button goes down and stays down), 40 reading, 60 delete.
Install (the owner's word, game closed; loose files are not read, the installer packs them into a ba2):
  python scripts\\newgame\\anim_console_four_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\newgame\\anim_console_four_install.py uninstall --starfield <game dir>
Read:    python scripts\\newgame\\make_anim_console_four.py log
Session card: docs/research/anim-console-four.md. THROWAWAY STATE ONLY, NO SAVE (the spawned references are persistent).
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, {len(copied)} files, anim_manifest.json, plan.json, README.txt; optional lines: {fate}")
    return 0


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = anim_probe_log.summarize(f)
    print("\n".join(anim_probe_log.report(s)))
    return 0 if s["spawned"] is not None else 1


def precheck(a):
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    r = probe_a.precheck_sources(read_sources(a.content_resources), text)
    for k, ok in r["required"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  {k}")
    for k, ok in r["optional"].items():
        print(f"{'declared' if ok else 'not declared'}  (optional) {k}")
    print(f"RegisterForAnimationEvent returns: {'bool' if r['register_returns_bool'] else ('nothing / other' if r['register_returns_bool'] is False else 'declaration not found')}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print("precheck: " + ("ok" if not r["missing"] else f"{len(r['missing'])} required name(s) missing; do not stage"))
    return 0 if not r["missing"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    c = sub.add_parser("clips")
    c.add_argument("--fo4-data", required=True)
    c.add_argument("--starfield-data", default=os.path.join(STARFIELD, "Data"))
    c.add_argument("--port-data", default="")
    c.add_argument("--model", default="")
    c.add_argument("--edid", default=EDID)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--starfield-data", default=os.path.join(STARFIELD, "Data"))
    s.add_argument("--port-data", default="", help="the folder with FO4Port.esm and its archives (default: --starfield-data)")
    s.add_argument("--game-archive", action="append", default=[], help="a Starfield archive (absolute, or relative to --starfield-data, * allowed); "
                   'default "Starfield - Meshes*.ba2" and "Starfield - Animations.ba2"')
    s.add_argument("--fo4-data", required=True)
    s.add_argument("--door-anim-dll", required=True)
    s.add_argument("--collision-template", required=True)
    s.add_argument("--texconv", required=True)
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--states", default=STATES_DEFAULT, help="FO4 sequence = Play slot in order A, B, C, D with none skipped; default the scene map (see `clips`)")
    s.add_argument("--slow", default=SLOW_DEFAULT, help="FO4 sequence = whole factor 2..8: that clip runs slower by the factor (default Stage3=4, the button); empty = as authored")
    s.add_argument("--foley", default="", help="a Starfield foley name for the clips' sound frames (default: none, no sound)")
    s.add_argument("--model", default="")
    s.add_argument("--edid", default=EDID)
    i = sub.add_parser("inspect")
    i.add_argument("--stage", required=True)
    d = sub.add_parser("dump")
    d.add_argument("--stage", required=True)
    d.add_argument("--dll", required=True)
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "clips": mac.clips, "stage": stage, "inspect": mac.inspect_stage, "dump": mac.dump_stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
