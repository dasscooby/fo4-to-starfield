"""Synthetic release metadata publication, interruptions and ownership; no game."""
import copy
import json
import importlib.util
import contextlib
import io
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
        self.my_games = self.root / "My Games"
        self.my_games.mkdir()
        self.plugins = Path(instance.plugins_txt(str(self.game)))
        self.plugins.parent.mkdir(parents=True)
        self.plugins.write_text("*FO4Port.esm\n")
        (self.game / "Starfield.exe").write_bytes(b"synthetic exe")
        (self.data / "FO4Port.esm").write_bytes(b"synthetic master")
        self.receipt = self.game / instance.RECORD
        self.original = {"schema": 1, "complete": True, "source": "synthetic", "made": ["Starfield.exe"]}
        self.receipt.write_bytes(ri.encode(self.original))
        self.candidate = self.root / "candidate.json"
        self.release = {"schema": 2, "implicit_loaders": {"game": None, "my_games": None}, "release_id": "release-旅", "masters": [
            dict(sr.identity(self.data / "FO4Port.esm"), name="FO4Port.esm")], "state_layouts": {}}
        self.candidate.write_bytes(ri.encode(self.release))
        self.target = self.data / sr.RELEASE_FILE
        self.values = settings.defaults()
        self.values.update(instance=str(self.game), my_games=str(self.my_games))
        self.settings_path = self.root / "settings.json"
        settings.save(str(self.settings_path), self.values)

    def publish(self, **kwargs):
        return ri.publish(self.values, self.candidate, running=kwargs.pop("running", lambda: False),
                          say=lambda *_: None, **kwargs)

    def snapshot(self):
        return {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def managed(self, call=None, **kwargs):
        command = kwargs.pop("command", ["synthetic-installer", "--starfield", str(self.game)])
        return ri.run(self.values, self.candidate, command, call=call or (lambda *a, **k: 0),
                      running=kwargs.pop("running", lambda: False), say=lambda *_: None, **kwargs)

    def test_managed_command_has_pending_pin_before_replacing_old_master(self):
        self.publish(apply=True)
        old = self.target.read_bytes()
        new_bytes = b"new synthetic master for new release"
        self.release["release_id"] = "B"
        self.release["masters"][0].update(ri.pin(new_bytes))
        self.candidate.write_bytes(ri.encode(self.release))
        seen = []
        def install(command, cwd, env):
            self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
            self.assertEqual(self.target.read_bytes(), old)
            self.assertIn("repeat install-release", sr.play_reason(self.values, self.game))
            self.assertEqual(env["LOCALAPPDATA"], instance.local_dir(self.game))
            seen.append(command)
            (self.data / "FO4Port.esm").write_bytes(new_bytes)
            return 0
        self.assertEqual(self.managed(install), 0)
        self.assertEqual(ri.installed(self.game), sr.declaration(self.release))
        self.assertEqual(len(seen), 1)
        self.assertEqual({k: json.loads(self.receipt.read_bytes())[k] for k in self.original}, self.original)

    def test_managed_failure_or_exception_stays_pending_then_resumes(self):
        for failure in (7, OSError("synthetic stop")):
            self.receipt.write_bytes(ri.encode(self.original))
            self.target.unlink(missing_ok=True)
            def install(*args, **kwargs):
                if isinstance(failure, Exception):
                    raise failure
                return failure
            if isinstance(failure, Exception):
                with self.assertRaisesRegex(OSError, "synthetic stop"):
                    self.managed(install)
            else:
                self.assertEqual(self.managed(install), failure)
            self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
            self.assertFalse(self.target.exists())
            self.assertIn("repeat install-release", sr.play_reason(self.values, self.game))
            self.assertEqual(self.managed(), 0)
            self.assertEqual(ri.installed(self.game), sr.declaration(self.release))

    def test_managed_target_refused_before_any_write_or_command(self):
        before = self.snapshot()
        call = mock.Mock(return_value=0)
        for command in ([], ["x"], ["x", "--starfield", str(self.root)],
                        ["x", "--starfield", str(self.game), "--starf", str(self.game)]):
            with self.assertRaises(ValueError):
                self.managed(call, command=command)
        call.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_managed_running_or_failed_query_refuses_before_writes(self):
        before = self.snapshot()
        call = mock.Mock(return_value=0)
        for running in (lambda: True, mock.Mock(side_effect=ValueError("query unavailable"))):
            with self.assertRaises(ValueError):
                self.managed(call, running=running)
        call.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_managed_game_appearing_after_pending_never_runs_command(self):
        call = mock.Mock(return_value=0)
        with self.assertRaisesRegex(ValueError, "remains pending"):
            self.managed(call, running=mock.Mock(side_effect=[False, False, True]))
        call.assert_not_called()
        self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])

    def test_managed_omitted_declaration_refuses_legacy_runner(self):
        self.publish(apply=True)
        call = mock.Mock(return_value=0)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "needs --declaration"):
            instance.run(str(self.game), ["x", "--starfield", str(self.game)], call=call)
        call.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_managed_changed_candidate_refuses_and_original_can_resume(self):
        original = self.candidate.read_bytes()
        def change(*args, **kwargs):
            self.candidate.write_bytes(ri.encode(dict(self.release, release_id="unexpected")))
            return 0
        with self.assertRaisesRegex(ValueError, "input changed"):
            self.managed(change)
        self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
        self.assertFalse(self.target.exists())
        with self.assertRaisesRegex(ValueError, "different release"):
            self.managed()
        self.candidate.write_bytes(original)
        self.assertEqual(self.managed(), 0)

    def test_managed_concurrent_receipt_edit_preserved(self):
        changed = []
        def change(*args, **kwargs):
            rec = json.loads(self.receipt.read_bytes())
            rec["other_writer"] = True
            changed.append(ri.encode(rec))
            self.receipt.write_bytes(changed[0])
            return 0
        with self.assertRaisesRegex(ValueError, "receipt changed"):
            self.managed(change)
        self.assertEqual(self.receipt.read_bytes(), changed[0])
        self.assertFalse(self.target.exists())

    def test_managed_incomplete_component_or_wrong_final_bytes_cannot_finalize(self):
        def incomplete(*args, **kwargs):
            (self.data / "FO4SFExp.install.json").write_text('{"complete":false}')
            return 0
        with self.assertRaisesRegex(ValueError, "Installation incomplete"):
            self.managed(incomplete)
        self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
        (self.data / "FO4SFExp.install.json").unlink()
        def wrong(*args, **kwargs):
            (self.data / "FO4Port.esm").write_bytes(b"wrong final master")
            return 0
        with self.assertRaisesRegex(ValueError, "installed bytes"):
            self.managed(wrong)
        self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])

    def test_managed_my_games_confirmation_required_before_writes(self):
        self.values["my_games"] = ""
        before = self.snapshot()
        call = mock.Mock(return_value=0)
        with self.assertRaisesRegex(ValueError, "My Games"):
            self.managed(call)
        self.assertEqual(before, self.snapshot())
        call.assert_not_called()

    def test_managed_cli_routes_declaration_and_refuses_unconfirmed_target(self):
        spec = importlib.util.spec_from_file_location("managed_launcher_cli", ROOT / "scripts/launcher.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        command = ["python", "synthetic.py", "--starfield", str(self.game)]
        argv = ["instance", "run", "--settings", str(self.settings_path),
                "--declaration", str(self.candidate), "--", *command]
        with mock.patch.object(ri, "run", return_value=0) as run:
            self.assertEqual(cli.main(argv), 0)
            self.assertEqual(run.call_args.args[:3], (self.values, str(self.candidate), command))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(argv[:-len(command)-1] + ["--at", str(self.root), "--", *command]), 2)
            self.assertEqual(run.call_count, 1)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["instance", "plan", "--declaration", str(self.candidate)]), 2)
            self.assertEqual(run.call_count, 1)

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

    def test_changed_ccc_during_publication_keeps_pending_receipt(self):
        calls = []
        def running():
            calls.append(True)
            if len(calls) == 2:
                (self.game / "Starfield.ccc").write_text("Starfield.esm\n")
            return False
        with self.assertRaisesRegex(ValueError, "implicit loader configuration differs"):
            self.publish(apply=True, running=running)
        self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
        self.assertFalse(self.target.exists())
        self.assertIn("repeat install-release", sr.play_reason(self.values, self.game))
        (self.game / "Starfield.ccc").unlink()
        self.publish(apply=True)
        self.assertEqual(ri.installed(self.game), sr.declaration(self.release))

    def test_publication_refuses_changed_ccc_without_writes(self):
        (self.game / "Starfield.ccc").write_text("Starfield.esm\n")
        before = self.snapshot()
        for apply in (False, True):
            with self.assertRaisesRegex(ValueError, "implicit loader configuration differs"):
                self.publish(apply=apply)
        self.assertEqual(before, self.snapshot())

    def test_publication_refuses_other_active_configuration_without_writes(self):
        self.plugins.write_text("FO4Port.esm\n")
        before = self.snapshot()
        for apply in (False, True):
            with self.assertRaisesRegex(ValueError, "active master set/order"):
                self.publish(apply=apply)
        self.assertEqual(before, self.snapshot())

    def native_fixture(self):
        from fo4sf.launcher import runtimes as rt
        folder = self.data / "SFSE/Plugins"
        folder.mkdir(parents=True, exist_ok=True)
        dll = folder / "FOCCPing.dll"
        dll.write_bytes(b"synthetic probe")
        library = folder / rt._native_table()["address_library"]["file"]
        library.write_bytes(b"synthetic library")
        (self.game / "sfse_loader.exe").write_bytes(b"synthetic loader")
        sfse = self.game / "sfse_1_16_244.dll"
        sfse.write_bytes(b"synthetic sfse")
        runtime = rt._native_table()["runtime"]
        entry = {"exe_sha256": ri.pin(b"synthetic exe")["sha256"], "exe_version": runtime,
                 "sfse": {"loader_sha256": ri.pin(b"synthetic loader")["sha256"],
                          "dlls": {sfse.name: ri.pin(sfse.read_bytes())["sha256"]}},
                 "native": {"schema": 1, "plugins": {dll.name: dict(ri.pin(dll.read_bytes()),
                     runtime=runtime, required=False, needs_address_library=True,
                     source_commit="c" * 40, artifact_receipt="synthetic fixture")},
                     "address_library": dict(ri.pin(library.read_bytes()), file=library.name,
                                             provenance="synthetic fixture")}}
        patch = mock.patch.object(rt, "load_runtimes", return_value={"schema": 1, "runtimes": [entry]})
        patch.start()
        self.addCleanup(patch.stop)
        return dll, library, sfse

    def test_native_publication_unknown_identity_refuses_wet_dry_and_cli(self):
        folder = self.data / "SFSE/Plugins"
        folder.mkdir(parents=True)
        (folder / "FOCCPing.dll").write_bytes(b"unknown synthetic native")
        before = self.snapshot()
        for apply in (False, True):
            with self.assertRaisesRegex(ValueError, "no measured identity"):
                self.publish(apply=apply)
        argv = [sys.executable, "-I", str(ROOT / "scripts/launcher.py"), "install-release",
                "--settings", str(self.settings_path), "--declaration", str(self.candidate)]
        for extra in ([], ["--apply"]):
            result = subprocess.run(argv + extra, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("no measured identity", result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_native_publication_matching_and_changed_dependency_controls(self):
        paths = self.native_fixture()
        before = self.snapshot()
        self.publish()
        self.assertEqual(before, self.snapshot())
        for path in paths:
            raw = path.read_bytes()
            for bad in (None, b"changed"):
                if bad is None:
                    path.unlink()
                else:
                    path.write_bytes(bad)
                # Optional absent probe does not need its library/SFSE at all.
                if path == paths[0] and bad is None:
                    self.publish()
                else:
                    with self.assertRaises(ValueError):
                        self.publish(apply=True)
                self.assertFalse(self.target.exists())
            path.write_bytes(raw)
        self.publish(apply=True)
        self.assertEqual(ri.installed(self.game), sr.declaration(self.release))
        paths[0].write_bytes(b"changed after complete")
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.publish(apply=True)
        self.assertEqual(before, self.snapshot())

    def test_native_change_at_each_publication_boundary_stays_pending_and_resumes(self):
        dll, _, _ = self.native_fixture()
        valid = dll.read_bytes()
        real = ri._write
        for boundary in (self.receipt, self.target):
            self.receipt.write_bytes(ri.encode(self.original))
            self.target.unlink(missing_ok=True)
            dll.write_bytes(valid)
            def changed(path, raw, expected):
                real(path, raw, expected)
                if path == boundary:
                    dll.write_bytes(b"changed during publication")
            with mock.patch.object(ri, "_write", side_effect=changed):
                with self.assertRaises(ValueError):
                    self.publish(apply=True)
            self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
            dll.write_bytes(valid)
            self.publish(apply=True)
            self.assertEqual(ri.installed(self.game), sr.declaration(self.release))

    def test_managed_installer_can_replace_unknown_native_but_cannot_finalize_wrong_bytes(self):
        dll, _, _ = self.native_fixture()
        valid = dll.read_bytes()
        dll.write_bytes(b"old native to replace")
        def install(*args, **kwargs):
            self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
            dll.write_bytes(valid)
            return 0
        self.assertEqual(self.managed(install), 0)
        dll.write_bytes(b"wrong final native")
        with self.assertRaises(ValueError):
            self.managed()
        self.assertFalse(json.loads(self.receipt.read_bytes())[ri.FIELD]["complete"])
        dll.write_bytes(valid)
        self.assertEqual(self.managed(), 0)


if __name__ == "__main__":
    unittest.main()
