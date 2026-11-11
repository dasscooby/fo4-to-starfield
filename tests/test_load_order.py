"""load_order (scripts/game/load_order.py): the one target order for our plugins, on synthetic files only."""
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import load_order  # noqa: E402

# the order the game wrote on the owner's PC, 2026-10-22, 25 s after a start (Install thread)
GAME = ["FO4TerrainCore.esm", "FO4TerrainCore_Mars.esm", "FO4ActorRaider.esm", "FO4SFMission.esm", "FO4Port.esm",
        "FO4SFMapMarkers.esm", "FO4SFBridge.esm"]
MASTERS = {"FO4TerrainCore_Mars.esm": ["FO4TerrainCore.esm"], "FO4SFMapMarkers.esm": ["FO4TerrainCore.esm"],
           "FO4SFMission.esm": ["Starfield.esm"]}


def plugin(path, masters=()):
    sub = b"".join(b"MAST" + struct.pack("<H", len(m) + 1) + m.encode() + b"\0" for m in masters)
    with open(path, "wb") as f:
        f.write(b"TES4" + struct.pack("<I", len(sub)) + b"\0" * 16 + sub)


class LoadOrderTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.game = os.path.join(t.name, "Starfield")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        for p in GAME:
            plugin(os.path.join(self.data, p), MASTERS.get(p, ()))
        self.txt = os.path.join(t.name, "Plugins.txt")
        self.said = []

    def write(self, lines, bom=b"\xef\xbb\xbf", nl="\r\n"):
        with open(self.txt, "wb") as f:
            f.write(bom + (nl.join(lines) + nl).encode())

    def run_(self, cmd):
        return load_order.run(cmd, self.game, plugins_txt=self.txt, say=self.said.append)

    def read(self):
        with open(self.txt, "rb") as f:
            return f.read()

    def test_the_order_the_game_wrote_is_the_target(self):
        self.write(["# This file is used by the game", "*Other.esm"] + ["*" + p for p in GAME])
        before = self.read()
        self.assertEqual(self.run_("check"), 0)
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read(), before)                         # nothing written
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.txt)) if ".bak-" in n], [])

    def test_two_kits_after_markers_and_an_unticked_bridge_keep_their_positions(self):
        # FAL-354: play's load_order=fix moved both kits ahead of markers and the held bridge.
        kits = ["FO4SFPipboyProbe.esm", "FO4SFRadsProbe.esm"]
        for p in kits:
            plugin(os.path.join(self.data, p), ["FO4Port.esm"])
        lines = ["# owner order"] + ["*" + p for p in GAME[:-1]] + [GAME[-1]] + ["*" + p for p in kits]
        for bom, nl in ((b"", "\n"), (b"\xef\xbb\xbf", "\r\n")):
            with self.subTest(bom=bom, nl=nl):
                self.write(lines, bom=bom, nl=nl)
                old = self.read()
                self.assertEqual(self.run_("check"), 0)
                self.assertEqual(self.run_("fix"), 0)
                self.assertEqual(self.read(), old)
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.txt)) if ".bak-" in n], [])

    def test_markers_and_bridge_still_follow_their_masters(self):
        plugin(os.path.join(self.data, "FO4SFBridge.esm"), ["FO4SFMapMarkers.esm"])
        self.write(["*FO4SFBridge.esm", "*FO4SFMapMarkers.esm", "*FO4TerrainCore.esm"])
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read().decode("utf-8-sig").split(),
                         ["*FO4TerrainCore.esm", "*FO4SFMapMarkers.esm", "*FO4SFBridge.esm"])
        self.assertEqual(self.run_("check"), 0)

    def test_the_morning_order_keeps_port_first_and_the_unticked_bridge_in_place(self):
        # 2026-10-22 05:50 local: FO4Port first, as the map markers install recorded it. File order holds (the
        # install tools put the lines there). Even an unticked bridge above markers keeps its place (FAL-354).
        morning = ["*FO4Port.esm", "*FO4TerrainCore.esm", "*Other.esm", "*FO4TerrainCore_Mars.esm", "*FO4ActorRaider.esm",
                   "*FO4SFMission.esm", "FO4SFBridge.esm", "*FO4SFMapMarkers.esm"]
        self.write(morning)
        old = self.read()
        self.assertEqual(self.run_("check"), 0)
        self.assertEqual(self.read(), old)                            # check never writes
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read(), old)
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.txt)) if ".bak-" in n], [])
        self.assertEqual(self.run_("check"), 0)

    def test_the_full_install_order_of_the_runner_tools_is_the_target(self):
        # the owner's PC, 2026-10-28 (Install thread): the install, map-marker and bridge tools had just written this
        # file, and the old grouped target would have moved 7 lines. FAL-354 also removes the remaining marker/bridge
        # groups: the later CombinedProbe install must keep its place after the markers.
        plugin(os.path.join(self.data, "FO4SFQuestProbe.esm"), ["Starfield.esm"])
        for p in ("FO4SFDoorsAnim.esm", "FO4SFCombinedProbe.esm"):
            plugin(os.path.join(self.data, p), ["FO4TerrainCore.esm"])
        pc = ["# This file is used by the game", "*Other.esm", "*FO4SFQuestProbe.esm", "*FO4TerrainCore.esm",
              "*FO4TerrainCore_Mars.esm", "*FO4ActorRaider.esm", "*FO4SFMission.esm", "*FO4SFDoorsAnim.esm",
              "*FO4Port.esm", "*FO4SFMapMarkers.esm", "*FO4SFCombinedProbe.esm", "*FO4SFBridge.esm"]
        self.write(pc)
        before = self.read()
        self.assertEqual(self.run_("check"), 0)
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read(), before)
        self.assertEqual(self.run_("check"), 0)

    def test_a_second_fix_in_the_same_second_keeps_the_first_copy(self):
        from unittest import mock
        import datetime
        fixed = datetime.datetime(2026, 10, 22, 19, 40, 0)
        with mock.patch.object(load_order.datetime, "datetime", mock.Mock(now=mock.Mock(return_value=fixed))):
            # A real master-order repair still keeps each backup; group-only changes no longer rewrite anything.
            self.write(["*FO4SFMapMarkers.esm"] + ["*" + p for p in GAME if p != "FO4SFMapMarkers.esm"])
            first = self.read()
            self.assertEqual(self.run_("fix"), 0)
            self.write(["*FO4TerrainCore_Mars.esm"] + ["*" + p for p in GAME if p != "FO4TerrainCore_Mars.esm"])
            self.assertEqual(self.run_("fix"), 0)
        folder = os.path.dirname(self.txt)
        baks = sorted(n for n in os.listdir(folder) if ".bak-" in n)
        self.assertEqual(len(baks), 2)
        with open(os.path.join(folder, baks[0]), "rb") as f:
            self.assertEqual(f.read(), first)

    def test_a_plugin_loads_after_its_master(self):
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["FO4Port.esm"])
        self.write(["*" + p for p in GAME])
        self.assertEqual(self.run_("fix"), 0)
        lines = self.read().decode("utf-8-sig").split()
        self.assertLess(lines.index("*FO4Port.esm"), lines.index("*FO4SFMission.esm"))

    def test_a_patch_for_our_plugins_still_loads_after_them(self):
        # Codex on #487: a plugin that is not ours but masters one of ours, or such a patch, must stay after it
        plugin(os.path.join(self.data, "PortPatch.esm"), ["FO4Port.esm"])
        plugin(os.path.join(self.data, "PatchOfPatch.esp"), ["PortPatch.esm"])
        plugin(os.path.join(self.data, "Other.esm"))
        self.write(["*FO4Port.esm", "*PortPatch.esm", "*Other.esm", "*PatchOfPatch.esp"]
                   + ["*" + p for p in GAME if p != "FO4Port.esm"])
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read().decode("utf-8-sig").split(),
                         ["*FO4Port.esm", "*PortPatch.esm", "*Other.esm", "*PatchOfPatch.esp", "*FO4TerrainCore.esm",
                          "*FO4TerrainCore_Mars.esm", "*FO4ActorRaider.esm", "*FO4SFMission.esm",
                          "*FO4SFMapMarkers.esm", "*FO4SFBridge.esm"])       # file order; each patch after its master
        self.assertEqual(self.run_("check"), 0)

    def test_a_chain_from_ours_through_a_patch_back_to_ours_keeps_its_masters_first(self):
        # Codex's QA on #487: Port <- PortPatch <- Mission was rewritten Mission, Port, PortPatch and then accepted
        plugin(os.path.join(self.data, "PortPatch.esm"), ["FO4Port.esm"])
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["PortPatch.esm"])
        self.write(["*FO4TerrainCore.esm", "*FO4Port.esm", "*PortPatch.esm", "*FO4SFMission.esm"])
        self.assertEqual(self.run_("check"), 0)                              # already valid and in the target
        self.write(["*FO4SFMission.esm", "*PortPatch.esm", "*FO4Port.esm", "*FO4TerrainCore.esm"])
        self.assertEqual(self.run_("fix"), 0)
        self.assertEqual(self.read().decode("utf-8-sig").split(),
                         ["*FO4Port.esm", "*PortPatch.esm", "*FO4SFMission.esm", "*FO4TerrainCore.esm"])

    def test_a_cycle_across_ours_and_a_patch_and_a_patch_missing_its_master_are_refused(self):
        plugin(os.path.join(self.data, "PortPatch.esm"), ["FO4SFMission.esm"])
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["PortPatch.esm"])
        self.write(["*FO4SFMission.esm", "*PortPatch.esm"])
        old = self.read()
        self.assertEqual(self.run_("fix"), 6)
        self.assertIn("cycle", self.said[-1])
        self.assertEqual(self.read(), old)
        plugin(os.path.join(self.data, "Lone.esm"), ["Absent.esm"])
        self.write(["*" + p for p in GAME] + ["*Lone.esm"])
        old = self.read()
        self.assertEqual(self.run_("check"), 6)
        self.assertIn("Lone.esm needs master Absent.esm", self.said[-1])
        self.assertEqual(self.run_("fix"), 6)
        self.assertEqual(self.read(), old)

    def test_what_cannot_be_judged_is_refused_and_left_alone(self):
        cases = [
            (["*" + p for p in GAME if p != "FO4TerrainCore.esm"], "needs master FO4TerrainCore.esm"),
            (["*" + p for p in GAME] + ["*FO4SFNew.esm"], "active but not in"),
            (["*" + p for p in GAME] + ["*FO4Port.esm"], "more than once"),
        ]
        for lines, text in cases:
            with self.subTest(text=text):
                self.write(lines)
                old, self.said = self.read(), []
                self.assertEqual(self.run_("fix"), 6)
                self.assertIn(text, self.said[-1])
                self.assertEqual(self.read(), old)
        plugin(os.path.join(self.data, "FO4Port.esm"), ["FO4SFMission.esm"])
        plugin(os.path.join(self.data, "FO4SFMission.esm"), ["FO4Port.esm"])
        self.write(["*" + p for p in GAME])
        self.assertEqual(self.run_("check"), 6)
        self.assertIn("cycle", self.said[-1])

    def test_no_plugins_file_is_nothing_to_order(self):
        self.assertEqual(self.run_("fix"), 0)
        self.assertFalse(os.path.exists(self.txt))

    def test_every_plugin_of_ours_active_must_be_in_data_slices_probes_and_reserved_names_too(self):
        # the old list here (fo4terrain, fo4actor, fo4sf, fo4port) let an active slice, FOCC probe or FOSF_ plugin
        # that is missing from Data pass unjudged; the one list (fo4sf.core.loadset) holds them to the same rule
        for p in ("FO4SliceRedRocketCore.esm", "FOCCProbe.esp", "FOSF_Start.esm", "FNVSF_Goodsprings.esm"):
            with self.subTest(plugin=p):
                self.write(["*" + g for g in GAME] + ["*" + p])
                old, self.said = self.read(), []
                self.assertEqual(self.run_("fix"), 6)
                self.assertIn(f"{p} is active but not in", self.said[-1])
                self.assertEqual(self.read(), old)
        self.write(["*SomeoneElses.esm"] + ["*" + g for g in GAME])     # not ours: absent from Data, not judged
        self.said = []
        self.assertEqual(self.run_("check"), 0)

    def test_it_runs_isolated_as_the_launcher_starts_it(self):
        # crashwatch.apply_load_order runs `python -I load_order.py`: -I leaves the script's folder and src off sys.path
        import subprocess
        env = dict(os.environ, LOCALAPPDATA="")
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "game", "load_order.py"), "check",
                            "--starfield", self.game], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("no LOCALAPPDATA folder", r.stdout)


if __name__ == "__main__":
    unittest.main()
