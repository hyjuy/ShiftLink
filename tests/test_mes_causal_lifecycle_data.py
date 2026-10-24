"""Pi data-contract checks for latent faults and repair boundaries."""
import json,unittest
from pathlib import Path
from scripts import mes_causal_lifecycle_validate as v
OUT=Path('/home/pi/shiftlink/analytics/validation/fault-lifecycle-20261024')
@unittest.skipUnless((OUT/'development/manifest.json').exists(),'Pi development data required')
class LifecycleDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=v.load(OUT/'development/manifest.json');cls.base=v.unzip(OUT/'development-source.json.gz')
    def case(self,kind,mode):
        c=next(c for c in self.manifest['cases'] if c['kind']==kind and c['lifecycle']==mode)
        return c,v.unzip(OUT/'development/cases'/(c['id']+'.json.gz'))
    def test_frozen_hashes_counts_and_truth_is_separate(self):
        self.assertEqual(len(self.manifest['cases']),40)
        self.assertEqual(sum(len(c['events']) for c in self.manifest['cases']),40)
        for c in self.manifest['cases']:self.assertEqual(v.sha(OUT/'development/cases'/(c['id']+'.json.gz')),c['sha256'])
        c,frames=self.case('friction','persistent')
        for frame in frames:
            self.assertEqual(set(frame),set(self.base[0])|{'config_id'});self.assertEqual(frame['active_alarms'],[])
            for key in ['repair','incident_id','lifecycle','symptom_segments']:self.assertNotIn(key,frame)
    def test_normal_streams_use_different_seeds_and_no_previous_sensor_frames(self):
        p=v.load(OUT/'normal-source-provenance.json');a,b=p['streams']['development'],p['streams']['test']
        self.assertNotEqual(a['normal_seed'],b['normal_seed']);self.assertNotEqual(a['run_id'],b['run_id'])
        self.assertEqual(a['exact_sensor_frame_overlap_with_prior'],0);self.assertEqual(b['exact_sensor_frame_overlap_with_prior'],0)
        self.assertEqual(p['development_test_sensor_overlap'],0)
    def test_intermittent_quiet_keeps_same_latent_incident(self):
        c,frames=self.case('sensor_bias','intermittent');e=c['events'][0];segments=e['symptom_segments']
        self.assertGreater(len(segments),1);self.assertEqual(segments[0][1]-segments[0][0],32)
        for a,b in zip(segments,segments[1:]):
            self.assertGreaterEqual(b[0]-a[1],4);self.assertLessEqual(b[0]-a[1],20)
            i=a[1];self.assertLess(i,e['repair'])
            self.assertEqual([m['value'] for m in frames[i]['measurements']],[m['value'] for m in self.base[c['source_offset']+i]['measurements']])
        self.assertEqual(len(c['events']),1)
    def test_repair_restores_unmodified_source_without_changing_truth_early(self):
        c,frames=self.case('sensor_bias','persistent');e=c['events'][0]
        for i in [e['start']-1,e['repair'],len(frames)-1]:
            self.assertEqual([m['value'] for m in frames[i]['measurements']],[m['value'] for m in self.base[c['source_offset']+i]['measurements']])
        self.assertEqual(e['end'],e['repair'])
    def test_progressive_bias_effect_increases_until_final_plateau(self):
        c,frames=self.case('sensor_bias','progressive');e=c['events'][0];deltas=[]
        for i in range(e['start'],e['repair']):
            raw=next(m['value'] for m in self.base[c['source_offset']+i]['measurements'] if m['equipment_id']==e['equipment_id'] and m['signal']==e['signal'])
            changed=next(m['value'] for m in frames[i]['measurements'] if m['equipment_id']==e['equipment_id'] and m['signal']==e['signal'])
            deltas.append(abs(changed-raw))
        self.assertTrue(all(b>=a-0.00001 for a,b in zip(deltas,deltas[1:])));self.assertGreater(deltas[-1],deltas[0])
    def test_progressive_sensor_stall_finishes_with_thirty_two_stuck_samples(self):
        c,frames=self.case('sensor_stuck','progressive');e=c['events'][0]
        values=[next(m['value'] for m in frames[i]['measurements'] if m['equipment_id']==e['equipment_id'] and m['signal']==e['signal']) for i in range(e['repair']-32,e['repair'])]
        self.assertEqual(len(set(values)),1)
    def test_shared_leak_strength_moves_pressure_and_flow_coherently(self):
        c,frames=self.case('hydraulic_leak','persistent');i=c['events'][0]['start']+24;e=c['events'][0]
        raw={m['signal']:m['value'] for m in self.base[c['source_offset']+i]['measurements'] if m['equipment_id']==e['equipment_id']}
        changed={m['signal']:m['value'] for m in frames[i]['measurements'] if m['equipment_id']==e['equipment_id']}
        self.assertLess(changed['hpu_pressure'],raw['hpu_pressure']);self.assertGreater(changed['hpu_flow'],raw['hpu_flow'])
if __name__=='__main__':unittest.main()