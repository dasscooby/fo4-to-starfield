"""The FO4SF game folder (src/fo4sf/launcher/instance.py) made from a synthetic Starfield folder: hard links for the game's
files, copies of the game folder's INIs, only the game's own files in Data, nothing written in the source, nothing
overwritten, and a stopped run goes on. No game."""
import contextlib
import hashlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import files, instance  # noqa: E402

GAME = {
    "Starfield.exe": b"MZ game",
    "steam_api64.dll": b"MZ steam",
    "sfse_loader.exe": b"MZ sfse",
    "Starfield.ini": b"[General]\r\nsLanguage=en\r\n",
    "Ultra.ini": b"[Display]\r\n",
    "Tools/Archive2/Archive2.exe": b"MZ archive2",
    "Data/Starfield.esm": b"TES4 sf",
    "Data/Starfield - Textures01.ba2": b"BTDX tex",
    "Data/Constellation.esm": b"TES4 cons",
    "Data/Constellation - Localization.ba2": b"BTDX loc",
    "Data/SFBGS003.esm": b"TES4 003",
    "Data/SFBGS003 - Main.ba2": b"BTDX 003",
    "Data/BlueprintShips-Starfield.esm": b"TES4 bp",
    "Data/BlueprintShips-Starfield - Localization.ba2": b"BTDX bploc",
}
MODS = {                                        # the player's mod pack and our installs: never in the FO4SF folder
    "Data/SomeOwnerMod.esm": b"TES4 mod",
    "Data/SomeOwnerMod - Main.ba2": b"BTDX mod",
    "Data/FO4Port.esm": b"TES4 port",
    "Data/FO4Port.deploy.json": b"{}",
    "Data/textures/loose.dds": b"DDS ",
    "Data/SFSE/Plugins/SomeOwnerPlugin.dll": b"MZ plug",
}


def write(root, rel, data):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def digest_tree(root):
    out = {}
    for d, _dirs, names in os.walk(root):
        for n in names:
            p = os.path.join(d, n)
            with open(p, "rb") as f:
                out[os.path.relpath(p, root)] = (hashlib.sha256(f.read()).hexdigest(), os.stat(p).st_mtime_ns)
    return out


def plenty(_path):
    return SimpleNamespace(free=500 * 1024 ** 3)


class InstanceTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.src = os.path.join(self.root, "SteamLibrary", "steamapps", "common", "Starfield")
        for rel, data in {**GAME, **MODS}.items():
            write(self.src, rel, data)
        self.dst = os.path.join(self.root, "FO4SF", "Starfield")

    def create(self, **kw):
        kw.setdefault("disk_usage", plenty)
        kw.setdefault("say", lambda *_: None)
        return instance.create(self.src, self.dst, **kw)

    def test_plan_links_data_and_tools_copies_the_rest_and_leaves_the_mods_out(self):
        p = instance.plan(self.src, self.dst)
        linked = [r for r in GAME if r.startswith(("Data/", "Tools/")) and not r.endswith(".ini")]
        self.assertEqual(sorted(p["link"]), sorted(linked))
        self.assertEqual(sorted(p["copy"]), sorted(r for r in GAME if r not in linked))   # the exe, DLLs, SFSE, INIs
        self.assertEqual(sorted(p["left_out"]), ["Data/FO4Port.deploy.json", "Data/FO4Port.esm", "Data/SFSE/",
                                                 "Data/SomeOwnerMod - Main.ba2", "Data/SomeOwnerMod.esm", "Data/textures/"])
        self.assertTrue(any("left out" in line for line in instance.summary(p)))

    def test_the_players_add_ons_beside_the_exe_are_left_out_and_its_files_are_copies(self):
        # review of the stack (second round), P2: a linked top-level file carried in-place writes both ways
        for rel in ("dxgi.dll", "ReShade.ini", "reshade-shaders/Shaders/x.fx", "Starfield_10-31-18-44.dmp",
                    "enbseries/a.fx"):
            write(self.src, rel, b"player's")
        p = instance.plan(self.src, self.dst)
        for rel in ("dxgi.dll", "ReShade.ini", "reshade-shaders/", "Starfield_10-31-18-44.dmp", "enbseries/"):
            self.assertIn(rel, p["left_out"])
        self.create()
        self.assertFalse(os.path.exists(os.path.join(self.dst, "dxgi.dll")))
        with open(os.path.join(self.dst, "sfse_loader.exe"), "r+b") as f:  # an SFSE update writes in place
            f.write(b"NEW")
        with open(os.path.join(self.src, "sfse_loader.exe"), "rb") as f:
            self.assertEqual(f.read(), GAME["sfse_loader.exe"])               # the player's install is untouched

    def test_create_makes_links_and_copies_and_never_writes_in_the_source(self):
        before = digest_tree(self.src)
        p = self.create()
        self.assertEqual(digest_tree(self.src), before)                      # the Steam install is untouched
        for rel in GAME:
            src, dst = os.path.join(self.src, *rel.split("/")), os.path.join(self.dst, *rel.split("/"))
            with open(dst, "rb") as f:
                self.assertEqual(f.read(), GAME[rel])
            self.assertEqual(os.path.samefile(src, dst), rel in p["link"], rel)
        for rel in MODS:
            self.assertFalse(os.path.exists(os.path.join(self.dst, *rel.split("/"))), rel)
        with open(os.path.join(self.dst, "Starfield.ini"), "ab") as f:      # the FO4SF folder's settings are its own
            f.write(b"SLocalSavePath=Saves\\FO4SF\\\r\n")
        with open(os.path.join(self.src, "Starfield.ini"), "rb") as f:
            self.assertEqual(f.read(), GAME["Starfield.ini"])
        rec = files.load_json(os.path.join(self.dst, instance.RECORD))
        self.assertTrue(rec["complete"])
        self.assertEqual(os.path.normcase(rec["source"]), os.path.normcase(os.path.abspath(self.src)))

    def test_a_kept_data_folder_comes_along(self):
        p = instance.plan(self.src, self.dst, keep_data_dirs=["Textures"])
        self.assertIn("Data/textures/loose.dds", p["link"])
        self.assertNotIn("Data/textures/", p["left_out"])

    def test_a_stopped_run_goes_on_and_a_rerun_changes_nothing(self):
        calls = []

        def stop_after_three(src, dst):
            if len(calls) == 3:
                raise OSError("power cut")
            calls.append(dst)
            os.link(src, dst)
        with self.assertRaises(OSError):
            self.create(link=stop_after_three)
        self.assertFalse(files.load_json(os.path.join(self.dst, instance.RECORD))["complete"])
        self.create()
        self.assertTrue(files.load_json(os.path.join(self.dst, instance.RECORD))["complete"])
        before = digest_tree(self.dst)
        self.create()
        after = digest_tree(self.dst)
        self.assertEqual(after.pop(instance.RECORD)[0], before.pop(instance.RECORD)[0])   # rewritten, same content
        self.assertEqual(after, before)                                    # every game file as it was

    def test_a_file_that_is_not_the_games_is_never_overwritten(self):
        self.create()
        esm = os.path.join(self.dst, "Data", "Starfield.esm")              # a linked file
        os.remove(esm)
        write(self.dst, "Data/Starfield.esm", b"TES4 something else")
        with self.assertRaisesRegex(instance.InstanceRefused, "not the game's file"):
            self.create()
        with open(esm, "rb") as f:
            self.assertEqual(f.read(), b"TES4 something else")
        # the folder's own copies (the exe after an SFSE update in it, its INIs) are its own: a rerun leaves them
        os.remove(esm)
        os.link(os.path.join(self.src, "Data", "Starfield.esm"), esm)
        write(self.dst, "sfse_loader.exe", b"MZ newer sfse")
        self.create()
        with open(os.path.join(self.dst, "sfse_loader.exe"), "rb") as f:
            self.assertEqual(f.read(), b"MZ newer sfse")
        # checked before the record changes: the refused rerun leaves the finished folder finished (playable)
        self.assertTrue(files.load_json(os.path.join(self.dst, instance.RECORD))["complete"])

    # --- review of the stack, P2 1: a rerun or a resume never strands the folder -----------------------------------
    def test_a_rerun_after_the_folder_changed_its_own_ini_is_fine(self):
        self.create()
        instance.ensure_saves(self.dst, say=lambda *_: None)               # what every play does
        self.create()                                                      # a rerun of a finished folder
        self.assertTrue(files.load_json(os.path.join(self.dst, instance.RECORD))["complete"])
        with open(os.path.join(self.dst, "Starfield.ini"), "rb") as f:
            self.assertIn(b"SLocalSavePath", f.read())                      # the folder's own INI kept

    def test_a_run_stopped_after_a_copy_but_before_its_record_goes_on(self):
        from unittest import mock
        real, calls = instance.files.save_json, []

        def stop_at_the_first_copys_record(path, data):
            calls.append(path)
            if len(calls) == 2:                                            # 1: before the files, 2: after a copy
                raise OSError("power cut")
            real(path, data)
        with mock.patch.object(instance.files, "save_json", side_effect=stop_at_the_first_copys_record):
            with self.assertRaises(OSError):
                self.create()
        rec = files.load_json(os.path.join(self.dst, instance.RECORD))
        self.assertFalse(rec["complete"])
        self.assertEqual([r for r in rec["made"] if r.endswith(".ini")], [])   # the copy is there, its record not
        self.create()
        rec = files.load_json(os.path.join(self.dst, instance.RECORD))
        self.assertTrue(rec["complete"])
        self.assertIn("Starfield.ini", rec["made"])
        # a copy the record lacks must still be the game's bytes
        os.remove(os.path.join(self.dst, "Ultra.ini"))
        rec["made"].remove("Ultra.ini")
        files.save_json(os.path.join(self.dst, instance.RECORD), rec)
        write(self.dst, "Ultra.ini", b"[Display]\r\nmine=1\r\n")
        with self.assertRaisesRegex(instance.InstanceRefused, "not the game's file"):
            self.create()

    def test_a_copy_stopped_half_way_never_takes_its_name(self):
        from unittest import mock
        real = instance.shutil.copy2

        def half(src, dst):
            with open(dst, "wb") as f:
                f.write(b"[Gen")
            raise OSError("power cut")
        first = instance.plan(self.src, self.dst)["copy"][0]              # the first file a run copies
        with mock.patch.object(instance.shutil, "copy2", side_effect=half):
            with self.assertRaises(OSError):
                self.create()
        self.assertFalse(os.path.exists(os.path.join(self.dst, first)))
        self.assertTrue(os.path.exists(os.path.join(self.dst, first + instance.PART)))
        with mock.patch.object(instance.shutil, "copy2", side_effect=real):
            self.create()
        with open(os.path.join(self.dst, first), "rb") as f:
            self.assertEqual(f.read(), GAME[first])
        self.assertFalse(os.path.exists(os.path.join(self.dst, first + instance.PART)))

    def test_an_ini_in_a_kept_folder_is_copied_not_linked(self):
        write(self.src, "Data/SFSE/Plugins/SomeOwnerPlugin.ini", b"[Main]\r\nOn=1\r\n")
        p = instance.plan(self.src, self.dst, keep_data_dirs=["SFSE"])
        self.assertIn("Data/SFSE/Plugins/SomeOwnerPlugin.ini", p["copy"])
        self.assertIn("Data/SFSE/Plugins/SomeOwnerPlugin.dll", p["link"])

    def test_a_drive_or_share_that_is_not_there_is_refused_not_looped(self):
        from unittest import mock
        with mock.patch.object(instance.os.path, "isdir", return_value=False):
            with self.assertRaisesRegex(instance.InstanceRefused, "no such drive or share"):
                instance.check_target(self.src, os.path.join(self.root, "nowhere", "FO4SF"), 0, 0, plenty)

    def test_refusals_before_anything_is_written(self):
        cases = [
            (os.path.join(self.src, "FO4SF"), "outside the Starfield install"),
            (os.path.join(self.root, "SteamLibrary", "steamapps", "FO4SF"), "steamapps"),
            (os.path.join(self.root, "OneDrive", "FO4SF"), "onedrive"),
            (os.path.join(self.root, "OneDrive - Contoso", "FO4SF"), "onedrive - contoso"),
            (os.path.join(self.root, "Dropbox", "FO4SF"), "dropbox"),
            (os.path.join(self.root, "Dropbox (Personal)", "FO4SF"), "dropbox"),
            (os.path.join(self.root, "Box", "FO4SF"), "box"),
        ]
        for target, text in cases:
            with self.subTest(target=target):
                with self.assertRaisesRegex(instance.InstanceRefused, text):
                    instance.create(self.src, target, disk_usage=plenty, say=lambda *_: None)
                self.assertFalse(os.path.exists(os.path.join(target, instance.RECORD)))
        busy = os.path.join(self.root, "busy")
        write(busy, "notes.txt", b"mine")
        with self.assertRaisesRegex(instance.InstanceRefused, "not empty"):
            instance.create(self.src, busy, disk_usage=plenty)
        with self.assertRaisesRegex(instance.InstanceRefused, "GB would be left free"):
            self.create(disk_usage=lambda _p: SimpleNamespace(free=10 * 1024 ** 3))
        with self.assertRaisesRegex(instance.InstanceRefused, "not a Starfield game folder"):
            instance.plan(os.path.join(self.root, "nothing"), self.dst)

    def test_another_drive_is_refused(self):
        from unittest import mock
        devices = {os.path.abspath(self.src): 1, os.path.abspath(self.root): 2}
        with mock.patch.object(instance, "_device", side_effect=lambda p: devices[os.path.abspath(p)]):
            with self.assertRaisesRegex(instance.InstanceRefused, "another drive"):
                instance.check_target(self.src, os.path.join(self.root, "new"), 40, 0, plenty)

    def test_a_folder_made_from_another_install_is_refused(self):
        self.create()
        other = os.path.join(self.root, "Other", "Starfield")
        for rel, data in GAME.items():
            write(other, rel, data)
        with self.assertRaisesRegex(instance.InstanceRefused, "was made from"):
            instance.create(other, self.dst, disk_usage=plenty)

    def symlink(self, link, target):
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError) as e:          # Windows without the symlink right
            self.skipTest(f"no directory symlinks here: {e}")

    def test_a_link_inside_the_folder_is_refused_before_anything_is_written_through_it(self):
        # #655 finding 1, with a POSIX symlink in place of the NTFS junction (tests/test_launcher_instance_windows_safety.py)
        exterior = os.path.join(self.root, "exterior")
        os.makedirs(exterior)
        os.makedirs(self.dst)
        files.save_json(os.path.join(self.dst, instance.RECORD),
                        {"schema": 1, "source": os.path.abspath(self.src), "made": [], "complete": False})
        self.symlink(os.path.join(self.dst, "Data"), exterior)
        with self.assertRaisesRegex(instance.InstanceRefused, "link or junction inside the FO4SF folder"):
            self.create()
        self.assertEqual(os.listdir(exterior), [])
        self.assertFalse(os.path.exists(os.path.join(self.dst, "Starfield.exe")))   # refused before the first file

    def test_a_link_that_appears_during_the_run_is_refused_at_that_file(self):
        exterior = os.path.join(self.root, "exterior")
        os.makedirs(exterior)
        made = []

        def link_then_plant(src, dst):
            os.link(src, dst)
            made.append(dst)
            if len(made) == 1:                              # after the first file (in Data): a link where Tools goes
                self.symlink(os.path.join(self.dst, "Tools"), exterior)
        with self.assertRaisesRegex(instance.InstanceRefused, "is a link or junction"):
            self.create(link=link_then_plant)
        self.assertEqual(os.listdir(exterior), [])

    def test_an_alias_of_a_steam_library_is_refused(self):
        # #655 finding 2: the denylist sees the resolved path, not only the spelling given
        alias = os.path.join(self.root, "library-alias")
        self.symlink(alias, os.path.join(self.root, "SteamLibrary", "steamapps", "common"))
        target = os.path.join(alias, "FO4SF")
        with self.assertRaisesRegex(instance.InstanceRefused, "steamapps"):
            instance.check_target(self.src, target, 0, 0, plenty)
        self.assertFalse(os.path.lexists(target))

    def test_cli_plan_and_create(self):
        spec = importlib.util.spec_from_file_location("launcher_cli_inst", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["instance", "plan", "--starfield", self.src, "--at", self.dst,
                                       "--min-free-gb", "0"]), 0)
        self.assertIn("plan only", out.getvalue())
        self.assertFalse(os.path.exists(self.dst))                          # plan writes nothing
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["instance", "create", "--starfield", self.src, "--at", self.dst,
                                       "--min-free-gb", "0"]), 0)
            self.assertEqual(cli.main(["instance", "create", "--starfield", self.src,
                                       "--at", os.path.join(self.src, "x"), "--min-free-gb", "0"]), 2)
        self.assertTrue(os.path.isfile(os.path.join(self.dst, instance.RECORD)))


if __name__ == "__main__":
    unittest.main()
