"""Install / uninstall the observation bridge next to the converted build (docs/ai/test-queue.md "Bridge").

The bridge is its own small deployment, independent of the queue's experiment (exp_install.py keeps exactly one
experiment record; the bridge rides along with any of them): FO4SFBridge.esm and "FO4SFBridge - Main.ba2" (the
compiled script FO4SF_Bridge.pex, packed from the staged Data tree the way exp_install packs experiments: loose
scripts are not read on this install) go into the game's Data folder, "*FO4SFBridge.esm" goes to the end of
Plugins.txt, and Data\\FO4SFBridge.install.json records what was added. install is idempotent: the same staged bridge
already in place (same file hashes) is left alone and only its Plugins.txt line is checked; a different one is
refused until uninstalled. uninstall removes exactly the recorded files (unchanged ones only) and the Plugins.txt line
it added. exp_install.py uninstall never touches the bridge; the chain may leave it installed between queues.

usage: python bridge_install.py install|uninstall|status --dir <staged bridge dir> --starfield <game dir>
       (the staged dir: scripts/bridge/make_bridge.py stage, e.g. C:\\Modding\\staging\\bridge_t0)
"""
import argparse
import base64
from contextlib import nullcontext
from collections import Counter
import json
import os
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_install  # noqa: E402
from exp_install import deployment  # noqa: E402

RECORD = "FO4SFBridge.install.json"
PLUGIN = "FO4SFBridge.esm"
ARCHIVE = "FO4SFBridge - Main.ba2"
PEX = os.path.join("Data", "Scripts", "FO4SF_Bridge.pex")
KIT = "bridge"                                    # names this kit in messages (map_markers_install.py reuses the module)
STAGE_HINT = "scripts/bridge/make_bridge.py stage"


def record_path(a):
    data = os.path.abspath(os.path.join(a.starfield, "Data"))
    return data, os.path.join(data, RECORD)


def read_record(rec_p):
    with open(rec_p, encoding="utf-8") as f:
        return json.load(f)


def plugin_line_present(lines, plugin):
    """The index of the active line for plugin in Plugins.txt's lines, else None."""
    for k, ln in enumerate(lines):
        if ln.strip().casefold() == ("*" + plugin).casefold():
            return k
    return None


def activate(plugin, rec, rec_p):
    """Journal before/intended bytes, then activate last; retain cleanup ownership."""
    p = exp_install.plugins_txt()
    original = exp_install.read_bytes(p)
    lines, bom, nl = exp_install.plugin_lines(original)
    removed = [ln for ln in lines if ln.strip().lstrip("*").casefold() == plugin.casefold()]
    kept = [ln for ln in lines if ln not in removed]
    new = kept + ["*" + plugin]
    # Persist exact before/intended bytes before activation can change anything.
    # complete=False also covers a crash while reactivating an existing bridge.
    rec.update({"complete": False, "plugins_txt": p, "plugin_line_added": "*" + plugin,
                "plugin_lines_removed": removed,
                "plugins_original": base64.b64encode(original).decode("ascii") if original is not None else None,
                "plugins_activated": base64.b64encode(deployment.render_lines(new, original)).decode("ascii"),
                "plugins_restore_pending": True})
    deployment.write_manifest(rec_p, rec)
    try:
        exp_install.write_plugins(p, new, bom, nl, original)
    except deployment.ConcurrentUpdateError:
        # The typed failure proves no activation was published. Preserve the
        # external edit and don't attempt to restore over it during recovery.
        rec["plugins_restore_pending"] = False
        rec["plugin_line_added"] = ""
        rec["plugin_lines_removed"] = []
        deployment.write_manifest(rec_p, rec)
        raise


def validate_profile(rec):
    p = exp_install.plugins_txt()
    recorded = rec.get("plugins_txt", p)
    if not isinstance(recorded, str) or os.path.normcase(os.path.abspath(recorded)) != os.path.normcase(os.path.abspath(p)):
        raise ValueError("recorded Plugins.txt does not match the current user path")
    return p


def deactivate(rec):
    """Undo activation; a retry must not duplicate already-restored inactive lines."""
    p = validate_profile(rec)
    original = exp_install.read_bytes(p)
    if original is None:
        return
    lines, bom, nl = exp_install.plugin_lines(original)
    added = (rec.get("plugin_line_added") or "").strip().casefold()
    new = [ln for ln in lines if ln.strip().casefold() != added]
    removed = list(rec.get("plugin_lines_removed") or [])
    required = Counter(ln.strip().casefold() for ln in removed)
    present = Counter(ln.strip().casefold() for ln in new)
    for line in removed:
        key = line.strip().casefold()
        if present[key] < required[key]:
            new.append(line)
            present[key] += 1
    if new != lines:
        exp_install.write_plugins(p, new, bom, nl, original)


def staged(a):
    d = os.path.abspath(a.dir)
    plugin = os.path.join(d, PLUGIN)
    pex = os.path.join(d, PEX)
    for p in (plugin, pex):
        if not os.path.exists(p):
            sys.exit(f"staged {KIT} incomplete: {p} missing ({STAGE_HINT})")
    return d, plugin, pex


def source_inventory(directory):
    source = {PLUGIN: exp_install.digest(os.path.join(directory, PLUGIN))}
    for root, dirs, names in os.walk(os.path.join(directory, "Data")):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(root, name)
            source[os.path.relpath(path, directory)] = exp_install.digest(path)
    return source


def archive_inputs(source):
    return {name.replace("\\", "/"): identity for name, identity in source.items()}


def install(a):
    data, rec_p = record_path(a)
    try:
        exp_install.require_complete_master(data)
    except (OSError, ValueError) as error:
        sys.exit(f"{KIT} not installed: {error}")
    d, plugin_src, _pex = staged(a)
    source = source_inventory(d)  # every packed file: another script set is another bridge
    targets = {PLUGIN: exp_install.data_path(data, PLUGIN), ARCHIVE: exp_install.data_path(data, ARCHIVE)}
    if os.path.exists(rec_p):
        rec = read_record(rec_p)
        if rec.get("complete") is not True or rec.get("cleanup_pending"):
            sys.exit(f"incomplete {KIT} install ({rec_p}); uninstall it first")
        same = (rec.get("source_sha256") == source and isinstance(rec.get("files"), dict)
                and set(rec["files"]) == set(targets) and all(
            os.path.exists(targets[rel]) and exp_install.digest(targets[rel]) == h for rel, h in rec["files"].items())
                )
        if not same:
            sys.exit(f"another {KIT} is installed ({rec_p}: {rec.get('dir')}); uninstall it first")
        exp_install.verify_archive(targets[ARCHIVE], archive_inputs(source))
        try:
            held = PLUGIN.casefold() in exp_install.held_off(data)
        except (OSError, ValueError) as error:
            sys.exit(f"bridge not installed: {error}")
        if held:                                          # plugin_toggle.py holds it off: stays unticked
            if plugin_line_present(exp_install.read_plugins(exp_install.plugins_txt())[0], PLUGIN) is not None:
                sys.exit(f"bridge not installed: {PLUGIN} is held off by plugin_toggle.py but active in Plugins.txt")
            print(f"already installed; {PLUGIN} held off by plugin_toggle.py")
            return
        lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
        if plugin_line_present(lines, PLUGIN) is None:    # e.g. a deploy rewrote Plugins.txt: activate again
            # Verified complete legacy receipts already own these files. Retain
            # that proof if reactivation is interrupted before completion.
            rec.setdefault("published_files", list(rec["files"]))
            activate(PLUGIN, rec, rec_p)
            rec["complete"] = True
            deployment.write_manifest(rec_p, rec)
            print(f"already installed; {PLUGIN} activated again")
        else:
            print("already installed")
        return
    exp_install.refuse_while_held(data, "bridge not installed")
    clash = [rel for rel in targets if os.path.exists(targets[rel])]
    if clash:
        sys.exit(f"refusing to overwrite existing game files: {clash}")
    rec = {"schema": 2, "dir": d, "plugin": PLUGIN, "source_sha256": source,
           "files": {}, "published_files": [], "complete": False}
    prepacked = getattr(a, "prepacked", "")
    with (nullcontext(None) if prepacked else tempfile.TemporaryDirectory(prefix=f"fo4sf-{KIT}-pack-")) as tmp:
        ba2 = prepacked or exp_install.build_ba2(SimpleNamespace(starfield=a.starfield), os.path.join(d, "Data"),
                                                os.path.join(tmp, ARCHIVE))
        if source_inventory(d) != source:
            raise OSError(f"{KIT} source changed while packing; nothing installed")
        exp_install.verify_archive(ba2, archive_inputs(source))
        identities = {PLUGIN: source[PLUGIN], ARCHIVE: exp_install.digest(ba2)}
        deployment.write_manifest(rec_p, rec)
        try:
            for rel, src in ((PLUGIN, plugin_src), (ARCHIVE, ba2)):
                rec["files"][rel] = identities[rel]  # intent before publication
                deployment.write_manifest(rec_p, rec)
                try:
                    deployment.copy_new_artifact(src, targets[rel], expected_sha256=identities[rel])
                except FileExistsError:
                    rec["files"].pop(rel)  # exclusive creation proves this isn't ours
                    rec.setdefault("not_published", []).append(rel)
                    deployment.write_manifest(rec_p, rec)
                    raise
                rec["published_files"].append(rel)
                deployment.write_manifest(rec_p, rec)
                if exp_install.digest(targets[rel]) != identities[rel]:
                    raise OSError(f"installed {KIT} differs from pinned source: {rel}")
            activate(PLUGIN, rec, rec_p)
            rec["complete"] = True
            deployment.write_manifest(rec_p, rec)
        except BaseException:
            rec["complete"] = False
            try:
                uninstall(a, _recovery=rec)
            except (OSError, ValueError, SystemExit) as recovery:
                print(f"{KIT} recovery incomplete; preserve {rec_p}: {recovery}", file=sys.stderr)
            raise
    print(f"installed {PLUGIN} + \"{ARCHIVE}\" from {d}; {PLUGIN} active")


def uninstall(a, _recovery=None):
    data, rec_p = record_path(a)
    if not os.path.exists(rec_p):
        print(f"{KIT} not installed")
        return
    if _recovery is None:
        exp_install.refuse_while_held(data, "bridge not uninstalled")
    rec = read_record(rec_p) if _recovery is None else _recovery
    validate_profile(rec)  # interrupted recovery must obey the same profile guard
    if not isinstance(rec.get("files"), dict) or set(rec["files"]) - {PLUGIN, ARCHIVE}:
        raise ValueError(f"unexpected {KIT} file ownership; record preserved")
    errors = []
    try:
        if not rec.get("complete"):
            if rec.get("plugins_restore_pending"):
                deployment.restore_plugins(rec)
        else:
            deactivate(rec)
        rec["plugins_restore_pending"] = False
        rec["plugin_line_added"] = ""
        rec["plugin_lines_removed"] = []
    except (OSError, ValueError) as e:
        errors.append(str(e))
    kept = {}
    for rel, h in list(rec.get("files", {}).items()):
        dst = exp_install.data_path(data, rel)
        try:
            if os.path.exists(dst):
                if not rec.get("complete") and rel not in rec.get("published_files", []):
                    raise OSError(f"unconfirmed {KIT} publication; preserved: {rel}")
                if exp_install.digest(dst) != h:
                    raise OSError(f"file changed since install; preserved: {rel}")
                os.remove(dst)
        except OSError as e:
            kept[rel] = h
            errors.append(str(e))
    rec["files"] = kept
    # Old interrupted copies or a damaged receipt can leave untracked bridge
    # files. Only an explicit exclusive-create refusal proves a file isn't ours.
    for rel in (PLUGIN, ARCHIVE):
        if (rel not in rec["files"] and rel not in rec.get("not_published", [])
                and os.path.exists(exp_install.data_path(data, rel))):
            errors.append(f"untracked {KIT} file; preserved: {rel}")
    if errors:
        rec["cleanup_pending"] = True
        deployment.write_manifest(rec_p, rec)
        sys.exit(f"{KIT} partly uninstalled, record retained at {rec_p}: {'; '.join(errors)}")
    os.remove(rec_p)
    print("uninstalled")


def order_preflight(a):
    """order's read-only checks, before it touches Plugins.txt: None when the kit is not installed, else
    (data, rec_p, rec, Plugins.txt path, held off); ValueError when order would refuse (campaign_arm.py runs the same
    checks before it arms a chain, Codex on #391)."""
    data, rec_p = record_path(a)
    if not os.path.exists(rec_p):
        return None
    rec = read_record(rec_p)
    if rec.get("complete") is not True or rec.get("cleanup_pending"):
        raise ValueError(f"incomplete {KIT} install: recover before ordering")
    if not isinstance(rec.get("files"), dict) or set(rec["files"]) != {PLUGIN, ARCHIVE}:
        raise ValueError(f"incomplete {KIT} file coverage: recover before ordering")
    for relative, expected in rec["files"].items():
        target = exp_install.data_path(data, relative)
        if not os.path.isfile(target) or exp_install.digest(target) != expected:
            raise ValueError(f"installed {KIT} changed: {relative}")
    p = validate_profile(rec)
    held = PLUGIN.casefold() in exp_install.held_off(data)
    if held and plugin_line_present(exp_install.read_plugins(p)[0], PLUGIN) is not None:
        raise ValueError(f"{PLUGIN} is held off by plugin_toggle.py but active in Plugins.txt: "
                         f"run plugin_toggle.py on, or untick it")
    return data, rec_p, rec, p, held


def order(a):
    """The bridge's line moved to the END of Plugins.txt, right before launch (cycle.ps1 after exp_install order).
    The bridge has no masters and nothing depends on its load index, but every planned test addresses the experiment's
    records by load index (plugin_index 02 for the terrain, the cave slice's door 05000800): cave_core64c_1015 a1
    (2026-10-15) had "*FO4SFBridge.esm" first, every experiment shifted one index up, prid 05000800 hit FO4Port's
    record and the reads came back from the console's previous selection. Exit 0 whether or not a move was needed."""
    pre = order_preflight(a)
    if pre is None:
        print(f"{KIT} not installed: nothing to order")
        return
    data, rec_p, rec, p, held = pre
    if held:
        print(f"{PLUGIN} held off by plugin_toggle.py: left unticked")
        return
    original = exp_install.read_bytes(p)
    lines, bom, nl = exp_install.plugin_lines(original)
    k = plugin_line_present(lines, PLUGIN)
    if k is None:
        rec.setdefault("published_files", list(rec["files"]))
        activate(PLUGIN, rec, rec_p)
        rec["complete"] = True
        deployment.write_manifest(rec_p, rec)
        print(f"{PLUGIN} was not active: appended last")
        return
    if k == len(lines) - 1:
        print(f"{PLUGIN} already last")
        return
    new = lines[:k] + lines[k + 1:] + [lines[k]]
    exp_install.write_plugins(p, new, bom, nl, original)
    print(f"{PLUGIN} moved from line {k + 1} to the end ({len(new)} lines)")


def status(a):
    data, rec_p = record_path(a)
    if not os.path.exists(rec_p):
        print(json.dumps({"installed": False}))
        return
    rec = read_record(rec_p)
    lines, _, _ = exp_install.read_plugins(exp_install.plugins_txt())
    print(json.dumps(dict(rec, installed=True, active=plugin_line_present(lines, PLUGIN) is not None)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("install", "uninstall", "status", "order"))
    ap.add_argument("--dir", default="", help="the staged bridge folder (install)")
    ap.add_argument("--starfield", required=True)
    ap.add_argument("--prepacked", default="", help="verify and install this existing archive; never build")
    a = ap.parse_args(argv)
    if a.cmd == "install":
        if not a.dir:
            sys.exit("install needs --dir")
        install(a)
    elif a.cmd == "uninstall":
        uninstall(a)
    elif a.cmd == "order":
        order(a)
    else:
        status(a)


if __name__ == "__main__":
    main()
