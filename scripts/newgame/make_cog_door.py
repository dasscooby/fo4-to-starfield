"""Stage the Vault 111 cog door probe: the DOOR install route and the SetOpen fallback (FAL-756, FAL-489 Plan B step 1).

Plan B step 0 (PC, 14 Nov 2026, nothing installed) showed the placed cog door (REFR 00126D of FO4Port.esm) shows no prompt and does
nothing on E from the ramp end, and that the converted door (PR 778, the seam rule) cannot be tried in game because no tool wrote a DOOR
override: make_anim_console.py stage overrides an ACTI only, and the session installer replaces no archived file. This stage is the route:

  * the full kit converts the Fallout 4 cog door again on a NEW model path (the conversion's own `_anim` suffix: the rig and the clip folder
    take the new path too), ships only meshes, geometries and materials, and writes FO4SFCogDoor.esm: an OVERRIDE of the DOOR base the
    placed reference stands on (model, rig and clip folder replaced; the door graph, name, flags and sounds kept) and QUST FO4SF_CogDoorQuest;
  * --control writes the quest alone: the installed port's own door answers the same stages (the SetOpen control, step 0 repeated).
The quest (scripts/newgame/FO4SF_CogDoorQuest.psc) reads the reference, calls SetOpen(true) / SetOpen(false) / Activate(player) one stage at
a time and logs the open state every two seconds for a minute, so the door has a trigger a player does not need to stand beside.

usage:
  python make_cog_door.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs against ContentResources.zip.
  python make_cog_door.py stage --out <new dir> --starfield-data <Starfield Data> --fo4-data <Fallout 4 Data>
         --door-anim-dll <CALUMI.Animation dll> --collision-template <nif> --texconv <texconv.exe> --content-resources <zip>
         [--port-data <dir with FO4Port.esm and its archives>] [--ref <hex local id, default 00126D>] [--model <FO4 mesh path>]
         [--compiler <exe>] [--control]
      1. the plugin tool's `info` on FO4Port.esm: the reference's DOOR base, its model and door graph (refused when the reference is
         missing or its base is not a DOOR of FO4Port.esm);
      2. (full kit) the conversion of the Fallout 4 door on the new path; every texture it wrote must already be in the port's own archives;
      3. dotnet/CogDoorProbe build + check (offline_check.txt), the Papyrus compile (RefId written into the script), plan.json with a
         SHA-256 of every file, cog_manifest.json and README.txt. Built in <out>.partial-<time>-<pid> and renamed to <out> only when every
         step passed.
  python make_cog_door.py log [--file <FO4SFCogDoor.0.log>]
      the run's user log as one table per stage and what the open state did.
Nothing here installs anything: scripts/newgame/cog_door_install.py does, on the owner's word, game closed. Needs numpy, the CALUMI.Animation
library and the game's archives: the PC's part. Nothing of the game enters the repo.
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
sys.path.insert(0, os.path.join(REPO, "scripts", "planet"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
from make_newgame import declares, extract_sources, new_partial, run  # noqa: E402
from make_workshop_probe import compile_text, read_sources, sha256  # noqa: E402
import make_anim_console as mac  # noqa: E402  (the converter inputs, the texture rule and the original's lookup are shared)
import make_anim_probe as probe_a  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "CogDoorProbe")
PLUGIN = "FO4SFCogDoor.esm"
SCRIPT = "FO4SF_CogDoorQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
KIND = "cog-door"
STARFIELD = mac.STARFIELD
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFCogDoor.0.log")
DEFAULT_REF = "00126D"
MODEL_SUFFIX = "_anim"
REF_LINE = re.compile(r"^int RefId = 0 +;REF", re.M)
REQUIRED = {
    "ObjectReference": ["GetOpenState", "SetOpen", "Activate", "Is3DLoaded", "GetBaseObject", "GetParentCell", "GetPositionX", "GetPositionY",
                        "GetPositionZ", "GetDistance"],
    "Game": ["GetPlayer", "GetFormFromFile", "IsPluginInstalled"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
    "Utility": ["GetCurrentRealTime"],
    "Quest": ["GetStageDone"],
    "ScriptObject": ["StartTimer"],
    "Form": ["GetFormID"],
}


def set_ref_id(text, ref_id):
    """The script's text with the reference's local id in (0x<hex>); the line must be there once."""
    if not re.fullmatch(r"(0x)?[0-9A-Fa-f]{1,6}", ref_id) or int(ref_id, 16) == 0:
        sys.exit(f"reference id {ref_id!r} is not a local form id (one to six hex digits, not zero)")
    new = REF_LINE.sub("int RefId = 0x" + ref_id.lower().removeprefix("0x") + "  ;REF", text, count=1)
    if new == text:
        sys.exit("the script has no 'int RefId = 0 ;REF' line to put the id into")
    return new


def precheck_sources(sources):
    """{"required": {"Base.Name": bool}, "missing": [...]} (inheritance followed, as the other probes' prechecks)."""
    req = {f"{b}.{f}": declares(sources, b, f) for b, fs in REQUIRED.items() for f in fs}
    return {"required": req, "missing": [k for k, ok in req.items() if not ok]}


def precheck(a):
    r = precheck_sources(read_sources(a.content_resources))
    for k, ok in r["required"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  {k}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print("precheck: " + ("ok" if not r["missing"] else f"{len(r['missing'])} required name(s) missing; do not stage"))
    return 0 if not r["missing"] else 1


def model_args(model_path, anim):
    """The plugin tool's three path options for the converted door."""
    return ["--model", model_path, "--rig", anim["skeleton"], "--anims", anim["animations"]]


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the cog door probe's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
    problems = []
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
        p = os.path.join(data, "Starfield.esm")
        if not os.path.isfile(p):
            problems.append(f"no Starfield.esm in {data}: name the game's Data folder (the install: the game folder)")
        elif sha256(p) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm changed since the stage: re-stage")
    return problems


def load_plan(stage_dir):
    path = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_cog_door.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage(a, converter=None):
    """converter: (a, staging) -> (src, conv) for tests; default make_anim_console.build_converter."""
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    control = bool(getattr(a, "control", False))
    ref = getattr(a, "ref", DEFAULT_REF) or DEFAULT_REF
    port_data = a.port_data or a.starfield_data
    sf_esm, port_esm = os.path.join(a.starfield_data, "Starfield.esm"), os.path.join(port_data, "FO4Port.esm")
    before = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    out = new_partial(final)
    work = os.path.join(out, "work")
    staging = os.path.join(work, "conversion")
    os.makedirs(staging)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    info = mac.parse_info(run(tool + ["info", port_esm, sf_esm, "--ref", ref]).stdout)
    out_data = os.path.join(out, "Data")
    manifest = {"ref": ref, "base_id": info["base_id"], "port_model": info["model"], "control": control}
    margs, copied, textures = [], [], []
    if not control:
        src, conv = (converter or mac.build_converter)(a, staging)
        original, _raw = mac.find_original(src, info["model"], a.model)
        res = conv.convert_nif(original, out_suffix=MODEL_SUFFIX)
        if not res.get("ok"):
            sys.exit(f"the door did not convert: {res.get('reason')} (attempt kept in {out})")
        door = res.get("door")
        if not door or door.get("rig") != "native" or res.get("door_error") or res.get("door_not_opening"):
            sys.exit(f"the door did not come out with its own rig (door_error {res.get('door_error')!r}, door_not_opening "
                     f"{res.get('door_not_opening')!r}): a static copy would not be the door under test (attempt kept in {out})")
        model_path = res["out_name"].replace("/", "\\") + ".nif"
        if res["out_name"].replace("/", "\\").lower() == info["model"].replace("/", "\\").lower().removeprefix("meshes\\").removesuffix(".nif"):
            sys.exit(f"the converted door's path equals the port's own ({model_path}): the override would shadow an archived file (attempt kept in {out})")
        copied, textures = mac.collect_kit_files(staging, out_data)
        lacking = mac.missing_textures(textures, mac.port_archive_names(port_data))
        if lacking:
            sys.exit(f"the conversion wrote {len(lacking)} texture(s) the port's archives do not hold (the kit ships none): {lacking[:8]} (attempt kept in {out})")
        margs = model_args(model_path, door)
        manifest.update(original=original, model=model_path, door={k: v for k, v in door.items() if k not in ("shapes", "attachments", "pose_boxes_m")},
                        kit_files=copied, textures_not_shipped=textures)
    kind_arg = ["--control"] if control else margs
    wrote = run(tool + ["build", port_esm, sf_esm, out, "--ref", ref, *kind_arg]).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), port_esm, sf_esm, "--ref", ref, *kind_arg]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = set_ref_id(f.read(), ref)
    sources = read_sources(a.content_resources)
    src_dir = extract_sources(a.content_resources, work)
    pre = precheck_sources(sources)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    scripts = os.path.join(out_data, "Scripts")
    ok, err = compile_text(a.compiler, text, src_dir, scripts, SCRIPT)
    if not ok:
        sys.exit(f"the Papyrus compile of {SCRIPT}.psc failed: {err} (attempt kept in {out})")
    with open(os.path.join(out, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    with open(os.path.join(out, "cog_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    shutil.rmtree(work)
    after = {"Starfield.esm": sha256(sf_esm), "FO4Port.esm": sha256(port_esm)}
    if after != before:
        sys.exit(f"Starfield.esm or FO4Port.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": KIND, "version": 1, "plugins": [PLUGIN], "outputs": probe_a.stage_files(out),
            "inputs": {k: {"sha256": v} for k, v in before.items()}, "control": control, "ref": ref,
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFCogDoor.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    what = (f"CONTROL kit: the quest alone, no DOOR override; the installed port's own door answers the stages." if control else
            f"an override of the DOOR base 0x{info['base_id']} (the base of reference {ref}) with the converted door on the new path\n"
            f"{manifest['model']} (rig and clips beside it), the base's own door graph kept; {len(copied)} mesh / geometry / material "
            f"files in Data (no textures)")
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Cog door probe ({datetime.date.today().isoformat()}). FAL-756 / FAL-489 Plan B step 1.
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): {what}, plus QUST FO4SF_CogDoorQuest (stages 10, 20, 30, 40, 50). Masters Starfield.esm +
FO4Port.esm. Checked against Starfield.esm {before['Starfield.esm']}, FO4Port.esm {before['FO4Port.esm']}.
Stages (set one at a time from the console, `setstage <quest form id> <n>`, after the last watch closed; the quest form id is the plugin's load
index plus 000800, e.g. 0E000800 when the plugin loaded as 0E: read the index from the load order; the name form `setstage FO4SF_CogDoorQuest <n>`
is refused ("Item ... not found for parameter Quest", nothing is set, PC session 14 Nov)): 10 read, 20 SetOpen(true),
30 SetOpen(false), 40 Activate(player), 50 read. Each of 20/30/40 logs the open state every 2 s for 60 s. Keep the console closed.
Install (the owner's word, game closed; loose files are not read, the installer packs them into a ba2):
  python scripts\\newgame\\cog_door_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\newgame\\cog_door_install.py uninstall --starfield <game dir>
Read:    python scripts\\newgame\\make_cog_door.py log
THROWAWAY STATE ONLY, NO SAVE.
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, {len(copied)} files, cog_manifest.json, plan.json, README.txt; control={control}")
    return 0


# ----------------------------------------------------------------------------------------------- the log
LINE = re.compile(r"FO4SFDOOR rt=(?P<rt>[-\d.]+) (?P<event>\w+)(?P<rest>.*?) end=true")


def summarize(lines):
    """{"stages": {stage: {"states": [(after_s or None, openstate)], "events": [event names]}}, "init": {...} or None}: the open state the quest
    read per stage, in the order logged (read / after / watch lines), and the stages whose state ever changed."""
    stages, init = {}, None
    for raw in lines:
        m = LINE.search(raw)
        if not m:
            continue
        kv = dict(re.findall(r"(\w+)=(\S*)", m.group("rest")))
        if m.group("event") == "init":
            init = kv
            continue
        stage = kv.get("stage")
        if stage is None:
            continue
        s = stages.setdefault(int(stage), {"states": [], "events": []})
        s["events"].append(m.group("event"))
        if "openstate" in kv:
            t = kv.get("after") or kv.get("seconds")           # "watch" lines say after=, the closing line seconds=
            s["states"].append((float(t) if t else None, int(kv["openstate"])))
    for s in stages.values():
        s["changed"] = len({st for _t, st in s["states"]}) > 1
    return {"stages": stages, "init": init}


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    s = summarize(lines)
    if s["init"]:
        print("init: " + " ".join(f"{k}={v}" for k, v in s["init"].items()))
    for stage, d in sorted(s["stages"].items()):
        seq = " ".join(f"{st}" if t is None else f"{st}@{t:.0f}s" for t, st in d["states"])
        print(f"stage {stage}: open state {seq or 'not read'}; {'CHANGED' if d['changed'] else 'did not change'} ({', '.join(dict.fromkeys(d['events']))})")
    return 0 if s["stages"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    pc.add_argument("--out", default=None)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--starfield-data", default=os.path.join(STARFIELD, "Data"))
    s.add_argument("--port-data", default="", help="the folder with FO4Port.esm and its archives (default: --starfield-data)")
    s.add_argument("--fo4-data", default="", help="Fallout 4 Data (needed unless --control)")
    s.add_argument("--door-anim-dll", default="")
    s.add_argument("--collision-template", default="")
    s.add_argument("--texconv", default="")
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--ref", default=DEFAULT_REF, help="the cog door reference's local id in FO4Port.esm (default 00126D)")
    s.add_argument("--model", default="", help="the Fallout 4 mesh path when the port path's candidates do not find it")
    s.add_argument("--control", action="store_true", help="the quest alone: no conversion, no DOOR override (the SetOpen control on the installed door)")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    if a.cmd == "stage" and not a.control:
        missing = [n for n in ("fo4_data", "door_anim_dll", "collision_template", "texconv") if not getattr(a, n)]
        if missing:
            p.error("the full kit needs " + ", ".join("--" + n.replace("_", "-") for n in missing) + " (or --control)")
    return {"precheck": precheck, "stage": stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
