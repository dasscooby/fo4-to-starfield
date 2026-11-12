"""FO4SFPipboyMenu's Tab and Esc close (FAL-414): source-level checks that the input vtable override, the log line and
the ini keys stay together (the native build and the game run are the PC's)."""
import pathlib
import re
import unittest

PLUGIN = pathlib.Path(__file__).resolve().parents[1] / "sfse" / "FO4SFPipboyMenu"


class PipboyCancelTest(unittest.TestCase):
    def setUp(self):
        self.src = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
        self.ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="ascii")

    def test_input_vtable_slots_replaced(self):
        self.assertIn("g_inputVtbl.slots[1] = reinterpret_cast<std::uintptr_t>(&MenuShouldHandleEvent)", self.src)
        self.assertIn("g_inputVtbl.slots[8] = reinterpret_cast<std::uintptr_t>(&MenuOnButtonEvent)", self.src)
        self.assertIn("base + 0x10) = reinterpret_cast<std::uintptr_t>(g_inputVtbl.slots.data())", self.src)

    def test_cancel_stops_event_and_closes_by_cancel(self):
        self.assertIn("Status::kStop;", self.src)
        self.assertIn('Close(n, "cancel")', self.src)
        self.assertIn('by={} was_open', self.src)

    def test_ini_cancel_codes_default_to_esc_and_tab_virtual_keys(self):
        codes = dict(re.findall(r"^(CancelCode\d)=(\S+)", self.ini, re.M))
        self.assertEqual(codes, {"CancelCode1": "0x1B", "CancelCode2": "0x09", "CancelCode3": "0", "CancelCode4": "0"})
        for key, default in (("CancelCode1", "0x1B"), ("CancelCode2", "0x09")):
            self.assertIn(f'L"{key}", {default}', self.src)


    def test_one_close_per_press_and_menu_detail_diagnostic(self):
        self.assertIn("g_cancelHeld.exchange(true)", self.src)
        self.assertIn("step=menu_detail", self.src)
        self.assertIn('a_tag == "key"', self.src)

    def test_helpers_are_defined_before_first_use(self):
        # MSVC C3861 at fa610324: LogOpenMenuDetails was called in Snapshot before its definition
        for name in ("LogOpenMenuDetails", "a_eventValueIsRelease"):
            first_call = self.src.index(name + "(")
            definition = re.search(r"^\t(?:void|bool) " + name + r"\(", self.src, re.M).start()
            self.assertEqual(first_call, definition + len("\tvoid "), name)

    def test_flag_sweep_room(self):
        self.assertIn("kMaxFlagSets = 16", self.src)
        self.assertIn("PageFlagSets=0x9,0xB,", self.ini)

    def test_default_flag_set_has_bit4_and_not_pause_or_blank(self):
        self.assertIn('L"PageFlagSets", L"0x19"', self.src)
        self.assertIn("PageFlagSets=0x19\n", self.ini)
        self.assertEqual(0x19 & 0x2, 0)    # bit 1 pauses the game
        self.assertEqual(0x19 & 0x100, 0)  # bit 8 blanks the world
        self.assertTrue(0x19 & 0x10)

    def test_cancel_gate_cleared_on_open_and_close(self):
        self.assertEqual(self.src.count("g_cancelHeld = false;   // FAL-414"), 2)


if __name__ == "__main__":
    unittest.main()
