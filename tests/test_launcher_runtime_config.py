"""Runtime config ownership, interruption and launch gates on synthetic folders."""
import contextlib
import importlib.util
import io
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from fo4sf.launcher import crashwatch, instance, release_install as ri, runtime_config as rc, settings  # noqa: E402
from test_launcher_crashwatch import FakeSystem  # noqa: E402

DIRECTORY = r"C:\Profiles\Jürgen Ødegård\Documents\My Games\Starfield\Saves\FO4SF\FO4SF-Runtime"


class SyntaxTests(unittest.TestCase):
    def test_accepted_upstream_vectors_and_deterministic_round_trip(self):
        cases = json.loads((ROOT / "tests/data/runtime_dir_vectors.json").read_text())["cases"]
        for case in cases:
            with self.subTest(case["name"]):
                if case["ok"]:
                    self.assertEqual(rc.parse(case["text"].encode()), case["dir"])
                    encoded = rc.encode(case["dir"])
                    self.assertEqual(rc.parse(encoded), case["dir"])
                    self.assertEqual(encoded, ("[Runtime]\nDir=" + case["dir"] + "\n").encode())
                else:
                    with self.assertRaisesRegex(ValueError, case["error"].replace("[", r"\[").replace("]", r"\]")):
                        rc.parse(case["text"].encode())

    def test_invalid_utf8_over_limit_and_injection_refuse(self):
        for raw in (b"[Runtime]\nDir=C:\\R\xff", b";" * (rc.MAX_INI + 1)):
            with self.assertRaises(ValueError):
                rc.parse(raw)
        for directory in ("C:\\R\nDir=D:\\other", "C:\\R\n[Other]", "C:\\R\t", "C:\\R\n"):
            with self.assertRaises(ValueError):
                rc.encode(directory)
        line = b"[Runtime]\nDir=C:\\R\n"
        self.assertEqual(rc.parse(line + b";" * (rc.MAX_INI - len(line))), r"C:\R")


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "instance"
        self.plugins = self.game / "Data/SFSE/Plugins"
        self.plugins.mkdir(parents=True)
        self.my_games = self.root / "My Games/Starfield"
        self.saves = self.my_games / "Saves/FO4SF"
        self.saves.mkdir(parents=True)
        (self.game / "Starfield.exe").write_bytes(b"synthetic exe")
        (self.game / "sfse_loader.exe").write_bytes(b"synthetic loader")
        self.receipt = self.game / instance.RECORD
        self.original = {"schema": 1, "complete": True, "source": "synthetic", "made": ["Starfield.exe"],
                         "unrelated": {"keep": "旅"}}
        self.receipt.write_bytes(ri.encode(self.original))
        # An installed consumer makes configuration mandatory even for a legacy
        # instance. This is a synthetic opaque file, never a native binary.
        (self.plugins / "FOCCSidecar.dll").write_bytes(b"synthetic consumer")
        # The installed synthetic consumer now also needs a measured release
        # identity. Keep the native gate real while isolating runtime INI behavior.
        from fo4sf.launcher import runtimes as rt
        blob = b"synthetic consumer"
        library = b"synthetic library"
        native = {"schema": 1, "plugins": {"FOCCSidecar.dll": {
            "runtime": "1.16.244.0", "sha256": hashlib.sha256(blob).hexdigest(), "size": len(blob),
            "required": False, "needs_address_library": True, "source_commit": "c" * 40,
            "artifact_receipt": "synthetic fixture"}}, "address_library": {
            "file": "versionlib-1-16-244-0.bin", "sha256": hashlib.sha256(library).hexdigest(),
            "size": len(library), "provenance": "synthetic fixture"}}
        (self.plugins / native["address_library"]["file"]).write_bytes(library)
        measured = {"schema": 1, "runtimes": [{"exe_version": "1.16.244.0", "native": native,
            "exe_sha256": hashlib.sha256(b"synthetic exe").hexdigest()}]}
        runtime_table = mock.patch.object(rt, "load_runtimes", return_value=measured)
        runtime_table.start()
        self.addCleanup(runtime_table.stop)
        self.target = self.plugins / rc.NAME
        self.values = settings.defaults()
        self.values.update(instance=str(self.game), starfield=str(self.game), my_games=str(self.my_games),
                           route="exe", load_order="off")
        local = self.root / "Local"
        self.player = local / "Starfield/Plugins.txt"
        self.player.parent.mkdir(parents=True)
        self.player.write_bytes(b"*Player.esm\n")
        ours = Path(instance.plugins_txt(self.game))
        ours.parent.mkdir(parents=True)
        ours.write_bytes(b"")
        env = mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)})
        env.start()
        self.addCleanup(env.stop)
        # Host filesystem checks are real; only its Windows path spelling is
        # injected. No Linux path is allowed to masquerade as a Windows path.
        spelling = mock.patch.object(rc, "_runtime_dir", return_value=DIRECTORY)
        self.spelling = spelling.start()
        self.addCleanup(spelling.stop)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def publish(self, **kw):
        return rc.publish(self.values, self.game, running=kw.pop("running", lambda: False),
                          say=lambda *_: None, **kw)

    def play(self, system=None, **kw):
        return crashwatch.play(self.values, str(self.game), system=system or FakeSystem([(42, 0, 30, 0)]),
                               folder=str(self.game), say=lambda *_: None, **kw)

    def test_publish_tracks_config_in_existing_receipt_and_never_makes_runtime_tree(self):
        self.publish(apply=True)
        self.assertEqual(self.target.read_bytes(), rc.encode(DIRECTORY))
        receipt = ri.decode(self.receipt.read_bytes())
        self.assertEqual({k: receipt[k] for k in self.original}, self.original)
        self.assertEqual(receipt[rc.FIELD], {"schema": 1, "complete": True,
                                          "ini": ri.pin(self.target.read_bytes()), "previous": None})
        self.assertFalse((self.saves / "FO4SF-Runtime").exists())
        before = self.snapshot()
        self.publish(apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_is_read_only_even_with_missing_runtime(self):
        before = self.snapshot()
        self.publish()
        self.play(dry_run=True)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.saves / "FO4SF-Runtime").exists())

    def test_missing_save_parent_and_missing_component_folders_refuse_without_mkdir(self):
        for missing in (self.saves, self.plugins):
            with self.subTest(missing=missing):
                if missing == self.plugins:
                    (missing / "FOCCSidecar.dll").unlink()
                    (self.plugins / "versionlib-1-16-244-0.bin").unlink()
                missing.rmdir()
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, "missing"):
                    self.publish(apply=True, required=True)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(missing.exists())
                missing.mkdir()

    def test_unowned_even_identical_ini_is_preserved(self):
        for raw in (b"player config", rc.encode(DIRECTORY)):
            self.target.write_bytes(raw)
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "unowned"):
                self.publish(apply=True)
            self.assertEqual(self.snapshot(), before)

    def test_changed_or_missing_owned_ini_is_preserved(self):
        self.publish(apply=True)
        for raw in (b"external edit", None):
            if raw is None:
                self.target.unlink()
            else:
                self.target.write_bytes(raw)
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                self.publish(apply=True)
            self.assertEqual(self.snapshot(), before)

    def test_owned_replacement_preserves_previous_identity_while_pending(self):
        self.publish(apply=True)
        old = ri.pin(self.target.read_bytes())
        self.spelling.return_value = r"D:\Profiles\FO4SF-Runtime"
        real = rc._write
        seen = []
        def observe(plan, path, raw, expected, running):
            if path == self.target:
                owned = ri.decode(self.receipt.read_bytes())[rc.FIELD]
                self.assertFalse(owned["complete"])
                self.assertEqual(owned["previous"], old)
                seen.append(True)
            return real(plan, path, raw, expected, running)
        with mock.patch.object(rc, "_write", side_effect=observe):
            self.publish(apply=True)
        self.assertEqual(seen, [True])
        self.assertEqual(rc.parse(self.target.read_bytes()), self.spelling.return_value)

    def test_every_publication_boundary_interruption_blocks_play_and_resumes_same_input(self):
        initial = self.receipt.read_bytes()
        real = rc._write
        for boundary in (1, 2, 3):
            with self.subTest(boundary=boundary):
                self.receipt.write_bytes(initial)
                self.target.unlink(missing_ok=True)
                count = 0
                def interrupt(*args):
                    nonlocal count
                    count += 1
                    real(*args)
                    if count == boundary:
                        raise KeyboardInterrupt
                with mock.patch.object(rc, "_write", side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        self.publish(apply=True)
                if boundary < 3:
                    before = self.snapshot()
                    with self.assertRaisesRegex(ValueError, "incomplete"):
                        self.play()
                    self.assertEqual(self.snapshot(), before)
                    self.spelling.return_value = r"D:\other"
                    with self.assertRaisesRegex(ValueError, "different runtime config"):
                        self.publish(apply=True, resume=True)
                    self.spelling.return_value = DIRECTORY
                self.publish(apply=True, resume=True)
                self.assertTrue(ri.decode(self.receipt.read_bytes())[rc.FIELD]["complete"])

    def test_unknown_and_running_game_never_publish(self):
        for state in (True, None, [], 0):
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, "close Starfield"):
                self.publish(apply=True, running=lambda: state)
            self.assertEqual(self.snapshot(), before)
        with self.assertRaisesRegex(ValueError, "cannot query"):
            self.publish(apply=True, running=mock.Mock(side_effect=ValueError("cannot query")))

    def test_game_appearing_mid_write_leaves_pending_and_no_ini(self):
        state = False
        real = rc._write
        def after_pending(*args):
            nonlocal state
            real(*args)
            state = True
        with mock.patch.object(rc, "_write", side_effect=after_pending):
            with self.assertRaises(ValueError):
                self.publish(apply=True, running=lambda: state)
        self.assertFalse(ri.decode(self.receipt.read_bytes())[rc.FIELD]["complete"])
        self.assertFalse(self.target.exists())

    def test_concurrent_ini_edit_is_preserved_and_completion_stays_pending(self):
        real = os.fsync
        def edit(fd):
            real(fd)
            if rc.FIELD in ri.decode(self.receipt.read_bytes()):
                self.target.write_bytes(b"concurrent owner")
        with mock.patch.object(rc.os, "fsync", side_effect=edit):
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.publish(apply=True)
        self.assertEqual(self.target.read_bytes(), b"concurrent owner")
        self.assertFalse(ri.decode(self.receipt.read_bytes())[rc.FIELD]["complete"])

    def test_concurrent_receipt_edit_is_preserved(self):
        real = os.fsync
        edited = ri.encode(dict(self.original, concurrent="keep"))
        def edit(fd):
            real(fd)
            self.receipt.write_bytes(edited)
        with mock.patch.object(rc.os, "fsync", side_effect=edit):
            with self.assertRaisesRegex(ValueError, "ownership changed"):
                self.publish(apply=True)
        self.assertEqual(self.receipt.read_bytes(), edited)
        self.assertFalse(self.target.exists())

    def test_changed_parent_folder_refuses_before_replacement(self):
        real = os.fsync
        moved = self.plugins.with_name("kept")
        def move(fd):
            real(fd)
            if not moved.exists():
                self.plugins.rename(moved)
                self.plugins.mkdir()
        with mock.patch.object(rc.os, "fsync", side_effect=move):
            with self.assertRaisesRegex(ValueError, "folder changed"):
                self.publish(apply=True)
        self.assertFalse(self.target.exists())
        self.assertEqual(ri.decode(self.receipt.read_bytes()), self.original)

    def test_symlink_hardlink_and_reparse_config_targets_refuse(self):
        other = self.root / "other.ini"
        other.write_bytes(b"preserve")
        for make in (lambda: self.target.symlink_to(other), lambda: os.link(other, self.target)):
            make()
            with self.assertRaises(ValueError):
                self.publish(apply=True)
            self.assertEqual(other.read_bytes(), b"preserve")
            self.target.unlink()
        real = Path.lstat
        def reparse(path):
            info = real(path)
            if path == self.plugins:
                return type("Reparse", (), {"st_mode": info.st_mode,
                    "st_file_attributes": stat.FILE_ATTRIBUTE_REPARSE_POINT})()
            return info
        with mock.patch.object(Path, "lstat", reparse):
            with self.assertRaisesRegex(ValueError, "reparse"):
                self.publish(apply=True)

    def test_redirected_save_root_or_runtime_is_refused_without_outside_writes(self):
        other = self.root / "elsewhere"
        other.mkdir()
        for path in (self.saves, self.saves / "FO4SF-Runtime"):
            if path == self.saves:
                path.rmdir()
            path.symlink_to(other, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "linked"):
                self.publish(apply=True)
            self.assertEqual(list(other.iterdir()), [])
            path.unlink()
            if path == self.saves:
                path.mkdir()

    def test_wrong_instance_unconfirmed_profile_and_incomplete_owner_refuse(self):
        for key, bad in (("instance", ""), ("instance", str(self.root)), ("my_games", ""),
                         ("my_games", str(self.my_games / ".." / "Starfield"))):
            original = self.values[key]
            self.values[key] = bad
            with self.assertRaises(ValueError):
                self.publish(apply=True)
            self.values[key] = original
        for bad in ({"schema": 2, "complete": True}, {"schema": 1, "complete": False}):
            self.receipt.write_bytes(ri.encode(bad))
            with self.assertRaisesRegex(ValueError, "complete known instance"):
                self.publish(apply=True)

    def test_malformed_owner_and_case_alias_refuse(self):
        for owned in ({}, {"schema": 2, "complete": True, "ini": ri.pin(b"x"), "previous": None}):
            self.receipt.write_bytes(ri.encode(dict(self.original, **{rc.FIELD: owned})))
            with self.assertRaises(ValueError):
                self.publish(apply=True)
        self.receipt.write_bytes(ri.encode(self.original))
        alias = self.plugins / rc.NAME.lower()
        alias.write_bytes(b"player config")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.publish(apply=True)
        self.assertEqual(alias.read_bytes(), b"player config")

    def test_managed_release_cannot_skip_when_no_native_probe_is_installed(self):
        (self.plugins / "FOCCSidecar.dll").unlink()
        (self.game / "Data/FO4Port.esm").write_bytes(b"synthetic master")
        declaration = {"schema": 2, "release_id": "A", "masters": [dict(ri.pin(b"synthetic master"), name="FO4Port.esm")], "state_layouts": {},
                       "implicit_loaders": {"game": None, "my_games": None}}
        raw = ri.encode(declaration)
        (self.game / "Data/FO4SF.release.json").write_bytes(raw)
        self.receipt.write_bytes(ri.encode(dict(self.original, save_release={"schema": 1, "complete": True,
                                                   "declaration": ri.pin(raw), "previous": None})))
        self.saves.rmdir()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.publish(apply=True)

    def test_legacy_without_runtime_consumers_remains_unchanged(self):
        (self.plugins / "FOCCSidecar.dll").unlink()
        before = self.snapshot()
        self.assertIsNone(self.publish(apply=True))
        self.assertEqual(self.snapshot(), before)

    def test_actual_play_publishes_before_start_and_after_tools(self):
        system = FakeSystem([(42, 0, 30, 0)])
        start = system.start_game
        seen = []
        def observe(route, folder):
            self.assertEqual(self.target.read_bytes(), rc.encode(DIRECTORY))
            self.assertTrue(ri.decode(self.receipt.read_bytes())[rc.FIELD]["complete"])
            seen.append("started")
            start(route, folder)
        system.start_game = observe
        self.assertTrue(self.play(system)["started"])
        self.assertEqual(seen, ["started"])
        self.assertFalse((self.saves / "FO4SF-Runtime").exists())

    def test_post_publication_edit_refuses_start_and_restores_player_plugins(self):
        system = FakeSystem([(42, 0, 30, 0)])
        start = mock.Mock()
        system.start_game = start
        real = instance.swap_in
        def change(*args):
            real(*args)
            self.target.write_bytes(b"late edit")
        with mock.patch.object(instance, "swap_in", side_effect=change):
            with self.assertRaisesRegex(ValueError, "changed before launch"):
                self.play(system)
        start.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b"late edit")
        self.assertEqual(self.player.read_bytes(), b"*Player.esm\n")

    def test_routes_allow_unknown_and_process_errors_cannot_bypass(self):
        self.target.write_bytes(b"unowned")
        for route in ("exe", "sfse", "steam"):
            self.values["route"] = route
            self.values["allow_unknown"] = True
            system = FakeSystem([])
            system.runtime_problems = lambda *_: []
            system.start_game = mock.Mock()
            with self.assertRaises(ValueError):
                self.play(system)
            system.start_game.assert_not_called()
        self.target.unlink()
        self.values["route"] = "exe"
        for result in (None, [99], ValueError("query unknown")):
            system = FakeSystem([])
            system.pids = mock.Mock(side_effect=result) if isinstance(result, Exception) else lambda: result
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.play(system)
            self.assertEqual(self.snapshot(), before)

    def test_explicit_cli_resume_and_cli_dry_run_use_same_publisher(self):
        spec = importlib.util.spec_from_file_location("runtime_cli", ROOT / "scripts/launcher.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        path = self.root / "settings.json"
        settings.save(path, self.values)
        real = rc._write
        def interrupt(plan, target, *args):
            if target == self.target:
                raise KeyboardInterrupt
            return real(plan, target, *args)
        with mock.patch.object(rc, "_write", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.publish(apply=True)
        before = self.snapshot()
        with mock.patch.object(cli.restore, "game_running", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["configure-runtime", "--settings", str(path)]), 0)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(cli.main(["configure-runtime", "--settings", str(path), "--apply"]), 0)
        self.assertTrue(ri.decode(self.receipt.read_bytes())[rc.FIELD]["complete"])


if __name__ == "__main__":
    unittest.main()
