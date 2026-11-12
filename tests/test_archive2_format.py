"""Archive2's -format values: the game's Tools\\Archive2 takes General, DDS or XBoxDDS (not DX10). exp_install.build_ba2 must pass
DDS for the texture archive and General for the rest; checked on the command line it builds, with Archive2 replaced by a stub."""
import argparse
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
import deploy_starfield as deploy  # noqa: E402
import exp_install  # noqa: E402

ARCHIVE2_FORMATS = {"General", "DDS", "XBoxDDS"}


class Archive2FormatTests(unittest.TestCase):
    def run_build(self, textures):
        with tempfile.TemporaryDirectory() as t:
            game = Path(t, "game")
            tool = game / "Tools" / "Archive2" / "Archive2.exe"
            tool.parent.mkdir(parents=True)
            tool.write_bytes(b"")
            root = Path(t, "root")
            (root / "Textures").mkdir(parents=True)
            (root / "Meshes").mkdir()
            calls = []

            def run(cmd, **kw):
                calls.append(cmd)
                out = [c for c in cmd if c.startswith("-create=")][0][len("-create="):]
                Path(out).write_bytes(b"BTDX" + bytes(32))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            a = argparse.Namespace(starfield=str(game))
            with patch.object(deploy.subprocess, "run", side_effect=run):
                exp_install.build_ba2(a, str(root), str(Path(t, "out.ba2")), textures=textures)
            self.assertEqual(len(calls), 1)
            return calls[0]

    def test_texture_archive_asks_for_dds(self):
        cmd = self.run_build(True)
        self.assertIn("-format=DDS", cmd)
        self.assertEqual(cmd[1], "Textures")

    def test_general_archive_asks_for_general(self):
        cmd = self.run_build(False)
        self.assertIn("-format=General", cmd)
        self.assertEqual(cmd[1], "Meshes")

    def test_every_format_is_one_archive2_accepts(self):
        for textures in (True, False):
            fmt = [c for c in self.run_build(textures) if c.startswith("-format=")][0][len("-format="):]
            self.assertIn(fmt, ARCHIVE2_FORMATS)


if __name__ == "__main__":
    unittest.main()
