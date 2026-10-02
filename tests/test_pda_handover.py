"""PDA retries keep the ID after a lost acknowledgement."""
import subprocess
import unittest


class PdaHandoverTests(unittest.TestCase):
    def test_retry_keeps_payload_and_only_clears_after_acknowledgement(self):
        result = subprocess.run(['node', '-e', r'''
const assert = require('node:assert/strict');
const {submitHandover} = require('./shiftlink/mes/web/pda.js');
const values = new Map();
const store = {getItem:k=>values.get(k)||null, setItem:(k,v)=>values.set(k,v), removeItem:k=>values.delete(k)};
const note = {memo_text:'Check GR-01', required_context:{recipient_role:'night'}};
let sent;
const fail = async (path, init) => { sent = JSON.parse(init.body); throw new Error('lost acknowledgement'); };
(async () => {
  await assert.rejects(submitHandover(note, fail, store), /lost acknowledgement/);
  assert.ok(sent.handover_id);
  const first = sent;
  await assert.rejects(submitHandover({...note,memo_text:'changed'}, fail, store), /pending/);
  const ok = async (path, init) => {assert.equal(path,'/api/handover');assert.deepEqual(JSON.parse(init.body),first);return {ok:true,json:async()=>({handover_id:first.handover_id,duplicate:true})};};
  await submitHandover(note, ok, store);
  assert.equal(values.size,0);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
