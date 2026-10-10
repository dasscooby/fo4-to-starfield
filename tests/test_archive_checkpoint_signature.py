"""The batch resume signature changes when source archive bytes change."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("convert_batch_signature", ROOT / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class ArchiveCheckpointSignatureTests(unittest.TestCase):
    def test_same_metadata_different_archive_bytes_invalidate_resume_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "fo4-data"
            data.mkdir()
            archive = data / "Fallout4 - Synthetic.ba2"
            archive.write_bytes(b"first archive payload")
            for name in ("texconv.exe", "resources.zip", "collision.nif"):
                (root / name).write_bytes(b"synthetic dependency")
            args = SimpleNamespace(fo4_data=str(data), starfield_data=None,
                                   texconv=str(root / "texconv.exe"),
                                   content_resources=str(root / "resources.zip"),
                                   collision_template=str(root / "collision.nif"))

            before = batch.checkpoint_signature(args)
            original_stat = archive.stat()
            archive.write_bytes(b"other archive payload")
            os.utime(archive, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            after = batch.checkpoint_signature(args)

            self.assertEqual(archive.stat().st_size, original_stat.st_size)
            self.assertEqual(archive.stat().st_mtime_ns, original_stat.st_mtime_ns)
            self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
