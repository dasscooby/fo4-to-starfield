"""Synthetic tests for fo4sf dds-summary CLI."""
import io
import os
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))  # run alone: put fo4sf on the path
from fo4sf.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

_NO_NUMPY = textwrap.dedent(
    """\
    import sys
    sys.path.insert(0, sys.argv[1])

    class _BlockNumpy:
        def find_spec(self, fullname, path, target=None):
            if fullname == "numpy" or fullname.startswith("numpy."):
                raise ModuleNotFoundError("No module named %r" % fullname)
            return None

    sys.meta_path.insert(0, _BlockNumpy())
    sys.argv = ["fo4sf", *sys.argv[2:]]
    from fo4sf.__main__ import main
    raise SystemExit(main())
    """
)


def _make_minimal_dds(width=4, height=4, fourcc=b"DXT1"):
    # Minimal valid DDS header that read_dds_header accepts
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 28, 1)  # mips
    header[84:88] = fourcc
    return bytes(header)


def _run_without_numpy(*args: str) -> subprocess.CompletedProcess[str]:
    """Child process whose site packages cannot provide numpy.

    UTF-8 on both ends: the CLI description has a non-ASCII arrow, and on Windows a captured child otherwise writes
    cp1252 and --help fails before numpy matters. -I ignores PYTHONUTF8, so the child needs -X utf8 itself.
    """
    return subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-X", "utf8", "-c", _NO_NUMPY, str(SRC), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=os.getcwd(),
    )


class DdsSummaryTests(unittest.TestCase):
    def test_summary_text(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.dds"
            p.write_bytes(_make_minimal_dds(8, 8, b"BC5U"))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["dds-summary", str(p)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("8x8", out)
            self.assertIn("BC5U", out)

    def test_zero_fourcc_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "zero.dds"
            p.write_bytes(_make_minimal_dds(4, 2, b"\x00\x00\x00\x00"))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["dds-summary", str(p)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("fourCC=(none)", out)
            self.assertNotIn("\x00", out)

    def test_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            rc = main(["dds-summary", "no-such-file.dds"])
        self.assertEqual(rc, 1)
        self.assertIn("missing:", buf_err.getvalue())

    def test_other_commands_work_without_numpy(self):
        """#548 P2: a top-level textures import must not break dependency-free commands."""
        help_run = _run_without_numpy("--help")
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("usage:", help_run.stdout.lower())
        self.assertNotIn("ModuleNotFoundError", help_run.stderr)

        validate_help = _run_without_numpy("validate", "--help")
        self.assertEqual(validate_help.returncode, 0, validate_help.stderr)
        self.assertIn("usage:", validate_help.stdout.lower())
        self.assertNotIn("ModuleNotFoundError", validate_help.stderr)

        with tempfile.TemporaryDirectory() as td:
            dds = Path(td) / "t.dds"
            dds.write_bytes(_make_minimal_dds())
            summary = _run_without_numpy("dds-summary", str(dds))
            self.assertEqual(summary.returncode, 1)
            self.assertIn("needs numpy", summary.stderr)
            self.assertNotIn("Traceback", summary.stderr)

            if sys.version_info < (3, 11):
                # load_config needs tomllib. CI is 3.12; this host may be older.
                return
            cfg = Path(td) / "config.toml"
            cfg.write_text(
                "\n".join(
                    [
                        "[fo4]",
                        'data_dirs = ["/tmp"]',
                        "[starfield]",
                        'data_dir = "/tmp"',
                        "[paths]",
                        'work_dir = "/tmp"',
                        'staging_dir = "/tmp"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            status = _run_without_numpy("--config", str(cfg), "status")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("fo4-to-starfield status", status.stdout)
            self.assertNotIn("ModuleNotFoundError", status.stderr)

            validate = _run_without_numpy("--config", str(cfg), "validate")
            combined = validate.stdout + validate.stderr
            self.assertIn("numpy: MISSING", combined)
            self.assertNotIn("Traceback", combined)
            self.assertNotIn("ModuleNotFoundError", combined)


if __name__ == "__main__":
    unittest.main()
