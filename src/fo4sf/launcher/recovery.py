"""Interrupted-install gate and rollback through the existing ownership-aware installers.

Read only until the player chooses Recover install. Never infer ownership from Plugins.txt,
upgrade an old receipt, repair a corrupt receipt, or remove a healthy dependent install.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile

from . import restore, test_kits


COMPONENTS = dict(restore.COMPONENTS, **{kit.key: (kit.receipt, kit.installer) for kit in test_kits.KITS})
UNINSTALL_ORDER = tuple(kit.key for kit in reversed(test_kits.KITS)
                        if kit.key not in restore.COMPONENTS) + restore.UNINSTALL_ORDER


def inspect(starfield):
    """Return (receipt bytes, pending components, errors), without reading game assets."""
    records, pending, errors = {}, [], []
    for comp in UNINSTALL_ORDER:
        name = COMPONENTS[comp][0]
        try:
            with open(os.path.join(starfield, "Data", name), "rb") as stream:
                raw = stream.read()
        except FileNotFoundError:
            continue
        except OSError:
            errors.append(f"cannot read {name}; preserve it for a failure report")
            continue
        records[comp] = raw
        try:
            rec = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(rec, dict) or not rec:
                raise ValueError("receipt is not an object")
            # Core deploy records a list of paths, with identities in artifacts;
            # the ride-along installers record a path-to-digest object instead.
            # Leave missing legacy fields alone; each installer validates ownership.
            files_type = list if comp == "port" else dict
            if "files" in rec and not isinstance(rec["files"], files_type):
                raise ValueError("receipt files do not match the component's format")
        except (UnicodeError, ValueError):
            errors.append(f"cannot read {name}; preserve it for a failure report")
            continue
        # Legacy receipts can omit complete. A pending restore on a complete install
        # is intentional: it owns the later uninstall, not an interrupted operation.
        if rec.get("complete", True) is not True or rec.get("cleanup_pending") or "rollback_completed" in rec:
            pending.append(comp)
    return records, pending, errors


def play_reason(starfield):
    _records, pending, errors = inspect(starfield)
    if errors:
        return "Installation state unreadable: " + "; ".join(errors) + ". Play is blocked."
    if pending:
        return ("Installation incomplete (" + ", ".join(pending) + "). Choose Recover install "
                "to keep a copy of a partial plugin list and roll back interrupted work before playing "
                "(CLI: launcher.py recover-install).")
    return ""


def _preserve_partial_plugins(raw, env, running, say):
    """A partial/external list is kept before restoring the recorded pre-install list.

    Only explicit recovery may do this. Normal Play and the installers still refuse
    unknown bytes. The journal stays active across every failure or interruption.
    """
    rec = json.loads(raw.decode("utf-8-sig"))
    if rec.get("complete", True) is not False or not rec.get("plugins_restore_pending"):
        return
    local = env.get("LOCALAPPDATA")
    if not local:
        raise ValueError("Cannot find this profile's Plugins.txt; keep the recovery journal.")
    path = restore._plugins_txt_path(os.path.join(local, "Starfield", "Plugins.txt"))
    recorded = rec.get("plugins_txt")
    if not isinstance(recorded, str) or os.path.normcase(os.path.abspath(recorded)) != os.path.normcase(path):
        raise ValueError("Recovery journal belongs to a different Plugins.txt; nothing changed.")
    try:
        original = rec["plugins_original"]
        activated = rec["plugins_activated"]
        original_bytes = None if original is None else base64.b64decode(original, validate=True)
        activated_bytes = base64.b64decode(activated, validate=True)
    except (KeyError, TypeError, ValueError):
        raise ValueError("Recovery journal has unreadable saved plugin bytes; nothing changed.") from None
    current = restore._read(path)
    if current in (original_bytes, activated_bytes):
        return  # the installer already knows how to restore these states
    if current is not None:
        descriptor, backup = tempfile.mkstemp(prefix="Plugins.txt.recovery-", suffix=".bak",
                                             dir=os.path.dirname(path))
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(current)
            stream.flush()
            os.fsync(stream.fileno())
        if restore._read(backup) != current:
            raise ValueError("Plugin-list backup could not be verified; nothing restored.")
        say(f"Recover install: kept the partial/current plugin list in {backup}")
    if running():
        raise ValueError("Game state changed; plugin list and recovery journal preserved.")
    expected = None if current is None else hashlib.sha256(current).hexdigest()
    restore.write_plugins_txt(path, original, expected)


def recover(starfield, repo, *, apply=False, env=None, running=restore.game_running,
            run=subprocess.run, say=print):
    """Plan, or apply, only pending rollbacks. A refusal retains the installers' journals."""
    starfield = os.path.abspath(starfield)
    env = dict(os.environ) if env is None else env
    records, pending, errors = inspect(starfield)
    if errors:
        raise ValueError("; ".join(errors))
    for rider, base in restore.RIDES_ON.items():
        if base in pending and rider in records and rider not in pending:
            raise ValueError(f"{rider} still needs {base}; preserve both receipts and remove the rider "
                             "through its installer before recovering the base")
    if not pending:
        say("No interrupted installation to recover.")
        return
    if apply and running():
        raise ValueError("Close Starfield before recovering (an unknown process state also blocks recovery).")
    if apply:
        for comp in pending:
            if not os.path.isfile(os.path.join(repo, *COMPONENTS[comp][1].split("/"))):
                raise ValueError(f"Recovery installer for {comp} is unavailable; keep all journals and ask the PC helper.")
    for comp in pending:
        argv = [sys.executable, "-I", os.path.join(repo, *COMPONENTS[comp][1].split("/")),
                "uninstall", "--starfield", starfield]
        say(f"Recover install: roll back interrupted {comp}")
        if apply:
            # Recheck after each installer. Never act on a replaced receipt or launch
            # another rollback under a game that started while recovery was running.
            current, _pending, errors = inspect(starfield)
            if errors or current != records or running():
                raise ValueError("Installation or game state changed during recovery; journals preserved.")
            _preserve_partial_plugins(records[comp], env, running, say)
            result = run(argv, cwd=repo, env=env)
            if result.returncode:
                raise ValueError(f"Recovery of {comp} stopped (exit {result.returncode}); keep the journal, "
                                 "resolve the installer's reported conflict, then choose Recover install again.")
            after, left, errors = inspect(starfield)
            expected = {key: raw for key, raw in records.items() if key != comp}
            if errors or comp in left or after != expected:
                raise ValueError("Recovery did not retire only its own journal; Play must be checked again.")
            records = after
    say("Interrupted work rolled back. Run the install again before playing." if apply else
        "Preview only. Choose Recover install in the window, or repeat with --apply, to roll back.")
