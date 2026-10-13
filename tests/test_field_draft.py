"""현장 해결 기록 → 카드 초안: 빌더 규칙, 인계 저장과의 연결, GET 목록."""
import json
import tempfile
import threading
import unittest
from dataclasses import asdict, replace
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from shiftlink.agent.schemas import KnowledgeCard
from shiftlink.mes import configuration
from shiftlink.mes.field_draft import PLACEHOLDER, build_draft
from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import HandoverConflictError, MesStorage

CATALOG = Path('docs/data/reference/00_plant_and_relations.json')
NOW = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)


def hpu_config():
    return configuration.from_catalog(json.loads(CATALOG.read_text(encoding='utf-8')))


def hot_evidence(value=66.5, *, quality='good'):
    return {'equipment_id': 'EQ-0001', 'equipment_code': 'HPU-01', 'simulated_at': '2026-10-13T08:59:00+09:00',
            'measurements': [
                {'equipment_id': 'EQ-0001', 'signal': 'hpu_oil_temp', 'value': value, 'unit': 'degC',
                 'quality': quality, 'used_for_conditions': True},
                {'equipment_id': 'EQ-0001', 'signal': 'hpu_pressure', 'value': 150.0, 'unit': 'bar',
                 'quality': 'good', 'used_for_conditions': True}],
            'alarms': []}


def resolution(**overrides):
    base = {'question': '작동유 온도가 높아요', 'symptom': '작동유 온도 경보, 냉각기 소음이 평소보다 큼',
            'actions': ['냉각기 팬 필터 청소', '작동유 온도 재확인'], 'result': 'resolved',
            'verification': '온도가 50도 아래로 내려갔고 경보가 꺼짐', 'evidence': hot_evidence()}
    base.update(overrides)
    return base


class FieldDraftBuilderTests(unittest.TestCase):
    def test_resolved_high_oil_temp_becomes_schema_valid_draft(self):
        out = build_draft('HO-1', resolution(), hpu_config(), 'EQ-0001', 'K-7000', NOW)
        self.assertEqual(out['status'], 'pending_review')
        card = out['card']
        KnowledgeCard.model_validate(card)
        self.assertEqual((card['status'], card['grade'], card['confidence'], card['split']), ('draft', 'L0', 0.0, 'dev'))
        self.assertEqual(card['tacit_type'], 'T3')
        self.assertEqual((card['equipment'], card['mes_equipment_id']), ('HPU', 'EQ-0001'))
        self.assertEqual(card['conditions'], [{'signal': 'hpu_oil_temp_state', 'op': '==', 'value': 'high', 'unit': None}])
        steps = card['type_payload']['steps']
        self.assertEqual([s['step_id'] for s in steps], ['ST-01', 'ST-02'])
        self.assertEqual(steps[1]['expected_result'], '온도가 50도 아래로 내려갔고 경보가 꺼짐')
        self.assertEqual(steps[0]['expected_result'], '현장 기록에 결과 없음 — 검수 보완')
        self.assertEqual(out['review_flags']['placeholder_steps'], ['ST-01'])
        self.assertEqual(card['provenance']['sources'], [{'source_id': 'HO-1', 'locator': 'handover'}])
        self.assertFalse(card['safety_flag'])

    def test_state_is_derived_from_config_not_from_client(self):
        # 클라이언트가 quality를 나쁘게 보내면 상태 조건에서 빠져야 하고, 범위 안 값은 high가 될 수 없다.
        out = build_draft('HO-2', resolution(evidence=hot_evidence(value=40.0)), hpu_config(), 'EQ-0001', 'K-7000', NOW)
        self.assertEqual(out['card']['conditions'], [])
        self.assertTrue(out['review_flags']['no_out_of_range_signal'])
        out = build_draft('HO-3', resolution(evidence=hot_evidence(value=66.5, quality='bad')), hpu_config(),
                          'EQ-0001', 'K-7000', NOW)
        self.assertEqual(out['card']['conditions'], [])

    def test_failed_makes_no_draft(self):
        out = build_draft('HO-4', resolution(result='failed', actions=[], verification=''), hpu_config(),
                          'EQ-0001', 'K-7000', NOW)
        self.assertEqual(out, {'status': 'attempt_only'})

    def test_safety_words_are_flagged_not_invented_as_basis(self):
        out = build_draft('HO-5', resolution(actions=['차단기 내리고 커버 열어 필터 교체']), hpu_config(),
                          'EQ-0001', 'K-7000', NOW)
        card = out['card']
        self.assertFalse(card['safety_flag'])
        self.assertNotIn('safety_basis', card)
        self.assertEqual(out['review_flags']['needs_safety_review'], ['차단기', '커버'])

    def test_temporary_without_verification_still_valid_t3(self):
        out = build_draft('HO-6', resolution(result='temporary', verification=''), hpu_config(),
                          'EQ-0001', 'K-7000', NOW)
        self.assertEqual(out['status'], 'pending_review')
        self.assertEqual(out['card']['tacit_type'], 'T3')
        self.assertEqual(out['review_flags']['placeholder_steps'], ['ST-01', 'ST-02'])

    def test_invalid_card_is_kept_with_errors(self):
        # 설비 코드 접두어가 스키마 Equipment에 없으면 초안은 invalid로 보관되고 오류가 남는다.
        cfg = hpu_config()
        odd = replace(cfg, equipment=tuple(replace(e, code='XYZ-01') if e.equipment_id == 'EQ-0001' else e
                                           for e in cfg.equipment))
        out = build_draft('HO-7', resolution(), odd, 'EQ-0001', 'K-7000', NOW)
        self.assertEqual(out['status'], 'invalid')
        self.assertTrue(any(err.startswith('equipment') for err in out['review_flags']['validation_errors']))
        self.assertEqual(out['card']['card_id'], 'K-7000')

    def test_rejects_bad_input_before_anything_is_stored(self):
        cfg = hpu_config()
        with self.assertRaises(ValueError):
            build_draft('HO-9', resolution(result='maybe'), cfg, 'EQ-0001', 'K-7000', NOW)
        with self.assertRaises(ValueError):
            build_draft('HO-9', resolution(actions=[]), cfg, 'EQ-0001', 'K-7000', NOW)
        with self.assertRaises(ValueError):
            build_draft('HO-9', resolution(verification='', result='resolved'), cfg, 'EQ-0001', 'K-7000', NOW)
        with self.assertRaises(ValueError):
            build_draft('HO-9', resolution(), cfg, 'EQ-9999', 'K-7000', NOW)
        bad_signal = hot_evidence()
        bad_signal['measurements'][0]['signal'] = 'not_a_signal'
        with self.assertRaises(ValueError):
            build_draft('HO-9', resolution(evidence=bad_signal), cfg, 'EQ-0001', 'K-7000', NOW)
        bad_value = hot_evidence(value=float('nan'))
        with self.assertRaises(ValueError):
            build_draft('HO-9', resolution(evidence=bad_value), cfg, 'EQ-0001', 'K-7000', NOW)

    def test_step_results_fill_their_own_steps(self):
        out = build_draft('HO-10', resolution(actions=[{'action': '냉각기 팬 필터 청소', 'result': '팬 바람 세짐'},
                                                       '작동유 온도 재확인']), hpu_config(), 'EQ-0001', 'K-7000', NOW)
        steps = out['card']['type_payload']['steps']
        self.assertEqual([s['expected_result'] for s in steps], ['팬 바람 세짐', '온도가 50도 아래로 내려갔고 경보가 꺼짐'])
        self.assertEqual(out['review_flags']['placeholder_steps'], [])
        with self.assertRaises(ValueError):
            build_draft('HO-10', resolution(actions=[{'action': 'x', 'note': 'y'}]), hpu_config(), 'EQ-0001', 'K-7000', NOW)

    def test_thin_and_temporary_records_are_marked(self):
        thin = build_draft('HO-11', resolution(symptom='뜨거움', actions=['팬 봄'], verification='고침'),
                           hpu_config(), 'EQ-0001', 'K-7000', NOW)
        self.assertEqual(thin['status'], 'pending_review')
        self.assertEqual(thin['review_flags']['thin_record'], ['증상이 짧음', '조치가 짧음', '해결 근거가 짧음'])
        self.assertIn('기록 빈약: 증상이 짧음, 조치가 짧음, 해결 근거가 짧음', thin['review_flags']['completeness']['missing'])
        temp = build_draft('HO-12', resolution(result='temporary', verification=''), hpu_config(), 'EQ-0001', 'K-7000', NOW)
        self.assertTrue(temp['card']['title'].startswith('[임시조치] HPU-01 '))
        self.assertIn('MES로 확인된 해결 기록', temp['review_flags']['completeness']['missing'])

    def test_completeness_lists_blanks_and_never_ready_from_one_record(self):
        out = build_draft('HO-13', resolution(actions=['차단기 재투입 후 냉각기 팬 확인', '작동유 온도 재확인']),
                          hpu_config(), 'EQ-0001', 'K-7000', NOW)
        done = out['review_flags']['completeness']
        # 빌더만 부르면 MES 확인이 없다 → 해결 기록으로 세지 않고 불일치로 표시한다.
        self.assertEqual(done['missing'], ['단계 결과 ST-01', 'MES로 확인된 해결 기록'])
        self.assertEqual(done['operator'], ['부품 확인', '시나리오 확인', '안전 근거', '해결 표기와 MES 불일치 HO-13'])
        self.assertEqual((done['resolved_records'], done['ready']), (0, False))


class FieldDraftServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.service = MesService(CATALOG, MesStorage(Path(self.directory.name) / 'mes.sqlite3'))

    def tearDown(self):
        self.service.storage.close()
        self.directory.cleanup()

    def handover(self, handover_id, **extra):
        # 실행 정보가 없는 근거(hot_evidence)는 실제 흐름처럼 '과열 중 질의 → MES 조치·복구' 뒤 저장한 것으로 만든다.
        res = extra.get('resolution')
        if res and res.get('evidence') and 'run_id' not in res['evidence']:
            self.fault()
            asked = self.evidence_now()
            self.recover()
            extra['resolution'] = {**res, 'evidence': {**res['evidence'], 'run_id': asked['run_id'],
                                                       'simulated_at': asked['simulated_at']}}
        return {'handover_id': handover_id, 'memo_text': '작동유 온도 경보 처리', 'equipment_id': 'EQ-0001',
                'required_context': {}, 'attempts': [], 'observations': [], **extra}

    def count(self):
        return self.service.storage.connection.execute('SELECT COUNT(*) FROM card_drafts').fetchone()[0]

    def test_handover_creates_one_pending_draft_and_retry_does_not_duplicate(self):
        body = self.handover('HO-100', resolution=resolution())
        first = self.service.record_handover(body)
        self.assertEqual(first['draft'], {'created': True, 'reason': 'pending_review', 'mes_recovered': True})
        again = self.service.record_handover(body)
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['draft'], {'created': False, 'reason': 'already_exists', 'mes_recovered': True})
        self.assertEqual(self.count(), 1)
        drafts = self.service.card_drafts()['drafts']
        self.assertEqual([d['draft_id'] for d in drafts], ['K-7000'])
        self.assertEqual(drafts[0]['status'], 'pending_review')

    def test_conflict_creates_no_draft(self):
        self.service.record_handover(self.handover('HO-101', resolution=resolution()))
        with self.assertRaises(HandoverConflictError):
            self.service.record_handover(self.handover('HO-101', memo_text='다른 내용', resolution=resolution()))
        self.assertEqual(self.count(), 1)

    def test_failed_and_plain_handover_store_no_draft(self):
        failed = self.service.record_handover(self.handover('HO-102', resolution=resolution(result='failed', actions=[], verification='')))
        self.assertEqual(failed['draft'], {'created': False, 'reason': 'attempt_only', 'mes_recovered': True})
        plain = self.service.record_handover(self.handover('HO-103'))
        self.assertNotIn('draft', plain)
        self.assertEqual(self.count(), 0)

    def test_invalid_resolution_rejected_before_handover_is_saved(self):
        with self.assertRaises(ValueError):
            self.service.record_handover(self.handover('HO-104', resolution=resolution(symptom='')))
        self.assertIsNone(self.service.storage.get_handover('HO-104'))
        self.assertEqual(self.count(), 0)

    def test_card_ids_are_sequential_in_field_range(self):
        self.service.record_handover(self.handover('HO-105', resolution=resolution()))
        # 조치가 겹치지 않으면 같은 이상이라도 다른 원인 후보라 새 초안이다.
        self.service.record_handover(self.handover('HO-106', resolution=resolution(actions=['작동유 보충', '유면 게이지 확인'])))
        self.assertEqual([d['draft_id'] for d in self.service.card_drafts()['drafts']], ['K-7000', 'K-7001'])

    def test_drafts_do_not_reach_kb_cards(self):
        self.service.record_handover(self.handover('HO-107', resolution=resolution()))
        kb = json.loads(Path('docs/data/knowledge_cards/kb/kb_cards.json').read_text(encoding='utf-8'))['cards']
        self.assertNotIn('K-7000', {card['card_id'] for card in kb})

    def draft(self):
        return self.service.card_drafts()['drafts']

    def test_matching_record_fills_blank_instead_of_new_draft(self):
        self.service.record_handover(self.handover('HO-300', resolution=resolution()))
        second = resolution(actions=[{'action': '냉각기 팬 필터 청소', 'result': '팬 풍량 회복'}], verification='유온 52도로 내려감')
        body = self.handover('HO-301', resolution=second)
        out = self.service.record_handover(body)
        self.assertEqual(out['draft'], {'created': False, 'reason': 'supporting', 'mes_recovered': True})
        [row] = self.draft()
        steps = row['card']['type_payload']['steps']
        self.assertEqual(steps[0]['expected_result'], '팬 풍량 회복')
        self.assertNotIn(PLACEHOLDER, [s['expected_result'] for s in steps])
        done = row['review_flags']['completeness']
        self.assertEqual((done['missing'], done['resolved_records'], done['ready']), ([], 2, True))
        self.assertEqual([s['source_id'] for s in row['card']['provenance']['sources']], ['HO-300', 'HO-301'])
        KnowledgeCard.model_validate(row['card'])
        again = self.service.record_handover(body)
        self.assertEqual(again['draft'], {'created': False, 'reason': 'already_exists', 'mes_recovered': True})
        self.assertEqual(len(self.draft()[0]['review_flags']['records']), 2)

    def test_different_cause_same_condition_stays_separate(self):
        self.service.record_handover(self.handover('HO-310', resolution=resolution()))
        self.service.record_handover(self.handover('HO-311', resolution=resolution(actions=['작동유 보충', '유면 게이지 확인'])))
        self.assertEqual(len(self.draft()), 2)

    def test_failed_same_action_is_contradicting_and_blocks_ready(self):
        self.service.record_handover(self.handover('HO-320', resolution=resolution(
            actions=[{'action': '냉각기 팬 필터 청소', 'result': '팬 풍량 회복'}, '작동유 온도 재확인'])))
        self.service.record_handover(self.handover('HO-321', resolution=resolution(
            actions=['냉각기 팬 필터 청소', '작동유 온도 재확인'], verification='온도 49도, 경보 해제')))
        out = self.service.record_handover(self.handover('HO-322', resolution=resolution(
            result='failed', actions=['냉각기 팬 필터 청소'], verification='')))
        self.assertEqual(out['draft'], {'created': False, 'reason': 'contradicting', 'mes_recovered': True})
        done = self.draft()[0]['review_flags']['completeness']
        self.assertEqual((done['resolved_records'], done['contradicting_records'], done['ready']), (2, 1, False))

    def test_temporary_then_resolved_drops_temporary_mark(self):
        self.service.record_handover(self.handover('HO-330', resolution=resolution(result='temporary', verification='')))
        self.service.record_handover(self.handover('HO-331', resolution=resolution()))
        [row] = self.draft()
        self.assertFalse(row['card']['title'].startswith('[임시조치]'))
        self.assertNotIn('temporary', row['review_flags'])

    def test_each_new_result_fills_its_best_matching_step_once(self):
        # '확인' 같은 공통어만 겹치는 단계에 다른 단계의 결과가 들어가면 안 된다.
        self.service.record_handover(self.handover('HO-340', resolution=resolution(
            actions=['쿨러 팬 전원 차단기 트립 확인 후 재투입', '팬 회전 확인', '유온 추이 확인'], verification='유온 52도')))
        self.service.record_handover(self.handover('HO-341', resolution=resolution(
            actions=[{'action': '쿨러 팬 차단기 트립 확인, 재투입', 'result': '팬 다시 돎'},
                     {'action': '팬 회전 방향·소음 확인', 'result': '정방향, 이상음 없음'}, '유온 추이 확인'],
            verification='30분 뒤 유온 54도')))
        steps = self.draft()[0]['card']['type_payload']['steps']
        self.assertEqual([s['expected_result'] for s in steps], ['팬 다시 돎', '정방향, 이상음 없음', '유온 52도'])

    def test_incidental_signals_are_pruned_as_records_accumulate(self):
        # 실제 스냅샷처럼 압력도 함께 낮았던 첫 기록 → 두 번째 기록에는 유온만 → 공통 조건(유온)만 남는다.
        first = hot_evidence()
        first['measurements'][1]['value'] = 130.0
        out = self.service.record_handover(self.handover('HO-350', resolution=resolution(evidence=first)))
        [row] = self.draft()
        self.assertEqual(len(row['card']['conditions']), 2)
        self.assertTrue(row['card']['title'].startswith('HPU-01 유압유 온도 높음 외 1 — '))
        out = self.service.record_handover(self.handover('HO-351', resolution=resolution()))
        self.assertEqual(out['draft']['reason'], 'supporting')
        self.assertEqual(self.draft()[0]['card']['conditions'],
                         [{'signal': 'hpu_oil_temp_state', 'op': '==', 'value': 'high', 'unit': None}])

    def test_generic_word_alone_does_not_fill_a_step(self):
        # '팬 회전 확인'과 '유온 추이 확인'은 '확인'만 겹친다 → 결과를 옮기지 않는다.
        self.service.record_handover(self.handover('HO-360', resolution=resolution(
            actions=['쿨러 팬 전원 차단기 트립 확인 후 재투입', '팬 회전 확인', '20분 운전하며 유온 추이 확인'], verification='유온 52도')))
        self.service.record_handover(self.handover('HO-361', resolution=resolution(
            actions=[{'action': '쿨러 팬 차단기 트립 확인, 재투입', 'result': '팬 다시 돎'}, '유온 추이 확인'],
            verification='30분 뒤 유온 54도')))
        steps = self.draft()[0]['card']['type_payload']['steps']
        self.assertEqual([s['expected_result'] for s in steps], ['팬 다시 돎', PLACEHOLDER, '유온 52도'])

    def fault(self):
        # 유압유 과열 시나리오: 라인이 서고 유온 78, 경보 AL-HYD-HOT.
        self.service.control({'command': 'start'})
        self.service.engine.tick(30)
        self.service.control({'command': 'scenario', 'scenario_id': 'hydraulic_overheat'})
        self.service.engine.tick(5)

    def recover(self):
        for action in ('inspect', 'repair', 'verify'):
            self.service.control({'command': 'recovery_action', 'action_id': action})
        self.service.control({'command': 'recover'})
        self.service.engine.tick(5)

    def evidence_now(self):
        s = asdict(self.service.engine.snapshot)
        return {'equipment_id': 'EQ-0001', 'run_id': s['run_id'], 'simulated_at': s['simulated_at'].isoformat(),
                'measurements': [m for m in s['measurements'] if m['equipment_id'] == 'EQ-0001']}

    def test_reset_after_query_is_not_a_recovery(self):
        # '새 시뮬레이션 시작'으로 값이 정상처럼 보여도 복구가 아니다(10/13 실측).
        self.fault()
        asked = self.evidence_now()
        self.service.control({'command': 'reset'})
        self.service.control({'command': 'start'})
        self.service.engine.tick(30)
        out = self.service.record_handover(self.handover('HO-430', resolution=resolution(evidence=asked)))
        self.assertFalse(out['draft']['mes_recovered'])
        self.assertIn('MES 확인: 확인 불가 — 질의 뒤 시뮬레이션이 새로 시작됨', self.draft()[0]['card']['rationale'])
        # 같은 실행에서 조치 없이 정상 운전처럼 보이는 경우도 복구 기록이 없으면 인정하지 않는다.
        self.fault()
        asked = self.evidence_now()
        out = self.service.record_handover(self.handover('HO-431', resolution=resolution(evidence=asked)))
        self.assertFalse(out['draft']['mes_recovered'])

    def test_mes_confirms_resolution_only_after_real_recovery(self):
        self.fault()
        at_fault = self.evidence_now()
        # 아직 고장 중인데 '해결'로 저장 → MES 불일치, 해결 기록으로 세지 않는다.
        early = self.service.record_handover(self.handover('HO-400', resolution=resolution(evidence=at_fault)))
        self.assertFalse(early['draft']['mes_recovered'])
        [row] = self.draft()
        conditions = {c['signal'] for c in row['card']['conditions']}
        self.assertIn('hpu_oil_temp_state', conditions)
        self.assertNotIn('hpu_flow_state', conditions)  # 멈춰서 0인 유량은 조건이 아니다
        self.assertIn('MES 확인: 아직 이상', row['card']['rationale'])
        self.assertEqual(row['review_flags']['completeness']['resolved_records'], 0)
        self.assertIn('해결 표기와 MES 불일치 HO-400', row['review_flags']['completeness']['operator'])
        # 조치 3단계 + 재가동 뒤 저장 → 정상 복귀가 확인된 해결로 센다.
        self.recover()
        late = self.service.record_handover(self.handover('HO-401', resolution=resolution(evidence=at_fault)))
        self.assertEqual(late['draft'], {'created': False, 'reason': 'supporting', 'mes_recovered': True})
        row = self.draft()[0]
        self.assertIn('MES 확인: 정상 복귀', row['card']['rationale'])
        self.assertEqual(row['review_flags']['completeness']['resolved_records'], 1)

    def test_same_fix_in_other_words_joins_and_other_cause_stays_apart(self):
        # 10/13 같은 상황 실측 문구: 팬 정지를 두 사람이 다르게 적음 → 한 초안, 핀 막힘은 따로.
        self.service.record_handover(self.handover('HO-410', resolution=resolution(
            actions=['쿨러 팬 차단기 트립 확인 후 재투입', '팬 회전 확인', 'MES에서 조치 완료 후 재가동'])))
        out = self.service.record_handover(self.handover('HO-411', resolution=resolution(
            actions=['팬 차단기 올림', '팬 회전 방향·소음 확인', '재가동 후 유온 확인'])))
        self.assertEqual(out['draft']['reason'], 'supporting')
        out = self.service.record_handover(self.handover('HO-412', resolution=resolution(
            actions=['쿨러 핀 에어 블로우로 먼지 제거', '기름때 세척제로 닦음', '재가동 후 유온 확인'])))
        self.assertEqual(out['draft']['reason'], 'pending_review')
        self.assertEqual(len(self.draft()), 2)

    def test_resolution_mes_did_not_confirm_attaches_but_fills_nothing(self):
        self.service.record_handover(self.handover('HO-420', resolution=resolution(
            actions=['쿨러 팬 차단기 트립 확인 후 재투입', '팬 회전 확인'])))
        self.fault()
        out = self.service.record_handover(self.handover('HO-421', resolution=resolution(
            evidence=self.evidence_now(),
            actions=[{'action': '쿨러 팬 차단기 재투입', 'result': '팬 돌아서 해결된 듯'}])))
        self.assertEqual(out['draft'], {'created': False, 'reason': 'supporting', 'mes_recovered': False})
        row = self.draft()[0]
        self.assertEqual(row['card']['type_payload']['steps'][0]['expected_result'], PLACEHOLDER)
        self.assertEqual(row['review_flags']['completeness']['resolved_records'], 1)
        self.assertIn('해결 표기와 MES 불일치 HO-421', row['review_flags']['completeness']['operator'])


class FieldDraftHttpTests(unittest.TestCase):
    def test_get_lists_drafts_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            service = MesService(CATALOG, MesStorage(Path(directory) / 'mes.sqlite3'))
            handler = type('DraftHandler', (_Handler,), {'service': service})
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            worker = threading.Thread(target=server.serve_forever)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                body = json.dumps({'handover_id': 'HO-200', 'memo_text': 'memo', 'equipment_id': 'EQ-0001',
                                   'resolution': resolution()}).encode()
                with urlopen(Request(base + '/api/handover', body, {'Content-Type': 'application/json'}), timeout=5) as res:
                    # 실행 정보 없는 근거라 MES 복구 확인은 안 된다
                    self.assertEqual(json.load(res)['draft'], {'created': True, 'reason': 'pending_review', 'mes_recovered': False})
                with urlopen(base + '/api/card-drafts', timeout=5) as res:
                    listed = json.load(res)
                self.assertEqual(listed['drafts'][0]['status'], 'pending_review')
                self.assertEqual(listed['drafts'][0]['card']['card_id'], 'K-7000')
                with self.assertRaises(HTTPError) as caught:
                    urlopen(Request(base + '/api/card-drafts', b'{}', {'Content-Type': 'application/json'}), timeout=5)
                self.assertEqual(caught.exception.code, 404)
                caught.exception.close()
            finally:
                server.shutdown()
                worker.join()
                server.server_close()
                service.storage.close()


if __name__ == '__main__':
    unittest.main()
