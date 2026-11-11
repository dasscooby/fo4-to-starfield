"""Read-only Tests catalog. Kit data never supplies commands or claims installation ownership."""
import json
import ntpath
import os
import re
import sys
from dataclasses import dataclass

from . import files

CARD = "owner-card.txt"
SAVE_NOTICE = "saves made now will list this test plugin"


@dataclass(frozen=True)
class Kit:
    key: str
    title: str
    receipt: str
    installer: str
    plugin: str


# Installer paths are code-owned, never read from a staged manifest or receipt.
KITS = (
    Kit("planet_probe", "Planet", "FO4SFPlanetProbe.install.json",
        "scripts/planet/planet_probe_install.py", "FO4SFPlanet.esm"),
    Kit("quest_probe", "Quest", "FO4SFQuestProbe.install.json",
        "scripts/questprobe/questprobe_install.py", "FO4SFQuestProbe.esm"),
    Kit("pipboy_probe", "Pip-Boy", "FO4SFPipboyProbe.install.json",
        "scripts/ui/pipboy_probe_install.py", "FO4SFPipboyProbe.esm"),
    Kit("rads_probe", "Radiation", "FO4SFRadsProbe.install.json",
        "scripts/planet/rads_probe_install.py", "FO4SFRadsProbe.esm"),
    Kit("power_armor_probe", "Power armor", "FO4SFPowerArmorProbe.install.json",
        "scripts/planet/power_armor_probe_install.py", "FO4SFPowerArmorProbe.esm"),
)
BY_KEY = {kit.key: kit for kit in KITS}


def registry_path(settings_path):
    return os.path.join(os.path.dirname(os.path.abspath(settings_path)), "launcher_test_kits.json")


def load_registry(path):
    """Only explicitly registered local folders; no home-directory searches or downloads."""
    try:
        with open(path, encoding="utf-8-sig") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("kits"), dict):
        raise ValueError("Unreadable test-kit registry; expected schema 1 and a kits object")
    kits = value["kits"]
    for key, folder in kits.items():
        if key not in BY_KEY:
            raise ValueError(f"Unknown test kit {key!r}")
        if not isinstance(folder, str) or not os.path.isabs(folder):
            raise ValueError(f"Test kit {key}: choose an absolute local stage folder")
    return dict(kits)


def owner_card(folder):
    """Return bounded plain text; the caller displays it, never opens it as an executable."""
    path = os.path.join(folder, CARD)
    if os.path.islink(path):
        raise ValueError("Owner card must be a text file beside the kit, not a link")
    try:
        with open(path, "rb") as stream:
            raw = stream.read(16385)
    except FileNotFoundError:
        raise ValueError("Owner card is missing; ask the PC helper for owner-card.txt beside this kit") from None
    except OSError:
        raise ValueError("Cannot read owner card; ask the PC helper to check the card file") from None
    if len(raw) > 16384:
        raise ValueError("Owner card is too long")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ValueError("Owner card must be UTF-8 text") from None
    if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
        raise ValueError("Owner card contains control characters")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not 2 <= len(lines) <= 9 or re.match(r"\d+\.", lines[0]):
        raise ValueError("Owner card needs a title and one to eight plain steps")
    if any(not re.fullmatch(rf"{i}\. \S.*", line) for i, line in enumerate(lines[1:], 1)):
        raise ValueError("Owner card steps must be numbered 1. through 8. in order")
    return "\n".join(lines) + "\n"


def _relative(name):
    if not isinstance(name, str) or not name or ntpath.isabs(name) or ":" in name:
        raise ValueError("invalid owned file path")
    parts = name.replace("\\", "/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("invalid owned file path")
    return parts


def _installed_problems(record, data):
    if record.get("complete", True) is not True or record.get("cleanup_pending") or "rollback_completed" in record:
        return ["Installation incomplete; choose Recover install"]
    owned = record.get("files")
    if not isinstance(owned, dict) or not owned:
        return ["Install receipt has no owned files; preserve it for the PC helper"]
    problems = []
    for name, digest in owned.items():
        try:
            parts = _relative(name)
            if not isinstance(digest, str) or not re.fullmatch("[0-9a-fA-F]{64}", digest):
                raise ValueError("invalid owned hash")
            path = os.path.join(data, *parts)
            if os.path.commonpath((os.path.realpath(data), os.path.realpath(path))) != os.path.realpath(data):
                raise ValueError("owned file leaves Data")
            if files.sha256(path).lower() != digest.lower():
                problems.append(f"Installed file changed: {name}")
        except (OSError, ValueError) as error:
            problems.append(f"Cannot verify installed file {name}: {error}")
    return problems


def active_plugins(path):
    """Read the selected profile, refusing undecodable/unreadable bytes without edits."""
    if not path:
        raise ValueError("Cannot find this profile's Plugins.txt")
    try:
        with open(path, encoding="utf-8-sig") as stream:
            return {line.strip()[1:].strip().casefold() for line in stream
                    if line.strip().startswith("*")}
    except FileNotFoundError:
        return set()
    except UnicodeError:
        raise ValueError("Cannot read this profile's Plugins.txt: it must be UTF-8. Nothing changed") from None
    except OSError:
        raise ValueError("Cannot read this profile's Plugins.txt; check read permissions. Nothing changed") from None


def list_kits(starfield, registered, plugins_txt, repo):
    """Stable rows for staged or recorded kits, including broken/orphaned installs.

    A bad receipt is visible and prevents an active claim. Existence alone never proves
    ownership or a healthy install. This function writes nothing, including on failures.
    """
    if set(registered) - BY_KEY.keys():
        raise ValueError("Unknown test kit in registry")
    data = os.path.join(starfield, "Data")
    active, plugin_error = set(), ""
    try:
        active = active_plugins(plugins_txt)
    except ValueError as error:
        plugin_error = str(error)
    rows = []
    for kit in KITS:
        record, problems, installed = {}, [], False
        try:
            with open(os.path.join(data, kit.receipt), encoding="utf-8-sig") as stream:
                installed = True
                record = json.load(stream)
            if not isinstance(record, dict) or not record:
                raise ValueError("receipt must be a nonempty object")
            problems.extend(_installed_problems(record, data))
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError, ValueError):
            installed = True
            record = {}
            problems.append("Cannot read install receipt; preserve it for the PC helper")
        if kit.key not in registered and not installed:
            continue
        stage = registered.get(kit.key) or record.get("exp_dir") or record.get("dir") or ""
        if not isinstance(stage, str) or (stage and not os.path.isabs(stage)):
            stage = ""
            problems.append("Install receipt has no usable stage folder")
        plugins = record.get("plugins", [record.get("plugin", kit.plugin)])
        if (not isinstance(plugins, list) or not plugins or
                any(not isinstance(p, str) or not p.lower().endswith((".esm", ".esp", ".esl")) or
                    "/" in p or "\\" in p for p in plugins)):
            plugins = []
            problems.append("Install receipt has no valid plugin list")
        owned = record.get("files")
        if installed and (kit.plugin not in plugins or not isinstance(owned, dict) or
                          any(p not in owned for p in plugins)):
            problems.append("Install receipt does not own every test plugin")
        if installed and plugin_error:
            problems.append(plugin_error)
        if stage and not os.path.isdir(stage):
            problems.append("Stage folder is unavailable; installed kit can still be removed")
        # A missing stage does not change the state of verified installed files.
        health = [p for p in problems if not p.startswith("Stage folder")]
        enabled = installed and not health and bool(plugins) and all(p.casefold() in active for p in plugins)
        rows.append({"key": kit.key, "title": kit.title, "stage": stage, "installed": installed,
                     "state": "installed and active" if enabled else "installed" if installed else "not installed",
                     "problems": problems, "notice": SAVE_NOTICE if installed else "",
                     "installer_available": os.path.isfile(os.path.join(repo, *kit.installer.split("/"))),
                     "card_available": bool(stage) and os.path.isfile(os.path.join(stage, CARD))})
    return rows


def register(path, key, folder):
    """Record a chosen existing local stage; game files are never written here."""
    if key not in BY_KEY:
        raise ValueError("Unknown test kit")
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder) or not os.path.isfile(os.path.join(folder, BY_KEY[key].plugin)):
        raise ValueError("Choose the staged kit folder containing its test plugin")
    registered = load_registry(path)
    registered[key] = folder
    files.save_json(path, {"schema": 1, "kits": registered})


def context(values, environ):
    """The saved target and its profile. Instance lists never use the normal profile."""
    from . import instance
    folder = values["instance"] or values["starfield"]
    if not folder or not os.path.isfile(os.path.join(folder, "Starfield.exe")) or not os.path.isdir(os.path.join(folder, "Data")):
        raise ValueError("Confirm an existing Starfield folder on the Locations tab")
    env = dict(environ)
    if values["instance"]:
        instance.check_ready(folder)
        env = instance.env_for(folder, environ)
    local = env.get("LOCALAPPDATA", "")
    if not local or not os.path.isabs(local):
        raise ValueError("Cannot find this profile's Plugins.txt (LOCALAPPDATA)")
    return os.path.abspath(folder), os.path.join(local, "Starfield", "Plugins.txt"), env


def inventory(settings_path, repo, *, environ=None):
    from . import settings
    values = settings.load(settings_path)
    folder, plugins, _env = context(values, os.environ if environ is None else environ)
    return list_kits(folder, load_registry(registry_path(settings_path)), plugins, repo)


def execute(key, action, settings_path, repo, *, expected_folder, running, run, environ=None):
    """One fixed installer, with fail-closed checks immediately before invocation.

    No builds: install always passes an existing archive to --prepacked. Unsupported
    older installers reject that option rather than silently building an archive.
    """
    from . import recovery, settings
    if key not in BY_KEY or action not in ("install", "remove"):
        raise ValueError("Unknown test kit or action")
    def idle():
        try:
            state = running()
        except Exception as error:
            raise ValueError(f"Cannot check Starfield processes; nothing changed: {error}") from None
        if state is not False:
            raise ValueError("Close Starfield before installing or removing a test kit (unknown state also refuses)")
    idle()
    values = settings.load(settings_path)
    folder, plugins, env = context(values, os.environ if environ is None else environ)
    norm = lambda path: os.path.normcase(os.path.abspath(path))  # noqa: E731
    if not expected_folder or norm(expected_folder) != norm(folder):
        raise ValueError("Saved game location changed; reload the Tests page")
    reason = recovery.play_reason(folder)
    if reason:
        raise ValueError(reason)
    active_plugins(plugins)  # refuse unreadable/unknown encoding before even starting the installer
    records = recovery.inspect(folder)[0]
    registered = load_registry(registry_path(settings_path))
    rows = {row["key"]: row for row in list_kits(folder, registered, plugins, repo)}
    if key not in rows:
        raise ValueError("Test kit is neither staged nor installed; add its stage folder first")
    row, kit = rows[key], BY_KEY[key]
    if not row["installer_available"]:
        raise ValueError("This kit's installer is unavailable in this checkout; ask the PC helper to update it")
    if action == "remove" and not row["installed"]:
        raise ValueError("This test kit is not installed")
    if action == "install" and row["installed"]:
        raise ValueError("This test kit is already installed; remove it before changing its stage")
    argv = [sys.executable, "-I", os.path.join(repo, *kit.installer.split("/")),
            "uninstall" if action == "remove" else "install", "--starfield", folder]
    if action == "install":
        stage = row["stage"]
        if not stage or not os.path.isfile(os.path.join(stage, kit.plugin)):
            raise ValueError("The staged test plugin is missing; ask the PC helper to prepare the kit")
        archive = os.path.join(stage, os.path.splitext(kit.plugin)[0] + " - Main.ba2")
        if not os.path.isfile(archive):
            raise ValueError("The prebuilt test archive is missing; ask the PC helper to prepare it (nothing built)")
        argv += ["--dir", stage, "--prepacked", archive]
    # Hashing/reading inventory can take time; late game, settings, registry or journal
    # changes must not act on the previously selected target.
    idle()
    if settings.load(settings_path) != values or load_registry(registry_path(settings_path)) != registered:
        raise ValueError("Settings or test stages changed; reload the Tests page")
    reason = recovery.play_reason(folder)
    if reason or recovery.inspect(folder)[0] != records:
        raise ValueError(reason or "Installation state changed; reload the Tests page")
    active_plugins(plugins)  # a late encoding/readability change must refuse too
    result = run(argv, cwd=repo, env=env)
    if result.returncode:
        raise ValueError(f"Test {action} stopped (exit {result.returncode}); keep the installer's journal and read its report")
    return 0
