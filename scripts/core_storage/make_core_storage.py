"""Stage FO4SFCoreStorage.esm: the core storage probe (FAL-208; dotnet/CoreStorage, scripts/core_storage/FO4SF_CoreStorageQuest.psc).

usage:
  python scripts/core_storage/make_core_storage.py stage --core <installed FO4TerrainCore.esm> --out <NEW folder>
        [--starfield <game dir>] [--sf <Starfield.esm>] [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>]
        [--variant topcell|full|persist-only|temp-only|cell-only|world-only]
      1. dotnet/CoreStorage build: the plugin (a persistent XMarker in an override of the core world's persistent cell and a
         temporary one in the core's FO4Core_RedRocketSpawn; --variant full is run 3's layout, persistent group under the cell,
         a quest with no properties);
      2. the Papyrus compile of FO4SF_CoreStorageQuest.psc (base sources from the Creation Kit's ContentResources.zip, as
         scripts/bridge/make_bridge.py), the .pex into <out>/Data/Scripts;
      3. dotnet/CoreStorage check against the same core and Starfield.esm (offline_check.txt, with the build output);
      4. the .psc beside the stage, plan.json (sha256 of every input and output), README.txt.
Install (game closed), after the core: python scripts/core_storage/core_storage_install.py install --dir <out> --starfield <game>
The plugin is built from the installed core (its spawn cell, its COC marker's position): rebuild with every core build.
Nothing of the game enters the repo: the stage is a NEW folder under the staging root.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "bridge"))

PLUGIN = "FO4SFCoreStorage.esm"
SCRIPT = "FO4SF_CoreStorageQuest"
LOG = "<My Games>/Starfield/Logs/Script/User/FO4SFCoreStorage.0.log"
PREFIX = "FO4SFCS rt="
SPAWN_CELL = "FO4Core_RedRocketSpawn"
IDS = {"cs_p": 0x800, "cs_t": 0x801, "quest": 0x802}
IMPORTS = ("Actor", "Cell", "Debug", "Form", "Game", "ObjectReference", "Quest", "ScriptObject", "Utility", "WorldSpace")
TOOL = os.path.join(REPO, "dotnet", "CoreStorage")
VARIANTS = ("topcell", "full", "persist-only", "temp-only", "cell-only", "world-only")     # dotnet/CoreStorage --variant (FAL-273, #707)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tool_cmd(*argv):
    return ["dotnet", "run", "-c", "Release", "--project", TOOL, "--", *argv]


def stage(a):
    import make_bridge  # noqa: E402  (run, the default tool paths)
    import zipfile
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"{out} is not empty: stage into a new folder")
    os.makedirs(out, exist_ok=True)
    work = os.path.join(out, "work")
    sf = a.sf or os.path.join(a.starfield, "Data", "Starfield.esm")
    compiler = a.compiler or os.path.join(a.starfield, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe")
    zip_path = a.content_resources or os.path.join(a.starfield, "Tools", "ContentResources.zip")
    built = make_bridge.run(tool_cmd("build", "--sf", sf, "--core", a.core, "--out", out, "--plugin", PLUGIN, "--variant", a.variant))
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    want = {f"Scripts/Source/{n}.psc" for n in IMPORTS} | {"Scripts/Source/Starfield_Papyrus_Flags.flg"}
    got = set()
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name in want:
                with z.open(name) as f, open(os.path.join(src, os.path.basename(name)), "wb") as o:
                    shutil.copyfileobj(f, o)
                got.add(name)
    if want - got:
        sys.exit(f"ContentResources.zip lacks {sorted(want - got)}")
    pex_dir = os.path.join(out, "Data", "Scripts")
    os.makedirs(pex_dir, exist_ok=True)
    text = make_bridge.run([compiler, SCRIPT + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src}", f"-o={pex_dir}"], cwd=HERE)
    pex = os.path.join(pex_dir, SCRIPT + ".pex")
    if "Compilation succeeded" not in text or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile did not produce {SCRIPT}.pex")
    check = make_bridge.run(tool_cmd("check", os.path.join(out, PLUGIN), "--sf", sf, "--core", a.core, "--variant", a.variant))
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(built + check)
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))
    plugin_sha = sha256(os.path.join(out, PLUGIN))
    plan = {"kind": "core-storage-probe", "plugin": PLUGIN, "plugins": [PLUGIN], "build_id": plugin_sha[:8],
            "plugin_sha256": plugin_sha, "variant": a.variant, "spawn_cell": SPAWN_CELL, "script": SCRIPT, "ids": IDS,
            "log": LOG, "log_prefix": PREFIX, "readings_s": [2, 10, 30, 60],
            "inputs": {"core": {"sha256": sha256(a.core)},
                       "starfield_esm": {"sha256": sha256(sf) if os.path.exists(sf) else None},
                       "source": {SCRIPT + ".psc": sha256(os.path.join(HERE, SCRIPT + ".psc"))}},
            "outputs": {PLUGIN: plugin_sha, f"Data/Scripts/{SCRIPT}.pex": sha256(pex)},
            "offline_check": "offline_check.txt"}      # no date: same inputs, same bytes (CONTRIBUTING.md)
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Core storage probe (FAL-208), variant {a.variant}. {PLUGIN} (build {plugin_sha[:8]}), masters Starfield.esm + FO4TerrainCore.esm.
FO4SF_CS_P (0x800, persistent; variant {a.variant}: world persistent cell for topcell) and FO4SF_CS_T (0x801, temporary, in {SPAWN_CELL}): XMarkers at its COC marker + 4 / 8 m east.
Install (game closed), after the core: python scripts\\core_storage\\core_storage_install.py install --dir "{out}" --starfield <game>
In game: coc {SPAWN_CELL} with the roofs on screen; stay 75 s; the user log {LOG} holds FO4SFCS lines 2, 10, 30 and 60 s
after the arrival. CS_T not found: cell not loaded (not a failure). CS_T found and CS_P with the player: PASS.
CS_T found and CS_P left behind or not found: FAIL.
Uninstall (game closed): python scripts\\core_storage\\core_storage_install.py uninstall --starfield <game>
""")
    print(f"staged {out}: {PLUGIN} ({plugin_sha[:8]}), Data/Scripts/{SCRIPT}.pex, offline_check.txt, plan.json, README.txt")


def verify_stage(d):
    """Problems of a staged folder against its own plan.json (empty: it matches)."""
    plan_p = os.path.join(d, "plan.json")
    if not os.path.exists(plan_p):
        return None, [f"{plan_p} missing (scripts/core_storage/make_core_storage.py stage)"]
    with open(plan_p, encoding="utf-8") as f:
        plan = json.load(f)
    if plan.get("kind") != "core-storage-probe" or plan.get("plugin") != PLUGIN:
        return plan, [f"{plan_p} is not a core-storage-probe stage of {PLUGIN}"]
    problems = []
    for rel, want in (plan.get("outputs") or {}).items():
        path = os.path.join(d, rel.replace("/", os.sep))
        if not os.path.exists(path):
            problems.append(f"{rel} missing")
        elif sha256(path) != want:
            problems.append(f"{rel} does not match plan.json")
    if PLUGIN not in (plan.get("outputs") or {}):
        problems.append(f"plan.json does not pin {PLUGIN}")
    return plan, problems


def core_pin_problems(plan, data_dir):
    """Problems with the core the stage was built against (plan.json inputs.core.sha256) against the one installed in
    data_dir: the plugin names the core's cell and marker position, so another core, a missing one or a plan
    without the pin is refused (FAL-211)."""
    want = ((plan.get("inputs") or {}).get("core") or {}).get("sha256")
    if not want:
        return ["plan.json does not pin the core it was built against"]
    path = os.path.join(data_dir, "FO4TerrainCore.esm")
    if not os.path.exists(path):
        return [f"{path} is not installed (the plugin masters it)"]
    if sha256(path) != want:
        return ["the installed FO4TerrainCore.esm is not the core this stage was built against (re-stage)"]
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--core", required=True, help="the installed FO4TerrainCore.esm the plugin is built against")
    s.add_argument("--out", required=True, help="a NEW folder under the staging root")
    s.add_argument("--starfield", default=r"D:\SteamLibrary\steamapps\common\Starfield", help="the game folder")
    s.add_argument("--sf", default="", help="Starfield.esm (default <starfield>\\Data\\Starfield.esm)")
    s.add_argument("--compiler", default="", help="default <starfield>\\Tools\\Papyrus Compiler\\PapyrusCompiler.exe")
    s.add_argument("--content-resources", default="", help="default <starfield>\\Tools\\ContentResources.zip")
    s.add_argument("--variant", default="topcell", choices=VARIANTS,
                   help="which part of the override is written (the crash of #707: one game run per variant)")
    a = ap.parse_args(argv)
    stage(a)


if __name__ == "__main__":
    main()
