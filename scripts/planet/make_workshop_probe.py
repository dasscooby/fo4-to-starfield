"""Stage the workshop probe (docs/research/workshop-probe.md): FO4SFWorkshopProbe.esm and its two scripts.

usage:
  python make_workshop_probe.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs, and each optional reading's name, looked up in Starfield's base
      sources (Scripts/Source of ContentResources.zip; inheritance followed). Exit 1 when a required one is missing.
  python make_workshop_probe.py stage --out <dir> [--starfield <Starfield.esm>] [--compiler <exe>]
                                         [--content-resources <zip>] [--item <MISC editor id>]
                                         [--beacon <hex form id of the vanilla outpost beacon base>]
      1. dotnet/WorkshopProbe build + check against the Starfield.esm given (offline_check.txt);
      2. the Papyrus compile: each optional reading (";OPT <Base.Name> " lines of the .psc) whose name the base sources
         declare is compiled on its own, the ones that compile are kept, every other one is reported in plan.json
         ("optional") and logs "na"; then the script itself;
      3. plan.json (SHA-256 of every file, of Starfield.esm, the optional readings' fate) and README.txt. Built in a new
         <out>.partial-<time>-<pid> and renamed to <out> only when every step passed; an existing <out> is refused.
  python make_workshop_probe.py scan [--content-resources <zip>] [--out <scan.txt>]
      read only, no game: every function of ObjectReference / Game / Location / Form / Actor whose name says workshop,
      outpost or beacon, and every call line of the base scripts whose own name says so: what vanilla's beacon script
      actually calls. Post it before the PC session.
  python make_workshop_probe.py resources [--starfield <Starfield.esm>] [--match <regex>] [--out <additem.txt>]
      read only: the COBJ of the workbench stations, their components, the player.additem lines (dotnet/WorkshopProbe).
  python make_workshop_probe.py log [--file <FO4SFWorkshop.0.log>]
      the run's user log as one table and a verdict (src/fo4sf/workshop/probe_log.py); exit 0 when the bench and the
      control pad were both placed, 1 when the session is inconclusive.
Nothing here installs anything: scripts/planet/workshop_probe_install.py does, on the owner's word, game closed.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
sys.path.insert(0, os.path.join(REPO, "src"))
from make_newgame import declares, extract_sources, new_partial, run  # noqa: E402
from fo4sf.workshop import probe_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "WorkshopProbe")
PLUGIN = "FO4SFWorkshopProbe.esm"
SCRIPT = "FO4SF_WSProbeQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
HAND_SCRIPT = "FO4SF_WSHandQuest"        # the by-hand mode (FAL-273): same plugin, its own quest and script
HAND_PSC = os.path.join(HERE, HAND_SCRIPT + ".psc")
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFWorkshop.0.log")
# what the script cannot run without (the optional readings are the .psc's ";OPT" lines)
REQUIRED = {
    "Actor": ["GetActorBase", "GetItemCount", "AddItem", "PlaceAtMe", "GetPositionX", "GetPositionY", "GetPositionZ",
              "GetDistance", "GetParentCell", "GetAngleZ"],
    "ObjectReference": ["Is3DLoaded", "IsDisabled", "Disable", "Enable", "Activate", "GetBaseObject"],
    "Math": ["Sin", "Cos"],
    "Game": ["GetPlayer", "GetFormFromFile", "IsPluginInstalled"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
    "Utility": ["GetCurrentRealTime"],
    "Quest": ["GetStageDone"],
    "ScriptObject": ["StartTimer"],
    "Form": ["GetFormID", "HasKeyword"],
}
OPT = re.compile(r"^;OPT (?P<name>[\w]+\.[\w]+) ", re.M)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def optional_names(text):
    """The optional readings the script lists, in order: ["Actor.GetWornItem", ...]."""
    return list(dict.fromkeys(m.group("name") for m in OPT.finditer(text)))


def enable(text, names):
    """The script's text with the ";OPT <name> " prefix removed from every line of the names given."""
    keep = set(names)

    def sub(m):
        return "" if m.group("name") in keep else m.group(0)
    return OPT.sub(sub, text)


def read_sources(zip_path):
    """{lower case script name: source} of the base scripts (Scripts/Source/*.psc)."""
    sources = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            parts = name.split("/")
            if len(parts) == 3 and parts[:2] == ["Scripts", "Source"] and name.lower().endswith(".psc"):
                sources[parts[2][:-4].lower()] = z.read(name).decode("utf-8", errors="replace")
    return sources


def precheck_sources(sources, text, hand_text=""):
    """{"required": {"Base.Name": bool}, "optional": {"Base.Name": bool}, "missing": [required names not declared]}."""
    req = {f"{b}.{f}": declares(sources, b, f) for b, fs in REQUIRED.items() for f in fs}
    opt = {n: declares(sources, *n.split(".")) for n in dict.fromkeys(optional_names(text) + optional_names(hand_text))}
    return {"required": req, "optional": opt, "missing": [k for k, ok in req.items() if not ok]}


def precheck(a):
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    with open(HAND_PSC, encoding="utf-8") as f:
        hand_text = f.read()
    r = precheck_sources(read_sources(a.content_resources), text, hand_text)
    for k, ok in r["required"].items():
        print(f"{'ok  ' if ok else 'MISSING'}  {k}")
    for k, ok in r["optional"].items():
        print(f"{'declared' if ok else 'not declared'}  (optional) {k}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1)
    print("precheck: " + ("ok" if not r["missing"] else f"{len(r['missing'])} required name(s) missing; do not stage") +
          "".join(f"; optional {k} is not declared (that reading logs na)" for k, ok in r["optional"].items() if not ok))
    return 0 if not r["missing"] else 1


def compile_text(compiler, text, src_dir, out_dir, script=SCRIPT):
    """Compile the script's text; (True, "") or (False, the compiler's first error line)."""
    with tempfile.TemporaryDirectory(prefix="fo4sf-ws-compile-") as work:
        with open(os.path.join(work, script + ".psc"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.makedirs(out_dir, exist_ok=True)
        r = subprocess.run([compiler, script + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={work};{src_dir}", f"-o={out_dir}"],
                           cwd=work, capture_output=True, text=True)
    ok = r.returncode == 0 and "Compilation succeeded" in r.stdout and os.path.exists(os.path.join(out_dir, script + ".pex"))
    if ok:
        return True, ""
    # the compiler's own lines: "X.psc(12,3): ..." (some carry no word "error", e.g. "variable race cannot have the same name ...")
    lines = [l.strip() for l in (r.stdout + r.stderr).splitlines() if ".psc(" in l or "error" in l.lower()]
    err = " | ".join(lines[:8]) if lines else "no compiler output"
    return False, err


def set_beacon(text, beacon):
    """The script's text with the vanilla beacon base's id put in (--beacon <hex>; empty keeps 0: stage 40 says it was not given)."""
    if not beacon:
        return text
    if not re.fullmatch(r"(0x)?[0-9A-Fa-f]{1,8}", beacon):
        sys.exit(f"--beacon {beacon!r} is not a hex form id")
    new = re.sub(r"^int BeaconId = 0 +;BEACON", "int BeaconId = 0x" + beacon.lower().removeprefix("0x") + "  ;BEACON", text, count=1, flags=re.M)
    if new == text:
        sys.exit("the script has no 'int BeaconId = 0 ;BEACON' line to put the id into")
    return new


WORDS = re.compile(r"workshop|outpost|beacon", re.I)
SCAN_BASES = ("objectreference", "game", "location", "form", "actor", "quest", "scriptobject")


def scan_sources(sources):
    """Lines (text) naming workshop / outpost / beacon natives and calls in the base scripts: Function / Event lines of the
    scripts in SCAN_BASES, then every non-comment line of each script whose own name matches that calls something."""
    out = []
    for base in SCAN_BASES:
        for ln in sources.get(base, "").splitlines():
            if re.match(r"\s*(Function|Event|\w[\w:\[\]]*\s+Function)\b", ln, re.I) or " function " in ln.lower():
                if WORDS.search(ln):
                    out.append(f"{base}: {ln.strip()}")
    for name in sorted(n for n in sources if WORDS.search(n)):
        out.append(f"== script {name}")
        for ln in sources[name].splitlines():
            t = ln.strip()
            if t and not t.startswith(";") and re.search(r"\w\(", t):
                out.append(f"  {t}")
    return out


def scan(a):
    lines = scan_sources(read_sources(a.content_resources))
    print("\n".join(lines))
    print(f"scan: {len(lines)} line(s)")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return 0 if lines else 1


def resources(a):
    r = run(["dotnet", "run", "-c", "Release", "--project", PROJECT, "--", "resources", a.starfield, "--match", a.match])
    if a.out:
        adds = [l for l in r.stdout.splitlines() if l.startswith("player.additem ")]
        with open(a.out, "w", encoding="utf-8") as f:
            f.write("\n".join(adds) + "\n")
    return 0


def stage_files(out):
    """{path relative to the stage, "/" separated: SHA-256} of the plugin and every file under Data/."""
    files = {}
    for name in sorted(os.listdir(out)):
        if name.lower().endswith(".esm"):
            files[name] = sha256(os.path.join(out, name))
    for root, dirs, names in os.walk(os.path.join(out, "Data")):
        dirs.sort()
        for n in sorted(names):
            p = os.path.join(root, n)
            files[os.path.relpath(p, out).replace(os.sep, "/")] = sha256(p)
    return files


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, Starfield.esm."""
    problems = []
    if plan.get("kind") != "workshop-probe" or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the workshop probe's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
        sf = os.path.join(data, "Starfield.esm")
        if not os.path.isfile(sf):
            problems.append(f"no Starfield.esm in {data}: name the game's Data folder (the install: the game folder)")
        elif sha256(sf) != plan["inputs"]["Starfield.esm"]["sha256"]:
            problems.append("Starfield.esm changed since the stage: re-stage")
    return problems


def load_plan(stage_dir):
    path = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_workshop_probe.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    before = sha256(a.starfield)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    tool = ["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"]
    opts = ["--item", a.item] if a.item else []
    wrote = run(tool + ["build", a.starfield, out] + opts).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield] + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = set_beacon(f.read(), a.beacon)
    with open(HAND_PSC, encoding="utf-8") as f:
        hand_text = f.read()
    src = extract_sources(a.content_resources, work)
    pre = precheck_sources(read_sources(a.content_resources), text, hand_text)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    scripts = os.path.join(out, "Data", "Scripts")

    def build_script(name, source_text):
        """Each optional reading of the script on its own (declared, then compiles), then the script with the kept ones:
        the fate of every optional reading. Exits when the script does not compile."""
        fate, keep = {}, []
        for opt in optional_names(source_text):
            if not pre["optional"][opt]:
                fate[opt] = "not declared in the base scripts"
                continue
            ok, err = compile_text(a.compiler, enable(source_text, [opt]), src, os.path.join(work, "try"), name)
            fate[opt] = "kept" if ok else f"declared but did not compile: {err}"
            if ok:
                keep.append(opt)
        final_text = enable(source_text, keep)
        ok, err = compile_text(a.compiler, final_text, src, scripts, name)
        if not ok:
            sys.exit(f"the Papyrus compile of {name}.psc with {keep or 'no optional reading'} failed: {err}")
        with open(os.path.join(out, name + ".psc"), "w", encoding="utf-8", newline="\n") as f:
            f.write(final_text)
        return fate

    fate = build_script(SCRIPT, text)
    hand_fate = build_script(HAND_SCRIPT, hand_text)
    shutil.rmtree(work)
    # what the owner's PC run needs next to the plugin: the base scripts' workshop / outpost / beacon lines, and the
    # player.additem lines of the stations' resources (read from Starfield.esm by dotnet/WorkshopProbe)
    with open(os.path.join(out, "scan.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(scan_sources(read_sources(a.content_resources))) + "\n")
    res = run(tool + ["resources", a.starfield], check=False)
    with open(os.path.join(out, "additem.txt"), "w", encoding="utf-8") as f:
        f.write(res.stdout)
    if sha256(a.starfield) != before:
        sys.exit(f"Starfield.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": "workshop-probe", "version": 1, "plugins": [PLUGIN], "outputs": stage_files(out),
            "inputs": {"Starfield.esm": {"sha256": before}}, "item": a.item or "", "beacon": a.beacon or "", "optional": fate, "optional_hand": hand_fate,
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFWorkshop.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Workshop probe ({datetime.date.today().isoformat()}). docs/research/workshop-probe.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): QUST FO4SF_WSProbeQuest (start game enabled, stages 10..60: spawn the core's
workshop base, one call per sub-stage on it and on the vanilla OutpostPlayerHouseActivator 0x024DC7, the vanilla beacon,
readings), QUST FO4SF_WSHandQuest (by hand: a kit item that places the bench when dropped), MISC FO4SF_WSKit (a copy of one
vanilla MISC). Master Starfield.esm only; adds records, overrides none; the installed core is found by script, not mastered.
Checked against Starfield.esm {before}. Re-stage after a game update.
Optional readings: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}; by hand: {', '.join(f'{k}: {v}' for k, v in hand_fate.items()) or 'none'}.
Install (the owner's word, game closed; loose scripts are not read, the installer packs them into a ba2):
  python scripts\\planet\\workshop_probe_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\planet\\workshop_probe_install.py uninstall --starfield <game dir>
Read:    python scripts\\planet\\make_workshop_probe.py log
Session card: docs/research/workshop-probe.md. THROWAWAY STATE ONLY, NO SAVE (spawned persistent references would stay in it).
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, {HAND_SCRIPT}.pex, offline_check.txt, plan.json, README.txt; optional readings: {fate}")
    return 0


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = probe_log.summarize(f)
    print("\n".join(probe_log.report(s)))
    return 0 if s["control"][0] else 1


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
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=cr)
    s.add_argument("--item", default="", help="MISC editor id the hand kit copies (default: the tool's list)")
    s.add_argument("--beacon", default="", help="hex form id (Starfield.esm) of the vanilla outpost beacon base, for stage 40")
    sc = sub.add_parser("scan")
    sc.add_argument("--content-resources", default=cr)
    sc.add_argument("--out", default=None)
    rs = sub.add_parser("resources")
    rs.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    rs.add_argument("--match", default="Workbench|Lab|Station")
    rs.add_argument("--out", default=None)
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "log": log, "scan": scan, "resources": resources}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
