"""Stage the map marker probe (FAL-771, FAL-489 notes 34 and 36): a session kit, one quest and its script, nothing else.

The question: can the new-game exit move and discover map markers while the player is still inside the vault cell, and what does
Starfield offer once the first location is discovered (the owner, 14 Nov: fast travel unlocks then)? The quest
(scripts/mapmarkers/FO4SF_MarkerProbeQuest.psc) reads four markers (Vault 111 = the exit anchor, the landing marker and two plain ones)
and the player's world around each call, one stage at a time from the console, and logs every line. Starfield has no getter for a
marker's discovered state, so the reads are the proxies (IsMapMarkerVisible, CanFastTravelToMarker, Game.IsFastTravelEnabled) and the
PC's own look at the map.

usage:
  python make_marker_probe.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs against ContentResources.zip.
  python make_marker_probe.py stage --out <new dir> --starfield-data <Starfield Data> [--content-resources <zip>] [--compiler <exe>]
      dotnet/MarkerProbe build + check (offline_check.txt), the Papyrus compile, plan.json with a SHA-256 of every file, README.txt.
      Built in <out>.partial-<time>-<pid> and renamed to <out> only when every step passed.
  python make_marker_probe.py log [--file <FO4SFMarkerProbe.0.log>]
      the run's user log as one table per stage.
Nothing here installs anything: scripts/mapmarkers/marker_probe_install.py does, on the owner's word, game closed. Stage 60 and 70 need
the map-marker plugin built with --landing-undiscovered (PR 781, make_map_markers.py stage). Nothing of the game enters the repo.
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
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
sys.path.insert(0, os.path.join(REPO, "src"))
from make_newgame import declares, extract_sources, new_partial, run  # noqa: E402
from make_workshop_probe import compile_text, read_sources, sha256  # noqa: E402
import make_anim_probe as probe_a  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "MarkerProbe")
PLUGIN = "FO4SFMarkerProbe.esm"
SCRIPT = "FO4SF_MarkerProbeQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
KIND = "marker-probe"
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFMarkerProbe.0.log")
REQUIRED = {
    "ObjectReference": ["MoveTo", "SetPosition", "GetPositionX", "GetPositionY", "GetPositionZ", "GetWorldSpace", "GetParentCell",
                        "SetMarkerDiscovered", "AddToMap", "IsMapMarkerVisible", "CanFastTravelToMarker"],
    "Game": ["GetPlayer", "GetFormFromFile", "IsPluginInstalled", "IsFastTravelEnabled", "IsFastTravelControlsEnabled"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
    "Utility": ["GetCurrentRealTime"],
    "Quest": ["GetStageDone"],
    "ScriptObject": ["StartTimer"],
    "Form": ["GetFormID"],
}


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


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the marker probe's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
        sys.exit(f"{path} missing: stage with make_marker_probe.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    sf_esm = os.path.join(a.starfield_data, "Starfield.esm")
    before = {"Starfield.esm": sha256(sf_esm)}
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    wrote = run(tool + ["build", out]).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN)]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    sources = read_sources(a.content_resources)
    src_dir = extract_sources(a.content_resources, work)
    pre = precheck_sources(sources)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    scripts = os.path.join(out, "Data", "Scripts")
    ok, err = compile_text(a.compiler, text, src_dir, scripts, SCRIPT)
    if not ok:
        sys.exit(f"the Papyrus compile of {SCRIPT}.psc failed: {err} (attempt kept in {out})")
    with open(os.path.join(out, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    shutil.rmtree(work)
    after = {"Starfield.esm": sha256(sf_esm)}
    if after != before:
        sys.exit(f"Starfield.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": KIND, "version": 1, "plugins": [PLUGIN], "outputs": probe_a.stage_files(out),
            "inputs": {k: {"sha256": v} for k, v in before.items()},
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFMarkerProbe.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Map marker probe ({datetime.date.today().isoformat()}). FAL-771 / FAL-489 notes 34 and 36.
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): QUST FO4SF_MarkerProbeQuest (stages 10 20 30 40 50 60 70), master Starfield.esm only.
Checked against Starfield.esm {before['Starfield.esm']}.
Stages (set one at a time from the console, `setstage FO4SF_MarkerProbeQuest <n>`, after the last stage's "later done" line; the console
stays closed between stages): 10 read, 20 move a plain marker onto the exit anchor from INSIDE the vault, 30 discover Vault 111 inside,
40 read outside, 50 read after save / quit / load, 60 discover the landing marker (needs the --landing-undiscovered map-marker build),
70 AddToMap(false) on a second plain marker.
Install (the owner's word, game closed; loose files are not read, the installer packs them into a ba2):
  python scripts\\mapmarkers\\marker_probe_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\mapmarkers\\marker_probe_install.py uninstall --starfield <game dir>
Read:    python scripts\\mapmarkers\\make_marker_probe.py log
THROWAWAY STATE ONLY, EXCEPT STAGE 50's SAVE: use a throwaway save name.
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, plan.json, README.txt")
    return 0


# ----------------------------------------------------------------------------------------------- the log
LINE = re.compile(r"FO4SFMARK rt=(?P<rt>[-\d.]+) (?P<event>\w+)(?P<rest>.*?) end=true")


def summarize(lines):
    """{"stages": {stage: [row, ...]}, "init": {...} or None}: a row is {"event", "when", "name", + every key=value}, in the order logged."""
    stages, init = {}, None
    for raw in lines:
        m = LINE.search(raw)
        if not m:
            continue
        kv = dict(re.findall(r"(\w+)=(\S*)", m.group("rest")))
        if m.group("event") == "init":
            init = kv
            continue
        stage_no = kv.get("stage")
        if stage_no is None:
            continue
        row = {"event": m.group("event"), "rt": float(m.group("rt")), **kv}
        stages.setdefault(int(stage_no), []).append(row)
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
    for stage_no, rows in sorted(s["stages"].items()):
        print(f"stage {stage_no}:")
        for r in rows:
            if r["event"] == "fast":
                print(f"  {r['when']:<7} fast travel enabled={r.get('enabled')} controls={r.get('controls')} player world={r.get('pworld')} cell={r.get('pcell')}")
            elif r["event"] == "read":
                print(f"  {r['when']:<7} {r.get('name'):<5} world={r.get('world')} cell={r.get('cell')} visible={r.get('visible')} canfast={r.get('canfast')} pos={r.get('pos')}")
            else:
                print(f"  {r['event']}: " + " ".join(f"{k}={v}" for k, v in r.items() if k not in ("event", "rt", "stage")))
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
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
