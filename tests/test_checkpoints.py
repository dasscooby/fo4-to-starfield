"""Resume behavior uses synthetic NIFs and generated file graphs only."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import checkpoints, nif, sfnif
spec = importlib.util.spec_from_file_location("resume_batch", ROOT / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def generated(staging, stem="chair"):
    files = {
        "geometries/test/mesh.mesh": b"synthetic geometry",
        "materials/fo4port/test.mat": json.dumps({"Objects": [], "texture": "Data\\Textures\\fo4port\\color.dds"}).encode(),
        "textures/fo4port/color.dds": b"synthetic texture",
    }
    shape = sfnif.StaticShape(b"Synthetic", b"test\\mesh", 3, 3, "materials\\fo4port\\test.mat", (0, 0, 0, 1), (0, 0, 0, 1, 1, 1))
    files[f"meshes/fo4port/{stem}.nif"] = nif.serialize(sfnif.build_static_nif(b"Synthetic", [shape]))
    for name, data in files.items():
        path = Path(staging) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {"ok": True, "out_name": "fo4port/" + stem, "fallback_materials": 0, "shapes": 1}, files


class CheckpointTests(unittest.TestCase):
    def test_each_missing_or_changed_dependency_invalidates_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, files = generated(tmp)
            cache = checkpoints.Checkpoints(tmp, {"inputs": "same"})
            self.assertTrue(cache.save("meshes/chair.nif", result))
            self.assertEqual(cache.load("Meshes\\Chair.NIF"), result)
            for name, original in files.items():
                path = Path(tmp) / name
                stat = path.stat()
                path.write_bytes(b"X" * len(original))
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                self.assertIsNone(cache.load("meshes/chair.nif"), name)
                path.write_bytes(original)
                path.unlink()
                self.assertIsNone(cache.load("meshes/chair.nif"), name)
                path.write_bytes(original)

    def test_changed_inputs_or_degraded_result_cannot_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = generated(tmp)
            cache = checkpoints.Checkpoints(tmp, {"input": 1})
            cache.save("chair.nif", result)
            self.assertIsNone(checkpoints.Checkpoints(tmp, {"input": 2}).load("chair.nif"))
            self.assertFalse(cache.save("bad.nif", {**result, "fallback_materials": 1}))
            self.assertIsNone(cache.load("bad.nif"))

    def test_corrupt_checkpoint_and_escape_are_cache_misses(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, _ = generated(tmp)
            cache = checkpoints.Checkpoints(tmp, {})
            cache.save("chair.nif", result)
            cache.path("chair.nif").write_text("{")
            self.assertIsNone(cache.load("chair.nif"))
            with self.assertRaises(ValueError):
                checkpoints.local_path(tmp, "../outside.dds")

    def test_interrupted_batch_reuses_first_model_and_preserves_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            collision = root / "template.nif"
            collision.write_bytes(b"synthetic")
            names = ["meshes/a.nif", "meshes/b.nif"]
            source = SimpleNamespace(mesh_names=lambda pattern: names)
            calls = []
            interrupted = True

            def convert(name):
                calls.append(name)
                if interrupted and name == names[1]:
                    raise KeyboardInterrupt("simulated interrupted build")
                result, _ = generated(staging, Path(name).stem)
                return result

            converter = SimpleNamespace(convert_nif=convert, stats={}, material_errors={})
            argv = ["convert_batch.py", "--fo4-data", str(root), "--staging", str(staging),
                    "--content-resources", str(collision), "--texconv", str(collision),
                    "--collision-template", str(collision), "--resume"]
            with patch.object(sys, "argv", argv), \
                    patch.object(batch.pipeline, "Fo4Archives", return_value=source), \
                    patch.object(batch.pipeline, "Converter", return_value=converter), \
                    patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                    patch("builtins.print"):
                with self.assertRaises(KeyboardInterrupt):
                    batch.main()
                ids = json.loads((staging / "editorids.json").read_text())
                interrupted = False
                calls.clear()
                batch.main()
                self.assertEqual(calls, [names[1]])
                manifest = json.loads((staging / "manifest.json").read_text())
                self.assertEqual(manifest["stats"]["reused"], 1)
                self.assertEqual(manifest["items"][0]["editor_id"], ids[names[0]])
                calls.clear()
                with patch.object(batch.pipeline, "Converter", side_effect=AssertionError("unneeded converter initialized")):
                    batch.main()
                self.assertEqual(calls, [])
