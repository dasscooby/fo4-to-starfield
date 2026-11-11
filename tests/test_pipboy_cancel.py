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

    def test_ini_cancel_codes_default_to_esc_and_tab(self):
        codes = dict(re.findall(r"^(CancelCode\d)=(\S+)", self.ini, re.M))
        self.assertEqual(codes, {"CancelCode1": "0x01", "CancelCode2": "0x0F", "CancelCode3": "0", "CancelCode4": "0"})
        for key, default in (("CancelCode1", "0x01"), ("CancelCode2", "0x0F")):
            self.assertIn(f'L"{key}", {default}', self.src)


if __name__ == "__main__":
    unittest.main()
