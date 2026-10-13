const assert = require('node:assert/strict');
const {homeEquipmentSummary} = require('../shiftlink/mes/web/pda.js');
const equipment = [{equipment_id:'EQ-1'}, {equipment_id:'EQ-2'}];
const faults = [{eq:equipment[0]}, {eq:equipment[0]}, {eq:{equipment_id:'outside-config'}}];
assert.deepEqual(homeEquipmentSummary(equipment, faults, true), {total:2,normal:1,abnormal:1});
assert.deepEqual(homeEquipmentSummary(equipment, faults, false), {total:2,normal:null,abnormal:null}, 'unavailable data must not imply normal equipment');
assert.deepEqual(homeEquipmentSummary(equipment, [], true), {total:2,normal:2,abnormal:0});
assert.deepEqual(homeEquipmentSummary([], [], true), {total:0,normal:0,abnormal:0});
console.log('PDA live home overview PASS');
