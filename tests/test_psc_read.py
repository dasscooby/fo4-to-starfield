"""psc_read.py: the read-only report over named Papyrus sources. A fake ContentResources.zip; no game."""
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "newgame"))
import psc_read as pr  # noqa: E402

MASTER = """ScriptName MovingPlatformMasterScript extends ObjectReference
Import Game

Group Links
Keyword Property MovingPlatform_TranslationHelperKeyword Auto Const
RefType Property MovingPlatform_FloorMarkerLocationRefType Auto Const mandatory
EndGroup

Sound Property TravelSound Auto
CustomEvent UpwardTravelStopsEvent
int count = 0

Auto State Idle
    Event OnActivate(ObjectReference akActionRef)
        MoveToFloor(1)
    EndEvent
EndState

Int Function MoveToFloor(int aiFloor)
    ObjectReference h = GetLinkedRef(MovingPlatform_TranslationHelperKeyword)
    return aiFloor
EndFunction

Function Reset()
EndFunction
"""


class PscReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.zip = os.path.join(self.tmp.name, "ContentResources.zip")
        self.out = os.path.join(self.tmp.name, "r.txt")
        with zipfile.ZipFile(self.zip, "w") as z:
            z.writestr("Scripts/Source/User/MovingPlatformMasterScript.psc", MASTER)
            z.writestr("Scripts/Source/User/LoadElevatorManagerScript.psc", "ScriptName LoadElevatorManagerScript extends ObjectReference\nMovingPlatformMasterScript m\n")
            z.writestr("Scripts/Source/User/LoadElevatorFloorScript.psc", "ScriptName LoadElevatorFloorScript extends ObjectReference\n; no mention\n")
            z.writestr("Scripts/Source/Other.psc", "x = MovingPlatformMasterScriptFoo\ny = movingplatformmasterscript\n")
            z.writestr("Scripts/Source/Notes.txt", "MovingPlatformMasterScript in a non-psc file is skipped\n")
            z.writestr("Other/Elsewhere/Plain.psc", "MovingPlatformMasterScript\n")

    def run_tool(self, *argv):
        self.assertEqual(pr.main(["--zip", self.zip, "--out", self.out] + list(argv)), 0)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_the_whole_file_is_printed_numbered_and_nothing_is_cut(self):
        text = self.run_tool("--script", "movingplatformmasterscript")           # case-insensitive
        self.assertIn("===== Scripts/Source/User/MovingPlatformMasterScript.psc  (%d lines" % len(MASTER.splitlines()), text)
        for i, ln in enumerate(MASTER.splitlines(), 1):
            self.assertIn("%5d| %s" % (i, ln), text)

    def test_the_outline_has_line_numbers_and_the_declarations_it_knows_and_says_it_is_a_filter(self):
        text = self.run_tool("--script", "MovingPlatformMasterScript")
        out = text.split("----- outline of", 1)[1].split("----- other sources", 1)[0]
        self.assertIn("    1| ScriptName MovingPlatformMasterScript extends ObjectReference", out)
        self.assertIn("    5| Keyword Property MovingPlatform_TranslationHelperKeyword Auto Const", out)
        self.assertIn("    6| RefType Property MovingPlatform_FloorMarkerLocationRefType Auto Const mandatory", out)
        self.assertIn("   10| CustomEvent UpwardTravelStopsEvent", out)
        self.assertIn("   13| Auto State Idle", out)
        self.assertIn("   14|     Event OnActivate(ObjectReference akActionRef)", out)
        self.assertIn("   19| Int Function MoveToFloor(int aiFloor)", out)
        self.assertIn("   24| Function Reset()", out)
        self.assertNotIn("int count = 0", out)                                    # a plain variable is not in the outline (it is in the whole file)
        self.assertNotIn("GetLinkedRef", out)                                     # a call is not either
        self.assertIn("a line filter, not a parse", text)

    def test_other_sources_that_name_it_are_listed_by_whole_word_and_other_files_are_skipped(self):
        text = self.run_tool("--script", "MovingPlatformMasterScript")
        self.assertIn("other sources that name MovingPlatformMasterScript: 2", text)
        self.assertIn("Scripts/Source/User/LoadElevatorManagerScript.psc: line(s) 2", text)
        self.assertIn("Scripts/Source/Other.psc: line(s) 2", text)                # line 1 has it as part of a longer word: not a mention
        self.assertNotIn("Notes.txt", text)
        self.assertNotIn("Plain.psc", text)                                      # outside a 'source' path
        self.assertIn("psc_read: 4 source file(s) read", text)

    def test_match_and_grep_and_a_script_that_is_not_there(self):
        text = self.run_tool("--match", "loadelevator", "--grep", "gettlinkedref", "--grep", "GetLinkedRef", "--script", "NoSuchScript")
        self.assertIn("source names matching 'loadelevator': 2", text)
        self.assertIn("LoadElevatorFloorScript.psc  (2 lines)", text)
        self.assertIn("lines containing 'gettlinkedref': 0", text)
        self.assertIn("MovingPlatformMasterScript.psc:20:     ObjectReference h = GetLinkedRef(", text)
        self.assertIn("===== NoSuchScript: no source of that name in the zip (unread)", text)

    def test_grep_limit_and_only_the_report_is_written(self):
        text = self.run_tool("--grep", "Script", "--grep-limit", "2")
        self.assertIn("(first 2)", text)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), sorted(["ContentResources.zip", "r.txt"]))

    def test_it_needs_something_to_read_and_a_zip(self):
        with self.assertRaises(SystemExit):
            pr.main(["--zip", self.zip, "--out", self.out])
        with self.assertRaises(SystemExit):
            pr.main(["--zip", os.path.join(self.tmp.name, "nope.zip"), "--out", self.out, "--script", "x"])


if __name__ == "__main__":
    unittest.main()
