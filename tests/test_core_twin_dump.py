"""scripts/core_storage/twin_dump.py on plugins written by hand in this file (no dotnet, no game): the differences it must
name between an override and its twin in the core: a subrecord the override lost, a changed one, flags, the groups."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "core_storage"))
import twin_dump  # noqa: E402


def sub(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def rec(sig, form, subs, flags=0, version=576, compress=False):
    body = b"".join(subs)
    if compress:
        body = struct.pack("<I", len(body)) + zlib.compress(body)
        flags |= twin_dump.COMPRESSED
    return sig + struct.pack("<IIIIHH", len(body), flags, form, 0, version, 0) + body


def grup(gtype, label, content):
    return b"GRUP" + struct.pack("<I", 24 + len(content)) + label + struct.pack("<IIHH", gtype, 0, 0, 0) + content


def tes4(masters):
    body = sub(b"HEDR", struct.pack("<fII", 0.96, 0, 0x800)) + b"".join(sub(b"MAST", m.encode() + b"\0") + sub(b"DATA", b"\0" * 8) for m in masters)
    return rec(b"TES4", 0, [body])


def plugin(masters, cell_idx, cell_subs, cell_flags=0, children=b"", compress=False):
    world = rec(b"WRLD", cell_idx << 24 | 0x803, [sub(b"EDID", b"World\0")])
    cell = rec(b"CELL", cell_idx << 24 | 0x901, cell_subs, flags=cell_flags, compress=compress)
    cellgrp = grup(6, struct.pack("<I", cell_idx << 24 | 0x901), children) if children else b""
    sb = grup(5, struct.pack("<hh", -2, 1), cell + cellgrp)
    blk = grup(4, struct.pack("<hh", -1, 0), sb)
    wc = grup(1, struct.pack("<I", cell_idx << 24 | 0x803), blk)
    return tes4(masters) + grup(0, b"WRLD", world + wc)


EDID = sub(b"EDID", b"FO4Core_RedRocketSpawn\0")
XCLC = sub(b"XCLC", struct.pack("<ii", -10, 11) + b"\0\0\0\0")
XCLL = sub(b"XCLL", bytes(range(40)))
REFR = rec(b"REFR", 0x02000800, [sub(b"EDID", b"X\0")])


class TwinDumpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_pair(self, core_subs, over_subs, over_flags=0, children=b"", core_flags=0, compress_core=False):
        core = Path(self.tmp.name) / "FO4TerrainCore.esm"
        over = Path(self.tmp.name) / "FO4SFCoreStorage.esm"
        core.write_bytes(plugin(["Starfield.esm"], 1, core_subs, core_flags, compress=compress_core))
        over.write_bytes(plugin(["Starfield.esm", "FO4TerrainCore.esm"], 1, over_subs, over_flags, children))
        return twin_dump.report(str(over), str(core))

    def test_an_identical_override_has_no_difference(self):
        lines, summary = self.run_pair([EDID, XCLC, XCLL], [EDID, XCLC, XCLL])
        self.assertEqual(summary, ["WRLD 000803: no difference in header or subrecords", "CELL 000901: no difference in header or subrecords"])

    def test_a_subrecord_the_override_lost_is_named(self):
        lines, summary = self.run_pair([EDID, XCLC, XCLL], [EDID, XCLC])
        self.assertTrue(any("XCLL" in l and "ONLY IN THE CORE" in l for l in lines), lines)
        self.assertEqual(summary[1], "CELL 000901: XCLL only in the core")

    def test_a_changed_subrecord_names_the_byte_and_the_bytes(self):
        changed = sub(b"XCLL", bytes(range(40))[:10] + b"\xff" + bytes(range(40))[11:])
        lines, summary = self.run_pair([EDID, XCLC, XCLL], [EDID, XCLC, changed])
        self.assertIn("XCLL differs at byte 10", summary[1])

    def test_a_flag_or_a_compressed_twin_is_read_and_reported(self):
        lines, summary = self.run_pair([EDID, XCLC, XCLL], [EDID, XCLC, XCLL], over_flags=0x400, compress_core=True)
        self.assertEqual(summary[1], "CELL 000901: flags 0x00040000 vs 0x00000400")       # the core's record is zlib packed and still compared
        self.assertTrue(any("(compressed)" in l for l in lines))

    def test_the_cells_child_groups_are_listed_for_both(self):
        children = grup(8, struct.pack("<I", 0x01000901), REFR) + grup(9, struct.pack("<I", 0x01000901), REFR + REFR)
        lines, _ = self.run_pair([EDID, XCLC], [EDID, XCLC], children=children)
        self.assertIn("  children, core:     no child groups", lines)
        self.assertIn("  children, override: cell persistent children: REFR x1; cell temporary children: REFR x2", lines)

    def test_a_plugin_that_does_not_master_the_core_is_said(self):
        core = Path(self.tmp.name) / "FO4TerrainCore.esm"
        over = Path(self.tmp.name) / "FO4SFCoreStorage.esm"
        core.write_bytes(plugin(["Starfield.esm"], 1, [EDID]))
        over.write_bytes(plugin(["Starfield.esm"], 1, [EDID]))
        _, summary = twin_dump.report(str(over), str(core))
        self.assertEqual(summary, ["the core is not a master of the plugin"])

    def test_the_command_writes_a_report_and_ends_with_the_verdicts(self):
        import contextlib
        import io
        core = Path(self.tmp.name) / "FO4TerrainCore.esm"
        over = Path(self.tmp.name) / "FO4SFCoreStorage.esm"
        core.write_bytes(plugin(["Starfield.esm"], 1, [EDID, XCLC, XCLL]))
        over.write_bytes(plugin(["Starfield.esm", "FO4TerrainCore.esm"], 1, [EDID, XCLC]))
        out = Path(self.tmp.name) / "r.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(twin_dump.main([str(over), str(core), "--out", str(out)]), 0)
        text = out.read_text(encoding="utf-8")
        self.assertIn("VERDICTS", text)
        self.assertIn("CELL 000901: XCLL only in the core", text)


if __name__ == "__main__":
    unittest.main()
