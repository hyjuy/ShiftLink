"""현장 해결 기록 → 카드 초안: 빌더 규칙, 인계 저장과의 연결, GET 목록."""
import json
import tempfile
import threading
import unittest
from dataclasses import replace
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
        self.assertIn('해결 확인 기록', temp['review_flags']['completeness']['missing'])

    def test_completeness_lists_blanks_and_never_ready_from_one_record(self):
        out = build_draft('HO-13', resolution(actions=['차단기 재투입 후 냉각기 팬 확인', '작동유 온도 재확인']),
                          hpu_config(), 'EQ-0001', 'K-7000', NOW)
        done = out['review_flags']['completeness']
        self.assertEqual(done['missing'], ['단계 결과 ST-01'])
        self.assertEqual(done['operator'], ['부품 확인', '시나리오 확인', '안전 근거'])
        self.assertEqual((done['resolved_records'], done['ready']), (1, False))


class FieldDraftServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.service = MesService(CATALOG, MesStorage(Path(self.directory.name) / 'mes.sqlite3'))

    def tearDown(self):
        self.service.storage.close()
        self.directory.cleanup()

    def handover(self, handover_id, **extra):
        return {'handover_id': handover_id, 'memo_text': '작동유 온도 경보 처리', 'equipment_id': 'EQ-0001',
                'required_context': {}, 'attempts': [], 'observations': [], **extra}

    def count(self):
        return self.service.storage.connection.execute('SELECT COUNT(*) FROM card_drafts').fetchone()[0]

    def test_handover_creates_one_pending_draft_and_retry_does_not_duplicate(self):
        body = self.handover('HO-100', resolution=resolution())
        first = self.service.record_handover(body)
        self.assertEqual(first['draft'], {'created': True, 'reason': 'pending_review'})
        again = self.service.record_handover(body)
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['draft'], {'created': False, 'reason': 'already_exists'})
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
        self.assertEqual(failed['draft'], {'created': False, 'reason': 'attempt_only'})
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
        out = self.service.record_handover(self.handover('HO-301', resolution=second))
        self.assertEqual(out['draft'], {'created': False, 'reason': 'supporting'})
        [row] = self.draft()
        steps = row['card']['type_payload']['steps']
        self.assertEqual(steps[0]['expected_result'], '팬 풍량 회복')
        self.assertNotIn(PLACEHOLDER, [s['expected_result'] for s in steps])
        done = row['review_flags']['completeness']
        self.assertEqual((done['missing'], done['resolved_records'], done['ready']), ([], 2, True))
        self.assertEqual([s['source_id'] for s in row['card']['provenance']['sources']], ['HO-300', 'HO-301'])
        KnowledgeCard.model_validate(row['card'])
        again = self.service.record_handover(self.handover('HO-301', resolution=second))
        self.assertEqual(again['draft'], {'created': False, 'reason': 'already_exists'})
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
        self.assertEqual(out['draft'], {'created': False, 'reason': 'contradicting'})
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
                    self.assertEqual(json.load(res)['draft'], {'created': True, 'reason': 'pending_review'})
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
