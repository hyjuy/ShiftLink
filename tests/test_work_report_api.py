import json
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import MesStorage
from shiftlink.pda.__main__ import make_handler

class WorkReportApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name) / 'mes.sqlite3'
        self.start()
        ids = [eq.equipment_id for eq in self.service.active_config.equipment[:2]]
        self.note = {'handover_id':'HO-REPORT-API', 'kind':'work_log', 'equipment_id':None, 'equipment_ids':ids,
            'memo_text':'추가 기록', 'required_context':{'author':'작업자','start_at':'2026-10-15T08:00','end_at':'2026-10-15T17:00','context':'MES 원본'},
            'work_report':{'legacy_memo':'','mes_context':'MES 원본','records':[{'type':'고장·정비','equipment':ids,'story':'점검',
                'causes':[{'equipment':ids[:1],'certainty':'확인','note':'오염'}], 'result':'인계', 'pms':'PMS-01','candidate':True}]}}
    def start(self):
        self.service = MesService(Path('docs/data/reference/00_plant_and_relations.json'), MesStorage(self.db))
        handler = type('ReportHandler', (_Handler,), {'service': self.service})
        self.server = ThreadingHTTPServer(('127.0.0.1',0),handler)
        self.worker=threading.Thread(target=self.server.serve_forever); self.worker.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'
    def stop(self):
        self.server.shutdown(); self.worker.join(); self.server.server_close(); self.service.storage.close()
    def tearDown(self):
        self.stop(); self.directory.cleanup()
    def request(self,path,body=None,base=None):
        req=Request((base or self.base)+path, json.dumps(body).encode() if body is not None else None, {'Content-Type':'application/json'})
        with urlopen(req,timeout=5) as response: return json.load(response)
    def test_durable_report_roundtrip_after_upload_and_restart(self):
        first=self.request('/api/work-reports',self.note)
        self.assertFalse(first['duplicate'])
        self.service.storage.mark_handover(self.note['handover_id'],'uploaded')
        self.stop(); self.start()
        reports=self.request('/api/work-reports')['reports']
        self.assertEqual(reports[0]['work_report'],self.note['work_report'])
        self.assertEqual(reports[0]['status'],'uploaded')
        self.assertEqual(self.request('/api/work-reports/HO-REPORT-API')['report']['work_report'],self.note['work_report'])
        self.assertTrue(self.request('/api/work-reports',self.note)['duplicate'])
        with self.assertRaises(HTTPError) as caught: self.request('/api/work-reports',{**self.note,'memo_text':'변경'})
        self.assertEqual(caught.exception.code,409);caught.exception.close()
    def test_invalid_records_rejected_on_both_save_routes(self):
        variants=[]
        for field,value in [('equipment',[]),('story',' '),('candidate','yes'),('occurred_at','not-a-date'),('occurred_at',123),('occurred_at','2026-10-15')]:
            note=deepcopy(self.note);note['work_report']['records'][0][field]=value;variants.append(note)
        note=deepcopy(self.note);note['work_report']['records'][0]['causes'][0]['equipment']=['UNKNOWN'];variants.append(note)
        for path in ['/api/work-reports','/api/handover']:
            for note in variants:
                with self.subTest(path=path,note=note):
                    with self.assertRaises(HTTPError) as caught: self.request(path,note)
                    self.assertEqual(caught.exception.code,400);caught.exception.close()
        self.assertEqual(self.service.storage.pending_handovers(),[])
    def test_occurrence_timestamp_roundtrip(self):
        self.note['work_report']['records'][0]['occurred_at'] = '2026-10-15T09:20'
        self.request('/api/work-reports',self.note)
        saved = self.request('/api/work-reports/HO-REPORT-API')['report']
        self.assertEqual(saved['work_report']['records'][0]['occurred_at'],'2026-10-15T09:20')
    def test_normal_report_and_missing_or_nonreport_detail(self):
        note=deepcopy(self.note);note['work_report']['records']=[];note['memo_text']='별도 작성 내용 없음'
        self.request('/api/work-reports',note)
        self.service.storage.save_handover({'handover_id':'HO-OTHER','memo_text':'인계'})
        for path in ['/api/work-reports/HO-OTHER','/api/work-reports/HO-MISSING']:
            with self.assertRaises(HTTPError) as caught: self.request(path)
            self.assertEqual(caught.exception.code,404);caught.exception.close()
        for query in ['limit=0','limit=101','limit=nope']:
            with self.assertRaises(HTTPError) as caught: self.request('/api/work-reports?'+query)
            self.assertEqual(caught.exception.code,400);caught.exception.close()
    def test_uploader_preserves_full_structured_report(self):
        from shiftlink.mes.uploader import upload_pending
        self.request('/api/work-reports', self.note)
        uploaded = []
        class Cursor:
            rowcount = 1
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def execute(self, sql, args):
                assert sql.startswith('INSERT IGNORE INTO handover_upload')
                uploaded.append(json.loads(args[-2]))
        class Connection:
            def cursor(self): return Cursor()
            def close(self): pass
        result = upload_pending(self.service.storage, Connection)
        self.assertEqual(result, {'uploaded': 1, 'conflict': 0, 'pending': 0})
        self.assertEqual(uploaded, [self.note])
        self.assertEqual(self.request('/api/work-reports')['reports'][0]['status'], 'uploaded')

    def test_pi_proxy_roundtrip(self):
        proxy=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.base))
        worker=threading.Thread(target=proxy.serve_forever);worker.start()
        try:
            base=f'http://127.0.0.1:{proxy.server_port}'
            self.request('/api/work-reports',self.note,base)
            self.assertEqual(self.request('/api/work-reports',base=base)['reports'][0]['work_report'],self.note['work_report'])
        finally: proxy.shutdown();worker.join();proxy.server_close()

    def test_fault_records_create_distinct_incidents_and_keep_candidate_intent(self):
        note = deepcopy(self.note)
        record = note['work_report']['records'][0]
        other = deepcopy(record)
        other['candidate'] = False
        note['work_report']['records'] += [other, {**deepcopy(record), 'type': 'PMS 정비'}]
        saved = self.request('/api/work-reports', note)
        links = saved['incidents']
        self.assertEqual([link['record_index'] for link in links], [0, 1])
        self.assertNotEqual(links[0]['incident_id'], links[1]['incident_id'])
        incident = self.request('/api/incidents/' + links[0]['incident_id'])['incident']
        self.assertEqual(incident['equipment_ids'], sorted(record['equipment']))
        self.assertEqual(incident['records'][0]['record'], record)
        self.assertEqual(incident['records'][0]['handover_id'], note['handover_id'])
        self.assertEqual(self.service.storage.list_card_drafts(), [])
        detail = self.request('/api/work-reports/' + note['handover_id'])['report']
        self.assertEqual(detail['incidents'], links)
        self.assertEqual(self.request('/api/work-reports')['reports'][0]['incidents'], links)
        self.assertEqual(self.service.storage.get_handover(note['handover_id'])['payload'], note)

    def test_incident_retry_restart_and_handover_route(self):
        saved = self.request('/api/handover', self.note)
        self.stop(); self.start()
        retry = self.request('/api/work-reports', self.note)
        self.assertTrue(retry['duplicate'])
        self.assertEqual(retry['incidents'], saved['incidents'])
        self.assertEqual(len(self.request('/api/incidents')['incidents']), 1)
        self.assertEqual(self.request('/api/incidents/' + saved['incidents'][0]['incident_id'])['incident']['records'][0]['record'],
                         self.note['work_report']['records'][0])

    def test_explicit_incident_continuation_and_same_equipment_new_fault(self):
        first = self.request('/api/work-reports', self.note)['incidents'][0]['incident_id']
        note = deepcopy(self.note)
        note['handover_id'] = 'HO-CONTINUED'
        note['work_report']['records'][0]['incident_id'] = first
        note['work_report']['records'][0]['followup_from'] = {'handover_id':self.note['handover_id'],'record_index':0}
        self.assertEqual(self.request('/api/work-reports', note)['incidents'][0]['incident_id'], first)
        self.assertEqual(len(self.request('/api/incidents/' + first)['incident']['records']), 2)
        note['handover_id'] = 'HO-NEW-FAULT'
        del note['work_report']['records'][0]['incident_id']
        del note['work_report']['records'][0]['followup_from']
        self.assertNotEqual(self.request('/api/work-reports', note)['incidents'][0]['incident_id'], first)

    def test_report_pages_keep_older_reports_reachable(self):
        for index in range(3):
            note=deepcopy(self.note);note['handover_id']=f'HO-PAGE-{index}'
            self.request('/api/work-reports',note)
        first=self.request('/api/work-reports?limit=2&offset=0')['reports']
        second=self.request('/api/work-reports?limit=2&offset=2')['reports']
        self.assertEqual(len(first),2);self.assertEqual(len(second),1)
        self.assertEqual(len({h['handover_id'] for h in first+second}),3)
        with self.assertRaises(HTTPError) as caught:self.request('/api/work-reports?offset=-1')
        self.assertEqual(caught.exception.code,400);caught.exception.close()

    def test_invalid_incident_reference_rolls_back_whole_report(self):
        from dataclasses import replace
        first = self.request('/api/work-reports', self.note)['incidents'][0]['incident_id']
        for suffix, change in [('unknown', {'incident_id': 'INC-missing'}),
                               ('equipment', {'incident_id': first, 'equipment': self.note['equipment_ids'][:1]}),
                               ('nonfault', {'incident_id': first, 'type': 'PMS 정비'}),
                               ('badtype', {'incident_id': 123}), ('blank', {'incident_id': ''})]:
            note = deepcopy(self.note)
            note['handover_id'] = 'HO-BAD-' + suffix
            note['work_report']['records'].append({**deepcopy(note['work_report']['records'][0]), **change,
                'followup_from':{'handover_id':self.note['handover_id'],'record_index':0}})
            with self.subTest(suffix=suffix):
                with self.assertRaises(HTTPError) as caught:
                    self.request('/api/work-reports', note)
                self.assertEqual(caught.exception.code, 400); caught.exception.close()
                self.assertIsNone(self.service.storage.get_handover(note['handover_id']))
                self.assertEqual(len(self.request('/api/incidents')['incidents']), 1)
        eq = self.service.active_config.equipment[0]
        self.service.active_config = replace(self.service.active_config,
            equipment=(replace(eq, asset_id=eq.asset_id + '-replacement'), *self.service.active_config.equipment[1:]))
        note = deepcopy(self.note); note['handover_id'] = 'HO-REPLACED'
        note['work_report']['records'][0]['incident_id'] = first
        note['work_report']['records'][0]['followup_from'] = {'handover_id':self.note['handover_id'],'record_index':0}
        with self.assertRaises(HTTPError) as caught: self.request('/api/work-reports', note)
        self.assertEqual(caught.exception.code, 400); caught.exception.close()
        self.assertIsNone(self.service.storage.get_handover(note['handover_id']))

    def test_nonfault_and_legacy_reports_do_not_gain_invented_incidents(self):
        self.service.storage.save_handover(self.note)
        self.assertEqual(self.request('/api/work-reports', self.note)['incidents'], [])
        note = deepcopy(self.note); note['handover_id'] = 'HO-PMS'
        note['work_report']['records'][0]['type'] = 'PMS 정비'
        self.assertEqual(self.request('/api/work-reports', note)['incidents'], [])
        self.assertEqual(self.request('/api/incidents')['incidents'], [])
        with self.assertRaises(HTTPError) as caught: self.request('/api/incidents/INC-missing')
        self.assertEqual(caught.exception.code, 404); caught.exception.close()
        for limit in ('0', '101', 'nope'):
            with self.assertRaises(HTTPError) as caught: self.request('/api/incidents?limit=' + limit)
            self.assertEqual(caught.exception.code, 400); caught.exception.close()

    def test_incident_creation_rolls_back_on_database_failure(self):
        self.service.storage.connection.execute(
            "CREATE TRIGGER reject_incident BEFORE INSERT ON incidents BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError): self.service.record_work_report(self.note)
        self.assertIsNone(self.service.storage.get_handover(self.note['handover_id']))
        self.assertEqual(self.service.incidents()['incidents'], [])

    def test_concurrent_retries_create_only_one_incident(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as workers:
            replies = list(workers.map(lambda _: self.request('/api/work-reports', self.note), range(4)))
        self.assertEqual(sum(not reply['duplicate'] for reply in replies), 1)
        self.assertTrue(all(reply['incidents'] == replies[0]['incidents'] for reply in replies))
        self.assertEqual(len(self.request('/api/incidents')['incidents']), 1)

    def test_legacy_database_upgrade_preserves_report_without_backfill(self):
        import sqlite3
        old_path = Path(self.directory.name) / 'legacy.sqlite3'
        with sqlite3.connect(old_path) as connection:
            connection.execute("CREATE TABLE handover_outbox (handover_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
                               "status TEXT NOT NULL DEFAULT 'pending', payload TEXT NOT NULL)")
            connection.execute("INSERT INTO handover_outbox VALUES (?, ?, 'uploaded', ?)",
                               (self.note['handover_id'], '2026-10-15T08:00:00+09:00',
                                json.dumps(self.note, ensure_ascii=False, sort_keys=True)))
        connection.close()
        storage = MesStorage(old_path)
        try:
            self.assertEqual(storage.get_handover(self.note['handover_id'])['payload'], self.note)
            self.assertEqual(storage.list_work_reports()[0]['incidents'], [])
            self.assertEqual(storage.list_incidents(), [])
            self.assertTrue(storage.save_work_report(self.note, {}, 'current')['duplicate'])
        finally:
            storage.close()

    def test_pi_proxy_exposes_incident_detail(self):
        proxy = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.base))
        worker = threading.Thread(target=proxy.serve_forever); worker.start()
        try:
            base = f'http://127.0.0.1:{proxy.server_port}'
            saved = self.request('/api/work-reports', self.note, base)
            incident_id = saved['incidents'][0]['incident_id']
            self.assertEqual(self.request('/api/incidents/' + incident_id, base=base)['incident']['incident_id'], incident_id)
        finally:
            proxy.shutdown(); worker.join(); proxy.server_close()

if __name__=='__main__':unittest.main()
