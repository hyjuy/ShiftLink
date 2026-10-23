"""Production binding guards for the separately frozen normal profile."""
import copy,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,main
from scripts.mes_causal_pda_service import BoundSource,AdvisorySession
from scripts.mes_causal_context import ContextDetector
from tests.test_mes_causal_context import config,profile,source_rows
from tests.test_mes_causal_pda_service import source_config

class ContextBindingTests(TestCase):
    def test_cli_pins_profile_and_preserves_external_stop_switch(self):
        import hashlib,signal,sys
        from unittest.mock import patch
        from scripts import mes_causal_pda_service as m
        with TemporaryDirectory() as directory:
            root=Path(directory);settings=root/'settings.json';source=root/'source.json';normal=root/'profile.json';output=root/'latest.json';stop=root/'operator-STOP'
            settings.write_text(json.dumps(config()));source.write_text(json.dumps(source_config()));normal.write_text(json.dumps(profile()));stop.touch()
            argv=['service','--mes-url','http://source','--settings',str(settings),'--source-config',str(source),'--normal-profile',str(normal),'--normal-profile-sha256',hashlib.sha256(normal.read_bytes()).hexdigest(),'--stop-file',str(stop),'--state-dir',str(root/'new-state'),'--output',str(output),'--once']
            old={n:signal.getsignal(n) for n in (signal.SIGINT,signal.SIGTERM)}
            try:
                with patch.object(sys,'argv',argv),patch.object(m,'SETTINGS_SHA256',hashlib.sha256(settings.read_bytes()).hexdigest()),patch.object(m,'get_json',return_value=source_rows(1)[0]):m.main()
                result=json.loads(output.read_text());self.assertEqual(result['status'],'disabled');self.assertFalse(result['operational_notifications']);self.assertFalse((root/'new-state/checkpoint.json').exists())
                normal.write_text('{}')
                with patch.object(sys,'argv',argv),patch.object(m,'SETTINGS_SHA256',hashlib.sha256(settings.read_bytes()).hexdigest()):
                    with self.assertRaisesRegex(ValueError,'normal profile hash'):m.main()
            finally:
                for n,h in old.items():signal.signal(n,h)

    def test_opt_in_only_and_profile_is_in_checkpoint_identity(self):
        settings=config();before=copy.deepcopy(settings);old=BoundSource(settings,source_config());new=BoundSource(settings,source_config(),normal_profile=profile())
        self.assertIsInstance(new.new_detector(),ContextDetector);self.assertNotEqual(old.fingerprint,new.fingerprint);self.assertEqual(settings,before)
        wrong=profile();wrong['source_config_id']='different'
        with self.assertRaises(ValueError):BoundSource(settings,source_config(),normal_profile=wrong)
    def test_context_history_roundtrip_preserves_normal_and_stall_decisions(self):
        with TemporaryDirectory() as directory:
            b=BoundSource(config(),source_config(),normal_profile=profile());path=Path(directory)/'state.json';a=AdvisorySession(b,path)
            data=source_rows(160)
            for f in data[:100]:a.feed(f,b.config_id)
            a.flush();saved=a.detector.context_state();a=AdvisorySession(b,path);self.assertEqual(a.detector.context_state(),saved)
            self.assertEqual(a.report(data[99])['items'],[])
            with self.assertRaises(ValueError):AdvisorySession(BoundSource(config(),source_config()),path)
    def test_old_model_state_cannot_silently_enter_new_profile(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';old=AdvisorySession(BoundSource(config(),source_config()),path)
            for f in source_rows(80):old.feed(f,old.binding.config_id)
            old.flush()
            with self.assertRaises(ValueError):AdvisorySession(BoundSource(config(),source_config(),normal_profile=profile()),path)

if __name__=='__main__':main()
