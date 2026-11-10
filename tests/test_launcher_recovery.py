"""Synthetic interrupted installs: the real installer owns rollback; no game is started."""
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
from fo4sf.launcher import crashwatch, gui, recovery, settings  # noqa: E402
from test_launcher_crashwatch import FakeSystem  # noqa: E402
from test_launcher_restore import tes4  # noqa: E402


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        (self.game / "Starfield.exe").write_bytes(b"")
        self.local = self.root / "local"
        self.plugins = self.local / "Starfield" / "Plugins.txt"
        self.plugins.parent.mkdir(parents=True)
        self.original = b"\xef\xbb\xbf# player comment\r\n*Other.esm\r\n"
        self.plugins.write_bytes(self.original)
        self.env = dict(os.environ, LOCALAPPDATA=str(self.local))
        self.record = self.data / "FO4SFExp.install.json"
        self.settings_path = self.root / "settings.json"
        self.values = settings.defaults()
        self.values.update(starfield=str(self.game), route="exe", update="off")
        settings.save(str(self.settings_path), self.values)
        self.launcher = ROOT / "scripts" / "launcher.py"

    def receipt(self, rec):
        self.record.write_text(json.dumps(rec), encoding="utf-8")

    def recover(self, **kwargs):
        return recovery.recover(str(self.game), str(ROOT), env=self.env, say=lambda *_: None,
                                running=kwargs.pop("running", lambda: False), **kwargs)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-I", str(self.launcher), *args,
                               "--settings", str(self.settings_path)], env=self.env,
                              capture_output=True, text=True)

    def interrupted_experiment(self):
        stage = self.root / "stage"
        stage.mkdir()
        (stage / "Example.esm").write_bytes(tes4())
        result = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/game/exp_install.py"),
                                 "install", "--exp-dir", str(stage), "--starfield", str(self.game)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rec = json.loads(self.record.read_text())
        # Process died after the atomic Plugins.txt publication, before committing complete.
        rec["complete"] = False
        self.receipt(rec)

    def test_play_and_dry_run_refuse_before_settings_or_process_mutations(self):
        self.receipt({"complete": False, "plugins_restore_pending": True})
        before = self.record.read_bytes(), self.plugins.read_bytes()
        for dry_run in (False, True):
            system = FakeSystem([])
            with mock.patch.object(crashwatch, "apply_papyrus") as papyrus:
                with self.assertRaisesRegex(ValueError, "Choose Recover install"):
                    crashwatch.play(self.values, str(self.game), system=system, dry_run=dry_run)
                papyrus.assert_not_called()
            self.assertEqual(system.calls + system.ran + system.spawned, [])
        self.assertEqual((self.record.read_bytes(), self.plugins.read_bytes()), before)

    def test_gate_rechecks_after_settings_before_start(self):
        system = FakeSystem([])
        with mock.patch.object(crashwatch, "apply_papyrus", side_effect=lambda *a:
                               self.receipt({"complete": False})):
            with self.assertRaisesRegex(ValueError, "Installation incomplete"):
                crashwatch.play(self.values, str(self.game), system=system)
        self.assertEqual(system.calls, [])

    def test_real_rollback_restores_plugin_bytes_and_preserves_unowned_files(self):
        self.interrupted_experiment()
        stranger = self.data / "Stranger.txt"
        stranger.write_bytes(b"keep")
        self.assertIn("incomplete", recovery.play_reason(str(self.game)))
        self.recover(apply=True)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertEqual(stranger.read_bytes(), b"keep")
        self.assertFalse((self.data / "Example.esm").exists())
        self.assertFalse(self.record.exists())
        self.assertEqual(recovery.play_reason(str(self.game)), "")
        self.recover(apply=True)  # retry after success does nothing

    def test_preview_and_cli_dry_run_preserve_interrupted_state(self):
        self.interrupted_experiment()
        before = self.record.read_bytes(), self.plugins.read_bytes()
        result = self.cli("recover-install")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Preview only", result.stdout)
        result = self.cli("play", "--dry-run")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Recover install", result.stdout)
        self.assertEqual((self.record.read_bytes(), self.plugins.read_bytes()), before)

    def test_cli_apply_runs_real_rollback(self):
        self.interrupted_experiment()
        result = self.cli("recover-install", "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_partial_or_external_plugin_edit_is_backed_up_before_rollback(self):
        self.interrupted_experiment()
        partial = b"# interrupted or edited\r\n*Exam"
        self.plugins.write_bytes(partial)
        self.recover(apply=True)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertEqual([p.read_bytes() for p in self.plugins.parent.glob("Plugins.txt.recovery-*.bak")], [partial])
        self.assertFalse(self.record.exists())

    def test_failed_backup_or_changed_plugins_prevents_any_rollback(self):
        self.interrupted_experiment()
        partial = b"*Exam"
        self.plugins.write_bytes(partial)
        before = self.record.read_bytes()
        with mock.patch.object(recovery.tempfile, "mkstemp", side_effect=PermissionError("backup denied")):
            with self.assertRaisesRegex(PermissionError, "backup denied"):
                self.recover(apply=True)
        self.assertEqual((self.plugins.read_bytes(), self.record.read_bytes()), (partial, before))
        real = recovery.restore.write_plugins_txt
        def concurrent_edit(*args):
            self.plugins.write_bytes(b"new external edit")
            return real(*args)
        with mock.patch.object(recovery.restore, "write_plugins_txt", side_effect=concurrent_edit):
            with self.assertRaisesRegex(recovery.restore.RestoreRefused, "changed"):
                self.recover(apply=True)
        self.assertEqual(self.plugins.read_bytes(), b"new external edit")
        self.assertEqual(self.record.read_bytes(), before)
        self.assertTrue((self.data / "Example.esm").exists())

    def test_a_different_profiles_journal_cannot_restore_our_list(self):
        self.interrupted_experiment()
        rec = json.loads(self.record.read_text())
        rec["plugins_txt"] = str(self.root / "someone-else/Starfield/Plugins.txt")
        self.receipt(rec)
        self.plugins.write_bytes(b"*Exam")
        with self.assertRaisesRegex(ValueError, "different Plugins.txt"):
            self.recover(apply=True)
        self.assertEqual(self.plugins.read_bytes(), b"*Exam")

    def test_absent_original_list_is_restored_as_absent_after_partial_publication(self):
        self.plugins.unlink()
        self.interrupted_experiment()
        self.plugins.write_bytes(b"*Exam")
        self.recover(apply=True)
        self.assertFalse(self.plugins.exists())
        self.assertFalse(self.record.exists())
        self.assertEqual([p.read_bytes() for p in self.plugins.parent.glob("Plugins.txt.recovery-*.bak")], [b"*Exam"])

    def test_failed_installer_retains_gate_and_retry_uses_the_same_receipt(self):
        self.interrupted_experiment()
        before = self.record.read_bytes(), self.plugins.read_bytes()
        with mock.patch.object(recovery.subprocess, "run", return_value=mock.Mock(returncode=1)) as run:
            with self.assertRaisesRegex(ValueError, "keep the journal"):
                self.recover(apply=True, run=run)
        self.assertEqual((self.record.read_bytes(), self.plugins.read_bytes()), before)
        self.assertIn("incomplete", recovery.play_reason(str(self.game)))
        self.recover(apply=True)
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_running_unknown_or_changed_state_starts_no_rollback(self):
        self.receipt({"complete": False})
        with mock.patch.object(recovery.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "Close Starfield"):
                self.recover(apply=True, running=lambda: True, run=run)
            run.assert_not_called()
        states = iter((False, True))
        with mock.patch.object(recovery.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "state changed"):
                self.recover(apply=True, running=lambda: next(states), run=run)
            run.assert_not_called()

    def test_corrupt_and_wrong_type_receipts_block_without_guessing(self):
        for raw in (b"{", b"[]", b"null", b"{}", b"\xff"):
            self.record.write_bytes(raw)
            self.assertIn("unreadable", recovery.play_reason(str(self.game)))
            with self.assertRaisesRegex(ValueError, "preserve"):
                self.recover(apply=True)
            self.assertEqual(self.record.read_bytes(), raw)

    def test_healthy_restore_pending_and_legacy_receipts_are_not_rolled_back(self):
        for rec in ({"complete": True, "plugins_restore_pending": True}, {"files": {}}):
            self.receipt(rec)
            self.assertEqual(recovery.play_reason(str(self.game)), "")
            with mock.patch.object(recovery.subprocess, "run") as run:
                self.recover(apply=True, run=run)
                run.assert_not_called()

    def test_all_known_journals_cleanup_and_completed_rollback_gate_play(self):
        for name, _script in recovery.restore.COMPONENTS.values():
            path = self.data / name
            for rec in ({"complete": False}, {"complete": True, "cleanup_pending": True},
                        {"complete": False, "rollback_completed": {}}):
                path.write_text(json.dumps(rec))
                self.assertIn("incomplete", recovery.play_reason(str(self.game)))
            path.unlink()

    def test_healthy_rider_blocks_base_rollback_before_any_command(self):
        self.receipt({"complete": False})
        (self.data / "FO4SFMapMarkers.install.json").write_text('{"complete": true}')
        with mock.patch.object(recovery.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "markers still needs experiment"):
                self.recover(apply=True, run=run)
            run.assert_not_called()

    def test_gui_blocks_play_and_delegates_one_recovery_action(self):
        self.receipt({"complete": False})
        model = gui.SettingsModel(str(self.launcher), str(self.settings_path))
        self.assertIn("Recover install", model.play_reason(model.saved, "", [], windows=True))
        argv = model.command("recover-install", model.saved, pids=[])
        self.assertEqual(argv[4:], ["recover-install", "--settings", str(self.settings_path),
                                    "--starfield", str(self.game), "--apply"])
        for pids in (None, [42]):
            with self.assertRaisesRegex(ValueError, "Close Starfield"):
                model.command("recover-install", model.saved, pids=pids)

    def test_saved_instance_controls_gate_and_recovery_target(self):
        other = self.root / "other"
        (other / "Data").mkdir(parents=True)
        (other / "Data/FO4SFExp.install.json").write_text('{"complete": false}')
        self.values["instance"] = str(other)
        settings.save(str(self.settings_path), self.values)
        model = gui.SettingsModel(str(self.launcher), str(self.settings_path))
        self.assertIn("incomplete", model.play_reason(model.saved, str(self.game), [], windows=True))
        argv = model.command("recover-install", model.saved, starfield=str(self.game), pids=[])
        self.assertEqual(argv[-3:], ["--starfield", str(other), "--apply"])
        result = self.cli("recover-install", "--starfield", str(self.game), "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertIn("saved FO4SF", result.stdout)
