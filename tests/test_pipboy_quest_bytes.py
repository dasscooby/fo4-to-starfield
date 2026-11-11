"""FAL-446: the mission's bytes on F11 at the Pip-Boy kit's stage (e), and the helper that names the current stage's
offset from two dumps (scripts/ui/pipboy_quest_bytes.py). The plugin's side is checked as text (no compiler here: the
PC build is the compile check); the helper on a made-up log in the plugin's format."""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import pipboy_quest_bytes as pqb  # noqa: E402


def function(text, signature):
    start = text.index(signature)
    return text[start:text.index("\n\t}\n", start)]


def dump_lines(n, form, body):
    """The plugin's lines for one dump: body is the 0x300 bytes from +0x38."""
    lines = []
    for i in range(0, len(body), 0x40):
        chunk = body[i:i + 0x40]
        hexes = ",".join(chunk[j:j + 8].hex() for j in range(0, len(chunk), 8))
        lines.append(f"[info] step=kit_quest_bytes n={n} form={form} at=+{0x38 + i:03X} bytes={hexes}\n")
    return lines


class PluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (PLUGIN / "src" / "main.cpp").read_text(encoding="utf-8")
        cls.readme = (PLUGIN / "README.md").read_text(encoding="utf-8")

    def test_the_dump_is_the_quest_body_on_the_snapshot_key(self):
        self.assertIn("kQuestDumpAt = 0x38;", self.main)
        self.assertIn("kQuestDumpEnd = 0x338;", self.main)   # libxse 9d090c4: startEventData at +0x330, 8 bytes
        dump = function(self.main, "void LogKitQuestBytes(")
        self.assertIn('if (!IsType(g_kitQuest, "TESQuest@@", type)) {', dump)   # checked again by its RTTI
        self.assertLess(dump.index("IsType(g_kitQuest"), dump.index("KitBytes(g_kitQuest + at, 0x40)"))
        self.assertIn("for (auto at = kQuestDumpAt; at < kQuestDumpEnd; at += 0x40) {", dump)
        self.assertNotIn("FormById(", dump)                                      # no call into the game
        self.assertNotIn("REL::", dump)
        self.assertIn('"step=kit_quest_bytes n={} form={:08X} at=+{:03X} bytes={}"', dump)
        rows = function(self.main, "std::vector<KitRow> KitQuestRows(")
        self.assertLess(rows.index('if (!IsType(quest, "TESQuest@@", type)) {'), rows.index("g_kitQuest = quest;"))
        self.assertIn("g_kitQuest = 0;", rows)
        self.assertIn('{ "STAGE", "?" }', rows)                                  # until the PC names the offset
        key = function(self.main, "std::uint32_t KeyThread(")
        snap = key[key.index('Snapshot("key", true);'):]
        self.assertLess(snap.index("if (g_stage == 5) {"), snap.index("LogKitQuestBytes();"))
        self.assertLess(self.main.index("\tvoid LogKitQuestBytes("), self.main.index("LogKitQuestBytes();"))
        self.assertRegex(self.main, r"\n\tstd::uintptr_t +g_kitQuest = 0; +// main thread only")
        self.assertLess(self.main.index("g_kitQuest = 0;"), self.main.index("std::vector<KitRow> KitQuestRows("))

    def test_pause_is_a_setting(self):
        """FAL-446: the owner chose both modes; Pause=1 adds bit 1 (0x2, the PC sweep's pausing bit) to every page set."""
        self.assertIn("kPauseFlag = 0x2;", self.main)
        load = self.main[self.main.index('ReadFlagSets(ini, L"PageFlagSets", L"0x19");'):]
        load = load[:load.index("} else {")]
        self.assertIn('pause = ReadNumber(ini, L"Pause", 0) != 0;', load)
        self.assertIn("for (std::size_t i = 0; pause && i < g_flagSetCount; ++i) {", load)
        self.assertIn("g_flagSets[i] |= kPauseFlag;", load)
        self.assertIn("pause={}", self.main)
        ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        self.assertRegex(ini, r"\nPause=0\n")                                    # ships not pausing
        self.assertIn("`Pause=1`", self.readme)

    def test_the_readme_names_the_dump_and_the_helper(self):
        self.assertIn("step=kit_quest_bytes", self.readme)
        self.assertIn("scripts/ui/pipboy_quest_bytes.py", self.readme)


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.before = bytearray(range(256)) * 3                                  # 0x300 bytes
        self.after = bytearray(self.before)
        stage_at = 0x1A4 - 0x38
        self.before[stage_at:stage_at + 2] = (20).to_bytes(2, "little")
        self.after[stage_at:stage_at + 2] = (30).to_bytes(2, "little")
        self.after[0x200 - 0x38] ^= 0xFF                                        # a byte that is not the stage

    def test_the_lines_read_back_as_the_dump(self):
        found = pqb.dumps(dump_lines(4, "07000800", self.before) + ["step=snapshot n=4 tag=key\n"])
        self.assertEqual(list(found), [4])
        form, data = found[4]
        self.assertEqual(form, "07000800")
        self.assertEqual(sorted(data), list(range(0x38, 0x338)))
        self.assertEqual(bytes(data[at] for at in range(0x38, 0x338)), bytes(self.before))

    def test_the_stage_word_is_marked(self):
        found = pqb.dumps(dump_lines(4, "07000800", self.before) + dump_lines(7, "07000800", self.after))
        rows = pqb.changed(found[4][1], found[7][1], (20, 30))
        self.assertEqual([row[0] for row in rows], [0x1A4, 0x200])
        self.assertEqual(rows[0], (0x1A4, 20, 30, True))
        self.assertFalse(rows[1][3])

    def test_an_unreadable_line_is_left_out(self):
        lines = dump_lines(4, "07000800", self.before)
        lines[1] = re.sub(r"bytes=\S+", "bytes=unreadable", lines[1])
        _, data = pqb.dumps(lines)[4]
        self.assertNotIn(0x78, data)
        self.assertNotIn(0x78, pqb.words(data))

    def test_main_on_a_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "FO4SFPipboyMenu.log")
            with open(log, "w", encoding="utf-8") as handle:
                handle.writelines(dump_lines(4, "07000800", self.before) + dump_lines(7, "07000800", self.after))
            self.assertEqual(pqb.main([log, "--stages", "20,30"]), 0)
            self.assertEqual(pqb.main([log, "--before", "5"]), 2)
            with open(log, "w", encoding="utf-8") as handle:
                handle.writelines(dump_lines(4, "07000800", self.before))
            self.assertEqual(pqb.main([log]), 2)


if __name__ == "__main__":
    unittest.main()
