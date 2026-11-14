"""Guarded runtime INI publication in the instance's existing ownership receipt.

Only Data configuration is written. The resolved save parent must already exist;
native consumers create the runtime tree. An interrupted publication blocks Play
until an explicit configure-runtime --apply resumes the same input.
"""
import os
from pathlib import Path
import re
import stat
import tempfile

from . import instance, recovery, release_install as ri, save_release as sr

FIELD = "runtime_config"
NAME = "FO4SF-Runtime.ini"
RELATIVE = ("Data", "SFSE", "Plugins", NAME)
CONSUMERS = ("FOCCSidecar.dll", "FO4SFBorder.dll")
MAX_INI = 64 * 1024


def parse(raw):
    """The shared runtime_dir.h syntax, with strict UTF-8 validation too."""
    if len(raw) > MAX_INI:
        raise sr.BindingError("runtime INI file too large")
    if b"\0" in raw:
        raise sr.BindingError("runtime INI has a NUL byte; UTF-8 is required")
    text = raw.decode("utf-8-sig")
    active = seen = False
    values = []
    for line in text.split("\n"):
        line = line.removesuffix("\r").strip(" \t")
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise sr.BindingError("runtime INI has a malformed section")
            active = line[1:-1].strip(" \t").lower() == "runtime"
            seen |= active
        elif active:
            if "=" not in line:
                raise sr.BindingError("runtime INI line without '='")
            key, value = line.split("=", 1)
            if key.strip(" \t").lower() == "dir":
                values.append(value.strip(" \t"))
    if not seen:
        raise sr.BindingError("runtime INI has no [Runtime] section")
    if not values:
        raise sr.BindingError("runtime INI has no Dir=")
    if len(values) != 1:
        raise sr.BindingError("runtime INI has more than one Dir=")
    value = values[0]
    if not value:
        raise sr.BindingError("runtime Dir is empty")
    seps = "\\/"
    if len(value) >= 3 and value[0].isascii() and value[0].isalpha() and value[1] == ":" and value[2] in seps:
        tail = value[3:]
    elif len(value) >= 5 and value[0] in seps and value[1] in seps and value[2] not in seps:
        tail = value[2:]
        split = min((i for i, c in enumerate(tail) if c in seps), default=-1)
        if split < 0 or split + 1 >= len(tail) or tail[split + 1] in seps:
            raise sr.BindingError("runtime Dir is not absolute (UNC needs server and share)")
    else:
        raise sr.BindingError("runtime Dir is not absolute (Windows drive or UNC required)")
    if any(ord(c) < 32 or ord(c) == 127 or c in '<>:"|?*' for c in tail):
        raise sr.BindingError("runtime Dir has a character Windows refuses")
    if any(p in (".", "..") for p in re.split(r"[\\/]", tail)):
        raise sr.BindingError("runtime Dir must be resolved without . or .. components")
    return value


def encode(directory):
    raw = f"[Runtime]\nDir={directory}\n".encode("utf-8")
    if parse(raw) != directory:
        raise sr.BindingError("runtime Dir would change when parsed")
    return raw


def _path(value):
    # Reject dot components before Path/abspath can discard them.
    if not value or any(p in (".", "..") for p in re.split(r"[\\/]", str(value))):
        raise sr.BindingError("confirm a resolved absolute folder without . or .. components")
    path = Path(value)
    if not path.is_absolute():
        raise sr.BindingError("confirm an absolute folder")
    return path


def _safe(path, *, directory=False, optional=False):
    """No redirected component, special file, or multiply linked file; no mkdir."""
    path = _path(path)
    chain = list(reversed(path.parents)) + [path]
    for component in chain:
        try:
            info = component.lstat()
        except FileNotFoundError:
            if component == path and optional:
                return None
            raise sr.BindingError(f"{component}: required folder is missing") from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise sr.BindingError(f"{component}: linked or reparse path; nothing written")
        if component != path or directory:
            if not stat.S_ISDIR(info.st_mode):
                raise sr.BindingError(f"{component}: expected a folder")
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise sr.BindingError(f"{component}: config/receipt is not a private regular file")
    return info


def _read(path):
    if _safe(path, optional=True) is None:
        return None
    return ri.read(path)


def _directory_id(path):
    info = _safe(path, directory=True)
    return info.st_dev, info.st_ino, info.st_mode


def _runtime_dir(saves):
    # On Windows this is the already confirmed absolute drive/UNC spelling.
    # Linux cannot manufacture a Windows Documents location.
    return str(saves / "FO4SF-Runtime")


def ownership(value):
    sr._keys(value, ("schema", "complete", "ini", "previous"), "runtime config ownership")
    if type(value["schema"]) is not int or value["schema"] != 1 or type(value["complete"]) is not bool:
        raise sr.BindingError("unknown runtime config ownership schema/state")
    sr._identity_fields(value["ini"])
    if value["previous"] is not None:
        sr._identity_fields(value["previous"])
    if value["complete"] and value["previous"] is not None:
        raise sr.BindingError("complete runtime config has pending previous identity")
    return value


def prepare(values, starfield, *, resume=False, required=False):
    root = Path(starfield)
    target = root.joinpath(*RELATIVE)
    receipt_path = root / instance.RECORD
    # Legacy unmanaged installs without runtime consumers/config keep their old path.
    # Managed releases always require the gate, even without an installed optional DLL.
    receipt_raw = _read(receipt_path) if os.path.lexists(receipt_path) else None
    receipt = ri.decode(receipt_raw) if receipt_raw is not None else {}
    if not isinstance(receipt, dict):
        raise sr.BindingError("instance receipt is not an object")
    needed = (required or ri.FIELD in receipt or FIELD in receipt or os.path.lexists(target)
              or any(os.path.lexists(target.parent / name) for name in CONSUMERS))
    if not needed:
        return None
    root = _path(starfield)
    confirmed = _path(values.get("instance", ""))
    if os.path.normcase(str(root)) != os.path.normcase(str(confirmed)):
        raise sr.BindingError("runtime config needs the confirmed FO4SF instance; target differs")
    if type(receipt.get("schema")) is not int or receipt.get("schema") != instance.SCHEMA or receipt.get("complete") is not True:
        raise sr.BindingError("runtime config needs a complete known instance receipt")
    instance.check_ready(str(root))
    reason = recovery.play_reason(str(root))
    if reason:
        raise sr.BindingError(reason)
    if ri.FIELD in receipt:
        ri.installed(root)  # do not publish through an incomplete release transaction
    my_games = _path(values.get("my_games", ""))
    problems = instance.custom_ini_problems(str(my_games), values)
    if problems:
        raise sr.BindingError(problems[0])
    saves = my_games / "Saves" / "FO4SF"
    dirs = list(dict.fromkeys([*reversed(root.parents), root, root / "Data", root / "Data" / "SFSE", target.parent,
                              *reversed(saves.parents), saves]))
    guards = {p: _directory_id(p) for p in dirs}
    _safe(saves / "FO4SF-Runtime", directory=True, optional=True)
    for parent, name in ((target.parent, NAME), (root, instance.RECORD)):
        aliases = [p.name for p in parent.iterdir() if p.name.casefold() == name.casefold()]
        if len(aliases) > 1 or (aliases and aliases != [name]):
            raise sr.BindingError(f"{name}: ambiguous config/receipt spelling")
    raw = encode(_runtime_dir(saves))
    old_raw = _read(target)
    owned = ownership(receipt[FIELD]) if FIELD in receipt else None
    previous = None
    if owned is None:
        if old_raw is not None:
            raise sr.BindingError("unowned runtime INI exists; preserve it, nothing overwritten")
    elif owned["complete"]:
        if old_raw is None or ri.pin(old_raw) != owned["ini"]:
            raise sr.BindingError("owned runtime INI missing or changed; preserve ownership")
        previous = owned["ini"]
    else:
        if not resume:
            raise sr.BindingError("runtime config publication incomplete; repeat configure-runtime --apply with the same settings")
        if owned["ini"] != ri.pin(raw):
            raise sr.BindingError("different runtime config is pending; restore its original settings")
        previous = owned["previous"]
        if (None if old_raw is None else ri.pin(old_raw)) not in (previous, owned["ini"]):
            raise sr.BindingError("pending runtime INI has unknown bytes; preserve ownership")
    return {"root": root, "target": target, "receipt_path": receipt_path, "receipt": receipt,
            "receipt_raw": receipt_raw, "raw": raw, "old_raw": old_raw, "previous": previous,
            "owned": owned, "guards": guards, "saves": saves}


def _guard(plan, running):
    if running() is not False:
        raise sr.BindingError("close Starfield before runtime config publication (unknown state also refuses)")
    if any(_directory_id(p) != identity for p, identity in plan["guards"].items()):
        raise sr.BindingError("runtime config folder changed during publication")
    _safe(plan["saves"] / "FO4SF-Runtime", directory=True, optional=True)
    if _read(plan["receipt_path"]) != plan["receipt_raw"]:
        raise sr.BindingError("instance ownership changed during runtime publication")


def _write(plan, path, raw, expected, running):
    _guard(plan, running)
    if _read(path) != expected:
        raise sr.BindingError(f"{path.name}: changed during runtime publication; nothing replaced")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".part", dir=path.parent)
    temporary_info = os.fstat(fd)
    try:
        with os.fdopen(fd, "wb") as stream:
            _guard(plan, running)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _guard(plan, running)
        if _read(path) != expected:
            raise sr.BindingError(f"{path.name}: changed during runtime publication; nothing replaced")
        os.replace(temporary, path)
    finally:
        # A renamed/redirected parent may now name somebody else's file. Clean
        # only our still-private temporary inode through an unchanged real path.
        try:
            current = _safe(Path(temporary), optional=True)
            if current is not None and (current.st_dev, current.st_ino) == (temporary_info.st_dev, temporary_info.st_ino):
                os.unlink(temporary)
        except (OSError, ValueError):
            pass


def publish(values, starfield, *, running, apply=False, resume=False, required=False, say=print):
    """Preview or publish, preserving unrelated receipt fields and unowned bytes."""
    plan = prepare(values, starfield, resume=resume, required=required)
    if plan is None:
        return None
    _guard(plan, running)
    say(f"Runtime config: {plan['target']} -> launcher-resolved {parse(plan['raw'])}")
    if not apply:
        return None
    if plan["owned"] is not None and plan["owned"]["complete"] and plan["old_raw"] == plan["raw"]:
        verify(plan, running)
        return plan
    pending = dict(plan["receipt"], **{FIELD: {"schema": 1, "complete": False,
                                             "ini": ri.pin(plan["raw"]), "previous": plan["previous"]}})
    pending_raw = ri.encode(pending)
    _write(plan, plan["receipt_path"], pending_raw, plan["receipt_raw"], running)
    plan["receipt_raw"] = pending_raw
    if _read(plan["receipt_path"]) != pending_raw:
        raise sr.BindingError("runtime config ownership changed; publication remains pending")
    _write(plan, plan["target"], plan["raw"], plan["old_raw"], running)
    _guard(plan, running)
    if _read(plan["target"]) != plan["raw"]:
        raise sr.BindingError("runtime INI changed; publication remains pending")
    complete = dict(pending, **{FIELD: {"schema": 1, "complete": True, "ini": ri.pin(plan["raw"]), "previous": None}})
    final_raw = ri.encode(complete)
    _write(plan, plan["receipt_path"], final_raw, pending_raw, running)
    plan["receipt_raw"] = final_raw
    verify(plan, running)
    return plan


def verify(plan, running):
    """Last comparison before start; also used when publication was already complete."""
    if plan is None:
        return
    _guard(plan, running)
    if _read(plan["receipt_path"]) != plan["receipt_raw"] or _read(plan["target"]) != plan["raw"]:
        raise sr.BindingError("runtime config or instance changed before launch; preserve both")
