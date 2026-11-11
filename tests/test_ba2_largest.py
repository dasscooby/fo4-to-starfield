"""Synthetic tests for Ba2.largest_entries."""
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


if __name__ == "__main__":
    unittest.main()

class SummaryTotalsTests(unittest.TestCase):
    def test_summary_includes_totals_and_extensions(self):
        entries = {
            "a.txt": b"x" * 100,
            "b.nif": b"y" * 200,
            "c.dds": b"z" * 50,  # will be treated as general in fixture
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mix.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            s = a.summary()
            self.assertEqual(s["entries"], 3)
            self.assertEqual(s["total_unpacked"], 350)
            self.assertGreater(s["total_packed"], 0)
            self.assertIn("txt", s["by_extension"])
            self.assertEqual(s["by_extension"]["txt"], 1)
            self.assertEqual(s["by_extension"]["nif"], 1)
