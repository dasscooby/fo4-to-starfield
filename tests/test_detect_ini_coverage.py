"""Unknown profile INIs must be visible in read-only API and real CLI output."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock

import test_launcher_detect as fixture


class IniCoverageTests(unittest.TestCase):
    run_detect = fixture.DetectTests.run_detect

    def setUp(self):
        fixture.DetectTests.setUp(self)
        self.profile = Path(self.root) / "redirected-documents/My Games/Starfield"
        self.profile.mkdir(parents=True)

    def test_omitted_profile_is_unknown_and_not_guessed(self):
        ini = Path(self.my_games) / "StarfieldCustom.ini"
        ini.write_bytes(b"[General]\nsTestFile1=Hidden.esm\n")
        with mock.patch.dict(os.environ, {"USERPROFILE": self.root}):
            for value in (None, ""):
                with self.subTest(value=value):
                    result = self.run_detect(my_games=value)
                    self.assertTrue(result["ready"], result["refusals"])
                    self.assertTrue(any("My Games not checked" in w and "--my-games" in w
                                        for w in result["warnings"]))
                    self.assertNotIn("my_games", result)
                    self.assertEqual(result["refusals"], [])

    def test_unavailable_supplied_profile_is_explicitly_unchecked(self):
        missing = self.profile / "absent"
        for path in (missing, self.profile / "is-a-file"):
            if path.name == "is-a-file":
                path.write_bytes(b"keep")
            with self.subTest(path=str(path)):
                result = self.run_detect(my_games=str(path))
                self.assertTrue(result["ready"], result["refusals"])
                self.assertTrue(any("not found" in w and "INIs in My Games not checked" in w
                                    for w in result["warnings"]))
                self.assertNotIn("my_games", result)
        self.assertFalse(missing.exists())

    def test_explicit_redirected_profile_is_checked_and_testfile_still_refuses(self):
        result = self.run_detect(my_games=str(self.profile))
        self.assertTrue(result["ready"], result["refusals"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["my_games"]["path"], str(self.profile))
        ini = self.profile / "StarfieldCustom.ini"
        ini.write_bytes(b"[General]\nsTestFile1=Hidden.esm\n")
        result = self.run_detect(my_games=str(self.profile))
        self.assertFalse(result["ready"])
        self.assertTrue(any("sTestFile1=Hidden.esm" in r and str(ini) in r
                            for r in result["refusals"]))
        self.assertFalse(any("not checked" in w for w in result["warnings"]))

    def test_game_folder_ini_refusal_is_preserved_without_profile(self):
        ini = Path(self.sf) / "StarfieldCustom.ini"
        ini.write_bytes(b"[General]\nsTestFile1=GameFolder.esm\n")
        result = self.run_detect()
        self.assertFalse(result["ready"])
        self.assertTrue(any("sTestFile1=GameFolder.esm" in r for r in result["refusals"]))
        self.assertTrue(any("My Games not checked" in w for w in result["warnings"]))

    def test_actual_cli_reports_coverage_and_preserves_inputs(self):
        table = Path(self.root) / "sources.json"
        table.write_text(json.dumps(self.table), encoding="utf-8")
        settings = Path(self.root) / "settings.json"
        settings.write_text(json.dumps({"my_games": ""}), encoding="utf-8")
        # Poison only the synthetic default profile. The explicit settings file above must win.
        default_profile = Path(self.root) / "synthetic-default/My Games/Starfield"
        default_profile.mkdir(parents=True)
        (default_profile / "StarfieldCustom.ini").write_bytes(b"[General]\nsTestFile1=Default.esm\n")
        local_app_data = Path(self.root) / "local-app-data"
        default_settings = local_app_data / "FO4SF/launcher_settings.json"
        default_settings.parent.mkdir(parents=True)
        default_settings.write_text(json.dumps({"my_games": str(default_profile)}), encoding="utf-8")
        def inputs():
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                    for folder in (Path(self.fo4), Path(self.sf), self.profile, default_profile)
                    for p in folder.rglob("*") if p.is_file()} | {
                        str(table): hashlib.sha256(table.read_bytes()).hexdigest(),
                        str(settings): hashlib.sha256(settings.read_bytes()).hexdigest(),
                        str(default_settings): hashlib.sha256(default_settings.read_bytes()).hexdigest()}
        before = inputs()
        for kind, profile, expected in (("omitted", None, 0), ("missing", self.profile / "absent", 0),
                                        ("clean", self.profile, 0), ("blocked", self.profile, 1)):
            with self.subTest(kind=kind):
                if kind == "blocked":
                    (self.profile / "StarfieldCustom.ini").write_bytes(b"[General]\nsTestFile1=Hidden.esm\n")
                    before = inputs()
                report = Path(self.root) / f"{kind}.json"
                argv = [sys.executable, "-I", "-B", os.path.join(fixture.ROOT, "scripts", "launcher.py"),
                        "detect", "--fo4-data", self.fo4, "--starfield", self.sf, "--table", str(table),
                        "--report", str(report), "--allow-unknown-runtime", "--settings", str(settings)]
                if profile is not None:
                    argv.extend(["--my-games", str(profile)])
                child_env = os.environ.copy()
                child_env["LOCALAPPDATA"] = str(local_app_data)
                child = subprocess.run(argv, capture_output=True, text=True, check=False, env=child_env)
                self.assertEqual(child.returncode, expected, child.stderr + child.stdout)
                result = json.loads(report.read_text(encoding="utf-8"))
                self.assertEqual(result["ready"], expected == 0)
                if kind in ("omitted", "missing"):
                    self.assertIn("INIs in My Games not checked", child.stdout)
                    self.assertTrue(any("not checked" in w for w in result["warnings"]))
                else:
                    self.assertNotIn("not checked", child.stdout)
                if kind == "blocked":
                    self.assertIn("sTestFile1=Hidden.esm", child.stdout)
                    self.assertIn("NOT READY", child.stdout)
                if kind == "omitted":
                    self.assertNotIn("Default.esm", child.stdout)
                self.assertEqual(inputs(), before)

        # Negative control: without the explicit file, the real CLI sees the synthetic default and refuses.
        report = Path(self.root) / "poisoned-default.json"
        argv = [sys.executable, "-I", "-B", os.path.join(fixture.ROOT, "scripts", "launcher.py"),
                "detect", "--fo4-data", self.fo4, "--starfield", self.sf, "--table", str(table),
                "--report", str(report), "--allow-unknown-runtime"]
        child_env = os.environ.copy()
        child_env["LOCALAPPDATA"] = str(local_app_data)
        child = subprocess.run(argv, capture_output=True, text=True, check=False, env=child_env)
        self.assertEqual(child.returncode, 1, child.stderr + child.stdout)
        self.assertIn("sTestFile1=Default.esm", child.stdout)
        self.assertIn("NOT READY", child.stdout)
        self.assertEqual(inputs(), before)


if __name__ == "__main__":
    unittest.main()
