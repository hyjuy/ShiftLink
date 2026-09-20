"""Executable browser-view logic checks without a front-end dependency."""
from pathlib import Path
import subprocess
import unittest


class RecoveryWebTests(unittest.TestCase):
    def test_recovery_and_component_visual_states(self):
        result = subprocess.run(["node", "-e", r'''
const assert = require('node:assert/strict');
const {recoveryView, componentView} = require('./shiftlink/mes/web/app.js');
const plan = {title:'감속기 과열',stage:'actions',actions:[
 {action_id:'inspect',title:'점검',detail:'확인',completed:false},
 {action_id:'repair',title:'정비',detail:'복구',completed:false}]};
let view = recoveryView({recovery:plan}, true);
assert.match(view, /data-action="inspect"/);
assert.doesNotMatch(view, /data-action="repair"/);
assert.match(view, /aria-current="step"/);
assert.doesNotMatch(recoveryView({recovery:plan}, false), /data-action=/);
assert.match(recoveryView({recovery:{...plan,stage:'completed'}},true), /정상 복귀 완료/);
assert.match(recoveryView({},true), /시나리오/);
const components = [{equipment_id:'x',component_id:'seal',name:'씰',health_percent:25,operating_seconds:3600,maintenance_count:1}];
view = componentView({components}, 'x');
assert.match(view, /25/); assert.match(view, /점검 필요/); assert.match(view, /meter/);
assert.match(componentView({},'x'), /기록 없음/);
assert.doesNotMatch(componentView({components},'other'), /25/);
console.log('Recovery visualization assertions passed');
'''], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
