"""Deployment failure injection: synthetic files, no game installation required."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "deploy_starfield", Path(__file__).resolve().parents[1] / "scripts" / "deploy_starfield.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentRollbackTests(unittest.TestCase):
    def test_uninstall_disables_plugin_even_when_one_file_is_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "Data"
            data.mkdir()
            plugin = data / deploy.PLUGIN
            archive = data / deploy.ARCHIVE
            plugin.write_bytes(b"synthetic plugin")
            archive.write_bytes(b"synthetic archive")
            pt = root / "Plugins.txt"
            pt.write_text("*Other.esm\n*FO4Port.esm\n")
            manifest = data / deploy.MANIFEST
            deploy.write_manifest(str(manifest), {"files": [deploy.PLUGIN, deploy.ARCHIVE],
                "plugins_txt": str(pt), "plugins_added": ["*FO4Port.esm"], "complete": True})
            remove = deploy.os.remove

            def locked(path):
                if Path(path) == plugin:
                    raise PermissionError("injected locked plugin")
                remove(path)

            args = SimpleNamespace(starfield=str(root), dry_run=False)
            with patch.object(deploy.os, "remove", side_effect=locked):
                with self.assertRaisesRegex(SystemExit, "uninstall incomplete"):
                    deploy.uninstall(args)
            self.assertTrue(plugin.exists())
            self.assertFalse(archive.exists())
            self.assertEqual(pt.read_text().splitlines(), ["*Other.esm"])
            state = json.loads(manifest.read_text())
            self.assertEqual(state["files"], [deploy.PLUGIN])
            self.assertEqual(state["plugins_added"], [])
            deploy.uninstall(args)
            self.assertFalse(manifest.exists() or plugin.exists())
            self.assertEqual(pt.read_text().splitlines(), ["*Other.esm"])

    def run_failure(self, failure, existing_plugins=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            data = game / "Data"
            data.mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            if failure == "unfinished_build":
                (staging / "build-state.json").write_text(json.dumps({"complete": False, "status": "converting"}))
            if failure == "texture_build":
                (staging / "textures").mkdir()
            pt = root / "Plugins.txt"
            original = b"# user comment\r\n*Other.esm\r\n"
            if existing_plugins:
                pt.write_bytes(original)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)

            def build(a, out, folders, fmt):
                if failure == "texture_build" and fmt == "DDS":
                    raise SystemExit("injected texture archive failure")
                Path(out).write_bytes((b"BAD!" if failure == "invalid_archive" else b"BTDX") + bytes(32))

            original_copy = deploy.shutil.copy2
            original_dump = deploy.json.dump
            original_remove = deploy.os.remove
            original_write_lines = deploy.write_lines

            def copy(src, dst):
                if failure == "corrupt_copy":
                    Path(dst).write_bytes(b"successful call, incorrect bytes")
                    return dst
                if failure in ("copy", "cleanup"):
                    Path(dst).write_bytes(b"partial")
                    raise OSError("injected partial copy")
                return original_copy(src, dst)

            def dump(state, stream, **kwargs):
                if failure == "manifest" and state["complete"]:
                    raise OSError("injected final manifest failure")
                return original_dump(state, stream, **kwargs)

            def remove(path):
                if failure == "cleanup" and Path(path) == data / deploy.PLUGIN:
                    raise PermissionError("injected locked destination")
                return original_remove(path)

            def write_lines(path, lines):
                original_write_lines(path, lines)
                if failure == "interrupt":
                    raise KeyboardInterrupt("injected interruption after activation")

            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build), \
                    patch.object(deploy.shutil, "copy2", side_effect=copy), \
                    patch.object(deploy.json, "dump", side_effect=dump), \
                    patch.object(deploy.os, "remove", side_effect=remove), \
                    patch.object(deploy, "write_lines", side_effect=write_lines):
                with self.assertRaises(KeyboardInterrupt if failure == "interrupt" else SystemExit):
                    deploy.install(args)
            if failure == "cleanup":
                state = json.loads((data / deploy.MANIFEST).read_text())
                self.assertEqual(state["files"], [deploy.PLUGIN])
                self.assertFalse(state["complete"])
                deploy.uninstall(args)
            if failure == "interrupt":
                state = json.loads((data / deploy.MANIFEST).read_text())
                self.assertTrue(state["plugins_restore_pending"])
                self.assertFalse(state["complete"])
                deploy.uninstall(args)
            self.assertEqual(list(data.iterdir()), [])
            if existing_plugins:
                self.assertEqual(pt.read_bytes(), original)
            else:
                self.assertFalse(pt.exists())

    def test_partial_copy_is_removed(self):
        self.run_failure("copy")

    def test_successful_but_corrupt_copy_rolls_back_before_activation(self):
        self.run_failure("corrupt_copy")

    def test_success_records_exact_installed_hashes(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            plugin = b"TES4" + bytes(32)
            archive = b"BTDX" + bytes(32)
            (staging / deploy.PLUGIN).write_bytes(plugin)
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            def build(a, out, folders, fmt):
                Path(out).write_bytes(archive)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            state = json.loads((game / "Data" / deploy.MANIFEST).read_text())
            self.assertTrue(state["complete"])
            for name, payload in [(deploy.PLUGIN, plugin), (deploy.ARCHIVE, archive)]:
                self.assertEqual(state["artifacts"][name],
                    {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})

    def test_texture_build_failure_does_not_touch_installation(self):
        self.run_failure("texture_build")

    def test_invalid_archive_does_not_touch_installation(self):
        self.run_failure("invalid_archive")

    def test_interrupted_build_cannot_be_deployed(self):
        self.run_failure("unfinished_build")

    def test_final_manifest_failure_restores_plugins_exactly(self):
        self.run_failure("manifest")

    def test_rollback_removes_new_plugins_file(self):
        self.run_failure("manifest", existing_plugins=False)

    def test_failed_cleanup_retains_retryable_manifest(self):
        self.run_failure("cleanup")

    def test_interrupted_activation_is_recoverable(self):
        self.run_failure("interrupt")

    def test_interrupted_activation_removes_new_plugin_list(self):
        self.run_failure("interrupt", existing_plugins=False)

    def test_failed_manifest_write_preserves_previous_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            previous = {"files": ["owned.file"], "complete": False}
            deploy.write_manifest(str(path), previous)
            with patch.object(deploy.json, "dump", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    deploy.write_manifest(str(path), {"files": []})
            self.assertEqual(json.loads(path.read_text()), previous)
            self.assertEqual(list(Path(tmp).iterdir()), [path])
