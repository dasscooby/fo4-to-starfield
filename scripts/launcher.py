r"""Launcher backbone CLI (docs/ai/launcher-backbone.md). Offline except `restore --apply`.

    python scripts/launcher.py manifest --out <manifest.json> [--fo4-data <dir> ...] [--starfield <game dir>]
                                        [--output <build dir or file> ...] [--hash-archives] [--hash-limit-mb N]
    python scripts/launcher.py manifest-diff <a.json> <b.json>
    python scripts/launcher.py build <recipe.json> [--set name=value ...] [--dry-run] [--force step,...]
                                     [--until step] [--keep-going] [--min-free-gb N --disk <path> ...] [--idle]
    python scripts/launcher.py status <recipe.json> [--set name=value ...] [--json <out.json>]
    python scripts/launcher.py same-ids <build A> <build B> [--plugins a.esm,b.esm] [--report <out.json>]
    python scripts/launcher.py gui [--settings <json>] [--recipe <json>] [--starfield <game>] [--fo4-data <Data>]
    python scripts/launcher.py snapshot --starfield <game dir> --out <snapshot.json> [--plugins-txt <path>] [--watch <file> ...]
    python scripts/launcher.py restore --snapshot <snapshot.json> [--port-staging <dir>] [--apply]
    python scripts/launcher.py detect --fo4-data <dir> ... --starfield <game dir> [--out-dir <drive or folder>]
                                      [--need-gb N] [--floor-gb 40] [--allow-unknown] [--allow-missing-dlc]
                                      [--my-games <Documents\My Games\Starfield>] [--allow-unknown-runtime]
                                      [--allow-missing-sfse]
    python scripts/launcher.py sources-add --manifest <build manifest.json> --label <text> [--table <json>]
    python scripts/launcher.py runtimes-add --manifest <build manifest.json> [--label <text>] [--table <json>]
    python scripts/launcher.py check-plugins <build folder> [--starfield-data <Starfield\Data>] [--also <master> ...]
    python scripts/launcher.py find [--steam <Steam folder>] [--gog <GOG Fallout 4 folder>] [--json <out.json>]
    python scripts/launcher.py bundle --out <support.zip> [--state-dir <dir> ...] [--manifest <json>] [--detect-report <json>]
                                      [--starfield <game dir>] [--plugins-txt <path>] [--my-games <dir>] [--file <path> ...]
    python scripts/launcher.py measure <folder> ...
    python scripts/launcher.py settings [--set key=value ...] [--settings <json>]
    python scripts/launcher.py play --starfield <game dir> [--settings <json>] [--dry-run]
    python scripts/launcher.py watch [--pid N] [--repeat] [--timeout S] [--settings <json>] [--dry-run]
    python scripts/launcher.py update [--check]
    python scripts/launcher.py instance plan|create --starfield <Steam's game folder> --at <new folder>
                                        [--keep-data-dir <name> ...] [--min-free-gb 40]
    python scripts/launcher.py instance run [--at <folder>] -- <installer command with --starfield <folder>>
    python scripts/launcher.py instance recover

manifest   what a build was made from and what it made (read only).
build      runs a recipe of the repo's make scripts with resumable, recorded steps (src/fo4sf/launcher/driver.py).
status     read only, no lock: each step's last result, its log if it failed, and what a run now would do
           (exit 0 only if every step would be reused).
same-ids   do two builds give the same FormIDs? IDENTICAL / SAME_IDS exit 0; IDS_DIFFER / INCOMPLETE exit 1.
detect     can this PC build? Fallout 4 version and DLC, Starfield, Archive2, CK, SFSE, disk (read only; exit 1 if not).
sources-add  adds a real install's master hashes (from a build manifest) to the known-sources table.
runtimes-add adds a real install's Starfield.exe and SFSE hashes (from a build manifest) to the known-runtimes table;
           detect refuses a Starfield.exe that is not listed there, a missing SFSE and a Game Pass install.
check-plugins  each built plugin's masters: refuses BlueprintShips-Starfield.esm as a master and masters that are
           neither in the build nor in the Starfield Data folder (read only; exit 1 on a problem).
find       finds Steam's Fallout 4 (normal install and depot downloads) and Starfield, and prints the detect line
           (read only).
bundle     a local support zip (driver state and newest logs, manifest, detect report, install records, Plugins.txt,
           INIs) with the home folder and user name taken out; nothing is sent.
measure    a folder's real disk use, hard links counted once (read only).
snapshot   records Starfield's Plugins.txt, Data plugins and archives and the three install records (read only).
restore    prints what would bring the install back to a snapshot; --apply does it through the existing installers
           and refuses while the game runs or on any conflict.
settings   shows the optional pieces (crash watcher, bridge, Papyrus logging, how the game starts) and what each one
           costs; --set changes them. Saved per player (default %LOCALAPPDATA%\FO4SF\launcher_settings.json).
play       applies the settings with the game closed, starts Starfield, and with the crash watcher on attaches
           ProcDump once the game has settled and logs how it ended (src/fo4sf/launcher/crashwatch.py).
watch      the same watcher for a game something else starts (the test runner): waits for Starfield.exe (or --pid),
           attaches after it settles, logs its end; --repeat goes on to each next game until none appears within
           --timeout. Starts nothing and changes no setting; refuses while the watcher is off in the settings.
update     brings this checkout up to GitHub's main now (a fast-forward only, src/fo4sf/launcher/selfupdate.py);
           --check only says how far behind it is. With the setting update=pull, play and gui do it first by themselves
           and start again on the new code (update=check: they only say it; off, the default: nothing is fetched).
instance   the FO4SF game folder, separate from the player's own Starfield and its mods (docs/ai/fo4sf-instance.md):
           plan (read only) says what would be hard-linked, copied and left out of Data, and the disk it costs; create
           makes it (Data's game files and Tools hard-linked on the same drive, the rest copied, the player's mods
           and add-ons left out), never writing in the Steam install. run: one of our installers on the folder, with its own Plugins.txt (LOCALAPPDATA =
           <folder>\FO4SF-local; the command must name the folder once as --starfield). With the setting
           instance=<folder>, play starts the game from it and puts FO4SF's Plugins.txt in the player's place only
           while it runs; recover (and every play) puts the player's back after a crash.
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf.launcher import (bundle, crashwatch, detect, driver, files, instance, locate, manifest,  # noqa: E402
                            paths, plugin_checks, restore, runtimes, same_ids, selfupdate, settings)

SOURCES = os.path.join(REPO, "scripts", "launcher_recipes", "known_sources.json")


def cmd_manifest(a):
    m = manifest.build_manifest(repo=REPO, fo4_data=a.fo4_data, starfield=a.starfield, output_paths=a.output,
                                hash_archives=a.hash_archives,
                                hash_game_esm=getattr(a, "hash_game_esm", False),
                                hash_limit=None if a.hash_limit_mb is None else int(a.hash_limit_mb * 2 ** 20))
    files.save_json(a.out, m)
    if "fo4" in m:
        print(f"Fallout 4: {len(m['fo4']['masters'])} masters, {len(m['fo4']['archives'])} archives; "
              f"DLC missing: {', '.join(m['fo4']['dlc_missing']) or 'none'}")
    if "game" in m:
        ver = (m["game"].get("exe_version") or {}).get("file") or "unknown"
        print(f"Starfield: exe version {ver}, SFSE {'yes' if m['game']['sfse'] else 'no'}, Creation Kit "
              f"{'yes' if m['game']['creation_kit'] else 'no'}")
    print(f"tools: commit {m['tools']['repo_commit']} dirty={m['tools']['repo_dirty']}; {a.out}")
    return 0


def cmd_manifest_diff(a):
    left, right = files.load_json(a.a), files.load_json(a.b)
    diffs = manifest.compare_inputs(left, right)
    unverified = []
    for side, value in (("first", left), ("second", right)):
        fo4 = value.get("fo4") or {}
        for kind, entries in (("master", fo4.get("masters", {})), ("archive", fo4.get("archives", {})),
                              ("game", (value.get("game") or {}).get("files", {}))):
            for name, identity in sorted(entries.items()):
                if identity is not None and not identity.get("sha256"):
                    unverified.append(f"{kind} {name} ({side})")
    for d in diffs:
        print("  " + d)
    if diffs:
        print(f"{len(diffs)} differences")
    elif unverified:
        print("no compared input/pin differences; content identity unverified")
    else:
        print("compared input identities and pins match")
    for name in unverified:
        print(f"  content not compared (missing SHA-256): {name}")
    return 0 if not diffs else 1


def cmd_build(a):
    recipe, _env = driver.load_recipe(a.recipe, a.set, repo=REPO)
    force = [s for s in (a.force or "").split(",") if s]
    report = driver.build(recipe, REPO, dry_run=a.dry_run, force=force, until=a.until, min_free_gb=a.min_free_gb,
                          disk_paths=a.disk, idle=a.idle, break_lock=a.break_lock, keep_going=a.keep_going)
    if a.dry_run:
        return 0
    print(f"{recipe['name']}: {'COMPLETE' if report['complete'] else 'NOT complete'} {report['counts']}")
    return 0 if report["complete"] else 1


def cmd_status(a):
    recipe, _env = driver.load_recipe(a.recipe, a.set, repo=REPO)
    st = driver.status(recipe, REPO)
    print(f"{st['recipe']}: " + (f"a driver is running ({st['lock']})" if st["lock"] else "no driver running"))
    lr = st["last_run"]
    if lr:
        print(f"  last run {lr['started']} to {lr['finished']}: {'COMPLETE' if lr['complete'] else 'NOT complete'} "
              f"{lr['counts']}")
    for s in st["steps"]:
        took = f"{s['seconds']} s" if s["seconds"] is not None else ""
        print(f"  {s['id']:<20} {s['last']:<11} runs {s['runs']:<3} {took:<10} now: {s['would']} ({s['why']})")
        if s["log"] and s["last"] not in driver.OK:
            print(f"  {'':<20} log {s['log']}")
    if a.json:
        files.save_json(a.json, st)
    return 0 if all(s["would"] == "reuse" for s in st["steps"]) else 1


def cmd_same_ids(a):
    plugins = [p for p in (a.plugins or "").split(",") if p] or None
    rep = same_ids.check(a.a, a.b, plugins)
    for line in same_ids.summary_lines(rep):
        print(line)
    if a.report:
        files.save_json(a.report, rep)
    return 0 if rep["verdict"] in same_ids.VERDICT_OK else 1


def cmd_snapshot(a):
    s = restore.take(a.starfield, a.plugins_txt or None, a.watch)
    files.save_json(a.out, s)
    print(f"snapshot: {len(s['data_top'])} Data files, installs "
          f"{[k for k, v in s['records'].items() if v] or 'none'}; {a.out}")
    return 0


def cmd_restore(a):
    target = files.load_json(a.snapshot)
    if not a.apply:
        cur = restore.take(target["starfield"], target["plugins_txt"], tuple(target.get("watched") or ()))
        p = restore.plan(target, cur, REPO, a.port_staging or None)
        for st in p["steps"]:
            print(f"  {st['what']}: {' '.join(st['argv'][1:])}")
        print(f"  Plugins.txt: {p['plugins_txt']}")
        for n in p["notes"]:
            print("  note: " + n)
        for c in p["conflicts"]:
            print("  CONFLICT: " + c)
        print("dry run (nothing changed); --apply to restore" if not p["conflicts"] else "conflicts: --apply refuses")
        return 0 if not p["conflicts"] else 1
    try:
        left = restore.apply(target, REPO, port_staging=a.port_staging or None)
    except restore.RestoreRefused as e:
        print(f"restore refused: {e}")
        return 1
    for d in left:
        print("  still differs: " + d)
    print("restored" if not left else "NOT fully restored")
    return 0 if not left else 1


def cmd_detect(a):
    # settings are read only for a missing argument; when only the optional my_games is missing, a settings file
    # that cannot be read leaves it unset instead of stopping a check that was given everything it needs (Codex, #481)
    if not (a.fo4_data and a.starfield):
        saved = settings.load(a.settings or default_settings_path())
        a.fo4_data = a.fo4_data or paths.split_dirs(saved["fo4_data"])
        a.starfield = a.starfield or saved["starfield"]
        a.my_games = a.my_games or saved["my_games"]
    elif not a.my_games:
        try:
            a.my_games = settings.load(a.settings or default_settings_path())["my_games"]
        except (OSError, ValueError) as e:
            print(f"settings not read ({e}); detect runs without --my-games")
    if not a.fo4_data or not a.starfield:
        raise ValueError("needs --fo4-data and --starfield, or both saved as locations (launcher.py paths --accept)")
    r = detect.detect(fo4_data=a.fo4_data, starfield=a.starfield, sources=a.table, out_dir=a.out_dir or None,
                      need_gb=a.need_gb, floor_gb=a.floor_gb, allow_unknown=a.allow_unknown,
                      allow_missing_dlc=a.allow_missing_dlc, require_ck=a.require_ck,
                      require_sfse=not a.allow_missing_sfse, my_games=a.my_games or None,
                      runtimes=a.runtimes, allow_unknown_runtime=a.allow_unknown_runtime)
    for m, v in ((r.get("fo4") or {}).get("masters") or {}).items():
        print(f"  {m:<20} {v['version'] or 'unknown version'}  {v['sha256'][:12]}")
    if r.get("game"):
        g = r["game"]
        print(f"  Starfield: Archive2 {'yes' if g['archive2'] else 'no'}, Creation Kit "
              f"{'yes' if g['creation_kit'] else 'no'}, SFSE {'yes' if g['sfse'] else 'no'}, runtime "
              f"{g['runtime'] or 'not listed'}")
    if r.get("disk"):
        d = r["disk"]
        print(f"  disk: {d['free_gb']} GB free, {d['floor_gb']:g} kept free, {d['usable_gb']} usable, need {d['need_gb']:g}")
    for w in r["warnings"]:
        print("  warning: " + w)
    for x in r["refusals"]:
        print("  REFUSED: " + x)
    if a.report:
        files.save_json(a.report, r)
    print("READY" if r["ready"] else "NOT READY")
    return 0 if r["ready"] else 1


def cmd_sources_add(a):
    table = detect.load_sources(a.table)
    n = detect.add_sources(table, files.load_json(a.manifest), a.label)
    files.save_json(a.table, table)
    print(f"{n} entries added to {a.table} ({len(table['sources'])} in all)")
    return 0


def cmd_runtimes_add(a):
    table = runtimes.load_runtimes(a.table)
    n = runtimes.add_runtime(table, files.load_json(a.manifest), a.label)
    files.save_json(a.table, table)
    print(f"{n} runtime added to {a.table} ({len(table['runtimes'])} in all)")
    return 0


def cmd_check_plugins(a):
    r = plugin_checks.check(a.folder, a.starfield_data or None, a.also)
    for n, ms in r["plugins"].items():
        print(f"  {n:<32} masters: {', '.join(ms) or 'none'}")
    for p in r["problems"]:
        print("  PROBLEM: " + p)
    print("plugins ok" if not r["problems"] else f"{len(r['problems'])} problems")
    return 0 if not r["problems"] else 1


def cmd_find(a):
    r = locate.locate(a.steam or None, a.gog or None)
    print(f"  Steam: {r['steam'] or 'not found'}")
    for lib in r["libraries"][1:]:
        print(f"    library: {lib}")
    print(f"  Fallout 4: {r['fallout4'] or 'no normal install'}"
          + (f" ({r['fallout4_store']})" if r["fallout4_store"] else ""))
    for d in r["fallout4_depots"]:
        print(f"    depot download: {d}")
    print(f"  Starfield: {r['starfield'] or 'not found'}")
    for n in r["notes"]:
        print("  note: " + n)
    data = locate.fo4_data_folders(r)
    if data and r["starfield"]:
        print("  detect: python scripts/launcher.py detect " + " ".join(f'--fo4-data "{d}"' for d in data)
              + f' --starfield "{r["starfield"]}"')
    if a.json:
        files.save_json(a.json, r)
    return 0 if data and r["starfield"] else 1


def cmd_bundle(a):
    pt = a.plugins_txt or (restore.plugins_txt_default() if a.starfield else None)
    lines = bundle.make(a.out, state_dirs=a.state_dir, manifest=a.manifest or None,
                        detect_report=a.detect_report or None, starfield=a.starfield or None, plugins_txt=pt,
                        my_games=a.my_games or None, extra=a.file, about=[selfupdate.describe(REPO)])
    for line in lines[2:]:
        print(line)
    print(f"bundle written: {a.out} (nothing was sent; look inside before attaching it to an issue)")
    return 0


def cmd_measure(a):
    for p in a.paths:
        m = detect.measure(p)
        print(f"  {p}: {m['files']:,} files, listed {m['bytes_listed'] / 2**30:.2f} GiB, unique "
              f"{m['bytes_unique'] / 2**30:.2f} GiB, shared with other folders {m['bytes_shared'] / 2**30:.2f} GiB, "
              f"deleting frees {m['frees_if_deleted'] / 2**30:.2f} GiB")
    return 0


def default_settings_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "FO4SF", "launcher_settings.json")


def cmd_settings(a):
    path = a.settings or default_settings_path()
    values = settings.load(path)
    if a.set:
        values = settings.assign(values, a.set)
        settings.save(path, values)
        print(f"saved {path}")
    for line in settings.describe(values):
        print(line)
    for p in settings.problems(values):
        print(f"play would refuse: {p}")
    return 0


def updated(mode):
    """The update setting before play or the window: True when the checkout moved (the caller then starts the same
    command again on the new code, selfupdate.restart)."""
    return selfupdate.update(REPO, mode, running=restore.game_running) if mode != "off" else False


def put_back_left_swap(dry_run):
    """A Plugins.txt swap left by an FO4SF folder start that did not see its end: the player's list comes back before
    any start (a dry run only says so). Its journal sits beside the launcher's settings, never in the folder."""
    try:
        player = instance.player_plugins_txt()
    except instance.InstanceRefused:                   # no LOCALAPPDATA: no player's list, and no journal for one
        return
    if dry_run:
        if instance.pending(player):
            print(f"Plugins.txt: a swap is left from an earlier FO4SF start ({instance.journal_path(player)}); "
                  "play puts yours back first (a dry run changes nothing)")
        return
    instance.recover(player, restore.game_running)


def cmd_play(a):
    put_back_left_swap(a.dry_run)                      # every play, before anything that could refuse (the settings)
    values = settings.load(a.settings or default_settings_path())
    # a dry run only looks: it says how far behind it is, and never moves the checkout
    if updated("check" if a.dry_run and values["update"] != "off" else values["update"]):
        return selfupdate.restart(a.argv)
    folder = values["instance"]
    norm = lambda p: os.path.normcase(os.path.abspath(p))   # noqa: E731
    if folder and a.starfield and norm(a.starfield) != norm(folder):
        raise ValueError(f"--starfield {a.starfield} is not the FO4SF game folder {folder} (setting instance); "
                         "pass that folder or none")
    if folder:                                        # the FO4SF game folder: always FO4SF, the player's left alone
        r = crashwatch.play(values, folder, dry_run=a.dry_run, folder=folder)
        return 0 if r.get("dry_run") or r.get("started") else 1
    starfield = a.starfield or values["starfield"]
    if not starfield:
        raise ValueError("no Starfield folder: confirm it in the window's Locations tab, run `launcher.py paths "
                         "--accept`, or pass --starfield")
    if not a.starfield and paths.check("starfield", starfield):   # a saved folder the game has since left (Codex, #481)
        raise ValueError(f"the saved Starfield folder {starfield}: {paths.check('starfield', starfield)}; confirm it "
                         "again in the window's Locations tab or with `launcher.py paths --accept`")
    r = crashwatch.play(values, starfield, dry_run=a.dry_run)
    return 0 if r.get("dry_run") or r.get("started") else 1


def cmd_paths(a):
    """Each location the launcher needs: the saved one, or what was found on this PC and is waiting to be confirmed."""
    path = a.settings or default_settings_path()
    values = settings.load(path)
    found = paths.detect()
    accept = []
    for r in paths.rows(values, found):
        mark = {"saved": "ok", "found": "found", "problem": "PROBLEM", "missing": "missing"}[r["status"]]
        print(f"  {r['label']:<24} {mark:<8} {r['value'] or '-'}" + ("" if r["status"] == "saved" else f"  ({r['note']})"))
        if r["status"] == "found":
            accept.append(f"{r['key']}={r['value']}")
    if a.accept and accept:
        settings.save(path, settings.assign(values, accept))
        print(f"saved {len(accept)} found location(s) to {path}")
    elif accept:
        print("check the found ones, then run again with --accept to save them (or confirm them in the window)")
    values = settings.load(path) if a.accept else values
    left = [k for k in paths.needed(values) if paths.check(k, values[k])]
    for k in left:
        print(f"  still needed to play: {settings.LABELS[k]}")
    return 0 if not left else 1


def cmd_watch(a):
    values = settings.load(a.settings or default_settings_path())
    r = crashwatch.watch(values, pid=a.pid, repeat=a.repeat, start_timeout_s=a.timeout, dry_run=a.dry_run)
    if r[0].get("dry_run"):
        return 0
    watched = [x for x in r if x.get("started")]
    # 0 only when every game seen was armed and nothing stopped the watch early (Codex, #449)
    return 0 if watched and all(x.get("armed") for x in watched) and not any(x.get("stopped") for x in r) else 1


def cmd_update(a):
    if selfupdate.update(REPO, "check" if a.check else "pull", running=restore.game_running):
        print("updated: the next launcher command runs the new code")
    return 0


def cmd_instance(a):
    if a.action == "recover":                          # found without the folder or the settings (instance.journal_path)
        done = instance.recover(instance.player_plugins_txt(), restore.game_running)
        print("done" if done else "nothing to put back")
        return 0
    folder = a.at or settings.load(a.settings or default_settings_path())["instance"]
    if a.action == "run":
        if not folder:
            raise ValueError("no FO4SF game folder: pass --at or set the setting instance")
        return instance.run(folder, a.command, running=restore.game_running, cwd=REPO)
    if not a.starfield or not a.at:
        raise ValueError(f"instance {a.action} needs --starfield <Steam's game folder> and --at <new folder>")
    if a.action == "plan":
        p = instance.plan(a.starfield, a.at, a.keep_data_dir)
        instance.check_target(a.starfield, a.at, a.min_free_gb, p["copy_bytes"])
        for line in instance.summary(p):
            print(line)
        print(f"plan only: `launcher.py instance create` makes {a.at}")
        return 0
    instance.create(a.starfield, a.at, a.keep_data_dir, a.min_free_gb)
    return 0


def cmd_gui(a):
    if updated(settings.load(a.settings or default_settings_path())["update"]):
        return selfupdate.restart(a.argv)
    from fo4sf.launcher import gui
    return gui.launch(__file__, a.settings or default_settings_path(), recipe=a.recipe, overrides=a.set,
                      fo4_data=a.fo4_data, starfield=a.starfield)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("manifest")
    s.add_argument("--out", required=True)
    s.add_argument("--fo4-data", action="append", default=[])
    s.add_argument("--starfield", default="")
    s.add_argument("--output", action="append", default=[])
    s.add_argument("--hash-archives", action="store_true")
    s.add_argument("--hash-game-esm", action="store_true",
                   help="also hash Starfield.esm input content (large optional read)")
    s.add_argument("--hash-limit-mb", type=float, default=None,
                   help="hash non-plugin outputs up to this size (default: hash everything)")
    s = sub.add_parser("manifest-diff")
    s.add_argument("a")
    s.add_argument("b")
    s = sub.add_parser("build")
    s.add_argument("recipe")
    s.add_argument("--set", action="append", default=[])
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--force", default="")
    s.add_argument("--until", default=None)
    s.add_argument("--keep-going", action="store_true")
    s.add_argument("--min-free-gb", type=float, default=0.0)
    s.add_argument("--disk", action="append", default=[])
    s.add_argument("--idle", action="store_true", help="Windows: run steps at Idle priority")
    s.add_argument("--break-lock", action="store_true")
    s = sub.add_parser("status", help="read only: each step's last result and what a run now would do")
    s.add_argument("recipe")
    s.add_argument("--set", action="append", default=[])
    s.add_argument("--json", default=None)
    s = sub.add_parser("same-ids")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("--plugins", default="")
    s.add_argument("--report", default="")
    s = sub.add_parser("snapshot")
    s.add_argument("--starfield", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--plugins-txt", default="")
    s.add_argument("--watch", action="append", default=[])
    s = sub.add_parser("restore")
    s.add_argument("--snapshot", required=True)
    s.add_argument("--port-staging", default="")
    s.add_argument("--apply", action="store_true")
    s = sub.add_parser("detect")
    s.add_argument("--fo4-data", action="append", default=[], help="default: the saved fo4_data location")
    s.add_argument("--starfield", default="", help="default: the saved starfield location")
    s.add_argument("--settings", default="")
    s.add_argument("--table", default=SOURCES)
    s.add_argument("--out-dir", default="")
    s.add_argument("--need-gb", type=float, default=0.0)
    s.add_argument("--floor-gb", type=float, default=detect.DEFAULT_FLOOR_GB)
    s.add_argument("--allow-unknown", action="store_true")
    s.add_argument("--allow-missing-dlc", action="store_true")
    s.add_argument("--require-ck", action="store_true")
    s.add_argument("--require-sfse", action="store_true", help="the default now (NG-1); kept for old command lines")
    s.add_argument("--allow-missing-sfse", action="store_true", help="report a missing SFSE instead of refusing")
    s.add_argument("--runtimes", default=runtimes.DEFAULT_TABLE)
    s.add_argument("--allow-unknown-runtime", action="store_true")
    s.add_argument("--my-games", default="", help="Documents\\My Games\\Starfield, as Windows resolves it (not guessed)")
    s.add_argument("--report", default="")
    s = sub.add_parser("sources-add")
    s.add_argument("--manifest", required=True)
    s.add_argument("--label", required=True)
    s.add_argument("--table", default=SOURCES)
    s = sub.add_parser("runtimes-add")
    s.add_argument("--manifest", required=True)
    s.add_argument("--label", help="default: the exe's own file version")
    s.add_argument("--table", default=runtimes.DEFAULT_TABLE)
    s = sub.add_parser("check-plugins")
    s.add_argument("folder")
    s.add_argument("--starfield-data", default="")
    s.add_argument("--also", action="append", default=[])
    s = sub.add_parser("find")
    s.add_argument("--steam", default="")
    s.add_argument("--gog", default="", help="GOG Fallout 4's folder, when the registry does not have it")
    s.add_argument("--json", default="")
    s = sub.add_parser("bundle")
    s.add_argument("--out", required=True)
    s.add_argument("--state-dir", action="append", default=[])
    s.add_argument("--manifest", default="")
    s.add_argument("--detect-report", default="")
    s.add_argument("--starfield", default="")
    s.add_argument("--plugins-txt", default="")
    s.add_argument("--my-games", default="")
    s.add_argument("--file", action="append", default=[])
    s = sub.add_parser("measure")
    s.add_argument("paths", nargs="+")
    s = sub.add_parser("settings")
    s.add_argument("--settings", default="", help="default: %%LOCALAPPDATA%%\\FO4SF\\launcher_settings.json")
    s.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    s = sub.add_parser("gui", help="open the optional launcher window (tkinter)")
    s.add_argument("--settings", default="")
    s.add_argument("--recipe", default="")
    s.add_argument("--set", action="append", default=[], help="recipe variable name=value (for build status)")
    s.add_argument("--fo4-data", action="append", default=[])
    s.add_argument("--starfield", default="")
    s = sub.add_parser("paths", help="find the folders and files the launcher needs and show what is saved")
    s.add_argument("--settings", default="")
    s.add_argument("--accept", action="store_true", help="save the found locations that are not saved yet")
    s = sub.add_parser("play")
    s.add_argument("--starfield", default="", help="default: the saved starfield location")
    s.add_argument("--settings", default="")
    s.add_argument("--dry-run", action="store_true", help="print what play would do; change and start nothing")
    s = sub.add_parser("watch", help="watch a game something else starts (the test runner): ProcDump as play attaches it")
    s.add_argument("--settings", default="")
    s.add_argument("--pid", type=int, default=None, help="follow this process only (default: the next Starfield.exe)")
    s.add_argument("--repeat", action="store_true", help="go on to each next game until none appears within --timeout")
    s.add_argument("--timeout", type=float, default=600.0, help="seconds to wait for a game to appear (default 600)")
    s.add_argument("--dry-run", action="store_true", help="print what watch would do; attach nothing")
    s = sub.add_parser("update", help="bring this checkout up to GitHub's main now (fast-forward only)")
    s.add_argument("--check", action="store_true", help="only say how far behind GitHub's main this checkout is")
    s = sub.add_parser("instance", help="the FO4SF game folder beside the player's own Starfield")
    s.add_argument("action", choices=("plan", "create", "run", "recover"))
    s.add_argument("--starfield", default="", help="plan/create: the Steam Starfield folder it is made from (read only)")
    s.add_argument("--at", default="", help="the FO4SF game folder (default for run/recover: the setting instance)")
    s.add_argument("--settings", default="")
    s.add_argument("--keep-data-dir", action="append", default=[], help="a Data folder to keep (repeatable)")
    s.add_argument("--min-free-gb", type=float, default=40.0, help="free space the drive keeps (default 40)")
    given = list(sys.argv[1:] if argv is None else argv)
    command = []
    if given[:1] == ["instance"] and "--" in given:            # instance run -- <command>: everything after -- is it
        cut = given.index("--")
        given, command = given[:cut], given[cut + 1:]
    a = ap.parse_args(given)
    a.command = command
    a.argv = [os.path.abspath(__file__), *(sys.argv[1:] if argv is None else argv)]   # the command, to start it again
    try:
        return {"manifest": cmd_manifest, "manifest-diff": cmd_manifest_diff, "build": cmd_build,
                "same-ids": cmd_same_ids, "snapshot": cmd_snapshot, "restore": cmd_restore,
                "detect": cmd_detect, "sources-add": cmd_sources_add, "runtimes-add": cmd_runtimes_add,
                "check-plugins": cmd_check_plugins, "find": cmd_find, "bundle": cmd_bundle, "measure": cmd_measure,
                "status": cmd_status, "settings": cmd_settings, "play": cmd_play,
                "watch": cmd_watch, "gui": cmd_gui, "paths": cmd_paths, "update": cmd_update,
                "instance": cmd_instance}[a.cmd](a)
    except driver.RecipeError as e:
        print(f"recipe: {e}")
        return 2
    except (ValueError, FileExistsError) as e:          # runtimes-add's refusals, bundle's no-overwrite
        print(f"{a.cmd}: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
