"""src/fo4sf/record_writer.py on a synthetic Starfield.esm (no game data)."""
import os
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from fo4sf import plugin_verify, record_writer as rw  # noqa: E402
from fo4sf.planet import esm  # noqa: E402
import dump_starfield_records  # noqa: E402


def z(t):
    return t.encode("ascii") + b"\0"


def spel(n, mgef):
    spit = struct.pack("<9I", 0, 0, n, 0, 0, 0, 0, 0, 7)            # bytes 8..11 vary: a synthetic "cost"
    return esm.Record(b"SPEL", 0x1000 + n, [
        (b"EDID", z(f"Spell{n}")), (b"OBND", b"\0" * 12), (b"ODTY", b"\0" * 4), (b"FULL", struct.pack("<I", 100 + n)),
        (b"ETYP", struct.pack("<I", 1)), (b"DESC", struct.pack("<I", 200 + n)), (b"SPIT", spit),
        (b"EFID", struct.pack("<I", mgef)), (b"EFIT", struct.pack("<fII", 10.0 + n, 0, 0)),
        (b"EFIF", b"\x01\x02"), (b"MUID", b"\xAA\xBB\xCC\xDD")])


def mgef(n):
    return esm.Record(b"MGEF", 0x2000 + n, [(b"EDID", z(f"Effect{n}")), (b"DATA", struct.pack("<2I", 5, n)),
                                           (b"DNAM", b"\0" * 4)])


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sf = os.path.join(self.tmp.name, "Starfield.esm")
        w = esm.PluginWriter([], esm.ESM | esm.LOCALIZED)
        for n in range(1, 6):
            w.add(mgef(n))
            w.add(spel(n, 0x2000 + n))
        w.write(self.sf)


class DumpTests(Base):
    def test_layout_shows_which_bytes_vary(self):
        d = rw.dump_records(self.sf, ["SPEL", "MGEF"], per_class=5, keep=2, edids=["Spell5"])
        lay = d["classes"]["SPEL"]["layout"]
        self.assertEqual(lay["SPIT"]["length"], 36)
        self.assertEqual(lay["SPIT"]["varying"], [8])                  # only the byte that was made to differ
        self.assertIn(0, lay["ETYP"]["constant"])
        self.assertEqual([r["edid"] for r in d["classes"]["SPEL"]["records"]], ["Spell1", "Spell2", "Spell5"])
        self.assertTrue(d["localized"])
        self.assertEqual(d["plugin"], "Starfield.esm")                 # the file name only: the dump travels
        self.assertIn("SPIT", rw.dump_text(d))

    def test_missing_edid_is_reported(self):
        d = rw.dump_records(self.sf, ["SPEL"], per_class=2, edids=["Nope"])
        self.assertEqual(d["missing_edids"], ["nope"])

    def test_a_found_edid_is_not_missing_in_any_class(self):
        # Spell1 is in the first `keep` records; Spell5 is past per_class; Effect2 is in the other class
        d = rw.dump_records(self.sf, ["SPEL", "MGEF"], per_class=2, keep=2, edids=["Spell1", "Spell5", "Effect2"])
        self.assertEqual(d["missing_edids"], [])
        self.assertEqual(d["classes"]["SPEL"]["found_edids"], ["spell1", "spell5"])
        self.assertEqual(d["classes"]["MGEF"]["found_edids"], ["effect2"])
        self.assertEqual([r["edid"] for r in d["classes"]["SPEL"]["records"]], ["Spell1", "Spell2", "Spell5"])
        with open(os.devnull, "w") as sink:
            import contextlib
            with contextlib.redirect_stdout(sink):
                out = os.path.join(self.tmp.name, "o2")
                self.assertEqual(dump_starfield_records.main(
                    [self.sf, out, "--classes", "SPEL", "MGEF", "--per-class", "2", "--edid", "Spell5", "--edid", "Effect2"]), 0)
                self.assertEqual(dump_starfield_records.main([self.sf, out, "--classes", "SPEL", "--edid", "Nope"]), 1)

    def test_cli(self):
        out = os.path.join(self.tmp.name, "o")
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dump_starfield_records.main([self.sf, out, "--classes", "SPEL", "--per-class", "3"]), 0)
        self.assertTrue(os.path.exists(os.path.join(out, "starfield_records.json")))
        self.assertTrue(os.path.exists(os.path.join(out, "starfield_records.txt")))


class MakeTests(Base):
    def test_clone_keeps_everything_but_what_is_replaced(self):
        t = rw.Template.from_plugin(self.sf, "SPEL", edid="spell3")
        r = rw.make(t, 0x01000800, "FO4SF_RadsSpell", full="Rads", desc="")
        self.assertEqual(r.get(b"EDID"), z("FO4SF_RadsSpell"))
        self.assertEqual(r.get(b"FULL"), z("Rads"))
        for sub in (b"OBND", b"ETYP", b"SPIT", b"EFID", b"EFIT", b"EFIF", b"MUID"):
            self.assertEqual(r.get(sub), t.record.get(sub), sub)
        self.assertEqual([s for s, _ in r.subs], [s for s, _ in t.record.subs])
        self.assertEqual(t.record.get(b"EDID"), z("Spell3"))             # the template is untouched

    def test_a_template_by_predicate_and_from_dump(self):
        t = rw.Template.from_plugin(self.sf, "MGEF", pick=lambda r: struct.unpack_from("<I", r.get(b"DATA"), 4)[0] == 4)
        self.assertEqual(t.record.edid, "Effect4")
        d = rw.dump_records(self.sf, ["MGEF"], per_class=5, edids=["Effect5"])
        self.assertEqual(rw.Template.from_dump(d, "MGEF", "effect5").record.get(b"DATA"), mgef(5).get(b"DATA"))
        with self.assertRaises(rw.WriterError):
            rw.Template.from_plugin(self.sf, "MGEF", edid="Nobody")
        with self.assertRaises(rw.WriterError):
            rw.Template.from_plugin(self.sf, "MGEF")

    def test_a_template_without_required_fields_is_refused(self):
        rec = spel(1, 0x2001)
        rec.subs = [(s, d) for s, d in rec.subs if s != b"ETYP"]
        with self.assertRaises(rw.WriterError) as cm:
            rw.make(rw.Template(rec, "x"), 0x01000800, "X")
        self.assertIn("ETYP", str(cm.exception))

    def test_replace_does_not_add_blind(self):
        t = rw.Template.from_plugin(self.sf, "MGEF", edid="Effect1")
        r = rw.make(t, 0x01000800, "E", replace={"DATA": b"\1" * 8}, drop=["DNAM"])
        self.assertEqual(r.get(b"DATA"), b"\1" * 8)
        self.assertIsNone(r.get(b"DNAM"))
        with self.assertRaises(rw.WriterError):
            rw.make(t, 0x01000800, "E", replace={"XXXX": b""})

    def test_set_field_needs_a_varying_offset(self):
        d = rw.dump_records(self.sf, ["SPEL"], per_class=5)
        lay = rw.Layout(d)
        t = rw.Template.from_plugin(self.sf, "SPEL", edid="Spell1")
        r = rw.make(t, 0x01000800, "S")
        rw.set_field(r, "EFIT", 0, "f", 100.0, lay)
        self.assertEqual(struct.unpack_from("<f", r.get(b"EFIT"))[0], 100.0)
        rw.set_field(r, "SPIT", 8, "I", 9, lay)
        with self.assertRaises(rw.WriterError) as cm:
            rw.set_field(r, "SPIT", 0, "I", 1, lay)                    # constant in every sample: a flag
        self.assertIn("flag or a version", str(cm.exception))
        rw.set_field(r, "SPIT", 0, "I", 1, lay, force=True)
        with self.assertRaises(rw.WriterError):
            rw.set_field(r, "SPIT", 0, "I", 1)                         # no layout, no force
        with self.assertRaises(rw.WriterError):
            rw.set_field(r, "SPIT", 34, "I", 1, lay, force=True)       # does not fit

    def test_retarget_effect(self):
        r = rw.make(rw.Template.from_plugin(self.sf, "SPEL", edid="Spell2"), 0x01000800, "S")
        rw.retarget_effect(r, 0x01000801)
        self.assertEqual(r.get(b"EFID"), struct.pack("<I", 0x01000801))
        self.assertEqual(r.get(b"MUID"), b"\xAA\xBB\xCC\xDD")
        with self.assertRaises(rw.WriterError):
            rw.retarget_effect(r, 1, index=1)
        with self.assertRaises(rw.WriterError):
            rw.retarget_effect(rw.make(rw.Template.from_plugin(self.sf, "MGEF", edid="Effect1"), 0x01000802, "E"), 1)


class PluginTests(Base):
    def test_written_kit_passes_the_load_check(self):
        eff = rw.make(rw.Template.from_plugin(self.sf, "MGEF", edid="Effect1"), 0x01000801, "FO4SF_RadsEffect")
        sp = rw.retarget_effect(rw.make(rw.Template.from_plugin(self.sf, "SPEL", edid="Spell1"), 0x01000800,
                                         "FO4SF_RadsSpell", full="Rads"), 0x01000801)
        out = os.path.join(self.tmp.name, "FO4SFKit.esm")
        rw.write_plugin(out, ["Starfield.esm"], [sp, eff])
        self.assertTrue(plugin_verify.verify(out).ok)

    def test_a_bad_kit_is_refused_and_removed(self):
        rec = rw.make(rw.Template.from_plugin(self.sf, "MGEF", edid="Effect1"), 0x01000801, "E", drop=["DNAM"])
        out = os.path.join(self.tmp.name, "Bad.esm")
        with self.assertRaises(plugin_verify.PluginVerifyError):
            rw.write_plugin(out, ["Starfield.esm"], [rec])
        self.assertFalse(os.path.exists(out))

    def test_first_master_must_be_starfield(self):
        with self.assertRaises(rw.WriterError):
            rw.write_plugin(os.path.join(self.tmp.name, "X.esm"), ["Other.esm", "Starfield.esm"], [])


if __name__ == "__main__":
    unittest.main()
