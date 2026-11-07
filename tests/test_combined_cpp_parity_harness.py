"""Compiler discovery and unittest gating, without building or running a C++ core."""
import os
import unittest
from unittest import mock

from tests import test_combined_cpp_parity as parity


class CompilerDiscoveryTests(unittest.TestCase):
    def test_cxx_precedes_path_defaults(self):
        with mock.patch.dict(os.environ, {"CXX": "custom-cxx"}, clear=True), \
                mock.patch.object(parity.shutil, "which", return_value="/toolchain/custom-cxx") as which:
            self.assertEqual(parity.compiler(), "/toolchain/custom-cxx")
        which.assert_called_once_with("custom-cxx")

    def test_fallback_order_after_unavailable_cxx(self):
        candidates = ["custom-cxx", "c++", "g++", "clang++"]
        for selected in candidates[1:]:
            with self.subTest(selected=selected), \
                    mock.patch.dict(os.environ, {"CXX": candidates[0]}, clear=True), \
                    mock.patch.object(parity.shutil, "which") as which:
                which.side_effect = lambda name: f"/toolchain/{name}" if name == selected else None
                self.assertEqual(parity.compiler(), f"/toolchain/{selected}")
                self.assertEqual(which.call_args_list,
                                 [mock.call(name) for name in candidates[:candidates.index(selected) + 1]])

    def test_cxx_unset_starts_with_cxx_driver(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(parity.shutil, "which", return_value="/toolchain/c++") as which:
            self.assertEqual(parity.compiler(), "/toolchain/c++")
        which.assert_called_once_with("c++")

    def test_missing_compiler_does_not_probe_msvc(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(parity.shutil, "which", return_value=None) as which:
            self.assertIsNone(parity.compiler())
        self.assertEqual(which.call_args_list, [mock.call(name) for name in ("c++", "g++", "clang++")])


class ParityHarnessTests(unittest.TestCase):
    def run_probe(self):
        # Inherit the real class gate, but run no parity methods or external core.
        class Probe(parity.CppParityTests):
            def runTest(self):
                pass

        result = unittest.TestResult()
        unittest.TestSuite([Probe()]).run(result)
        return result

    def test_missing_compiler_errors_in_ci(self):
        with mock.patch.dict(os.environ, {"CI": "1"}, clear=True), \
                mock.patch.object(parity.shutil, "which", return_value=None), \
                mock.patch.object(parity.tempfile, "mkdtemp") as mkdtemp, \
                mock.patch.object(parity.subprocess, "run") as run:
            result = self.run_probe()
        self.assertEqual(result.testsRun, 0)
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.failures, [])
        self.assertEqual(len(result.errors), 1)
        self.assertIn("C++ parity tests need a C++17 compiler or FOCCSIM_EXE in CI", result.errors[0][1])
        mkdtemp.assert_not_called()
        run.assert_not_called()

    def test_missing_compiler_skips_locally(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(parity.shutil, "which", return_value=None), \
                mock.patch.object(parity.tempfile, "mkdtemp") as mkdtemp, \
                mock.patch.object(parity.subprocess, "run") as run:
            result = self.run_probe()
        self.assertEqual(result.testsRun, 0)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("FOCCSIM_EXE", result.skipped[0][1])
        mkdtemp.assert_not_called()
        run.assert_not_called()

    def test_prebuilt_core_runs_without_compiler_in_ci(self):
        prebuilt = os.path.abspath("synthetic-foccsim")
        with mock.patch.dict(os.environ, {"CI": "1", "FOCCSIM_EXE": prebuilt}, clear=True), \
                mock.patch.object(parity.shutil, "which", return_value=None) as which, \
                mock.patch.object(parity.os.path, "isfile", return_value=True) as isfile, \
                mock.patch.object(parity.tempfile, "mkdtemp", return_value="synthetic-temp"), \
                mock.patch.object(parity.shutil, "rmtree"), \
                mock.patch.object(parity.subprocess, "run") as run:
            result = self.run_probe()
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful(), result.errors)
        self.assertEqual(result.skipped, [])
        isfile.assert_called_once_with(prebuilt)
        which.assert_not_called()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
