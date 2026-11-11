"""scripts/find_power_armor_furniture.py on a synthetic Starfield.esm (no game data): the keywords by name, the furniture that
carries one, who else names them (FAL-273, the PC search for a real power armor station)."""
import os
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fo4sf.planet import esm  # noqa: E402
import find_power_armor_furniture as fpa  # noqa: E402


def z(t):
    return t.encode("ascii") + b"\0"


def kywd(fid, edid):
    return esm.Record(b"KYWD", fid, [(b"EDID", z(edid))])


def furn(fid, edid, kws, model="Furniture\\Station.nif", script=False):
    subs = [(b"EDID", z(edid)), (b"KSIZ", struct.pack("<I", len(kws))), (b"KWDA", struct.pack(f"<{len(kws)}I", *kws)),
            (b"MODL", z(model))]
    if script:
        subs.append((b"VMAD", b"\0\0"))
    return esm.Record(b"FURN", fid, subs)


def armo(fid, edid, kw):
    return esm.Record(b"ARMO", fid, [(b"EDID", z(edid)), (b"KWDA", struct.pack("<I", kw))])


class FindTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "Starfield.esm")
        w = esm.PluginWriter([], esm.ESM)
        for label, recs in (
                ("KYWD", [kywd(0x1000, "FurnitureTypePowerArmor"), kywd(0x1001, "LinkPowerArmor"), kywd(0x1002, "ChairKeyword")]),
                ("FURN", [furn(0x2000, "PowerArmorStation01", [0x1000, 0x1002], script=True), furn(0x2001, "PlainChair", [0x1002]),
                          furn(0x2002, "PAWorkbench", [0x1001])]),
                ("ARMO", [armo(0x3000, "FrameChestPiece", 0x1001), armo(0x3001, "Jacket", 0x1002)])):
            for r in recs:
                w.add(r)
        w.write(self.path)

    def test_the_keywords_and_the_furniture_that_carries_them_are_named(self):
        text = "\n".join(fpa.report(self.path))
        self.assertIn("2 keywords match", text)
        self.assertIn("KYWD 00001000 FurnitureTypePowerArmor", text)
        self.assertIn("KYWD 00001001 LinkPowerArmor", text)
        self.assertNotIn("ChairKeyword", text.split("FURN carrying")[0])
        self.assertIn("FURN carrying one of them: 2", text)
        self.assertIn("FURN 00002000 PowerArmorStation01: keywords ['FurnitureTypePowerArmor'] of 2 total", text)
        self.assertIn("script yes", text)
        self.assertIn("FURN 00002002 PAWorkbench", text)
        self.assertNotIn("PlainChair", text)

    def test_other_classes_that_name_them_are_counted_and_the_report_has_no_bytes(self):
        text = "\n".join(fpa.report(self.path))
        self.assertIn("ARMO: 1  ['FrameChestPiece']", text)
        self.assertNotIn("Jacket", text)
        self.assertNotRegex(text, r"[0-9a-f]{16}")                       # editor ids and form ids only

    def test_a_word_can_be_chosen_and_the_command_writes_the_file(self):
        out = os.path.join(self.tmp.name, "r.txt")
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fpa.main([self.path, out, "--word", "ChairKeyword"]), 0)
        with open(out, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("1 keywords match ['ChairKeyword']", text)
        self.assertIn("FURN carrying one of them: 2", text)


if __name__ == "__main__":
    unittest.main()
