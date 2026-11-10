"""Publish an explicitly supplied release declaration in a finished FO4SF instance.

The instance receipt owns its declaration pin. Pending goes first, complete last;
repeating the same operation resumes interrupted publication. Never bind a save.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from . import instance, recovery, restore, save_release as sr

FIELD = "save_release"


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def pin(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def read(path):
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if path.is_symlink() or info.st_nlink != 1:
        raise sr.BindingError(f"{path.name}: release metadata is linked")
    with path.open("rb") as stream:
        raw = stream.read(sr.MAX_METADATA_BYTES + 1)
    if len(raw) > sr.MAX_METADATA_BYTES:
        raise sr.BindingError("release metadata exceeds size limit")
    return raw


def decode(raw):
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=sr._pairs, parse_constant=sr._constant)


def ownership(value):
    sr._keys(value, ("schema", "complete", "declaration", "previous"), "release ownership")
    if type(value["schema"]) is not int or value["schema"] != 1 or type(value["complete"]) is not bool:
        raise sr.BindingError("unknown release ownership schema/state")
    sr._identity_fields(value["declaration"])
    if value["previous"] is not None:
        sr._identity_fields(value["previous"])
    if value["complete"] and value["previous"] is not None:
        raise sr.BindingError("complete release has pending previous identity")
    return value


def installed(starfield):
    """Read the owned declaration, None for a legacy instance with neither record."""
    root = Path(starfield)
    raw = read(root / instance.RECORD)
    receipt = decode(raw) if raw is not None else {}
    if not isinstance(receipt, dict):
        raise sr.BindingError("instance receipt is not an object")
    declaration_raw = read(root / "Data" / sr.RELEASE_FILE)
    if FIELD not in receipt:
        if declaration_raw is not None:
            raise sr.BindingError("release declaration has no installer ownership")
        return None
    owned = ownership(receipt[FIELD])
    if receipt.get("schema") != instance.SCHEMA or receipt.get("complete") is not True:
        raise sr.BindingError("release instance is incomplete or unknown")
    if not owned["complete"]:
        raise sr.BindingError("release publication incomplete; repeat install-release with the same declaration")
    if declaration_raw is None or pin(declaration_raw) != owned["declaration"]:
        raise sr.BindingError("owned release declaration is missing or changed")
    return sr.declaration(decode(declaration_raw))


def _write(path, raw, expected):
    """Atomic replacement, refusing linked metadata and observed concurrent edits."""
    path = Path(path)
    if len(raw) > sr.MAX_METADATA_BYTES:
        raise sr.BindingError("published release metadata exceeds size limit")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".part", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if read(path) != expected:
            raise sr.BindingError(f"{path.name}: metadata changed during publication; nothing replaced")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish(values, candidate_path, *, apply=False, running=restore.game_running, say=print):
    """Preview, or install, declaration metadata only. Existing saves stay untouched."""
    root = Path(values.get("instance", ""))
    if not values.get("instance") or not root.is_absolute():
        raise sr.BindingError("install-release needs an absolute confirmed FO4SF instance")
    if instance._is_link(str(root)) or instance._is_link(str(root / "Data")):
        raise sr.BindingError("instance or Data is redirected")
    receipt_path, target = root / instance.RECORD, root / "Data" / sr.RELEASE_FILE
    receipt_raw = read(receipt_path)
    if receipt_raw is None:
        raise sr.BindingError("instance receipt is missing")
    receipt = decode(receipt_raw)
    if not isinstance(receipt, dict) or receipt.get("schema") != instance.SCHEMA or receipt.get("complete") is not True:
        raise sr.BindingError("unknown or incomplete instance receipt")
    instance.check_ready(str(root))
    reason = recovery.play_reason(str(root))
    if reason:
        raise sr.BindingError(reason)
    candidate_raw = read(candidate_path)
    if candidate_raw is None:
        raise sr.BindingError("release declaration input is missing")
    release = sr.declaration(decode(candidate_raw))
    raw = encode(release)
    problems = sr._installed_masters(release, root)
    if problems:
        raise sr.BindingError(problems[0])
    old_raw = read(target)
    old = receipt.get(FIELD)
    if FIELD not in receipt:
        if old_raw is not None:
            raise sr.BindingError("unowned declaration already exists; nothing overwritten")
        previous = None
    else:
        old = ownership(old)
        previous = old["declaration"] if old["complete"] else old["previous"]
        if old["complete"]:
            if old_raw is None or pin(old_raw) != old["declaration"]:
                raise sr.BindingError("owned declaration missing or changed; preserve receipt")
        elif old["declaration"] != pin(raw):
            raise sr.BindingError("different release publication is pending; resume its original declaration")
        elif (None if old_raw is None else pin(old_raw)) not in (previous, pin(raw)):
            raise sr.BindingError("pending declaration has unknown bytes; preserve receipt")
    say(f"Release {release['release_id']}: publish declaration only; no saves adopted or changed")
    if not apply:
        say("Preview only; --apply publishes after the game-closed check")
        return
    if running():
        raise sr.BindingError("close Starfield before publishing a release")
    if old is not None and old["complete"] and old_raw == raw:
        say("Matching release declaration already published; nothing changed")
        return
    pending = dict(receipt, **{FIELD: {"schema": 1, "complete": False,
                                    "declaration": pin(raw), "previous": previous}})
    pending_raw = encode(pending)
    _write(receipt_path, pending_raw, receipt_raw)
    if running() or read(receipt_path) != pending_raw:
        raise sr.BindingError("game or instance changed; release publication remains pending")
    _write(target, raw, old_raw)
    if running() or read(target) != raw:
        raise sr.BindingError("game or declaration changed; release publication remains pending")
    complete = dict(pending, **{FIELD: {"schema": 1, "complete": True,
                                     "declaration": pin(raw), "previous": None}})
    _write(receipt_path, encode(complete), pending_raw)
    say("Release declaration published; Play still checks every save binding")
