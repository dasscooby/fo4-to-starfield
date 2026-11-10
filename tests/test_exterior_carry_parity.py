"""Carry parity (FO4-to-Starfield FAL-164, owner playtest rows 26 and 34): loose objects can be carried inside the
converted interiors but not outdoors. The interior writer (dotnet/PluginSpike) turns every manifest item that carries
"movable" into a MoveableStatic (DATA 4); the exterior path (exterior.place -> objects.json -> dotnet/TerrainOverlays)
writes every non-door base as a Static, and a Static never simulates (docs/ai/research-log.md, 2026-10-10). Both start
from the same convert_batch manifest item, so one synthetic fixture feeds both. Offline check, not in-game acceptance."""
import importlib.util
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("make_core64c", root / "scripts" / "terrain" / "make_core64c.py")
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)
from fo4sf import exterior as ex  # noqa: E402

CAN = "SetDressing\\Junk\\Can01.nif"
BOOK = "SetDressing\\Junk\\Book01.nif"


def manifest_item(model, movable=None):
    """One convert_batch manifest item (pipeline.Converter result): a converted loose item with a dynamic body carries
    "movable": {"mass_kg": ...}."""
    item = {"editor_id": "FO4Port_" + model.rsplit("\\", 1)[-1][:-4], "model": "fo4cw\\" + model.lower(),
            "source": "meshes\\" + model}
    if movable is not None:
        item["movable"] = movable
    return item


def ref(fk, model, typ, pos=(70.0, 70.0, 0.0)):
    return {"formkey": fk, "type": typ, "base_editor_id": "E" + fk[:6], "base_formkey": "000001:Fallout4.esm",
            "model": model, "pos": list(pos), "rot": [0.0, 0.0, 0.0], "scale": 1, "disabled": 0, "persistent": False,
            "exterior_cell": [0, 0], "enable_parent": None}


class CarryParityTests(unittest.TestCase):
    def fixture(self):
        manifest = {"items": [manifest_item(CAN, {"mass_kg": 5.0}), manifest_item(BOOK)], "failures": []}
        sel = {"refs": [ref("000A01", CAN, "MiscItem"), ref("000A02", BOOK, "Book")]}
        return manifest, sel

    def test_exterior_base_keeps_the_movable_mass(self):
        """The manifest says the can's mesh has a dynamic 5 kg body; the exterior base the writer reads must say so too,
        or TerrainOverlays cannot tell a pushable item from a prop (the interior writer reads the same key)."""
        manifest, sel = self.fixture()
        bases, placed, skipped = ex.place(sel, manifest, -14, 14)
        self.assertEqual(skipped, [])
        by_edid = {b["edid"]: b for b in bases}
        self.assertEqual(by_edid["FO4CW_Can01"].get("movable"), {"mass_kg": 5.0})
        self.assertNotIn("movable", by_edid["FO4CW_Book01"])      # a model without a dynamic body stays a plain base

    def test_objects_json_bases_pass_movable_on(self):
        """make_core64c writes objects.json "bases" from an explicit key list; "movable" has to be in it."""
        manifest, sel = self.fixture()
        bases, _placed, _skipped = ex.place(sel, manifest, -14, 14)
        # the production list, as source text: it is an inline comprehension in cmd_stage
        text = (root / "scripts" / "terrain" / "make_core64c.py").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if '"bases": [{k: b[k] for k in' in l)
        self.assertIn('"movable"', line)

    def test_both_dotnet_writers_make_movable_bases_moveable_statics(self):
        """C# is not built by the unittest run, so pin the source: the interior writer reads manifest "movable" and adds
        a MoveableStatic; the exterior writer must read the same key from objects.json bases and do the same."""
        interior = (root / "dotnet" / "PluginSpike" / "Program.cs").read_text(encoding="utf-8")
        exterior_cs = (root / "dotnet" / "TerrainOverlays" / "Program.cs").read_text(encoding="utf-8")
        self.assertTrue('TryGetProperty("movable"' in interior and "new MoveableStatic(" in interior)
        self.assertTrue('TryGetProperty("movable"' in exterior_cs, "TerrainOverlays never reads a base's movable")
        self.assertTrue("new MoveableStatic(" in exterior_cs, "TerrainOverlays never writes a MoveableStatic")

    def test_static_body_rule_follows_the_book_decision(self):
        """FAL-171 changed the rule (owner may overrule): convert_list marks a model static_body unless some reference
        of it is MiscItem / Ingestible / Weapon / Book. A Book converts with a dynamic body outdoors as the interior batch
        (which has no such rule) does; cars, cones and the like (MovableStatic, Static) stay static."""
        kept = [{"model": CAN, "type": "MiscItem", "formkey": "000A01"}, {"model": BOOK, "type": "Book", "formkey": "000A02"}]
        entries = {e["model"]: e for e in mk.convert_list(kept)}
        self.assertNotIn("static_body", entries[CAN])
        self.assertNotIn("static_body", entries[BOOK])
        cone = mk.convert_list([{"model": "Props\\Cone.nif", "type": "MovableStatic", "formkey": "000A03"}])
        self.assertTrue(cone[0].get("static_body"))


if __name__ == "__main__":
    unittest.main()
