"""Stage the cut-down "When Freedom Calls" mission (docs/mission/when-freedom-calls.md) and read its in-game log.

usage:
  python make_mission.py stage --out <experiment dir> --fo4 <Fallout4.esm> --starfield <Starfield.esm>
                               --core <FO4TerrainCore.esm> --raider <FO4ActorRaider.esm>
                               [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>] [--no-alias]
      1. dotnet/Mission points: Fallout 4's Concord raiders and the museum door's outside arrival (points.json);
      2. dotnet/Mission write + check: FO4SFMission.esm against the given core and raider plugins (offline_check.txt);
      3. the Papyrus compile of FO4SF_Min00Quest.psc against every base script of ContentResources.zip;
      4. plan.json (the plugin's, the script's and the masters' SHA-256) and README.txt.
      The masters are hashed BEFORE the build and again before publication: a core or raider plugin that changed
      during the build is refused. The stage is built in a new <out>.partial-<time>-<pid> folder (never reused or
      deleted: a failed attempt stays as evidence) and renamed to <out> only when every step passed; an existing
      <out> is refused, so a failed rebuild never touches an earlier stage.
  python make_mission.py fold --mission <stage dir> --core-dir <core experiment dir> --out <new experiment dir>
                              [--raider <FO4ActorRaider.esm>]
      exp_install.py holds one experiment at a time, so the mission goes in WITH the core set: a copy of the core's
      experiment folder plus FO4SFMission.esm and Data\Scripts\FO4SF_Min00Quest.pex, written only after verify
      passes on the result (built in a new <out>.partial-<time>-<pid>, kept on failure; an existing <out> is refused).
  python make_mission.py verify --exp-dir <experiment dir> --plan <stage dir>\plan.json [--raider <FO4ActorRaider.esm>]
      the install preflight: FO4SFMission.esm and the .pex in <exp-dir> match the plan's hashes, FO4TerrainCore.esm
      in <exp-dir> and FO4ActorRaider.esm (in <exp-dir>, else --raider) match the masters the plugin was built
      against (it copies the core's world record). Exit 1 on any mismatch or missing file: install only after exit 0.
  python make_mission.py log [--file <fo4sf_mission.0.log>]
      the mission's user log as a summary: stages reached in order, the last status line, the reward; exit 0 when
      stage 200 was reached, 1 otherwise.
Install (the install session, game closed, on the owner's words): fold, then verify, then
  python scripts/game/exp_install.py install --exp-dir <folded dir> --starfield <game> --plugins <the core set's list>,FO4SFMission.esm --pack
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PROJECT = os.path.join(REPO, "dotnet", "Mission")
PLUGIN = "FO4SFMission.esm"
SCRIPT = "FO4SF_Min00Quest"
# Codsworth's own model (scripts/actors/convert_codsworth.py, PR #361): the asset folders stage copies into Data and the
# mesh the plugin's ARMA names (relative to Data\Meshes)
ASSET_DIRS = ("meshes", "geometries", "materials", "textures")
CODSWORTH_MESH = "fo4port\\actors\\codsworth\\codsworth.nif"
# his voice (scripts/actors/codsworth_voice.py, PR #361): lines.tsv plus wem\Windows\<info>_<response>.wem. Each line
# gets a WEMFile id and its file is named by it under his voice type's folder (verified on the PC: all 20 vanilla
# robotminibota names are INFO WEMFile values, all below 0x01000000, so ours are too). He inherits RobotMiniBotA.
VOICE_DIR = "sound/voice/" + PLUGIN.lower() + "/robotminibota"
FIRST_WEM = 0x00F4C001
STAGES = (10, 20, 30, 40, 200)
# the script properties dotnet/Mission writes (Program.cs, Write): a renamed property would leave the script unbound
PROPERTIES = ("Preston", "Raiders", "Credits")
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User",
                   "fo4sf_mission.0.log")
LINE = re.compile(r"FO4SF_MISSION rt=(?P<rt>[-\d.]+) (?P<msg>.*)$")


def run(cmd, cwd=None):
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stdout.write(r.stderr)
        sys.exit(f"{os.path.basename(cmd[0])} exit {r.returncode}")
    return r.stdout


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def mandatory_properties(psc_text):
    """The names of the script's Auto Const Mandatory properties (what the plugin must fill), in source order."""
    return [m.group(1) for m in re.finditer(r"^\s*[\w\[\]]+\s+Property\s+(\w+)\s+Auto\s+Const\s+Mandatory\b",
                                            psc_text, re.M | re.I)]


def extract_sources(zip_path, work):
    """Every base script (Scripts/Source/*.psc, top level) and the flags file from ContentResources.zip: the quest
    script uses Actor, Quest, ObjectReference, MiscObject and their own imports, so all of them are given."""
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and (
                    parts[2].lower().endswith(".psc") or parts[2] == "Starfield_Papyrus_Flags.flg"):
                with z.open(name) as f, open(os.path.join(src, parts[2]), "wb") as o:
                    shutil.copyfileobj(f, o)
                n += 1
    if not os.path.exists(os.path.join(src, "Starfield_Papyrus_Flags.flg")) or n < 2:
        sys.exit(f"{zip_path}: no Scripts/Source base scripts or flags file")
    return src


def compile_script(compiler, src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    name = SCRIPT + ".psc"
    out = run([compiler, name, "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"], cwd=HERE)
    pex = os.path.join(out_dir, SCRIPT + ".pex")
    if "Compilation succeeded" not in out or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile did not produce {SCRIPT}.pex")
    return pex


def stage(a):
    with open(os.path.join(HERE, SCRIPT + ".psc"), encoding="utf-8") as f:
        props = mandatory_properties(f.read())
    if tuple(props) != PROPERTIES:
        sys.exit(f"{SCRIPT}.psc properties {props} differ from what dotnet/Mission writes {list(PROPERTIES)}")
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    masters = pin_masters((a.core, a.raider))            # the bytes the build reads, hashed before it starts
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work, exist_ok=True)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    points = os.path.join(work, "points.json")
    run(tool + ["points", a.fo4, points])
    alias = [] if a.alias else ["--no-alias"]
    cods = [] if a.codsworth else ["--no-codsworth"]
    assets = set()
    if getattr(a, "codsworth_assets", None):
        if not a.codsworth:
            sys.exit("--codsworth-assets needs Codsworth (drop --no-codsworth)")
        assets = set(copy_assets(a.codsworth_assets, os.path.join(out, "Data")))
        cods = ["--codsworth-model", CODSWORTH_MESH]
    if getattr(a, "codsworth_voice", None):
        if not a.codsworth:
            sys.exit("--codsworth-voice needs Codsworth (drop --no-codsworth)")
        voice_json = os.path.join(work, "voice.json")
        assets |= set(copy_voice(a.codsworth_voice, os.path.join(out, "Data"), voice_json))
        cods = cods + ["--codsworth-voice", voice_json]
    run(tool + ["write", a.starfield, a.core, a.raider, points, out, "--plugin", PLUGIN] + alias + cods)
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield, a.core, a.raider] + alias + cods)
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(check)
    src = extract_sources(a.content_resources, work)
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))
    with open(points, encoding="utf-8") as f:
        pts = json.load(f)
    drift = [f"{n}: {masters[n]} at the start, {h} now" for n, h in pin_masters((a.core, a.raider)).items()
             if h != masters[n]]
    if drift:
        sys.exit("a master changed during the build, nothing published (" + "; ".join(drift) + f"); attempt kept in {out}")
    plan = {"kind": "mission", "plugin": PLUGIN, "plugin_sha256": sha256(os.path.join(out, PLUGIN)),
            "script": SCRIPT, "script_sha256": sha256(pex), "alias": a.alias, "masters_sha256": masters, "stages": list(STAGES),
            "raiders": [r["src"] for r in pts["raiders"]], "preston": pts["preston"],
            "codsworth": pts.get("codsworth") if a.codsworth else None,
            "assets": {rel: sha256(os.path.join(out, "Data", rel)) for rel in sorted(assets)},
            "log": "<My Games>/Starfield/Logs/Script/User/fo4sf_mission.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    raiders = ", ".join(f"{r['src']} ({r.get('dist_m', '?')} m)" for r in pts["raiders"])
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Cut-down "When Freedom Calls" (Claude-cloud, {datetime.date.today().isoformat()}). docs/mission/when-freedom-calls.md
{PLUGIN} (sha256 {plan['plugin_sha256']}): QUST FO4SF_Min00 (start game enabled), NPC_ FO4_PrestonGarvey, Preston's ACHR
at the museum door's outside arrival {pts['preston']['pos']} m, {len(pts['raiders'])} raider ACHRs of FO4_LvlRaider at
Fallout 4's Concord positions ({raiders}), all persistent in the core world's persistent cell (WRLD override).
Codsworth: {"NPC_ FO4_Codsworth (a Starfield robot body under his name) at his Sanctuary spot " + str(plan["codsworth"]["pos"]) + " m, kept by QUST FO4SF_CodsworthKeeper (start game enabled, so it also starts on an existing save)" if plan["codsworth"] else "left out (--no-codsworth)"}.
Masters (must match the installed files): {json.dumps(masters)}. Rebuild after any core change.
Data\\Scripts\\{SCRIPT}.pex compiled from {SCRIPT}.psc (beside this file).
Install (game closed): exp_install.py holds one experiment, so fold this stage into a copy of the core set and
verify it first: python scripts\\mission\\make_mission.py fold --mission "{final}" --core-dir <core experiment dir> --out <new dir>
Logging needs the [Papyrus] keys of make_bridge.py ini (already set where the bridge runs).
In game: load a save, walk to Concord. The HUD shows the objectives; the log {plan['log']} gets each stage and a
status line every 5 s. Read it: python scripts\\mission\\make_mission.py log
Uninstall: exp_install.py uninstall.
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {os.path.relpath(pex, out)}, offline_check.txt, plan.json, README.txt")


def copy_assets(src, data):
    """Copies the asset folders (ASSET_DIRS) of a convert_codsworth.py output into data; anything else there (its
    report) stays out. Refuses a source without the mesh the plugin names. Returns the copied paths, relative to data."""
    mesh = os.path.join(src, "meshes", *CODSWORTH_MESH.split("\\"))
    if not os.path.isfile(mesh):
        sys.exit(f"--codsworth-assets {src} has no meshes\\{CODSWORTH_MESH}")
    copied = []
    for d in ASSET_DIRS:
        root = os.path.join(src, d)
        for dirpath, _, files in os.walk(root):
            for name in files:
                rel = os.path.relpath(os.path.join(dirpath, name), src)
                os.makedirs(os.path.join(data, os.path.dirname(rel)), exist_ok=True)
                shutil.copy2(os.path.join(src, rel), os.path.join(data, rel))
                copied.append(rel.replace(os.sep, "/"))
    return copied


def copy_voice(src, data, voice_json):
    """Reads src/lines.tsv, finds each line's src/wem/**/<info>_<response>.wem, copies it to data/VOICE_DIR/<wem>.wem
    with the line's WEMFile id (FIRST_WEM on, 8 lowercase hex digits) and writes voice.json for the writer. A line that
    says "sir" is for a male player, "mum" for a female one. Returns the copied paths, relative to data."""
    with open(os.path.join(src, "lines.tsv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    wems = {}
    for dirpath, _, files in os.walk(os.path.join(src, "wem")):
        for name in files:
            if name.lower().endswith(".wem"):
                wems.setdefault(name.lower(), []).append(os.path.join(dirpath, name))
    lines, copied = [], []
    for i, r in enumerate(rows):
        want = f"{r['info'].lower()}_{r['response']}.wem"
        hits = wems.get(want, [])
        if len(hits) != 1:
            sys.exit(f"--codsworth-voice: {len(hits)} files named {want} under {os.path.join(src, 'wem')}")
        wem = f"{FIRST_WEM + i:08x}"
        text = r["text"]
        sex = "male" if re.search(r"\bsir\b", text, re.I) else "female" if re.search(r"\bmum\b", text, re.I) else None
        rel = f"{VOICE_DIR}/{wem}.wem"
        os.makedirs(os.path.join(data, *VOICE_DIR.split("/")), exist_ok=True)
        shutil.copy2(hits[0], os.path.join(data, *rel.split("/")))
        copied.append(rel)
        lines.append({"info": r["info"], "response": int(r["response"]), "text": text, "wem": wem, "sex": sex})
    if not lines:
        sys.exit(f"--codsworth-voice: {src}/lines.tsv has no lines")
    with open(voice_json, "w", encoding="utf-8") as f:
        json.dump(lines, f, indent=1)
    return copied


def pin_masters(paths):
    """{file name: SHA-256} of the masters the plugin is built against."""
    return {os.path.basename(p): sha256(p) for p in paths}


def new_partial(final, create=True):
    """A new, unique attempt folder beside final (<final>.partial-<UTC time>-<pid>[-n]); never an existing one, so an
    earlier failed attempt or another writer's folder is never reused or deleted."""
    base = f"{final}.partial-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
    out, n = base, 1
    while os.path.exists(out):
        out, n = f"{base}-{n}", n + 1
    if create:
        os.makedirs(out)
    return out


def verify_dir(exp_dir, plan, raider=None):
    """Problems (a list of strings, empty when the experiment folder may be installed) of an experiment folder against
    a mission plan: the plugin and the script are the staged ones, the core and the raider plugin the ones it was
    built against."""
    problems = []

    def same(label, path, want):
        if not os.path.isfile(path):
            problems.append(f"{label}: {path} missing")
        elif sha256(path) != want:
            problems.append(f"{label}: {path} sha256 {sha256(path)} is not the plan's {want}")

    same("plugin", os.path.join(exp_dir, plan["plugin"]), plan["plugin_sha256"])
    same("script", os.path.join(exp_dir, "Data", "Scripts", plan["script"] + ".pex"), plan["script_sha256"])
    for rel, want in plan.get("assets", {}).items():
        same("asset", os.path.join(exp_dir, "Data", *rel.split("/")), want)
    for name, want in plan["masters_sha256"].items():
        path = os.path.join(exp_dir, name)
        if not os.path.isfile(path) and raider and name.lower() == os.path.basename(raider).lower():
            path = raider
        same(f"master {name}", path, want)
    return problems


def load_plan(path):
    with open(path, encoding="utf-8") as f:
        plan = json.load(f)
    missing = [k for k in ("plugin", "plugin_sha256", "script", "script_sha256", "masters_sha256") if k not in plan]
    if missing or plan.get("kind") != "mission":
        sys.exit(f"{path} is not a mission plan (missing {missing})")
    return plan


def verify(a):
    problems = verify_dir(a.exp_dir, load_plan(a.plan), a.raider)
    for p in problems:
        print("FAIL  " + p)
    print("verify: ok" if not problems else f"verify: {len(problems)} problem(s); do not install")
    return 0 if not problems else 1


def fold(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: fold into a new folder")
    plan = load_plan(os.path.join(a.mission, "plan.json"))
    if os.path.exists(os.path.join(a.core_dir, plan["plugin"])):
        sys.exit(f"{a.core_dir} already holds {plan['plugin']}")
    out = new_partial(final, create=False)
    shutil.copytree(a.core_dir, out)
    shutil.copy2(os.path.join(a.mission, plan["plugin"]), os.path.join(out, plan["plugin"]))
    for rel in ["Scripts/" + plan["script"] + ".pex"] + sorted(plan.get("assets", {})):
        dst = os.path.join(out, "Data", *rel.split("/"))
        if os.path.exists(dst):
            sys.exit(f"fold refused: the core set already has Data/{rel} (attempt kept in {out})")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(a.mission, "Data", *rel.split("/")), dst)
    problems = verify_dir(out, plan, a.raider)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        sys.exit(f"fold refused: {len(problems)} problem(s); nothing published (attempt kept in {out})")
    os.replace(out, final)
    print(f"folded {final}: {a.core_dir} + {plan['plugin']} + Data\\Scripts\\{plan['script']}.pex"
          f" + {len(plan.get('assets', {}))} Codsworth asset(s); verify ok")
    return 0


def next_stage(stage, dead, total, fighting, at_preston, found=False):
    """The script's NextStage (FO4SF_Min00Quest.psc), the same rule in Python so it can be tested: the fight counts as
    started when a raider fights or is dead (whoever started it, a reload mid-fight included) or the player has found
    Preston (activated him or came within FindRadius before the fight), all dead is 30, standing at Preston after that
    is 40; it never goes back."""
    s = stage
    if s < 20 and (fighting or dead > 0 or found):
        s = 20
    if s < 30 and total > 0 and dead == total:
        s = 30
    if s == 30 and at_preston:
        s = 40
    return s


def summarize(lines):
    """The mission log's lines as {"stages": [...], "status": <last status line or None>, "reward": int or None,
    "startcombat": n, "activated": n, "found": <how the player found Preston before the fight, or None>}; lines of
    other logs are ignored."""
    s = {"stages": [], "status": None, "reward": None, "startcombat": 0, "activated": 0, "found": None}
    for line in lines:
        m = LINE.search(line)
        if not m:
            continue
        msg = m.group("msg")
        if msg.startswith("stage "):
            s["stages"].append(int(msg.split()[1]))
        elif msg.startswith("status "):
            s["status"] = msg
        elif msg.startswith("reward credits="):
            s["reward"] = int(msg.split("=", 1)[1])
        elif msg.startswith("startcombat "):
            s["startcombat"] += 1
        elif msg.startswith("preston activated"):
            s["activated"] += 1
        elif msg.startswith("found preston ") and s["found"] is None:
            s["found"] = msg[len("found preston "):]
    return s


def log(a):
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = summarize(f)
    print(json.dumps(s, indent=1))
    return 0 if 200 in s["stages"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--fo4", required=True)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--core", required=True)
    s.add_argument("--raider", required=True)
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(STARFIELD, "Tools", "ContentResources.zip"))
    s.add_argument("--no-alias", dest="alias", action="store_false")
    s.add_argument("--no-codsworth", dest="codsworth", action="store_false", help="leave Codsworth out of the plugin")
    s.add_argument("--codsworth-voice", default=None,
                   help="a codsworth_voice.py output folder (lines.tsv, wem): his Hello lines and their .wem files")
    s.add_argument("--codsworth-assets", default=None,
                   help="a convert_codsworth.py output folder: his own model (ARMA, skin ARMO) and its files in Data")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    v = sub.add_parser("verify")
    v.add_argument("--exp-dir", required=True)
    v.add_argument("--plan", required=True)
    v.add_argument("--raider", default=None)
    fo = sub.add_parser("fold")
    fo.add_argument("--mission", required=True)
    fo.add_argument("--core-dir", required=True)
    fo.add_argument("--out", required=True)
    fo.add_argument("--raider", default=None)
    a = p.parse_args(argv)
    if a.cmd == "stage":
        stage(a)
        return 0
    if a.cmd == "verify":
        return verify(a)
    if a.cmd == "fold":
        return fold(a)
    return log(a)


if __name__ == "__main__":
    sys.exit(main())
