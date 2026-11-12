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
