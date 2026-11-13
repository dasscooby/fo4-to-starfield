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


# A synthetic state machine. The REAL transition layout is unread: this fixture invents three places a transition could live (a sheet with
# transition-word headers, extra children of an output, an element the reader does not know) to show that the dump prints all of them and
# the report mode's sheet filter does not.
MACHINE = (b"<root><Name>Machine</Name><Category>Activators</Category>"
           b"<node><node_type>NT_STATE_MACHINE</node_type><name>SM</name>"
           b"<input><name>in</name><id>1</id><idx>0</idx></input>"
           b"<output><name>out</name><id>2</id><idx>0</idx><target>StateB</target><event>Trans01</event></output>"
           b"<transition_hint from='StateA' to='StateB'>on Trans01</transition_hint>"
           + ("<property_sheet><num_columns>3</num_columns>"
              "<column><header>From</header></column><column><header>To</header></column><column><header>Fires On</header></column>"
              "<row><prop><value>StateA</value></prop><prop><value>StateB</value></prop><prop><value>Trans01</value></prop></row>"
              "<row><prop><value>StateB</value></prop><prop><value></value></prop><prop><value>Done</value><listindex>2</listindex></prop></row>"
              "</property_sheet>").encode()
           + b"<graph><node><node_type>NT_GAMEBRYO_SEQUENCE</node_type><name>StateA</name></node></graph></node></root>")


class DumpTests(unittest.TestCase):
    def test_every_sheet_row_and_element_is_printed_whatever_its_columns(self):
        text = "\n".join(graphs.dump_lines("m.agx", "x", MACHINE))
        self.assertIn("COMPLETE DUMP", text)
        self.assertIn("property_sheet /root/node/property_sheet {num_columns='3'}: 3 column(s) ['From', 'To', 'Fires On']; 2 row(s)", text)   # its interior is printed now
        self.assertIn("a header names a transition word (by name only)", text)
        self.assertIn("row 0: From='StateA' | To='StateB' | Fires On='Trans01'", text)
        self.assertIn("row 1: From='StateB' | Fires On[2]='Done'  [3 cell(s), 1 empty]", text)      # an empty cell is counted, a listindex kept
        self.assertIn("transition_hint from='StateA' to='StateB' = 'on Trans01'", text)             # an element the reader does not know
        self.assertIn("target = 'StateB'", text)
        self.assertIn("event = 'Trans01'", text)
        self.assertIn("/root/node/transition_hint", text)                                          # the census lists its path
        self.assertIn("/root/node/graph/node/name", text)
        self.assertNotIn("transition", "\n".join(graphs.graph_lines("m.agx", "x", MACHINE)[0]).replace("NT_STATE_MACHINE", ""))   # the report mode prints none of it

    def test_the_caps_are_said_and_the_census_still_counts(self):
        rows = [[f"S{i}", "B"] for i in range(7)]
        data = agx("Big", rows, headers=("From", "To"))
        lines, census = graphs.dump_agx(data, max_rows=3, per_path=1)
        text = "\n".join(lines)
        self.assertIn("... 4 more row(s) not printed", text)
        self.assertEqual(census["/root/node/graph/node"], 1)
        many = b"<root>" + b"".join(b"<node><name>n%d</name></node>" % i for i in range(5)) + b"</root>"
        lines, census = graphs.dump_agx(many, per_path=2)
        self.assertEqual(census["/root/node"], 5)
        self.assertEqual(sum(1 for ln in lines if ln.strip() == "node"), 2)
        self.assertIn("(path /root/node: 3 element(s) not printed", "\n".join(lines))

    def test_a_file_that_is_not_xml_says_so(self):
        self.assertIn("not XML", "\n".join(graphs.dump_lines("b.agx", "x", b"\0\1binary")))


SHEET_XML = ("<root><node><node_type>NT_SM</node_type><name>Top</name><id>1</id><input><name>in</name><link node='2' output='0' hidden='false'>"
             "<property_sheet id='9'>sheet-text<num_columns>2</num_columns>"
             "<column kind='k'><header>Property</header><types>1</types></column><column kind='k'><header>Value</header><types>1</types></column><extra>E</extra>"
             "<row r='1'><prop><type>1</type><value>Event</value></prop><prop><type>1</type><value>Play01</value><flag>F</flag></prop></row>"
             "<row r='1'><prop><type>1</type><value>Transition Type</value></prop><prop><type>1</type><value></value></prop><transition_inside>q</transition_inside></row>"
             "</property_sheet></link></input></node>"
             "<node><node_type>NT_ANIM</node_type><name>StateA</name><id>2</id></node></root>").encode()


class SheetInteriorTests(unittest.TestCase):
    """The Courier's FAL-578 hold: everything inside a property_sheet is printed or counted, and a link sheet says what it is."""
    def setUp(self):
        lines, self.census = graphs.dump_agx(SHEET_XML)
        self.text = "\n".join(lines)

    def test_the_sheets_own_attributes_text_and_other_children_are_printed(self):
        for want in ("@id='9'", "#text='sheet-text'", "num_columns='2'", "extra='E'"):
            self.assertIn(want, self.text)

    def test_column_attributes_and_children_are_printed_once_as_common(self):
        self.assertIn("every column also has {@kind='k', types='1'}", self.text)

    def test_row_attributes_and_children_and_cell_children_are_printed(self):
        self.assertIn("row 1 {transition_inside='q'}: Property='Transition Type'", self.text)      # the one row that has the child says so
        self.assertNotIn("every row also has {@r='1', transition_inside", self.text)   # one of two is not "every"
        self.assertIn("every row also has {@r='1'}", self.text)
        self.assertIn("every cell also has {type='1'}", self.text)
        self.assertIn("Value='Play01' {flag='F'}", self.text)                   # a cell's own difference sits by the cell
        self.assertIn("1 empty", self.text)

    def test_the_census_counts_every_element_inside_a_sheet(self):
        base = "/root/node/input/link/property_sheet"
        for tail, n in (("", 1), ("/num_columns", 1), ("/column", 2), ("/column/types", 2), ("/extra", 1), ("/row", 2), ("/row/prop", 4),
                        ("/row/prop/type", 4), ("/row/prop/flag", 1), ("/row/transition_inside", 1)):
            self.assertEqual(self.census.get(base + tail), n, tail)

    def test_a_sheet_with_event_and_transition_type_rows_is_marked_and_a_link_says_where_it_sits(self):
        self.assertIn("TRANSITION LINK SHEET (rows Event and Transition Type)", self.text)
        self.assertIn("link on node 'Top' (type 'NT_SM', id '1'); attributes node='2' output='0' hidden='false'", self.text)
        self.assertIn("child/attribute id: 'StateA'", self.text)
        self.assertIn("position from 1: 'StateA'", self.text)
        self.assertIn("user_id: none", self.text)
        self.assertIn("none chosen", self.text)                                 # every plausible reading, none picked

    def test_an_ordinary_sheet_is_not_marked_a_link_sheet(self):
        lines, _ = graphs.dump_agx(agx("Machine.agx", [("StateA", "Seq", "", "", "Trans01")]))
        self.assertNotIn("TRANSITION LINK SHEET", "\n".join(lines))


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

    def test_afx_event_strings_are_printed_and_a_rig_without_cnam_lists_its_clips(self):
        rig = "Props\\Generic\\characterassets\\skeleton.rig"
        w = esm.PluginWriter([])
        w.add(esm.Record("ACTI", 0x1001, [(b"EDID", esm.zbytes("Rigged"))] + comp("Stages.agx", rig) + [(b"MODL", esm.zbytes("Props\\Rigged.nif"))]))
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(w.to_bytes())
        self.write_archive("Starfield - Meshes01.ba2", {"Meshes\\Props\\Rigged.nif": model_nif(sequences=(), manager=False),
                                                       "Meshes\\Props\\Generic\\animations\\PlayAnim01.af": b"af",
                                                       "Meshes\\Props\\Generic\\animations\\PlayAnim01.afx": b"\0afx\0Trans01\0KlaxonStop\0"})
        text = self.run_graphs()
        self.assertIn("no CNAM; rig " + rig + ": clips under the rig's folders: 2 file(s)", text)
        self.assertIn("Trans01 | KlaxonStop", text)

    def test_a_guessed_rig_folder_clip_not_tied_to_the_graph_does_not_count_for_m1(self):
        rig = "Props\\Generic\\characterassets\\skeleton.rig"
        w = esm.PluginWriter([])
        w.add(esm.Record("ACTI", 0x1001, [(b"EDID", esm.zbytes("Rigged"))] + comp("Stages.agx", rig) + [(b"MODL", esm.zbytes("Props\\Rigged.nif"))]))
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(w.to_bytes())
        self.write_archive("Starfield - Meshes01.ba2", {"Meshes\\Props\\Rigged.nif": model_nif(sequences=(), manager=False),
                                                       "Meshes\\Props\\Generic\\animations\\HumanWalk.af": b"af",
                                                       "Meshes\\Props\\Generic\\animations\\HumanWalk.afx": b"\0afx\0WalkStart\0"})
        text = self.run_graphs()
        self.assertIn("found beside the rig, not tied to this graph", text)
        self.assertIn("read: NO: none of 1 model(s) read has .af/.afx in its clip folder", text)
        # the same clips become evidence when the .afx names the graph's sequence
        self.write_archive("Starfield - Meshes01.ba2", {"Meshes\\Props\\Rigged.nif": model_nif(sequences=(), manager=False),
                                                       "Meshes\\Props\\Generic\\animations\\HumanWalk.af": b"af",
                                                       "Meshes\\Props\\Generic\\animations\\HumanWalk.afx": b"\0afx\0playanim01\0"})
        text = self.run_graphs()
        self.assertIn("read: YES: 1 of 1 parsed model(s) have .af/.afx in their clip folder", text)

    def test_the_default_list_has_the_hybrid_graph(self):
        self.assertIn("hybridstategraph01", graphs.DEFAULT_GRAPHS)

    def test_the_old_probe_modes_still_parse(self):
        self.assertEqual(sys.modules["vault111_anim_probe"].DEFAULT_REFS, ("00126D", "00138B", "001616"))


class DumpModeTests(unittest.TestCase):
    setUp = GraphsModeTests.setUp                       # the same synthetic Data folder, without re-running its tests
    write_archive = GraphsModeTests.write_archive
    run_graphs = GraphsModeTests.run_graphs

    def run_dump(self, *names, extra=()):
        argv = ["--out", self.out, "--data", self.data, "--game-archive", "Starfield - Animations.ba2"]
        for n in names:
            argv += ["--dump-graph", n]
        self.assertEqual(probe.main(["--graphs"] + argv + list(extra)), 0)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_the_dump_mode_reads_only_the_archives_and_says_what_is_missing(self):
        self.write_archive("Starfield - Animations.ba2", {GRAPHS + "Machine.agx": MACHINE, GRAPHS + "Stages.agx": STAGES})
        before = sorted(os.listdir(self.data))
        text = self.run_dump("machine", "Stages.agx", "nothere")
        self.assertIn("vault111_anim_graphs --dump-graph (read-only; FAL-489): machine, stages, nothere", text)
        self.assertIn("=== graph machine.agx", text)
        self.assertIn("row 0: From='StateA' | To='StateB' | Fires On='Trans01'", text)
        self.assertIn("=== graph stages.agx", text)
        self.assertIn("=== graph nothere.agx: unread (no entry of that name in the archives read)", text)
        self.assertNotIn("##### 2. ACTI", text)                       # no Starfield.esm read
        self.assertNotIn("##### 3. models", text)                     # no models read
        self.assertEqual(sorted(os.listdir(self.data)), before)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), sorted(["Data", "r.txt"]))

    def test_without_dump_graph_the_report_mode_is_unchanged(self):
        self.assertIn("##### 1. the .agx graphs", self.run_graphs())


LIFT = 0x10C35
LIFT_MODEL = "Ships\\QuickLift\\QuickLift1.nif"


def lift_esm():
    """Starfield.esm with a lift-like ACTI (graph component, a VMAD with a script name, a keyword, an unreadable blob) and a CELL group
    holding two references to it (one persistent, one temporary), one to another base, and one compressed-sized REFR without NAME."""
    w = esm.PluginWriter([])
    vmad = struct.pack("<hhH", 6, 2, 1) + struct.pack("<H", 14) + b"QuickLiftScript" + b"\x00\x00\x00"
    w.add(esm.Record("ACTI", LIFT, [(b"EDID", esm.zbytes("ShipQuickLift1")), (b"VMAD", vmad), (b"KWDA", struct.pack("<I", 0xABCD)),
                                    (b"FNAM", b"\x01\x02\x03\x04\x05\x06")] + comp("AnimTextData\\Tables\\Graphs\\TwoStages.agx", "Ships\\QuickLift\\skeleton.rig", "Ships\\QuickLift\\Animations")
                     + [(b"MODL", esm.zbytes(LIFT_MODEL))]))
    w.add(esm.Record("ACTI", 0x10C36, [(b"EDID", esm.zbytes("NoModel"))]))
    body = w.to_bytes()
    cell = esm.Record("CELL", 0x3001, [(b"EDID", esm.zbytes("ShipCellA"))])
    def ref(fid, base, pos=None):
        subs = [(b"NAME", struct.pack("<I", base))] + ([(b"DATA", struct.pack("<6f", *pos, 0, 0, 0))] if pos else [])
        return esm.Record("REFR", fid, subs).to_bytes()
    persistent = esm.group_bytes(struct.pack("<I", 0x3001), ref(0x4001, LIFT, (1.0, 2.0, 3.5)), 8)
    temporary = esm.group_bytes(struct.pack("<I", 0x3001), ref(0x4002, LIFT, (10.0, 20.0, 30.0)) + ref(0x4003, 0x10C36) + ref(0x4004, LIFT), 9)
    return body + esm.group_bytes("CELL", cell.to_bytes() + persistent + temporary)


class FormModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "Data")
        os.makedirs(self.data)
        self.out = os.path.join(self.tmp.name, "r.txt")
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(lift_esm())
        with open(os.path.join(self.data, "Starfield - Meshes01.ba2"), "wb") as f:
            f.write(general_archive({"Meshes\\" + LIFT_MODEL: model_nif()}))

    def run_form(self, *argv):
        self.assertEqual(probe.main(["--graphs", "--out", self.out, "--data", self.data] + list(argv)), 0)
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_dump_form_prints_every_subrecord_the_strings_in_the_blob_and_the_form_id_a_four_byte_subrecord_could_be(self):
        text = self.run_form("--dump-form", "00010C35", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertIn("=== form 00010C35", text)
        self.assertIn("ACTI  edid ShipQuickLift1", text)
        self.assertIn("EDID [15] text 'ShipQuickLift1'", text)
        self.assertIn("VMAD [", text)
        self.assertIn("QuickLiftScript", text)                       # the script name, found inside the blob without parsing it
        self.assertIn("KWDA [4] hex cd ab 00 00   (u32 0x0000abcd", text)
        self.assertIn("FNAM [6] hex 01 02 03 04 05 06", text)        # an unknown blob is printed as hex, not guessed
        self.assertIn("components (BFCB): BGSAnimationGraph_Component", text)
        self.assertIn("ANAM=AnimTextData\\Tables\\Graphs\\TwoStages.agx", text)
        self.assertIn("BNAM=Ships\\QuickLift\\skeleton.rig", text)
        self.assertIn("CNAM=Ships\\QuickLift\\Animations", text)
        self.assertIn("model: " + LIFT_MODEL, text)

    def test_the_model_is_checked_against_the_archives_given(self):
        text = self.run_form("--dump-form", "10C35", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertIn("--- model " + LIFT_MODEL, text)
        self.assertIn("NiControllerManager: 1", text)
        self.assertIn("PlayAnim01", text)
        # the same record, a model that is NOT in the archives read: said, not hidden
        os.remove(os.path.join(self.data, "Starfield - Meshes01.ba2"))
        with open(os.path.join(self.data, "Starfield - Meshes01.ba2"), "wb") as f:
            f.write(general_archive({"Meshes\\Other.nif": model_nif()}))
        self.assertIn("not in the archives read", self.run_form("--dump-form", "10C35", "--game-archive", "Starfield - Meshes*.ba2"))

    def test_without_an_archive_the_model_check_is_unread(self):
        self.assertIn("model check unread: no --game-archive given", self.run_form("--dump-form", "10C35"))

    def test_a_record_without_a_model_and_a_form_that_is_not_there_say_so(self):
        text = self.run_form("--dump-form", "10C36", "--dump-form", "0x99999", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertIn("model: no .nif text in the record", text)
        self.assertIn("=== form 00099999\n  no record with that form id (searched ACTI", text)
        self.assertNotIn("--- model", text)

    def test_refs_to_counts_placements_in_every_child_group_with_cell_and_position(self):
        text = self.run_form("--refs-to", "00010C35")
        self.assertIn("=== references to 00010C35", text)
        self.assertIn("4 placed record(s) scanned", text)
        self.assertIn("3 found; first 3:", text)
        self.assertIn("REFR 00004001  cell 00003001 ShipCellA  position 1.0, 2.0, 3.5", text)
        self.assertIn("REFR 00004002  cell 00003001 ShipCellA  position 10.0, 20.0, 30.0", text)
        self.assertIn("REFR 00004004  cell 00003001 ShipCellA  position unread", text)         # no DATA: unread, not zero
        self.assertNotIn("00004003", text)                                                        # the reference to another base

    def test_refs_limit_caps_the_list_and_a_base_never_placed_says_so_without_a_why(self):
        self.assertIn("3 found; first 1:", self.run_form("--refs-to", "10C35", "--refs-limit", "1"))
        text = self.run_form("--refs-to", "777")
        self.assertIn("0 found", text)
        self.assertIn("none found: no placed reference of that base in the groups read (the game may place it another way: unread)", text)

    def test_only_the_report_is_written_and_a_missing_esm_is_said(self):
        before = sorted(os.listdir(self.data))
        self.run_form("--dump-form", "10C35", "--refs-to", "10C35")
        self.assertEqual(sorted(os.listdir(self.data)), before)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), sorted(["Data", "r.txt"]))
        os.remove(os.path.join(self.data, "Starfield.esm"))
        self.assertIn("unread: ", self.run_form("--dump-form", "10C35"))

    def test_a_bad_form_id_is_refused(self):
        with self.assertRaises(SystemExit):
            self.run_form("--dump-form", "notahex")


def candidates_esm():
    """Three ACTIs on twostages.agx: A (model in the archive, placed twice), B (model NOT in the archive, placed once), C (no model, never placed); one on another graph."""
    w = esm.PluginWriter([])
    tg = "AnimTextData\\Tables\\Graphs\\TwoStages.agx"
    w.add(esm.Record("ACTI", 0x1A, [(b"EDID", esm.zbytes("LiftA"))] + comp(tg, "G\\skeleton.rig") + [(b"MODL", esm.zbytes(LIFT_MODEL))]))
    w.add(esm.Record("ACTI", 0x1B, [(b"EDID", esm.zbytes("LiftB"))] + comp(tg, "G\\skeleton.rig") + [(b"MODL", esm.zbytes("Ships\\Gone.nif"))]))
    w.add(esm.Record("ACTI", 0x1C, [(b"EDID", esm.zbytes("LiftC"))] + comp(tg)))
    w.add(esm.Record("ACTI", 0x1D, [(b"EDID", esm.zbytes("Other"))] + comp("AnimTextData\\Tables\\Graphs\\Stages.agx") + [(b"MODL", esm.zbytes(LIFT_MODEL))]))
    body = w.to_bytes()
    cell = esm.Record("CELL", 0x3001, [(b"EDID", esm.zbytes("CellA"))])
    def ref(fid, base, pos):
        return esm.Record("REFR", fid, [(b"NAME", struct.pack("<I", base)), (b"DATA", struct.pack("<6f", *pos, 0, 0, 0))]).to_bytes()
    kids = esm.group_bytes(struct.pack("<I", 0x3001), ref(0x4001, 0x1A, (1, 2, 3)) + ref(0x4002, 0x1A, (4, 5, 6)) + ref(0x4003, 0x1B, (7, 8, 9)) + ref(0x4004, 0x1D, (0, 0, 0)), 9)
    return body + esm.group_bytes("CELL", cell.to_bytes() + kids)


class CandidatesTests(unittest.TestCase):
    setUp_form = FormModeTests.setUp
    run_form = FormModeTests.run_form

    def setUp(self):
        self.setUp_form()
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(candidates_esm())

    def test_the_candidates_list_every_user_with_its_model_check_and_placement_count_best_first(self):
        text = self.run_form("--candidates", "twostages", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertIn("=== candidates for graph twostages: 3 ACTI/FURN record(s) name it", text)
        self.assertIn("4 placed record(s) in the CELL and WRLD groups", text)
        a, b, c = (text.index(f"ACTI {x}") for x in ("0000001A LiftA", "0000001B LiftB", "0000001C LiftC"))
        self.assertTrue(a < b < c)                                                          # most placed first
        self.assertIn("LiftA  placed 2  model in the archives  model=" + LIFT_MODEL, text)
        self.assertIn("LiftB  placed 1  model NOT in the archives read", text)
        self.assertIn("LiftC  placed 0  no model", text)
        self.assertIn("REFR 00004002  cell 00003001 CellA  position 4.0, 5.0, 6.0", text)
        self.assertNotIn("Other", text)                                                       # another graph's user is not a candidate
        self.assertIn("usable (model in the archives AND placed at least once): 1 of 3", text)

    def test_without_an_archive_the_model_is_unread_not_missing_and_nothing_is_usable(self):
        text = self.run_form("--candidates", "twostages.agx")
        self.assertIn("model check: unread (no --game-archive given)", text)
        self.assertIn("LiftA  placed 2  model unread", text)
        self.assertNotIn("NOT in the archives", text)
        self.assertIn("usable (model in the archives AND placed at least once): 0 of 3", text)

    def test_a_graph_nobody_names_says_so(self):
        self.assertIn("none found: unread or no record names this graph", self.run_form("--candidates", "nosuchgraph"))

    def test_the_one_form_refs_still_work_through_the_shared_scan(self):
        self.assertIn("2 found; first 2:", self.run_form("--refs-to", "1A"))


def placed_esm():
    """ACTI/FURN with graphs: Stages x2 (one placed, model present; one placed, model missing), TwoStages x1 (never placed), GenericOpenClose x1 (placed 3 times, model present),
    an ACTI without a graph component whose editor id has 'Lift', and a FURN with a graph, placed, no model."""
    w = esm.PluginWriter([])
    G = "AnimTextData\\Tables\\Graphs\\"
    w.add(esm.Record("ACTI", 0x21, [(b"EDID", esm.zbytes("ConsoleOne"))] + comp(G + "Stages.agx", "G\\skeleton.rig", "C\\Anim") + [(b"MODL", esm.zbytes(LIFT_MODEL))]))
    w.add(esm.Record("ACTI", 0x22, [(b"EDID", esm.zbytes("ConsoleGone"))] + comp(G + "Stages.agx") + [(b"MODL", esm.zbytes("Ships\\Gone.nif"))]))
    w.add(esm.Record("ACTI", 0x23, [(b"EDID", esm.zbytes("LiftNever"))] + comp(G + "TwoStages.agx") + [(b"MODL", esm.zbytes("Ships\\Gone2.nif"))]))
    w.add(esm.Record("ACTI", 0x24, [(b"EDID", esm.zbytes("DoorishThing"))] + comp(G + "GenericOpenClose01.agx") + [(b"MODL", esm.zbytes(LIFT_MODEL))]))
    w.add(esm.Record("ACTI", 0x25, [(b"EDID", esm.zbytes("PlainLiftSwitch")), (b"MODL", esm.zbytes(LIFT_MODEL))]))
    w.add(esm.Record("FURN", 0x26, [(b"EDID", esm.zbytes("ChairNoModel"))] + comp(G + "FurnitureDefault.agx")))
    body = w.to_bytes()
    cell = esm.Record("CELL", 0x3001, [(b"EDID", esm.zbytes("CellA"))])
    def ref(fid, base, pos):
        return esm.Record("REFR", fid, [(b"NAME", struct.pack("<I", base)), (b"DATA", struct.pack("<6f", *pos, 0, 0, 0))]).to_bytes()
    refs = ref(0x4001, 0x21, (1, 2, 3)) + ref(0x4002, 0x22, (4, 5, 6)) + ref(0x4003, 0x24, (7, 8, 9)) + ref(0x4004, 0x24, (0, 0, 0)) + ref(0x4005, 0x24, (0, 0, 1)) + ref(0x4006, 0x25, (9, 9, 9)) + ref(0x4007, 0x26, (1, 1, 1))
    return body + esm.group_bytes("CELL", cell.to_bytes() + esm.group_bytes(struct.pack("<I", 0x3001), refs, 9))


class PlacedTests(unittest.TestCase):
    setUp_form = FormModeTests.setUp
    run_form = FormModeTests.run_form

    def setUp(self):
        self.setUp_form()
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(placed_esm())

    def test_the_census_groups_by_graph_counts_placed_and_usable_and_orders_by_usable(self):
        text = self.run_form("--placed", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertIn("=== placed census: 6 ACTI/FURN record(s) read, 5 with an animation graph component", text)
        self.assertIn("7 placed record(s) in the CELL and WRLD groups", text)
        self.assertIn("  stages: 2 base(s), 2 placed, 1 usable, 2 placement(s) in all", text)
        self.assertIn("  genericopenclose01: 1 base(s), 1 placed, 1 usable, 3 placement(s) in all", text)
        self.assertIn("  twostages: 1 base(s), 0 placed, 0 usable, 0 placement(s) in all", text)
        self.assertIn("  furnituredefault: 1 base(s), 1 placed, 0 usable, 1 placement(s) in all", text)
        order = [text.index(f"  {g}: ") for g in ("stages", "genericopenclose01", "furnituredefault", "twostages")]
        self.assertEqual(order, sorted(order))                                      # usable 1 (stages < genericopenclose01 by name), then placed-not-usable, then unplaced
        self.assertIn("ACTI 00000024 DoorishThing  placed 3  model in the archives  model=" + LIFT_MODEL, text)
        self.assertIn("first REFR 00004003 cell 00003001 CellA at 7.0, 8.0, 9.0", text)
        self.assertIn("ACTI 00000022 ConsoleGone  placed 1  model NOT in the archives read", text)
        self.assertNotIn("LiftNever  placed", text)                                  # never placed: counted, not listed under the graph's placed bases
        self.assertNotIn("PlainLiftSwitch", text)                                    # no graph, no --edid-word: not in the census

    def test_placed_top_caps_the_listed_bases_per_graph_but_not_the_counts(self):
        text = self.run_form("--placed", "--placed-top", "1", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertIn("  stages: 2 base(s), 2 placed, 1 usable", text)
        self.assertEqual(text.count("ConsoleOne  placed") + text.count("ConsoleGone  placed"), 1)

    def test_without_an_archive_models_are_unread_and_nothing_is_usable(self):
        text = self.run_form("--placed")
        self.assertIn("model check: unread (no --game-archive given)", text)
        self.assertIn("1 placed, 0 usable", text)
        self.assertNotIn("NOT in the archives", text)

    def test_edid_word_lists_every_match_with_or_without_a_graph_case_insensitive(self):
        text = self.run_form("--edid-word", "LIFT", "--edid-word", "nosuch", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertIn("editor id contains 'LIFT': 2 record(s), 1 placed", text)
        self.assertIn("ACTI 00000025 PlainLiftSwitch  graph=none  placed 1  model in the archives", text)
        self.assertIn("ACTI 00000023 LiftNever  graph=twostages  placed 0  model NOT in the archives read", text)
        self.assertLess(text.index("PlainLiftSwitch"), text.index("LiftNever"))        # placed first
        self.assertIn("editor id contains 'nosuch': 0 record(s), 0 placed", text)
        self.assertNotIn("per graph (", text)                                              # --edid-word alone does not print the per-graph census

    def test_only_the_report_is_written_and_the_other_options_are_unchanged(self):
        before = sorted(os.listdir(self.data))
        self.run_form("--placed", "--edid-word", "lift")
        self.assertEqual(sorted(os.listdir(self.data)), before)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), sorted(["Data", "r.txt"]))
        self.assertIn("=== candidates for graph stages: 2 ACTI/FURN record(s) name it", self.run_form("--candidates", "stages"))


class DumpFormEdidTests(unittest.TestCase):
    setUp_form = FormModeTests.setUp
    run_form = FormModeTests.run_form

    def setUp(self):
        self.setUp_form()
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(placed_esm())

    def test_an_editor_id_resolves_to_its_form_id_and_dumps_like_dump_form(self):
        text = self.run_form("--dump-form-edid", "doorishthing", "--game-archive", "Starfield - Meshes*.ba2")        # case-insensitive
        self.assertIn("=== editor id 'doorishthing' resolved to form id 00000024", text)
        self.assertIn("=== form 00000024", text)
        self.assertIn("ACTI  edid DoorishThing", text)
        self.assertIn("--- model " + LIFT_MODEL, text)
        same = self.run_form("--dump-form", "24", "--game-archive", "Starfield - Meshes*.ba2")
        self.assertEqual(text.split("=== form 00000024", 1)[1], same.split("=== form 00000024", 1)[1])

    def test_an_unknown_editor_id_and_a_record_type_not_searched_say_so(self):
        text = self.run_form("--dump-form-edid", "NoSuchThing")
        self.assertIn("=== editor id 'NoSuchThing': no ACTI/FURN record has that editor id (other record types are not searched; use --dump-form with the hex id)", text)
        self.assertNotIn("=== form ", text)

    def test_two_records_with_one_editor_id_are_both_dumped(self):
        w = esm.PluginWriter([])
        for fid in (0x31, 0x32):
            w.add(esm.Record("ACTI", fid, [(b"EDID", esm.zbytes("TwinMarker"))]))
        with open(os.path.join(self.data, "Starfield.esm"), "wb") as f:
            f.write(w.to_bytes())
        text = self.run_form("--dump-form-edid", "TwinMarker")
        self.assertIn("resolved to form id 00000031 (1 of 2)", text)
        self.assertIn("resolved to form id 00000032 (1 of 2)", text)

    def test_it_works_beside_dump_form_and_writes_only_out(self):
        before = sorted(os.listdir(self.data))
        text = self.run_form("--dump-form", "21", "--dump-form-edid", "ConsoleGone")
        self.assertIn("=== form 00000021", text)
        self.assertIn("=== form 00000022", text)
        self.assertEqual(sorted(os.listdir(self.data)), before)


if __name__ == "__main__":
    unittest.main()
