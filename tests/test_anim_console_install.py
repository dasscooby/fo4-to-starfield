"""scripts/newgame/anim_console_install.py: the animation console probe's own install record next to an installed
experiment and the planet probe, on a synthetic stage (a temp game folder, a temp LOCALAPPDATA, the archive builder
replaced by a stub; no game, no Archive2). The other records must stay byte for byte."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
sys.path.insert(0, str(ROOT / "src"))
from ba2_fixture import archive_from_tree  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
import exp_install  # noqa: E402
import make_anim_console as mws  # noqa: E402
import planet_probe_install  # noqa: E402
import anim_console_install as pai  # noqa: E402

PLUGIN = "FO4SFAnimConsole.esm"
EXP_RECORD = b'{"exp_dir": "C:/stage/core", "files": {}, "complete": true}'
PLANET_RECORD = b'{"exp_dir": "C:/stage/planet", "files": {}, "complete": true}'
STARFIELD = b"Starfield.esm of the test"


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stage(d):
    files = {PLUGIN: esm.PluginWriter(["Starfield.esm"], esm.ESM, author=PLUGIN).to_bytes(),
             "Data/Scripts/FO4SF_AnimConsoleQuest.pex": b"pex", "Data/meshes/fo4port/c_anim.nif": b"nif"}
    for rel, data in files.items():
        write(os.path.join(d, *rel.split("/")), data)
    write(os.path.join(d, "FO4SF_AnimConsoleQuest.psc"), b"source, not packed")
    plan = {"kind": "anim-console", "version": 1, "plugins": [PLUGIN], "outputs": {k: sha(v) for k, v in files.items()},
            "inputs": {"Starfield.esm": {"sha256": sha(STARFIELD)}}}
    with open(os.path.join(d, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f)
    return d


class AnimConsoleInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        write(os.path.join(self.data, "Starfield.esm"), STARFIELD)
        write(os.path.join(self.data, exp_install.RECORD), EXP_RECORD)
        write(os.path.join(self.data, planet_probe_install.RECORD), PLANET_RECORD)
        self.staged = stage(os.path.join(root, "anim_console"))
        local = os.path.join(root, "local")
        self.plugins = os.path.join(local, "Starfield", "Plugins.txt")
        write(self.plugins, b"# header\r\n*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n")
        old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = local
        self.addCleanup(lambda: os.environ.__setitem__("LOCALAPPDATA", old_local) if old_local is not None
                        else os.environ.pop("LOCALAPPDATA", None))
        old_build = exp_install.build_ba2
        self.addCleanup(setattr, exp_install, "build_ba2", old_build)

        def stub_build(a, root_dir, out):
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = pai.main(list(argv) + ["--starfield", self.game]) or 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def lines(self):
        with open(self.plugins, encoding="utf-8-sig") as f:
            return f.read().splitlines()

    def read(self, name):
        with open(os.path.join(self.data, name), "rb") as f:
            return f.read()

    def test_the_record_is_its_own(self):
        self.assertNotIn(pai.RECORD, (exp_install.RECORD, planet_probe_install.RECORD))
        self.assertEqual(pai.RECORD, "FO4SFAnimConsole.install.json")

    def test_install_rides_along_and_uninstall_restores(self):
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertEqual(code, 0, out)
        self.assertEqual(exp_install.RECORD, "FO4SFExp.install.json")             # restored after the call
        for name in (PLUGIN, "FO4SFAnimConsole - Main.ba2", pai.RECORD):
            self.assertTrue(os.path.isfile(os.path.join(self.data, name)), name)
        self.assertFalse(os.path.exists(os.path.join(self.data, "Scripts")))      # packed, not loose
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm", "*" + PLUGIN])
        self.assertTrue(json.loads(self.read(pai.RECORD))["complete"])
        self.assertEqual(self.read(exp_install.RECORD), EXP_RECORD)               # the core's record, untouched
        self.assertEqual(self.read(planet_probe_install.RECORD), PLANET_RECORD)   # the planet probe's, untouched

        code, out = self.run_main("status")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["plugins"], [PLUGIN])
        self.assertEqual(self.run_main("active")[0], 0)
        self.assertEqual(self.run_main("order")[0], 0)
        self.assertEqual(self.run_main("install", "--dir", self.staged)[1].strip().splitlines()[-1], "already installed")

        code, out = self.run_main("uninstall")
        self.assertEqual(code, 0, out)
        for name in (PLUGIN, "FO4SFAnimConsole - Main.ba2", pai.RECORD):
            self.assertFalse(os.path.exists(os.path.join(self.data, name)), name)
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"])
        self.assertEqual(self.read(exp_install.RECORD), EXP_RECORD)
        self.assertEqual(self.read(planet_probe_install.RECORD), PLANET_RECORD)

    def test_a_changed_stage_is_refused(self):
        with open(os.path.join(self.staged, PLUGIN), "ab") as f:
            f.write(b"!")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("does not match its plan.json", str(code))
        self.assertFalse(os.path.exists(os.path.join(self.data, pai.RECORD)))
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm"])

    def test_a_file_the_plan_does_not_name_is_refused(self):
        write(os.path.join(self.staged, "Data", "Scripts", "Extra.pex"), b"x")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("files not in plan.json", str(code))

    def test_a_changed_starfield_esm_is_refused(self):
        write(os.path.join(self.data, "Starfield.esm"), b"after a game update")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("Starfield.esm changed since the stage", str(code))
        self.assertFalse(os.path.exists(os.path.join(self.data, pai.RECORD)))

    def test_another_probes_plan_is_refused(self):
        plan = json.loads(Path(self.staged, "plan.json").read_text())
        plan["kind"] = "anim-probe"
        Path(self.staged, "plan.json").write_text(json.dumps(plan))
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("is not the animation console probe's", str(code))

    def test_an_extra_plugin_is_refused(self):
        write(os.path.join(self.staged, "Other.esm"), b"TES4")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("files not in plan.json", str(code))

    def test_an_existing_file_is_never_overwritten(self):
        write(os.path.join(self.data, PLUGIN), b"someone else's")
        code, _ = self.run_main("install", "--dir", self.staged)
        self.assertIn("refusing to overwrite", str(code))
        self.assertEqual(self.read(PLUGIN), b"someone else's")

    def test_prepacked_is_forwarded_unchanged_and_only_when_given(self):
        """FAL-274: the launcher passes an existing archive; the wrapper hands it to exp_install.py and never builds."""
        from unittest import mock
        with mock.patch.object(pai, "installer", return_value=0) as inst, \
                mock.patch.object(pai, "prepacked_supported", return_value=True):
            self.run_main("install", "--dir", self.staged)
            plain = inst.call_args[0][0]
            self.run_main("install", "--dir", self.staged, "--prepacked", "C:/cache/kit.ba2")
            packed = inst.call_args[0][0]
        self.assertNotIn("--prepacked", plain)
        self.assertEqual(packed[-2:], ["--prepacked", "C:/cache/kit.ba2"])
        self.assertEqual(packed[:-2], plain)                                      # nothing else changes
        self.assertIn("--pack", packed)

    def test_prepacked_is_refused_before_anything_runs_when_exp_install_cannot_honor_it(self):
        """FAL-286: an exp_install.py without --prepacked would reject the flag (exit 2) or build its own archive."""
        from unittest import mock
        with mock.patch.object(pai, "installer", return_value=0) as inst, \
                mock.patch.object(pai, "prepacked_supported", return_value=False):
            code, _ = self.run_main("install", "--dir", self.staged, "--prepacked", "C:/cache/kit.ba2")
        self.assertIn("--prepacked is not supported", str(code))
        inst.assert_not_called()
        self.assertFalse(os.path.exists(os.path.join(self.data, PLUGIN)))

    def test_the_support_check_reads_the_real_exp_install(self):
        self.assertEqual(pai.prepacked_supported(), "--prepacked" in Path(pai.exp_install.__file__).read_text(encoding="utf-8"))

    def test_the_stage_needs_its_dir(self):
        code, _ = self.run_main("install")
        self.assertIn("needs --dir", str(code))


if __name__ == "__main__":
    unittest.main()
