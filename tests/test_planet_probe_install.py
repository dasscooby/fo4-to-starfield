"""scripts/planet/planet_probe_install.py: the planet probe's own install record next to an installed experiment,
on a synthetic stage (a temp game folder, a temp LOCALAPPDATA, the archive builder replaced by a stub; no game, no
Archive2). The installed experiment's record must stay byte for byte."""
import contextlib
import hashlib
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
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))
from ba2_fixture import archive_from_tree  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
import exp_install  # noqa: E402
import make_planet_probe  # noqa: E402
import planet_probe_install as ppi  # noqa: E402

PLUGINS = ["FO4SFPlanet.esm", "FO4SFPlanetProbe.esm", "FO4SFPlanetProbe_Reg.esm", "FO4SFMergeProbe.esm"]
MASTERS = {"FO4SFPlanet.esm": ["Starfield.esm"], "FO4SFPlanetProbe.esm": ["Starfield.esm", "FO4SFPlanet.esm"],
           "FO4SFPlanetProbe_Reg.esm": ["Starfield.esm", "FO4SFPlanet.esm", "FO4SFPlanetProbe.esm"],
           "FO4SFMergeProbe.esm": ["Starfield.esm"]}
EXP_RECORD = b'{"exp_dir": "C:/stage/core", "files": {}, "complete": true}'


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stage(d):
    files = {name: esm.PluginWriter(MASTERS[name], esm.ESM, author=name).to_bytes() for name in PLUGINS}
    files["Data/Terrain/FO4SF_PlanetProbeWorld.btd"] = b"BTDB-test"
    files["Data/Scripts/FO4SF_PlanetProbeQuest.pex"] = b"pex"
    for rel, data in files.items():
        write(os.path.join(d, *rel.split("/")), data)
    plan = {"kind": "planet-probe", "version": 1, "plugins": PLUGINS, "outputs": {k: sha(v) for k, v in files.items()},
            "inputs": {"Starfield.esm": {"sha256": "0" * 64}}}
    with open(os.path.join(d, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f)
    return d


class PlanetProbeInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        write(os.path.join(self.data, exp_install.RECORD), EXP_RECORD)
        self.staged = stage(os.path.join(root, "planet_probe_20261029"))
        self.local = os.path.join(root, "local")
        self.plugins = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.plugins, b"# header\r\n*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n")
        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.local
        self.saved = (exp_install.build_ba2, make_planet_probe.verify_stage)

        def stub_build(a, root_dir, out):
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build
        make_planet_probe.verify_stage = lambda d, plan, data=None: []

    def tearDown(self):
        exp_install.build_ba2, make_planet_probe.verify_stage = self.saved
        if self.old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_local
        self.tmp.cleanup()

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = ppi.main(list(argv) + ["--starfield", self.game]) or 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def lines(self):
        with open(self.plugins, encoding="utf-8-sig") as f:
            return f.read().splitlines()

    def exp_record(self):
        with open(os.path.join(self.data, exp_install.RECORD), "rb") as f:
            return f.read()

    def test_prepacked_path_never_calls_archive_builder(self):
        archive = os.path.join(self.staged, "FO4SFPlanet - Main.ba2")
        write(archive, archive_from_tree(Path(self.staged) / "Data"))
        with patch.object(exp_install, "build_ba2", side_effect=AssertionError("must not build")):
            code, output = self.run_main("install", "--dir", self.staged, "--prepacked", archive)
        self.assertEqual(code, 0, output)
        self.assertTrue(Path(self.data, ppi.RECORD).exists())

    def test_wrong_prepacked_archive_refuses_without_game_changes(self):
        archive = os.path.join(self.staged, "FO4SFPlanet - Main.ba2")
        write(archive, archive_from_tree(Path(self.staged) / "Data"))
        raw = bytearray(Path(archive).read_bytes())
        raw[0:4] = b"FAIL"
        Path(archive).write_bytes(raw)
        before = Path(self.plugins).read_bytes()
        with patch.object(exp_install, "build_ba2", side_effect=AssertionError("must not build")):
            code, output = self.run_main("install", "--dir", self.staged, "--prepacked", archive)
        self.assertNotEqual(code, 0, output)
        self.assertFalse(Path(self.data, ppi.RECORD).exists())
        self.assertEqual(Path(self.plugins).read_bytes(), before)

    def test_install_rides_along_and_uninstall_restores(self):
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertEqual(code, 0, out)
        self.assertEqual(exp_install.RECORD, "FO4SFExp.install.json")         # restored after the call
        for name in PLUGINS + ["FO4SFPlanet - Main.ba2"]:
            self.assertTrue(os.path.isfile(os.path.join(self.data, name)), name)
        self.assertFalse(os.path.exists(os.path.join(self.data, "Terrain")))  # packed, not loose
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"] + ["*" + p for p in PLUGINS])
        with open(os.path.join(self.data, ppi.RECORD), encoding="utf-8") as f:
            rec = json.load(f)
        self.assertTrue(rec["complete"])
        self.assertEqual(rec["plugins"], PLUGINS)
        self.assertEqual(self.exp_record(), EXP_RECORD)

        code, out = self.run_main("status")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["plugins"], PLUGINS)
        self.assertEqual(self.run_main("active")[0], 0)
        self.assertEqual(self.run_main("order")[0], 0)
        self.assertEqual(self.run_main("install", "--dir", self.staged)[1].strip().splitlines()[-1], "already installed")

        code, out = self.run_main("uninstall")
        self.assertEqual(code, 0, out)
        for name in PLUGINS + ["FO4SFPlanet - Main.ba2", ppi.RECORD]:
            self.assertFalse(os.path.exists(os.path.join(self.data, name)), name)
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"])
        self.assertEqual(self.exp_record(), EXP_RECORD)

    def test_a_changed_stage_is_refused(self):
        make_planet_probe.verify_stage = self.saved[1]                      # the real check: hashes first
        with open(os.path.join(self.staged, "FO4SFPlanetProbe.esm"), "ab") as f:
            f.write(b"!")
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertIn("does not match its plan.json", str(code))
        self.assertFalse(os.path.exists(os.path.join(self.data, ppi.RECORD)))
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"])

    def test_install_checks_the_stage_against_the_games_data(self):
        seen = []
        make_planet_probe.verify_stage = lambda d, plan, data=None: seen.append(data) or ["planet id 8 is in use"]
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertEqual(seen, [self.data])
        self.assertIn("does not match its plan.json or Data (re-stage): planet id 8 is in use", str(code))
        self.assertFalse(os.path.exists(os.path.join(self.data, ppi.RECORD)))

    def test_an_extra_plugin_is_refused(self):
        write(os.path.join(self.staged, "Other.esm"), b"TES4")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("plan.json lists", str(code))

    def test_an_existing_file_is_never_overwritten(self):
        write(os.path.join(self.data, "FO4SFPlanet.esm"), b"someone else's")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("refusing to overwrite", str(code))
        with open(os.path.join(self.data, "FO4SFPlanet.esm"), "rb") as f:
            self.assertEqual(f.read(), b"someone else's")


if __name__ == "__main__":
    unittest.main()
