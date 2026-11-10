"""Read-only release checks for explicit plugin order and implicit membership.

Uses the existing launcher loader rules; does not infer native load indexes or
parse opaque save files. Native implicit ordering still needs PC evidence.
"""
import hashlib
import os
from pathlib import Path

from ..core import loadset, preflight
from . import detect, instance, loadprobe, save_release as sr


def _loader_text(path):
    if path.is_symlink() or instance._is_link(str(path)):
        raise sr.BindingError(f"{path.name}: loader input is linked")
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            raw = stream.read(sr.MAX_METADATA_BYTES + 1)
            after = os.fstat(stream.fileno())
    except FileNotFoundError:
        return
    if len(raw) > sr.MAX_METADATA_BYTES:
        raise sr.BindingError(f"{path.name}: loader input exceeds metadata limit")
    # Existing reader rules are UTF-8 text. Do not turn unsupported encoding into
    # replacement characters that hide a loader override from those rules.
    if b"\0" in raw:
        raise sr.BindingError(f"{path.name}: unsupported loader text encoding")
    raw.decode("utf-8-sig")
    stamp = lambda s: (s.st_size, s.st_mtime_ns, s.st_ino)  # noqa: E731
    if stamp(before) != stamp(after) or stamp(after) != stamp(path.stat()):
        raise sr.BindingError(f"{path.name}: loader input changed while reading")
    return {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def implicit_inputs(starfield, my_games):
    """Capture supported CCC bytes or explicit absence; not native ordering proof."""
    return {key: _loader_text(sr._inside(folder, "Starfield.ccc"))
            for key, folder in (("game", starfield), ("my_games", my_games))}


def check(release, starfield, my_games):
    release = sr.declaration(release)
    if not my_games or not Path(my_games).is_absolute() or not Path(my_games).is_dir():
        raise sr.BindingError("confirm an absolute existing My Games folder for release load checks")
    root = Path(starfield)
    plugins = sr._inside(root, instance.LOCAL + "/Starfield/Plugins.txt")
    # Do not use read_lines' missing-file => empty convention for a release gate.
    with plugins.open("rb") as stream:
        raw = stream.read(sr.MAX_METADATA_BYTES + 1)
    if len(raw) > sr.MAX_METADATA_BYTES:
        raise sr.BindingError("Plugins.txt exceeds release metadata limit")
    lines = raw.decode("utf-8-sig").splitlines()
    active, seen = [], set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = sr._name(line[1:].strip() if line.startswith("*") else line).casefold()
        if not loadset.is_plugin(name):
            raise sr.BindingError("Plugins.txt contains an unknown entry")
        if name in seen:
            raise sr.BindingError(f"Plugins.txt has duplicate entries for {name}")
        seen.add(name)
        if line.startswith("*"):
            active.append(name)
    implicit = {n.casefold() for n in (loadprobe.builtin_plugins(str(root / "Data")) or {})}
    wanted_implicit = {m["name"] for m in release["masters"] if loadset.built_in(m["name"])}
    if implicit != wanted_implicit:
        raise sr.BindingError("installed built-in master membership differs from release")
    if any(loadset.built_in(n) and n not in implicit for n in active):
        raise sr.BindingError("Plugins.txt activates a missing built-in master")
    wanted = [m["name"] for m in release["masters"] if not loadset.built_in(m["name"])]
    actual = [n for n in active if not loadset.built_in(n)]
    if actual != wanted:
        raise sr.BindingError("active master set/order differs from release; restore its Plugins.txt")
    for folder in (root, Path(my_games)):
        for name in detect.INI_NAMES + detect.LANGUAGE_INIS:
            _loader_text(folder / name)
    if implicit_inputs(root, my_games) != release["implicit_loaders"]:
        raise sr.BindingError("implicit loader configuration differs from release; restore its CCC inputs")
    probe = loadprobe.LoadProbe(str(root), [str(my_games)], str(plugins))
    loaders = preflight.check_loaders(probe)
    if loaders.status != preflight.PASS:
        raise sr.BindingError("release loader configuration refused: " + loaders.detail)


def play_reason(values, starfield):
    """Cheap final recheck after tools may change Plugins.txt; no asset hashing."""
    try:
        from . import release_install
        release = release_install.installed(starfield)
        if release is not None:
            if not values.get("instance"):
                raise sr.BindingError("release load checks require the confirmed FO4SF instance")
            check(release, starfield, values.get("my_games"))
        return ""
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        return f"Save release load check refused: {error}"
