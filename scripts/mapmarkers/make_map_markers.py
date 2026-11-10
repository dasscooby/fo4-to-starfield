"""Stage FO4SFMapMarkers.esm: the quest that puts the core's map markers into the merged world the player walks in
(docs/terrain/map-markers.md "Markers in the merged world").

usage:
  python scripts/mapmarkers/make_map_markers.py stage --core <FO4TerrainCore.esm> --out <NEW folder>
                                                     [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>]
                                                     [--z-lift <m>] [--world control|nosmall|city]
                                                     [--fo4-map-markers <export.json>] [--landing <x> <y>]
                                                     [--landing-name <name>] [--core-stage <folder>]
                                                     [--star-map <name> ... | --star-map-all] [--no-reload]
      0. with --fo4-map-markers (the owner's "more location markers", 2026-10-23): the rest of FO4's named
         Commonwealth markers, picked as make_core64c.py stage --fo4-map-markers picks them for a core
         (fo4sf.map_markers.load_fo4_markers and extra_markers: 200 m inside the land, none on a same-named fixed or
         kept marker within 100 m), z the core's BTD ground, into <out>/extra_markers.json (the left out with their
         reason in map_markers_left_out.json). --core-stage is the folder that staged the core: its overlays_params.json
         (bounds, the BTD path, the fixed markers) and its BTD; its copy of the core must be --core, byte for byte;
         with --landing (the owner's "temp ship landing spot", 2026-10-23): a pad at getpos (x, y), the merged frame
         the game and the owner's snapshots report, and LandingOverlay01's trigger, "Landing Area" marker and heading
         around it (fo4sf.map_markers.landing_spot, heights from the same BTD), into <out>/landing.json;
      1. dotnet/MapMarkers build: the plugin (one start-game-enabled quest carrying FO4SF_MapMarkers, its Markers the
         core's MapMarker REFRs, LocalX / LocalY / LocalZ their positions as overridden below), plus an override of
         each of those REFRs: the marker's own name on the map (no UseLocationName flag) and the arrival lifted
         --z-lift metres (a multiple of 0.1; default the tool's 2.5) above the core's sampled terrain height; the
         override's containers, copies of the core's WRLD and persistent CELL, override the core's records too, so a
         stage belongs to one core build (check fails a stale one), and --world takes the WRLD copy from
         dotnet/BorderProbe's variants (the border settling test): control as the core's, nosmall without
         SmallWorld, city without SmallWorld and HNAM 5; with step 0, --extra adds those markers as this plugin's
         own REFRs, with one LCSR row each in an override of the core's Location, after the core's in the quests,
         and --landing adds the landing spot's four REFRs and its three LCSR rows, after those in the quests;
         --star-map (<out>/star_map.json, the owner's pick A, 2026-10-28) keeps "Visible on Star Map" on the named
         markers only (default STAR_MAP: the core's four and a few major places; not strict, so a stage without
         those markers still builds), so Mars's planet view lists those and the landing area under its one icon,
         while the surface map keeps every marker; names given here are strict (each must name a marker);
         --star-map-all leaves every marker on the star map, as before; --reload (unless --no-reload) adds the
         reload's stop, a small interior of the plugin's own whose marker the first quest's HopMarker names: the map
         lists only the markers in a world when the player enters it, so once every marker is in place the first quest
         takes the player there and back once, behind a black screen (the owner's Cydonia trip, 2026-10-31);
      2. the Papyrus compile of FO4SF_MapMarkers.psc (base sources from the Creation Kit's ContentResources.zip, as
         scripts/bridge/make_bridge.py), the .pex into <out>/Data/Scripts;
      3. dotnet/MapMarkers check: the plugin read back against the core (offline_check.txt); core.json (the core's
         sha256, which the installer requires in Data); README.txt.
Install (game closed), with the core it was built from active (its own record, beside exp_install's experiment):
  python scripts/game/map_markers_install.py install --dir <out> --starfield <game>
The plugin names the core's references by FormID, so it is rebuilt with every core build.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "bridge"))
import make_bridge  # noqa: E402  (run, extract_sources, the default tool paths)

SCRIPT = "FO4SF_MapMarkers"
LOG = "<My Games>/Starfield/Logs/Script/User/fo4sf_map.0.log"


def compile_script(compiler, src_dir, out_dir):
    """PapyrusCompiler.exe on FO4SF_MapMarkers.psc by its bare name from this folder; returns the .pex path."""
    os.makedirs(out_dir, exist_ok=True)
    name = SCRIPT + ".psc"
    out = make_bridge.run([compiler, name, "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"],
                          cwd=HERE)
    pex = os.path.join(out_dir, SCRIPT + ".pex")
    if "Compilation succeeded" not in out or not os.path.exists(pex):
        sys.exit(f"the Papyrus compile did not produce {SCRIPT}.pex")
    return pex


PLUGIN = "FO4SFMapMarkers.esm"   # the one name scripts/game/map_markers_install.py installs
DEFAULT_Z_LIFT = 2.5             # dotnet/MapMarkers DefaultZLift: the landing heading's lift when --z-lift is not given
# the markers Mars's planet view lists under the Commonwealth's one icon (the owner's pick A, 2026-10-28: "go with a"):
# the core's four and a few major places of FO4's export (Diamond City and Goodneighbor have no marker in it); the
# landing marker is always on it (dotnet/MapMarkers LandingMarkerFlags 0x33)
STAR_MAP = ("Red Rocket Truck Stop", "Sanctuary Hills", "Vault 111", "Concord",
            "Lexington", "The Castle", "Vault 81", "Bunker Hill")
PIN = "core.json"                # {"masters": {core file name: sha256}}: the core this plugin's FormIDs belong to
WORLDS = {"control": ", as the core's record (SmallWorld kept, HNAM the core's)",
          "nosmall": " (dotnet/BorderProbe's: SmallWorld cleared, HNAM the core's)",
          "city": " (dotnet/BorderProbe's: SmallWorld cleared, HNAM 5)"}


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def core_terrain(core_stage, core_sha256, core_name):
    """The core's own stage: (its one overlay's params, ground(x, y) from its BTD), local metres."""
    sys.path.insert(0, os.path.join(REPO, "src"))
    sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))
    import make_core64c                                  # Terrain: the BTD reader the core's own stage samples with
    staged_core = os.path.join(core_stage, core_name)
    if not os.path.isfile(staged_core) or sha256(staged_core) != core_sha256:
        sys.exit(f"--core-stage {core_stage}: its {core_name} is not --core (another build): the BTD and params must be "
                 "the ones this core was built from")
    with open(os.path.join(core_stage, "overlays_params.json"), encoding="utf-8-sig") as f:
        overlays = json.load(f).get("overlays") or []
    if len(overlays) != 1:
        sys.exit(f"--core-stage {core_stage}: overlays_params.json has {len(overlays)} overlays, want the one core world")
    ov = overlays[0]
    terrain = make_core64c.Terrain(os.path.join(core_stage, *ov["btd_file"].split("/")))
    return ov, lambda x, y: float(terrain.bilinear([x], [y])[0])


def fo4_extra(export, core_stage, ov, ground, out):
    """Step 0: the markers --extra adds, written to <out>/extra_markers.json; returns (its path, kept, left out)."""
    sys.path.insert(0, os.path.join(REPO, "src"))
    from fo4sf import map_markers
    fixed = ov.get("map_markers") or []
    with open(export, encoding="utf-8-sig") as f:
        doc = json.load(f)
    try:
        rows, left = map_markers.load_fo4_markers(doc)
    except ValueError as e:
        sys.exit(f"--fo4-map-markers {export}: {e}")
    built = {m["tag"] for m in fixed} & {r[0] for r in rows}             # M<FO4 id>, as the core's stage tags them
    if built:
        sys.exit(f"the core already has {len(built)} of these markers ({sorted(built)[0]}, ...): it was built with "
                 "--fo4-map-markers, so the plugin needs no extra ones")
    extra, outside = map_markers.extra_markers(rows, (ov["bounds_min_m"], ov["bounds_max_m"]), ground, fixed=fixed)
    path = os.path.join(out, "extra_markers.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"source": os.path.abspath(export), "core_stage": os.path.abspath(core_stage),
                   "btd": ov["btd_file"], "markers": extra}, f, indent=1)
    with open(os.path.join(out, "map_markers_left_out.json"), "w", encoding="utf-8") as f:
        json.dump({"left_out": left + outside}, f, indent=1)
    return path, len(extra), len(left) + len(outside)


def landing(at, name, core_stage, ov, ground, lift, out):
    """Step 0: the landing spot --landing adds, its pad at getpos `at`, written to <out>/landing.json; returns
    (its path, the spot)."""
    sys.path.insert(0, os.path.join(REPO, "src"))
    sys.path.insert(0, os.path.join(REPO, "scripts", "terrain"))
    from fo4sf import map_markers
    import vmad_patch                                    # MERGE_MEASURED: getpos = local + the merge offset
    ox, oy, _ = vmad_patch.MERGE_MEASURED
    try:
        spot = map_markers.landing_spot(at[0] - ox, at[1] - oy, (ov["bounds_min_m"], ov["bounds_max_m"]), ground, lift,
                                        name=name)
    except ValueError as e:
        sys.exit(f"--landing {at[0]} {at[1]}: {e}")
    path = os.path.join(out, "landing.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"getpos": list(at), "merge_offset": [ox, oy], "core_stage": os.path.abspath(core_stage), "btd": ov["btd_file"],
                   "landing": spot}, f, indent=1)
    return path, spot


def stage(a):
    a.plugin = PLUGIN
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"{out} is not empty: stage into a new folder")
    if bool(a.fo4_map_markers or a.landing) != bool(a.core_stage):
        sys.exit("--core-stage goes with --fo4-map-markers or --landing (the core's own stage folder, for its BTD)")
    names = [] if a.star_map_all else list(a.star_map) if a.star_map else list(STAR_MAP)
    if len(set(names)) != len(names) or not all(names):              # before anything is written, so a retry can reuse --out
        sys.exit(f"--star-map {names}: names must be non-empty and not repeat")
    core_sha256 = sha256(a.core)                         # the installer refuses any other core build
    os.makedirs(out, exist_ok=True)
    tool = os.path.join(REPO, "dotnet", "MapMarkers")
    lift = [] if a.z_lift is None else ["--z-lift", repr(float(a.z_lift))]
    lift += [] if a.world == "control" else ["--world", a.world]      # build and check take the same variant
    extra_note = ""
    if a.core_stage:
        ov, ground = core_terrain(a.core_stage, core_sha256, os.path.basename(a.core))
    if a.fo4_map_markers:
        path, kept, dropped = fo4_extra(a.fo4_map_markers, a.core_stage, ov, ground, out)
        with open(path, encoding="utf-8") as f:
            from fo4sf import map_markers      # fo4_extra put src on sys.path
            icons = map_markers.format_type_counts(json.load(f)["markers"])
        lift += ["--extra", path]                                     # build and check take the same markers
        extra_note = (f"\n  Plus {kept} markers of its own (extra_markers.json, from {os.path.abspath(a.fo4_map_markers)}; "
                      f"{dropped} left out, map_markers_left_out.json),\n  each with an LCSR row in its override of the core's Location.\n  Icon types (from the FO4 type table, src/fo4sf/map_marker_types.json):\n" + icons)
    if a.landing:
        path, spot = landing(a.landing, a.landing_name, a.core_stage, ov, ground, DEFAULT_Z_LIFT if a.z_lift is None else a.z_lift, out)
        lift += ["--landing", path]                                   # build and check take the same spot
        pad = spot["pad"]["pos"]
        extra_note += (f"\n  Plus a ship landing spot \"{spot['name']}\" (landing.json): a pad at getpos {a.landing[0]} {a.landing[1]} "
                       f"(local {pad[0]} {pad[1]}, z {pad[2]}),\n  its landing zone, map marker and heading as LandingOverlay01 "
                       "places them, and its three LCSR rows.")
    if not a.no_reload:
        lift += ["--reload"]                                          # build and check take the same stop
        extra_note += ("\n  Plus the reload's stop FO4SF_MapMarkersHop, a small interior: once every marker is in place"
                       "\n  and some went in after the player came, the first quest takes them there and back once, the screen black,"
                       "\n  so the map lists the markers (offline_check.txt: reload stop, HopMarker).")
    if not a.star_map_all:
        path = os.path.join(out, "star_map.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"names": names, "strict": bool(a.star_map)}, f, indent=1)
        lift += ["--star-map", path]                                  # build and check take the same names
        extra_note += (f"\n  Visible on Star Map (star_map.json) only for those of {', '.join(names)} the plugin has"
                       + (", and the landing marker" if a.landing else "") + " (offline_check.txt: star map);"
                       "\n  every marker stays on the surface map.")
    built = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "build", "--core", a.core,
                             "--out", out, "--plugin", a.plugin] + lift)
    src = make_bridge.extract_sources(a.content_resources, os.path.join(out, "work"))
    pex = compile_script(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    check = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "check",
                             os.path.join(out, a.plugin), a.core] + lift)
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(built + check)
    with open(os.path.join(out, PIN), "w", encoding="utf-8") as f:
        json.dump({"masters": {os.path.basename(a.core): core_sha256}}, f, indent=1)
    shutil.copy(os.path.join(HERE, SCRIPT + ".psc"), os.path.join(out, SCRIPT + ".psc"))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Map markers into the merged world (Claude-cloud, {datetime.date.today().isoformat()}). docs/terrain/map-markers.md.
{a.plugin}: QUST FO4SF_MapMarkersQuest (0x800, start game enabled) carrying {SCRIPT}, built against
  {os.path.abspath(a.core)} (its MapMarker REFRs by FormID: rebuild with every core build), and an override of
  each of those REFRs: the marker's own name on the map, the arrival lifted {'the tool\'s default 2.5' if a.z_lift is None else a.z_lift} m.{extra_note}
  Its WRLD copy (an override too, loading after the core's): --world {a.world}{WORLDS[a.world]}.
  {PIN} pins that core's sha256: the installer refuses a Data folder holding any other build of it.
Data\\Scripts\\{SCRIPT}.pex: compiled from {SCRIPT}.psc here.
Install (game closed), with the core active (its own record, beside exp_install's experiment; packs the .pex):
  python scripts\\game\\map_markers_install.py install --dir "{out}" --starfield <game>
In game: outdoors in the Commonwealth the log {LOG} gets one line per marker moved:
  FO4SF_MAP rt=<s> q=<quest, 2048 for 0x800> moved <i> to <x> <y> <z> target <x> <y> <z> before=<distance> off=<dx> <dy> <dz> d=<distance> moves=<n>
  then from the first quest (q=2048) "fast travel, all <n> quests' markers in place or out of moves, ...", and with the stop
  "reload 1: out to ...", "reload 1: at the stop=True ...", "reload 1 back: ... same=True", "fast travel, after reload 1: ...";
  after an arrival the screen stays black from "dark hold: ..." to "dark hold ends with the reload after <s> s".
Then open the map. Uninstall: map_markers_install.py uninstall --starfield <game>. Uninstall it before a core swap
  and install it again after (its only master, the core, leaves Plugins.txt during the swap).
""")
    print(f"staged {out}: {a.plugin}, {os.path.relpath(pex, out)}, {PIN}, offline_check.txt, README.txt"
          + (", extra_markers.json, map_markers_left_out.json" if a.fo4_map_markers else "")
          + (", landing.json" if a.landing else "") + ("" if a.star_map_all else ", star_map.json"))


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--core", required=True, help="the FO4TerrainCore.esm the plugin is installed with")
    s.add_argument("--out", required=True)
    s.add_argument("--compiler", default=os.path.join(make_bridge.STARFIELD, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe"))
    s.add_argument("--content-resources", default=os.path.join(make_bridge.STARFIELD, "Tools", "ContentResources.zip"))
    s.add_argument("--z-lift", type=float, default=None,
                   help="metres the override lifts each marker above the core's height, a multiple of 0.1 (default: the tool's 2.5)")
    s.add_argument("--world", choices=sorted(WORLDS), default="control",
                   help="the plugin's WRLD copy: the core's record (control) or dotnet/BorderProbe's nosmall / city variant of it")
    s.add_argument("--fo4-map-markers", default="",
                   help="a Fo4Land export-mapmarkers json (Commonwealth): add the rest of FO4's named markers as the plugin's own")
    s.add_argument("--landing", type=float, nargs=2, metavar=("X", "Y"), default=None,
                   help="a temporary ship landing spot: the pad at this getpos x, y (the merged frame)")
    s.add_argument("--landing-name", default="Commonwealth Landing Area", help="the landing spot's name on the map")
    s.add_argument("--core-stage", default="",
                   help="with --fo4-map-markers or --landing: the folder that staged --core (overlays_params.json and the BTD)")
    star = s.add_mutually_exclusive_group()
    star.add_argument("--star-map", nargs="+", metavar="NAME", default=None,
                      help="the markers Mars's planet view lists (default: STAR_MAP); each must name a marker")
    star.add_argument("--star-map-all", action="store_true", help="leave every marker on the star map (as before)")
    s.add_argument("--no-reload", action="store_true",
                   help="leave out the reload's stop: the markers then show on the map only after the player leaves the world and comes back")
    a = ap.parse_args(argv)
    stage(a)


if __name__ == "__main__":
    main()
