"""scripts/ui/pipboy_probe_install.py: the Pip-Boy probe's own install record next to an installed experiment, on a
stage written by make_pipboy_probe.py (a temp game folder, a temp LOCALAPPDATA, the archive builder replaced by a
stub; no game, no Archive2). The installed experiment's record must stay byte for byte."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts" / "ui"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))
from ba2_fixture import archive_from_tree  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
import exp_install  # noqa: E402
import make_pipboy_probe  # noqa: E402
import pipboy_probe_install as pbi  # noqa: E402

PLUGIN = "FO4SFPipboyProbe.esm"
ARCHIVE = "FO4SFPipboyProbe - Main.ba2"
EXP_RECORD = b'{"exp_dir": "C:/stage/core", "files": {}, "complete": true}'
BEFORE = ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"]


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


class PipboyProbeInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        write(os.path.join(self.data, exp_install.RECORD), EXP_RECORD)
        self.staged = os.path.join(root, "pipboy_probe")
        make_pipboy_probe.stage(self.staged)
        self.local = os.path.join(root, "local")
        self.plugins = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.plugins, ("\r\n".join(BEFORE) + "\r\n").encode())
        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.local
        self.saved = exp_install.build_ba2

        def stub_build(a, root_dir, out):
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build

    def tearDown(self):
        exp_install.build_ba2 = self.saved
        if self.old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_local
        self.tmp.cleanup()

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = pbi.main(list(argv) + ["--starfield", self.game]) or 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def lines(self):
        with open(self.plugins, encoding="utf-8-sig") as f:
            return f.read().splitlines()

    def exp_record(self):
        with open(os.path.join(self.data, exp_install.RECORD), "rb") as f:
            return f.read()

    def assert_untouched(self):
        self.assertFalse(os.path.exists(os.path.join(self.data, pbi.RECORD)))
        self.assertFalse(os.path.exists(os.path.join(self.data, PLUGIN)))
        self.assertEqual(self.lines(), BEFORE)
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_prepacked_path_never_calls_archive_builder(self):
        archive = os.path.join(self.staged, "FO4SFPipboyProbe - Main.ba2")
        write(archive, archive_from_tree(Path(self.staged) / "Data"))
        with patch.object(exp_install, "build_ba2", side_effect=AssertionError("must not build")):
            code, output = self.run_main("install", "--dir", self.staged, "--prepacked", archive)
        self.assertEqual(code, 0, output)
        self.assertTrue(Path(self.data, pbi.RECORD).exists())

    def test_wrong_prepacked_archive_refuses_without_game_changes(self):
        archive = os.path.join(self.staged, "FO4SFPipboyProbe - Main.ba2")
        write(archive, archive_from_tree(Path(self.staged) / "Data"))
        raw = bytearray(Path(archive).read_bytes())
        raw[0:4] = b"FAIL"
        Path(archive).write_bytes(raw)
        before = Path(self.plugins).read_bytes()
        with patch.object(exp_install, "build_ba2", side_effect=AssertionError("must not build")):
            code, output = self.run_main("install", "--dir", self.staged, "--prepacked", archive)
        self.assertNotEqual(code, 0, output)
        self.assertFalse(Path(self.data, pbi.RECORD).exists())
        self.assertEqual(Path(self.plugins).read_bytes(), before)

    def test_the_names_match_the_stager(self):
        self.assertEqual(make_pipboy_probe.PLUGIN, PLUGIN)
        self.assertEqual(make_pipboy_probe.ARCHIVE, ARCHIVE)
        self.assertNotEqual(pbi.RECORD, exp_install.RECORD)

    def test_install_rides_along_and_uninstall_restores(self):
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertEqual(code, 0, out)
        self.assertEqual(exp_install.RECORD, "FO4SFExp.install.json")         # restored after the call
        for name in (PLUGIN, ARCHIVE):
            self.assertTrue(os.path.isfile(os.path.join(self.data, name)), name)
        self.assertFalse(os.path.exists(os.path.join(self.data, "Interface")))  # packed, not loose
        self.assertEqual(self.lines(), BEFORE + ["*" + PLUGIN])
        with open(os.path.join(self.data, pbi.RECORD), encoding="utf-8") as f:
            rec = json.load(f)
        self.assertTrue(rec["complete"])
        self.assertEqual(rec["plugins"], [PLUGIN])
        self.assertEqual(self.exp_record(), EXP_RECORD)

        code, out = self.run_main("status")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["plugins"], [PLUGIN])
        self.assertEqual(self.run_main("active")[0], 0)
        self.assertEqual(self.run_main("order")[0], 0)
        self.assertEqual(self.run_main("install", "--dir", self.staged)[1].strip().splitlines()[-1], "already installed")

        code, out = self.run_main("uninstall")
        self.assertEqual(code, 0, out)
        for name in (PLUGIN, ARCHIVE, pbi.RECORD):
            self.assertFalse(os.path.exists(os.path.join(self.data, name)), name)
        self.assertEqual(self.lines(), BEFORE)
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_the_stage_without_label_installs(self):
        make_pipboy_probe.stage(self.staged, label=False)
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertEqual(code, 0, out)

    def test_an_extra_plugin_is_refused(self):
        write(os.path.join(self.staged, "Other.esm"), b"TES4")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("expected ['FO4SFPipboyProbe.esm']", str(code))
        self.assert_untouched()

    def test_a_plugin_with_records_or_another_master_is_refused(self):
        bad = esm.PluginWriter(["Starfield.esm", "FO4SFPlanet.esm"], esm.ESM).to_bytes()
        write(os.path.join(self.staged, PLUGIN), bad)
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("masters", str(code))
        self.assert_untouched()

    def test_an_extra_data_file_is_refused(self):
        write(os.path.join(self.staged, "Data", "Interface", "Other.swf"), b"FWS")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("the twin Interface/Other.swf is not the movie byte for byte", str(code))  # FAL-250: twins only
        self.assert_untouched()

    def test_a_broken_movie_is_refused(self):
        write(os.path.join(self.staged, "Data", *make_pipboy_probe.MOVIE.split("/")), b"not a movie")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("the movie does not read back", str(code))
        self.assert_untouched()

    def test_an_existing_file_is_never_overwritten(self):
        write(os.path.join(self.data, PLUGIN), b"someone else's")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("refusing to overwrite", str(code))
        with open(os.path.join(self.data, PLUGIN), "rb") as f:
            self.assertEqual(f.read(), b"someone else's")
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_install_needs_a_dir(self):
        code, _ = self.run_main("install")
        self.assertIn("install needs --dir", str(code))

    def test_a_twin_is_packed_with_the_movie(self):
        # FAL-250: make_pipboy_probe.py twin, our movie again at a vanilla movie's path, rides in the probe archive
        make_pipboy_probe.twin(self.staged, "Interface/testmenus_dynamictexturedgeo.swf")
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.data, ARCHIVE)))
        self.assertFalse(os.path.exists(os.path.join(self.data, "Interface")))  # packed, not loose
        self.assertEqual(self.run_main("uninstall")[0], 0)
        self.assertFalse(os.path.exists(os.path.join(self.data, ARCHIVE)))
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_a_twin_that_is_not_the_movie_is_refused(self):
        twin = make_pipboy_probe.twin(self.staged, "Interface/terminalmenu.swf")
        write(twin, open(twin, "rb").read() + b"\0")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("is not the movie byte for byte", str(code))
        self.assert_untouched()

    def test_a_copy_outside_interface_is_refused(self):
        movie = os.path.join(self.staged, "Data", *make_pipboy_probe.MOVIE.split("/"))
        write(os.path.join(self.staged, "Data", "Textures", "x.swf"), open(movie, "rb").read())
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("Data holds", str(code))
        self.assert_untouched()


if __name__ == "__main__":
    unittest.main()
