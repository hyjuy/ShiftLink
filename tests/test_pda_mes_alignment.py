"""PDA screen reads the MES configuration, live observations and kb cards with MesCardAdapter's rules."""

import json
from pathlib import Path
import subprocess
import tempfile
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from shiftlink.mes import configuration
from shiftlink.mes.server import MesService, _Handler, kb_cards

CATALOG = Path('docs/data/reference/00_plant_and_relations.json')


def test_server_serves_pda_and_only_searchable_cards():
    service = MesService(CATALOG)
    handler = type('TestHandler', (_Handler,), {'service': service, 'web_root': Path('shiftlink/mes/web')})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    worker = threading.Thread(target=server.serve_forever)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        assert b'/static/pda.js' in urlopen(base + '/pda.html', timeout=5).read()
        assert b'equipmentFrom' in urlopen(base + '/static/pda.js', timeout=5).read()
        body = json.load(urlopen(base + '/api/kb/cards', timeout=5))
    finally:
        server.shutdown(); worker.join(); server.server_close(); service.storage.close()
    assert body['is_synthetic'] and body['cards']
    assert {(c['status'], c['split'], c['grade']) for c in body['cards']} == {('accepted', 'kb', 'L1')}
    assert isinstance(body['handovers'], list)
    assert body['basis_records']['AX-0102']['detail']
    assert body['basis_records']['OC-0101']['post_measurements']
    assert body['basis_records']['AC-0101']['title']
    ids = {basis for h in body['handovers'] for item in h['open_items'] for basis in item['basis_ids']}
    assert set(body['basis_records']) <= ids
    assert 'eval_items' not in body



def test_pda_uses_live_mes_observations_and_derived_states():
    service = MesService(CATALOG)
    try:
        service.control({'command': 'start'})
        service.tick()
        service.control({'command': 'scenario', 'scenario_id': 'sensor_anomaly_EQ-0001_hpu_filter_dp'})
        for _ in range(3):
            service.tick()
        fixture = {'config': configuration.to_payload(service.active_config), 'catalog': service.catalog.data,
                   'state': service.state(), 'cards': kb_cards()['cards']}
    finally:
        service.storage.close()
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(fixture, f, ensure_ascii=False, default=str)
    result = subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const fx = JSON.parse(require('node:fs').readFileSync(process.argv[1], 'utf8'));
const pda = require('./shiftlink/mes/web/pda.js');
const {S} = pda;
S.equipment = pda.equipmentFrom(fx.config, fx.catalog);
S.cards = fx.cards;
const hpu = S.equipment.find(e => e.code === 'HPU-01');
assert.equal(hpu.type, 'HPU');
assert.ok(hpu.signals.length > 10, 'configured signals, not only catalog measurement points');
S.eq = hpu;
const r = pda.usableReadings(fx.state, hpu);
S.observations = r.kept;
const dp = S.observations.find(o => o.signal === 'hpu_filter_dp');
assert.ok(dp && dp.value > 1.2, 'injected anomaly is read from MES');
assert.match(pda.obsView(dp).text, /▲ 상한 1.2 대비/);
assert.equal(pda.evalCondition({signal:'hpu_filter_dp_state', op:'==', value:'high'}).state, 'match');
assert.equal(pda.evalCondition({signal:'hpu_filter_dp', op:'>', value:1.2, unit:'psi'}).state, 'unknown', 'unit mismatch stays unverified');
assert.equal(pda.stateOf({min:0, max:1.2}, 1.2), 'normal', 'boundary is normal');
const ranked = pda.rankCards(hpu);
assert.ok(ranked.actions.length + ranked.safety.length + ranked.excluded.length === ranked.total);
assert.ok(S.cards.filter(c => c.equipment === 'CV').every(c => !pda.cardFits(c, hpu)));
assert.ok(S.cards.some(c => c.equipment === 'COMMON' && pda.cardFits(c, hpu)));
const top = ranked.actions[0];
assert.match(top.why, /조건 일치/, 'a card whose MES condition holds ranks first');
// A stale manual sample is excluded, like MesCardAdapter.
const visc = hpu.signals.find(s => s.signal === 'fluid_viscosity');
if (visc) {
  const old = JSON.parse(JSON.stringify(fx.state));
  old.measurements.filter(m => m.equipment_id === hpu.equipment_id && m.signal === 'fluid_viscosity')
    .forEach(m => { m.observed_at = '2000-01-01T00:00:00+00:00'; });
  assert.ok(pda.usableReadings(old, hpu).excluded.includes('fluid_viscosity'));
}
''', f.name], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8')
    Path(f.name).unlink()
    assert result.returncode == 0, result.stdout + result.stderr


def test_stopped_zero_is_not_highlighted_but_still_low_for_conditions():
    result = subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const pda = require('./shiftlink/mes/web/pda.js');
pda.S.eq = {signals:[{signal:'hpu_flow', unit:'L_min', min:38, max:46, zeroStopped:true, semantics:{}}]};
pda.S.mes = {operating:'stopped'};
const o = {signal:'hpu_flow', value:0, unit:'L_min'};
assert.deepEqual(pda.obsView(o), {st:'stopped', text:''});
pda.S.observations = [o];
assert.equal(pda.evalCondition({signal:'hpu_flow_state', op:'==', value:'low'}).state, 'match');
pda.S.mes = {operating:'running'};
assert.match(pda.obsView(o).text, /▼ 하한 38/);
'''], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr


def test_unknown_operator_stays_unverified():
    result = subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const pda = require('./shiftlink/mes/web/pda.js');
pda.S.eq = {signals:[{signal:'x', unit:'A', min:0, max:1, semantics:{}}]};
pda.S.observations = [{signal:'x', value:2, unit:'A'}];
assert.equal(pda.evalCondition({signal:'x', op:'in', value:[2]}).state, 'unknown');
assert.match(pda.evalCondition({signal:'x', op:'>=', value:1}).text, /≥/);
'''], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
