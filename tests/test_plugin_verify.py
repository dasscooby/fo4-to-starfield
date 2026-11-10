"""src/fo4sf/plugin_verify.py: the offline plugin-load check, on synthetic plugins (no game data, no dotnet)."""
import json
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
import planet_fixture as pf  # noqa: E402
from fo4sf import plugin_verify as pv  # noqa: E402
from fo4sf.planet import esm, probe, records  # noqa: E402
import verify_plugin  # noqa: E402


def z(t):
    return t.encode("ascii") + b"\0"


def spel(fid, drop=()):
    subs = [(b"EDID", z("T_Spell")), (b"OBND", b"\0" * 12), (b"ODTY", b"\0" * 4), (b"ETYP", struct.pack("<I", 1)),
            (b"DESC", struct.pack("<I", 0)), (b"SPIT", b"\0" * 36)]
    return esm.Record(b"SPEL", fid, [(s, d) for s, d in subs if s.decode() not in drop])


def mgef(fid, drop=()):
    subs = [(b"EDID", z("T_Effect")), (b"DATA", b"\0" * 8), (b"DNAM", b"\0" * 4)]
    return esm.Record(b"MGEF", fid, [(s, d) for s, d in subs if s.decode() not in drop])


def build(path, masters, recs, flags=esm.ESM):
    w = esm.PluginWriter(masters, flags)
    for r in recs:
        w.add(r)
    w.write(path)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def p(self, name):
        return os.path.join(self.tmp.name, name)

    def problems(self, name, masters, recs, **kw):
        build(self.p(name), masters, recs)
        return pv.verify(self.p(name), **kw)


class RecordTests(Base):
    def test_a_complete_spell_and_effect_pass(self):
        r = self.problems("A.esp", ["Starfield.esm"], [spel(0x01000800), mgef(0x01000801)])
        self.assertEqual(r.problems, [])
        self.assertTrue(r.ok)

    def test_the_cast_crash_shapes_are_refused(self):
        r = self.problems("A.esp", ["Starfield.esm"], [spel(0x01000800, drop=("ETYP", "SPIT")),
                                                       mgef(0x01000801, drop=("DNAM",))])
        text = "\n".join(r.problems)
        self.assertIn("SPEL 01000800 T_Spell: missing ETYP, SPIT", text)
        self.assertIn("MGEF 01000801 T_Effect: missing DNAM", text)

    def test_an_override_is_not_held_to_the_new_record_rule(self):
        r = self.problems("A.esp", ["Starfield.esm"], [esm.Record(b"SPEL", 0x00001234, [(b"EDID", z("Vanilla"))])])
        self.assertEqual(r.problems, [])

    def test_form_id_rules(self):
        r = self.problems("A.esp", ["Starfield.esm"], [mgef(0x01000801), mgef(0x01000801), mgef(0x01000010),
                                                       mgef(0x05000801)])
        text = "\n".join(r.problems)
        self.assertIn("own form id 01000801 used by two records", text)
        self.assertIn("below 0x800", text)
        self.assertIn("master index 5", text)

    def test_reference_rules(self):
        own_missing = pf.placed(b"REFR", 0x01000900, 0x01000999, (0, 0, 0))     # base is an own record not in the file
        beyond = pf.placed(b"REFR", 0x01000901, 0x07000001, (0, 0, 0))
        ok = pf.placed(b"REFR", 0x01000902, 0x00001234, (0, 0, 0))
        r = self.problems("A.esp", ["Starfield.esm"], [own_missing, beyond, ok])
        text = "\n".join(r.problems)
        self.assertIn("NAME 01000999 names a record of this plugin that is not in it", text)
        self.assertIn("NAME 07000001 has master index 7", text)
        self.assertNotIn("01000902", text)

    def test_a_keyword_array_is_checked(self):
        rec = esm.Record(b"MGEF", 0x01000801, [(b"EDID", z("K")), (b"DATA", b"\0" * 8), (b"DNAM", b"\0" * 4),
                                              (b"KWDA", struct.pack("<2I", 0x00061990, 0x09000001))])
        r = self.problems("A.esp", ["Starfield.esm"], [rec])
        self.assertTrue(any("KWDA 09000001" in t for t in r.problems), r.problems)

    def test_unproven_fields_only_warn(self):
        quest = esm.Record(b"QUST", 0x01000800, [(b"EDID", z("Q")), (b"DNAM", b"\0" * 12)])
        r = self.problems("A.esp", ["Starfield.esm"], [quest])
        self.assertEqual(r.problems, [])
        self.assertTrue(any("QUST" in w and "NEXT" in w for w in r.warnings), r.warnings)


class MasterTests(Base):
    def test_master_rules(self):
        cases = {
            "twice": (["Starfield.esm", "Starfield.esm"], "listed twice"),
            "self": (["Starfield.esm", "M.esp"], "lists itself"),
            "blueprint": (["Starfield.esm", "BlueprintShips-Starfield.esm"], "blueprint plugins load last"),
            "first": (["SFBGS003.esm", "Starfield.esm"], "not the first"),
            "unknown": (["Starfield.esm", "Nobody.esm"], "Nobody.esm is not a game master"),
        }
        for name, (masters, want) in cases.items():
            with self.subTest(name):
                r = self.problems("M.esp", masters, [mgef(len(masters) << 24 | 0x800)], known=["SFBGS003.esm"])
                self.assertTrue(any(want in t for t in r.problems), r.problems)

    def test_kit_load_order(self):
        build(self.p("A.esm"), ["Starfield.esm"], [mgef(0x01000800)])
        build(self.p("B.esm"), ["Starfield.esm", "A.esm"], [mgef(0x02000800)])
        ok = pv.verify_kit([self.p("A.esm"), self.p("B.esm")])
        self.assertEqual([r.problems for r in ok], [[], []])
        late = pv.verify_kit([self.p("B.esm"), self.p("A.esm")])        # B needs A, but loads first
        self.assertTrue(any("loads after this plugin" in t for t in late[0].problems), late[0].problems)
        with self.assertRaises(pv.PluginVerifyError):
            pv.assert_loadable([self.p("B.esm"), self.p("A.esm")])
        self.assertEqual(len(pv.assert_loadable([self.p("A.esm"), self.p("B.esm")])), 2)

    def test_master_list_order_must_follow_the_load_order(self):
        build(self.p("A.esm"), ["Starfield.esm"], [mgef(0x01000800)])
        build(self.p("B.esm"), ["Starfield.esm"], [mgef(0x01000800)])
        build(self.p("C.esm"), ["Starfield.esm", "B.esm", "A.esm"], [mgef(0x03000800)])
        r = pv.verify_kit([self.p("A.esm"), self.p("B.esm"), self.p("C.esm")])
        self.assertTrue(any("different order" in t for t in r[2].problems), r[2].problems)

    def test_not_a_plugin_and_truncation(self):
        with open(self.p("X.esp"), "wb") as f:
            f.write(b"NOPE" + b"\0" * 40)
        self.assertFalse(pv.verify(self.p("X.esp")).ok)
        build(self.p("T.esp"), ["Starfield.esm"], [mgef(0x01000800)])
        with open(self.p("T.esp"), "rb") as f:
            data = f.read()
        with open(self.p("T.esp"), "wb") as f:
            f.write(data[:-10])
        self.assertFalse(pv.verify(self.p("T.esp")).ok)


class GroupTests(Base):
    def world(self, persistent_flag, temporary_flag):
        world = esm.Record(b"WRLD", 0x01000800, [(b"EDID", z("W"))])
        pcell = pf.cell(0x01000801)
        ref_p = pf.placed(b"REFR", 0x01000802, 0x00001234, (0, 0, 0), persistent=persistent_flag)
        ref_t = pf.placed(b"REFR", 0x01000804, 0x00001234, (0, 0, 0), persistent=temporary_flag)
        cell = pf.cell(0x01000803, grid=(0, 0))
        w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
        data = w.to_bytes() + esm.group_bytes("WRLD", pf.world_group(world, pcell, [ref_p], [(cell, [ref_t])]))
        with open(self.p("W.esm"), "wb") as f:
            f.write(data)
        return pv.verify(self.p("W.esm"))

    def test_persistence_flags_follow_the_group(self):
        self.assertEqual(self.world(True, False).problems, [])
        bad = self.world(False, True)
        text = "\n".join(bad.problems)
        self.assertIn("persistent group without flag 0x400", text)
        self.assertIn("temporary group with flag 0x400", text)

    def test_a_children_group_without_its_record_is_a_warning(self):
        world = esm.Record(b"WRLD", 0x01000800, [(b"EDID", z("W"))])
        w = esm.PluginWriter(["Starfield.esm"], esm.ESM)
        ghost = pf.cell(0x01000899)
        group = esm.group_bytes(struct.pack("<I", 0x01000800), esm.group_bytes(struct.pack("<I", 0x01000899), b"", 6), 1)
        with open(self.p("G.esm"), "wb") as f:
            f.write(w.to_bytes() + esm.group_bytes("WRLD", world.to_bytes() + group))
        r = pv.verify(self.p("G.esm"))
        self.assertEqual(r.problems, [])
        self.assertTrue(any("CELL children group 01000899" in t for t in r.warnings), r.warnings)
        del ghost


class WritersTests(Base):
    def test_the_planet_probe_plugin_has_nothing_found(self):
        prm = probe.params(records.DEFAULT_SYSTEM_ID, records.DEFAULT_PLANET_ID, list(range(9)),
                           world_biome=("Starfield.esm", 0x7F88A))
        build(self.p("FO4SFPlanet.esm"), ["Starfield.esm"], [mgef(0x01000800)])
        pf.probe_plugin(self.p("FO4SFPlanetProbe.esm"), prm)
        reports = pv.assert_loadable([self.p("FO4SFPlanet.esm"), self.p("FO4SFPlanetProbe.esm")])
        self.assertTrue(all(r.ok for r in reports))


class SampleTests(unittest.TestCase):
    def test_required_fields_are_in_every_sampled_vanilla_record(self):
        path = os.path.join(ROOT, "docs", "measurements", "sf_esm.json")
        if not os.path.exists(path):
            self.skipTest("docs/measurements/sf_esm.json not present")
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
        for table in (pv.REQUIRED, pv.SAMPLED_ONLY):
            for sig, subs in table.items():
                n = d["sampled"][sig]
                for sub in subs:
                    self.assertEqual(d["subrecord_sigs"][sig].get(sub), n, f"{sig} {sub}")
        for sig in pv.REQUIRED:
            self.assertGreaterEqual(d["sampled"][sig], 75, sig)


class CliTests(Base):
    def test_exit_codes(self):
        build(self.p("A.esp"), ["Starfield.esm"], [spel(0x01000800), mgef(0x01000801)])
        build(self.p("B.esp"), ["Starfield.esm"], [mgef(0x01000800, drop=("DNAM",))])
        out = os.devnull
        with open(out, "w") as sink:
            old, sys.stdout = sys.stdout, sink
            try:
                self.assertEqual(verify_plugin.main([self.p("A.esp")]), 0)
                self.assertEqual(verify_plugin.main([self.p("B.esp"), "--json"]), 1)
            finally:
                sys.stdout = old


if __name__ == "__main__":
    unittest.main()
