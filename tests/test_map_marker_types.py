"""FO4 map-marker type -> Starfield icon number table (src/fo4sf/map_marker_types.json), synthetic data only.
Checks that every FO4 type of the export is mapped, that the numbers are legal Starfield icon positions, and that the
writers' inputs carry the type while positions, names and tags are unchanged."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from fo4sf import map_markers as mm  # noqa: E402

BOUNDS = (-3200.0, 3200.0)
# xEdit's wbDefinitionsFO4 TNAM enum: 0-80 are vanilla (81-95 are its "Custom" slots)
FO4_VANILLA_TYPES = range(81)


class TypeTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = mm.load_type_table()

    def test_every_export_type_is_mapped_once(self):
        self.assertEqual(sorted(self.table["by_fo4"]), list(FO4_VANILLA_TYPES))

    def test_numbers_are_0_to_93_and_not_0_to_9(self):
        for fid, row in self.table["by_fo4"].items():
            self.assertTrue(10 <= row["sf_type"] <= 93, (fid, row))
            self.assertTrue(row["reason"].strip(), fid)
        self.assertTrue(10 <= self.table["default"] <= 93)

    def test_bad_number_is_refused(self):
        for bad in (5, 94, -1):
            doc = json.loads(Path(mm.MAP_MARKER_TYPES_JSON).read_text(encoding="utf-8"))
            doc["types"][0]["sf_type"] = bad
            with tempfile.TemporaryDirectory() as d:
                tmp = Path(d) / "types.json"
                tmp.write_text(json.dumps(doc), encoding="utf-8")
                with self.assertRaises(ValueError):
                    mm.load_type_table(str(tmp))

    def test_the_issue_examples(self):
        want = {0: 10, 40: 11, 8: 14, 7: 22, 13: 35, 26: 20, 41: 32, 45: 19, 1: 70}
        for fo4, sf in want.items():
            self.assertEqual(mm.starfield_type(fo4), sf, fo4)
        self.assertEqual(mm.starfield_type(None), self.table["default"])
        self.assertEqual(mm.starfield_type(200), self.table["default"])


class TypedEntries(unittest.TestCase):
    DOC = {"plugin": "Fallout4.esm", "world": "Commonwealth", "markers": [
        {"fid": "0001F2A9", "name": "Abernathy Farm", "pos": [-81000.0, 86000.0, 0], "type_id": 26},
        {"fid": "0001F2AA", "name": "Some Cave", "pos": [-70000.0, 80000.0, 0], "type_id": 0},
        {"fid": "0001F2AB", "name": "Vault 81", "pos": [-60000.0, 60000.0, 0], "type_id": 15},
        {"fid": "0001F2AC", "name": "Odd", "pos": [-50000.0, 60000.0, 0], "type_id": 999},
        {"fid": "0001F2AD", "name": "Untyped", "pos": [-40000.0, 60000.0, 0]},
    ]}

    def test_exported_markers_carry_their_icon_and_nothing_else_changes(self):
        rows, _ = mm.load_fo4_markers(self.DOC)
        entries, left = mm.extra_markers(rows, BOUNDS, lambda x, y: 2.0)
        self.assertEqual(left, [])
        self.assertEqual([(e["tag"], e["name"], e["type"]) for e in entries],
                         [("M01F2A9", "Abernathy Farm", 20), ("M01F2AA", "Some Cave", 10),
                          ("M01F2AB", "Vault 81", 86), ("M01F2AC", "Odd", 85), ("M01F2AD", "Untyped", 85)])
        self.assertEqual(set(entries[0]), {"tag", "name", "src", "pos", "cell", "type"})
        self.assertEqual(entries[0]["src"], "01F2A9:Fallout4.esm")
        self.assertAlmostEqual(entries[0]["pos"][0], -81000.0 / 70, places=3)
        self.assertEqual(entries[0]["pos"][2], 2.0)

    def test_the_fixed_four_are_typed_by_tag(self):
        ms = mm.overlay_markers([-989.257, 1146.514, 107.143], BOUNDS, lambda x, y: 0.0)
        self.assertEqual([(m["tag"], m["type"]) for m in ms],
                         [("RedRocket", 86), ("Sanctuary", 35), ("Vault111", 86), ("Concord", 35)])

    def test_counts_per_starfield_number(self):
        rows, _ = mm.load_fo4_markers(self.DOC)
        entries, _ = mm.extra_markers(rows, BOUNDS, lambda x, y: 0.0)
        self.assertEqual(mm.type_counts(entries), {10: 1, 20: 1, 85: 2, 86: 1})
        table = mm.format_type_counts(entries)
        print("\n" + table)                       # the check's printed table
        self.assertIn("            85        2", table)

    def test_the_landing_marker_keeps_its_own_type(self):
        spot = mm.landing_spot(-759.0, 2207.0, BOUNDS, lambda x, y: 0.0, 2.5)
        self.assertNotIn("type", spot["marker"])            # dotnet/MapMarkers writes its fixed type 45


if __name__ == "__main__":
    unittest.main()
