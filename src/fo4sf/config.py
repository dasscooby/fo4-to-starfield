"""Load and validate fo4-to-starfield config.toml.

Uses tomllib (Python 3.11+). Paths are returned as absolute pathlib.Path objects.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore


class ConfigError(ValueError):
    """Raised when config.toml is missing required sections or values."""


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config.toml (or the given path) and return a normalised dict.

    Expected sections: fo4, starfield, paths, tools.
    A missing file, invalid TOML, a known section that is not a table or a known path field of the
    wrong type raises ConfigError. Unknown keys are preserved; non-string tool entries are left as they are.
    """
    if tomllib is None:
        raise ConfigError("tomllib requires Python 3.11+")

    cfg_path = Path(path) if path else Path("config.toml")
    if not cfg_path.is_file():
        raise ConfigError(f"config file not found: {cfg_path}")

    with cfg_path.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:   # callers report ConfigError; a typo must not end in a traceback
            raise ConfigError(f"{cfg_path}: not valid TOML: {e}") from e

    for section in ("fo4", "starfield", "paths", "tools"):
        if section in data and not isinstance(data[section], dict):
            raise ConfigError(f"[{section}] must be a table, found {type(data[section]).__name__}")

    # Normalise known path fields to absolute Paths
    def abs_path(p: Any, key: str) -> Path | None:
        if not isinstance(p, str):   # Path(5) raises TypeError, which callers do not catch
            raise ConfigError(f"{key} must be a path string, found {type(p).__name__}")
        if not p.strip():   # a blank setting stays missing; Path("") would resolve to the cwd
            return None
        return Path(p).expanduser().resolve()

    if "fo4" in data and "data_dirs" in data["fo4"]:
        dirs = data["fo4"]["data_dirs"]
        if not isinstance(dirs, list):   # a bare string would be split into one path per character
            raise ConfigError(f"fo4.data_dirs must be a list of paths, found {type(dirs).__name__}")
        data["fo4"]["data_dirs"] = [abs_path(p, f"fo4.data_dirs[{i}]") for i, p in enumerate(dirs)]
    if "starfield" in data and "data_dir" in data["starfield"]:
        data["starfield"]["data_dir"] = abs_path(data["starfield"]["data_dir"], "starfield.data_dir")
    if "paths" in data:
        for key in ("work_dir", "staging_dir"):
            if key in data["paths"]:
                data["paths"][key] = abs_path(data["paths"][key], f"paths.{key}")
    if "tools" in data:
        for key, val in list(data["tools"].items()):
            if isinstance(val, str):
                data["tools"][key] = abs_path(val, f"tools.{key}")

    return data


def require_section(cfg: dict[str, Any], section: str) -> dict[str, Any]:
    if section not in cfg:
        raise ConfigError(f"missing required section [{section}]")
    return cfg[section]
