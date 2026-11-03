"""Playing from the FO4SF game folder (docs/ai/fo4sf-instance.md steps 2 to 4): the folder's own Plugins.txt stands in
the player's place only while the game runs and the player's comes back byte for byte (also after a crash, from the
journal), its own Starfield.ini takes the saves path and the Papyrus keys, and our tools run on its own Plugins.txt.
Synthetic folders and a fake process table; no game."""
import base64
import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
from fo4sf.launcher import crashwatch, files, instance, settings  # noqa: E402
from test_launcher_crashwatch import FakeSystem  # noqa: E402
from test_launcher_instance import GAME, plenty, write  # noqa: E402

PLAYER = b"# This file is used by Starfield to keep track of your downloaded content.\r\n*MyModPack.esm\r\n*Another.esp\r\n"
OURS = b"*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n"


class FolderPlayTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        src = os.path.join(self.root, "Steam", "Starfield")
        for rel, data in GAME.items():
            write(src, rel, data)
        self.folder = os.path.join(self.root, "FO4SF", "Starfield")
        instance.create(src, self.folder, disk_usage=plenty, say=lambda *_: None)
        self.local = os.path.join(self.root, "AppData", "Local")
        self.player = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.local, "Starfield/Plugins.txt", PLAYER)
        write(instance.local_dir(self.folder), "Starfield/Plugins.txt", OURS)
        env = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local})
        env.start()
        self.addCleanup(env.stop)
        self.journal = instance.journal_path(self.player)
        self.said = []

    def read(self, p):
        with open(p, "rb") as f:
            return f.read()

    # --- the swap -----------------------------------------------------------------------------------------------
    def test_swap_round_trip_puts_the_players_list_back_byte_for_byte(self):
        instance.swap_in(self.folder, self.player, self.said.append)
        self.assertEqual(self.read(self.player), OURS)                       # the game reads FO4SF's list
        self.assertEqual(os.path.dirname(self.journal), os.path.join(self.local, "FO4SF"))   # outside the folder
        backups = [n for n in os.listdir(os.path.dirname(self.journal)) if n.startswith("player-Plugins.txt.bak-")]
        self.assertEqual(len(backups), 1)                                    # a second copy, kept
        rewritten = b"*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n"
        with open(self.player, "wb") as f:                                   # the game rewrites it at its start
            f.write(rewritten)
        self.assertTrue(instance.swap_out(self.player, self.said.append))
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertEqual(self.read(instance.plugins_txt(self.folder)), rewritten)   # FO4SF keeps the game's order
        self.assertFalse(os.path.exists(self.journal))
        self.assertFalse(instance.swap_out(self.player))                    # nothing left to put back

    def test_a_player_without_a_plugins_txt_gets_none_back(self):
        os.remove(self.player)
        instance.swap_in(self.folder, self.player, self.said.append)
        instance.swap_out(self.player, self.said.append)
        self.assertFalse(os.path.exists(self.player))

    def test_a_left_journal_is_put_back_first_and_never_overwritten(self):
        instance.swap_in(self.folder, self.player, self.said.append)
        with self.assertRaisesRegex(instance.InstanceRefused, "left from an earlier start"):
            instance.swap_in(self.folder, self.player, self.said.append)
        with self.assertRaisesRegex(instance.InstanceRefused, "running"):
            instance.recover(self.player, lambda: True, self.said.append)
        self.assertEqual(self.read(self.player), OURS)                       # left alone under a running game
        with open(self.player, "wb") as f:                                   # whoever rewrote it, it is kept aside
            f.write(b"*Unknown.esm\r\n")
        self.assertTrue(instance.recover(self.player, lambda: False, self.said.append))
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertEqual(self.read(instance.plugins_txt(self.folder)), OURS)  # a recovery never adopts a stranger's
        kept = [n for n in os.listdir(os.path.dirname(self.journal)) if ".after-" in n]
        self.assertEqual(len(kept), 1)
        self.assertFalse(instance.recover(self.player, lambda: False, self.said.append))

    def test_a_left_swap_comes_back_whatever_the_setting_and_without_the_folder(self):
        # review of the stack, P2 2: the journal is found from the player's list, not from the setting `instance`
        instance.swap_in(self.folder, self.player, self.said.append)
        spec = importlib.util.spec_from_file_location("launcher_cli_left", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cli.put_back_left_swap(dry_run=True)                            # a dry run only says so
        self.assertIn("a swap is left", out.getvalue())
        self.assertEqual(self.read(self.player), OURS)
        import shutil
        shutil.rmtree(self.folder)                                         # even the folder gone
        with mock.patch.object(cli.restore, "game_running", return_value=False):
            cli.put_back_left_swap(dry_run=False)
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertFalse(os.path.exists(self.journal))
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": ""}):
            cli.put_back_left_swap(dry_run=False)                           # no LOCALAPPDATA: nothing to do

    def test_a_swap_out_with_the_folder_gone_keeps_the_games_list_beside_the_journal(self):
        instance.swap_in(self.folder, self.player, self.said.append)
        with open(self.player, "wb") as f:
            f.write(b"*Rewritten.esm\r\n")
        import shutil
        shutil.rmtree(self.folder)
        self.assertTrue(instance.swap_out(self.player, self.said.append, after_game=True))
        self.assertEqual(self.read(self.player), PLAYER)
        kept = [n for n in os.listdir(os.path.dirname(self.journal)) if ".after-" in n]
        self.assertEqual([self.read(os.path.join(os.path.dirname(self.journal), n)) for n in kept],
                         [b"*Rewritten.esm\r\n"])

    def test_starfieldcustom_ini_that_would_undo_the_folders_ini_is_named(self):
        my_games = os.path.join(self.root, "My Games", "Starfield")
        self.assertEqual(instance.custom_ini_problems(my_games, {"bridge": "on"}), [])          # no file
        write(my_games, "StarfieldCustom.ini", b"[Papyrus]\r\nbEnableLogging=1\r\n")
        self.assertEqual(instance.custom_ini_problems(my_games, {"bridge": "on"}), [])
        write(my_games, "StarfieldCustom.ini", b"[General]\r\nSLocalSavePath=Saves\\Mine\\\r\n"
                                               b"[Papyrus]\r\nbEnableLogging=0\r\n")
        self.assertEqual(len(instance.custom_ini_problems(my_games, {"bridge": "on"})), 2)
        self.assertEqual(len(instance.custom_ini_problems(my_games, {"bridge": "off"})), 1)
        self.assertEqual(instance.custom_ini_problems("", {"bridge": "on"}), [])
        write(my_games, "StarfieldCustom.ini", b"\xef\xbb\xbf[General]\r\nSLocalSavePath=Saves\\Mine\\\r\n")   # BOM
        self.assertEqual(len(instance.custom_ini_problems(my_games, {"bridge": "off"})), 1)
        with self.assertRaisesRegex(ValueError, "SLocalSavePath"):
            self.play(self.values(my_games=my_games), self.game())
        self.assertEqual(self.read(self.player), PLAYER)                    # refused before anything
        self.play(self.values(), self.game())                               # my_games unset: said, not silent
        self.assertTrue(any("StarfieldCustom.ini not checked" in s for s in self.said))

    # --- review of the stack (second round), P3s --------------------------------------------------------------------
    def test_the_players_list_is_back_before_the_wait_on_procdump(self):
        dumps, procdump = os.path.join(self.root, "dumps"), os.path.join(self.root, "procdump64.exe")
        write(self.root, "procdump64.exe", b"")
        sys_ = self.game()
        spawn, at_wait = sys_.spawn, []

        def spawn_watching(argv, log_path):
            proc = spawn(argv, log_path)
            wait = proc.wait
            proc.wait = lambda timeout=None: at_wait.append(self.read(self.player)) or wait(timeout)
            return proc
        sys_.spawn = spawn_watching
        self.play(self.values(**{"crash_watch.enabled": True, "crash_watch.folder": dumps,
                                 "crash_watch.procdump": procdump}), sys_)
        self.assertEqual(at_wait, [PLAYER])                                 # already back while the dump is awaited

    def test_a_failed_put_back_at_the_games_end_keeps_the_crash_record(self):
        # third review of the stack, P3: the put-back moved before the log; its failure must not cost the log
        dumps, procdump = os.path.join(self.root, "dumps"), os.path.join(self.root, "procdump64.exe")
        write(self.root, "procdump64.exe", b"")
        real, calls = instance.swap_out, []

        def busy_once(*a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("Plugins.txt is busy")
            return real(*a, **k)
        with mock.patch.object(instance, "swap_out", side_effect=busy_once):
            r = self.play(self.values(**{"crash_watch.enabled": True, "crash_watch.folder": dumps,
                                         "crash_watch.procdump": procdump}), self.game())
        self.assertTrue(r["started"])
        with open(os.path.join(dumps, "crashwatch.log"), encoding="utf-8") as f:
            log = f.read()
        self.assertIn("after the game ended: Plugins.txt is busy", log)
        self.assertIn("ended: process", log)                                # the crash record is still written
        self.assertEqual(self.read(self.player), PLAYER)                    # and the after-path put the list back

    def test_an_unreadable_process_list_after_the_game_says_where_the_players_list_is(self):
        # review of 66c353dd, P3: tasklist failing after the game ended made the put-back fail quietly, then raised out
        # of play from the after-path, and STILL_SWAPPED was never said; now it is, and the journal waits for recover()
        sys_ = self.game()
        pids, seen = sys_.pids, []

        def pids_until_the_end(*a, **k):
            out = pids(*a, **k)
            if out:
                seen.append(1)
            elif seen:                              # the game came and went: from here on tasklist fails
                raise ValueError("Cannot check the running processes")
            return out
        sys_.pids = pids_until_the_end
        r = self.play(self.values(), sys_)
        self.assertTrue(r["started"])
        self.assertTrue(any("after the game ended: Cannot check" in s for s in self.said), self.said)
        self.assertTrue(any("still in your place" in s for s in self.said), self.said)
        self.assertTrue(instance.pending(self.player))                      # the journal stays for recover()
        self.assertTrue(instance.recover(self.player, lambda: False, self.said.append))
        self.assertEqual(self.read(self.player), PLAYER)

    def test_a_stop_under_a_running_game_says_where_the_players_list_is(self):
        sys_ = self.game()
        start = sys_.start_game

        def start_then_ctrl_c(route, starfield):
            start(route, starfield)
            raise KeyboardInterrupt
        sys_.start_game = start_then_ctrl_c
        with self.assertRaises(KeyboardInterrupt):
            self.play(self.values(), sys_)
        self.assertEqual(self.read(self.player), OURS)                      # never swapped under a running game
        self.assertTrue(any("still in your place" in s for s in self.said))

    def test_a_swap_interrupted_after_its_write_keeps_the_journal(self):
        real = instance._put

        def put_then_stop(path, raw, expect):
            real(path, raw, expect)
            raise KeyboardInterrupt
        with mock.patch.object(instance, "_put", side_effect=put_then_stop):
            with self.assertRaises(KeyboardInterrupt):
                instance.swap_in(self.folder, self.player, self.said.append)
        self.assertEqual(self.read(self.player), OURS)
        self.assertTrue(os.path.exists(self.journal))                       # recover() can still put it back
        self.assertTrue(instance.recover(self.player, lambda: False, self.said.append))
        self.assertEqual(self.read(self.player), PLAYER)

    def test_a_list_already_back_only_drops_the_journal(self):
        instance.swap_in(self.folder, self.player, self.said.append)
        write(self.local, "Starfield/Plugins.txt", PLAYER)                  # a put-back cut before the journal went
        self.assertTrue(instance.recover(self.player, lambda: False, self.said.append))
        self.assertFalse(os.path.exists(self.journal))
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.journal)) if ".after-" in n], [])

    def test_recover_and_play_put_the_list_back_even_with_a_broken_settings_file(self):
        instance.swap_in(self.folder, self.player, self.said.append)
        bad = os.path.join(self.root, "bad.json")
        write(self.root, "bad.json", b'{"no_such_setting": 1}')
        spec = importlib.util.spec_from_file_location("launcher_cli_bad", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with mock.patch.object(cli.restore, "game_running", return_value=False), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["instance", "recover", "--settings", bad]), 0)
            self.assertEqual(self.read(self.player), PLAYER)
            instance.swap_in(self.folder, self.player, self.said.append)
            self.assertNotEqual(cli.main(["play", "--settings", bad]), 0)   # the settings refuse the play itself
        self.assertEqual(self.read(self.player), PLAYER)                    # but the list came back first

    def test_the_folders_real_system_runs_our_tools_on_its_own_plugins_txt(self):
        made = {}

        def system(**kw):
            made.update(kw)
            return self.game()
        with mock.patch.object(crashwatch, "System", side_effect=system):
            crashwatch.play(self.values(), "ignored", say=self.said.append, folder=self.folder)
        self.assertEqual(made["env"]["LOCALAPPDATA"], instance.local_dir(self.folder))
        self.assertEqual(made["plugins_txt"], instance.plugins_txt(self.folder))
        with mock.patch.object(crashwatch.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            crashwatch.System(env=made["env"]).run(["x"])
        self.assertEqual(run.call_args.kwargs["env"]["LOCALAPPDATA"], instance.local_dir(self.folder))

    def test_the_folders_own_list_all_unticked_is_refused_before_any_swap(self):
        # #662: the folder's System reads the folder's list; the player's (ticked) is never swapped or touched
        write(instance.local_dir(self.folder), "Starfield/Plugins.txt", OURS.replace(b"*", b""))
        own = crashwatch.System(plugins_txt=instance.plugins_txt(self.folder))
        own.pids = lambda image=None: []                                     # never this PC's own process table
        why = crashwatch.unticked_ours(own, self.values(), self.folder)
        self.assertIn("every FO4SF plugin in Plugins.txt is unticked (2 listed", why)
        self.assertIn(instance.plugins_txt(self.folder), why)
        self.assertIn("the FO4SF game folder's own list", why)                # the remedy fits the folder
        with mock.patch.object(crashwatch, "System", side_effect=lambda **kw: own):
            with self.assertRaisesRegex(ValueError, "every FO4SF plugin"):
                crashwatch.play(self.values(), "ignored", say=self.said.append, folder=self.folder)
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertFalse(os.path.exists(self.journal))

    def test_a_kept_list_is_never_overwritten_and_a_retry_reuses_its_own(self):
        # #655 finding 3: the same second's name, with other bytes, gets -2; with the same bytes it is reused
        base = instance.plugins_txt(self.folder) + ".after-20261101-123456"
        os.makedirs(os.path.dirname(base), exist_ok=True)
        with open(base, "wb") as f:
            f.write(b"*Older.esm\r\n")
        self.assertEqual(instance._keep_after(base, b"*New.esm\r\n"), base + "-2")
        self.assertEqual(self.read(base), b"*Older.esm\r\n")
        self.assertEqual(instance._keep_after(base, b"*New.esm\r\n"), base + "-2")    # a retry: the same evidence
        self.assertEqual(instance._keep_after(base, b"*Older.esm\r\n"), base)
        self.assertEqual(instance._keep_after(base[:-1] + "9", b"*New.esm\r\n"), base + "-2")   # a later second too
        self.assertEqual(sorted(n for n in os.listdir(os.path.dirname(base)) if ".after-" in n),
                         [os.path.basename(base), os.path.basename(base) + "-2"])

    # --- the folder's own INI ------------------------------------------------------------------------------------
    def test_saves_go_to_their_own_folder_through_the_folders_ini(self):
        ini = os.path.join(self.folder, "Starfield.ini")
        instance.ensure_saves(self.folder, self.said.append)
        text = self.read(ini).decode()
        self.assertIn("[General]\r\nsLanguage=en\r\nSLocalSavePath=Saves\\FO4SF\\\r\n", text)   # CRLF kept
        before = self.read(ini)
        instance.ensure_saves(self.folder, self.said.append)
        self.assertEqual(self.read(ini), before)                             # once
        os.remove(ini)
        os.link(os.path.join(self.root, "Steam", "Starfield", "Starfield.ini"), ini)
        with self.assertRaisesRegex(instance.InstanceRefused, "second name"):
            instance.ensure_saves(self.folder)                              # never through a link to Steam's file

    def test_set_ini_key(self):
        self.assertEqual(instance.set_ini_key("", "General", "A", "1"), ("[General]\nA=1\n", True))
        self.assertEqual(instance.set_ini_key("[general]\na=1\n", "General", "A", "1"), ("[general]\na=1\n", False))
        self.assertEqual(instance.set_ini_key("[General]\nA=0\r\n[Display]\nB=2", "General", "A", "1")[0],
                         "[General]\nA=1\r\n[Display]\nB=2")
        self.assertEqual(instance.set_ini_key("[Display]\nB=2", "General", "A", "1")[0], "[Display]\nB=2\n[General]\nA=1\n")
        self.assertEqual(instance.set_ini_key("[General]\nX=1\n[D]\n", "General", "A", "1")[0], "[General]\nX=1\nA=1\n[D]\n")

    # --- our tools on the folder ---------------------------------------------------------------------------------
    def test_run_gives_the_folder_its_own_plugins_txt_and_guards_the_target(self):
        seen = {}
        code = instance.run(self.folder, ["python", "exp_install.py", "install", "--starfield", self.folder],
                            call=lambda cmd, cwd, env: seen.update(env=env) or 0)
        self.assertEqual(code, 0)
        self.assertEqual(seen["env"]["LOCALAPPDATA"], instance.local_dir(self.folder))
        steam = os.path.join(self.root, "Steam", "Starfield")
        for cmd in (["x", "--starfield", steam], ["x", f"--starfield={steam}"], ["x", "--starf", steam],
                    ["x", f"--sta={steam}"]):
            with self.assertRaisesRegex(instance.InstanceRefused, "is not the FO4SF game folder"):
                instance.run(self.folder, cmd, call=lambda *a, **k: 0)
        # review of the stack, P3 4: a tool's default --starfield is the player's install, so one must be named, once
        for cmd in (["x", "run"], ["x", "--starfield", self.folder, "--starf", self.folder]):
            with self.assertRaisesRegex(instance.InstanceRefused, "once"):
                instance.run(self.folder, cmd, call=lambda *a, **k: 0)
        rel = os.path.relpath(self.folder, self.root)                       # resolved from the command's own folder
        self.assertEqual(instance.run(self.folder, ["x", "--starfield", rel], cwd=self.root,
                                      call=lambda *a, **k: 0), 0)
        with self.assertRaisesRegex(instance.InstanceRefused, "is not the FO4SF game folder"):
            instance.run(self.folder, ["x", "--starfield", rel], cwd=os.path.join(self.root, "Steam"),
                         call=lambda *a, **k: 0)
        with self.assertRaisesRegex(instance.InstanceRefused, "running"):
            instance.run(self.folder, ["x"], running=lambda: True, call=lambda *a, **k: 0)
        with self.assertRaisesRegex(instance.InstanceRefused, "not a finished FO4SF game folder"):
            instance.run(steam, ["x"], call=lambda *a, **k: 0)

    # --- play ----------------------------------------------------------------------------------------------------
    def values(self, **kw):
        v = settings.defaults()
        v.update({"instance": self.folder, "route": "exe", "load_order": "off"})
        v.update(kw)
        return v

    def game(self, rewrite=None, **kw):
        sys_ = FakeSystem([(4242, 0, 30, 0)], **kw)
        start = sys_.start_game

        def start_game(route, starfield):
            self.during = (self.read(self.player), starfield)
            if rewrite is not None:
                with open(self.player, "wb") as f:
                    f.write(rewrite)
            start(route, starfield)
        sys_.start_game = start_game
        return sys_

    def play(self, values, system):
        return crashwatch.play(values, "ignored", system=system, say=self.said.append, folder=self.folder)

    def test_play_starts_the_folder_with_its_list_and_gives_the_players_back(self):
        sys_ = self.game(rewrite=b"*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n")
        r = self.play(self.values(papyrus_logging="on"), sys_)
        self.assertTrue(r["started"])
        self.assertEqual(self.during, (OURS, os.path.abspath(self.folder)))   # the folder, with FO4SF's list
        self.assertEqual(self.read(self.player), PLAYER)                    # and the player's back after it
        self.assertEqual(self.read(instance.plugins_txt(self.folder)), b"*FO4TerrainCore.esm\r\n*FO4Port.esm\r\n")
        ini = self.read(os.path.join(self.folder, "Starfield.ini")).decode()
        self.assertIn("bEnableLogging=1", ini)                               # Papyrus in the folder's own INI
        self.assertIn("SLocalSavePath=Saves\\FO4SF\\", ini)
        self.assertFalse(os.path.exists(self.journal))

    def test_route_steam_is_refused_for_the_folder(self):
        with self.assertRaisesRegex(ValueError, "route=steam"):
            self.play(self.values(route="steam"), self.game())
        self.assertEqual(self.read(self.player), PLAYER)

    def test_a_start_that_fails_gives_the_players_list_back(self):
        sys_ = self.game()
        sys_.start_error = OSError(2, "not found")
        with self.assertRaisesRegex(ValueError, "could not start"):
            self.play(self.values(), sys_)
        self.assertEqual(self.read(self.player), PLAYER)
        self.assertFalse(os.path.exists(self.journal))

    def test_a_game_still_running_keeps_the_swap_until_it_closes(self):
        sys_ = FakeSystem([])

        def pids(image=crashwatch.GAME_EXE):                                 # comes up just as the watch gives up
            return [4242] if sys_.started_at is not None and sys_.t - sys_.started_at >= 180 else []
        sys_.pids = pids
        r = self.play(self.values(), sys_)
        self.assertFalse(r["started"])
        self.assertTrue(os.path.exists(self.journal))                       # never swapped under a game
        self.assertEqual(self.read(self.player), OURS)
        self.assertTrue(any("comes back at the next launcher play" in s for s in self.said))
        self.assertTrue(instance.recover(self.player, lambda: False, self.said.append))   # once it has closed
        self.assertEqual(self.read(self.player), PLAYER)

    def test_play_command_uses_the_setting_and_refuses_another_starfield(self):
        spec = importlib.util.spec_from_file_location("launcher_cli_play", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        path = os.path.join(self.root, "s.json")
        settings.save(path, self.values())
        with mock.patch.object(cli.crashwatch, "play", return_value={"dry_run": True}) as play, \
                mock.patch.object(cli.instance, "recover", return_value=False) as recover:
            self.assertEqual(cli.main(["play", "--settings", path, "--dry-run"]), 0)
            self.assertEqual(play.call_args.kwargs["folder"], self.folder)
            recover.assert_not_called()                                     # a dry run only looks (P3 5)
            play.return_value = {"started": True}
            self.assertEqual(cli.main(["play", "--settings", path]), 0)
            recover.assert_called_once()
            self.assertEqual(recover.call_args.args[0], self.player)        # found from the player's list
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["play", "--settings", path, "--starfield", self.root]), 2)
        with mock.patch.object(cli.instance, "run", return_value=0) as run:
            self.assertEqual(cli.main(["instance", "run", "--settings", path, "--", "python", "x.py", "--a"]), 0)
            self.assertEqual(run.call_args.args[1], ["python", "x.py", "--a"])

    def test_the_setting_frees_papyrus_from_my_games(self):
        v = self.values(papyrus_logging="on", bridge="off")
        self.assertEqual(settings.problems(v), [])
        v["instance"] = ""
        self.assertTrue(any("my_games" in p for p in settings.problems(v)))


if __name__ == "__main__":
    unittest.main()
