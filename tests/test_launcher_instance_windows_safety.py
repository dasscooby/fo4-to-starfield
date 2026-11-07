"""Synthetic Windows regressions for the three safety findings tracked by PR #647 / issue #655 (Codex, #657). The fix in
instance.py makes them pass, so they are plain tests now; tests/test_launcher_instance.py checks the same rules with
POSIX symlinks, so CI on Linux covers them too. Junctions and their targets live
only below the synthetic temp root; cleanup removes each junction itself before the temp root.
"""
import datetime as datetime_module
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import files, instance


PLAYER_BYTES = b"# synthetic player list\r\n*PlayerPack.esm\r\n"
FO4SF_BYTES = b"*FO4SF.esm\r\n"
UNKNOWN_BYTES = b"*UnknownAfterCrash.esm\r\n"


def write(path, raw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(raw)


def tree_snapshot(root):
    """Bytes of ordinary files under a synthetic root; never descends through directory links."""
    result = {}
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(current, name))
                   and not getattr(os.path, "isjunction", lambda _p: False)(os.path.join(current, name))]
        for name in names:
            path = os.path.join(current, name)
            with open(path, "rb") as f:
                result[os.path.relpath(path, root)] = f.read()
    return result


class WindowsInstanceSafetyRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pr647-safety-")
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def make_junction(self, link, target):
        if os.name != "nt" or not hasattr(os.path, "isjunction"):
            self.skipTest("Windows directory junction support is unavailable")
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.makedirs(target, exist_ok=True)
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", link, target],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest(f"could not create an NTFS junction: {result.stdout.strip()} {result.stderr.strip()}")
        # Registered after temp.cleanup, so LIFO cleanup removes the junction itself first. os.rmdir removes the
        # reparse point and does not recurse into its target.
        self.addCleanup(self.remove_junction, link)
        if not os.path.isjunction(link):
            self.skipTest("mklink did not produce a directory junction")

    @staticmethod
    def remove_junction(path):
        if os.path.lexists(path) and getattr(os.path, "isjunction", lambda _p: False)(path):
            os.rmdir(path)

    @staticmethod
    def disk_usage(_path):
        return SimpleNamespace(free=500 * 1024 ** 3)

    def test_refuses_descendant_junction_before_any_external_file_is_written(self):
        source = os.path.join(self.root, "source", "Starfield")
        write(os.path.join(source, "Starfield.exe"), b"synthetic game executable")
        write(os.path.join(source, "Tools", "Archive2.exe"), b"synthetic tool")

        target = os.path.join(self.root, "FO4SF", "Starfield")
        os.makedirs(target)
        files.save_json(os.path.join(target, instance.RECORD),
                        {"schema": 1, "source": os.path.abspath(source), "made": [], "complete": False})
        exterior = os.path.join(self.root, "synthetic-exterior")
        os.makedirs(exterior)
        junction = os.path.join(target, "Tools")
        self.make_junction(junction, exterior)
        before = tree_snapshot(exterior)

        refusal = None
        try:
            instance.create(source, target, min_free_gb=0, disk_usage=self.disk_usage, say=lambda *_: None)
        except instance.InstanceRefused as exc:
            refusal = exc

        after = tree_snapshot(exterior)
        self.assertEqual(after, before, "instance creation wrote into the junction target")
        self.assertIsNotNone(refusal, "instance creation must refuse a destination containing a junction")

    def test_a_junction_planted_during_the_run_is_refused_at_that_file(self):
        # the Windows form of test_launcher_instance's mid-run link test, which needs POSIX symlink rights here
        source = os.path.join(self.root, "source", "Starfield")
        write(os.path.join(source, "Starfield.exe"), b"synthetic game executable")
        write(os.path.join(source, "Data", "Starfield.esm"), b"synthetic game plugin")
        write(os.path.join(source, "Tools", "Archive2.exe"), b"synthetic tool")
        target = os.path.join(self.root, "FO4SF", "Starfield")
        exterior = os.path.join(self.root, "synthetic-exterior")
        os.makedirs(exterior)
        made = []

        def link_then_plant(src, dst):
            os.link(src, dst)
            made.append(dst)
            if len(made) == 1:                              # after Data's first link: a junction where Tools will go
                self.make_junction(os.path.join(target, "Tools"), exterior)
        with self.assertRaisesRegex(instance.InstanceRefused, "is a link or junction"):
            instance.create(source, target, min_free_gb=0, disk_usage=self.disk_usage, say=lambda *_: None,
                            link=link_then_plant)
        self.assertEqual(tree_snapshot(exterior), {}, "instance creation wrote into the junction target")

    def test_refuses_target_whose_resolved_path_is_inside_steamapps(self):
        common = os.path.join(self.root, "SteamLibrary", "steamapps", "common")
        source = os.path.join(common, "Starfield")
        write(os.path.join(source, "Starfield.exe"), b"synthetic game executable")
        alias = os.path.join(self.root, "library-alias")
        self.make_junction(alias, common)
        target = os.path.join(alias, "FO4SF")
        before = tree_snapshot(common)

        refusal = None
        try:
            instance.check_target(source, target, 0, 0, self.disk_usage)
        except instance.InstanceRefused as exc:
            refusal = exc

        after = tree_snapshot(common)
        self.assertEqual(after, before, "target validation changed the synthetic Steam library")
        self.assertIsNotNone(refusal, "the resolved target is inside synthetic SteamLibrary\\steamapps")
        self.assertFalse(os.path.lexists(target), "refusal must happen before creating the target")

    def test_recovery_retry_after_post_preservation_failure_restores_exact_player_bytes(self):
        folder = os.path.join(self.root, "FO4SF", "Starfield")
        player = os.path.join(self.root, "profile", "Local", "Starfield", "Plugins.txt")
        own_plugins = instance.plugins_txt(folder)
        journal = instance.journal_path(player)
        write(own_plugins, FO4SF_BYTES)
        write(player, PLAYER_BYTES)
        preserved = {}

        def preserved_unknown_lists():
            directory = os.path.dirname(journal)                # kept beside the journal, outside the folder
            prefix = "Plugins.txt.after-"
            found = {}
            for name in os.listdir(directory):
                path = os.path.join(directory, name)
                if name.startswith(prefix) and os.path.isfile(path):
                    with open(path, "rb") as f:
                        if f.read() == UNKNOWN_BYTES:
                            found[path] = UNKNOWN_BYTES
            return found

        real_datetime = datetime_module.datetime

        class FrozenDateTime(real_datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 11, 1, 12, 34, 56, tzinfo=tz)

        with mock.patch.object(datetime_module, "datetime", FrozenDateTime):
            instance.swap_in(folder, player, say=lambda *_: None)
            write(player, UNKNOWN_BYTES)
            original_put = instance._put
            injected = {"done": False}

            def fail_once_after_unknown_bytes_are_preserved(path, raw, expect):
                if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(player)) \
                        and not injected["done"]:
                    preserved.update(preserved_unknown_lists())
                    self.assertTrue(preserved, "failure injection must follow preservation")
                    injected["done"] = True
                    raise OSError("synthetic interruption after preserving the unexpected list")
                return original_put(path, raw, expect)

            with mock.patch.object(instance, "_put", side_effect=fail_once_after_unknown_bytes_are_preserved):
                with self.assertRaisesRegex(OSError, "synthetic interruption"):
                    instance.recover(player, lambda: False, say=lambda *_: None)

            self.assertTrue(injected["done"], "the one-shot failure was not injected")
            self.assertTrue(os.path.isfile(journal), "journal must survive interruption")
            self.assertTrue(preserved_unknown_lists())

            recovered = instance.recover(player, lambda: False, say=lambda *_: None)

            self.assertTrue(recovered)
            with open(player, "rb") as f:
                self.assertEqual(f.read(), PLAYER_BYTES)
            self.assertTrue(preserved_unknown_lists())
            for path, original in preserved.items():
                with open(path, "rb") as f:
                    self.assertEqual(f.read(), original, "retry must preserve the earlier evidence unchanged")
            self.assertFalse(os.path.exists(journal), "successful retry closes the journal")


if __name__ == "__main__":
    unittest.main()
