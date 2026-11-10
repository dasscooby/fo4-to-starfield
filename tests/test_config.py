"""load_config reports every malformed config.toml as ConfigError (synthetic; no real game paths)."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from fo4sf.__main__ import main
from fo4sf.config import ConfigError, load_config

try:
    import tomllib
except ImportError:
    tomllib = None


@unittest.skipUnless(tomllib, "tomllib requires Python 3.11+")
class TestLoadConfigShapes(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name)

    def write(self, text):
        p = self.root / "config.toml"
        p.write_text(text, encoding="utf-8")
        return p

    def assert_config_error(self, text, *needles):
        with self.assertRaises(ConfigError) as cm:
            load_config(self.write(text))
        for needle in needles:
            self.assertIn(needle, str(cm.exception))

    def test_invalid_toml_is_config_error(self):
        self.assert_config_error('[paths\nwork_dir = "w"\n', "not valid TOML")

    def test_data_dirs_string_is_rejected_not_split_per_character(self):
        self.assert_config_error(f'[fo4]\ndata_dirs = "{self.root / "fo4"}"\n', "fo4.data_dirs", "list")

    def test_non_string_path_fields_name_the_key(self):
        self.assert_config_error("[paths]\nwork_dir = 5\n", "paths.work_dir", "int")
        self.assert_config_error("[starfield]\ndata_dir = true\n", "starfield.data_dir", "bool")
        self.assert_config_error(f'[fo4]\ndata_dirs = ["{self.root}", 3]\n', "fo4.data_dirs[1]")

    def test_known_section_must_be_a_table(self):
        self.assert_config_error('paths = "w"\n', "[paths]", "table")
        self.assert_config_error("fo4 = [1]\n", "[fo4]", "table")

    def test_valid_shapes_still_load(self):
        cfg = load_config(self.write(
            f'[fo4]\ndata_dirs = ["{self.root / "fo4"}", " "]\n'
            f'[starfield]\ndata_dir = "{self.root / "sf"}"\n'
            f'[paths]\nwork_dir = "{self.root / "w"}"\nstaging_dir = ""\n'
            '[tools]\nretries = 3\nextra = { a = 1 }\n'
            '[other]\nkept = "x"\n'))
        self.assertEqual(cfg["fo4"]["data_dirs"], [(self.root / "fo4").resolve(), None])
        self.assertEqual(cfg["starfield"]["data_dir"], (self.root / "sf").resolve())
        self.assertEqual(cfg["paths"]["work_dir"], (self.root / "w").resolve())
        self.assertIsNone(cfg["paths"]["staging_dir"])
        self.assertEqual(cfg["tools"], {"retries": 3, "extra": {"a": 1}})   # non-string tool entries pass through
        self.assertEqual(cfg["other"], {"kept": "x"})

    def test_status_and_validate_report_malformed_config_without_traceback(self):
        cfg = self.write('[fo4]\ndata_dirs = "/x"\n')
        for cmd in ("status", "validate"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = main(["--config", str(cfg), cmd])
            self.assertEqual(rc, 1, cmd)
            self.assertIn("config error: fo4.data_dirs must be a list", err.getvalue(), cmd)


if __name__ == "__main__":
    unittest.main()
