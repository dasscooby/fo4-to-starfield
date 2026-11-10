"""Read-only per-save release contract (FAL-247 item 7, part 1).

Saves are opaque bytes. No save headers are parsed, migrated or adopted. A future
publisher must establish that a newly produced save belongs to the running release;
snapshot_binding only captures bytes and is not itself proof of that provenance.
An instance-owned declaration activates a read-only profile gate. Binding publication
remains a later part of item 7; legacy instances are not retroactively adopted.
"""
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA = 1
MAX_METADATA_BYTES = 1 << 20
SHA = re.compile(r"[0-9a-f]{64}")
RELEASE_FILE = "FO4SF.release.json"
BINDING_SUFFIX = ".fo4sf-release.json"
MAX_PROFILE_SAVES = 4096


class BindingError(ValueError):
    pass


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and not any(c in value for c in "\0\r\n")


def _name(value):
    if not _text(value) or value in (".", "..") or any(c in value for c in "/\\:"):
        raise BindingError("invalid file/component name")
    return value


def _keys(value, expected, what):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise BindingError(f"{what}: missing or unknown fields")


def _number(value):
    return type(value) is int and value >= 0


def _identity_fields(value):
    _keys(value, ("sha256", "size"), "file identity")
    if not isinstance(value["sha256"], str) or not SHA.fullmatch(value["sha256"]) or not _number(value["size"]):
        raise BindingError("invalid file identity")
    return dict(value)


def declaration(value):
    """Validated, independent copy. Master order matters; Windows name casing does not."""
    _keys(value, ("schema", "release_id", "masters", "state_layouts"), "release declaration")
    if type(value["schema"]) is not int or value["schema"] != SCHEMA or not _text(value["release_id"]):
        raise BindingError("unknown release schema or missing release id")
    if not isinstance(value["masters"], list) or not value["masters"]:
        raise BindingError("release needs ordered master identities")
    masters, seen = [], set()
    for master in value["masters"]:
        _keys(master, ("name", "sha256", "size"), "master")
        name = _name(master["name"]).casefold()
        if not name.endswith((".esm", ".esp", ".esl")) or name in seen:
            raise BindingError("invalid or duplicate master name")
        seen.add(name)
        masters.append(dict(_identity_fields({k: master[k] for k in ("sha256", "size")}), name=name))
    if not isinstance(value["state_layouts"], dict):
        raise BindingError("state layouts must be an object")
    layouts, seen = {}, set()
    for component, layout in value["state_layouts"].items():
        _name(component)
        if component.casefold() in seen:
            raise BindingError("duplicate state component")
        seen.add(component.casefold())
        _keys(layout, ("format", "envelope_schema", "payload_schema"), "state layout")
        if (not _text(layout["format"]) or not _text(layout["payload_schema"])
                or not _number(layout["envelope_schema"])):
            raise BindingError("invalid envelope or payload schema identity")
        layouts[component.casefold()] = dict(layout)
    return {"schema": SCHEMA, "release_id": value["release_id"], "masters": masters, "state_layouts": layouts}


def compatibility(value):
    """A patch release can keep compatibility inputs while retaining its own release id."""
    value = declaration(value)
    value.pop("release_id")
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _relative(value):
    if not _text(value):
        raise BindingError("invalid state path")
    for part in value.split("/"):
        _name(part)
    return value


def _inside(root, relative):
    relative = _relative(relative)
    root = Path(root).resolve()
    path = root
    for part in relative.split("/"):
        path = path / part
        if path.is_symlink():
            raise BindingError("state/master path is a link")
    if os.path.commonpath((str(root), str(path.resolve()))) != str(root):
        raise BindingError("state/master path escapes its root")
    return path


def identity(path):
    """Hash an opaque file; refuse a publication/change observed during the read."""
    path = Path(path)
    if path.is_symlink():
        raise BindingError("bound file is a link")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    current = path.stat()
    stamp = lambda s: (s.st_size, s.st_mtime_ns, s.st_ino)  # noqa: E731
    if stamp(before) != stamp(after) or stamp(after) != stamp(current):
        raise BindingError("bound file changed while reading")
    return {"size": current.st_size, "sha256": digest.hexdigest()}


def _state_files(value, layouts):
    if not isinstance(value, dict):
        raise BindingError("state files must be an object")
    out, seen, components = {}, set(), set()
    for relative, pin in value.items():
        _relative(relative)
        if relative.casefold() in seen:
            raise BindingError("duplicate state path")
        seen.add(relative.casefold())
        _keys(pin, ("component", "sha256", "size"), "state file")
        component = _name(pin["component"]).casefold()
        components.add(component)
        out[relative] = dict(_identity_fields({k: pin[k] for k in ("sha256", "size")}), component=component)
    if components != set(layouts):
        raise BindingError("state files do not cover the declared state components")
    return out


def snapshot_binding(release, save, state_dir, state_files=None):
    """Capture metadata only; never publishes it or establishes save provenance."""
    release = declaration(release)
    state_files = {} if state_files is None else state_files
    if not isinstance(state_files, dict):
        raise BindingError("state paths must map to components")
    pins = {p: dict(identity(_inside(state_dir, p)), component=c) for p, c in state_files.items()}
    pins = _state_files(pins, release["state_layouts"])
    return {"schema": SCHEMA, "release": release, "save_name": _name(Path(save).name),
            "save_identity": identity(save),
            "state_files": pins}


def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise BindingError("duplicate metadata key")
        out[key] = value
    return out


def _constant(_value):
    raise BindingError("non-finite metadata number")


def read_metadata(path):
    with open(path, "rb") as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    if len(raw) > MAX_METADATA_BYTES:
        raise BindingError("metadata exceeds size limit")
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs, parse_constant=_constant)


def _installed_masters(release, starfield):
    problems = []
    data = Path(starfield) / "Data"
    names = {}
    for path in data.iterdir():
        names.setdefault(path.name.casefold(), []).append(path.name)
    for master in release["masters"]:
        found = names.get(master["name"], [])
        if len(found) != 1:
            problems.append(f"{master['name']}: missing or ambiguous installed master")
        elif identity(_inside(data, found[0])) != {k: master[k] for k in ("size", "sha256")}:
            problems.append(f"{master['name']}: installed bytes differ from release")
    return problems


def _bound_save(release, binding, save, state_dir):
    """Internal binding check; caller must separately verify installed masters."""
    _keys(binding, ("schema", "release", "save_name", "save_identity", "state_files"), "save binding")
    if type(binding["schema"]) is not int or binding["schema"] != SCHEMA:
        raise BindingError("unknown save-binding schema")
    old = declaration(binding["release"])
    _name(binding["save_name"])
    saved_pin = _identity_fields(binding["save_identity"])
    state_files = _state_files(binding["state_files"], old["state_layouts"])
    problems = []
    if release["masters"] != old["masters"]:
        problems.append("required master identities/order changed")
    if release["state_layouts"] != old["state_layouts"]:
        problems.append("required state envelope/payload layout changed")
    if binding["save_name"].casefold() != Path(save).name.casefold() or identity(save) != saved_pin:
        problems.append("save name or bytes differ from its binding")
    for relative, pin in state_files.items():
        if identity(_inside(state_dir, relative)) != {k: pin[k] for k in ("size", "sha256")}:
            problems.append(f"{relative}: state bytes differ from save binding")
    return problems


def check(release, binding, save, starfield, state_dir):
    """Return refusal reasons. No writes and no inference that an unbound save is safe."""
    try:
        release = declaration(release)
        return _bound_save(release, binding, save, state_dir) + _installed_masters(release, starfield)
    except (OSError, ValueError, UnicodeError) as error:
        return [f"save release refused: {error}"]


def check_files(release_path, binding_path, save, starfield, state_dir):
    try:
        return check(read_metadata(release_path), read_metadata(binding_path), save, starfield, state_dir)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        return [f"unbound or unreadable save release: {error}"]


def play_reason(values, starfield):
    """Gate a declared FO4SF instance, including dry runs. Never publish or adopt saves.

    An installer ownership pin makes a missing/changed declaration or interrupted
    publication refuse too. Legacy instances with neither record retain their
    existing behavior; publication never retroactively binds their old saves.
    """
    try:
        from . import release_install
        release = release_install.installed(starfield)
        if release is None:
            return ""
        if not values.get("instance") or not values.get("my_games"):
            raise BindingError("confirm the FO4SF instance and My Games folder before playing this release")
        from . import instance
        overrides = instance.custom_ini_problems(values["my_games"], values)
        if overrides:
            raise BindingError("; ".join(overrides))
        my_games = Path(values["my_games"])
        if not my_games.is_absolute() or not my_games.is_dir():
            raise BindingError("My Games folder is missing or is not absolute")
        from . import release_load
        release_load.check(release, starfield, my_games)
        # This is the launcher-resolved SLocalSavePath, not observed H3 placement.
        saves = my_games / "Saves" / "FO4SF"
        if os.path.normcase(str(saves.resolve())) != os.path.normcase(os.path.abspath(saves)):
            raise BindingError("save folder is redirected; confirm its location before playing")
        runtime = saves / "FO4SF-Runtime"
        if os.path.normcase(str(runtime.resolve())) != os.path.normcase(os.path.abspath(runtime)):
            raise BindingError("runtime folder is redirected; confirm its location before playing")
        problems = _installed_masters(release, starfield)
        if problems:
            raise BindingError(problems[0])
        if not saves.exists():
            return ""  # first run: do not create the folder during a read-only check
        names = set()
        for save in saves.iterdir():
            if save.suffix.casefold() != ".sfs":
                continue
            if save.name.casefold() in names:
                raise BindingError("ambiguous save names")
            names.add(save.name.casefold())
            if len(names) > MAX_PROFILE_SAVES:
                raise BindingError("save inventory exceeds supported limit")
            binding_path = save.with_name(save.name + BINDING_SUFFIX)
            if binding_path.is_symlink():
                raise BindingError(f"{save.name}: binding is a link")
            binding = read_metadata(binding_path)
            problems = _bound_save(release, binding, save, runtime)
            if problems:
                raise BindingError(f"{save.name}: {problems[0]}")
        return ""
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        return (f"Save release check refused: {error}. Keep the saves and their bindings; "
                "restore their matching release before playing. Unbound saves are never adopted automatically.")
