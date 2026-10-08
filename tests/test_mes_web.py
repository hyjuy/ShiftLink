from pathlib import Path
import unittest
import shutil
import subprocess


WEB = Path(__file__).resolve().parents[1] / "shiftlink" / "mes" / "web"


class MesWebTests(unittest.TestCase):
    def test_dashboard_assets_describe_the_mes_operator_flow(self) -> None:
        """The dependency-free dashboard exposes the required operator regions."""
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="line-map"', html)
        self.assertIn('id="utility-links"', html)
        self.assertIn('id="equipment-detail"', html)
        self.assertIn('id="alarm-list"', html)
        self.assertIn('id="event-list"', html)
        self.assertIn('id="control-panel"', html)
        self.assertIn('id="scenario"', html)
        self.assertIn('id="synthetic-notice"', html)
        self.assertIn('aria-live="polite"', html)

    def test_flow_and_demo_controls_share_one_operator_workspace(self) -> None:
        html = (WEB / "index.html").read_text(encoding="utf-8")
        # 시연 제어는 서랍이 아니라 탭 아래 한 줄 바로 늘 보인다
        self.assertIn('id="control-panel"', html)
        self.assertIn('id="run-toggle"', html)
        self.assertNotIn('id="control-drawer"', html)
        self.assertIn('id="operations-table"', html)
        self.assertNotIn('id="tab-setup"', html)

    def test_dashboard_uses_only_documented_observation_and_control_apis(self) -> None:
        script = (WEB / "app.js").read_text(encoding="utf-8")
        for endpoint in ("/api/state", "/api/events", "/api/config", "/api/control"):
            self.assertIn(endpoint, script)
        self.assertIn("fetch(", script)
        self.assertIn("is_synthetic", script)
        self.assertIn("connectionState", script)
        self.assertIn("pause", script)
        self.assertIn("snapshot.coils", script)
        self.assertIn("config?.equipment", script)
        self.assertIn('control("scenario"', script)

    def test_event_cursor_is_separate_from_the_current_snapshot_sequence(self) -> None:
        """Events emitted with the displayed snapshot must not be skipped."""
        script = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("history.cursor", script)
        self.assertNotIn("after_sequence=${snapshot.sequence}", script)
        self.assertIn("history.cursor = Math.max", script)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for JavaScript behavior checks")
    def test_javascript_history_and_connection_behavior(self) -> None:
        result = subprocess.run(["node", "-e", r'''
const assert = require('node:assert/strict');
const {createHistory, acceptSnapshot, acceptEvents, connectionState, stateClass, equipmentKind, machineMoving, processMessage, operationRows, operationMetrics, metricWindow, eventText} = require('./shiftlink/mes/web/app.js');
assert.match(metricWindow({line_mode:'paused'}, []), /일시정지.*운전 재개 후 집계/);
assert.match(metricWindow({line_mode:'stopped'}, []), /운전 정지.*운전 시작 후 집계/);
assert.match(metricWindow({line_mode:'running'}, []), /집계 중 \(0\/10회\)/);
assert.equal(eventText({event_type:'alarm_raised',equipment_id:'x'}, {equipment:[{equipment_id:'x',code:'GR-01'}]}), '알람 발생 · GR-01');
assert.equal(equipmentKind({profile_id:'hpu', code:'CUSTOM-01'}), 'hpu');
assert.equal(equipmentKind({profile_id:'custom', code:'HPU-01'}), 'generic', 'unknown profile must not invent equipment internals');
assert.equal(equipmentKind({code:'RT-01'}), 'rt');
const running = {operating_state:'running', fault_level:'normal'};
assert.equal(machineMoving({line_mode:'running'}, running, true), true);
assert.equal(machineMoving({line_mode:'paused'}, running, true), false);
assert.equal(machineMoving({line_mode:'running'}, running, false), false, 'paused replay and animation toggle stop motion');
assert.equal(machineMoving({line_mode:'running'}, {...running, operating_state:'waiting'}, true), false);
assert.equal(machineMoving({line_mode:'running'}, {...running, fault_level:'critical'}, true), false);
const message = processMessage({line_mode:'running', equipment:[{equipment_id:'h', operating_state:'stopped', fault_level:'critical'}, {equipment_id:'r', operating_state:'waiting', fault_level:'normal'}]}, {equipment:[{equipment_id:'h',code:'HPU-01'}, {equipment_id:'r',code:'RT-01'}]});
assert.match(message, /HPU-01에 자체 이상/);
assert.match(message, /RT-01은 대기/);
assert.match(processMessage({line_mode:'paused'}, {}), /움직임도 멈춥니다/);
const h = createHistory();
acceptSnapshot(h, {run_id:'old', sequence:12});
const events = ['scenario_selected','alarm_raised'].map(event_type => ({run_id:'old', sequence:12, event_type}));
assert.equal(acceptEvents(h, {run_id:'old', events}), true);
assert.equal(h.events.length, 2, 'same-tick distinct events survive');
acceptEvents(h, {run_id:'old', events});
assert.equal(h.events.length, 2, 'boundary tick refetch deduplicates');
acceptSnapshot(h, {run_id:'new', sequence:0});
assert.equal(h.events.length, 0); assert.equal(h.cursor, -1); assert.equal(h.snapshots.length, 1);
assert.equal(acceptEvents(h, {run_id:'old', events}), false, 'in-flight prior-run response rejected');
assert.equal(h.events.length, 0);
acceptEvents(h, {run_id:'new', events:[{run_id:'new',sequence:1,event_type:'started'}]});
assert.equal(h.cursor, 1);
assert.equal(connectionState(1000, 2000, 'running'), '실시간 수신 중');
assert.equal(connectionState(1000, 12000, 'running'), '데이터 수신 지연');
assert.equal(connectionState(1000, 2000, 'paused'), '실시간 수신 중 · 운전 일시정지');
assert.equal(stateClass({fault_level:'warning',operating_state:'running'}), 'warning');
assert.equal(stateClass({fault_level:'normal',operating_state:'waiting'}), 'waiting');
const rows = operationRows({equipment:[{equipment_id:'EQ-1', operating_state:'waiting', fault_level:'normal'}], coils:[{equipment_id:'EQ-1'}], active_alarms:[{equipment_id:'EQ-1', severity:'warning', code:'AL-X', label:'경보 이름'}], measurements:[{equipment_id:'EQ-1', signal:'cycle_time', value:12, unit:'s'}]}, {equipment:[{equipment_id:'EQ-1', code:'RT-01', name:'Roller', dwell_seconds:10}], route:['EQ-1']});
assert.deepEqual(rows[0], {equipment_id:'EQ-1', name:'RT-01', status:'waiting', faultLevel:'normal', onRoute:true, throughput:null, utilization:null, queue:1, cycleTime:'12 s', alerts:1, alarmLabel:'경보 이름', changed:true});
// 계산 지표: 20 스냅샷(1초 간격) 중 RT 가 15번 가동, 코일 C1 은 5초 머물고 다음 설비로, C0 은 창 시작부터 있다가 떠남
const snaps = Array.from({length:20}, (_, i) => ({simulated_at:new Date(Date.UTC(2026,0,1,0,0,i)).toISOString(),
  equipment:[{equipment_id:'RT', operating_state: i < 15 ? 'running' : 'stopped', fault_level:'normal'}],
  coils:[...(i < 3 ? [{coil_id:'C0', equipment_id:'RT'}] : []), ...(i >= 5 && i < 10 ? [{coil_id:'C1', equipment_id:'RT'}] : i >= 10 ? [{coil_id:'C1', equipment_id:'CV'}] : [])]}));
const m = operationMetrics(snaps);
assert.equal(m.RT.utilization, 75);
assert.equal(m.RT.throughput, 2);
assert.equal(m.RT.cycle, 5, 'C0 은 들어온 시각을 몰라 머문 시간에서 뺀다');
assert.equal(m.CV.throughput, 0, '창 끝까지 머문 코일은 처리량이 아니다');
assert.equal(operationMetrics(snaps.map(x => ({...x, equipment:[...x.equipment, {equipment_id:'GR', operating_state:'stopped', fault_level:'critical'}]}))).GR.utilization, 0, '내내 멈춘 설비는 0%');
assert.deepEqual(operationMetrics(snaps.slice(0, 5)), {}, '표본이 적으면 계산하지 않는다');
acceptEvents(h, {run_id:'new',events:[{run_id:'new', sequence:2, event_type:'coil_exited'}]});
acceptEvents(h, {run_id:'new',events:[{run_id:'new', sequence:2, event_type:'coil_exited'}]});
assert.equal(h.completed, 1, 'boundary replay does not inflate throughput');
acceptSnapshot(h, {run_id:'third',sequence:0});
assert.equal(h.completed, 0);
console.log('JavaScript behavior assertions passed');
'''], cwd=WEB.parents[2], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is needed for JavaScript behavior checks")
    def test_initial_connection_failure_is_retried(self) -> None:
        result = subprocess.run(["node", "-e", r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
let calls = 0, interval;
const elements = new Map();
const document = { addEventListener() {}, querySelector(selector) { if (!elements.has(selector)) elements.set(selector, {addEventListener() {}}); return elements.get(selector); }, querySelectorAll() {return [];} };
vm.runInNewContext(fs.readFileSync('./shiftlink/mes/web/app.js', 'utf8'), {
 document, fetch: async () => { calls++; throw new Error('offline'); }, AbortSignal,
 setInterval(callback) { interval = callback; }, Date, console
});
(async () => {
 await new Promise(setImmediate);
 assert.equal(calls, 1);
 assert.match(elements.get('#connection-status').textContent, /offline/);
 interval(); await new Promise(setImmediate);
 assert.equal(calls, 2, 'first failure must not disable future polling');
})().catch(error => { console.error(error); process.exitCode = 1; });
'''], cwd=WEB.parents[2], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dashboard_style_is_responsive_and_has_non_color_status_cues(self) -> None:
        css = (WEB / "style.css").read_text(encoding="utf-8")
        self.assertIn("@media", css)
        self.assertIn(".conn-status", css)
        self.assertIn(".equipment", css)


if __name__ == "__main__":
    unittest.main()
