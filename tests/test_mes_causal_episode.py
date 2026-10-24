"""Pi regression for three consumed duplicate cases; original input stays intact."""
import gzip,json,os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.mes_causal_pda_service import AdvisorySession,BoundSource as Source
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=Path(os.environ.get('SHIFTLINK_RANDOM_INJECTION_ROOT','/home/pi/shiftlink/analytics/validation/random-injection-20261024'))

@unittest.skipUnless((FIXTURES/'plan.json').exists(),'consumed Pi random-injection fixtures required')
class ConsumedDuplicates(unittest.TestCase):
    def check_case(self,name):
        plan=json.loads((FIXTURES/'plan.json').read_text());case=next(c for c in plan['cases'] if c['id']==name)
        settings=json.loads((ROOT/'docs/research/evidence/mes-causal-v14c-20261023/settings.json').read_text())
        config=json.loads((ROOT/'deploy/analytics/source-config.json').read_text());profile=json.loads((ROOT/'deploy/analytics/normal-profile.json').read_text())
        binding=Source(settings,config,normal_profile=profile)
        with gzip.open(FIXTURES/'cases'/(name+'.json.gz'),'rt') as f:frames=json.load(f)
        with TemporaryDirectory() as tmp:
            session=AdvisorySession(binding,Path(tmp)/'checkpoint.json');events=[]
            for frame in frames:
                if case['event']['equipment_id'] in session.feed(frame,binding.config_id):events.append(frame['sequence'])
        self.assertEqual(events[0],{'friction-02':149,'friction-03':133,'variance-01':136}[name],'first notice changed')
        self.assertEqual(len(events),1,'same injected incident produced multiple first notices: '+str(events))
    def test_friction_thermal_then_level_is_one_notice(self):self.check_case('friction-02')
    def test_second_friction_thermal_then_level_is_one_notice(self):self.check_case('friction-03')
    def test_variance_dip_is_not_complete_recovery(self):self.check_case('variance-01')

if __name__=='__main__':unittest.main()
