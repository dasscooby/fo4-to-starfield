"""The cut-down "When Freedom Calls" mission: the contract between dotnet/Mission (the plugin), FO4SF_Min00Quest.psc (the
quest script) and make_mission.py (staging and the log reader). Synthetic only; the C# writer's own self-test runs when
a dotnet SDK is on PATH (dotnet/Mission selftest: synthetic masters, write + check)."""
import os
import shutil
import subprocess
import sys
import json
import math
import re
import tempfile
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts", "mission"))
import make_mission  # noqa: E402

PSC = os.path.join(ROOT, "scripts", "mission", "FO4SF_Min00Quest.psc")
CS = os.path.join(ROOT, "dotnet", "Mission", "Program.cs")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def function_body(psc, name):
    """A script function's text, from its "Function <name>(" to its EndFunction."""
    i = psc.index(f"Function {name}(")
    return psc[i:psc.index("EndFunction", i)]


class ContractTests(unittest.TestCase):
    def test_script_properties_are_the_ones_the_plugin_fills(self):
        self.assertEqual(tuple(make_mission.mandatory_properties(read(PSC))), make_mission.PROPERTIES)
        cs = read(CS)
        for name in make_mission.PROPERTIES:
            self.assertIn(f'"{name}"', cs, f"Program.cs never writes the property {name}")

    def test_stages_match_between_plugin_and_script(self):
        cs = read(CS)
        stages = ", ".join(str(s) for s in make_mission.STAGES)
        self.assertIn("Stages = { " + stages + " }", cs)
        psc = read(PSC)
        for s in make_mission.STAGES:
            self.assertRegex(psc, rf"auiStageID == {s}\b", f"the script never handles stage {s}")
        for o in (10, 85, 86):                                   # Min00's objective indices, written by Program.cs
            self.assertIn(f"SetObjectiveDisplayed({o})", psc)
            self.assertIn(f"({o}, \"", cs)

    def test_make_mission_compiles_without_warnings(self):
        """PC, Python 3.14 (FAL-128): make_mission.py's docstring printed a SyntaxWarning for "\\S" (Data\\Scripts)."""
        import warnings
        src = read(os.path.join(ROOT, "scripts", "mission", "make_mission.py"))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            compile(src, "make_mission.py", "exec")
        self.assertIn(r"Data\Scripts\FO4SF_Min00Quest.pex", make_mission.__doc__)     # the help text is unchanged

    def test_mandatory_properties_parser(self):
        text = ("Actor Property A Auto Const Mandatory\nActor[] Property B Auto Const Mandatory\n"
                "int Property C = 1 Auto Const\n  MiscObject Property D Auto Const Mandatory\n")
        self.assertEqual(make_mission.mandatory_properties(text), ["A", "B", "D"])


class LogTests(unittest.TestCase):
    LINES = [
        "[10/18/2026 - 02:00:00PM] FO4SF_MISSION rt=10.5 init raiders=3",
        "[10/18/2026 - 02:00:00PM] FO4SF_MISSION rt=10.6 stage 10",
        "[10/18/2026 - 02:01:00PM] FO4SF_MISSION rt=70.1 startcombat raider 0 d=55.2",
        "[10/18/2026 - 02:01:00PM] FO4SF_MISSION rt=70.1 stage 20",
        "[10/18/2026 - 02:01:01PM] FO4SF rt=70.2 pos=1 2 3 ang=0 cell=none world=none loaded=True n=4",
        "[10/18/2026 - 02:03:00PM] FO4SF_MISSION rt=190.0 status stage=20 dead=3/3 nearest_raider=-1.0 preston=40.0 pos=1 2 3",
        "[10/18/2026 - 02:03:00PM] FO4SF_MISSION rt=190.0 stage 30",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 preston activated at stage 30",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 stage 40",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 reward credits=100",
        "[10/18/2026 - 02:04:00PM] FO4SF_MISSION rt=250.0 stage 200",
    ]

    def test_full_run(self):
        s = make_mission.summarize(self.LINES)
        self.assertEqual(s["stages"], [10, 20, 30, 40, 200])
        self.assertEqual(s["reward"], 100)
        self.assertEqual(s["startcombat"], 1)
        self.assertEqual(s["activated"], 1)
        self.assertTrue(s["status"].startswith("status stage=20 dead=3/3"))

    def test_partial_run_is_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "fo4sf_mission.0.log")
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(self.LINES[:4]) + "\n")
            self.assertEqual(make_mission.main(["log", "--file", p]), 1)
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(self.LINES) + "\n")
            self.assertEqual(make_mission.main(["log", "--file", p]), 0)

    def test_other_log_lines_ignored(self):
        self.assertEqual(make_mission.summarize(["FO4SF rt=1 pos=1 2 3 n=1", "noise"])["stages"], [])

    def test_found_preston_is_reported_once(self):
        s = make_mission.summarize(self.LINES)
        self.assertIsNone(s["found"])
        lines = ["[10/28/2026 - 06:12:45PM] FO4SF_MISSION rt=200.0 preston activated at stage 10",
                 "[10/28/2026 - 06:12:45PM] FO4SF_MISSION rt=200.0 found preston activated",
                 "[10/28/2026 - 06:12:46PM] FO4SF_MISSION rt=201.0 found preston near d=2.5",
                 "[10/28/2026 - 06:12:46PM] FO4SF_MISSION rt=201.0 startcombat raider 0 d=91.3",
                 "[10/28/2026 - 06:12:46PM] FO4SF_MISSION rt=201.0 stage 20"]
        s = make_mission.summarize(lines)
        self.assertEqual((s["found"], s["activated"], s["startcombat"], s["stages"]), ("activated", 1, 1, [20]))

    def test_keeper_reports_preston_after_the_mission(self):
        """FAL-64: after stage 200 the keeper's lines are the only evidence of where Preston is."""
        s = make_mission.summarize(self.LINES)
        self.assertEqual((s["preston_moves"], s["keeper"]), (0, None))
        after = self.LINES + [
            "[11/07/2026 - 09:40:00PM] FO4SF_MISSION rt=300.0 keeper load preston d=155.3 off=160.2 state=none moves=0 "
            "at -1960.0 -1850.0 89.1 disabled=False dead=False fails=0 player=-2011.1 -1697.2 90.0 interior=False",
            "[11/07/2026 - 09:40:05PM] FO4SF_MISSION rt=305.0 moved preston to -2011.1 -1697.5 89.1 target -2011.1 "
            "-1697.5 89.1 before=155.3 off=160.2 d=0.3 failed=False by=keeper",
            "[11/07/2026 - 09:40:05PM] FO4SF_MISSION rt=305.0 moved codsworth to 1 2 3 target 1 2 3 before=1 d=1 failed=False",
            "[11/07/2026 - 09:41:00PM] FO4SF_MISSION rt=360.0 keeper status preston d=3.2 off=0.4 state=at spot moves=1 "
            "at -2011.1 -1697.5 89.1 disabled=False dead=False fails=0 player=-2012.0 -1700.0 90.0 interior=False",
        ]
        s = make_mission.summarize(after)
        self.assertEqual(s["preston_moves"], 1)
        self.assertTrue(s["keeper"].startswith("keeper status preston d=3.2"))
        self.assertEqual(s["preston_off"], 0.4)                         # FAL-128: the PC check's PASS reads this
        self.assertEqual(s["stages"], [10, 20, 30, 40, 200])
        # a 2590549e keeper line has no off=, and an unreadable one is None, never an error
        self.assertIsNone(make_mission.summarize([after[-1].replace(" off=0.4", "")])["preston_off"])
        self.assertIsNone(make_mission.summarize([after[-1].replace("off=0.4", "off=nan?")])["preston_off"])

    def test_names_are_read_in_any_case(self):
        """The 31 Oct logs (FAL-128 pc-evidence-20261110) print "moved Codsworth" and "moved Preston" where the script's
        literals were "codsworth" and "preston": the game prints a name as the property it matches. Those moves count."""
        lines = [
            "[15:04:21] FO4SF_MISSION rt=130.3 moved Codsworth to -2346.7 -1406.1 111.7 target -2346.7 -1406.1 111.7 "
            "before=INF d=122.0 failed=false",
            "[15:04:21] FO4SF_MISSION rt=131.1 moved Preston to -2011.5 -1697.2 89.0 target -2011.1 -1697.5 89.0 "
            "before=INF d=544.4 failed=false",
            "[15:04:22] FO4SF_MISSION rt=131.6 moved raider 0 to -2029.7 -1696.5 88.3 target -2029.1 -1698.2 88.3 "
            "before=INF d=529.7 failed=false",
        ]
        s = make_mission.summarize(lines)
        self.assertEqual((s["preston_moves"], s["codsworth_moves"]), (1, 1))

    def test_keeper_reports_codsworth(self):
        """FAL-163: the keeper's lines for Codsworth (load, status) are read like Preston's, apart from his."""
        lines = [
            "[11/10/2026 - 09:40:00PM] FO4SF_MISSION rt=30.0 keeper load Preston d=3.0 off=0.5 state=at spot moves=1 "
            "at -2011.1 -1697.5 89.1 disabled=False dead=False fails=0 player=-2012.0 -1700.0 90.0 interior=False",
            "[11/10/2026 - 09:40:00PM] FO4SF_MISSION rt=30.0 keeper load Codsworth d=3102.0 off=2955.1 state=none "
            "moves=0 at -1146.7 1293.8 111.7 disabled=False dead=False fails=0 player=-2012.0 -1700.0 90.0 interior=False",
            "[11/10/2026 - 09:45:05PM] FO4SF_MISSION rt=335.0 moved Codsworth to -2346.7 -1406.2 111.7 target -2346.709 "
            "-1406.163 111.734 before=3001.2 off=2955.1 d=120.3 failed=False by=keeper",
            "[11/10/2026 - 09:46:00PM] FO4SF_MISSION rt=390.0 keeper status Codsworth d=118.0 off=1.2 state=placed "
            "moves=1 at -2346.0 -1406.0 111.7 disabled=False dead=False fails=0 player=-2460.0 -1400.0 127.0 "
            "interior=False",
        ]
        s = make_mission.summarize(lines)
        self.assertEqual((s["codsworth_moves"], s["codsworth_off"], s["preston_moves"], s["preston_off"]),
                         (1, 1.2, 0, 0.5))
        self.assertTrue(s["codsworth_keeper"].startswith("keeper status Codsworth d=118.0"))
        self.assertTrue(s["keeper"].startswith("keeper load Preston"))
        self.assertIsNone(make_mission.summarize(lines[:1])["codsworth_keeper"])


class NextStageTests(unittest.TestCase):
    """make_mission.next_stage mirrors the script's NextStage (Codex review 5563368986: progress must not depend on
    this script having issued StartCombat)."""
    def test_fight_started_by_anyone_advances(self):
        self.assertEqual(make_mission.next_stage(10, 0, 5, True, False), 20)      # already fighting at start/reload
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, False), 10)     # nothing yet

    def test_dead_before_next_check(self):
        self.assertEqual(make_mission.next_stage(10, 2, 5, False, False), 20)
        self.assertEqual(make_mission.next_stage(10, 5, 5, False, False), 30)     # all died between two checks
        self.assertEqual(make_mission.next_stage(20, 5, 5, False, False), 30)

    def test_preston_only_after_the_raiders(self):
        self.assertEqual(make_mission.next_stage(20, 4, 5, True, True), 20)
        self.assertEqual(make_mission.next_stage(30, 5, 5, False, True), 40)
        self.assertEqual(make_mission.next_stage(30, 5, 5, False, False), 30)

    def test_never_goes_back_and_no_raiders_never_counts_as_cleared(self):
        self.assertEqual(make_mission.next_stage(40, 0, 5, False, False), 40)
        self.assertEqual(make_mission.next_stage(10, 0, 0, False, False), 10)

    def test_finding_preston_starts_the_fight(self):
        # in game 28 Oct (new game run 3): Preston activated five times at stage 10, every raider 91 to 129 m away and
        # none fighting; the stage stayed 10. Found, it is 20 even before a raider's 3D is loaded.
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, False), 10)
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, False, found=True), 20)
        self.assertEqual(make_mission.next_stage(10, 0, 5, False, True, found=True), 20)    # not past the fight
        self.assertEqual(make_mission.next_stage(20, 3, 5, True, True, found=True), 20)
        self.assertEqual(make_mission.next_stage(10, 5, 5, False, False, found=True), 30)   # all dead is still 30
        self.assertEqual(make_mission.next_stage(10, 0, 0, False, False, found=True), 20)   # never "cleared"

    def test_script_carries_the_same_rule(self):
        psc = read(PSC)
        for cond in ("s < 20 && (fighting || dead > 0 || found)", "s < 30 && total > 0 && dead == total",
                     "s == 30 && atPreston"):
            self.assertIn(cond, psc)
        self.assertNotIn("GetCombatState() == 0\n", psc)
        self.assertIn("int Function NextStage(int stage, int dead, int total, bool fighting, bool atPreston, bool found)",
                      psc)
        self.assertIn("NextStage(stage, dead, Raiders.Length, fighting, dp < TalkRadius, prestonFound)", psc)


class FindPrestonTests(unittest.TestCase):
    """In game 28 Oct (new game run 3, the owner: "the freedoms calls activation didnt work"): OnActivate ran ("preston
    activated at stage 10" five times) but only stage 30 acted on it, and the fight waited for a raider within
    EngageRadius while the nearest stayed 91 to 129 m away. Reaching Preston (activation or FindRadius) now starts the
    fight, and once it is on every loaded raider is put into combat."""

    def setUp(self):
        self.psc = read(PSC)

    def block(self, start, end):
        i = self.psc.index(start)
        return self.psc[i:self.psc.index(end, i)]

    def test_activation_before_the_fight_finds_preston(self):
        act = self.block("Event ObjectReference.OnActivate(", "EndEvent")
        self.assertRegex(act, r"if stage < 20\s+FoundPreston\(\"activated\"\)")
        self.assertRegex(act, r"elseif stage == 30\s+AdvanceTo\(40\)")

    def test_standing_near_preston_before_the_fight_finds_him(self):
        tick = self.block("Event OnTimer(", "EndEvent")
        self.assertRegex(tick, r"if stage < 20 && dp < FindRadius\s+FoundPreston\(")
        self.assertLess(tick.index("FoundPreston("), tick.index("while i < Raiders.Length"))   # before the raiders' loop
        num = lambda name: float(re.search(r"float Property %s = (-?[\d.]+) Auto Const" % name, self.psc).group(1))
        self.assertEqual(num("FindRadius"), 20.0)                                          # the documented 20 m
        self.assertGreater(num("FindRadius"), num("TalkRadius"))
        self.assertNotIn("FindRadius", make_mission.mandatory_properties(self.psc))         # the plugin never fills it

    def test_once_the_fight_is_on_every_loaded_raider_is_put_into_combat(self):
        tick = self.block("Event OnTimer(", "EndEvent")
        self.assertIn("bool everyone = prestonFound || stage >= 20", tick)
        self.assertIn("elseif stage < 30 && (everyone || d < EngageRadius) && r.Is3DLoaded()", tick)
        # the raider itself is put into combat, with the player as its target
        self.assertRegex(tick, r"r\.Is3DLoaded\(\)\s+(;[^\n]*\s+)*r\.StartCombat\(player\)")
        self.assertEqual(re.findall(r"\b(\w+)\.StartCombat\((\w+)\)", self.psc), [("r", "player")])

    def test_dead_raiders_are_skipped(self):
        """A dead raider is counted and never put into combat: the loop's first test on each raider is IsDead."""
        tick = self.block("Event OnTimer(", "EndEvent")
        self.assertRegex(tick, r"Actor r = Raiders\[i\]\s+if r\.IsDead\(\)\s+dead \+= 1\s+else\s")
        loop = tick[tick.index("Actor r = Raiders[i]"):]
        self.assertLess(loop.index("if r.IsDead()"), loop.index("r.StartCombat(player)"))

    def test_found_is_set_and_logged_once(self):
        found = self.block("Function FoundPreston(string how)", "EndFunction")
        self.assertRegex(found, r"if !prestonFound && !Preston\.IsDead\(\)\s+prestonFound = True\s+"
                                r"Trace\(\"found preston \" \+ how\)")
        self.assertRegex(self.psc, r"(?m)^bool prestonFound = False$")


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class RelocateContractTests(unittest.TestCase):
    """In game 18 Oct: the core's persistent cell keeps its references at their local position in the base world, so the
    script moves its actors by the core's merge offset; that offset must be the one the door writer uses."""

    def test_script_merge_offset_is_the_measured_one(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
        import vmad_patch
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        got = {k: float(v) for k, v in re.findall(r"float Property MergeOffset([XY]) = (-?[\d.]+) Auto Const", psc)}
        self.assertEqual((got["X"], got["Y"]), vmad_patch.MERGE_MEASURED[:2])

    def test_no_exponent_float_literals(self):
        """Papyrus has no 1.0e30 literals (PC compile of 6ee0896: "required (...)+ loop did not match anything at
        input 'e30'"); comments and doc strings are exempt."""
        with open(PSC, encoding="utf-8") as f:
            code = re.sub(r"\{[^}]*\}", "", f.read())
        code = "\n".join(line.split(";")[0] for line in code.splitlines())
        self.assertIsNone(re.search(r"\d[eE][-+]?\d", code))

    def test_no_keyword_names(self):
        """Papyrus keywords (case-insensitive) cannot name a parameter or a variable: a parameter "state" (TraceSpot,
        FAL-163) would not compile, and this host has no Papyrus compiler to catch it."""
        keywords = {"as", "auto", "autoreadonly", "betaonly", "bool", "collapsed", "conditional", "const", "customevent",
                    "debugonly", "else", "elseif", "endevent", "endfunction", "endguard", "endif", "endproperty",
                    "endstate", "endstruct", "endwhile", "event", "extends", "false", "float", "function", "global",
                    "guard", "hidden", "if", "import", "int", "is", "length", "mandatory", "native", "new", "none",
                    "parent", "property", "return", "scriptname", "self", "state", "string", "struct", "true",
                    "tryguard", "var", "while"}
        code = re.sub(r"\{[^}]*\}", "", read(PSC))
        code = re.sub(r'"[^"]*"', '""', "\n".join(line.split(";")[0] for line in code.splitlines()))
        names = [n for n in re.findall(r"\b(?:bool|int|float|string|Actor|WorldSpace|MiscObject)(?:\[\])?\s+(\w+)",
                                       code, re.I) if n not in ("Property", "Function")]
        self.assertIn("spotState", names)
        self.assertEqual([n for n in names if n.lower() in keywords], [])

    def test_relocate_decides_by_position(self):
        """In game 18 Oct 14:40 the unmoved actors read a finite distance of about 2,955 (the offset's length), and the
        "finite means reachable" test skipped the move: the gap must sit between the radius and that length."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        num = lambda name: float(re.search(r"float Property %s = (-?[\d.]+) Auto Const" % name, psc).group(1))
        offset = (num("MergeOffsetX") ** 2 + num("MergeOffsetY") ** 2) ** 0.5
        radius, gap = num("RelocateRadius"), num("RelocateGap")
        self.assertLess(radius, gap)
        self.assertLess(gap, offset - radius)
        self.assertNotIn("1000000000", psc)

    def test_relocate_is_per_actor_and_retries(self):
        """Codex 5564899342: no global "relocated" flag (a no-op or partial move must be retried, a moved actor never
        offset twice), and no move from an interior."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertNotIn("relocated = true", psc)
        self.assertIn("if player.IsInInterior()", psc)
        self.assertRegex(psc, r"if relocateFails < 10\s+Relocate\(player\)")

    def test_relocate_rule_model(self):
        """The PSC's per-actor rule on plain numbers: unmoved (same world at the local spot, or another world), moved,
        a no-op MoveTo, and a partial pass followed by a retry."""
        far = float("inf")
        ox, oy, radius, gap = -1200.0, -2700.0, 800.0, 1500.0

        def step(player, actors, moveto_works):
            for a in actors:
                dist = far if a["world"] != "merged" else math.dist(player, a["pos"])
                tx, ty = a["pos"][0] + ox, a["pos"][1] + oy
                if dist < gap or math.dist(player, (tx, ty)) > radius:
                    continue
                if moveto_works(a):
                    a["pos"], a["world"] = (tx, ty), "merged"

        street = (-2011.1, -1697.2)
        for world in ("merged", "base"):
            actors = [{"pos": (-811.1, 1002.5), "world": world}, {"pos": (-790.0, 1010.0), "world": world}]
            step(street, actors, lambda a: False)                       # no-op MoveTo: still pending
            self.assertTrue(all(a["pos"] == (-811.1, 1002.5) or a["pos"] == (-790.0, 1010.0) for a in actors))
            step(street, actors, lambda a: a is actors[0])              # partial: only the first arrives
            self.assertEqual(actors[0]["pos"], (-2011.1, -1697.5))
            self.assertEqual(actors[1]["pos"], (-790.0, 1010.0))
            step(street, actors, lambda a: True)                        # retry: the second arrives, the first stays
            self.assertEqual(actors[0]["pos"], (-2011.1, -1697.5))
            self.assertEqual(actors[1]["pos"], (-1990.0, -1690.0))
            step(street, actors, lambda a: True)                        # nothing moves twice
            self.assertEqual(actors[1]["pos"], (-1990.0, -1690.0))
        away = [{"pos": (-811.1, 1002.5), "world": "merged"}]
        step((-1276.0, -3032.0), away, lambda a: True)                  # Red Rocket: not at the museum yet
        self.assertEqual(away[0]["pos"], (-811.1, 1002.5))

    def test_codsworth_is_kept_after_the_mission(self):
        """Review 20 Oct: Codsworth has his own timer (2) and failure budget, which stage 200 does not cancel, and the
        mission's Relocate no longer moves him."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        keep = psc[psc.index("Function KeepCodsworth()"):psc.index("bool Function MoveOver")]
        self.assertIn("codsworthFails += 1", keep)
        self.assertRegex(keep, r"if \(Codsworth != None && \(codsworthFails < 10 \|\| codsworthHolds > 0\)\) \|\| "
                               r"\(KeeperOnly && \(prestonFails < 10 \|\| prestonHolds > 0\)\)"
                               r"\s+StartTimer\(CodsworthCheck, 2\)")
        self.assertNotIn("GetStage", keep)
        relocate = psc[psc.index("Function Relocate("):psc.index("Function KeepCodsworth()")]
        self.assertNotIn("MoveOver(Codsworth", relocate)
        self.assertIn("CancelTimer(1)", psc)
        self.assertNotIn("CancelTimer(2)", psc)
        self.assertRegex(psc, r"if aiTimerID == 2\s+KeepCodsworth\(\)")
        self.assertEqual(psc.count("KeepCodsworthStart()"), 3)          # defined, from OnQuestInit, from timer 1

    def test_the_keeper_restarts_codsworth_on_an_existing_save(self):
        """22 Oct, the owner's save: Codsworth unmoved and no mission log, since stage 200 cancels timer 1 and nothing
        else started his timer. His keeper (a start-game-enabled quest of its own, KeeperOnly) starts on such a save,
        enables him, and restarts his timer with a fresh budget at its init and on every save load; it never runs the
        mission."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertRegex(psc, r"(?m)^bool Property KeeperOnly = False Auto Const$")
        self.assertNotIn("KeeperOnly", make_mission.mandatory_properties(psc))
        init = psc[psc.index("Event OnQuestInit()"):psc.index("EndEvent", psc.index("Event OnQuestInit()"))]
        keeper = init[:init.index("endif")]
        self.assertIn("if KeeperOnly", keeper)
        self.assertIn('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")', keeper)
        self.assertIn("KeepCodsworthLoad()", keeper)
        self.assertIn("return", keeper)
        self.assertLess(init.index("return"), init.index("AdvanceTo(10)"))     # the keeper never starts the mission
        load = psc[psc.index("Function KeepCodsworthLoad()"):psc.index("EndFunction", psc.index("Function KeepCodsworthLoad()"))]
        self.assertRegex(load, r"if Codsworth.IsDisabled\(\)\s+Codsworth.Enable\(\)")
        self.assertIn("codsworthFails = 0", load)
        self.assertIn("StartTimer(CodsworthCheck, 2)", load)
        self.assertRegex(psc, r"Event Actor.OnPlayerLoadGame\(Actor akSender\)\s+if KeeperOnly\s+KeepCodsworthLoad\(\)")
        keep = psc[psc.index("Function KeepCodsworth()"):psc.index("bool Function MoveOver")]
        # the mission's old timer 2 (no Codsworth, not the keeper) moves nobody and is not restarted
        self.assertRegex(keep, r"if Codsworth != None && codsworthFails < 10\s+if PlaceCodsworth\(player\)")

    def test_a_missing_codsworth_does_not_stop_preston(self):
        """FAL-128 (2590549e review): KeepCodsworthLoad and KeepCodsworth returned early when Codsworth was None, which
        also silently stopped Preston's keeping. Only Codsworth's own steps need him now."""
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        for name in ("KeepCodsworthLoad", "KeepCodsworth"):
            self.assertNotIn("Codsworth == None", body(name), name)
            self.assertNotRegex(body(name), r"(?m)^\s+return\s*$", name)
        load = body("KeepCodsworthLoad")
        guarded = load[load.index("if Codsworth != None"):load.index("prestonFails = 0")]
        for step in ("Codsworth.Enable()", "codsworthFails = 0", "codsworthKept = True"):
            self.assertIn(step, guarded)
        rest = load[load.index("prestonFails = 0"):]
        for step in ('TracePreston("keeper load")', "StartTimer(CodsworthCheck, 2)"):
            self.assertIn(step, rest)                                   # outside Codsworth's guard

    def test_the_keeper_keeps_preston_after_the_mission(self):
        """FAL-64, the owner's report of 7 Nov: "no preston garvy after misson finshes". Stage 200 cancels timer 1, the
        mission's Relocate with it, while Preston snaps back to his unmerged spot (in game 19 Oct: moved 5 times in one
        session). The keeper (timer 2, not cancelled by stage 200, restarted on every load) puts him back by the same
        rule and to the same spot as the mission (PlacePreston), with its own budget, and logs where he is; the mission
        instance never runs KeepPreston."""
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        keep, preston, load = body("KeepCodsworth"), body("KeepPreston"), body("KeepCodsworthLoad")
        self.assertRegex(keep, r"if KeeperOnly\s+KeepPreston\(player\)")                # only the keeper instance
        self.assertRegex(preston, r"if prestonFails < 10\s+if PlacePreston\(player, \"keeper\"\)")
        self.assertRegex(body("Relocate"), r"if PlacePreston\(player, \"mission\"\)\s+relocateFails \+= 1")
        self.assertNotIn("MoveOver(Preston", psc)                       # one rule for him: PlacePreston
        self.assertIn("prestonFails += 1", preston)
        self.assertNotIn("GetStage", preston)                           # runs after stage 200, whatever the stage
        self.assertNotIn("GetStage", body("PlacePreston"))
        self.assertNotIn("MoveTo(", preston)                            # the same move as Relocate: PlacePreston only
        self.assertIn('TracePreston("keeper status")', preston)
        self.assertIn("keeperChecks % KeeperStatusEvery == 0", preston)
        self.assertIn("prestonFails = 0", load)                         # a fresh budget on every save load
        self.assertLess(load.index("prestonFails = 0"), load.index("StartTimer(CodsworthCheck, 2)"))
        self.assertIn('TracePreston("keeper load")', load)
        self.assertNotIn("CancelTimer(2)", psc)
        for v in ("int prestonFails = 0", "int keeperChecks = 0"):
            self.assertRegex(psc, rf"(?m)^{v}$")
        self.assertRegex(psc, r"(?m)^int Property KeeperStatusEvery = 12 Auto Const$")
        self.assertNotIn("KeeperStatusEvery", make_mission.mandatory_properties(psc))     # the plugin is unchanged
        self.assertIn('TraceSpot(what, Preston, "preston", prestonOff, prestonState, prestonMoves, prestonHeld, prestonHolds, '
                      'prestonFails)',
                      body("TracePreston"))
        trace = body("TraceSpot")
        for field in ('" d="', '" off="', '" state="', '" moves="', '" disabled="', '" dead="', '" fails="',
                      '" player="', '" interior="'):
            self.assertIn(field, trace)
        self.assertIn('Trace(what + " " + name + " d="', trace)
        # the keeper quest carries the mission's properties, Preston among them (no new plugin record)
        cs = read(CS)
        keeper = cs[cs.index("var ks = new SF.ScriptEntry"):cs.index("keeper.VirtualMachineAdapter")]
        self.assertIn("MissionProps(ks);", keeper)
        self.assertIn('Obj("Preston", prestonRef.FormKey)', cs[cs.index("void MissionProps("):cs.index("MissionProps(script);")])

    def test_keeper_rule_model_after_the_mission(self):
        """The keeper's rule on plain numbers, after stage 200, with make_mission.place_at (the script's PlaceAt, by
        PlacePreston): Preston snapped back to his local spot, the mission's check is off. He is put back only when the
        player is outdoors near his merged spot, always to that spot, and a no-op move spends the budget until a load
        renews it."""
        ox, oy, local = -1200.0, -2700.0, (-811.14, 1002.46)
        spot = (local[0] + ox, local[1] + oy)

        def keeper_check(state, player, outdoors, moveto_works, same_world=True):
            if state["fails"] >= 10:
                return
            off = math.dist(state["pos"], spot)
            dp = math.dist(player, state["pos"]) if same_world else float("inf")
            if make_mission.place_at(off, dp, math.dist(player, spot), not outdoors, False) == "move":
                if moveto_works:
                    state["pos"] = spot
                else:
                    state["fails"] += 1

        street, sanctuary = (-2011.1, -1697.2), (-1146.7, 1293.8)
        s = {"pos": local, "fails": 0}
        keeper_check(s, sanctuary, True, True)                          # elsewhere: he stays where he is
        self.assertEqual(s["pos"], local)
        keeper_check(s, street, False, True)                            # in the museum: no move from an interior
        self.assertEqual(s["pos"], local)
        keeper_check(s, street, True, True)                             # back at the museum: put back
        self.assertEqual(s["pos"], spot)
        keeper_check(s, street, True, True)                             # at his spot: left alone
        self.assertEqual(s["pos"], spot)
        s = {"pos": local, "fails": 0}
        for _ in range(12):
            keeper_check(s, street, True, False)
        self.assertEqual(s["fails"], 10)                                # budget spent: the keeper stops trying
        keeper_check(s, street, True, True)
        self.assertEqual(s["pos"], local)
        s["fails"] = 0                                                  # a save load renews it
        keeper_check(s, street, True, True, same_world=False)           # another world (float max) counts as off
        self.assertEqual(s["pos"], spot)

    def test_preston_off_his_spot_near_the_player_is_put_back(self):
        """FAL-128, the PC's 31 Oct logs (pc-evidence-20261110): Preston was moved once from 544 m away (cell=None) and
        then read 100 to 453 m from the player all session; at 20:59:31 the player stood 9 m from the spot and he was
        155.3 away. Under RelocateGap, MoveOver called that "already moved" and never moved him again. The fixed-spot
        rule puts him back once the player is within PlaceRadius, but not while he fights or the player is inside."""
        spot, player, preston = (-2011.14, -1697.54), (-2018.7, -1692.4), (-1960.0, -1850.0)
        off, dp, to_spot = math.dist(preston, spot), math.dist(player, preston), math.dist(player, spot)
        self.assertGreater(off, 25.0)
        self.assertLess(dp, 1500.0)                                     # what MoveOver read as "already there"
        self.assertEqual(make_mission.place_at(off, dp, to_spot, False, False), "move")
        self.assertEqual(make_mission.place_at(off, dp, to_spot, False, True), "off, fighting")
        self.assertEqual(make_mission.place_at(off, dp, to_spot, True, False), "off, player inside")
        self.assertEqual(make_mission.place_at(off, dp, 544.4, False, False), "off, player away")   # cell=None range
        self.assertEqual(make_mission.place_at(10.0, 9.0, to_spot, False, False), "at spot")
        # snapped back or in another world: off, also while "fighting" (he cannot fight from there)
        self.assertEqual(make_mission.place_at(2955.0, 2955.0, to_spot, False, True), "move")
        self.assertEqual(make_mission.place_at(0.0, float("inf"), to_spot, False, False), "move")

    def test_preston_is_never_offset_twice(self):
        """31 Oct 16:33 (.1.log): with the player about one offset length south-west of them, raiders already moved
        were offset again by MoveOver, to (-3000..-3150, -4500..-4600). PlacePreston's target is fixed, never his own
        position + the offset, so the keeper can never send Preston there (2590549e's keeper could)."""
        psc = read(PSC)
        place = psc[psc.index("bool Function PlacePreston("):psc.index("EndFunction", psc.index("bool Function PlacePreston("))]
        self.assertIn("float tx = PrestonLocalX + MergeOffsetX", place)
        self.assertIn("float ty = PrestonLocalY + MergeOffsetY", place)
        self.assertIn("float tz = PrestonLocalZ", place)
        self.assertNotRegex(place, r"\.GetPosition[XY]\(\) \+ MergeOffset")
        self.assertIn('PlaceAt(Preston, "Preston", tx, ty, tz, player, who, "at the museum door", fighting)', place)
        self.assertIn("a.MoveTo(player, tx - px, ty - py, tz - pz, True, False)", function_body(psc, "PlaceAt"))
        far = (-2011.14 - 1200.0, -1697.54 - 2700.0)                    # MoveOver's second target for him
        self.assertEqual(make_mission.place_at(0.0, 2955.0, math.dist(far, (-2011.14, -1697.54)), False, False),
                         "off, player away")

    def test_script_carries_the_place_rule(self):
        """make_mission.place_at is PlaceAt's decision with its callers' hold, in the same order; PlacePreston and
        PlaceCodsworth both use it, count a move whichever way it ends, and hold (FAL-170: the hold at the spot and after
        a move that lands; the release is the callers', before it)."""
        psc = read(PSC)
        place = function_body(psc, "PlaceAt")
        steps = ["if off <= HoldRadius && dp < RelocateGap", 'return "at spot"',
                 "if player.IsInInterior()", 'return "off, player inside"',
                 "> PlaceRadius * PlaceRadius", 'return "off, player away"',
                 "if dp < RelocateGap && fighting", 'return "off, fighting"',
                 "a.MoveTo(", "bool failed = after > HoldRadius || d >= RelocateGap", 'return "move failed"',
                 'return "placed"']
        at = [place.index(s) for s in steps]
        self.assertEqual(at, sorted(at))
        self.assertIn("Debug.Notification(", place)
        self.assertNotIn("SetRestrained", place)                         # the callers hold (HoldDue)
        self.assertEqual(len(re.findall(r"\.MoveTo\(", psc)), 2)          # PlaceAt's and MoveOver's (the raiders)
        due = function_body(psc, "HoldDue")
        self.assertRegex(due, r"if fighting\s+return False\s+endif\s+"
                              r'return s == "placed" \|\| \(s == "at spot" && !held && off <= HeldRadius\)')
        for who in ("Preston", "Codsworth"):
            wrap = function_body(psc, "Place" + who)
            low = who[0].lower() + who[1:]
            steps = [f"bool fighting = {who}.GetCombatState() != 0",
                     f'string s = PlaceAt({who}, "{who}", tx, ty, tz, player, ',
                     f"{low}Off = SpotOff({who}, tx, ty, tz)",
                     'if s == "placed" || s == "move failed"', f"{low}Moves += 1",
                     f"if HoldDue(s, fighting, {low}Held, {low}Off)", f"Hold{who}(",
                     f"{low}State = HeldState(s, {low}Held)", 'return s == "move failed"']
            at = 0
            for s in steps:                                             # each one after the one before
                at = wrap.index(s, at) + len(s)
            self.assertNotIn(f'{low}State = "', wrap)                    # every state goes through HeldState

    def test_place_radii_follow_the_evidence(self):
        """PlaceRadius below the farthest move that landed in a loaded cell and held (353 m, raider 4, 31 Oct) and so
        below every move that ended with cell=None (488 m on), and above Codsworth's 122 m moves (loaded cell, 31 Oct);
        HoldRadius above FindRadius (finding him is no move)."""
        f = make_mission.script_floats(read(PSC))
        self.assertLess(f["PlaceRadius"], 353.0)
        self.assertGreater(f["PlaceRadius"], 122.0)
        self.assertLess(f["PlaceRadius"], f["RelocateRadius"])
        self.assertGreater(f["HoldRadius"], f["FindRadius"])
        self.assertLess(f["HoldRadius"], f["PlaceRadius"])
        self.assertLess(f["HeldRadius"], f["HoldRadius"])               # FAL-170: held only close to the spot...
        self.assertGreater(f["HeldRadius"], 1.5)                        # ...where the 10 Nov placement landed
        for name in ("PlaceRadius", "HoldRadius", "HeldRadius", "PrestonLocalX", "PrestonLocalY", "PrestonLocalZ",
                     "CodsworthLocalX", "CodsworthLocalY", "CodsworthLocalZ"):
            self.assertNotIn(name, make_mission.mandatory_properties(read(PSC)))   # the plugin is unchanged

    def test_codsworth_spot_is_where_the_moves_put_him(self):
        """FAL-163: every logged move put Codsworth at (-2346.7, -1406.1..-1406.2, 111.7) (23 Oct, playtest row 32; 31 Oct,
        pc-evidence-20261110): his plugin spot (ACHR 0x811 = Fallout 4's 01CA7D, the writer's fixture and the doc's
        table) + the merge offset."""
        f = make_mission.script_floats(read(PSC))
        local = (f["CodsworthLocalX"], f["CodsworthLocalY"], f["CodsworthLocalZ"])
        self.assertEqual(local, (-1146.709, 1293.837, 111.734))
        self.assertIn('"pos": [-1146.709, 1293.837, 111.734]', read(CS))
        self.assertIn("(-1146.709, 1293.837, 111.734) m",
                      read(os.path.join(ROOT, "docs", "mission", "when-freedom-calls.md")))
        merged = (local[0] + f["MergeOffsetX"], local[1] + f["MergeOffsetY"], local[2])
        for a, b in zip(merged, (-2346.7, -1406.15, 111.7)):
            self.assertAlmostEqual(a, b, delta=0.06)

    def test_codsworth_has_prestons_rule(self):
        """FAL-163, the owner's most reported defect ("Codsworth is not at Sanctuary", playtest rows 27, 32, 42): the
        keeper moved him with MoveOver once per session (31 Oct, from 122 m) and never again, and he went back to his
        unmerged spot within about three minutes (29 Oct). He now has Preston's fixed-spot rule (PlaceAt): his own
        fixed target, budget, state variables, load and status lines and on-screen notes; MoveOver is the raiders' only."""
        psc = read(PSC)
        place = function_body(psc, "PlaceCodsworth")
        for line in ("float tx = CodsworthLocalX + MergeOffsetX", "float ty = CodsworthLocalY + MergeOffsetY",
                     "float tz = CodsworthLocalZ"):
            self.assertIn(line, place)
        self.assertNotRegex(place, r"\.GetPosition[XY]\(\) \+ MergeOffset")
        self.assertNotIn("MoveOver(Codsworth", psc)
        self.assertEqual(re.findall(r"if MoveOver\((\w+)", psc), ["Raiders"])
        keep = function_body(psc, "KeepCodsworth")
        self.assertRegex(keep, r"if PlaceCodsworth\(player\)\s+codsworthFails \+= 1\s+if codsworthFails >= 10\s+"
                               r'codsworthState = "gave up"\s+Trace\([^\n]*\n\s+Debug\.Notification\(')
        self.assertRegex(keep, r"if KeeperOnly\s+KeepPreston\(player\)\s+"
                               r"if Codsworth != None && keeperChecks % KeeperStatusEvery == 0\s+"
                               r'TraceCodsworth\("keeper status"\)')
        self.assertNotIn("GetStage", keep + place)                      # after stage 200 too
        load = function_body(psc, "KeepCodsworthLoad")
        tail = load[load.rindex("if Codsworth != None"):]
        self.assertRegex(tail, r'if Codsworth != None\s+TraceCodsworth\("keeper load"\)\s+Debug\.Notification\('
                               r'"FO4SF keeper: Codsworth "')
        self.assertLess(load.index('TraceCodsworth("keeper load")'), load.index("StartTimer(CodsworthCheck, 2)"))
        self.assertIn('TraceSpot(what, Codsworth, "codsworth", codsworthOff, codsworthState, codsworthMoves, '
                      'codsworthHeld, codsworthHolds, codsworthFails)', function_body(psc, "TraceCodsworth"))
        for v in ("int codsworthMoves = 0", "float codsworthOff = -1.0", 'string codsworthState = "none"'):
            self.assertRegex(psc, rf"(?m)^{v}$")                          # sqv FO4SF_CodsworthKeeper shows them

    def test_codsworth_rule_model(self):
        """His rule on the logged numbers (make_mission.place_at, the script's PlaceAt). 31 Oct: moved from 122 m, he
        landed in a loaded cell. A snap-back is caught at the next check once the player is near; from Concord (444 m)
        nothing is moved into an unloaded cell, where MoveOver (800 m) would; a drift under RelocateGap from the player,
        which MoveOver called "already moved", is put back."""
        spot, local = (-2346.709, -1406.163), (-1146.709, 1293.837)
        start, concord = (-2467.7, -1406.9), (-2011.1, -1697.5)          # the walk's start and the museum door

        def decide(codsworth, player, same_world=True, interior=False):
            dp = math.dist(player, codsworth) if same_world else float("inf")
            return make_mission.place_at(math.dist(codsworth, spot), dp, math.dist(player, spot), interior, False)

        self.assertAlmostEqual(math.dist(start, spot), 121.0, delta=1.5)
        self.assertEqual(decide(local, start), "move")                  # unmoved at the start: placed from 121 m
        self.assertEqual(decide(local, start, same_world=False), "move")
        self.assertEqual(decide((-2346.5, -1406.0), start), "at spot, held")   # calm within HeldRadius
        self.assertEqual(decide(local, concord), "off, player away")    # snapped back while the player is at Concord
        self.assertEqual(decide(local, (-2300.0, -1450.0)), "move")     # ...caught when he comes back
        self.assertEqual(decide(local, start, interior=True), "off, player inside")
        drifted = (-2290.0, -1380.0)                                    # 62 m off his spot, 180 m from the player
        self.assertLess(math.dist(drifted, start), 1500.0)              # what MoveOver read as "already there"
        self.assertEqual(decide(drifted, start), "move")

    def test_codsworth_is_held_once_placed(self):
        """FAL-163, the PC's saves of 7 to 9 Nov (save-evidence-20261110): Codsworth heads straight for his editor
        coordinates (heading = bearing within 0.02 degrees) at about 0.34 m/s, so a put-back alone repeats about every
        75 s. With the keeper's check (8.3 s measured on the PC) over 10 minutes: without a hold that holds, 9 put-backs;
        with it, the one at the start. A fight releases him whatever his flag; calm at his spot, he is held again."""
        def put_backs(hold_works, step=8.3, speed=0.34):
            off, held, moves, t = 178.9, False, 0, 0.0                   # 9 Nov 19:49:33: 178.9 m off his spot
            while t < 600.0:
                state = make_mission.place_at(off, off, 120.0, False, False, held=held, landed=True)
                if state.startswith("placed"):
                    off, moves = 0.5, moves + 1
                held = hold_works and state.endswith(", held")
                if not held:
                    off += speed * step                                 # he walks off towards his editor spot
                t += step
            return moves

        self.assertEqual(put_backs(False), 9)
        self.assertEqual(put_backs(True), 1)
        self.assertEqual(make_mission.place_at(0.5, 120.0, 120.0, False, True, held=True), "at spot")     # released
        self.assertEqual(make_mission.place_at(0.5, 120.0, 120.0, False, False, held=False), "at spot, held")

    def test_raiders_are_never_offset_twice(self):
        """31 Oct 16:33:47 (.1.log): with the player at about (-2551, -4055), one offset length south-west of the
        museum, MoveOver moved raiders already at the museum a second time, raider 0 from about (-1950, -1850) to
        (-3150, -4550). A raider's target must lie within RelocateRadius of Preston's merged spot (its unmerged spot is
        within 120 m of his), so a raider already moved is never moved again (FAL-163)."""
        psc = read(PSC)
        move = function_body(psc, "MoveOver")
        guard = ("float hx = x - (PrestonLocalX + MergeOffsetX)", "float hy = y - (PrestonLocalY + MergeOffsetY)",
                 "if hx * hx + hy * hy > RelocateRadius * RelocateRadius")
        for line in guard:
            self.assertIn(line, move)
        self.assertLess(move.index(guard[-1]), move.index("a.MoveTo("))
        self.assertRegex(move, re.escape(guard[-1]) + r"\s+return False")
        f = make_mission.script_floats(psc)
        ox, oy, radius, gap = f["MergeOffsetX"], f["MergeOffsetY"], f["RelocateRadius"], f["RelocateGap"]
        door = (f["PrestonLocalX"] + ox, f["PrestonLocalY"] + oy)

        def moves(raider, player):
            target = (raider[0] + ox, raider[1] + oy)
            return (math.dist(player, raider) >= gap and math.dist(player, target) <= radius
                    and math.dist(target, door) <= radius)

        self.assertTrue(moves((-829.1, 1001.8), (-2011.1, -1697.5)))    # unmerged, player at the door: moved
        moved, far_player = (-1950.0, -1850.0), (-2551.3, -4055.1)
        self.assertTrue(math.dist(far_player, moved) >= gap and
                        math.dist(far_player, (moved[0] + ox, moved[1] + oy)) <= radius)   # what MoveOver did
        self.assertFalse(moves(moved, far_player))                      # now: no second offset
        self.assertFalse(moves((-829.1, 1001.8), far_player))           # and the player is not at its spot

    def test_preston_spot_is_where_the_moves_put_him(self):
        """In game 28 Oct (new game run 3) the moves put Preston at (-2011.14, -1697.54, 89.09): his spot + the merge
        offset must be that point."""
        f = make_mission.script_floats(read(PSC))
        got = (f["PrestonLocalX"] + f["MergeOffsetX"], f["PrestonLocalY"] + f["MergeOffsetY"], f["PrestonLocalZ"])
        for a, b in zip(got, (-2011.14, -1697.54, 89.09)):
            self.assertAlmostEqual(a, b, places=2)

    def test_keeper_state_is_visible_without_a_log(self):
        """FAL-128: both owner tests (7 and 9 Nov) ran with Papyrus logging off, so nothing showed whether the keeper
        ran. Its state is in script variables (sqv FO4SF_CodsworthKeeper) and on screen at each load, each move and a
        spent budget."""
        psc = read(PSC)
        for v in ("int prestonMoves = 0", "float prestonOff = -1.0", 'string prestonState = "none"'):
            self.assertRegex(psc, rf"(?m)^{v}$")
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        load = body("KeepCodsworthLoad")
        self.assertLess(load.index('TracePreston("keeper load")'), load.index("Debug.Notification("))
        self.assertIn("PlaceAt(Preston,", body("PlacePreston"))
        self.assertIn("Debug.Notification(", body("PlaceAt"))         # every move, on screen
        self.assertRegex(body("KeepPreston"), r'prestonState = "gave up"[^\n]*\n(.*\n)*\s+Debug\.Notification\(')
        self.assertIn('" preston_off=" + prestonOff', psc)             # and in the mission's status line

    def test_preston_is_held_after_a_placement(self):
        """FAL-170, in game 10 Nov (f9cae827, the 9 Nov save, logging on): placed 1.5 m off his spot, he walked off at
        about 0.9 m/s, not fighting, and was put back every 29 s. A move that lands holds him in the same call (unless he
        fights); a failed move holds nobody. Only the move is on screen."""
        spot, player = (-2011.14, -1697.54), (-2013.0, -1696.0)
        off = 73.7                                                      # at the load, 10 Nov
        self.assertEqual(make_mission.place_at(off, off, math.dist(player, spot), False, False), "move")
        self.assertEqual(make_mission.place_at(off, off, 2.4, False, False, landed=True), "placed, held")
        self.assertEqual(make_mission.place_at(off, off, 2.4, False, False, landed=False), "move failed")
        self.assertEqual(make_mission.place_at(off, off, 2.4, False, False, held=True, landed=False),
                         "move failed, held")
        # in another world while "fighting": moved, but never held in a fight
        self.assertEqual(make_mission.place_at(0.0, float("inf"), 2.4, False, True, landed=True), "placed")
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        hold = body("HoldActor")
        self.assertIn("bool ok = a.SetRestrained(True)", hold)
        self.assertIn('Trace("hold " + name + " by=" + who + " off=" + off + " ok=" + ok)', hold)
        self.assertEqual(body("PlaceAt").count("Debug.Notification("), 1)   # the move's, as before
        for who in ("Preston", "Codsworth"):                            # FAL-163: the same hold for Codsworth
            low = who.lower()
            mine = body("Hold" + who)
            for step in (f'HoldActor({who}, "{low}", who, {low}Off)', f"{low}Held = True", f"{low}Holds += 1"):
                self.assertIn(step, mine)
            place = body("Place" + who)
            self.assertLess(place.index("PlaceAt("), place.index(f"Hold{who}("))   # in the same call, after the move
            self.assertNotIn("Debug.Notification(", place)
            for v in (f"bool {low}Held = False", f"int {low}Holds = 0"):   # readable with sqv
                self.assertRegex(psc, rf"(?m)^{v}$")
        for name in ("HoldActor", "HoldPreston", "HoldCodsworth", "HoldDue", "ReleaseInFight", "ReleaseCodsworthInFight",
                     "ReleaseActor", "HeldState"):
            self.assertNotIn("Debug.Notification(", body(name), name)
            self.assertNotIn("GetStage", body(name), name)
        self.assertRegex(psc, r"(?m)^float Property HeldRadius = 3\.0 Auto Const$")

    def test_preston_is_held_at_his_spot(self):
        """FAL-170: at his spot, calm, not yet held and within HeldRadius, he is held without a move (a load whose hold
        the engine did not keep, a save where he already stands there). Up to HoldRadius he is left until his put-back,
        which holds him."""
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False), "at spot, held")
        self.assertEqual(make_mission.place_at(3.0, 4.0, 2.4, False, False), "at spot, held")
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False, held=True), "at spot, held")
        self.assertEqual(make_mission.place_at(10.0, 12.0, 2.4, False, False), "at spot")
        self.assertEqual(make_mission.place_at(10.0, 12.0, 2.4, False, False, held=True), "at spot, held")
        self.assertEqual(make_mission.place_at(26.0, 28.0, 2.4, False, False), "move")
        self.assertEqual(make_mission.place_at(1.5, float("inf"), 2.4, False, False), "move")   # another world
        psc = read(PSC)
        trace = function_body(psc, "TraceSpot")
        for field in ('" held=" + held', '" holds=" + holds'):
            self.assertIn(field, trace)
        for who in ("Preston", "Codsworth"):                            # FAL-163: his status line too
            low = who.lower()
            self.assertIn(f"{low}Moves, {low}Held, {low}Holds, {low}Fails)", function_body(psc, "Trace" + who))
        self.assertIn('" preston_off=" + prestonOff + " held=" + prestonHeld', psc)   # the mission's status line
        self.assertRegex(function_body(psc, "HeldState"), r'if held\s+return s \+ ", held"\s+endif\s+return s')

    def test_a_held_preston_is_let_go_in_a_fight(self):
        """FAL-170: never held in a fight (his death stays the quest's failure path). PC review of 79c9ba81: the release
        trusted this instance's prestonHeld, which can be False while he is held. Now both instances let him go on
        every check of a fight, whatever the flag, before PlacePreston, whatever the budget, interior or stage, with one
        log line per fight and instance; held again once calm."""
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, True, held=True), "at spot")
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, True), "at spot")
        self.assertEqual(make_mission.place_at(40.0, 42.0, 2.4, False, True, held=True), "off, fighting")
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False), "at spot, held")   # calm again
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        self.assertRegex(body("ReleaseActor"), r"if a\.GetCombatState\(\) != 0\s+a\.SetRestrained\(False\)\s+"
                                               r"if !logged\s+Trace\(\"release \" \+ name \+ \" by=\" \+ who \+ "
                                               r"\" reason=fighting\"\)\s+endif\s+return True\s+endif\s+return False")
        for who, fn in (("Preston", "ReleaseInFight"), ("Codsworth", "ReleaseCodsworthInFight")):
            low = who.lower()
            self.assertRegex(body(fn), rf'if ReleaseActor\({who}, "{low}", who, {low}Fighting\)\s+{low}Held = False\s+'
                                       rf"{low}Fighting = True\s+return True\s+endif\s+{low}Fighting = False\s+return False")
            self.assertRegex(psc, rf"(?m)^bool {low}Fighting = False$")
        # FAL-163: the keeper releases Codsworth on every check, before his placement and whatever his budget
        self.assertRegex(body("KeepCodsworth"), r'if Codsworth != None\s+ReleaseCodsworthInFight\("keeper"\)\s+endif\s+'
                                                r"if Codsworth != None && codsworthFails < 10\s+if PlaceCodsworth")
        self.assertIn("(Codsworth != None && (codsworthFails < 10 || codsworthHolds > 0))", body("KeepCodsworth"))
        self.assertNotIn("ReleasePreston", psc)
        self.assertNotRegex(psc, r"if prestonHeld &&")                   # no release behind the flag
        self.assertNotIn("ReleaseInFight(\"", body("PlacePreston"))      # the callers release, not PlacePreston
        tick = psc[psc.index("Event OnTimer("):psc.index("EndEvent", psc.index("Event OnTimer("))]
        self.assertRegex(tick, r'KeepCodsworthStart\(\)\s+ReleaseInFight\("mission"\)[^\n]*\s+if relocateFails < 10')
        self.assertRegex(body("KeepPreston"), r'ReleaseInFight\("keeper"\)\s+if prestonFails < 10')
        # the keeper keeps checking with a spent budget once it has held him, so a fight still releases him
        self.assertIn("(KeeperOnly && (prestonFails < 10 || prestonHolds > 0))", body("KeepCodsworth"))
        self.assertRegex(psc, r"(?m)^bool prestonFighting = False$")

    def test_two_instances_a_load_and_a_spent_budget(self):
        """PC review of 79c9ba81, on plain numbers: the engine's restraint is one, the flags are two (mission, keeper).
        Each check of an instance: in a fight SetRestrained(False) whatever its flag (ReleaseInFight), then PlacePreston
        (make_mission.place_preston) unless its budget is spent; a new hold sets the restraint."""
        def check(world, who, fighting, off=1.5, spent=False):
            if fighting:
                world["restrained"] = False                             # ReleaseInFight
                world[who] = False
            if spent:
                return
            state = make_mission.place_at(off, off + 2.0, 2.4, False, fighting, held=world[who], landed=True)
            if state.endswith(", held") and not world[who]:
                world["restrained"] = True                              # HoldPreston
            world[who] = state.endswith(", held")

        # the mission holds him; the keeper's flag stays False until its own check: a fight still releases him
        w = {"restrained": False, "mission": False, "keeper": False}
        check(w, "mission", False)
        self.assertEqual(w, {"restrained": True, "mission": True, "keeper": False})
        check(w, "keeper", True)
        self.assertFalse(w["restrained"])
        # held across a load: the keeper clears its flag, the engine keeps the restraint; after stage 200 only the
        # keeper runs, and a fight releases him
        w = {"restrained": True, "mission": True, "keeper": False}
        check(w, "keeper", True)
        self.assertFalse(w["restrained"])
        # a spent budget: no PlacePreston, the release still runs
        w = {"restrained": True, "mission": False, "keeper": False}
        check(w, "keeper", True, spent=True)
        self.assertFalse(w["restrained"])
        check(w, "keeper", False, spent=True)                           # no hold without PlacePreston
        self.assertFalse(w["restrained"])
        # a hold 3 to 25 m off (a put-back that landed there): out of HeldRadius, still released in a fight
        w = {"restrained": False, "mission": False, "keeper": False}
        check(w, "mission", False, off=60.0)
        self.assertTrue(w["restrained"])
        check(w, "keeper", True, off=10.0)
        self.assertFalse(w["restrained"])

    def test_a_load_holds_him_again(self):
        """FAL-170: the keeper counts Preston as not held at every save load, Codsworth or not, so its first check after
        the load holds him again whatever the engine kept. The mission instance registers no load event, so its flag can
        outlive a load: the keeper's hold and every put-back cover that."""
        psc = read(PSC)
        load = psc[psc.index("Function KeepCodsworthLoad()"):psc.index("EndFunction", psc.index("Function KeepCodsworthLoad()"))]
        self.assertIn("prestonHeld = False", load[load.index("prestonFails = 0"):])       # outside Codsworth's guard
        self.assertLess(load.index("prestonHeld = False"), load.index("StartTimer(CodsworthCheck, 2)"))
        self.assertEqual(psc.count('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")'), 1)   # the keeper's
        guarded = load[load.index("if Codsworth != None"):load.index("prestonFails = 0")]
        self.assertIn("codsworthHeld = False", guarded)                  # FAL-163: Codsworth too
        # held before the save; after the load the flag is False, so the first check at his spot holds him again
        self.assertEqual(make_mission.place_at(1.5, 4.0, 2.4, False, False, held=False), "at spot, held")

    def test_held_preston_is_put_back_once(self):
        """In game 10 Nov: 73.7 m off at the load, placed within a second, then 7 put-backs in 175 s while he walked off
        at about 0.9 m/s; held from the console, none in 100 s and the same position in every line. On plain numbers,
        with the mission's 1 s check: without a hold that holds, 7 put-backs; with it, the one at the load (the PC's check
        3 expects that)."""
        def put_backs(hold_works):
            off, held, moves = 73.7, False, 0
            for _ in range(175):
                state = make_mission.place_at(off, off, 2.4, False, False, held=held, landed=True)
                if state.startswith("placed"):
                    off, moves = 1.5, moves + 1
                held = hold_works and state.endswith(", held")
                if not held:
                    off += 0.9                                          # he walks off
            return moves

        self.assertEqual(put_backs(False), 7)
        self.assertEqual(put_backs(True), 1)

    def test_moves_trace_the_worlds(self):
        """Codex's world-identity point (#353): every move logs the player's and the actor's world before it and the
        actor's world after it, so the anchor gate can be designed from evidence."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        move = psc[psc.index("bool Function MoveOver"):psc.index("Function Trace(")]
        self.assertIn("player.GetWorldSpace()", move)
        self.assertIn("a.GetWorldSpace()", move)
        self.assertLess(move.index('" player="'), move.index("a.MoveTo("))
        self.assertGreater(move.index('" player="'), move.index("RelocateRadius * RelocateRadius"))   # moves only
        self.assertGreater(move.index('" after="'), move.index("a.MoveTo("))

    def test_trace_reopens_the_log_after_a_save_load(self):
        """21 Oct crash runs: OnQuestInit's OpenUserLog does not survive a save load, so the timers ran with no log.
        Trace opens the log itself, right before it writes (a no-op when it is already open)."""
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        trace = psc[psc.index("Function Trace("):]
        trace = trace[:trace.index("EndFunction")]
        lines = [ln.strip() for ln in trace.splitlines()[1:] if ln.strip() and not ln.strip().startswith(";")]
        self.assertEqual(lines[0], "Debug.OpenUserLog(LogName)")
        self.assertTrue(lines[1].startswith("Debug.TraceUser(LogName,"))

    def test_codsworth_is_an_optional_property(self):
        with open(PSC, encoding="utf-8") as f:
            psc = f.read()
        self.assertRegex(psc, r"(?m)^Actor Property Codsworth Auto Const$")
        self.assertNotIn("Codsworth", make_mission.mandatory_properties(psc))


class StageAndInstallTests(unittest.TestCase):
    """Codex review 5563368986: a failed rebuild keeps the earlier stage; the pins are checked before install."""

    SPOT = [-811.14, 1002.46, 89.09]                                    # the script's PrestonLocalX/Y/Z
    CODSWORTH_SPOT = [-1146.709, 1293.837, 111.734]                     # the script's CodsworthLocalX/Y/Z

    def fake_stage(self, d, out, fail_at=None, during_check=None, extra=(), writes=None, preston=None, codsworth=None):
        def fake_run(cmd, cwd=None):
            if "points" in cmd:
                with open(cmd[-1], "w", encoding="utf-8") as f:
                    json.dump({"raiders": [{"src": "046458", "dist_m": 18.9}], "preston": {"pos": preston or self.SPOT},
                               "codsworth": {"src": "01CA7D", "name": "Codsworth", "pos": codsworth or self.CODSWORTH_SPOT,
                                             "rot": [0, 0, 1]}}, f)
            elif "write" in cmd:
                if writes is not None:
                    writes.append(cmd)
                _write(os.path.join(cmd[cmd.index("write") + 5], make_mission.PLUGIN), b"plugin-" + out.encode())
            elif "check" in cmd:
                if writes is not None:
                    writes.append(cmd)
                if during_check:
                    during_check()
                if fail_at == "check":
                    sys.exit("check exit 1")
                return "all checks pass"
            elif "PapyrusCompiler" in cmd[0] or cmd[0] == "compiler":
                _write(os.path.join(cmd[-1][3:], make_mission.SCRIPT + ".pex"), b"pex")
                return "Compilation succeeded"
            return ""
        core, raider = os.path.join(d, "FO4TerrainCore.esm"), os.path.join(d, "FO4ActorRaider.esm")
        for p, b in ((core, b"core"), (raider, b"raider")):
            if not os.path.exists(p):
                _write(p, b)
        zf = os.path.join(d, "cr.zip")
        if not os.path.exists(zf):
            import zipfile
            with zipfile.ZipFile(zf, "w") as z:
                z.writestr("Scripts/Source/Quest.psc", "Scriptname Quest")
                z.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "")
        with mock.patch.object(make_mission, "run", side_effect=fake_run):
            make_mission.main(["stage", "--out", out, "--fo4", "f4", "--starfield", "sf", "--core", core,
                               "--raider", raider, "--compiler", "compiler", "--content-resources", zf, *extra])

    def test_codsworth_is_in_the_plan_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, writes=writes)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertEqual(plan["codsworth"]["src"], "01CA7D")
            self.assertNotIn("--no-codsworth", writes[0])
            self.assertIn("check", writes[1])
            self.assertNotIn("--no-codsworth", writes[1])

    def test_no_codsworth_reaches_the_writer_and_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--no-codsworth"], writes=writes)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertIsNone(plan["codsworth"])
            self.assertIn("--no-codsworth", writes[0])
            self.assertIn("--no-codsworth", writes[1])   # check expects the same mode (Codex review 5564480667)

    def test_codsworth_assets_reach_the_writer_fold_and_verify(self):
        """The Codsworth thread's model (PR #361): stage copies the asset folders (not the report), names the mesh to the
        writer and check, pins each file in the plan; fold carries them and verify catches a changed one."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "codsworth_1018b")
            files = {"meshes/fo4port/actors/codsworth/codsworth.nif": b"nif", "geometries/ab/cd.mesh": b"mesh",
                     "materials/fo4port/texsets/actors/handy/body.mat": b"mat",
                     "textures/fo4port/actors/handy/body_color.dds": b"dds", "codsworth_report.json": b"{}"}
            for rel, b in files.items():
                _write(os.path.join(src, *rel.split("/")), b)
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--codsworth-assets", src], writes=writes)
            for cmd in writes:
                self.assertEqual(cmd[cmd.index("--codsworth-model") + 1], make_mission.CODSWORTH_MESH)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            self.assertEqual(sorted(plan["assets"]), sorted(r for r in files if r != "codsworth_report.json"))
            core_dir = os.path.join(d, "coreset")
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"core")
            folded = os.path.join(d, "folded")
            raider = os.path.join(d, "FO4ActorRaider.esm")
            self.assertEqual(make_mission.main(["fold", "--mission", out, "--core-dir", core_dir, "--out", folded,
                                                "--raider", raider]), 0)
            nif = os.path.join(folded, "Data", "meshes", "fo4port", "actors", "codsworth", "codsworth.nif")
            self.assertTrue(os.path.isfile(nif))
            self.assertFalse(os.path.exists(os.path.join(folded, "Data", "codsworth_report.json")))
            _write(nif, b"other")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", os.path.join(out, "plan.json"),
                                                "--raider", raider]), 1)

    def test_codsworth_voice_reaches_the_writer_and_the_plan(self):
        """His voice (PR #361): each lines.tsv row's <info>_<response>.wem is copied under his voice type's folder, named
        by its WEMFile id; voice.json carries the text and the sex rule ("sir" male, "mum" female) to the writer."""
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "voice")
            rows = [("000F1F6E", "1", "Yes?"), ("000F1F78", "1", "Sir?"), ("000F1F80", "1", "Right away, mum.")]
            os.makedirs(src)
            with open(os.path.join(src, "lines.tsv"), "w", encoding="utf-8", newline="") as f:
                f.write("quest\tsubtype\ttopic\tinfo\tresponse\tvoice\ttext\n")
                for info, resp, text in rows:
                    f.write(f"COMCodsworth\tHELO\tCOMCodsworthHellos\t{info}\t{resp}\tv.fuz\t{text}\n")
                    _write(os.path.join(src, "wem", "Windows", f"{info.lower()}_{resp}.wem"), info.encode())
            out, writes = os.path.join(d, "m"), []
            self.fake_stage(d, out, extra=["--codsworth-voice", src], writes=writes)
            voice_json = writes[0][writes[0].index("--codsworth-voice") + 1]
            self.assertEqual(writes[1][writes[1].index("--codsworth-voice") + 1], voice_json)
            with open(os.path.join(out, "plan.json"), encoding="utf-8") as f:
                plan = json.load(f)
            base = make_mission.VOICE_DIR
            self.assertEqual(sorted(plan["assets"]), [f"{base}/00f4c001.wem", f"{base}/00f4c002.wem", f"{base}/00f4c003.wem"])
            with open(os.path.join(out, "Data", *base.split("/"), "00f4c002.wem"), "rb") as f:
                self.assertEqual(f.read(), b"000F1F78")

    def test_voice_sex_rule_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "voice")
            os.makedirs(src)
            with open(os.path.join(src, "lines.tsv"), "w", encoding="utf-8", newline="") as f:
                f.write("info\tresponse\ttext\nAA\t1\tYes, sir.\nBB\t1\tMum!\nCC\t1\tSirius\n")
            for n in ("aa_1", "bb_1", "cc_1"):
                _write(os.path.join(src, "wem", f"{n}.wem"), b"x")
            vj = os.path.join(d, "voice.json")
            make_mission.copy_voice(src, os.path.join(d, "data"), vj)
            with open(vj, encoding="utf-8") as f:
                self.assertEqual([l["sex"] for l in json.load(f)], ["male", "female", None])
            os.remove(os.path.join(src, "wem", "bb_1.wem"))
            with self.assertRaises(SystemExit):
                make_mission.copy_voice(src, os.path.join(d, "data2"), vj)

    def test_codsworth_assets_need_the_mesh(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "empty")
            os.makedirs(src)
            with self.assertRaises(SystemExit):
                self.fake_stage(d, os.path.join(d, "m"), extra=["--codsworth-assets", src])

    def snapshot(self, root):
        got = {}
        for base, _, files in os.walk(root):
            for n in files:
                p = os.path.join(base, n)
                with open(p, "rb") as f:
                    got[os.path.relpath(p, root)] = f.read()
        return got

    def test_rebuild_into_existing_stage_refused_and_failure_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            first = os.path.join(d, "wfc1")
            self.fake_stage(d, first)
            before = self.snapshot(first)
            self.assertIn("plan.json", before)
            with self.assertRaises(SystemExit):
                self.fake_stage(d, first)                       # occupied output
            self.assertEqual(self.snapshot(first), before)
            second = os.path.join(d, "wfc2")
            with self.assertRaises(SystemExit):
                self.fake_stage(d, second, fail_at="check")     # a failed rebuild publishes nothing
            self.assertFalse(os.path.exists(second))
            self.assertEqual(self.snapshot(first), before)
            # the failed attempt is kept, and a retry neither reuses nor deletes it
            failed = [n for n in os.listdir(d) if n.startswith("wfc2.partial-")]
            self.assertEqual(len(failed), 1)
            _write(os.path.join(d, failed[0], "failed-run.txt"), b"evidence")
            kept = self.snapshot(os.path.join(d, failed[0]))
            with self.assertRaises(SystemExit):
                self.fake_stage(d, second, fail_at="check")
            self.assertEqual(self.snapshot(os.path.join(d, failed[0])), kept)
            self.assertEqual(len([n for n in os.listdir(d) if n.startswith("wfc2.partial-")]), 2)
            self.fake_stage(d, second)                          # and a good retry still publishes
            self.assertTrue(os.path.exists(os.path.join(second, "plan.json")))
            self.assertEqual(self.snapshot(os.path.join(d, failed[0])), kept)

    def test_points_that_moved_preston_are_refused(self):
        """FAL-128: the script keeps Preston at its own PrestonLocalX/Y/Z, so a build whose points put him elsewhere
        would ship a keeper that drags him to the old spot. stage refuses it before the writer runs."""
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            with self.assertRaises(SystemExit) as e:
                self.fake_stage(d, out, writes=writes, preston=[-880.5, 1050.25, 90.0])   # the writer's synthetic spot
            self.assertIn("PrestonLocalX/Y/Z", str(e.exception))
            self.assertEqual(writes, [])
            self.assertFalse(os.path.exists(out))
            self.fake_stage(d, out, preston=[-811.1, 1002.5, 89.1])     # within SPOT_TOLERANCE: staged
            self.assertTrue(os.path.exists(os.path.join(out, "plan.json")))
        psc = read(PSC)
        self.assertIsNone(make_mission.spot_problem(psc, self.SPOT))
        self.assertIsNotNone(make_mission.spot_problem(psc, [-811.14, 1002.46]))           # not a position
        self.assertIsNotNone(make_mission.spot_problem(psc, [-811.14, 1002.46, 90.0]))     # z off by 0.91

    def test_points_that_moved_codsworth_are_refused(self):
        """FAL-163: the same guard for Codsworth's CodsworthLocalX/Y/Z; a --no-codsworth build has no keeper to drag him,
        so it is not refused."""
        with tempfile.TemporaryDirectory() as d:
            out, writes = os.path.join(d, "m"), []
            with self.assertRaises(SystemExit) as e:
                self.fake_stage(d, out, writes=writes, codsworth=[4, 5, 6])
            self.assertIn("CodsworthLocalX/Y/Z", str(e.exception))
            self.assertEqual(writes, [])
            self.assertFalse(os.path.exists(out))
            self.fake_stage(d, out, codsworth=[4, 5, 6], extra=["--no-codsworth"])
            self.assertTrue(os.path.exists(os.path.join(out, "plan.json")))
        psc = read(PSC)
        self.assertIsNone(make_mission.spot_problem(psc, self.CODSWORTH_SPOT, "Codsworth"))
        self.assertIsNotNone(make_mission.spot_problem(psc, self.SPOT, "Codsworth"))

    def test_master_changed_during_build_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            core = os.path.join(d, "FO4TerrainCore.esm")
            _write(core, b"core A")
            out = os.path.join(d, "wfc1")
            with self.assertRaises(SystemExit) as e:
                self.fake_stage(d, out, during_check=lambda: _write(core, b"core B"))
            self.assertIn("changed during the build", str(e.exception))
            self.assertFalse(os.path.exists(out))

    def test_fold_and_verify(self):
        with tempfile.TemporaryDirectory() as d:
            stage = os.path.join(d, "wfc1")
            self.fake_stage(d, stage)
            core_dir = os.path.join(d, "coreset")
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"core")
            _write(os.path.join(core_dir, "Data", "Terrain", "x.btd"), b"btd")
            raider = os.path.join(d, "FO4ActorRaider.esm")
            folded = os.path.join(d, "folded")
            self.assertEqual(make_mission.main(["fold", "--mission", stage, "--core-dir", core_dir, "--out", folded,
                                                "--raider", raider]), 0)
            plan = os.path.join(stage, "plan.json")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 0)
            self.assertTrue(os.path.exists(os.path.join(folded, "Data", "Terrain", "x.btd")))
            # the masters or the staged files changed: verify refuses
            _write(raider, b"other raider")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 1)
            _write(raider, b"raider")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan]), 1)   # raider missing
            _write(os.path.join(folded, "FO4TerrainCore.esm"), b"newer core")
            self.assertEqual(make_mission.main(["verify", "--exp-dir", folded, "--plan", plan, "--raider", raider]), 1)
            # fold against a different core is refused and writes nothing
            _write(os.path.join(core_dir, "FO4TerrainCore.esm"), b"newer core")
            with self.assertRaises(SystemExit):
                make_mission.main(["fold", "--mission", stage, "--core-dir", core_dir, "--out", os.path.join(d, "f2"),
                                   "--raider", raider])
            self.assertFalse(os.path.exists(os.path.join(d, "f2")))
            self.assertFalse(os.path.exists(os.path.join(d, "f2.partial")))


@unittest.skipUnless(shutil.which("dotnet") and os.environ.get("FO4SF_DOTNET_TESTS"),
                     "set FO4SF_DOTNET_TESTS=1 with a dotnet SDK on PATH to run the C# self-test")
class WriterSelfTest(unittest.TestCase):
    def test_selftest(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, DOTNET_ROLL_FORWARD="Major")
            r = subprocess.run(["dotnet", "run", "-c", "Release", "--project", os.path.join(ROOT, "dotnet", "Mission"),
                                "--", "selftest", d], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("selftest pass", r.stdout)


if __name__ == "__main__":
    unittest.main()
