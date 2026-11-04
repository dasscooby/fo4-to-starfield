"""Stage FO4SFCombinedProbe.esm: the probe plugin of the combined core's engine questions P2 to P10
(docs/spikes/combined-core-probes.md; research/framework/combined-core-notes/engine-feasibility.md "PC probes").

usage:
  python scripts/combined_probes/make_combined_probe.py stage --core <installed FO4TerrainCore.esm> --out <NEW folder>
        --stat <plugin:hexid> --lvln-b <plugin:hexid> [--npc Starfield.esm:2B211C] [--lvln-a Starfield.esm:2B211C]
        [--starfield <game dir>] [--sf <Starfield.esm>] [--compiler <PapyrusCompiler.exe>] [--content-resources <zip>]
        [--world FO4Core_Commonwealth] [--location FO4Core_CommonwealthLocation]
        [--p3-cells --port <installed FO4Port.esm>] [--skip lvln,sm]
      1. dotnet/CombinedProbe build: the plugin (records in the header of dotnet/CombinedProbe/Program.cs);
      2. the Papyrus compile of FOCC_ProbeQuest.psc, FOCC_Probe.psc and FOCC_P10Quest.psc (base sources from the
         Creation Kit's ContentResources.zip, the IMPORTS below, as scripts/bridge/make_bridge.py), the .pex files into
         <out>/Data/Scripts; a compile that fails stops the stage: for P2 (Location.SetKeywordData and friends) and
         P10 (Keyword.SendStoryEvent) a failure is itself the finding, so the compiler's output is in the error;
      3. the separate, allowed-to-fail compile of FOCC_P5_Array129.psc (the 128-entry array cap, P5): the compiler's
         full output goes to compile_p5_array129.txt and its .pex, if any, stays in work/ and is never packed;
         and of FOCC_P9Drive.psc (P9's scripted driver, Actor.PathToReference): compile_p9_drive.txt, and its .pex
         joins Data/Scripts (packed) only when it compiled; and of FOCC.psc with FOCC_B0.psc (B0, the plugin bridge:
         the native stub and its console entry points): compile_b0.txt, both .pex packed only when both compiled;
      4. dotnet/CombinedProbe check: the plugin read back against the masters (offline_check.txt, with the build output);
      5. the .psc sources beside the stage, plan.json (sha256 of every input and output, the build id, the variant,
         the skips, the compile results), README.txt.
Install (game closed), after the core it was built from: python scripts/combined_probes/probe_install.py install --dir <out> --starfield <game>
The plugin names the core's location and world by FormID, so it is rebuilt with every core build (check refuses a
plugin built against another core). Nothing of the game enters the repo: the stage is a NEW folder under the staging root.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts", "bridge"))
import make_bridge  # noqa: E402  (run, the default tool paths)

PLUGIN = "FO4SFCombinedProbe.esm"
LOG = "<My Games>/Starfield/Logs/Script/User/focc.0.log"
# the base scripts the probe scripts use (make_bridge.IMPORTS is a module constant, so this is its own superset:
# Keyword for Holder / Route / P10Event and SendStoryEvent; Form for the list and base properties). ActorBase and
# LeveledActor are not needed: the scripts declare those properties as Form (PlaceAtMe takes a Form). Alias and
# ReferenceAlias for P9's package driver (FOCC_P9Drive.Travel: the probe quest's alias 0).
IMPORTS = ("Actor", "Alias", "Cell", "Debug", "Form", "Game", "GlobalVariable", "Keyword", "Location", "ObjectReference", "Package",
           "Quest", "ReferenceAlias", "ScriptObject", "Utility", "WorldSpace")
PACKED = ("FOCC_ProbeQuest", "FOCC_Probe", "FOCC_P10Quest")       # compiled into Data/Scripts and packed
COMPILE_ONLY = "FOCC_P5_Array129"                                  # compiled on its own; its result is the finding
DRIVE = "FOCC_P9Drive"                                             # compiled on its own; packed only when it compiles
B0 = ("FOCC", "FOCC_B0")                                           # B0's native stub, then its entry points; packed only when both compile
ENTRY_POINTS = ("Hello", "P2Set", "P2Link", "P2Read", "P2LinkRead", "P3Set", "P3Read", "Where", "P4Run", "P5Tick", "P6",
                "P7", "P8Move", "P8Stage", "P9Dest", "P9Track", "P10Send", "P10State")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_sources(zip_path, work, imports=IMPORTS):
    """The base .psc files the probe scripts import, and the flags file, from ContentResources.zip into work/Source
    (make_bridge.extract_sources with this module's IMPORTS)."""
    want = {f"Scripts/Source/{n}.psc" for n in imports} | {"Scripts/Source/Starfield_Papyrus_Flags.flg"}
    src = os.path.join(work, "Source")
    os.makedirs(src, exist_ok=True)
    got = set()
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name in want:
                with z.open(name) as f, open(os.path.join(src, os.path.basename(name)), "wb") as o:
                    shutil.copyfileobj(f, o)
                got.add(name)
    missing = sorted(want - got)
    if missing:
        sys.exit(f"ContentResources.zip lacks {missing}")
    return src


def sources():
    """Every .psc of this folder, sorted (the three packed scripts, the compile-only one, P9's driver and B0's two)."""
    return sorted(f for f in os.listdir(HERE) if f.lower().endswith(".psc"))


def compile_cmd(compiler, name, src_dir, out_dir):
    return [compiler, name + ".psc", "-f=Starfield_Papyrus_Flags.flg", f"-i={HERE};{src_dir}", f"-o={out_dir}"]


def compile_packed(compiler, src_dir, out_dir):
    """PapyrusCompiler.exe on each packed script by its bare name from this folder (the compiler compares the file
    name with the Scriptname and rejects a path); a script that does not compile stops the stage. Returns the .pex paths."""
    os.makedirs(out_dir, exist_ok=True)
    pexes = []
    for name in PACKED:
        out = make_bridge.run(compile_cmd(compiler, name, src_dir, out_dir), cwd=HERE)
        pex = os.path.join(out_dir, name + ".pex")
        if "Compilation succeeded" not in out or not os.path.exists(pex):
            sys.exit(f"the Papyrus compile did not produce {name}.pex (P2's Location functions or P10's SendStoryEvent "
                     f"missing in Starfield's base scripts is itself a finding: keep the output above)")
        pexes.append(pex)
    return pexes


def run_capture(cmd, cwd=None):
    """A command whose failure is a result, not an error: returns (exit code, stdout + stderr)."""
    print("+ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def compile_array129(compiler, src_dir, work, out):
    """The compile-only cap test: FOCC_P5_Array129.psc (new float[129]) compiled into work/p5, the full compiler
    output and verdict written to <out>/compile_p5_array129.txt. Returns the plan entry."""
    p5_out = os.path.join(work, "p5")
    os.makedirs(p5_out, exist_ok=True)
    code, text = run_capture(compile_cmd(compiler, COMPILE_ONLY, src_dir, p5_out), cwd=HERE)
    pex = os.path.join(p5_out, COMPILE_ONLY + ".pex")
    compiled = code == 0 and "Compilation succeeded" in text and os.path.exists(pex)
    verdict = ("compiled: no compile-time cap at 129 entries" if compiled
               else "refused: the compiler did not accept new float[129] (see the output above)")
    with open(os.path.join(out, "compile_p5_array129.txt"), "w", encoding="utf-8") as f:
        f.write(f"{COMPILE_ONLY}.psc: new float[129] (compile-only, never packed)\nexit code {code}\n{text}\n{verdict}\n")
    return {"script": COMPILE_ONLY, "compiled": compiled, "exit_code": code, "output": "compile_p5_array129.txt"}


def compile_apart(compiler, src_dir, work, out, sub, names):
    """Scripts compiled on their own, in order, into work/<sub>: a refusal of any one stops the group (its output is the
    finding) and nothing of the group is packed; all compiled, every .pex is copied into <out>/Data/Scripts. Returns
    (exit code, the compiler output of every script run, the packed .pex paths or None)."""
    sub_out = os.path.join(work, sub)
    os.makedirs(sub_out, exist_ok=True)
    texts, pexes = [], []
    for name in names:
        code, text = run_capture(compile_cmd(compiler, name, src_dir, sub_out), cwd=HERE)
        texts.append(f"--- {name}.psc\nexit code {code}\n{text}")
        pex = os.path.join(sub_out, name + ".pex")
        if not (code == 0 and "Compilation succeeded" in text and os.path.exists(pex)):
            return code, "\n".join(texts), None
        pexes.append(pex)
    packed = []
    for pex in pexes:
        dst = os.path.join(out, "Data", "Scripts", os.path.basename(pex))
        shutil.copyfile(pex, dst)
        packed.append(dst)
    return 0, "\n".join(texts), packed


def compile_drive(compiler, src_dir, work, out):
    """P9's scripted driver, FOCC_P9Drive.psc (Actor.PathToReference from Papyrus), compiled on its own into work/p9: a
    Starfield Actor.psc without that function, or with another signature, refuses only this script, and the stage goes
    on without it. Compiled, its .pex joins <out>/Data/Scripts and is packed. The compiler's output and the verdict go to
    <out>/compile_p9_drive.txt. Returns (the plan entry, the packed .pex path or None)."""
    code, text, packed = compile_apart(compiler, src_dir, work, out, "p9", (DRIVE,))
    verdict = ("compiled: Actor.PathToReference(ObjectReference, float, float) is callable from Papyrus; packed" if packed
               else "refused: this stage has no P9 scripted driver (see the output above); the other probes are unaffected")
    with open(os.path.join(out, "compile_p9_drive.txt"), "w", encoding="utf-8") as f:
        f.write(f"{DRIVE}.psc: Actor.PathToReference from Papyrus (P9's scripted driver)\n{text}\n{verdict}\n")
    return {"script": DRIVE, "compiled": bool(packed), "exit_code": code, "output": "compile_p9_drive.txt"}, (packed or [None])[0]


def compile_b0(compiler, src_dir, work, out):
    """B0's two scripts (docs/combined-core-cpp-port.md section 4): FOCC.psc, the native stub the SFSE plugin binds, then
    FOCC_B0.psc, its console entry points (Game.GetGameSettingInt and FOCC.Ping), compiled on their own into work/b0 and
    packed only when both compiled, so a refusal leaves only B0 out of the stage. The output and the verdict go to
    <out>/compile_b0.txt. Returns (the plan entry, the packed .pex paths)."""
    code, text, packed = compile_apart(compiler, src_dir, work, out, "b0", B0)
    verdict = ("compiled: FOCC.Ping is declared and FOCC_B0 calls it and Game.GetGameSettingInt; both packed" if packed
               else "refused: this stage has no B0 scripts (see the output above); the probes are unaffected")
    with open(os.path.join(out, "compile_b0.txt"), "w", encoding="utf-8") as f:
        f.write(f"{' and '.join(n + '.psc' for n in B0)}: B0's plugin bridge (native stub and entry points)\n{text}\n{verdict}\n")
    return {"scripts": list(B0), "compiled": bool(packed), "exit_code": code, "output": "compile_b0.txt"}, (packed or [])


def stage(a):
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"{out} is not empty: stage into a new folder")
    os.makedirs(out, exist_ok=True)
    work = os.path.join(out, "work")
    sf = a.sf or os.path.join(a.starfield, "Data", "Starfield.esm")
    tool = os.path.join(REPO, "dotnet", "CombinedProbe")
    opts = ["--sf", sf, "--core", a.core, "--stat", a.stat, "--npc", a.npc, "--lvln-a", a.lvln_a, "--plugin", PLUGIN,
            "--world", a.world, "--location", a.location]
    if a.lvln_b:
        opts += ["--lvln-b", a.lvln_b]
    if a.skip:
        opts += ["--skip", a.skip]
    if a.p3_cells:
        if not a.port:
            sys.exit("--p3-cells needs --port <installed FO4Port.esm>")
        opts += ["--p3-cells", "--port", a.port]
    built = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "build", "--out", out] + opts)
    src = extract_sources(a.content_resources, work)
    pexes = compile_packed(a.compiler, src, os.path.join(out, "Data", "Scripts"))
    array129 = compile_array129(a.compiler, src, work, out)
    drive, drive_pex = compile_drive(a.compiler, src, work, out)
    if drive_pex:
        pexes.append(drive_pex)
    b0, b0_pexes = compile_b0(a.compiler, src, work, out)
    pexes += b0_pexes
    check = make_bridge.run(["dotnet", "run", "-c", "Release", "--project", tool, "--", "check", os.path.join(out, PLUGIN)] + opts)
    with open(os.path.join(out, "offline_check.txt"), "w", encoding="utf-8") as f:
        f.write(built + check)
    for name in sources():                                 # the source of every .pex, beside the stage
        shutil.copy(os.path.join(HERE, name), os.path.join(out, name))
    plugin_path = os.path.join(out, PLUGIN)
    plugin_sha = sha256(plugin_path)
    inputs = {"core": {"path": os.path.abspath(a.core), "sha256": sha256(a.core)},
              "starfield_esm": {"path": os.path.abspath(sf), "sha256": sha256(sf) if os.path.exists(sf) else None},
              "compiler": {"path": os.path.abspath(a.compiler), "sha256": sha256(a.compiler) if os.path.exists(a.compiler) else None},
              "content_resources": {"path": os.path.abspath(a.content_resources),
                                    "sha256": sha256(a.content_resources) if os.path.exists(a.content_resources) else None},
              "sources": {n: sha256(os.path.join(HERE, n)) for n in sources()}}
    if a.p3_cells:
        inputs["port"] = {"path": os.path.abspath(a.port), "sha256": sha256(a.port)}
    outputs = {PLUGIN: plugin_sha}
    for pex in pexes:
        outputs[os.path.relpath(pex, out).replace("\\", "/")] = sha256(pex)
    variant = "p3cells" if a.p3_cells else "default"
    skips = sorted({s.strip() for s in a.skip.split(",") if s.strip()})
    plan = {"kind": "combined-probe", "plugin": PLUGIN, "build_id": plugin_sha[:8], "plugin_sha256": plugin_sha,
            "variant": variant, "skip": skips, "world": a.world, "location": a.location,
            # the judge's blocked flags (probes.check_p6 / p7 / p10 and the runbook): a skipped group was never built
            "lvln_conditions_written": "lvln" not in skips, "sm_nodes_written": "sm" not in skips,
            "bases": {"npc": a.npc, "lvln_a": a.lvln_a, "lvln_b": a.lvln_b or None, "stat": a.stat},
            "scripts": {"quest": PACKED[0], "console": PACKED[1], "p10": PACKED[2],
                        "p9_drive": DRIVE if drive_pex else None, "b0": B0[1] if b0_pexes else None},
            "entry_points": list(ENTRY_POINTS),
            "log": LOG, "log_prefix": "FOCC rt=", "imports": list(IMPORTS),
            "ids": {"quest": 0x804, "p2_loc": 0x806, "p3_no_parent": 0x807, "p3_chained": 0x808, "p10_quest": 0x820},
            "inputs": inputs, "outputs": outputs, "array129": array129, "p9_drive": drive, "b0": b0,
            "sendstoryevent_compiles": True,                     # FOCC_Probe.psc (which calls it) compiled, or the stage stopped
            "offline_check": "offline_check.txt"}   # no date: same inputs, same bytes (CONTRIBUTING.md)
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    scripts = ", ".join(f"Data\\Scripts\\{n}.pex" for n in PACKED + ((DRIVE,) if drive_pex else ()) + (B0 if b0_pexes else ()))
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(f"""Combined core engine probes P2 to P10 (Claude-cloud). docs/spikes/combined-core-probes.md.
{PLUGIN} (build {plugin_sha[:8]}, variant {variant}{', skip ' + a.skip if a.skip else ''}): the records listed in dotnet/CombinedProbe/Program.cs,
  built against {os.path.abspath(a.core)} (its {a.location} and {a.world} by FormID: rebuild with every core build).
{scripts}: compiled from the .psc files here. compile_p5_array129.txt: the array-cap compile (never packed).
compile_p9_drive.txt: P9's scripted driver ({'compiled and packed' if drive_pex else 'refused, not packed: no scripted P9'}).
compile_b0.txt: B0's bridge scripts FOCC and FOCC_B0 ({'compiled and packed' if b0_pexes else 'refused, not packed: no B0'}); cgf "FOCC_B0.Gmst" needs no SFSE plugin.
Install (game closed), after the core, one probe plugin at a time, never beside FO4SFMission.esm (both override the core's persistent cell):
  python scripts\\combined_probes\\probe_install.py install --dir "{out}" --starfield <game>
In game, after loading a save: cgf "FOCC_Probe.Hello" then the probe's commands (FOCC_Probe.psc lists them); every answer is a line
  FOCC rt=<s> <probe> <event> key=value ...   in {LOG}
Collect the log into D:\\Modding\\testqueue\\focc_<probe>_<date>\\ and judge: python -m fo4sf.combined.probes <pN> --collect <folder>
Uninstall (game closed) before any core swap or another experiment: python scripts\\combined_probes\\probe_install.py uninstall --starfield <game>
""")
    print(f"staged {out}: {PLUGIN} ({plugin_sha[:8]}), {', '.join(os.path.relpath(p, out) for p in pexes)}, "
          f"compile_p5_array129.txt ({'compiled' if array129['compiled'] else 'refused'}), "
          f"compile_p9_drive.txt ({'compiled, packed' if drive_pex else 'refused'}), "
          f"compile_b0.txt ({'compiled, packed' if b0_pexes else 'refused'}), offline_check.txt, plan.json, README.txt")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stage")
    s.add_argument("--core", required=True, help="the installed FO4TerrainCore.esm the plugin is built against")
    s.add_argument("--out", required=True, help="a NEW folder under the staging root")
    s.add_argument("--stat", required=True, help="a visible vanilla STAT for the P8 children, <plugin>:<hexid> (job card)")
    s.add_argument("--lvln-b", default="", help="the second vanilla NPC_ of the P6 / P7 lists, <plugin>:<hexid> (job card); or --skip lvln")
    s.add_argument("--npc", default="Starfield.esm:2B211C", help="the NPC_ P4 places (the test sheet's citizen)")
    s.add_argument("--lvln-a", default="Starfield.esm:2B211C")
    s.add_argument("--starfield", default=make_bridge.STARFIELD, help="the game folder (Starfield.esm, compiler and zip defaults)")
    s.add_argument("--sf", default="", help="Starfield.esm (default <starfield>\\Data\\Starfield.esm)")
    s.add_argument("--compiler", default="", help="default <starfield>\\Tools\\Papyrus Compiler\\PapyrusCompiler.exe")
    s.add_argument("--content-resources", default="", help="default <starfield>\\Tools\\ContentResources.zip")
    s.add_argument("--world", default="FO4Core_Commonwealth")
    s.add_argument("--location", default="FO4Core_CommonwealthLocation")
    s.add_argument("--p3-cells", action="store_true", help="the P3 cell variant: CELL overrides of FO4Port.esm's two interiors")
    s.add_argument("--port", default="", help="the installed FO4Port.esm (with --p3-cells)")
    s.add_argument("--skip", default="", help="lvln,sm: leave out the records whose Mutagen API failed to build")
    a = ap.parse_args(argv)
    if a.cmd == "stage":                        # tool defaults follow the chosen game folder, not make_bridge's
        a.compiler = a.compiler or os.path.join(a.starfield, "Tools", "Papyrus Compiler", "PapyrusCompiler.exe")
        a.content_resources = a.content_resources or os.path.join(a.starfield, "Tools", "ContentResources.zip")
    if a.cmd == "stage":
        if not a.lvln_b and "lvln" not in a.skip.split(","):
            sys.exit("--lvln-b <plugin:hexid> is required (a second vanilla NPC_ picked in xSFEdit), or --skip lvln")
        stage(a)


if __name__ == "__main__":
    main()
