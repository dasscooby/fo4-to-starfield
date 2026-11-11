"""CLI tests for scripts/ba2_summary.py and scripts/ba2_largest.py."""
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tests.ba2_fixture import general_archive


def _load_script(name):
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", name)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Ba2SummaryCliTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_script("ba2_summary.py")

    def test_usage_when_missing_arg(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = self.mod.main(["ba2_summary.py"])
        self.assertEqual(rc, 2)
        self.assertIn("usage:", err.getvalue().lower())

    def test_rejects_missing_file(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = self.mod.main(["ba2_summary.py", os.path.join("no", "such.ba2")])
        self.assertEqual(rc, 1)
        self.assertIn("not a file", err.getvalue())

    def test_prints_json_summary(self):
        data = general_archive({"a.txt": b"hello", "b.nif": b"x" * 20})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.ba2")
            with open(path, "wb") as f:
                f.write(data)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = self.mod.main(["ba2_summary.py", path])
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue())
            self.assertEqual(payload["entries"], 2)
            self.assertEqual(payload["total_unpacked"], 5 + 20)
            self.assertEqual(payload["by_extension"]["txt"], 1)
            self.assertEqual(payload["by_extension"]["nif"], 1)

    def test_docstring_uses_isolated_python(self):
        self.assertIn("python -I scripts/ba2_summary.py", self.mod.__doc__)


class Ba2LargestCliTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_script("ba2_largest.py")

    def test_lists_top_by_unpacked(self):
        data = general_archive({
            "small.txt": b"a" * 10,
            "large.dat": b"c" * 1000,
        }, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "l.ba2")
            with open(path, "wb") as f:
                f.write(data)
            out = io.StringIO()
            with redirect_stdout(out):
                rc = self.mod.main([path, "--n", "1"])
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("large.dat", text)
            self.assertNotIn("small.txt", text)
            self.assertIn("1,000", text)

    def test_missing_archive_rc_1(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = self.mod.main([os.path.join("no", "such.ba2")])
        self.assertEqual(rc, 1)
        self.assertIn("error:", err.getvalue())

    def test_usage_when_missing_arg(self):
        err = io.StringIO()
        with redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                self.mod.main([])
            self.assertEqual(cm.exception.code, 2)
        self.assertIn("usage:", err.getvalue().lower())

    def test_rejects_negative_n(self):
        data = general_archive({"a.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "n.ba2")
            with open(path, "wb") as f:
                f.write(data)
            err = io.StringIO()
            with redirect_stderr(err):
                with self.assertRaises(SystemExit) as cm:
                    self.mod.main([path, "--n", "-1"])
            self.assertEqual(cm.exception.code, 2)
            self.assertIn("must be >= 0", err.getvalue())

    def test_truncated_archive_rc_1_no_traceback(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trunc.ba2")
            with open(path, "wb") as f:
                f.write(b"BTDX" + b"\x00" * 4)
            err = io.StringIO()
            with redirect_stderr(err):
                rc = self.mod.main([path])
            self.assertEqual(rc, 1)
            text = err.getvalue()
            self.assertIn("error:", text)
            self.assertNotIn("Traceback", text)

    def test_docstring_uses_isolated_python(self):
        self.assertIn("python -I scripts/ba2_largest.py", self.mod.__doc__)


if __name__ == "__main__":
    unittest.main()
