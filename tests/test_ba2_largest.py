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


class SummaryTotalsTests(unittest.TestCase):
    def test_summary_includes_totals_and_extensions(self):
        entries = {
            "a.txt": b"x" * 100,
            "b.nif": b"y" * 200,
            "c.dds": b"z" * 50,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mix.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            s = a.summary()
            self.assertEqual(s["entries"], 3)
            self.assertEqual(s["general"], 3)
            self.assertEqual(s["textures"], 0)
            self.assertEqual(s["total_unpacked"], 350)
            self.assertGreater(s["total_packed"], 0)
            self.assertLess(s["total_packed"], s["total_unpacked"])
            self.assertEqual(s["by_extension"]["txt"], 1)
            self.assertEqual(s["by_extension"]["nif"], 1)
            self.assertEqual(s["by_extension"]["dds"], 1)

    def test_extension_uses_basename_not_dotted_directory(self):
        # Codex P3 on #374: extensionless files under dotted dirs must not
        # inherit the directory's suffix.
        entries = {
            "meshes/setdressing.lod/readme": b"no-ext",
            "meshes\\setdressing.lod\\notes": b"also-none",
            "meshes/door01.nif": b"nif-bytes",
            "foo.bar.dds": b"dds-bytes",
        }
        data = general_archive(entries)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "dotted.ba2")
            with open(path, "wb") as f:
                f.write(data)
            s = Ba2(path).summary()
            self.assertEqual(s["by_extension"].get(""), 2)
            self.assertEqual(s["by_extension"]["nif"], 1)
            self.assertEqual(s["by_extension"]["dds"], 1)
            self.assertNotIn("lod/readme", s["by_extension"])
            self.assertNotIn("lod\\notes", s["by_extension"])
            self.assertNotIn("lod", s["by_extension"])
            self.assertNotIn("bar.dds", s["by_extension"])


class SizeEstimateTests(unittest.TestCase):
    def test_total_and_estimates(self):
        entries = {
            "a.txt": b"a" * 50,
            "b.bin": b"b" * 150,
        }
        data = general_archive(entries, compressed=True)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sizes.ba2")
            with open(path, "wb") as f:
                f.write(data)
            a = Ba2(path)
            self.assertEqual(a.total_unpacked_estimate(), 200)
            est = a.size_estimates()
            self.assertEqual(est["unpacked_bytes"], 200)
            self.assertEqual(est["entries"], 2)
            self.assertEqual(est["total_unpacked"], 200)
            self.assertEqual(est["general_unpacked"], 200)
            self.assertEqual(est["texture_unpacked"], 0)
            self.assertEqual(est["entry_count"], 2)
            self.assertEqual(est["average_unpacked"], 100)
            self.assertGreater(est["packed_bytes"], 0)
            self.assertEqual(est["total_packed"], est["packed_bytes"])
            self.assertEqual(a.summary()["total_unpacked"], est["unpacked_bytes"])
            self.assertEqual(a.summary()["total_packed"], est["packed_bytes"])


if __name__ == "__main__":
    unittest.main()

