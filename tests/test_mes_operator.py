"""Operator map must preserve topology and distinguish observations from assumptions."""
import json
from pathlib import Path
import subprocess
import unittest

from shiftlink.mes.server import MesService


class OperatorViewTests(unittest.TestCase):
    def test_topology_fault_parts_evidence_and_accessible_graph(self):
        service = MesService(Path("docs/00_plant_and_relations.json"))
        self.addCleanup(service.storage.close)
        examples = {}
        for scenario in ("normal", "drive_fault", "hydraulic_fault", "downstream_block", "gearbox_overheat", "hydraulic_overheat", "gearbox_leak", "coil_quality_hold"):
            service.control({"command": "reset"}); service.control({"command": "start"})
            if scenario != "normal":
                service.control({"command": "scenario", "scenario_id": scenario})
            service.tick()
            examples[scenario] = service.state()
        for action in service.state()["recovery"]["actions"]:
            service.control({"command": "recovery_action", "action_id": action["action_id"]})
            service.tick()
        service.control({"command": "recover"}); service.tick()
        examples["stabilizing"] = service.state()
        service.tick(); examples["completed"] = service.state()
        result = subprocess.run(["node", "-e", r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {buildOperatorModel, flowView, incidentView, evidenceView, partView} = require('./shiftlink/mes/web/operator.js');
const {config, examples} = JSON.parse(fs.readFileSync(0, 'utf8'));
const id = code => config.equipment.find(e=>e.code===code).equipment_id;
const configured=[...config.relations,...config.branches];
assert.equal(configured.length,19);
assert.deepEqual(configured.filter(l=>l.relation_type==='material_flow').map(l=>[l.from_id,l.to_id]),[
 ['EQ-0006','EQ-0007'],['EQ-0007','EQ-0008'],['EQ-0008','EQ-0009'],['EQ-0008','EQ-0010']]);
assert.deepEqual(configured.filter(l=>l.relation_type==='interlock').map(l=>[l.from_id,l.to_id]),[
 ['EQ-0009','EQ-0008'],['EQ-0010','EQ-0008']]);
const simultaneous=flowView(buildOperatorModel(examples.normal,config,'EQ-0007')).match(/<g class="flow-edge [^>]*data-type="co_occurrence"[\s\S]*?<\/g>/)[0];
assert.match(simultaneous,/RT-02 ↔ RT-03/);assert.doesNotMatch(simultaneous,/marker-end/);
// All filters are emphasis controls: visibility is material + direct selection only.
for (const selected of [null, ...config.equipment.map(e=>e.equipment_id)]) {
 for (const filter of ['related','affected','material','all','power_supply']) {
  const model=buildOperatorModel(examples.hydraulic_fault,config,selected);
  assert.equal(model.selected?.equipment_id ?? null,selected,'no implicit selection');
  const html=flowView(model,'learn',filter);
  const actual=[...html.matchAll(/data-relation="([^"]+)"/g)].map(m=>m[1]).sort();
  const expected=model.links.filter(l=>l.relation_type==='material_flow'||[l.from_id,l.to_id].includes(selected)).map(l=>`${l.from_id}|${l.to_id}|${l.relation_type}`).sort();
  assert.deepEqual(actual,expected,`${selected}/${filter}: exact configured visibility`);
  const map=require('./shiftlink/mes/web/operator.js').layout(model);
  assert.ok(map.height<=750,'baseline overview must fit a compact three-row map');
  const segments=[];
  for(const edge of html.matchAll(/<path class="edge-line" d="([^"]+)"/g)) {
   const points=[...edge[1].matchAll(/[ML]([\d.-]+) ([\d.-]+)/g)].map(p=>[+p[1],+p[2]]);
   for(let i=1;i<points.length;i++) {
    const [a,b]=[points[i-1],points[i]];
    for(const n of map.nodes) {
     const hit=a[0]===b[0]?a[0]>n.x-101&&a[0]<n.x+101&&Math.max(a[1],b[1])>n.y-46&&Math.min(a[1],b[1])<n.y+106:a[1]>n.y-46&&a[1]<n.y+106&&Math.max(a[0],b[0])>n.x-101&&Math.min(a[0],b[0])<n.x+101;
     assert.equal(hit,false,`${selected}: rendered edge clears ${n.equipment_id}`);
    }
    for(const [c,d] of segments) {
     const v=a[0]===b[0],w=c[0]===d[0],axis=v?1:0;
     if(v===w&&a[1-axis]===c[1-axis])assert.ok(Math.min(Math.max(a[axis],b[axis]),Math.max(c[axis],d[axis]))<=Math.max(Math.min(a[axis],b[axis]),Math.min(c[axis],d[axis])),'no shared line segment');
    }
    segments.push([a,b]);
   }
  }
 }
}
let m = buildOperatorModel(examples.hydraulic_fault, config, id('RT-02'));
assert.equal(m.links.filter(l=>l.affected).length,4);
assert.ok(m.links.filter(l=>l.affected).every(l=>l.from_id===id('HPU-01')));
assert.ok(!m.links.some(l=>l.affected && l.to_id===id('CV-02')));
assert.equal(m.nodes.find(n=>n.equipment_id===id('CV-02')).group,'branch');
assert.ok(m.links.some(l=>l.relation_type==='material_flow' && l.to_id===id('CV-02')));
assert.equal(m.selected.operating_state,'waiting');
assert.equal(m.selected.fault_level,'normal');
assert.match(evidenceView(m), /HPU-01/);
m = buildOperatorModel(examples.drive_fault, config, id('GR-01'));
assert.equal(m.links.filter(l=>l.affected).length,2);
m = buildOperatorModel(examples.downstream_block, config, id('CV-01'));
assert.ok(m.links.some(l=>l.affected && l.relation_type==='interlock' && l.to_id===id('RT-03')));
m = buildOperatorModel(examples.gearbox_overheat,config,id('GR-01'));
assert.equal(m.problemPart,'cooling');
assert.match(partView(m),/가정/);
assert.match(partView(m),/data-part="cooling"/);
assert.match(evidenceView(m),/85/);
assert.match(evidenceView(m),/62/);
let graph = flowView(m, 'learn', 'related');
assert.match(graph,/role="button"/); assert.match(graph,/tabindex="0"/);
assert.match(graph,/data-equipment=/); assert.match(graph,/aria-pressed=/);
assert.match(graph,/marker-end=/); assert.match(graph,/물류 분기/);
assert.match(graph,/class="machine-illustration"/);
assert.match(graph,/class="rotor"/);
assert.match(graph,/class="belt-motion"/);
assert.match(graph,/class="supply-motion"/);
assert.match(graph,/data-coil=/);
const moved=JSON.parse(JSON.stringify(examples.normal));
moved.coils.forEach(c=>{c.position=Math.min(1,c.position+0.05);});
assert.equal(flowView(buildOperatorModel(moved,config,id('RT-01'))),flowView(buildOperatorModel(examples.normal,config,id('RT-01'))),'position updates must not rebuild machine animation nodes');
assert.match(incidentView(m),/GR-01/);
m = buildOperatorModel(examples.coil_quality_hold,config,id('RT-01'));
assert.equal(m.faults.length,0); assert.equal(m.held.length,3);
assert.match(incidentView(m),/보류/);
const broken = JSON.parse(JSON.stringify(examples.gearbox_overheat));
broken.measurements = broken.measurements.filter(m=>m.signal!=='gr_brg_temp');
assert.match(evidenceView(buildOperatorModel(broken,config,id('GR-01'))),/관측 없음/);
const unknown = buildOperatorModel(examples.gearbox_overheat,null,id('GR-01'));
assert.equal(unknown.links.length,0); assert.match(flowView(unknown,'learn','related'),/구성 미보존/);
// A normal-band crossing is evidence to check, not a new authoritative fault.
const normal = JSON.parse(JSON.stringify(examples.normal));
normal.measurements.find(x=>x.equipment_id===id('GR-01') && x.signal==='gr_brg_temp').value=100;
assert.equal(buildOperatorModel(normal,config,id('GR-01')).faults.length,0);
assert.match(flowView(buildOperatorModel(examples.stabilizing,config,id('RT-01'))),/복구 관찰/);
assert.doesNotMatch(flowView(buildOperatorModel(examples.stabilizing,config,id('RT-01'))),/>↳ 영향 대기</);
assert.equal(buildOperatorModel(examples.completed,config,id('RT-01')).faults.length,0);
assert.equal(buildOperatorModel(examples.hydraulic_overheat,config,id('HPU-01')).problemPart,'cooling');
const noBand=JSON.parse(JSON.stringify(config));
noBand.equipment.find(e=>e.code==='GR-01').signals.forEach(s=>{s.normal_min=null;s.normal_max=null;});
assert.match(evidenceView(buildOperatorModel(normal,noBand,id('GR-01'))),/기준 없음 · 판정 불가/);
const inactive=JSON.parse(JSON.stringify(config));
inactive.equipment.find(e=>e.code==='GR-01').active=false;
assert.equal(buildOperatorModel(normal,inactive,id('GR-02')).cause,undefined);
const drive=JSON.parse(JSON.stringify(examples.drive_fault));
assert.equal(buildOperatorModel(drive,inactive,id('GR-02')).cause.equipment_id,id('GR-02'));
const {relationKey}=require('./shiftlink/mes/web/operator.js');
const hydraulic=buildOperatorModel(examples.hydraulic_fault,config,id('HPU-01'));
const key=relationKey(hydraulic.links.find(l=>l.affected && l.to_id===id('RT-02')));
assert.match(evidenceView(hydraulic,key),/선택 연결: HPU-01 → RT-02/);
assert.ok(flowView(hydraulic,'learn','related',key).includes(`data-relation="${key}" aria-pressed="true"`));
assert.equal(new Set(hydraulic.links.map(relationKey)).size,hydraulic.links.length);
const {layout,routePoints}=require('./shiftlink/mes/web/operator.js');
const placed=layout(hydraulic).nodes;
for (const link of hydraulic.links) {
 const a=placed.find(n=>n.equipment_id===link.from_id),b=placed.find(n=>n.equipment_id===link.to_id);
 const points=routePoints(a,b,link.relation_type);
 for(let i=1;i<points.length;i++) {
  const [x1,y1]=points[i-1],[x2,y2]=points[i];
  assert.ok(x1===x2 || y1===y2,'orthogonal path');
  for(const n of placed) {
   const left=n.x-101,right=n.x+101,top=n.y-46,bottom=n.y+106;
   const overlap=x1===x2 ? x1>left&&x1<right&&Math.max(y1,y2)>top&&Math.min(y1,y2)<bottom : y1>top&&y1<bottom&&Math.max(x1,x2)>left&&Math.min(x1,x2)<right;
   assert.equal(overlap,false,`${relationKey(link)} must clear ${n.equipment_id} plus 10px margin`);
  }
 }
}
console.log('Topology, isolation, part assumption, evidence, and graph checks passed');
'''], input=json.dumps({"config": service.config()["config"], "examples": examples}),
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_operator_controls_have_labels_and_work_area_contains_recovery(self):
        from tests.test_mes_ui_layout import Elements
        html = Path("shiftlink/mes/web/index.html").read_text(encoding="utf-8")
        dom = Elements(html)
        for identifier in ("experience-mode", "equipment-search", "relation-filter", "map-scale"):
            self.assertIn(identifier, dom.labels)
        self.assertIn("incident-summary", dom.ids)
        self.assertIn("part-locator", dom.ids)
        self.assertIn("selection-evidence", dom.ids)
        self.assertLess(html.index('id="recovery-panel"'), html.index('id="control-panel"'))

    def test_refresh_preserves_summary_and_exact_relation_focus(self):
        result = subprocess.run(["node", "tests/mes_operator_dom.cjs"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
