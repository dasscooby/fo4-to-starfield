"""snapshot.ps1: the owner's "look": a screenshot, the bridge's newest line and the log tail, nothing sent to the game."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "game", "snapshot.ps1")


@unittest.skipUnless(os.name == "nt", "PowerShell and the screen: Windows only")
class SnapshotTests(unittest.TestCase):
    def test_a_failed_capture_never_leaves_a_stale_screen(self):
        # Codex's review of #175: a reused folder held the previous screen.png; the capture's exit code was ignored
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            os.makedirs(out)
            open(os.path.join(out, "screen.png"), "wb").write(b"OLD!")               # the previous call's picture
            stub = os.path.join(d, "shot_fails.ps1")
            open(stub, "w").write("param([string]$Out)\nexit 2\n")
            env = dict(os.environ, FO4SF_SHOT_SCRIPT=stub)
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out, "-MaxAge", "1"],
                               capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertIsNone(state["screen"])
            self.assertIn("exit 2", state["screen_error"])
            self.assertFalse(os.path.exists(os.path.join(out, "screen.png")), "the stale picture must be gone")

    def test_plugins_txt_is_written_as_plain_strings(self):
        # Install, 22 Oct: Get-Content's lines carried PSPath, PSDrive and Provider into a 3 MB state.json
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            os.makedirs(os.path.join(d, "Starfield"))
            open(os.path.join(d, "Starfield", "Plugins.txt"), "w").write("# comment\n*FO4TerrainCore.esm\nFO4Port.esm\n")
            stub = os.path.join(d, "shot_fails.ps1")
            open(stub, "w").write("param([string]$Out)\nexit 2\n")
            env = dict(os.environ, FO4SF_SHOT_SCRIPT=stub, LOCALAPPDATA=d)
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out, "-MaxAge", "1"],
                           capture_output=True, text=True, timeout=120, env=env)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["plugins_txt"], ["*FO4TerrainCore.esm", "FO4Port.esm"])

    def test_the_look_button_press_takes_a_snapshot(self):
        # look_hotkey.ps1 -TestFire runs the press handler once (no hotkey registered): a snapshot appears
        hot = os.path.join(ROOT, "scripts", "game", "look_hotkey.ps1")
        root = tempfile.mkdtemp(prefix="fo4sf_snaps_")             # never the owner's C:\Modding\snapshots
        before = set()
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", hot, "-TestFire"],
                           capture_output=True, text=True, timeout=60, env=dict(os.environ, FO4SF_SNAPSHOT_ROOT=root))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pressed", r.stdout)
        import time
        for _ in range(30):
            after = set(os.listdir(root))
            if after - before:
                break
            time.sleep(1)
        self.assertTrue(after - before, "no new snapshot folder")

    def test_writes_state_and_screen_without_a_game(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            log = os.path.join(d, "fo4sf.0.log")
            open(log, "w").write("[12:00:00] FO4SF rt=1.0 pos=-2189.257080 -1553.485718 105.260857 ang=0.000000 cell=33557935 world=-16708427 loaded=true n=1\n")
            env = dict(os.environ, FO4SF_BRIDGE_LOG=log)
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                                "-Note", "test", "-MaxAge", "999999999"], capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("snapshot", r.stdout)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["note"], "test")
            self.assertIn("game_running", state)
            self.assertTrue(os.path.exists(os.path.join(out, "screen.png")), "the screenshot")
            # the bridge line is read from $FO4SF_BRIDGE_LOG only when the tool is told; here the real log may or may not
            # exist, so only the shape is checked
            self.assertIn("bridge", state)


    def run_snapshot(self, out, answer):
        env = dict(os.environ, FO4SF_ASK_ANSWER=answer)          # stands in for the typed text: no window opens
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                               "-MaxAge", "1", "-Ask"], capture_output=True, text=True, timeout=120, env=env)

    def test_ask_saves_the_description_with_the_capture(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            r = self.run_snapshot(out, "the door at Red Rocket does not open")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("described=yes", r.stdout)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["description"], "the door at Red Rocket does not open")
            self.assertNotIn("description_pending", state)       # written while the box was open, cleared after
            self.assertEqual(open(os.path.join(out, "description.txt"), encoding="utf-8-sig").read().strip(),
                             "the door at Red Rocket does not open")
            self.assertTrue(os.path.exists(os.path.join(out, "screen.png")))

    def test_an_unanswered_box_leaves_a_describe_later_note(self):
        # the owner's play test, 2026-10-22: boxes behind full-screen Starfield waited unseen; one that times out says so
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            os.makedirs(out)
            open(os.path.join(out, "description.txt"), "w").write("the previous capture's text")   # Codex on #463
            r = self.run_snapshot(out, "<timeout>")                   # stands in for the box closing at -AskTimeout
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertIsNone(state["description"])
            self.assertEqual(state["description_timed_out"], 600)
            self.assertNotIn("description_pending", state)
            self.assertTrue(os.path.exists(os.path.join(out, "describe_later.txt")))
            self.assertFalse(os.path.exists(os.path.join(out, "description.txt")))
            self.assertIn(out, open(os.path.join(d, "describe_later.txt"), encoding="utf-8-sig").read())

    def test_screenshot_only_when_the_box_is_left_empty(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            r = self.run_snapshot(out, "   ")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertIsNone(state["description"])
            self.assertFalse(os.path.exists(os.path.join(out, "description.txt")))

    def test_submit_fills_the_player_report_form(self):
        # players' kit: the link opens the community form (labels community + needs-triage), never a folder path
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            env = dict(os.environ, FO4SF_ASK_ANSWER="door will not open\nat Red Rocket", FO4SF_SUBMIT_DRYRUN="1")
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                                "-MaxAge", "1", "-Ask", "-Submit"], capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            url = open(os.path.join(out, "issue_url.txt"), encoding="utf-8-sig").read().strip()
            self.assertTrue(url.startswith("https://github.com/fo4sf/fo4-to-starfield/issues/new?template=community_report.yml"))
            self.assertIn("title=%5BPlayer%20report%5D%3A%20door%20will%20not%20open&", url)
            self.assertIn("what=door%20will%20not%20open", url)
            self.assertNotIn("%3A%5C", url, "no Windows folder path in the link")
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["issue_url"], "issue_url.txt")

    def test_submit_skips_the_form_when_the_capture_failed(self):
        # Codex's review of #350: no screenshot means no link promising one on the clipboard
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            stub = os.path.join(d, "shot_fails.ps1")
            open(stub, "w").write("param([string]$Out)\nexit 2\n")
            env = dict(os.environ, FO4SF_SHOT_SCRIPT=stub, FO4SF_SUBMIT_DRYRUN="1")
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                                "-MaxAge", "1", "-Submit"], capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertFalse(os.path.exists(os.path.join(out, "issue_url.txt")))
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["submit_skipped"], "no screenshot")
            self.assertIn("exit 2", state["screen_error"])

    def test_submit_lists_only_enabled_port_plugins(self):
        # Codex's review of #350: Plugins.txt keeps disabled entries without '*'
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            os.makedirs(os.path.join(d, "Starfield"))
            open(os.path.join(d, "Starfield", "Plugins.txt"), "w").write("*FO4Active.esm\nFO4Disabled.esm\n*Other.esm\n")
            env = dict(os.environ, LOCALAPPDATA=d, FO4SF_SUBMIT_DRYRUN="1")
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                                "-MaxAge", "1", "-Submit"], capture_output=True, text=True, timeout=120, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            url = open(os.path.join(out, "issue_url.txt"), encoding="utf-8-sig").read()
            self.assertIn("FO4Active.esm", url)
            self.assertNotIn("FO4Disabled", url)
            self.assertNotIn("Other.esm", url)

    def test_the_ask_setting_switches_the_main_key(self):
        hot = os.path.join(ROOT, "scripts", "game", "look_hotkey.ps1")
        d = tempfile.mkdtemp(prefix="fo4sf_ask_")                 # the presses' snapshots land here after the test returns
        env = dict(os.environ, FO4SF_LOOK_SETTINGS=os.path.join(d, "look.settings.json"),
                   FO4SF_SNAPSHOT_ROOT=d, FO4SF_ASK_ANSWER=" ")   # " ": Windows drops an empty variable
        ps = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", hot]
        run = lambda *a: subprocess.run(ps + list(a), capture_output=True, text=True, timeout=60, env=env)
        self.assertIn("ask=False", run("-TestFire").stdout, "off by default: screenshots only")
        self.assertEqual(run("-SetAsk", "on").returncode, 0)
        self.assertIn("ask=True", run("-TestFire").stdout)
        self.assertIn("ask=True", run("-TestAsk").stdout, "the second key always asks")
        run("-SetAsk", "off")
        self.assertIn("ask=False", run("-TestFire").stdout)

    # the mission's own log (FAL-144): an isolated profile (USERPROFILE and LOCALAPPDATA in the temp folder, never the
    # owner's) and a stub capture that succeeds, so a mission-log problem can never pass for a screenshot failure
    MISSION_LINES = ("[10/28/2026 - 06:12:45PM] FO4SF_MISSION rt=200.0 preston activated at stage 10\r\n"
                     "[10/28/2026 - 06:12:46PM] FO4SF_MISSION rt=201.0 stage 20\r\n")

    def mission_log(self, profile, onedrive=False):
        folder = os.path.join(profile, *(["OneDrive"] if onedrive else []), "Documents", "My Games", "Starfield", "Logs",
                              "Script", "User")
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, "fo4sf_mission.0.log")

    def run_in_profile(self, d, out):
        stub = os.path.join(d, "shot_ok.ps1")
        open(stub, "w").write("param([string]$Out)\nSet-Content -LiteralPath $Out -Value 'png'\nexit 0\n")
        env = dict(os.environ, FO4SF_SHOT_SCRIPT=stub, USERPROFILE=os.path.join(d, "profile"), LOCALAPPDATA=d)
        return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, "-Out", out,
                               "-MaxAge", "1"], capture_output=True, text=True, timeout=120, env=env)

    def test_the_mission_log_is_copied_whole_with_its_record(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            log = self.mission_log(os.path.join(d, "profile"))
            data = self.MISSION_LINES.encode()
            open(log, "wb").write(data)
            old = time.time() - 7200
            os.utime(log, (old, old))                                   # the session last wrote two hours ago
            folder = os.path.dirname(log)
            open(os.path.join(folder, "fo4sf_mission.1.log"), "w").write("an earlier session\n")
            open(os.path.join(folder, "another_mod.0.log"), "w").write("not the mission's\n")
            with open(log, "ab"):                                       # the running game holds it open for writing
                r = self.run_in_profile(d, out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(open(os.path.join(out, "fo4sf_mission.0.log"), "rb").read(), data)
            self.assertEqual(sorted(os.listdir(out)), ["fo4sf_mission.0.log", "screen.png", "state.json"],
                             "only the mission's current log, nothing else from the folder")
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["screen"], "screen.png")
            m = state["mission_log"]
            self.assertEqual(m["file"], "fo4sf_mission.0.log")
            self.assertEqual(m["from"], r"Documents\My Games\Starfield\Logs\Script\User\fo4sf_mission.0.log")  # no user name
            self.assertEqual(m["bytes"], len(data))
            self.assertGreaterEqual(m["age_s"], 7000)

    def test_the_onedrive_mission_log_comes_first_as_papyrus_does(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            profile = os.path.join(d, "profile")
            open(self.mission_log(profile, onedrive=True), "w").write("the OneDrive Documents log\n")
            open(self.mission_log(profile), "w").write("the plain Documents log\n")
            r = self.run_in_profile(d, out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(open(os.path.join(out, "fo4sf_mission.0.log")).read(), "the OneDrive Documents log\n")
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["mission_log"]["from"],
                             r"OneDrive\Documents\My Games\Starfield\Logs\Script\User\fo4sf_mission.0.log")

    def test_a_missing_mission_log_is_recorded_and_the_snapshot_still_succeeds(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "snap")
            os.makedirs(out)
            open(os.path.join(out, "fo4sf_mission.0.log"), "w").write("the previous capture's log\n")   # a reused folder
            log = self.mission_log(os.path.join(d, "profile"))
            open(os.path.join(os.path.dirname(log), "fo4sf_mission.1.log"), "w").write("an earlier session\n")
            r = self.run_in_profile(d, out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = json.load(open(os.path.join(out, "state.json"), encoding="utf-8-sig"))
            self.assertEqual(state["screen"], "screen.png")
            self.assertIsNone(state["mission_log"]["file"])
            self.assertIn("no fo4sf_mission.0.log", state["mission_log"]["why"])
            self.assertFalse(os.path.exists(os.path.join(out, "fo4sf_mission.0.log")), "the stale copy must be gone")


class SnapshotMissionLogSourceTests(unittest.TestCase):
    """FAL-144 on any system (the tests above need Windows): the mission log is looked up as Papyrus.0.log is."""

    def test_the_mission_log_follows_the_papyrus_lookup(self):
        with open(SCRIPT, encoding="utf-8") as f:
            src = f.read()
        pap = re.findall(r"'((?:OneDrive\\)?Documents)\\My Games\\Starfield\\Logs\\Script\\Papyrus\.0\.log'", src)
        mis = re.findall(r'"((?:OneDrive\\)?Documents)\\My Games\\Starfield\\Logs\\Script\\User\\\$misName"', src)
        self.assertEqual(pap, ["OneDrive\\Documents", "Documents"])
        self.assertEqual(mis, pap, "the same two folders, OneDrive first")
        self.assertIn("$misName = 'fo4sf_mission.0.log'", src)        # the current session's log only
        self.assertIn("[System.IO.File]::Open($misSrc, 'Open', 'Read', 'ReadWrite')", src)   # the game may be writing it


if __name__ == "__main__":
    unittest.main()
