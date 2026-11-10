"""Stage the rads probe (docs/research/rads-probe.md): FO4SFRadsProbe.esm and its script.

usage:
  python make_rads_probe.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs, and each optional reading's name, looked up in Starfield's base
      sources (Scripts/Source of ContentResources.zip; inheritance followed). Exit 1 when a required one is missing.
  python make_rads_probe.py stage --out <dir> [--starfield <Starfield.esm>] [--compiler <exe>]
                                         [--content-resources <zip>] [--health <AVIF editor id>] [--type <AVIF type>]
      1. dotnet/RadsProbe build + check against the Starfield.esm given (offline_check.txt);
      2. the Papyrus compile: each optional reading (";OPT <Base.Name> " lines of the .psc) whose name the base sources
         declare is compiled on its own, the ones that compile are kept, every other one is reported in plan.json
         ("optional") and logs "na"; then the script itself;
      3. plan.json (SHA-256 of every file, of Starfield.esm, the optional readings' fate) and README.txt. Built in a new
         <out>.partial-<time>-<pid> and renamed to <out> only when every step passed; an existing <out> is refused.
  python make_rads_probe.py log [--file <FO4SFRadsProbe.0.log>]
      the run's user log as one table and a verdict (src/fo4sf/rads/probe_log.py); exit 0 when the control held,
      1 when the session is inconclusive. The log is looked for under OneDrive\\Documents first, then Documents.
  python make_rads_probe.py console [--file <FO4SFRadsProbe.0.log>]
      the card's console lines with this session's quest form id (the console does not find the quest by name).
Nothing here installs anything: scripts/planet/rads_probe_install.py does, on the owner's word, game closed.
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
from fo4sf.rads import probe_log  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "RadsProbe")
PLUGIN = "FO4SFRadsProbe.esm"
SCRIPT = "FO4SF_RadsProbeQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
HAND_SCRIPT = "FO4SF_RadsHandQuest"       # the by-hand mode (FAL-273): same plugin, its own quest and script
HAND_PSC = os.path.join(HERE, HAND_SCRIPT + ".psc")
DEFAULT_HEALTH = "Health"        # Starfield.esm's own Health AVIF: the control and the route's target
DEFAULT_TYPE = "Variable"          # the type our AVIF is written with (an open question: the PC run tells)
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
LOG_NAME = "FO4SFRadsProbe.0.log"


def user_logs(name=LOG_NAME):
    """Where the game writes the user log, in the order tried: Documents under OneDrive (the owner's PC, as
    make_planet_probe.py's user_logs), then plain Documents."""
    home = os.path.expanduser("~")
    return [os.path.join(home, *base, "My Games", "Starfield", "Logs", "Script", "User", name)
            for base in (("OneDrive", "Documents"), ("Documents",))]


def default_log():
    """The first existing log of user_logs(), else the first candidate (so the message names a real place)."""
    found = [p for p in user_logs() if os.path.isfile(p)]
    return found[0] if found else user_logs()[0]


LOG = default_log()
# what the script cannot run without (the optional readings are the .psc's ";OPT" lines)
REQUIRED = {
    "Actor": ["GetValue", "SetValue", "AddItem", "EquipItem", "GetItemCount"],
    "Spell": ["Cast"],
    "Game": ["GetPlayer", "IsPluginInstalled"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
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


def precheck_sources(sources, text, hand_text=""):
    """{"required": {"Base.Name": bool}, "optional": {"Base.Name": bool}, "missing": [required names not declared]}.
    The optional names are those of the probe script, then those of the by-hand script (hand_text) not already listed."""
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
    with tempfile.TemporaryDirectory(prefix="fo4sf-rads-compile-") as work:
        with open(os.path.join(work, script + ".psc"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.makedirs(out_dir, exist_ok=True)
        r = subprocess.run([compiler, script + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={work};{src_dir}", f"-o={out_dir}"],
                           cwd=work, capture_output=True, text=True)
    ok = r.returncode == 0 and "Compilation succeeded" in r.stdout and os.path.exists(os.path.join(out_dir, script + ".pex"))
    if ok:
        return True, ""
    err = next((l.strip() for l in (r.stdout + r.stderr).splitlines() if "error" in l.lower()), "no compiler output")
    return False, err


def template_line(text):
    """The writer's "templates (<level>): SPEL ..., MGEF ..., ALCH ..." line (the vanilla records the effect, the spell
    and RadAway were copied from), "" when there is none."""
    m = re.search(r"^templates \((\w+)\): (.*)$", text, re.M)
    return f"{m.group(1)}: {m.group(2)}" if m else ""


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
    if plan.get("kind") != "rads-probe" or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the rads probe's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
        sys.exit(f"{path} missing: stage with make_rads_probe.py first")
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
    opts = ["--health", a.health, "--type", a.type]
    if a.template_spell:
        opts += ["--template-spell", a.template_spell]
    if a.template_aid:
        opts += ["--template-aid", a.template_aid]
    wrote = run(tool + ["build", a.starfield, out] + opts).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield] + opts).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    with open(HAND_PSC, encoding="utf-8") as f:
        hand_text = f.read()
    src = extract_sources(a.content_resources, work)
    pre = precheck_sources(read_sources(a.content_resources), text, hand_text)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    scripts = os.path.join(out, "Data", "Scripts")

    def build_script(name, source_text):
        """Each optional reading of the script on its own (declared, then compiles), then the script with the kept ones:
        (fate of every optional reading, final text). Exits when the script does not compile."""
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
    if sha256(a.starfield) != before:
        sys.exit(f"Starfield.esm changed during the build, nothing published; attempt kept in {out}")
    plan = {"kind": "rads-probe", "version": 1, "plugins": [PLUGIN], "outputs": stage_files(out),
            "inputs": {"Starfield.esm": {"sha256": before}}, "health": a.health, "avif_type": a.type, "templates": template_line(wrote), "optional": fate, "optional_hand": hand_fate,
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFRadsProbe.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Rads probe ({datetime.date.today().isoformat()}). docs/research/rads-probe.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): AVIF FO4SF_Rads ({a.type}, default 0, 0 to 1000), MGEF FO4SF_RadsEffect (value
modifier on it), SPEL FO4SF_RadsSpell (+100), ALCH FO4SF_RadAway "RadAway" (-200), QUST FO4SF_RadsProbeQuest (start game
enabled, stages 10 / 20 / 30 / 40, four properties: our AVIF, Starfield's {a.health}, the spell, RadAway), ALCH FO4SF_RadDose
"Rad Dose" (+100), QUST FO4SF_RadsHandQuest (by hand: no console, gives 3 RadAway and 3 Rad Dose, shows every rads change on
screen; script {HAND_SCRIPT}). Master
Starfield.esm only; adds records, overrides none. Checked against Starfield.esm {before}. Re-stage after a game update.
Optional readings: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}; by hand: {', '.join(f'{k}: {v}' for k, v in hand_fate.items()) or 'none'}.
Install (the owner's word, game closed; loose scripts are not read, the installer packs them into a ba2):
  python scripts\\planet\\rads_probe_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\planet\\rads_probe_install.py uninstall --starfield <game dir>
Read:    python scripts\\planet\\make_rads_probe.py log
Console lines of this session (the quest is found by form id, not name):
  python scripts\\planet\\make_rads_probe.py console
Session card: docs/research/rads-probe.md. No save unless the owner allowed one (variant B of the card).
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


def console(a):
    """The exact console lines of the session card for this game session: the console does not find the quest by its
    editor id, so setstage takes the form id from the init line of the user log (the quest starts with the game)."""
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}: start the game with the probe ticked, then run this again")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        rs, _ = probe_log.runs(f)
    quest = next((e.get("quest") for r in reversed(rs) for e in r if e["event"] == "init" and isinstance(e.get("quest"), int)), None)
    if quest is None:
        print("no init line with a quest id in the log: the script has not started yet")
        return 1
    for stage in probe_log.STAGES:
        print(f"setstage {quest:08X} {stage}")
    print("player.getav FO4SF_Rads")
    print("player.getav health")
    return 0


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
    s.add_argument("--health", default=DEFAULT_HEALTH)
    s.add_argument("--type", default=DEFAULT_TYPE)
    s.add_argument("--template-spell", default="", help="a vanilla self-cast value-modifier spell to copy (default: found)")
    s.add_argument("--template-aid", default="", help="a vanilla medicine ingestible to copy (default: found)")
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    c = sub.add_parser("console")
    c.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "log": log, "console": console}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
