"""scripts/game/plugin_toggle.py and how exp_install.py / bridge_install.py respect it. Synthetic game folder and
Plugins.txt; never a live install."""
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "game"))
import plugin_toggle as pt  # noqa: E402
import exp_install as exp  # noqa: E402
import bridge_install as bi  # noqa: E402
import load_order  # noqa: E402


def tes4(*masters):
    sub = b"".join(b"MAST" + struct.pack("<H", len(m) + 1) + m.encode() + b"\0" for m in masters)
    return b"TES4" + struct.pack("<I", len(sub)) + bytes(16) + sub


class ToggleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.game, self.data = root / "game", root / "game" / "Data"
        self.data.mkdir(parents=True)
        (root / "local" / "Starfield").mkdir(parents=True)
        self.txt = root / "local" / "Starfield" / "Plugins.txt"
        env = patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")})
        env.start()
        self.addCleanup(env.stop)
        (self.data / "FO4Port.esm").write_bytes(tes4("Starfield.esm"))
        (self.data / "Core.esm").write_bytes(tes4("FO4Port.esm"))
        (self.data / "Mission.esm").write_bytes(tes4("Core.esm"))
        (self.data / bi.PLUGIN).write_bytes(tes4())
        (self.data / exp.RECORD).write_text(json.dumps({"complete": True, "plugins": ["Core.esm", "Mission.esm"],
                                                       "files": {}, "plugins_txt": str(self.txt)}))
        (self.data / bi.ARCHIVE).write_bytes(b"BTDX")
        (self.data / bi.RECORD).write_text(json.dumps({
            "complete": True, "plugins_txt": str(self.txt),
            "files": {n: exp.digest(str(self.data / n)) for n in (bi.PLUGIN, bi.ARCHIVE)}}))
        self.original = "# keep\r\n*FO4Port.esm\r\n*Core.esm\r\n*Mission.esm\r\n*FO4SFBridge.esm\r\n"
        self.txt.write_bytes(self.original.encode())

    def run_cmd(self, *argv):
        with redirect_stdout(io.StringIO()) as buf:
            pt.main([*argv, "--starfield", str(self.game)])
        return buf.getvalue()

    def lines(self):
        return self.txt.read_bytes().decode().split("\r\n")[:-1]

    def test_hold_pair_with_an_unticked_bridge_and_two_foreign_kits_keeps_bytes(self):
        # Foreign to the toggle's install records; the bridge was already unticked before this hold.
        for p in ("FO4SFPipboyProbe.esm", "FO4SFRadsProbe.esm"):
            (self.data / p).write_bytes(tes4("Core.esm"))
        original = (self.original.replace("*FO4SFBridge.esm", "FO4SFBridge.esm")
                    + "*FO4SFPipboyProbe.esm\r\n*FO4SFRadsProbe.esm\r\n").encode()
        for with_order in (False, True):
            with self.subTest(launcher_load_order=with_order):
                self.txt.write_bytes(original)
                self.run_cmd("off", "--plugins", "Mission.esm")
                if with_order:
                    self.assertEqual(load_order.run("fix", str(self.game), say=lambda _: None), 0)
                self.run_cmd("on", "--plugins", "Mission.esm")
                if with_order:
                    self.assertEqual(load_order.run("fix", str(self.game), say=lambda _: None), 0)
                self.assertEqual(self.txt.read_bytes(), original)
                self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])

    def a(self):
        return SimpleNamespace(starfield=str(self.game))

    def test_off_and_on_round_trip_byte_for_byte(self):
        self.run_cmd("off", "--plugins", "Mission.esm,FO4SFBridge.esm", "--why", "crash split")
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "FO4SFBridge.esm"])
        rec = json.loads((self.data / exp.TOGGLE).read_text())
        self.assertEqual((rec["off"], rec["why"]), (["Mission.esm", "FO4SFBridge.esm"], "crash split"))
        self.assertNotIn("at", rec)                                    # Codex on #407: no timestamp in the record
        self.assertIn("already held off", self.run_cmd("off", "--plugins", "Mission.esm"))
        self.run_cmd("on", "--plugins", "FO4SFBridge.esm")
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], ["Mission.esm"])
        self.run_cmd("on")
        self.assertEqual(self.txt.read_bytes().decode(), self.original)
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])
        self.assertIn("nothing held off", self.run_cmd("on"))

    def test_off_again_unticks_a_held_plugin_the_game_ticked_again(self):
        # Codex on #407: the retry the order and relaunch checks advise reported success and changed nothing
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes(self.original.encode())       # the game ticked it again
        self.assertIn("held off", self.run_cmd("off", "--plugins", "Mission.esm"))
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "*FO4SFBridge.esm"])
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], ["Mission.esm"])
        self.assertIn("already held off", self.run_cmd("off", "--plugins", "Mission.esm"))

    def test_on_refuses_a_plugin_whose_master_the_game_unticked(self):
        # Codex on #407: Core.esm unticked by the game while Mission.esm was held
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes("# keep\r\n*FO4Port.esm\r\nCore.esm\r\nMission.esm\r\n*FO4SFBridge.esm\r\n".encode())
        before = self.txt.read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on", "--plugins", "Mission.esm")
        self.assertIn("Core.esm as a master, which is not active", str(cm.exception))
        self.assertEqual(self.txt.read_bytes(), before)
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], ["Mission.esm"])

    def test_off_refusals_change_nothing(self):
        for plugins, why in (("FO4Port.esm", "not a plugin our installers own"),
                             ("Core.esm", "Mission.esm stays active and needs Core.esm"),
                             ("", "off needs --plugins")):
            with self.subTest(plugins=plugins), self.assertRaises(SystemExit) as cm:
                self.run_cmd("off", "--plugins", plugins)
            self.assertIn(why, str(cm.exception))
        self.txt.write_bytes(self.original.replace("*Mission.esm", "Mission.esm").encode())
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("off", "--plugins", "Mission.esm")
        self.assertIn("missing, inactive or duplicated", str(cm.exception))
        self.assertFalse((self.data / exp.TOGGLE).exists())
        self.txt.write_bytes(self.original.encode())
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm")       # both together: nothing left needing Core
        self.assertEqual(self.lines()[2:4], ["Core.esm", "Mission.esm"])

    def test_installers_respect_the_toggle(self):
        self.run_cmd("off", "--plugins", "Mission.esm,FO4SFBridge.esm")
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(self.a()), 0)
        self.assertIn("held off: Mission.esm", buf.getvalue())
        with redirect_stdout(io.StringIO()):
            bi.order(SimpleNamespace(starfield=str(self.game), dir=""))    # never re-ticks a held bridge
        self.assertEqual(self.lines()[4], "FO4SFBridge.esm")
        for call, what in ((lambda: exp.uninstall(self.a()), "experiment not uninstalled"),
                           (lambda: bi.uninstall(self.a()), "bridge not uninstalled")):
            with self.subTest(what=what), self.assertRaises(SystemExit) as cm:
                call()
            self.assertIn(what, str(cm.exception))
            self.assertIn("plugin_toggle.py on", str(cm.exception))
        (self.data / bi.RECORD).rename(self.data / "bridge.json.bak")      # a NEW bridge install refuses too
        with patch.object(bi, "staged", return_value=("d", "p", "x")), patch.object(bi, "source_inventory", return_value={}), \
                self.assertRaises(SystemExit) as cm:
            bi.install(SimpleNamespace(starfield=str(self.game), dir="d"))
        self.assertIn("bridge not installed: plugins held off", str(cm.exception))
        (self.data / "bridge.json.bak").rename(self.data / bi.RECORD)
        self.txt.write_bytes(self.original.encode())                      # the game re-ticked a held plugin
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(self.a()), 8)
        self.assertIn("held off by plugin_toggle.py but active", buf.getvalue())

    def test_a_relaunch_of_the_same_experiment_keeps_held_plugins_off(self):
        self.run_cmd("off", "--plugins", "Mission.esm")
        rec = {"files": {}, "source_inputs": {"k": 1}}
        a = SimpleNamespace(starfield=str(self.game), exp_dir="x")
        with patch.object(exp, "source_inventory", return_value={"k": 1}):
            exp.verify_relaunch(a, str(self.data), ["Core.esm", "Mission.esm"], False, rec, exp.held_off(str(self.data)))
            with self.assertRaisesRegex(SystemExit, "inactive"):         # without the toggle it is a fault
                exp.verify_relaunch(a, str(self.data), ["Core.esm", "Mission.esm"], False, rec)
            self.txt.write_bytes(self.original.encode())                  # review pass on #407: ticked again
            with self.assertRaisesRegex(SystemExit, "held off by plugin_toggle.py but active in Plugins.txt: Mission.esm"):
                exp.verify_relaunch(a, str(self.data), ["Core.esm", "Mission.esm"], False, rec, exp.held_off(str(self.data)))

    def test_on_refuses_a_child_whose_master_stays_held(self):
        # Codex on #407: on --plugins Mission.esm after holding Core and Mission activated Mission without its master
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm")
        before, rec = self.txt.read_bytes(), (self.data / exp.TOGGLE).read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on", "--plugins", "Mission.esm")
        self.assertIn("Mission.esm needs Core.esm as a master, which stays held off", str(cm.exception))
        self.assertEqual((self.txt.read_bytes(), (self.data / exp.TOGGLE).read_bytes()), (before, rec))
        self.run_cmd("on", "--plugins", "Core.esm")                        # the master alone is fine
        self.run_cmd("on")
        self.assertEqual(self.txt.read_bytes().decode(), self.original)

    def test_a_held_bridge_ticked_again_is_refused_not_accepted(self):
        # Codex on #407: order and active accepted the record alone while *FO4SFBridge.esm was active again
        self.run_cmd("off", "--plugins", "FO4SFBridge.esm")
        self.txt.write_bytes(self.original.encode())
        with self.assertRaisesRegex(ValueError, "held off by plugin_toggle.py but active"):
            bi.order(SimpleNamespace(starfield=str(self.game), dir=""))
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(self.a()), 8)
        self.assertIn("but active in Plugins.txt: fo4sfbridge.esm", buf.getvalue())
        self.assertEqual(self.txt.read_bytes().decode(), self.original)       # nothing rewritten

    def test_order_refuses_a_held_plugin_ticked_again(self):
        # review pass on #407: order printed "order ok", exit 0, with *Mission.esm active while held
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes(self.original.encode())
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.order(self.a()), 6)
        self.assertIn("held off by plugin_toggle.py but active in Plugins.txt: Mission.esm", buf.getvalue())
        self.assertEqual(self.txt.read_bytes().decode(), self.original)       # nothing rewritten

    def test_order_skips_held_plugins(self):
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes("*Core.esm\r\n*FO4Port.esm\r\nMission.esm\r\n".encode())   # Core before its master
        with redirect_stdout(io.StringIO()) as buf, patch.object(exp, "require_complete_master"):
            self.assertEqual(exp.order(self.a()), 0)
        self.assertIn("held off (plugin_toggle.py), left unticked: Mission.esm", buf.getvalue())
        self.assertEqual(self.lines(), ["*FO4Port.esm", "*Core.esm", "Mission.esm"])

    def test_a_bad_record_and_a_lost_line(self):
        (self.data / exp.TOGGLE).write_text(json.dumps({"off": "Mission.esm"}))
        with self.assertRaises(SystemExit):
            self.run_cmd("status")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(exp.active(self.a()), 8)
        (self.data / exp.TOGGLE).unlink()
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes("*FO4Port.esm\r\n*Core.esm\r\n".encode())
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on")
        self.assertIn("no Plugins.txt line left for Mission.esm", str(cm.exception))
        self.assertEqual(json.loads(self.run_cmd("status"))["off"], ["Mission.esm"])

    def test_active_with_only_the_bridge_record(self):
        # Codex on #407: cycle.ps1 now runs active after the load with only the bridge record; it reads the toggle record
        # without assuming an experiment install
        (self.data / exp.RECORD).unlink()                  # a bridge-only install
        self.run_cmd("off", "--plugins", "FO4SFBridge.esm")
        a = SimpleNamespace(starfield=str(self.game))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(exp.active(a), 0)
        self.txt.write_bytes(self.original.encode())       # the game ticked the held bridge again
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(a), 8)
        self.assertIn("held off by plugin_toggle.py but active in Plugins.txt: fo4sfbridge.esm", buf.getvalue())


    def test_active_fails_when_the_game_unticks_a_bridge_that_is_not_held(self):
        # Codex on #407: with only the bridge record, active said "nothing installed" (exit 0) for an unticked bridge
        (self.data / exp.RECORD).unlink()
        self.assertEqual((exp.BRIDGE_RECORD, exp.BRIDGE_PLUGIN), (bi.RECORD, bi.PLUGIN))
        a = SimpleNamespace(starfield=str(self.game))
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(a), 0)
        self.assertIn("active: FO4SFBridge.esm", buf.getvalue())
        self.txt.write_bytes(self.original.replace("*FO4SFBridge.esm", "FO4SFBridge.esm").encode())
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(a), 8)
        self.assertIn("inactive in Plugins.txt: FO4SFBridge.esm", buf.getvalue())

    def test_off_and_on_refuse_a_record_from_another_profile(self):
        # Codex on #407: off compared nothing and rewrote this user's Plugins.txt under another user's record
        self.run_cmd("off", "--plugins", "Mission.esm")
        p = self.data / exp.TOGGLE
        rec = json.loads(p.read_text())
        rec["plugins_txt"] = str(self.txt.parent.parent / "Other" / "Plugins.txt")
        p.write_text(json.dumps(rec))
        before = self.txt.read_bytes()
        for argv in (("off", "--plugins", "FO4SFBridge.esm"), ("off", "--plugins", "Mission.esm"), ("on",)):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as cm:
                self.run_cmd(*argv)
            self.assertIn("is not the current user's", str(cm.exception))
            self.assertEqual(self.txt.read_bytes(), before)
            self.assertEqual(json.loads(p.read_text())["off"], ["Mission.esm"])

    def test_every_reader_of_the_hold_refuses_another_profile(self):
        # Codex on #407: held_off returned profile A's hold to relaunch and active under profile B
        self.run_cmd("off", "--plugins", "FO4SFBridge.esm")
        p = self.data / exp.TOGGLE
        rec = json.loads(p.read_text())
        rec["plugins_txt"] = str(self.txt.parent.parent / "Other" / "Plugins.txt")
        p.write_text(json.dumps(rec))
        with self.assertRaisesRegex(ValueError, "is not the current user's"):
            exp.held_off(str(self.data))
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(self.a()), 8)
        self.assertIn("is not the current user's", buf.getvalue())
        p.write_text(json.dumps(dict(rec, off=[])))          # nothing held: another profile's empty record is no hold
        self.assertEqual(exp.held_off(str(self.data)), set())

    def test_on_refuses_a_plugin_whose_non_implicit_master_is_inactive(self):
        # Codex on #407: only our installers' masters were checked; FO4Port.esm unticked let Core.esm come back
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm")
        self.txt.write_bytes("# keep\r\nFO4Port.esm\r\nCore.esm\r\nMission.esm\r\n*FO4SFBridge.esm\r\n".encode())
        before = self.txt.read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on")
        self.assertIn("Core.esm needs FO4Port.esm as a master, which is not active", str(cm.exception))
        self.assertEqual(self.txt.read_bytes(), before)
        (self.data / "Core.esm").write_bytes(tes4("Starfield.esm", "SFBGS003.esm"))   # implicit masters need no line
        self.run_cmd("on")
        self.assertEqual(self.lines(), ["# keep", "FO4Port.esm", "*Core.esm", "*Mission.esm", "*FO4SFBridge.esm"])

    def test_on_refuses_a_duplicated_line(self):
        # Codex on #407: on ticked both lines of a held plugin and cleared the hold
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes((self.txt.read_bytes().decode() + "Mission.esm\r\n").encode())
        before = self.txt.read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on")
        self.assertIn("Mission.esm has 2 lines in Plugins.txt", str(cm.exception))
        self.assertEqual(self.txt.read_bytes(), before)
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], ["Mission.esm"])

    def test_a_missing_plugin_file_is_never_held_and_a_stuck_hold_is_released(self):
        # Codex on #407: off held a plugin whose Data file was gone, and on then failed on its masters for good
        (self.data / "Mission.esm").unlink()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("off", "--plugins", "Mission.esm")
        self.assertIn("Mission.esm: the plugin file is missing", str(cm.exception))
        self.assertEqual(self.txt.read_bytes().decode(), self.original)
        self.assertFalse((self.data / exp.TOGGLE).exists())
        (self.data / "Mission.esm").write_bytes(tes4("Core.esm"))
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm")
        (self.data / "Mission.esm").unlink()               # gone while held
        out = self.run_cmd("on")
        self.assertIn("back on: Core.esm; released, left unticked (cannot load): Mission.esm: the plugin file is "
                      "missing", out)
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "*FO4SFBridge.esm"])
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])

    def test_a_held_plugin_with_an_unreadable_header_is_released(self):
        # Codex on #407: a truncated held .esm made on fail on its header, and the hold blocked the uninstallers
        (self.data / "Mission.esm").write_bytes(b"TES4")
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("off", "--plugins", "Mission.esm")
        self.assertIn("Mission.esm: the plugin file is unreadable", str(cm.exception))
        (self.data / "Mission.esm").write_bytes(tes4("Core.esm"))
        self.run_cmd("off", "--plugins", "Mission.esm")
        (self.data / "Mission.esm").write_bytes(b"TES4")     # damaged while held
        out = self.run_cmd("on")
        self.assertIn("released, left unticked (cannot load): Mission.esm: the plugin file is unreadable", out)
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "*FO4SFBridge.esm"])
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])

    def test_on_releases_the_held_dependents_of_an_unloadable_master(self):
        # Codex on #407: a damaged held Core.esm refused its held child Mission.esm, so both stayed held for good
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm,FO4SFBridge.esm")
        (self.data / "Core.esm").write_bytes(b"TES4")
        out = self.run_cmd("on")
        self.assertIn("back on: FO4SFBridge.esm; released, left unticked (cannot load): Core.esm: the plugin file is "
                      "unreadable", out)
        self.assertIn("; Mission.esm: needs Core.esm: the plugin file is unreadable", out)
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "Core.esm", "Mission.esm", "*FO4SFBridge.esm"])
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])

    def test_on_unticks_a_released_plugin_the_game_ticked_again(self):
        # Codex on #407: the hold was cleared with the broken plugin still ticked
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes(self.original.encode())         # the game ticked it again
        (self.data / "Mission.esm").unlink()
        self.run_cmd("on")
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "*FO4SFBridge.esm"])
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])

    def test_on_releases_a_held_child_of_a_broken_master_that_is_not_held(self):
        # Codex on #407: Core.esm stays ticked and not held, but its file broke; Mission.esm was ticked anyway
        self.run_cmd("off", "--plugins", "Mission.esm")
        (self.data / "Core.esm").unlink()
        out = self.run_cmd("on")
        self.assertIn("back on: none; released, left unticked (cannot load): Mission.esm: needs Core.esm: the plugin "
                      "file is missing", out)
        # the broken master that is not held is never ticked or unticked by us
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "*FO4SFBridge.esm"])
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])

    def test_on_follows_the_whole_master_chain_from_data(self):
        # a master's master, outside the held set and the request, breaks the chain too
        self.run_cmd("off", "--plugins", "Mission.esm")
        (self.data / "FO4Port.esm").write_bytes(b"TES4")
        out = self.run_cmd("on")
        self.assertIn("Mission.esm: needs Core.esm: needs FO4Port.esm: the plugin file is unreadable", out)
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "*FO4SFBridge.esm"])

    def test_on_for_one_child_releases_it_when_its_held_master_is_broken(self):
        # on --plugins Mission.esm refused ("bring them back together") while the held Core.esm was broken
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm")
        (self.data / "Core.esm").write_bytes(b"TES4")
        out = self.run_cmd("on", "--plugins", "Mission.esm")
        self.assertIn("released, left unticked (cannot load): Mission.esm: needs Core.esm", out)
        self.assertIn("still held off: Core.esm", out)
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "Core.esm", "Mission.esm", "*FO4SFBridge.esm"])
        self.run_cmd("on")
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])

    def test_off_refuses_when_an_active_plugin_would_lose_a_master_down_its_chain(self):
        # Codex on #407: off Core.esm was allowed while Addon.esm -> Bridgehead.esm -> Core.esm (neither ours) stayed
        # active; Stale.esm, whose chain was already broken by the held Mission.esm, is not ours to judge
        self.run_cmd("off", "--plugins", "Mission.esm")
        (self.data / "Addon.esm").write_bytes(tes4("Bridgehead.esm"))
        (self.data / "Bridgehead.esm").write_bytes(tes4("Starfield.esm"))
        (self.data / "Stale.esm").write_bytes(tes4("Mission.esm"))
        self.txt.write_bytes("# keep\r\n*FO4Port.esm\r\n*Core.esm\r\nMission.esm\r\n*FO4SFBridge.esm\r\n"
                             "*Stale.esm\r\n*Addon.esm\r\n*Bridgehead.esm\r\n".encode())
        self.run_cmd("off", "--plugins", "FO4SFBridge.esm")   # Bridgehead does not need Core yet: allowed
        self.run_cmd("on", "--plugins", "FO4SFBridge.esm")
        (self.data / "Bridgehead.esm").write_bytes(tes4("Core.esm"))
        before = self.txt.read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("off", "--plugins", "Core.esm")
        self.assertEqual(str(cm.exception), "not changed: Addon.esm stays active and needs Core.esm as a master: "
                                            "untick it by hand first")
        self.assertNotIn("Stale.esm", str(cm.exception))
        self.assertEqual(self.txt.read_bytes(), before)
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], ["Mission.esm"])

    def test_on_refuses_a_child_whose_grand_master_is_inactive(self):
        # Codex on #407: Mission.esm's direct master Core.esm is active but its grand-master FO4Port.esm is not
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes("# keep\r\nFO4Port.esm\r\n*Core.esm\r\nMission.esm\r\n*FO4SFBridge.esm\r\n".encode())
        before = self.txt.read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on")
        self.assertIn("Mission.esm needs FO4Port.esm as a master, which is not active", str(cm.exception))
        self.assertEqual(self.txt.read_bytes(), before)
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], ["Mission.esm"])

class CycleTests(unittest.TestCase):
    def test_cycle_does_not_launch_when_the_bridge_order_refuses(self):
        # Codex on #407: bridge_install.py order exits nonzero on a held bridge the game ticked again, and cycle.ps1
        # went on to launch with the bridge active (checked as text: no PowerShell here)
        text = (ROOT / "scripts" / "game" / "cycle.ps1").read_text(encoding="utf-8")
        block = text[text.index("bridge_install.py\" order"):text.index("function Wait-Screen")]
        self.assertIn("$bordCode = $LASTEXITCODE", block)
        self.assertIn("if ($bordCode -ne 0) {", block)
        self.assertIn("not launching\"; exit 7 }", block)
        self.assertLess(text.index("$bordCode -ne 0"), text.index("Start-Process"))

    def test_cycle_checks_activation_after_the_load_with_only_the_bridge_installed(self):
        # Codex on #407: the post-load active check ran only with the experiment record, so a bridge-only crash split
        # went on after the game ticked the held bridge again (checked as text: no PowerShell here)
        text = (ROOT / "scripts" / "game" / "cycle.ps1").read_text(encoding="utf-8")
        at = text.index("exp_install.py\" active")
        cond = text[text.rindex("\nif (", 0, at):at]
        self.assertIn("FO4SFExp.install.json", cond)
        self.assertIn("-or (Test-Path (Join-Path $sf 'Data\\FO4SFBridge.install.json'))", cond)
        self.assertLess(text.index("Wait-Screen 'save loaded'"), at)


if __name__ == "__main__":
    unittest.main()
