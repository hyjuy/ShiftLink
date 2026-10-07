const assert = require('node:assert/strict');
const { stopFaceCamera } = require('../shiftlink/mes/web/pda.js');
// 10/7: faceRun was declared inside the browser-only block, so stopFaceCamera (used by every show()) threw
// ReferenceError and the face screen never opened the camera or left after the bypass/pass.
assert.doesNotThrow(() => { stopFaceCamera(); stopFaceCamera(); });
console.log('PDA face camera scope PASS');
