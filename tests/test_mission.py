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
        self.assertRegex(keep, r"if \(Codsworth != None && codsworthFails < 10\) \|\| "
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
        self.assertRegex(keep, r"if Codsworth != None && codsworthFails < 10 && !player\.IsInInterior\(\)\s+"
                               r"if MoveOver\(Codsworth,")

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
        trace = body("TracePreston")
        for field in ('" preston d="', '" off="', '" state="', '" moves="', '" disabled="', '" dead="', '" fails="',
                      '" player="', '" interior="'):
            self.assertIn(field, trace)
        # the keeper quest carries the mission's properties, Preston among them (no new plugin record)
        cs = read(CS)
        keeper = cs[cs.index("var ks = new SF.ScriptEntry"):cs.index("keeper.VirtualMachineAdapter")]
        self.assertIn("MissionProps(ks);", keeper)
        self.assertIn('Obj("Preston", prestonRef.FormKey)', cs[cs.index("void MissionProps("):cs.index("MissionProps(script);")])

    def test_keeper_rule_model_after_the_mission(self):
        """The keeper's rule on plain numbers, after stage 200, with make_mission.place_preston (the script's
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
            if make_mission.place_preston(off, dp, math.dist(player, spot), not outdoors, False) == "move":
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
        self.assertEqual(make_mission.place_preston(off, dp, to_spot, False, False), "move")
        self.assertEqual(make_mission.place_preston(off, dp, to_spot, False, True), "off, fighting")
        self.assertEqual(make_mission.place_preston(off, dp, to_spot, True, False), "off, player inside")
        self.assertEqual(make_mission.place_preston(off, dp, 544.4, False, False), "off, player away")   # cell=None range
        self.assertEqual(make_mission.place_preston(10.0, 9.0, to_spot, False, False), "at spot")
        # snapped back or in another world: off, also while "fighting" (he cannot fight from there)
        self.assertEqual(make_mission.place_preston(2955.0, 2955.0, to_spot, False, True), "move")
        self.assertEqual(make_mission.place_preston(0.0, float("inf"), to_spot, False, False), "move")

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
        self.assertIn("Preston.MoveTo(player, tx - px, ty - py, tz - pz, True, False)", place)
        far = (-2011.14 - 1200.0, -1697.54 - 2700.0)                    # MoveOver's second target for him
        self.assertEqual(make_mission.place_preston(0.0, 2955.0, math.dist(far, (-2011.14, -1697.54)), False, False),
                         "off, player away")

    def test_script_carries_the_place_rule(self):
        """make_mission.place_preston is PlacePreston's decision, in the same order (FAL-170: the hold at the spot and
        after a move that lands; the release is the callers', before it)."""
        psc = read(PSC)
        place = psc[psc.index("bool Function PlacePreston("):psc.index("EndFunction", psc.index("bool Function PlacePreston("))]
        steps = ["bool fighting = Preston.GetCombatState() != 0",
                 "if prestonOff <= HoldRadius && dp < RelocateGap",
                 "if !prestonHeld && !fighting && prestonOff <= HeldRadius", "HoldPreston(who)",
                 'SetPrestonState("at spot")',
                 "if player.IsInInterior()", 'SetPrestonState("off, player inside")',
                 "> PlaceRadius * PlaceRadius", 'SetPrestonState("off, player away")',
                 "if dp < RelocateGap && fighting", 'SetPrestonState("off, fighting")',
                 "Preston.MoveTo(", "bool failed = off > HoldRadius || d >= RelocateGap", "prestonOff = off",
                 'SetPrestonState("move failed")', "if !fighting", "HoldPreston(who)", 'SetPrestonState("placed")']
        at = 0
        for s in steps:                                                 # each one after the one before
            at = place.index(s, at) + len(s)
        self.assertIn("prestonMoves += 1", place)
        self.assertNotIn("prestonState = ", place)                      # every state goes through SetPrestonState

    def test_place_radii_follow_the_evidence(self):
        """PlaceRadius below the farthest move that landed in a loaded cell and held (353 m, raider 4, 31 Oct) and so
        below every move that ended with cell=None (488 m on); HoldRadius above FindRadius (finding him is no move)."""
        f = make_mission.script_floats(read(PSC))
        self.assertLess(f["PlaceRadius"], 353.0)
        self.assertLess(f["PlaceRadius"], f["RelocateRadius"])
        self.assertGreater(f["HoldRadius"], f["FindRadius"])
        self.assertLess(f["HoldRadius"], f["PlaceRadius"])
        self.assertLess(f["HeldRadius"], f["HoldRadius"])               # FAL-170: held only close to the spot...
        self.assertGreater(f["HeldRadius"], 1.5)                        # ...where the 10 Nov placement landed
        for name in ("PlaceRadius", "HoldRadius", "HeldRadius", "PrestonLocalX", "PrestonLocalY", "PrestonLocalZ"):
            self.assertNotIn(name, make_mission.mandatory_properties(read(PSC)))   # the plugin is unchanged

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
        self.assertIn("Debug.Notification(", body("PlacePreston"))
        self.assertRegex(body("KeepPreston"), r'prestonState = "gave up"[^\n]*\n(.*\n)*\s+Debug\.Notification\(')
        self.assertIn('" preston_off=" + prestonOff', psc)             # and in the mission's status line

    def test_preston_is_held_after_a_placement(self):
        """FAL-170, in game 10 Nov (f9cae827, the 9 Nov save, logging on): placed 1.5 m off his spot, he walked off at
        about 0.9 m/s, not fighting, and was put back every 29 s. A move that lands holds him in the same call (unless he
        fights); a failed move holds nobody. Only the move is on screen."""
        spot, player = (-2011.14, -1697.54), (-2013.0, -1696.0)
        off = 73.7                                                      # at the load, 10 Nov
        self.assertEqual(make_mission.place_preston(off, off, math.dist(player, spot), False, False), "move")
        self.assertEqual(make_mission.place_preston(off, off, 2.4, False, False, landed=True), "placed, held")
        self.assertEqual(make_mission.place_preston(off, off, 2.4, False, False, landed=False), "move failed")
        self.assertEqual(make_mission.place_preston(off, off, 2.4, False, False, held=True, landed=False),
                         "move failed, held")
        # in another world while "fighting": moved, but never held in a fight
        self.assertEqual(make_mission.place_preston(0.0, float("inf"), 2.4, False, True, landed=True), "placed")
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        hold = body("HoldPreston")
        self.assertIn("bool ok = Preston.SetRestrained(True)", hold)
        for step in ("prestonHeld = True", "prestonHolds += 1", 'Trace("hold preston by=" + who + " off=" + prestonOff + " ok=" + ok)'):
            self.assertIn(step, hold)
        place = body("PlacePreston")
        self.assertLess(place.index("Debug.Notification("), place.rindex("HoldPreston(who)"))
        self.assertEqual(place.count("Debug.Notification("), 1)         # the move's, as before
        for name in ("HoldPreston", "ReleaseInFight", "SetPrestonState"):
            self.assertNotIn("Debug.Notification(", body(name), name)
            self.assertNotIn("GetStage", body(name), name)
        for v in ("bool prestonHeld = False", "int prestonHolds = 0"):   # readable with sqv
            self.assertRegex(psc, rf"(?m)^{v}$")
        self.assertRegex(psc, r"(?m)^float Property HeldRadius = 3\.0 Auto Const$")

    def test_preston_is_held_at_his_spot(self):
        """FAL-170: at his spot, calm, not yet held and within HeldRadius, he is held without a move (a load whose hold
        the engine did not keep, a save where he already stands there). Up to HoldRadius he is left until his put-back,
        which holds him."""
        self.assertEqual(make_mission.place_preston(1.5, 4.0, 2.4, False, False), "at spot, held")
        self.assertEqual(make_mission.place_preston(3.0, 4.0, 2.4, False, False), "at spot, held")
        self.assertEqual(make_mission.place_preston(1.5, 4.0, 2.4, False, False, held=True), "at spot, held")
        self.assertEqual(make_mission.place_preston(10.0, 12.0, 2.4, False, False), "at spot")
        self.assertEqual(make_mission.place_preston(10.0, 12.0, 2.4, False, False, held=True), "at spot, held")
        self.assertEqual(make_mission.place_preston(26.0, 28.0, 2.4, False, False), "move")
        self.assertEqual(make_mission.place_preston(1.5, float("inf"), 2.4, False, False), "move")   # another world
        psc = read(PSC)
        trace = psc[psc.index("Function TracePreston("):psc.index("EndFunction", psc.index("Function TracePreston("))]
        for field in ('" held=" + prestonHeld', '" holds=" + prestonHolds'):
            self.assertIn(field, trace)
        self.assertIn('" preston_off=" + prestonOff + " held=" + prestonHeld', psc)   # the mission's status line
        state = psc[psc.index("Function SetPrestonState("):psc.index("EndFunction", psc.index("Function SetPrestonState("))]
        self.assertRegex(state, r'if prestonHeld\s+prestonState = s \+ ", held"\s+else\s+prestonState = s')

    def test_a_held_preston_is_let_go_in_a_fight(self):
        """FAL-170: never held in a fight (his death stays the quest's failure path). PC review of 79c9ba81: the release
        trusted this instance's prestonHeld, which can be False while he is held. Now both instances let him go on
        every check of a fight, whatever the flag, before PlacePreston, whatever the budget, interior or stage, with one
        log line per fight and instance; held again once calm."""
        self.assertEqual(make_mission.place_preston(1.5, 4.0, 2.4, False, True, held=True), "at spot")
        self.assertEqual(make_mission.place_preston(1.5, 4.0, 2.4, False, True), "at spot")
        self.assertEqual(make_mission.place_preston(40.0, 42.0, 2.4, False, True, held=True), "off, fighting")
        self.assertEqual(make_mission.place_preston(1.5, 4.0, 2.4, False, False), "at spot, held")   # calm again
        psc = read(PSC)
        body = lambda name: psc[psc.index(f"Function {name}("):psc.index("EndFunction", psc.index(f"Function {name}("))]
        release = body("ReleaseInFight")
        self.assertRegex(release, r"if Preston\.GetCombatState\(\) != 0\s+Preston\.SetRestrained\(False\)\s+"
                                  r"prestonHeld = False\s+if !prestonFighting\s+prestonFighting = True\s+"
                                  r"Trace\(\"release preston by=\" \+ who \+ \" reason=fighting\"\)\s+endif\s+"
                                  r"return True\s+endif\s+prestonFighting = False\s+return False")
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
            state = make_mission.place_preston(off, off + 2.0, 2.4, False, fighting, held=world[who], landed=True)
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
        # held before the save; after the load the flag is False, so the first check at his spot holds him again
        self.assertEqual(make_mission.place_preston(1.5, 4.0, 2.4, False, False, held=False), "at spot, held")

    def test_held_preston_is_put_back_once(self):
        """In game 10 Nov: 73.7 m off at the load, placed within a second, then 7 put-backs in 175 s while he walked off
        at about 0.9 m/s; held from the console, none in 100 s and the same position in every line. On plain numbers,
        with the mission's 1 s check: without a hold that holds, 7 put-backs; with it, the one at the load (the PC's check
        3 expects that)."""
        def put_backs(hold_works):
            off, held, moves = 73.7, False, 0
            for _ in range(175):
                state = make_mission.place_preston(off, off, 2.4, False, False, held=held, landed=True)
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

    def fake_stage(self, d, out, fail_at=None, during_check=None, extra=(), writes=None, preston=None):
        def fake_run(cmd, cwd=None):
            if "points" in cmd:
                with open(cmd[-1], "w", encoding="utf-8") as f:
                    json.dump({"raiders": [{"src": "046458", "dist_m": 18.9}], "preston": {"pos": preston or self.SPOT},
                               "codsworth": {"src": "01CA7D", "name": "Codsworth", "pos": [4, 5, 6], "rot": [0, 0, 1]}}, f)
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
