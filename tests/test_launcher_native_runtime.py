"""Measured native identities: synthetic bytes, no native binaries or game action."""
import copy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fo4sf.launcher import runtimes as rt, crashwatch, detect, settings
from test_launcher_crashwatch import FakeSystem


def pin(raw):
    return {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class NativeRuntimeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.game = Path(tmp.name) / 'Starfield'
        self.plugins = self.game / 'Data' / 'SFSE' / 'Plugins'
        self.plugins.mkdir(parents=True)
        (self.game / 'Starfield.exe').write_bytes(b'game')
        (self.game / 'sfse_loader.exe').write_bytes(b'loader')
        (self.game / 'sfse_1_16_244.dll').write_bytes(b'sfse dll')
        self.source = rt._native_table()
        self.dll, self.lib = b'probe dll bytes', b'library bytes'
        self.library = self.source['address_library']['file']
        self.entry = {'label': 'synthetic', 'exe_version': self.source['runtime'],
            'sfse': {'loader_sha256': pin(b'loader')['sha256'],
                     'dlls': {'sfse_1_16_244.dll': pin(b'sfse dll')['sha256']}}, 'native': {'schema': 1,
            'plugins': {'FOCCPing.dll': dict(pin(self.dll), runtime=self.source['runtime'], required=False,
                needs_address_library=True, source_commit='c' * 40, artifact_receipt='synthetic build receipt')},
            'address_library': dict(pin(self.lib), file=self.library, provenance='synthetic measurement')}}

    def put(self, name, raw):
        path = self.plugins / name
        path.write_bytes(raw)
        return path

    def problems(self, entry=None):
        return rt.native_problems(self.entry if entry is None else entry, self.game)

    def install(self):
        self.put('FOCCPing.dll', self.dll)
        self.put(self.library, self.lib)

    def test_absent_probes_need_no_native_block_or_library(self):
        self.assertEqual(rt.native_problems({}, self.game), [])
        self.assertEqual(rt.native_problems(None, self.game), [])
        self.assertEqual(self.problems(), [])

    def test_missing_plugins_folder_is_fine_only_when_optional(self):
        self.plugins.rmdir()
        self.assertEqual(self.problems(), [])
        self.entry['native']['plugins']['FOCCPing.dll']['required'] = True
        self.assertIn('missing', ' '.join(self.problems()))

    def test_installed_optional_requires_measured_identity(self):
        self.put('FOCCPing.dll', self.dll)
        for entry in ({}, None):
            with self.subTest(entry=entry):
                self.assertIn('no measured identity', ' '.join(rt.native_problems(entry, self.game)))

    def test_matching_installed_bytes_pass_with_case_variation(self):
        self.put('foccping.DLL', self.dll)
        self.put(self.library.upper(), self.lib)
        self.assertEqual(self.problems(), [])

    def test_installed_native_enforces_sfse_on_every_route(self):
        self.install()
        self.entry["sfse"]["loader_sha256"] = "0" * 64
        self.assertIn("sfse_loader.exe", " ".join(self.problems()))

    def test_measured_native_missing_or_malformed_sfse_refuses_every_play_route(self):
        self.install()
        self.entry['exe_sha256'] = pin(b'game')['sha256']
        valid = copy.deepcopy(self.entry['sfse'])
        bad = [None, {}, [], {'loader_sha256': '', 'dlls': valid['dlls']},
               {'loader_sha256': valid['loader_sha256'], 'dlls': {}},
               {'loader_sha256': valid['loader_sha256'], 'dlls': {'../sfse_bad.dll': 'a' * 64}},
               {'loader_sha256': valid['loader_sha256'], 'dlls': {'sfse_bad.dll': []}},
               {'loader_sha256': valid['loader_sha256'], 'dlls': {
                   'sfse_a.dll': 'a' * 64, 'sfse_A.dll': 'b' * 64}}]
        for sfse in bad:
            for route in ('exe', 'steam', 'sfse'):
                for dry in (False, True):
                    entry = copy.deepcopy(self.entry)
                    if sfse is None:
                        entry.pop('sfse')
                    else:
                        entry['sfse'] = sfse
                    result = detect.detect(fo4_data=[], starfield=str(self.game), sources={'sources': []},
                        runtimes={'runtimes': [entry]}, allow_unknown_runtime=True, require_sfse=False)
                    self.assertTrue(any('native' in p and 'SFSE' in p for p in result['refusals']))
                    v = settings.defaults()
                    v.update(route=route, load_order='off')
                    system = FakeSystem([])
                    with self.subTest(sfse=sfse, route=route, dry=dry), mock.patch.object(
                            rt, 'load_runtimes', return_value={'runtimes': [entry]}), mock.patch.object(
                            crashwatch, 'apply_papyrus') as apply:
                        with self.assertRaisesRegex(ValueError, 'SFSE'):
                            crashwatch.play(v, str(self.game), system=system, dry_run=dry)
                        apply.assert_not_called()
                        self.assertIsNone(system.started_at)
        self.entry.pop('sfse')
        result = detect.detect(fo4_data=[], starfield=str(self.game), sources={'sources': []},
            runtimes={'runtimes': [self.entry]}, allow_unknown_runtime=True, require_sfse=False)
        self.assertTrue(any('native' in p and 'SFSE' in p for p in result['refusals']))

    def test_complete_sfse_pins_allow_play_but_missing_or_wrong_files_refuse(self):
        self.install()
        self.entry['exe_sha256'] = pin(b'game')['sha256']
        for route in ('exe', 'steam', 'sfse'):
            v = settings.defaults()
            v.update(route=route, load_order='off')
            with mock.patch.object(rt, 'load_runtimes', return_value={'runtimes': [self.entry]}):
                system = FakeSystem([])
                crashwatch.play(v, str(self.game), system=system)
                self.assertIsNotNone(system.started_at)
                for name, original in (('sfse_loader.exe', b'loader'), ('sfse_1_16_244.dll', b'sfse dll')):
                    path = self.game / name
                    for raw in (None, b'wrong SFSE'):
                        if raw is None:
                            path.unlink()
                        else:
                            path.write_bytes(raw)
                        system = FakeSystem([])
                        with self.subTest(route=route, name=name, raw=raw):
                            with self.assertRaisesRegex(ValueError, 'sfse_'):
                                crashwatch.play(v, str(self.game), system=system)
                            self.assertIsNone(system.started_at)
                        path.write_bytes(original)

    def test_final_gate_refuses_sfse_pins_removed_by_tool(self):
        self.install()
        self.entry['exe_sha256'] = pin(b'game')['sha256']
        v = settings.defaults()
        v.update(route='exe', load_order='off')
        system = FakeSystem([])
        def late(*args, **kwargs):
            self.entry.pop('sfse')
        with mock.patch.object(rt, 'load_runtimes', return_value={'runtimes': [self.entry]}), mock.patch.object(
                crashwatch, 'apply_load_order', side_effect=late):
            with self.assertRaisesRegex(ValueError, 'measured SFSE'):
                crashwatch.play(v, str(self.game), system=system)
        self.assertIsNone(system.started_at)

    def test_hardlinked_native_bytes_refuse(self):
        self.install()
        try:
            os.link(self.plugins / 'FOCCPing.dll', self.game / 'aliased.dll')
        except OSError as error:
            self.skipTest(str(error))
        self.assertIn('hard links', ' '.join(self.problems()))

    def test_wrong_same_size_hash_and_size_refuse(self):
        self.install()
        for raw in (b'x' * len(self.dll), self.dll + b'x'):
            self.put('FOCCPing.dll', raw)
            self.assertIn('differ', ' '.join(self.problems()))

    def test_library_required_only_for_installed_or_required_component(self):
        self.put(self.library, b'wrong')
        self.assertEqual(self.problems(), [])
        self.put('FOCCPing.dll', self.dll)
        self.assertIn('Address Library bytes', ' '.join(self.problems()))
        (self.plugins / self.library).unlink()
        self.assertIn('Address Library file missing', ' '.join(self.problems()))

    def test_border_does_not_acquire_library_dependency(self):
        self.put('FO4SFBorder.dll', self.dll)
        p = self.entry['native']['plugins'].pop('FOCCPing.dll')
        p['needs_address_library'] = False
        self.entry['native']['plugins']['FO4SFBorder.dll'] = p
        self.entry['native'].pop('address_library')
        self.assertEqual(self.problems(), [])

    def test_required_missing_refuses(self):
        self.entry['native']['plugins']['FOCCPing.dll']['required'] = True
        self.assertIn('required native component', ' '.join(self.problems()))

    def test_source_required_cannot_be_weakened_by_release(self):
        source = copy.deepcopy(self.source)
        source['plugins']['FOCCPing.dll']['required'] = True
        self.assertIn('required native component', ' '.join(rt.native_problems(self.entry, self.game, source)))

    def test_unrelated_plugin_preserved_and_ignored(self):
        path = self.put('OtherUser.dll', b'private plugin')
        self.assertEqual(rt.native_problems({}, self.game), [])
        self.assertEqual(path.read_bytes(), b'private plugin')

    def test_case_collisions_refuse(self):
        self.install()
        path = self.put('foccping.DLL', b'another')
        if path.samefile(self.plugins / 'FOCCPing.dll'):
            self.skipTest('case-insensitive filesystem')
        self.assertIn('collide', ' '.join(self.problems()))

    def test_links_and_linked_parent_refuse(self):
        self.install()
        path = self.plugins / 'FOCCPing.dll'
        path.unlink()
        target = self.game / 'copy.dll'
        target.write_bytes(self.dll)
        try:
            path.symlink_to(target)
        except OSError as error:
            self.skipTest(str(error))
        self.assertIn('linked', ' '.join(self.problems()))
        path.unlink()
        old = self.plugins.rename(self.plugins.with_name('stored'))
        self.plugins.symlink_to(old, target_is_directory=True)
        self.assertIn('linked', ' '.join(self.problems()))

    def test_changed_during_hash_refuses(self):
        self.install()
        original = rt.hashlib.sha256
        path = self.plugins / 'FOCCPing.dll'
        class Change:
            def __init__(self):
                self.hash = original()
            def update(self, block):
                self.hash.update(block)
                path.write_bytes(self.dll + b'changed')
            def hexdigest(self):
                return self.hash.hexdigest()
        # Bind bytes separately from the digest object.
        Change.dll = self.dll
        with mock.patch.object(rt.hashlib, 'sha256', Change):
            self.assertIn('changed', ' '.join(self.problems()))

    def test_malformed_native_shapes_refuse_without_exception(self):
        for native in (None, [], 'bad', {'schema': True, 'plugins': {}}, {'schema': 1, 'plugins': []}):
            with self.subTest(native=native):
                self.assertTrue(rt.native_declaration_problems({'native': native}))

    def test_malformed_plugin_identity_fields_refuse(self):
        for key, value in (('size', True), ('size', 0), ('sha256', 'B' * 64), ('source_commit', 'abc'),
                           ('artifact_receipt', ' '), ('required', 'no'), ('needs_address_library', False),
                           ('runtime', 'other')):
            entry = copy.deepcopy(self.entry)
            entry['native']['plugins']['FOCCPing.dll'][key] = value
            with self.subTest(key=key):
                self.assertTrue(rt.native_declaration_problems(entry))

    def test_library_shape_and_provenance_refuse(self):
        for key, value in (('size', True), ('sha256', []), ('file', '../bad'), ('provenance', '')):
            entry = copy.deepcopy(self.entry)
            entry['native']['address_library'][key] = value
            with self.subTest(key=key):
                self.assertTrue(rt.native_declaration_problems(entry))

    def test_unknown_names_fields_collisions_and_runtime_refuse(self):
        for name in ('../FOCCPing.dll', 'Unknown.dll', 'foccping.DLL'):
            entry = copy.deepcopy(self.entry)
            entry['native']['plugins'][name] = entry['native']['plugins']['FOCCPing.dll']
            self.assertTrue(rt.native_declaration_problems(entry))
        self.entry['exe_version'] = 'other'
        self.assertTrue(rt.native_declaration_problems(self.entry))

    def test_duplicate_or_oversized_runtime_json_refuses(self):
        path = self.game / 'table.json'
        for raw in (b'{"schema":1,"runtimes":[],"runtimes":[]}', b' ' * ((1 << 20) + 1)):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                rt.load_runtimes(path)

    def test_all_play_routes_refuse_unknown_installed_dll_before_writes(self):
        self.put('FOCCPing.dll', self.dll)
        for route in ('exe', 'steam', 'sfse'):
            for dry in (True, False):
                v = settings.defaults()
                v.update(route=route, load_order='off')
                system = FakeSystem([])
                with self.subTest(route=route, dry=dry), mock.patch.object(crashwatch, 'apply_papyrus') as apply:
                    with self.assertRaisesRegex(ValueError, 'no measured identity'):
                        crashwatch.play(v, str(self.game), system=system, dry_run=dry)
                    apply.assert_not_called()
                    self.assertIsNone(system.started_at)

    def test_final_check_catches_dll_added_after_early_gate(self):
        v = settings.defaults()
        v.update(route='exe', load_order='off')
        system = FakeSystem([])
        def late(*args, **kwargs):
            self.put('FOCCPing.dll', self.dll)
        with mock.patch.object(crashwatch, 'apply_load_order', side_effect=late):
            with self.assertRaisesRegex(ValueError, 'no measured identity'):
                crashwatch.play(v, str(self.game), system=system)
        self.assertIsNone(system.started_at)

    def test_detect_allow_unknown_and_no_sfse_cannot_bypass(self):
        self.put('FOCCPing.dll', self.dll)
        result = detect.detect(fo4_data=[], starfield=str(self.game), sources={'sources': []},
                               runtimes={'runtimes': []}, allow_unknown_runtime=True, require_sfse=False)
        self.assertTrue(any('no measured identity' in p for p in result['refusals']))


if __name__ == '__main__':
    unittest.main()
