"""questprobe_install.py: the probe ships as its own small deployment through bridge_install's logic, its scripts in a
ba2 (no loose files on the test PC). A temp game folder, a temp LOCALAPPDATA and the archive builder replaced by a stub
(the same fixture as test_bridge_install.py); no game, no Archive2."""
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
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ba2_fixture import archive_from_tree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "questprobe"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
import bridge_install  # noqa: E402
import exp_install  # noqa: E402
import questprobe_install as qi  # noqa: E402

SCRIPTS = ("FO4SF_QProbeQuest", "FO4SF_QProbeFragments", "FO4SF_QProbeSMQuest")


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


class ProbeInstallTests(unittest.TestCase):
    def setUp(self):
        self.saved = {k: getattr(bridge_install, k) for k in qi.NAMES}
        self.addCleanup(lambda: [setattr(bridge_install, k, v) for k, v in self.saved.items()])
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        self.port = os.path.join(self.data, "FO4Port.esm")
        write(self.port, b"TES4-port")
        self.staged = os.path.join(root, "questprobe_v1")
        write(os.path.join(self.staged, qi.NAMES["PLUGIN"]), b"TES4-probe")
        for s in SCRIPTS:
            write(os.path.join(self.staged, "Data", "Scripts", s + ".pex"), s.encode())
        write(os.path.join(self.staged, "FO4SF_QProbeQuest.psc"), b"source, not packed")
        self.write_plan()
        local = os.path.join(root, "local")
        self.plugins = os.path.join(local, "Starfield", "Plugins.txt")
        write(self.plugins, b"# header\r\n*FO4Port.esm\r\n*FO4SFBridge.esm\r\n")
        old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = local
        self.addCleanup(lambda: os.environ.__setitem__("LOCALAPPDATA", old_local) if old_local is not None
                        else os.environ.pop("LOCALAPPDATA", None))
        old_build = exp_install.build_ba2
        self.addCleanup(setattr, exp_install, "build_ba2", old_build)
        self.packed = []

        def stub_build(a, root_dir, out):
            self.packed.append(sorted(str(p.relative_to(root_dir)) for p in Path(root_dir).rglob("*") if p.is_file()))
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build

    def write_plan(self):
        h = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
        plan = {"kind": "questprobe", "plugin": qi.NAMES["PLUGIN"],
                "plugin_sha256": h(os.path.join(self.staged, qi.NAMES["PLUGIN"])),
                "scripts": {s: h(os.path.join(self.staged, "Data", "Scripts", s + ".pex")) for s in SCRIPTS},
                "checked_against_sha256": {"FO4Port.esm": h(self.port)}}
        write(os.path.join(self.staged, "plan.json"), json.dumps(plan).encode())

    def run_cmd(self, cmd):
        return qi.main([cmd, "--dir", self.staged, "--starfield", self.game])

    def lines(self):
        return Path(self.plugins).read_text(encoding="utf-8-sig").splitlines()

    def test_prepacked_path_never_calls_archive_builder(self):
        archive = os.path.join(self.staged, qi.NAMES["ARCHIVE"])
        write(archive, archive_from_tree(Path(self.staged) / "Data"))
        with patch.object(exp_install, "build_ba2", side_effect=AssertionError("must not build")):
            qi.main(["install", "--dir", self.staged, "--starfield", self.game, "--prepacked", archive])
        self.assertTrue(Path(self.data, qi.NAMES["RECORD"]).exists())
        self.assertEqual(self.packed, [])

    def test_wrong_prepacked_archive_refuses_without_writing_receipt(self):
        archive = os.path.join(self.staged, qi.NAMES["ARCHIVE"])
        write(archive, archive_from_tree(Path(self.staged) / "Data"))
        write(os.path.join(self.staged, "Data", "Scripts", SCRIPTS[0] + ".pex"), b"changed")
        self.write_plan()  # stage is valid, supplied archive is stale
        before = Path(self.plugins).read_bytes()
        with patch.object(exp_install, "build_ba2", side_effect=AssertionError("must not build")):
            with self.assertRaises((ValueError, SystemExit)):
                qi.main(["install", "--dir", self.staged, "--starfield", self.game, "--prepacked", archive])
        self.assertFalse(Path(self.data, qi.NAMES["RECORD"]).exists())
        self.assertEqual(Path(self.plugins).read_bytes(), before)

    def test_install_packs_the_three_scripts_and_activates_last(self):
        self.run_cmd("install")
        self.assertEqual(self.packed, [sorted(os.path.join("Scripts", s + ".pex") for s in SCRIPTS)])
        for name in (qi.NAMES["PLUGIN"], qi.NAMES["ARCHIVE"], qi.NAMES["RECORD"]):
            self.assertTrue(os.path.exists(os.path.join(self.data, name)), name)
        self.assertFalse(os.path.exists(os.path.join(self.data, "Scripts")), "no loose scripts")
        self.assertEqual(self.lines()[-1], "*FO4SFQuestProbe.esm")

    def test_uninstall_leaves_the_bridge_and_the_rest(self):
        self.run_cmd("install")
        self.run_cmd("uninstall")
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4SFBridge.esm"])
        self.assertEqual(os.listdir(self.data), ["FO4Port.esm"])

    def test_the_bridge_record_is_not_the_probe_record(self):
        self.run_cmd("install")
        self.assertFalse(os.path.exists(os.path.join(self.data, "FO4SFBridge.install.json")))
        qi.configure()
        self.assertEqual(bridge_install.RECORD, "FO4SFQuestProbe.install.json")

    def test_a_changed_staged_script_is_refused(self):
        write(os.path.join(self.staged, "Data", "Scripts", "FO4SF_QProbeSMQuest.pex"), b"edited")
        with self.assertRaises(SystemExit):
            self.run_cmd("install")
        self.assertEqual(os.listdir(self.data), ["FO4Port.esm"])

    def test_every_dir_spelling_is_plan_checked(self):
        """20 Oct review on #393: "--dir=X" skipped check_plan. Each spelling must refuse a changed script."""
        write(os.path.join(self.staged, "Data", "Scripts", "FO4SF_QProbeSMQuest.pex"), b"edited")
        for args in (["--dir=" + self.staged], ["--dir", self.staged]):
            with self.subTest(args[0][:6]), self.assertRaises(SystemExit):
                qi.main(["install", *args, "--starfield", self.game])
            self.assertEqual(os.listdir(self.data), ["FO4Port.esm"])

    def test_install_without_dir_is_refused(self):
        with self.assertRaises(SystemExit):
            qi.main(["install", "--starfield", self.game])
        self.assertEqual(os.listdir(self.data), ["FO4Port.esm"])

    def test_a_different_installed_port_is_refused(self):
        """21 Oct review on #393: the probe's ids are port-local, so a rebuilt port must not take it."""
        write(self.port, b"TES4-port-rebuilt")
        with self.assertRaises(SystemExit):
            self.run_cmd("install")
        self.assertEqual(sorted(os.listdir(self.data)), ["FO4Port.esm"])
        os.remove(self.port)
        with self.assertRaises(SystemExit):
            self.run_cmd("install")
        self.assertEqual(os.listdir(self.data), [])

    def test_an_unplanned_file_in_data_is_refused(self):
        write(os.path.join(self.staged, "Data", "Scripts", "Other.pex"), b"x")
        with self.assertRaises(SystemExit):
            self.run_cmd("install")

    def test_pack_check_touches_nothing_in_the_game(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.run_cmd("pack-check")
        # archive names are relative to Data (Scripts/...), never Data/Scripts/...
        self.assertIn("Scripts/FO4SF_QProbeQuest.pex", out.getvalue())
        self.assertNotIn("Data/Scripts", out.getvalue())
        self.assertEqual(len(self.packed), 1)
        self.assertEqual(os.listdir(self.data), ["FO4Port.esm"])
        self.assertEqual(self.lines(), ["# header", "*FO4Port.esm", "*FO4SFBridge.esm"])


if __name__ == "__main__":
    unittest.main()
