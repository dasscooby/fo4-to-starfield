"""Synthetic tests for fo4sf bgsm-summary CLI."""
import io
import struct
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))  # run alone: put fo4sf on the path
from fo4sf.__main__ import main


def _make_minimal_bgsm():
    """Minimal v2 BGSM that parse_bgsm accepts."""
    d = bytearray(200)
    d[0:4] = b"BGSM"
    struct.pack_into("<I", d, 4, 2)  # version
    struct.pack_into("<I", d, 8, 3)  # tile both
    struct.pack_into("<4f", d, 12, 0.0, 0.0, 1.0, 1.0)
    pos = 63
    for name in (b"diffuse.dds\0", b"normal.dds\0", b"spec.dds\0", b"", b"", b""):
        struct.pack_into("<I", d, pos, len(name))
        pos += 4
        if name:
            d[pos:pos + len(name)] = name
        pos += len(name)
    return bytes(d)


class BgsmSummaryTests(unittest.TestCase):
    def test_summary_text(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.bgsm"
            p.write_bytes(_make_minimal_bgsm())
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["bgsm-summary", str(p)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("v2", out)
            self.assertIn("diffuse.dds", out)
            self.assertIn("normal.dds", out)
            self.assertIn("tile_u=True", out)

    def test_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            rc = main(["bgsm-summary", "no-such-file.bgsm"])
        self.assertEqual(rc, 1)
        self.assertIn("missing:", buf_err.getvalue())


if __name__ == "__main__":
    unittest.main()
