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
import zlib

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
import make_probe_swf  # noqa: E402
import pipboy_probe_install as pbi  # noqa: E402

PLUGIN = "FO4SFPipboyProbe.esm"
ARCHIVE = "FO4SFPipboyProbe - Main.ba2"
EXP_RECORD = b'{"exp_dir": "C:/stage/core", "files": {}, "complete": true}'
BEFORE = ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"]


def other_swf(movie):
    """A SWF that is not our movie byte for byte: the same movie, stored uncompressed (FWS) instead of CWS."""
    with open(movie, "rb") as f:
        raw = f.read()
    assert raw[:3] == b"CWS", raw[:3]
    return b"FWS" + raw[3:8] + zlib.decompress(raw[8:])


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

    def stage_extra(self, name="FO4SF_Fo4Boot", raw=None):
        # FAL-614 proof 1: the player's own movie copied in; here a movie of ours with other bytes stands in for it
        path = os.path.join(self.staged, "Data", "Interface", name + ".swf")
        movie = os.path.join(self.staged, "Data", *make_pipboy_probe.MOVIE.split("/"))
        write(path, raw if raw is not None else other_swf(movie))
        return path

    def test_the_extra_movie_is_packed_and_uninstalled(self):
        self.stage_extra()
        code, out = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Boot")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.data, ARCHIVE)))
        self.assertFalse(os.path.exists(os.path.join(self.data, "Interface")))  # packed, not loose
        code, out = self.run_main("uninstall")
        self.assertEqual(code, 0, out)
        for name in (PLUGIN, ARCHIVE, pbi.RECORD):
            self.assertFalse(os.path.exists(os.path.join(self.data, name)), name)
        self.assertEqual(self.lines(), BEFORE)
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_the_extra_movie_is_refused_unless_named(self):
        self.stage_extra()
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("the twin Interface/FO4SF_Fo4Boot.swf is not the movie byte for byte", str(code))
        self.assert_untouched()

    def test_a_second_unnamed_file_is_still_refused(self):
        self.stage_extra()
        write(os.path.join(self.staged, "Data", "Interface", "Other.swf"),
              other_swf(os.path.join(self.staged, "Data", *make_pipboy_probe.MOVIE.split("/"))))
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Boot")
        self.assertIn("the twin Interface/Other.swf is not the movie byte for byte", str(code))
        self.assert_untouched()

    def test_a_missing_extra_movie_is_refused(self):
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Boot")
        self.assertIn("the extra movie Interface/FO4SF_Fo4Boot.swf is not in the stage's Data", str(code))
        self.assert_untouched()

    def test_an_extra_movie_that_is_not_a_swf_is_refused(self):
        self.stage_extra(raw=b"not a movie")
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Boot")
        self.assertIn("does not read back as a SWF", str(code))
        self.assert_untouched()

    def test_an_extra_movie_with_tags_our_writer_never_makes_installs(self):
        # Scribe FAL-632: the player's movie holds tags of its own (D1: DefineEditText with other flags, DoABC);
        # only the container is checked. Code 82 (DoABC) and 37 with a layout byte, short and long lengths.
        body = (bytes([0x00]) + b"\x00\x1e\x01\x00"
                + make_probe_swf.tag(37, b"\x01\x00" + bytes(20) + b"\x20\x00")
                + make_probe_swf.tag(82, b"\x01\x00\x00\x00boot\x00" + bytes(80)) + make_probe_swf.tag(0))
        raw = b"CWS\x0f" + (8 + len(body)).to_bytes(4, "little") + zlib.compress(body)
        with self.assertRaises(make_probe_swf.SwfError):    # the writer's reader refuses it (the finding)
            make_probe_swf.read_movie(raw)
        self.assertIsNone(pbi.swf_problem(self.stage_extra(raw=raw)))
        code, out = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Boot")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.run_main("uninstall")[0], 0)
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_a_cut_or_padded_extra_movie_is_refused(self):
        body = bytes([0x00]) + b"\x00\x1e\x01\x00" + make_probe_swf.tag(82, bytes(80)) + make_probe_swf.tag(0)
        for cut, why in ((body[:-8], "runs past the body"), (body + b"\0\0", "after the End tag"),
                         (body[:-2], "no End tag")):
            raw = b"FWS\x0f" + (8 + len(cut)).to_bytes(4, "little") + cut
            self.assertIn(why, pbi.swf_problem(self.stage_extra(raw=raw)))
        raw = b"FWS\x0f" + (9 + len(body)).to_bytes(4, "little") + body
        self.assertIn("FileLength", pbi.swf_problem(self.stage_extra(raw=raw)))

    def test_extra_movie_names(self):
        for bad in ("", "Fo4Boot", "pipboybootsequence", "FO4SF_", "FO4SF_a.b", "FO4SF_../x", "FO4SF_é",
                    "FO4SF_" + "x" * 59, "FO4SF_PipboyMenu", "fo4sf_pipboymenu", "FO4SF_PIPBOYMENU"):
            if bad:
                self.assertIsNotNone(pbi.extra_movie_problem(bad), bad)
        for good in ("FO4SF_Fo4Boot", "FO4SF_a", "FO4SF_" + "x" * 58):
            self.assertIsNone(pbi.extra_movie_problem(good), good)
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "pipboybootsequence")
        self.assertIn("FO4SF_ then letters", str(code))
        self.assert_untouched()

    def test_extra_movie_belongs_to_install(self):
        code, _ = self.run_main("status", "--extra-movie", "FO4SF_Fo4Boot")
        self.assertIn("--extra-movie and --page-movie belong to install", str(code))
        code, _ = self.run_main("uninstall", "--page-movie", "Pipboy_StatsPage")
        self.assertIn("--extra-movie and --page-movie belong to install", str(code))

    def stage_shell(self, pages=pbi.PAGE_MOVIES):
        # FAL-614 S1: the shell as the extra movie and its pages under Fallout 4's own names; ours stand in for them
        self.stage_extra("FO4SF_Fo4Shell")
        return [self.stage_extra(page) for page in pages]

    def page_args(self, pages=pbi.PAGE_MOVIES):
        return [arg for page in pages for arg in ("--page-movie", page)]

    def test_the_shell_and_its_pages_are_packed_and_uninstalled(self):
        self.stage_shell()
        code, out = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell", *self.page_args())
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.data, ARCHIVE)))
        self.assertFalse(os.path.exists(os.path.join(self.data, "Interface")))  # packed, not loose
        code, out = self.run_main("uninstall")
        self.assertEqual(code, 0, out)
        for name in (PLUGIN, ARCHIVE, pbi.RECORD):
            self.assertFalse(os.path.exists(os.path.join(self.data, name)), name)
        self.assertEqual(self.lines(), BEFORE)
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_the_page_names_are_fallout_4s(self):
        self.assertEqual(pbi.PAGE_MOVIES, ("Pipboy_StatsPage", "Pipboy_InvPage", "Pipboy_DataPage", "Pipboy_MapPage",
                                           "Pipboy_RadioPage"))
        self.assertTrue(all(not p.startswith(pbi.EXTRA_PREFIX) for p in pbi.PAGE_MOVIES))

    def test_one_page_alone_installs(self):
        self.stage_shell(["Pipboy_StatsPage"])
        code, out = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell",
                                  *self.page_args(["Pipboy_StatsPage"]))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.run_main("uninstall")[0], 0)

    def test_a_page_is_refused_unless_named(self):
        self.stage_shell()
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell",
                                *self.page_args(pbi.PAGE_MOVIES[:-1]))
        self.assertIn("the twin Interface/Pipboy_RadioPage.swf is not the movie byte for byte", str(code))
        self.assert_untouched()

    def test_a_page_needs_the_shell(self):
        self.stage_shell(["Pipboy_StatsPage"])
        code, _ = self.run_main("install", "--dir", self.staged, *self.page_args(["Pipboy_StatsPage"]))
        self.assertIn("--page-movie needs --extra-movie", str(code))
        self.assert_untouched()

    def test_page_names_outside_the_five_are_refused(self):
        self.stage_extra("FO4SF_Fo4Shell")
        for bad in ("PipboyMenu", "PipboyMessageBox", "pipboy_statspage", "Pipboy_StatsPage.swf", "../Pipboy_StatsPage",
                    "FO4SF_PipboyMenu", "terminalmenu"):
            code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell", "--page-movie", bad)
            self.assertIn(f"--page-movie {bad!r}: one of", str(code), bad)
        self.assert_untouched()

    def test_a_page_named_twice_is_refused(self):
        self.stage_shell(["Pipboy_StatsPage"])
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell",
                                *self.page_args(["Pipboy_StatsPage", "Pipboy_StatsPage"]))
        self.assertIn("each page once", str(code))
        self.assert_untouched()

    def test_a_missing_page_is_refused(self):
        self.stage_shell(["Pipboy_StatsPage"])
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell",
                                *self.page_args(["Pipboy_StatsPage", "Pipboy_MapPage"]))
        self.assertIn("the page movie Interface/Pipboy_MapPage.swf is not in the stage's Data", str(code))
        self.assert_untouched()

    def test_a_page_that_is_not_a_swf_is_refused(self):
        self.stage_shell(["Pipboy_StatsPage"])
        self.stage_extra("Pipboy_StatsPage", raw=b"not a movie")
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell",
                                *self.page_args(["Pipboy_StatsPage"]))
        self.assertIn("the page movie Interface/Pipboy_StatsPage.swf does not read back as a SWF", str(code))
        self.assert_untouched()

    def test_a_page_outside_interface_is_refused(self):
        self.stage_extra("FO4SF_Fo4Shell")
        movie = os.path.join(self.staged, "Data", *make_pipboy_probe.MOVIE.split("/"))
        write(os.path.join(self.staged, "Data", "Interface", "Pages", "Pipboy_StatsPage.swf"), other_swf(movie))
        code, _ = self.run_main("install", "--dir", self.staged, "--extra-movie", "FO4SF_Fo4Shell",
                                *self.page_args(["Pipboy_StatsPage"]))
        self.assertIn("the page movie Interface/Pipboy_StatsPage.swf is not in the stage's Data", str(code))
        self.assert_untouched()


if __name__ == "__main__":
    unittest.main()
