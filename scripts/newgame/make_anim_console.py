"""Stage the animation probe, variant D: OUR console on a vanilla activator graph (docs/research/anim-console-probe.md, FAL-489).

Variant A (12 Nov, PC) showed that PlayAnimation moves a vanilla activator on activatorstategraph01 and that Done arrives after a
clip. This builds the same thing from the port's own console: the converter's door path, generalised (src/fo4sf/anim_object.py),
turns the Fallout 4 console's sequences into a rig and one .af / .afx clip per graph slot; a plugin overrides the port's console
base with the model and an AnimationGraphComponent; the quest script spawns it and plays the slots.

usage:
  python make_anim_console.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs against ContentResources.zip, and the register call's return type.
  python make_anim_console.py clips --fo4-data <Fallout 4 Data> [--port-data <dir with FO4Port.esm>] [--model <FO4 mesh path>] [--edid <EditorID>]
      read only: the console's Fallout 4 sequences (name, seconds, bones moved, text keys), to choose the --states map. Finds the
      original from the port base's model path (the probe's original_candidates) unless --model names it.
  python make_anim_console.py stage --out <new dir> --starfield-data <Starfield Data> --fo4-data <Fallout 4 Data>
         --door-anim-dll <CALUMI.Animation dll> --collision-template <nif> --texconv <texconv.exe> --content-resources <zip>
         --states "Stage1=StateA_Play,Stage2=StateB_Play" [--port-data <dir with FO4Port.esm and its archives>] [--foley <name>]
         [--model <FO4 mesh path>] [--edid <EditorID>] [--compiler <exe>]
      1. the plugin tool's `info` on FO4Port.esm (the console base's id and model);
      2. the conversion of the Fallout 4 console (pipeline.Converter.convert_anim_object: model, rig, four clips, materials);
      3. only meshes, geometries and materials go in the kit (textures are not shipped: every texture the conversion wrote must
         already be in the port's own archives, or the stage refuses and lists them);
      4. dotnet/AnimConsoleProbe build + check (offline_check.txt), the Papyrus compile (optional lines kept when they
         compile; the register call in the shape the game declares; BaseId written into the script), plan.json with a
         SHA-256 of every file, anim_manifest.json (the clip table, the state map, the files) and README.txt. Built in a new
         <out>.partial-<time>-<pid> and renamed to <out> only when every step passed.
  python make_anim_console.py inspect --stage <staged kit folder>
      read only, offline: the rig's bone order, which rig index every clip track is filed under, the written model's node order
      (is it the rig's?), which bone every shape rides and its box, and the PREDICTED end-of-clip box of every shape per clip.
      It reads anim_manifest.json and the model NIF; it does not read the .rig/.af (CALUMI's files) or the game.
  python make_anim_console.py dump --stage <staged kit folder> --dll <CALUMI.Animation.dll>
      read only, offline: reads the WRITTEN skeleton.rig and every .af back through CALUMI (LoadAnimationSceneFromSFBGSFormatC) and
      prints the rig bones in file order and, per clip, every block's enumeration position, the bone name it is filed under, its key count,
      and its first and last rotation as angle and axis (degrees). Exit 1 when a block names a bone the rig lacks, a bone has two blocks, or
      the clips of one kit disagree about the rig. The enumeration position is what CALUMI's read-back gives (blocks in the order they
      were added); it is NOT the rig index the writer passed to CreateAnimBlockC (nothing in this repo reads that back). So a position that
      differs from the rig index is printed as a NOTE, and as a failure only when the clip has a block for every rig bone (then the writer's
      own contract is block i = rig bone i). A clip with fewer blocks than bones (a door: only animated bones) is not a failure. Translation values are not read (only their count): the read-back names for them are
      not in the repo. It cannot say how the GAME applies a track.
  python make_anim_console.py log [--file <FO4SFAnimD.0.log>]
      the run's user log as one table and a verdict (src/fo4sf/anim_probe_log.py, the same reader as variant A).
Nothing here installs anything: scripts/newgame/anim_console_install.py does, on the owner's word, game closed. Needs numpy, the
CALUMI.Animation library and the game's archives: the PC's part. Nothing of the game enters the repo.
"""
import argparse
import datetime
import glob
import json
import math
import os
import re
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "planet"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
from make_newgame import extract_sources, new_partial, run  # noqa: E402
from make_workshop_probe import compile_text, enable, optional_names, read_sources, sha256  # noqa: E402
import make_anim_probe as probe_a  # noqa: E402
from fo4sf import anim_object, anim_probe_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "AnimConsoleProbe")
PLUGIN = "FO4SFAnimConsole.esm"
SCRIPT = "FO4SF_AnimConsoleQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
KIND = "anim-console"
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFAnimD.0.log")
EDID = "FO4Port_acti_091a48_fallout4"
KIT_FOLDERS = ("meshes", "geometries", "materials")      # what the kit ships; textures must already be in the port's archives
BASE_LINE = re.compile(r"^int BaseId = 0 +;BASE", re.M)


def set_base_id(text, base_id):
    """The script's text with the console base's local id in (0x<hex>); the line must be there once."""
    if not re.fullmatch(r"(0x)?[0-9A-Fa-f]{1,6}", base_id):
        sys.exit(f"base id {base_id!r} is not a local form id (at most six hex digits)")
    new = BASE_LINE.sub("int BaseId = 0x" + base_id.lower().removeprefix("0x") + "  ;BASE", text, count=1)
    if new == text:
        sys.exit("the script has no 'int BaseId = 0 ;BASE' line to put the id into")
    return new


def parse_info(text):
    """{"base_id": "001234", "model": "Meshes/..."} from the plugin tool's `info` output; exits when either is missing."""
    base = re.search(r"^BASE_ID 0x([0-9A-Fa-f]+)", text, re.M)
    model = re.search(r"^MODEL (.+)$", text, re.M)
    if not base or not model or not model.group(1).strip():
        sys.exit("the plugin tool's info did not give BASE_ID and MODEL (is the base's model empty?)")
    return {"base_id": base.group(1), "model": model.group(1).strip().replace("\\", "/")}   # one form: forward slashes, whatever the OS prints


# ----------------------------------------------------------------------------------------------- the original console
def original_names(port_model):
    """FO4 mesh names to try for the port's model path (vault111_anim_probe.original_candidates)."""
    import vault111_anim_probe as vp
    return vp.original_candidates(port_model.replace("/", "\\"))


def find_original(src, port_model, override=""):
    """(mesh name, bytes) of the Fallout 4 original: the override, else the port path's candidates, else a unique file name."""
    names = [override] if override else original_names(port_model)
    for n in names:
        raw = src.mesh(n)
        if raw is not None:
            return n, raw
    base = names[0].replace("/", "\\").rsplit("\\", 1)[-1]
    same = src.mesh_names(re.escape(base) + "$")
    if len(same) == 1:
        return same[0], src.mesh(same[0])
    sys.exit(f"the Fallout 4 original of {port_model} was not found by {names} ({len(same)} files named {base}); name it with --model")


def sequences_table(raw):
    """[{name, seconds, bones, text_keys}] of every NiControllerSequence of a Fallout 4 NIF (read only)."""
    from fo4sf import door_motion, nif
    src = nif.parse(raw)
    names = []
    for i, block in enumerate(src.blocks):
        if src.type_of(i) == "NiControllerSequence":
            idx, = struct.unpack_from("<i", block)
            names.append(src.strings[idx] if 0 <= idx < len(src.strings) else b"?")
    rows = []
    for seq in door_motion.inspect(src, None, tuple(dict.fromkeys(names)))["sequences"]:
        t = seq["timing"]
        rows.append({"name": seq["name"], "seconds": round((t["stop"] - t["start"]) / t["frequency"], 4),
                     "bones": sorted(x["name"] for x in seq["targets"]),
                     "text_keys": [f"{round(e['time'], 3)}s {e['text']}" for e in t["text_events"]]})
    return rows


def sequence_motion(raw, names):
    """{sequence: [{bone, travel_m, rotation_deg, axis}]}: what each track of each sequence does from its first to its last
    sample (door_rig.open_motion over a plan that keeps every named sequence). A track listed in sequences_table can stand
    still: travel 0 and 0 degrees. {} when the plan cannot be made."""
    from fo4sf import convert_static, door_rig, nif
    try:
        src = nif.parse(raw)
        plan = door_rig.animated_identity_binds(door_rig.plan(src, placed=True, allowed=tuple(names)))
        return {n: door_rig.open_motion(plan, convert_static.UNIT_SCALE, n) for n in names if any(c["name"] == n for c in plan["clips"])}
    except (nif.NifError, KeyError, ValueError, IndexError, struct.error):
        return {}


def clips(a):
    from fo4sf import pipeline
    port = os.path.join(a.port_data or a.starfield_data, "FO4Port.esm")
    info = parse_info(run(["dotnet", "run", "-c", "Release", "--project", PROJECT, "--", "info", port,
                           os.path.join(a.starfield_data, "Starfield.esm"), "--edid", a.edid]).stdout)
    name, raw = find_original(pipeline.Fo4Archives(a.fo4_data), info["model"], a.model)
    print(f"original: {name} ({len(raw)} bytes); port base {a.edid} id 0x{info['base_id']} model {info['model']}")
    rows = sequences_table(raw)
    motion = sequence_motion(raw, [r["name"] for r in rows])
    for r in rows:
        print(f"  {r['name']}: {r['seconds']} s, tracks {', '.join(r['bones']) or 'none'}; text keys: {'; '.join(r['text_keys']) or 'none'}")
        for m in motion.get(r["name"], []):
            print(f"      {m['bone']}: travel {m['travel_m']} m, turns {m['rotation_deg']} deg (first to last sample)")
        if r["name"] not in motion:
            print("      motion: unread (the rig plan did not take this sequence)")
    return 0


# ----------------------------------------------------------------------------------------------- the conversion
def build_converter(a, staging):
    """The Fallout 4 archives and a pipeline.Converter with the door path's inputs (as scripts/convert_batch.py makes them)."""
    from fo4sf import ba2, convert_static, pipeline, sfcollision, sfnif
    src = pipeline.Fo4Archives(a.fo4_data)
    with open(a.collision_template, "rb") as f:
        template = convert_static.collision_template_from_nif(f.read())
    donor = sfcollision.physics_blob_from_nif(ba2.Ba2(os.path.join(a.starfield_data, "Starfield - Meshes01.ba2")).read(sfnif.DOOR_TEMPLATE["nif"]))
    return src, pipeline.Converter(src, staging, a.texconv, a.content_resources, template, rig_doors=True, door_physics_donor=donor,
                                   door_anim_dll=a.door_anim_dll)


def port_archive_names(port_data):
    """Lower-case, slash-normalised entry names of every FO4Port*.ba2 beside the plugin (the textures the kit may point at)."""
    from fo4sf import ba2
    out = set()
    for p in sorted(glob.glob(os.path.join(port_data, "FO4Port*.ba2"))):
        try:
            out.update(n.replace("\\", "/").lower() for n in ba2.Ba2(p).names)
        except (ba2.Ba2Error, OSError, struct.error):
            pass
    return out


def collect_kit_files(staging, out_data):
    """Copy meshes / geometries / materials of the conversion's staging into the kit's Data tree; returns
    ([relative paths copied], [texture files the conversion wrote, relative to the staging])."""
    copied, textures = [], []
    for root, _dirs, names in os.walk(staging):
        for n in sorted(names):
            rel = os.path.relpath(os.path.join(root, n), staging).replace(os.sep, "/")
            top = rel.split("/", 1)[0].lower()
            if top in KIT_FOLDERS:
                dst = os.path.join(out_data, *rel.split("/"))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(os.path.join(root, n), dst)
                copied.append(rel)
            elif top == "textures":
                textures.append(rel)
    return sorted(copied), sorted(textures)


def missing_textures(textures, port_names):
    return sorted(t for t in textures if t.lower() not in port_names)


# ----------------------------------------------------------------------------------------------- the stage
def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    problems = []
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the animation console probe's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
    now = probe_a.stage_files(stage_dir)
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
        sys.exit(f"{path} missing: stage with make_anim_console.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage(a, converter=None):
    """converter: (a, staging) -> (src, conv) for tests; default build_converter."""
    states = anim_object.parse_states(a.states)
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    port_data = a.port_data or a.starfield_data
    sf_esm, port_esm = os.path.join(a.starfield_data, "Starfield.esm"), os.path.join(port_data, "FO4Port.esm")
    before = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    out = new_partial(final)
    work = os.path.join(out, "work")
    staging = os.path.join(work, "conversion")
    os.makedirs(staging)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    info = parse_info(run(tool + ["info", port_esm, sf_esm, "--edid", a.edid]).stdout)
    src, conv = (converter or build_converter)(a, staging)
    original, _raw = find_original(src, info["model"], a.model)
    extra = {}
    if getattr(a, "swap_siblings", False):
        extra["swap_siblings"] = True
    if getattr(a, "idles", "toggle") != "toggle":
        extra["idles"] = a.idles
    res = conv.convert_anim_object(original, states, a.foley or None, **extra)
    if not res.get("ok"):
        sys.exit(f"the console did not convert: {res.get('reason')} (attempt kept in {out})")
    anim = res["anim"]
    model_path = res["out_name"].replace("/", "\\") + ".nif"
    out_data = os.path.join(out, "Data")
    copied, textures = collect_kit_files(staging, out_data)
    lacking = missing_textures(textures, port_archive_names(port_data))
    if lacking:
        sys.exit(f"the conversion wrote {len(lacking)} texture(s) the port's archives do not hold (the kit ships none): {lacking[:8]} (attempt kept in {out})")
    wrote = run(tool + ["build", port_esm, sf_esm, out, "--model", model_path, "--rig", anim["skeleton"], "--anims", anim["animations"],
                        "--edid", a.edid]).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), port_esm, sf_esm, "--model", model_path, "--rig", anim["skeleton"],
                        "--anims", anim["animations"], "--edid", a.edid]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = set_base_id(f.read(), info["base_id"])
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
    manifest = {"original": original, "port_model": info["model"], "base_edid": a.edid, "base_id": info["base_id"],
                "model": model_path, "states": states, "foley": a.foley or "", "anim": anim, "kit_files": copied,
                "textures_not_shipped": textures}
    with open(os.path.join(out, "anim_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    shutil.rmtree(work)
    after = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    if after != before:
        sys.exit(f"Starfield.esm or FO4Port.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": KIND, "version": 1, "plugins": [PLUGIN], "outputs": probe_a.stage_files(out),
            "inputs": {k: {"sha256": v} for k, v in before.items()}, "optional": fate, "register_returns_bool": pre["register_returns_bool"],
            "states": states, "log": "<My Games>/Starfield/Logs/Script/User/FO4SFAnimD.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    table = "\n".join(f"  {c['name']}: {c['seconds']} s ({c['frames']} frames), bones {', '.join(c['bones'])}"
                      + (f", held from the {c.get('hold_frame') or 'last'} frame of {c['hold_of']}" if c["hold_of"] else "")
                      + (f", starts from {c['starts_from']} (bones held at its pose: {', '.join(c.get('held_at_idle_pose') or []) or 'none'})"
                         if c.get("starts_from") else "") for c in anim["clips"])
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Animation console probe, variant D ({datetime.date.today().isoformat()}). docs/research/anim-console-probe.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): an override of the port's console base {a.edid} (0x{info['base_id']}) with the converted model
{model_path}, its own rig and the graph component of activatorstategraph01, plus QUST FO4SF_AnimConsoleQuest (stages 10..60). Masters
Starfield.esm + FO4Port.esm. Original: {original}. State map: {states}. Foley: {a.foley or 'none (no sound frames)'}.
Clips:
{table}
{len(copied)} mesh / geometry / material files in Data (no textures). Checked against Starfield.esm {before['Starfield.esm']}, FO4Port.esm {before['FO4Port.esm']}.
Optional lines: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}. RegisterForAnimationEvent returns bool: {pre['register_returns_bool']}.
Install (the owner's word, game closed; loose files are not read, the installer packs them into a ba2):
  python scripts\\newgame\\anim_console_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\newgame\\anim_console_install.py uninstall --starfield <game dir>
Read:    python scripts\\newgame\\make_anim_console.py log
Session card: docs/research/anim-console-probe.md. THROWAWAY STATE ONLY, NO SAVE (the spawned reference is persistent).
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, {len(copied)} files, anim_manifest.json, plan.json, README.txt; optional lines: {fate}")
    return 0


def model_bone_order(nif_bytes, rig_names):
    """The names of the written model's NiNode blocks that are rig bones, in file order (door_model.build adds the bones in rig
    order, so a different order here would be a swap between the rig's indices and the model's nodes)."""
    from fo4sf import nif
    f = nif.parse(nif_bytes)
    names = []
    for i in range(len(f.blocks)):
        if f.type_of(i) == "NiNode":
            idx = struct.unpack_from("<i", f.blocks[i])[0]
            names.append(f.strings[idx].decode("latin-1") if 0 <= idx < len(f.strings) else "")
    return [n for n in names if n in set(rig_names)], names


def inspect_stage(a):
    """Read-only: what a staged kit's rig, tracks, model nodes and shapes say, with the predicted pose of every shape at the end of
    each clip. No game, no CALUMI: it reads anim_manifest.json and the model NIF the stage wrote."""
    with open(os.path.join(a.stage, "anim_manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    anim = man["anim"]
    rig = anim.get("rig")
    if not isinstance(rig, list) or not rig or not isinstance(rig[0], dict):          # missing, or the door manifest's "native" string
        print("this stage's manifest has no rig table (staged by an older head, or a door's \"native\" marker): re-stage")
        return 2
    print(f"original {man['original']}  model {man['model']}  states {man['states']}")
    if anim.get("swap_siblings"):
        print("SIBLINGS SWAPPED (--swap-siblings): the two children of one bone are written in exchanged order")
    print("rig bones (index: name, parent, bind in m):")
    for r in rig:
        print(f"  {r['index']}: {r['name']} (parent {r['parent']}) {r['bind_t_m']}")
    model = os.path.join(a.stage, "Data", "meshes", *man["model"].replace("\\", "/").split("/"))
    problems = []
    if os.path.isfile(model):
        want = [r["name"] for r in rig]
        try:
            order, _all = model_bone_order(open(model, "rb").read(), want)
        except Exception as e:                      # noqa: BLE001  (a model our parser cannot read is said, not hidden)
            order = None
            problems.append(f"the model could not be parsed: {type(e).__name__}: {e}")
        if order is not None:
            print(f"model NiNode order (bones only): {order}")
            print("  matches the rig order: " + ("yes" if order == want else f"NO (rig {want})"))
            if order != want:
                problems.append("model node order differs from rig order")
    else:
        print(f"model file {model} not found")
    print("clip tracks (clip: bone -> rig index, keys):")
    for c in anim["clips"]:
        print(f"  {c['name']} ({c['seconds']} s): " + (", ".join(f"{t['bone']} -> {t['bone_index']} ({t['keys']} keys)" for t in c.get("tracks", [])) or "no tracks"))
        for t in c.get("tracks", []):
            if rig[t["bone_index"]]["name"] != t["bone"]:
                problems.append(f"{c['name']}: track {t['bone']} filed under rig index {t['bone_index']} = {rig[t['bone_index']]['name']}")
    print("shapes (name: fate, bone, rest box in m):")
    boxes = anim.get("pose_boxes_m", {})
    atts = {x["key"]: x for x in anim.get("attachments", [])}
    for k, x in atts.items():
        print(f"  {x['shape']} [{k}]: rides {x['bone']} (rig {x['bone_index']}), rest {boxes.get('rest', {}).get(k)}")
    print("predicted end-of-clip box per shape (differs from rest = the shape moves in that clip):")
    for clip, per in boxes.get("end_of_clip", {}).items():
        moved = [f"{atts[k]['shape']}[{k}]@{atts[k]['bone']}" for k, b in per.items() if b != boxes["rest"][k]]
        print(f"  {clip}: moves {', '.join(moved) or 'nothing'}")
        for k in per:
            if per[k] != boxes["rest"][k]:
                print(f"      {atts[k]['shape']}[{k}]@{atts[k]['bone']} {boxes['rest'][k]} -> {per[k]}")
    for p in problems:
        print("FAIL  " + p)
    print("inspect: " + ("ok" if not problems else f"{len(problems)} problem(s)"))
    return 0 if not problems else 1


def quat_angle_axis(xyzw):
    """(degrees, (x, y, z) unit axis or None) of a unit quaternion given as (x, y, z, w); the angle is the shorter way round (0 to 180)."""
    x, y, z, w = xyzw
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    if w < 0:
        x, y, z, w = -x, -y, -z, -w
    s = math.sqrt(max(0.0, 1 - w * w))
    angle = math.degrees(2 * math.acos(max(-1.0, min(1.0, w))))
    return round(angle, 3), (None if s < 1e-6 else tuple(round(v / s, 4) for v in (x, y, z)))


class CalumiReader:
    """Reads a written .rig and .af back with the CALUMI library (the calls scripts/oracles/native_door_animation.py already uses).
    read(rig_path, af_path) -> {"bones": [(name, parent)], "blocks": [{"position", "bone", "rot": [(frame, xyzw)], "trans_count"}]}."""
    def __init__(self, dll):
        import ctypes as c
        self.c = c
        self.lib = c.CDLL(str(os.path.abspath(dll)))

    def _bind(self, name, args, result):
        fn = getattr(self.lib, name)
        fn.argtypes, fn.restype = args, result
        return fn

    def read(self, rig_path, af_path):
        c, p = self.c, self.c.c_void_p
        b = self._bind
        err = b("CreateStringContainerC", [], p)()
        msg = b("GetStringFromContainerC", [p], c.c_char_p)
        try:
            scene = b("LoadAnimationSceneFromSFBGSFormatC", [c.POINTER(c.c_wchar_p), c.c_int, p], p)((c.c_wchar_p * 2)(str(rig_path), str(af_path)), 2, err)
            if not scene:
                raise RuntimeError(f"CALUMI could not read {af_path}: {(msg(err) or b'').decode(errors='replace')}")
            try:
                rig = b("GetSkeletonRigC", [p], p)(scene)
                bones = []
                for i in range(b("GetSkeletonRigBoneCountC", [p], c.c_size_t)(rig)):
                    bone = b("GetSkeletonBoneC", [p, c.c_int, p], p)(rig, i, err)
                    bones.append((b("GetSkeletonBoneNameC", [p], c.c_char_p)(bone).decode("latin-1"),
                                  b("GetSkeletonBoneParentIndexC", [p], c.c_int)(bone)))
                anim = b("GetAnimationC", [p, c.c_int, p], p)(scene, 0, err)
                blocks = []
                for k in range(b("GetAnimationBlockCountC", [p], c.c_size_t)(anim)):
                    block = b("GetAnimationBlockC", [p, c.c_int, p], p)(anim, k, err)
                    rot = []
                    for j in range(b("GetRotationSqSizeC", [p], c.c_size_t)(block)):
                        entry = b("GetRotationFromSqC", [p, c.c_int, p], p)(block, j, err)
                        q = b("GetValueFromRotationEntryC", [p], p)(entry)
                        rot.append((b("GetFrameFromRotationEntryC", [p], c.c_uint16)(entry),
                                    tuple(b("GetQuaternion" + ax, [p], c.c_float)(q) for ax in "XYZW")))
                    blocks.append({"position": k, "bone": b("GetAnimBlockBoneNameC", [p], c.c_char_p)(block).decode("latin-1"),
                                   "rot": rot, "trans_count": b("GetTranslationSqSizeC", [p], c.c_size_t)(block)})
                return {"bones": bones, "blocks": blocks}
            finally:
                b("DeleteAnimationSceneC", [p], c.c_bool)(scene)
        finally:
            b("DeleteStringContainerC", [p], None)(err)


def dump_stage(a, reader=None):
    """Read-only: the written rig and every .af of a staged kit, read back, with the track-to-bone checks (see the usage text)."""
    with open(os.path.join(a.stage, "anim_manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    folder = os.path.join(a.stage, "Data", "meshes", *man["model"].replace("\\", "/").rsplit(".", 1)[0].split("/"))
    rig_path = os.path.join(folder, "characterassets", "skeleton.rig")
    afs = sorted(glob.glob(os.path.join(folder, "animations", "*.af")))
    if not os.path.isfile(rig_path) or not afs:
        print(f"no rig or no .af under {folder}")
        return 2
    reader = reader or CalumiReader(a.dll)
    problems, rig_names = [], None
    print(f"rig file {os.path.relpath(rig_path, a.stage)} ({os.path.getsize(rig_path)} bytes)")
    for af in afs:
        data = reader.read(rig_path, af)
        names = [n for n, _ in data["bones"]]
        if rig_names is None:
            rig_names = names
            print("rig bones in file order (index: name, parent):")
            for i, (n, par) in enumerate(data["bones"]):
                print(f"  {i}: {n} (parent {par})")
        elif names != rig_names:
            problems.append(f"{os.path.basename(af)}: the rig read with this clip differs from the first")
        print(f"{os.path.basename(af)} ({os.path.getsize(af)} bytes), {len(data['blocks'])} blocks:")
        full = len(data["blocks"]) == len(names)
        for blk in data["blocks"]:
            rot = blk["rot"]
            if rot:
                a0, ax0 = quat_angle_axis(rot[0][1])
                a1, ax1 = quat_angle_axis(rot[-1][1])
                shown = f"first {a0} deg about {ax0}, last {a1} deg about {ax1}, frames {rot[0][0]}..{rot[-1][0]}"
            else:
                shown = "no rotation keys"
            pos = blk["position"]
            rig_at = names[pos] if pos < len(names) else None
            ok = "" if rig_at == blk["bone"] else f"  <-- NOTE: position {pos} but the rig has {rig_at!r} at index {pos}"
            print(f"  block {pos}: bone {blk['bone']!r}, {len(rot)} rotation keys, {blk['trans_count']} translation keys; {shown}{ok}")
            if blk["bone"] not in names:
                problems.append(f"{os.path.basename(af)}: block names {blk['bone']!r}, which the rig lacks")
            elif full and rig_at != blk["bone"]:
                problems.append(f"{os.path.basename(af)}: one block per rig bone, but the block at position {pos} is {blk['bone']!r} and the rig has {rig_at!r} there")
        seen = [blk["bone"] for blk in data["blocks"]]
        for dup in sorted({n for n in seen if seen.count(n) > 1}):
            problems.append(f"{os.path.basename(af)}: two blocks for {dup!r}")
        if not full:
            print(f"  NOTE: {len(data['blocks'])} blocks for {len(names)} rig bones; positions are not rig indices here and nothing was checked by position")
    for p in problems:
        print("FAIL  " + p)
    print("dump: " + ("ok (names are in the rig; how the game pairs a block with a bone is not read)" if not problems else f"{len(problems)} problem(s)"))
    return 0 if not problems else 1


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
    s.add_argument("--fo4-data", required=True)
    s.add_argument("--door-anim-dll", required=True)
    s.add_argument("--collision-template", required=True)
    s.add_argument("--texconv", required=True)
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--states", required=True, help='FO4 sequence = Play slot, e.g. "Stage1=StateA_Play,Stage2=StateB_Play" (see `clips`)')
    s.add_argument("--foley", default="", help="a Starfield foley name for the clips' sound frames (default: none, no sound)")
    s.add_argument("--swap-siblings", action="store_true", help="EXPERIMENT (FAL-489 session 6): write the root's two children (Lid, Button) with their indices exchanged: rig, .af blocks, model nodes and attachments; nothing else changes")
    s.add_argument("--idles", choices=("toggle", "hold"), default="toggle",
                   help="toggle (default, FAL-489 session 7): StateA_Idle = first frame of slot A's clip, StateB_Idle = its last frame, slot B starts from there; "
                        "hold: each Idle holds the last frame of its own Play clip (sessions 1 to 7)")
    s.add_argument("--model", default="")
    s.add_argument("--edid", default=EDID)
    i = sub.add_parser("inspect")
    i.add_argument("--stage", required=True, help="a staged kit folder (make_anim_console.py stage --out)")
    d = sub.add_parser("dump")
    d.add_argument("--stage", required=True)
    d.add_argument("--dll", required=True, help="CALUMI.Animation.dll (the library the stage used)")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "clips": clips, "stage": stage, "inspect": inspect_stage, "dump": dump_stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
