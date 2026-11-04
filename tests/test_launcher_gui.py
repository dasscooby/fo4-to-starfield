"""Headless GUI model and real settings CLI, synthetic files only. No Tk, game, Steam or watcher is started."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import gui, paths, settings  # noqa: E402


class GuiModelTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.path = self.folder / "settings.json"
        self.launcher = str(ROOT / "scripts" / "launcher.py")
        self.model = gui.SettingsModel(self.launcher, str(self.path))
        self.game = str(self.folder / "game folder")          # Play checks the folder holds Starfield.exe
        os.makedirs(self.game)
        Path(self.game, "Starfield.exe").write_bytes(b"")

    def run_cli(self, argv):
        return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)

    def test_exactly_one_control_per_setting_with_labels_choices_and_costs(self):
        specs = gui.controls()
        # the file locations live on the Locations tab, not among the toggles
        spec = [s for s in settings.SPEC if s[0] not in paths.KEYS]
        self.assertEqual([s["key"] for s in specs], [s[0] for s in spec])
        for desc, (key, default, kind, cost) in zip(specs, spec):
            self.assertEqual((desc["label"], desc["default"], desc["cost"]), (settings.LABELS[key], default, cost))
            expected = "bool" if kind is bool else "choice" if isinstance(kind, tuple) else "text"
            self.assertEqual(desc["kind"], expected)
            self.assertEqual(desc["choices"], kind if isinstance(kind, tuple) else ())

    def test_unchanged_save_never_creates_or_rewrites_settings(self):
        self.assertIsNone(self.model.command("save", self.model.saved))
        self.assertFalse(self.path.exists())
        # Preserve even noncanonical bytes and explicit defaults; this is a no-op, not a reserialization.
        original = b'{\n  "route" : "steam", "crash_watch.min_free_gb": 25\n}\n'
        self.path.write_bytes(original)
        self.model.reload()
        before = self.path.stat().st_mtime_ns
        raw = {k: str(v) if not isinstance(v, bool) else v for k, v in self.model.saved.items()}
        self.assertIsNone(self.model.command("save", raw))
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_save_uses_real_settings_command_and_validation(self):
        raw = dict(self.model.saved, **{"crash_watch.dump": "full", "crash_watch.min_free_gb": "42.5"})
        argv = self.model.command("save", raw)
        self.assertEqual(argv[:5], [sys.executable, "-I", "-u", self.launcher, "settings"])
        result = self.run_cli(argv)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.model.reload()
        self.assertEqual(self.model.saved["crash_watch.dump"], "full")
        self.assertEqual(self.model.saved["crash_watch.min_free_gb"], 42.5)
        for invalid in ("nan", "inf", "-1", "nope"):
            raw["crash_watch.min_free_gb"] = invalid
            before = self.path.read_bytes()
            with self.assertRaises(ValueError):
                self.model.command("save", raw)
            self.assertEqual(self.path.read_bytes(), before)

    def test_save_applies_only_changed_keys_and_preserves_external_settings(self):
        # Someone changes an unrelated key after the window opens; the existing CLI merges only this window's edits.
        self.path.write_text(json.dumps({"route": "exe"}), encoding="utf-8")
        raw = dict(self.model.saved, **{"crash_watch.dump": "full"})
        argv = self.model.command("save", raw)
        self.assertNotIn("route=steam", argv)
        result = self.run_cli(argv)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(settings.load(str(self.path))["route"], "exe")

    def test_watcher_requirements_use_existing_problems_and_are_visible(self):
        raw = dict(self.model.saved, **{"crash_watch.enabled": True})
        # CLI allows saving a setup in progress; Play's existing problems remain visible and block the button.
        self.assertIn("crash_watch.folder", self.model.play_reason(raw, "game", [], windows=True))
        result = self.run_cli(self.model.command("save", raw))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("play would refuse: crash_watch.folder", result.stdout)
        self.assertIn("play would refuse: crash_watch.procdump", result.stdout)

    def test_play_is_disabled_for_running_unknown_and_invalid_state(self):
        raw = dict(self.model.saved)
        for pids, want in ((None, "Checking"), ([123, 456], "already running")):
            self.assertIn(want, self.model.play_reason(raw, "game", pids, windows=True))
            with self.assertRaises(ValueError):
                self.model.command("play", raw, starfield="game", pids=pids, windows=True)
        self.assertIn("Windows", self.model.play_reason(raw, "game", [], windows=False))
        self.assertIn("Choose", self.model.play_reason(raw, "", [], windows=True))
        raw["route"] = "exe"
        self.assertIn("Save", self.model.play_reason(raw, "game", [], windows=True))

    def test_unconfirmed_locations_block_play_until_saved(self):
        raw = dict(self.model.saved, starfield="found game folder")
        self.assertIn("Confirm the locations", self.model.play_reason(raw, "found game folder", [], windows=True))
        raw["route"] = "exe"
        self.assertIn("Save the changed settings", self.model.play_reason(raw, "found game folder", [], windows=True))

    def test_save_settings_never_saves_unconfirmed_locations(self):
        raw = dict(self.model.saved, **{"starfield": "found game", "crash_watch.dump": "full"})
        argv = self.model.command("save", self.model.part(raw, "settings"))
        self.assertIn("crash_watch.dump=full", argv)
        self.assertFalse([a for a in argv if a.startswith("starfield=")])
        argv = self.model.command("save", self.model.part(raw, "locations"))
        self.assertIn("starfield=found game", argv)
        self.assertFalse([a for a in argv if a.startswith("crash_watch.dump=")])
        self.assertEqual(self.model.part(raw), raw)

    def test_play_and_detect_fall_back_to_the_saved_locations(self):
        self.path.write_text(json.dumps({"starfield": self.game, "fo4_data": "Data A;Data B"}), encoding="utf-8")
        self.model.reload()
        argv = self.model.command("play", self.model.saved, pids=[], windows=True)
        self.assertEqual(argv[-2:], ["--starfield", self.game])
        argv = self.model.command("detect")
        self.assertEqual(argv[4:], ["detect", "--settings", str(self.path), "--starfield", self.game,
                                    "--fo4-data", "Data A", "--fo4-data", "Data B"])

    def test_play_waits_while_a_saved_location_no_longer_works(self):
        self.path.write_text(json.dumps({"starfield": self.game}), encoding="utf-8")
        self.model.reload()
        self.assertEqual(self.model.play_reason(self.model.saved, "", [], windows=True), "")
        os.remove(os.path.join(self.game, "Starfield.exe"))          # the game moved since it was confirmed
        self.assertIn("no Starfield.exe", self.model.play_reason(self.model.saved, "", [], windows=True))
        raw = dict(self.model.saved, **{"crash_watch.enabled": True, "crash_watch.folder": self.game,
                                        "crash_watch.procdump": os.path.join(self.game, "gone", "procdump64.exe")})
        self.path.write_text(json.dumps(dict(raw, starfield=self.game)), encoding="utf-8")
        Path(self.game, "Starfield.exe").write_bytes(b"")
        self.model.reload()
        self.assertIn("ProcDump path: file not found", self.model.play_reason(self.model.saved, "", [], windows=True))

    def test_a_late_detection_leaves_the_players_edits_alone(self):
        found = {"starfield": (self.game, "Steam library")}
        self.assertEqual([r["key"] for r in self.model.locations(found)], list(paths.KEYS))
        rows = self.model.locations(found, dirty={"starfield"})
        self.assertNotIn("starfield", [r["key"] for r in rows])
        self.assertEqual(len(rows), len(paths.KEYS) - 1)

    def test_play_delegates_to_existing_cli_for_both_routes(self):
        for route in ("sfse", "steam", "exe"):
            self.path.write_text(json.dumps({"route": route}), encoding="utf-8")
            self.model.reload()
            argv = self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True)
            self.assertEqual(argv[4:], ["play", "--settings", str(self.path), "--starfield", self.game])
            # Do NOT execute this command: the existing play handler owns routes, process checks and the watcher.

    def test_play_starts_the_fo4sf_game_folder_when_one_is_set(self):
        self.path.write_text(json.dumps({"route": "sfse", "instance": "D:/FO4SF/Starfield"}), encoding="utf-8")
        self.model.reload()
        argv = self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True)
        self.assertEqual(argv[-2:], ["--starfield", "D:/FO4SF/Starfield"])

    def test_play_refuses_a_stale_view_of_the_saved_settings(self):
        raw = dict(self.model.saved)
        self.path.write_text(json.dumps({"route": "exe"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed outside"):
            self.model.command("play", raw, starfield=self.game, pids=[], windows=True)
        self.model.reload()
        self.assertEqual(self.model.saved["route"], "exe")
        self.assertIn("play", self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True))

    def test_settings_read_failure_is_a_visible_command_error(self):
        with mock.patch.object(settings, "load", side_effect=PermissionError("settings cannot be read")):
            with self.assertRaisesRegex(ValueError, "Cannot read saved settings"):
                self.model.command("play", self.model.saved, starfield=self.game, pids=[], windows=True)

    def test_status_and_detect_argv_request_no_writes(self):
        argv = self.model.command("status", recipe="recipe file.json", overrides=["root=some folder"])
        self.assertEqual(argv[4:], ["status", "recipe file.json", "--set", "root=some folder"])
        self.assertNotIn("--json", argv)
        argv = self.model.command("detect", fo4_data=["Data A", "Data B"], starfield="game")
        self.assertEqual(argv[4:], ["detect", "--settings", str(self.path), "--starfield", "game",
                                    "--fo4-data", "Data A", "--fo4-data", "Data B"])
        self.assertNotIn("--report", argv)
        self.assertNotIn("--allow-unknown", argv)
        with self.assertRaises(ValueError):
            self.model.command("status")
        with self.assertRaises(ValueError):
            self.model.command("detect")

    def test_the_update_buttons_run_the_update_command(self):
        self.assertEqual(self.model.command("update-check")[4:], ["update", "--check"])
        self.assertEqual(self.model.command("update")[4:], ["update"])

    def test_saved_my_games_argument_is_forwarded_without_guessing(self):
        self.path.write_text(json.dumps({"my_games": "resolved documents folder"}), encoding="utf-8")
        self.model.reload()
        argv = self.model.command("detect", fo4_data=["data"], starfield="game")
        self.assertEqual(argv[-2:], ["--my-games", "resolved documents folder"])

    def test_streaming_preserves_output_and_nonzero_exit_without_a_shell(self):
        calls = []
        class Child:
            stdout = io.StringIO("first\nerror\n")
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                self.stdout.close()
            def wait(self):
                return 7
        def spawn(argv, **kwargs):
            calls.append((argv, kwargs))
            return Child()
        lines = []
        argv = self.model.command("status", recipe="a b.json")
        self.assertEqual(gui.run_command(argv, lines.append, popen=spawn), 7)
        self.assertEqual(lines, ["first\n", "error\n"])
        self.assertEqual(calls[0][0], argv)
        self.assertEqual(calls[0][1]["cwd"], str(ROOT))
        self.assertNotIn("shell", calls[0][1])

    def test_missing_or_unknown_widgets_are_not_silently_saved(self):
        for raw in ({}, dict(self.model.saved, unknown="x")):
            with self.assertRaises(ValueError):
                self.model.command("save", raw)


class PathsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / "Starfield"
        self.data = self.root / "Fallout 4" / "Data"
        self.docs = self.root / "user" / "Documents" / "My Games" / "Starfield"
        self.tools = self.root / "Program Files" / "Sysinternals"
        for d in (self.game, self.data, self.docs, self.tools):
            d.mkdir(parents=True)
        (self.game / "Starfield.exe").write_bytes(b"")
        (self.data / "Fallout4.esm").write_bytes(b"")
        (self.tools / "procdump64.exe").write_bytes(b"")
        self.env = {"USERPROFILE": str(self.root / "user"), "ProgramFiles": str(self.root / "Program Files"),
                    "LOCALAPPDATA": str(self.root / "local")}
        # Keep Windows' redirected Documents folder out of these synthetic path-discovery fixtures.
        documents = mock.patch.object(paths, "_documents", return_value=[str(self.docs.parents[1])])
        documents.start()
        self.addCleanup(documents.stop)

    def find(self):
        return {"starfield": str(self.game), "fallout4": str(self.data.parent), "fallout4_depots": []}

    def test_check_names_what_is_wrong(self):
        self.assertEqual(paths.check("starfield", str(self.game)), "")
        self.assertIn("Starfield.exe", paths.check("starfield", str(self.data)))
        self.assertIn("not found", paths.check("starfield", str(self.root / "nope")))
        self.assertEqual(paths.check("fo4_data", f"{self.data};{self.game}"), "")
        self.assertIn("Fallout4.esm", paths.check("fo4_data", str(self.game)))
        self.assertIn("not found", paths.check("fo4_data", f"{self.data};{self.root / 'nope'}"))
        self.assertEqual(paths.check("crash_watch.procdump", str(self.tools / "procdump64.exe")), "")
        self.assertIn("not procdump", paths.check("crash_watch.procdump", str(self.game / "Starfield.exe")))
        self.assertEqual(paths.check("crash_watch.folder", str(self.root / "new dumps")), "")
        # play makes every missing folder, so a fresh %LOCALAPPDATA%\FO4SF\crashdumps is fine (Codex, #481)
        self.assertEqual(paths.check("crash_watch.folder", str(self.root / "a" / "b")), "")
        self.assertIn("is a file", paths.check("crash_watch.folder", str(self.game / "Starfield.exe" / "dumps")))
        self.assertEqual(paths.check("my_games", ""), "not set")

    def test_detect_finds_every_location_without_writing(self):
        before = sorted(p for p in self.root.rglob("*"))
        found = paths.detect(env=self.env, find=self.find, which=lambda _n: None)
        self.assertEqual(paths.check("crash_watch.folder", found["crash_watch.folder"][0]), "")
        self.assertEqual(found["starfield"][0], os.path.normpath(self.game))
        self.assertEqual(found["fo4_data"][0], str(self.data))
        self.assertEqual(found["my_games"][0], os.path.normpath(self.docs))
        self.assertEqual(found["crash_watch.procdump"], (os.path.normpath(self.tools / "procdump64.exe"), "Program Files"))
        self.assertEqual(found["crash_watch.folder"][1], "suggested")
        self.assertEqual(sorted(p for p in self.root.rglob("*")), before)

    def test_detect_reports_nothing_it_cannot_verify(self):
        (self.game / "Starfield.exe").unlink()
        def broken():
            raise OSError("registry unreadable")
        for find in (self.find, broken):
            found = paths.detect(env={}, find=find, which=lambda _n: str(self.game / "not-procdump.exe"))
            self.assertEqual(found["starfield"], ("", ""))
            self.assertEqual(found["crash_watch.procdump"], ("", ""))

    def test_rows_ask_about_found_values_and_keep_good_saved_ones(self):
        found = paths.detect(env=self.env, find=self.find, which=lambda _n: None)
        saved = dict(settings.defaults(), **{"starfield": str(self.game), "my_games": str(self.root / "gone")})
        rows = {r["key"]: r for r in paths.rows(saved, found)}
        self.assertEqual(rows["starfield"]["status"], "saved")
        self.assertEqual(rows["fo4_data"]["status"], "found")
        self.assertIn("is this right?", rows["fo4_data"]["note"])
        # a saved value that no longer works is replaced by what was found, and still has to be confirmed
        self.assertEqual((rows["my_games"]["status"], rows["my_games"]["value"]), ("found", os.path.normpath(self.docs)))
        # a path given on the command line is offered even over a good saved one (Codex, #481)
        other = str(self.root / "Other Starfield")
        rows = {r["key"]: r for r in paths.rows(saved, {"starfield": (other, "command line")}, prefer=["starfield"])}
        self.assertEqual((rows["starfield"]["status"], rows["starfield"]["value"]), ("found", other))
        rows = {r["key"]: r for r in paths.rows(saved, {"starfield": (str(self.game), "command line")},
                                                prefer=["starfield"])}
        self.assertEqual(rows["starfield"]["status"], "saved")
        rows = {r["key"]: r for r in paths.rows(saved, {})}
        self.assertEqual(rows["my_games"]["status"], "problem")
        self.assertEqual(rows["fo4_data"]["status"], "missing")

    def test_needed_follows_the_settings(self):
        values = settings.defaults()
        self.assertEqual(paths.needed(values), ["starfield"])
        values.update({"crash_watch.enabled": True, "papyrus_logging": "on"})
        self.assertEqual(paths.needed(values), ["starfield", "crash_watch.procdump", "crash_watch.folder", "my_games"])


class LocationsCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "launcher.py"), *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_play_without_any_starfield_folder_is_refused_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.run_cli("play", "--dry-run", "--settings", os.path.join(d, "s.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no Starfield folder", result.stdout + result.stderr)

    def test_plain_play_refuses_a_saved_starfield_folder_that_moved(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            Path(path).write_text(json.dumps({"starfield": os.path.join(d, "moved")}), encoding="utf-8")
            result = self.run_cli("play", "--dry-run", "--settings", path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("saved Starfield folder", result.stdout + result.stderr)
        self.assertIn("folder not found", result.stdout + result.stderr)

    def test_detect_given_every_location_does_not_need_a_readable_settings_file(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "s.json")
            Path(bad).write_text('{"newer_setting": 1}', encoding="utf-8")
            args = ("detect", "--settings", bad, "--fo4-data", os.path.join(d, "Data"), "--starfield", d)
            full = self.run_cli(*args, "--my-games", d)
            self.assertNotIn("newer_setting", full.stdout + full.stderr)
            part = self.run_cli(*args)
            self.assertIn("settings not read", part.stdout)
            self.assertIn("detect runs without --my-games", part.stdout)

    def test_paths_lists_every_location_and_says_what_play_still_needs(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            result = self.run_cli("paths", "--settings", path)
            self.assertFalse(os.path.exists(path))
        for _key, label, _kind, _what in paths.LOCATIONS:
            self.assertIn(label, result.stdout)
        # no Steam here, so nothing is saved or found for the game folder
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("still needed to play: Starfield game folder", result.stdout)


WINDOW_SCRIPT = r"""
import gc, json, os, sys, tempfile, threading, time
sys.path.insert(0, sys.argv[1])
import tkinter as tk
from fo4sf.launcher import gui, paths
d = tempfile.mkdtemp()
def made(name, file):
    os.makedirs(os.path.join(d, name))
    open(os.path.join(d, name, file), "wb").close()
    return os.path.join(d, name)
detected, typed = made("SteamGame", "Starfield.exe"), made("MyGame", "Starfield.exe")
gate = threading.Event()
def late_detect(**_kw):
    gate.wait(10)
    return {k: ("", "") for k in paths.KEYS} | {"starfield": (detected, "Steam library")}
paths.detect = late_detect
errors = []
tk.Tk.report_callback_exception = lambda self, *a: errors.append(repr(a[1]))
def pump(root, s):
    end = time.time() + s
    while time.time() < end:
        root.update()
        time.sleep(0.02)
def run(root):
    w = next(o for o in gc.get_objects() if type(o).__name__ == "Window")
    pump(root, 0.3)
    entry = w.loc["starfield"]["entry"]
    entry.delete(0, "end")
    entry.insert(0, typed)                      # the player types while detection is still running
    pump(root, 0.2)
    gate.set()
    pump(root, 1.0)
    out = {"after_detect": w.location_value("starfield")}
    w.detect_locations()                        # Detect again
    pump(root, 1.0)
    out["after_redetect"] = w.location_value("starfield")
    data = w.loc["fo4_data"]["entry"]          # the player browses to other Data folders, then checks the install
    data.delete("1.0", "end")
    data.insert("1.0", "Data A\nData B")
    games = w.loc["my_games"]["entry"]
    games.delete(0, "end")
    games.insert(0, "Other My Games")
    ran = []
    gui.run_command = lambda argv, on_line, **_kw: ran.append(argv) or 0
    w.start("detect")
    pump(root, 0.5)
    out["detect_argv"] = ran[0][4:] if ran else w.message.get()
    out["errors"] = errors
    print(json.dumps(out))
    root.destroy()
tk.Tk.mainloop = lambda self, n=0: run(self)
gui.launch(sys.argv[2], os.path.join(d, "settings.json"))
"""


def can_open_a_window():
    try:
        import tkinter
        tkinter.Tk().destroy()
        return True
    except Exception:            # no tkinter, or no display (CI): the model tests above still run
        return False


@unittest.skipUnless(can_open_a_window(), "needs tkinter and a display")
class GuiWindowTests(unittest.TestCase):
    def test_a_late_detection_keeps_a_typed_location_in_the_real_window(self):
        result = subprocess.run([sys.executable, "-I", "-c", WINDOW_SCRIPT, str(ROOT / "src"),
                                 str(ROOT / "scripts" / "launcher.py")], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(out["errors"], [])
        self.assertTrue(out["after_detect"].endswith("MyGame"), out)
        self.assertTrue(out["after_redetect"].endswith("MyGame"), out)
        # Check installation uses the folders on screen, not the saved ones (Codex, #481)
        argv = out["detect_argv"]
        self.assertEqual(argv[argv.index("--fo4-data"):], ["--fo4-data", "Data A", "--fo4-data", "Data B",
                                                           "--my-games", "Other My Games"], out)
        self.assertTrue(argv[argv.index("--starfield") + 1].endswith("MyGame"), out)


class GuiEntryTests(unittest.TestCase):
    def test_opening_without_tkinter_gives_a_clear_error(self):
        import builtins
        original = builtins.__import__
        def no_tk(name, *args, **kwargs):
            if name == "tkinter" or name.startswith("tkinter."):
                raise ImportError("not installed")
            return original(name, *args, **kwargs)
        with mock.patch("builtins.__import__", side_effect=no_tk):
            with self.assertRaisesRegex(ValueError, "needs Python's tkinter"):
                gui.launch("launcher.py", "not-read.json")

    def test_import_and_cli_help_need_neither_tkinter_nor_a_display(self):
        code = """
import builtins,runpy,sys
sys.path.insert(0,sys.argv[1])
original=builtins.__import__
def guarded(name,*args,**kwargs):
    if name=='tkinter' or name.startswith('tkinter.'):
        raise AssertionError('headless import tried tkinter')
    return original(name,*args,**kwargs)
builtins.__import__=guarded
import fo4sf.launcher.gui
sys.argv=[sys.argv[2],'gui','--help']
runpy.run_path(sys.argv[0],run_name='__main__')
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(ROOT / "src"),
                                 str(ROOT / "scripts" / "launcher.py")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--settings", result.stdout)
        self.assertIn("--recipe", result.stdout)


if __name__ == "__main__":
    unittest.main()
