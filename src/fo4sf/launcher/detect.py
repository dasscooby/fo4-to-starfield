"""detect: can this PC build the port? The launcher's first stage (research/next-phase launcher-architecture.md §2),
read only.

    Fallout 4   Fallout4.esm present and its hash in the known-sources table (unknown versions are refused unless
                allow_unknown: Wabbajack and TTW refuse sources they cannot match); the six DLC masters, missing ones
                named (the port assumes all six, so a missing DLC is a refusal unless allow_missing_dlc)
    Starfield   Starfield.exe and Data present; Archive2 present (packing needs it: required); Creation Kit presence
                reported (required only if asked). Runtime gate (owner, 2026-10-19: LA-15, LA-16, NG-1, RE-12):
                Starfield.exe must be listed in the known-runtimes table, SFSE must be installed and be the SFSE
                build listed for that runtime, and a Microsoft Store / Game Pass folder is refused (Steam only)
    INIs        any sTestFileN in Starfield.ini, the language INIs the game ships, StarfieldPrefs.ini or
                StarfieldCustom.ini (game folder and My Games) is a refusal: the game then ignores Plugins.txt. The game
                folder holds Starfield_de, _es, _fr, _it, _ja, _pl, _ptbr and _zhhans.ini (verified: the owner's
                1.16.244 install, 29 Oct 2026; English has none). That the game reads sTestFile in them is a hypothesis
                (sfstack.md question 18 lists them): reading them only refuses more
    My Games    loose files in its Data folder are reported (the game reads them over archives); the folder is given
                as Windows resolves it, never guessed (OneDrive and redirected Documents move it). An omitted or
                unavailable folder warns that its INIs were not checked; READY does not clear unchecked INIs.
    Disk        free space on the output drive, minus the floor that must stay free (40 GB on the owner's D:), against
                the space the build needs

The known-sources table (scripts/launcher_recipes/known_sources.json) maps master hashes to a version label. Entries
come from a real install's build manifest (`launcher.py sources-add --manifest <build manifest>`), never made up.
"""
import os
import re
import shutil

from . import files
from . import manifest as mf
from . import runtimes as rt

DEFAULT_FLOOR_GB = 40.0
INI_NAMES = ("Starfield.ini", "StarfieldPrefs.ini", "StarfieldCustom.ini")
LANGUAGE_INIS = tuple(f"Starfield_{x}.ini" for x in ("de", "es", "fr", "it", "ja", "pl", "ptbr", "zhhans"))
_TEST_FILE = re.compile(r"^\s*(sTestFile\d+)\s*=\s*(\S.*?)\s*$", re.IGNORECASE)


def load_sources(path):
    if not path or not os.path.isfile(path):
        return {"schema": 1, "sources": []}
    return files.load_json(path)


def add_sources(table, man, label):
    """Entries for every master in a build manifest, under one label. Returns the number added (duplicates skipped)."""
    have = {(s["file"].casefold(), s["sha256"]) for s in table["sources"]}
    n = 0
    for name, m in sorted(((man.get("fo4") or {}).get("masters") or {}).items()):
        if not m.get("sha256"):
            continue
        key = (name.casefold(), m["sha256"])
        if key not in have:
            table["sources"].append({"file": name, "sha256": m["sha256"], "size": m.get("size"), "label": label})
            have.add(key)
            n += 1
    return n


def match_source(table, name, sha):
    for s in table["sources"]:
        if s["file"].casefold() == name.casefold() and s["sha256"] == sha:
            return s["label"]
    return None


# folders a build must not run in (Wabbajack and GAMMA refuse the same, appeng §6-7): protected or synced by Windows,
# or a drive root
PROTECTED_PARTS = ("program files", "program files (x86)", "windows", "programdata")


def work_folder_problems(path):
    """[problems] with a build output folder, read from its path alone (Windows or POSIX spelling)."""
    raw = os.path.abspath(path) if not re.match(r"^[A-Za-z]:[\\/]", path) else path
    parts = [p for p in re.split(r"[\\/]+", raw) if p]
    low = [p.casefold() for p in parts]
    out = []
    if len(parts) <= 1:
        out.append(f"{path} is a drive root; use a folder such as D:\\Modding\\FO4SF")
    if any(p in PROTECTED_PARTS for p in low):
        out.append(f"{path} is under a protected Windows folder (Program Files, Windows, ProgramData)")
    if any(p == "onedrive" or p.startswith("onedrive - ") for p in low):
        out.append(f"{path} is under OneDrive, which syncs and locks files while the build writes them")
    if len(low) > 1 and re.match(r"^[a-z]:$", low[0]) and low[1] == "users":
        out.append(f"{path} is under the Users folder (Documents and Desktop are guarded by Controlled Folder Access)")
    return out


def free_gb(path):
    probe = os.path.abspath(path)
    while not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return shutil.disk_usage(probe).free / 2 ** 30


def ini_test_files(folders):
    """[(ini path, line number, key, value)] for every non-empty sTestFileN in Starfield's INIs under the folders.
    Any one makes the game ignore Plugins.txt (MO2 and Vortex both say so), so our plugins would silently not load."""
    hits = []
    for folder in folders:
        for name in INI_NAMES + LANGUAGE_INIS:
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for n, line in enumerate(f, 1):
                    m = _TEST_FILE.match(line)
                    if m:
                        hits.append((path, n, m.group(1), m.group(2)))
    return hits


def loose_data(my_games):
    """Files in Documents\\My Games\\Starfield\\Data (the second Data folder the game reads), relative paths sorted."""
    root = os.path.join(my_games, "Data")
    out = []
    for d, _dirs, names in os.walk(root):
        for name in names:
            out.append(os.path.relpath(os.path.join(d, name), root).replace(os.sep, "/"))
    return sorted(out)


def detect(*, fo4_data, starfield, sources=None, out_dir=None, need_gb=0.0, floor_gb=DEFAULT_FLOOR_GB,
           allow_unknown=False, allow_missing_dlc=False, require_ck=False, require_sfse=True, my_games=None,
           runtimes=None, allow_unknown_runtime=False):
    """{"ready": bool, "refusals": [...], "warnings": [...], "fo4": {...}, "game": {...}, "disk": {...}}."""
    refusals, warnings = [], []
    table = sources if isinstance(sources, dict) else load_sources(sources)
    out = {"fo4": None, "game": None, "disk": None}
    # one folder named twice (in another case, or with a trailing separator, as a lower-case Steam library path in
    # libraryfolders.vdf gives on Windows) is read once: otherwise every archive in it is "found 2 times" (PC, 2026-10-22)
    seen, folders = set(), []
    for d in fo4_data:
        key = os.path.normcase(os.path.normpath(d))
        if key not in seen:
            seen.add(key)
            folders.append(d)
    try:
        fo4 = mf.fo4_inputs(folders)
    except FileNotFoundError as e:
        refusals.append(f"Fallout 4: {e}")
        fo4 = None
    if fo4:
        versions = {}
        for name, m in fo4["masters"].items():
            label = match_source(table, name, m["sha256"])
            versions[name] = label
            if label is None:
                (warnings if allow_unknown else refusals).append(
                    f"Fallout 4: {name} (sha256 {m['sha256'][:12]}...) is not a known version")
        if fo4["dlc_missing"]:
            (warnings if allow_missing_dlc else refusals).append("DLC missing: " + ", ".join(fo4["dlc_missing"]))
        ba2_versions = {}
        for a in fo4["archives"].values():
            ba2_versions[str(a["ba2_version"])] = ba2_versions.get(str(a["ba2_version"]), 0) + 1
        if set(ba2_versions) - {"1"}:
            warnings.append("Fallout 4: archive header versions " + ", ".join(
                f"v{v} x{n}" for v, n in sorted(ba2_versions.items())) + " (v7 and v8 come from the 2024 next-gen "
                "update or later; the converter is tested on v1 data)")
        for name, paths in sorted(fo4["archive_duplicates"].items()):
            warnings.append(f"Fallout 4: {name} found {len(paths)} times; using {paths[-1]}")
        out["fo4"] = {"masters": {n: {"sha256": m["sha256"], "size": m["size"], "version": versions[n]}
                                  for n, m in fo4["masters"].items()},
                      "dlc_missing": fo4["dlc_missing"], "archives": len(fo4["archives"]),
                      "ba2_versions": ba2_versions, "archive_duplicates": fo4["archive_duplicates"]}
    if starfield and os.path.isdir(starfield):
        g = mf.game_pins(starfield)
        f = g["files"]
        if f.get("Starfield.exe") is None:
            refusals.append("Starfield: Starfield.exe not found")
        if not os.path.isdir(os.path.join(starfield, "Data")):
            refusals.append("Starfield: no Data folder")
        if f.get("Tools/Archive2/Archive2.exe") is None:
            refusals.append("Starfield: Archive2 not found (Tools\\Archive2, installed with the free Creation Kit)")
        if not g["creation_kit"]:
            (refusals if require_ck else warnings).append("Starfield: Creation Kit not installed")
        if not g["sfse"]:
            if require_sfse:
                refusals.append("Starfield: SFSE not installed (required)")
            else:
                warnings.append("Starfield: SFSE not installed")
        if rt.store_install(starfield):
            refusals.append("Starfield: this looks like a Microsoft Store / Game Pass install; version 1 supports "
                            "Steam Starfield only (SFSE does not run on the Store build)")
        exe_sha = (f.get("Starfield.exe") or {}).get("sha256")
        table_rt = runtimes if isinstance(runtimes, dict) else rt.load_runtimes(runtimes)
        known = rt.match_runtime(table_rt, exe_sha)
        if exe_sha and known is None:
            (warnings if allow_unknown_runtime else refusals).append(
                f"Starfield: this Starfield.exe (sha256 {exe_sha[:12]}...) is not listed as a good runtime yet; "
                "keep Steam set to update Starfield only when launched until support is published")
        elif known is not None and g["sfse"]:
            for p in rt.sfse_problems(known, g):
                (refusals if require_sfse else warnings).append(f"Starfield: SFSE: {p}")
        refusals += [f"Starfield: native: {p}" for p in rt.native_problems(known, starfield)]
        out["game"] = {"sfse": g["sfse"], "creation_kit": g["creation_kit"],
                       "archive2": f.get("Tools/Archive2/Archive2.exe") is not None,
                       "exe_sha256": exe_sha, "runtime": None if known is None else known["label"],
                       "sfse_dlls": sorted(g["sfse_dlls"])}
    else:
        refusals.append(f"Starfield: folder {starfield!r} not found")
    ini_folders = [starfield] if starfield and os.path.isdir(starfield) else []
    if my_games:
        if os.path.isdir(my_games):
            ini_folders.append(my_games)
            loose = loose_data(my_games)
            out["my_games"] = {"path": os.path.abspath(my_games), "loose_files": len(loose), "loose_sample": loose[:20]}
            if loose:
                warnings.append(f"Starfield: {len(loose)} loose files in {os.path.join(my_games, 'Data')} "
                                "(the game reads them over archives; they are not ours and restore leaves them)")
        else:
            warnings.append(f"Starfield: My Games folder {my_games!r} not found; INIs in My Games not checked")
    else:
        warnings.append("Starfield: INIs in My Games not checked (pass --my-games with the resolved folder)")
    for path, n, key, value in ini_test_files(ini_folders):
        refusals.append(f"Starfield: {key}={value} in {path} line {n} makes the game ignore Plugins.txt")
    if out_dir:
        for p in work_folder_problems(out_dir):
            refusals.append("Work folder: " + p)
        free = free_gb(out_dir)
        usable = free - floor_gb
        out["disk"] = {"path": os.path.abspath(out_dir), "free_gb": round(free, 1), "floor_gb": floor_gb,
                       "need_gb": need_gb, "usable_gb": round(usable, 1)}
        if usable < need_gb:
            refusals.append(f"Disk: {free:.1f} GB free on {out_dir}, {floor_gb:g} GB must stay free, the build needs "
                            f"{need_gb:g} GB")
    out.update(ready=not refusals, refusals=refusals, warnings=warnings)
    return out


def measure(root):
    """Disk use of a folder counting each hard-linked file once: {"files", "bytes_listed", "bytes_unique",
    "bytes_shared", "frees_if_deleted"}. bytes_shared is the part of bytes_unique in files that also have links
    outside this folder (their space stays held elsewhere), so deleting the folder frees bytes_unique - bytes_shared."""
    inodes, listed, n = {}, 0, 0
    for d, _dirs, names in os.walk(root):
        for name in names:
            st = os.stat(os.path.join(d, name))
            n += 1
            listed += st.st_size
            key = (st.st_dev, st.st_ino) if st.st_ino else ("path", os.path.join(d, name))
            if key in inodes:
                inodes[key][2] += 1
            else:
                inodes[key] = [st.st_size, st.st_nlink, 1]
    unique = sum(v[0] for v in inodes.values())
    shared = sum(v[0] for v in inodes.values() if v[1] > v[2])
    return {"files": n, "bytes_listed": listed, "bytes_unique": unique, "bytes_shared": shared,
            "frees_if_deleted": unique - shared}
