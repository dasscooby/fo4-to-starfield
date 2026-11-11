"""Synthetic tests for Ba2.largest_entries and by_extension."""
import os
import tempfile
import unittest

from tests.ba2_fixture import general_archive
from fo4sf.ba2 import Ba2


class LargestEntriesTests(unittest.TestCase):
    def test_orders_by_unpacked_size(self):
        entries = {
            "small.txt": b"a" * 10,
            "medium.bin": b"b" * 100,
            "large.dat": b"c" * 1000,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            top = a.largest_entries(2)
            self.assertEqual(len(top), 2)
            self.assertEqual(top[0]["name"], "large.dat")
            self.assertEqual(top[0]["unpacked"], 1000)
            self.assertGreater(top[0]["packed"], 0)  # compressed
            self.assertEqual(top[1]["name"], "medium.bin")
            self.assertEqual(top[1]["unpacked"], 100)

    def test_empty_and_n_limit(self):
        data = general_archive({"only.txt": b"x"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "one.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            self.assertEqual(len(a.largest_entries(5)), 1)
            self.assertEqual(a.largest_entries(0), [])

    def test_by_extension_counts(self):
        entries = {
            "meshes/chair.nif": b"nifdata",
            "meshes/table.NIF": b"more",
            "textures/stone.dds": b"ddsdata",
            "materials/iron.bgsm": b"mat",
            "readme.txt": b"text",
            "noext": b"raw",
        }
        data = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mix.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            counts = a.by_extension()
            self.assertEqual(counts.get("nif"), 2)
            self.assertEqual(counts.get("dds"), 1)
            self.assertEqual(counts.get("bgsm"), 1)
            self.assertEqual(counts.get("txt"), 1)
            self.assertEqual(counts.get(""), 1)
            self.assertEqual(sum(counts.values()), 6)


if __name__ == "__main__":
    unittest.main()
