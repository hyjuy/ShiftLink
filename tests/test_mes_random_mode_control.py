"""Button opt-in and observation-driven repair; run on the Pi in isolation."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from shiftlink.mes.server import MesService
from shiftlink.mes.field_draft import RESTART_ACTION

CATALOG = Path('docs/data/reference/00_plant_and_relations.json')

class RandomModeControlTests(unittest.TestCase):
    def service(self):
        s = MesService(CATALOG, seed=31, progressive_faults=True, run_nonce='button-repair')
        self.addCleanup(s.storage.close)
        return s

    def fault(self, s):
        s.control({'command':'random_mode', 'enabled':True})
        s.engine.scheduler.next_fault = 1
        s.engine.tick(145)
        self.assertIsNotNone(s.state()['recovery'])
        return s.engine.scheduler.active['equipment_id']

    def test_plain_start_matches_original_and_cannot_schedule_faults(self):
        from shiftlink.mes.engine import MesEngine
        s = self.service()
        original = MesEngine(s.engine.run, s.active_config)
        original.start()
        s.control({'command':'start'})
        for _ in range(430):
            original.tick(); s.engine.tick()
        self.assertIsNone(s.engine.scheduler.active)
        self.assertEqual(s.engine.snapshot.measurements, original.snapshot.measurements)
        self.assertEqual(s.state()['simulation_mode'], 'standard')

    def test_button_is_explicit_validated_and_does_not_reset_history(self):
        s = self.service(); run = s.engine.run.run_id
        s.control({'command':'start'}); s.tick(); seq = s.state()['sequence']
        for bad in ('true', 1, None):
            with self.assertRaises(ValueError): s.control({'command':'random_mode','enabled':bad})
        s.control({'command':'random_mode','enabled':True})
        self.assertEqual(s.state()['simulation_mode'],'progressive')
        self.assertEqual(s.state()['run_id'],run)
        self.assertEqual(s.state()['sequence'],seq)
        self.assertEqual(s.state()['line_mode'],'running')
        s.control({'command':'random_mode','enabled':False})
        self.assertEqual(s.state()['simulation_mode'],'standard')
        s.control({'command':'reset'})
        self.assertEqual(s.state()['simulation_mode'],'standard')

    def test_active_fault_cannot_be_erased_by_mode_or_scenario(self):
        s = self.service(); self.fault(s)
        fault = dict(s.engine.scheduler.active)
        for payload in ({'command':'random_mode','enabled':False}, {'command':'scenario','scenario_id':'normal'}):
            with self.assertRaises(ValueError): s.control(payload)
        self.assertEqual(s.engine.scheduler.active, fault)
        s.control({'command':'random_mode','enabled':True})
        self.assertEqual(s.engine.scheduler.active, fault)

    def test_no_repair_target_before_observed_anomaly_and_no_truth_in_state(self):
        s = self.service(); s.control({'command':'random_mode','enabled':True})
        s.engine.scheduler.next_fault = 1; s.engine.tick()
        self.assertIsNotNone(s.engine.scheduler.active)
        self.assertIsNone(s.state()['recovery'])
        for key in ('signal_targets','intensity','next_fault','hydraulic_leak','pneumatic_leak','drive_friction','cooling_loss'):
            self.assertNotIn(key,json.dumps(s.state()))

    def test_card_and_no_card_repair_through_existing_steps(self):
        for cards in ([], ['K-1002']):
            with self.subTest(cards=cards), patch('shiftlink.mes.server.SIM_LINK',True):
                s = self.service(); eq = self.fault(s); before = s.state()['active_alarms']
                out = s.resolution_start({'equipment_id':eq, 'question':'센서 이상 확인', 'card_ids':cards})
                mes = [a for a in out['action_suggestions'] if a['source']=='mes_recovery']
                self.assertEqual(len(mes),1)
                self.assertTrue(any(a['source']=='mes_restart' for a in out['action_suggestions']))
                sid = out['session_id']
                with self.assertRaises(ValueError): s.resolution_step(sid,{'action':RESTART_ACTION})
                step = s.resolution_step(sid,{'action':mes[0]['text']})
                self.assertEqual(step['mes_linked'],'recovery_action:verify')
                self.assertIsNone(s.engine.scheduler.active)
                self.assertEqual(s.state()['recovery']['stage'],'ready')
                self.assertEqual(s.state()['active_alarms'],before)
                step = s.resolution_step(sid,{'action':RESTART_ACTION})
                self.assertEqual(step['mes_linked'],'recover')
                self.assertEqual(s.state()['recovery']['stage'],'stabilizing')
                self.assertFalse(any(e.event_type=='recovered' for e in s.engine.events))
                s.engine.tick(15)
                self.assertEqual(s.state()['recovery']['stage'],'completed')
                self.assertTrue(any(e.event_type=='recovered' for e in s.engine.events))
                self.assertEqual(s.resolution_finish(sid)['verdict']['verdict'],'recovered')
                s.control({'command':'random_mode','enabled':False})
                self.assertEqual(s.state()['simulation_mode'],'standard')

    def test_bad_measurement_does_not_confirm_recovery(self):
        s = self.service(); self.fault(s)
        s.control({'command':'recovery_action','action_id':'verify'})
        s.control({'command':'recover'})
        with patch.object(s.engine.dynamics, 'values', side_effect=lambda seq,at,ms,es:tuple(replace(m,quality='bad') for m in ms)):
            s.engine.tick(15)
        self.assertEqual(s.state()['recovery']['stage'],'stabilizing')
        s.engine.tick(15)
        self.assertEqual(s.state()['recovery']['stage'],'completed')

if __name__ == '__main__': unittest.main()
