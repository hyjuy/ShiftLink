"""Ephemeral MES server for the typed-report browser harness. Stop via stdin."""
import json
import hashlib
from dataclasses import asdict
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import MesStorage
from shiftlink.mes.accounts import Accounts
from shiftlink.agent.pipeline import FixedPipeline
from shiftlink.rag.retrieval import InMemoryToolProvider

with TemporaryDirectory(prefix='shiftlink-typed-report-') as directory:
    accounts=Accounts(Path(directory)/'accounts.json')
    salt=b'local-browser-test-only'
    accounts.path.write_text(json.dumps([{'id':'BROWSER-01','name':'로컬 검증 근무자','role':'operator',
        'salt':salt.hex(),'hash':hashlib.scrypt(b'local-browser-test-only',salt=salt,n=16384,r=8,p=1).hex()}]),encoding='utf-8')
    service=MesService(Path('docs/data/reference/00_plant_and_relations.json'),MesStorage(Path(directory)/'mes.sqlite3'))
    service.query_pipeline=FixedPipeline(model=lambda **kwargs: (_ for _ in ()).throw(AssertionError('No external model')),
        tools=InMemoryToolProvider(cards=[],equipment_db=service.catalog.data['equipment'],equipment_types=service.catalog.data['equipment_types']))
    handler=type('BrowserReportHandler',(_Handler,),{'service':service,'accounts':accounts,'web_root':Path('shiftlink/mes/web'),
        'log_message':lambda *args:None})
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    worker=Thread(target=server.serve_forever);worker.start()
    print(json.dumps({'port':server.server_port,'equipment':[asdict(eq) for eq in service.active_config.equipment]}),flush=True)
    try:
        input()
    finally:
        server.shutdown();worker.join();server.server_close();service.storage.close()
