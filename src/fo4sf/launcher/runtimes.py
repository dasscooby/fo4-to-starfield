"""Known-good Starfield runtimes: which Starfield.exe builds the launcher builds and launches against, and the SFSE
files each one needs.

Owner decisions, 2026-10-19: refuse until a runtime is listed as good (LA-15); players keep Steam on "update only
when launched" (LA-16); SFSE is required (NG-1); Steam only for version 1 (RE-12). So detect refuses an unlisted
Starfield.exe, a missing SFSE, and an SFSE whose files are not the ones listed for that runtime.

The table (scripts/launcher_recipes/known_runtimes.json) maps a Starfield.exe sha256 to a label and the SFSE files
measured with it (sfse_loader.exe and every sfse_*.dll next to it, by sha256). Entries come from a real install's
build manifest (`launcher.py runtimes-add --manifest <build manifest> --label <text>`), never made up: no version
number, DLL name or hash is written here by hand.
"""
import os
import hashlib
from pathlib import Path
import re
import stat

from . import files

DEFAULT_TABLE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), "scripts", "launcher_recipes", "known_runtimes.json")
# path parts of a Microsoft Store / Game Pass install (stores.md §6: XboxGames\Starfield\Content; WindowsApps)
STORE_PARTS = ("xboxgames", "windowsapps")


def load_runtimes(path=None):
    path = DEFAULT_TABLE if path is None else path
    if not path or not os.path.isfile(path):
        return {"schema": 1, "runtimes": []}
    from .save_release import read_metadata
    table = read_metadata(path)
    if (not isinstance(table, dict) or type(table.get("schema")) is not int or table["schema"] != 1
            or not isinstance(table.get("runtimes"), list)
            or any(not isinstance(entry, dict) for entry in table["runtimes"])):
        raise ValueError("known runtimes table is malformed")
    return table


def _sha(identity):
    return (identity or {}).get("sha256")


def add_runtime(table, man, label=None):
    """Add the Starfield runtime a build manifest recorded, with the SFSE files it found. Returns 1 if added, 0 if
    that executable is already listed. Refuses a manifest without a hashed Starfield.exe or without SFSE. Without a
    label the exe's own file version names it ("Steam, Starfield.exe <version>")."""
    game = man.get("game") or {}
    exe = _sha((game.get("files") or {}).get("Starfield.exe"))
    if not exe:
        raise ValueError("the manifest records no hashed Starfield.exe (run `launcher.py manifest --starfield ...`)")
    loader = _sha((game.get("files") or {}).get("sfse_loader.exe"))
    dlls = {n: _sha(i) for n, i in sorted((game.get("sfse_dlls") or {}).items()) if _sha(i)}
    if not loader or not dlls:
        raise ValueError("the manifest records no SFSE loader and DLL; SFSE is required (NG-1), so a runtime is "
                         "listed only with the SFSE build that works on it")
    if any(r["exe_sha256"] == exe for r in table["runtimes"]):
        return 0
    version = (game.get("exe_version") or {}).get("file")
    if not label:
        if not version:
            raise ValueError("the manifest records no Starfield.exe version; pass --label")
        label = f"Steam, Starfield.exe {version}"
    table["runtimes"].append({"label": label, "exe_version": version, "exe_sha256": exe,
                              "exe_size": ((game.get("files") or {}).get("Starfield.exe") or {}).get("size"),
                              "sfse": {"loader_sha256": loader, "dlls": dlls}})
    return 1


def match_runtime(table, exe_sha256):
    for r in table["runtimes"]:
        if exe_sha256 and r["exe_sha256"] == exe_sha256:
            return r
    return None


def sfse_problems(runtime, game):
    """[problems] with the installed SFSE against what the listed runtime was measured with."""
    want = runtime.get("sfse") or {}
    out = []
    have_loader = _sha((game.get("files") or {}).get("sfse_loader.exe"))
    if want.get("loader_sha256") and have_loader != want["loader_sha256"]:
        out.append("sfse_loader.exe is not the SFSE build listed for this runtime"
                   if have_loader else "sfse_loader.exe missing")
    have = {n.casefold(): _sha(i) for n, i in (game.get("sfse_dlls") or {}).items()}
    for name, sha in sorted((want.get("dlls") or {}).items()):
        got = have.get(name.casefold())
        if got is None:
            out.append(f"{name} missing (the SFSE build listed for this runtime has it)")
        elif got != sha:
            out.append(f"{name} is not the SFSE build listed for this runtime")
    listed = {n.casefold() for n in (want.get("dlls") or {})}
    for name in sorted(n for n in (game.get("sfse_dlls") or {}) if n.casefold() not in listed):
        out.append(f"{name} is not part of the SFSE build listed for this runtime (another SFSE build left behind?)")
    return out


def store_install(starfield_dir):
    """True when the folder looks like a Microsoft Store / Game Pass install (by its path)."""
    parts = [p.casefold() for p in os.path.abspath(starfield_dir).replace("\\", "/").split("/")]
    return any(p in STORE_PARTS for p in parts)


NATIVE_COMPONENTS = Path(DEFAULT_TABLE).parents[2] / "sfse" / "native_components.json"
_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX40 = re.compile(r"[0-9a-f]{40}")


def _native_table():
    # Source capabilities are shipped source data, never installed DLL identities.
    from .save_release import read_metadata
    table = read_metadata(NATIVE_COMPONENTS)
    if (not isinstance(table, dict) or type(table.get("schema")) is not int or table["schema"] != 1
            or not isinstance(table.get("runtime"), str) or not isinstance(table.get("plugins"), dict)
            or not table["plugins"] or not isinstance(table.get("address_library"), dict)):
        raise ValueError("native source declaration is malformed")
    names = set()
    for name, component in table["plugins"].items():
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_]+\.dll", name)
                or name.casefold() in names or not isinstance(component, dict)
                or type(component.get("required")) is not bool
                or type(component.get("needs_address_library")) is not bool):
            raise ValueError("native source declaration has invalid plugin metadata")
        names.add(name.casefold())
    if not re.fullmatch(r"versionlib-[0-9-]+\.bin", str(table["address_library"].get("file", ""))):
        raise ValueError("native source declaration has invalid Address Library metadata")
    return table


def native_declaration_problems(entry, table=None):
    """Validate measured metadata only. Empty never claims artifact authenticity."""
    table = _native_table() if table is None else table
    if not isinstance(entry, dict):
        return ["native runtime entry is malformed"]
    if "native" not in entry:
        return []
    native = entry["native"]
    if (not isinstance(native, dict) or set(native) - {"schema", "plugins", "address_library"}
            or type(native.get("schema")) is not int or native["schema"] != 1
            or not isinstance(native.get("plugins"), dict)):
        return ["native schema or fields are malformed"]
    out = []
    if entry.get("exe_version") != table["runtime"]:
        out.append("native block runtime differs from the source declaration")
    seen, needs_library = set(), False
    for name, pin in native["plugins"].items():
        if not isinstance(name, str):
            out.append("native plugin name is malformed")
            continue
        if name.casefold() in seen:
            out.append("native plugin names collide ignoring case")
        seen.add(name.casefold())
        source = table["plugins"].get(name)
        if source is None:
            out.append(f"{name}: not one of our dlls")
            continue
        if (not isinstance(pin, dict) or set(pin) != {"runtime", "sha256", "size", "required",
                "needs_address_library", "source_commit", "artifact_receipt"}):
            out.append(f"{name}: missing or unknown identity fields")
            continue
        for key, pattern in (("sha256", _HEX64), ("source_commit", _HEX40)):
            if not isinstance(pin[key], str) or not pattern.fullmatch(pin[key]):
                out.append(f"{name}: invalid {key}")
        if type(pin["size"]) is not int or pin["size"] <= 0:
            out.append(f"{name}: size is not a positive integer")
        if type(pin["required"]) is not bool:
            out.append(f"{name}: required is not true or false")
        if pin["needs_address_library"] is not source["needs_address_library"]:
            out.append(f"{name}: needs_address_library differs from the source")
        if pin["runtime"] != table["runtime"]:
            out.append(f"{name}: runtime differs from the source")
        if not isinstance(pin["artifact_receipt"], str) or not pin["artifact_receipt"].strip():
            out.append(f"{name}: no artifact_receipt")
        needs_library |= source["needs_address_library"]
    library = native.get("address_library")
    if needs_library and library is None:
        out.append("a listed dll needs the Address Library and the block measures none")
    if library is not None:
        if not isinstance(library, dict) or set(library) != {"file", "size", "sha256", "provenance"}:
            out.append("address_library identity fields are malformed")
        else:
            if library["file"] != table["address_library"]["file"]:
                out.append("address_library file differs from the source")
            if not isinstance(library["sha256"], str) or not _HEX64.fullmatch(library["sha256"]):
                out.append("address_library sha256 is malformed")
            if type(library["size"]) is not int or library["size"] <= 0:
                out.append("address_library size is not a positive integer")
            if not isinstance(library["provenance"], str) or not library["provenance"].strip():
                out.append("address_library has no provenance")
    return out


def _native_plain(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        st = part.lstat()
        if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & 0x400:
            raise ValueError("native file path is linked or redirected")
    return path


def _native_identity(path, expected):
    path = _native_plain(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("native path is not a regular file")
    if before.st_size != expected["size"]:
        return False
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if stamp(before) != stamp(os.fstat(stream.fileno())):
            raise ValueError("native file changed before reading")
        count = 0
        for block in iter(lambda: stream.read(1 << 20), b""):
            count += len(block)
            if count > expected["size"]:
                raise ValueError("native file changed while reading")
            digest.update(block)
        after = os.fstat(stream.fileno())
    _native_plain(path)
    if stamp(before) != stamp(after) or stamp(after) != stamp(path.stat()):
        raise ValueError("native file changed while reading")
    return digest.hexdigest() == expected["sha256"]


def native_problems(runtime, starfield, table=None):
    """Read-only installed native gate, shared by detect and every Play route."""
    try:
        table = _native_table() if table is None else table
        problems = native_declaration_problems(runtime, table) if runtime is not None else []
        if problems:
            return problems
        pins = ((runtime or {}).get("native") or {}).get("plugins", {})
        # Resolve Windows case-insensitively even in Linux synthetic fixtures.
        folder = Path(starfield)
        for name in ("Data", "SFSE", "Plugins"):
            _native_plain(folder)
            found = [p for p in folder.iterdir() if p.name.casefold() == name.casefold()]
            if len(found) > 1:
                return ["native folder names collide ignoring case"]
            if not found:
                folder = None
                break
            folder = _native_plain(found[0])
            if not folder.is_dir():
                return ["native plugin folder is not a directory"]
        entries = {}
        if folder is not None:
            for path in folder.iterdir():
                entries.setdefault(path.name.casefold(), []).append(path)
        out, needs_library, uses_native = [], False, False
        for name, source in table["plugins"].items():
            paths = entries.get(name.casefold(), [])
            pin = pins.get(name)
            required = source["required"] or bool(pin and pin["required"])
            uses_native |= required or bool(paths)
            needs_library |= required and source["needs_address_library"]
            if len(paths) > 1:
                out.append(f"{name}: installed names collide ignoring case")
                continue
            if not paths:
                if required:
                    out.append(f"{name} missing (required native component)")
                continue
            if runtime is None or pin is None:
                out.append(f"{name}: no measured identity for this game runtime")
                continue
            if not _native_identity(paths[0], pin):
                out.append(f"{name}: installed bytes differ from the measured release")
            needs_library |= source["needs_address_library"]
        if uses_native and runtime is not None:
            from . import manifest
            out.extend(sfse_problems(runtime, manifest.game_pins(starfield)))
        if needs_library:
            library = ((runtime or {}).get("native") or {}).get("address_library")
            if library is None:
                out.append("Address Library: no measured identity for the installed native components")
            else:
                paths = entries.get(library["file"].casefold(), [])
                if len(paths) != 1:
                    out.append("Address Library file missing or ambiguous")
                elif not _native_identity(paths[0], library):
                    out.append("Address Library bytes differ from the measured release")
        return out
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        return [f"native runtime cannot be verified: {error}"]


def installed_native_problems(starfield):
    """Current game hash chooses the measured table; no allow-unknown escape."""
    try:
        from . import manifest
        game = manifest.game_pins(starfield)
        exe = (game["files"].get("Starfield.exe") or {}).get("sha256")
        return native_problems(match_runtime(load_runtimes(), exe), starfield)
    except (OSError, ValueError, TypeError, KeyError) as error:
        return [f"native runtime cannot be verified: {error}"]
