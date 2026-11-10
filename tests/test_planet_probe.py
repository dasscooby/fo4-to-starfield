"""src/fo4sf/planet/probe.py: the planet probe's layout, terrain, parameters and the raw check of the written plugin
(tests/planet_fixture.py writes it the way dotnet/PlanetProbe lays it out; no game data), and the probe script's ids
and natives against that layout (scripts/planet/FO4SF_PlanetProbeQuest.psc, make_planet_probe.py NATIVES)."""
import os
import re
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "planet"))
import planet_fixture as pf  # noqa: E402
from fo4sf.planet import esm, probe, probe_log, records  # noqa: E402
import make_planet_probe  # noqa: E402

PSC = os.path.join(ROOT, "scripts", "planet", probe.SCRIPT + ".psc")


def params(**kw):
    return probe.params(records.DEFAULT_SYSTEM_ID, records.DEFAULT_PLANET_ID, list(range(9)), **kw)


class LayoutTests(unittest.TestCase):
    def test_ids_are_unique_and_in_order(self):
        ids = [r[1] for r in probe.REFS] + [probe.BLOCK_ID, probe.LOCATION_ID, probe.WORLD_ID, probe.PERSISTENT_CELL_ID]
        ids += [probe.cell_id(x, y) for x, y in probe.cells()] + [probe.QUEST_ID]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sorted(ids), list(range(0x800, probe.NEXT_ID)))
        self.assertEqual(probe.cell_id(0, 0), 0x80F)
        self.assertEqual(probe.cells()[:2], [(-1, -1), (-1, 0)])

    def test_every_reference_stands_on_flat_ground_in_the_spawn_cell(self):
        for tag, _, kind, edid, base, pers, linked, pos, rz in probe.REFS:
            self.assertEqual(probe.cell_of(pos[0], pos[1]), (0, 0), tag)
            self.assertLessEqual(abs(pos[2] - probe.ground_at(pos[0], pos[1])), 1.0, tag)
        self.assertEqual(set(probe.TEST_TAGS), set(probe.MEANING))
        kinds = {(r[5], r[6], r[2]) for r in probe.REFS if r[0].startswith("T")}
        self.assertEqual(len(kinds), 6)                         # six different combinations (T7 repeats T1's)

    def test_heights_hold_the_block_north_of_the_arrival(self):
        h = probe.heights()
        self.assertEqual(h.shape, (384, 384))
        row = int((90 - probe.ORIGIN) / probe.STEP_M)
        col = int((60 - probe.ORIGIN) / probe.STEP_M)
        self.assertEqual(h[row, col], probe.BLOCK_TOP)
        self.assertEqual(h[int((50 - probe.ORIGIN) / probe.STEP_M), col], probe.GROUND)
        self.assertEqual(probe.ground_at(*probe.COC_POS[:2]), probe.GROUND)

    def test_params_shape(self):
        p = params(world_biome=("Starfield.esm", 0x7F88A))
        self.assertEqual(p["masters"], ["Starfield.esm", records.MASTER])
        self.assertEqual(p["world_biome"], "07F88A:Starfield.esm")
        self.assertEqual(p["templates"]["world"], {"key": "02DF8C:Starfield.esm", "edid": "LC172World"})
        self.assertEqual([r["tag"] for r in p["refs"]], ["T1", "T2", "T3", "T4", "T5", "T6", "COC", "T7"])
        self.assertEqual(p["refs"][2]["rot"], [0.0, 0.0, probe.FACE_SOUTH])
        self.assertEqual(p["block"]["fnam"], list(range(9)))
        self.assertIsNone(params()["world_biome"])
        with self.assertRaises(probe.ProbeError):
            probe.params(1, 1, [0] * 8)

    def test_lcpr_rows_read_grid_y_before_x(self):
        data = struct.pack("<IIhhI", 0x02000801, 0x02000809, 5, -2, 0xFFFFFFFF)
        self.assertEqual(probe.lcpr_rows(data), [(0x02000801, 0x02000809, -2, 5, 0xFFFFFFFF)])
        with self.assertRaises(probe.ProbeError):
            probe.lcpr_rows(b"\0" * 15)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, probe.PLUGIN)
        self.prm = params(world_biome=("Starfield.esm", 0x7F88A))

    def problems(self, change=None, prm=None):
        pf.probe_plugin(self.path, prm or self.prm, change)
        return probe.check_plugin(self.path, prm or self.prm)

    def test_the_layout_passes(self):
        problems, summary = self.problems()
        self.assertEqual(problems, [])
        self.assertEqual(summary["location"]["parent"], "01000804")
        self.assertEqual(len(summary["location"]["lcpr"]), 3)
        self.assertEqual({r["tag"]: r["group"] for r in summary["refs"]},
                         {"T1": "persistent", "T2": "persistent", "T3": "temporary", "T4": "persistent",
                          "T5": "temporary", "T6": "persistent", "COC": "temporary", "T7": "persistent"})
        self.assertEqual(summary["quest"]["scripts"], [(probe.SCRIPT, 0)])

    def test_a_reference_in_another_cell_gets_its_grid(self):
        prm = params()
        t2 = next(r for r in prm["refs"] if r["tag"] == "T2")
        t2["pos"], t2["cell"] = [164.0, 50.0, 10.0], [1, 0]
        problems, summary = self.problems(prm=prm)
        self.assertEqual(problems, [])
        self.assertIn(["02000801", "02000809", 1, 0, "FFFFFFFF"], summary["location"]["lcpr"])

        def swap(kind, rec):                                    # X written before Y: the order xEdit refutes
            if kind == "location":
                rows = rec.get(b"LCPR")
                fixed = b"".join(rows[i:i + 8] + rows[i + 10:i + 12] + rows[i + 8:i + 10] + rows[i + 12:i + 16]
                                 for i in range(0, len(rows), 16))
                rec.subs = [(s, fixed if s == b"LCPR" else d) for s, d in rec.subs]
        problems, _ = self.problems(swap, prm)
        self.assertTrue(any(p.startswith("LCPR rows") for p in problems), problems)

    def test_missing_link_flag_or_group_are_found(self):
        def unlink(kind, rec):
            if kind == "ref:T2":
                rec.subs = [s for s in rec.subs if s[0] != b"XLCN"]
        self.assertIn("T2 XLCN None", self.problems(unlink)[0])

        def unflag(kind, rec):
            if kind == "ref:T4":
                rec.flags &= ~esm.PERSISTENT
        self.assertIn("T4 persistent flag 0x0", self.problems(unflag)[0])

        def drop(kind, rec):
            return kind != "ref:T3"
        self.assertTrue(any(p.startswith("T3 ") and p.endswith("missing") for p in self.problems(drop)[0]))

    def test_world_block_quest_mistakes_are_found(self):
        def world(kind, rec):
            if kind == "world":
                rec.subs.append((b"OFST", b"\0" * 8))
                rec.subs = [(s, struct.pack("<i", 0) if s == b"SNAM" else d) for s, d in rec.subs]
        problems = self.problems(world)[0]
        self.assertIn("WRLD keeps OFST", problems)
        self.assertTrue(any(p.startswith("overlay SNAM") for p in problems))

        def block(kind, rec):
            if kind == "block":
                rec.subs = [(s, b"\x00" if s == b"INAM" else d) for s, d in rec.subs]
        self.assertIn("SFBK INAM", self.problems(block)[0])

        def quest(kind, rec):
            if kind == "quest":
                rec.subs = [(s, struct.pack("<HB", 0, 30) if s == b"DNAM" else d) for s, d in rec.subs]
        self.assertIn("QUST is not start game enabled", self.problems(quest)[0])

    def test_wrong_biome_and_parent(self):
        def biome(kind, rec):
            if kind == "world":
                rec.subs = [s for s in rec.subs if not (s[0] == b"BNAM" and s[1] == struct.pack("<I", 0x7F88A))]
        self.assertIn("WRLD biome is not the planet's", self.problems(biome)[0])

        def parent(kind, rec):
            if kind == "location":
                rec.subs = [(s, struct.pack("<I", 0x01000802) if s == b"PNAM" else d) for s, d in rec.subs]
        self.assertTrue(any(p.startswith("LCTN parent") for p in self.problems(parent)[0]))


# what run 1 wrote, pinned: T7 (FAL-192) adds a record and changes none of these
RUN1_REFS = (
    ("T1", 0x800, "REFR", "FO4SF_PP_T1_Plain", 0x3B, True, False, (60.0, 50.0, 10.0), 0.0),
    ("T2", 0x801, "REFR", "FO4SF_PP_T2_Linked", 0x3B, True, True, (64.0, 50.0, 10.0), 0.0),
    ("T3", 0x802, "ACHR", "FO4SF_PP_T3_TempLinkedActor", 0x2B211C, False, True, (60.0, 64.0, 10.0), probe.FACE_SOUTH),
    ("T4", 0x803, "ACHR", "FO4SF_PP_T4_PlainActor", 0x2B211C, True, False, (52.0, 62.0, 10.0), probe.FACE_SOUTH),
    ("T5", 0x804, "REFR", "FO4SF_PP_T5_Temp", 0x3B, False, False, (56.0, 50.0, 10.0), 0.0),
    ("T6", 0x805, "ACHR", "FO4SF_PP_T6_LinkedActor", 0x2B211C, True, True, (68.0, 62.0, 10.0), probe.FACE_SOUTH),
    ("COC", 0x806, "REFR", "", 0x32, False, False, (60.0, 50.0, 11.0), 0.0),
)


class T7Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, probe.PLUGIN)

    def test_layout_of_t7_and_the_run_1_records_unchanged(self):
        self.assertEqual(probe.REFS[:7], RUN1_REFS)
        t7 = probe.REFS[7]
        self.assertEqual(t7, ("T7", 0x815, "REFR", "FO4SF_PP_T7_ExtPersistent", probe.XMARKER, True, False,
                              (72.0, 50.0, probe.GROUND), 0.0))
        self.assertEqual((probe.QUEST_ID, probe.NEXT_ID, probe.WORLD_ID, probe.PERSISTENT_CELL_ID), (0x814, 0x816, 0x809, 0x80A))
        self.assertEqual(probe.SCRIPT_IDS["T7Id"], 0x815)
        self.assertEqual((probe.SCRIPT_IDS["MergeId"], probe.SCRIPT_IDS["LC172CocId"]), (0x800, 0x10238E))
        self.assertEqual(probe.EXTERIOR_PERSISTENT, {"T7"})
        self.assertIn("T7", probe.MEANING)
        self.assertEqual(probe.cell_of(72.0, 50.0), (0, 0))                  # the spawn cell

    def test_params_flag_only_t7(self):
        prm = params()
        self.assertEqual({r["tag"]: r["exterior_persistent"] for r in prm["refs"]},
                         {"T1": False, "T2": False, "T3": False, "T4": False, "T5": False, "T6": False, "COC": False,
                          "T7": True})
        self.assertEqual(prm["next_id"], 0x816)

    def test_t7_is_in_the_spawn_cell_persistent_group_not_the_worlds(self):
        prm = params()
        pf.probe_plugin(self.path, prm)
        problems, summary = probe.check_plugin(self.path, prm)
        self.assertEqual(problems, [])
        t7 = next(r for r in summary["refs"] if r["tag"] == "T7")
        self.assertEqual((t7["group"], t7["flags"], t7["formid"]), ("persistent", "00000400", "02000815"))
        with esm.Plugin(self.path) as p:
            hit = [i for i in probe.world_items(p) if i["rec"].formid == 0x02000815]
        self.assertEqual([(i["group"], i["cell"]) for i in hit], [("persistent", 0x0200080F)])      # not 0x0200080A
        self.assertEqual(probe.cell_id(0, 0), 0x80F)

    def test_t7_in_the_worlds_persistent_cell_is_found(self):
        prm = params()
        t7 = next(r for r in prm["refs"] if r["tag"] == "T7")
        flat = dict(t7, exterior_persistent=False)                          # the writer's mistake: T1's place
        pf.probe_plugin(self.path, dict(prm, refs=[flat if r is t7 else r for r in prm["refs"]]))
        problems, _ = probe.check_plugin(self.path, prm)
        self.assertTrue(any(p.startswith("T7 in persistent group of") for p in problems), problems)

    def test_t7_as_temporary_is_found(self):
        prm = params()
        t7 = next(r for r in prm["refs"] if r["tag"] == "T7")
        temp = dict(t7, persistent=False, exterior_persistent=False)
        pf.probe_plugin(self.path, dict(prm, refs=[temp if r is t7 else r for r in prm["refs"]]))
        problems, _ = probe.check_plugin(self.path, prm)
        self.assertTrue(any(p.startswith("T7 in temporary group") or "T7 persistent flag" in p for p in problems), problems)

    def test_other_records_are_the_same_with_and_without_t7(self):
        prm = params()
        old = dict(prm, refs=[r for r in prm["refs"] if r["tag"] != "T7"])
        pf.probe_plugin(self.path, old)
        _, before = probe.check_plugin(self.path, old)
        pf.probe_plugin(self.path, prm)
        _, after = probe.check_plugin(self.path, prm)
        self.assertEqual([r for r in after["refs"] if r["tag"] != "T7"], before["refs"])     # group, flags, pos, XLCN, subrecords
        for k in ("block", "location", "world", "quest"):
            self.assertEqual(after[k], before[k], k)

    def test_alignment_option_is_a_parameter_and_checked(self):
        self.assertEqual(params()["block"]["inam"], 1)
        prm = probe.params(records.DEFAULT_SYSTEM_ID, records.DEFAULT_PLANET_ID, list(range(9)),
                           alignment=probe.ALIGNMENTS["relative"])
        self.assertEqual((prm["block"]["inam"], prm["block"]["hnam"]), (0, 0))
        pf.probe_plugin(self.path, prm)
        self.assertEqual(probe.check_plugin(self.path, prm)[0], [])
        absolute = params()
        self.assertIn("SFBK INAM", probe.check_plugin(self.path, absolute)[0])      # a relative block, absolute asked
        with self.assertRaises(probe.ProbeError):
            probe.params(1, 1, [0] * 9, alignment=2)


class ScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PSC, encoding="utf-8") as f:
            cls.src = f.read()

    def test_script_ids_are_the_layout(self):
        got = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"^int\s+(\w+Id)\s*=\s*0x([0-9A-Fa-f]+)", self.src, re.M)}
        self.assertEqual(got, probe.SCRIPT_IDS)
        strings = dict(re.findall(r'^string\s+(\w+)\s*=\s*"([^"]*)"', self.src, re.M))
        self.assertEqual(strings, {"LogName": probe.LOG_NAME, "ProbePlugin": probe.PLUGIN,
                                   "PlanetPlugin": records.MASTER, "MergePlugin": make_planet_probe.MERGE_PLUGIN})
        self.assertIn(f'"{probe.LOG_PREFIX} rt="', self.src)
        self.assertRegex(self.src, rf"^Scriptname {probe.SCRIPT} extends Quest", )

    def test_the_chain_line_writes_what_the_reader_reads(self):
        loc = {"probe": "ProbeLoc", "surface": "SurfaceLoc", "planet": "PlanetLoc"}
        for pair in probe_log.ISCHILD:                          # <caller>_ischild_<argument>, the parent first
            for key in pair:
                caller, arg = key.split("_ischild_")
                self.assertIn(f'" {key}=" + {loc[caller]}.IsChild({loc[arg]})', self.src)
        for key in probe_log.LIST_KEYS:
            self.assertIn(f'" {key}="', self.src)
        kw = {"parents": "", "systems": "starSystem", "orbitals": "majorOrbital"}
        for key in probe_log.LIST_KEYS:
            whose, what = key.split("_")
            self.assertIn(f'" {key}=" + IdList({loc[whose]}.GetParentLocations({kw[what]}))', self.src)
        self.assertIn('Keyword starSystem = Game.GetFormFromFile(StarSystemKwId, "Starfield.esm") as Keyword', self.src)
        self.assertIn('Keyword majorOrbital = Game.GetFormFromFile(MajorOrbitalKwId, "Starfield.esm") as Keyword',
                      self.src)
        self.assertEqual({k: probe.SCRIPT_IDS[k] for k in probe.SCRIPT_KEYWORDS},
                         {k: records.KEYWORDS[n] for k, n in probe.SCRIPT_KEYWORDS.items()})
        self.assertIn('Trace(line + " end=true")', self.src)     # so the reader can tell a cut line
        for key in probe_log.CHAIN_V1:                          # version 1's keys are gone from the script
            self.assertNotIn(key, self.src)

    def test_t7_is_the_ninth_entry_and_the_run_1_ones_keep_their_slots(self):
        self.assertEqual(re.findall(r"= new (string|int|string)\[(\d+)\]", self.src), [("string", "9"), ("int", "9"), ("string", "9")])
        rows = re.findall(r'^\s*SetRef\((\d+), "(\w+)", (\w+), ([^)]+)\)', self.src, re.M)
        self.assertEqual(rows, [("0", "T1", "T1Id", "ProbePlugin"), ("1", "T2", "T2Id", "ProbePlugin"),
                                ("2", "T3", "T3Id", "ProbePlugin"), ("3", "T4", "T4Id", "ProbePlugin"),
                                ("4", "T5", "T5Id", "ProbePlugin"), ("5", "T6", "T6Id", "ProbePlugin"),
                                ("6", "MERGE", "MergeId", "MergePlugin"), ("7", "LC172COC", "LC172CocId", '"Starfield.esm"'),
                                ("8", "T7", "T7Id", "ProbePlugin")])

    def test_no_properties(self):
        self.assertNotRegex(self.src, r"(?im)^\s*[\w\[\]]+\s+Property\s")

    def test_every_call_is_the_scripts_own_or_a_checked_native(self):
        body = re.sub(r"\{.*?\}", "", self.src, flags=re.S)
        body = re.sub(r";[^\n]*", "", body)
        body = re.sub(r'"[^"]*"', '""', body)
        own = set(re.findall(r"(?im)^\s*(?:[\w\[\]]+\s+)?(?:Function|Event)\s+(\w+)\s*\(", body))
        calls = set(re.findall(r"(?<![\w.])(?:\w+\.)?(\w+)\s*\(", body)) - own
        calls -= {"if", "elseif", "while", "return", "Function", "Event"}
        natives = {f for fs in make_planet_probe.NATIVES.values() for f in fs}
        self.assertEqual(calls - natives, set())
        self.assertTrue({"OnInit", "OnTimer"} <= own)


if __name__ == "__main__":
    unittest.main()
