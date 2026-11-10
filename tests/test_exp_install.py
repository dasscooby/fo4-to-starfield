"""Experiment deployment failures use synthetic files, never a live game install."""
import json
import hashlib
import os
from pathlib import Path
import sys
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ba2_fixture import general_archive, archive_from_tree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "game"))
import exp_install as exp  # noqa: E402


class ExperimentRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.staging = self.root / "staging"
        self.data = self.root / "game" / "Data"
        self.local = self.root / "local"
        self.terrain = Path("Terrain") / "nested" / "World.btd"
        self.data.mkdir(parents=True)
        (self.staging / "Data" / self.terrain.parent).mkdir(parents=True)
        (self.staging / "Experiment.esm").write_bytes(b"synthetic plugin")
        (self.staging / "Data" / self.terrain).write_bytes(b"synthetic terrain")
        (self.local / "Starfield").mkdir(parents=True)
        self.plugins = self.local / "Starfield" / "Plugins.txt"
        self.original = b"\xef\xbb\xbf# keep this comment\r\n*FO4Port.esm\r\n"
        self.plugins.write_bytes(self.original)
        environment = patch.dict(os.environ, {"LOCALAPPDATA": str(self.local)})
        environment.start()
        self.addCleanup(environment.stop)
        self.args = SimpleNamespace(starfield=str(self.data.parent), exp_dir=str(self.staging), plugins="")

    def archive_builder(self, payload=None):
        tool = self.data.parent / "Tools" / "Archive2" / "Archive2.exe"
        tool.parent.mkdir(parents=True, exist_ok=True)
        tool.write_bytes(b"synthetic tool; never executed")
        self.args.pack = True

        def build(command, **kwargs):
            self.assertEqual(Path(kwargs["cwd"]), self.staging / "Data")
            self.assertIn("-format=General", command)
            output = next(arg[len("-create="):] for arg in command if arg.startswith("-create="))
            Path(output).write_bytes(payload if payload is not None else archive_from_tree(self.staging / "Data"))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        return build

    def assert_rolled_back(self):
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def make_package(self):
        self.args.package = str(self.root / "package")
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.main(["package", "--exp-dir", self.args.exp_dir, "--starfield", self.args.starfield,
                      "--package", self.args.package, "--plugins", self.args.plugins])
            process.assert_called_once()
        self.args.pack = False
        return Path(self.args.package)

    def test_package_install_matches_every_pack_receipt_field_and_uninstalls_exactly(self):
        self.args.plugins = "Experiment.esm,Experiment_Mars.esm"
        (self.staging / "Experiment_Mars.esm").write_bytes(b"synthetic registration plugin")
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build):
            exp.install(self.args)
        packed = json.loads((self.data / exp.RECORD).read_bytes())
        exp.uninstall(self.args)
        package = self.make_package()
        existing = self.data / "Owner.txt"
        existing.write_bytes(b"owner")
        # --package implies packed install even without --pack, and invokes no packing tool.
        with patch.object(exp.subprocess, "run", side_effect=AssertionError("must reuse package")):
            exp.main(["install", "--exp-dir", self.args.exp_dir, "--starfield", self.args.starfield,
                      "--package", self.args.package, "--plugins", self.args.plugins])
            receipt = (self.data / exp.RECORD).read_bytes()
            actual = json.loads(receipt)
            self.assertEqual(actual.pop("package_sha256"),
                             hashlib.sha256((package / exp.PACKAGE_MANIFEST).read_bytes()).hexdigest())
            self.assertEqual(actual, packed)
            exp.install(self.args)
            self.assertEqual((self.data / exp.RECORD).read_bytes(), receipt)
        exp.uninstall(self.args)
        self.assertEqual(list(self.data.iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b"owner")
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertEqual(set(p.name for p in package.iterdir()),
                         {exp.PACKAGE_MANIFEST, "Experiment - Main.ba2"})

    def test_package_manifest_binds_paths_sizes_hashes_plugins_and_policy(self):
        package = self.make_package()
        manifest = json.loads((package / exp.PACKAGE_MANIFEST).read_bytes())
        self.assertEqual(manifest["schema"], 1)
        self.assertEqual(manifest["packing_policy"], "general-stored-verified-v2")
        self.assertEqual(manifest["plugins"], [{"path": "Experiment.esm", "size": 16,
                                              "sha256": exp.digest(self.staging / "Experiment.esm")}])
        self.assertEqual(manifest["members"], [{"path": self.terrain.as_posix(), "size": 17,
                                              "sha256": exp.digest(self.staging / "Data" / self.terrain)}])
        self.assertEqual(manifest["archive"], {"path": "Experiment - Main.ba2",
                                              **exp.deployment.artifact_identity(package / "Experiment - Main.ba2")})

    def test_package_rejects_changed_member_or_plugin_before_data_publication(self):
        self.make_package()
        for path in (self.staging / "Data" / self.terrain, self.staging / "Experiment.esm"):
            with self.subTest(path=path):
                original = path.read_bytes()
                # Same size and timestamps cannot make changed content acceptable.
                times = path.stat()
                path.write_bytes(b"x" * len(original))
                os.utime(path, ns=(times.st_atime_ns, times.st_mtime_ns))
                with self.assertRaisesRegex(SystemExit, "package validation"):
                    exp.install(self.args)
                self.assert_rolled_back()
                path.write_bytes(original)

    def test_package_rejects_added_or_removed_members_before_data_publication(self):
        self.make_package()
        member = self.staging / "Data" / self.terrain
        original = member.read_bytes()
        member.unlink()
        with self.assertRaisesRegex(SystemExit, "package validation"):
            exp.install(self.args)
        self.assert_rolled_back()
        member.write_bytes(original)
        (member.parent / "extra.btd").write_bytes(b"extra")
        with self.assertRaisesRegex(SystemExit, "package validation"):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_package_rejects_truncated_archive_before_data_publication(self):
        package = self.make_package()
        archive = package / "Experiment - Main.ba2"
        archive.write_bytes(archive.read_bytes()[:-1])
        with self.assertRaisesRegex(SystemExit, "package validation"):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_manifest_from_another_staged_set_is_refused_before_data_publication(self):
        package = self.make_package()
        member = self.staging / "Data" / self.terrain
        original = member.read_bytes()
        member.write_bytes(b"another set")
        self.args.package = str(self.root / "other-package")
        with patch.object(exp.subprocess, "run", side_effect=self.archive_builder()):
            exp.package(self.args)
        member.write_bytes(original)
        (package / exp.PACKAGE_MANIFEST).write_bytes((Path(self.args.package) / exp.PACKAGE_MANIFEST).read_bytes())
        self.args.package = str(package)
        with self.assertRaisesRegex(SystemExit, "package validation"):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_package_checks_actual_archive_members_even_with_matching_archive_digest(self):
        package = self.make_package()
        archive = package / "Experiment - Main.ba2"
        archive.write_bytes(general_archive({self.terrain.as_posix(): b"wrong member"}))
        path = package / exp.PACKAGE_MANIFEST
        manifest = json.loads(path.read_bytes())
        manifest["archive"].update(exp.deployment.artifact_identity(archive))
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(SystemExit, "archive resource differs"):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_package_rejects_policy_size_and_path_tampering(self):
        package = self.make_package()
        path = package / exp.PACKAGE_MANIFEST
        original = path.read_bytes()
        for key in ("policy", "size", "path"):
            with self.subTest(key=key):
                manifest = json.loads(original)
                if key == "policy":
                    manifest["packing_policy"] = "unverified"
                elif key == "size":
                    manifest["members"][0]["size"] += 1
                else:
                    manifest["archive"]["path"] = "../Experiment - Main.ba2"
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(SystemExit, "package validation"):
                    exp.install(self.args)
                self.assert_rolled_back()

    def test_package_rejects_a_different_selected_plugin_list(self):
        self.args.plugins = "Experiment.esm,Other.esm"
        (self.staging / "Other.esm").write_bytes(b"other plugin")
        self.make_package()
        for selection in ("Other.esm,Experiment.esm", "Experiment.esm"):
            with self.subTest(selection=selection):
                self.args.plugins = selection
                with self.assertRaisesRegex(SystemExit, "package validation"):
                    exp.install(self.args)
                self.assert_rolled_back()

    def test_package_relaunch_revalidates_archive_before_already_installed(self):
        package = self.make_package()
        exp.install(self.args)
        before = {p.name: p.read_bytes() for p in self.data.iterdir()}
        (package / "Experiment - Main.ba2").write_bytes(b"changed package")
        with self.assertRaisesRegex(SystemExit, "package validation"):
            exp.install(self.args)
        self.assertEqual({p.name: p.read_bytes() for p in self.data.iterdir()}, before)

    def test_package_respects_no_overwrite_and_held_off_refusal(self):
        self.make_package()
        existing = self.data / "Experiment - Main.ba2"
        existing.write_bytes(b"owner archive")
        with self.assertRaisesRegex(SystemExit, "overwrite"):
            exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b"owner archive")
        existing.unlink()
        toggle = self.data / exp.TOGGLE
        toggle.write_text(json.dumps({"off": ["Experiment.esm"]}))
        with self.assertRaisesRegex(SystemExit, "held off"):
            exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [toggle])
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_package_archive_changed_during_copy_rolls_back(self):
        package = self.make_package()
        real_copy = exp.shutil.copyfile

        def copy(source, target):
            if Path(source) == package / "Experiment - Main.ba2":
                Path(source).write_bytes(b"changed during copy")
            return real_copy(source, target)

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_package_creation_refuses_existing_or_nested_output(self):
        package = self.make_package()
        before = {p.name: p.read_bytes() for p in package.iterdir()}
        with self.assertRaisesRegex(SystemExit, "overwrite"):
            exp.package(self.args)
        self.assertEqual({p.name: p.read_bytes() for p in package.iterdir()}, before)
        self.args.package = str(self.staging / "package")
        with self.assertRaisesRegex(SystemExit, "separate"):
            exp.package(self.args)
        self.assertFalse(Path(self.args.package).exists())

    def test_package_can_be_created_on_a_separate_drive(self):
        self.args.package = str(self.root / "package")
        with patch.object(exp.os.path, "commonpath", side_effect=ValueError("Paths don't have the same drive")), \
                patch.object(exp.subprocess, "run", side_effect=self.archive_builder()):
            exp.package(self.args)
        self.assertTrue((Path(self.args.package) / exp.PACKAGE_MANIFEST).is_file())

    def test_failed_package_build_never_publishes_a_manifest(self):
        self.args.package = str(self.root / "package")
        with patch.object(exp.subprocess, "run", side_effect=self.archive_builder(general_archive({}))):
            with self.assertRaisesRegex(SystemExit, "coverage"):
                exp.package(self.args)
        self.assertFalse((Path(self.args.package) / exp.PACKAGE_MANIFEST).exists())
        self.assert_rolled_back()

    def test_successful_install_is_idempotent_and_uninstall_preserves_existing_files(self):
        existing = self.data / "Owner.txt"
        existing.write_bytes(b"owner file")
        exp.install(self.args)
        record = self.data / exp.RECORD
        installed = record.read_bytes()
        self.assertTrue(json.loads(installed)["complete"])
        self.assertEqual((self.data / "Experiment.esm").read_bytes(), b"synthetic plugin")
        self.assertEqual((self.data / self.terrain).read_bytes(), b"synthetic terrain")
        self.assertEqual(self.plugins.read_bytes(), self.original + b"*Experiment.esm\r\n")
        exp.install(self.args)
        self.assertEqual(record.read_bytes(), installed)
        exp.uninstall(self.args)
        self.assertEqual(list(self.data.iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b"owner file")
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_packed_install_publishes_plugins_and_archive_only(self):
        build = self.archive_builder()
        self.args.plugins = "Experiment.esm,Experiment_Mars.esm"
        (self.staging / "Experiment_Mars.esm").write_bytes(b"synthetic registration plugin")
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
            process.assert_called_once()
            exp.install(self.args)
            process.assert_called_once()
        self.assertFalse((self.data / "Terrain").exists())
        self.assertEqual((self.data / "Experiment - Main.ba2").read_bytes(),
                         archive_from_tree(self.staging / "Data"))
        self.assertEqual((self.data / "Experiment_Mars.esm").read_bytes(), b"synthetic registration plugin")
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_terrain_archive_is_stored_uncompressed(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
        self.assertIn("-compression=None", process.call_args.args[0])
        self.assertNotIn("-compression=Default", process.call_args.args[0])

    def test_packed_archive_missing_the_pinned_terrain_cannot_install(self):
        build = self.archive_builder(general_archive({}))
        with patch.object(exp.subprocess, "run", side_effect=build):
            with self.assertRaisesRegex(SystemExit, "archive"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_packed_archive_with_changed_terrain_bytes_cannot_install(self):
        build = self.archive_builder(general_archive({self.terrain.as_posix(): b"wrong terrain"}))
        with patch.object(exp.subprocess, "run", side_effect=build):
            with self.assertRaisesRegex(SystemExit, "archive"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_compressed_terrain_output_cannot_install_despite_the_requested_flag(self):
        build = self.archive_builder(general_archive({self.terrain.as_posix(): b"synthetic terrain"}, compressed=True))
        with patch.object(exp.subprocess, "run", side_effect=build):
            with self.assertRaisesRegex(SystemExit, "archive"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_overstated_archive_name_length_cannot_install(self):
        payload = bytearray(general_archive({self.terrain.as_posix(): b"synthetic terrain"}))
        name_offset, = struct.unpack_from("<Q", payload, 16)
        struct.pack_into("<H", payload, name_offset, 65535)
        build = self.archive_builder(payload)
        with patch.object(exp.subprocess, "run", side_effect=build):
            with self.assertRaisesRegex(SystemExit, "name length"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_packing_keeps_staging_read_only_and_cleans_temporary_output(self):
        build = self.archive_builder()
        old_archive = self.staging / "Experiment - Main.ba2"
        old_archive.write_bytes(b"another track's previous archive")
        before = {p.relative_to(self.staging): p.read_bytes()
                  for p in self.staging.rglob("*") if p.is_file()}
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
        output = Path(next(arg[len("-create="):] for arg in process.call_args.args[0]
                           if arg.startswith("-create=")))
        self.assertFalse(output.is_relative_to(self.staging))
        self.assertFalse(output.parent.parent.exists())
        self.assertEqual({p.relative_to(self.staging): p.read_bytes()
                          for p in self.staging.rglob("*") if p.is_file()}, before)
        self.assertNotEqual((self.data / old_archive.name).read_bytes(), old_archive.read_bytes())

    def test_terrain_and_overlay_mask_share_the_general_archive(self):
        build = self.archive_builder()
        mask = self.staging / "Data" / "textures" / "terrain" / "overlaymasks" / "synthetic.dds"
        mask.parent.mkdir(parents=True)
        mask.write_bytes(b"synthetic mask")
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
            process.assert_called_once()
        command = process.call_args.args[0]
        self.assertEqual(command[1], "Terrain,textures")
        self.assertIn("-format=General", command)
        self.assertIn("-compression=None", command)
        record = json.loads((self.data / exp.RECORD).read_bytes())
        self.assertIn("Data/textures/terrain/overlaymasks/synthetic.dds", record["source_inputs"])
        self.assertEqual(set(record["files"]), {"Experiment.esm", "Experiment - Main.ba2"})
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_relaunch_rejects_a_previous_packing_policy(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build):
            exp.install(self.args)
        record_path = self.data / exp.RECORD
        record = json.loads(record_path.read_bytes())
        record.pop("packing_policy", None)
        record_path.write_text(json.dumps(record), encoding="utf-8")
        before = record_path.read_bytes()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            with self.assertRaisesRegex(SystemExit, "packing policy"):
                exp.install(self.args)
            process.assert_not_called()
        self.assertEqual(record_path.read_bytes(), before)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_failed_pack_cleans_temporary_output_without_touching_staging(self):
        build = self.archive_builder()
        before = {p.relative_to(self.staging): p.read_bytes()
                  for p in self.staging.rglob("*") if p.is_file()}

        def fail(command, **kwargs):
            build(command, **kwargs)
            return SimpleNamespace(returncode=1, stdout="synthetic failure", stderr=None)

        with patch.object(exp.subprocess, "run", side_effect=fail) as process:
            with self.assertRaisesRegex(SystemExit, "synthetic failure"):
                exp.install(self.args)
        output = Path(next(arg[len("-create="):] for arg in process.call_args.args[0]
                           if arg.startswith("-create=")))
        self.assertFalse(output.parent.parent.exists())
        self.assertEqual({p.relative_to(self.staging): p.read_bytes()
                          for p in self.staging.rglob("*") if p.is_file()}, before)
        self.assert_rolled_back()

    def test_packed_archive_copy_failure_rolls_back_published_plugin(self):
        build = self.archive_builder()
        real_copy = exp.shutil.copyfile

        def copy(source, target):
            if Path(source).suffix == ".ba2":
                Path(target).write_bytes(b"partial archive")
                raise OSError("injected archive copy failure")
            return real_copy(source, target)

        with patch.object(exp.subprocess, "run", side_effect=build), \
                patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_packed_build_failure_preserves_previous_archive_and_game(self):
        build = self.archive_builder()
        archive = self.staging / "Experiment - Main.ba2"
        previous = b"previous staging archive"
        archive.write_bytes(previous)

        def fail(command, **kwargs):
            result = build(command, **kwargs)
            result.returncode = 1
            return result

        with patch.object(exp.subprocess, "run", side_effect=fail):
            with self.assertRaises(SystemExit):
                exp.install(self.args)
        self.assertEqual(archive.read_bytes(), previous)
        self.assert_rolled_back()

    def test_truncated_packed_archive_is_rejected_before_installation(self):
        build = self.archive_builder(b"BTDX")
        archive = self.staging / "Experiment - Main.ba2"
        previous = b"previous staging archive"
        archive.write_bytes(previous)
        with patch.object(exp.subprocess, "run", side_effect=build):
            with self.assertRaises(SystemExit):
                exp.install(self.args)
        self.assertEqual(archive.read_bytes(), previous)
        self.assert_rolled_back()

    def test_missing_plugin_is_rejected_before_packing(self):
        build = self.archive_builder()
        self.args.plugins = "Experiment.esm,Missing.esm"
        archive = self.staging / "Experiment - Main.ba2"
        previous = b"previous staging archive"
        archive.write_bytes(previous)
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
            process.assert_not_called()
        self.assertEqual(archive.read_bytes(), previous)
        self.assert_rolled_back()

    def test_packing_mode_change_is_not_reported_as_already_installed(self):
        exp.install(self.args)
        installed = (self.data / exp.RECORD).read_bytes()
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            with self.assertRaisesRegex(SystemExit, "mode"):
                exp.install(self.args)
            process.assert_not_called()
        self.assertEqual((self.data / exp.RECORD).read_bytes(), installed)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def changed_plugin_blocks_relaunch_after_partial_cleanup(self):
        exp.install(self.args)
        plugin = self.data / "Experiment.esm"
        plugin.write_bytes(b"owner changed plugin")
        with self.assertRaisesRegex(SystemExit, "changed since install"):
            exp.uninstall(self.args)
        self.assertEqual({path.name for path in self.data.iterdir()}, {"Experiment.esm", exp.RECORD})
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            exp.install(self.args)
        self.assertEqual(plugin.read_bytes(), b"owner changed plugin")
        # Once the owner restores the recorded content, cleanup is retryable.
        plugin.write_bytes((self.staging / "Experiment.esm").read_bytes())
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_partial_loose_uninstall_cannot_masquerade_as_installed(self):
        self.changed_plugin_blocks_relaunch_after_partial_cleanup()

    def test_partial_packed_uninstall_cannot_masquerade_as_installed(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            self.changed_plugin_blocks_relaunch_after_partial_cleanup()
            process.assert_called_once()

    def test_interrupted_uninstall_is_journaled_before_plugin_changes(self):
        exp.install(self.args)
        real_write = exp.write_plugins

        def remove_activation_then_interrupt(*args, **kwargs):
            real_write(*args, **kwargs)
            raise KeyboardInterrupt("injected interrupted uninstall")

        with patch.object(exp, "write_plugins", side_effect=remove_activation_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                exp.uninstall(self.args)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            exp.install(self.args)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_inactive_existing_plugin_is_activated_and_restored(self):
        self.original += b"  Experiment.esm  \r\n"
        self.plugins.write_bytes(self.original)
        exp.install(self.args)
        lines = self.plugins.read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(lines.count("*Experiment.esm"), 1)
        self.assertNotIn("  Experiment.esm  ", lines)
        exp.install(self.args)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_activation_restoration_preserves_cr_and_missing_trailing_newline(self):
        for original in (b"# owner\r*FO4Port.esm\rExperiment.esm\r",
                         b"\xef\xbb\xbf# owner\n*FO4Port.esm\nExperiment.esm"):
            with self.subTest(original=original):
                self.original = original
                self.plugins.write_bytes(original)
                exp.install(self.args)
                expected = original.replace(b"Experiment.esm", b"*Experiment.esm")
                self.assertEqual(self.plugins.read_bytes(), expected)
                exp.uninstall(self.args)
                self.assert_rolled_back()

    def test_relaunch_rejects_an_externally_deactivated_plugin(self):
        exp.install(self.args)
        inactive = self.original + b"Experiment.esm\r\n"
        self.plugins.write_bytes(inactive)
        with self.assertRaisesRegex(SystemExit, "inactive"):
            exp.install(self.args)
        self.assertEqual(self.plugins.read_bytes(), inactive)

    def test_relaunch_rejects_a_missing_packed_archive(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
            (self.data / "Experiment - Main.ba2").unlink()
            with self.assertRaisesRegex(SystemExit, "missing or changed"):
                exp.install(self.args)
            process.assert_called_once()

    def test_relaunch_rejects_rebuilt_staged_plugin(self):
        exp.install(self.args)
        (self.staging / "Experiment.esm").write_bytes(b"rebuilt plugin")
        with self.assertRaisesRegex(SystemExit, "source inputs changed"):
            exp.install(self.args)
        self.assertEqual((self.data / "Experiment.esm").read_bytes(), b"synthetic plugin")

    def test_relaunch_rejects_changed_packed_terrain_inputs(self):
        build = self.archive_builder()
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            exp.install(self.args)
            (self.staging / "Data" / self.terrain).write_bytes(b"changed terrain")
            with self.assertRaisesRegex(SystemExit, "source inputs changed"):
                exp.install(self.args)
            process.assert_called_once()

    def test_changed_terrain_during_packing_is_rejected_before_installation(self):
        build = self.archive_builder()

        def change_inputs(command, **kwargs):
            result = build(command, **kwargs)
            (self.staging / "Data" / self.terrain).write_bytes(b"changed while packing")
            return result

        with patch.object(exp.subprocess, "run", side_effect=change_inputs):
            with self.assertRaisesRegex(SystemExit, "changed during preparation"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_packing_refuses_omitted_root_data_files_before_building(self):
        build = self.archive_builder()
        (self.staging / "Data" / "extra.txt").write_bytes(b"synthetic root resource")
        with patch.object(exp.subprocess, "run", side_effect=build) as process:
            with self.assertRaisesRegex(SystemExit, "root"):
                exp.install(self.args)
            process.assert_not_called()
        self.assert_rolled_back()

    def test_missing_local_appdata_cannot_activate_a_relative_profile(self):
        previous = os.getcwd()
        os.chdir(self.root)
        try:
            with patch.dict(os.environ, {"LOCALAPPDATA": ""}):
                with self.assertRaisesRegex(SystemExit, "LOCALAPPDATA"):
                    exp.install(self.args)
        finally:
            os.chdir(previous)
        self.assert_rolled_back()

    def test_pre_replacement_config_conflict_finishes_rollback(self):
        real_write = exp.write_plugins
        edited = self.original + b"*OwnerAdded.esm\r\n"

        def edit_before_write(*args, **kwargs):
            self.plugins.write_bytes(edited)
            return real_write(*args, **kwargs)

        with patch.object(exp, "write_plugins", side_effect=edit_before_write):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), edited)

    def test_changed_source_during_copy_is_never_published(self):
        real_copy = exp.shutil.copyfile

        def copy(source, target):
            if Path(source).suffix == ".esm":
                Path(source).write_bytes(b"changed source while copying")
            return real_copy(source, target)

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_duplicate_destinations_are_rejected_before_publication(self):
        (self.staging / "Data" / "Experiment.esm").write_bytes(b"conflicting synthetic plugin")
        with self.assertRaisesRegex(SystemExit, "duplicate"):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_resource_added_after_enumeration_cannot_be_recorded_but_omitted(self):
        real_files = exp.staged_files

        def files(*args):
            planned = real_files(*args)
            (self.staging / "Data" / "Terrain" / "late.bin").write_bytes(b"late synthetic resource")
            return planned

        with patch.object(exp, "staged_files", side_effect=files):
            with self.assertRaisesRegex(SystemExit, "inventory changed"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_publication_is_recorded_before_full_installed_archive_hash(self):
        build = self.archive_builder()
        real_digest = exp.digest

        def interrupt(path):
            if Path(path) == self.data / "Experiment - Main.ba2":
                raise KeyboardInterrupt("injected interruption during installed archive hash")
            return real_digest(path)

        with patch.object(exp.subprocess, "run", side_effect=build), \
                patch.object(exp, "digest", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                exp.install(self.args)
        record = json.loads((self.data / exp.RECORD).read_text())
        self.assertIn("Experiment - Main.ba2", record["published_files"])
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_partial_second_copy_rolls_back_files_and_directories(self):
        real_copy = exp.shutil.copyfile

        def copy(source, target):
            if Path(source).suffix == ".btd":
                Path(target).write_bytes(b"partial copy")
                raise OSError("injected terrain copy failure")
            return real_copy(source, target)

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_missing_source_is_rejected_before_any_publication(self):
        self.args.plugins = "Experiment.esm,Missing.esm"
        with self.assertRaises((OSError, SystemExit)):
            exp.install(self.args)
        self.assert_rolled_back()

    def test_failure_after_activation_restores_exact_plugin_bytes(self):
        real_write = exp.write_plugins

        def activate_then_fail(*args, **kwargs):
            real_write(*args, **kwargs)
            raise OSError("injected failure after activation")

        with patch.object(exp, "write_plugins", side_effect=activate_then_fail):
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_final_record_failure_rolls_back_activation_and_files(self):
        real_write = exp.deployment.write_manifest

        def write(path, record):
            if record["complete"]:
                raise OSError("injected final record failure")
            return real_write(path, record)

        with patch.object(exp.deployment, "write_manifest", side_effect=write):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assert_rolled_back()

    def test_rollback_removes_activation_when_no_plugins_file_existed(self):
        self.plugins.unlink()
        self.plugins.parent.rmdir()
        real_write = exp.write_plugins

        def activate_then_fail(*args, **kwargs):
            real_write(*args, **kwargs)
            raise OSError("injected failure after first activation")

        with patch.object(exp, "write_plugins", side_effect=activate_then_fail):
            with self.assertRaisesRegex(SystemExit, "rolled back"):
                exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertFalse(self.plugins.exists())

    def test_interrupted_activation_has_a_durable_uninstall_record(self):
        real_write = exp.write_plugins

        def activate_then_interrupt(*args, **kwargs):
            real_write(*args, **kwargs)
            raise KeyboardInterrupt("injected interruption")

        with patch.object(exp, "write_plugins", side_effect=activate_then_interrupt):
            with self.assertRaises(KeyboardInterrupt):
                exp.install(self.args)
        record = self.data / exp.RECORD
        self.assertTrue(record.exists(), "interruption must not strand untracked files")
        self.assertFalse(json.loads(record.read_text())["complete"])
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            exp.install(self.args)
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_failed_cleanup_retains_a_retryable_record(self):
        real_remove = exp.os.remove
        plugin = self.data / "Experiment.esm"

        def remove(path):
            if Path(path) == plugin:
                raise PermissionError("injected locked plugin")
            return real_remove(path)

        with patch.object(exp, "write_plugins", side_effect=OSError("activation failed")), \
                patch.object(exp.os, "remove", side_effect=remove):
            with self.assertRaises((OSError, SystemExit)):
                exp.install(self.args)
        record = self.data / exp.RECORD
        self.assertTrue(record.exists(), "failed rollback must retain cleanup ownership")
        self.assertEqual(list(json.loads(record.read_text())["files"]), ["Experiment.esm"])
        exp.uninstall(self.args)
        self.assert_rolled_back()

    def test_plugin_edit_during_copy_is_preserved(self):
        real_copy = exp.shutil.copyfile
        edited = self.original + b"*OwnerAdded.esm\r\n"

        def copy(source, target):
            result = real_copy(source, target)
            self.plugins.write_bytes(edited)
            return result

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaisesRegex(SystemExit, "changed"):
                exp.install(self.args)
        self.assertEqual(list(self.data.iterdir()), [])
        self.assertEqual(self.plugins.read_bytes(), edited)

    def test_destination_race_never_claims_or_deletes_the_other_file(self):
        real_copy = exp.shutil.copyfile
        target = self.data / self.terrain
        # Identical bytes do not establish that this installer published a file.
        foreign = (self.staging / "Data" / self.terrain).read_bytes()

        def copy(source, destination):
            if Path(source).suffix == ".btd":
                target.write_bytes(foreign)
            return real_copy(source, destination)

        with patch.object(exp.shutil, "copyfile", side_effect=copy):
            with self.assertRaises(SystemExit):
                exp.install(self.args)
        self.assertEqual(target.read_bytes(), foreign)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertFalse((self.data / exp.RECORD).exists(), "proven foreign publication must not trap recovery")
        exp.uninstall(self.args)
        self.assertEqual(target.read_bytes(), foreign)

    def test_recovery_record_cannot_delete_outside_data(self):
        outside = self.data.parent / "Owner.txt"
        outside.write_bytes(b"owner file")
        record = self.data / exp.RECORD
        record.write_text(json.dumps({"files": {"../Owner.txt": exp.digest(outside)},
                                     "dirs": [], "plugins_added": []}))
        with self.assertRaisesRegex(SystemExit, "outside Data"):
            exp.uninstall(self.args)
        self.assertEqual(outside.read_bytes(), b"owner file")
        self.assertTrue(record.exists())


class ActiveCheckTests(unittest.TestCase):
    """exp_install.py active: Starfield can deactivate installed plugins while running (2026-10-13 load order dialog)."""

    def run_active(self, plugins_txt_text, record):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Data").mkdir()
            (root / "Local" / "Starfield").mkdir(parents=True)
            if record is not None:
                (root / "Data" / exp.RECORD).write_text(json.dumps(record))
            (root / "Local" / "Starfield" / "Plugins.txt").write_text(plugins_txt_text)
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "Local")}):
                return exp.active(SimpleNamespace(starfield=str(root)))

    def test_all_active(self):
        txt = "# header\n*FO4Port.esm\n*FO4TerrainExp2.esm\n*FO4TerrainExp2_Mars.esm\n"
        self.assertEqual(self.run_active(txt, {"plugins": ["FO4TerrainExp2.esm", "FO4TerrainExp2_Mars.esm"]}), 0)

    def test_deactivated_by_the_game(self):
        # Plugins.txt as Starfield rewrote it at 23:27 on 2026-10-13
        txt = "# header\n*FO4Port.esm\nFO4TerrainExp2.esm\nFO4TerrainExp2_Mars.esm\n"
        self.assertEqual(self.run_active(txt, {"plugins": ["FO4TerrainExp2.esm", "FO4TerrainExp2_Mars.esm"]}), 8)

    def test_missing_line_and_legacy_record(self):
        self.assertEqual(self.run_active("*FO4Port.esm\n", {"plugins_added": ["*Experiment.esm"]}), 8)

    def test_nothing_installed(self):
        self.assertEqual(self.run_active("*FO4Port.esm\n", None), 0)


if __name__ == "__main__":
    unittest.main()
