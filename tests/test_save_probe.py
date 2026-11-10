"""scripts/game/save_probe.py against a synthetic save built here (no real save, or part of one, is ever used)."""
import contextlib
import io
import json
import math
import os
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import save_probe  # noqa: E402

PREFIX = 0x05                       # the load index the fixture gives the mission plugin
MISSION_IID = bytes.fromhex("a1b2c3d4e5f60718")
KEEPER_IID = bytes.fromhex("1827364554637281")
PRESTON_POS = (-1938.25, -1701.85, 80.36)
PLAYER_POS = (-2022.71, -1704.28, 88.19)
SPOT = (-2011.14, -1697.54, 89.09)


def u16s(s):
    b = s.encode("latin-1")
    return struct.pack("<H", len(b)) + b


def change_form(refbytes, xyz, heading, flags=0x10):
    # RefID(3) flags(4) vsval A=1, B=1, C=16 (one byte each), 1*3 bytes, 1*2 bytes, 1 byte, then x y z heading
    return (refbytes + struct.pack("<I", flags) + bytes([1 << 2, 1 << 2, 16 << 2]) + b"\x00" * 3 + b"\x00" * 2
            + b"\x00" + struct.pack("<4f", *xyz, heading))


def build_plain_save(keeper_object_member=False, ids=None, mission_ref=1, keeper_ref=3):
    """The decompressed save. Returns bytes. `ids` replaces the form-id array (Preston stays at index 2)."""
    strings = ["Quest", SCRIPT_NAME, "applied", "Int", "ticks", "Int", "found", "Bool", "label", "String",
               "ratio", "Float", "target", "ObjectReference", "hello"]
    s = {v: i for i, v in enumerate(strings)}
    out = bytearray(b"SFS_SAVEGAME" + b"\x00" * 13)
    out += u16s("Hero") + struct.pack("<I", 42) + u16s("Sanctuary Hills") + u16s("12h 3m") + u16s("Human")
    out += b"\x00\x00" + b"1.14.70.0\x00" + b"\xff" * 16
    # change forms: Preston (array index 2) and the player (RefID 40 00 14)
    out += change_form(bytes([0, 0, 2]), PRESTON_POS, 1.5) + b"\xff" * 4
    out += change_form(bytes([0x40, 0, 0x14]), PLAYER_POS, 0.25) + b"\xff" * 8
    # Papyrus string table
    out += struct.pack("<I", len(strings)) + b"".join(u16s(x) for x in strings)
    # script type: name, parent, member count, (name, type) pairs
    members = [("applied", "Int"), ("ticks", "Int"), ("found", "Bool"), ("label", "String"), ("ratio", "Float"),
               ("target", "ObjectReference")]
    out += struct.pack("<III", s[SCRIPT_NAME], s["Quest"], len(members))
    for n, t in members:
        out += struct.pack("<II", s[n], s[t])
    out += b"\xff" * 4
    # instances: id(8) name idx(4) 00 00 ff ff ref(3); mission = array index 1, keeper = array index 3
    for iid, ref in ((MISSION_IID, mission_ref), (KEEPER_IID, keeper_ref)):
        out += iid + struct.pack("<I", s[SCRIPT_NAME]) + b"\x00\x00\xff\xff" + bytes([0, 0, ref]) + b"\xee" * 3
    # member values: id 0x2B count, then typed values
    mission = (bytes([3]) + struct.pack("<i", 30) + bytes([3]) + struct.pack("<i", 429) + bytes([5, 0])
               + bytes([2]) + struct.pack("<I", s["hello"]) + bytes([4]) + struct.pack("<f", 0.5) + bytes([0]))
    out += MISSION_IID + b"\x2b" + struct.pack("<I", len(members)) + mission + b"\xff" * 4
    if keeper_object_member:
        # 'found' is an object reference (code 1, width unknown): 'found' and everything after is not decoded
        keeper = bytes([3]) + struct.pack("<i", 7) + bytes([3]) + struct.pack("<i", 151) + bytes([1]) + b"\x00" * 12
    else:
        keeper = (bytes([3]) + struct.pack("<i", 7) + bytes([3]) + struct.pack("<i", 151) + bytes([5, 1])
                  + bytes([2]) + struct.pack("<I", s["hello"]) + bytes([4]) + struct.pack("<f", 1.5) + bytes([0]))
    out += KEEPER_IID + b"\x2b" + struct.pack("<I", len(members)) + keeper + b"\xff" * 4
    # timers: ms(4) id(4) instance id(8) 00 x5
    out += struct.pack("<II", 2500, 1) + MISSION_IID + b"\x00" * 5 + b"\xff" * 4
    out += struct.pack("<II", 8000, 2) + KEEPER_IID + b"\x00" * 5 + b"\xff" * 4
    # form-id array: count then ids; index 1 = mission quest, 2 = Preston, 3 = keeper quest
    ids = ids or [(PREFIX << 24) | 0x800, (PREFIX << 24) | 0x802, (PREFIX << 24) | 0x814]
    out += struct.pack("<I", len(ids)) + b"".join(struct.pack("<I", i) for i in ids)
    out += b"\xff" * 16
    return bytes(out)


def slurp(path):
    with open(path, "rb") as f:
        return f.read()


SCRIPT_NAME = save_probe.SCRIPT_NAME


def build_container(plain, chunk=None):
    """BCPS container with two chunks: the first stored (its size equals its uncompressed size), the second zlib."""
    chunk = chunk or (len(plain) + 1) // 2
    parts = [plain[:chunk], plain[chunk:]]
    stored = parts[0]
    packed = zlib.compress(parts[1])
    assert len(packed) != len(parts[1]), "fixture: second chunk must really be compressed"
    sizes = [len(stored), len(packed)]
    head = bytearray(64)
    head[:4] = b"BCPS"
    struct.pack_into("<Q", head, 8, 64)                          # chunk size table
    struct.pack_into("<Q", head, 24, 64 + 4 * len(sizes))        # compressed data
    struct.pack_into("<Q", head, 32, len(plain))                 # uncompressed size
    struct.pack_into("<Q", head, 48, chunk)                      # chunk uncompressed size
    struct.pack_into("<Q", head, 56, 0)                          # no padding
    return bytes(head) + struct.pack("<2I", *sizes) + stored + packed


class ContainerTests(unittest.TestCase):
    def test_stored_and_compressed_chunks_round_trip(self):
        plain = build_plain_save()
        self.assertEqual(save_probe.decode_container(build_container(plain)), plain)

    def test_plain_save_passes_through(self):
        plain = build_plain_save()
        self.assertEqual(save_probe.decode_container(plain), plain)

    def test_truncated_container_is_a_clear_error(self):
        raw = build_container(build_plain_save())
        for cut in (10, len(raw) - 12, 70):
            with self.assertRaises(save_probe.SaveError) as cm:
                save_probe.decode_container(raw[:cut])
            self.assertIn("truncated", str(cm.exception))

    def test_not_a_save(self):
        with self.assertRaises(save_probe.SaveError) as cm:
            save_probe.decode_container(b"PK\x03\x04 this is a zip, not a save" * 4)
        self.assertIn("not a Starfield save", str(cm.exception))
        with self.assertRaises(save_probe.SaveError):
            save_probe.decode_container(b"")


class ReportTests(unittest.TestCase):
    def report(self, **kw):
        spots = {"Preston": SPOT}
        return save_probe.build_report(build_plain_save(**kw), spots, None, "fixture.sfs")

    def test_header(self):
        h = self.report()["header"]
        self.assertNotIn("player", h)                      # the character name is off by default
        rep = save_probe.build_report(build_plain_save(), None, None, "x", show_name=True)
        self.assertEqual(rep["header"]["player"], "Hero")
        self.assertEqual((h["level"], h["location"], h["play_time"], h["race"], h["game_version"]),
                         (42, "Sanctuary Hills", "12h 3m", "Human", "1.14.70.0"))

    def test_plugin_index_is_found_from_the_save(self):
        self.assertEqual(self.report()["plugin_index"], "%02X" % PREFIX)

    def test_script_state_of_both_instances(self):
        rep = self.report()
        by_role = {i["role"]: i for i in rep["instances"]}
        self.assertEqual(set(by_role), {"mission", "keeper"})
        m = {x["name"]: x["value"] for x in by_role["mission"]["members"]}
        self.assertEqual(m, {"applied": 30, "ticks": 429, "found": False, "label": "hello", "ratio": 0.5, "target": None})
        k = {x["name"]: x["value"] for x in by_role["keeper"]["members"]}
        self.assertEqual((k["applied"], k["ticks"], k["found"], k["ratio"]), (7, 151, True, 1.5))
        self.assertEqual(by_role["mission"]["quest_form"], "%02X000800" % PREFIX)
        self.assertEqual(by_role["keeper"]["quest_form"], "%02X000814" % PREFIX)

    def test_timers(self):
        rep = self.report()
        by_role = {i["role"]: i["timers"] for i in rep["instances"]}
        self.assertEqual(by_role["mission"], [{"timer_id": 1, "ms_left": 2500}])
        self.assertEqual(by_role["keeper"], [{"timer_id": 2, "ms_left": 8000}])

    def test_actor_and_player_positions_and_distances(self):
        rep = self.report()
        pre = next(a for a in rep["actors"] if a["label"] == "Preston")
        self.assertTrue(pre["found"])
        self.assertEqual(pre["pos"], [-1938.25, -1701.85, 80.36])
        self.assertAlmostEqual(pre["heading_rad"], 1.5, places=3)
        self.assertEqual(pre["from_spot_m"], round(math.dist(PRESTON_POS, SPOT), 1))
        self.assertEqual(pre["spot"], list(SPOT))
        other = next(a for a in rep["actors"] if a["label"] == "Codsworth")
        self.assertFalse(other["found"])                        # not in this fixture: said, not invented
        pl = rep["player"][0]
        self.assertEqual(pl["pos"], [-2022.71, -1704.28, 88.19])
        self.assertEqual(pl["from_spots_m"]["Preston"], round(math.dist(PLAYER_POS, SPOT), 1))

    def test_no_spots_means_no_distances(self):
        rep = save_probe.build_report(build_plain_save(), None, None, "x")
        pre = next(a for a in rep["actors"] if a["label"] == "Preston")
        self.assertIsNone(pre["from_spot_m"])

    def test_stage_flags_are_reported_as_not_decoded(self):
        qs = self.report()["quest_stage"]
        self.assertFalse(qs["decoded"])
        self.assertIn("not decoded", qs["note"])

    def test_script_stage_is_the_mission_applied_value(self):
        ss = self.report()["script_stage"]
        self.assertEqual(ss["value"], 30)
        self.assertEqual(ss["description"], "the last stage the mission script applied")

    def test_script_stage_missing_without_mission(self):
        plain = build_plain_save().replace(SCRIPT_NAME.encode(), b"X" * len(SCRIPT_NAME))
        self.assertIsNone(save_probe.build_report(plain, {}, None, "x")["script_stage"])

    def test_unknown_type_code_does_not_fail_the_read(self):
        rep = self.report(keeper_object_member=True)
        keeper = next(i for i in rep["instances"] if i["role"] == "keeper")
        got = {m["name"]: m for m in keeper["members"]}
        self.assertEqual((got["applied"]["value"], got["ticks"]["value"]), (7, 151))
        self.assertTrue(got["applied"]["decoded"])
        for name in ("found", "label", "ratio", "target"):
            self.assertFalse(got[name]["decoded"], name)
            self.assertIn("not decoded", got[name]["note"])
        self.assertIn("type code 1", got["found"]["note"])
        # the mission instance and the positions are still there
        mission = next(i for i in rep["instances"] if i["role"] == "mission")
        self.assertEqual(mission["members"][0]["value"], 30)
        self.assertTrue(any(a["label"] == "Preston" and a["found"] for a in rep["actors"]))
        self.assertTrue(any("not decoded" in w for w in rep["warnings"]))

    def test_save_without_the_mission_still_reports_the_player(self):
        plain = build_plain_save().replace(SCRIPT_NAME.encode(), b"X" * len(SCRIPT_NAME))
        rep = save_probe.build_report(plain, {"Preston": SPOT}, None, "x")
        self.assertIsNone(rep["script"])
        self.assertTrue(any("not found" in w for w in rep["warnings"]))
        self.assertEqual(rep["header"]["location"], "Sanctuary Hills")


class ReviewFindingTests(unittest.TestCase):
    """FAL-176 review of 4f7650ee."""

    def test_false_member_record_does_not_win_a_tie(self):
        plain = build_plain_save() + MISSION_IID + bytes([0x2B]) + struct.pack("<I", 6) + bytes(6)
        rep = save_probe.build_report(plain, None, None, "x")
        self.assertEqual(rep["script_stage"]["value"], 30)                  # the type-fitting record wins
        self.assertEqual(rep["warnings"], [])

    def test_conflicting_equal_records_are_ambiguous_and_say_so(self):
        plain = build_plain_save()
        i = plain.index(MISSION_IID + b"\x2b")
        dup = bytearray(plain[i:i + 13 + 5 + 5 + 2 + 5 + 5 + 1])
        dup[14:18] = struct.pack("<i", 40)                                  # same shape, applied=40
        rep = save_probe.build_report(plain + bytes(dup), None, None, "x")
        self.assertIsNone(rep["script_stage"])
        text = "\n".join(rep["warnings"])
        self.assertIn("equally plausible", text)
        self.assertIn("script_stage could not be read", text)

    def test_applied_must_be_a_decoded_integer(self):
        plain = build_plain_save()
        i = plain.index(MISSION_IID + b"\x2b") + 13
        bad = plain[:i] + bytes([5, 1]) + plain[i + 5:]                     # applied as a bool
        rep = save_probe.build_report(bad, None, None, "x")
        self.assertIsNone(rep["script_stage"])

    def test_compressed_chunk_cannot_expand_past_its_declared_size(self):
        plain = build_plain_save()
        bomb = zlib.compress(b"\x00" * 1_000_000)
        head = bytearray(64)
        head[:4] = b"BCPS"
        struct.pack_into("<Q", head, 8, 64)
        struct.pack_into("<Q", head, 24, 68)
        struct.pack_into("<Q", head, 32, 12)
        struct.pack_into("<Q", head, 48, 12)
        raw = bytes(head) + struct.pack("<I", len(bomb)) + bomb
        with self.assertRaises(save_probe.SaveError) as cm:
            save_probe.decode_container(raw)
        self.assertIn("expands past", str(cm.exception))
        # a stream that stops early is a clear error too
        short = zlib.compress(plain)[:-10]
        head2 = bytearray(head)
        struct.pack_into("<Q", head2, 32, len(plain))
        struct.pack_into("<Q", head2, 48, len(plain))
        with self.assertRaises(save_probe.SaveError):
            save_probe.decode_container(bytes(head2) + struct.pack("<I", len(short)) + short)

    def test_plain_save_with_only_the_magic_is_truncated(self):
        for raw in (b"SFS_SAVEGAME", build_plain_save()[:30]):
            with self.assertRaises(save_probe.SaveError) as cm:
                save_probe.decode_container(raw)
            self.assertIn("truncated", str(cm.exception))


class FormArrayTests(unittest.TestCase):
    def roles(self, rep):
        return {i["instance_id"]: i["role"] for i in rep["instances"]}

    def test_decoy_id_in_the_array_does_not_mislabel_the_roles(self):
        # the reported failure: mission ref 1, keeper ref 4, an unrelated id between them
        ids = [(PREFIX << 24) | 0x800, (PREFIX << 24) | 0x802, 0x00000010, (PREFIX << 24) | 0x814]
        rep = save_probe.build_report(build_plain_save(ids=ids, keeper_ref=4), {"Preston": SPOT}, None, "x")
        self.assertEqual(self.roles(rep), {MISSION_IID.hex(): "mission", KEEPER_IID.hex(): "keeper"})
        self.assertEqual(rep["script_stage"]["value"], 30)
        self.assertEqual(rep["plugin_index"], "%02X" % PREFIX)
        self.assertEqual(rep["warnings"], [])

    def test_false_low_prefix_candidate_is_rejected(self):
        # a second, inconsistent look-alike (prefix 01, no keeper/Preston) earlier in the file must not win
        decoy = struct.pack("<I", 7) + struct.pack("<I", 0x01000800) + b"\x00" * 40
        plain = build_plain_save()
        rep = save_probe.build_report(plain.replace(b"\xff" * 16, decoy, 1), None, None, "x")
        self.assertEqual(rep["plugin_index"], "%02X" % PREFIX)
        self.assertEqual(rep["script_stage"]["value"], 30)

    def test_no_consistent_array_gives_warning_and_no_roles(self):
        ids = [(PREFIX << 24) | 0x800, (PREFIX << 24) | 0x802, 0x10]          # no xx000814 anywhere
        rep = save_probe.build_report(build_plain_save(ids=ids, keeper_ref=3), None, None, "x")
        self.assertIsNone(rep["plugin_index"])
        self.assertTrue(all(i["role"] == "unknown" for i in rep["instances"]))
        self.assertIsNone(rep["script_stage"])
        text = "\n".join(rep["warnings"])
        self.assertIn("--plugin-index", text)
        self.assertIn("script_stage could not be read", text)

    def test_two_candidates_are_ambiguous(self):
        # two arrays with different prefixes, each consistent: the tool must not choose
        ids2 = [(0x06 << 24) | 0x800, (0x06 << 24) | 0x802, (0x06 << 24) | 0x814]
        extra = struct.pack("<I", 3) + b"".join(struct.pack("<I", i) for i in ids2)
        plain = build_plain_save()
        rep = save_probe.build_report(plain + extra, None, None, "x")
        self.assertIsNone(rep["plugin_index"])
        self.assertTrue(any("ambiguous" in x and "--plugin-index" in x for x in rep["warnings"]))
        self.assertTrue(all(i["role"] == "unknown" for i in rep["instances"]))
        # naming the index resolves it
        rep = save_probe.build_report(plain + extra, None, PREFIX, "x")
        self.assertEqual(rep["plugin_index"], "%02X" % PREFIX)
        self.assertEqual(rep["script_stage"]["value"], 30)

    def test_both_instances_pointing_at_the_mission_gives_no_roles(self):
        # both refs hit xx000800: no instance can be the keeper, so no candidate passes and nothing is labelled
        ids = [(PREFIX << 24) | 0x800, (PREFIX << 24) | 0x802, (PREFIX << 24) | 0x814]
        rep = save_probe.build_report(build_plain_save(ids=ids, keeper_ref=1), None, None, "x")
        self.assertTrue(all(i["role"] == "unknown" for i in rep["instances"]))
        self.assertIsNone(rep["script_stage"])
        self.assertTrue(any("--plugin-index" in x for x in rep["warnings"]))


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.save = os.path.join(self.tmp.name, "fixture.sfs")
        with open(self.save, "wb") as f:
            f.write(build_container(build_plain_save()))

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = save_probe.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_text_report_and_json(self):
        spots = os.path.join(self.tmp.name, "spots.json")
        with open(spots, "w") as f:
            json.dump({"Preston": list(SPOT)}, f)
        before = slurp(self.save)
        out_json = os.path.join(self.tmp.name, "out.json")
        code, out, err = self.run_main(self.save, "--spots", spots, "--json", out_json)
        self.assertEqual(code, 0, err)
        self.assertIn("applied=30", out)
        self.assertIn("script_stage: 30 (the last stage the mission script applied)", out)
        self.assertIn("m from spot", out)
        self.assertRegex(out, r"actor player .*\d m from spot Preston")
        self.assertNotRegex(out, r"m from Preston")
        self.assertEqual(json.loads(slurp(out_json))["plugin_index"], "%02X" % PREFIX)
        self.assertEqual(slurp(self.save), before)                 # the save is untouched
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["fixture.sfs", "out.json", "spots.json"])

    def test_spot_argument(self):
        code, out, _ = self.run_main(self.save, "--spot", "preston=%r,%r,%r" % SPOT)
        self.assertEqual(code, 0)
        self.assertIn("m from spot", out)

    def test_plugin_index_override(self):
        code, out, _ = self.run_main(self.save, "--plugin-index", "%02x" % PREFIX)
        self.assertEqual(code, 0)
        self.assertIn("applied=30", out)

    def test_truncated_file_exits_nonzero_with_a_message(self):
        cut = os.path.join(self.tmp.name, "cut.sfs")
        raw = slurp(self.save)
        with open(cut, "wb") as f:
            f.write(raw[:-20])
        code, out, err = self.run_main(cut)
        self.assertEqual(code, 1)
        self.assertIn("truncated", err)
        self.assertEqual(out, "")

    def test_not_a_save_and_missing_file_exit_nonzero(self):
        junk = os.path.join(self.tmp.name, "junk.sfs")
        with open(junk, "wb") as f:
            f.write(b"hello world" * 10)
        for path in (junk, os.path.join(self.tmp.name, "absent.sfs")):
            code, out, err = self.run_main(path)
            self.assertEqual(code, 1)
            self.assertIn("save_probe:", err)

    def test_json_may_not_overwrite_the_save(self):
        code, _, _ = self.run_main(self.save, "--json", self.save)
        self.assertEqual(code, 2)

    def test_name_is_left_out_unless_asked(self):
        code, out, _ = self.run_main(self.save)
        self.assertNotIn("Hero", out)
        code, out, _ = self.run_main(self.save, "--show-name")
        self.assertIn("player='Hero'", out)
        out_json = os.path.join(self.tmp.name, "o.json")
        self.run_main(self.save, "--json", out_json)
        self.assertNotIn("Hero", slurp(out_json).decode())

    def test_error_messages_carry_no_directory(self):
        code, _, err = self.run_main(os.path.join(self.tmp.name, "absent.sfs"))
        self.assertEqual(code, 1)
        self.assertNotIn(self.tmp.name, err)

    def test_hard_link_output_cannot_overwrite_the_save(self):
        link = os.path.join(self.tmp.name, "report.json")
        os.link(self.save, link)
        before = slurp(self.save)
        code, _, err = self.run_main(self.save, "--json", link)
        self.assertEqual(code, 2)
        self.assertEqual(slurp(self.save), before)
        self.assertEqual(slurp(link), before)

    def test_json_replaces_an_existing_report_without_writing_into_its_inode(self):
        old = os.path.join(self.tmp.name, "old.json")
        with open(old, "w") as f:
            f.write("old")
        keep = os.path.join(self.tmp.name, "keep.json")
        os.link(old, keep)                                  # a second name for the old report's inode
        code, _, _ = self.run_main(self.save, "--json", old)
        self.assertEqual(code, 0)
        self.assertEqual(slurp(keep), b"old")               # the old inode was not truncated
        self.assertIn("plugin_index", slurp(old).decode())
        self.assertEqual([n for n in os.listdir(self.tmp.name) if n.endswith(".tmp")], [])

    def test_truncated_plain_save_exits_nonzero(self):
        cut = os.path.join(self.tmp.name, "plain.sfs")
        with open(cut, "wb") as f:
            f.write(b"SFS_SAVEGAME")
        code, out, err = self.run_main(cut)
        self.assertEqual(code, 1)
        self.assertIn("truncated", err)
        self.assertEqual(out, "")

    def test_bad_spot_is_a_usage_error(self):
        code, _, _ = self.run_main(self.save, "--spot", "Preston=1,2")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
