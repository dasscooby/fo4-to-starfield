"""Synthetic tests for the nif-summary CLI."""
from __future__ import annotations

import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))  # run alone: put fo4sf on the path
from fo4sf.nif import NifFile, serialize
from fo4sf.__main__ import cmd_nif_summary


class TestNifSummary(unittest.TestCase):
    def _minimal_nif(self, bs: int = 130) -> bytes:
        n = NifFile()
        n.bs_version = bs
        n.author = b"test"
        n.block_types = ["NiNode"]
        n.block_type_index = [0]
        n.blocks = [b"\x00" * 16]
        n.strings = [b"root"]
        return serialize(n)

    def test_text_summary(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "tiny.nif"
            path.write_bytes(self._minimal_nif())
            # Capture stdout
            import sys
            old = sys.stdout
            sys.stdout = buf = io.StringIO()
            try:
                rc = cmd_nif_summary(type("A", (), {"paths": [str(path)], "json": False})())
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("BS version: 130", out)
            self.assertIn("Blocks: 1", out)
            self.assertIn("NiNode=1", out)

    def test_json_summary(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "tiny.nif"
            path.write_bytes(self._minimal_nif(175))
            import sys
            old = sys.stdout
            sys.stdout = buf = io.StringIO()
            try:
                rc = cmd_nif_summary(type("A", (), {"paths": [str(path)], "json": True})())
            finally:
                sys.stdout = old
            self.assertEqual(rc, 0)
            import json
            data = json.loads(buf.getvalue())
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["bs_version"], 175)
            self.assertEqual(data[0]["blocks"], 1)

    def test_missing_file(self):
        import sys
        old_err = sys.stderr
        sys.stderr = io.StringIO()
        try:
            rc = cmd_nif_summary(type("A", (), {"paths": ["/nonexistent.nif"], "json": False})())
        finally:
            sys.stderr = old_err
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
