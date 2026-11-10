"""scripts/ui/make_pipboy_probe.py (FAL-187): the empty FO4SFPipboyProbe.esm and its check, and the staged folder.
Everything goes to a temporary folder."""
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_pipboy_probe as mpp  # noqa: E402
import make_probe_swf  # noqa: E402
from fo4sf.planet.esm import EsmError, PluginWriter  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "ui", "make_pipboy_probe.py")


class PluginTest(unittest.TestCase):
    def test_header_from_the_bytes(self):
        data = mpp.plugin_bytes()
        sig, size, flags = struct.unpack_from("<4sII", data, 0)
        self.assertEqual(sig, b"TES4")
        self.assertEqual(len(data), 24 + size)                   # the header and nothing after it
        self.assertTrue(flags & 1)
        self.assertIn(b"MAST\x0e\x00Starfield.esm\x00", data)
        self.assertEqual(data.count(b"MAST"), 1)
        self.assertNotIn(b"GRUP", data)

    def test_deterministic(self):
        self.assertEqual(mpp.plugin_bytes(), mpp.plugin_bytes())

    def test_stage_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            esm, movie = mpp.stage(tmp)
            self.assertEqual(os.path.basename(esm), "FO4SFPipboyProbe.esm")
            self.assertEqual(os.path.relpath(movie, tmp).replace(os.sep, "/"), mpp.MOVIE)
            self.assertEqual(mpp.check(esm)["masters"], ["Starfield.esm"])
            with open(movie, "rb") as f:
                self.assertEqual(f.read(), make_probe_swf.movie_bytes())

    def test_stage_without_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, movie = mpp.stage(tmp, label=False)
            names = [t["name"] for t in make_probe_swf.read_movie(movie)["tags"]]
            self.assertEqual(names.count("DefineShape3"), 1)

    def write(self, tmp, writer):
        path = os.path.join(tmp, "x.esm")
        with open(path, "wb") as f:
            f.write(writer.to_bytes())
        return path

    def test_check_refuses_other_masters(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(EsmError, "masters"):
                mpp.check(self.write(tmp, PluginWriter(["Starfield.esm", "Other.esm"])))

    def test_check_refuses_no_esm_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(EsmError, "ESM flag"):
                mpp.check(self.write(tmp, PluginWriter(["Starfield.esm"], flags=0)))

    def test_check_refuses_records(self):
        from fo4sf.planet.esm import Record
        w = PluginWriter(["Starfield.esm"])
        w.add(Record(b"GLOB", w.own(0x800), [(b"EDID", b"X\0"), (b"FLTV", struct.pack("<f", 0))], 0, 0, 576, 0))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(EsmError, "groups"):
                mpp.check(self.write(tmp, w))

    def test_check_refuses_not_a_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.esm")
            with open(path, "wb") as f:
                f.write(b"NOPE" + bytes(40))
            with self.assertRaises(EsmError):
                mpp.check(path)


class CliTest(unittest.TestCase):
    def test_stage_then_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, SCRIPT, "stage", tmp], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("FO4SFPipboyProbe - Main.ba2", r.stdout)
            r = subprocess.run([sys.executable, SCRIPT, "check", os.path.join(tmp, "FO4SFPipboyProbe.esm")],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("ok: "))

    def test_check_missing_file_is_one_line_exit_1(self):
        r = subprocess.run([sys.executable, SCRIPT, "check", os.path.join(ROOT, "no-such.esm")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(r.stderr.startswith("make_pipboy_probe: "))


if __name__ == "__main__":
    unittest.main()
