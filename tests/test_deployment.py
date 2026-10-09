"""Deployment failure injection: synthetic files, no game installation required."""
import importlib.util
import json
import stat
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
    def test_atomic_publish_handles_read_only_source_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / "source.esm", root / "target.esm"
            source.write_bytes(b"synthetic read-only plugin")
            source.chmod(stat.S_IREAD)
            deploy.copy_new_artifact(str(source), str(target))
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual({p.name for p in root.iterdir()}, {"source.esm", "target.esm"})

    def test_publish_falls_back_to_exclusive_copy_without_hard_link_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / "source.ba2", root / "target.ba2"
            source.write_bytes(b"synthetic archive")
            with patch.object(deploy.os, "link", side_effect=OSError("hard links unavailable")):
                deploy.copy_new_artifact(str(source), str(target))
            self.assertEqual(target.read_bytes(), source.read_bytes())
            self.assertEqual({p.name for p in root.iterdir()}, {"source.ba2", "target.ba2"})

    def test_plugin_list_edit_during_copy_aborts_without_clobbering_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            data = game / "Data"
            data.mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            original = b"*Other.esm\r\n"
            edited = b"*Other.esm\r\n*UserAdded.esm\r\n"
            pt.write_bytes(original)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            real_publish = deploy.copy_new_artifact
            def publish(src, dst):
                result = real_publish(src, dst)
                if Path(dst).name == deploy.ARCHIVE:
                    pt.write_bytes(edited)
                return result
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build), \
                    patch.object(deploy, "copy_new_artifact", side_effect=publish):
                with self.assertRaisesRegex(SystemExit, "rolled back"):
                    deploy.install(args)
            self.assertEqual(pt.read_bytes(), edited)
            self.assertFalse(any((data / name).exists() for name in (deploy.PLUGIN, deploy.ARCHIVE)))
            self.assertFalse((data / deploy.MANIFEST).exists())

    def test_plugin_list_changes_during_archive_build_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            pt.write_text("*Other.esm\n")
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
                pt.write_text("*Other.esm\n*AddedDuringBuild.esm\n")
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            self.assertEqual(pt.read_text().splitlines(),
                             ["*Other.esm", "*AddedDuringBuild.esm", "*FO4Port.esm"])
            deploy.uninstall(args)
            self.assertEqual(pt.read_text().splitlines(), ["*Other.esm", "*AddedDuringBuild.esm"])

    def test_target_created_during_archive_build_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            data = game / "Data"
            data.mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            target = data / deploy.PLUGIN
            external = b"created by another process during archive build"
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)

            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
                target.write_bytes(external)

            with patch.object(deploy, "plugins_txt_path", return_value=str(root / "Plugins.txt")), \
                    patch.object(deploy, "build_archive", side_effect=build):
                with self.assertRaisesRegex(SystemExit, "recovery manifest retained"):
                    deploy.install(args)
            self.assertEqual(target.read_bytes(), external)
            self.assertTrue((data / deploy.MANIFEST).exists())
            with self.assertRaisesRegex(SystemExit, "uninstall incomplete"):
                deploy.uninstall(args)
            self.assertEqual(target.read_bytes(), external)

    def test_uninstall_preserves_artifact_changed_after_successful_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "Data"
            data.mkdir()
            plugin = data / deploy.PLUGIN
            plugin.write_bytes(b"original installed bytes")
            expected = deploy.artifact_identity(plugin)
            plugin.write_bytes(b"replacement bytes to preserve")
            pt = root / "Plugins.txt"
            pt.write_text("*Other.esm\n*FO4Port.esm\n")
            manifest = data / deploy.MANIFEST
            deploy.write_manifest(str(manifest), {"files": [deploy.PLUGIN],
                "plugins_txt": str(pt), "plugins_added": ["*FO4Port.esm"], "complete": True,
                "artifacts": {deploy.PLUGIN: expected}})
            args = SimpleNamespace(starfield=str(root), dry_run=False)
            with self.assertRaisesRegex(SystemExit, "uninstall incomplete"):
                deploy.uninstall(args)
            self.assertEqual(plugin.read_bytes(), b"replacement bytes to preserve")
            self.assertEqual(pt.read_text().splitlines(), ["*Other.esm"])
            self.assertEqual(json.loads(manifest.read_text())["files"], [deploy.PLUGIN])
            plugin.write_bytes(b"original installed bytes")
            deploy.uninstall(args)
            self.assertFalse(plugin.exists() or manifest.exists())

    def test_uninstall_preserves_artifact_changed_after_interrupted_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "Data"
            data.mkdir()
            plugin = data / deploy.PLUGIN
            plugin.write_bytes(b"installed before interruption")
            expected = deploy.artifact_identity(plugin)
            plugin.write_bytes(b"user replacement after interruption")
            pt = root / "Plugins.txt"
            pt.write_text("*Other.esm\n*FO4Port.esm\n")
            manifest = data / deploy.MANIFEST
            deploy.write_manifest(str(manifest), {"files": [deploy.PLUGIN],
                "plugins_txt": str(pt), "plugins_added": ["*FO4Port.esm"], "complete": False,
                "artifacts": {deploy.PLUGIN: expected}})
            args = SimpleNamespace(starfield=str(root), dry_run=False)
            with self.assertRaisesRegex(SystemExit, "uninstall incomplete"):
                deploy.uninstall(args)
            self.assertEqual(plugin.read_bytes(), b"user replacement after interruption")
            self.assertEqual(pt.read_text().splitlines(), ["*Other.esm"])
            self.assertEqual(json.loads(manifest.read_text())["files"], [deploy.PLUGIN])
            plugin.write_bytes(b"installed before interruption")
            deploy.uninstall(args)
            self.assertFalse(plugin.exists() or manifest.exists())

    def test_bom_prefixed_active_plugin_is_not_duplicated_or_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            original = b"\xef\xbb\xbf*FO4Port.esm\r\n*Other.esm\r\n"
            pt.write_bytes(original)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            manifest = json.loads((game / "Data" / deploy.MANIFEST).read_text())
            self.assertEqual(manifest["plugins_added"], [])
            self.assertEqual(pt.read_bytes(), original)
            deploy.uninstall(args)
            self.assertEqual(pt.read_bytes(), original)

    def test_case_variant_plugin_line_is_not_duplicated_or_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            original = b"*fo4port.esm\r\n*Other.esm\r\n"
            pt.write_bytes(original)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            state = json.loads((game / "Data" / deploy.MANIFEST).read_text())
            self.assertEqual(state["plugins_added"], [])
            self.assertEqual(pt.read_bytes(), original)
            deploy.uninstall(args)
            self.assertEqual(pt.read_bytes(), original)

    def test_inactive_plugin_entry_is_activated_then_restored_on_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            pt.write_text("FO4Port.esm\n*Other.esm\n")
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            self.assertEqual(pt.read_text().splitlines(), ["*FO4Port.esm", "*Other.esm"])
            deploy.uninstall(args)
            self.assertEqual(pt.read_text().splitlines(), ["FO4Port.esm", "*Other.esm"])

    def test_uninstall_preserves_duplicate_plugin_entry_added_after_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            pt.write_text("*Other.esm\n")
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            with pt.open("a") as plugins:
                plugins.write("\n*fo4port.esm\n")
            deploy.uninstall(args)
            self.assertEqual(pt.read_text().splitlines(), ["*Other.esm", "", "*fo4port.esm"])

    def test_inactive_plugin_activation_preserves_bom_and_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            original = b"\xef\xbb\xbfFO4Port.esm\n*Other.esm\n"
            pt.write_bytes(original)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            self.assertEqual(pt.read_bytes(), b"\xef\xbb\xbf*FO4Port.esm\n*Other.esm\n")
            deploy.uninstall(args)
            self.assertEqual(pt.read_bytes(), original)

    def test_uninstall_preserves_preexisting_empty_plugins_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            pt.write_bytes(b"")
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            deploy.uninstall(args)
            self.assertTrue(pt.exists())
            self.assertEqual(pt.read_bytes(), b"")

    def test_uninstall_removes_case_only_edit_to_added_plugin_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            (game / "Data").mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            pt.write_text("*Other.esm\n")
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)
            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))
            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build):
                deploy.install(args)
            pt.write_text("*Other.esm\n*fo4port.esm\n")
            deploy.uninstall(args)
            self.assertEqual(pt.read_text().splitlines(), ["*Other.esm"])

    def check_archive_build(self, outcome):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool = root / "Tools" / "Archive2" / "Archive2.exe"
            tool.parent.mkdir(parents=True)
            tool.touch()
            out = root / deploy.ARCHIVE
            old = b"BTDX old build"
            fresh = b"BTDX new build" + bytes(16)
            out.write_bytes(old)
            args = SimpleNamespace(starfield=str(root), staging=str(root))

            def run(command, **kwargs):
                destination = Path(next(arg[len("-create="):] for arg in command if arg.startswith("-create=")))
                if outcome in ("success", "failure"):
                    destination.write_bytes(fresh)
                if outcome == "invalid":
                    destination.write_bytes(b"BAD!" + bytes(32))
                if outcome == "truncated":
                    destination.write_bytes(b"BTDX")
                return SimpleNamespace(returncode=1 if outcome == "failure" else 0, stdout="", stderr="")

            with patch.object(deploy.subprocess, "run", side_effect=run):
                if outcome == "success":
                    deploy.build_archive(args, str(out), ["meshes"], "General")
                else:
                    with self.assertRaises(SystemExit):
                        deploy.build_archive(args, str(out), ["meshes"], "General")
            self.assertEqual(out.read_bytes(), fresh if outcome == "success" else old)
            self.assertEqual(sorted(p.name for p in root.iterdir()), [deploy.ARCHIVE, "Tools"])

    def test_archive_success_without_new_output_rejects_stale_build(self):
        self.check_archive_build("missing")

    def test_archive_failure_preserves_previous_build(self):
        self.check_archive_build("failure")

    def test_archive_success_replaces_previous_build(self):
        self.check_archive_build("success")

    def test_invalid_fresh_archive_preserves_previous_build(self):
        self.check_archive_build("invalid")

    def test_truncated_fresh_archive_preserves_previous_build(self):
        self.check_archive_build("truncated")

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
            if failure in ("texture_build", "plugin_as_texture_archive"):
                (staging / "textures").mkdir()
            if failure == "archive_as_plugin":
                (staging / deploy.PLUGIN).write_bytes(b"BTDX" + bytes(32))
            pt = root / "Plugins.txt"
            original = b"# user comment\r\n*Other.esm\r\n"
            if existing_plugins:
                pt.write_bytes(original)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)

            def build(a, out, folders, fmt):
                if failure == "texture_build" and fmt == "DDS":
                    raise SystemExit("injected texture archive failure")
                head = b"BTDX"
                if failure == "invalid_archive":
                    head = b"BAD!"
                if failure == "plugin_as_main_archive" or (failure == "plugin_as_texture_archive" and fmt == "DDS"):
                    head = b"TES4"
                Path(out).write_bytes(head + bytes(32))

            original_copy = deploy.shutil.copyfile
            original_dump = deploy.json.dump
            original_remove = deploy.os.remove
            original_write_lines = deploy.write_lines

            def copy(src, dst):
                if failure == "corrupt_copy":
                    Path(dst).write_bytes(b"successful call, incorrect bytes")
                    return dst
                if failure == "copy":
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

            def write_lines(path, lines, original=None):
                original_write_lines(path, lines, original)
                if failure == "interrupt":
                    raise KeyboardInterrupt("injected interruption after activation")
                if failure == "cleanup":
                    raise OSError("injected failure after activation")

            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build), \
                    patch.object(deploy.shutil, "copyfile", side_effect=copy), \
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

    def test_archive_cannot_be_installed_as_plugin(self):
        self.run_failure("archive_as_plugin")

    def test_plugin_cannot_be_installed_as_main_archive(self):
        self.run_failure("plugin_as_main_archive")

    def test_plugin_cannot_be_installed_as_texture_archive(self):
        self.run_failure("plugin_as_texture_archive")

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
