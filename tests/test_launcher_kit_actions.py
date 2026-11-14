"""Fixed installer dispatch and refusal boundaries, all on synthetic local files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts/ui'))
sys.path.insert(0, str(ROOT / 'tests'))
from fo4sf.launcher import gui, instance, recovery, settings, test_kits as kits  # noqa: E402
from ba2_fixture import archive_from_tree  # noqa: E402
import make_pipboy_probe  # noqa: E402


class KitActions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / 'game'
        self.data = self.game / 'Data'
        self.data.mkdir(parents=True)
        (self.game / 'Starfield.exe').write_bytes(b'synthetic')
        self.local = self.root / 'local'
        self.plugins = self.local / 'Starfield/Plugins.txt'
        self.plugins.parent.mkdir(parents=True)
        self.original = b'# keep owner comment\r\n*Other.esm\r\n'
        self.plugins.write_bytes(self.original)
        self.env = dict(os.environ, LOCALAPPDATA=str(self.local))
        self.path = self.root / 'settings.json'
        self.values = dict(settings.defaults(), starfield=str(self.game), update='off', route='exe')
        settings.save(str(self.path), self.values)
        self.stage = self.root / 'stage'
        make_pipboy_probe.stage(str(self.stage))
        self.archive = self.stage / 'FO4SFPipboyProbe - Main.ba2'
        self.archive.write_bytes(archive_from_tree(self.stage / 'Data'))
        kits.register(kits.registry_path(self.path), 'pipboy_probe', str(self.stage))
        self.run = mock.Mock(return_value=subprocess.CompletedProcess([], 0))

    def execute(self, action='install', key='pipboy_probe', **kwargs):
        return kits.execute(key, action, str(self.path), str(kwargs.pop('repo', ROOT)), expected_folder=kwargs.pop('expected_folder',str(self.game)),
                            running=kwargs.pop('running',lambda:False), run=kwargs.pop('run',self.run),
                            environ=self.env, **kwargs)

    def refuses(self, pattern, **kwargs):
        before = self.plugins.read_bytes()
        with self.assertRaisesRegex(ValueError, pattern):
            self.execute(**kwargs)
        self.run.assert_not_called()
        self.assertEqual(self.plugins.read_bytes(), before)

    def test_actual_pipboy_prepacked_install_and_remove_preserve_owner_files(self):
        sentinel = self.data / 'Owner.txt'
        sentinel.write_bytes(b'untouched')
        self.execute(run=subprocess.run)
        row = kits.inventory(str(self.path),str(ROOT),environ=self.env)[0]
        self.assertEqual(row['state'], 'installed and active')
        self.assertEqual(row['notice'], kits.SAVE_NOTICE)
        self.assertFalse((self.data / 'Interface').exists())
        self.assertTrue((self.data / 'FO4SFPipboyProbe - Main.ba2').exists())
        # An orphaned install can be removed without rebuilding or its source stage.
        for path in self.stage.rglob('*'):
            if path.is_file(): path.unlink()
        self.execute('remove',run=subprocess.run)
        self.assertEqual(self.plugins.read_bytes(), self.original)
        self.assertEqual(sentinel.read_bytes(), b'untouched')
        self.assertEqual(sorted(p.name for p in self.data.iterdir()), ['Owner.txt'])

    def test_dispatch_is_fixed_and_uses_only_existing_archive_and_selected_profile(self):
        self.execute()
        argv = self.run.call_args.args[0]
        self.assertEqual(argv[:4], [sys.executable,'-I',str(ROOT/'scripts/ui/pipboy_probe_install.py'),'install'])
        self.assertEqual(argv[argv.index('--prepacked')+1],str(self.archive))
        self.assertEqual(self.run.call_args.kwargs['env']['LOCALAPPDATA'],str(self.local))
        self.assertNotIn('build',argv)

    def test_core_deploy_list_receipt_allows_kit_round_trip_without_changing_core(self):
        core = self.data / 'FO4Port.esm'
        core.write_bytes(b'synthetic core')
        manifest = self.data / 'FO4Port.deploy.json'
        # Core deploy stores path names separately from artifact identities; kit
        # installers instead store a path-to-digest object in their files field.
        manifest.write_text(json.dumps({'files': [core.name], 'published_files': [core.name],
            'artifacts': {core.name: {'sha256': '0' * 64, 'size': len(core.read_bytes())}},
            'plugins_txt': str(self.plugins), 'plugins_added': [], 'plugins_replaced': [],
            'complete': True}), encoding='utf-8')
        before = {p: p.read_bytes() for p in (core, manifest, self.plugins)}
        model = gui.SettingsModel(str(ROOT/'scripts/launcher.py'), str(self.path))
        self.assertEqual(model.play_reason(model.saved, str(self.game), [], windows=True), '')
        for action in ('install', 'remove'):
            argv = model.kit_command(action, model.saved, 'pipboy_probe', [], windows=True)
            self.assertEqual(argv[4:6], ['tests', action])
            self.execute(action, run=subprocess.run)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(set(self.data.iterdir()), {core, manifest})

    def test_running_unknown_exception_and_late_game_start_refuse(self):
        for callback in [lambda:True,lambda:None,lambda:'unknown',mock.Mock(side_effect=OSError('tasklist failed')),
                         mock.Mock(side_effect=[False,True])]:
            self.refuses('Starfield|processes',running=callback)

    def test_stale_selected_game_refuses(self):
        self.refuses('location changed',expected_folder=str(self.root/'different'))

    def test_interrupted_or_corrupt_other_kit_blocks_before_dispatch(self):
        receipt = self.data/'FO4SFPlanetProbe.install.json'
        for payload in [b'{"complete":false}',b'{']:
            receipt.write_bytes(payload)
            self.refuses('incomplete|unreadable')
            self.assertEqual(receipt.read_bytes(),payload)

    def test_non_utf8_plugin_list_refuses_before_installer_or_journal_changes(self):
        self.plugins.write_bytes(b"\xff\xfeunreadable")
        before = sorted(self.data.iterdir())
        self.refuses("Plugins.txt.*UTF-8")
        self.assertEqual(sorted(self.data.iterdir()), before)
        self.assertEqual(self.plugins.read_bytes(), b"\xff\xfeunreadable")

    def test_unreadable_plugin_list_has_a_path_free_refusal(self):
        original_open = open
        def denied(path, *args, **kwargs):
            if os.fspath(path) == str(self.plugins):
                raise PermissionError(13, "denied", str(self.plugins))
            return original_open(path, *args, **kwargs)
        with mock.patch("builtins.open", side_effect=denied):
            with self.assertRaisesRegex(ValueError, "Plugins.txt.*permissions") as refused:
                self.execute()
        self.assertNotIn(str(self.root), str(refused.exception))
        self.run.assert_not_called()
        self.assertEqual(self.plugins.read_bytes(), self.original)

    def test_late_encoding_change_refuses_and_preserves_the_new_bytes(self):
        def running():
            if running.calls:
                self.plugins.write_bytes(b"\xff")
            running.calls += 1
            return False
        running.calls = 0
        with self.assertRaisesRegex(ValueError, "Plugins.txt.*UTF-8"):
            self.execute(running=running)
        self.run.assert_not_called()
        self.assertEqual(self.plugins.read_bytes(), b"\xff")
        self.assertEqual(list(self.data.iterdir()), [])

    def test_missing_stage_plugin_and_prebuilt_archive_refuse_without_build(self):
        self.archive.unlink()
        self.refuses('prebuilt.*missing')
        (self.stage/'FO4SFPipboyProbe.esm').unlink()
        self.refuses('staged.*missing')

    def test_unknown_kit_or_action_and_unregistered_kit_refuse(self):
        self.refuses('Unknown',key='foreign')
        self.refuses('Unknown',action='build')
        self.refuses('neither staged nor installed',key='quest_probe')

    def test_missing_installer_and_remove_not_installed_refuse(self):
        stage = self.root/'rads'
        stage.mkdir()
        (stage/'FO4SFRadsProbe.esm').write_bytes(b'synthetic')
        kits.register(kits.registry_path(self.path),'rads_probe',str(stage))
        self.refuses('installer.*unavailable',key='rads_probe',repo=self.root/'missing-checkout')
        self.refuses('not installed',action='remove')

    def test_double_install_refuses(self):
        self.execute(run=subprocess.run)
        self.refuses('already installed')

    def test_installer_failure_is_reported_and_journal_preserved(self):
        receipt = self.data/'FO4SFPipboyProbe.install.json'
        def fail(*args,**kwargs):
            receipt.write_text('{"complete":false}')
            return subprocess.CompletedProcess(args[0],4)
        with self.assertRaisesRegex(ValueError,'exit 4.*journal'):
            self.execute(run=fail)
        self.assertEqual(receipt.read_text(),'{"complete":false}')

    def test_late_settings_or_registry_changes_refuse(self):
        for change in ['settings','registry']:
            def running():
                if running.calls:
                    if change == 'settings':
                        settings.save(str(self.path),dict(self.values, route='steam'))
                    else:
                        Path(kits.registry_path(self.path)).write_text('{"schema":1,"kits":{}}')
                running.calls += 1
                return False
            running.calls = 0
            self.refuses('changed',running=running)
            settings.save(str(self.path), self.values)
            kits.register(kits.registry_path(self.path),'pipboy_probe',str(self.stage))

    def test_late_journal_change_refuses(self):
        def running():
            if running.calls:
                (self.data/'FO4SFPlanetProbe.install.json').write_text('{"complete":false}')
            running.calls += 1
            return False
        running.calls = 0
        self.refuses('incomplete',running=running)

    def test_missing_game_or_local_profile_refuses(self):
        (self.game/'Starfield.exe').unlink()
        self.refuses('existing Starfield')
        (self.game/'Starfield.exe').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'LOCALAPPDATA'):
            kits.context(self.values,{})

    def test_instance_inventory_uses_its_profile_and_does_not_create_normal_plugin_list(self):
        local = Path(instance.local_dir(str(self.game)))
        p = local/'Starfield/Plugins.txt'
        p.parent.mkdir(parents=True)
        p.write_bytes(b'# instance profile')
        values = dict(self.values,instance=str(self.game))
        with mock.patch.object(instance,'check_ready'):
            folder, plugins, env = kits.context(values,self.env)
        self.assertEqual(plugins,str(p))
        self.assertEqual(env['LOCALAPPDATA'],str(local))
        self.assertEqual(self.plugins.read_bytes(),self.original)

    def test_registration_refuses_wrong_stage_and_preserves_existing_registry(self):
        path = Path(kits.registry_path(self.path))
        before = path.read_bytes()
        for key, folder in [('unknown',str(self.stage)),('pipboy_probe',str(self.root/'absent'))]:
            with self.assertRaises(ValueError): kits.register(path,key,folder)
            self.assertEqual(path.read_bytes(),before)

    def test_model_refuses_unsaved_stale_missing_platform_and_process_state(self):
        model = gui.SettingsModel(str(ROOT/'scripts/launcher.py'),str(self.path))
        for raw,pids,windows in [(dict(model.saved,starfield='changed'),[],True),
                                  (model.saved,None,True),(model.saved,[42],True),(model.saved,[],False)]:
            with self.assertRaises(ValueError):
                model.kit_command('install',raw,'pipboy_probe',pids,windows=windows)
        settings.save(str(self.path),dict(self.values,route='steam'))
        with self.assertRaisesRegex(ValueError,'Save or reload'):
            model.kit_command('remove',model.saved,'pipboy_probe',[],windows=True)

    def test_model_uses_selected_settings_and_refuses_recovery_state(self):
        model = gui.SettingsModel(str(ROOT/'scripts/launcher.py'),str(self.path))
        argv = model.kit_command('install',model.saved,'pipboy_probe',[],windows=True)
        self.assertEqual(argv[4:6],['tests','install'])
        self.assertEqual(argv[argv.index('--settings')+1],str(self.path))
        self.assertEqual(argv[argv.index('--starfield')+1],str(self.game))
        (self.data/'FO4SFPlanetProbe.install.json').write_text('{"complete":false}')
        with self.assertRaisesRegex(ValueError,'Recover install'):
            model.kit_command('remove',model.saved,'pipboy_probe',[],windows=True)

    def test_real_cli_lists_and_registers_without_mutating_game(self):
        argv = [sys.executable,'-I',str(ROOT/'scripts/launcher.py'),'tests']
        env = self.env
        result = subprocess.run(argv+['list','--settings',str(self.path)],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertEqual(json.loads(result.stdout)[0]['state'],'not installed')
        result = subprocess.run(argv+['register','--kit','pipboy_probe','--stage',str(self.stage),
                                    '--settings',str(self.path)],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertEqual(list(self.data.iterdir()),[])
