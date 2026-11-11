"""Read-only Tests catalog. Kit data never supplies commands or claims installation ownership."""
import json
import ntpath
import os
import re
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
    with open(path, "rb") as stream:
        raw = stream.read(16385)
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


def list_kits(starfield, registered, plugins_txt, repo):
    """Stable rows for staged or recorded kits, including broken/orphaned installs.

    A bad receipt is visible and prevents an active claim. Existence alone never proves
    ownership or a healthy install. This function writes nothing, including on failures.
    """
    if set(registered) - BY_KEY.keys():
        raise ValueError("Unknown test kit in registry")
    data = os.path.join(starfield, "Data")
    active, plugin_error = set(), ""
    if not plugins_txt:
        plugin_error = "Cannot find this profile's Plugins.txt"
    else:
        try:
            with open(plugins_txt, encoding="utf-8-sig") as stream:
                active = {line.strip()[1:].strip().casefold() for line in stream
                          if line.strip().startswith("*")}
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError):
            plugin_error = "Cannot read this profile's Plugins.txt"
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
                     "installer_available": os.path.isfile(os.path.join(repo, kit.installer)),
                     "card_available": bool(stage) and os.path.isfile(os.path.join(stage, CARD))})
    return rows
