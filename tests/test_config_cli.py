"""Tests for config loading and CLI (synthetic; no real game paths)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fo4sf.config import ConfigError, load_config
from fo4sf.__main__ import main

try:
    import tomllib
except ImportError:
    tomllib = None

_real_access = os.access


def _exec_ok(*tools):
    """Treat these fake tools as executable: a temp dir may be on a noexec mount, where access(X_OK) always fails."""
    names = {str(t) for t in tools}
    return patch("fo4sf.__main__.os.access",
                 side_effect=lambda p, m, *a, **k: True if str(p) in names else _real_access(p, m, *a, **k))


@unittest.skipUnless(tomllib, "tomllib requires Python 3.11+")
class TestConfig(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(ConfigError):
            load_config("/nonexistent/config.toml")

    def test_load_example_structure(self):
        # Write a minimal synthetic config
        with tempfile.TemporaryDirectory() as td:
            cfg_path = Path(td) / "config.toml"
            cfg_path.write_text(
                """
[fo4]
data_dirs = ["/tmp/fo4"]
version = "1.10.163"

[starfield]
data_dir = "/tmp/sf"
version = "1.16.244"

[paths]
work_dir = "/tmp/work"
staging_dir = "/tmp/staging"
"""
            )
            cfg = load_config(cfg_path)
            self.assertEqual(len(cfg["fo4"]["data_dirs"]), 1)
            self.assertTrue(str(cfg["paths"]["work_dir"]).endswith("work"))


@unittest.skipUnless(tomllib, "tomllib requires Python 3.11+")
class TestCLI(unittest.TestCase):
    def test_status_missing_config(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            os.chdir(td)
            try:
                rc = main(["status"])
                self.assertEqual(rc, 1)
            finally:
                os.chdir(old)
        self.assertEqual(os.getcwd(), old)

    def test_status_ok(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[paths]\nwork_dir = "/tmp/w"\n')
            with patch("sys.stdout") as mock_out:
                rc = main(["--config", str(cfg), "status"])
            self.assertEqual(rc, 0)

    def test_status_reports_directory_existence(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("fo4a", "sf", "work"):
                (root / name).mkdir()
            cfg = root / "config.toml"
            cfg.write_text(
                "[fo4]\n"
                f'data_dirs = ["{(root / "fo4a").as_posix()}", "{(root / "fo4b").as_posix()}"]\n'
                "[starfield]\n"
                f'data_dir = "{(root / "sf").as_posix()}"\n'
                "[paths]\n"
                f'work_dir = "{(root / "work").as_posix()}"\n'
                f'staging_dir = "{(root / "staging").as_posix()}"\n'
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["--config", str(cfg), "status"])
            text = out.getvalue()
        self.assertEqual(rc, 0)
        lines = {line.strip() for line in text.splitlines()}
        self.assertIn("Fallout 4 data dirs: 2 configured", lines)
        self.assertTrue(any(l.startswith("[0]") and "fo4a" in l and l.endswith("(exists)") for l in lines), text)
        self.assertTrue(any(l.startswith("[1]") and "fo4b" in l and l.endswith("(MISSING)") for l in lines), text)
        self.assertTrue(any(l.startswith("Starfield data dir:") and l.endswith("(exists)") for l in lines), text)
        self.assertTrue(any(l.startswith("work_dir:") and l.endswith("(exists)") for l in lines), text)
        self.assertTrue(any(l.startswith("staging_dir:") and l.endswith("(MISSING or not created)") for l in lines), text)
        self.assertTrue(any(l.startswith("Python:") for l in lines), text)

    def test_status_reports_unset_directories(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text("[fo4]\ndata_dirs = []\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["--config", str(cfg), "status"])
        self.assertEqual(rc, 0)
        lines = {line.strip() for line in out.getvalue().splitlines()}
        self.assertIn("Fallout 4 data dirs: 0 configured", lines)
        self.assertIn("Starfield data dir: missing", lines)
        self.assertIn("work_dir: missing", lines)
        self.assertIn("staging_dir: missing", lines)

    def test_status_explicit_missing_manifest_is_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[paths]\nwork_dir = "/tmp/w"\n')
            missing = Path(td) / "no-manifest.json"
            with patch("sys.stdout"), patch("sys.stderr"):
                rc = main(["--config", str(cfg), "status", "--manifest", str(missing)])
            self.assertEqual(rc, 1)

    def test_status_explicit_invalid_manifest_is_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[paths]\nwork_dir = "/tmp/w"\n')
            bad = Path(td) / "manifest.json"
            bad.write_text("{", encoding="utf-8")
            with patch("sys.stdout"), patch("sys.stderr"):
                rc = main(["--config", str(cfg), "status", "--manifest", str(bad)])
            self.assertEqual(rc, 1)

    def test_status_auto_missing_manifest_is_zero(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            work = Path(td) / "work"
            work.mkdir()
            cfg.write_text(f'[paths]\nwork_dir = "{work.as_posix()}"\n')
            with patch("sys.stdout"):
                rc = main(["--config", str(cfg), "status"])
            self.assertEqual(rc, 0)

    def _validate_cfg(self, root: Path, *, data_dirs=None, work="dir", staging="dir", stage_path=None):
        for name in ("fo4", "sf"):
            (root / name).mkdir()
        if work == "dir":
            (root / "work").mkdir()
        elif work == "file":
            (root / "work").write_text("x")
        if staging == "dir":
            (root / "stage").mkdir()
        cfg = root / "config.toml"
        dirs = data_dirs if data_dirs is not None else [str(root / "fo4")]
        listed = ", ".join(f'"{Path(d).as_posix()}"' for d in dirs)
        cfg.write_text(
            "[fo4]\n"
            f"data_dirs = [{listed}]\n"
            "[starfield]\n"
            f'data_dir = "{(root / "sf").as_posix()}"\n'
            "[paths]\n"
            f'work_dir = "{(root / "work").as_posix()}"\n'
            f'staging_dir = "{(stage_path or root / "stage").as_posix()}"\n'
        )
        return cfg

    def test_validate_ok(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = self._validate_cfg(root)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            out, err = io.StringIO(), io.StringIO()
            with patch("fo4sf.__main__.shutil.which", return_value=str(tex)), _exec_ok(tex), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main(["--config", str(cfg), "validate"])
            text = out.getvalue()
        self.assertEqual(rc, 0, text + err.getvalue())
        self.assertIn("Pillow: available", text)
        self.assertIn("numpy: available", text)
        self.assertIn(f"Python version: {sys.version_info.major}.{sys.version_info.minor}", text)
        self.assertIn("Validation: OK", text)

    def test_validate_imports_pillow_as_pil_not_distro_name(self):
        import builtins
        import contextlib
        import io
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "Pillow":
                raise ImportError("distribution name is not an import name")
            return real_import(name, *a, **k)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = self._validate_cfg(root)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            out, err = io.StringIO(), io.StringIO()
            with patch("fo4sf.__main__.shutil.which", return_value=str(tex)), _exec_ok(tex), \
                    patch("builtins.__import__", side_effect=fake_import), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main(["--config", str(cfg), "validate"])
            text = out.getvalue()
        self.assertEqual(rc, 0, text + err.getvalue())
        self.assertIn("Pillow: available", text)

    def test_validate_rejects_empty_fo4_dirs(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = self._validate_cfg(root, data_dirs=[])
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            out, err = io.StringIO(), io.StringIO()
            with patch("fo4sf.__main__.shutil.which", return_value=str(tex)), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main(["--config", str(cfg), "validate"])
            text = out.getvalue() + err.getvalue()
        self.assertEqual(rc, 1)
        self.assertIn("none configured", text)
        self.assertIn("FAILED", text)

    def test_validate_rejects_work_dir_file(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = self._validate_cfg(root, work="file")
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            out, err = io.StringIO(), io.StringIO()
            with patch("fo4sf.__main__.shutil.which", return_value=str(tex)), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main(["--config", str(cfg), "validate"])
            text = out.getvalue() + err.getvalue()
        self.assertEqual(rc, 1)
        self.assertIn("not a directory", text)
        self.assertIn("FAILED", text)


    def _run_validate(self, cfg, tex, *, exec_ok=True, which=True):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch("fo4sf.__main__.shutil.which", return_value=str(tex) if which else None))
            if exec_ok:
                stack.enter_context(_exec_ok(tex))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            rc = main(["--config", str(cfg), "validate"])
        return rc, out.getvalue() + err.getvalue()

    def test_blank_config_paths_stay_missing(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[fo4]\ndata_dirs = [""]\n[starfield]\ndata_dir = " "\n'
                           '[paths]\nwork_dir = ""\nstaging_dir = ""\n[tools]\ntexconv = ""\n')
            loaded = load_config(cfg)
        self.assertEqual(loaded["fo4"]["data_dirs"], [None])
        self.assertIsNone(loaded["starfield"]["data_dir"])
        self.assertIsNone(loaded["paths"]["work_dir"])
        self.assertIsNone(loaded["paths"]["staging_dir"])
        self.assertIsNone(loaded["tools"]["texconv"])

    def test_validate_rejects_blank_directory_settings(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = root / "config.toml"
            cfg.write_text('[fo4]\ndata_dirs = [""]\n[starfield]\ndata_dir = ""\n'
                           '[paths]\nwork_dir = ""\nstaging_dir = ""\n')
            old = os.getcwd()
            os.chdir(td)   # the cwd is a real directory, so a blank path must not resolve to it
            try:
                rc, text = self._run_validate(cfg, tex)
            finally:
                os.chdir(old)
        self.assertEqual(rc, 1, text)
        self.assertIn("(blank entry): NOT FOUND", text)
        self.assertIn("Starfield data dir: missing in config", text)
        self.assertIn("work_dir: missing in config", text)
        self.assertIn("staging_dir: missing in config", text)
        self.assertNotIn("Validation: OK", text)

    def test_status_shows_a_blank_fo4_dir_as_missing(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "config.toml"
            cfg.write_text('[fo4]\ndata_dirs = [""]\n')
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["--config", str(cfg), "status"])
        self.assertEqual(rc, 0)
        self.assertIn("[0] (blank) (MISSING)", out.getvalue())

    def test_validate_rejects_a_directory_as_a_tool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = self._validate_cfg(root)
            (root / "tooldir").mkdir()
            cfg.write_text(cfg.read_text() + f'[tools]\nmesh = "{(root / "tooldir").as_posix()}"\n')
            rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 1, text)
        self.assertIn("mesh: not an executable file at", text)
        self.assertIn("FAILED", text)

    @unittest.skipIf(os.name == "nt", "Windows has no execute bit")
    def test_validate_rejects_a_non_executable_tool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o644)
            cfg = self._validate_cfg(root)
            rc, text = self._run_validate(cfg, tex, exec_ok=False)
        self.assertEqual(rc, 1, text)
        self.assertIn("texconv: not an executable file at", text)

    def test_validate_rejects_a_blank_tool(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = self._validate_cfg(root)
            cfg.write_text(cfg.read_text() + '[tools]\ntexconv = ""\n')
            rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 1, text)
        self.assertIn("texconv: configured but blank", text)

    def test_validate_rejects_an_unsupported_python(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = self._validate_cfg(root)
            with patch("fo4sf.__main__.MIN_PYTHON", (99, 0)):
                rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 1, text)
        self.assertIn("(needs 99.0 or newer)", text)
        self.assertIn("FAILED", text)

    def test_validate_rejects_an_output_dir_under_a_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            (root / "block").write_text("x")
            cfg = self._validate_cfg(root, staging="none", stage_path=root / "block" / "child" / "stage")
            rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 1, text)
        self.assertIn("cannot be created (", text)
        self.assertIn("block is not a directory)", text)
        self.assertIn("FAILED", text)

    def test_validate_accepts_a_missing_output_dir_under_a_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = self._validate_cfg(root, staging="none", stage_path=root / "new" / "stage")
            rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 0, text)
        self.assertIn("NOT FOUND (will be created by tools)", text)

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "needs POSIX permissions that apply to the current user")
    def test_validate_rejects_an_output_dir_under_a_read_only_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            locked = root / "locked"
            locked.mkdir()
            locked.chmod(0o555)
            try:
                cfg = self._validate_cfg(root, staging="none", stage_path=locked / "stage")
                rc, text = self._run_validate(cfg, tex)
            finally:
                locked.chmod(0o755)
        self.assertEqual(rc, 1, text)
        self.assertIn("locked is not writable)", text)

    def test_validate_rejects_a_lone_blank_fo4_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = self._validate_cfg(root)   # every other setting is valid
            cfg.write_text(cfg.read_text().replace('data_dirs = ["', 'data_dirs = ["", "', 1))
            rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 1, text)
        self.assertIn("(blank entry): NOT FOUND", text)
        self.assertNotIn("Validation: OK", text)

    def test_windows_executables_follow_pathext(self):
        from fo4sf.__main__ import _is_executable_file
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "readme.txt").write_text("x")
            (root / "tool.EXE").write_bytes(b"x")
            with patch.dict(os.environ, {"PATHEXT": ".EXE;.BAT"}):
                self.assertFalse(_is_executable_file(root / "readme.txt", windows=True))
                self.assertTrue(_is_executable_file(root / "tool.EXE", windows=True))
                self.assertFalse(_is_executable_file(root, windows=True))

    def test_validate_rejects_a_read_only_existing_output_dir(self):
        from fo4sf import __main__ as cli
        real = cli._writable_dir
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = self._validate_cfg(root)
            work = (root / "work").resolve()
            with patch.object(cli, "_writable_dir", side_effect=lambda d: Path(d).resolve() != work and real(d)):
                rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 1, text)
        self.assertIn("exists but is not writable", text)

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "needs POSIX permissions that apply to the current user")
    def test_validate_rejects_a_read_only_existing_output_dir_on_disk(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            cfg = self._validate_cfg(root)
            (root / "work").chmod(0o555)
            try:
                rc, text = self._run_validate(cfg, tex)
            finally:
                (root / "work").chmod(0o755)
        self.assertEqual(rc, 1, text)
        self.assertIn("work_dir: ", text)
        self.assertIn("exists but is not writable", text)

    def test_validate_finds_texconv_in_xedit_edit_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            xedit = root / "xedit"
            (xedit / "Edit Scripts").mkdir(parents=True)
            sfedit = xedit / "xSFEdit64.exe"
            sfedit.write_bytes(b"x")
            tex = xedit / "Edit Scripts" / "texconv.exe"
            tex.write_bytes(b"x")
            for f in (sfedit, tex):
                f.chmod(0o755)
            cfg = self._validate_cfg(root)
            cfg.write_text(cfg.read_text() + f'[tools]\nxsfedit = "{sfedit.as_posix()}"\n')
            import contextlib
            import io
            out = io.StringIO()
            with patch("fo4sf.__main__.shutil.which", return_value=None), _exec_ok(sfedit, tex), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc = main(["--config", str(cfg), "validate"])
            text = out.getvalue()
        self.assertEqual(rc, 0, text)
        self.assertIn("texconv: found at", text)
        self.assertIn("Edit Scripts", text)

    def test_validate_without_any_texconv_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "unused.exe"
            cfg = self._validate_cfg(root)
            rc, text = self._run_validate(cfg, tex, which=False)
        self.assertEqual(rc, 1, text)
        self.assertIn("texconv: not found in PATH or xEdit's Edit Scripts", text)

    def test_repo_root_is_this_checkout(self):
        from fo4sf.__main__ import _repo_root
        self.assertEqual(_repo_root(), Path(__file__).resolve().parents[1])

    def _validate_with_repo(self, place):
        """Run validate with a fake checkout at root/repo and one configured path moved inside it."""
        from fo4sf import __main__ as cli
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            repo = root / "repo"
            repo.mkdir()
            cfg = self._validate_cfg(root)
            text = cfg.read_text()
            inside = repo / "out" / place
            if place != "stage_missing":
                inside.mkdir(parents=True)
            old = {"fo4": (root / "fo4"), "sf": (root / "sf"), "work": (root / "work"),
                   "stage_missing": (root / "stage")}[place]
            cfg.write_text(text.replace(f'"{old.as_posix()}"', f'"{inside.as_posix()}"', 1))
            with patch.object(cli, "_repo_root", return_value=repo.resolve()):
                return self._run_validate(cfg, tex)

    def test_validate_rejects_paths_inside_the_repository(self):
        for place in ("fo4", "sf", "work", "stage_missing"):
            with self.subTest(place=place):
                rc, text = self._validate_with_repo(place)
                self.assertEqual(rc, 1, text)
                self.assertIn("inside the repository (must be outside it)", text)
                self.assertNotIn("Validation: OK", text)

    def test_validate_allows_a_sibling_of_the_repository(self):
        from fo4sf import __main__ as cli
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tex = root / "texconv.exe"
            tex.write_bytes(b"x")
            tex.chmod(0o755)
            (root / "repo").mkdir()
            (root / "repo-work").mkdir()   # shares a name prefix, but is not inside
            cfg = self._validate_cfg(root)
            cfg.write_text(cfg.read_text().replace(f'"{(root / "work").as_posix()}"',
                                                   f'"{(root / "repo-work").as_posix()}"', 1))
            with patch.object(cli, "_repo_root", return_value=(root / "repo").resolve()):
                rc, text = self._run_validate(cfg, tex)
        self.assertEqual(rc, 0, text)

if __name__ == "__main__":
    unittest.main()
