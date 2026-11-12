"""FAL-446: the mission's bytes on F11 at the Pip-Boy kit's stage (e), and the helper that names the current stage's
offset from two dumps (scripts/ui/pipboy_quest_bytes.py); FAL-527: [Kit] MissionStageAt=, the quest page's STAGE;
FAL-571: the blocks behind the mission's pointers on F11 and [Kit] MissionObjective=, its objectives. The plugin's side
is checked as text (no compiler here: the PC build is the compile check); the helper on a made-up log in the plugin's
format."""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "sfse" / "FO4SFPipboyMenu"
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_pipboy_kit as kit  # noqa: E402
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


def obj_lines(n, form, blocks, followed=40):
    """The plugin's FAL-571 lines for one F11 press: blocks is {path: (address, 0x40 bytes)}."""
    lines = [f"[info] step=kit_quest_obj n={n} form={form} path={path} at={at:#x} bytes="
             + ",".join(data[j:j + 8].hex() for j in range(0, len(data), 8)) + "\n" for path, (at, data) in blocks.items()]
    return lines + [f"[info] step=kit_quest_objs n={n} form={form} followed={followed} owned={len(blocks)}\n"]


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
        self.assertIn('{ "STAGE", stageText }', rows)                             # ? until MissionStageAt= names it
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

    def test_pause_has_its_own_trial_card(self):
        """FAL-565: Pause=1 becomes the default only after its own run; the card names the ini line and the log's lines."""
        card = (ROOT / "docs" / "spikes" / "pipboy-pause-trial-card.md").read_text(encoding="utf-8")
        self.assertIn("docs/spikes/pipboy-pause-trial-card.md", self.readme)
        self.assertIn(f"flag_sets={0x19 | 0x2:#x} pause=1", card)    # the shipped PageFlagSets plus the pause bit
        self.assertIn("flag_sets=0x1b pause=1", self.readme)
        for line in ("tag=key paused=1", "tag=main_after_close paused=0", "tag=key paused=0", "-replace '^Pause=0','Pause=1'"):
            self.assertIn(line, card)
        self.assertIn("pause={}", self.main)
        self.assertIn("tag={} paused={}", self.main)

    def test_the_stage_reads_the_offset_mission_stage_at_names(self):
        """FAL-527: the u16 at MissionStageAt=, read with Peek only, ? and one page_unknown line without it."""
        self.assertIn("kQuestStageLast = kQuestDumpEnd - 2;", self.main)
        self.assertIn("std::size_t                                    missionStageAt = 0;", self.main)
        check = function(self.main, "bool KitStageAt(")
        for part in ("a_text.size() > 3", "std::isxdigit", "at < kQuestDumpAt || at > kQuestStageLast || at % 2 != 0",
                     "g_kit.missionStageAt = at;"):
            self.assertIn(part, check, part)
        self.assertLess(check.index("return false;"), check.index("g_kit.missionStageAt = at;"))
        read = function(self.main, "bool ReadKit(")
        self.assertIn('key == "MissionStageAt" && !g_kit.missionStageAt && KitStageAt(value)', read)   # once
        rows = function(self.main, "std::vector<KitRow> KitQuestRows(")
        stage = rows[rows.index("static int    loggedStage = -1;"):]
        self.assertIn('std::string   stageText = "?";', stage)
        self.assertIn('Unknown("quest_stage", "reason=no_stage_at (MissionStageAt= in [Kit])");', stage)
        self.assertIn("Peek(quest + g_kit.missionStageAt, stage)", stage)
        self.assertIn("stageText = std::to_string(stage);", stage)
        self.assertIn('"step=kit_quest_stage form={:08X} stage_at=+{:03X} stage={}"', stage)
        self.assertLess(stage.index("if (loggedStage != stage) {"), stage.index("step=kit_quest_stage"))
        self.assertNotIn("FormById(", stage)
        self.assertNotIn("REL::", stage)
        ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        self.assertNotRegex(ini, r"\nMissionStageAt=")                            # ships without it: STAGE ?
        self.assertIn("; [Kit] MissionStageAt=<hex offset>", ini)
        self.assertIn("MissionStageAt=", self.readme)
        self.assertIn("step=kit_quest_stage", self.readme)

    def test_setstage_takes_the_form_id(self):
        """FAL-527, the PC's run at 10409137: the console refuses the mission's editor ID in setstage; the docs say form id."""
        card = (ROOT / "docs" / "spikes" / "pipboy-page-kit-owner-card.md").read_text(encoding="utf-8")
        self.assertIn("`setstage 07000800 20`", self.readme)
        self.assertIn("`setstage <id> <n>`", card)
        self.assertIn("form id", pqb.__doc__)
        for text in (self.readme, card, pqb.__doc__):
            self.assertIn("load index", text)
        for text in (self.readme, card, pqb.__doc__):
            self.assertNotIn("setstage FO4SF_Min00", text)

    def test_the_wider_dump_follows_pointers_that_point_back(self):
        """FAL-571: on F11, after the quest's bytes, each followable word one hop and one more, owned blocks logged."""
        self.assertIn("kQuestPointerLast = kQuestDumpEnd - 8;", self.main)
        self.assertIn("kObjectiveBlock = 0x40;", self.main)
        follow = function(self.main, "bool Followable(")
        for part in ("a_addr % 8 != 0", "InImage(a_addr, 1)", "REX::W32::VirtualQuery(", "info.state != REX::W32::MEM_COMMIT",
                     "constexpr std::uint32_t guard = 0x100;", "(info.protect & guard) == 0",
                     "a_addr + kObjectiveBlock <= end"):
            self.assertIn(part, follow, part)
        log = function(self.main, "void LogKitQuestObjectives(")
        self.assertIn("std::set<std::uintptr_t> seen{ quest };", log)                  # each block once, never the quest
        self.assertLess(log.index("Followable(to)"), log.index("Peek(to, words.data(), kObjectiveBlock)"))
        self.assertIn("std::ranges::find(words, quest) != words.end()", log)          # it points back: logged
        self.assertIn('"step=kit_quest_obj n={} form={:08X} path={} at={} bytes={}"', log)
        self.assertIn('"step=kit_quest_objs n={} form={:08X} followed={} owned={}"', log)
        self.assertIn("for (auto at = kQuestDumpAt; at <= kQuestPointerLast; at += 8) {", log)
        self.assertIn("for (const auto& block : hop1) {", log)                        # two hops, no third
        self.assertIn("nullptr);", log)
        for text in (follow, log):
            self.assertNotIn("FormById(", text)
            self.assertNotIn("REL::", text)
        dump = function(self.main, "void LogKitQuestBytes(")
        self.assertLess(dump.index("step=kit_quest_bytes n={} form="), dump.index("LogKitQuestObjectives(n, formId);"))
        self.assertLess(self.main.index("\tvoid LogKitQuestObjectives("), self.main.index("\tvoid LogKitQuestBytes("))

    def test_the_objectives_read_the_paths_mission_objective_names(self):
        """FAL-571: each MissionObjective= read with Peek only along its path; one OBJECTIVES ? row without any."""
        self.assertIn("kKitObjectives = 8;", self.main)
        self.assertIn("std::vector<KitObjective>                      objectives;", self.main)
        check = function(self.main, "bool KitObjectiveLine(")
        for part in ("g_kit.objectives.size() == kKitObjectives", "number.size() > 5", "value > 0xFFFF",
                     "a_o.index == index", "part.size() > 3", "objective.path.size() == 3", "path.size() < 2",
                     "path.front() < kQuestDumpAt || path.front() > kQuestPointerLast || path.front() % 8 != 0",
                     "path[1] > kObjectiveBlock - 8 || path[1] % 8 != 0", "path.back() >= kObjectiveBlock",
                     "g_kit.objectives.push_back(std::move(objective));"):
            self.assertIn(part, check, part)
        read = function(self.main, "bool ReadKit(")
        self.assertIn('key == "MissionObjective" && KitObjectiveLine(value)', read)
        rows = function(self.main, "std::vector<KitRow> KitQuestRows(")
        self.assertIn("KitObjectiveRows(quest, formId, info);", rows)
        self.assertIn("return { { name, \"\", std::move(info) } };", rows)
        part = function(self.main, "std::string>>& a_info)\n\t{")
        part = part[part.index("for (std::size_t i = 0; i < g_kit.objectives.size(); ++i) {"):]   # the override
        self.assertIn("read = Peek(at + objective.path[p], at) && at;", part)       # a null pointer stops the path
        self.assertIn("Peek(at + objective.path.back(), state)", part)
        self.assertIn('shown(objective.index, state, "path=" + path);', part)
        self.assertNotIn("FormById(", part)
        self.assertNotIn("REL::", part)
        ini = (PLUGIN / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        self.assertNotRegex(ini, r"\nMissionObjective=")                         # ships without: the walk
        self.assertIn("; [Kit] MissionObjective=<n>|<path>", ini)
        for text in ("MissionObjective=<n>|<path>", "step=kit_quest_obj ", "step=kit_quest_objs", "owned=0",
                     "step=kit_quest_objective", "--objective <n>", "setobjectivedisplayed <form id> <n> 1"):
            self.assertIn(text, self.readme, text)
        card = (ROOT / "docs" / "spikes" / "pipboy-page-kit-owner-card.md").read_text(encoding="utf-8")
        self.assertIn("`setobjectivecompleted <id> <n> 1`", card)

    def test_the_objectives_are_walked_from_the_array(self):
        """FAL-571, the PC at 73271aa3: the BSTArray at +0x148 (data +0x150), each entry's +0x18 the quest, its number at
        +0x24 and its state at +0x28; bounded by size, capacity and 64; all or nothing; states named 0, 1, 3."""
        for part in ("kQuestObjectivesAt = 0x148;", "kObjectiveOwnerAt = 0x18;", "kObjectiveNumberAt = 0x24;",
                     "kObjectiveStateAt = 0x28;", "kQuestObjectivesMax = 64;", "kKitObjectiveRows = 12;"):
            self.assertIn(part, self.main, part)
        names = function(self.main, "std::string ObjectiveState(")
        for part in ('case 0:\n\t\t\treturn "NOT SHOWN";', 'case 1:\n\t\t\treturn "SHOWN";', 'case 3:\n\t\t\treturn "DONE";',
                     'return std::format("STATE {}", static_cast<unsigned>(a_state));'):
            self.assertIn(part, names, part)
        walk = function(self.main, "std::string>>& a_info)\n\t{")
        self.assertLess(walk.index("if (g_kit.objectives.empty()) {"),
                        walk.index("for (std::size_t i = 0; i < g_kit.objectives.size(); ++i) {"))   # lines override
        for part in ("Peek(a_quest + kQuestObjectivesAt, head)", "head.size > head.capacity",
                     "head.size > kQuestObjectivesMax", "(head.size && !head.data)",
                     "for (std::uint32_t i = 0; why.empty() && i < head.size; ++i) {",
                     "Peek(head.data + 8ull * i, objective) || !objective", "Peek(objective + kObjectiveOwnerAt, owner)",
                     "owner != a_quest", "Peek(objective + kObjectiveNumberAt, number)",
                     "Peek(objective + kObjectiveStateAt, state)",
                     'a_info.emplace_back("OBJECTIVES", Unknown("quest_objectives", why));',
                     'a_info.emplace_back("OBJECTIVES", "NONE");', 'shown(found[i].first, found[i].second, "array");',
                     'a_info.emplace_back("MORE OBJECTIVES", std::to_string(found.size() - rows));',
                     '"step=kit_quest_objectives form={:08X} at=+{:03X} {}"',
                     '"step=kit_quest_objective form={:08X} objective={} from={} state={}"',
                     "a_info.emplace_back(std::format(\"OBJECTIVE {}\", a_number), ObjectiveState(a_state));"):
            self.assertIn(part, walk, part)
        # all or nothing: rows come only after the reason check
        self.assertLess(walk.index("if (!why.empty()) {"), walk.index('shown(found[i].first, found[i].second, "array");'))
        self.assertLess(walk.index("if (walk != loggedWalk) {"), walk.index("step=kit_quest_objectives"))
        self.assertLess(walk.index("if (logged != a_state) {"), walk.index("step=kit_quest_objective form"))
        self.assertNotIn("FormById(", walk)
        self.assertNotIn("REL::", walk)
        self.assertNotIn("reinterpret_cast<", walk)
        self.assertLess(self.main.index("\tvoid KitObjectiveRows(std::uintptr_t a_quest, std::uint32_t a_formId, "
                                        "std::vector<std::pair<std::string, std::string>>& a_info);"),
                        self.main.index("\tstd::vector<KitRow> KitQuestRows("))
        for text in ("step=kit_quest_objectives", "+0x150", "`+0x18`", "`+0x24`", "`+0x28`", "NOT SHOWN", "MORE OBJECTIVES",
                     "**Verified at `73271aa3`**", "+0x148"):
            self.assertIn(text, self.readme, text)
        card = (ROOT / "docs" / "spikes" / "pipboy-page-kit-owner-card.md").read_text(encoding="utf-8")
        self.assertIn("NOT SHOWN", card)

    def test_the_readme_names_the_dump_and_the_helper(self):
        self.assertIn("step=kit_quest_bytes", self.readme)
        self.assertIn("scripts/ui/pipboy_quest_bytes.py", self.readme)


class StageAtTests(unittest.TestCase):
    """parse_kit's MissionStageAt=, the same check as the plugin's KitStageAt."""
    PAGE = "[Page DATA/QUESTS]\nList=quests\n"

    def test_good(self):
        for value, at in (("38", 0x38), ("1A4", 0x1A4), ("1a4", 0x1A4), ("336", 0x336), ("0038", None)):
            text = f"[Kit]\nMission=FO4SFMission.esm|800\nMissionStageAt={value}\n" + self.PAGE
            if at is None:
                with self.assertRaises(kit.KitError):                              # more than 3 digits
                    kit.parse_kit(text)
            else:
                self.assertEqual(kit.parse_kit(text)["stage_at"], at, value)

    def test_bad(self):
        for value in ("", "36", "1A5", "338", "+1A4", "0x1A4", "1G4", "1A 4"):   # outside, odd, not bare hex
            with self.assertRaises(kit.KitError, msg=value):
                kit.check_stage_at(value, 1)
        twice = "[Kit]\nMissionStageAt=1A4\nMissionStageAt=1A4\n" + self.PAGE
        with self.assertRaises(kit.KitError):
            kit.parse_kit(twice)

    def test_the_shipped_ini_has_none(self):
        self.assertIsNone(kit.read_kit()["stage_at"])


class ObjectiveTests(unittest.TestCase):
    """parse_kit's MissionObjective=, the same check as the plugin's KitObjectiveLine."""
    KIT = "[Kit]\nMission=FO4SFMission.esm|800\n"
    PAGE = "[Page DATA/QUESTS]\nList=quests\n"

    def test_good(self):
        for value, index, path in (("10|1A0/1C", 10, [0x1A0, 0x1C]), ("85|38/0/3F", 85, [0x38, 0, 0x3F]),
                                   ("86|330/38/0", 86, [0x330, 0x38, 0]), ("65535|1a8/8/1c", 65535, [0x1A8, 8, 0x1C])):
            kit_ = kit.parse_kit(self.KIT + f"MissionObjective={value}\n" + self.PAGE)
            self.assertEqual(kit_["objectives"], [{"index": index, "path": path}], value)

    def test_bad(self):
        for value in ("", "10", "10|", "|1A0/1C", "65536|1A0/1C", "-1|1A0/1C", "1 0|1A0/1C", "10|1A0", "10|1A0/8/8/1C",
                      "10|30/1C", "10|338/1C", "10|1A4/1C", "10|1A0/40", "10|1A0/4/1C", "10|1A0/40/1C", "10|1A0//1C",
                      "10|+1A0/1C", "10|0x1A0/1C", "10|1A0/1C/", "10|1A0/1C|2"):
            with self.assertRaises(kit.KitError, msg=value):
                kit.check_objective(value, 1)

    def test_each_once_and_at_most_eight(self):
        with self.assertRaises(kit.KitError):
            kit.parse_kit(self.KIT + "MissionObjective=10|1A0/1C\nMissionObjective=010|1A8/1C\n" + self.PAGE)
        eight = "".join(f"MissionObjective={n}|1A0/{n:X}\n" for n in range(8))
        self.assertEqual(len(kit.parse_kit(self.KIT + eight + self.PAGE)["objectives"]), 8)
        with self.assertRaises(kit.KitError):
            kit.parse_kit(self.KIT + eight + "MissionObjective=9|1A0/9\n" + self.PAGE)

    def test_the_shipped_ini_has_none(self):
        self.assertEqual(kit.read_kit()["objectives"], [])


class ObjectiveHelperTests(unittest.TestCase):
    """FAL-571: pipboy_quest_bytes.py --objective on a made-up log in the plugin's format."""
    QUEST = 0x7FF6_1234_0000

    def block(self, index, state):
        data = bytearray(0x40)
        data[0x08:0x10] = self.QUEST.to_bytes(8, "little")                     # its owner, as the plugin requires
        data[0x1C:0x1E] = index.to_bytes(2, "little")
        data[0x20] = state
        return bytes(data)

    def presses(self, state_a, state_b):
        stage = bytearray(0x40)
        stage[0:8] = self.QUEST.to_bytes(8, "little")
        stage[0x30] = 1
        before = {"+1A0/+00": (0x2000, self.block(10, state_a)), "+1A0/+08": (0x2100, self.block(85, 0)),
                  "+200": (0x3000, bytes(stage))}
        after = dict(before)
        after["+1A0/+00"] = (0x2000, self.block(10, state_b))
        changed = bytearray(stage)
        changed[0x30] = 2                                                        # a block that is not objective 10's
        after["+200"] = (0x3000, bytes(changed))
        return obj_lines(3, "07000800", before) + obj_lines(5, "07000800", after)

    def test_the_lines_read_back(self):
        found = pqb.blocks(self.presses(0, 1) + dump_lines(3, "07000800", bytes(0x300)))
        self.assertEqual(sorted(found), [3, 5])
        form, blocks, counts = found[3]
        self.assertEqual((form, counts), ("07000800", (40, 3)))
        self.assertEqual(blocks["+1A0/+00"], (0x2000, self.block(10, 0)))

    def test_the_state_byte_is_marked(self):
        found = pqb.blocks(self.presses(0, 1))
        rows = pqb.objective_changes(found[3][1], found[5][1], 10)
        self.assertEqual(rows, [("+1A0/+00", 0x20, 0, 1, True), ("+200", 0x30, 1, 2, False)])
        line = pqb.objective_line(10, rows)
        self.assertEqual(line, "MissionObjective=10|1A0/0/20")
        self.assertEqual(kit.check_objective(line.split("=", 1)[1], 1), {"index": 10, "path": [0x1A0, 0, 0x20]})
        self.assertIsNone(pqb.objective_line(10, pqb.objective_changes(found[3][1], found[5][1], 86)))   # none marked
        self.assertIsNone(pqb.objective_line(10, rows + [("+1A0/+08", 0x20, 0, 1, True)]))           # several

    def test_a_block_that_moved_is_not_compared(self):
        found = pqb.blocks(self.presses(0, 1))
        moved = dict(found[5][1])
        moved["+1A0/+00"] = (0x2800, moved["+1A0/+00"][1])
        self.assertEqual([row[0] for row in pqb.objective_changes(found[3][1], moved, 10)], ["+200"])

    def test_main_on_a_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "FO4SFPipboyMenu.log")
            with open(log, "w", encoding="utf-8") as handle:
                handle.writelines(self.presses(1, 3))
            self.assertEqual(pqb.main([log, "--objective", "10"]), 0)
            self.assertEqual(pqb.main([log, "--objective", "10", "--after", "4"]), 2)
            with open(log, "w", encoding="utf-8") as handle:                     # nothing points back: wider dump
                handle.writelines(obj_lines(3, "07000800", {}) + obj_lines(5, "07000800", {}))
            self.assertEqual(pqb.main([log, "--objective", "10"]), 1)
            with open(log, "w", encoding="utf-8") as handle:                     # a plugin before FAL-571
                handle.writelines(dump_lines(3, "07000800", bytes(0x300)))
            self.assertEqual(pqb.main([log, "--objective", "10"]), 2)


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
        self.assertEqual(pqb.stage_line(rows), "MissionStageAt=1A4")              # FAL-527: the [Kit] line
        self.assertEqual(kit.check_stage_at(pqb.stage_line(rows).split("=")[1], 1), 0x1A4)
        self.assertIsNone(pqb.stage_line(pqb.changed(found[4][1], found[7][1], (1, 2))))   # none marked
        self.assertIsNone(pqb.stage_line(rows + [(0x1B0, 20, 30, True)]))         # several marked

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
