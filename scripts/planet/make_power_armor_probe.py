"""Stage the power armor probe (docs/research/power-armor-probe.md): FO4SFPowerArmorProbe.esm and its script.

usage:
  python make_power_armor_probe.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs, and each optional reading's name, looked up in Starfield's base
      sources (Scripts/Source of ContentResources.zip; inheritance followed). Exit 1 when a required one is missing.
  python make_power_armor_probe.py stage --out <dir> [--starfield <Starfield.esm>] [--compiler <exe>]
                                         [--content-resources <zip>] [--control <furniture editor id>]
                                         [--variant race,furniture,keyword,armor] [--armor <armor editor id>] [--kw-first]
      1. dotnet/PowerArmorProbe build + check against the Starfield.esm given (offline_check.txt). --variant overrides
         Starfield's empty power armor default objects in the plugin, each on its own (race: PowerArmorRace_DO ->
         FO4SF_PARace; furniture: PowerArmorDefaultFrameFurniture_DO -> the suit, which also gets isPowerArmorFrame; keyword:
         PowerArmorArmorKeyword_DO -> a keyword of ours; armor: PowerArmorDefaultFrameArmor_DO -> a copy of a plain vanilla
         armor (--armor, required with it) that carries isPowerArmorFrame); the PC run of 11 Nov (stage 10 did nothing) suggested it;
      2. the Papyrus compile: each optional reading (";OPT <Base.Name> " lines of the .psc) whose name the base sources
         declare is compiled on its own, the ones that compile are kept, every other one is reported in plan.json
         ("optional") and logs "na"; then the script itself;
      3. plan.json (SHA-256 of every file, of Starfield.esm, the optional readings' fate) and README.txt. Built in a new
         <out>.partial-<time>-<pid> and renamed to <out> only when every step passed; an existing <out> is refused.
  python make_power_armor_probe.py log [--file <FO4SFPAProbe.0.log>] [--papyrus <Papyrus.0.log>]
      the run's user log (and the game's Papyrus log: errors naming our forms, a refused stage 10) as one table and a verdict (src/fo4sf/powerarmor/probe_log.py); exit 0 when the control held,
      1 when the session is inconclusive.
Nothing here installs anything: scripts/planet/power_armor_probe_install.py does, on the owner's word, game closed.
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
from fo4sf.powerarmor import probe_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "PowerArmorProbe")
PLUGIN = "FO4SFPowerArmorProbe.esm"
SCRIPT = "FO4SF_PAProbeQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
DEFAULT_CONTROL = "NPCChairTech03_Free_270"
VARIANTS = ("race", "furniture", "keyword", "armor")
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
PAPYRUS_LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "Papyrus.0.log")
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFPAProbe.0.log")
# what the script cannot run without (the optional readings are the .psc's ";OPT" lines)
REQUIRED = {
    "Actor": ["SwitchToPowerArmor", "SetRace", "GetRace", "GetPositionX", "GetPositionY", "GetPositionZ", "GetDistance",
              "GetParentCell"],
    "Game": ["GetPlayer", "GetFormFromFile", "IsPluginInstalled"],
    "Debug": ["OpenUserLog", "TraceUser"],
    "Utility": ["GetCurrentRealTime"],
    "Quest": ["GetStageDone"],
    "ScriptObject": ["StartTimer"],
    "Form": ["GetFormID"],
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


def precheck_sources(sources, text):
    """{"required": {"Base.Name": bool}, "optional": {"Base.Name": bool}, "missing": [required names not declared]}."""
    req = {f"{b}.{f}": declares(sources, b, f) for b, fs in REQUIRED.items() for f in fs}
    opt = {n: declares(sources, *n.split(".")) for n in optional_names(text)}
    return {"required": req, "optional": opt, "missing": [k for k, ok in req.items() if not ok]}


def precheck(a):
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    r = precheck_sources(read_sources(a.content_resources), text)
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


def compile_text(compiler, text, src_dir, out_dir):
    """Compile the script's text; (True, "") or (False, the compiler's first error line)."""
    with tempfile.TemporaryDirectory(prefix="fo4sf-pa-compile-") as work:
        with open(os.path.join(work, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.makedirs(out_dir, exist_ok=True)
        r = subprocess.run([compiler, SCRIPT + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={work};{src_dir}", f"-o={out_dir}"],
                           cwd=work, capture_output=True, text=True)
    ok = r.returncode == 0 and "Compilation succeeded" in r.stdout and os.path.exists(os.path.join(out_dir, SCRIPT + ".pex"))
    if ok:
        return True, ""
    err = next((l.strip() for l in (r.stdout + r.stderr).splitlines() if "error" in l.lower()), "no compiler output")
    return False, err


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
    if plan.get("kind") != "power-armor-probe" or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the power armor probe's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
        sys.exit(f"{path} missing: stage with make_power_armor_probe.py first")
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
    variant = [v for v in a.variant.split(",") if v]
    if [v for v in variant if v not in VARIANTS] or len(set(variant)) != len(variant):
        sys.exit(f"--variant is a comma list of {', '.join(VARIANTS)}, each once (got {a.variant!r})")
    if "armor" in variant and not a.armor:
        sys.exit("--variant armor copies a plain vanilla armor: name it with --armor <armor editor id> (the tool lists candidates)")
    opts = ["--control", a.control, "--variant", ",".join(variant)] + (["--armor", a.armor] if a.armor else []) + (
        ["--kw-first"] if a.kw_first else [])
    wrote = run(tool + ["build", a.starfield, out] + opts).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield] + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    src = extract_sources(a.content_resources, work)
    pre = precheck_sources(read_sources(a.content_resources), text)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    # each optional reading on its own: declared, then compiles
    fate, keep = {}, []
    for name, declared in pre["optional"].items():
        if not declared:
            fate[name] = "not declared in the base scripts"
            continue
        ok, err = compile_text(a.compiler, enable(text, [name]), src, os.path.join(work, "try"))
        fate[name] = "kept" if ok else f"declared but did not compile: {err}"
        if ok:
            keep.append(name)
    scripts = os.path.join(out, "Data", "Scripts")
    final_text = enable(text, keep)
    ok, err = compile_text(a.compiler, final_text, src, scripts)
    if not ok:
        sys.exit(f"the Papyrus compile of {SCRIPT}.psc with {keep or 'no optional reading'} failed: {err}")
    with open(os.path.join(out, SCRIPT + ".psc"), "w", encoding="utf-8", newline="\n") as f:
        f.write(final_text)
    shutil.rmtree(work)
    if sha256(a.starfield) != before:
        sys.exit(f"Starfield.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": "power-armor-probe", "version": 1, "plugins": [PLUGIN], "outputs": stage_files(out),
            "inputs": {"Starfield.esm": {"sha256": before}}, "control": a.control, "variant": variant, "armor": a.armor, "kw_first": bool(a.kw_first), "optional": fate,
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFPAProbe.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Power armor probe ({datetime.date.today().isoformat()}). docs/research/power-armor-probe.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): CELL FO4SF_PAProbeCell (coc FO4SF_PAProbeCell), FURN FO4SF_PAProbeSuit (a copy of
{a.control} with FurnitureTypePowerArmor added), the vanilla {a.control} beside it as the control, RACE FO4SF_PARace
(a copy of HumanRace), QUST FO4SF_PAProbeQuest (start game enabled, stages 10 / 20 / 30). Master Starfield.esm only; adds
records, overrides none. Checked against Starfield.esm {before}. Re-stage after a game update.
Variant (default objects overridden): {', '.join(variant) or 'none'}{f' (frame armor: a copy of {a.armor})' if a.armor else ''}.
Optional readings: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}.
Install (the owner's word, game closed; loose scripts are not read, the installer packs them into a ba2):
  python scripts\\planet\\power_armor_probe_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\planet\\power_armor_probe_install.py uninstall --starfield <game dir>
Read:    python scripts\\planet\\make_power_armor_probe.py log
Session card: docs/research/power-armor-probe.md. THROWAWAY STATE ONLY, NO SAVE (the race swap can break a save).
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, offline_check.txt, plan.json, README.txt; optional readings: {fate}")
    return 0


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    papyrus = None
    if a.papyrus and os.path.isfile(a.papyrus):      # the game's own log: a refusal of SwitchToPowerArmor is only there
        with open(a.papyrus, encoding="utf-8", errors="replace") as f:
            papyrus = f.read().splitlines()
    with open(a.file, encoding="utf-8", errors="replace") as f:
        s = probe_log.summarize(f, papyrus=papyrus)
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
    s.add_argument("--control", default=DEFAULT_CONTROL)
    s.add_argument("--variant", default="", help="comma list of default objects to override: race, furniture, keyword, armor")
    s.add_argument("--armor", default="", help="the plain vanilla armor the armor variant copies (editor ID)")
    s.add_argument("--kw-first", action="store_true", help="FurnitureTypePowerArmor first in the suit's keyword list")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    g.add_argument("--papyrus", default=PAPYRUS_LOG, help="the game's Papyrus.0.log (errors naming our forms are shown)")
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
