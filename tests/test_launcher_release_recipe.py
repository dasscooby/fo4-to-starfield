"""Real synthetic subprocesses across one managed recipe; no game files."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import driver, instance, release_install as ri, save_release as sr, settings  # noqa: E402


class ReleaseRecipeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "instance"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        (self.game / "Starfield.exe").write_bytes(b"synthetic exe")
        (self.game / instance.RECORD).write_bytes(ri.encode({"schema": 1, "complete": True, "made": []}))
        self.my_games = self.root / "My Games"
        self.my_games.mkdir()
        plugins = Path(instance.plugins_txt(self.game))
        plugins.parent.mkdir(parents=True)
        self.names = ("FO4Port.esm", "FO4SFBridge.esm")
        plugins.write_text("".join("*" + name + "\n" for name in self.names))
        self.candidate = self.root / "release.json"
        self.release = {"schema": 2, "release_id": "synthetic", "implicit_loaders": {"game": None, "my_games": None},
                        "masters": [dict(ri.pin(name.encode()), name=name) for name in self.names], "state_layouts": {}}
        self.candidate.write_bytes(ri.encode(self.release))
        self.settings = self.root / "settings.json"
        values = settings.defaults()
        values.update(instance=str(self.game), my_games=str(self.my_games))
        settings.save(str(self.settings), values)
        self.script = self.root / "install.py"
        self.script.write_text(r"""import json, os, pathlib, sys
name = sys.argv[1]
root = pathlib.Path(sys.argv[3])
rec = json.loads((root / 'FO4SF-instance.json').read_bytes())
assert rec['save_release']['complete'] is False
assert os.environ['LOCALAPPDATA'] == str(root / 'FO4SF-local')
if (root.parent / ('fail-' + name)).exists():
    sys.exit(7)
(root / 'Data' / name).write_bytes(name.encode())
with (root.parent / 'calls.txt').open('a') as stream:
    stream.write(name + '\n')
""")
        self.recipe_path = self.root / "recipe.json"
        self.spec = {"name": "managed-fixture", "state_dir": str(self.root / "state"),
                     "managed_release": {"settings": str(self.settings), "declaration": str(self.candidate)},
                     "steps": [{"id": str(i), "argv": [sys.executable, "-I", str(self.script), name,
                                                         "--starfield", str(self.game)],
                                "outputs": [str(self.data / name)], "after": [str(i - 1)] if i else [],
                                "code": [str(self.script)]} for i, name in enumerate(self.names)]}
        # The script sees name at argv1 and target at argv3; Python's -I is removed by the interpreter.
        self.write_recipe()

    def write_recipe(self):
        self.recipe_path.write_text(json.dumps(self.spec))

    def recipe(self):
        return driver.load_recipe(self.recipe_path, repo=str(ROOT))[0]

    def build(self, **kwargs):
        return driver.build(self.recipe(), str(ROOT), echo=lambda *_: None, **kwargs)

    def calls(self):
        path = self.root / "calls.txt"
        return path.read_text().splitlines() if path.exists() else []

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}

    def test_two_components_share_pending_then_publish_and_reuse(self):
        report = self.build()
        self.assertTrue(report["complete"])
        self.assertEqual(report["release"]["status"], "complete")
        self.assertEqual(self.calls(), list(self.names))
        self.assertEqual(ri.installed(self.game), sr.declaration(self.release))
        report = self.build()
        self.assertEqual([s["status"] for s in report["steps"]], ["reused", "reused"])
        self.assertTrue(report["complete"])
        self.assertEqual(self.calls(), list(self.names))

    def test_failed_second_component_stays_pending_and_resumes_first_from_cache(self):
        fail = self.root / ("fail-" + self.names[1])
        fail.touch()
        report = self.build()
        self.assertFalse(report["complete"])
        self.assertEqual(report["release"]["status"], "pending")
        self.assertIn("repeat install-release", sr.play_reason(settings.load(self.settings), self.game))
        fail.unlink()
        report = self.build()
        self.assertEqual([s["status"] for s in report["steps"]], ["reused", "done"])
        self.assertTrue(report["complete"])
        self.assertEqual(self.calls(), list(self.names))

    def test_dry_run_is_read_only_even_without_installed_target_masters(self):
        before = self.snapshot()
        self.assertTrue(self.build(dry_run=True)["dry_run"])
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.calls(), [])

    def test_until_keeps_partial_release_pending(self):
        report = self.build(until="0")
        self.assertFalse(report["complete"])
        self.assertEqual(report["release"]["status"], "pending")
        self.assertEqual(self.calls(), [self.names[0]])
        self.assertTrue(self.build()["complete"])

    def test_reuse_still_rechecks_changed_ccc_and_reports_refusal(self):
        self.assertTrue(self.build()["complete"])
        (self.game / "Starfield.ccc").write_text("Starfield.esm\n")
        report = self.build()
        self.assertFalse(report["complete"])
        self.assertEqual(report["release"]["status"], "refused")
        self.assertIn("implicit loader configuration", report["release"]["detail"])
        self.assertEqual([s["status"] for s in report["steps"]], ["reused", "reused"])
        self.assertEqual(self.calls(), list(self.names))

    def test_bad_managed_config_never_falls_back_to_generic_recipe(self):
        for config in (None, {}, {"settings": str(self.settings)},
                       {"settings": "", "declaration": str(self.candidate)},
                       {"settings": str(self.settings), "declaration": str(self.candidate), "other": "x"}):
            self.spec["managed_release"] = config
            self.write_recipe()
            with self.assertRaises(ValueError):
                self.build()
        self.assertEqual(self.calls(), [])

    def test_missing_candidate_or_wrong_target_refuses_without_writes(self):
        self.spec["steps"][1]["argv"][-1] = str(self.root)
        self.write_recipe()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "not the FO4SF"):
            self.build()
        self.assertEqual(before, self.snapshot())
        self.spec["steps"][1]["argv"][-1] = str(self.game)
        self.write_recipe()
        self.candidate.unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "input is missing"):
            self.build()
        self.assertEqual(before, self.snapshot())

    def test_metadata_are_fingerprint_inputs(self):
        recipe = self.recipe()
        for step in recipe["steps"]:
            self.assertIn(str(self.candidate), step["inputs"])
            self.assertIn(str(self.settings), step["inputs"])

    def test_changed_settings_during_step_cannot_move_next_command(self):
        real = driver.run_step
        def changed(*args):
            result = real(*args)
            self.settings.write_text('{}')
            return result
        with mock.patch.object(driver, "run_step", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                self.build()
        self.assertEqual(self.calls(), [self.names[0]])
        self.assertFalse(json.loads((self.game / instance.RECORD).read_bytes())[ri.FIELD]["complete"])

    def test_running_game_refuses_before_command(self):
        with mock.patch.object(ri.restore, "game_running", return_value=True):
            # Defaults are pinned functions: patch the actual begin call's injected running argument.
            real = ri.begin
            with mock.patch.object(ri, "begin", side_effect=lambda v, p: real(v, p, running=lambda: True)):
                with self.assertRaisesRegex(ValueError, "close Starfield"):
                    self.build()
        self.assertEqual(self.calls(), [])
        self.assertNotIn(ri.FIELD, json.loads((self.game / instance.RECORD).read_bytes()))

    def generic(self):
        self.spec.pop("managed_release", None)
        self.script.write_text("""import pathlib, sys
root = pathlib.Path(sys.argv[3])
(root / 'Data' / sys.argv[1]).write_bytes(sys.argv[1].encode())
with (root.parent / 'calls.txt').open('a') as stream:
    stream.write(sys.argv[1] + '\\n')
""")
        self.write_recipe()

    def own_release(self, complete=True):
        raw = ri.encode(sr.declaration(self.release))
        (self.data / sr.RELEASE_FILE).write_bytes(raw)
        receipt = json.loads((self.game / instance.RECORD).read_bytes())
        receipt[ri.FIELD] = {"schema": 1, "complete": complete,
                             "declaration": ri.pin(raw), "previous": None}
        (self.game / instance.RECORD).write_bytes(ri.encode(receipt))

    def test_generic_recipe_cannot_target_owned_release_wet_or_dry(self):
        self.generic()
        self.own_release()
        before = self.snapshot()
        for dry in (False, True):
            with self.assertRaisesRegex(ValueError, "needs managed_release"):
                self.build(dry_run=dry)
            self.assertEqual(before, self.snapshot())
        self.assertEqual(self.calls(), [])

    def test_generic_recipe_checks_abbreviated_equals_relative_and_multiple_targets(self):
        self.generic()
        self.own_release()
        for args in (("--starfield=" + str(self.game),), ("--starf=instance",),
                     ("--starf", "instance"), ("--starfield", str(self.root / "legacy"),
                                               "--starfield", str(self.game))):
            self.spec["steps"][0]["argv"] = [sys.executable, str(self.script), self.names[0], *args]
            self.spec["steps"][0]["cwd"] = str(self.root)
            self.write_recipe()
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "needs managed_release"):
                self.build()
            self.assertEqual(before, self.snapshot())

    def test_generic_pending_corrupt_and_unowned_release_refuse(self):
        self.generic()
        self.own_release(complete=False)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.build()
        self.assertEqual(before, self.snapshot())
        (self.game / instance.RECORD).write_text('{"save_release":{}}')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(before, self.snapshot())
        (self.game / instance.RECORD).write_text('{"schema":1,"complete":true}')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "no installer ownership"):
            self.build()
        self.assertEqual(before, self.snapshot())

    def test_generic_legacy_runs_but_cached_owned_target_refuses(self):
        self.generic()
        self.assertTrue(self.build()["complete"])
        self.assertEqual(self.calls(), list(self.names))
        self.assertEqual([s["status"] for s in self.build()["steps"]], ["reused", "reused"])
        self.own_release()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "needs managed_release"):
            self.build()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.calls(), list(self.names))

    def test_generic_rechecks_ownership_between_commands(self):
        self.generic()
        real = driver.run_step
        def changed(*args):
            result = real(*args)
            self.own_release()
            return result
        with mock.patch.object(driver, "run_step", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "needs managed_release"):
                self.build()
        self.assertEqual(self.calls(), [self.names[0]])

    def test_native_refusal_keeps_managed_recipe_pending_including_cached_retry(self):
        with self.script.open("a") as stream:
            stream.write("\nplugins = root / 'Data/SFSE/Plugins'\nplugins.mkdir(parents=True, exist_ok=True)\n"
                         "(plugins / 'FOCCPing.dll').write_bytes(b'unknown synthetic native')\n")
        report = self.build()
        self.assertFalse(report["complete"])
        self.assertEqual(report["release"]["status"], "refused")
        self.assertIn("no measured identity", report["release"]["detail"])
        self.assertFalse(json.loads((self.game / instance.RECORD).read_bytes())[ri.FIELD]["complete"])
        report = self.build()
        self.assertFalse(report["complete"])
        self.assertEqual([s["status"] for s in report["steps"]], ["reused", "reused"])
        (self.data / "SFSE/Plugins/FOCCPing.dll").unlink()
        self.assertTrue(self.build()["complete"])
        self.assertEqual(self.calls(), list(self.names))


if __name__ == "__main__":
    unittest.main()
