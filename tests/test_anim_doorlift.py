"""The door and lift controls (FAL-489, the Scribe's vault111-gear-door rev 4 section 2c; Claude's request of 12 Nov 21:06 UTC): the script's
ids, stages, calls and events against the writer's (dotnet/AnimDoorLiftControl), the plugin the tool writes and the stage with a fake Papyrus
compiler and synthetic archives (never a game; the real compile, the real Starfield.esm and the real archives are the PC's job). The dotnet tests
skip without the .NET SDK."""
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts" / "newgame"))
sys.path.insert(0, str(ROOT / "scripts" / "planet"))
sys.path.insert(0, str(ROOT / "src"))
import make_anim_doorlift as mad  # noqa: E402
import make_anim_probe as map_  # noqa: E402
import vault111_anim_graphs as graphs  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402
from test_anim_probe import fake_compiler, fake_sources  # noqa: E402

PSC = (ROOT / "scripts" / "newgame" / "FO4SF_AnimDoorLiftQuest.psc").read_text(encoding="utf-8")
TOOL_SRC = (ROOT / "dotnet" / "AnimDoorLiftControl" / "Program.cs").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "research" / "anim-doorlift-control.md").read_text(encoding="utf-8")
PLUGIN = "FO4SFAnimDoorLift.esm"
GRAPH_ENTRY = "Meshes\\AnimTextData\\Tables\\Graphs\\GenericOpenClose01.agx"
ANAM = "AnimTextData\\Tables\\Graphs\\GenericOpenClose01.agx"


def const_ids(text):
    out = {}
    for m in re.finditer(r"const uint ([^;]+);", text):
        for name, val in re.findall(r"(\w+) = (0x[0-9A-Fa-f]+)", m.group(1)):
            out[name] = int(val, 16)
    return out


def strings(prefix, text):
    return [v for _, v in sorted(re.findall(rf'{prefix}\[(\d+)\] = "(\w+)"', text), key=lambda t: int(t[0]))]


class ScriptTests(unittest.TestCase):
    def test_the_scripts_ids_stages_and_log_are_the_tools(self):
        ids = const_ids(TOOL_SRC)
        self.assertEqual((ids["QuestId"], ids["ControlId"], ids["DoorId"], ids["LiftId"]), (0x800, 0x801, 0xAA24A, 0x10C35))
        self.assertIn("int DoorControlId = 0x801", PSC)
        self.assertIn("int LiftId = 0x10C35", PSC)
        self.assertIn(f'string ProbePlugin = "{PLUGIN}"', PSC)
        self.assertIn('string GamePlugin = "Starfield.esm"', PSC)                  # the lift is the vanilla form, not a copy
        self.assertTrue(PSC.startswith("Scriptname FO4SF_AnimDoorLiftQuest extends Quest"))
        self.assertIn('Script = "FO4SF_AnimDoorLiftQuest"', TOOL_SRC)
        ran = [int(s) for s in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        m = re.search(r"Stages = \{ ([\d, ]+) \}", TOOL_SRC)
        self.assertEqual(ran, [int(x) for x in m.group(1).split(",")])
        self.assertEqual(ran, [10, 20, 21, 22, 23, 24, 30, 31, 32, 33, 34, 35, 36, 37, 38, 40, 60])
        self.assertIn(f"new int[{len(ran)}]", PSC)
        self.assertIn('string LogName = "FO4SFAnimDL"', PSC)
        self.assertTrue(mad.LOG.endswith("FO4SFAnimDL.0.log"))
        self.assertIn('" end=true"', PSC)

    def test_the_doc_comment_stays_under_the_repos_papyrus_limit(self):
        i = PSC.index("{")
        j = PSC.index("}", i)
        self.assertLess(len(PSC[i + 1:j].encode()), 3072)                          # tests/test_papyrus_strings.py (the 31 Oct load crash)

    def test_no_property_the_wait_form_is_never_called_and_the_master_is_starfield_only(self):
        self.assertIsNone(re.search(r"^\s*\w+(\[\])?\s+\w+\s+Auto\b", PSC, re.M | re.I))
        code = "\n".join(ln.split(";")[0] for ln in PSC.splitlines() if not ln.startswith(" ") or ln.strip())
        self.assertNotIn("PlayAnimationAndWait", code)
        self.assertIn("masters are not exactly [Starfield.esm]", TOOL_SRC)
        self.assertIn("records of another plugin (overrides)", TOOL_SRC)

    def test_the_calls_are_the_pcs_read_one_per_stage(self):
        """Claude, #755 1bfe5534, 12 Nov 21:15 UTC: door Open, Close, Opened, Closed; lift Stage1, Stage2, Stage1NoTransition, Stage2NoTransition
        and, once, the clip names Stage1Transition / Stage2Transition (not events: expected false); one call per stage."""
        self.assertEqual(strings("DoorCalls", PSC), ["Open", "Close", "Opened", "Closed"])
        self.assertEqual(strings("LiftCalls", PSC), ["Stage1", "Stage2", "Stage1NoTransition", "Stage2NoTransition", "Stage1Transition", "Stage2Transition"])
        self.assertIn("PlayOne(stage, \"door\", DoorRef, DoorCalls[stage - 21])", PSC)             # now inside CallStage, run by the stage's own timer
        self.assertIn("PlayOne(stage, \"lift\", LiftRef, LiftCalls[stage - 31])", PSC)
        self.assertIn("elseif stage >= 21 && stage <= 24", PSC)
        self.assertIn("elseif stage >= 31 && stage <= 36", PSC)
        self.assertIn("new string[6]", PSC)
        self.assertEqual(PSC.count("r.PlayAnimation(n)"), 1)
        self.assertIn("bool ok = r.PlayAnimation(n)", PSC)

    def test_the_registered_events_are_the_pcs_read(self):
        self.assertEqual(strings("DoorEvents", PSC)[:6], ["Opened", "Closed", "Trans01", "Done", "IsOn", "IsOff"])
        # the PC's read of the links (Claude, #755 1bfe5534): TransitionComplete, Stage1, Stage2, Stage1NoTransition, Stage2NoTransition; the last two are called at
        # stages 33 and 34, so an arrival is logged. Stage1Transition / Stage2Transition (35, 36) are clip names, not events: not registered.
        self.assertEqual(strings("LiftEvents", PSC), ["TransitionComplete", "Stage1", "Stage2", "Stage1NoTransition", "Stage2NoTransition"])
        calls = strings("LiftCalls", PSC)
        self.assertEqual((calls[2], calls[3]), ("Stage1NoTransition", "Stage2NoTransition"))              # stages 33 and 34
        for stage_no, name in ((31, "Stage1"), (32, "Stage2"), (33, "Stage1NoTransition"), (34, "Stage2NoTransition")):
            self.assertEqual(calls[stage_no - 31], name)
            self.assertIn(name, strings("LiftEvents", PSC))                                               # every called event name is also registered
        self.assertNotIn("Stage1Transition", strings("LiftEvents", PSC))
        self.assertNotIn("Stage2Transition", strings("LiftEvents", PSC))
        self.assertNotIn("UNREAD here", PSC)                                          # the lift's events are read now
        self.assertIn("RegisterForAnimationEvent(r, n)", PSC)
        for lst in ("DoorEvents", "LiftEvents"):
            self.assertIn(f"new string[{len(strings(lst, PSC))}]", PSC)

    def test_the_lift_is_placed_disabled_and_enabled_only_after_a_move_away_from_the_player(self):
        self.assertIn("LiftRef = p.PlaceAtMe(liftBase, 1, true, true, false)", PSC)    # abInitiallyDisabled = true
        self.assertIn("LiftRef.Enable(false)", PSC)
        self.assertIn("if LiftRef && liftMoved", PSC)                                  # not moved, not enabled: never a platform on the player
        self.assertIn("float LiftAheadM = 2.5", PSC)
        self.assertIn("float LiftSideM = 0.0", PSC)
        self.assertNotIn("LiftM", PSC.replace("LiftMoved", ""))                      # the old 40 m constant is gone
        self.assertIn("p.PlaceAtMe(doorBase, 1, true, false, false)", PSC)
        # the move is an optional native: with no MoveTo the optional lines stay comments and the lift stays disabled
        self.assertEqual(map_.enable(PSC, []), PSC)
        on = map_.enable(PSC, ["ObjectReference.MoveTo"])
        self.assertIn("        LiftRef.MoveTo(p, LiftAheadM * Math.Sin(a) + LiftSideM", on.replace("            ", "        "))
        self.assertEqual(map_.optional_names(PSC), ["ObjectReference.MoveTo", "ObjectReference.EnableNoWait", "ObjectReference.Delete"])

    def test_the_lift_enable_does_not_block_when_the_game_has_a_non_blocking_one(self):
        """PC session 13 Nov: a blocking Enable may never have returned. EnableNoWait is an optional native; the blocking Enable is the fallback only."""
        on = map_.enable(PSC, ["ObjectReference.MoveTo", "ObjectReference.EnableNoWait"])
        self.assertIn("LiftRef.EnableNoWait(false)", on)
        self.assertIn("nowait = true", on)
        self.assertIn("        if !nowait\n            LiftRef.Enable(false)", PSC)             # Enable only when the no-wait call was not kept
        self.assertNotIn("LiftRef.EnableNoWait(false)", PSC.replace(";OPT ObjectReference.EnableNoWait         LiftRef.EnableNoWait(false)", ""))   # only as an optional line

    def test_the_call_timers_do_not_claim_to_isolate_a_hung_call_and_the_step_notices_come_before_the_step_twice(self):
        """FAL-629 hold: a native that never returns keeps the script's one stack, so a one-shot timer per stage cannot isolate it. The script must not say it can;
        the notices before the reading and the call are shown twice (latent wait) BEFORE the step, because nothing repeats them after it starts."""
        step = PSC[PSC.index("Function Step(int stage)"):PSC.index("Function PlayOne(")]
        self.assertEqual(step.count("StartTimer(CALL_DELAY_S, TIMER_CALL + stage)"), 2)
        self.assertLess(PSC.index("aiTimerID == TIMER_RESAY"), PSC.index("aiTimerID >= TIMER_CALL"))       # the id orders: 1, 200, then >= 400, then >= 100
        self.assertLess(PSC.index("aiTimerID >= TIMER_CALL"), PSC.index("aiTimerID >= TIMER_QUIET"))
        self.assertIn("int TIMER_CALL = 400", PSC)
        self.assertIn("DOES NOT ISOLATE A CALL", PSC)
        for claim in ("cannot hold the poll", "so a call that hangs cannot", "cannot hold the poll or the other stages"):
            self.assertNotIn(claim, PSC)
        i = DOC.index("cannot hold the poll")                                                            # the card quotes the retracted claim once, inside its retraction
        self.assertEqual(DOC.count("cannot hold the poll"), 1)
        self.assertIn("that was wrong", DOC[i:i + 120])
        pre = PSC[PSC.index("Function PreNotice("):PSC.index("Function CallStage(")]
        self.assertEqual(pre.count("Say("), 2)
        self.assertLess(pre.index('Trace("notice text=" + msg)'), pre.index("Say(msg)"))                       # in the user log BEFORE the first show (FAL-634)
        self.assertIn("the rule", DOC)
        self.assertIn("does not enforce it", DOC)
        self.assertIn("the script does not enforce it", PSC)
        self.assertNotIn("notice stage=", PSC)                                                              # the header quotes the line the call writes (FAL-636)
        self.assertIn('Trace, "notice text=', PSC)
        self.assertIn("PROVIDED no later stage was set", PSC)
        self.assertIn("provided no later stage was set", DOC)
        self.assertEqual(pre.count("Utility.Wait(1.2)"), 2)
        play = PSC[PSC.index("Function PlayOne("):PSC.index("Function Cleanup()")]
        self.assertEqual(re.findall(r'(PreNotice|SayHold|Say)\("((?:C s|PLAY )[^"]*)', play), [("Say", "C s"), ("PreNotice", "C s"), ("PreNotice", "C s"), ("SayHold", "PLAY ")])        # the first is the early return for a missing reference
        self.assertLess(play.index('" reading")'), play.index('Reading("before"'))                          # a notice BEFORE the reading ...
        self.assertLess(play.index('" calling")'), play.index("r.PlayAnimation(n)"))                         # ... and BEFORE the call
        self.assertLess(play.index("StartTimer(LISTEN_S"), play.index("r.PlayAnimation(n)"))
        self.assertEqual(PSC.count("r.PlayAnimation(n)"), 1)
        self.assertNotIn("PlayAnimationAndWait", PSC)

    def test_the_closing_and_return_notices_are_repeated_and_the_readings_are_on_screen(self):
        """The door's four windows printed no W line in the 13 Nov shots (taken up to 20 s after a 15 s window; one notice had gone), and stage 40 only logged."""
        self.assertIn('SayHold("W s" + stage + " quiet")', PSC)
        self.assertIn('SayHold("W s" + stage + " heard " + WindowEvents)', PSC)
        self.assertIn('SayHold("PLAY " + what', PSC)
        self.assertIn('Say(LastLine + " (again)")', PSC)
        reading = PSC[PSC.index("Function Reading("):PSC.index("Function Spawn(int stage)")]
        self.assertIn('Say("READ s" + stage', reading)
        self.assertIn('if when != "before"', reading)                                                        # the reading before every call stays log-only

    def test_the_lift_3d_is_polled_each_second_with_a_notice_and_a_log_line_and_the_timer_id_cannot_collide(self):
        """PC session 3 (13 Nov 03:15 UTC): every lift reading said 3D=FALSE. Stage 30 now polls Is3DLoaded for LIFT3D_S seconds, one timer tick a second."""
        self.assertIn("float LIFT3D_S = 8.0", PSC)
        self.assertIn("int TIMER_LIFT3D = 500", PSC)
        self.assertLess(PSC.index("aiTimerID == TIMER_LIFT3D"), PSC.index("aiTimerID >= TIMER_CALL"))     # id 500 would else be taken for the call of stage 100
        self.assertLess(PSC.index("aiTimerID == TIMER_RESAY"), PSC.index("aiTimerID == TIMER_LIFT3D"))
        tick = PSC[PSC.index("Function Lift3DTick()"):PSC.index("Function Lift3DLoaded()")]
        self.assertIn("Lift3DRef.Is3DLoaded()", tick)
        self.assertIn('Trace("lift3d "', tick)
        self.assertIn("Say(line)", tick)
        self.assertIn("StartTimer(1.0, TIMER_LIFT3D)", tick)
        self.assertEqual(PSC.count("Is3DLoaded()"), PSC.count(".Is3DLoaded()"))                           # always on a reference
        lift = PSC[PSC.index("Function SpawnLift(int stage)"):PSC.index("; ---------------------------------------------------------------- poll and steps")]
        self.assertLess(lift.index('RegisterList(stage, "lift"'), lift.index('Lift3DStart("s30", LiftRef)'))    # the poll starts after the registration
        self.assertLess(lift.index('Lift3DStart("s30", LiftRef)'), lift.index('Say("S30 done")'))

    def test_the_two_retries_are_stages_37_and_38_with_the_blocking_enable_and_a_second_lift_placed_enabled(self):
        step = PSC[PSC.index("Function Step(int stage)"):PSC.index("Function CallStage(")]
        self.assertIn("elseif stage == 37\n        LiftRetryEnable(stage)", step)
        self.assertIn("elseif stage == 38\n        LiftPlaceEnabled(stage)", step)
        retry = PSC[PSC.index("Function LiftRetryEnable("):PSC.index("Function LiftPlaceEnabled(")]
        self.assertLess(retry.index('PreNotice("S37 enable (blocking) calling")'), retry.index("LiftRef.Enable(false)"))   # a notice BEFORE the call that may block
        self.assertNotIn("EnableNoWait", retry.split("}", 1)[1])
        self.assertLess(retry.index("LiftRef.Enable(false)"), retry.index('Lift3DStart("s37", LiftRef)'))
        place = PSC[PSC.index("Function LiftPlaceEnabled("):PSC.index("Function Cleanup()")]
        self.assertIn("LiftRef2 = p.PlaceAtMe(liftBase, 1, true, false, false)", place)                   # abInitiallyDisabled = false
        code = place.split("}", 1)[1]                                                                        # the code, not the doc comment that names what it does not use
        self.assertNotIn("EnableNoWait", code)
        self.assertNotIn(".Enable(", code)
        self.assertLess(place.index("PlaceAtMe"), place.index('Lift3DStart("s38", LiftRef2)'))
        loaded = PSC[PSC.index("Function Lift3DLoaded()"):PSC.index("Function LiftRetryEnable(")]
        self.assertIn('Lift3DWhat == "s38"', loaded)                                                         # only the second lift is adopted
        self.assertLess(loaded.index("LiftRef.Disable(false)"), loaded.index("LiftRef = Lift3DRef"))         # the first one is disabled before it is replaced
        cleanup = PSC[PSC.index("Function Cleanup()"):]
        self.assertIn("LiftRef2.Disable(false)", cleanup)
        self.assertIn("LiftRef2 = None", cleanup)
        self.assertIn("if LiftRef2 && LiftRef2 != LiftRef", cleanup)                                          # an adopted lift is not disabled twice

    def test_the_staged_readme_does_not_say_where_an_old_head_put_the_lift(self):
        src = (ROOT / "scripts" / "newgame" / "make_anim_doorlift.py").read_text(encoding="utf-8")
        self.assertNotIn("5 m ahead and 3 m to the right", src)                                              # stale since the lift moved to 2.5 m (FAL-489)
        self.assertIn("2.5 m ahead of the player", src)
        self.assertIn("lift_model", src)

    def test_the_door_is_placed_and_registered_before_the_lift_is_touched_and_every_step_says_so(self):
        """The 13 Nov session was silent after stage 10: a notice at the start and after each step, the door first, the lift in its own stage 30."""
        spawn = PSC[PSC.index("Function Spawn(int stage)"):PSC.index("Function SpawnLift(int stage)")]
        lift = PSC[PSC.index("Function SpawnLift(int stage)"):PSC.index("; ---------------------------------------------------------------- poll and steps")]
        self.assertNotIn("Lift", spawn.split("{", 1)[1].split("}", 1)[1])                # stage 10 never touches the lift (outside its doc comment)
        self.assertEqual(re.findall(r'Say\("(S10 [a-z ]+)', spawn), ["S10 start", "S10 door base none", "S10 door placed", "S10 door moved", "S10 done"])
        self.assertLess(spawn.index("PlaceAtMe"), spawn.index("RegisterList(stage, \"door\""))
        self.assertEqual(re.findall(r'Say\("(S30 [a-z() ]+)', lift), ["S30 start", "S30 lift base none", "S30 lift placed (disabled)", "S30 lift moved", "S30 lift enabled nowait", "S30 done"])
        self.assertLess(lift.index("PlaceAtMe"), lift.index("Say(\"S30 lift moved="))                    # the order: placed, moved, enabled, registered
        self.assertLess(lift.index("Say(\"S30 lift moved="), lift.index("LiftRef.Enable(false)"))
        self.assertLess(lift.index("LiftRef.Enable(false)"), lift.index("RegisterList(stage, \"lift\""))
        self.assertIn("elseif stage == 30\n        SpawnLift(stage)", PSC)
        self.assertEqual(PSC.count("Spawn(stage)"), 1)

    def test_every_play_and_event_line_names_which_reference(self):
        self.assertIn('" label=" + Label(akSource)', PSC)
        self.assertIn("label=door base=", PSC)
        self.assertIn("label=lift base=", PSC)
        self.assertIn('"play stage=" + stage + " label=" + what', PSC)

    def test_the_log_reader_takes_the_scripts_lines(self):
        """A session as the script would write it: both refs spawned, a door call true with events, a lift call false."""
        lines = [
            "FO4SFANIM rt=1.0 init version=1 end=true",
            "FO4SFANIM rt=2.0 spawn stage=10 label=door base=1 ref=11 moved=true persist=true end=true",
            "FO4SFANIM rt=2.0 spawn stage=10 label=lift base=2 ref=12 moved=true enabled=true persist=true end=true",
            "FO4SFANIM rt=3.0 register stage=10 label=door name=Open ref=11 ok=true end=true",
            "FO4SFANIM rt=4.0 play stage=21 label=door name=Open ref=11 ok=true end=true",
            "FO4SFANIM rt=5.0 event name=Done label=door src=11 stage=21 since=1.0 end=true",
            "FO4SFANIM rt=6.0 play stage=31 label=lift name=Stage1 ref=12 ok=false end=true",
        ]
        s = map_.anim_probe_log.summarize(lines)
        self.assertEqual(s["spawned"], 11)
        self.assertEqual(s["verdict"][0], "EVENTS ARRIVE")

    def test_the_committed_script_compiles_alone_every_optional_and_void_line_is_a_comment(self):
        self.assertEqual(len(map_.VOID.findall(PSC)), 2)
        self.assertIn(map_.BOOL_LINE, PSC)


class ToolBase(unittest.TestCase):
    """The built tool and a synthetic Starfield.esm; no tests of its own."""
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet") or (str(Path.home() / ".dotnet" / "dotnet") if (Path.home() / ".dotnet" / "dotnet").exists() else None)
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        proc = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet" / "AnimDoorLiftControl"), "-c", "Release", "--nologo"], capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.tool = ROOT / "dotnet/AnimDoorLiftControl/bin/Release/net9.0/AnimDoorLiftControl.dll"
        tmp = tempfile.TemporaryDirectory(prefix="fo4sf-animdl-")
        cls.addClassCleanup(tmp.cleanup)
        cls.root = Path(tmp.name)
        cls.master = cls.root / "m" / "Starfield.esm"
        r = cls.run_tool("fixture", cls.root / "m")
        assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)


class ToolTests(ToolBase):
    def test_info_names_the_door_and_the_lift(self):
        info = mad.parse_info(self.run_tool("info", self.master).stdout)
        self.assertEqual(info["door_edid"], "AK_Ext_Bld_WallA_DoorA_01_Alt02")
        self.assertTrue(info["door_anam"].lower().endswith("simpleopenclose01.agx"))
        self.assertEqual(info["door_cnam"], "Architecture\\Doors\\Animations")
        self.assertEqual((info["lift_type"], info["lift_edid"]), ("ACTI", "ShipQuickLift1"))
        self.assertEqual(info["lift_names_twostages"], "True")

    def test_build_and_check(self):
        out = self.root / "b1"
        proc = self.run_tool("build", self.master, out, ANAM)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        check = self.run_tool("check", out / PLUGIN, self.master, ANAM)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("masters [Starfield.esm]", check.stdout)
        self.assertIn("scripts [FO4SF_AnimDoorLiftQuest (0 properties)]", check.stdout)
        slashed = check.stdout.replace("\\", "/")                                    # the tool prints with the OS separator (backslashes on Windows)
        want = (f"ACTI FO4SF_AnimDoorControl model Meshes/Architecture/Doors/WallA_DoorA_01.nif components 1 graph ANAM {ANAM} "
                f"BNAM Architecture\\Doors\\CharacterAssets\\skeleton.rig CNAM Architecture\\Doors\\Animations").replace("\\", "/")
        self.assertIn(want, slashed)                                                   # the door's model, rig and folder; our graph
        self.assertIn("all checks pass", check.stdout)

    def test_the_control_keeps_the_doors_dnam_and_enam(self):
        """The same flaw as the Courier's FAL-579 hold on the generic control: the door's whole component is copied and only ANAM changes; check
        fails when DNAM differs from the vanilla door's."""
        info = mad.parse_info(self.run_tool("info", self.master).stdout)
        self.assertEqual((info["door_dnam"], info["door_enam"]), ("Architecture\\Doors\\DNAM-KEPT", "Architecture\\Doors\\ENAM-KEPT"))
        out = self.root / "b7"
        self.assertEqual(self.run_tool("build", self.master, out, ANAM).returncode, 0)
        slashed = self.run_tool("check", out / PLUGIN, self.master, ANAM).stdout.replace("\\", "/")
        self.assertIn("DNAM Architecture/Doors/DNAM-KEPT ENAM Architecture/Doors/ENAM-KEPT", slashed)
        other = self.root / "o2"
        other.mkdir()
        raw = bytearray(self.master.read_bytes())
        i = raw.find(b"DNAM-KEPT")
        self.assertGreater(i, 0)
        raw[i:i + 9] = b"DNAM-DIFF"
        (other / "Starfield.esm").write_bytes(bytes(raw))
        proc = self.run_tool("check", out / PLUGIN, other / "Starfield.esm", ANAM)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertIn("DNAM is ", proc.stdout)

    def test_the_plugin_adds_one_quest_and_one_acti_and_no_door_or_override(self):
        out = self.root / "b2"
        self.assertEqual(self.run_tool("build", self.master, out, ANAM).returncode, 0)
        data = (out / PLUGIN).read_bytes()
        self.assertEqual(data[:4], b"TES4")
        kinds, ids = {}, []

        def walk(buf, i, end):
            while i < end:
                sig = buf[i:i + 4]
                size = struct.unpack_from("<I", buf, i + 4)[0]
                if sig == b"GRUP":
                    walk(buf, i + 24, i + size)
                    i += size
                    continue
                kinds[sig] = kinds.get(sig, 0) + 1
                if sig != b"TES4":
                    ids.append(struct.unpack_from("<I", buf, i + 12)[0])
                i += 24 + size
        walk(data, 0, len(data))
        self.assertEqual({k: v for k, v in kinds.items() if k != b"TES4"}, {b"QUST": 1, b"ACTI": 1})       # the vanilla DOOR is not copied or overridden
        self.assertEqual(sorted(ids), [0x01000800, 0x01000801])

    def test_the_vanilla_door_graph_is_refused_as_the_control_graph(self):
        proc = self.run_tool("build", self.master, self.root / "b3", "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("is not genericopenclose01", proc.stderr)
        self.assertFalse((self.root / "b3").exists())

    def test_a_door_whose_graph_is_not_simpleopenclose01_is_refused(self):
        other = self.root / "o"
        other.mkdir()
        raw = bytearray(self.master.read_bytes())
        i = raw.find(b"SimpleOpenClose01")
        self.assertGreater(i, 0)
        raw[i:i + len(b"SimpleOpenClose01")] = b"SimpleOpenCloseXX"
        (other / "Starfield.esm").write_bytes(bytes(raw))
        proc = self.run_tool("build", other / "Starfield.esm", self.root / "b5", ANAM)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("not simpleopenclose01", proc.stderr)


class StageTests(ToolBase):
    """The whole stage on a synthetic Starfield.esm, a synthetic archive next to it and the fake compiler."""
    def data_dir(self, name, graph=True):
        d = self.root / name
        d.mkdir()
        shutil.copy(self.master, d / "Starfield.esm")
        files = {GRAPH_ENTRY: b"<root/>"} if graph else {"Meshes\\Other.agx": b"<root/>"}
        (d / "Starfield - Animations.ba2").write_bytes(general_archive(files))
        (d / "Starfield - Meshes01.ba2").write_bytes(general_archive({"Meshes\\x.nif": b"n"}))
        return d

    def args(self, out, d, extra=()):
        z = self.root / (Path(out).name + "-cr.zip")
        fake_sources(z)
        return ["stage", "--out", str(out), "--starfield", str(d / "Starfield.esm"), "--compiler", str(fake_compiler(self.root)),
                "--content-resources", str(z), *extra]

    def test_stage_builds_compiles_and_pins_every_file(self):
        d = self.data_dir("d1")
        out = self.root / "staged"
        self.assertEqual(mad.main(self.args(out, d)), 0)
        plan = json.loads((out / "plan.json").read_text())
        self.assertEqual((plan["kind"], plan["plugins"]), ("anim-doorlift", [PLUGIN]))
        self.assertEqual(plan["graph"], {"anam": ANAM, "archive_entry": GRAPH_ENTRY})
        self.assertEqual(plan["vanilla"]["lift_edid"], "ShipQuickLift1")
        self.assertEqual(set(plan["outputs"]), {PLUGIN, "Data/Scripts/FO4SF_AnimDoorLiftQuest.pex"})        # no clip, no game asset
        self.assertEqual(plan["inputs"]["Starfield.esm"]["sha256"], mad.sha256(str(d / "Starfield.esm")))
        self.assertEqual(mad.verify_stage(str(out), plan, str(d)), [])
        self.assertIn("all checks pass", (out / "offline_check.txt").read_text())
        readme = (out / "README.txt").read_text()
        self.assertIn(ANAM, readme)
        self.assertIn("MOVING PLATFORM", readme)
        self.assertIn("ShipQuickLift1", readme)
        # the staged README's stage list is the quest's (the Courier's FAL-588 hold: it said 31..34 while the quest also ran 35 and 36)
        m = re.search(r"stages ([\d. ]+?):", readme)
        self.assertIsNotNone(m, readme[:400])
        self.assertEqual(m.group(1), mad.stage_list(PSC))
        self.assertEqual(m.group(1), "10 20..24 30..38 40 60")
        ran = [int(x) for x in re.findall(r"StageList\[\d+\] = (\d+)", PSC)]
        expanded = []
        for tok in m.group(1).split():
            lo, _, hi = tok.partition("..")
            expanded += list(range(int(lo), int(hi or lo) + 1))
        self.assertEqual(expanded, ran)                                                                  # the README's text expands to the quest's stages
        tool_stages = re.search(r"QUST FO4SF_AnimDoorLiftQuest stages \[([\d,]+)\]", (out / "offline_check.txt").read_text())
        self.assertEqual([int(x) for x in tool_stages.group(1).split(",")], ran)                         # and to what the tool wrote into the plugin
        with self.assertRaises(SystemExit):                                                              # an earlier stage is never overwritten
            mad.main(self.args(out, d))

    def test_stage_list_compresses_runs_and_leaves_pairs_and_singles(self):
        text = "".join(f"StageList[{i}] = {n}\n" for i, n in enumerate([10, 20, 21, 22, 23, 24, 31, 32, 40, 41, 42, 60]))
        self.assertEqual(mad.stage_list(text), "10 20..24 31 32 40..42 60")

    def test_a_missing_graph_stops_the_stage_with_the_archive_to_pass(self):
        d = self.data_dir("d2", graph=False)
        out = self.root / "staged-nograph"
        with self.assertRaises(SystemExit) as ctx:
            mad.main(self.args(out, d))
        self.assertIn("genericopenclose01.agx is not in the archives read", str(ctx.exception))
        self.assertIn("Starfield - Animations.ba2", str(ctx.exception))
        self.assertFalse(out.exists())

    def test_a_changed_stage_is_refused_by_verify(self):
        d = self.data_dir("d3")
        out = self.root / "staged-v"
        mad.main(self.args(out, d))
        plan = json.loads((out / "plan.json").read_text())
        with open(out / PLUGIN, "ab") as f:
            f.write(b"!")
        self.assertIn("changed after the stage", " ".join(mad.verify_stage(str(out), plan)))
        self.assertIn("is not the door and lift control's", " ".join(mad.verify_stage(str(out), dict(plan, kind="anim-generic"))))

    def test_no_archive_matching_the_pattern_is_said(self):
        d = self.data_dir("d4")
        with self.assertRaises(SystemExit) as ctx:
            mad.main(self.args(self.root / "staged-noarc", d, ["--game-archive", "Nothing*.ba2"]))
        self.assertIn("no archive matched", str(ctx.exception))

    def test_log_command_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "log.txt")
            self.assertEqual(mad.main(["log", "--file", f]), 2)
            Path(f).write_text("[11/12/2026 - 06:00:00AM] FO4SFANIM rt=1.0 spawn stage=10 label=door base=77 ref=99 moved=true persist=true end=true\n", encoding="utf-8")
            self.assertEqual(mad.main(["log", "--file", f]), 0)
            Path(f).write_text("nothing here\n", encoding="utf-8")
            self.assertEqual(mad.main(["log", "--file", f]), 1)

    def test_the_precheck_runs_on_the_door_lift_script(self):
        z = self.root / "cr-pre.zip"
        fake_sources(z)
        out = self.root / "pre.json"
        self.assertEqual(mad.main(["precheck", "--content-resources", str(z), "--out", str(out)]), 0)
        r = json.loads(out.read_text())
        self.assertEqual(r["missing"], [])
        self.assertEqual(r["optional"], {"ObjectReference.MoveTo": True, "ObjectReference.EnableNoWait": False, "ObjectReference.Delete": True})   # the fixture base declares no EnableNoWait: the blocking Enable stays


if __name__ == "__main__":
    unittest.main()
