"""Explicit order and implicit membership on synthetic loader files only."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import instance, release_load as rl, save_release as sr  # noqa: E402


class ReleaseLoadTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        self.my_games = self.root / "My Games"
        self.my_games.mkdir()
        self.plugins = Path(instance.plugins_txt(str(self.game)))
        self.plugins.parent.mkdir(parents=True)
        self.plugins.write_bytes(b"\xef\xbb\xbf# fixture\r\n*FO4Port.esm\r\n*FO4SFBridge.esm\r\n")
        names = ("Starfield.esm", "FO4Port.esm", "FO4SFBridge.esm")
        for name in names:
            (self.data / name).write_bytes(("opaque " + name).encode())
        self.release = {"schema": 2, "implicit_loaders": {"game": None, "my_games": None}, "release_id": "A", "masters": [
            dict(sr.identity(self.data / name), name=name) for name in names], "state_layouts": {}}

    def check(self, release=None):
        rl.check(release or self.release, self.game, self.my_games)

    def test_matching_order_is_read_only_and_case_insensitive(self):
        self.plugins.write_text("# comment\n*fo4PORT.esm\n*FO4SFBRIDGE.ESM\nInactive.esm\n")
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.root.rglob("*") if p.is_file()}
        self.check()
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
                                 for p in self.root.rglob("*") if p.is_file()})

    def test_changed_explicit_set_or_order_refuses(self):
        for text in ("*FO4SFBridge.esm\n*FO4Port.esm\n", "*FO4Port.esm\nFO4SFBridge.esm\n",
                     "*FO4Port.esm\n*FO4SFBridge.esm\n*Other.esm\n"):
            self.plugins.write_text(text)
            with self.assertRaisesRegex(ValueError, "active master set/order"):
                self.check()

    def test_added_implicit_master_refuses(self):
        (self.data / "OldMars.esm").write_bytes(b"new implicit master")
        with self.assertRaisesRegex(ValueError, "built-in master membership"):
            self.check()

    def test_missing_declared_implicit_master_refuses(self):
        (self.data / "Starfield.esm").unlink()
        with self.assertRaisesRegex(ValueError, "built-in master membership"):
            self.check()

    def test_explicit_listing_of_installed_builtin_does_not_duplicate_it(self):
        self.plugins.write_text("*Starfield.esm\n*FO4Port.esm\n*FO4SFBridge.esm\n")
        self.check()

    def test_missing_builtin_on_active_line_refuses(self):
        self.plugins.write_text("*OldMars.esm\n*FO4Port.esm\n*FO4SFBridge.esm\n")
        with self.assertRaisesRegex(ValueError, "missing built-in"):
            self.check()

    def test_duplicate_even_inactive_entry_refuses(self):
        self.plugins.write_text("FO4Port.esm\n*fo4port.ESM\n*FO4SFBridge.esm\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.check()

    def test_unknown_or_non_utf8_entries_refuse(self):
        for raw in (b"*not-a-plugin\n", b"\xff\xfe\x00"):
            self.plugins.write_bytes(raw)
            with self.assertRaises(ValueError):
                self.check()

    def test_missing_plugins_file_is_unknown_not_empty(self):
        self.plugins.unlink()
        with self.assertRaises(OSError):
            self.check()

    def test_stestfile_loader_override_refuses(self):
        (self.game / "Starfield.ini").write_text("[General]\nsTestFile1=Other.esm\n")
        with self.assertRaisesRegex(ValueError, "sTestFile"):
            self.check()

    def test_ccc_foreign_plugin_override_refuses(self):
        for folder in (self.game, self.my_games):
            path = folder / "Starfield.ccc"
            path.write_text("Starfield.esm\nOther.esm\n")
            self.release["implicit_loaders"] = rl.implicit_inputs(self.game, self.my_games)
            with self.assertRaisesRegex(ValueError, "loader configuration"):
                self.check()
            path.unlink()

    def test_shadow_plugin_refuses(self):
        shadow = self.my_games / "Data"
        shadow.mkdir()
        (shadow / "FO4Port.esm").write_bytes(b"another file could load")
        with self.assertRaisesRegex(ValueError, "copy of Data"):
            self.check()

    def test_linked_plugin_list_refuses(self):
        target = self.root / "other-plugins.txt"
        target.write_bytes(self.plugins.read_bytes())
        self.plugins.unlink()
        try:
            self.plugins.symlink_to(target)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, "link"):
            self.check()

    def test_my_games_must_be_known_and_metadata_bounded(self):
        with self.assertRaisesRegex(ValueError, "My Games"):
            rl.check(self.release, self.game, "")
        self.plugins.write_bytes(b"#" * (sr.MAX_METADATA_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "limit"):
            self.check()

    def test_declared_explicit_order_is_authoritative(self):
        release = copy.deepcopy(self.release)
        release["masters"][1:] = reversed(release["masters"][1:])
        with self.assertRaisesRegex(ValueError, "set/order"):
            self.check(release)

    def test_unsupported_loader_encoding_is_unknown_not_a_clean_config(self):
        for raw in ("[General]\nsTestFile1=Other.esm".encode("utf-16"), b"\xff invalid"):
            (self.game / "Starfield.ini").write_bytes(raw)
            with self.assertRaises(ValueError):
                self.check()

    def test_pinned_ccc_add_remove_change_and_reorder_refuse(self):
        for folder in (self.game, self.my_games):
            with self.subTest(folder=folder):
                path = folder / "Starfield.ccc"
                self.release["implicit_loaders"] = rl.implicit_inputs(self.game, self.my_games)
                path.write_text("Starfield.esm\n")
                with self.assertRaisesRegex(ValueError, "implicit loader configuration differs"):
                    self.check()
                self.release["implicit_loaders"] = rl.implicit_inputs(self.game, self.my_games)
                self.check()
                for raw in (b"# changed comment\nStarfield.esm\n", b"OldMars.esm\nStarfield.esm\n"):
                    path.write_bytes(raw)
                    with self.assertRaisesRegex(ValueError, "implicit loader configuration differs"):
                        self.check()
                path.unlink()
                with self.assertRaisesRegex(ValueError, "implicit loader configuration differs"):
                    self.check()

    def test_implicit_pin_shape_is_required_and_strict(self):
        for pins in (None, {}, {"game": None}, {"game": None, "my_games": None, "other": None},
                     {"game": {"size": True, "sha256": "0" * 64}, "my_games": None},
                     {"game": {"size": 1, "sha256": "bad"}, "my_games": None}):
            with self.subTest(pins=pins), self.assertRaises(ValueError):
                self.check(dict(self.release, implicit_loaders=pins))

    def test_old_draft_schema_is_not_silently_upgraded(self):
        with self.assertRaisesRegex(ValueError, "unknown release schema"):
            self.check(dict(self.release, schema=1))
        old = dict(self.release)
        del old["implicit_loaders"]
        with self.assertRaisesRegex(ValueError, "missing or unknown"):
            self.check(old)

    def test_pin_locations_cannot_be_swapped(self):
        (self.game / "Starfield.ccc").write_text("Starfield.esm\n")
        pins = rl.implicit_inputs(self.game, self.my_games)
        self.release["implicit_loaders"] = dict(game=pins["my_games"], my_games=pins["game"])
        with self.assertRaisesRegex(ValueError, "implicit loader configuration differs"):
            self.check()

    def test_capture_refuses_linked_or_oversized_ccc(self):
        path = self.game / "Starfield.ccc"
        path.write_bytes(b"#" * (sr.MAX_METADATA_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "limit"):
            rl.implicit_inputs(self.game, self.my_games)
        path.unlink()
        target = self.root / "foreign.ccc"
        target.write_text("Starfield.esm\n")
        try:
            path.symlink_to(target)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaisesRegex(ValueError, "link"):
            rl.implicit_inputs(self.game, self.my_games)

    def test_changed_ccc_during_read_refuses(self):
        path = self.game / "Starfield.ccc"
        path.write_text("Starfield.esm\n")
        actual = rl.os.fstat
        calls = []
        def changing(fd):
            result = actual(fd)
            calls.append(result)
            if len(calls) == 1:
                path.write_text("# changed during read\nStarfield.esm\n")
            return result
        with mock.patch.object(rl.os, "fstat", side_effect=changing):
            with self.assertRaisesRegex(ValueError, "changed while reading"):
                rl.implicit_inputs(self.game, self.my_games)

    def test_builtin_only_ccc_uses_existing_loader_rules_without_claiming_indexes(self):
        (self.game / "Starfield.ccc").write_text("Starfield.esm\n")
        self.release["implicit_loaders"] = rl.implicit_inputs(self.game, self.my_games)
        self.check()


if __name__ == "__main__":
    unittest.main()
