"""Synthetic tests for fo4sf btd-summary CLI."""
import io
import json
import struct
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import zlib
import numpy as np

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))  # run alone: put fo4sf on the path
from fo4sf.__main__ import main
from fo4sf.btd import read as read_btd, Btd
from test_dds_summary import _run_without_numpy


def _minimal_btd(ncx=1, ncy=1, hmin=0.0, hmax=100.0, version=1) -> bytes:
    """Build a tiny valid BTD for testing (1 cell, no LTEX, trivial zlib blocks)."""
    # Header
    header = struct.pack("<4sIffIIiiiiI", b"BTDB", version, hmin, hmax, ncx*128, ncy*128, 0, 0, 0, 0, 0)
    # cell minmax (2 floats per cell)
    mm = struct.pack("<ff", hmin, hmax) * (ncx * ncy)
    # quad map (32 bytes per cell)
    quad = b"\x00" * (32 * ncx * ncy)
    # LOD4 placeholder (256 * n)
    lod4 = b"\x00" * (256 * ncx * ncy)
    # tables for LOD 3,2,1,0 — for 1x1, counts are 1
    tables = b""
    data_blocks = b""
    offsets = []
    for l in (3, 2, 1, 0):
        # one group each
        raw = b"\x00" * 65536  # dummy for non-LOD0; LOD0 needs real
        if l == 0:
            # simple height/weight block
            heights = np.zeros((128, 128), np.uint16)
            weights = np.zeros((128, 128), np.uint16)
            raw = heights.tobytes() + weights.tobytes()
        compressed = zlib.compress(raw)
        offsets.append(len(data_blocks))
        tables += struct.pack("<II", len(data_blocks), len(compressed))
        data_blocks += compressed
    return header + mm + quad + lod4 + tables + data_blocks


class TestBtdSummary(unittest.TestCase):
    def test_needs_numpy_message_without_numpy(self):
        """Like dds-summary (#548): numpy loads only when btd-summary runs."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tiny.btd"
            path.write_bytes(_minimal_btd())
            run = _run_without_numpy("btd-summary", str(path))
        self.assertEqual(run.returncode, 1)
        self.assertIn("needs numpy", run.stderr)
        self.assertNotIn("Traceback", run.stderr)

    def test_text_output(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tiny.btd"
            path.write_bytes(_minimal_btd())
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["btd-summary", str(path)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("Version: 1", out)
            self.assertIn("Cells: 1 x 1", out)
            self.assertIn("LTEX FormIDs: 0", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tiny.btd"
            path.write_bytes(_minimal_btd(hmin=10.0, hmax=50.0))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["btd-summary", "--json", str(path)])
            self.assertEqual(rc, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["cells_x"], 1)
            self.assertAlmostEqual(data[0]["height_min_m"], 10.0)

    def test_missing_file(self):
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main(["btd-summary", "/nonexistent.btd"])
        self.assertEqual(rc, 1)
        self.assertIn("not a file", err.getvalue())


if __name__ == "__main__":
    unittest.main()
