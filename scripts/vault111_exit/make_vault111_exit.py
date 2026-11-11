"""Stage the Vault 111 exit kit (docs/newgame/vault111-exit-kit.md; FAL-461): FO4SFVault111Exit.esm and its three compiled scripts.

usage:
  python make_vault111_exit.py precheck [--content-resources <zip>]
      read only: every native the three scripts call, looked up in Starfield's base sources. Exit 1 when one is missing.
  python make_vault111_exit.py stage --out <dir> [--params <params.json>] [--starfield <Starfield.esm>] [--port <FO4Port.esm>]
                                     [--compiler ..] [--content-resources ..]
      1. dotnet/Vault111Exit build + check against the Starfield.esm and FO4Port.esm given (offline_check.txt);
      2. the Papyrus compile of the three scripts (Data/Scripts/*.pex);
      3. plan.json (SHA-256 of every file and of both inputs) and README.txt. Built in a new <out>.partial-<time>-<pid> and
         renamed to <out> only when every step passed; an existing <out> is refused.
  python make_vault111_exit.py log [--file <FO4SFV111.0.log>]
      the run's user log and a verdict (exit 0 when the pickup, the plug-in and the door opening all show).
Nothing here installs anything: scripts/vault111_exit/vault111_exit_install.py does, on the owner's word, game closed.
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
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts", "newgame"))
sys.path.insert(0, os.path.join(REPO, "scripts", "planet"))
from make_newgame import declares, extract_sources, new_partial, run  # noqa: E402
import make_workshop_probe as wp  # noqa: E402

PROJECT = os.path.join(REPO, "dotnet", "Vault111Exit")
PLUGIN = "FO4SFVault111Exit.esm"
SCRIPTS = ("FO4SF_V111Exit", "FO4SF_V111PipBoyPickup", "FO4SF_V111DoorTerminal")
PARAMS = os.path.join(HERE, "params.json")
STARFIELD = wp.STARFIELD
PORT_NAME = "FO4Port.esm"
LOG = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Starfield", "Logs", "Script", "User", "FO4SFV111.0.log")
REQUIRED = {
    "Game": ["GetFormFromFile", "GetPlayer"],
    "Debug": ["OpenUserLog", "TraceUser", "Notification"],
    "ObjectReference": ["GetItemCount", "AddItem", "SetOpen", "GetOpenState", "Disable"],
    "Quest": ["SetStage", "GetStageDone"],
}
# what the log must show, in order, for a full run
LOG_STEPS = (("pickup", "pickup: taken, stage 10"), ("plug", "terminal: plugged in, stage 20"), ("open", "terminal: cog door open_state"))


def tool(args, **kw):
    return run(["dotnet", "run", "-c", "Release", "--project", PROJECT, "--"] + args, **kw)


def script_text(name):
    with open(os.path.join(HERE, name + ".psc"), encoding="utf-8") as f:
        return f.read()


def called_natives(text):
    """{(Base, name)} of the Game / Debug calls a script's code makes (comments and {doc} left out)."""
    code = re.sub(r"\{[^}]*\}", "", "\n".join(l for l in text.splitlines() if not l.strip().startswith(";")), flags=re.S)
    return set(re.findall(r"\b(Game|Debug)\.(\w+)\(", code))


def missing_natives(sources):
    return [f"{b}.{n}" for b, ns in REQUIRED.items() for n in ns if not declares(sources, b, n)]


def precheck(a):
    sources = wp.read_sources(a.content_resources)
    missing = missing_natives(sources)
    print("precheck: " + ("ok" if not missing else f"{len(missing)} required name(s) missing: {missing}; do not stage"))
    return 0 if not missing else 1


def stage_files(out):
    files = {}
    for name in sorted(os.listdir(out)):
        if name.lower().endswith(".esm"):
            files[name] = wp.sha256(os.path.join(out, name))
    for root, dirs, names in os.walk(os.path.join(out, "Data")):
        dirs.sort()
        for n in sorted(names):
            p = os.path.join(root, n)
            files[os.path.relpath(p, out).replace(os.sep, "/")] = wp.sha256(p)
    return files


def verify_stage(stage_dir, plan, data=None):
    """Problems of a stage ([] = none): its files against plan.json and, with the game's Data folder, its two inputs."""
    if plan.get("kind") != "vault111-exit" or plan.get("plugins") != [PLUGIN]:
        return [f"plan.json is not the Vault 111 exit kit's (kind {plan.get('kind')!r}, plugins {plan.get('plugins')})"]
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
    for n in SCRIPTS:
        if f"Data/Scripts/{n}.pex" not in plan["outputs"]:
            problems.append(f"Data/Scripts/{n}.pex is not in plan.json")
    if data is not None:
        for key, name in (("Starfield.esm", "Starfield.esm"), ("FO4Port.esm", PORT_NAME)):
            p = os.path.join(data, name)
            if not os.path.isfile(p):
                problems.append(f"no {name} in {data}: name the game's Data folder (the install: the game folder)")
            elif wp.sha256(p) != plan["inputs"][key]["sha256"]:
                problems.append(f"{name} changed since the stage: re-stage (the models and the cell were read from it)")
    return problems


def load_plan(stage_dir):
    path = os.path.join(stage_dir, "plan.json")
    if not os.path.isfile(path):
        sys.exit(f"{path} missing: stage with make_vault111_exit.py first")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage(a):
    final = os.path.abspath(a.out)
    if os.path.exists(final):
        sys.exit(f"{final} exists: stage into a new folder (an earlier stage is never overwritten)")
    sf_before, port_before = wp.sha256(a.starfield), wp.sha256(a.port)
    out = new_partial(final)
    work = os.path.join(out, "work")
    os.makedirs(work)
    wrote = tool(["build", a.params, a.starfield, a.port, out]).stdout
    check = tool(["check", os.path.join(out, PLUGIN), a.params, a.starfield, a.port]).stdout
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(wrote + check)
    src = extract_sources(a.content_resources, work)
    missing = missing_natives(wp.read_sources(a.content_resources))
    if missing:
        sys.exit(f"the base scripts do not declare {missing}: do not stage (attempt kept in {out})")
    scripts = os.path.join(out, "Data", "Scripts")
    for n in SCRIPTS:
        ok, err = wp.compile_text(a.compiler, script_text(n), src, scripts, n)
        if not ok:
            sys.exit(f"the Papyrus compile of {n}.psc failed: {err} (attempt kept in {out})")
    shutil.rmtree(work)
    if wp.sha256(a.starfield) != sf_before or wp.sha256(a.port) != port_before:
        sys.exit(f"Starfield.esm or {PORT_NAME} changed during the build, nothing published; attempt kept in {out}")
    shutil.copy(a.params, os.path.join(out, "params.json"))
    plan = {"kind": "vault111-exit", "version": 1, "plugins": [PLUGIN], "outputs": None,
            "inputs": {"Starfield.esm": {"sha256": sf_before}, "FO4Port.esm": {"sha256": port_before}},
            "log": "<My Games>/Starfield/Logs/Script/User/FO4SFV111.0.log"}
    plan["outputs"] = {k: v for k, v in stage_files(out).items()}
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Vault 111 exit kit, steps 1-3 ({datetime.date.today().isoformat()}). docs/newgame/vault111-exit-kit.md, FAL-461.
{PLUGIN} (sha256 {plan['outputs'][PLUGIN]}): a quest with stages 5 10 20 30, a token item, an activator over the Pip-Boy on the
skeleton and one over the door control, both as temporary references in an override of FO4Port_Vault111Cryo. Masters
Starfield.esm and {PORT_NAME}. Checked against Starfield.esm {sf_before} and {PORT_NAME} {port_before}. Re-stage after either changes.
Install (the owner's word, game closed; loose scripts are not read, the installer packs them into a ba2):
  python scripts\\\\vault111_exit\\\\vault111_exit_install.py install --dir <this folder> --starfield <game dir>
Remove:  python scripts\\\\vault111_exit\\\\vault111_exit_install.py uninstall --starfield <game dir>
Read:    python scripts\\\\vault111_exit\\\\make_vault111_exit.py log
Play: load a save that is already in Vault 111's start room (NOT a new game: the new-game quest opens the cog door itself when
the player stands at the console during its own start). Pick up the Pip-Boy, use the door control twice.
THROWAWAY STATE ONLY, NO SAVE.
""")
    os.replace(out, final)
    print(f"staged {final}: {PLUGIN}, {len(SCRIPTS)} .pex, offline_check.txt, params.json, plan.json, README.txt")
    return 0


def read_log(lines):
    """{step: bool} for LOG_STEPS, each shown after the one before it."""
    seen, pos = {}, 0
    for key, text in LOG_STEPS:
        hit = next((i for i in range(pos, len(lines)) if text in lines[i]), None)
        seen[key] = hit is not None
        if hit is not None:
            pos = hit + 1
    return seen


def log(a):
    if not os.path.isfile(a.file):
        print(f"no log at {a.file}")
        return 2
    with open(a.file, encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n") for l in f if "FO4SFV111" in l or "pickup:" in l or "terminal:" in l]
    seen = read_log(lines)
    denied = any("terminal: no Pip-Boy" in l for l in lines)
    print("\n".join(lines[-40:]))
    print("verdict: " + ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in seen.items()) + f"; denied_without_pipboy={'yes' if denied else 'no'}")
    return 0 if all(seen.values()) else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    cr = os.path.join(STARFIELD, "Tools", "ContentResources.zip")
    pc = sub.add_parser("precheck")
    pc.add_argument("--content-resources", default=cr)
    s = sub.add_parser("stage")
    s.add_argument("--out", required=True)
    s.add_argument("--params", default=PARAMS)
    s.add_argument("--starfield", default=os.path.join(STARFIELD, "Data", "Starfield.esm"))
    s.add_argument("--port", default=os.path.join(STARFIELD, "Data", PORT_NAME))
    s.add_argument("--compiler", default=os.path.join(STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=cr)
    g = sub.add_parser("log")
    g.add_argument("--file", default=LOG)
    a = p.parse_args(argv)
    return {"precheck": precheck, "stage": stage, "log": log}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
