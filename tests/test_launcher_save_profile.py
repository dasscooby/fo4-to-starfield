"""Declared instance gate on opaque fixtures; no game or live profile."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from fo4sf.launcher import crashwatch, gui, save_release as sr, settings  # noqa: E402
from test_launcher_crashwatch import FakeSystem  # noqa: E402


class SaveProfileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        self.my_games = self.root / "My Games"
        self.saves = self.my_games / "Saves" / "FO4SF"
        self.saves.mkdir(parents=True)
        (self.data / "FO4Port.esm").write_bytes(b"synthetic master")
        self.release = {"schema": 1, "release_id": "A", "masters": [
            dict(sr.identity(self.data / "FO4Port.esm"), name="FO4Port.esm")], "state_layouts": {}}
        self.marker = self.data / sr.RELEASE_FILE
        self.marker.write_text(json.dumps(self.release))
        self.values = settings.defaults()
        self.values.update(instance=str(self.game), starfield=str(self.game), my_games=str(self.my_games),
                           route="exe", load_order="off")

    def reason(self):
        return sr.play_reason(self.values, self.game)

    def bound(self, name="player.sfs"):
        save = self.saves / name
        save.write_bytes(b"opaque save")
        binding = sr.snapshot_binding(self.release, save, self.saves / "FO4SF-Runtime")
        save.with_name(name + sr.BINDING_SUFFIX).write_text(json.dumps(binding))
        return save

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def test_empty_and_compatible_profile_are_read_only(self):
        self.assertEqual(self.reason(), "")
        self.bound("Unicode-旅.SFS")
        before = self.snapshot()
        self.assertEqual(self.reason(), "")
        self.assertEqual(before, self.snapshot())

    def test_first_run_does_not_create_save_folder(self):
        self.saves.rmdir()
        self.assertEqual(self.reason(), "")
        self.assertFalse(self.saves.exists())

    def test_legacy_absence_is_explicitly_not_a_managed_release(self):
        self.marker.unlink()
        (self.saves / "old.sfs").write_bytes(b"old unbound")
        self.assertEqual(self.reason(), "")

    def test_unbound_save_refuses_without_creating_binding(self):
        (self.saves / "old.sfs").write_bytes(b"old unbound")
        before = self.snapshot()
        self.assertIn("never adopted", self.reason())
        self.assertEqual(before, self.snapshot())

    def test_every_save_checked_not_only_newest(self):
        old = self.bound("old.sfs")
        self.bound("newest.sfs")
        old.write_bytes(b"changed")
        self.assertIn("save name or bytes", self.reason())

    def test_changed_master_blocks_even_empty_profile(self):
        (self.data / "FO4Port.esm").write_bytes(b"other release")
        self.assertIn("installed bytes", self.reason())

    def test_changed_layout_refuses_bound_save(self):
        self.bound()
        changed = copy.deepcopy(self.release)
        changed["state_layouts"] = {"focc": {"format": "focc", "envelope_schema": 1, "payload_schema": "v2"}}
        self.marker.write_text(json.dumps(changed))
        self.assertIn("layout changed", self.reason())

    def test_unconfirmed_profile_and_custom_save_override_refuse(self):
        self.values["instance"] = ""
        self.assertIn("confirm", self.reason())
        self.values["instance"] = str(self.game)
        (self.my_games / "StarfieldCustom.ini").write_text("[General]\nSLocalSavePath=Saves\\Other\\\n")
        self.assertIn("overrides", self.reason())

    def test_bad_or_unreadable_declaration_and_binding_refuse(self):
        self.marker.write_text("{")
        self.assertIn("refused", self.reason())
        self.marker.write_text(json.dumps(self.release))
        save = self.bound()
        save.with_name(save.name + sr.BINDING_SUFFIX).write_text("{")
        self.assertIn("refused", self.reason())

    def test_file_named_as_save_directory_and_inventory_limit_refuse(self):
        (self.saves / "bad.sfs").mkdir()
        self.assertIn("refused", self.reason())
        (self.saves / "bad.sfs").rmdir()
        self.bound()
        with mock.patch.object(sr, "MAX_PROFILE_SAVES", 0):
            self.assertIn("inventory", self.reason())

    def test_links_refuse_instead_of_following_player_data(self):
        target = self.root / "foreign.json"
        target.write_text(json.dumps(self.release))
        self.marker.unlink()
        try:
            self.marker.symlink_to(target)
        except OSError as error:
            self.skipTest(str(error))
        self.assertIn("link", self.reason())
        self.marker.unlink()
        self.marker.write_text(json.dumps(self.release))
        save = self.bound()
        binding = save.with_name(save.name + sr.BINDING_SUFFIX)
        target.write_bytes(binding.read_bytes())
        binding.unlink()
        binding.symlink_to(target)
        self.assertIn("link", self.reason())

    def test_play_and_dry_run_refuse_before_any_settings_or_process_call(self):
        (self.saves / "old.sfs").write_bytes(b"unbound")
        before = self.snapshot()
        for dry in (False, True):
            system = FakeSystem([])
            with mock.patch.object(crashwatch, "apply_papyrus") as papyrus:
                with self.assertRaisesRegex(ValueError, "Save release check refused"):
                    crashwatch.play(self.values, str(self.game), system=system, folder=str(self.game), dry_run=dry)
                papyrus.assert_not_called()
            self.assertEqual(system.calls + system.ran + system.spawned, [])
        self.assertEqual(before, self.snapshot())

    def test_cli_gate_rechecked_after_settings_before_load_order(self):
        values = settings.defaults()
        values.update(starfield=str(self.game), route="exe", load_order="off")
        (self.game / "Starfield.exe").write_bytes(b"")
        # Consumer is inactive before settings, then sees a declaration appear.
        self.marker.unlink()
        def installed(*args):
            self.marker.write_text(json.dumps(self.release))
        system = FakeSystem([])
        with mock.patch.object(crashwatch, "apply_papyrus", side_effect=installed):
            with mock.patch.object(crashwatch, "apply_load_order") as order:
                with self.assertRaisesRegex(ValueError, "Save release check refused"):
                    crashwatch.play(values, str(self.game), system=system)
                order.assert_not_called()
        self.assertEqual(system.calls, [])

    def test_gui_launch_worker_runs_cli_gate_without_ui_poll_hashing(self):
        (self.game / "Starfield.exe").write_bytes(b"")
        (self.saves / "old.sfs").write_bytes(b"unbound")
        path = self.root / "settings.json"
        settings.save(str(path), self.values)
        model = gui.SettingsModel(str(ROOT / "scripts/launcher.py"), str(path))
        with mock.patch.object(gui.paths, "check", return_value=""):
            with mock.patch.object(sr, "play_reason", side_effect=AssertionError("hash on UI thread")):
                argv = model.command("play", self.values, starfield=str(self.game), pids=[], windows=True)
        # Same command as the GUI's existing worker, kept synthetic with --dry-run.
        result = subprocess.run(argv + ["--dry-run"], capture_output=True, text=True,
                                env=dict(os.environ, LOCALAPPDATA=str(self.root / "local")))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Save release check refused", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
