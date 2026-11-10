"""Combined-core sidecar codec (sidecar.py): round trip, tamper detection, atomic write and orphans, in temp dirs."""
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import fixtures, model, sidecar, sim  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402


def world(seed=1, hours=0):
    ws = WorldState(seed=seed)
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_1))
    model.load_pack(ws, copy.deepcopy(fixtures.REGION_2))
    if hours:
        sim.run(ws, hours)
    return ws


class NameTests(unittest.TestCase):
    def test_name_is_safe_and_unique(self):
        for name in ("Save1_Player", "Quick Save", "../evil", "a/b\\c:d*e?f\"g<h>i|j", "ünïcödé", "x" * 300):
            fn = sidecar.sidecar_name(name)
            self.assertTrue(fn.endswith(sidecar.EXTENSION), fn)
            self.assertNotIn(os.sep, fn)
            self.assertNotIn("/", fn)
            self.assertRegex(fn, r"^[A-Za-z0-9_.-]+$")
            self.assertLessEqual(len(fn), sidecar.SAFE_NAME_MAX + 1 + sidecar.HASH_CHARS + len(sidecar.EXTENSION))
        self.assertNotEqual(sidecar.sidecar_name("a/b"), sidecar.sidecar_name("a_b"))     # the hash tells them apart
        self.assertNotEqual(sidecar.sidecar_name("y" * 300), sidecar.sidecar_name("y" * 301))
        self.assertEqual(sidecar.sidecar_name("Save 1"), sidecar.sidecar_name("Save 1"))

    def test_empty_name_refused(self):
        for bad in ("", None):
            with self.assertRaises(ValueError):
                sidecar.sidecar_name(bad)


class RoundTripTests(unittest.TestCase):
    def test_write_then_read_gives_the_same_state(self):
        for seed in (1, 4, 9):
            ws = world(seed, hours=30 * 24)
            with tempfile.TemporaryDirectory() as d:
                path = sidecar.write(d, f"Save{seed}", ws)
                self.assertTrue(os.path.isfile(path))
                self.assertEqual(os.listdir(d), [os.path.basename(path)])   # no temp file left behind
                back = sidecar.read(d, f"Save{seed}")
                self.assertEqual(back.to_json(), ws.to_json())
                sim.run(back, 10 * 24)
                sim.run(ws, 10 * 24)
                self.assertEqual(back.to_json(), ws.to_json())              # and it replays exactly

    def test_body_shape_and_determinism(self):
        ws = world(2, hours=24)
        text = sidecar.encode("Save2", ws)
        self.assertEqual(text, sidecar.encode("Save2", ws))
        body = json.loads(text)
        self.assertEqual(set(body), {"format", "schema", "save_name", "world_state", "sha256"})
        self.assertEqual((body["format"], body["schema"], body["save_name"]), (sidecar.FORMAT, sidecar.SCHEMA, "Save2"))
        self.assertEqual(body["world_state"]["schema"], model.SCHEMA_VERSION)
        self.assertEqual(body["sha256"], sidecar.checksum(ws.to_json()))
        with tempfile.TemporaryDirectory() as d:
            sidecar.write(d, "Save2", ws)
            with open(sidecar.sidecar_path(d, "Save2"), encoding="utf-8") as f:
                self.assertEqual(f.read(), text)

    def test_rewrite_replaces_the_old_sidecar(self):
        ws = world(3)
        with tempfile.TemporaryDirectory() as d:
            sidecar.write(d, "Save3", ws)
            sim.run(ws, 20 * 24)
            sidecar.write(d, "Save3", ws)
            self.assertEqual(len(os.listdir(d)), 1)
            self.assertEqual(sidecar.read(d, "Save3").hour, ws.hour)

    def test_missing_sidecar_is_file_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                sidecar.read(d, "Nope")


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.ws = world(5, hours=12 * 24)
        self.text = sidecar.encode("Save5", self.ws)
        self.body = json.loads(self.text)

    def rewrite(self, body):
        return json.dumps(body, sort_keys=True)

    def test_tampered_state_fails_checksum(self):
        body = copy.deepcopy(self.body)
        body["world_state"]["places"]["ruins"]["holder"] = "raiders"
        with self.assertRaisesRegex(ValueError, "checksum"):
            sidecar.decode(self.rewrite(body), "Save5")
        body = copy.deepcopy(self.body)
        body["world_state"]["reputation"]["raiders"]["fame"] += 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            sidecar.decode(self.rewrite(body))

    def test_wrong_format_schema_or_save_name(self):
        body = dict(self.body, format="other")
        with self.assertRaisesRegex(ValueError, "not a focc-sidecar"):
            sidecar.decode(self.rewrite(body))
        body = dict(self.body, schema=sidecar.SCHEMA + 1)
        with self.assertRaisesRegex(ValueError, "schema"):
            sidecar.decode(self.rewrite(body))
        with self.assertRaisesRegex(ValueError, "belongs to save"):
            sidecar.decode(self.text, "Save6")
        sidecar.decode(self.text)                                     # no name given: name not checked

    def test_truncated_or_foreign_text(self):
        with self.assertRaisesRegex(ValueError, "not JSON"):
            sidecar.decode(self.text[:-20])
        with self.assertRaisesRegex(ValueError, "not a focc-sidecar"):
            sidecar.decode("[1, 2, 3]")
        body = {k: v for k, v in self.body.items() if k != "sha256"}
        with self.assertRaisesRegex(ValueError, "lacks"):
            sidecar.decode(self.rewrite(body))

    def test_stale_world_schema_is_refused_after_checksum(self):
        body = copy.deepcopy(self.body)
        body["world_state"]["schema"] = 99
        body["sha256"] = sidecar.checksum(json.dumps(body["world_state"], sort_keys=True))
        with self.assertRaisesRegex(ValueError, "world-state schema"):
            sidecar.decode(self.rewrite(body))

    def test_tamper_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            path = sidecar.write(d, "Save5", self.ws)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace('"hour": 288', '"hour": 289'))
            with self.assertRaisesRegex(ValueError, "checksum"):
                sidecar.read(d, "Save5")


class AtomicTests(unittest.TestCase):
    def test_failed_write_keeps_the_old_file_and_no_temp(self):
        ws = world(7)
        with tempfile.TemporaryDirectory() as d:
            path = sidecar.write(d, "Save7", ws)
            with open(path, encoding="utf-8") as f:
                before = f.read()
            sim.run(ws, 24)
            with mock.patch.object(sidecar, "encode", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    sidecar.write(d, "Save7", ws)
            self.assertEqual(os.listdir(d), [os.path.basename(path)])
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), before)

    def test_write_uses_replace_not_in_place(self):
        ws = world(8)
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(sidecar.os, "replace", wraps=os.replace) as rep:
                sidecar.write(d, "Save8", ws)
            self.assertEqual(rep.call_count, 1)
            src, dst = rep.call_args[0]
            self.assertEqual(os.path.dirname(src), d)                 # temp file in the same directory
            self.assertEqual(dst, sidecar.sidecar_path(d, "Save8"))


class OrphanTests(unittest.TestCase):
    def test_orphans_listed_never_deleted(self):
        ws = world(9)
        with tempfile.TemporaryDirectory() as d:
            paths = {n: sidecar.write(d, n, ws) for n in ("Save1", "Save2", "Quick Save")}
            with open(os.path.join(d, "notes.txt"), "w") as f:
                f.write("not a sidecar")
            self.assertEqual(sidecar.orphans(d, ["Save1", "Save2", "Quick Save"]), [])
            got = sidecar.orphans(d, ["Save2"])
            self.assertEqual(got, sorted([paths["Save1"], paths["Quick Save"]]))
            self.assertEqual(sidecar.orphans(d, []), sorted(paths.values()))
            self.assertEqual(sorted(os.listdir(d)),                      # nothing removed
                             sorted([os.path.basename(p) for p in paths.values()] + ["notes.txt"]))
            self.assertEqual(sidecar.orphans(d, ["Save1", "Save2", "Quick Save", "Never Written"]), [])

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sidecar.orphans(d, ["Save1"]), [])


class CharacterNameTests(unittest.TestCase):
    def test_golden_name(self):
        self.assertEqual(sidecar.character_sidecar_name("Save 1", "character_A-01"),
                         "Save_1-01107a54-f05d3f7ca8396b6d.focc")

    def test_safe_names_and_id_boundaries(self):
        for name in ("../evil", "...", "ünïcödé", "x" * 300):
            for cid in ("a", "A_0-9", "x" * 64):
                with self.subTest(name=name, cid=cid):
                    filename = sidecar.character_sidecar_name(name, cid)
                    self.assertRegex(filename, r"^[A-Za-z0-9_.-]+$")
                    self.assertLessEqual(len(filename), 111)
                    self.assertEqual(filename, sidecar.character_sidecar_name(name, cid))
        self.assertNotEqual(sidecar.character_sidecar_name("a/b", "a"),
                            sidecar.character_sidecar_name("a_b", "a"))
        self.assertNotEqual(sidecar.character_sidecar_name("x" * 300, "a"),
                            sidecar.character_sidecar_name("x" * 301, "a"))

    def test_invalid_character_ids(self):
        for cid in ("", "x" * 65, ".", "/", " ", "é", None, 7, b"abc", "abc\n"):
            with self.subTest(cid=cid):
                with self.assertRaises(ValueError):
                    sidecar.validate_character_id(cid)
                with self.assertRaises(ValueError):
                    sidecar.character_sidecar_name("Save", cid)
                with self.assertRaises(ValueError):
                    sidecar.character_encode("Save", world(), cid)

    def test_save_name_validated_before_character_id(self):
        for save_name in ("", None, 7):
            with self.subTest(save_name=save_name):
                with self.assertRaisesRegex(ValueError, "save name"):
                    sidecar.character_sidecar_name(save_name, ".")


class CharacterVerifyTests(unittest.TestCase):
    def setUp(self):
        self.ws = world(5, hours=24)
        self.text = sidecar.character_encode("Save5", self.ws, "character_5")
        self.body = json.loads(self.text)

    def decode(self, body):
        return sidecar.character_decode(json.dumps(body, sort_keys=True), "Save5", "character_5")

    def test_character_envelope_is_deterministic(self):
        self.assertEqual(self.text, sidecar.character_encode("Save5", self.ws, "character_5"))
        self.assertEqual(self.text, json.dumps(self.body, sort_keys=True))
        self.assertEqual(set(self.body), {"character_id", "format", "save_name", "schema", "sha256", "world_state"})
        self.assertEqual((self.body["character_id"], self.body["format"], self.body["save_name"], self.body["schema"]),
                         ("character_5", sidecar.FORMAT, "Save5", 2))
        self.assertEqual(self.body["sha256"], sidecar.checksum(self.ws.to_json()))
        self.assertEqual(sidecar.character_decode(self.text, "Save5", "character_5").to_json(), self.ws.to_json())

    def test_legacy_classified_before_checksum_and_identity(self):
        legacy = json.loads(sidecar.encode("OtherSave", self.ws))
        for checksum in (legacy["sha256"], "wrong"):
            with self.subTest(checksum=checksum):
                body = dict(legacy, sha256=checksum)
                with self.assertRaisesRegex(sidecar.LegacySidecarError,
                                            "schema 1 has no character id; refused, not adopted"):
                    self.decode(body)

    def test_unknown_schema_is_not_legacy(self):
        for schema in (0, 3, 99, None, "2"):
            with self.subTest(schema=schema):
                with self.assertRaisesRegex(ValueError, "unknown sidecar schema") as caught:
                    self.decode(dict(self.body, schema=schema, sha256="wrong"))
                self.assertNotIsInstance(caught.exception, sidecar.LegacySidecarError)

    def test_edited_character_id_with_valid_state_checksum(self):
        with self.assertRaises(ValueError) as caught:
            self.decode(dict(self.body, character_id="other_character"))
        self.assertIn("other_character", str(caught.exception))
        self.assertIn("character_5", str(caught.exception))

    def test_edited_save_name_with_valid_state_checksum(self):
        with self.assertRaises(ValueError) as caught:
            self.decode(dict(self.body, save_name="OtherSave"))
        self.assertIn("OtherSave", str(caught.exception))
        self.assertIn("Save5", str(caught.exception))

    def test_missing_fields_and_checksum_have_distinct_errors(self):
        for field in ("world_state", "sha256"):
            with self.subTest(field=field):
                body = {k: v for k, v in self.body.items() if k != field}
                with self.assertRaisesRegex(ValueError, "^sidecar lacks world_state or sha256$"):
                    self.decode(body)
        body = copy.deepcopy(self.body)
        body["world_state"]["hour"] += 1
        with self.assertRaisesRegex(ValueError, "^sidecar checksum mismatch: body edited or truncated$"):
            self.decode(body)

    def test_invalid_json_or_format_is_not_legacy(self):
        for text, message in ((self.text[:-20], "not JSON"), ("[]", "not a focc-sidecar"),
                              (json.dumps(dict(self.body, format="other", schema=1)), "not a focc-sidecar")):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, message) as caught:
                    sidecar.character_decode(text, "Save5", "character_5")
                self.assertNotIsInstance(caught.exception, sidecar.LegacySidecarError)

    def test_stale_world_schema_refused_after_checksum(self):
        body = copy.deepcopy(self.body)
        body["world_state"]["schema"] = 99
        body["sha256"] = sidecar.checksum(json.dumps(body["world_state"], sort_keys=True))
        with self.assertRaisesRegex(ValueError, "world-state schema"):
            self.decode(body)


class CharacterFileTests(unittest.TestCase):
    def bytes_at(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_same_save_two_characters_survive_and_rewrite_independently(self):
        first, second = world(1, hours=24), world(2, hours=48)
        with tempfile.TemporaryDirectory() as d:
            first_path = sidecar.character_write(d, "Quicksave", first, "first")
            first_bytes = self.bytes_at(first_path)
            second_path = sidecar.character_write(d, "Quicksave", second, "second")
            self.assertNotEqual(first_path, second_path)
            self.assertEqual(len(os.listdir(d)), 2)
            self.assertEqual(self.bytes_at(first_path), first_bytes)
            second_bytes = self.bytes_at(second_path)
            self.assertEqual(sidecar.character_read(d, "Quicksave", "first").to_json(), first.to_json())
            self.assertEqual(sidecar.character_read(d, "Quicksave", "second").to_json(), second.to_json())
            sim.run(first, 24)
            self.assertEqual(sidecar.character_write(d, "Quicksave", first, "first"), first_path)
            self.assertEqual(sidecar.character_read(d, "Quicksave", "first").to_json(), first.to_json())
            self.assertEqual(self.bytes_at(second_path), second_bytes)
            self.assertEqual(len(os.listdir(d)), 2)

    def test_legacy_only_refused_with_path_and_untouched_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            legacy_path = sidecar.write(d, "Save", world())
            for data in (self.bytes_at(legacy_path), b"not JSON\xff"):
                with self.subTest(data=data):
                    with open(legacy_path, "wb") as f:
                        f.write(data)
                    with self.assertRaises(sidecar.LegacySidecarError) as caught:
                        sidecar.character_read(d, "Save", "first")
                    self.assertIn(legacy_path, str(caught.exception))
                    self.assertEqual(self.bytes_at(legacy_path), data)
                    self.assertEqual(os.listdir(d), [os.path.basename(legacy_path)])

    def test_both_files_read_character_and_report_legacy_orphan(self):
        with tempfile.TemporaryDirectory() as d:
            ws = world(2, hours=24)
            legacy_path = sidecar.write(d, "Save", world(1))
            character_path = sidecar.character_write(d, "Save", ws, "second")
            before = self.bytes_at(legacy_path)
            self.assertEqual(sidecar.character_read(d, "Save", "second").to_json(), ws.to_json())
            self.assertEqual(self.bytes_at(legacy_path), before)
            self.assertEqual(sidecar.character_orphans(d, {("Save", "second")}), [legacy_path])
            self.assertEqual(sidecar.orphans(d, ["Save"]), [character_path])  # schema-1 behavior stays frozen

    def test_character_write_never_reads_or_moves_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            legacy_path = sidecar.write(d, "Save", world(1))
            before = self.bytes_at(legacy_path)
            with mock.patch("builtins.open", side_effect=AssertionError("must not read legacy")):
                character_path = sidecar.character_write(d, "Save", world(2), "second")
            self.assertEqual(self.bytes_at(legacy_path), before)
            self.assertEqual(sorted(os.listdir(d)),
                             sorted([os.path.basename(legacy_path), os.path.basename(character_path)]))

    def test_character_orphans_keep_legacy_unknown_pairs_and_non_sidecars(self):
        with tempfile.TemporaryDirectory() as d:
            legacy_path = sidecar.write(d, "Save", world())
            known = sidecar.character_write(d, "Save", world(), "first")
            unknown = sidecar.character_write(d, "Save", world(2), "second")
            notes = os.path.join(d, "notes.txt")
            with open(notes, "w") as f:
                f.write("not a sidecar")
            before = {p: self.bytes_at(p) for p in (legacy_path, known, unknown, notes)}
            self.assertEqual(sidecar.character_orphans(d, {("Save", "first")}), sorted([legacy_path, unknown]))
            self.assertEqual(sidecar.character_orphans(d, set()), sorted([legacy_path, known, unknown]))
            self.assertEqual(sorted(os.listdir(d)), sorted(os.path.basename(p) for p in before))
            for path, data in before.items():
                self.assertEqual(self.bytes_at(path), data)

    def test_neither_file_is_file_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError) as caught:
                sidecar.character_read(d, "Save", "first")
            self.assertEqual(caught.exception.filename, sidecar.character_sidecar_path(d, "Save", "first"))

    def test_corrupt_character_file_does_not_fall_back_to_legacy(self):
        with tempfile.TemporaryDirectory() as d:
            legacy_path = sidecar.write(d, "Save", world())
            before = self.bytes_at(legacy_path)
            path = sidecar.character_write(d, "Save", world(2), "second")
            with open(path, "w") as f:
                f.write("{")
            with self.assertRaisesRegex(ValueError, "not JSON"):
                sidecar.character_read(d, "Save", "second")
            self.assertEqual(self.bytes_at(legacy_path), before)

    def test_failed_atomic_replace_keeps_previous_file_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as d:
            path = sidecar.character_write(d, "Save", world(), "first")
            before = self.bytes_at(path)
            with mock.patch.object(sidecar.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    sidecar.character_write(d, "Save", world(2), "first")
            self.assertEqual(self.bytes_at(path), before)
            self.assertEqual(os.listdir(d), [os.path.basename(path)])


if __name__ == "__main__":
    unittest.main()
