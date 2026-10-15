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
        for field,value in [('equipment',[]),('story',' '),('candidate','yes')]:
            note=deepcopy(self.note);note['work_report']['records'][0][field]=value;variants.append(note)
        note=deepcopy(self.note);note['work_report']['records'][0]['causes'][0]['equipment']=['UNKNOWN'];variants.append(note)
        for path in ['/api/work-reports','/api/handover']:
            for note in variants:
                with self.subTest(path=path,note=note):
                    with self.assertRaises(HTTPError) as caught: self.request(path,note)
                    self.assertEqual(caught.exception.code,400);caught.exception.close()
        self.assertEqual(self.service.storage.pending_handovers(),[])
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

if __name__=='__main__':unittest.main()
