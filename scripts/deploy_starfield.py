"""Install / uninstall converted files into a Starfield install for testing (reversible).

install  : packs <staging>/{meshes,geometries,materials,textures} into "FO4Port - Main.ba2" with the official Archive2
           (shipped with the Starfield Creation Kit), copies it and FO4Port.esm into Starfield\\Data, and enables the plugin
           in %LOCALAPPDATA%\\Starfield\\Plugins.txt. Starfield loads a plugin's "<name> - Main.ba2" automatically, so no
           ini change is needed. It refuses to overwrite existing files; everything it adds is recorded in
           Data/FO4Port.deploy.json.
uninstall: removes exactly what the manifest lists, including the Plugins.txt line.

usage: python deploy_starfield.py install|uninstall --staging <dir> --starfield <game dir> [--dry-run]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

PLUGIN = "FO4Port.esm"
ARCHIVE = "FO4Port - Main.ba2"
MANIFEST = "FO4Port.deploy.json"
ASSET_DIRS = ("meshes", "geometries", "materials", "textures")


def plugins_txt_path():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), "Starfield", "Plugins.txt")


def read_lines(p):
    return open(p, encoding="utf-8").read().splitlines() if os.path.exists(p) else []


def write_lines(p, lines):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))


def build_archive(a, out):
    tool = os.path.join(a.starfield, "Tools", "Archive2", "Archive2.exe")
    if not os.path.exists(tool):
        sys.exit(f"Archive2 not found at {tool} (install the Starfield Creation Kit)")
    folders = [d for d in ASSET_DIRS if os.path.isdir(os.path.join(a.staging, d))]
    if not folders:
        sys.exit("nothing to archive: no meshes/geometries/materials/textures in staging")
    r = subprocess.run([tool, ",".join(folders), f"-create={out}", f"-root={a.staging}", "-format=General",
                        "-compression=Default"], cwd=a.staging, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        sys.exit("Archive2 failed:\n" + r.stdout + r.stderr)


def install(a):
    data = os.path.join(a.starfield, "Data")
    man_path = os.path.join(data, MANIFEST)
    if os.path.exists(man_path):
        sys.exit("already installed (manifest exists); uninstall first")
    esm = next((p for p in (os.path.join(a.staging, "Data", PLUGIN), os.path.join(a.staging, PLUGIN)) if os.path.exists(p)), None)
    if not esm:
        sys.exit(f"{PLUGIN} not found in staging")
    targets = [os.path.join(data, PLUGIN), os.path.join(data, ARCHIVE)]
    clash = [t for t in targets if os.path.exists(t)]
    if clash:
        sys.exit("refusing to overwrite existing files:\n  " + "\n  ".join(clash))
    pt = plugins_txt_path()
    pl = read_lines(pt)
    pl_add = [] if f"*{PLUGIN}" in pl or PLUGIN in pl else [f"*{PLUGIN}"]
    print(f"install: {PLUGIN} + {ARCHIVE} -> {data}\nPlugins.txt ({pt}): add {pl_add or 'nothing'}")
    if a.dry_run:
        return
    built = os.path.join(a.staging, ARCHIVE)
    build_archive(a, built)
    shutil.copy2(esm, targets[0])
    shutil.copy2(built, targets[1])
    if pl_add:
        write_lines(pt, pl + pl_add)
    json.dump({"files": [PLUGIN, ARCHIVE], "plugins_txt": pt, "plugins_added": pl_add}, open(man_path, "w"), indent=1)
    print("installed. Undo with: python deploy_starfield.py uninstall --starfield <game dir>")


def uninstall(a):
    data = os.path.join(a.starfield, "Data")
    man_path = os.path.join(data, MANIFEST)
    if not os.path.exists(man_path):
        sys.exit("nothing to uninstall (no manifest)")
    m = json.load(open(man_path))
    print(f"removing {m['files']} and Plugins.txt entries {m['plugins_added']}")
    if a.dry_run:
        return
    for rel in m["files"]:
        p = os.path.join(data, rel)
        if os.path.exists(p):
            os.remove(p)
    if m["plugins_added"]:
        pl = [l for l in read_lines(m["plugins_txt"]) if l not in m["plugins_added"]]
        if pl:
            write_lines(m["plugins_txt"], pl)
        elif os.path.exists(m["plugins_txt"]):
            os.remove(m["plugins_txt"])
    os.remove(man_path)
    print("uninstalled")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["install", "uninstall"])
    ap.add_argument("--staging", default="")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    (install if args.action == "install" else uninstall)(args)
