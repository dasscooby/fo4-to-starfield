"""Compiler discovery, unittest gating and parity coverage pins, without building or running a C++ core."""
import json
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


class ParityCoverageTests(unittest.TestCase):
    def test_python_one_time_kinds_are_pinned_without_a_compiler(self):
        # C++ jobs.cpp::one_time is checked by CppParityTests' cross-instance outcome cases.
        self.assertCountEqual(parity.jobs._ONE_TIME, ("defend", "escort", "retake"))

    def test_large_seed_cases_compare_every_tick_and_exercise_both_layers(self):
        seeds = []

        def check(name, ws, ticks, actions, *, every):
            seeds.append(ws.seed)
            self.assertEqual(every, 1)
            self.assertEqual(ticks, (90 if parity.FULL else 8) * parity.DAY)
            self.assertEqual(parity.WorldState.from_json(ws.to_json()).to_json(), ws.to_json())
            self.assertLess(parity.sim.rng_seed(ws.seed, ticks * parity.sim.TICK_HOURS), 2 ** 64)
            self.assertEqual(ws.settlements["market"].priority, "food")
            self.assertEqual(ws.settlements["river_town"].priority, "water")
            # Execute the real hour-zero prelude rather than mocking the model or its player hooks.
            results, last = [], []
            for action in actions[:7]:
                results.append(json.loads(parity.run(ws, action, last))[2]["ok"])
            self.assertEqual(results[0]["priority"], "food")
            self.assertEqual(results[1][0]["kind"], "resupply")
            self.assertEqual(results[3][0]["kind"], "defend")
            self.assertGreater(ws.regional_reputation["R1"]["settlers"].fame, 9)
            self.assertGreater(ws.regional_reputation["R2"]["settlers"].fame, 24)
            self.assertGreater(ws.regional_reputation["R2"]["traders"].infamy, 25)
            for result, outcome_text in zip(results[5:], ("finished a job", "let traders down")):
                texts = " ".join(item["text"] for item in result["items"])
                self.assertIn("putting its effort into", texts)
                self.assertIn(outcome_text, texts)

        case = parity.CppParityTests("test_large_seeds_with_priority_settlements_and_regional_reputation")
        with mock.patch.object(case, "parity", side_effect=check):
            case.test_large_seeds_with_priority_settlements_and_regional_reputation()
        self.assertEqual(seeds, [2 ** 32, 2 ** 32 + 7])


if __name__ == "__main__":
    unittest.main()
