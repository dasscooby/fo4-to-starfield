"""FAL-595: the MAP page's HEADING and GRID rows (step 1 of docs/spikes/pipboy-map-page-plan.md), the player's angle and
cell on F11 at the Pip-Boy kit's stage (e), [Kit] HeadingAt= and GridUnits=, and the helper that names them from two
dumps (scripts/ui/pipboy_map_bytes.py). The plugin's side is checked as text (no compiler here: the PC build is the
compile check); the helper on a made-up log in the plugin's format."""
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_pipboy_kit as kit  # noqa: E402
import pipboy_map_bytes as pmb  # noqa: E402


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n\t}\n", start)]


def map_lines(n, floats, cell=0x2a0001000, world=0x2b0002000, xy=(-1, 0), flags=0x0, worlds=None):
    """The plugin's F11 lines for one press: six floats at +0x80, the cell (xy None: unreadable), then the worldspace
    scan (worlds: {offset: address}; None: no scan logged). world= is the cell's word at kCellWorldAt."""
    raw = struct.pack("<6f", *floats) + bytes(0x40 - 24)
    hexes = ",".join(raw[j:j + 8].hex() for j in range(0, len(raw), 8))
    text = ",".join(f"{f:.4f}" for f in floats)
    grid = "cell_xy=unreadable" if xy is None else f"cell_x={xy[0]} cell_y={xy[1]}"
    return [f"[info] step=kit_map_bytes n={n} at=+080 bytes={hexes} floats={text}\n",
            f"[info] step=kit_map_cell n={n} cell={cell:#x} world={world:#x} flags={flags:#x} data=0x2c0003000 {grid}\n"] + \
        ([] if worlds is None else [f'[info] step=kit_map_world n={n} at=+{at:03X} world={addr:#x} name="X (00000001)"\n'
                                    for at, addr in worlds.items()] +
         [f"[info] step=kit_map_worlds n={n} cell={cell:#x} found={len(worlds)}\n"])


class PluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
        cls.readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
        cls.ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")

    def test_the_offsets_are_libxse_9d090c4s(self):
        self.assertIn("kAngleAt = 0x80;", self.main)                  # OBJ_REFR::angle, before location (+0x0C)
        self.assertIn("kPositionAt = 0x80 + 0x0C;", self.main)
        self.assertIn("kMapDumpBytes = 0x40;", self.main)             # +0x80 to +0xC0: parentCell at +0xB0 inside
        self.assertIn("kCellFlagsAt = 0x40;", self.main)
        self.assertIn("kCellDataAt = 0x58;", self.main)               # TESObjectCELL::cellData, EXTERIOR_DATA*
        self.assertIn("kCellWorldAt = 0x110;", self.main)              # the PC, 12 Nov: "Mars" there outdoors
        self.assertNotIn("kCellInterior", self.main)                  # the PC's indoor press had it clear
        self.assertIn("kCellScanEnd = 0x200;", self.main)

    def test_f11_dumps_the_player_and_its_cell_peek_only(self):
        dump = function(self.main, "void LogKitMapBytes(")
        self.assertIn("KitBytes(player + kAngleAt, kMapDumpBytes)", dump)
        self.assertIn("std::array<float, 6> floats{};", dump)
        self.assertIn('"step=kit_map_bytes n={} at=+{:03X} bytes={} floats={}"', dump)
        self.assertLess(dump.index('IsType(cell, "TESObjectCELL@@", cellType)'), dump.index("cell + kCellDataAt"))
        self.assertIn("Peek(cell + kCellDataAt, data) && data && Peek(data, xy)", dump)
        self.assertIn('"step=kit_map_cell n={} cell={} world={} flags={} data={} {}"', dump)
        scan = dump[dump.index("for (auto at = std::size_t{ 0x38 }; at < kCellScanEnd; at += 8) {"):]
        self.assertLess(scan.index("Followable(word)"), scan.index('IsType(word, "TESWorldSpace@@", worldType)'))
        self.assertIn('"step=kit_map_world n={} at=+{:03X} world={} name=\\"{}\\""', dump)
        self.assertIn('"step=kit_map_worlds n={} cell={} found={}"', dump)
        for call in ("FormById(", "REL::", "LookupByID", "GetActorValue"):
            self.assertNotIn(call, dump)                                # no call into the game
        key = self.main[self.main.index('Snapshot("key", true);'):]
        key = key[:key.index("});")]
        self.assertLess(key.index("LogKitQuestBytes();"), key.index("LogKitMapBytes();"))
        self.assertIn("if (g_stage == 5) {", key)                       # stage (e) only

    def test_heading_is_unknown_until_heading_at_names_its_float(self):
        text = function(self.main, "std::string HeadingText(")
        self.assertIn('Unknown("heading", "reason=no_heading_at (HeadingAt= in [Kit])");', text)
        self.assertLess(text.index("if (!g_kit.headingAt) {"), text.index("Peek("))
        self.assertIn("Peek(Singleton(kPlayerSingleton) + g_kit.headingAt, rad)", text)
        self.assertIn("g_kit.headingTurnsDown ? -rad : rad", text)
        self.assertIn("deg = (deg % 360 + 360) % 360;", text)
        self.assertIn('"step=kit_heading heading_at={}+{:03X} rad={:.4f} deg={}"', text)
        parse = function(self.main, "bool KitHeadingAt(")
        self.assertIn('a_text != "80" && a_text != "84" && a_text != "88"', parse)
        read = function(self.main, "bool ReadKit(") if "bool ReadKit(" in self.main else self.main
        self.assertIn('key == "HeadingAt" && !g_kit.headingAt && KitHeadingAt(value)', read)   # once

    def test_grid_is_unknown_until_grid_units_is_set(self):
        text = function(self.main, "std::string GridText(")
        self.assertIn('Unknown("grid", "reason=no_grid_units (GridUnits= in [Kit])");', text)
        self.assertLess(text.index("if (!g_kit.gridUnits) {"), text.index("ReadPosition(xyz)"))
        self.assertIn("return world;", text)
        self.assertIn('if (world == "NONE (INTERIOR)") {', text)            # where WORLD says so
        self.assertIn("const auto world = PlaceText().second;", text)
        place = function(self.main, "std::pair<std::string, std::string> PlaceText(")
        self.assertIn('return { cellText, "NONE (INTERIOR)" };', place)    # 0 at +0x110 indoors (the PC, 12 Nov)
        self.assertIn("std::floor(xyz[0] / static_cast<double>(g_kit.gridUnits))", text)
        self.assertIn('"step=kit_grid units={} x={} y={}"', text)
        parse = function(self.main, "bool KitGridUnits(")
        self.assertIn("units < kGridUnitsMin || units > kGridUnitsMax", parse)
        self.assertIn("kGridUnitsMin = 1;", self.main)
        self.assertIn("kGridUnitsMax = 65536;", self.main)
        self.assertIn('key == "GridUnits" && !g_kit.gridUnits && KitGridUnits(value)', self.main)

    def test_the_values_and_the_page(self):
        values = self.main[self.main.index("kKitValues{"):]
        values = values[:values.index("};")]
        self.assertEqual(tuple(v.strip(' "\n\t') for v in values[len("kKitValues{"):].split(",")), kit.VALUE_PROVIDERS)
        read = function(self.main, "std::string KitValueRead(")
        self.assertIn('if (a_spec == "heading") {\n\t\t\treturn HeadingText();', read)
        self.assertIn('if (a_spec == "grid") {\n\t\t\treturn GridText();', read)
        pages = {(p["tab"], p["sub"]): p for p in kit.read_kit()["pages"]}
        rows = pages[("MAP", "WORLD")]["rows"]
        self.assertIn(("HEADING", "heading"), rows)
        self.assertIn(("GRID", "grid"), rows)

    def test_ships_heading_at_88_and_no_grid_units(self):
        self.assertRegex(self.ini, r"\nHeadingAt=88\n")                   # verified on the PC, 12 Nov (e2e551c8)
        self.assertRegex(self.ini, r"\nGridUnits=100\n")                  # verified on the PC, 12 Nov (4d1e7641)
        self.assertIn("; [Kit] HeadingAt=[-]<80, 84 or 88>", self.ini)
        self.assertIn("[Kit] GridUnits=<decimal>", self.ini)
        kit_now = kit.read_kit()
        self.assertEqual(kit_now["heading_at"], {"at": 0x88, "down": False})
        self.assertEqual(kit_now["grid_units"], 100)
        for text in ("`heading`", "`grid`", "HeadingAt=", "GridUnits=", "step=kit_map_bytes", "step=kit_map_cell",
                     "scripts/ui/pipboy_map_bytes.py"):
            self.assertIn(text, self.readme, text)


class KitTests(unittest.TestCase):
    PAGE = "[Page MAP/WORLD]\nRow=HEADING|heading\nRow=GRID|grid\n"

    def test_heading_at(self):
        for value, want in (("80", (0x80, False)), ("84", (0x84, False)), ("88", (0x88, False)), ("-88", (0x88, True))):
            got = kit.parse_kit(f"[Kit]\nHeadingAt={value}\n" + self.PAGE)["heading_at"]
            self.assertEqual((got["at"], got["down"]), want, value)
        for value in ("", "8C", "0x88", "--88", "+88", "7C", "88 ", "8"):
            with self.assertRaises(kit.KitError, msg=value):
                kit.check_heading_at(value, 1)
        with self.assertRaises(kit.KitError):
            kit.parse_kit("[Kit]\nHeadingAt=88\nHeadingAt=88\n" + self.PAGE)   # once

    def test_grid_units(self):
        for value in ("1", "100", "4096", "65536"):
            self.assertEqual(kit.parse_kit(f"[Kit]\nGridUnits={value}\n" + self.PAGE)["grid_units"], int(value))
        for value in ("", "0", "65537", "4096.0", "-4096", "0x1000", "100000"):
            with self.assertRaises(kit.KitError, msg=value):
                kit.check_grid_units(value, 1)
        with self.assertRaises(kit.KitError):
            kit.parse_kit("[Kit]\nGridUnits=4096\nGridUnits=4096\n" + self.PAGE)


class HelperTests(unittest.TestCase):
    def run_log(self, lines, *args):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "FO4SFPipboyMenu.log"
            log.write_text("".join(lines), encoding="utf-8")
            out = []
            real = print
            try:
                import builtins
                builtins.print = lambda *a, **k: out.append(" ".join(str(x) for x in a))
                code = pmb.main([str(log), *args])
            finally:
                builtins.print = real
        return code, out

    def test_a_turn_to_the_right_names_the_float(self):
        before = [0.0, 0.0, 0.30, -989.25, 1146.5, 107.1]
        after = [0.0, 0.0, 0.30 + math.pi / 2, -990.0, 1147.0, 107.1]
        code, out = self.run_log(map_lines(4, before) + map_lines(5, after))
        self.assertEqual(code, 0)
        self.assertEqual(out[-1], "HeadingAt=88")
        self.assertIn("heading?", out[2])

    def test_a_float_that_falls_gets_a_minus(self):
        before = [0.0, 0.0, 0.2, 0.0, 0.0, 0.0]
        after = [0.0, 0.0, 0.2 - 1.5, 0.0, 0.0, 0.0]
        self.assertEqual(self.run_log(map_lines(1, before) + map_lines(2, after))[1][-1], "HeadingAt=-88")

    def test_the_turn_across_pi_wraps(self):
        rows, _ = pmb.heading([0, 0, 3.0, 0, 0, 0], [0, 0, 3.0 + 1.6 - 2 * math.pi, 0, 0, 0])
        self.assertTrue(rows[2][4])
        self.assertAlmostEqual(rows[2][3], math.degrees(1.6), places=3)
        self.assertEqual(pmb.heading_line(rows, 0.0), "HeadingAt=88")

    def test_no_line_when_two_floats_move_or_the_player_walks(self):
        rows, moved = pmb.heading([0.0, 0.5, 0.2, 0, 0, 0], [0.0, 0.5 + 0.2, 0.2 + 1.5, 0, 0, 0])
        self.assertIsNone(pmb.heading_line(rows, moved))
        rows, moved = pmb.heading([0, 0, 0.2, 0, 0, 0], [0, 0, 1.7, 500.0, 0, 0])
        self.assertIsNone(pmb.heading_line(rows, moved))
        code, out = self.run_log(map_lines(1, [0, 0, 0.2, 0, 0, 0]) + map_lines(2, [0, 0, 0.25, 0, 0, 0]))
        self.assertEqual(code, 1)
        self.assertTrue(out[-1].startswith("no line"))

    def test_grid_units_over_two_cells(self):
        # the PC's presses (12 Nov): -2189.06 in cell -22, 10252.89 in 102; world=0x0 outdoors does not matter
        lines = map_lines(1, [0, 0, 0, -2189.06, 1146.0, 107.0], cell=0x2a0001000, xy=(-22, 11)) + \
            map_lines(2, [0, 0, 0, 10252.89, 1150.0, 107.0], cell=0x2a0005000, xy=(102, 11))
        code, out = self.run_log(lines, "--grid")
        self.assertEqual(code, 0)
        self.assertEqual(out[-1], "GridUnits=100")
        self.assertIn("match", out[0])
        self.assertEqual(self.run_log(lines, "--grid", "--units", "4096")[0], 1)

    def test_grid_needs_two_cells_and_matching_grids(self):
        one = map_lines(1, [0, 0, 0, -89.0, 46.0, 107.0], xy=(-1, 0)) + map_lines(2, [0, 0, 0, -50.0, 46.0, 107.0], xy=(-1, 0))
        code, out = self.run_log(one, "--grid")
        self.assertEqual((code, out[-1]), (1, "one cell only: walk across a border and press F11 again"))
        wrong = map_lines(1, [0, 0, 0, -89.0, 46.0, 107.0], xy=(-1, 0)) + \
            map_lines(2, [0, 0, 0, 10.0, 50.0, 107.0], cell=0x2a0005000, xy=(-1, 0))
        code, out = self.run_log(wrong, "--grid")
        self.assertEqual(code, 1)
        self.assertIn("DIFFERS", out[1])

    def test_grid_without_the_cells_grid_prints_no_line(self):
        lines = map_lines(1, [0, 0, 0, -89.0, 46.0, 107.0], xy=None) + \
            map_lines(2, [0, 0, 0, 10.0, 50.0, 107.0], cell=0x2a0005000, xy=None)
        code, out = self.run_log(lines, "--grid")
        self.assertEqual(code, 1)
        self.assertIn("weaker: no line printed", out[-1])

    def test_interiors_are_left_out_by_their_world(self):
        lines = map_lines(1, [0, 0, 0, 10.0, 10.0, 0], world=0x0)
        self.assertEqual(pmb.grid(pmb.dumps(lines), 100), [])
        lines = map_lines(1, [0, 0, 0, 10.0, 10.0, 0], world=0x0, worlds={0x110: 0x2d0001000})   # the scan wins
        self.assertEqual(len(pmb.grid(pmb.dumps(lines), 100)), 1)
        self.assertEqual(len(pmb.grid(pmb.dumps(map_lines(1, [0, 0, 0, 10.0, 10.0, 0])), 100)), 1)

    def test_world_is_the_offset_found_outdoors_and_not_indoors(self):
        lines = map_lines(1, [0] * 6, worlds={0x110: 0x2d0001000, 0x1A0: 0x2d0001000}) + \
            map_lines(2, [0] * 6, cell=0x2a0005000, worlds={0x110: 0x2d0001000}) + \
            map_lines(3, [0] * 6, cell=0x2a0009000, world=0x0, worlds={})
        code, out = self.run_log(lines, "--world")
        self.assertEqual(code, 0)
        self.assertEqual(out[-1], "the worldspace is at +110 (every outdoor press, no indoor one)")
        self.assertIn("n=3 indoors none", out)
        code, out = self.run_log(lines[:-2], "--world")               # no indoor press
        self.assertEqual(code, 1)
        self.assertEqual(out[-1], "no single place: press F11 outdoors in two cells and once indoors")
        both = map_lines(1, [0] * 6, worlds={0x110: 1, 0x1A0: 1}) + map_lines(2, [0] * 6, worlds={0x110: 1, 0x1A0: 1}) + \
            map_lines(3, [0] * 6, world=0x0, worlds={})
        self.assertEqual(self.run_log(both, "--world")[1][-1], "no single place: +110, +1A0 in every outdoor press")


    def test_the_pcs_session_at_4d1e7641(self):
        """The PC, 12 Nov: three outdoor presses in two cells (world= at the old +0x118 read 0x0, the scan found Mars
        at +0x110), one indoor press with kInterior clear and found=0. --world named no place and --grid counted the
        indoor press; both leave it out now."""
        mars = {0x110: 0x2d0001000}
        lines = map_lines(1, [0, 0, 0, 230.0, -1553.29, 5.0], cell=0x2a0001000, world=0x0, xy=(2, -16), worlds=mars) + \
            map_lines(2, [0, 0, 0, 240.0, -1553.29, 5.0], cell=0x2a0001000, world=0x0, xy=(2, -16), worlds=mars) + \
            map_lines(3, [0, 0, 0, 230.0, -1493.29, 5.0], cell=0x2a0005000, world=0x0, xy=(2, -15), worlds=mars) + \
            map_lines(4, [0, 0, 0, 2.0, -7.0, -1.0], cell=0x2a0009000, world=0x0, xy=(0, 0), worlds={})
        code, out = self.run_log(lines, "--world")
        self.assertEqual((code, out[-1]), (0, "the worldspace is at +110 (every outdoor press, no indoor one)"))
        code, out = self.run_log(lines, "--grid")
        self.assertEqual((code, out[-1]), (0, "GridUnits=100"))
        self.assertFalse(any("n=4" in line for line in out))


if __name__ == "__main__":
    unittest.main()
