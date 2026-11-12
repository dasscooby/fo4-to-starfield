import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "newgame"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault111_anim_probe as probe  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402
from fo4sf import nif  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

MODEL = "Meshes\\Interiors\\Vault111\\Cryo\\CryoDoor01.nif"
GRAPH = "Animations\\Cryo\\CryoDoor.hkx"


def model_nif():
    f = nif.NifFile(bs_version=130)
    root, clip, key, graph = [f.string_index(s) for s in (b"Root", b"Open", b"Sound: CryoOpen", GRAPH.encode())]
    f.add_block("NiNode", struct.pack("<i", root))
    f.add_block("NiControllerSequence", struct.pack("<iII", clip, 0, 0))
    f.add_block("NiTextKeyExtraData", struct.pack("<iIfi", -1, 1, .5, key))
    f.add_block("BSBehaviorGraphExtraData", struct.pack("<iiB", root, graph, 1))
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


def plugin_bytes():
    w = esm.PluginWriter(["Starfield.esm"])
    base = w.own(0x803)
    w.add(esm.Record("DOOR", base, [(b"EDID", esm.zbytes("CryoDoor01")), (b"MODL", esm.zbytes(MODEL[len("Meshes\\"):]))]))
    ref = esm.Record("REFR", w.own(0x126D), [(b"EDID", esm.zbytes("CryoRef")), (b"NAME", struct.pack("<I", base)),
                                              (b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 0))])
    w.add(ref)
    far = esm.Record("REFR", w.own(0x138B), [(b"NAME", struct.pack("<I", 0x00ABCDEF)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))])
    w.add(far)
    return w.to_bytes()


PORT_MODEL = "Meshes\\fo4port\\interiors\\vault\\doors\\CogDoor01.nif"
FO4_MODEL = "Meshes\\Interiors\\Vault\\Doors\\CogDoor01.nif"


def second_plugin_bytes():
    """A DOOR (linked to a sound-like record that names a graph file) and a STAT console, both placed."""
    w = esm.PluginWriter(["Starfield.esm"])
    link = w.own(0x900)
    w.add(esm.Record("SOUN", link, [(b"EDID", esm.zbytes("CogOpenSound")), (b"FNAM", esm.zbytes(GRAPH))]))
    door = w.own(0x901)
    w.add(esm.Record("DOOR", door, [(b"EDID", esm.zbytes("FO4Port_VltGearDoor01")), (b"MODL", esm.zbytes(PORT_MODEL[len("Meshes\\"):])),
                                    (b"SNAM", struct.pack("<I", link)), (b"FNAM", b"\x01")]))
    stat = w.own(0x902)
    w.add(esm.Record("STAT", stat, [(b"EDID", esm.zbytes("FO4Port_V111GearDoorConsole02")), (b"MODL", esm.zbytes("Other\\Console.nif"))]))
    w.add(esm.Record("REFR", w.own(0x126D), [(b"NAME", struct.pack("<I", door)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))]))
    w.add(esm.Record("REFR", w.own(0x138B), [(b"NAME", struct.pack("<I", stat)), (b"DATA", struct.pack("<6f", 1, 1, 1, 0, 0, 0))]))
    return w.to_bytes()


class Vault111AnimProbeSecondHeadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "Data")
        self.fo4 = os.path.join(self.tmp.name, "FO4")
        os.makedirs(self.data)
        os.makedirs(self.fo4)
        with open(os.path.join(self.data, "FO4Port.esm"), "wb") as f:
            f.write(second_plugin_bytes())
        with open(os.path.join(self.data, "FO4Port - Main.ba2"), "wb") as f:
            f.write(general_archive({PORT_MODEL: b"not a nif at all, graph.hkx", GRAPH: b"\0\0hkb\0LinkEvent\0\0"}))
        self.out = os.path.join(self.tmp.name, "report.txt")

    def write_fo4(self, files):
        with open(os.path.join(self.fo4, "Fallout4 - Meshes.ba2"), "wb") as f:
            f.write(general_archive(files))

    def run_probe(self, *extra):
        self.assertEqual(probe.main(["--out", self.out, "--data", self.data] + list(extra)), 0)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_every_base_subrecord_is_printed_and_a_link_is_followed_with_its_file(self):
        text = self.run_probe("--ref", "00126D")
        self.assertIn("SNAM 4 bytes:", text)
        self.assertIn("FNAM 1 bytes: 01", text)
        self.assertIn("base link SNAM -> SOUN", text)
        self.assertIn("edid=CogOpenSound", text)
        self.assertIn("link SNAM path (FNAM): read from FO4Port - Main.ba2", text)
        self.assertIn("LinkEvent", text)

    def test_the_original_is_found_by_the_port_path_with_its_prefix_taken_out(self):
        self.write_fo4({FO4_MODEL: b"original bytes"})
        text = self.run_probe("--ref", "00126D", "--fo4-data", self.fo4)
        self.assertIn("original (Fallout 4) at Meshes\\Interiors\\vault\\doors\\CogDoor01.nif", text)      # the port's own folder case
        self.assertIn("original: read from Fallout4 - Meshes.ba2: 14 bytes", text)
        self.assertIn("Fallout 4 archives: Fallout4 - Meshes.ba2 (1 files)", text)

    def test_the_original_is_found_by_file_name_when_the_folders_differ(self):
        self.write_fo4({"Meshes\\Somewhere\\Else\\CogDoor01.nif": b"original bytes"})
        text = self.run_probe("--ref", "00126D", "--fo4-data", self.fo4)
        self.assertIn("original (Fallout 4) found by file name Meshes\\Somewhere\\Else\\CogDoor01.nif", text)

    def test_a_missing_original_says_what_was_tried_and_no_data_says_so(self):
        self.write_fo4({"Meshes\\Other.nif": b"x"})
        text = self.run_probe("--ref", "00126D", "--fo4-data", self.fo4)
        self.assertIn("original (Fallout 4): not found by the paths", text)
        self.assertIn("no file of that name", text)
        self.assertIn("original (Fallout 4): not read: no --fo4-data given", self.run_probe("--ref", "00126D"))

    def test_references_are_found_by_base_word_and_an_absent_one_is_said(self):
        text = self.run_probe("--ref", "00126D", "--base-edid", "GearDoorConsole", "--base-edid", "PipboySkeleton")
        self.assertIn("references whose base EditorID contains 'GearDoorConsole': 1 (00138B)", text)
        self.assertIn("base type STAT", text)
        self.assertIn("references whose base EditorID contains 'PipboySkeleton': 0", text)
        self.assertIn("none: the port has no placed reference on such a base", text)

    def test_a_reference_already_listed_is_not_reported_twice(self):
        text = self.run_probe("--ref", "00126D", "--base-edid", "VltGearDoor")
        self.assertIn("ref 00126D: already reported above", text)

    def test_the_default_words_name_the_console_the_skeleton_and_the_pickup(self):
        for w in ("GearDoorConsole", "PipboySkeleton", "PipboyGroundTake"):
            self.assertIn(w, probe.DEFAULT_BASE_WORDS)


AGX = "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx"
RIG = "Meshes\\fo4port\\interiors\\vault\\doors\\CogDoorRig\\skeleton.rig"
ANIMS = "fo4port\\interiors\\vault\\doors\\CogDoorRig\\animations"


class Vault111AnimProbeGraphFilesTests(unittest.TestCase):
    """A Starfield DOOR names its graph (ANAM, a path with no Meshes prefix), its rig (BNAM) and an animations folder (CNAM):
    the probe must open each file and list the folder."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        w = esm.PluginWriter(["Starfield.esm"])
        door = w.own(0x901)
        w.add(esm.Record("DOOR", door, [(b"EDID", esm.zbytes("FO4Port_VltGearDoor01")), (b"ANAM", esm.zbytes(AGX)),
                                        (b"BNAM", esm.zbytes(RIG[len("Meshes\\"):])), (b"CNAM", esm.zbytes(ANIMS))]))
        w.add(esm.Record("REFR", w.own(0x126D), [(b"NAME", struct.pack("<I", door)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))]))
        with open(os.path.join(self.tmp.name, "FO4Port.esm"), "wb") as f:
            f.write(w.to_bytes())
        files = {AGX: b"\0agx\0StateOpen\0EventDone\0", RIG: b"\0rig\0b_Cog\0b_Walkway01\0",
                 "Meshes\\" + ANIMS + "\\Open.af": b"\0af\0Open\0", "Meshes\\" + ANIMS + "\\Open.afx": b"\0afx\0KlaxonStop\0"}
        with open(os.path.join(self.tmp.name, "FO4Port - Main.ba2"), "wb") as f:
            f.write(general_archive(files))
        self.out = os.path.join(self.tmp.name, "r.txt")

    def run_probe(self):
        self.assertEqual(probe.main(["--out", self.out, "--data", self.tmp.name, "--ref", "00126D"]), 0)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_the_graph_is_found_without_a_meshes_prefix_and_its_strings_printed(self):
        text = self.run_probe()
        self.assertIn("animation file (ANAM): " + AGX, text)
        self.assertIn("base ANAM: read from FO4Port - Main.ba2", text)
        self.assertIn("StateOpen | EventDone", text)

    def test_the_rig_is_opened(self):
        text = self.run_probe()
        self.assertIn("animation file (BNAM)", text)
        self.assertIn("b_Cog | b_Walkway01", text)

    def test_the_animations_folder_is_listed_and_each_clip_file_read(self):
        text = self.run_probe()
        self.assertIn("base CNAM: folder " + ANIMS + ": 2 entries", text)
        self.assertIn("Open.af", text)
        self.assertIn("base CNAM file: read from FO4Port - Main.ba2", text)
        self.assertIn("KlaxonStop", text)

    def test_a_graph_missing_from_the_archives_is_said(self):
        with open(os.path.join(self.tmp.name, "FO4Port - Main.ba2"), "wb") as f:
            f.write(general_archive({"Meshes\\Other.nif": b"x"}))
        text = self.run_probe()
        self.assertIn("base ANAM: model not in the archives read", text)
        self.assertIn("no archive entry under it", text)


class Vault111AnimProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.port = os.path.join(self.tmp.name, "FO4Port.esm")
        with open(self.port, "wb") as f:
            f.write(plugin_bytes())
        self.archive = os.path.join(self.tmp.name, "FO4Port - Main.ba2")
        with open(self.archive, "wb") as f:
            f.write(general_archive({MODEL: model_nif(), GRAPH: b"\0\0hkb\0idle\0EventOpen\0StateClosed\0\0"}))
        self.out = os.path.join(self.tmp.name, "report.txt")

    def run_probe(self, *refs):
        argv = ["--out", self.out, "--data", self.tmp.name]
        for r in refs:
            argv += ["--ref", r]
        self.assertEqual(probe.main(argv), 0)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_base_clip_event_and_graph_are_read(self):
        text = self.run_probe("00126D")
        self.assertIn("DOOR", text)
        self.assertIn("edid=CryoDoor01", text)
        self.assertIn("model path (MODL): Interiors\\Vault111\\Cryo\\CryoDoor01.nif", text)
        self.assertIn("clips (NiControllerSequence): Open", text)
        self.assertIn("0.500s Sound: CryoOpen", text)
        self.assertIn("behavior graph (BSBehaviorGraphExtraData): " + GRAPH, text)
        self.assertIn("EventOpen", text)
        self.assertIn("pos=(1.000, 2.000, 3.000)", text)

    def test_missing_ref_and_foreign_base_are_said_plainly(self):
        text = self.run_probe("00FFFF", "00138B")
        self.assertIn("not found: no REFR or ACHR with local id 00FFFF", text)
        self.assertIn("is not in this plugin", text)

    def test_model_missing_from_archives_is_not_found_not_invented(self):
        os.remove(self.archive)
        with open(self.archive, "wb") as f:
            f.write(general_archive({"Meshes\\Other.nif": b"x"}))
        text = self.run_probe("00126D")
        self.assertIn("model not in the archives read", text)
        self.assertNotIn("clips (NiControllerSequence)", text)

    def test_probe_writes_only_the_report(self):
        before = sorted(os.listdir(self.tmp.name))
        self.run_probe("00126D")
        self.assertEqual(sorted(os.listdir(self.tmp.name)), sorted(before + ["report.txt"]))


if __name__ == "__main__":
    unittest.main()
