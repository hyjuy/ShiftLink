"""Button opt-in and observation-driven repair; run on the Pi in isolation."""
import json
import shutil
import subprocess
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
                self.assertEqual(s.resolution_finish(sid)['verdict'],'recovered')
                s.control({'command':'random_mode','enabled':False})
                self.assertEqual(s.state()['simulation_mode'],'standard')

    def test_early_ai_session_can_repair_before_range_crossing(self):
        s = self.service()
        s.control({'command':'random_mode','enabled':True})
        s.engine.scheduler.next_fault = 1
        s.engine.tick()
        self.assertIsNone(s.state()['recovery'])
        eq = s.engine.scheduler.active['equipment_id']
        with patch('shiftlink.mes.server.SIM_LINK',True):
            out = s.resolution_start({'equipment_id':eq})
            actions = [a for a in out['action_suggestions'] if a['source']=='mes_recovery']
            self.assertEqual(len(actions),1)
            with self.assertRaises(ValueError):
                s.resolution_step(out['session_id'], {'action':RESTART_ACTION})
            step = s.resolution_step(out['session_id'], {'action':actions[0]['text']})
            self.assertEqual(step['mes_linked'],'recovery_action:verify')
            self.assertIsNone(s.engine.scheduler.active)

    def test_wrong_equipment_does_not_repair_or_pause_other_fault(self):
        s = self.service(); eq = self.fault(s)
        wrong = next(e.equipment_id for e in s.active_config.equipment if e.active and e.equipment_id != eq)
        out = s.resolution_start({'equipment_id':wrong})
        actions = [a for a in out['action_suggestions'] if a['source']=='mes_recovery']
        self.assertEqual(len(actions),1)
        before = dict(s.engine.scheduler.active)
        with patch('shiftlink.mes.server.SIM_LINK',True), self.assertRaises(ValueError):
            s.resolution_step(out['session_id'], {'action':actions[0]['text']})
        self.assertEqual(s.engine.scheduler.active,before)
        self.assertEqual(s.state()['line_mode'],'running')

    def test_next_fault_on_same_equipment_has_fresh_repair_steps(self):
        s = self.service(); eq = self.fault(s)
        kind = s.engine.scheduler.active['kind']
        s.control({'command':'recovery_action','action_id':'verify'})
        s.control({'command':'recover'}); s.engine.tick(10)
        s.engine.scheduler.options = [(eq,kind)]
        s.engine.scheduler.next_fault = s.engine.scheduler.clock + 1
        s.engine.tick(145)
        self.assertEqual(s.state()['recovery']['stage'],'actions')
        self.assertFalse(s.state()['recovery']['actions'][0]['completed'])

    def test_old_run_session_cannot_repair_new_run(self):
        s = self.service(); eq = self.fault(s)
        out = s.resolution_start({'equipment_id':eq})
        s.control({'command':'reset'}); self.fault(s)
        fault = dict(s.engine.scheduler.active)
        with patch('shiftlink.mes.server.SIM_LINK',True), self.assertRaises(ValueError):
            s.resolution_step(out['session_id'],{'action':'모의 수리 완료 기록'})
        self.assertEqual(s.engine.scheduler.active,fault)

    def test_no_card_direct_action_before_after_and_recovery_are_saved(self):
        s = self.service(); eq = self.fault(s)
        with patch('shiftlink.mes.server.SIM_LINK',True):
            out = s.resolution_start({'equipment_id':eq,'card_ids':[],'question':'관측 이상을 직접 점검하고 조치를 기록합니다'})
            self.assertFalse(any(a['source']=='card_step' for a in out['action_suggestions']))
            sid = out['session_id']
            action = '냉각기 팬 필터를 청소하고 팬 회전 상태를 확인함'
            s.resolution_step(sid,{'action':action})
            repair = next(a['text'] for a in out['action_suggestions'] if a['source']=='mes_recovery')
            s.resolution_step(sid,{'action':repair})
            s.resolution_step(sid,{'action':RESTART_ACTION})
            s.engine.tick(15)
            self.assertEqual(s.resolution_finish(sid)['verdict'],'recovered')
            components = [c['component_id'] for c in s.state()['components'] if c['equipment_id']==eq]
            saved = s.record_handover({'handover_id':'HO-RANDOM-NO-CARD','equipment_id':eq,'memo_text':'직접 조치 후 MES 회복 확인',
                'resolution':{'session_id':sid,'symptom':'센서 이상 징후를 보고 현장 점검을 진행함','cause':'원인 모름',
                              'component_id':components[0] if components else '', 'result':'resolved'}})
            self.assertTrue(saved['draft']['mes_recovered'])
            data = s.resolution_get(sid)
            self.assertEqual(data['status'],'saved')
            record = data['data']
            self.assertEqual(record['card_ids'],[])
            self.assertEqual(record['steps'][0]['action'],action)
            self.assertEqual(record['steps'][0]['measurements'],record['before']['measurements'])
            self.assertIsNone(record['steps'][0]['mes_linked'])
            self.assertEqual([step['mes_linked'] for step in record['steps'][1:]],['recovery_action:verify','recover'])
            self.assertNotEqual(record['before']['measurements'],record['after']['measurements'])
            self.assertTrue(record['verdict']['check']['recovered'])
            [draft] = s.card_drafts()['drafts']
            self.assertEqual(draft['status'],'pending_review')
            self.assertIn(action,draft['card']['know_how'])
            self.assertEqual(draft['card']['status'],'draft')

    def test_no_card_unrepaired_attempt_is_saved_as_failed(self):
        s = self.service(); eq = self.fault(s)
        out = s.resolution_start({'equipment_id':eq,'card_ids':[]})
        sid = out['session_id']
        s.resolution_step(sid,{'action':'팬 회전 상태 점검했으나 센서 이상은 계속됨'})
        self.assertNotEqual(s.resolution_finish(sid)['verdict'],'recovered')
        components = [c['component_id'] for c in s.state()['components'] if c['equipment_id']==eq]
        saved = s.record_handover({'handover_id':'HO-RANDOM-FAILED','equipment_id':eq,'memo_text':'추가 점검 필요',
            'resolution':{'session_id':sid,'symptom':'점검 뒤에도 센서 이상이 유지됨','cause':'원인 모름',
                          'component_id':components[0] if components else '', 'result':'failed'}})
        self.assertFalse(saved['draft']['mes_recovered'])
        self.assertFalse(saved['draft']['created'])
        self.assertEqual(s.resolution_get(sid)['status'],'saved')
        self.assertEqual(s.card_drafts()['drafts'],[])

    @unittest.skipUnless(shutil.which('node'), 'Node is required for PDA DOM checks')
    def test_cardless_answer_can_start_direct_action_record(self):
        result = subprocess.run(['node','tests/pda_cardless_recovery.cjs'],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for actual PDA serialization')
    def test_no_card_actual_pda_work_report_keeps_action_and_recovery(self):
        from shiftlink.mes.configuration import to_payload
        s = self.service(); eq = self.fault(s)
        with patch('shiftlink.mes.server.SIM_LINK',True):
            out = s.resolution_start({'equipment_id':eq,'card_ids':[],'question':'이상 징후 점검'})
            sid = out['session_id']; action = '팬 필터 오염을 제거하고 회전 상태를 확인함'
            s.resolution_step(sid,{'action':action})
            repair = next(a['text'] for a in out['action_suggestions'] if a['source']=='mes_recovery')
            s.resolution_step(sid,{'action':repair})
            s.resolution_step(sid,{'action':RESTART_ACTION}); s.engine.tick(15)
            verdict = s.resolution_finish(sid)
        data = s.resolution_get(sid)['data']
        components = [c for c in s.state()['components'] if c['equipment_id']==eq]
        state = dict(sessionId=sid,phase='wrap',result='resolved',before=out['before'],verdict=verdict,
            symptom='운전 중 센서 이상을 보고 직접 점검함',cause='원인 모름',causeCustom='',components=components,
            componentId=components[0]['component_id'] if components else '',
            steps=[dict(step,at=step['simulated_at']) for step in data['steps']],
            turn=dict(question='이상 징후 점검',started=s.engine.run.started_at.isoformat(),response={}))
        source = """
const p=require('./shiftlink/mes/web/pda.js');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
p.S.equipment=input.equipment;
process.stdout.write(JSON.stringify(p.sessionRecord(input.state,input.eq)));
"""
        encoded = subprocess.run(['node','-e',source],input=json.dumps(dict(state=state,eq=eq,equipment=to_payload(s.active_config)['equipment'])),
                                 text=True,capture_output=True)
        self.assertEqual(encoded.returncode,0,encoded.stderr)
        record = json.loads(encoded.stdout)
        self.assertIn(action,record['action_steps'][0]['action'])
        self.assertIn('모의 수리 완료 기록',record['action_steps'][0]['observed_result'])
        self.assertIn('MES 정상 복귀 확인',record['normal_run_evidence'])
        self.assertEqual(record['source_session_id'],sid)
        payload = dict(handover_id='HO-PDA-RANDOM-NO-CARD',kind='work_log',equipment_id=eq,equipment_ids=[eq],memo_text='직접 조치 기록',
            required_context=dict(author='합성 검증 작업자',start_at='2026-10-25T00:00',end_at='2026-10-25T23:59',context='격리 검증'),
            work_report=dict(legacy_memo='',mes_context='',records=[record]))
        s.record_work_report(payload)
        saved = s.work_report(payload['handover_id'])['report']['work_report']['records'][0]
        self.assertEqual(saved['action_steps'],record['action_steps'])
        self.assertEqual(saved['normal_run_evidence'],record['normal_run_evidence'])
        self.assertEqual(saved['outcome'],'resolved')
        self.assertEqual(saved['normal_run_status'],'unconfirmed')
        self.assertFalse(saved['candidate'])
        self.assertTrue(s.resolution_get(sid)['data']['verdict']['check']['recovered'])

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
