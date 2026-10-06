"""Isolated Jetson HTTP acceptance; never touches existing MES processes/data."""
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from shiftlink.mes.server import MesService, _Handler
from shiftlink.mes.storage import MesStorage

root = Path(__file__).resolve().parent
catalog = Path('docs/data/reference/00_plant_and_relations.json')
database = root / 'acceptance.sqlite3'


def start():
    service = MesService(catalog, MesStorage(database))
    handler = type('AcceptanceHandler', (_Handler,), {'service': service, 'web_root': Path('shiftlink/mes/web')})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    return service, server, worker


def stop(service, server, worker):
    server.shutdown()
    worker.join()
    server.server_close()
    service.storage.close()


def post(server, path, payload):
    request = Request(f'http://127.0.0.1:{server.server_port}' + path,
                      json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    with urlopen(request, timeout=150) as response:
        return json.load(response)


service, server, worker = start()
try:
    scan = post(server, '/api/equipment/scan', {'class': 'HPU', 'conf': .95, 'device_id': 'isolated-acceptance'})
    cards = json.loads(Path('docs/data/knowledge_cards/kb/kb_cards.json').read_text())['cards']
    question = next(c['title'] for c in cards if c['card_id'] == 'K-1001')
    answer = post(server, '/api/query', {'question': question, 'scan_id': scan['scan']['scan_id']})
    assert answer['answer'] and answer['cited_card_ids'], answer
    assert answer['safety_notices'] and not answer['review_queue'], answer
    assert answer['evidence']['equipment_id'] == scan['scan']['equipment_id']
    assert 'ground_truth' not in json.dumps(answer) and 'scenario_id' not in json.dumps(answer)
    model_call = service.query_pipeline.model.last_call
    assert model_call['model'] == 'exaone3.5:2.4b-instruct-q4_K_M'
    note = {'handover_id': 'HO-acceptance-5e64420', 'memo_text': 'HPU 인계 실기기 영속성 검증'}
    stored = post(server, '/api/handover', note)
finally:
    stop(service, server, worker)

service, server, worker = start()
try:
    retry = post(server, '/api/handover', note)
    assert retry['duplicate'] and retry['created_at'] == stored['created_at']
    assert service.storage.get_handover(note['handover_id'])['payload'] == note
    count = service.storage.connection.execute('SELECT COUNT(*) FROM handover_outbox WHERE handover_id=?',
                                               (note['handover_id'],)).fetchone()[0]
    assert count == 1
finally:
    stop(service, server, worker)

report = {'revision': '5e64420', 'query': answer, 'model_call': model_call,
          'handover_first': stored, 'handover_restart_retry': retry, 'outbox_rows': count,
          'scope': 'Isolated real Jetson HTTP server + actual Ollama exaone; recognition injected, physical PDA untested'}
(root / 'jetson-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({'passed': True, 'cited_card_ids': answer['cited_card_ids'],
                  'safety_notices': len(answer['safety_notices']), 'model_call': model_call,
                  'outbox_rows': count}, ensure_ascii=False))
