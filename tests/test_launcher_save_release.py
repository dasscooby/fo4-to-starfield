"""Opaque synthetic saves/state and masters; no game formats or live profile used."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import save_release as sr  # noqa: E402


class SaveReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.game = self.root / "game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        self.save = self.root / "player-save.bin"
        self.save.write_bytes(b"opaque synthetic save")
        self.state = self.root / "runtime"
        (self.state / "sidecars").mkdir(parents=True)
        (self.state / "sidecars/state.focc").write_bytes(b"opaque synthetic sidecar")
        for name in ("Starfield.esm", "FO4Port.esm"):
            (self.data / name).write_bytes(("synthetic master " + name).encode())
        self.release = {"schema": 2, "implicit_loaders": {"game": None, "my_games": None}, "release_id": "release-A",
                        "masters": [dict(sr.identity(self.data / n), name=n)
                                    for n in ("Starfield.esm", "FO4Port.esm")],
                        "state_layouts": {"focc": {"format": "focc-sidecar", "envelope_schema": 1,
                                                   "payload_schema": "P1-stub"}}}
        self.binding = sr.snapshot_binding(self.release, self.save, self.state,
                                           {"sidecars/state.focc": "focc"})
        self.release_path = self.root / "release.json"
        self.binding_path = self.root / "binding.json"
        self.publish_fixture()

    def publish_fixture(self):
        self.release_path.write_text(json.dumps(self.release), encoding="utf-8")
        self.binding_path.write_text(json.dumps(self.binding), encoding="utf-8")

    def check(self, release=None, binding=None):
        return sr.check(self.release if release is None else release,
                        self.binding if binding is None else binding, self.save, self.game, self.state)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    def cli(self):
        return subprocess.run([sys.executable, "-I", str(ROOT / "scripts/launcher.py"), "check-save-release",
                               "--release", str(self.release_path), "--binding", str(self.binding_path),
                               "--save", str(self.save), "--starfield", str(self.game),
                               "--state-dir", str(self.state)], capture_output=True, text=True)

    def test_compatible_and_patch_release_keep_original_release_binding(self):
        before = copy.deepcopy(self.binding)
        self.assertEqual(self.check(), [])
        self.release["release_id"] = "release-B"
        self.assertEqual(self.check(), [])
        self.assertEqual(sr.compatibility(self.release), sr.compatibility(self.binding["release"]))
        self.assertEqual(self.binding, before)
        self.assertEqual(self.binding["release"]["release_id"], "release-A")

    def test_changed_master_order_membership_and_declared_identity_refuse(self):
        for change in (lambda r: r["masters"].reverse(), lambda r: r["masters"].pop(),
                       lambda r: r["masters"][0].update(sha256="0" * 64)):
            release = copy.deepcopy(self.release)
            change(release)
            self.assertTrue(any("master identities/order" in p for p in self.check(release=release)))

    def test_changed_implicit_configuration_refuses_old_binding(self):
        release = copy.deepcopy(self.release)
        release["implicit_loaders"]["game"] = {"size": 1, "sha256": "0" * 64}
        before = self.snapshot()
        self.assertIn("required implicit loader configuration changed", self.check(release=release))
        self.assertNotEqual(sr.compatibility(release), sr.compatibility(self.release))
        self.assertEqual(before, self.snapshot())

    def test_changed_actual_master_bytes_refuse_even_with_same_declaration(self):
        (self.data / "FO4Port.esm").write_bytes(b"changed actual master")
        self.assertTrue(any("installed bytes differ" in p for p in self.check()))

    def test_missing_installed_master_refuses(self):
        (self.data / "FO4Port.esm").unlink()
        self.assertTrue(any("missing or ambiguous" in p for p in self.check()))

    def test_changed_envelope_and_payload_are_independent_refusals(self):
        for key, value in (("envelope_schema", 2), ("payload_schema", "world-state-v2"), ("format", "other")):
            release = copy.deepcopy(self.release)
            release["state_layouts"]["focc"][key] = value
            self.assertTrue(any("envelope/payload layout" in p for p in self.check(release=release)))

    def test_changed_save_or_state_bytes_refuse_and_never_rebind(self):
        for path in (self.save, self.state / "sidecars/state.focc"):
            original = path.read_bytes()
            path.write_bytes(b"changed")
            before = self.snapshot()
            self.assertTrue(self.check())
            self.assertEqual(self.snapshot(), before)
            path.write_bytes(original)

    def test_missing_save_or_state_refuses(self):
        for path in (self.save, self.state / "sidecars/state.focc"):
            original = path.read_bytes()
            path.unlink()
            self.assertTrue(self.check())
            path.write_bytes(original)

    def test_binding_to_another_save_name_is_refused(self):
        binding = copy.deepcopy(self.binding)
        binding["save_name"] = "other-save.bin"
        self.assertTrue(any("save name or bytes" in p for p in self.check(binding=binding)))

    def test_missing_and_corrupt_bindings_do_not_create_any_files(self):
        for raw in (None, b"{", b"[]", b"null", b"\xff", b'{"schema": 1, "schema": 1}'):
            if raw is None:
                self.binding_path.unlink(missing_ok=True)
            else:
                self.binding_path.write_bytes(raw)
            before = self.snapshot()
            self.assertTrue(sr.check_files(self.release_path, self.binding_path, self.save, self.game, self.state))
            self.assertEqual(self.snapshot(), before)

    def test_unknown_or_malformed_declarations_fail_closed(self):
        for change in (lambda r: r.update(schema=999), lambda r: r.update(schema=True),
                       lambda r: r.update(extra="unknown"), lambda r: r.update(masters=[]),
                       lambda r: r["masters"].append(dict(r["masters"][0], name="STARFIELD.ESM")),
                       lambda r: r["masters"][0].update(size=True),
                       lambda r: r["masters"][0].update(name="../escape.esm"),
                       lambda r: r["state_layouts"]["focc"].update(envelope_schema=True)):
            release = copy.deepcopy(self.release)
            change(release)
            self.assertTrue(self.check(release=release))

    def test_state_components_must_be_covered_without_foreign_components(self):
        for states in ({}, {"sidecars/state.focc": dict(self.binding["state_files"]["sidecars/state.focc"],
                                                       component="other")}):
            binding = dict(self.binding, state_files=states)
            self.assertTrue(any("cover" in p for p in self.check(binding=binding)))
        with self.assertRaises(sr.BindingError):
            sr.snapshot_binding(self.release, self.save, self.state)

    def test_state_path_escape_and_case_collision_refuse(self):
        pin = self.binding["state_files"]["sidecars/state.focc"]
        for relative in ("../outside", "/outside", "C:/outside", "sidecars\\state.focc", "sidecars//state.focc"):
            self.assertTrue(self.check(binding=dict(self.binding, state_files={relative: pin})))
        states = {"sidecars/state.focc": pin, "SIDECARS/STATE.FOCC": pin}
        self.assertTrue(any("duplicate state path" in p for p in self.check(binding=dict(self.binding, state_files=states))))

    def test_linked_state_is_refused(self):
        sidecar = self.state / "sidecars/state.focc"
        sidecar.unlink()
        target = self.root / "foreign"
        target.write_bytes(b"foreign")
        try:
            sidecar.symlink_to(target)
        except OSError as error:
            self.skipTest(f"symlink unavailable: {error}")
        self.assertTrue(any("link" in p for p in self.check()))

    def test_changed_file_during_hash_is_refused(self):
        real_stat = Path.stat
        def changed(path, *args, **kwargs):
            stat = real_stat(path, *args, **kwargs)
            if path == self.save:
                return mock.Mock(st_size=stat.st_size + 1, st_mtime_ns=stat.st_mtime_ns, st_ino=stat.st_ino)
            return stat
        with mock.patch.object(Path, "stat", changed):
            self.assertTrue(any("changed while reading" in p for p in self.check()))

    def test_bounded_metadata_and_nonfinite_numbers_refuse(self):
        for raw in (b" " * (sr.MAX_METADATA_BYTES + 1), b'{"x": NaN}'):
            self.binding_path.write_bytes(raw)
            self.assertTrue(sr.check_files(self.release_path, self.binding_path, self.save, self.game, self.state))

    def test_excessive_metadata_nesting_refuses_without_traceback(self):
        self.binding_path.write_bytes(b"[" * 10000 + b"]" * 10000)
        before = self.snapshot()
        result = self.cli()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_unknown_and_malformed_binding_fields_refuse(self):
        for change in (lambda b: b.update(schema=2), lambda b: b.update(schema=True),
                       lambda b: b.update(save_identity=[]), lambda b: b.update(extra="unknown"),
                       lambda b: b.update(state_files=[])):
            binding = copy.deepcopy(self.binding)
            change(binding)
            self.assertTrue(self.check(binding=binding))

    def test_state_free_release_needs_no_state_files(self):
        self.release["state_layouts"] = {}
        self.binding = sr.snapshot_binding(self.release, self.save, self.state)
        self.assertEqual(self.check(), [])

    def test_cli_positive_and_negative_are_read_only(self):
        before = self.snapshot()
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("compatible", result.stdout)
        self.assertEqual(self.snapshot(), before)
        self.binding["release"]["state_layouts"]["focc"]["payload_schema"] = "older-layout"
        self.publish_fixture()
        before = self.snapshot()
        result = self.cli()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("layout changed", result.stdout)
        self.assertEqual(self.snapshot(), before)

    def test_unicode_save_name_and_state_path(self):
        self.save = self.save.rename(self.root / "save-雪.bin")
        sidecar = self.state / "sidecars/state.focc"
        sidecar.rename(self.state / "sidecars/état.focc")
        self.binding = sr.snapshot_binding(self.release, self.save, self.state, {"sidecars/état.focc": "focc"})
        self.assertEqual(self.check(), [])
