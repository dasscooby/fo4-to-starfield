"""Tests for Ba2.summary and largest_entries used by the census CLI."""
import tempfile
import unittest
from pathlib import Path

from fo4sf.ba2 import Ba2
from tests.ba2_fixture import general_archive


class TestBa2Summary(unittest.TestCase):
    def test_summary_and_largest(self):
        data = general_archive({
            "a.txt": b"hello",
            "b.bin": b"x" * 100,
            "c.dds": b"y" * 50,
        })
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tiny.ba2"
            path.write_bytes(data)
            a = Ba2(str(path))
            s = a.summary()
            self.assertEqual(s.get("entries"), 3)
            self.assertEqual(s.get("general"), 3)
            self.assertEqual(s.get("textures"), 0)
            largest = a.largest_entries(2)
            self.assertEqual(len(largest), 2)
            self.assertEqual(largest[0]["name"], "b.bin")
            self.assertEqual(largest[0]["unpacked"], 100)
            self.assertGreater(largest[0]["unpacked"], largest[1]["unpacked"])


if __name__ == "__main__":
    unittest.main()
