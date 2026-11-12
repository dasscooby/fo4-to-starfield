"""vault111_anim_probe.py --graphs (FAL-489 Step 0): synthetic graphs, plugin, models and archives only; no game data."""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "newgame"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vault111_anim_graphs as graphs  # noqa: E402
import vault111_anim_probe as probe  # noqa: E402
from ba2_fixture import general_archive  # noqa: E402
from fo4sf import nif  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

GRAPHS = "Meshes\\AnimTextData\\Tables\\Graphs\\"
MODEL = "Props\\Console\\Console01.nif"
FOLDER = "Props\\Console\\Animations"


def prop(value, listindex=None):
    return f"<prop><type>1</type><value>{value}</value>" + (f"<listindex>{listindex}</listindex>" if listindex is not None else "") + "</prop>"


def sheet(headers, rows):
    return ("<property_sheet><num_columns>%d</num_columns>" % len(headers)
            + "".join(f"<column><header>{h}</header><types>1</types></column>" for h in headers)
            + "".join("<row>" + "".join(prop(*c) if isinstance(c, tuple) else prop(c) for c in r) + "</row>" for r in rows)
            + "</property_sheet>")


def agx(name, state_rows, headers=("State Name", "Sequence Name", "Enter Events", "Exit Events", "Send Event On End")):
    return ("<root><Name>%s</Name><Category>Activators</Category><Link_Style>0</Link_Style>" % name
            + "<node><node_type>NT_STATE_MACHINE_EMBEDDED</node_type><name>Machine</name><input><name>in</name><id>1</id><idx>0</idx></input>"
              "<output><name>out</name><id>2</id><idx>0</idx></output><graph>"
            + "<node><node_type>NT_GAMEBRYO_SEQUENCE</node_type><name>Play</name>" + sheet(headers, state_rows) + "</node>"
            + sheet(["Other", "Stuff"], [["a", "b"]]) + "</graph></node></root>").encode()


STAGES = agx("Stages", [["PlayAnim01", "PlayAnim01", "", "Done:payload1", "Reset"], ["PlayAnim02", "PlayAnim02", ("Play02", 0), ("Play03", 1), ""]])
EMPTYGRAPH = b"<root><Name>X</Name></root>"


def model_nif(sequences=("PlayAnim01", "Stage9"), manager=True, bs=172):
    f = nif.NifFile(bs_version=bs)
    root = f.string_index(b"Root")
    f.add_block("NiNode", struct.pack("<i", root))
    if manager:
        f.add_block("NiControllerManager", struct.pack("<i", -1))
    for s in sequences:
        f.add_block("NiControllerSequence", struct.pack("<iII", f.string_index(s.encode()), 0, 0))
    keys = [f.string_index(b"start"), f.string_index(b"Stage4")]
    f.add_block("NiTextKeyExtraData", struct.pack("<iI", -1, 2) + struct.pack("<fi", 0.0, keys[0]) + struct.pack("<fi", 1.5, keys[1]))
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


def comp(anam, bnam="", cnam="", name="BGSAnimationGraph_Component"):
    subs = [(b"BFCB", esm.zbytes(name)), (b"ANAM", esm.zbytes(anam))]
    if bnam:
        subs.append((b"BNAM", esm.zbytes(bnam)))
    if cnam:
        subs.append((b"CNAM", esm.zbytes(cnam)))
    return subs + [(b"BFCE", b"")]


def starfield_esm():
    w = esm.PluginWriter([])
    w.add(esm.Record("ACTI", 0x1001, [(b"EDID", esm.zbytes("Console01"))] + comp("AnimTextData\\Tables\\Graphs\\Stages.agx", "Props\\Console\\skeleton.rig", FOLDER)
                     + [(b"MODL", esm.zbytes(MODEL))]))
    w.add(esm.Record("ACTI", 0x1002, [(b"EDID", esm.zbytes("Console02"))] + comp("AnimTextData\\Tables\\Graphs\\stages.agx") + [(b"MODL", esm.zbytes("Props\\Other.nif"))]))
    w.add(esm.Record("ACTI", 0x1003, [(b"EDID", esm.zbytes("Door01"))] + comp("AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx")))
    w.add(esm.Record("ACTI", 0x1004, [(b"EDID", esm.zbytes("NoGraph")), (b"ANAM", esm.zbytes("Stages.agx"))]))    # ANAM outside a component: not a graph component
    w.add(esm.Record("FURN", 0x2001, [(b"EDID", esm.zbytes("Chair01"))] + comp("AnimTextData\\Tables\\Graphs\\FurnitureDefault.agx") + [(b"MODL", esm.zbytes("Props\\Chair.nif"))]))
    return w.to_bytes()


class GraphParseTests(unittest.TestCase):
    def test_rows_carry_their_state_and_the_four_fields_with_payloads(self):
        lines, values = graphs.graph_lines("stages.agx", "A.ba2: x", STAGES)
        text = "\n".join(lines)
        self.assertIn("NT_STATE_MACHINE_EMBEDDED 'Machine'", text)
        self.assertIn("node 'Play' (NT_GAMEBRYO_SEQUENCE) sheet 0 row 0 state 'PlayAnim01'", text)
        self.assertIn("Sequence Name='PlayAnim01'", text)
        self.assertIn("Exit Events='Done:payload1'", text)
        self.assertIn("Send Event On End='Reset'", text)
        self.assertIn("Enter Events[0]='Play02'", text)          # list items keep their index
        self.assertEqual(values["Sequence Name"], {"PlayAnim01", "PlayAnim02"})
        self.assertEqual(values["Send Event On End"], {"Reset"})
        self.assertEqual(values["Exit Events"], {"Done:payload1", "Play03"})
        self.assertIn("1 other sheet(s) not printed", text)        # the 'Other/Stuff' sheet is counted, not printed

    def test_a_name_value_row_layout_is_read_too(self):
        data = agx("Odd", [["Sequence Name", "Stage1"], ["Send Event On End", "TransitionComplete"]], headers=("Property", "Value"))
        _, values = graphs.graph_lines("odd.agx", "x", data)
        self.assertEqual(values["Sequence Name"], {"Stage1"})
        self.assertEqual(values["Send Event On End"], {"TransitionComplete"})

    def test_a_graph_without_rows_and_a_non_xml_file_say_so(self):
        self.assertIn("no state-table row", "\n".join(graphs.graph_lines("e.agx", "x", EMPTYGRAPH)[0]))
        self.assertIn("not XML", "\n".join(graphs.graph_lines("b.agx", "x", b"\0\1binary")[0]))


class NifFactsTests(unittest.TestCase):
    def test_manager_sequences_and_text_keys(self):
        f = graphs.nif_facts(model_nif())
        self.assertEqual((f["bs_version"], f["version"], f["managers"]), (172, 0x14020007, 1))
        self.assertEqual(f["sequences"], ["PlayAnim01", "Stage9"])
        self.assertEqual(f["text_keys"][0][1], ["0.000s start", "1.500s Stage4"])

    def test_a_model_without_sequences_and_a_refused_container(self):
        f = graphs.nif_facts(model_nif(sequences=(), manager=False))
        self.assertEqual((f["managers"], f["sequences"]), (0, []))
        bad = graphs.nif_facts(b"Gamebryo File Format, Version 20.2.0.7\n" + b"\0" * 8 + b"NiControllerSequence")
        self.assertIsNone(bad["sequences"])
        self.assertIn("container not parsed", bad["note"])
        self.assertIn("not a Gamebryo NIF", graphs.nif_facts(b"nope")["note"])


class GraphsModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "Data")
        os.makedirs(self.data)
        self.out = os.path.join(self.tmp.name, "r.txt")
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(starfield_esm())
        self.write_archive("Starfield - Animations.ba2", {GRAPHS + "Stages.agx": STAGES, GRAPHS + "FurnitureDefault.agx": EMPTYGRAPH})
        self.write_archive("Starfield - Meshes01.ba2", {"Meshes\\" + MODEL: model_nif(), "Meshes\\Props\\Other.nif": model_nif(sequences=(), manager=False),
                                                       "Meshes\\" + FOLDER + "\\Open.af": b"af", "Meshes\\" + FOLDER + "\\Open.afx": b"afx"})

    def write_archive(self, name, files):
        with open(os.path.join(self.data, name), "wb") as f:
            f.write(general_archive(files))

    def run_graphs(self, *extra, probe_entry=True):
        argv = ["--out", self.out, "--data", self.data, "--game-archive", "Starfield - Animations.ba2", "--game-archive", "Starfield - Meshes*.ba2",
                "--graph", "stages", "--graph", "furnituredefault", "--graph", "twostages"] + list(extra)
        self.assertEqual(probe.main(["--graphs"] + argv) if probe_entry else graphs.main(argv), 0)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_the_probe_flag_runs_the_graphs_mode_and_needs_no_port_plugin(self):
        text = self.run_graphs()
        self.assertIn("vault111_anim_graphs (read-only; FAL-489 Step 0)", text)
        self.assertIn("Starfield - Meshes01.ba2 (4 entries)", text)       # the * was expanded

    def test_graph_rows_records_and_models_are_tied_together(self):
        text = self.run_graphs()
        self.assertIn("Sequence Name values: PlayAnim01, PlayAnim02", text)
        self.assertIn("graph twostages.agx: unread", text)
        self.assertIn("stages: 2 record(s) (ACTI 2, FURN 0)", text)         # case-blind graph match; the ANAM outside a component is not counted
        self.assertIn("ACTI 00001001 Console01  model=Props\\Console\\Console01.nif  ANAM=AnimTextData\\Tables\\Graphs\\Stages.agx"
                      "  BNAM=Props\\Console\\skeleton.rig  CNAM=Props\\Console\\Animations", text)
        self.assertIn("furnituredefault: 1 record(s) (ACTI 0, FURN 1)", text)
        self.assertIn("twostages: 0 record(s)", text)
        self.assertIn("simpleopenclose01 x1", text)                           # another graph named by an ACTI is listed, not dropped
        self.assertIn("BGSAnimationGraph_Component x4", text)
        self.assertIn("read from Starfield - Meshes01.ba2 as Meshes\\Props\\Console\\Console01.nif", text)
        self.assertIn("version 0x14020007", text)
        self.assertIn("bs_version 172", text)
        self.assertIn("NiControllerManager: 1", text)
        self.assertIn("NiControllerSequence: 2: PlayAnim01, Stage9", text)
        self.assertIn("0.000s start, 1.500s Stage4", text)
        self.assertIn("2 .af/.afx/.rig file(s)", text)

    def test_the_outcome_table_is_filled_from_the_reads(self):
        text = self.run_graphs()
        self.assertIn("read: YES: Props\\Console\\Console01.nif carries ['playanim01'] (graph stages)", text)
        self.assertIn("read: NO: none of 2 model(s) read has .af/.afx in its clip folder with no sequences", text)     # the console model has clips AND sequences
        rows = dict((f, g) for f, g, _ in graphs.outcome_table(
            {"stages": {"Sequence Name": {"PlayAnim01"}}}, {"stages": 1},
            [{"path": "a.nif", "read": True, "sequences": ["PlayAnim01"], "managers": 1, "af": 2, "graph": "stages"}], True, 1))
        self.assertTrue(rows["vanilla activator models carry NiControllerSequence named as the graph's Sequence Name values"].startswith("YES"))
        self.assertTrue(rows["vanilla activator ACTIs use rig + .af and their models carry no sequences"].startswith("NO"))
        self.assertEqual(rows["both exist"], "NO")
        self.assertTrue(rows["neither: no vanilla ACTI names these graphs"].startswith("NO"))

    def test_m1_row_is_yes_for_a_model_with_clips_and_no_sequences(self):
        rows = dict((f, g) for f, g, _ in graphs.outcome_table(
            {"stages": {"Sequence Name": {"PlayAnim01"}}}, {"stages": 1},
            [{"path": "b.nif", "read": True, "sequences": [], "managers": 0, "af": 3, "graph": "stages"}], True, 1))
        self.assertTrue(rows["vanilla activator ACTIs use rig + .af and their models carry no sequences"].startswith("YES: 1 of 1"))
        self.assertTrue(rows["vanilla activator models carry NiControllerSequence named as the graph's Sequence Name values"].startswith("NO: 1 model(s) read"))

    def test_a_refused_container_is_unread_not_no_sequences(self):
        refused = {"path": "bad.nif", "read": True, "sequences": None, "managers": None, "af": 2, "graph": "stages", "raw": ["NiControllerSequence"]}
        parsed = {"path": "ok.nif", "read": True, "sequences": [], "managers": 0, "af": 0, "graph": "stages", "raw": []}
        rows = graphs.outcome_table({"stages": {"Sequence Name": {"PlayAnim01"}}}, {"stages": 2}, [parsed, refused], True, 1)
        self.assertTrue(rows[0][1].startswith("unread: 1 model(s) parsed with no sequence"), rows[0][1])
        self.assertIn("bad.nif (raw scan saw NiControllerSequence)", rows[0][1])
        self.assertTrue(rows[1][1].startswith("unread"), rows[1][1])        # the refused model's .af folder does not make M1 YES
        self.assertEqual(rows[2][1], "unread")
        only = graphs.outcome_table({}, {"stages": 1}, [refused], True, 1)
        self.assertTrue(only[0][1].startswith("unread") and only[1][1].startswith("unread"))

    def test_sequence_names_are_compared_exactly_not_without_punctuation(self):
        m = {"path": "a.nif", "read": True, "sequences": ["Open_01"], "managers": 1, "af": 0, "graph": "stages", "raw": []}
        rows = graphs.outcome_table({"stages": {"Sequence Name": {"Open01"}}}, {"stages": 1}, [m], True, 1)
        self.assertTrue(rows[0][1].startswith("NO"), rows[0][1])
        m["sequences"] = ["OPEN01"]
        self.assertTrue(graphs.outcome_table({"stages": {"Sequence Name": {"Open01"}}}, {"stages": 1}, [m], True, 1)[0][1].startswith("YES"))

    def test_a_state_called_sequence_name_in_a_headed_table_does_not_pull_cells_in(self):
        data = agx("T", [["Sequence Name", "NotASequence", "", "", ""], ["Real", "PlayAnim01", "", "", ""]])
        _, values = graphs.graph_lines("t.agx", "x", data)
        self.assertEqual(values["Sequence Name"], {"PlayAnim01", "NotASequence"})       # by its column header only; the first cell's text is a state name
        self.assertNotIn("Sequence Name", values["Sequence Name"])

    def test_nothing_read_says_unread_everywhere(self):
        for name in os.listdir(self.data):
            os.remove(os.path.join(self.data, name))
        text = self.run_graphs()
        self.assertIn("nothing matched", text)
        self.assertIn("unread: ", text)
        self.assertIn("graph stages.agx: unread", text)
        self.assertIn("no model to read", text)
        self.assertEqual(text.count("read: unread"), 4)       # all four outcome rows
        self.assertIn("read: unread (Starfield.esm was not read)", text)

    def test_neither_row_is_yes_when_no_record_names_a_graph(self):
        rows = graphs.outcome_table({}, {}, [], True, 2)
        self.assertTrue(rows[3][1].startswith("YES: no ACTI or FURN names these graphs"))

    def test_named_models_and_a_missing_one_are_read(self):
        text = self.run_graphs("--model", "Props\\Missing.nif", "--model", "Props\\Other.nif")
        self.assertIn("--- model Props\\Missing.nif\n  not in the archives read", text)
        self.assertIn("--- model Props\\Other.nif", text)
        self.assertIn("NiControllerSequence: 0: none", text)

    def test_the_default_models_are_the_first_per_graph_and_not_repeated(self):
        text = self.run_graphs("--default-models", "1")
        self.assertEqual(text.count("--- model Props\\Console\\Console01.nif"), 1)
        self.assertNotIn("--- model Props\\Other.nif", text)             # second record of the same graph, beyond the first one

    def test_only_the_report_is_written(self):
        before = sorted(os.listdir(self.tmp.name)), sorted(os.listdir(self.data))
        self.run_graphs()
        self.assertEqual(sorted(os.listdir(self.tmp.name)), sorted(before[0] + ["r.txt"]))
        self.assertEqual(sorted(os.listdir(self.data)), before[1])

    def test_the_old_probe_modes_still_parse(self):
        self.assertEqual(sys.modules["vault111_anim_probe"].DEFAULT_REFS, ("00126D", "00138B", "001616"))


if __name__ == "__main__":
    unittest.main()
