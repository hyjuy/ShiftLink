"""Deployment guard and rollback tests; no system services are changed."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('analytics_release',Path(__file__).resolve().parents[1]/'deploy/analytics/apply_release.py')
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)

class ReleaseTests(TestCase):
    def test_identical_pda_files_are_preserved_without_rewrite(self):
        with TemporaryDirectory() as directory:
            source=Path(directory)/'source';target=Path(directory)/'target';source.write_text('same');target.write_text('same');before=target.stat().st_mtime_ns
            self.assertFalse(d.replace(source,target));self.assertEqual(before,target.stat().st_mtime_ns)
            source.write_text('changed');self.assertTrue(d.replace(source,target));self.assertEqual(target.read_text(),'changed')

    def test_unit_template_must_be_in_verified_manifest(self):
        manifest={'files':{'deploy/analytics/context.service.in':'hash'},'unit_template':'deploy/analytics/context.service.in'}
        self.assertEqual(d.unit_template(manifest),'deploy/analytics/context.service.in')
        with self.assertRaises(ValueError):d.unit_template(dict(manifest,unit_template='../other'))

    def test_update_restarts_the_existing_worker(self):
        with patch.object(d,'command',return_value='') as command:
            d.activate_worker(True)
            self.assertIn(('sudo','-n','systemctl','restart',d.UNIT),[c.args for c in command.call_args_list])
        with patch.object(d,'command',return_value='') as command:
            d.activate_worker(False)
            self.assertNotIn(('sudo','-n','systemctl','restart',d.UNIT),[c.args for c in command.call_args_list])

    def test_restart_waits_until_old_pda_really_exits(self):
        with patch.object(d,'pda_pid',side_effect=[10,10,11]),patch.object(d,'get',return_value={}),patch.object(d.time,'sleep'):
            self.assertEqual(d.restart_pda(),11)

    def test_rollback_restores_exact_files_and_falls_back_if_endpoint_is_down(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);app=root/'app';backup=root/'backup';backup.mkdir()
            rel=d.TARGETS[0];old=backup/'files'/rel;old.parent.mkdir(parents=True);old.write_text('old')
            target=app/rel;target.parent.mkdir(parents=True);target.write_text('new')
            added=app/d.TARGETS[1];added.write_text('new reader')
            record=dict(present={rel:d.sha(old)},unit_present=False,unit_enabled=False,unit_active=False,
                        launch=dict(argv=['python','-m','shiftlink.pda'],environment={'DISPLAY':':0'}))
            (backup/'record.json').write_text(json.dumps(record))
            with patch.object(d,'APP',app),patch.object(d,'command',return_value=''),patch.object(d.subprocess,'run'),patch.object(d,'restart_pda',side_effect=OSError('down')),patch.object(d,'pda_pid',side_effect=[RuntimeError('none'),12]),patch.object(d.subprocess,'Popen') as start,patch.object(d.time,'sleep'),patch.object(d,'get',return_value={}):
                result=d.restore(backup)
            self.assertTrue(result['restored']);self.assertTrue(all(result['files'].values()));self.assertFalse(added.exists())
            self.assertEqual(start.call_args.args[0],record['launch']['argv'])
            self.assertEqual(start.call_args.kwargs['env']['DISPLAY'],':0')

if __name__=='__main__':main()
