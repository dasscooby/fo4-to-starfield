"""Archive checkpoint identities detect content edits, not just metadata."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import checkpoints


class ArchiveIdentityTests(unittest.TestCase):
    def test_same_size_edit_with_restored_timestamp_changes_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "synthetic.ba2"
            archive.write_bytes(b"first archive payload")
            original_stat = archive.stat()
            original_identity = checkpoints.archive_identity(archive)

            archive.write_bytes(b"other archive payload")
            os.utime(archive, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            changed_stat = archive.stat()

            self.assertEqual(changed_stat.st_size, original_stat.st_size)
            self.assertEqual(changed_stat.st_mtime_ns, original_stat.st_mtime_ns)
            self.assertNotEqual(original_identity, checkpoints.archive_identity(archive))

    def test_stable_archive_identity_contains_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "synthetic.ba2"
            archive.write_bytes(b"synthetic immutable archive")

            identity = checkpoints.archive_identity(archive)

            self.assertEqual(identity[0], str(archive.resolve()))
            self.assertEqual(identity[1], archive.stat().st_size)
            self.assertEqual(identity[2], checkpoints.digest(archive))
            self.assertEqual(identity, checkpoints.archive_identity(archive))

    def test_archive_modified_during_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "synthetic.ba2"
            archive.write_bytes(b"before")
            hash_open_file = checkpoints._hash_open_file

            def mutate_after_read(stream):
                result = hash_open_file(stream)
                archive.write_bytes(b"after!")
                return result

            with patch.object(checkpoints, "_hash_open_file", side_effect=mutate_after_read):
                with self.assertRaisesRegex(OSError, "changed while fingerprinting"):
                    checkpoints.archive_identity(archive)


if __name__ == "__main__":
    unittest.main()
