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
const {createHistory, acceptSnapshot, acceptEvents, connectionState, stateClass} = require('./shiftlink/mes/web/app.js');
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
assert.equal(connectionState(1000, 2000, 'running'), '연결됨');
assert.equal(connectionState(1000, 12000, 'running'), '데이터 수신 지연');
assert.equal(connectionState(1000, 2000, 'paused'), '연결됨 · 일시정지');
assert.equal(stateClass({fault_level:'warning',operating_state:'running'}), 'warning');
assert.equal(stateClass({fault_level:'normal',operating_state:'waiting'}), 'waiting');
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
const document = { querySelector(selector) { if (!elements.has(selector)) elements.set(selector, {}); return elements.get(selector); }, querySelectorAll() {return [];} };
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
        self.assertIn(".status-label", css)
        self.assertIn(".equipment", css)


if __name__ == "__main__":
    unittest.main()
