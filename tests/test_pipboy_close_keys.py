"""FO4SFPipboyMenu at stages (d) and (e), FAL-404: Tab and Esc close the page, and while it is open the game's
MenuOpenHandler hears no input (the owner PC, 11 Nov: both keys opened the pause menu over the page). The plugin as
text: the close keys are read and checked like the kit's, polled by the key thread like F10 and sent down CLOSE's route;
the hold's three ids are their own set, read and checked like the others, and a failure there turns off the hold alone;
every check comes before the one write, and the write is one guarded byte in two places (hold and give back); the hold
is given back after any hide once no close key has been held for three ticks. Also the ini, the README and the owner's
card. No compiler here: the PC build is the compile check."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
sys.path.insert(0, str(ROOT / "scripts" / "ui"))

import make_pipboy_probe as mpp  # noqa: E402

HOLD_IDS = [("MenuControls.Singleton", 938076), ("MenuControls.RTTI", 864851), ("MenuOpenHandler.RTTI", 864856)]


def function(text, signature):
    """The body of the function whose definition starts with `signature` (to its closing brace at one tab)."""
    start = text.index(signature)
    end = text.index("\n\t}\n", start)
    return text[start:end]


class CloseKeyTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
    ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="ascii")

    def test_the_keys_are_read_and_checked_like_the_kits(self):
        read = function(self.main, "bool ReadCloseKeys(")
        self.assertIn('L"CloseKeys", L"0x09,0x1B"', read)
        self.assertIn("\nCloseKeys=0x09,0x1B\n", self.ini)                      # the shipped ini says the default
        self.assertIn("vk == 0 || vk > 0xFE || vk == g_key || vk == g_snapshotKey || kitKey(vk)", read)
        self.assertIn("g_stage == 5 && std::find(binding.vk.begin(), end, a_vk) != end", read)
        self.assertIn('return Refuse("ini", "close_keys', read)
        self.assertIn('g_holdKeys = ReadNumber(a_ini, L"HoldMenuKeys", 1) != 0;', read)
        self.assertIn("\nHoldMenuKeys=1\n", self.ini)
        self.assertIn('"step=close_keys keys={} hold_menu_keys={}"', read)
        load = self.main[self.main.index("SFSE_PLUGIN_LOAD"):]
        self.assertIn("if (g_stage >= 4 && !ReadCloseKeys(ini)) {", load)
        # after the kit's keys (no close key may be one), before the checks (the hold's ids are read only if wanted)
        self.assertLess(load.index("ReadKitKeys(ini)"), load.index("ReadCloseKeys(ini)"))
        self.assertLess(load.index("ReadCloseKeys(ini)"), load.index("CheckEverything(dir)"))
        kit_defaults = " ".join(re.findall(r'\{ KitMove::k\w+, L"Kit\w+", L"([0-9x,]+)" \}', self.main))
        for vk in ("0x09", "0x1B"):
            self.assertNotIn(vk, kit_defaults)

    def test_a_close_key_takes_closes_route_on_the_key_thread(self):
        thread = function(self.main, "std::uint32_t KeyThread(")
        block = thread[thread.index("if (g_stage >= 4) {"):thread.index("// stage c: the snapshot key")]
        self.assertIn("const auto closeVk = CloseKeyDown();", block)
        self.assertIn("if (closeVk && !closeDown && g_open && GameInFront()) {", block)   # a press, page open, in front
        self.assertIn("g_task->AddTask([n, closeVk]() { Close(n, closeVk); });", block)
        self.assertLess(block.index("Close(n, closeVk)"), block.index("CheckState(n)", block.index("Close(n, closeVk)")))
        self.assertIn("g_task->AddTask([n]() { Close(n); });", block)                       # CLOSE's own, unchanged
        close = function(self.main, "void Close(")
        self.assertIn("void Close(std::uint32_t a_n, std::uint32_t a_vk = 0)", close)
        self.assertIn('a_vk ? std::format("key vk={}", Hex(a_vk)) : "button"', close)
        self.assertIn("if (open) {\n\t\t\tqueue->AddMessage(MenuName(), RE::UI_MESSAGE_TYPE::kHide);", close)
        down = function(self.main, "std::uint32_t CloseKeyDown()")
        self.assertIn("W32_IMPL_GetAsyncKeyState(static_cast<std::int32_t>(g_closeKeys[i])) & 0x8000", down)


class HoldTests(unittest.TestCase):
    main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")

    def test_the_holds_ids_are_their_own_set(self):
        table = self.main[self.main.index("constexpr std::array<Id, kHoldIdCount> kHoldIds"):]
        table = table[:table.index("} };")]
        self.assertEqual([(n, int(i)) for n, i in re.findall(r'\{ "([A-Za-z0-9_.]+)", (\d+), "', table)], HOLD_IDS)
        ids = self.main[self.main.index("constexpr std::array<Id, kIdCount> kIds"):]
        ids = ids[:ids.index("} };")]
        for name, _ in HOLD_IDS:
            self.assertNotIn(name, ids)                                         # not in the set whose failure idles all
        library = function(self.main, "bool ReadAddressLibrary(")
        hold = library[library.index("for (std::size_t i = 0; g_stage >= 4 && g_holdKeys && i < kHoldIds.size(); ++i) {"):]
        self.assertNotIn("return Refuse", hold)                                 # a failure turns off the hold alone
        self.assertIn("g_holdOff = true;", hold)
        self.assertIn("break;", hold)
        self.assertIn('"step=hold_id name={} id={} rva={} source={}"', hold)
        # libxse is asked for an id only after the file has it: zero and out-of-range are ruled out first
        self.assertLess(hold.index('!offset ? "missing"'), hold.index("REL::ID(id.id).offset() != offset"))
        self.assertLess(hold.index('offset >= g_imageSize ? "outside_image"'), hold.index("REL::ID(id.id).offset()"))
        names = function(self.main, "void CheckHoldIds()")
        for tail in ('"MenuControls@@"sv', '"MenuOpenHandler@@"sv'):
            self.assertIn(tail, names)
        self.assertNotIn("return false", names)
        self.assertIn("if (g_stage >= 4) {\n\t\t\tCheckHoldIds();", self.main)

    def test_every_check_before_the_one_write(self):
        target = function(self.main, "std::uintptr_t HoldTarget()")
        order = ["Peek(HoldAddress(kHoldControls), controls)",
                 "type.descriptor != HoldAddress(kHoldControlsRtti) || type.offset != 0",
                 "Peek(controls + kMenuOpenHandlerAt, handler)",
                 "handlerType.descriptor != HoldAddress(kHoldHandlerRtti)",
                 "Peek(controls + kHandlersAt, list) && list.size <= kMaxHandlers",
                 "entry == handler",
                 "!Peek(handler + kHandlingEnabledAt, enabled) || enabled > 1",
                 "g_holdAt = handler + kHandlingEnabledAt;"]
        at = [target.index(s) for s in order]
        self.assertEqual(at, sorted(at))
        self.assertNotIn("Poke(", target)
        for constant, value in (("kHandlersAt", "0x20"), ("kMenuOpenHandlerAt", "0x48"), ("kHandlingEnabledAt", "0x38")):
            self.assertIn(f"constexpr std::size_t   {constant} = {value};", self.main)
        hold = function(self.main, "void Hold(")
        self.assertLess(hold.index("HoldTarget()"), hold.index("Poke(at, 0)"))
        self.assertIn("!Peek(at, was) || was > 1 || !Poke(at, 0)", hold)
        # the one write: a guarded byte, called from Hold and Release only
        poke = function(self.main, "bool Poke(")
        self.assertIn("__try {", poke)
        self.assertIn("*reinterpret_cast<volatile std::uint8_t*>(a_addr) = a_value;", poke)
        self.assertEqual(self.main.count("Poke("), 3)                         # the definition and two calls
        self.assertIn("Poke(g_holdAt, g_holdWas)", function(self.main, "void Release("))
        # a byte is logged as a number, not as a character
        self.assertIn("static_cast<int>(was)", hold)
        self.assertIn("static_cast<int>(g_holdWas)", function(self.main, "void Release("))

    def test_held_from_before_the_show_to_after_any_hide(self):
        toggle = function(self.main, "void Toggle(")
        self.assertLess(toggle.index("Hold(a_n);"), toggle.index("queue->AddMessage("))
        self.assertIn("if (g_stage >= 4 && !open) {\n\t\t\tHold(a_n);", toggle)
        hold = function(self.main, "void Hold(")
        self.assertLess(hold.index("g_hidden = false;"), hold.index("if (!g_holdKeys || g_held) {"))
        # any hide lets it go: ours or the engine's (the message), a destroy, a main-thread read that finds it closed
        process = function(self.main, "RE::UI_MESSAGE_RESULT MenuProcessMessage(")
        self.assertIn("g_hidden = type == RE::UI_MESSAGE_TYPE::kHide;", process)
        self.assertLess(process.index("g_hidden = type"), process.index("g_engineProcessMessage(a_self, a_message)"))
        self.assertIn("g_hidden = true;", function(self.main, "void* MenuDestroy("))
        self.assertIn("if (!open) {\n\t\t\tg_hidden = true;", function(self.main, "void CheckState("))
        self.assertIn("g_open = false;\n\t\t\tg_hidden = true;", function(self.main, "void SendUpdate()"))
        # given back on the main thread, after the hide, once no close key has been held for three ticks
        thread = function(self.main, "std::uint32_t KeyThread(")
        self.assertIn("closeUp = closeVk ? 0u : closeUp + 1;", thread)
        self.assertIn("if (g_held && g_hidden && closeUp >= 3 && !g_releasePending.exchange(true)) {", thread)
        self.assertIn("g_task->AddTask([]() { ReleaseIfClosed(); });", thread)
        release = function(self.main, "void ReleaseIfClosed()")
        self.assertIn("if (g_hidden && ui && !ui->IsMenuOpen(MenuName())) {\n\t\t\tRelease(\"hide\");", release)
        self.assertIn("g_releasePending = false;", release)
        self.assertIn("if (!g_held.exchange(false)) {", function(self.main, "void Release("))


class DocTests(unittest.TestCase):
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    card = (ROOT / "docs" / "spikes" / "pipboy-page-kit-owner-card.md").read_text(encoding="utf-8")

    def test_readme(self):
        section = self.readme[self.readme.index("## Tab and Esc close the page (FAL-404)"):self.readme.index("## Build (PC)")]
        for name, number in HOLD_IDS:
            self.assertIn(f"| {name} | {number} |", section)
        for words in ("`0,1`", "`78,2,11,3,13`", "only `13` (Cursor)", "`+0x38`", "three ticks",
                      "step=close n=<k> by=key vk=<vk> was_open=1 sent=hide", "step=hold n=<k> on=1 was=1",
                      "step=hold on=0 by=hide restored=1 ok=1", "**Not verified until the session:**"):
            self.assertIn(words, section, words)
        passing = self.readme[self.readme.index("### PASS at (e)"):self.readme.index("### What each failure line means")]
        self.assertIn("step=close_keys keys=0x9,0x1b hold_menu_keys=1", passing)  # Hex() prints 0x9, 0x1b
        self.assertIn("*Control:* the Esc after, with the page closed, opens the game's pause menu.", passing)
        for line in ("refuse step=ini close_keys", "refuse step=hold name=<x> id=<n> reason=<r>",
                     "refuse step=hold what=menu_controls", "step=hold_target result=no_menu_controls"):
            self.assertIn(line, self.readme, line)

    def test_owner_cards(self):
        steps = self.card[self.card.index("## The eight steps"):self.card.index("**Report:**")]
        seven = next(r for r in steps.splitlines() if r.startswith("| 7 |"))
        for words in ("**Tab**", "**Esc**", "**F10**", "Esc** once more", "no game menu opens"):
            self.assertIn(words, seven, words)
        self.assertIn("`CloseKeys=0x09,0x1B` and `HoldMenuKeys=1`", self.card)
        line = next(s for s in mpp.KIT_CARD.splitlines() if s.startswith("7. "))
        for words in ("Tab", "Esc", "F10", "no game menu"):
            self.assertIn(words, line, words)


if __name__ == "__main__":
    unittest.main()
