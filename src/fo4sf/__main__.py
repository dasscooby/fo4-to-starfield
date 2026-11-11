"""Minimal CLI for fo4-to-starfield.

python -m fo4sf status    # print config summary (including directory existence) and optional manifest coverage
python -m fo4sf validate  # check paths, tools, and dependencies (PYTHONPATH=src)
python -m fo4sf nif-summary <paths>  # summarize NIF block structure for conversion diagnostics
python -m fo4sf bgsm-summary <files>  # offline summary of Fallout 4 .bgsm materials
python -m fo4sf dds-summary <files>   # DDS header summary (needs numpy)
python -m fo4sf btd-summary <files>   # Starfield .btd terrain summary (needs numpy)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from .config import ConfigError, load_config
from .manifest import ManifestError, load_manifest, summarize_manifest
from .nif import NifError, parse as parse_nif
from .convert_material import parse_bgsm

MIN_PYTHON = (3, 12)


def cmd_status(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    print("fo4-to-starfield status")
    print(f"  config: {Path(args.config or 'config.toml').resolve()}")
    root = _repo_root()
    if root:
        print(f"  repo: {root}")
        # best-effort branch name
        try:
            import subprocess
            br = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
            print(f"  branch: {br}")
        except Exception:
            pass
    fo4 = cfg.get("fo4", {})
    data_dirs = fo4.get("data_dirs", [])
    print(f"  Fallout 4 data dirs: {len(data_dirs)} configured")
    for i, d in enumerate(data_dirs):
        if d is None:
            print(f"    [{i}] (blank) (MISSING)")
            continue
        exists = d.is_dir() if isinstance(d, Path) else Path(d).is_dir()
        print(f"    [{i}] {d} ({'exists' if exists else 'MISSING'})")
    sf = cfg.get("starfield", {})
    sf_dir = sf.get("data_dir")
    if sf_dir:
        exists = sf_dir.is_dir() if isinstance(sf_dir, Path) else Path(sf_dir).is_dir()
        print(f"  Starfield data dir: {sf_dir} ({'exists' if exists else 'MISSING'})")
    else:
        print("  Starfield data dir: missing")
    paths = cfg.get("paths", {})
    for key in ("work_dir", "staging_dir"):
        d = paths.get(key)
        if d:
            exists = d.is_dir() if isinstance(d, Path) else Path(d).is_dir()
            print(f"  {key}: {d} ({'exists' if exists else 'MISSING or not created'})")
        else:
            print(f"  {key}: missing")

    if args.manifest:
        return _print_manifest(Path(args.manifest))

    # Optional auto-discovery in staging_dir or work_dir
    for key in ("staging_dir", "work_dir"):
        d = paths.get(key)
        if d:
            cand = Path(d) / "manifest.json"
            if cand.is_file():
                return _print_manifest(cand)
    print("  Manifest: not found (run a conversion stage to generate one)")
    return 0


def _print_manifest(manifest_path: Path) -> int:
    try:
        items = load_manifest(manifest_path)
    except ManifestError as e:
        print(f"  manifest error: {e}", file=sys.stderr)
        return 1
    summary = summarize_manifest(items)
    print(f"\n  Manifest: {manifest_path} ({summary['total']} items)")
    if summary["by_type"]:
        print("  By type:")
        for k, v in sorted(summary["by_type"].items()):
            print(f"    {k}: {v}")
    if summary["by_tier"]:
        print("  By fidelity tier:")
        for k, v in sorted(summary["by_tier"].items()):
            print(f"    {k}: {v}")
    return 0


def _repo_root() -> Path | None:
    """This checkout's root, when running from one (config paths must stay outside it: no game data in Git)."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / ".git").exists() and (root / "src" / "fo4sf").is_dir() else None


def _inside(p: Path, root: Path | None) -> bool:
    if root is None:
        return False
    a, b = os.path.normcase(str(Path(p).resolve())), os.path.normcase(str(root))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:   # different drives
        return False


def _nearest_existing(p: Path) -> Path:
    """The closest ancestor of p that exists (a missing output dir is created under it)."""
    for parent in p.parents:
        if parent.exists():
            return parent
    return Path(p.anchor or ".")


def _writable_dir(d: Path) -> bool:
    """Whether a file can be created in d: a real probe, since os.access ignores W_OK for Windows directories."""
    try:
        with tempfile.TemporaryFile(dir=d):
            return True
    except OSError:
        return False


def _is_executable_file(path, *, windows: bool = os.name == "nt") -> bool:
    """A regular file the OS will run: PATHEXT on Windows (os.access ignores X_OK there), the execute bit elsewhere."""
    p = Path(path)
    if not p.is_file():
        return False
    if windows:
        exts = {e.strip().lower() for e in (os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD").split(";") if e.strip()}
        return p.suffix.lower() in exts
    return os.access(p, os.X_OK)


def _texconv_near_xedit(xedit) -> str | None:
    """docs/SETUP.md: texconv is the copy in xEdit's Edit Scripts folder, next to the configured xSFEdit."""
    if not xedit:
        return None
    for name in ("texconv.exe", "Texconvx64.exe", "texconv"):
        cand = Path(xedit).parent / "Edit Scripts" / name
        if cand.is_file():
            return str(cand)
    return None


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate config, paths, and common tools for the conversion toolchain."""
    try:
        cfg = load_config(args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1

    print("fo4-to-starfield validate")
    ok = True
    repo = _repo_root()

    fo4 = cfg.get("fo4", {})
    data_dirs = fo4.get("data_dirs", [])
    print(f"  Fallout 4 data dirs ({len(data_dirs)}):")
    if not data_dirs:
        print("    none configured")
        ok = False
    for d in data_dirs:
        if d is None:
            print("    (blank entry): NOT FOUND")
            ok = False
            continue
        p = Path(d)
        if _inside(p, repo):
            print(f"    {d}: inside the repository (must be outside it)")
            ok = False
        elif p.is_dir():
            print(f"    {d}: exists")
        else:
            print(f"    {d}: NOT FOUND")
            ok = False

    sf = cfg.get("starfield", {})
    sf_dir = sf.get("data_dir")
    if sf_dir:
        p = Path(sf_dir)
        if _inside(p, repo):
            print(f"  Starfield data dir: {sf_dir}: inside the repository (must be outside it)")
            ok = False
        elif p.is_dir():
            print(f"  Starfield data dir: {sf_dir}: exists")
        else:
            print(f"  Starfield data dir: {sf_dir}: NOT FOUND")
            ok = False
    else:
        print("  Starfield data dir: missing in config")
        ok = False

    paths = cfg.get("paths", {})
    for key in ("work_dir", "staging_dir"):
        d = paths.get(key)
        if not d:
            print(f"  {key}: missing in config")
            ok = False
            continue
        p = Path(d)
        if _inside(p, repo):
            print(f"  {key}: {d}: inside the repository (must be outside it)")
            ok = False
        elif p.is_dir() and _writable_dir(p):
            print(f"  {key}: {d}: exists")
        elif p.is_dir():
            print(f"  {key}: {d}: exists but is not writable")
            ok = False
        elif p.exists():
            print(f"  {key}: {d}: not a directory")
            ok = False
        else:
            parent = _nearest_existing(p)
            if not parent.is_dir():
                print(f"  {key}: {d}: cannot be created ({parent} is not a directory)")
                ok = False
            elif not _writable_dir(parent):
                print(f"  {key}: {d}: cannot be created ({parent} is not writable)")
                ok = False
            else:
                print(f"  {key}: {d}: NOT FOUND (will be created by tools)")

    print("  Tools:")
    configured = set(cfg.get("tools", {}))
    tools = {
        "texconv": (shutil.which("texconv") or shutil.which("Texconvx64")
                    or _texconv_near_xedit(cfg.get("tools", {}).get("xsfedit"))),
        "python": sys.executable,
    }
    if "tools" in cfg:
        for name, path in cfg["tools"].items():
            tools[name] = path
    for name, path in tools.items():
        if path and _is_executable_file(path):
            print(f"    {name}: found at {path}")
        elif path and Path(path).exists():
            print(f"    {name}: not an executable file at {path}")
            ok = False
        elif path:
            print(f"    {name}: configured but NOT FOUND at {path}")
            ok = False
        elif name in configured:
            print(f"    {name}: configured but blank")
            ok = False
        else:
            print(f"    {name}: not found in PATH" + (" or xEdit's Edit Scripts" if name == "texconv" else ""))
            if name == "texconv":
                print("      (required for texture conversion)")
                ok = False

    version = ".".join(str(n) for n in sys.version_info[:3])
    if sys.version_info >= MIN_PYTHON:   # docs/SETUP.md requires 3.12+
        print(f"  Python version: {version}")
    else:
        print(f"  Python version: {version} (needs {'.'.join(map(str, MIN_PYTHON))} or newer)")
        ok = False

    print("  Python packages:")
    for display, module in (("numpy", "numpy"), ("Pillow", "PIL")):
        try:
            __import__(module)
            print(f"    {display}: available")
        except ImportError:
            print(f"    {display}: MISSING (pip install {display})")
            ok = False

    if ok:
        print("\n  Validation: OK")
        return 0
    print("\n  Validation: FAILED (see above)", file=sys.stderr)
    return 1


def cmd_nif_summary(args: argparse.Namespace) -> int:
    """Print a short structural summary of one or more NIF files (offline diagnostic)."""
    if not args.paths:
        print("error: at least one NIF path required", file=sys.stderr)
        return 1
    ok = True
    results = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_file():
            print(f"error: {path}: not a file", file=sys.stderr)
            ok = False
            continue
        try:
            data = path.read_bytes()
            nif = parse_nif(data)
            summary = nif.summary()
            summary["path"] = str(path)
            results.append(summary)
        except NifError as e:
            print(f"error: {path}: {e}", file=sys.stderr)
            ok = False
        except Exception as e:
            print(f"error: {path}: unexpected {type(e).__name__}: {e}", file=sys.stderr)
            ok = False
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for s in results:
            print(f"{s['path']}")
            print(f"  BS version: {s['bs_version']}")
            print(f"  Blocks: {s['blocks']}  Types: {s['block_types']}  Strings: {s['strings']}")
            if s["type_counts"]:
                top = sorted(s["type_counts"].items(), key=lambda kv: -kv[1])[:8]
                print("  Top types: " + ", ".join(f"{t}={c}" for t, c in top))
            print(f"  Footer: {s['footer_bytes']} bytes")
    return 0 if ok else 1


def cmd_bgsm_summary(args: argparse.Namespace) -> int:
    """Print a short offline summary of one or more .bgsm material files."""
    rc = 0
    for path_str in args.paths:
        p = Path(path_str)
        if not p.is_file():
            print(f"missing: {path_str}", file=sys.stderr)
            rc = 1
            continue
        try:
            data = p.read_bytes()
            mat = parse_bgsm(data)
        except Exception as e:  # noqa: BLE001 — diagnostic CLI reports any parse failure
            print(f"{p.name}: parse error: {e}", file=sys.stderr)
            rc = 1
            continue
        print(f"{p.name}: v{mat.version}  tile_u={mat.tile_u} tile_v={mat.tile_v}")
        print(f"  uv_offset={mat.uv_offset}  uv_scale={mat.uv_scale}")
        print(f"  diffuse={mat.diffuse or '(none)'}")
        print(f"  normal={mat.normal or '(none)'}")
        print(f"  smooth_spec={mat.smooth_spec or '(none)'}")
        flags = []
        if mat.alpha_blend:
            flags.append("alpha_blend")
        if mat.alpha_test:
            flags.append(f"alpha_test(ref={mat.alpha_ref})")
        if mat.decal:
            flags.append("decal")
        if mat.two_sided:
            flags.append("two_sided")
        if mat.palette_color:
            flags.append(f"palette_color(scale={mat.palette_scale})")
        print(f"  flags: {', '.join(flags) or 'none'}")
        if mat.version == 2:
            print(f"  smoothness={mat.smoothness:.3f}  spec_mult={mat.spec_mult:.3f}")
    return rc


def _fourcc_text(fourcc: bytes) -> str:
    """Plain-text FourCC. An all-zero or NUL-padded field is '(none)', not embedded NULs."""
    text = fourcc.replace(b"\x00", b"").decode("ascii", errors="replace").strip()
    return text or "(none)"


def cmd_dds_summary(args: argparse.Namespace) -> int:
    """Report DDS header info for one or more texture files (offline diagnostic)."""
    # textures imports numpy. Keep that off the process until this command runs,
    # so status / validate / --help still work when numpy is not installed.
    try:
        from . import textures
    except ImportError as e:
        print(f"dds-summary needs numpy ({e})", file=sys.stderr)
        return 1
    paths = [Path(p) for p in args.paths]
    ok = True
    for path in paths:
        if not path.is_file():
            print(f"missing: {path}", file=sys.stderr)
            ok = False
            continue
        try:
            data = path.read_bytes()
            hdr = textures.read_dds_header(data)
            four = _fourcc_text(hdr["fourcc"])
            dxgi = hdr["dxgi"]
            dxgi_s = f" DXGI={dxgi}" if dxgi is not None else ""
            print(f"{path}: {hdr['width']}x{hdr['height']} mips={hdr['mips']} fourCC={four}{dxgi_s} data_off={hdr['data_offset']}")
        except Exception as e:
            print(f"{path}: error {e}", file=sys.stderr)
            ok = False
    return 0 if ok else 1


def cmd_btd_summary(args: argparse.Namespace) -> int:
    """Print a short structural summary of one or more Starfield .btd terrain files (offline diagnostic)."""
    # btd imports numpy. Same rule as dds-summary: load it only when this command runs.
    try:
        from .btd import BtdError, read as read_btd
    except ImportError as e:
        print(f"btd-summary needs numpy ({e})", file=sys.stderr)
        return 1
    if not args.paths:
        print("error: at least one BTD path required", file=sys.stderr)
        return 1
    ok = True
    results = []
    for raw in args.paths:
        path = Path(raw)
        if not path.is_file():
            print(f"error: {path}: not a file", file=sys.stderr)
            ok = False
            continue
        try:
            data = path.read_bytes()
            btd = read_btd(data)
            summary = {
                "path": str(path),
                "version": btd.version,
                "height_min_m": btd.hmin,
                "height_max_m": btd.hmax,
                "cells_x": btd.ncx,
                "cells_y": btd.ncy,
                "ltex_count": len(btd.ltex),
                "raw_height_range": [int(btd.heights_raw.min()), int(btd.heights_raw.max())],
            }
            results.append(summary)
        except BtdError as e:
            print(f"error: {path}: {e}", file=sys.stderr)
            ok = False
        except Exception as e:
            print(f"error: {path}: unexpected {type(e).__name__}: {e}", file=sys.stderr)
            ok = False
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for s in results:
            print(f"{s['path']}")
            print(f"  Version: {s['version']}")
            print(f"  Height range: {s['height_min_m']:.2f} .. {s['height_max_m']:.2f} m")
            print(f"  Cells: {s['cells_x']} x {s['cells_y']}")
            print(f"  LTEX FormIDs: {s['ltex_count']}")
            print(f"  Raw height samples: {s['raw_height_range'][0]} .. {s['raw_height_range'][1]}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fo4sf", description="Fallout 4 → Starfield conversion tools")
    parser.add_argument("--config", help="path to config.toml (default: ./config.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="show configuration summary (with dir existence), and manifest coverage")
    p_status.add_argument("--manifest", help="explicit path to manifest.json")
    p_status.set_defaults(func=cmd_status)

    p_validate = sub.add_parser("validate", help="validate config paths, tools, and dependencies")
    p_validate.set_defaults(func=cmd_validate)

    p_nif = sub.add_parser("nif-summary", help="summarize NIF block structure (offline diagnostic)")
    p_nif.add_argument("paths", nargs="+", help="NIF file paths")
    p_nif.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p_nif.set_defaults(func=cmd_nif_summary)

    p_bgsm = sub.add_parser("bgsm-summary", help="offline summary of Fallout 4 .bgsm materials")
    p_bgsm.add_argument("paths", nargs="+", help="one or more .bgsm files")
    p_bgsm.set_defaults(func=cmd_bgsm_summary)

    p_dds = sub.add_parser("dds-summary", help="summarize DDS texture headers (width, height, format)")
    p_dds.add_argument("paths", nargs="+", help="one or more .dds files")
    p_dds.set_defaults(func=cmd_dds_summary)

    p_btd = sub.add_parser("btd-summary", help="summarize Starfield .btd terrain files (version, height range, cell grid, LTEX count)")
    p_btd.add_argument("paths", nargs="+", help="one or more .btd files")
    p_btd.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p_btd.set_defaults(func=cmd_btd_summary)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
