"""Synthetic kit inventories and recovery gates; no game assets, processes or display."""
import hashlib
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
from fo4sf.launcher import recovery, test_kits as kits  # noqa: E402


class TestKitCatalog(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.game = self.root / 'game'
        self.data = self.game / 'Data'
        self.data.mkdir(parents=True)
        self.plugins = self.root / 'Plugins.txt'
        self.registry = self.root / 'registry.json'

    def receipt(self, kit, **extra):
        payload = b'synthetic plugin'
        (self.data / kit.plugin).write_bytes(payload)
        value = {'complete': True, 'plugins': [kit.plugin],
                 'files': {kit.plugin: hashlib.sha256(payload).hexdigest()}}
        value.update(extra)
        path = self.data / kit.receipt
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def rows(self, stages=None):
        return kits.list_kits(str(self.game), stages or {}, str(self.plugins), str(ROOT))

    def test_empty_machine_has_no_invented_stages_and_writes_nothing(self):
        before = sorted(self.root.rglob('*'))
        self.assertEqual(self.rows(), [])
        self.assertEqual(sorted(self.root.rglob('*')), before)

    def test_all_five_registered_kits_have_stable_order_and_not_installed_state(self):
        stages = {}
        for kit in reversed(kits.KITS):
            stage = self.root / kit.key
            stage.mkdir()
            stages[kit.key] = str(stage)
        rows = self.rows(stages)
        self.assertEqual([r['key'] for r in rows], [k.key for k in kits.KITS])
        self.assertTrue(all(r['state'] == 'not installed' and not r['notice'] for r in rows))
        self.assertTrue(all(row['installer_available'] for row in rows))
        missing = kits.list_kits(str(self.game), stages, str(self.plugins), str(self.root / 'missing-checkout'))
        self.assertEqual([row['key'] for row in missing], [k.key for k in kits.KITS])
        self.assertTrue(all(not row['installer_available'] for row in missing))

    def test_multi_plugin_active_requires_every_plugin_and_unchanged_owned_bytes(self):
        kit = kits.KITS[0]
        receipt = self.receipt(kit, plugins=[kit.plugin, 'Second.esm'])
        (self.data / 'Second.esm').write_bytes(b'second')
        record = json.loads(receipt.read_text())
        record['files']['Second.esm'] = hashlib.sha256(b'second').hexdigest()
        receipt.write_text(json.dumps(record))
        self.plugins.write_text('*' + kit.plugin.lower() + '\nSecond.esm\n', encoding='utf-8-sig')
        before = receipt.read_bytes()
        self.assertEqual(self.rows()[0]['state'], 'installed')
        self.plugins.write_text('*' + kit.plugin.lower() + '\n*SECOND.ESM\n')
        self.assertEqual(self.rows()[0]['state'], 'installed and active')
        (self.data / kit.plugin).write_bytes(b'external edit')
        row = self.rows()[0]
        self.assertEqual(row['state'], 'installed')
        self.assertIn('changed', row['problems'][0])
        self.assertEqual(row['notice'], 'saves made now will list this test plugin')
        self.assertEqual(receipt.read_bytes(), before)

    def test_active_list_cannot_substitute_an_unowned_or_foreign_plugin(self):
        kit = kits.KITS[2]
        for plugins in [[kit.plugin, 'NotOwned.esm'], ['Foreign.esm']]:
            self.receipt(kit, plugins=plugins)
            self.plugins.write_text(''.join('*' + p + '\n' for p in plugins))
            row = self.rows()[0]
            self.assertEqual(row['state'], 'installed')
            self.assertIn('does not own', ' '.join(row['problems']))

    def test_installed_orphan_remains_listed_and_active_with_missing_stage(self):
        kit = kits.KITS[2]
        self.receipt(kit, exp_dir=str(self.root / 'gone'))
        self.plugins.write_text('*' + kit.plugin + '\n')
        row = self.rows()[0]
        self.assertTrue(row['installed'])
        self.assertEqual(row['state'], 'installed and active')
        self.assertIn('still be removed', row['problems'][0])

    def test_corrupt_empty_and_interrupted_receipts_never_claim_active(self):
        kit = kits.KITS[2]
        path = self.data / kit.receipt
        self.plugins.write_text('*' + kit.plugin + '\n')
        for raw in [b'{', b'[]', b'{}', b'null', b'{"complete":false}',
                    b'{"complete":true,"cleanup_pending":true}', b'{"rollback_completed":{}}',
                    b'{"files":5}']:
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                row = self.rows()[0]
                self.assertTrue(row['installed'])
                self.assertEqual(row['state'], 'installed')
                self.assertTrue(row['problems'])
                self.assertTrue(recovery.play_reason(str(self.game)))
                self.assertEqual(path.read_bytes(), raw)

    def test_invalid_owned_paths_and_hashes_are_refused_before_reading_outside_data(self):
        kit = kits.KITS[2]
        for name, digest in [('../secret', '0'*64), ('C:\\secret', '0'*64),
                             ('/secret', '0'*64), ('ok.esm', None), ('ok.esm', 'wrong')]:
            with self.subTest(name=name, digest=digest):
                self.receipt(kit, files={name: digest})
                with mock.patch.object(kits.files, 'sha256') as read:
                    row = self.rows()[0]
                read.assert_not_called()
                self.assertTrue(row['problems'])

    def test_missing_files_and_unreadable_plugin_list_do_not_claim_active(self):
        kit = kits.KITS[0]
        self.receipt(kit)
        self.plugins.write_bytes(b'\xff')
        self.assertIn('Cannot read', ' '.join(self.rows()[0]['problems']))
        self.plugins.write_text('*' + kit.plugin)
        (self.data / kit.plugin).unlink()
        self.assertEqual(self.rows()[0]['state'], 'installed')
        self.assertTrue(self.rows()[0]['problems'])

    def test_registry_is_strict_and_never_executes_kit_supplied_commands(self):
        self.assertEqual(kits.load_registry(self.registry), {})
        for value in [[], {'schema': 2, 'kits': {}}, {'schema': 1, 'kits': {'alien': '/somewhere'}},
                      {'schema': 1, 'kits': {'pipboy_probe': '../relative'}},
                      {'schema': 1, 'kits': {'pipboy_probe': ['command']}}]:
            self.registry.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                kits.load_registry(self.registry)
        expected = {'pipboy_probe': str(self.root)}
        self.registry.write_text(json.dumps({'schema': 1, 'kits': expected}))
        self.assertEqual(kits.load_registry(self.registry), expected)
        with self.assertRaises(ValueError):
            self.rows({'alien': str(self.root)})

    def test_owner_cards_accept_at_most_eight_numbered_plain_steps(self):
        card = self.root / kits.CARD
        text = 'Owner test\n\n' + '\n'.join(f'{i}. Watch the screen.' for i in range(1, 9)) + '\n'
        card.write_text(text, encoding='utf-8-sig')
        self.assertEqual(kits.owner_card(str(self.root)).count('Watch the screen.'), 8)
        for text in ['Title\n', '1. No title\n2. Second\n', 'Title\n2. Wrong order\n',
                     'Title\n1. One\ncontinuation\n', 'Title\n1. \x00control\n',
                     'Title\n' + '\n'.join(f'{i}. Step' for i in range(1, 10)), 'x'*16385]:
            card.write_text(text)
            with self.assertRaises(ValueError):
                kits.owner_card(str(self.root))
        card.write_bytes(b'\xff')
        with self.assertRaises(ValueError):
            kits.owner_card(str(self.root))
        card.unlink()
        with self.assertRaisesRegex(ValueError, "Owner card is missing"):
            kits.owner_card(str(self.root))

    def test_missing_or_unreadable_card_errors_do_not_disclose_private_paths(self):
        private = self.root / "private-person-name" / "staged kit"
        private.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Owner card is missing") as missing:
            kits.owner_card(str(private))
        self.assertNotIn(str(private), str(missing.exception))
        failure = PermissionError(13, "denied", str(private / kits.CARD))
        with mock.patch("builtins.open", side_effect=failure):
            with self.assertRaisesRegex(ValueError, "Cannot read owner card") as unreadable:
                kits.owner_card(str(private))
        self.assertNotIn("private-person-name", str(unreadable.exception))

    def test_owner_card_link_is_not_followed(self):
        elsewhere = self.root / 'elsewhere.txt'
        elsewhere.write_text('Title\n1. Step\n')
        (self.root / kits.CARD).symlink_to(elsewhere)
        with self.assertRaisesRegex(ValueError, 'not a link'):
            kits.owner_card(str(self.root))

    def test_every_kit_receipt_blocks_play_when_interrupted(self):
        for kit in kits.KITS:
            path = self.receipt(kit, complete=False)
            self.assertIn(kit.key, recovery.inspect(str(self.game))[1])
            self.assertIn('Choose Recover install', recovery.play_reason(str(self.game)))
            path.unlink()

    def test_missing_recovery_installer_refuses_before_plugin_backup_or_child_process(self):
        kit = kits.KITS[-1]
        path = self.receipt(kit, complete=False, plugins_restore_pending=True)
        before = path.read_bytes()
        with mock.patch.object(recovery, '_preserve_partial_plugins') as backup:
            with mock.patch.object(recovery, 'subprocess') as child:
                with self.assertRaisesRegex(ValueError, 'installer.*unavailable'):
                    recovery.recover(str(self.game), str(self.root / 'missing-checkout'), apply=True, running=lambda: False,
                                     run=child.run, say=lambda _: None)
                child.run.assert_not_called()
            backup.assert_not_called()
        self.assertEqual(path.read_bytes(), before)

    def test_new_pipboy_recovery_uses_only_fixed_installer_and_verifies_retired_journal(self):
        kit = kits.KITS[2]
        path = self.receipt(kit, complete=False)
        def uninstall(argv, **kwargs):
            self.assertEqual(argv, [sys.executable, '-I', str(ROOT / kit.installer),
                                    'uninstall', '--starfield', str(self.game)])
            path.unlink()
            return subprocess.CompletedProcess(argv, 0)
        recovery.recover(str(self.game), str(ROOT), apply=True, running=lambda: False,
                         run=uninstall, say=lambda _: None)
        self.assertFalse(path.exists())

    def test_recovery_refuses_running_or_unknown_game_state_for_new_kit(self):
        kit = kits.KITS[2]
        path = self.receipt(kit, complete=False)
        for state in [True, 'unknown']:
            with mock.patch.object(recovery, '_preserve_partial_plugins') as backup:
                with self.assertRaisesRegex(ValueError, 'Close Starfield'):
                    recovery.recover(str(self.game), str(ROOT), apply=True, running=lambda: state)
                backup.assert_not_called()
            self.assertTrue(path.exists())
