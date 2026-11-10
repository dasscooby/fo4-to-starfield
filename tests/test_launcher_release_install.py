"""Synthetic release metadata publication, interruptions and ownership; no game."""
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
from fo4sf.launcher import instance, release_install as ri, save_release as sr, settings  # noqa: E402


class ReleaseInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "instance"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        (self.game / "Starfield.exe").write_bytes(b"synthetic exe")
        (self.data / "FO4Port.esm").write_bytes(b"synthetic master")
        self.receipt = self.game / instance.RECORD
        self.original = {"schema": 1, "complete": True, "source": "synthetic", "made": ["Starfield.exe"]}
        self.receipt.write_bytes(ri.encode(self.original))
        self.candidate = self.root / "candidate.json"
        self.release = {"schema": 1, "release_id": "release-旅", "masters": [
            dict(sr.identity(self.data / "FO4Port.esm"), name="FO4Port.esm")], "state_layouts": {}}
        self.candidate.write_bytes(ri.encode(self.release))
        self.target = self.data / sr.RELEASE_FILE
        self.values = settings.defaults()
        self.values.update(instance=str(self.game))
        self.settings_path = self.root / "settings.json"
        settings.save(str(self.settings_path), self.values)

    def publish(self, **kwargs):
        return ri.publish(self.values, self.candidate, running=kwargs.pop("running", lambda: False),
                          say=lambda *_: None, **kwargs)

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def test_preview_is_read_only(self):
        before = self.snapshot()
        self.publish()
        self.assertEqual(before, self.snapshot())

    def test_initial_publish_preserves_receipt_and_all_saves(self):
        save = self.root / "old.sfs"
        save.write_bytes(b"unbound save must never be adopted")
        self.publish(apply=True)
        rec = json.loads(self.receipt.read_bytes())
        self.assertEqual({k: rec[k] for k in self.original}, self.original)
        self.assertTrue(rec[ri.FIELD]["complete"])
        self.assertEqual(ri.installed(self.game), sr.declaration(self.release))
        self.assertEqual(save.read_bytes(), b"unbound save must never be adopted")
        self.assertFalse(save.with_name(save.name + sr.BINDING_SUFFIX).exists())

    def test_identical_repeat_does_not_rewrite(self):
        self.publish(apply=True)
        before = self.snapshot()
        self.publish(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_owned_missing_or_changed_declaration_refuses_play_and_publish(self):
        self.publish(apply=True)
        for raw in (None, b"{}"):
            if self.target.exists():
                self.target.unlink()
            if raw is not None:
                self.target.write_bytes(raw)
            self.assertIn("missing or changed", sr.play_reason(self.values, self.game))
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                self.publish(apply=True)
            self.assertEqual(before, self.snapshot())

    def test_unowned_existing_declaration_never_adopted(self):
        self.target.write_bytes(self.candidate.read_bytes())
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "unowned"):
            self.publish(apply=True)
        self.assertIn("no installer ownership", sr.play_reason(self.values, self.game))
        self.assertEqual(before, self.snapshot())

    def test_interruption_before_or_after_declaration_resumes_same_input(self):
        for fail_at in (2, 3):
            self.receipt.write_bytes(ri.encode(self.original))
            if self.target.exists():
                self.target.unlink()
            real_write = ri._write
            calls = []
            def interrupted(*args):
                calls.append(args)
                if len(calls) == fail_at:
                    raise OSError("synthetic interruption")
                return real_write(*args)
            with mock.patch.object(ri, "_write", side_effect=interrupted):
                with self.assertRaisesRegex(OSError, "synthetic interruption"):
                    self.publish(apply=True)
            self.assertIn("repeat install-release", sr.play_reason(self.values, self.game))
            self.publish(apply=True)
            self.assertEqual(ri.installed(self.game), sr.declaration(self.release))

    def test_interrupted_upgrade_retains_old_identity_then_resumes(self):
        self.publish(apply=True)
        old_raw = self.target.read_bytes()
        self.release["release_id"] = "B"
        self.candidate.write_bytes(ri.encode(self.release))
        # A durable pending receipt with the old declaration still in place.
        rec = json.loads(self.receipt.read_bytes())
        rec[ri.FIELD] = {"schema": 1, "complete": False, "previous": ri.pin(old_raw),
                         "declaration": ri.pin(ri.encode(sr.declaration(self.release)))}
        self.receipt.write_bytes(ri.encode(rec))
        self.assertEqual(self.target.read_bytes(), old_raw)
        self.publish(apply=True)
        self.assertEqual(ri.installed(self.game)["release_id"], "B")

    def test_pending_different_input_or_unknown_bytes_refuse(self):
        # Initial publication interrupted before the declaration was written.
        rec = copy.deepcopy(self.original)
        rec[ri.FIELD] = {"schema": 1, "complete": False, "previous": None,
                         "declaration": ri.pin(ri.encode(sr.declaration(self.release)))}
        self.receipt.write_bytes(ri.encode(rec))
        changed = dict(self.release, release_id="other")
        self.candidate.write_bytes(ri.encode(changed))
        with self.assertRaisesRegex(ValueError, "different release"):
            self.publish(apply=True)
        self.candidate.write_bytes(ri.encode(self.release))
        self.target.write_bytes(b"unknown")
        with self.assertRaisesRegex(ValueError, "unknown bytes"):
            self.publish(apply=True)

    def test_running_game_or_failed_query_never_begin(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "close Starfield"):
            self.publish(apply=True, running=lambda: True)
        with self.assertRaisesRegex(ValueError, "process query"):
            self.publish(apply=True, running=mock.Mock(side_effect=ValueError("process query")))
        self.assertEqual(before, self.snapshot())

    def test_game_start_between_writes_retains_pending(self):
        with self.assertRaisesRegex(ValueError, "remains pending"):
            self.publish(apply=True, running=mock.Mock(side_effect=[False, True]))
        self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
        self.assertFalse(self.target.exists())

    def test_changed_master_or_incomplete_installer_refuses_without_writes(self):
        (self.data / "FO4Port.esm").write_bytes(b"wrong")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "installed bytes"):
            self.publish(apply=True)
        self.assertEqual(before, self.snapshot())
        (self.data / "FO4SFExp.install.json").write_text('{"complete":false}')
        with self.assertRaisesRegex(ValueError, "Installation incomplete"):
            self.publish(apply=True)

    def test_observed_concurrent_receipt_edit_is_preserved(self):
        expected = self.receipt.read_bytes()
        self.receipt.write_bytes(b"other writer")
        with self.assertRaisesRegex(ValueError, "metadata changed"):
            ri._write(self.receipt, b"replacement", expected)
        self.assertEqual(self.receipt.read_bytes(), b"other writer")
        self.assertEqual(list(self.game.glob("*.part")), [])

    def test_unknown_ownership_schema_refuses(self):
        self.publish(apply=True)
        rec = json.loads(self.receipt.read_bytes())
        rec[ri.FIELD]["schema"] = 2
        self.receipt.write_bytes(ri.encode(rec))
        self.assertIn("unknown release ownership", sr.play_reason(self.values, self.game))

    def test_null_ownership_is_corrupt_not_legacy(self):
        rec = dict(self.original, save_release=None)
        self.receipt.write_bytes(ri.encode(rec))
        self.assertIn("release ownership", sr.play_reason(self.values, self.game))
        with self.assertRaisesRegex(ValueError, "release ownership"):
            self.publish(apply=True)

    def test_linked_input_or_receipt_refuses_before_writes(self):
        other = self.root / "foreign.json"
        other.write_bytes(self.candidate.read_bytes())
        self.candidate.unlink()
        try:
            self.candidate.symlink_to(other)
        except OSError as error:
            self.skipTest(str(error))
        before = self.receipt.read_bytes()
        with self.assertRaisesRegex(ValueError, "linked"):
            self.publish(apply=True)
        self.assertEqual(self.receipt.read_bytes(), before)
        self.candidate.unlink()
        self.candidate.write_bytes(other.read_bytes())
        other.write_bytes(before)
        self.receipt.unlink()
        self.receipt.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "linked"):
            self.publish(apply=True)
        self.assertEqual(other.read_bytes(), before)

    def test_cli_preview_and_apply_are_explicit_and_synthetic(self):
        argv = [sys.executable, "-I", str(ROOT / "scripts/launcher.py"), "install-release",
                "--settings", str(self.settings_path), "--declaration", str(self.candidate)]
        env = dict(os.environ, LOCALAPPDATA=str(self.root / "local"))
        before = self.snapshot()
        result = subprocess.run(argv, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
        result = subprocess.run(argv + ["--apply"], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(ri.installed(self.game), sr.declaration(self.release))


if __name__ == "__main__":
    unittest.main()
