"""scripts/ci/run_tests.py against a temporary folder of synthetic test modules."""

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parent.parent / "scripts" / "ci" / "run_tests.py"

PASSING_A = """
    import unittest
    class A(unittest.TestCase):
        def test_one(self): pass
        def test_two(self): pass
"""
PASSING_B = """
    import unittest
    class B(unittest.TestCase):
        def test_three(self): pass
        @unittest.skip("synthetic")
        def test_skipped(self): pass
"""
FAILING = """
    import unittest
    class F(unittest.TestCase):
        def test_ok(self): pass
        def test_bad(self): self.assertEqual(1, 2)
"""
IMPORT_ERROR = """
    import module_that_does_not_exist_anywhere
    import unittest
    class E(unittest.TestCase):
        def test_never(self): pass
"""
HANGING = """
    import time, unittest
    class H(unittest.TestCase):
        def test_hang(self): time.sleep(600)
"""
ZERO = """
    import unittest
    class Z(unittest.TestCase):
        def helper(self): pass
"""


def make_tests_dir(root: Path, modules: dict) -> Path:
    tests = root / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    for name, body in modules.items():
        (tests / f"{name}.py").write_text(textwrap.dedent(body))
    return tests


def run_runner(tests_dir: Path, *extra: str):
    return subprocess.run(
        [sys.executable, str(RUNNER), "--tests-dir", str(tests_dir), *extra],
        capture_output=True, text=True, timeout=120,
    )


class RunTestsRunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_all_pass_exit_zero_and_totals(self):
        tests = make_tests_dir(self.root, {"test_a": PASSING_A, "test_b": PASSING_B})
        for extra in (["--jobs", "2"], ["--serial"]):
            with self.subTest(extra=extra):
                proc = run_runner(tests, *extra)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn("tests=4 failures=0 errors=0 skipped=1", proc.stdout)
                self.assertIn("modules=2", proc.stdout)
                self.assertIn("test_a", proc.stdout)
                self.assertIn("test_b", proc.stdout)

    def test_failing_module_is_named_with_full_output(self):
        tests = make_tests_dir(self.root, {"test_a": PASSING_A, "test_fails": FAILING})
        proc = run_runner(tests, "--jobs", "2")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAILED modules: test_fails", proc.stdout)
        self.assertIn("AssertionError", proc.stdout)  # full output of the failed module
        self.assertIn("failures=1", proc.stdout)

    def test_import_error_module_is_named(self):
        tests = make_tests_dir(self.root, {"test_a": PASSING_A, "test_broken": IMPORT_ERROR})
        proc = run_runner(tests, "--jobs", "2")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAILED modules: test_broken", proc.stdout)
        self.assertIn("module_that_does_not_exist_anywhere", proc.stdout)
        self.assertIn("errors=1", proc.stdout)

    def test_hanging_module_times_out_and_is_named(self):
        tests = make_tests_dir(self.root, {"test_a": PASSING_A, "test_hangs": HANGING})
        proc = run_runner(tests, "--jobs", "2", "--timeout", "3")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAILED modules: test_hangs", proc.stdout)
        self.assertIn("timed out", proc.stdout)

    def test_zero_test_module_is_named(self):
        tests = make_tests_dir(self.root, {"test_a": PASSING_A, "test_empty": ZERO})
        proc = run_runner(tests, "--jobs", "2")
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("FAILED modules: test_empty", proc.stdout)
        self.assertIn("zero tests", proc.stdout)

    def test_list_matches_synthetic_ids_and_runs_nothing(self):
        tests = make_tests_dir(self.root, {"test_a": PASSING_A, "test_b": PASSING_B})
        proc = run_runner(tests, "--list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            sorted(proc.stdout.split()),
            sorted([
                "test_a.A.test_one", "test_a.A.test_two",
                "test_b.B.test_three", "test_b.B.test_skipped",
            ]),
        )

    def test_empty_folder_is_an_error(self):
        tests = make_tests_dir(self.root, {})
        self.assertEqual(run_runner(tests).returncode, 1)


if __name__ == "__main__":
    unittest.main()
