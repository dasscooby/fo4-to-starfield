"""Stage the player-furniture control kit, variant P (docs/research/player-furniture-kit.md, FAL-518): FO4SFPlayerFurn.esm and its script.

usage:
  python make_player_furn.py precheck [--content-resources <zip>] [--out <precheck.json>]
      read only, no game: every native the script needs, and each optional line's name, looked up in Starfield's base sources
      (Scripts/Source of ContentResources.zip; inheritance followed), and whether RegisterForAnimationEvent declares a return.
      Exit 1 when a required one is missing.
  python make_player_furn.py stage --out <dir> [--starfield <Starfield.esm>] [--compiler <exe>] [--content-resources <zip>]
      1. dotnet/PlayerFurn build + check against the Starfield.esm given (offline_check.txt; refuses when one of the four vanilla
         FURN is not there under its editor id);
      2. the Papyrus compile: each optional line (";OPT <Base.Name> ") whose name the base sources declare is compiled on its own,
         the ones that compile are kept (the event handlers included), every other one is reported in plan.json ("optional"); then
         the script itself, with the register call in the shape the base scripts declare (bool return, or ";VOID " lines);
      3. plan.json (SHA-256 of every file and of Starfield.esm) and README.txt. Built in a new <out>.partial-<time>-<pid> and
         renamed to <out> only when every step passed; an existing <out> is refused.
There is no log reader: the readout is the on-screen "PF " notices (script logging is off on the PC) and, when logging is on, the
user log FO4SFPFurn.0.log, read by eye against the card.
Nothing here installs anything: scripts/newgame/player_furn_install.py does, on the owner's word, game closed.
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
from make_workshop_probe import compile_text, enable, optional_names, read_sources, sha256  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "PlayerFurn")
PLUGIN = "FO4SFPlayerFurn.esm"
SCRIPT = "FO4SF_PlayerFurnQuest"
PSC = os.path.join(HERE, SCRIPT + ".psc")
STARFIELD = r"D:\SteamLibrary\steamapps\common\Starfield"
KIND = "player-furn-probe"
# what the script cannot run without (the optional lines are the .psc's ";OPT" lines)
REQUIRED = {
    "Actor": ["PlaceAtMe", "GetPositionX", "GetPositionY", "GetPositionZ", "GetDistance", "GetAngleZ", "GetSitState"],
    "ObjectReference": ["Activate", "Is3DLoaded", "IsDisabled", "Disable", "GetBaseObject"],
    "Math": ["Sin", "Cos"],
    "Game": ["GetPlayer", "GetFormFromFile", "IsPluginInstalled"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
    "Utility": ["GetCurrentRealTime"],
    "Quest": ["GetStageDone"],
    "ScriptObject": ["StartTimer", "RegisterForAnimationEvent", "RegisterForRemoteEvent"],
    "Form": ["GetFormID"],
    "InputEnableLayer": ["Create", "DisablePlayerControls", "EnablePlayerControls", "Delete"],
}
VOID = re.compile(r"^;VOID ", re.M)
BOOL_LINE = '    return "" + RegisterForAnimationEvent(r, n)\n'
REG_DECL = re.compile(r"^\s*(?:(?P<ret>[\w:\[\]]+)\s+)?Function\s+RegisterForAnimationEvent\s*\(", re.I | re.M)


def register_returns_bool(sources):
    """True / False from the declaration of RegisterForAnimationEvent in the base sources (the first one found); None when none."""
    for text in sources.values():
        m = REG_DECL.search(text)
        if m:
            return (m.group("ret") or "").lower() == "bool"
    return None


def reg_shape(text, returns_bool):
    """The script's text with the register call in the shape the game declares: unchanged for a bool return, else the bool
    return line dropped and the ";VOID " lines kept."""
    if returns_bool is not False:
        return text
    if BOOL_LINE not in text:
        sys.exit("the script has no bool-return register line to replace (the .psc and make_player_furn.py disagree)")
    return VOID.sub("", text.replace(BOOL_LINE, "", 1))


def precheck_sources(sources, text):
    """{"required": {"Base.Name": bool}, "optional": {"Base.Name": bool}, "missing": [...], "register_returns_bool": bool or None}."""
    req = {f"{b}.{f}": declares(sources, b, f) for b, fs in REQUIRED.items() for f in fs}
    opt = {n: declares(sources, *n.split(".")) for n in optional_names(text)}
    return {"required": req, "optional": opt, "missing": [k for k, ok in req.items() if not ok],
            "register_returns_bool": register_returns_bool(sources)}


def precheck(a):
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    r = precheck_sources(read_sources(a.content_resources), text)
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
    if plan.get("kind") != KIND or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the player-furniture kit's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
        sys.exit(f"{path} missing: stage with make_player_furn.py first")
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
    wrote = run(tool + ["build", a.starfield, out]).stdout
    check = run(tool + ["check", os.path.join(out, PLUGIN), a.starfield]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    with open(PSC, encoding="utf-8") as f:
        text = f.read()
    sources = read_sources(a.content_resources)
    src = extract_sources(a.content_resources, work)
    pre = precheck_sources(sources, text)
    if pre["missing"]:
        sys.exit(f"the base scripts do not declare {pre['missing']}: do not stage (attempt kept in {out})")
    text = reg_shape(text, pre["register_returns_bool"])
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
            "optional": fate, "register_returns_bool": pre["register_returns_bool"],
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFPFurn.0.log"}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Player-furniture control kit, variant P ({datetime.date.today().isoformat()}). docs/research/player-furniture-kit.md
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): QUST FO4SF_PlayerFurnQuest (start game enabled; stages 10..13 spawn the vanilla FURN PowerCycle,
COM_Quest_Andreja_Q01_SecretPanel, NPCIDCardReader, Scenes_MQ101_HellerTechReaderPickUp one by one in front of the player; stages 20..23 put the
player into one (guard timer, input layer, Activate(player)) with 15 s of timed logging; 40 reading; 60 cleanup). Master Starfield.esm only; adds
one record, overrides none; no FURN, no REFR, no cell. Checked against Starfield.esm {before}. Re-stage after a game update.
Optional lines: {', '.join(f'{k}: {v}' for k, v in fate.items()) or 'none'}. RegisterForAnimationEvent returns bool: {pre['register_returns_bool']}.
Install (the owner's word, game closed; loose scripts are not read, the installer packs them into a ba2):
  python scripts\\newgame\\player_furn_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\newgame\\player_furn_install.py uninstall --starfield <game dir>
Readout: the on-screen "PF " notices; the user log (when script logging is on) is FO4SFPFurn.0.log.
Session card: docs/research/player-furniture-kit.md. THROWAWAY STATE ONLY, NO SAVE (the spawned references are persistent and would stay in it).
""")

    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {SCRIPT}.pex, offline_check.txt, plan.json, README.txt; optional lines: {fate}")
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
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
