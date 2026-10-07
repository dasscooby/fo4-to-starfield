"""Deployment failure injection: synthetic files, no game installation required."""
import importlib.util
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
    def run_failure(self, failure, existing_plugins=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging, game = root / "staging", root / "game"
            staging.mkdir()
            data = game / "Data"
            data.mkdir(parents=True)
            (staging / deploy.PLUGIN).write_bytes(b"TES4" + bytes(32))
            (staging / "meshes").mkdir()
            pt = root / "Plugins.txt"
            original = b"# user comment\r\n*Other.esm\r\n"
            if existing_plugins:
                pt.write_bytes(original)
            args = SimpleNamespace(staging=str(staging), starfield=str(game), dry_run=False)

            def build(a, out, folders, fmt):
                Path(out).write_bytes(b"BTDX" + bytes(32))

            original_copy = deploy.shutil.copy2
            original_dump = deploy.json.dump

            def copy(src, dst):
                if failure == "copy":
                    Path(dst).write_bytes(b"partial")
                    raise OSError("injected partial copy")
                return original_copy(src, dst)

            def dump(state, stream, **kwargs):
                if failure == "manifest" and state["complete"]:
                    raise OSError("injected final manifest failure")
                return original_dump(state, stream, **kwargs)

            with patch.object(deploy, "plugins_txt_path", return_value=str(pt)), \
                    patch.object(deploy, "build_archive", side_effect=build), \
                    patch.object(deploy.shutil, "copy2", side_effect=copy), \
                    patch.object(deploy.json, "dump", side_effect=dump):
                with self.assertRaises(SystemExit):
                    deploy.install(args)
            self.assertEqual(list(data.iterdir()), [])
            if existing_plugins:
                self.assertEqual(pt.read_bytes(), original)
            else:
                self.assertFalse(pt.exists())

    def test_partial_copy_is_removed(self):
        self.run_failure("copy")

    def test_final_manifest_failure_restores_plugins_exactly(self):
        self.run_failure("manifest")

    def test_rollback_removes_new_plugins_file(self):
        self.run_failure("manifest", existing_plugins=False)
